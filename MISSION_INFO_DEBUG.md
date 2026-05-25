# Mission Info - Debug Guide

## Các Fix Đã Áp Dụng

### 1. **Khởi tạo Animation Variables** (`ui_view.py` dòng 63-68)
```python
self._mission_pulse_start = 0
self._mission_pulse_duration = 400
self._mission_glow_start = 0
self._mission_glow_duration = 600
```
**Lý do**: Các biến này được sử dụng trong vẽ animation nhưng chưa được khởi tạo → AttributeError.

### 2. **Thêm `notify_mission_change()` Method** (`ui_view.py` dòng 72-76)
```python
def notify_mission_change(self):
    """Trigger pulse and glow animations when mission state changes."""
    self._mission_pulse_start = engine.get_time()
    self._mission_glow_start = engine.get_time()
```
**Lý do**: Phương thức được tham chiếu nhưng không được implement.

### 3. **Gọi `notify_mission_change()` khi SetLevelVar** (`action.py` dòng 593-597)
```python
# Notify mission info changes for animations
if self.nid.startswith('mission_'):
    if hasattr(game, 'ui_view'):
        game.ui_view.notify_mission_change()
```
**Lý do**: Kích hoạt animation khi mission variables thay đổi.

### 4. **Xóa Điều Kiện State Chặt Chẽ** (`ui_view.py` dòng 140)
```python
# TRƯỚC:
if game.state.current() in self.legal_states and cf.SETTINGS.get('show_mission', 1) and mission_info is not None:

# SAU:
if cf.SETTINGS.get('show_mission', 1) and mission_info is not None:
```
**Lý do**: Mission box nên hiển thị ở mọi state (dialog, enemy phase, etc.), không chỉ `'free'`, `'prep_formation'`, `'prep_formation_select'`.

## Checklist - Mission Info Không Hiển Thị

Nếu mission info vẫn không hiển thị, hãy kiểm tra:

### 1. **Level Vars Đã Được Set Chưa?**
```python
# Debug: thêm vào console
print(f"[v0] game.level_vars: {game.level_vars}")
print(f"[v0] show_mission: {game.level_vars.get('show_mission')}")
print(f"[v0] mission_count: {game.level_vars.get('mission_count')}")
```

**Điều kiện cần:**
- `game.level_vars['show_mission']` phải là `True` hoặc truthy value
- `game.level_vars['mission_count']` phải > 0, HOẶC có legacy `mission_status1`, `mission_status2`, etc.

### 2. **`cf.SETTINGS['show_mission']` Đã Được Set Chưa?**
```python
print(f"[v0] cf.SETTINGS.get('show_mission'): {cf.SETTINGS.get('show_mission', 'NOT SET')}")
```
**Lưu ý**: Mặc định là `1` (True), nhưng nếu nó là `0` hoặc `False` thì mission info sẽ không hiển thị.

### 3. **`_get_mission_info()` Có Trả Về Data Không?**
Thêm debug ở `ui_view.py` dòng 139:
```python
mission_info = self._get_mission_info()
print(f"[v0] mission_info result: {mission_info}")
```

**Kết quả mong đợi**: `{'done': X, 'total': Y, 'title': Z}` (không phải `None`)

### 4. **Mission Info Disp Có Được Set Không?**
Thêm debug ở dòng 141:
```python
self.mission_info_disp = self.create_mission_info(mission_info)
print(f"[v0] mission_info_disp created: {self.mission_info_disp}")
```

### 5. **Mission Info Có Được Vẽ Không?**
Tìm nơi mission_info_disp được draw/render. Hãy kiểm tra xem có bug trong:
- `create_mission_info()` method (dòng 468+)
- Draw/render logic ở đâu đó

## Data Model - Mission Variables

```
game.level_vars['show_mission']           → bool, hiển thị mission box không
game.level_vars['mission_count']          → int, tổng số mission
game.level_vars['mission_1_state']        → str, 'inactive' | 'active' | 'done' | 'failed' | 'claimed'
game.level_vars['mission_1_title']        → str (tuỳ chọn), hiển thị tên mission
game.level_vars['mission_2_state']        → ...
game.level_vars['mission_2_title']        → ...
...
```

**Legacy Format** (backward compatibility):
```
game.level_vars['mission_status1']        → str, 'green' (done) hoặc 'red' (active)
game.level_vars['mission_status2']        → ...
```

## Nếu Vẫn Không Hoạt Động

1. Kiểm tra xem có `TypeError` hoặc `AttributeError` không
2. Xem console logs tìm exception
3. Thêm `console.log("[v0] ...")` ở:
   - `_get_mission_info()` return statement
   - `create_mission_info()` method
   - Draw/render code
