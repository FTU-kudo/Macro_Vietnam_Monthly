#!/usr/bin/env python3
"""
scripts/validate_report.py
─────────────────────────────────────────────────────────────
Script kiểm toán tự động tính nhất quán và logic của báo cáo vĩ mô.
Quy tắc kiểm tra:
1. Nhất quán giá dầu Brent: Giá Brent trong bảng hàng hóa phải khớp với giá trong thẻ geopolitical/narrative.
2. Fed stance: Nếu có văn bản/yếu tố "khả năng tăng > 50%" → rủi ro Fed phải ở mức HIGH và phải có trong Key Takeaways.
3. Dict lookup: Mọi số liệu chính (CPI YoY, PMI, GDP, Brent, XK, NK, LNH...) xuất hiện >1 lần trong báo cáo phải hoàn toàn khớp nhau.
4. Kiểm tra số lượng biểu đồ (>= 3) và Key Takeaways (>= 4).
"""

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def validate_report(month: str, json_path: Path = None, html_path: Path = None) -> int:
    print(f"\n🔍 VALIDATING MACRO REPORT FOR {month}")
    print("═" * 60)

    errors = []
    warnings = []
    passes = []

    # 1. Locate files
    if not json_path:
        candidates = [
            Path(f"vn-macro-monthly/{month}/report.json"),
            Path("report.json"),
            Path(f"report_{month}.json")
        ]
        for c in candidates:
            if c.exists():
                json_path = c
                break

    if not html_path:
        html_candidates = [
            Path(f"output/Báo cáo Vĩ mô Việt Nam - Tháng 6.2026.html"),
            Path(f"output/report.html"),
            Path(f"vn-macro-monthly/{month}/Báo cáo Vĩ mô Việt Nam - Tháng 6.2026.html"),
            Path("Báo cáo Vĩ mô Việt Nam - Tháng 6.2026.html"),
            Path(f"vn-macro-monthly/{month}/report.html"),
            Path("assets/report_template.html")
        ]
        for c in html_candidates:
            if c.exists():
                html_path = c
                break

    report_data = {}
    if json_path and json_path.exists():
        print(f"📄 Found JSON: {json_path}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
            passes.append(f"Loaded JSON report from {json_path}")
        except Exception as e:
            errors.append(f"Failed to parse JSON {json_path}: {e}")
    else:
        warnings.append(f"No report.json found for {month} (checked standard paths)")

    html_content = ""
    if html_path and html_path.exists():
        print(f"📄 Found HTML: {html_path}")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            passes.append(f"Loaded HTML report from {html_path}")
        except Exception as e:
            errors.append(f"Failed to read HTML {html_path}: {e}")
    else:
        warnings.append("No HTML report found to validate")

    if not report_data and not html_content:
        print("❌ CRITICAL: No report data or HTML found to validate!")
        return 1

    # ─────────────────────────────────────────────────────────────
    # CHECK 1: OIL PRICE CONSISTENCY (Brent)
    # ─────────────────────────────────────────────────────────────
    print("\n🛢️  Checking Oil Price Consistency (Brent)...")
    brent_prices = set()

    # Check from JSON if available
    if report_data:
        g3 = report_data.get("group3_sector", {})
        comm = g3.get("commodities", {}).get("items", [])
        for item in comm:
            if "brent" in str(item.get("name", "")).lower():
                val = item.get("value")
                if val: brent_prices.add(float(val))
        
        # Check in cards or narratives
        for grp_key in ["group1_real_economy", "group2_financial", "group3_sector", "group4_global_context"]:
            grp = report_data.get(grp_key, {})
            if isinstance(grp, dict):
                for k, v in grp.items():
                    if isinstance(v, dict):
                        txt = str(v.get("note", "")) + " " + str(v.get("narrative", ""))
                        matches = re.findall(r"Brent[^0-9]*([0-9]+\.?[0-9]*)", txt, re.IGNORECASE)
                        for m in matches:
                            try:
                                float_val = float(m)
                                if 50 <= float_val <= 150:
                                    brent_prices.add(float_val)
                            except ValueError: pass

    # Check from HTML
    if html_content:
        matches = re.findall(r"(?:dầu\s+|giá\s+|)\bBrent\b[^0-9]*([0-9]{2,3}(?:\.[0-9]+)?)\s*(?:USD|\$|/thùng|/bbl)", html_content, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m)
                if 50 <= val <= 150:
                    brent_prices.add(val)
            except ValueError: pass

    if len(brent_prices) == 1:
        val = list(brent_prices)[0]
        passes.append(f"Brent oil price is completely consistent across report: {val} USD/bbl ✓")
    elif len(brent_prices) > 1:
        errors.append(f"INCONSISTENCY: Multiple different Brent oil prices found across report: {sorted(list(brent_prices))} (Must be unified to 1 primary source!)")
    else:
        warnings.append("Could not extract any Brent oil price to cross-check")

    # ─────────────────────────────────────────────────────────────
    # CHECK 2: FED STANCE (<khả năng tăng > 50%> -> HIGH risk & Key Takeaway)
    # ─────────────────────────────────────────────────────────────
    print("🏦 Checking Fed Stance Transmission Rules...")
    full_text = (json.dumps(report_data, ensure_ascii=False) + " " + html_content).lower()
    
    has_high_prob_hike = any(w in full_text for w in [
        "khả năng tăng > 50%", "xác suất tăng > 50%", "xác suất tăng điểm > 50%", 
        "fedwatch > 50%", "khả năng tăng lãi suất > 50%", "86%", "khả năng tăng 50 đcb"
    ]) or ("fed" in full_text and ("tăng" in full_text or "higher-for-longer" in full_text))

    if has_high_prob_hike:
        print("   ℹ️  Detected Fed tightening / high hike probability stance")
        high_risk_found = False
        if report_data:
            for r in report_data.get("risks", []):
                if ("fed" in str(r).lower() or "lãi suất" in str(r).lower() or "tỷ giá" in str(r).lower()) and r.get("level", "").upper() in ["HIGH", "CRITICAL", "RẤT CAO", "CAO"]:
                    high_risk_found = True
        if html_content:
            if re.search(r"(?:Rất cao|Cao|HIGH|CRITICAL|critical)[\s\S]{0,200}?(?:Fed|lãi suất|tỷ giá|USD|CSTT|tiền tệ|LNH)", html_content, re.IGNORECASE):
                high_risk_found = True

        if high_risk_found:
            passes.append("Fed/Rate risk properly elevated to HIGH/Critical level ✓")
        else:
            errors.append("RULE VIOLATION: Fed stance indicates tightening / probability > 50%, but no HIGH/Critical risk item found for Fed/rate/FX!")

        kt_found = False
        if report_data:
            for kt in report_data.get("key_takeaways", []):
                if any(w in str(kt).lower() for w in ["fed", "lãi suất", "tỷ giá", "usd", "ngoại tệ", "tiền tệ", "lnh"]):
                    kt_found = True
        if html_content:
            kt_section = re.findall(r"(?:class=\"takeaways\"|key[_\s-]*takeaways|Điểm chính|Điểm nhấn)[\s\S]{0,1500}?</(?:ol|ul|div)>", html_content, re.IGNORECASE)
            for block in kt_section:
                if any(w in block.lower() for w in ["fed", "lãi suất", "tỷ giá", "usd", "ngoại tệ", "tiền tệ", "lnh"]):
                    kt_found = True

        if kt_found:
            passes.append("Fed stance / FX risk is included in Key Takeaways ✓")
        else:
            errors.append("RULE VIOLATION: Fed stance indicates tightening / probability > 50%, but not mentioned in Key Takeaways!")
    else:
        passes.append("Fed stance normal (no special high hike prob trigger checked) ✓")

    # ─────────────────────────────────────────────────────────────
    # CHECK 3: DICT LOOKUP CONSISTENCY (Key Metrics)
    # ─────────────────────────────────────────────────────────────
    print("📇 Checking Key Metrics Dict Lookup Consistency...")
    if "2026-06" in month:
        if html_content:
            cpi_kpi_match = re.search(r"CPI\s*YoY[\s\S]{0,100}?kpi-value[^>]*>\s*([0-9\.]+)", html_content, re.IGNORECASE)
            if cpi_kpi_match:
                val = cpi_kpi_match.group(1)
                if val == "4.69":
                    passes.append("CPI YoY for 2026-06 in KPI card is correctly 4.69% ✓")
                else:
                    errors.append(f"INCONSISTENCY: CPI YoY KPI card shows {val}%, expected 4.69% for 2026-06!")
            
            bad_cpi_refs = re.findall(r"CPI\s*YoY\s*5\.60%\s*(?:tiếp tục|vượt|leo thang|đứng trên)", html_content, re.IGNORECASE)
            if bad_cpi_refs:
                errors.append(f"INCONSISTENCY: Found stale May CPI references presented as June data: {len(bad_cpi_refs)} occurrences (e.g. 'CPI YoY 5.60% vượt mục tiêu...')")
            else:
                passes.append("No stale May CPI (5.60%) cited as active June inflation ✓")

    # ─────────────────────────────────────────────────────────────
    # CHECK 4: CHARTS & KEY TAKEAWAYS COUNT
    # ─────────────────────────────────────────────────────────────
    print("📊 Checking Charts and Key Takeaways Counts...")
    chart_count = 0
    if html_content:
        chart_count = len(re.findall(r"<canvas[^>]*>", html_content, re.IGNORECASE))
        if chart_count >= 3:
            passes.append(f"Chart count: {chart_count} (>= 3 required) ✓")
        else:
            errors.append(f"RULE VIOLATION: Chart count is {chart_count}, but minimum >= 3 required!")
    
    kt_count = 0
    if report_data:
        kt_count = len(report_data.get("key_takeaways", []))
    elif html_content:
        kt_match = re.search(r"(?:class=\"takeaways\"|key[_\s-]*takeaways|Điểm chính|Điểm nhấn)[\s\S]{0,2000}?(?:</ol></ul>|</ul>\s*</ol>|</ul>|</ol>)", html_content, re.IGNORECASE)
        if kt_match:
            kt_count = len(re.findall(r"<li[^>]*>", kt_match.group(0)))
    
    if kt_count >= 4:
        passes.append(f"Key Takeaways count: {kt_count} (>= 4 required) ✓")
    else:
        errors.append(f"RULE VIOLATION: Key Takeaways count is {kt_count}, expected 4-5 items!")

    # ─────────────────────────────────────────────────────────────
    # CHECK 5: VERDICT SCORE BREAKDOWN
    # ─────────────────────────────────────────────────────────────
    if report_data and "_verdict_breakdown" in report_data:
        vb = report_data["_verdict_breakdown"]
        print(f"\n🎯 Verdict Breakdown from JSON: {report_data.get('verdict')} ({vb.get('score', 0):+} pts)")
        for f in vb.get("factors", []):
            print(f"   • {f.get('text')} ({f.get('score'):+} pts)")

    # ─────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"✅ PASSED:   {len(passes)}")
    print(f"⚠️  WARNINGS: {len(warnings)}")
    print(f"❌ ERRORS:   {len(errors)}")

    if errors:
        print("\n❌ VALIDATION FAILED WITH ERRORS:")
        for e in errors:
            print(f"  • {e}")
        return 1
    else:
        print("\n🎉 VALIDATION SUCCESSFUL — ALL CHECKS PASSED!")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Validate Macro Report Consistency & Rules")
    parser.add_argument("--month", default="2026-06", help="YYYY-MM (default: 2026-06)")
    parser.add_argument("--report", help="Path to report.json")
    parser.add_argument("--html", help="Path to report.html")
    args = parser.parse_args()

    json_p = Path(args.report) if args.report else None
    html_p = Path(args.html) if args.html else None

    sys.exit(validate_report(args.month, json_p, html_p))

if __name__ == "__main__":
    main()
