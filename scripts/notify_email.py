#!/usr/bin/env python3
"""
scripts/notify_email.py
─────────────────────────────────────────────────────────────
Gửi email thông báo kèm PDF + HTML báo cáo qua Gmail.
Repo private → không dùng link online, thay bằng đính kèm HTML.

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
from datetime import datetime, timezone, timedelta
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))


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
    has_html: bool = False,
) -> tuple[str, str]:
    """Tạo email subject + HTML body đẹp cho success."""
    year, m = int(month[:4]), int(month[5:7])
    vi_month = VI_MONTHS[m]
    # Giờ Việt Nam (UTC+7)
    generated = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M (giờ Việt Nam)")
    # Tên file đính kèm theo tháng
    pdf_name  = f"Báo cáo Vĩ mô Việt Nam - Tháng {m}.{year}.pdf"
    html_name = f"Báo cáo Vĩ mô Việt Nam - Tháng {m}.{year}.html"

    subject = f"📊 [VN Macro] Báo cáo {vi_month}/{year} · {sources}/5 nguồn"

    # Ghi chú đính kèm
    if has_pdf and has_html:
        attach_note = (
            '<div style="margin-top:12px;padding:10px 14px;background:rgba(16,185,129,0.1);'
            'border-radius:8px;border:1px solid rgba(16,185,129,0.25);">'
            '<p style="color:#10b981;font-size:13px;margin:0;font-weight:600;">📎 Đính kèm trong email:</p>'
            '<ul style="color:#94a3b8;font-size:12px;margin:6px 0 0;padding-left:16px;line-height:1.8;">'
            f'<li><strong style="color:#f1f5f9;">{pdf_name}</strong> — In &amp; lưu trữ</li>'
            f'<li><strong style="color:#f1f5f9;">{html_name}</strong> — Mở bằng Chrome/Edge để xem full theme + biểu đồ</li>'
            '</ul></div>'
        )
    elif has_pdf:
        attach_note = (
            '<p style="color:#10b981;font-size:13px;margin:12px 0 0;">'
            '📎 <strong>File PDF đính kèm</strong> trong email này để đọc offline.</p>'
        )
    elif has_html:
        attach_note = (
            '<div style="margin-top:12px;padding:10px 14px;background:rgba(6,182,212,0.08);'
            'border-radius:8px;border:1px solid rgba(6,182,212,0.2);">'
            '<p style="color:#06b6d4;font-size:13px;margin:0;font-weight:600;">📎 Đính kèm: report.html</p>'
            '<p style="color:#94a3b8;font-size:12px;margin:4px 0 0;">Tải xuống → mở bằng Chrome/Edge để xem báo cáo đầy đủ với biểu đồ.</p>'
            '</div>'
        )
    else:
        attach_note = (
            '<p style="color:#64748b;font-size:12px;margin:12px 0 0;">'
            '(Tệp đính kèm không khả dụng lần này.)</p>'
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
      {vi_month}/{year} · Cập nhật mới nhất: {generated}
    </p>
  </div>

  <!-- Status card -->
  <div style="background:#1e293b;border-radius:12px;padding:20px 24px;
              margin-bottom:16px;border:1px solid rgba(255,255,255,0.08);">
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <td style="padding:6px 0;color:#94a3b8;font-size:13px;width:150px;">Kỳ báo cáo</td>
        <td style="padding:6px 0;color:#f1f5f9;font-weight:600;font-size:13px;">{vi_month}/{year} (chốt số liệu hết tháng)</td>
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

    {attach_note}
  </div>

  <!-- Hướng dẫn mở HTML -->
  <div style="background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.2);
              border-radius:10px;padding:14px 18px;margin-bottom:20px;">
    <p style="color:#c4b5fd;font-size:12px;margin:0;line-height:1.7;">
      💡 <strong>Cách xem báo cáo đầy đủ:</strong>
      Tải file <code style="background:rgba(255,255,255,0.1);padding:1px 5px;border-radius:3px;">{html_name}</code>
      đính kèm &rarr; mở bằng <strong>Chrome</strong> hoặc <strong>Edge</strong> &rarr; xem báo cáo
      với biểu đồ tương tác và dark theme.<br>
      <span style="color:#8b8ba7;font-size:11px;margin-top:4px;display:inline-block;">
        PDF dùng để in ấn &amp; lưu trữ; HTML dùng để đọc trực tiếp trên máy tính.
      </span>
    </p>
  </div>

  <!-- Footer -->
  <p style="text-align:center;color:#475569;font-size:11px;margin:0;line-height:1.7;">
    © Bản quyền thuộc về FTU-Kudo<br>
    Email này được tạo tự động — Vui lòng không reply.
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


def attach_file(msg: MIMEMultipart, file_path: Path, mime_type: tuple,
                max_mb: float = 24.0) -> bool:
    """Dính kèm file vào email, trả về True nếu thành công."""
    if not file_path.exists():
        return False
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        print(f"  ⚠️  {file_path.name} quá lớn ({size_mb:.1f} MB > {max_mb} MB) — bỏ qua")
        return False
    with open(file_path, "rb") as f:
        part = MIMEBase(*mime_type)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    # Dùng keyword argument (filename=..., name=...) để Python tự động mã hóa chuẩn RFC 2231/2047 cho tên file tiếng Việt UTF-8
    part.add_header("Content-Disposition", "attachment", filename=file_path.name)
    part.add_header("Content-Type", f"{mime_type[0]}/{mime_type[1]}", name=file_path.name)
    msg.attach(part)
    print(f"  📎 Đính kèm: {file_path.name} ({size_mb:.1f} MB)")
    return True


def send_email(subject: str, html_body: str,
               pdf_path: Path | None = None,
               html_path: Path | None = None) -> bool:
    """Gửi email qua Gmail SMTP, đính kèm PDF và/hoặc HTML nếu có."""
    user     = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASS", "")
    to_raw   = os.environ.get("EMAIL_TO", "")

    if not all([user, password, to_raw]):
        print("  ⚠️  Email secrets chưa được cấu hình — bỏ qua gửi email")
        print("      Cần: EMAIL_USER, EMAIL_PASS (App Password), EMAIL_TO")
        return False

    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"VN Macro Bot <{user}>"
    # Gửi dạng BCC để bảo mật danh sách khách hàng (không ai thấy email của người khác)
    # Trong header To: chỉ để tên và email của chính bot/người gửi, danh sách recipients thực tế được truyền ngầm vào server.sendmail()
    msg["To"]      = f"VN Macro Report <{user}>"

    # HTML body
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Đính kèm PDF (nếu có, < 24 MB)
    if pdf_path:
        attach_file(msg, pdf_path, ("application", "pdf"), max_mb=24.0)

    # Đính kèm HTML (nếu có, < 10 MB)
    if html_path:
        attach_file(msg, html_path, ("text", "html"), max_mb=10.0)

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
    parser = argparse.ArgumentParser(description="Send email notification with PDF+HTML attachment")
    parser.add_argument("--status",    required=True,
                        choices=["success", "preflight_fail"],
                        help="Loại email")
    parser.add_argument("--month",     required=True, help="YYYY-MM")
    parser.add_argument("--sources",   default="0",   help="Số nguồn available")
    parser.add_argument("--repo-url",  default="",    help="GitHub repo URL")
    parser.add_argument("--pdf-path",  default="",    help="Đường dẫn file PDF đính kèm")
    parser.add_argument("--html-path", default="",    help="Đường dẫn file HTML đính kèm")
    parser.add_argument("--report",    default="",    help="Đường dẫn file report.json")
    args = parser.parse_args()

    pdf_path  = Path(args.pdf_path)  if args.pdf_path  else None
    html_path = Path(args.html_path) if args.html_path else None
    if not pdf_path or not pdf_path.exists():
        cand = Path("output") / f"Báo cáo Vĩ mô Việt Nam - Tháng {int(args.month[5:7]) if len(args.month)>=7 else 6}.{args.month[:4] if len(args.month)>=4 else '2026'}.pdf"
        if cand.exists(): pdf_path = cand
    if not html_path or not html_path.exists():
        cand = Path("output") / f"Báo cáo Vĩ mô Việt Nam - Tháng {int(args.month[5:7]) if len(args.month)>=7 else 6}.{args.month[:4] if len(args.month)>=4 else '2026'}.html"
        if cand.exists(): html_path = cand

    sources = args.sources
    # Nếu có file report.json, ưu tiên lấy chính xác số nguồn thực tế từ file report.json để đồng bộ 100% với PDF/HTML
    report_path = Path(args.report) if args.report else Path(f"vn-macro-monthly/{args.month}/report.json")
    if report_path.exists():
        try:
            import json
            with open(report_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                meta_sources = d.get("_meta", {}).get("sources_available")
                if meta_sources is not None:
                    sources = str(meta_sources)
                    print(f"  🔍 Đồng bộ số nguồn từ {report_path}: {sources}/5 nguồn")
        except Exception as e:
            print(f"  ⚠️ Không đọc được sources_available từ {report_path}: {e}")

    if args.status == "success":
        has_pdf  = bool(pdf_path  and pdf_path.exists())
        has_html = bool(html_path and html_path.exists())
        subject, html = build_success_email(
            args.month, sources, args.repo_url, has_pdf, has_html
        )
    else:
        subject, html = build_fail_email(args.month, sources)
        pdf_path  = None
        html_path = None

    send_email(subject, html, pdf_path, html_path)


if __name__ == "__main__":
    main()
