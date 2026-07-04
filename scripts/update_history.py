#!/usr/bin/env python3
"""
scripts/update_history.py
─────────────────────────────────────────────────────────────
Append tháng mới vào history.json (chuỗi thời gian cho chart).

Theo SKILL.md Rules:
  - Re-run tháng cũ → ghi đè (1 tháng = 1 giá trị)
  - Bắt đầu trống — KHÔNG seed data cũ
  - Đủ 6+ tháng → chart Cấp A render sparkline
"""

import argparse
import json
from pathlib import Path

# Các series được theo dõi trong history.json
TRACKED_SERIES = {
    # Group 1: Kinh tế thực
    "cpi_yoy_pct":       ("group1_real_economy", "cpi", "comparisons", "yoy_pct"),
    "iip_yoy_pct":       ("group1_real_economy", "iip", "comparisons", "yoy_pct"),
    "gdp_growth_pct":    ("group1_real_economy", "gdp", "comparisons", "yoy_pct"),
    "retail_sales_yoy":  ("group1_real_economy", "retail_sales", "comparisons", "yoy_pct"),
    "fdi_realized_b_usd":("group1_real_economy", "fdi_realized", "value"),
    "export_yoy_pct":    ("group1_real_economy", "exports", "comparisons", "yoy_pct"),
    "import_yoy_pct":    ("group1_real_economy", "imports", "comparisons", "yoy_pct"),

    # Group 2: Tài chính & Tiền tệ
    "credit_growth_pct": ("group2_financial", "credit_growth", "comparisons", "ytd_pct"),
    "exchange_rate_usd": ("group2_financial", "exchange_rate_usd", "value"),
    "gold_sjc_b_vnd":    ("group2_financial", "gold_sjc", "value"),
    "bond_gov_10y_pct":  ("group2_financial", "bond_gov_10y", "value"),

    # Group 3: PMI
    "pmi":               ("group3_sector", "pmi", "value"),
    "pmi_output":        ("group3_sector", "pmi_output", "value"),
    "pmi_new_orders":    ("group3_sector", "pmi_new_orders", "value"),

    # Group 4: Global
    "us_10y_yield_pct":  ("group4_global_context", "us_10y_yield", "value"),
    "wti_oil_usd":       ("group4_global_context", "wti_oil", "value"),
    "dxy":               ("group4_global_context", "dxy", "value"),
}


def deep_get(d: dict, *keys, default=None):
    """Safe nested dict access."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, {})
    return d if d != {} else default


def load_history(history_path: Path) -> dict:
    """Load hoặc khởi tạo history.json."""
    if history_path.exists():
        with open(history_path, encoding="utf-8") as f:
            return json.load(f)
    # Khởi tạo mới (trống — không seed)
    return {"series": {key: [] for key in TRACKED_SERIES}}


def update_history(history: dict, report: dict, month_str: str) -> dict:
    """Append (hoặc overwrite) giá trị tháng M vào history."""
    if "series" not in history:
        history["series"] = {}

    for series_key, path in TRACKED_SERIES.items():
        if series_key not in history["series"]:
            history["series"][series_key] = []

        # Lấy giá trị từ report.json
        value = deep_get(report, *path)
        if value is None or value == {}:
            continue  # Không có data → skip (không placeholder)

        # Overwrite nếu tháng đã tồn tại, append nếu mới
        series = history["series"][series_key]
        existing_idx = next(
            (i for i, entry in enumerate(series) if entry.get("month") == month_str),
            None
        )
        entry = {"month": month_str, "value": value}
        if existing_idx is not None:
            series[existing_idx] = entry  # Overwrite
        else:
            series.append(entry)          # Append

        # Sort theo thứ tự thời gian
        history["series"][series_key] = sorted(series, key=lambda x: x["month"])

    return history


def main():
    parser = argparse.ArgumentParser(description="Update history.json")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--report", required=True, help="report.json path")
    parser.add_argument("--history", required=True, help="history.json path")
    args = parser.parse_args()

    report_path = Path(args.report)
    history_path = Path(args.history)

    # Load
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    history = load_history(history_path)

    # Update
    history = update_history(history, report, args.month)

    # Thống kê
    filled_series = {
        k: len(v) for k, v in history["series"].items() if v
    }
    ready_for_chart = sum(1 for v in filled_series.values() if v >= 6)

    # Save
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"  💾 history.json updated: {len(filled_series)} series, {ready_for_chart} chart-ready (≥6 tháng)")
    print(f"  📁 {history_path}")


if __name__ == "__main__":
    main()
