#!/usr/bin/env python3
"""
scripts/notify_email.py
─────────────────────────────────────────────────────────────
Gửi email thông báo khi report được tạo (hoặc khi preflight fail).

Secrets cần thiết trong GitHub repo:
  EMAIL_USER  — địa chỉ Gmail gửi đi (e.g. youreport@gmail.com)
  EMAIL_PASS  — App Password Gmail (16 ký tự)
  EMAIL_TO    — danh sách nhận, cách nhau dấu phẩy
"""

import argparse
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


VI_MONTHS = [
    "", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4",
    "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8",
    "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
]

VERDICT_COLORS = {
    "TÍCH CỰC": "#1a7a3a",
    "TRUNG TÍNH": "#7a6a1a",
    "TIÊU CỰC": "#7a1a1a",
    "CẢNH GIÁC": "#7a4a1a",
}


def build_success_email(month: str, sources: str, repo_url: str) -> tuple[str, str]:
    """Tạo email subject + HTML body cho success."""
    year, m = int(month[:4]), int(month[5:7])
    vi_month = VI_MONTHS[m]
    generated = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    subject = f"📊 [VN Macro] Báo cáo {vi_month} {year} đã sẵn sàng ({sources}/5 nguồn)"

    # Link đến report trong repo
    report_url = f"{repo_url}/blob/main/vn-macro-monthly/{month}/report.html"
    raw_url = f"{repo_url}/raw/main/vn-macro-monthly/{month}/report.html"

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;padding:24px;margin:0;">
<div style="max-width:600px;margin:0 auto;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1d26,#252836);border-radius:12px;padding:24px;text-align:center;">
    <h1 style="color:#4f9cf9;margin:0;font-size:1.4rem;">📊 VN Macro Monthly</h1>
    <p style="color:#94a3b8;margin:8px 0 0;font-size:0.875rem;">Báo cáo vĩ mô Việt Nam – tự động</p>
  </div>

  <!-- Body -->
  <div style="background:#fff;border-radius:12px;padding:24px;margin-top:16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
    <h2 style="color:#1e293b;margin:0 0 8px;font-size:1.1rem;">
      ✅ Báo cáo {vi_month} {year} đã được tạo thành công
    </h2>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr><td style="padding:6px 0;color:#64748b;width:140px;">Kỳ báo cáo</td>
          <td style="padding:6px 0;color:#1e293b;font-weight:600;">{vi_month} {year} ({month})</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;">Nguồn dữ liệu</td>
          <td style="padding:6px 0;color:#1e293b;font-weight:600;">{sources}/5 nguồn chính thức</td></tr>
      <tr><td style="padding:6px 0;color:#64748b;">Tạo lúc</td>
          <td style="padding:6px 0;color:#1e293b;">{generated}</td></tr>
    </table>

    <div style="margin-top:16px;">
      <a href="{report_url}"
         style="display:inline-block;background:#4f9cf9;color:#fff;padding:10px 20px;
                border-radius:8px;text-decoration:none;font-weight:600;font-size:0.9rem;">
        📄 Xem báo cáo trên GitHub →
      </a>
      &nbsp;&nbsp;
      <a href="{raw_url}"
         style="display:inline-block;background:#e2e8f0;color:#1e293b;padding:10px 20px;
                border-radius:8px;text-decoration:none;font-weight:600;font-size:0.9rem;">
        ⬇️ Download HTML
      </a>
    </div>
  </div>

  <!-- Footer -->
  <p style="text-align:center;color:#94a3b8;font-size:0.75rem;margin-top:16px;">
    Tự động bởi GitHub Actions • vimovietnam •
    <a href="{repo_url}" style="color:#94a3b8;">{repo_url.replace("https://github.com/", "")}</a>
  </p>

</div>
</body>
</html>"""

    return subject, html


def build_fail_email(month: str, sources: str) -> tuple[str, str]:
    """Tạo email thông báo preflight fail."""
    year, m = int(month[:4]), int(month[5:7])
    vi_month = VI_MONTHS[m]

    subject = f"⚠️ [VN Macro] Preflight FAIL {vi_month} {year} ({sources}/5 nguồn)"

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;padding:24px;">
<div style="max-width:600px;margin:0 auto;">
  <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:24px;">
    <h2 style="color:#991b1b;margin:0 0 12px;">⚠️ Preflight Check Failed</h2>
    <p style="color:#7f1d1d;">
      Báo cáo VN Macro <strong>{vi_month} {year}</strong> chưa được tạo.
      Chỉ có <strong>{sources}/5</strong> nguồn khả dụng.
    </p>
    <p style="color:#7f1d1d;margin-top:8px;">
      Theo nguyên tắc "all-or-nothing" (SKILL.md), cần đủ 5 nguồn để tạo báo cáo đầy đủ.
      Hệ thống sẽ tự thử lại vào lần chạy tiếp theo (ngày 20 tháng sau),
      hoặc bạn có thể trigger thủ công khi đủ nguồn.
    </p>
    <p style="margin-top:16px;color:#92400e;background:#fffbeb;padding:8px;border-radius:6px;font-size:0.85rem;">
      💡 Để chạy partial (3+ nguồn), trigger workflow thủ công với <code>force_partial=true</code>.
    </p>
  </div>
</div>
</body>
</html>"""

    return subject, html


def send_email(subject: str, html_body: str) -> bool:
    """Gửi email qua Gmail SMTP."""
    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASS", "")
    to_raw = os.environ.get("EMAIL_TO", "")

    if not all([user, password, to_raw]):
        print("  ⚠️  Email secrets không đầy đủ — bỏ qua gửi email")
        return False

    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"VN Macro Bot <{user}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
        print(f"  ✅ Email sent to {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"  ❌ Email error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send email notification")
    parser.add_argument("--status", required=True,
                        choices=["success", "preflight_fail"],
                        help="Loại email")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--sources", default="0", help="Số nguồn available")
    parser.add_argument("--repo-url", default="", help="GitHub repo URL")
    args = parser.parse_args()

    if args.status == "success":
        subject, html = build_success_email(args.month, args.sources, args.repo_url)
    else:
        subject, html = build_fail_email(args.month, args.sources)

    send_email(subject, html)


if __name__ == "__main__":
    main()
