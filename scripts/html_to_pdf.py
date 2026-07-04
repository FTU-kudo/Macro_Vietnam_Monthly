#!/usr/bin/env python3
"""
scripts/html_to_pdf.py
─────────────────────────────────────────────────────────────
Bước 5: Xuất PDF từ report.html dùng Playwright (headless Chromium).

Tại sao Playwright thay vì wkhtmltopdf?
  - Playwright render đúng CSS hiện đại (grid, backdrop-filter, gradients)
  - Giữ nguyên dark theme + Chart.js charts
  - Chạy được trên GitHub Actions (ubuntu-latest) không cần cài Chrome riêng
  - Output đẹp hơn nhiều

Usage:
  python scripts/html_to_pdf.py \\
    --html "vn-macro-monthly/2026-03/report.html" \\
    --output "vn-macro-monthly/2026-03/report.pdf"
"""

import argparse
import sys
from pathlib import Path


def export_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Dùng Playwright để render HTML → PDF."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ❌ Playwright chưa được cài. Chạy: pip install playwright && playwright install chromium")
        return False

    html_abs = html_path.resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  🖨️  Rendering PDF từ: {html_abs.name}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",   # quan trọng cho Docker/CI
            ]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Load file HTML local
        page.goto(f"file://{html_abs}", wait_until="networkidle", timeout=60000)

        # Đợi Chart.js render xong (nếu có)
        try:
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # Xuất PDF
        page.pdf(
            path=str(pdf_path),
            format="A4",
            landscape=False,
            print_background=True,   # GIỮ dark theme + màu sắc
            margin={
                "top": "12mm",
                "bottom": "12mm",
                "left": "10mm",
                "right": "10mm",
            },
        )

        browser.close()

    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"  ✅ PDF → {pdf_path.name} ({size_mb:.1f} MB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Export HTML report to PDF via Playwright")
    parser.add_argument("--html",   required=True, help="Đường dẫn file report.html")
    parser.add_argument("--output", required=True, help="Đường dẫn output report.pdf")
    args = parser.parse_args()

    html_path = Path(args.html)
    pdf_path  = Path(args.output)

    if not html_path.exists():
        print(f"  ❌ Không tìm thấy HTML file: {html_path}")
        sys.exit(1)

    print(f"\n📄 Xuất PDF cho báo cáo\n{'─' * 40}")
    success = export_pdf(html_path, pdf_path)

    if not success:
        print("  ⚠️  Xuất PDF thất bại — workflow vẫn tiếp tục (PDF optional)")
        sys.exit(0)   # exit 0: không block workflow nếu PDF fail


if __name__ == "__main__":
    main()
