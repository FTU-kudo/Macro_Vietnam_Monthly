#!/usr/bin/env python3
"""
scripts/render_report.py
─────────────────────────────────────────────────────────────
Bước 4: Inject data từ report.json vào HTML template.

Kỹ thuật: thay thế placeholder __REPORT_JSON__ và __HISTORY_JSON__
trong assets/report_template.html bằng JSON thật.
Template dùng JS để render các tab/card từ JSON.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


VI_MONTHS = [
    "", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4",
    "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8",
    "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
]


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def inject_data_into_template(
    template_html: str,
    report: dict,
    history: dict,
    month_str: str,
) -> str:
    """
    Thay thế các placeholder trong template:
      __REPORT_JSON__   → nội dung report.json
      __HISTORY_JSON__  → nội dung history.json
      __REPORT_MONTH__  → "YYYY-MM"
      __REPORT_TITLE__  → "Báo cáo vĩ mô Việt Nam – Tháng X/YYYY"
      __GENERATED_AT__  → ISO timestamp
      __VERDICT__       → verdict text
      __MONTH_BADGE__   → "Tháng X/YYYY"
      __PERIOD_LINE__   → "Kỳ báo cáo: YYYY-MM · Chốt: DD/MM/YYYY · N/5 nguồn: ..."
      __EVENT_CALENDAR__ → Bảng lịch sự kiện tháng tới
    """
    import calendar
    from datetime import timezone, timedelta
    year, month = int(month_str[:4]), int(month_str[5:7])
    vi_month = VI_MONTHS[month]
    title = f"Báo cáo vĩ mô Việt Nam – {vi_month} {year}"
    
    # Giờ Việt Nam (UTC+7)
    vn_tz = timezone(timedelta(hours=7))
    now_vn = datetime.now(vn_tz)
    generated_at = now_vn.strftime("%d/%m/%Y %H:%M (UTC+7)")
    generated_date = now_vn.strftime("%d/%m/%Y")
    
    last_day = calendar.monthrange(year, month)[1]
    data_cutoff_str = f"{last_day:02d}/{month:02d}/{year}"

    # Đọc sources từ _meta
    meta = report.get("_meta", {})
    sources_count = meta.get("sources_available", 0)
    sources_list  = meta.get("sources_list", [])
    SRC_LABELS = {
        "NSO": "TCTK", "PMI": "S&P PMI",
        "Customs": "Hải quan", "VBMA": "HTT Trái phiếu", "VNBA": "HN Ngân hàng",
    }
    if sources_count == 5:
        sources_badge = "5 nguồn: TCTK · Hải quan · S&amp;P PMI · HTT Trái phiếu · HN Ngân hàng"
    else:
        labels = [SRC_LABELS.get(s, s) for s in sources_list]
        sources_badge = f"{sources_count}/5 nguồn: {' · '.join(labels)}"

    month_badge  = f"{vi_month}/{year}"
    period_line  = f"Kỳ báo cáo: {month_str} (Số liệu chốt kỳ: {data_cutoff_str}) · Ngày thu thập &amp; tổng hợp: {generated_date} · {sources_badge}"

    # Serialize JSON (compact cho embed)
    report_js  = json.dumps(report,  ensure_ascii=False, separators=(",", ":"))
    history_js = json.dumps(history, ensure_ascii=False, separators=(",", ":"))

    # Format key takeaways
    takeaways_list = report.get("key_takeaways", [])
    takeaways_html_parts = []
    if isinstance(takeaways_list, list) and len(takeaways_list) > 0:
        for idx, tk in enumerate(takeaways_list):
            if isinstance(tk, dict):
                text = tk.get("text") or tk.get("content") or tk.get("description") or str(tk)
                star = tk.get("star", idx == 0)
            elif isinstance(tk, str):
                text = tk
                star = (idx == 0 and "⭐" in text) or (idx == 0)
            else:
                text = str(tk)
                star = (idx == 0)
            
            if star and not text.startswith("⭐"):
                text = f"<strong>⭐ Điểm nhấn {idx+1}:</strong> {text}"
            elif not text.startswith("⭐") and not text.startswith("<strong>"):
                text = f"<strong>Điểm nhấn {idx+1}:</strong> {text}"
            
            takeaways_html_parts.append(f"<li>{text}</li>")
        takeaways_html = "\n      ".join(takeaways_html_parts)
    else:
        takeaways_html = f"<li><strong>⭐ Tổng quan:</strong> {report.get('verdict_reason', 'Chưa có thông tin tổng hợp.')}</li>"

    # Thay thế
    html = template_html
    html = html.replace("__REPORT_JSON__",   report_js)
    html = html.replace("__HISTORY_JSON__",  history_js)
    html = html.replace("__REPORT_MONTH__",  month_str)
    html = html.replace("__REPORT_TITLE__",  title)
    html = html.replace("__GENERATED_AT__",  generated_at)
    html = html.replace("__GENERATED_DATE__", generated_date)
    html = html.replace("__VERDICT__",       report.get("verdict", "N/A"))
    html = html.replace("__VERDICT_REASON__", report.get("verdict_reason", ""))
    html = html.replace("__KEY_TAKEAWAYS__", takeaways_html)
    html = html.replace("__DATA_CUTOFF__",   data_cutoff_str)
    html = html.replace("__MONTH_BADGE__",   month_badge)
    html = html.replace("__PERIOD_LINE__",   period_line)
    html = html.replace("__EVENT_CALENDAR__", generate_event_calendar(month_str))

    return html


def generate_event_calendar(report_month: str) -> str:
    """
    Tạo lịch sự kiện kinh tế vĩ mô cho tháng tiếp theo (M+1) theo P10.
    """
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
        if m == 12:
            next_y, next_m = y + 1, 1
        else:
            next_y, next_m = y, m + 1
    except Exception:
        next_y, next_m = 2026, 7

    calendar_html = f"""<div class="panel">
      <div class="panel-head">
        <span class="panel-title">📅 Lịch sự kiện kinh tế vĩ mô đáng chú ý — Tháng {next_m}/{next_y}</span>
        <span class="panel-note">Nguồn: TCTK · S&amp;P Global · Fed Calendar · VBMA</span>
      </div>
      <table class="panel-table">
        <thead>
          <tr>
            <th style="width:120px">Thời gian</th>
            <th>Sự kiện / Chỉ số công bố</th>
            <th style="width:140px">Cơ quan / Nguồn</th>
            <th>Mức độ ảnh hưởng</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="mono">01/{next_m:02d}/{next_y}</td>
            <td>Công bố Chỉ số Nhà quản trị Mua hàng (PMI) sản xuất tháng {m}/{y}</td>
            <td>S&amp;P Global / PMI</td>
            <td><span class="panel-tag TRUNG">CAO</span></td>
          </tr>
          <tr>
            <td class="mono">29/{next_m:02d}/{next_y}</td>
            <td>Công bố Báo cáo Tình hình Kinh tế - Xã hội tháng {next_m}/{next_y}</td>
            <td>TCTK (NSO)</td>
            <td><span class="panel-tag TRUNG">RẤT CAO</span></td>
          </tr>
          <tr>
            <td class="mono">30/{next_m:02d}/{next_y}</td>
            <td>Cuộc họp Ủy ban Thị trường Mở Liên bang Mỹ (FOMC) quyết định lãi suất</td>
            <td>Cục Dự trữ Liên bang (Fed)</td>
            <td><span class="panel-tag TIÊU">RẤT CAO</span></td>
          </tr>
          <tr>
            <td class="mono">Trong tháng {next_m:02d}</td>
            <td>Đánh giá định kỳ điều hành lãi suất LNH, tỷ giá trung tâm và OMO</td>
            <td>NHNN / VBMA</td>
            <td><span class="panel-tag TÍCH">CAO</span></td>
          </tr>
        </tbody>
      </table>
    </div>"""
    return calendar_html


def generate_fallback_html(report: dict, history: dict, month_str: str) -> str:
    """
    Fallback: nếu không có template, tạo HTML đơn giản nhúng JSON.
    """
    year, month = int(month_str[:4]), int(month_str[5:7])
    title = f"Báo cáo vĩ mô Việt Nam – {VI_MONTHS[month]} {year}"
    verdict = report.get("verdict", "N/A")
    verdict_reason = report.get("verdict_reason", "")

    # Lấy 4 KPI chính từ Group 1
    g1 = report.get("group1_real_economy", {})
    cpi_val = g1.get("cpi", {}).get("comparisons", {}).get("yoy_pct", "N/A")
    g3 = report.get("group3_sector", {})
    pmi_val = g3.get("pmi", {}).get("value", "N/A")
    exports = g1.get("exports", {}).get("value", "N/A")
    exports_unit = g1.get("exports", {}).get("value_unit", "")

    report_js = json.dumps(report, ensure_ascii=False, indent=2)
    history_js = json.dumps(history, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg:#0f1117; --surface:#1a1d26; --accent:#4f9cf9; --text:#e2e8f0; --muted:#94a3b8; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:24px; }}
  .hero {{ background:var(--surface); border-radius:12px; padding:24px; margin-bottom:24px; }}
  h1 {{ font-size:1.4rem; color:var(--accent); margin-bottom:8px; }}
  .verdict {{ display:inline-block; padding:4px 12px; border-radius:6px; font-weight:700; font-size:0.9rem;
    background:{'#1a3a2a' if 'TÍCH CỰC' in verdict else '#3a1a1a' if 'TIÊU CỰC' in verdict else '#2a2a1a'}; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-top:16px; }}
  .kpi {{ background:#222535; border-radius:8px; padding:16px; }}
  .kpi-label {{ font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }}
  .kpi-value {{ font-size:1.6rem; font-weight:700; color:var(--accent); }}
  .json-block {{ background:#111; border-radius:8px; padding:16px; overflow:auto; font-size:0.75rem;
    color:#a0c4ff; font-family:'Fira Code',monospace; max-height:500px; margin-top:24px; }}
  .section-title {{ font-size:1rem; color:var(--muted); margin:24px 0 8px; }}
</style>
</head>
<body>
<div class="hero">
  <h1>📊 {title}</h1>
  <span class="verdict">{verdict}</span>
  <p style="margin-top:8px;color:var(--muted);font-size:0.875rem;">{verdict_reason}</p>
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">CPI YoY</div><div class="kpi-value">{cpi_val}%</div></div>
    <div class="kpi"><div class="kpi-label">PMI</div><div class="kpi-value">{pmi_val}</div></div>
    <div class="kpi"><div class="kpi-label">Xuất khẩu</div><div class="kpi-value">{exports} {exports_unit}</div></div>
  </div>
</div>

<p class="section-title">⚠️ Template đầy đủ chưa được load — đây là fallback view. Raw data đầy đủ bên dưới.</p>

<details>
  <summary style="cursor:pointer;color:var(--accent);">📄 report.json (full data)</summary>
  <div class="json-block"><pre>{report_js}</pre></div>
</details>

<details style="margin-top:16px;">
  <summary style="cursor:pointer;color:var(--accent);">📈 history.json (chuỗi thời gian)</summary>
  <div class="json-block"><pre>{history_js}</pre></div>
</details>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Render HTML report")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--report", required=True, help="report.json path")
    parser.add_argument("--history", required=True, help="history.json path")
    parser.add_argument("--template", default="assets/report_template.html",
                        help="HTML template path")
    parser.add_argument("--output", required=True, help="Output report.html")
    args = parser.parse_args()

    report = load_json(Path(args.report))
    history = load_json(Path(args.history)) if Path(args.history).exists() else {"series": {}}

    template_path = Path(args.template)

    if template_path.exists():
        template_html = template_path.read_text(encoding="utf-8")
        html = inject_data_into_template(template_html, report, history, args.month)
        print(f"  ✅ Template loaded: {template_path}")
    else:
        print(f"  ⚠️  Template không tìm thấy: {template_path} — dùng fallback HTML")
        html = generate_fallback_html(report, history, args.month)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"  💾 report.html → {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
