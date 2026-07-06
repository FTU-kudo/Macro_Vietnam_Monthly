---
name: vn-macro-monthly
description: Báo cáo vĩ mô Việt Nam hàng tháng (toàn diện, 41 chỉ số) từ 5 nguồn chính thức miễn phí (NSO + Customs + S&P PMI + VBMA + VNBA). Use when người dùng yêu cầu "báo cáo vĩ mô", "monthly macro report", "CPI/PMI/XNK hàng tháng", "tình hình kinh tế VN tháng", hoặc khi cần dashboard vĩ mô bao phủ sản xuất + ngoại thương + tiền tệ + tài chính. Cốt lõi = theo yêu cầu skill với kiểm tra toàn vẹn (tất cả hoặc không gì cả) + 4 nguyên tắc (Thời gian/Tần suất/Xung đột/Đơn vị) + HTML dashboard 4 nhóm.
---

# VN Macro Monthly

Báo cáo vĩ mô Việt Nam hàng tháng — **toàn diện 41 chỉ số** bao phủ 4 trụ cột: sản xuất + ngoại thương + tiền tệ + tài chính. Theo yêu cầu (người dùng tự quyết định khi chạy), tất cả hoặc không gì cả (5/5 nguồn mới làm).

## Điều kiện tiên quyết

Không phụ thuộc skill khác (data từ 5 nguồn web chính thức). Nhưng output bổ sung tốt cho:
- `vn-news-digest` — thời sự 30 ngày cho cổ phiếu cụ thể
- `vn-research-dashboard` — equity research (vĩ mô = context cho định giá cổ phiếu)

## Workflow 4 bước

### Bước 1: Kiểm tra toàn vẹn (pre-flight) — tất cả hoặc không gì cả (BẮT BUỘC)

**Kiểm tra 5 nguồn có tồn tại cho tháng M chưa**. Nếu thiếu bất kỳ nguồn → **DỪNG**, không làm partial.

```
User: /vn-macro-monthly 2026-05
  ↓
WebSearch check 5 nguồn:
  - PMI (S&P): "Vietnam Manufacturing PMI" [tháng] [năm] site:pmi.spglobal.com
  - NSO: nso.gov.vn "báo cáo kinh tế xã hội" tháng [M] [Y]
  - Customs: customs.gov.vn tkId "tháng [M] [Y]"
  - VBMA: vbma.org.vn "BAO CAO TUAN TTP" [tuần cuối tháng M]
  - VNBA: vnba.org.vn "thông tin kinh tế tài chính" tháng [M] [Y]
  ↓
5/5? → Bước 2  |  thiếu? → DỪNG + đề xuất ngày thử lại
```

→ **KHÔNG tạo thư mục** khi bị DỪNG (máy sạch). Xem `references/preflight_check.md` cho lịch release + gợi ý thử lại.

### Bước 1.5: Partial run workflow (khi user override all-or-nothing)

All-or-nothing rule (Bước 1) cấm partial. Nhưng **user có quyền override** khi cần gấp (VD: chạy 3/5 nguồn vì Customs + VNBA chưa publish). Khi user override, áp dụng quy tắc sau:

```
User: "dùng 3 nguồn đã có" / "bỏ qua pre-flight" / tương đương
  ↓
1. Tạo thư mục + cache NHƯNG chỉ với nguồn có sẵn
2. Áp dụng Nguyên tắc KHÔNG placeholder (Bước 3.6) — KHÔNG tạo card cho chỉ số thiếu nguồn
3. Thêm 1 dòng coverage-warn ở hero ghi rõ "X/5 nguồn"
4. Bỏ qua Bước 3.5 (news enrichment) nếu partial < 4/5 nguồn — focus data chính
5. Trong report.json, thêm field `_sources_coverage` ghi nhận override
6. Cuối output, đề xuất ngày retry khi đủ 5 nguồn
```

**`_sources_coverage` schema trong report.json**:
```json
"_sources_coverage": {
  "available": ["PMI", "NSO", "VBMA"],
  "missing": ["Customs", "VNBA"],
  "user_override": true,
  "retry_hint": "Thử lại sau 15/07/2026 khi đủ 5 nguồn"
}
```

**Khi nào KHÔNG override** (user yêu cầu rõ "đợi đủ 5 nguồn" hoặc không nói gì → mặc định all-or-nothing).

### Bước 2: Fetch + cache 5 nguồn (Option C: PDF + text + JSON)

Tạo thư mục `{project}/vn-macro-monthly/2026-05/` (chỉ khi pre-flight ĐẠT). Tải về `sources_cache/`:

```bash
# PMI + NSO: WebReader trực tiếp
# Customs: WebSearch tkId → nguồn thứ cấp (VnEconomy/Báo CP) → .txt
# VBMA: curl + pdftotext (URL có %20 → WebReader fail)
curl -sL "https://vbma.org.vn/storage/reports/May2026/25052026-29052026%20%20BAO%20CAO%20TUAN%20TTTP.pdf" \
  -o "sources_cache/vbma_weekly_25-29may_2026.pdf"
pdftotext -layout sources_cache/vbma_weekly_25-29may_2026.pdf sources_cache/vbma_weekly_25-29may_2026.txt

# VNBA: WebSearch trang tin → lấy CDN link → curl + pdftotext
```

→ Xem `references/sources_overview.md` cho URL pattern + cách fetch từng nguồn.

### Bước 3: Extract 41 chỉ số + apply 4 rules

Parse text từ cache → extract theo **Thẻ dữ liệu schema** (11 trường). Áp 4 rules bắt buộc:

1. **Nhất quán thời gian** — mọi số ≤ data_cutoff (31/05/2026). VBMA chỉ lấy tuần kết thúc ≤ cutoff, VNBA bỏ "tuần 1 tháng 6".
2. **Frequency** — chỉ monthly, bỏ quý (→ tự loại PBT/NIM ngân hàng).
3. **Giải quyết xung đột** — Thứ tự ưu tiên nguồn chính + Kiểm chứng định nghĩa trước + Sai số chấp nhận được.
4. **Quy ước đơn vị** — đuôi trường chuẩn (`_b_vnd`, `_b_usd`, `_pct`...), tách mom/yoy/ytd.

→ Xem `references/core_rules.md` cho chi tiết 4 rules + `references/data_cards.md` cho schema + 41 chỉ số mapping theo 4 nhóm priority.

```json
{
  "cpi": {
    "name_vi": "Chỉ số giá tiêu dùng",
    "definition": "CPI YoY = tháng hiện tại vs cùng tháng năm trước",
    "value": 5.60, "value_unit": "%",
    "comparisons": {"mom_pct": 0.29, "yoy_pct": 5.60, "ytd_avg_pct": 4.31},
    "source_primary": "NSO",
    "signal": "RED",
    "note": "Vượt target 4.5%",
    "has_chart": true
  }
}
```

Tạo `report.json` (nguồn dữ liệu chuẩn) + **append** vào `history.json` (cho chart sau này).

### Bước 3.1: Narrative — đóng vai "người kể chuyện số liệu" (BẮT BUỘC cho 10+ card quan trọng)

Sau khi data chính xong, mỗi card quan trọng (CPI, PMI, IIP, XNK, LNH, FDI, TPDN, tỷ giá, tín dụng, vàng) phải có field `narrative` — **2-4 câu kể chuyện số liệu**.

**Nguyên tắc tone — "Người kể chuyện số liệu, KHÔNG phải người cho ý kiến"**:

| ❌ Tránh | ✅ Làm |
|---|---|
| "CPI vượt target → NHNN sẽ phải siết tiền tệ" | "CPI YoY 5.60% đã đứng trên mục tiêu 4.5% tháng thứ 2 liên tiếp, cùng lúc PMI Chi phí đạt đỉnh 15 năm — hai con số này cùng kể câu chuyện lạm phát chi phí." |
| "Tôi dự báo Q3 khó khăn" | "FDI +9.6% nhưng nhập siêu 13.8 tỷ — một bên vốn đến, một bên nguyên liệu nhập, hai số này định hình cán cân H2." |

**4 ĐỪNG**:
1. ĐỪNG dùng "tôi nghĩ/có thể/dự báo" → dùng "số liệu cho thấy", "cùng lúc"
2. ĐỪNG khuyên mua/bán/khuyến nghị → chỉ kể diễn biến số
3. ĐỪNG dùng tính từ cảm tính ("đáng lo", "tốt") → dùng số so sánh ("+99.1%", "đỉnh 15 năm")
4. ĐỪNG kết luận định hướng → mở câu hỏi cho người đọc

→ Xem `references/data_cards.md` mục **Narrative** cho template 4 câu + bảng sai-đúng + 10 ví dụ.

### Bước 3.5: Làm phong phú báo chí (BẮT BUỘC cho Cấp A khi đủ 5 nguồn)

Sau khi data chính xong, WebSearch tin báo chí trong tháng báo cáo để **làm phong phú** mỗi data card. Lớp bổ sung, KHÔNG thay thế số liệu chính.

**Quy tắc enrich (rõ ràng)**:
| Điều kiện | Hành động |
|---|---|
| Đủ 5 nguồn (full run) | ✅ **BẮT BUỘC** enrich cho 10 card Cấp A (CPI, PMI, IIP, XNK, FDI, LNH, TPCP, TPDN, bán lẻ, tỷ giá) — 1-2 tin/card |
| Partial run (3-4/5 nguồn) | ⚠️ TÙY CHỌN — focus data chính trước, enrich nếu còn thời gian |
| Không có tin chất lượng | ❌ BỎ QUA — thà trống hơn tin rác |

→ Enrich KHÔNG tạo placeholder. Nếu không tìm được tin tốt cho 1 card → bỏ field `news_enrichment` của card đó (không tạo empty array).

```
Cho mỗi data card có giá trị kinh tế:
  ↓
WebSearch theo template: "[chỉ số] [tháng] [năm]" site:[nguồn ưu tiên]
  ↓
Filter: publish ≤ chốt dữ liệu + có quote chuyên gia hoặc insight
  ↓
Embed 1-2 tin tốt nhất vào field news_enrichment
```

**Nguồn ưu tiên** (xem `references/news_sources.md` cho chi tiết):
- **A. Báo kinh tế chính thống**: VnEconomy, Báo Điện tử Chính phủ, Đầu tư, Thời báo Tài chính
- **B. Báo tài chính/CK**: CafeF, Vietstock, VietnamFinance (trích báo cáo CTCK)
- **C. Báo ngành**: Công Thương, Hải quan, Nông nghiệp VN

**Quy tắc**:
- Chỉ tin publish ≤ chốt dữ liệu (quy tắc thời gian)
- Tối đa 2 tin / card
- Ưu tiên tin có quote chuyên gia (TS. Nguyễn Trí Hiếu, SSI Research...)
- KHÔNG dùng số liệu báo chí thay số liệu chính thức — enrich chỉ bổ sung context
- Nếu không có tin chất lượng → KHÔNG enrich (thà trống hơn tin rác)

### Bước 3.6: Nguyên tắc KHÔNG placeholder (BẮT BUỘC)

**Chỉ đưa vào báo cáo những gì CÓ DỮ LIỆU THẬT. Không tạo khung/card/section "THIẾU" cho phần chưa có data.**

```
Cho mỗi chỉ số dự kiến:
  ↓
Có số liệu trace được tới file cache?
  ↓
  ┌──── CÓ ────┐                ┌──── KHÔNG ────┐
  ↓            ↓                ↓               ↓
Tạo data card  (xử lý bình thường)  BỎ QUA — KHÔNG tạo card
                                   KHÔNG tạo missing-card
                                   KHÔNG tạo _status: THIẾU
                                   KHÔNG để slot trống
```

**4 ĐỪNG khi thiếu dữ liệu**:
1. **ĐỪNG** tạo `missing-card` / placeholder box trong HTML ("📋 THIẾU VNBA — sẽ có khi publish...")
2. **ĐỪNG** tạo entry `_status: "THIẾU"` trong `report.json` (vô nghĩa — JSON không cần khai báo cái không có)
3. **ĐỪNG** để slot trống trong grid layout (gây vỡ UI)
4. **ĐỪNG** giải thích dài dòng trong dashboard về việc thiếu (chỉ 1 dòng trong coverage-warn hero là đủ)

**Ngoại lệ DUY NHẤT** — coverage warning ở đầu báo cáo:
- Nếu chạy partial (3/5 nguồn) → **1 dòng** ở hero `coverage-warn` ghi "Báo cáo dùng 3/5 nguồn: thiếu Customs + VNBA"
- KHÔNG lặp lại warning này trong từng group section

**Tại sao**: Placeholder "THIẾU" làm dashboard nặng mà không thêm giá trị — người đọc không cần biết dashboard *đáng lẽ có gì*, chỉ cần biết dashboard *có gì*. Khi nguồn bổ sung publish → chạy lại skill, card tự xuất hiện tự nhiên.

**Ví dụ sai vs đúng** (tháng 6/2026, thiếu VNBA):
| ❌ SAI | ✅ ĐÚNG |
|---|---|
| Tạo card "US 10Y yield · ECB · BOJ · TT/CV NHNN" với nội dung "THIẾU VNBA — sẽ có khi publish" | Bỏ hẳn card này. Khi VNBA publish → chạy lại skill → card tự xuất hiện |
| Tạo `_status: "THIẾU"` cho deposit_rate, lending_rate trong JSON | Không có field deposit_rate/lending_rate trong JSON kỳ này |
| 9 missing-card + 6 `_status: THIẾU` rải rác | 0 placeholder. Chỉ 1 dòng coverage-warn ở hero |

→ Xem `references/data_cards.md` mục **"Nguyên tắc không placeholder"** cho chi tiết + checklist.

### Bước 3.7: Data Provenance (BẮT BUỘC)

**Mọi số trong `report.json` phải trace được tới 1 file cụ thể trong `sources_cache/`.** Thêm section `_data_provenance` ở cuối report.json:

```json
"_data_provenance": {
  "_rule": "Mọi số trong report.json phải trace được tới 1 file cụ thể trong sources_cache/",
  "sources_files": {
    "nso_jun_2026.txt": ["CPI", "IIP", "GDP", "XNK", "FDI", "bán lẻ", "DN"],
    "pmi_jun_2026_extracted.txt": ["PMI headline + 10 sub-indices"],
    "vbma_weekly_22-26jun_2026.txt": ["LNH", "tỷ giá", "DXY", "TPCP", "TPDN"]
  }
}
```

**Quy tắc**:
- ✅ CHỈ ghi `sources_files` (file CÓ + chỉ số lấy từ file đó)
- ❌ KHÔNG ghi `missing_files` (file thiếu) — vi phạm Nguyên tắc không placeholder. Khi nguồn bổ sung publish → chạy lại skill → tự thêm vào sources_files
- ❌ KHÔNG ghi file mà không có chỉ số nào trace được tới nó

### Bước 4: Render HTML dashboard

Copy `assets/report_template.html` → fill data từ `report.json`. Template có:

- **Hero**: verdict badge + 4 KPI boxes (CPI/PMI/XNK/LNH)
- **NAV**: **5 tabs** (Kinh tế thực* / Tiền tệ & TC / Ngành & cơ cấu / Bối cảnh TG / **📊 Tổng hợp**)
- **4 group sections** (data card theo nhóm): mỗi nhóm có 🔴 tiêu cực + 🟢 tích cực highlight + thẻ dữ liệus grid
- **Click-to-chart**: nút `[📊]` mở modal với sparkline từ `history.json`
- **Section 5 "Tổng hợp"**: Risks / Catalysts / Key Takeaways — **PHẢI nằm trong `<section id="summary">` riêng** (tab thứ 5), KHÔNG đặt ngoài group-section (xem `references/rendering.md` rule placement)

→ Xem `references/rendering.md` cho design pattern + style guide đồng bộ `vn-research-dashboard`.

**Verify HTML (BẮT BUỘC)**:
```bash
# JS syntax check
node -e "
const fs=require('fs');
const html=fs.readFileSync('report.html','utf8');
const scripts=html.match(/<script>([\s\S]*?)<\/script>/g);
const last=scripts[scripts.length-1].replace(/<\/?script>/g,'');
fs.writeFileSync('/tmp/r.js',last);
" && node --check /tmp/r.js && echo '✅ Syntax OK'

# Automated QA (Playwright)
NODE_PATH=/tmp/qa-runner/node_modules node scripts/qa_report.js \
  --url=file:///path/to/2026-05/report.html --output=/tmp/qa-2026-05
```

Kết quả: `✅ PASS` → done | `⚠️ WARNINGS` → review | `❌ FAIL` → fix rerun.

## Output

### File cuối cùng
```
{project}/output/
├── Báo cáo Vĩ mô Việt Nam - Tháng X.YYYY.html   ← bản trình bày HTML chính thức
└── Báo cáo Vĩ mô Việt Nam - Tháng X.YYYY.pdf    ← bản in PDF chính thức

{project}/vn-macro-monthly/
├── history.json              ← chuỗi thời gian (append mỗi tháng)
├── 2026-05/
│   ├── report.json           ← data structured (nguồn dữ liệu chuẩn)
│   ├── report.html           ← dashboard sao lưu trong thư mục tháng

│   └── sources_cache/
│       ├── pmi_may_2026.html
│       ├── nso_may_2026.html
│       ├── customs_may_2026.txt
│       ├── vbma_weekly_25-29may_2026.pdf   ← bằng chứng (Option C)
│       ├── vbma_weekly_25-29may_2026.txt
│       ├── vnba_monthly_may_2026.pdf       ← bằng chứng
│       └── vnba_monthly_may_2026.txt
└── 2026-04/ (kỳ trước)
```

### `report.json` schema (tóm tắt)

```json
{
  "report_id": "vn-macro-2026-05",
  "period": {"month": 5, "year": 2026, "data_cutoff": "2026-05-31"},
  "verdict": "TRUNG TÍNH — CẢNH GIÁC",
  "verdict_reason": "...",
  "group1_real_economy": { /* 14 Thẻ dữ liệus */ },
  "group2_financial": { /* 12 Thẻ dữ liệus */ },
  "group3_sector": { /* 5 Thẻ dữ liệus */ },
  "group4_global_context": { /* 10 Thẻ dữ liệus */ },
  "risks": [ /* 5 items, level color-coded */ ],
  "catalysts": [ /* 5 items */ ],
  "key_takeaways": [ /* 5 bullets, #1 có ⭐ */ ]
}
```

### `history.json` schema

```json
{
  "series": {
    "cpi_yoy_pct": [{"month": "2026-05", "value": 5.60}],
    "pmi": [{"month": "2026-05", "value": 52.8}]
  }
}
```

**Rules history**:
- Mỗi lần skill chạy thành công → append entry
- **Re-run tháng cũ → ghi đè** (1 tháng = 1 giá trị)
- **Bắt đầu trống** (KHÔNG seed data cũ). Áp dụng cho CẢ `history.json` thật VÀ template sample (`assets/report_template.html`)
- → Dashboard demo sẽ không có nút `[📊]` cho đến khi skill chạy thật 6+ kỳ (feature ngủ chờ data — KHÔNG phải bug, xem "Pitfalls" cuối file)
- Đủ 6+ tháng → chart Cấp A render sparkline đẹp

## 4 Rules — tóm tắt (xem `references/core_rules.md` cho chi tiết)

| Rule | Tóm tắt |
|---|---|
| **1. Nhất quán thời gian** | "Nhìn lùi, không nhìn tới". Data cutoff = cuối RM. VBMA tuần ≤ cutoff, VNBA bỏ "tuần 1 tháng M+1" |
| **2. Frequency** | Chỉ monthly, bỏ quý |
| **3. Giải quyết xung đột** | Thứ tự ưu tiên nguồn chính + Kiểm chứng định nghĩa trước + Sai số chấp nhận được (<2%/<5%/>5%) |
| **4. Quy ước đơn vị** | 8 đuôi trường, tách mom_pct/yoy_pct/ytd_avg_pct |

## Phối hợp hệ sinh thái skill VN

```
vn-financial-data-collector  (DN cấp)
        ↓
vn-fundamental-analysis / vn-valuation-engine / vn-technical-analysis
vn-news-digest              (thời sự 30 ngày cho cổ phiếu)
⭐ vn-macro-monthly ⭐       (VĨ MÔ monthly)  ← SKILL NÀY
        ↓
vn-research-dashboard       (render HTML equity research — share style)
```

→ vn-macro-monthly = mảnh ghép **ngữ cảnh vĩ mô** còn thiếu. CPI/FDI/XNK/PMI/LNH là input cho mọi quyết định đầu tư VN.

## Pitfalls thực tế (lessons learned)

Tổng kết 4 sai lầm thường gặp khi làm/vận hành skill. Đọc trước khi debug.

### Pitfall 1 — "Feature ngủ chờ data"

- ❌ User báo "feature chart `[📊]` bị mất" khi dashboard không có nút nào → tưởng là bug
- ✅ Thực ra nút đang ẩn do `history.series[key].length < 6` — đúng spec (rule ẩn nút khi <6 tháng)
- → **Cách check**: mở source HTML, tìm `const history={series:{...}}`. Đếm số entry mỗi series. Nếu tất cả <6 → feature đang ngủ, không phải bug
- → **Cách kích hoạt**: chạy skill thêm tháng. Lần thứ 6+ → 2 series đầu (CPI/PMI) đạt 6 điểm → nút tự xuất hiện
- **KHÔNG** sửa code ép nút hiện, **KHÔNG** seed data để ép ngưỡng

### Pitfall 2 — "Đừng fill data qua WebSearch"

- ❌ Khi user hỏi "fill thêm data cũ cho dashboard demo", temptation là WebSearch + điền thẳng vào `history.json`/`report.json`
- ✅ Vi phạm rule cốt lõi: **"Mọi số liệu trong `report.json` phải trace được tới 1 file cụ thể trong `sources_cache/`"** (xem DESIGN.md + `references/sources_overview.md`)
- → Chỉ dùng data có trong cache của các kỳ chạy trước. WebSearch = để FIND URL nguồn, không phải để FILL data
- → Ngoại lệ duy nhất: enrich báo chí (lớp bổ sung, không phải số chính, có `references/news_sources.md` riêng)

### Pitfall 3 — "QA PASS ≠ feature hoạt động"

- ❌ QA script ghi `✅ PASS` → tưởng mọi thứ OK
- ✅ QA check `display:none` đúng — nhưng nếu **toàn bộ nút ẩn** (history rỗng, feature ngủ) → QA vẫn PASS (check #7 line 219-221 handle visible=0)
- → Đọc kỹ output QA: dòng `"X visible, Y hidden"`. Nếu `visible=0` → feature đang ngủ (Pitfall 1), không phải fail
- → QA chỉ check **structure** (nút tồn tại, modal mở được khi click nút visible). KHÔNG check **business logic** (nút nên visible hay không)

### Pitfall 4 — "Sample data trap"

- ❌ Template demo có seed data (CPI/PMI 5 điểm) → tưởng đây là source-of-truth để copy sang `history.json` thật
- ✅ Template sample phải bắt đầu **TRỐNG** đúng spec (xem "History rules" phía trên). Seed data = vi phạm rule "không seed"
- → Nếu dashboard demo hiện nút chart → có thể là seed data sót lại (phải xóa)
- → Khi run thật: data append từ cache kỳ trước, **KHÔNG** copy số từ template sample vào `history.json` thật

## Tham khảo

- **`references/core_rules.md`** — ⭐ 4 rules bắt buộc (Time/Frequency/Conflict/Unit) + CPI case study
- **`references/sources_overview.md`** — ⭐ 5 nguồn: URL pattern + cách fetch + pitfalls từng nguồn
- **`references/preflight_check.md`** — Kiểm tra toàn vẹn (pre-flight) workflow + lịch release + gợi ý thử lại
- **`references/data_cards.md`** — ⭐ Thẻ dữ liệu schema + 41 chỉ số mapping 4 nhóm priority
- **`references/rendering.md`** — ⭐ HTML design pattern + 3 component mới (nav/highlight/click-to-chart)
- **`references/news_sources.md`** — ⭐ Nguồn báo chí enrich (3 nhóm: kinh tế chính thống + tài chính/CK + ngành) + quy tắc lọc + schema news_enrichment
- **`assets/report_template.html`** — ⭐ Template HTML hoàn chỉnh (Chart.js + CSS fintech, đồng style vn-research-dashboard)
- **`scripts/qa_report.js`** — ⭐ Automated QA (Playwright): nav/modal/sections/console errors/screenshots

## Changelog

### 2026-07-03 — Bỏ section Cross-check khỏi dashboard

**Thay đổi**: Xóa hoàn toàn section "🔗 Đối chiếu chéo (Cross-checks)" (6 cặp thẻ đối chiều) khỏi output báo cáo.

**Lý do**: Phần kỹ thuật so sánh nguồn A vs nguồn B không phải insight người dùng cần. Khi thiếu nguồn (3/5 như tháng 6/2026), cross-check trở nên vô nghĩa (4/6 cặp phải "BỎ QUA"), làm dashboard nặng mà không thêm giá trị.

**Files đã sửa**:
- `SKILL.md` — bỏ mention cross-check trong Bước 3.1, Bước 4, schema report.json, Tham khảo
- `references/data_cards.md` — xóa section "## 6 Cross-check pairs" + key_takeaways giảm 5→3 bullets
- `references/rendering.md` — xóa section "## Cross-check: cặp thẻ đối chiều" + CSS `.xc-*` + checklist
- `assets/report_template.html` — bỏ key takeaway #5 + "đã đối chiếu chéo" trong footer
- `scripts/qa_report.js` — bỏ Check 5b + Check 8 (cross-check)

**GIỮ method luận (KHÔNG xóa)**: "cross-check" trong `references/core_rules.md` (Rule 3 Conflict Resolution), `references/preflight_check.md` (lý do all-or-nothing), `references/news_sources.md` — đây là cách **kiểm chứng chéo dữ liệu** để resolve conflict, KHÔNG phải phần hiển thị. Method luận này vẫn cần thiết cho chất lượng data.

**Lưu ý cho người sửa skill sau**: KHÔNG khôi phục section cross-check vào dashboard trừ khi user yêu cầu rõ.

### 2026-07-03 — Thêm nguyên tắc KHÔNG placeholder

**Thay đổi**: Thêm rule "Bước 3.6: Nguyên tắc KHÔNG placeholder" — bỏ hẳn card/section cho phần thiếu dữ liệu, không tạo `missing-card` / `_status: THIẾU`.

**Lý do**: Placeholder "THIẾU" làm dashboard nặng mà không thêm giá trị. Người đọc không cần biết dashboard *đáng lẽ có gì*, chỉ cần biết *có gì*. Khi nguồn publish → chạy lại skill → card tự xuất hiện.

**Files đã sửa**:
- `SKILL.md` — thêm "Bước 3.6: Nguyên tắc KHÔNG placeholder"
- `references/data_cards.md` — thêm section "## Nguyên tắc KHÔNG placeholder" + checklist + ví dụ sai-đúng

**Lưu ý cho người sửa skill sau**: KHÔNG tạo placeholder/missing-card cho phần thiếu data. Chỉ tạo card khi có số liệu thật trace được tới cache.

### 2026-07-03 — Thêm tab "Tổng hợp" + rule placement rc-grid/kt-section

**Thay đổi**: Dashboard có **5 tab** (thêm tab "📊 Tổng hợp"). Rủi ro (`rc-grid`) + Động lực + Key takeaways (`kt-section`) PHẢI nằm trong `<section class="group-section" id="summary">` (tab thứ 5), KHÔNG đặt ngoài group-section.

**Lý do**: Trước đây rc-grid/kt-section đặt ngoài 4 group-section → JS nav chỉ ẩn/hiện group-section → Rủi ro/Động lực luôn hiện bất kể tab nào → sai UX (xem tab Kinh tế thực vẫn thấy Rủi ro). User báo "phần rủi ro và động lực đang là như nhau" khi chuyển tab.

**Files đã sửa**:
- `SKILL.md` — Bước 4 liệt kê template: NAV 5 tab + Section 5 placement rule
- `references/rendering.md` — cập nhật layout diagram (5 tab) + thêm rule "Placement của Rủi ro/Động lực/Key takeaways" + checklist
- `assets/report_template.html` — (sẽ cập nhật ở lần render sau)

**Lưu ý cho người sửa skill sau**: Mọi component muốn ẩn/hiện theo tab → PHẢI nằm trong `<section class="group-section">`. Chỉ HERO, NAV, FOOTER đặt ngoài (luôn hiện).

