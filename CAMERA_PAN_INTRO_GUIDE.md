# Camera Pan Intro Guide

## Overview

Bạn đã có **event command mới `pan_camera_loop`** để tạo camera pan giống Fire Emblem 5!

## Cài đặt

Command đã được thêm vào `event_commands.py` và handler đã thêm vào `event_functions.py`.

## Cách sử dụng

### Trong Event Script (Event Format)

```event
# Sau event intro xong, thêm dòng này
pan_camera_loop;60
```

Hoặc nếu muốn continue event trong lúc camera pan:

```event
pan_camera_loop;60;no_block
# Event tiếp tục chạy ngay mà không chờ camera
```

### Trong Python Event Script (#pyev1)

```python
#pyev1
$pan_camera_loop 60
```

Hoặc non-blocking:

```python
#pyev1
$pan_camera_loop 60 "no_block"
```

## Tham số

| Tham số | Loại | Mặc định | Mô tả |
|---------|------|---------|-------|
| `Speed` | Integer | 60 | Tốc độ camera pan. Giá trị cao = chuyển động nhanh hơn |
| `Waypoints` | Optional List | None | Danh sách (x, y) coordinates để camera ghé qua. Nếu None, sử dụng pattern 4 góc mặc định |
| `no_block` | Flag | - | Khi set, event tiếp tục chạy trong lúc camera pan |

## Hành vi mặc định

Nếu không specify waypoints, camera sẽ:

1. **Pan tới góc trên-trái** (2, 2)
2. **Pan tới góc trên-phải** (width-3, 2)
3. **Pan tới góc dưới-phải** (width-3, height-3)
4. **Pan tới góc dưới-trái** (2, height-3)
5. **Pan trở về tâm map** (width/2, height/2)

Margin 2 tile được thêm vào để tránh viewport quá cực đoan.

## Ví dụ

### Ví dụ 1: Map Intro đơn giản (Fire Emblem 5 style)

```event
# Map start event
play_music;Map_Theme;400
say;Narrator;Welcome to the battlefield!
pan_camera_loop;60
# Map hiển thị cho player điều khiển
```

### Ví dụ 2: Với dialog khi camera pan

```event
play_music;Map_Theme;400
say;Narrator;The enemy is approaching from all sides!
pan_camera_loop;80;no_block
say;Commander;We must be strategic...
# Dialog xuất hiện khi camera đang pan
```

### Ví dụ 3: Custom waypoints (Python event)

```python
#pyev1
import math

# Define custom circular path around map
map_w = game.tilemap.width
map_h = game.tilemap.height

custom_waypoints = [
    (3, 3),
    (map_w - 4, 3),
    (map_w - 4, map_h - 4),
    (3, map_h - 4),
    (map_w // 2, map_h // 2)
]

$pan_camera_loop 75 custom_waypoints
```

## Tốc độ Tham khảo

- `Speed: 40` - Rất chậm, khoảng 3 giây cho góc này sang góc khác
- `Speed: 60` - Trung bình (được khuyến khích)
- `Speed: 80` - Nhanh
- `Speed: 120` - Rất nhanh

## Troubleshooting

### Camera không pan
- Đảm bảo command nằm sau `play_music` hoặc `show_map`
- Kiểm tra tên event và map đã tồn tại

### Camera bị stuck tại corner
- Nếu map quá nhỏ (< 5x5), hãy giảm margin hoặc set custom waypoints

### Event không wait cho camera xong
- Đảm bảo không set `no_block` flag nếu bạn muốn chờ

## Sửa đổi

Nếu bạn muốn thay đổi hành vi mặc định (ví dụ: thêm rotation thêm lần, thay đổi margin):

1. Mở `app/events/event_functions.py`
2. Tìm hàm `pan_camera_loop`
3. Sửa logic tính `waypoints`

Ví dụ: Để thêm một vòng xoắn ở giữa:

```python
waypoints = [
    (margin_x, margin_y),
    (map_width - 1 - margin_x, margin_y),
    (map_width - 1 - margin_x, map_height - 1 - margin_y),
    (margin_x, map_height - 1 - margin_y),
    (map_width // 2, map_height // 2),  # Center
    (map_width // 4, map_height // 4),  # Extra waypoint
]
```

---

**Enjoy your Fire Emblem-style camera intros!** 🎮
