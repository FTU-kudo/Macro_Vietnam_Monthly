#!/usr/bin/env python3
"""
scripts/notify_email.py
─────────────────────────────────────────────────────────────
Gửi email thông báo kèm PDF báo cáo qua Gmail.

Secrets cần thiết trong GitHub repo:
  EMAIL_USER  — địa chỉ Gmail gửi đi (e.g. yourreport@gmail.com)
  EMAIL_PASS  — App Password Gmail (16 ký tự, KHÔNG dùng password thường)
               Tạo tại: myaccount.google.com → Security → App passwords
  EMAIL_TO    — danh sách email nhận, cách nhau dấu phẩy
"""

import argparse
import os
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from pathlib import Path


VI_MONTHS = [
    "", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4",
    "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8",
    "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
]

VERDICT_EMOJI = {
    "TÍCH CỰC":  ("🟢", "#10b981", "#d1fae5"),
    "TRUNG TÍNH": ("🟡", "#f59e0b", "#fef3c7"),
    "TIÊU CỰC":  ("🔴", "#ef4444", "#fee2e2"),
    "CẢNH GIÁC": ("🟠", "#f97316", "#ffedd5"),
}


def build_success_email(
    month: str,
    sources: str,
    repo_url: str,
    has_pdf: bool = False,
) -> tuple[str, str]:
    """Tạo email subject + HTML body đẹp cho success."""
    year, m = int(month[:4]), int(month[5:7])
    vi_month = VI_MONTHS[m]
    generated = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    subject = f"📊 [VN Macro] Báo cáo {vi_month} {year} · {sources}/5 nguồn"

    report_url = f"{repo_url}/blob/main/vn-macro-monthly/{month}/report.html"
    pdf_note = (
        '<p style="color:#1e293b;font-size:13px;margin:12px 0 0;">'
        '📎 <strong>File PDF đính kèm</strong> trong email này để đọc offline.</p>'
        if has_pdf else
        '<p style="color:#64748b;font-size:12px;margin:12px 0 0;">'
        '(PDF không khả dụng lần này — xem báo cáo qua link bên dưới)</p>'
    )

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:620px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e1b4b 0%,#312e81 50%,#4c1d95 100%);
              border-radius:16px;padding:32px 28px;text-align:center;margin-bottom:16px;
              border:1px solid rgba(139,92,246,0.3);">
    <div style="display:inline-block;background:linear-gradient(135deg,#a855f7,#ec4899);
                color:#fff;padding:6px 16px;border-radius:999px;font-size:12px;
                font-weight:700;letter-spacing:0.5px;margin-bottom:12px;">
      📊 BÁO CÁO VĨ MÔ VIỆT NAM
    </div>
    <h1 style="color:#fff;margin:0;font-size:26px;font-weight:800;letter-spacing:-0.5px;">
      Tình hình Kinh tế · Tiền tệ · Tài chính
    </h1>
    <p style="color:#c4b5fd;margin:8px 0 0;font-size:14px;">
      {vi_month} {year} · Chốt dữ liệu: {month}
    </p>
  </div>

  <!-- Status card -->
  <div style="background:#1e293b;border-radius:12px;padding:20px 24px;
              margin-bottom:16px;border:1px solid rgba(255,255,255,0.08);">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="padding:6px 0;color:#94a3b8;font-size:13px;width:150px;">Kỳ báo cáo</td>
        <td style="padding:6px 0;color:#f1f5f9;font-weight:600;font-size:13px;">{vi_month} {year}</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#94a3b8;font-size:13px;">Nguồn dữ liệu</td>
        <td style="padding:6px 0;font-size:13px;">
          <span style="background:rgba(16,185,129,0.15);color:#10b981;padding:2px 10px;
                        border-radius:6px;font-weight:700;">{sources}/5 nguồn</span>
        </td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#94a3b8;font-size:13px;">Tạo lúc</td>
        <td style="padding:6px 0;color:#94a3b8;font-size:13px;">{generated}</td>
      </tr>
    </table>

    {pdf_note}
  </div>

  <!-- CTA -->
  <div style="text-align:center;margin-bottom:16px;">
    <a href="{report_url}"
       style="display:inline-block;background:linear-gradient(135deg,#a855f7,#ec4899);
              color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;
              font-weight:700;font-size:14px;letter-spacing:0.3px;
              box-shadow:0 4px 16px rgba(168,85,247,0.4);">
      🌐 Xem báo cáo online →
    </a>
  </div>

  <!-- Note về PDF -->
  <div style="background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.2);
              border-radius:10px;padding:14px 18px;margin-bottom:20px;">
    <p style="color:#c4b5fd;font-size:12px;margin:0;line-height:1.6;">
      💡 <strong>Lưu ý đọc PDF:</strong> Báo cáo dùng dark theme. Nếu PDF trông nhạt màu,
      hãy kiểm tra cài đặt "In nền màu" (Print background graphics) trong PDF reader.
    </p>
  </div>

  <!-- Footer -->
  <p style="text-align:center;color:#475569;font-size:11px;margin:0;line-height:1.7;">
    Tự động bởi GitHub Actions &nbsp;·&nbsp;
    <a href="{repo_url}" style="color:#7c3aed;text-decoration:none;">
      {repo_url.replace("https://github.com/", "")}
    </a><br>
    Email này được tạo tự động — không cần reply.
  </p>

</div>
</body>
</html>"""

    return subject, html


def build_fail_email(month: str, sources: str) -> tuple[str, str]:
    """Tạo email thông báo fail."""
    year, m = int(month[:4]), int(month[5:7])
    vi_month = VI_MONTHS[m]

    subject = f"⚠️ [VN Macro] Chưa đủ nguồn — {vi_month} {year} ({sources}/5)"

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:24px;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:560px;margin:0 auto;">
  <div style="background:#1e293b;border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:24px;">
    <h2 style="color:#ef4444;margin:0 0 12px;font-size:18px;">⚠️ Preflight Check Failed</h2>
    <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 12px;">
      Báo cáo VN Macro <strong style="color:#f1f5f9;">{vi_month} {year}</strong>
      chưa được tạo. Chỉ có <strong style="color:#fbbf24;">{sources}/5</strong> nguồn khả dụng.
    </p>
    <div style="background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.2);
                border-radius:8px;padding:12px 14px;">
      <p style="color:#fbbf24;font-size:13px;margin:0;">
        💡 Trigger thủ công với <code style="background:rgba(255,255,255,0.1);
        padding:1px 6px;border-radius:4px;">force_partial=true</code> để chạy với nguồn hiện có.
      </p>
    </div>
  </div>
</div>
</body>
</html>"""

    return subject, html


def send_email(subject: str, html_body: str, pdf_path: Path | None = None) -> bool:
    """Gửi email qua Gmail SMTP, đính kèm PDF nếu có."""
    user     = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASS", "")
    to_raw   = os.environ.get("EMAIL_TO", "")

    if not all([user, password, to_raw]):
        print("  ⚠️  Email secrets chưa được cấu hình — bỏ qua gửi email")
        print("      Cần: EMAIL_USER, EMAIL_PASS (App Password), EMAIL_TO")
        return False

    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]

    # Dùng mixed để đính kèm PDF
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"VN Macro Bot <{user}>"
    msg["To"]      = ", ".join(recipients)

    # Phần HTML body
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Đính kèm PDF nếu có
    if pdf_path and pdf_path.exists():
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > 24:
            print(f"  ⚠️  PDF quá lớn ({size_mb:.1f} MB > 24 MB) — không đính kèm")
        else:
            with open(pdf_path, "rb") as f:
                part = MIMEBase("application", "pdf")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{pdf_path.name}"',
            )
            msg.attach(part)
            print(f"  📎 PDF đính kèm: {pdf_path.name} ({size_mb:.1f} MB)")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
        print(f"  ✅ Email sent → {', '.join(recipients)}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  ❌ Gmail auth thất bại. Kiểm tra App Password (không dùng password thường).")
        print("     Tạo App Password: myaccount.google.com → Security → App passwords")
        return False
    except Exception as e:
        print(f"  ❌ Email error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send email notification with PDF attachment")
    parser.add_argument("--status",   required=True,
                        choices=["success", "preflight_fail"],
                        help="Loại email")
    parser.add_argument("--month",    required=True, help="YYYY-MM")
    parser.add_argument("--sources",  default="0",  help="Số nguồn available")
    parser.add_argument("--repo-url", default="",   help="GitHub repo URL")
    parser.add_argument("--pdf-path", default="",   help="Đường dẫn file PDF đính kèm")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path) if args.pdf_path else None

    if args.status == "success":
        has_pdf = bool(pdf_path and pdf_path.exists())
        subject, html = build_success_email(args.month, args.sources, args.repo_url, has_pdf)
    else:
        subject, html = build_fail_email(args.month, args.sources)
        pdf_path = None   # Không đính kèm PDF khi fail

    send_email(subject, html, pdf_path)


if __name__ == "__main__":
    main()
