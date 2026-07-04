#!/usr/bin/env python3
"""
scripts/preflight_check.py
─────────────────────────────────────────────────────────────
Pre-flight check: xác nhận 5 nguồn có thể truy cập.

THIẾT KẾ MỚI — "connectivity check", không phải "content match":
  - Chỉ kiểm tra HTTP 200/301/302 trả về
  - KHÔNG tìm từ khoá trong HTML (quá fragile với web chính phủ VN)
  - fetch_sources.py mới là nơi xác định data thật có hay không

force_partial=true → tiến hành dù bao nhiêu nguồn reachable
  (kể cả 0/5 — để fetch_sources.py xử lý tiếp)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}

# ─────────────────────────────────────────────────────────────────
# DANH SÁCH URL CHO TỪNG NGUỒN
# Nhiều URL fallback — chỉ cần 1 URL trả về 200 là PASS
# ─────────────────────────────────────────────────────────────────

SOURCE_URLS = {
    "NSO": [
        "https://www.gso.gov.vn/",
        "https://www.gso.gov.vn/bai-viet/thong-ke/tinh-hinh-kinh-te-xa-hoi/",
    ],
    "PMI": [
        "https://www.pmi.spglobal.com/Survey/PressRelease/VN",
        "https://vneconomy.vn/",           # VnEconomy thường đăng lại PMI
        "https://cafef.vn/",
    ],
    "Customs": [
        "https://www.customs.gov.vn/",
        "https://haiquanonline.com.vn/",
    ],
    "VBMA": [
        "https://vbma.org.vn/",
        "https://vbma.org.vn/bao-cao",
    ],
    "VNBA": [
        "https://vnba.org.vn/",
        "https://vnba.org.vn/tin-tuc/thong-tin-kinh-te-tai-chinh/",
    ],
}


def check_source(name: str, urls: list[str]) -> dict:
    """
    Kiểm tra connectivity: thử từng URL, trả về OK nếu bất kỳ URL nào
    trả về HTTP 200/301/302. Không cần phân tích nội dung trang.
    """
    for url in urls:
        try:
            r = requests.get(
                url, headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            if r.status_code in (200, 301, 302):
                return {
                    "source": name,
                    "status": "OK",
                    "url": url,
                    "http_code": r.status_code,
                }
        except requests.exceptions.SSLError:
            # Một số site chính phủ VN có SSL cũ — thử bỏ verify
            try:
                r = requests.get(
                    url, headers=HEADERS,
                    timeout=TIMEOUT,
                    allow_redirects=True,
                    verify=False,
                )
                if r.status_code in (200, 301, 302):
                    return {
                        "source": name,
                        "status": "OK",
                        "url": url,
                        "http_code": r.status_code,
                        "note": "SSL verify=False",
                    }
            except Exception:
                continue
        except Exception:
            continue

    # Không URL nào reachable
    return {
        "source": name,
        "status": "NOT_FOUND",
        "tried_urls": urls,
        "note": "Tất cả URLs không trả về 200/301/302",
    }


def run_preflight(year: int, month: int, force_partial: bool) -> dict:
    print(f"\n🔍 Pre-flight connectivity check cho {year}-{month:02d}")
    print(f"   force_partial={force_partial}")
    print("─" * 50)

    results = {}
    available = []
    missing = []

    for name, urls in SOURCE_URLS.items():
        print(f"  Checking {name}...", end=" ", flush=True)
        result = check_source(name, urls)
        results[name] = result

        if result["status"] == "OK":
            available.append(name)
            print(f"✅ HTTP {result.get('http_code', '?')} — {result['url']}")
        else:
            missing.append(name)
            print(f"⚠️  Không reachable (tiếp tục fetch sẽ xử lý)")

    sources_found = len(available)
    print(f"\n{'─' * 50}")
    print(f"📊 Connectivity: {sources_found}/5 nguồn reachable")

    # ── Quyết định status ─────────────────────────────────────────
    if sources_found == 5:
        status = "OK"
        print("✅ Đủ 5 nguồn reachable — full run\n")

    elif force_partial:
        # force_partial=true: tiến hành bất kể bao nhiêu nguồn reachable,
        # kể cả 0/5. fetch_sources.py sẽ thử tải và xác định data thật.
        status = "PARTIAL"
        print(f"⚠️  Partial run (force_partial=true) — tiến hành với {sources_found}/5\n")
        if sources_found == 0:
            print("   ℹ️  0/5 reachable nhưng force_partial=true")
            print("   → fetch_sources.py sẽ thử tải từ fallback URLs\n")

    else:
        status = "FAIL"
        print(f"❌ {sources_found}/5 reachable, force_partial=false → dừng\n")
        print("   💡 Thử lại với force_partial=true nếu muốn chạy partial\n")

    return {
        "status": status,
        "sources_found": sources_found,
        "available": available,
        "missing": missing,
        "details": results,
        "user_override": force_partial,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }


def parse_month(month_str: str) -> tuple[int, int]:
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.year, dt.month


def main():
    parser = argparse.ArgumentParser(description="VN Macro Pre-flight Check")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--force-partial", default="false",
                        help="Tiến hành dù thiếu nguồn (true/false)")
    parser.add_argument("--output", default="preflight_result.json")
    args = parser.parse_args()

    year, month = parse_month(args.month)
    force_partial = args.force_partial.lower() == "true"

    result = run_preflight(year, month, force_partial)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"💾 Kết quả preflight → {output_path}")

    # Exit 1 chỉ khi FAIL thật sự (force_partial=false VÀ < 5 nguồn)
    if result["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
