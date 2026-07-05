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
                "--disable-dev-shm-usage",
                "--disable-web-security",       # cho phép load local resources
                "--disable-features=VizDisplayCompositor",
            ]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Load file HTML local
        page.goto(f"file://{html_abs}", wait_until="networkidle", timeout=60000)

        # Đợi Chart.js và fonts load
        page.wait_for_timeout(2500)

        # ── Inject JS: chuẩn bị layout cho PDF ──────────────────────────
        page.evaluate("""() => {
            // 1. Ẩn navigation tabs (không cần trong PDF)
            document.querySelectorAll('.nav-tabs').forEach(el => {
                el.style.display = 'none';
            });

            // 2. Hiện TẤT CẢ group sections (không chỉ tab đang active)
            document.querySelectorAll('.group-section').forEach(el => {
                el.style.display = 'block';
                el.style.animation = 'none';
                el.style.opacity = '1';
                el.style.transform = 'none';
                el.classList.add('active');
            });

            // 3. Đóng tất cả modals
            document.querySelectorAll('.modal').forEach(el => {
                el.style.display = 'none';
            });

            // 4. Thêm CSS page-break cho print
            const style = document.createElement('style');
            style.textContent = `
                .data-card, .kpi, .highlight-box, .panel {
                    page-break-inside: avoid !important;
                    break-inside: avoid !important;
                }
                .group-header {
                    page-break-after: avoid !important;
                    break-after: avoid !important;
                }
                .group-section {
                    page-break-before: auto !important;
                    margin-bottom: 32px !important;
                }
                .data-card:hover {
                    transform: none !important;
                }
            `;
            document.head.appendChild(style);

            // 5. Scroll về đầu trang
            window.scrollTo(0, 0);
        }""")

        # Đợi thêm cho charts render sau khi sections được hiện
        page.wait_for_timeout(2500)

        # Xuất PDF với scale thu nhỏ để giảm file size và cải thiện layout
        page.pdf(
            path=str(pdf_path),
            format="A4",
            landscape=False,
            print_background=True,   # GIỮ dark theme + màu sắc
            scale=0.78,              # Thu nhỏ để vừa trang A4, giảm file size
            margin={
                "top": "10mm",
                "bottom": "10mm",
                "left": "8mm",
                "right": "8mm",
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
