# Kế hoạch triển khai: nhận bảng enemy dán dạng một cột

## Mục tiêu

Sửa parser của `enemy_event_generator` để đọc được bảng Nightmare được copy thành một giá trị trên mỗi dòng. Dữ liệu sẽ được dựng lại thành các hàng enemy trước khi áp dụng parser bảng hiện có.

## Nguyên nhân đã xác nhận

`_plain_rows()` trong `utilities/enemy_event_generator/parser.py` coi mỗi dòng vật lý là một hàng. Với dữ liệu Nightmare, các header `NAME`, `CLASS`, `LV`, ... nằm trên các hàng riêng, trong khi `parse_table()` chỉ nhận header khi `CLASS` và `LV/LEVEL` nằm trên cùng một hàng. Kết quả tái hiện: 27 hàng, mọi hàng rộng một ô, rồi trả về `missing_header`.

## Quyết định kỹ thuật

- Chỉ chuẩn hóa khi toàn bộ dữ liệu là hàng một ô và có chuỗi header liên tiếp hợp lệ; HTML, TSV và bảng cách cột bằng khoảng trắng giữ nguyên hành vi hiện tại.
- Header được nhận theo các alias sẵn có: `SKILL`/`SKL`, `LV`/`LEVEL`, `MOV`/`MOVE`, `ITEM & SKILL`.
- Một record chỉ được tách khi dòng kế tiếp có đủ chữ ký `NAME`, `CLASS`, rồi mười giá trị số liên tiếp từ `LV` đến `MOV`. Mọi dòng trước record kế tiếp được ghép bằng newline vào ô `ITEM & SKILL`.
- Không dùng catalog class/item của game để đoán ranh giới record. Nếu không chứng minh được ranh giới, tool phải báo lỗi rõ ràng, không tự sinh enemy sai.

## Công việc

### Task 1: Chuẩn hóa bảng một cột và khóa regression

**Mô tả:** Thêm bước chuẩn hóa giữa `extract_rows()` và dò header. Dùng một fixture mang đúng cấu trúc Nightmare đã cung cấp để tạo lại header hàng ngang và mười record.

**Tiêu chí chấp nhận:**

- [x] Dữ liệu Nightmare một cột tạo đúng 10 enemy và không có `missing_header`.
- [x] `ITEM & SKILL` giữ nhiều dòng; item, forge và danh sách skill vẫn được parser hiện tại đọc đúng.
- [x] Test HTML và TSV hiện có vẫn pass, không đổi kết quả.

**Xác minh:**

- [x] Chạy `E:\FE\lt-maker\utilities\enemy_event_generator\.python\python.exe -m unittest utilities.enemy_event_generator.tests.test_parser`.

**Phụ thuộc:** Không có.

**Files dự kiến:**

- `utilities/enemy_event_generator/parser.py`
- `utilities/enemy_event_generator/tests/test_parser.py`

**Quy mô:** S (2 files).

### Task 2: Chặn suy đoán không an toàn và mô tả định dạng nhập

**Mô tả:** Thêm lỗi có dấu, hướng dẫn rõ ràng khi phát hiện header một cột nhưng không thể chứng minh ranh giới từng enemy. Cập nhật README để mô tả ba định dạng được nhận: HTML table, TSV và bảng một cột theo cấu trúc đầy đủ.

**Tiêu chí chấp nhận:**

- [x] Dữ liệu một cột thiếu chuỗi số cần thiết không sinh enemy lệch cột.
- [x] Lỗi mới chỉ ra cần dán bảng HTML/TSV nếu input không thể tách an toàn.
- [x] README nêu rõ loadout được phép có nhiều dòng.

**Xác minh:**

- [x] Bổ sung test malformed input trong `test_parser.py`.
- [x] Đọc lại README và kiểm tra ví dụ khớp hành vi parser.

**Phụ thuộc:** Task 1.

**Files dự kiến:**

- `utilities/enemy_event_generator/parser.py`
- `utilities/enemy_event_generator/tests/test_parser.py`
- `utilities/enemy_event_generator/README.md`

**Quy mô:** S (3 files).

### Task 3: Kiểm tra tích hợp và phân loại cảnh báo còn lại

**Mô tả:** Chạy toàn bộ suite của generator bằng input Nightmare đã chuẩn hóa. Xác nhận parser hết lỗi header, còn các diagnostics không liên quan vẫn hiển thị đúng độ nghiêm trọng.

**Tiêu chí chấp nhận:**

- [x] Toàn bộ test của generator pass.
- [x] Nightmare không còn `missing_header`; event/plan vẫn được tạo.
- [x] Không thay đổi hay che giấu lỗi catalog `Elfire`, cảnh báo AI/baseline, hoặc yêu cầu group thủ công.

**Xác minh:**

- [x] Chạy `E:\FE\lt-maker\utilities\enemy_event_generator\.python\python.exe -m unittest discover -s utilities\enemy_event_generator\tests -p 'test*.py'`.
- [x] Dán block Nightmare vào UI và kiểm tra phần Issues/event output ở Qt offscreen.

**Phụ thuộc:** Tasks 1-2.

**Files dự kiến:**

- Không bắt buộc thay đổi source; chỉ bổ sung test tích hợp nếu phát hiện cần thiết.

**Quy mô:** XS.

## Checkpoint sau Tasks 1-2

- [x] Parser đọc đúng Nightmare one-column paste.
- [x] HTML/TSV không regression.
- [x] Input mơ hồ dừng bằng lỗi rõ ràng, không đoán NID hay cắt loadout sai.

## Rủi ro và cách giảm thiểu

| Rủi ro | Ảnh hưởng | Cách giảm thiểu |
| --- | --- | --- |
| Nhiều dòng item/skill bị nhầm là record kế tiếp | Cao | Chỉ bắt đầu record khi đủ 10 trường số sau `NAME` và `CLASS`. |
| Dữ liệu thiếu một stat làm lệch cả bảng | Cao | Không tự bù cột; trả lỗi hướng dẫn dán HTML/TSV. |
| Regression Word/TSV | Trung bình | Giữ normalizer sau `extract_rows()` và chỉ kích hoạt với toàn bộ hàng một ô; giữ test cũ. |

## Không thuộc lỗi header này

- `Elfire` không có exact NID trong catalog item. Đây là lỗi mapping riêng; cần thêm alias tới NID đã xác nhận hoặc thêm item vào project, không được tự đoán giữa `Fire_D`, `Fire_S`, `Fire_E`.
- Cảnh báo Default AI là do bảng không có cột AI; tool đang dùng Default AI theo thiết kế.
- Cảnh báo Normal là so sánh data chapter hiện có với baseline Normal.
- Lỗi group yêu cầu tạo group/positions thủ công trong LT Maker; generator không sinh `add_group;` theo yêu cầu trước đó.
