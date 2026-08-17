# Kế hoạch triển khai: Mystic Boost vô hiệu hóa cơ chế Staff Family

## Điều phối thực thi

- Executor: `gpt-5.6-terra`, reasoning effort `high`.
- Chỉ triển khai sau khi người dùng yêu cầu thực hiện.
- Không commit nếu chưa được yêu cầu.
- Worktree hiện có thay đổi từ các skill khác; chỉ sửa đúng các file nêu trong kế hoạch và không hoàn tác thay đổi ngoài phạm vi.
- Không sửa trực tiếp các file sinh tự động `app/engine/skill_system.py` hoặc `app/engine/item_system.py`.

## Mục tiêu

Mystic Boost T1/T2/T3 phải vô hiệu đúng hai cơ chế do skill của Foe cấp:

1. Dazzling Staff: phần `Foe cannot counterattack`.
2. Wrathful Staff: phần dùng `min(DEF, RES)` để tính phòng thủ.

Mystic Boost không được tắt toàn bộ Staff skill, không được xóa bonus damage/debuff/follow-up control của Wrathful T4, và không được biến Spell hoặc Siege Weapon vốn không thể bị phản công thành có thể bị phản công. Hồi HP sau combat vẫn lần lượt là 5/6/7.

## Hiện trạng đã xác nhận

- Mystic Boost đã có `negate_cannot_be_countered` và `post_combat_healing`, nhưng chưa có xử lý cho `WORSE_DEFENSE`.
- Dazzling Staff cấp `cannot_be_countered` thông qua `item_override: Cannot_Be_Countered_Override`.
- Wrathful Staff cấp `alternate_resist_formula: WORSE_DEFENSE` thông qua `item_override: WorseDefense_Weapons`.
- `combat_calcs.can_counterattack()` hiện cho `negate_cannot_be_countered` bỏ qua toàn bộ kết quả `item_system.can_be_countered()`. Vì vậy nó cũng có thể bỏ qua hạn chế gốc của Spell/Siege Weapon; đây là phạm vi quá rộng cần sửa.
- Công thức project hiện tại là `DEFENSE = DEF`, `MAGIC_DEFENSE = RES`, `WORSE_DEFENSE = min(DEF, RES)`.
- `dynamic_resist` của defender được dùng trong cả forecast và combat damage, nên có thể bù chính xác chênh lệch công thức mà không cần status/event.

## Quyết định kiến trúc

### 1. Dazzling: phân biệt component của item và component do skill override

Thêm helper nội bộ trong `app/engine/combat_calcs.py`, ví dụ `_can_be_countered_sources(unit, item)`, trả về hai kết quả:

- `base_allowed`: tổng hợp các component `can_be_countered` nằm trực tiếp trên `item.components`. Nếu không có component định nghĩa hook thì giữ semantics mặc định hiện tại là không được phản công.
- `skill_allowed`: tổng hợp các component `can_be_countered` lấy từ `skill_system.item_override(unit, item)`. Nếu không có override định nghĩa hook thì mặc định là `True`.

`can_counterattack()` xử lý theo thứ tự:

```text
không có/không dùng được vũ khí phòng thủ -> False
base_allowed == False                   -> False
skill_allowed == False và defender không có negate_cannot_be_countered -> False
các điều kiện can_counter/range/LOS hiện có -> giữ nguyên
```

Kết quả mong muốn:

- Weapon + Dazzling override + không có Mystic: không phản công.
- Weapon + Dazzling override + có Mystic: được phản công nếu range/các điều kiện khác hợp lệ.
- Spell/Siege/intrinsic cannot-be-countered + Mystic: vẫn không phản công.

Không thay đổi public hook `negate_cannot_be_countered`; chỉ thu hẹp nơi hook được phép bỏ qua.

### 2. Wrathful: marker nguồn và bù phần phòng thủ bị hạ

Thêm hai project custom components trong `custom_skill_components.py`:

#### `lower_def_res_source`

- Marker không tự tạo effect.
- Gắn vào năm skill cha: Wrathful T1, T2, T3, T4_1 và T4_2.
- Không gắn vào các effect/status con, vì nguồn đổi công thức nằm trên skill cha.

#### `neutralize_lower_def_res`

- Gắn vào Mystic Boost T1/T2/T3.
- Cài bằng `dynamic_resist` để hoạt động trong forecast lẫn combat thật.
- Chỉ component Mystic có `priority` cao nhất trên unit được trả giá trị; các bản sao còn lại trả `0` để không cộng bù nhiều lần.

Luồng `dynamic_resist(unit, item, target, item2, ...)`:

1. Nếu thiếu Foe/vũ khí Foe thì trả `0`.
2. Tìm một skill đang hoạt động trên Foe có component `lower_def_res_source`; dùng `skill_system.condition(skill, target, item2)` để tôn trọng `combat_condition` của Wrathful T1/T2.
3. Dùng cùng `resolve_defensive_formula` với combat calculator để xác nhận công thức thực tế đang được chọn là `WORSE_DEFENSE`. Nếu một formula override ưu tiên cao hơn đã thắng, trả `0`, tránh bù sai.
4. Xác định loại đòn bằng `item_funcs.is_magic(target, item2)`.
5. Tính bằng equation parser:

```text
normal = MAGIC_DEFENSE nếu magic, ngược lại DEFENSE
worse  = WORSE_DEFENSE
bonus  = max(0, normal - worse)
```

6. Trả `bonus` qua `dynamic_resist`.

Cách này chỉ triệt tiêu lợi thế đánh vào chỉ số thấp hơn. Mọi component khác của Wrathful T4 (`dynamic_damage`, status/debuff, speed modifier, `no_dynamic_attacks`) vẫn chạy.

### 3. Không dùng `negated_by_skills`

Không gắn `negated_by_skills` lên toàn bộ Wrathful/Dazzling vì component đó làm toàn bộ skill mất điều kiện. Với T4, cách này sẽ vô hiệu cả effect ngoài phạm vi Mystic Boost.

## Dependency graph

```text
Khóa semantics bằng test
    |
    +-- Source-aware can_be_countered
    |       |
    |       +-- Dazzling regression pass
    |
    +-- Marker lower_def_res_source
            |
            +-- neutralize_lower_def_res.dynamic_resist
                    |
                    +-- Migrate 5 Wrathful + 3 Mystic records
                            |
                            +-- Focused regression + static validation
```

## Task 1: Thu hẹp Dazzling neutralization theo nguồn

**Mô tả:** Viết test RED cho sự khác biệt giữa hạn chế gốc của item và `cannot_be_countered` do skill override, sau đó sửa `can_counterattack()` bằng helper phân nguồn.

**Trình tự TDD:**

1. Thêm test Weapon + Dazzling override không có Mystic trả `False`.
2. Thêm test cùng trường hợp nhưng defender có `negate_cannot_be_countered` trả `True`.
3. Thêm test Spell và Siege vẫn trả `False` khi defender có Mystic.
4. Chạy test để xác nhận ít nhất test Spell/Siege RED với code hiện tại.
5. Cài helper phân nguồn và thay đúng nhánh đầu trong `can_counterattack()`.
6. Chạy lại test tới GREEN.

**Tiêu chí chấp nhận:**

- [ ] Mystic chỉ bỏ qua `cannot_be_countered` đến từ `skill_system.item_override`.
- [ ] Hạn chế trực tiếp trên Spell, Siege hoặc item thật luôn được giữ.
- [ ] Logic availability, defender `can_counter`, range, distant/close counter và LOS không đổi.

**Xác minh:**

- [ ] `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_mystic_boost -v`
- [ ] `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_combat_calcs -v`

**Phụ thuộc:** Không có.

**Files dự kiến:**

- `app/engine/combat_calcs.py`
- `app/tests/test_mystic_boost.py`

**Quy mô:** S.

## Checkpoint A: Dazzling

- [ ] Ba nhánh Weapon/Dazzling, Spell và Siege được khóa bằng test.
- [ ] Không sửa generated item/skill system.
- [ ] Diff `combat_calcs.py` chỉ chứa helper phân nguồn và nhánh sử dụng helper.

## Task 2: Tạo cơ chế trung hòa `WORSE_DEFENSE`

**Mô tả:** Viết test RED rồi thêm marker và neutralizer trong project custom components. Test trực tiếp custom component bằng mock unit/item/skill, cùng cách load module đang dùng ở các test skill hiện tại.

**Trình tự TDD:**

1. Test physical: DEF > RES, Wrathful active; kết quả bù bằng `DEF - min(DEF, RES)`.
2. Test magic: RES > DEF; kết quả bù bằng `RES - min(DEF, RES)`.
3. Test Foe không có marker hoặc Wrathful condition không đạt: trả `0`.
4. Test công thức thực tế không phải `WORSE_DEFENSE`: trả `0`.
5. Test hai Mystic cùng tồn tại: chỉ priority cao nhất trả bonus.
6. Chạy RED, sau đó thêm `LowerDefResSource`, helper tìm source đang active và `NeutralizeLowerDefRes`.
7. Chạy lại tới GREEN.

**Tiêu chí chấp nhận:**

- [ ] Physical trở về DEF; magic trở về RES.
- [ ] Không bù khi Wrathful không active hoặc công thức khác đang thắng.
- [ ] Không tạo status, event hoặc state cần cleanup sau combat.
- [ ] Nhiều Mystic không cộng bù lặp.

**Xác minh:**

- [ ] `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_mystic_boost -v`
- [ ] `utilities\enemy_event_generator\.python\python.exe -m py_compile "Fire Emblem Tales of The Golden Knight.ltproj/resources/custom_components/custom_skill_components.py" app/tests/test_mystic_boost.py`

**Phụ thuộc:** Không phụ thuộc Task 1 về code, nhưng phải hoàn thành sau Checkpoint A để review từng lát nhỏ.

**Files dự kiến:**

- `Fire Emblem Tales of The Golden Knight.ltproj/resources/custom_components/custom_skill_components.py`
- `app/tests/test_mystic_boost.py`

**Quy mô:** S.

## Task 3: Migrate dữ liệu Wrathful và Mystic Boost

**Mô tả:** Gắn marker vào đúng năm Wrathful parent skills và neutralizer vào ba Mystic Boost tiers. Giữ nguyên toàn bộ component còn lại và thêm assertion dữ liệu vào test.

**Mapping bắt buộc:**

```text
Wrathfull_Staff_T1     -> lower_def_res_source
Wrathfull_Staff_T2     -> lower_def_res_source
Wrathfull_Staff_T3     -> lower_def_res_source
Wrathfull_Staff_T4_1   -> lower_def_res_source
Wrathfull_Staff_T4_2   -> lower_def_res_source

Mystic_Boost_T1        -> neutralize_lower_def_res + post_combat_healing 5
Mystic_Boost_T2        -> neutralize_lower_def_res + post_combat_healing 6
Mystic_Boost_T3        -> neutralize_lower_def_res + post_combat_healing 7
```

Mỗi Mystic vẫn giữ `negate_cannot_be_countered`. Không thêm marker vào `Wrathfull_Staff_T4_*_Effect` hay `Dazzling_Staff_T4_2_Effect`.

**Tiêu chí chấp nhận:**

- [ ] Đúng 5 Wrathful parent records có một marker.
- [ ] Đúng 3 Mystic records có một neutralizer và vẫn có `negate_cannot_be_countered`.
- [ ] Healing 5/6/7, priority 0/1/2 và mọi T4 effect cũ không đổi.

**Xác minh:**

- [ ] Test parse JSON và assertion chính xác mapping/component counts.
- [ ] `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_mystic_boost -v`

**Phụ thuộc:** Task 2.

**Files dự kiến:**

- `Fire Emblem Tales of The Golden Knight.ltproj/game_data/skills.json`
- `app/tests/test_mystic_boost.py`

**Quy mô:** S.

## Checkpoint B: Effect hoàn chỉnh

- [ ] Dazzling chỉ mất phần khóa counter.
- [ ] Wrathful chỉ mất phần `WORSE_DEFENSE`.
- [ ] Wrathful T4 bonus damage/debuff/follow-up control vẫn được test là còn hoạt động hoặc ít nhất còn nguyên component dữ liệu.
- [ ] Forecast/direct calculation và combat hook dùng cùng result.

## Task 4: Regression, review và bàn giao

**Mô tả:** Chạy validation theo lớp, review focused diff và ghi đúng giới hạn bằng chứng. Không sửa lỗi ngoài phạm vi Mystic Boost trong task này.

**Xác minh theo thứ tự:**

1. Focused Mystic:
   `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_mystic_boost -v`
2. Combat regressions:
   `utilities\enemy_event_generator\.python\python.exe -m unittest app.tests.test_combat_calcs app.tests.test_cancel_affinity app.tests.test_lull_family -v`
3. Static:
   - `py_compile` custom component và test mới.
   - PowerShell `ConvertFrom-Json` cho `skills.json`.
   - `git diff --check`.
4. Full suite:
   `utilities\enemy_event_generator\.python\python.exe -m unittest discover -s app/tests -p 'test*.py'`

Full suite từng gặp native exit `-1073740791`; nếu tái diễn, phải báo chính xác là full suite chưa PASS, lưu tail log, và chỉ dựa vào focused results đã hoàn tất. Không được quy lỗi native cho Mystic Boost nếu chưa có bằng chứng.

**Tiêu chí chấp nhận:**

- [ ] Focused Mystic và combat regressions PASS.
- [ ] JSON, syntax và whitespace validation PASS.
- [ ] Focused diff không có generated-file edit, debug output hay refactor ngoài phạm vi.
- [ ] Báo cáo nêu rõ files đổi, test counts, full-suite status và giới hạn chưa gameplay-test.

**Phụ thuộc:** Tasks 1-3.

**Files dự kiến:** Không thêm file ngoài các file đã liệt kê; chỉ sửa nếu focused test chứng minh lỗi trong phạm vi.

**Quy mô:** XS.

## Rủi ro và cách chặn

| Rủi ro | Mức | Cách chặn |
|---|---:|---|
| Mystic làm Spell/Siege bị phản công | Cao | Tách base item và skill override; test riêng hai loại item |
| Tắt toàn bộ Wrathful T4 | Cao | Marker + dynamic resist, không dùng `negated_by_skills` |
| Bù DEF/RES dù `WORSE_DEFENSE` không được chọn | Cao | Xác nhận resolved formula trước khi trả bonus |
| Wrathful T1/T2 không đủ HP vẫn bị xử lý | Trung bình | Kiểm tra `skill_system.condition` sau pre-combat |
| Nhiều Mystic cộng bonus nhiều lần | Trung bình | Chỉ priority/UID cao nhất trả bonus |
| Ghi đè dirty work hiện có | Cao | Focused diff trước/sau, không reset/checkout file |
| Full suite native crash | Trung bình | Chạy focused trước; ghi rõ trạng thái và exit code |

## Điều kiện dừng cho Terra High

Terra High phải dừng và báo người dùng trước khi mở rộng phạm vi nếu gặp một trong các trường hợp:

- Muốn sửa generated `skill_system.py`/`item_system.py` hoặc thay đổi public hook contract.
- Cần event/status/helper skill để effect hoạt động.
- Không thể phân biệt component gốc của item với `item_override` bằng dữ liệu hiện tại.
- `dynamic_resist` không chạy giống nhau giữa forecast và combat thật.
- T4 effect phải bị tắt toàn bộ mới làm test pass.
- Focused test cho thấy lỗi nằm ở subsystem khác ngoài bốn file dự kiến.

## Definition of Done

- [ ] Tất cả acceptance criteria từng task đạt.
- [ ] Test mới thực sự RED trước implementation và GREEN sau implementation.
- [ ] Focused regression PASS; full-suite status được báo trung thực.
- [ ] Không có thay đổi ngoài phạm vi, generated-file edit hoặc commit không được phép.
- [ ] Người dùng review kết quả trước khi merge/deploy/gameplay release.

