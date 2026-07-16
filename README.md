# 📊 Macro_Vietnam_Monthly — Báo cáo vĩ mô Việt Nam hàng tháng

**Nguồn tham khảo:** *https://github.com/Thanhtran-165/vimovietnam*

Skill tạo **báo cáo vĩ mô VN monthly** toàn diện 41 chỉ số từ 5 nguồn chính thức (NSO + Customs + S&P PMI + VBMA + VNBA). Bao phủ 4 trụ cột: sản xuất + ngoại thương + tiền tệ + tài chính. Xem [tại đây](https://ftu-kudo.github.io/Macro_Vietnam_Monthly/).

## Cấu trúc skill

```
vn-macro-monthly/
├── SKILL.md                      # Workflow chính (pre-flight → fetch → extract → render)
├── README.md                     # File này
├── references/
│   ├── core_rules.md             # 4 rules: Time / Frequency / Conflict / Unit
│   ├── sources_overview.md       # 5 nguồn: URL pattern + cách fetch
│   ├── preflight_check.md        # Kiểm tra toàn vẹn + lịch release + user override
│   ├── data_cards.md             # Schema data card + 41 chỉ số + narrative rule
│   ├── rendering.md              # HTML design pattern + 5 tab + placement rule
│   ├── news_sources.md           # Nguồn báo chí enrich (3 nhóm)
│   └── images.md                 # Ảnh minh họa stock (Unsplash)
├── assets/
│   └── report_template.html      # Template HTML dashboard (Chart.js + CSS fintech)
├── scripts/
│   └── qa_report.js              # Automated QA (Playwright)
└── agents/
    └── openai.yaml               # OpenAI agent interface
```

## Workflow 4 bước

1. **Pre-flight** — kiểm tra 5 nguồn có sẵn chưa (all-or-nothing, hoặc user override partial)
2. **Fetch + cache** — tải 5 nguồn về `sources_cache/`
3. **Extract** — parse → 41 data cards + apply 4 rules + narrative
4. **Render** — HTML dashboard 5 tab (Kinh tế thực / Tiền tệ / Ngành / Bối cảnh / Tổng hợp)

## Đặc trưng

- **5 nguồn chính thức miễn phí**: NSO, Tổng cục Hải quan, S&P Global PMI, VBMA, VNBA
- **4 rules chất lượng**: Time Consistency, Frequency (monthly-only), Conflict Resolution, Unit Convention
- **Dashboard đồng style**: fintech dark theme, 5 tab nav, click-to-chart (ngủ chờ <6 tháng data)
- **Nguyên tắc không placeholder**: chỉ tạo card khi có data thật
- **Narrative "người kể chuyện số liệu"**: KHÔNG cho ý kiến, chỉ kể diễn biến số

## Sử dụng

Skill này hoạt động trong môi trường có thể fetch web (WebSearch, WebReader, curl, pdftotext). Kích hoạt:

```
/vn-macro-monthly 2026-06
```

## Changelog

Xem cuối `SKILL.md` cho lịch sử thay đổi (bỏ cross-check, thêm nguyên tắc không placeholder, 5 tab, etc.).

## License

Miễn phí cho mục đích cá nhân và nghiên cứu. KHÔNG phải lời khuyên đầu tư.
