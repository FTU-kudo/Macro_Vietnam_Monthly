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

    # Suppress SSL warnings cho các site chính phủ VN dùng SSL cũ
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get_safe(url, **kwargs):
        """requests.get với fallback verify=False nếu SSLError."""
        try:
            return requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
        except requests.exceptions.SSLError:
            return requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False, **kwargs)
        except Exception:
            return None

    # Trang thống kê hải quan
    customs_url = "https://www.customs.gov.vn/index.jsp?pageIndex=1&category=27&cid=30"
    try:
        r = get_safe(customs_url)
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Tìm link bài viết tháng M — thử nhiều pattern
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"]
                if (
                    (vi_month in text or f"{month:02d}/{year}" in text or f"thang-{month}" in href)
                    and (str(year) in text or str(year) in href)
                ):
                    article_url = href if href.startswith("http") else f"https://www.customs.gov.vn{href}"
                    try:
                        ar = get_safe(article_url)
                        if ar and ar.status_code == 200:
                            art_soup = BeautifulSoup(ar.text, "html.parser")
                            text_content = art_soup.get_text(separator="\n", strip=True)
                            if len(text_content) > 200:
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

    # Fallback 1: trang danh sách hải quan — lấy bài đầu tiên
    try:
        r = get_safe(customs_url)
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Lấy link bài đầu tiên trong danh sách
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if ("xuat-nhap-khau" in href.lower() or "xnk" in href.lower()
                        or "xuat nhap khau" in text or "xuất nhập khẩu" in text):
                    article_url = href if href.startswith("http") else f"https://www.customs.gov.vn{href}"
                    try:
                        ar = get_safe(article_url)
                        if ar and ar.status_code == 200:
                            art_soup = BeautifulSoup(ar.text, "html.parser")
                            text_content = art_soup.get_text(separator="\n", strip=True)
                            if len(text_content) > 200:
                                output_file.write_text(text_content, encoding="utf-8")
                                print(f"     ⚠️  Customs (article fallback) → {output_file.name}")
                                return {
                                    "source": source, "status": "OK_FALLBACK",
                                    "url": article_url, "file": str(output_file),
                                }
                    except Exception:
                        continue
    except Exception:
        pass

    # Fallback 2: haiquanonline.com.vn
    try:
        fallback_url = f"https://haiquanonline.com.vn/?s=xuất+nhập+khẩu+{vi_month}+{year}"
        r = requests.get(fallback_url, headers=HEADERS, timeout=TIMEOUT)
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Tìm link bài viết cụ thể
            for a in soup.find_all("a", href=True):
                href = a["href"]
                a_text = a.get_text(strip=True).lower()
                if (str(year) in href or str(year) in a_text) and "xuat-nhap" in href.lower():
                    try:
                        ar = requests.get(href, headers=HEADERS, timeout=TIMEOUT)
                        if ar.status_code == 200:
                            art_soup = BeautifulSoup(ar.text, "html.parser")
                            text_content = art_soup.get_text(separator="\n", strip=True)
                            if len(text_content) > 300:
                                output_file.write_text(text_content, encoding="utf-8")
                                print(f"     ⚠️  Customs (haiquanonline article) → {output_file.name}")
                                return {
                                    "source": source, "status": "OK_FALLBACK",
                                    "url": href, "file": str(output_file),
                                }
                    except Exception:
                        continue
            # Fallback: lấy text trang search
            text_content = soup.get_text(separator="\n", strip=True)
            if len(text_content) > 300:
                output_file.write_text(text_content, encoding="utf-8")
                print(f"     ⚠️  Customs (haiquanonline search) → {output_file.name}")
                return {
                    "source": source, "status": "OK_FALLBACK",
                    "url": fallback_url, "file": str(output_file),
                }
    except Exception:
        pass

    # Fallback 3: tìm trên VnEconomy
    try:
        vne_url = f"https://vneconomy.vn/search/?q=hải+quan+xuất+nhập+khẩu+{vi_month}+{year}"
        r = requests.get(vne_url, headers=HEADERS, timeout=TIMEOUT)
        if r and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            if len(text_content) > 300:
                output_file.write_text(text_content, encoding="utf-8")
                print(f"     ⚠️  Customs (VnEconomy fallback) → {output_file.name}")
                return {
                    "source": source, "status": "OK_FALLBACK",
                    "url": vne_url, "file": str(output_file),
                }
    except Exception:
        pass

    return {"source": source, "status": "FAIL", "error": "Không tải được Customs"}


def fetch_vbma(year: int, month: int, cache_dir: Path) -> dict:
    """
    VBMA: PDF báo cáo tuần TTTP (tuần cuối tháng M).
    Strategy mới: scrape trang bao-cao để lấy link thực tế, sau đó tải PDF.
    """
    source = "VBMA"
    en_abbr = EN_MONTHS_ABBR[month]  # "May", "Jun"...
    pdf_out = cache_dir / f"vbma_{year}-{month:02d}.pdf"
    txt_out = cache_dir / f"vbma_{year}-{month:02d}.txt"

    # ── Strategy 1: Scrape trang báo cáo bằng Session + Referer ──────────
    vbma_session = requests.Session()
    vbma_session.headers.update({
        **HEADERS,
        "Referer": "https://vbma.org.vn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    report_pages = [
        "https://vbma.org.vn/bao-cao",
        "https://vbma.org.vn/bao-cao?page=1",
        "https://vbma.org.vn/en/reports",
    ]
    for page_url in report_pages:
        try:
            r = vbma_session.get(page_url, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                href_up = href.upper()
                link_text = a.get_text(strip=True).upper()
                is_report = (
                    "TTTP" in href_up or "BAO_CAO_TUAN" in href_up or "BAO CAO TUAN" in href_up
                    or "TTTP" in link_text or "BÁO CÁO TUẦN" in link_text
                    or "WEEKLY" in href_up or "BOND" in href_up
                )
                if is_report and ".PDF" in href_up:
                    pdf_url = href if href.startswith("http") else f"https://vbma.org.vn{href}"
                    try:
                        r2 = vbma_session.get(pdf_url, timeout=TIMEOUT, stream=True)
                        if r2.status_code == 200 and "pdf" in r2.headers.get("content-type", "").lower():
                            with open(pdf_out, "wb") as f:
                                for chunk in r2.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            size = pdf_out.stat().st_size
                            if size > 1024:
                                print(f"     ✅ VBMA (scraped) → {pdf_out.name} ({size:,} bytes)")
                                if pdf_to_text(pdf_out, txt_out):
                                    return {
                                        "source": source, "status": "OK",
                                        "url": pdf_url,
                                        "pdf_file": str(pdf_out),
                                        "txt_file": str(txt_out),
                                    }
                    except Exception:
                        continue
        except Exception:
            continue

    # ── Strategy 2: URL pattern cứng — nhiều biến thể folder + tên file ──
    import calendar
    # Thử tất cả các tuần trong tháng (không chỉ tuần cuối)
    all_week_ranges = []
    last_day = calendar.monthrange(year, month)[1]
    # Sinh các khoảng tuần từ đầu đến cuối tháng
    for start in range(1, last_day - 2):
        for length in [4, 5, 6]:
            end = min(start + length, last_day)
            if end - start >= 3:
                all_week_ranges.append((start, end))
    # Ưu tiên tuần cuối tháng
    priority_ranges = [(25, 29), (24, 28), (26, 30), (27, 31), (23, 27), (22, 26), (28, 31)]
    priority_ranges = [(s, min(e, last_day)) for s, e in priority_ranges]
    all_week_ranges = priority_ranges + [r for r in all_week_ranges if r not in priority_ranges]

    # Thử nhiều biến thể folder + tên file
    EN_MONTHS_FULL = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December",
    }
    folder_variants = [
        en_abbr,                          # "Mar"
        EN_MONTHS_FULL[month],            # "March"
        en_abbr.upper(),                  # "MAR"
        EN_MONTHS_FULL[month].upper(),    # "MARCH"
        en_abbr.lower(),                  # "mar"
    ]

    def make_vbma_urls(s: int, e: int) -> list:
        urls = []
        for folder in folder_variants:
            base = f"https://vbma.org.vn/storage/reports/{folder}{year}/"
            date_str = f"{s:02d}{month:02d}{year}-{e:02d}{month:02d}{year}"
            # Các biến thể tên file
            suffixes = [
                "%20%20BAO%20CAO%20TUAN%20TTTP.pdf",
                "%20BAO%20CAO%20TUAN%20TTTP.pdf",
                "_BAO_CAO_TUAN_TTTP.pdf",
                "%20BAO%20CAO%20TUAN%20TTTP%20.pdf",
                "-BAO-CAO-TUAN-TTTP.pdf",
            ]
            for sfx in suffixes:
                urls.append(base + date_str + sfx)
        return urls

    for start, end in all_week_ranges:
        if start < 1 or end < 1:
            continue
        for pdf_url in make_vbma_urls(start, end):
            try:
                r = requests.get(pdf_url, headers={**HEADERS, "Referer": "https://vbma.org.vn/"},
                                 timeout=TIMEOUT, stream=True)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and "pdf" in ct.lower():
                    with open(pdf_out, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    size = pdf_out.stat().st_size
                    print(f"     ✅ VBMA PDF → {pdf_out.name} ({size:,} bytes) [{start}-{end}/{month}]")
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

    vnba_pages = [
        "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
        f"https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/?page=1",
    ]

    for page_url in vnba_pages:
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                # Điều kiện nới lỏng: chỉ cần năm + có PDF hoặc download link
                # Chấp nhận cả chữ "tháng 3" lẫn số "3" lẫn "03"
                month_variants = [
                    vi_month,          # "tháng 3"
                    f"tháng {month}",  # "tháng 3" (trùng nhưng safe)
                    f" {month} ",      # " 3 "
                    f"-{month:02d}-",  # "-03-" trong URL
                    f"/{month:02d}/",  # "/03/" trong URL
                    f"thang-{month}",  # "thang-3" trong URL
                    f"thang{month:02d}",  # "thang03"
                ]
                has_month = any(v in text or v in href for v in month_variants)
                has_year = str(year) in text or str(year) in href
                has_link = (".pdf" in href.lower() or "download" in href.lower()
                            or "/uploads/" in href or "/files/" in href)
                if has_year and has_link:
                    # Nếu có thông tin tháng thì ưu tiên, không thì cũng lấy (bài mới nhất)
                    pdf_url = href if href.startswith("http") else f"https://vnba.org.vn{href}"
                    try:
                        r2 = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
                        if r2.status_code == 200:
                            with open(pdf_out, "wb") as f:
                                for chunk in r2.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            size = pdf_out.stat().st_size
                            if size > 1024:
                                pdf_to_text(pdf_out, txt_out)
                                tag = "✅" if has_month else "⚠️ "
                                print(f"     {tag} VNBA → {pdf_out.name} ({size:,} bytes)")
                                return {
                                    "source": source, "status": "OK" if has_month else "OK_FALLBACK",
                                    "url": pdf_url,
                                    "pdf_file": str(pdf_out),
                                    "txt_file": str(txt_out),
                                }
                    except Exception:
                        continue
        except Exception:
            pass

    # Fallback: lấy link PDF đầu tiên tìm được trên trang (bài mới nhất)
    try:
        r = requests.get(
            "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # Tìm link article đầu tiên rồi vào xem có PDF không
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "thong-tin-kinh-te" in href or "kinh-te-tai-chinh" in href:
                    article_url = href if href.startswith("http") else f"https://vnba.org.vn{href}"
                    try:
                        ar = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)
                        if ar.status_code == 200:
                            art_soup = BeautifulSoup(ar.text, "html.parser")
                            for a2 in art_soup.find_all("a", href=True):
                                h2 = a2["href"]
                                if ".pdf" in h2.lower() or "/uploads/" in h2:
                                    pdf_url = h2 if h2.startswith("http") else f"https://vnba.org.vn{h2}"
                                    r2 = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
                                    if r2.status_code == 200:
                                        with open(pdf_out, "wb") as f:
                                            for chunk in r2.iter_content(chunk_size=8192):
                                                f.write(chunk)
                                        if pdf_out.stat().st_size > 1024:
                                            pdf_to_text(pdf_out, txt_out)
                                            print(f"     ⚠️  VNBA (article PDF fallback) → {pdf_out.name}")
                                            return {
                                                "source": source, "status": "OK_FALLBACK",
                                                "url": pdf_url,
                                                "pdf_file": str(pdf_out),
                                                "txt_file": str(txt_out),
                                            }
                    except Exception:
                        continue
                    break  # Chỉ thử article đầu tiên
    except Exception:
        pass

    # Fallback cuối: HTML trang danh sách → extract text
    try:
        r = requests.get(
            "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200:
            txt_out_html = cache_dir / f"vnba_{year}-{month:02d}.txt"
            soup = BeautifulSoup(r.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            if len(text_content) > 200:
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
    parser.add_argument("--force-partial", default="false",
                        help="Tiếp tục dù thiếu nguồn (true/false)")
    args = parser.parse_args()
    force_partial = args.force_partial.lower() == "true"

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
        if force_partial:
            print("   ℹ️  force_partial=true → tiếp tục với nguồn đã có")
            sys.exit(0)
        else:
            print("   💡 Dùng force_partial=true để tiếp tục khi thiếu nguồn")
            sys.exit(1)
    else:
        print("✅ Tất cả nguồn đã được cache")


if __name__ == "__main__":
    main()
