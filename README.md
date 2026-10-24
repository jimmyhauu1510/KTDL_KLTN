# VietFin-DTMiner

Công cụ nghiên cứu BCTN Việt Nam, năm tài chính 2016–2025: giao diện web tiếng Việt, CLI batch, trích PDF/OCR, đối soát từ điển, gắn nhãn ngữ cảnh, duyệt bằng chứng, QA và xuất năm bảng kinh tế lượng.

Phiên bản **0.1.0** là ứng dụng một người dùng chạy cục bộ, đã có luồng xử lý đầu cuối. Chưa phải hạ tầng phân tán đã kiểm định cho 10.000 PDF. Không kèm từ điển giả, dữ liệu doanh nghiệp giả hoặc số liệu nghiên cứu dựng sẵn.

## Cài đặt và chạy

Yêu cầu Python **3.12+**, `uv`, `curl`, `tesseract-ocr`, font DejaVu. Trên Debian/Ubuntu có thể cài các gói hệ thống bằng trình quản lý gói: `tesseract-ocr fonts-dejavu-core`. Script giữ kiểm tra TLS, hash các gói Python và checksum mô hình OCR.

```bash
bash scripts/setup.sh
source .venv/bin/activate
export VIETFIN_TESSDATA="$PWD/data/tessdata"
vietfin serve
```

Ứng dụng nghe ở cổng 8000 trên loopback. API được mô tả tại đường dẫn `/docs` của server. Không mở ứng dụng này ra Internet: chưa có tài khoản, phân quyền hay bảo mật đa người dùng. Cloud onboarding không hỗ trợ đường dẫn preview loopback.

Trong môi trường cloud hiện tại:

```bash
cd /workspace/KTDL_KLTN
source /workspace/.venvs/vietfin-dtminer/bin/activate
export VIETFIN_DATA=/workspace/vietfin-data
export VIETFIN_TESSDATA=/workspace/.local/share/vietfin-dtminer/tessdata
vietfin serve
```

`VIETFIN_DATA` chọn workspace độc lập (mặc định `./data`). `VIETFIN_VENV` và `UV_CACHE_DIR` điều chỉnh vị trí cài đặt. Không chạy hai server hoặc các lệnh CLI ghi dữ liệu đồng thời trên cùng workspace. Chỉ một worker nền xử lý PDF tuần tự để giới hạn RAM; batch lớn dùng CLI và theo dõi log.

## Quy trình sử dụng

1. Vào **Phương pháp & cấu hình**, nạp Protocol gốc và Dictionary V1.0. Hai bản gốc người dùng bổ sung ngày 2026-10-24 đã được lưu tại `docs/methodology/`; hướng dẫn/tóm tắt trước đó ở `docs/provided/`. Xem [bản đối chiếu tài liệu gốc](docs/methodology/RECONCILIATION.md) trước khi chuyển đổi/import. Lưu tài liệu trong repository chưa đồng nghĩa đã nạp runtime hoặc xác nhận QA.
2. Nhập PDF, tải trực tiếp URL HTTPS hoặc đăng ký danh mục mã/năm còn thiếu. Mỗi PDF được lưu bất biến theo SHA-256. Bản đính chính chỉ thay bản được chọn khi người dùng chọn rõ và ghi lý do; PDF, metadata và kết quả cũ vẫn lưu trong lịch sử phiên bản.
3. Chạy trích xuất. PyMuPDF lấy text theo thứ tự bố cục; trang có dưới 30 chữ cái thử OCR tiếng Việt. Không tự coi OCR thành công là nội dung chính xác.
4. Duyệt **tất cả trang** để xác định FULL, NARRATIVE, bìa, mục lục, header/footer và số trang in. Các nhận diện tự động chỉ là gợi ý. FULL giữ BCTC/thuyết minh; NARRATIVE loại các phần đó sau khi người dùng đối chiếu. Có thể sửa OCR theo PDF, vẫn giữ bản trích xuất ban đầu.
5. Chạy lại phân tích sau khi chốt phạm vi. Mọi sửa phạm vi/văn bản làm mất hiệu lực kết quả và QA phụ thuộc. Tokenizer/phiên bản được khóa khi phân tích đầu tiên.
6. Duyệt từng occurrence: nhãn C1–C6, nghĩa công nghệ số, lý do trích dẫn. Rule engine và Ollama chỉ gợi ý, không tự chuyển thành dữ liệu đã xác nhận.
7. Kiểm chứng mẫu QA, nhập kiểm đếm từ độc lập và phương pháp kiểm đếm, đối chiếu metadata nguồn/năm tài chính. Chỉ đủ các điều kiện mới có `OK`.
8. Xuất ZIP CSV/Excel/Parquet; mỗi ZIP có đúng năm bảng trong đặc tả. Dữ liệu `REVIEW` là tạm tính; lọc `doc_status=OK` trước khi sử dụng như số liệu đã kiểm chứng.

## Dictionary và Protocol

Ứng dụng không tái tạo danh sách 107 khái niệm từ các ví dụ trong mô tả. Tình trạng tài liệu trước khi phân tích nghiên cứu:

- Đã có `docs/methodology/quy_trinh_chuan_hoa_DT_BCTN_v1_0.docx`, đủ 24 quy tắc và đã đối chiếu văn bản với sheet quy tắc Excel.
- Đã có `docs/methodology/bo_quy_tac_DT_BCTN_v1_0.xlsx`, đủ 107 concept đúng cơ cấu. Cần chuyển đổi đúng sheet `02_TuDien` sang schema nhập; CSV tám cột trích nguyên bản trong thư mục này chỉ phục vụ tra cứu, không nhập thẳng được.
- Vẫn cần PDF chuẩn và benchmark được thẩm định độc lập để xác nhận phương pháp và độ chính xác.

Dictionary nhập bằng CSV UTF-8 hoặc sheet đầu XLSX, với các cột:

| Cột | Nội dung |
| --- | --- |
| `concept_id` | Đúng KW001–KW107, không lặp |
| `keyword_name` | Tên khái niệm theo bản gốc |
| `concept_group` | Nhóm theo bản gốc |
| `category` | 39 CORE, 46 CONTEXT, 22 TECH_ONLY |
| `terms` | Biến thể chính thức, ngăn bằng `;` |
| `case_sensitive_terms` | Các biến thể phải đúng hoa/thường, ngăn bằng `;` |

Mẫu tải trong giao diện chỉ có tiêu đề cột. Không tự suy luận mapping từ workbook nhiều sheet; cần chuyển đổi và đối chiếu bởi người có bản gốc. Import kiểm tra cấu trúc, số lượng và trùng biến thể; không thể tự chứng nhận nội dung chỉ qua số lượng ID. Người dùng phải xác nhận nguồn gốc. Sau khi có phân tích, không cho đổi từ điển sang hash khác trong cùng workspace; phương pháp mới cần version/workspace mới và chạy lại toàn mẫu.

Các viết tắt AI, ML, NLP, IoT, BI, ERP, CRM, RPA, CNTT, ICT, API, IT luôn phải đúng hoa/thường. `ai` không được nhập như biến thể AI. Các lượt khớp ưu tiên span dài nhất trên trang, không chồng lấn, có boundary Unicode; tie được xử lý tất định theo vị trí và Concept ID. RAW được giữ để kiểm toán; DT_DISC chỉ cộng CORE/CONTEXT, nghĩa số đã duyệt, C1–C3 và loại KW086. C1 được đếm riêng trong IMPLEMENT. KW086 chỉ bổ sung DT_BROAD. TECH loại các trường hợp người duyệt xác nhận không mang nghĩa công nghệ.

Span `start_char/end_char` là khoảng nửa mở trong văn bản **trang đã chuẩn hóa**; offsets gốc và văn bản thô được giữ trong workspace. Cửa sổ là câu chứa hit và tối đa một câu trước/sau trong cùng trang. Phân câu hiện dùng dấu `. ! ?`, có hạn chế với viết tắt và cấu trúc bảng; cần đối chiếu PDF.

## Tách từ và QA

Underthesea mặc định có thể tách `trí_tuệ nhân_tạo`, `chuyển_đổi số`; không khẳng định mọi concept luôn là một token. Tổng từ đếm token có chữ cái, bỏ số/ký hiệu thuần. Chưa có từ điển bổ trợ tự tạo nhằm ép kết quả. Cần đối soát độc lập và xác nhận quy trình gốc trước khi sử dụng kết quả nghiên cứu.

QA lấy mẫu có thể tái lập bằng SHA-256: tối đa 30 hit DT (toàn bộ nếu ít hơn), 20 đoạn không hit, ít nhất 5 trang nội dung nếu có đủ, gồm đầu/giữa/cuối. Các tài liệu dưới 5 trang kiểm tra toàn bộ trang hiện có. Mọi trang phải được duyệt phạm vi; mọi occurrence phải được duyệt ngữ cảnh.

Precision = TP/(TP+FP), recall = TP/(TP+FN), với nhãn được nhập từ thẩm định độc lập trên mẫu. FN là số lượt bỏ sót phát hiện trong mẫu no-hit. Đây là ước lượng mẫu; không tự suy ra các ngưỡng đã đạt trên toàn corpus. Mẫu thiếu 20 no-hit, mẫu chưa duyệt, không có TP để ước lượng precision/recall, lỗi OCR nội dung chưa xử lý hoặc tổng từ bằng 0 đều giữ REVIEW. QA yêu cầu precision ≥95%, recall ≥90%, độ lệch từ so với kiểm đếm độc lập ≤2%, có mô tả phương pháp và đã đối chiếu nguồn/năm tài chính.

`MISSING` và chỉ số không xác định xuất `NA` trong CSV/Excel và null trong Parquet; không thay bằng 0. `DIGITAL_DUMMY` chỉ bằng 0/1 khi hồ sơ OK. C1–C3 chưa duyệt không được cộng vào DT_DISC. Các chỉ số ở hồ sơ REVIEW vẫn là tạm tính, kể cả khi giá trị hiện bằng 0.

## CLI batch

```bash
vietfin status
vietfin dictionary /path/dictionary.csv --attest-original
vietfin protocol /path/protocol.docx --attest-original
vietfin missing FPT CMG
vietfin ingest FPT 2024 /path/FPT_BCTN_2024.pdf --source-url https://official.example/report.pdf
vietfin batch templates/batch_manifest.csv
vietfin process
vietfin process FPT-2024 CMG-2024
vietfin export research_csv.zip
vietfin export research_parquet.zip --format parquet
```

`templates/batch_manifest.csv` chỉ chứa header. `path` tương đối tính từ thư mục manifest; nếu không có path thì tải `source_url`; cả hai trống thì MISSING. Năm tài chính do nghiên cứu viên xác định, không suy từ tên file. Batch tiếp tục sau lỗi từng dòng và trả exit code 1 nếu có lỗi; không coi batch lỗi một phần là hoàn tất. Chạy lại phân tích chủ động sẽ đặt lại nhãn/QA, giữ lịch sử thao tác trong audit.

Tính năng tìm PDF trên trang IR chỉ đọc liên kết PDF trong HTML tĩnh một trang. Chưa có adapter chuyên biệt vượt JavaScript/CAPTCHA cho HOSE, HNX, UBCKNN; có thể nhập URL được xác minh hoặc PDF tải thủ công. Không có dữ liệu crawler mẫu giả.

## Ollama local tùy chọn

Cần cài Ollama và model phù hợp tài nguyên máy riêng, sau đó đặt `VIETFIN_OLLAMA_MODEL` trước khi khởi động server. Mặc định endpoint `http://127.0.0.1:11434`; `VIETFIN_OLLAMA_URL` chỉ cho loopback. Nút **Gợi ý từ Ollama local** dùng JSON schema với temperature 0. Không tự tải model hoặc giả định có GPU. Các nhãn model vẫn cần duyệt; không dùng xác suất tự khai của LLM làm confidence đã hiệu chuẩn. Chưa có benchmark C1–C6 hoặc model fine-tuned được cung cấp.

## Lưu trữ và kiểm thử

SQLite WAL lưu metadata, nội dung, occurrence, trạng thái và audit. PDF lưu ở `pdf/<sha256>.pdf`; tài liệu phương pháp và phiên bản cũ ở `artifacts/`. SHA được kiểm tra lại trước mỗi xử lý. Để sao lưu, dừng server và CLI rồi sao chép **toàn bộ** `VIETFIN_DATA` (bao gồm các tệp SQLite WAL nếu còn). Không chỉ sao chép PDF hoặc file database đang mở.

```bash
VIETFIN_TESSDATA=/path/tessdata python -m pytest -q
node --check vietfin/static/app.js
```

Các test dùng từ điển 107 ID và PDF **giả lập rõ ràng**, chỉ để kiểm tra thuật toán, API, trạng thái QA, OCR, lưu phiên bản, tính toàn vẹn, xuất dữ liệu và khóa phương pháp. Chúng không phải bộ dữ liệu nghiên cứu hay bằng chứng đạt precision/recall thực tế. Kiểm tra OCR cần Tesseract tiếng Việt và font DejaVu.

Chưa triển khai Celery/Redis, PostgreSQL/pgvector, MinIO, xác thực đa người dùng, queue phân tán hoặc kiểm thử tải 1,5–2 triệu trang. Các điểm này cần một giai đoạn triển khai/vận hành riêng. Không quảng bá bản này là đạt quy mô sản xuất hay tuân thủ Protocol đầy đủ khi chưa có tài liệu gốc và benchmark.
