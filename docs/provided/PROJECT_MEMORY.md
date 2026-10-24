# MEMORY CARD — BCTN DIGITAL TRANSFORMATION RESEARCH

**Bộ quy tắc duy nhất:** Protocol V1.0 + Dictionary V1.0, khóa cho nghiên cứu BCTN năm tài chính 2016–2025. Tài liệu gốc trong package:
- `SKILL.md` (hướng dẫn áp dụng),
- `references/protocol/quy_trinh_chuan_hoa_DT_BCTN_v1_0.docx` (24 quy tắc R01–R24),
- `data/bo_quy_tac_DT_BCTN_v1_0.xlsx` (107 khái niệm, biến thể và nguồn),
- `references/studies/` (11 bài P0–P10).

**Mục tiêu:** theo doanh nghiệp–năm: TOTAL_WORDS_FULL, TECH_FREQ/UNIQUE, DT_RAW_FREQ, DT_DISC_FREQ/UNIQUE, DT_IMPLEMENT_FREQ; chỉ số DT_INDEX = ln(1 + DT_DISC_FREQ); tỷ lệ DT_PER_10000. TECH bao trùm DT nhưng không đếm kép.

**Từ điển:** 107 concept ID, CORE 39, CONTEXT 46, TECH_ONLY 22. Tiếng Việt/Anh nhiều biến thể chung ID; longest non-overlapping match; acronym đúng chữ hoa và ngữ cảnh. `KW086` (information technology/công nghệ thông tin) không tính trong DT chính, chỉ bổ trợ DT_BROAD_FREQ.

**Ngữ cảnh:** C1 triển khai nội bộ (DISC+IMPLEMENT); C2 sản phẩm/dịch vụ bán (DISC, không IMPLEMENT); C3 kế hoạch (DISC, không IMPLEMENT); C4 bên khác, C5 phủ định, C6 thông tin chung (RAW mà thôi, loại DISC/IMPLEMENT). Ngữ cảnh mơ hồ = REVIEW.

**BCTN:** một bản PDF chính thức cho mỗi năm, ưu tiên nguồn phát hành gốc, lưu URL, SHA-256, PDF trang in/trang tệp. FULL giữ BCTC và thuyết minh nhưng loại bìa, mục lục và phần lặp; NARRATIVE là sensitivity. Tổng từ bằng word segmentation tiếng Việt, không split dấu cách.

**QA:** kiểm tra OCR, 5 trang + >=30 hit DT (hoặc tất cả) + 20 đoạn no-hit mỗi BCTN; precision >=95%, recall >=90%, độ lệch tổng từ <=2%; chưa đạt ghi REVIEW. Thiếu tài liệu = NA chứ không 0.

**Nguồn học thuật:** P1–P5/P9 cho chuyển đổi số, P8 nền kinh tế số, P0/P6/P7/P10 cho AEM/REM. Từ điển/QA C1–C6 là thiết kế vận hành của nghiên cứu.

**Bất biến:** không thêm/xóa từ cho riêng doanh nghiệp/năm; sửa protocol thành V1.1/V2.0 và chạy lại toàn mẫu; luôn xuất evidence từng occurrence.

**Lưu ý:** Đây là **file memory card**, không phải Memory tự động của ChatGPT. Phải gắn/tải tài liệu này vào phiên/Project để sử dụng khi bắt đầu cuộc trò chuyện mới.
