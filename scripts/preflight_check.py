#!/usr/bin/env python3
"""
scripts/preflight_check.py
─────────────────────────────────────────────────────────────
Pre-flight check: xác nhận 5 nguồn có sẵn cho tháng báo cáo.
Theo SKILL.md: "All-or-nothing, trừ khi user override partial"

5 nguồn:
  1. NSO   — gso.gov.vn (báo cáo KTXH tháng)
  2. PMI   — pmi.spglobal.com (Vietnam Manufacturing PMI)
  3. Customs — customs.gov.vn (thống kê XNK)
  4. VBMA  — vbma.org.vn (báo cáo tuần TTTP)
  5. VNBA  — vnba.org.vn (thông tin kinh tế tài chính)
"""

import argparse
import json
import re
import sys
from datetime import datetime, date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Timeout chung cho mọi request ──────────────────────────────
TIMEOUT = 20
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}

# ── Tên tháng tiếng Việt + tiếng Anh ──────────────────────────
VI_MONTHS = [
    "", "tháng 1", "tháng 2", "tháng 3", "tháng 4",
    "tháng 5", "tháng 6", "tháng 7", "tháng 8",
    "tháng 9", "tháng 10", "tháng 11", "tháng 12",
]
EN_MONTHS = [
    "", "January", "February", "March", "April",
    "May", "June", "July", "August", "September",
    "October", "November", "December",
]


def parse_month(month_str: str) -> tuple[int, int]:
    """Parse 'YYYY-MM' → (year, month)."""
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.year, dt.month


# ─────────────────────────────────────────────────────────────────
# CHECK TỪNG NGUỒN
# ─────────────────────────────────────────────────────────────────

def check_nso(year: int, month: int) -> dict:
    """
    NSO (gso.gov.vn) — Báo cáo KTXH tháng M.
    Thường publish cuối tháng M hoặc đầu tháng M+1.
    """
    source = "NSO"
    vi_month = VI_MONTHS[month]
    
    # Tìm bài viết TCKH qua trang tin tức
    search_urls = [
        f"https://www.gso.gov.vn/bai-viet/thong-ke/tinh-hinh-kinh-te-xa-hoi/",
        f"https://www.gso.gov.vn/category/tinh-hinh-kinh-te-xa-hoi/",
    ]
    
    keywords = [
        f"kinh tế xã hội {vi_month} {year}",
        f"ktxh {vi_month}",
        f"thong cao bao chi {vi_month}",
    ]

    for url in search_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                text_lower = r.text.lower()
                for kw in keywords:
                    if kw.lower() in text_lower:
                        return {
                            "source": source, "status": "OK",
                            "url": url, "matched_keyword": kw,
                        }
        except Exception as e:
            continue

    # Fallback: tìm thông qua Google Site Search (dùng requests)
    try:
        query = f'site:gso.gov.vn "kinh tế xã hội" "{vi_month}" "{year}"'
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"q": query, "num": 3},
            timeout=10,
        )
        # Không cần API key cho preview check
    except Exception:
        pass

    return {
        "source": source, "status": "NOT_FOUND",
        "retry_hint": f"Thử lại sau ngày 3 tháng {month + 1}/{year}",
    }


def check_pmi(year: int, month: int) -> dict:
    """
    S&P Global PMI Vietnam — Manufacturing PMI.
    Release: ngày 1-3 của tháng M+1.
    """
    source = "PMI"
    en_month = EN_MONTHS[month]

    # S&P Global chính thức
    pmi_url = "https://www.pmi.spglobal.com/Survey/PressRelease/VN"
    try:
        r = requests.get(pmi_url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            text_lower = r.text.lower()
            if en_month.lower() in text_lower and str(year) in r.text:
                return {"source": source, "status": "OK", "url": pmi_url}
    except Exception:
        pass

    # Fallback: VnEconomy / CafeF thường đăng lại ngay
    fallback_sites = [
        f"https://vneconomy.vn/search/?q=PMI+{en_month}+{year}",
        f"https://cafef.vn/search/?q=PMI+Viet+Nam+{en_month}+{year}",
    ]
    for url in fallback_sites:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and "pmi" in r.text.lower():
                return {
                    "source": source, "status": "OK_FALLBACK",
                    "url": url, "note": "Dùng nguồn thứ cấp (VnEconomy/CafeF)",
                }
        except Exception:
            continue

    next_month = month % 12 + 1
    return {
        "source": source, "status": "NOT_FOUND",
        "retry_hint": f"PMI release ngày 1-3/{next_month}/{year}",
    }


def check_customs(year: int, month: int) -> dict:
    """
    Tổng cục Hải quan — thống kê XNK tháng.
    Release: ~ngày 15 tháng M+1.
    """
    source = "Customs"
    vi_month = VI_MONTHS[month]

    try:
        url = "https://www.customs.gov.vn/index.jsp?pageIndex=1&category=27&cid=30"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            text_lower = r.text.lower()
            if vi_month in text_lower and str(year) in r.text:
                return {"source": source, "status": "OK", "url": url}
    except Exception:
        pass

    # Fallback: báo Hải quan / VnEconomy
    try:
        fallback = (
            f"https://haiquanonline.com.vn/?s="
            f"xu%E1%BA%A5t+nh%E1%BA%ADp+kh%E1%BA%A9u+{vi_month.replace(' ', '+')}+{year}"
        )
        r = requests.get(fallback, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and vi_month in r.text.lower():
            return {
                "source": source, "status": "OK_FALLBACK",
                "url": fallback, "note": "Báo Hải quan online",
            }
    except Exception:
        pass

    return {
        "source": source, "status": "NOT_FOUND",
        "retry_hint": f"Customs release ~15/{month + 1}/{year}",
    }


def check_vbma(year: int, month: int) -> dict:
    """
    VBMA — Báo cáo tuần TTTP (tuần cuối tháng M).
    URL pattern: vbma.org.vn/storage/reports/[MonYYYY]/[dates] BAO CAO TUAN TTTP.pdf
    """
    source = "VBMA"
    en_month_abbr = datetime(year, month, 1).strftime("%b")  # "May", "Jun"...
    
    # Thử trang chủ báo cáo VBMA
    try:
        r = requests.get(
            "https://vbma.org.vn/bao-cao",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200:
            text_lower = r.text.lower()
            month_check = (
                en_month_abbr.lower() in text_lower
                or VI_MONTHS[month].split()[-1] in text_lower
            )
            if month_check and str(year) in r.text:
                return {"source": source, "status": "OK", "url": "https://vbma.org.vn/bao-cao"}
    except Exception:
        pass

    # Thử URL pattern trực tiếp (tuần cuối)
    # Tìm tuần 25-29, 24-28, 26-30 của tháng
    possible_weeks = [
        (25, 29), (24, 28), (26, 30), (27, 31), (23, 27),
    ]
    for start, end in possible_weeks:
        try:
            pdf_url = (
                f"https://vbma.org.vn/storage/reports/"
                f"{en_month_abbr}{year}/"
                f"{start:02d}{month:02d}{year}-{end:02d}{month:02d}{year}"
                f"%20%20BAO%20CAO%20TUAN%20TTTP.pdf"
            )
            r = requests.head(pdf_url, headers=HEADERS, timeout=10)
            if r.status_code in (200, 301, 302):
                return {
                    "source": source, "status": "OK",
                    "url": pdf_url, "note": f"PDF tuần {start}-{end}/{month}",
                }
        except Exception:
            continue

    return {
        "source": source, "status": "NOT_FOUND",
        "retry_hint": f"VBMA báo cáo tuần cuối tháng {month}/{year}",
    }


def check_vnba(year: int, month: int) -> dict:
    """
    VNBA — Thông tin kinh tế tài chính tháng.
    """
    source = "VNBA"
    vi_month = VI_MONTHS[month]

    try:
        r = requests.get(
            "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
            headers=HEADERS, timeout=TIMEOUT
        )
        if r.status_code == 200:
            text_lower = r.text.lower()
            if vi_month in text_lower and str(year) in r.text:
                return {"source": source, "status": "OK", "url": r.url}
    except Exception:
        pass

    return {
        "source": source, "status": "NOT_FOUND",
        "retry_hint": f"VNBA thường publish tuần 2-3 tháng {month + 1}/{year}",
    }


# ─────────────────────────────────────────────────────────────────
# MAIN PREFLIGHT LOGIC
# ─────────────────────────────────────────────────────────────────

def run_preflight(year: int, month: int, force_partial: bool) -> dict:
    """Chạy pre-flight check cho cả 5 nguồn."""
    checkers = [
        ("NSO",     check_nso),
        ("PMI",     check_pmi),
        ("Customs", check_customs),
        ("VBMA",    check_vbma),
        ("VNBA",    check_vnba),
    ]

    results = {}
    available = []
    missing = []

    print(f"\n🔍 Pre-flight check cho {year}-{month:02d}\n{'─' * 50}")
    for name, checker in checkers:
        print(f"  Checking {name}...", end=" ", flush=True)
        result = checker(year, month)
        results[name] = result
        status = result["status"]

        if status.startswith("OK"):
            available.append(name)
            print(f"✅ {status}")
        else:
            missing.append(name)
            print(f"❌ NOT_FOUND → {result.get('retry_hint', '')}")

    sources_found = len(available)
    print(f"\n{'─' * 50}")
    print(f"📊 Kết quả: {sources_found}/5 nguồn")

    # Quyết định status
    if sources_found == 5:
        status = "OK"
        print("✅ Đủ 5 nguồn — tiến hành full run\n")
    elif force_partial and sources_found >= 3:
        status = "PARTIAL"
        print(f"⚠️  Partial run ({sources_found}/5) — user override\n")
    else:
        status = "FAIL"
        retry_hints = [results[m].get("retry_hint", "") for m in missing]
        print(f"❌ Không đủ nguồn ({sources_found}/5) — dừng\n")
        for hint in retry_hints:
            if hint:
                print(f"   → {hint}")

    return {
        "status": status,
        "sources_found": sources_found,
        "available": available,
        "missing": missing,
        "details": results,
        "user_override": force_partial and status == "PARTIAL",
        "retry_hint": (
            "Thử lại sau ngày 20 tháng sau khi đủ 5 nguồn"
            if status == "FAIL" else None
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="VN Macro Pre-flight Check")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--force-partial", default="false",
                        help="Chạy partial nếu thiếu nguồn (true/false)")
    parser.add_argument("--output", default="preflight_result.json",
                        help="Output JSON file")
    args = parser.parse_args()

    year, month = parse_month(args.month)
    force_partial = args.force_partial.lower() == "true"

    result = run_preflight(year, month, force_partial)

    # Lưu kết quả
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"💾 Kết quả pre-flight → {output_path}")

    # Exit code: 0 = OK/PARTIAL, 1 = FAIL
    if result["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
