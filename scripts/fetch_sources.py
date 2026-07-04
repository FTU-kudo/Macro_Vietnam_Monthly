#!/usr/bin/env python3
"""
scripts/fetch_sources.py
─────────────────────────────────────────────────────────────
Bước 2: Fetch + cache 5 nguồn chính thức cho tháng báo cáo.

Output (trong --cache-dir):
  nso_{YYYY-MM}.html      ← Trang báo cáo KTXH từ gso.gov.vn
  pmi_{YYYY-MM}.html      ← Press release PMI từ S&P / VnEconomy
  customs_{YYYY-MM}.txt   ← Dữ liệu XNK từ customs.gov.vn
  vbma_{YYYY-MM}.pdf      ← PDF báo cáo tuần TTTP
  vbma_{YYYY-MM}.txt      ← Text extract từ PDF
  vnba_{YYYY-MM}.pdf      ← PDF VNBA tháng
  vnba_{YYYY-MM}.txt      ← Text extract từ PDF
  fetch_log.json          ← Log fetch của kỳ này
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Cấu hình ──────────────────────────────────────────────────
TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

VI_MONTHS = [
    "", "tháng 1", "tháng 2", "tháng 3", "tháng 4",
    "tháng 5", "tháng 6", "tháng 7", "tháng 8",
    "tháng 9", "tháng 10", "tháng 11", "tháng 12",
]
EN_MONTHS_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
EN_MONTHS_FULL = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def parse_month(month_str: str) -> tuple[int, int]:
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.year, dt.month


def pdf_to_text(pdf_path: Path, txt_path: Path) -> bool:
    """Dùng pdftotext (poppler-utils) để extract text từ PDF."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and txt_path.exists():
            size = txt_path.stat().st_size
            print(f"     📄 pdftotext OK — {size:,} bytes")
            return True
        else:
            print(f"     ⚠️  pdftotext failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"     ⚠️  pdftotext error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
# FETCH TỪNG NGUỒN
# ─────────────────────────────────────────────────────────────────

def fetch_nso(year: int, month: int, cache_dir: Path) -> dict:
    """
    NSO: Tìm và tải trang báo cáo KTXH tháng từ gso.gov.vn.
    Thử nhiều URL pattern khác nhau vì GSO không nhất quán.
    """
    source = "NSO"
    output_file = cache_dir / f"nso_{year}-{month:02d}.html"
    vi_month = VI_MONTHS[month]

    # Các URL có thể chứa báo cáo tháng
    candidate_urls = [
        # Pattern 1: URL chuẩn
        f"https://www.gso.gov.vn/bai-viet/thong-ke/tinh-hinh-kinh-te-xa-hoi/",
        # Pattern 2: Tìm từ trang chủ
        "https://www.gso.gov.vn/",
    ]

    # Tìm link bài viết cụ thể
    article_url = None
    for base_url in candidate_urls:
        try:
            r = requests.get(base_url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if (
                    ("kinh tế xã hội" in text or "ktxh" in text or "thong cao" in text)
                    and (vi_month in text or str(year) in text)
                ):
                    article_url = href if href.startswith("http") else f"https://www.gso.gov.vn{href}"
                    break
            if article_url:
                break
        except Exception:
            continue

    # Fetch bài viết tìm được hoặc trang danh mục
    fetch_url = article_url or candidate_urls[0]
    try:
        r = requests.get(fetch_url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            output_file.write_bytes(r.content)
            print(f"     ✅ NSO → {output_file.name} ({len(r.content):,} bytes)")
            return {
                "source": source, "status": "OK",
                "url": fetch_url, "file": str(output_file),
                "size_bytes": len(r.content),
            }
    except Exception as e:
        pass

    # Fallback: VnEconomy tổng hợp số liệu GSO
    fallback_url = f"https://vneconomy.vn/search/?q=tổng+cục+thống+kê+{vi_month}+{year}"
    try:
        r = requests.get(fallback_url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            output_file.write_bytes(r.content)
            print(f"     ⚠️  NSO (fallback VnEconomy) → {output_file.name}")
            return {
                "source": source, "status": "OK_FALLBACK",
                "url": fallback_url, "file": str(output_file),
            }
    except Exception as e:
        pass

    return {"source": source, "status": "FAIL", "error": "Không tải được NSO"}


def fetch_pmi(year: int, month: int, cache_dir: Path) -> dict:
    """
    PMI: S&P Global Vietnam Manufacturing PMI press release.
    Thử S&P chính thức, sau đó VnEconomy / CafeF.
    """
    source = "PMI"
    output_file = cache_dir / f"pmi_{year}-{month:02d}.html"
    en_month = EN_MONTHS_FULL[month]

    # S&P Global chính thức
    pmi_urls = [
        "https://www.pmi.spglobal.com/Survey/PressRelease/VN",
        f"https://www.pmi.spglobal.com/Survey/PressRelease/VN/{en_month}{year}",
    ]
    for url in pmi_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.text) > 1000:
                output_file.write_bytes(r.content)
                print(f"     ✅ PMI (S&P) → {output_file.name} ({len(r.content):,} bytes)")
                return {"source": source, "status": "OK", "url": url, "file": str(output_file)}
        except Exception:
            continue

    # Fallback: VnEconomy / CafeF
    fallback_urls = [
        f"https://vneconomy.vn/search/?q=PMI+Việt+Nam+{en_month}+{year}",
        f"https://cafef.vn/search/?q=PMI+Viet+Nam+{en_month}+{year}",
        f"https://tinnhanhchungkhoan.vn/search/?q=PMI+{en_month}+{year}",
    ]
    for url in fallback_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and "pmi" in r.text.lower():
                # Tìm link bài viết cụ thể
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    text = a.get_text(strip=True).lower()
                    href = a["href"]
                    if "pmi" in text and (en_month.lower() in text or str(year) in text):
                        article_url = href if href.startswith("http") else f"https://vneconomy.vn{href}"
                        try:
                            ar = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)
                            if ar.status_code == 200:
                                output_file.write_bytes(ar.content)
                                print(f"     ⚠️  PMI (fallback) → {output_file.name}")
                                return {
                                    "source": source, "status": "OK_FALLBACK",
                                    "url": article_url, "file": str(output_file),
                                }
                        except Exception:
                            continue
        except Exception:
            continue

    return {"source": source, "status": "FAIL", "error": "Không tải được PMI"}


def fetch_customs(year: int, month: int, cache_dir: Path) -> dict:
    """
    Customs: Thống kê XNK từ customs.gov.vn hoặc nguồn thứ cấp.
    """
    source = "Customs"
    output_file = cache_dir / f"customs_{year}-{month:02d}.txt"
    vi_month = VI_MONTHS[month]

    # Trang thống kê hải quan
    customs_url = "https://www.customs.gov.vn/index.jsp?pageIndex=1&category=27&cid=30"
    try:
        r = requests.get(customs_url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Tìm link bài viết tháng M
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"]
                if vi_month in text and (str(year) in text or str(year) in href):
                    article_url = href if href.startswith("http") else f"https://www.customs.gov.vn{href}"
                    try:
                        ar = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)
                        if ar.status_code == 200:
                            # Extract text
                            art_soup = BeautifulSoup(ar.text, "html.parser")
                            text_content = art_soup.get_text(separator="\n", strip=True)
                            output_file.write_text(text_content, encoding="utf-8")
                            print(f"     ✅ Customs → {output_file.name} ({len(text_content):,} chars)")
                            return {
                                "source": source, "status": "OK",
                                "url": article_url, "file": str(output_file),
                            }
                    except Exception:
                        continue
    except Exception:
        pass

    # Fallback: haiquanonline.com.vn
    try:
        fallback_url = f"https://haiquanonline.com.vn/?s=xuất+nhập+khẩu+{vi_month}+{year}"
        r = requests.get(fallback_url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            output_file.write_text(text_content, encoding="utf-8")
            print(f"     ⚠️  Customs (haiquanonline) → {output_file.name}")
            return {
                "source": source, "status": "OK_FALLBACK",
                "url": fallback_url, "file": str(output_file),
            }
    except Exception:
        pass

    return {"source": source, "status": "FAIL", "error": "Không tải được Customs"}


def fetch_vbma(year: int, month: int, cache_dir: Path) -> dict:
    """
    VBMA: PDF báo cáo tuần TTTP (tuần cuối tháng M).
    URL pattern: vbma.org.vn/storage/reports/[MonYYYY]/[dates] BAO CAO TUAN TTTP.pdf
    """
    source = "VBMA"
    en_abbr = EN_MONTHS_ABBR[month]  # "May", "Jun"...
    pdf_out = cache_dir / f"vbma_{year}-{month:02d}.pdf"
    txt_out = cache_dir / f"vbma_{year}-{month:02d}.txt"

    # Thử các tuần cuối tháng (ngày 22-31)
    week_ranges = [
        (25, 29), (24, 28), (26, 30), (27, 31), (23, 27), (22, 26),
    ]
    
    for start, end in week_ranges:
        # Clip end day nếu > ngày cuối tháng
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        end = min(end, last_day)

        pdf_url = (
            f"https://vbma.org.vn/storage/reports/"
            f"{en_abbr}{year}/"
            f"{start:02d}{month:02d}{year}-{end:02d}{month:02d}{year}"
            f"%20%20BAO%20CAO%20TUAN%20TTTP.pdf"
        )
        try:
            r = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
                with open(pdf_out, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                size = pdf_out.stat().st_size
                print(f"     ✅ VBMA PDF → {pdf_out.name} ({size:,} bytes) [{start}-{end}/{month}]")

                # Convert PDF → text
                if pdf_to_text(pdf_out, txt_out):
                    return {
                        "source": source, "status": "OK",
                        "url": pdf_url,
                        "pdf_file": str(pdf_out),
                        "txt_file": str(txt_out),
                        "week": f"{start:02d}-{end:02d}/{month:02d}",
                    }
        except Exception:
            continue

    # Fallback: trang báo cáo VBMA, lấy link mới nhất
    try:
        r = requests.get("https://vbma.org.vn/bao-cao", headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "BAO_CAO_TUAN" in href.upper() or "TTTP" in href.upper():
                    pdf_url = href if href.startswith("http") else f"https://vbma.org.vn{href}"
                    r2 = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
                    if r2.status_code == 200:
                        with open(pdf_out, "wb") as f:
                            for chunk in r2.iter_content(chunk_size=8192):
                                f.write(chunk)
                        pdf_to_text(pdf_out, txt_out)
                        print(f"     ⚠️  VBMA (fallback page scrape) → {pdf_out.name}")
                        return {
                            "source": source, "status": "OK_FALLBACK",
                            "url": pdf_url,
                            "pdf_file": str(pdf_out),
                            "txt_file": str(txt_out),
                        }
    except Exception:
        pass

    return {"source": source, "status": "FAIL", "error": "Không tải được VBMA PDF"}


def fetch_vnba(year: int, month: int, cache_dir: Path) -> dict:
    """
    VNBA: Thông tin kinh tế tài chính tháng.
    Thường là PDF, CDN link từ vnba.org.vn.
    """
    source = "VNBA"
    vi_month = VI_MONTHS[month]
    pdf_out = cache_dir / f"vnba_{year}-{month:02d}.pdf"
    txt_out = cache_dir / f"vnba_{year}-{month:02d}.txt"

    # Tìm link PDF trên trang tin tức VNBA
    try:
        r = requests.get(
            "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if (
                    (vi_month in text or str(month) in text)
                    and str(year) in text
                    and (".pdf" in href.lower() or "download" in href.lower())
                ):
                    pdf_url = href if href.startswith("http") else f"https://vnba.org.vn{href}"
                    r2 = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
                    if r2.status_code == 200:
                        with open(pdf_out, "wb") as f:
                            for chunk in r2.iter_content(chunk_size=8192):
                                f.write(chunk)
                        pdf_to_text(pdf_out, txt_out)
                        print(f"     ✅ VNBA → {pdf_out.name}")
                        return {
                            "source": source, "status": "OK",
                            "url": pdf_url,
                            "pdf_file": str(pdf_out),
                            "txt_file": str(txt_out),
                        }
    except Exception:
        pass

    # Fallback: lấy HTML trang tin tức → extract text
    try:
        r = requests.get(
            "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200 and vi_month in r.text.lower():
            txt_out_html = cache_dir / f"vnba_{year}-{month:02d}.txt"
            soup = BeautifulSoup(r.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            txt_out_html.write_text(text_content, encoding="utf-8")
            print(f"     ⚠️  VNBA (HTML fallback) → {txt_out_html.name}")
            return {
                "source": source, "status": "OK_FALLBACK",
                "url": r.url, "txt_file": str(txt_out_html),
            }
    except Exception:
        pass

    return {"source": source, "status": "FAIL", "error": "Không tải được VNBA"}


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch VN Macro sources")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--cache-dir", required=True, help="Output directory for cached files")
    args = parser.parse_args()

    year, month = parse_month(args.month)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📥 Fetching sources cho {args.month}\n{'─' * 50}")

    fetchers = [
        ("NSO",     fetch_nso),
        ("PMI",     fetch_pmi),
        ("Customs", fetch_customs),
        ("VBMA",    fetch_vbma),
        ("VNBA",    fetch_vnba),
    ]

    fetch_log = {"month": args.month, "sources": {}}
    failed = []

    for name, fetcher in fetchers:
        print(f"\n  [{name}]")
        result = fetcher(year, month, cache_dir)
        fetch_log["sources"][name] = result

        if result["status"] == "FAIL":
            failed.append(name)
            print(f"     ❌ FAIL: {result.get('error', 'Unknown')}")

    # Lưu fetch log
    log_path = cache_dir / "fetch_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(fetch_log, f, ensure_ascii=False, indent=2)

    print(f"\n{'─' * 50}")
    print(f"📊 Fetch xong: {len(fetchers) - len(failed)}/{len(fetchers)} nguồn thành công")

    if failed:
        print(f"⚠️  Thiếu: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("✅ Tất cả nguồn đã được cache")


if __name__ == "__main__":
    main()
