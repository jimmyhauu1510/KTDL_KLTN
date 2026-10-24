---
name: bctn-dt-text-mining
summary: Phân tích BCTN 2016–2025 theo Protocol V1.0/Dictionary V1.0 để đếm tổng từ, từ khóa công nghệ, chuyển đổi số và tần suất được kiểm chứng bằng chứng.
description: Sử dụng khi người dùng cung cấp mã cổ phiếu hoặc danh sách doanh nghiệp Việt Nam và muốn thu thập, xử lý, đếm từ khóa công nghệ/chuyển đổi số trong Báo cáo thường niên từ 2016 đến 2025. Luôn thực hiện nhất quán 24 quy tắc R01–R24 và bộ từ điển 107 khái niệm bất biến; xuất bảng firm-year, keyword-year, occurrence evidence và QC.
---

# Skill: BCTN – Technology & Digital Transformation Text Mining (V1.0)

**Trạng thái:** Quy tắc/định nghĩa đã khóa để áp dụng; **chưa phải kết quả nghiên cứu trên BCTN**. **Ngôn ngữ:** tiếng Việt. **Giai đoạn:** năm tài chính 2016–2025. **Đơn vị:** doanh nghiệp–năm tài chính (firm-year).

## 0. Bắt đầu phiên làm việc

1. Đọc `references/protocol/quy_trinh_chuan_hoa_DT_BCTN_v1_0.docx` và `data/bo_quy_tac_DT_BCTN_v1_0.xlsx` trước khi xử lý bất cứ BCTN nào. Bản Excel chứa chính xác 24 quy tắc, 107 khái niệm và công thức; bản DOCX giải thích phạm vi và phương pháp. File `data/dictionary_v1_0.csv` là phiên bản CSV phẳng được trích ra từ chính từ điển, thuận lợi cho code; không phải bộ từ điển khác.
2. `PROJECT_MEMORY.md` là bản tóm tắt ngắn và không được dùng để ghi đè tài liệu gốc. Nếu các tệp không khả dụng hoặc xung đột, **dừng tính chỉ số, yêu cầu bản gốc hoặc báo REVIEW**, không tự tạo lại danh sách từ khóa.
3. Xác nhận phạm vi năm 2016–2025, mã CK và trạng thái các BCTN. Nếu người dùng chỉ yêu cầu một công ty, không mặc định mở rộng sang công ty khác.
4. Ghi tên phiên bản: `PROTOCOL_V1.0` + `DICTIONARY_V1.0`. Không tùy biến bộ từ điển theo từng công ty/năm.

## 1. Phân cấp nguồn BCTN (R01–R03)

- Ưu tiên PDF chính thức trên website quan hệ cổ đông doanh nghiệp; sau đó hệ thống công bố thông tin thị trường; sau đó bản sao đối chiếu.
- Năm nghiên cứu là **năm tài chính ghi trên BCTN**, không phải năm tải hoặc năm công bố: BCTN 2025 có thể xuất bản 2026 vẫn là dữ liệu 2025.
- Chọn **một bản chuẩn duy nhất** mỗi doanh nghiệp-năm; nếu đính chính, chọn bản chính thức mới nhất và lưu dấu thay đổi. Không cộng các PDF trùng.
- Ghi `ticker, fiscal_year, publication_year, title, publisher, source_url, retrieval_date, file_name, SHA256, document_status, selected_version, exclusion_reason`.
- Không có bản chuẩn → `MISSING` / số liệu `NA`, **không phải 0**; bản có vấn đề nghiêm trọng → `REVIEW`.

## 2. Làm sạch và đếm từ (R04–R07)

- Phạm vi **FULL** là chính: bỏ bìa, mục lục, đầu/chân trang lặp, trang trắng, quảng cáo ngoài báo cáo, tệp kèm trùng; **giữ** thuyết minh và báo cáo tài chính. Phạm vi **NARRATIVE** là kiểm tra độ nhạy, trừ báo cáo tài chính, ý kiến kiểm toán và nhãn bảng số.
- Trích xuất PDF theo thứ tự đọc/cột, có đối chiếu trang; OCR **chỉ** trang ảnh/trang lỗi; giữ số trang PDF và số trang in; lưu log OCR/lỗi cột/cắt từ.
- Chuẩn Unicode NFC, dấu tiếng Việt, khoảng trắng, dấu gạch; giữ bản gốc, bản chuẩn và ánh xạ vị trí.
- Tổng từ = số từ vựng sau tách từ tiếng Việt (không đếm số âm tiết bằng dấu cách) và tách token tiếng Anh; không tính số và ký hiệu thuần túy. **Ghi công cụ và phiên bản tokenization, khóa cho toàn mẫu**. Không thay tổng từ bằng số ký tự/số dòng.

## 3. Từ điển và cơ chế match (R08–R12, R16, R20)

- Bộ từ điển cố định: **107 concept ID (`KW001`–`KW107`)**, gồm **39 CORE, 46 CONTEXT, 22 TECH_ONLY**. DT là tập con TECH; có các nhóm `AI`, `BLOCKCHAIN`, `CLOUD_IOT`, `BIG_DATA`, `APPLICATION`, `DT_DIRECT`, `TECH_ONLY`.
- Các đồng nghĩa Việt–Anh/viết tắt cùng ID chỉ là **một khái niệm duy nhất**. Tần suất = số lần xuất hiện hợp lệ, unique = số ID có ít nhất một lần.
- Khớp theo ranh giới từ/cụm, không substring; chọn match dài nhất khi chồng lấn, mỗi span tối đa một ID. Chỉ khớp viết tắt phân biệt hoa/thường như AI, ML, NLP, IoT, BI, ERP, CRM, RPA khi kiểm tra ngữ cảnh; `ai` tiếng Việt không được đếm là AI.
- `CORE`: công nghệ số đặc hiệu nhưng vẫn phải lọc ngữ cảnh không thuộc doanh nghiệp. `CONTEXT`: chỉ được vào DT khi cả nghĩa công nghệ số và ngữ cảnh doanh nghiệp phù hợp. `TECH_ONLY`: đếm trong TECH, **không** cộng DT chính.
- Riêng khái niệm "công nghệ thông tin" (`KW086` trong V1.0) **chỉ** đưa vào `DT_BROAD_FREQ` như kiểm tra độ nhạy theo P4, không đổi `DT_DISC_FREQ`.

## 4. Nhãn chủ thể/ngữ cảnh (R13–R15)

| Label | Ý nghĩa | DT_RAW | DT_DISC (D1) | DT_IMPLEMENT (D2) |
|---|---|---|---|---|
| C1 | Doanh nghiệp đã/đang triển khai **nội bộ** | Có | Có | Có |
| C2 | Doanh nghiệp **cung cấp** dịch vụ/sản phẩm số | Có | Có | Không |
| C3 | Kế hoạch/mục tiêu/sẽ triển khai của chính doanh nghiệp | Có | Có | Không |
| C4 | Khách hàng/nhà cung cấp/bên khác tự triển khai, không phản ánh hoạt động doanh nghiệp | Có | Không | Không |
| C5 | Phủ định/chưa triển khai | Có | Không | Không |
| C6 | Mô tả chung, chú giải, xu hướng không quy về công ty | Có | Không | Không |

- Câu mơ hồ không tự phán đoán C1; lưu `REVIEW` kèm câu và trang. Lưu lượt khớp gốc (RAW) để kiểm toán.
- `C2` rất quan trọng với doanh nghiệp công nghệ: **bán** nền tảng AI ≠ **tự triển khai** nền tảng AI trong quản trị doanh nghiệp.

## 5. Công thức (R17–R19)

- `TOTAL_WORDS_FULL` và tùy chọn `TOTAL_WORDS_NARR`.
- `TECH_FREQ`: số lượt match hợp lệ thuộc hợp tất cả concept TECH, **không đếm kép**; `TECH_UNIQUE`: số ID có xuất hiện.
- `DT_RAW_FREQ`: số lượt concept DT trước lọc ngữ cảnh; `DT_DISC_FREQ`: số lượt DT CORE/CONTEXT đã qua lọc, ngữ cảnh C1+C2+C3; `DT_UNIQUE`: số concept DT có occurrence hợp lệ.
- `DT_IMPLEMENT_FREQ`: số lượt DT có bằng chứng C1; `DT_IMPLEMENT_INDEX = ln(1+DT_IMPLEMENT_FREQ)`.
- **Biến nghiên cứu chính:** `DT_INDEX = ln(1+DT_DISC_FREQ)`.
- `DT_PER_10000 = 10000 * DT_DISC_FREQ / TOTAL_WORDS_FULL`.
- `TECH_PER_10000 = 10000 * TECH_FREQ / TOTAL_WORDS_FULL`.
- `DT_TECH_SHARE = DT_DISC_FREQ / TECH_FREQ` nếu mẫu số >0; ngược lại `NA`.
- `DT_BROAD_FREQ = DT_DISC_FREQ +` lượt hợp lệ C1–C3 thuộc `KW086` (không đưa vào DT chính).
- `DIGITAL_DUMMY = 1` nếu `DT_IMPLEMENT_FREQ>0`, ngược lại `0`, **chỉ khi DOC_STATUS=OK**.
- Nếu tài liệu không hợp lệ hoặc tổng từ bằng 0, những chỉ số không xác định phải là `NA`, không thay bằng 0.

## 6. Kiểm soát chất lượng (R21–R24)

- Trên **mỗi BCTN**: kiểm tra mọi trang có cảnh báo OCR; kiểm tra ít nhất 5 trang có nội dung (đầu, giữa, cuối, lấy mẫu); ít nhất 30 occurrence DT hoặc tất cả nếu ít hơn 30; thêm 20 đoạn không hit để kiểm tra bỏ sót.
- Trên tập kiểm chứng độc lập: `precision >= 0.95`, `recall >= 0.90`, chênh lệch số từ giữa hai phương pháp kiểm đếm độc lập `<= 2%`. Đây là **ngưỡng QA tự định nghĩa của protocol**, không quy thuộc các bài P0–P10.
- Không đạt hoặc chưa kiểm chứng → `REVIEW`, không công bố như số liệu đã kiểm toán.
- Giữ log thay đổi và bằng chứng; chỉ sửa từ điển qua `V1.1`/`V2.0` rồi **chạy lại toàn bộ** doanh nghiệp–năm, không vá riêng mã hoặc năm.

## 7. Đầu ra tối thiểu

1. `report_year.csv/.xlsx`: ticker, năm, URL, hash, phạm vi, tổng từ, các metrics và `DOC_STATUS`; tách NA/zero.
2. `keyword_year.csv/.xlsx`: một hàng/mã/năm/concept ID, số lượt RAW/DISC/IMPLEMENT, tên & nhóm, từ điển V1.0.
3. `occurrences.csv/.xlsx`: ticker, năm, SHA-256, trang PDF/trang in, từ khóa ID, biến thể khớp, span, câu và đoạn trích, C1–C6, lý do/ghi chú, trạng thái review.
4. `qa_log.csv/.xlsx`: trang lỗi/OCR, QA mẫu, sai lệch đếm từ, precision/recall, quyết định QA, trường hợp cần xử lý.
5. `sources_manifest.csv`: nguồn chính thức, bản được chọn, lịch sử thay đổi, trạng thái đầy đủ 10 năm.

Có thể dùng các mẫu đầu vào trong thư mục `data/templates/`.

## 8. Phân biệt khung học thuật và lựa chọn vận hành

- Đo lường từ khóa DT chủ yếu dựa trên **P1–P5 và P9**; `P1` Appendix 2 giới thiệu năm nhóm từ (dựa trên Wu et al. 2021); `P2` có nguyên tắc lọc phủ định/bên thứ ba; `P4` đặc biệt có nghiên cứu ở Việt Nam và phân đoạn từ; `P3`/`P5` có `ln(1+x)`.
- `P0`, `P6`, `P7`, `P10` phục vụ luận cứ về quản trị lợi nhuận, không phải từ điển chuyển đổi số; `P8` là nền lý thuyết kinh tế số.
- **107 khái niệm, biến thể tiếng Việt, nhãn C1–C6, rule CORE/CONTEXT và ngưỡng QA** là cách **nhóm nghiên cứu xây dựng/chốt**, không được giả trình bày như bản sao chính thức nguyên văn của một bài nào.
- Chỉ số thể hiện **mức độ công bố/thảo luận trong BCTN**, không đủ để khẳng định chuyển đổi số thực tế; báo cáo riêng số triển khai C1.

## 9. Hành vi trong trả lời người dùng

- Trước khi nghiên cứu mã mới, cho biết trạng thái đủ/thiếu BCTN; khi chưa chạy xong thì không bịa số.
- Mọi số định lượng phải có nguồn tài liệu BCTN, năm tài chính, bộ quy tắc, tình trạng QA.
- Không ghi `OK` khi chưa kiểm tra QA; không tạo URL, đoạn trích, số trang, hay tần suất từ suy đoán.
- Khi thông tin yêu cầu vượt Protocol V1.0, ghi nhận rõ đó là **phân tích bổ sung** và không thay đổi các biến chuẩn.
