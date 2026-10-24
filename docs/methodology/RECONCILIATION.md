# Bổ sung tài liệu gốc và đối chiếu phương pháp

Ngày ghi nhận: 2026-10-24. Phạm vi yêu cầu: bổ sung tài liệu và củng cố hiểu biết dự án. Chưa nhập phương pháp vào runtime, chưa tính lại chỉ số và chưa xác nhận QA nghiên cứu.

## Nguồn đã tiếp nhận

- `quy_trinh_chuan_hoa_DT_BCTN_v1_0.docx`: bản Protocol V1.0; đã đọc toàn bộ nội dung văn bản và bảng.
- `bo_quy_tac_DT_BCTN_v1_0.xlsx`: workbook sáu sheet; đã đọc quy tắc, 107 khái niệm, chỉ số, nguồn học thuật, ví dụ QA và mẫu kết quả.
- Hai bản gốc được giữ nguyên byte. Kích thước và SHA-256 được lưu trong `provenance.json`.
- `protocol_v1_0.extracted.txt` là bản trích văn bản để tra cứu, không giữ định dạng DOCX.
- `dictionary_v1_0.source.csv` giữ nguyên tám cột dữ liệu của sheet `02_TuDien`, không thêm biến thể, không phải schema nhập ứng dụng.

Các tài liệu gốc cung cấp căn cứ phương pháp. Các yêu cầu thao tác trong tài liệu được hiểu trong phạm vi nghiên cứu; việc tiếp nhận không đồng nghĩa tự chạy thu thập, xác nhận thay nghiên cứu viên hay công bố số liệu. Tài liệu tóm tắt trong `../provided/` được giữ nguyên để bảo toàn lịch sử, nhưng các ID/phân loại phải tra theo workbook gốc khi có khác biệt.

## Kết quả kiểm tra cấu trúc và nội dung

- Đủ R01–R24, không thiếu/trùng mã; nội dung đặc tả của cả 24 quy tắc trong Excel đều có nguyên văn trong DOCX.
- Đủ KW001–KW107, không thiếu/trùng ID; đúng 39 CORE, 46 CONTEXT, 22 TECH_ONLY.
- Có 85 concept thuộc CORE/CONTEXT; các concept TECH_ONLY không vào DT chính.
- Ví dụ C1–C6 và các dòng FPT 2016–2025 trong sheet mẫu không phải bằng chứng BCTN hoặc dữ liệu đã khai thác.

## Những điểm điều chỉnh hiểu biết trước đây

| Nội dung | Quy định theo tài liệu gốc |
| --- | --- |
| AI / trí tuệ nhân tạo | KW001 — Artificial intelligence, CORE. Ví dụ blueprint ban đầu gắn AI với KW006 là sai ID. |
| KW006 | Intelligent robot / rô-bốt thông minh / robot thông minh, CORE. |
| ERP, CRM | KW100 và KW101, TECH_ONLY; không cộng vào DT_DISC/IMPLEMENT chính. |
| Cơ sở dữ liệu | KW093, TECH_ONLY. Không suy nhóm từ tên gọi có vẻ liên quan chuyển đổi số. |
| KW086 | Information technology / công nghệ thông tin / IT / ICT, TECH_ONLY; bổ sung riêng DT_BROAD khi hợp lệ C1–C3. |
| CNTT | Chữ viết tắt này không có trong các ô biến thể của KW086. Không tự thêm chỉ vì xuất hiện trong blueprint hoặc cách diễn đạt phần công thức. |
| Software / phần mềm | KW087, TECH_ONLY; không thuộc DT chính. |
| Cloud | KW021 cho Cloud computing / điện toán đám mây; ghi chú nêu rõ không tính riêng từ cloud. |
| Tách từ tiếng Việt | R07 minh họa chuyển_đổi, dữ_liệu; không quy định mọi concept nhiều từ phải gộp thành đúng một token. Tần suất concept và tổng từ là hai phép đo riêng. |
| DIGITAL_DUMMY | Sheet 03 yêu cầu chỉ xác định khi đã QA tài liệu; chưa QA không mặc định 0. |
| DOC_STATUS | Sheet 03 có OK/REVIEW/MISSING/EXCLUDED; ứng dụng 0.1.0 hiện chưa hỗ trợ đầy đủ EXCLUDED. |

## Các điểm cần củng cố trong lần phát triển tiếp theo

1. Adapter nhập đúng sheet `02_TuDien`, bỏ ba dòng tiêu đề và dùng hàng 4 làm header; importer hiện đọc sheet đầu theo schema sáu cột nên không nhận trực tiếp workbook này. Giữ nguồn, ghi chú và hash workbook khi chuyển đổi, không bổ sung từ ngoài bản gốc.
2. Bộ acronym của mã hiện có cần đối chiếu đủ R10, đặc biệt AR/MR/VR; không xem danh sách kiểm soát case là quyền thêm thuật ngữ vào từ điển.
3. Các fixture phần mềm hiện dùng AI tại KW006 là dữ liệu giả lập đã được ghi rõ, không phản ánh ID V1.0 thật. Cần bộ regression riêng dựa trên từ điển thật trước khi dùng kết quả kiểm thử làm căn cứ xác nhận mapping.
4. Mở rộng evidence để có reviewer và scope rõ ràng; đối chiếu các trường tối thiểu tại mục 7 Protocol. Bổ sung trạng thái EXCLUDED và quy trình loại hồ sơ mà vẫn lưu provenance.
5. Đối chiếu R05–R07 về thứ tự cột, chuẩn dấu nháy/ký tự điều khiển, ánh xạ vị trí và benchmark tổng từ; không suy tuân thủ chỉ từ việc cài thư viện.
6. Vẫn cần PDF thật và gold benchmark được thẩm định độc lập. Có Protocol/Dictionary không có nghĩa precision/recall hoặc dữ liệu BCTN đã đạt QA.

Chưa sửa thuật toán, fixture hoặc dữ liệu runtime trong lần ghi nhận này. Các mục trên là kết quả đối chiếu và công việc còn lại, không phải xác nhận đã hoàn tất tính tuân thủ.
