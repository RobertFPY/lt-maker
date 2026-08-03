# LT Enemy Event Generator MVP

Ứng dụng Windows đọc bảng enemy dán từ Word/Google Docs, đối chiếu NID trong một
project Lex Talionis, lập kế hoạch **shared pool lấy Normal làm mặc định** và sinh event cấu hình
enemy. Tool không sinh `add_group`.

Tên trong Word được hiểu là trường `name`. Event output luôn dùng trường `nid`.
Với skill có tier, ví dụ `Darting Blow 1`, tool ưu tiên NID kết thúc bằng `_T1`
và loại các helper skill như `_Effect` khỏi kết quả tự động.
Nếu `name` không tồn tại trong catalog hoặc vẫn tương ứng với nhiều NID, tool giữ
`ERROR` để người dùng xác nhận alias thay vì tự chọn nhầm.

MVP **chỉ đọc** `.ltproj`. Nó không sửa `levels.json`, `events.json` hay unit/group
trong editor.

## Dùng ứng dụng

1. Chọn thư mục project `.ltproj` và Level NID.
2. Giữ `Unit prefix = Enemy_`, hoặc để trống để dùng NAME làm Unit NID. Nhập group prefix
   (level 0 là `Enemy1`).
3. Dán riêng bảng của Normal, Hard, Lunatic và Nightmare vào bốn tab.
4. Nếu dòng cuối mỗi bảng là boss, bật tùy chọn đó và nhập đúng Boss unit NID. Boss NID trống
   hoặc không có trong chapter sẽ bỏ qua chế độ boss và giữ dòng cuối là enemy thường.
5. Bấm **Đọc + sinh event**.
6. Sửa hết dòng `ERROR` trong tab **Kiểm tra**. Sau đó mới sao chép event.

Nếu bảng không có cột `AI`, tool dùng `AI mặc định` từ danh sách lấy trực tiếp từ `ai.json` và hiện cảnh báo. Phải kiểm tra
thủ công các unit dùng `Defend`, `Pursue` hoặc AI đặc biệt; đây là dữ liệu không thể
suy ra an toàn chỉ từ stats/item trong Word.

Định dạng cột được hỗ trợ:

```text
NAME  CLASS  LV  HP  STR  MAG  SKILL  SPD  LUCK  DEF  RES  MOV  ITEM & SKILL
```

Trong ô cuối, mỗi item/skill nên nằm trên một dòng:

```text
Iron Sword (mighty +3) (equipped)
Vulnerary (droppable)
Skill: Axebreaker T1, Vantage T4
```

Có thể thêm cột tùy chọn `AI` và `WEXP`. Ví dụ WEXP: `Axe:71, Bow:31`.

## Quy tắc shared pool

- Số slot bằng số enemy lớn nhất trong bốn bảng (thường là Nightmare).
- Slot được ghép theo **thứ tự dòng**: dòng 1 của mọi độ khó là `Enemy_0`.
- Class của cùng một slot phải giống nhau. Nếu khác, tool báo lỗi và không tự
  `change_class`, vì đổi class có thể làm lệch stats.
- Unit có mặt trong Normal phải được tạo sẵn với level, stats, AI, item và skill
  của Normal; `starting_position = None`.
- Nhánh Normal không sinh `set_stats`, `give_item` hoặc `give_skill`. Forge vẫn
  được sinh vì đó là thay đổi trên item instance lúc runtime.
- Hard/Lunatic/Nightmare đều so trực tiếp với Normal. Item/skill thiếu ở độ khó
  đích được xóa bằng `remove_item`/`remove_skill`; item/skill mới mới được thêm.
- Stat của độ khó cao chỉ xuất những trường khác Normal.
- Slot không xuất hiện trong Normal mới dùng nền trung tính, không item/skill.
- Skill cần thêm cho toàn bộ enemy (từ 2 unit) hoặc cho ít nhất 3 enemy trong cùng
  độ khó được gom thành vòng lặp `for`. Nhiều skill có cùng danh sách người nhận
  dùng chung một vòng lặp.
- Mỗi UnitGroup lưu danh sách subset và positions riêng.
- Event chỉ cấu hình unit; không tự gọi `add_group`.
- Nếu tab Normal trống, tool ưu tiên group `{Group prefix}Normal` trong chapter để lấy AI,
  item và skill gốc. Stats generic không được lưu trong JSON nên stats ở độ khó cao vẫn được đặt tuyệt đối.
- `set_level` của engine là phép cộng tương đối; tool tự sinh delta từ level nền.
- Item trùng cùng NID trên một unit bị báo lỗi vì forge/equip có thể trúng object đầu.

## Alias cho lỗi chính tả

Chuột phải vào từ đã bôi đen trong tool rồi chọn **Thêm vào alias…**. Dialog cho phép sửa từ gốc
và chọn NID đích hợp lệ từ project; alias được lưu vào [aliases.json](aliases.json). Tool không tự đoán tier skill.

```json
{
  "classes": {"Mercnary": "Mercenary"},
  "items": {},
  "skills": {},
  "ai": {}
}
```

Sau khi sửa alias, phân tích lại bảng. Chỉ dùng NID đích thực sự tồn tại trong project.
Các tên như `Quick Reposte+`, `Light and Death` hoặc `Luna+r` phải được bạn xác
nhận đúng tier/NID; MVP cố ý không đoán tự động.

## Chạy source

Yêu cầu Python 3.11/3.12 và PyQt5:

```powershell
py -3 -m pip install -r utilities\enemy_event_generator\requirements.txt
.\utilities\enemy_event_generator\run_dev.ps1
```

Chạy test core:

```powershell
py -3 -m unittest discover -s utilities\enemy_event_generator\tests -p 'test*.py'
```

## Build portable EXE

Build mặc định là PyInstaller `--onedir`: khởi động nhanh hơn `--onefile` và không
phải tự giải nén mỗi lần mở.

```powershell
.\utilities\enemy_event_generator\build.ps1
```

Kết quả nằm trong:

```text
utilities\enemy_event_generator\dist\LTEnemyEventGenerator\
```

Phát hành cả thư mục này. `aliases.json` nằm cạnh EXE để có thể chỉnh mà không build lại.
Script build cũng chép README này vào thư mục phát hành. Có thể nén nguyên thư mục
thành `LTEnemyEventGenerator-portable.zip` để chuyển sang máy Windows khác.

## Giới hạn MVP

- Không tự migration các unit/group cũ thành `Enemy_0...`.
- Không tự ghi event vào project.
- Không tự tạo positions; positions phải được đặt và kiểm tra trong LT Maker.
- Bảng plain text nhiều dòng nên dán trực tiếp từ Word/Google Docs để giữ HTML table;
  TSV phù hợp khi mỗi enemy nằm trọn trên một dòng.
- Event giả định chỉ chạy một lần; gọi lại sẽ cộng `set_level` lần nữa.
