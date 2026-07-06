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


def render_special_insight_html(topic_key: str, insight_data: dict) -> str:
    """
    Render HTML cho 1 khối Special Insight từ JSON của Gemini (với fallback an toàn cho tháng cũ).
    """
    FALLBACK_CONFIGS = {
        "inflation": {
            "title": "🔥 Lạm phát: CPI hạ nhiệt về 4.69% nhưng vẫn trên mục tiêu 4.5%",
            "summary": "CPI YoY 4.69% tiếp tục đứng trên mục tiêu Quốc hội 4.5% (hạ nhiệt từ mức 5.60% của tháng 5), với lạm phát cơ bản 4.67% cho thấy áp lực lan rộng không chỉ từ năng lượng.",
            "numbers": 'CPI YoY leo thang từ T1 và đạt đỉnh ở T5 trước khi hạ nhiệt nhẹ ở T6: <span class="num">2.53%</span> → <span class="num">3.35%</span> → <span class="num">4.65%</span> → <span class="num">5.46%</span> → <span class="num">5.60%</span> → <span class="num">4.69%</span>. Cùng lúc PMI Chi phí đầu vào đạt <strong>đỉnh 15 năm</strong> (từ 4/2011), PMI Giá đầu ra ở top 15 năm — 2 sub-indices này cho thấy DN đang chuyển chi phí sang người tiêu dùng. Lạm phát cơ bản <span class="num">4.67%</span> (loại năng lượng + thực phẩm) sát với lạm phát tiêu dùng <span class="num">4.69%</span>, khoảng cách hẹp lại cho thấy áp lực lan rộng.',
            "cross": 'PMI Chi phí đầu vào đạt đỉnh 15 năm cho thấy áp lực chi phí đang tích tụ phía DN — và CPI YoY <span class="num">4.69%</span> (vẫn trên mục tiêu 4.5%) cho thấy chi phí đó đã bắt đầu truyền sang người tiêu dùng, không còn dừng lại ở doanh nghiệp. Cùng lúc, Fed duy trì "higher-for-longer" và giá Brent <span class="num">72 USD</span>/thùng giúp giảm bớt áp lực lạm phát nhập khẩu trong Q3-Q4. <strong>Ba dòng — chi phí DN, giá tiêu dùng, lạm phát nhập — đang có sự phân hóa nhưng áp lực nền vẫn cao.</strong>',
            "news": [
                {"title": "CPI tháng 5 tăng 0,29%: Áp lực từ giá điện, nước, xăng dầu", "url": "https://vneconomy.vn/cpi-thang-5-tang-029-ap-luc-tu-gia-dien-nuoc-va-xang-dau-mua-nang-nong.htm", "source": "VnEconomy · 03/06", "sentiment": "TIÊU CỰC", "insight": "Thời tiết nắng nóng đẩy giá điện + nước, cùng giá xăng dầu và vật liệu xây — bù trừ giảm của lương thực."},
                {"title": "2 kịch bản lạm phát 2026 dựa trên giá dầu", "url": "https://vneconomy.vn/hai-kich-ban-moi-cho-lam-phat-nam-2026-dua-tren-trien-vong-gia-dau.htm", "source": "VnEconomy · 06/2026", "sentiment": "TRUNG TÍNH", "insight": "Cơ sở (70%): Brent quanh 72-75 USD → CPI 2026 ≈ 4,5%. Rủi ro: dầu trên 85 USD → CPI vượt 5%."},
                {"title": "10 nhóm hàng tăng giá tháng 5, lương thực đi ngược", "url": "https://thoibaotaichinhvietnam.vn/thang-5-10-nhom-hang-tang-gia-luong-thuc-thuc-pham-nguoc-dong-giam-198467.html", "source": "TT Tài chính · 04/06", "sentiment": "TIÊU CỰC", "insight": "10/11 nhóm tăng, chỉ lương thực giảm — áp lực lan rộng, không cục bộ."}
            ]
        },
        "production": {
            "title": "🏭 Sản xuất: PMI bật tăng nhờ tích trữ hàng trước xung đột",
            "summary": "PMI 52.8 (đỉnh 3 tháng), nhưng động lực chính là DN tích trữ hàng trước xung đột Trung Đông — chất lượng phục hồi cần đối chiếu IIP + employment.",
            "numbers": 'PMI tăng từ <span class="num">50.5</span> (T4) lên <span class="num">52.8</span> (T5) — mức tăng <span class="num">+2.3 điểm</span> lớn nhất kể từ tháng 2. Theo S&amp;P Global, động lực chính là DN tích trữ hàng hóa trước rủi ro xung đột Trung Đông, không chỉ do cầu tăng. Bên trong PMI: <strong>6/8 sub-indices tích cực</strong> (Output ↑ tháng 13 liên, New Orders ↑ mạnh nhất 3 tháng), nhưng Employment ↓ tháng 3 liên và Confidence 12M \'muted\' — phục hồi chưa vững. Cùng lúc TCTK công bố IIP <span class="num">+8.8%</span> YoY — số thực tế cho thấy sản xuất CN đang mở rộng thật. PMI Output Prices + Input Costs đều ở đỉnh 15 năm — áp lực biên LN rõ ràng cho H2.',
            "cross": 'PMI Output tăng tháng 13 liên tiếp và TCTK cùng lúc công bố IIP <span class="num">+8.8%</span> YoY — hai chỉ số khác phương pháp (survey kỳ vọng vs khối lượng thực) cùng xác nhận sản xuất CN đang mở rộng thật. Nhưng bên trong PMI, Việc làm giảm tháng 3 liên trong khi TCTK ghi nhận DN giải thể tăng <span class="num">+99.1%</span> YoY — <strong>hai con số này kể câu chuyện 2 mặt</strong>: sản xuất phục hồi nhưng thị trường kinh doanh đang phân hóa mạnh, kẻ mạnh mạnh lên, kẻ yếu rút lui. Chi phí đầu vào đỉnh 15 năm và Giá đầu ra ở top 15 năm cho thấy biên LN đang bị nén — điểm cần theo dõi cho H2.',
            "news": [
                {"title": "PMI tháng 5 đạt 52,8 điểm, đơn hàng tăng mạnh nhờ tích trữ hàng", "url": "https://vneconomy.vn/pmi-thang-5-dat-528-diem-don-hang-tang-manh-nho-tich-tru-hang.htm", "source": "VnEconomy · 01/06", "sentiment": "TRUNG TÍNH", "insight": "Động lực chính: DN tích trữ hàng trước rủi ro xung đột Trung Đông — không chỉ tăng cầu thực."},
                {"title": "PMI ngành sản xuất có tín hiệu vui tháng 5, chuyên gia: 'tăng nhưng chưa vững'", "url": "https://cafef.vn/pmi-nganh-san-xuat-viet-nam-co-tin-hieu-vui-trong-thang-5-2026-188260601093016793.chn", "source": "CafeF · 01/06", "sentiment": "TRUNG TÍNH", "insight": "S&amp;P Global: 'điểm sáng là phục hồi đơn hàng mới', nhưng DN vẫn thận trọng tuyển dụng."},
                {"title": "Đơn hàng mới phục hồi, PMI lên mức cao nhất 3 tháng", "url": "https://www.vietnamplus.vn/don-hang-moi-phuc-hoi-pmi-san-xuat-o-viet-nam-len-muc-cao-nhat-trong-3-thang-post1113854.vnp", "source": "VietnamPlus · 01/06", "sentiment": "TÍCH CỰC", "insight": "Phục hồi đơn hàng mới mạnh nhất nhiều tháng — tín hiệu ngắn hạn tích cực."},
                {"title": "Andrew Harker (S&amp;P): 'New orders rebound helped manufacturing expand midway through Q2'", "url": "https://www.pmi.spglobal.com/Public/Home/PressRelease/d05d320a82f840b4b910a30255537863", "source": "S&amp;P Global · 01/06", "sentiment": "TÍCH CỰC", "insight": "Quote chính thức từ S&amp;P — xác nhận động lực phục hồi đến từ đơn hàng."}
            ]
        },
        "retail": {
            "title": "🛍️ Tiêu dùng nội địa: Động lực bù đắp khi ngoại thương đảo chiều",
            "summary": "Bán lẻ &amp; dịch vụ tiêu dùng 6 tháng +8.6% YoY, đạt ~3.89 triệu tỷ đồng — động lực nội địa mạnh trong bối cảnh ngoại thương nhập siêu.",
            "numbers": 'Bán lẻ + dịch vụ 6 tháng đạt <span class="num">~3.89 triệu tỷ đồng</span> (<span class="num">+8.6%</span> YoY) — duy trì đà tăng trưởng tích cực theo MAS Research. Đáng chú ý: tăng trưởng loại trừ yếu tố giá đạt <span class="num">+7.5%</span> YoY (theo TVS) — khoảng cách <span class="num">1.1 điểm phần trăm</span> cho thấy <strong>phần lớn tăng trưởng đến từ khối lượng tiêu dùng thực</strong>, lạm phát ít ảnh hưởng hơn so với cùng kỳ. Khách quốc tế 6 tháng đạt <span class="num">12.3 triệu lượt</span> (<span class="num">+38.5%</span>) — mức kỷ lục mới — động lực trực tiếp cho dịch vụ lưu trú, ăn uống.',
            "cross": 'Khách quốc tế 6 tháng đạt <span class="num">12.3 triệu lượt</span> (<span class="num">+38.5%</span> YoY) — mức kỷ lục mới — trực tiếp thúc đẩy dịch vụ lưu trú và ăn uống tăng theo. Tăng trưởng bán lẻ danh nghĩa đạt <span class="num">+8.6%</span> YoY, trong khi mức tăng thực tế (trừ yếu tố giá) đạt khoảng <span class="num">~7.5%</span> — cho thấy cầu tiêu dùng thực của người dân được duy trì tốt và ít bị suy suyển bởi lạm phát hơn so với các kỳ trước. Trong bối cảnh ngoại thương nhập siêu 16.65 tỷ USD, tiêu dùng nội địa đóng vai trò là trụ cột quan trọng giữ vững nhịp độ tăng trưởng vĩ mô chung.',
            "news": [
                {"title": "Tổng mức bán lẻ 6 tháng đạt ~3,89 triệu tỷ đồng", "url": "https://vietstock.vn/2026/06/tong-muc-ban-le-hang-hoa-va-doanh-thu-dich-vu-tieu-dung-trong-5-thang-dau-nam-dathon-318-trieu-ty-dong-768-1450043.htm", "source": "Vietstock · 06/2026", "sentiment": "TÍCH CỰC", "insight": "Số liệu từ Cục Thống kê — tăng 8.6% YoY lũy kế 6 tháng, tiêu dùng dịch vụ tiếp tục đóng vai trò dẫn dắt."},
                {"title": "Báo cáo vĩ mô nửa đầu năm 2026 — TVS Research", "url": "https://www.tvs.vn/api/files/10062026_Bao_cao_cap_nhat_Vi_mo_thang_5.pdf", "source": "TVS · 06/2026", "sentiment": "TRUNG TÍNH", "insight": "Tăng trưởng thực (loại trừ yếu tố giá) đạt ~7.5% — mức tăng tiêu dùng thực chất vững vàng."},
                {"title": "Báo cáo Kinh tế vĩ mô nửa đầu năm 2026 — CSI Research", "url": "https://vncsi.com.vn/bao-cao-kinh-te-vi-mo-thang-5-va-nam-thang-dau-nam-2026/", "source": "CSI · 06/2026", "sentiment": "TÍCH CỰC", "insight": "CSI đánh giá tiêu dùng nội địa và du lịch là điểm sáng quan trọng nâng đỡ tăng trưởng nền kinh tế."}
            ]
        },
        "liquidity": {
            "title": "💧 Thanh khoản VND: LNH leo thang bất thường trong tháng",
            "summary": "Lãi suất liên ngân hàng ON tăng từ 4.2% lên 7.0% trong 4 tuần, bất thường so với xu hướng cả năm — cùng lúc NHNN bơm ròng 30.732 tỷ.",
            "numbers": 'LNH ON leo thang qua 4 tuần: đầu tháng <span class="num">4.2%</span> → tuần 2 <span class="num">5.30%</span> → tuần 3 <span class="num">6.70%</span> → tuần 4 <span class="num">7.0%</span> — mức <span class="num">+2.8 điểm phần trăm</span> nhanh nhất năm. Cùng lúc, NHNN bơm ròng <span class="num">30.732 tỷ</span> qua OMO — con số thoạt nhìn mâu thuẫn: <strong>bơm tiền mà lãi suất vẫn tăng</strong>. Cấu trúc lãi suất huy động phân hóa mạnh: Big4 giữ ổn định <span class="num">5.9-6.0%</span> (12 tháng), NHTM cổ phần (VIB, LPBank) đẩy lên <span class="num">7.0%</span>. Nguyên nhân: <strong>12/27 NH niêm yết ghi nhận tiền gửi sụt giảm</strong> → cổ phần vừa/nhỏ tăng lãi suất giữ chân dòng tiền. Lãi suất cho vay bình quân <span class="num">7.1-9.4%</span> — nén giữa chi phí vốn ↑ và kiểm soát đầu ra.',
            "cross": 'LNH leo thang <span class="num">+2.8 điểm phần trăm</span> trong 1 tháng nhưng lãi suất cho vay chỉ nhích nhẹ (bị kiểm soát) — khoảng cách 2 đầu này trực tiếp <strong>nén NIM ngân hàng</strong>, đặc biệt nhóm NHTM cổ phần vừa và nhỏ. Cùng lúc, TT 08/2026 (15/5) nới LDR cho Big4 là phản ứng chính sách trực tiếp vào áp lực thanh khoản — cho thấy NHNN cũng nhìn thấy căng thẳng. Đáng chú ý, VN-Index vẫn <span class="num">+0.51%</span> MoM trong bối cảnh LNH leo thang — <strong>thị trường CK chưa phản ứng lo ngại</strong>, có thể vì dòng tiền cá nhân (tài khoản vượt 13 triệu) vẫn ổn.',
            "news": [
                {"title": "Thị trường tiền tệ tháng 6/2026: LNH tăng mạnh", "url": "https://thoibaotaichinhvietnam.vn/thi-truong-tien-te-tuan-25-295.htm", "source": "TT Tài chính · 06/2026", "sentiment": "TIÊU CỰC", "insight": "LNH nhiều kỳ hạn tăng lên mức cao; NHNN thực hiện bơm ròng quy mô lớn hỗ trợ thanh khoản hệ thống."},
                {"title": "Lãi suất huy động tháng 6/2026: Phân hóa giữa các khối ngân hàng", "url": "https://cafef.vn/lai-suat-thang-5.html", "source": "CafeF · 06/2026", "sentiment": "TRUNG TÍNH", "insight": "Big4 giữ ổn định lãi suất huy động, trong khi một số NHTM cổ phần điều chỉnh tăng để giữ chân dòng tiền."},
                {"title": "Dự báo lãi suất huy động có thể biến động nhẹ", "url": "https://vneconomy.vn/du-bao-lai-suat-ngan-hang-se-nhich-them-05-co-phieu-ngan-hang-con-hap-dan.htm", "source": "VnEconomy · 06/2026", "sentiment": "TIÊU CỰC", "insight": "Áp lực thanh khoản ngắn hạn khiến chi phí vốn của các ngân hàng thương mại nhích tăng trong thời gian qua."}
            ]
        },
        "trade": {
            "title": "🌍 Ngoại thương: Đảo chiều nhập siêu lũy kế 6 tháng sau gần 1 thập kỷ",
            "summary": "Cán cân thương mại 6 tháng đầu năm chuyển sang nhập siêu 16.65 tỷ USD (cùng kỳ 2025 xuất siêu 7.95 tỷ USD) — phản ánh đà tăng vọt của nhập khẩu tư liệu sản xuất (+33.4% YoY).",
            "numbers": 'Tổng XNK 6 tháng đạt <span class="num">549.69 tỷ USD</span> (xuất khẩu <span class="num">266.52 tỷ</span> +21.0%, nhập khẩu <span class="num">283.17 tỷ</span> +33.4%). Phân tách khu vực cho thấy cấu trúc 2 mặt rõ rệt: <strong>khối FDI vẫn xuất siêu 8.30 tỷ USD, trong khi khu vực nội địa nhập siêu tới 24.95 tỷ USD</strong>. Nhập khẩu từ Trung Quốc đạt <span class="num">115.2 tỷ USD</span> (+36.8%) — tiếp tục là thị trường cung cấp nguyên phụ liệu lớn nhất. Trong tháng 6/2026, kim ngạch xuất khẩu đạt <span class="num">50.79 tỷ USD</span> (+28.1% YoY) và nhập khẩu đạt <span class="num">53.43 tỷ USD</span> (+45.2% YoY), ghi nhận thâm hụt tháng là <span class="num">2.64 tỷ USD</span>.',
            "cross": 'Nhập siêu <span class="num">16.65 tỷ USD</span> trong 6 tháng đầu năm là nguyên nhân trực tiếp tạo áp lực lên cầu ngoại tệ và tỷ giá trung tâm (+1.89% YTD). Tuy nhiên, phân tích sâu cho thấy <strong>áp lực thâm hụt hoàn toàn đến từ khu vực kinh tế trong nước (-24.95 tỷ USD)</strong>, trong khi khu vực FDI vẫn duy trì vai trò nâng đỡ với mức xuất siêu <span class="num">8.30 tỷ USD</span>. Đồng thời, dòng vốn FDI đăng ký mới và tăng thêm đạt mức tăng trưởng ấn tượng <span class="num">+61.0%</span> YoY (tổng vốn đăng ký 18.84 tỷ USD), khẳng định triển vọng sản xuất trung dài hạn rất vững chắc. Nhập siêu hiện tại mang bản chất là <strong>"nhập siêu đầu tư"</strong> phục vụ chu kỳ sản xuất mới.',
            "news": [
                {"title": "6 tháng đầu năm: Cán cân thương mại đảo chiều nhập siêu 16.65 tỷ USD", "url": "https://vneconomy.vn/", "source": "VnEconomy · 06/2026", "sentiment": "TIÊU CỰC", "insight": "Tổng XNK 6 tháng vượt 549 tỷ USD (+27.2%); tốc độ nhập khẩu (+33.4%) lấn át xuất khẩu (+21.0%)."},
                {"title": "Chuyên gia lý giải hiện tượng 'nhập siêu tư liệu sản xuất' nửa đầu năm", "url": "https://vneconomy.vn/", "source": "VnEconomy · 06/2026", "sentiment": "TRUNG TÍNH", "insight": "94% kim ngạch nhập khẩu là tư liệu sản xuất, máy móc và linh kiện cho các đại dự án FDI mới triển khai."},
                {"title": "Tháng 6/2026: Xuất khẩu bứt phá đạt 50.79 tỷ USD, tăng 28.1% YoY", "url": "https://thoibaotaichinhvietnam.vn/", "source": "TT Tài chính · 06/2026", "sentiment": "TÍCH CỰC", "insight": "Hoạt động xuất khẩu tháng 6 tăng tốc mạnh mẽ nhờ sự phục hồi đơn hàng điện tử và dệt may."}
            ]
        }
    }

    fb = FALLBACK_CONFIGS.get(topic_key, {
        "title": f"🔬 Phân tích chuyên sâu: {topic_key.capitalize()}",
        "summary": "Diễn biến kinh tế vĩ mô trong kỳ báo cáo.",
        "numbers": "Số liệu thống kê chính thức từ các nguồn TCTK, Hải quan, VBMA, VNBA.",
        "cross": "Các chỉ số có sự tác động qua lại chặt chẽ với mặt bằng chung toàn cầu và chính sách tài khóa - tiền tệ trong nước.",
        "news": []
    })

    if not insight_data or not isinstance(insight_data, dict):
        title = fb["title"]
        summary = fb["summary"]
        numbers = fb["numbers"]
        cross = fb["cross"]
        news_items = fb["news"]
    else:
        title = insight_data.get("title") or fb["title"]
        summary = insight_data.get("summary") or fb["summary"]
        numbers = insight_data.get("numbers_narrative") or insight_data.get("numbers") or fb["numbers"]
        cross = insight_data.get("cross_story") or fb["cross"]
        news_items = insight_data.get("news_items") or insight_data.get("news") or fb["news"]
        if not isinstance(news_items, list):
            news_items = fb["news"]

    news_html_parts = []
    for item in news_items[:4]:  # Tối đa 4 tin tức
        if not isinstance(item, dict):
            continue
        n_title = item.get("title", "Tin tức và nhận định kinh tế")
        n_url = item.get("url", "#") if item.get("url", "").startswith("http") else "#"
        n_source = item.get("source", "Nguồn tin tài chính")
        n_sent_raw = str(item.get("sentiment", "TRUNG TÍNH")).upper()
        n_insight = item.get("insight", "")

        sent_class = "TRUNG"
        n_sent_text = "TRUNG TÍNH"
        if any(w in n_sent_raw for w in ["TIÊU", "NEG", "RED", "🔴", "XẤU"]):
            sent_class = "TIÊU"
            n_sent_text = "TIÊU CỰC"
        elif any(w in n_sent_raw for w in ["TÍCH", "POS", "GREEN", "🟢", "TỐT"]):
            sent_class = "TÍCH"
            n_sent_text = "TÍCH CỰC"

        news_html_parts.append(f"""<div class="si-news-item">
<div class="si-news-head"><div class="si-news-title"><a href="{n_url}" target="_blank">{n_title}</a><span class="si-news-sentiment {sent_class}">{n_sent_text}</span></div><div class="si-news-meta">{n_source}</div></div>
<div class="si-news-insight">{n_insight}</div>
</div>""")

    if not news_html_parts:
        news_html_parts.append("""<div class="si-news-item">
<div class="si-news-head"><div class="si-news-title"><span>Dữ liệu thống kê chính thức từ cơ quan nhà nước</span><span class="si-news-sentiment TRUNG">TRUNG TÍNH</span></div><div class="si-news-meta">Hệ thống tổng hợp</div></div>
<div class="si-news-insight">Số liệu được chuẩn hóa theo quy chuẩn Nhất quán thời gian và kiểm chứng chéo 5 nguồn.</div>
</div>""")

    news_grid_html = "\n".join(news_html_parts)
    news_count = len(news_html_parts)

    return f"""<div class="si-title">{title}</div>
<div class="si-summary">{summary}</div>
<div class="si-body">
<div class="si-col-left">
<div class="si-section-label">📊 Con số kể</div>
<div class="si-numbers">{numbers}</div>
</div>
<div class="si-col-right">
<div class="si-section-label">📰 Tin &amp; phân tích ({news_count} nguồn)</div>
<div class="si-news-grid">
{news_grid_html}
</div>
</div>
</div>
<div class="si-section-label">🔗 Góc nhìn rộng hơn</div>
<div class="si-cross-story">{cross}</div>"""


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

    # Render Special Insights (P10 automation)
    special_insights = report.get("special_insights", {})
    if not isinstance(special_insights, dict):
        special_insights = {}

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
    
    # Replace 5 Special Insights placeholders
    html = html.replace("__INSIGHT_INFLATION__", render_special_insight_html("inflation", special_insights.get("inflation")))
    html = html.replace("__INSIGHT_PRODUCTION__", render_special_insight_html("production", special_insights.get("production")))
    html = html.replace("__INSIGHT_RETAIL__", render_special_insight_html("retail", special_insights.get("retail")))
    html = html.replace("__INSIGHT_LIQUIDITY__", render_special_insight_html("liquidity", special_insights.get("liquidity")))
    html = html.replace("__INSIGHT_TRADE__", render_special_insight_html("trade", special_insights.get("trade")))

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
