# Mission Info Display Bug - Analysis & Fix

## 📋 Problem Summary
Mission info box không hiển thị ngay cả khi `show_mission` đã được set thành `True`.

## 🔍 Root Causes

### 1. **Uninitialized Animation Variables** (PRIMARY BUG)
**File:** `app/engine/ui_view.py`  
**Lines:** 253-265

The following instance variables were used but **never initialized** in `__init__`:
- `_mission_pulse_start`
- `_mission_pulse_duration`
- `_mission_glow_start`
- `_mission_glow_duration`

**Result:** When mission info tries to render (line 250-277), it causes `AttributeError` because these variables don't exist:
```python
elapsed = engine.get_time() - self._mission_pulse_start  # ← AttributeError!
```

### 2. **Missing Animation Trigger Method**
**File:** `app/engine/ui_view.py`  
**Line:** 125 (in comments)

The code references `notify_mission_change()` method in comments, but this method doesn't exist:
```python
# are pushed instantly from action.SetLevelVar via notify_mission_change(),
```

This method should trigger pulse and glow animations when mission state changes.

### 3. **State-Based Display Restriction** (SECONDARY)
**File:** `app/engine/ui_view.py`  
**Line:** 129

Mission info only displays when game state is one of:
- `'free'`
- `'prep_formation'`
- `'prep_formation_select'`

If you're in other states (menu, dialog, enemy_phase, etc.), mission info won't show regardless of `show_mission` setting.

## ✅ Solution Implemented

### Fix 1: Initialize Animation Variables
Added initialization in `__init__()`:
```python
# Mission pulse and glow animation timing
self._mission_pulse_start = 0
self._mission_pulse_duration = 400  # milliseconds
self._mission_glow_start = 0
self._mission_glow_duration = 600  # milliseconds
```

### Fix 2: Implement notify_mission_change() Method
Added method to trigger animations:
```python
def notify_mission_change(self):
    """Trigger pulse and glow animations when mission state changes."""
    self._mission_pulse_start = engine.get_time()
    self._mission_glow_start = engine.get_time()
```

## 🧪 How to Test

1. In your event, set mission variables:
```
level_var.show_mission = 1
level_var.mission_count = 3
level_var.mission_1_state = "active"
level_var.mission_1_title = "Defeat all enemies"
level_var.mission_2_state = "inactive"
level_var.mission_3_state = "inactive"
```

2. Ensure you're in a valid game state:
   - Free movement on map
   - Prep formation screen
   - Prep formation selection screen

3. Mission info box should appear in top-left corner with:
   - A blue gem icon
   - "Missions 0/3" text
   - Smooth slide-in animation

4. When mission state changes, call:
```python
game.ui_view.notify_mission_change()
```
This triggers the pulse and glow animations.

## 📝 Additional Notes

- Mission info uses same styling as objective box
- Box slides in from left when conditions are met
- Disappears when cursor is in top-left or unit/tile info occupies that space
- Pulse animation: 400ms vertical bob
- Glow animation: 600ms yellow outline with pulsing alpha

## Files Modified
- `app/engine/ui_view.py` - Added variable initialization and method implementation
