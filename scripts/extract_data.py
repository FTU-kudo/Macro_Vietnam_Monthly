#!/usr/bin/env python3
"""
scripts/extract_data.py
─────────────────────────────────────────────────────────────
Bước 3: Dùng Gemini API để extract 41 chỉ số từ sources đã cache.
Output: report.json (data structured, nguồn sự thật)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Đổi sang google-genai (package mới chính thức, generativeai đã deprecated)
from google import genai
from google.genai import types

# gemini-3.1-flash-lite: còn đủ quota (38/500 RPD), nhanh, phù hợp cho batch extract
MODEL = "gemini-3.1-flash-lite"
MAX_TOKENS = 8000

# ─────────────────────────────────────────────────────────────────
# SYSTEM PROMPT (giữ nguyên — không liên quan đến SDK)
# ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích vĩ mô Việt Nam (chuẩn CFA). Nhiệm vụ:
Extract 41 chỉ số kinh tế từ 5 nguồn chính thức và trả về JSON chuẩn.

## 4 RULES BẮT BUỘC

**Rule 1 – Nhất quán thời gian**
- "Nhìn lùi, không nhìn tới". Mọi số liệu phải ≤ data_cutoff (cuối tháng M).
- VBMA: chỉ lấy tuần kết thúc ≤ cutoff. VNBA: bỏ số "tuần 1 tháng M+1".

**Rule 2 – Frequency**
- Chỉ lấy số monthly. Bỏ số quý (Q/4 months).
- Tự loại: PBT ngân hàng quarterly, NIM quarterly.

**Rule 3 – Giải quyết xung đột**
- Ưu tiên: NSO > Customs > VBMA > VNBA > PMI (tuỳ chỉ số).
- Sai số ≤2%: ghi trung bình, source_secondary. >5%: flag conflict.

**Rule 4 – Quy ước đơn vị**
- Tỷ VND: `_b_vnd` (1 tỷ = 1,000,000,000 VND)
- Triệu USD: `_m_usd` | Tỷ USD: `_b_usd`
- Phần trăm: `_pct`
- Tách: `mom_pct` (month-on-month), `yoy_pct` (year-on-year), `ytd_avg_pct` (trung bình từ đầu năm)

## NGUYÊN TẮC KHÔNG PLACEHOLDER
- Chỉ tạo field khi có data thật trace được tới cache.
- KHÔNG tạo field với value null, "N/A", "THIẾU".
- Nếu thiếu → bỏ hẳn field đó.

## NARRATIVE – "Người kể chuyện số liệu"
- 2-4 câu kể diễn biến số. KHÔNG cho ý kiến hay dự báo.
- Dùng: "số liệu cho thấy", "cùng lúc", "đứng trên/dưới mục tiêu X kỳ liên tiếp".
- ĐỪNG: "tôi nghĩ", "dự báo", "nên mua/bán".

## OUTPUT FORMAT
Trả về ONLY JSON hợp lệ (không có markdown, không có ```json).
Schema:
{
  "report_id": "vn-macro-YYYY-MM",
  "period": {
    "month": M,
    "year": YYYY,
    "data_cutoff": "YYYY-MM-31",
    "generated_at": "ISO8601"
  },
  "verdict": "TÍCH CỰC | TRUNG TÍNH | TIÊU CỰC | CẢNH GIÁC",
  "verdict_reason": "1-2 câu tóm tắt",
  "group1_real_economy": {
    "cpi": {
      "name_vi": "Chỉ số giá tiêu dùng",
      "definition": "CPI YoY so cùng tháng năm trước",
      "value": 5.60,
      "value_unit": "%",
      "comparisons": {"mom_pct": 0.29, "yoy_pct": 5.60, "ytd_avg_pct": 4.31},
      "source_primary": "NSO",
      "signal": "GREEN | YELLOW | RED",
      "note": "...",
      "narrative": "...",
      "has_chart": true
    }
  },
  "group2_financial": {},
  "group3_sector": {},
  "group4_global_context": {},
  "risks": [{"level": "HIGH | MEDIUM | LOW", "description": "..."}],
  "catalysts": [{"description": "..."}],
  "key_takeaways": [{"rank": 1, "text": "...", "star": true}],
  "_data_provenance": {
    "_rule": "Mọi số phải trace được tới file cụ thể trong sources_cache/",
    "sources_files": {
      "nso_YYYY-MM.html": ["CPI", "IIP", "GDP", "XNK", "FDI", "bán lẻ"],
      "pmi_YYYY-MM.html": ["PMI headline", "PMI sub-indices"],
      "customs_YYYY-MM.txt": ["XK", "NK", "cán cân thương mại"],
      "vbma_YYYY-MM.txt": ["LNH", "tỷ giá", "TPCP", "TPDN"],
      "vnba_YYYY-MM.txt": ["lãi suất", "tín dụng", "huy động"]
    }
  }
}"""


# ─────────────────────────────────────────────────────────────────
# ĐỌC CACHE FILES (giữ nguyên — không liên quan đến SDK)
# ─────────────────────────────────────────────────────────────────

def read_cache_file(path: Path, max_chars: int = 30000) -> str | None:
    """Đọc file cache, truncate nếu quá dài."""
    if not path.exists():
        return None
    try:
        if path.suffix == ".html":
            content = path.read_text(encoding="utf-8", errors="ignore")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n[... truncated {len(text)-max_chars} chars ...]"
        return text
    except Exception as e:
        print(f"  ⚠️  Lỗi đọc {path.name}: {e}")
        return None


def build_user_prompt(
    year: int, month: int,
    nso_text: str | None,
    pmi_text: str | None,
    customs_text: str | None,
    vbma_text: str | None,
    vnba_text: str | None,
) -> str:
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    cutoff = f"{year}-{month:02d}-{last_day:02d}"
    vi_months = [
        "", "tháng 1", "tháng 2", "tháng 3", "tháng 4",
        "tháng 5", "tháng 6", "tháng 7", "tháng 8",
        "tháng 9", "tháng 10", "tháng 11", "tháng 12",
    ]
    return f"""Tháng báo cáo: {year}-{month:02d} ({vi_months[month]} năm {year})
Data cutoff: {cutoff}

⚠️ QUAN TRỌNG — CHỈ ĐƯỢC DÙNG DỮ LIỆU CỦA THÁNG {month}/{year}:
- Nếu nguồn cung cấp số liệu của tháng khác (ví dụ tháng 5/2026 trong khi báo cáo là tháng 3/2026),
  hãy BỎ QUA hoàn toàn — KHÔNG extract, KHÔNG đưa vào JSON.
- Chỉ lấy số liệu được công bố VÀO hoặc TRƯỚC ngày {cutoff}.
- Nếu không có số liệu nào cho tháng {month}/{year} từ một nguồn → bỏ trống nguồn đó.

Dưới đây là nội dung từ 5 nguồn chính thức. Hãy extract tất cả chỉ số kinh tế quan trọng.

=== NGUỒN 1: NSO (gso.gov.vn) ===
{nso_text or '[KHÔNG CÓ DỮ LIỆU]'}

=== NGUỒN 2: PMI (S&P Global) ===
{pmi_text or '[KHÔNG CÓ DỮ LIỆU]'}

=== NGUỒN 3: CUSTOMS (customs.gov.vn) ===
{customs_text or '[KHÔNG CÓ DỮ LIỆU]'}

=== NGUỒN 4: VBMA (vbma.org.vn) ===
{vbma_text or '[KHÔNG CÓ DỮ LIỆU]'}

=== NGUỒN 5: VNBA (vnba.org.vn) ===
{vnba_text or '[KHÔNG CÓ DỮ LIỆU]'}

Yêu cầu:
1. CHỈ extract số liệu của {vi_months[month]} năm {year} — bỏ qua tháng khác.
2. Extract tất cả chỉ số có trong các nguồn trên (tối đa 41 chỉ số).
3. Áp dụng 4 rules (Time/Frequency/Conflict/Unit) đã nêu trong system prompt.
4. Bỏ qua chỉ số thiếu data — KHÔNG tạo placeholder.
5. Với mỗi chỉ số Cấp A (CPI, PMI, IIP, XNK, FDI, LNH, tỷ giá, tín dụng, vàng), viết narrative 2-4 câu.
6. Trả về JSON hợp lệ theo schema đã định nghĩa.

Trả về JSON (không có markdown, không có backtick):"""


# ─────────────────────────────────────────────────────────────────
# FIX: GỌI GEMINI API (thay hoàn toàn hàm extract_with_claude)
# ─────────────────────────────────────────────────────────────────

def extract_with_gemini(user_prompt: str) -> dict:
    """Gọi Gemini API (google-genai) để extract data, trả về parsed JSON."""

    # Dùng google-genai Client-based API mới
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print(f"  🤖 Calling Gemini API ({MODEL})...")

    response = client.models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    raw_text = response.text.strip()

    # Làm sạch phòng hờ (bỏ ```json nếu có)
    raw_text = re.sub(r"^```json\s*", "", raw_text)
    raw_text = re.sub(r"```\s*$", "", raw_text).strip()

    try:
        data = json.loads(raw_text)
        print(f"  ✅ JSON parsed OK ({len(raw_text):,} chars)")
        return data
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        print(f"  Raw (first 500): {raw_text[:500]}")
        raise


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract VN Macro data via Gemini API")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--cache-dir", required=True, help="Directory chứa source cache")
    parser.add_argument("--output", required=True, help="Output report.json path")
    args = parser.parse_args()

    year, month = int(args.month[:4]), int(args.month[5:7])
    cache_dir = Path(args.cache_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n🔬 Extracting data cho {args.month}\n{'─' * 50}")

    def read(pattern: str) -> str | None:
        matches = list(cache_dir.glob(pattern))
        return read_cache_file(matches[0]) if matches else None

    nso_text     = read(f"nso_{args.month}.*")
    pmi_text     = read(f"pmi_{args.month}.*")
    customs_text = read(f"customs_{args.month}.*")
    vbma_text    = read(f"vbma_{args.month}.txt") or read(f"vbma_{args.month}.*")
    vnba_text    = read(f"vnba_{args.month}.txt") or read(f"vnba_{args.month}.*")

    sources_available = sum(x is not None for x in [
        nso_text, pmi_text, customs_text, vbma_text, vnba_text
    ])
    print(f"  📂 Sources available: {sources_available}/5")

    if sources_available == 0:
        print("  ❌ Không có source nào — abort")
        sys.exit(1)

    user_prompt = build_user_prompt(
        year, month, nso_text, pmi_text, customs_text, vbma_text, vnba_text
    )

    # FIX: gọi extract_with_gemini thay vì extract_with_claude
    report_data = extract_with_gemini(user_prompt)
    report_data["_meta"] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": MODEL,
        "sources_available": sources_available,
        "cache_dir": str(cache_dir),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"  💾 report.json → {output_path}")
    print(f"  🏷️  Verdict: {report_data.get('verdict', 'N/A')}")


if __name__ == "__main__":
    main()
