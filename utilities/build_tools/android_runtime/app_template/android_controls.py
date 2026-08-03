from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path


class AndroidTouchControls:
    """Translate Android multi-touch into LT keys and draw editable controls."""

    BUTTONS = (
        "UP",
        "DOWN",
        "LEFT",
        "RIGHT",
        "SELECT",
        "BACK",
        "INFO",
        "AUX",
        "START",
        "FAST_FORWARD",
    )
    BUTTON_LABELS = {
        "UP": "UP",
        "DOWN": "DN",
        "LEFT": "LT",
        "RIGHT": "RT",
        "SELECT": "A",
        "BACK": "B",
        "INFO": "X",
        "AUX": "Y",
        "START": "START",
        "FAST_FORWARD": ">>",
    }
    DIRECTION_BUTTONS = ("UP", "DOWN", "LEFT", "RIGHT")
    ACTION_BUTTONS = ("SELECT", "BACK", "INFO", "AUX", "FAST_FORWARD")
    DPAD_STYLES = ("separate", "cross", "round")
    DEFAULT_DPAD_STYLE = "cross"
    DEFAULT_SCALE = 1.0
    MIN_SCALE = 0.70
    MAX_SCALE = 1.60
    SCALE_STEP = 0.10
    DEFAULT_POSITIONS = {
        "UP": (0.17, 0.55),
        "DOWN": (0.17, 0.85),
        "LEFT": (0.07, 0.70),
        "RIGHT": (0.27, 0.70),
        "SELECT": (0.89, 0.66),
        "BACK": (0.78, 0.82),
        "INFO": (0.78, 0.51),
        "AUX": (0.89, 0.36),
        "START": (0.525, 0.93),
        "FAST_FORWARD": (0.90, 0.16),
    }
    DEFAULT_OPACITY = 105
    MIN_OPACITY = 40
    MAX_OPACITY = 255
    OPACITY_STEP = 13

    def __init__(
        self,
        pygame_module,
        key_map: dict[str, int],
        preferences_path: str | Path | None = None,
        touch_module=None,
    ) -> None:
        self.pygame = pygame_module
        self.key_map = key_map
        self.preferences_path = (
            Path(preferences_path) if preferences_path is not None else None
        )
        self.touch_module = touch_module
        self.positions = dict(self.DEFAULT_POSITIONS)
        self.opacity = self.DEFAULT_OPACITY
        self.scales = {button: self.DEFAULT_SCALE for button in self.BUTTONS}
        self.dpad_style = self.DEFAULT_DPAD_STYLE
        self.dpad_center = self._default_dpad_center()
        self.dpad_scale = self.DEFAULT_SCALE

        self.live_fingers: set[tuple[int, int]] = set()
        self.finger_positions: dict[tuple[int, int], tuple[float, float]] = {}
        self.finger_order: dict[tuple[int, int], int] = {}
        self._finger_sequence = 0
        self.finger_buttons: dict[tuple[int, int], tuple[str, ...]] = {}
        self.button_fingers: dict[str, set[tuple[int, int]]] = defaultdict(set)
        self.active_buttons: set[str] = set()
        self.suppressed_fingers: set[tuple[int, int]] = set()
        self.ui_fingers: set[tuple[int, int]] = set()

        self.edit_mode = False
        self.toolbar_visible = True
        self.dragging_fingers: dict[tuple[int, int], str] = {}
        self.selected_control = "DPAD"
        self._editor_snapshot: dict | None = None
        self._editor_result: str | None = None
        self._release_requested = False
        self._font_cache: dict[int, object] = {}
        self._overlay_surface = None
        self._overlay_size: tuple[int, int] | None = None
        self._overlay_state = None
        self._overlay_blit_regions: list[tuple[int, int, int, int]] = []
        self._overlay_region_surfaces: list[tuple[object, tuple[int, int]]] = []
        self._load_preferences()

    @classmethod
    def _default_dpad_center(cls) -> tuple[float, float]:
        return (
            sum(cls.DEFAULT_POSITIONS[button][0] for button in cls.DIRECTION_BUTTONS)
            / len(cls.DIRECTION_BUTTONS),
            sum(cls.DEFAULT_POSITIONS[button][1] for button in cls.DIRECTION_BUTTONS)
            / len(cls.DIRECTION_BUTTONS),
        )

    def _load_preferences(self) -> None:
        if self.preferences_path is None or not self.preferences_path.is_file():
            return
        try:
            payload = json.loads(
                self.preferences_path.read_text(encoding="utf-8")
            )
            opacity = int(payload.get("opacity", self.DEFAULT_OPACITY))
            self.opacity = self._clamp_opacity(opacity)
            stored_positions = payload.get("positions", {})
            if isinstance(stored_positions, dict):
                for button in self.BUTTONS:
                    position = stored_positions.get(button)
                    if (
                        isinstance(position, list)
                        and len(position) == 2
                        and all(isinstance(value, (int, float)) for value in position)
                    ):
                        self.positions[button] = (
                            self._clamp_normalized(float(position[0])),
                            self._clamp_normalized(float(position[1])),
                        )
            schema_version = int(payload.get("schema_version", 2))
            if schema_version >= 3:
                dpad_style = payload.get("dpad_style", self.DEFAULT_DPAD_STYLE)
                if dpad_style in self.DPAD_STYLES:
                    self.dpad_style = dpad_style
                dpad = payload.get("dpad", {})
                if isinstance(dpad, dict):
                    center = dpad.get("center")
                    if (
                        isinstance(center, list)
                        and len(center) == 2
                        and all(isinstance(value, (int, float)) for value in center)
                    ):
                        self.dpad_center = (
                            self._clamp_normalized(float(center[0])),
                            self._clamp_normalized(float(center[1])),
                        )
                    self.dpad_scale = self._clamp_scale(
                        dpad.get("scale", self.DEFAULT_SCALE)
                    )
                stored_scales = payload.get("scales", {})
                if isinstance(stored_scales, dict):
                    for button in self.BUTTONS:
                        self.scales[button] = self._clamp_scale(
                            stored_scales.get(button, self.DEFAULT_SCALE)
                        )
            else:
                # Schema 2 had four independent direction controls. Keep that
                # established muscle-memory layout on upgrade instead of
                # silently replacing it with a D-pad.
                self.dpad_style = "separate"
                self.dpad_center = self._direction_centroid()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"LT_ANDROID_CONTROLS ignored invalid preferences: {exc}",
                flush=True,
            )

    def _save_preferences(self) -> None:
        if self.preferences_path is None:
            return
        try:
            self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 3,
                "opacity": self.opacity,
                "positions": {
                    button: list(self.positions[button])
                    for button in self.BUTTONS
                },
                "scales": {
                    button: self.scales[button]
                    for button in self.BUTTONS
                },
                "dpad_style": self.dpad_style,
                "dpad": {
                    "center": list(self.dpad_center),
                    "scale": self.dpad_scale,
                },
            }
            temporary = self.preferences_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(self.preferences_path)
        except OSError as exc:
            print(
                f"LT_ANDROID_CONTROLS could not save preferences: {exc}",
                flush=True,
            )

    @staticmethod
    def _clamp_normalized(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def _clamp_opacity(cls, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = cls.DEFAULT_OPACITY
        return max(cls.MIN_OPACITY, min(cls.MAX_OPACITY, parsed))

    @classmethod
    def _clamp_scale(cls, value: object) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = cls.DEFAULT_SCALE
        return max(cls.MIN_SCALE, min(cls.MAX_SCALE, parsed))

    def _direction_centroid(self) -> tuple[float, float]:
        return (
            sum(self.positions[button][0] for button in self.DIRECTION_BUTTONS)
            / len(self.DIRECTION_BUTTONS),
            sum(self.positions[button][1] for button in self.DIRECTION_BUTTONS)
            / len(self.DIRECTION_BUTTONS),
        )

    def _layout(self, size: tuple[int, int]) -> dict[str, tuple]:
        """Build the one geometry source used by draw, hit-test and dragging."""
        width, height = size
        unit = min(width, height)
        direction_size = max(14, int(unit * 0.145))
        action_radius = max(11, int(unit * 0.10))
        start_width = max(30, int(width * 0.15))
        start_height = max(14, int(height * 0.10))
        layout: dict[str, tuple] = {"_direction_size": (direction_size,)}
        if self.dpad_style == "separate":
            for button in self.DIRECTION_BUTTONS:
                px, py = self.positions[button]
                layout[button] = (
                    int(px * width),
                    int(py * height),
                    max(14, int(direction_size * self.scales[button])),
                )
        else:
            center_x = int(self.dpad_center[0] * width)
            center_y = int(self.dpad_center[1] * height)
            layout["DPAD"] = (
                center_x,
                center_y,
                max(18, int(direction_size * 1.55 * self.dpad_scale)),
            )
        for button in self.ACTION_BUTTONS:
            px, py = self.positions[button]
            layout[button] = (
                int(px * width),
                int(py * height),
                max(11, int(action_radius * self.scales[button])),
            )
        start_x, start_y = self.positions["START"]
        center_x = int(start_x * width)
        center_y = int(start_y * height)
        start_scale = self.scales["START"]
        scaled_width = max(30, int(start_width * start_scale))
        scaled_height = max(14, int(start_height * start_scale))
        layout["START"] = (
            center_x - scaled_width // 2,
            center_y - scaled_height // 2,
            center_x + scaled_width // 2,
            center_y + scaled_height // 2,
        )
        return layout

    @staticmethod
    def _contains(
        rect: tuple[int, int, int, int],
        x: int,
        y: int,
    ) -> bool:
        left, top, right, bottom = rect
        return left <= x <= right and top <= y <= bottom

    def _toolbar_layout(self, size: tuple[int, int]) -> dict[str, tuple[int, int, int, int]]:
        width, _ = size
        if not self.toolbar_visible:
            show_width = 52 if width >= 330 else 30
            left = (width - show_width) // 2
            return {"SHOW": (left, 3, left + show_width, 20)}

        # A single centered ruler keeps the editing tools together instead of
        # covering two rows of the screen. The compact form still fits a
        # 240px canvas used by non-wide Android devices and tests.
        compact = width < 330
        item_widths = (
            ("HIDE", 18 if compact else 32),
            ("STYLE", 28 if compact else 48),
            ("OPACITY_DOWN", 18 if compact else 22),
            ("OPACITY_UP", 18 if compact else 22),
            ("SIZE_DOWN", 18 if compact else 22),
            ("SIZE_UP", 18 if compact else 22),
            ("RESET", 24 if compact else 40),
            ("CANCEL", 18 if compact else 48),
            ("SAVE", 26 if compact else 42),
        )
        gap = 1
        ruler_width = sum(item_width for _, item_width in item_widths)
        ruler_width += gap * (len(item_widths) - 1)
        left = max(2, (width - ruler_width) // 2)
        layout: dict[str, tuple[int, int, int, int]] = {}
        for action, item_width in item_widths:
            layout[action] = (left, 3, left + item_width, 20)
            left += item_width + gap
        return layout

    def _toolbar_hit(self, x: int, y: int, size: tuple[int, int]) -> str | None:
        for action, rect in self._toolbar_layout(size).items():
            if self._contains(rect, x, y):
                return action
        return None

    def _hit_test(
        self,
        x: int,
        y: int,
        size: tuple[int, int],
        previous: str | tuple[str, ...] | None = None,
    ) -> str | tuple[str, ...] | None:
        layout = self._layout(size)
        for button in self.ACTION_BUTTONS:
            cx, cy, radius = layout[button]
            if math.hypot(x - cx, y - cy) <= radius * 1.22:
                return button

        if self._contains(layout["START"], x, y):
            return "START"

        if self.dpad_style == "separate":
            for button in self.DIRECTION_BUTTONS:
                cx, cy, button_size = layout[button]
                reach = button_size * 0.60
                if abs(x - cx) <= reach and abs(y - cy) <= reach:
                    return button
        else:
            cx, cy, radius = layout["DPAD"]
            return self._dpad_direction(x - cx, y - cy, radius, previous)
        return None

    def _dpad_direction(
        self, dx: int, dy: int, radius: int,
        previous: str | tuple[str, ...] | None = None,
    ) -> tuple[str, ...] | None:
        distance = math.hypot(dx, dy)
        if distance > radius:
            return None
        previous_buttons = self._as_buttons(previous)
        dead_zone = radius * (
            0.18 if set(previous_buttons) & set(self.DIRECTION_BUTTONS) else 0.25
        )
        if distance < dead_zone:
            return None
        horizontal = "RIGHT" if dx > 0 else "LEFT"
        vertical = "DOWN" if dy > 0 else "UP"
        # Split the circle into four cardinal and four diagonal sectors.
        # A 2:1 dominant axis retains a generous cardinal target while taps
        # near each corner press both directions on the same frame.
        if abs(dx) >= abs(dy) * 2:
            return (horizontal,)
        if abs(dy) >= abs(dx) * 2:
            return (vertical,)
        return (vertical, horizontal)

    @staticmethod
    def _as_buttons(
        buttons: str | tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        if buttons is None:
            return ()
        if isinstance(buttons, str):
            return (buttons,)
        return tuple(buttons)

    def _key_event(self, event_type: int, button: str):
        return self.pygame.event.Event(
            event_type,
            key=self.key_map[button],
            mod=0,
            unicode="",
        )

    def _change_finger(
        self,
        finger_key: tuple[int, int],
        button: str | tuple[str, ...] | None,
        generated_events: list,
    ) -> None:
        old_buttons = self._as_buttons(self.finger_buttons.get(finger_key))
        new_buttons = self._as_buttons(button)
        if old_buttons == new_buttons:
            return

        for old_button in set(old_buttons) - set(new_buttons):
            old_fingers = self.button_fingers[old_button]
            old_fingers.discard(finger_key)
            if not old_fingers:
                if old_button != "FAST_FORWARD":
                    self.active_buttons.discard(old_button)
                    generated_events.append(
                        self._key_event(self.pygame.KEYUP, old_button)
                    )

        for new_button in new_buttons:
            if new_button in old_buttons:
                continue
            new_fingers = self.button_fingers[new_button]
            if not new_fingers:
                if new_button == "FAST_FORWARD":
                    if new_button in self.active_buttons:
                        self.active_buttons.discard(new_button)
                        generated_events.append(
                            self._key_event(self.pygame.KEYUP, new_button)
                        )
                    else:
                        self.active_buttons.add(new_button)
                        generated_events.append(
                            self._key_event(self.pygame.KEYDOWN, new_button)
                        )
                else:
                    self.active_buttons.add(new_button)
                    generated_events.append(
                        self._key_event(self.pygame.KEYDOWN, new_button)
                    )
            new_fingers.add(finger_key)
        if new_buttons:
            self.finger_buttons[finger_key] = new_buttons
        else:
            self.finger_buttons.pop(finger_key, None)

    def _release_buttons(self, generated_events: list) -> None:
        for button in tuple(self.active_buttons):
            generated_events.append(self._key_event(self.pygame.KEYUP, button))
        self.finger_buttons.clear()
        self.button_fingers.clear()
        self.active_buttons.clear()

    def _release_all(self, generated_events: list) -> None:
        self._release_buttons(generated_events)
        self.live_fingers.clear()
        self.finger_positions.clear()
        self.finger_order.clear()
        self.suppressed_fingers.clear()
        self.ui_fingers.clear()
        self.dragging_fingers.clear()

    @staticmethod
    def _event_finger_key(event) -> tuple[int, int]:
        return (
            int(getattr(event, "touch_id", 0)),
            int(event.finger_id),
        )

    def _remember_finger(
        self,
        finger_key: tuple[int, int],
        x: float,
        y: float,
    ) -> None:
        if finger_key not in self.live_fingers:
            self._finger_sequence += 1
            self.finger_order[finger_key] = self._finger_sequence
        self.live_fingers.add(finger_key)
        self.finger_positions[finger_key] = (
            max(0.0, min(1.0, float(x))),
            max(0.0, min(1.0, float(y))),
        )

    def _forget_finger(self, finger_key: tuple[int, int]) -> None:
        self.live_fingers.discard(finger_key)
        self.finger_positions.pop(finger_key, None)
        self.finger_order.pop(finger_key, None)
        self.suppressed_fingers.discard(finger_key)
        self.ui_fingers.discard(finger_key)
        self.dragging_fingers.pop(finger_key, None)

    @staticmethod
    def _game_position(
        normalized: tuple[float, float], size: tuple[int, int]
    ) -> tuple[int, int] | None:
        """Map a full Android logical-canvas point into LT's game viewport."""
        try:
            from app.constants import WINHEIGHT, WINWIDTH
        except ImportError:
            return None
        width, height = size
        scale = min(width / WINWIDTH, height / WINHEIGHT)
        game_width = int(WINWIDTH * scale)
        game_height = int(WINHEIGHT * scale)
        offset_x = (width - game_width) // 2
        offset_y = (height - game_height) // 2
        raw_x = int(normalized[0] * width)
        raw_y = int(normalized[1] * height)
        if not (offset_x <= raw_x < offset_x + game_width and
                offset_y <= raw_y < offset_y + game_height):
            return None
        return (
            max(0, min(WINWIDTH - 1, int((raw_x - offset_x) / scale))),
            max(0, min(WINHEIGHT - 1, int((raw_y - offset_y) / scale))),
        )

    def _forward_ui_touch(
        self,
        phase: str,
        finger_key: tuple[int, int],
        normalized: tuple[float, float],
        size: tuple[int, int],
    ) -> bool:
        position = self._game_position(normalized, size)
        if position is None:
            return False
        try:
            from app.engine.android_runtime import dispatch_android_touch
            return dispatch_android_touch(phase, position, finger_key)
        except Exception:
            # An optional developer overlay must never break normal controls.
            return False

    @staticmethod
    def _ui_capture_active() -> bool:
        try:
            from app.engine.android_runtime import is_android_touch_consumer_active
            return is_android_touch_consumer_active()
        except Exception:
            return False

    @staticmethod
    def _ui_passthrough_buttons() -> frozenset[str]:
        try:
            from app.engine.android_runtime import \
                get_android_touch_passthrough_buttons
            return get_android_touch_passthrough_buttons()
        except Exception:
            return frozenset()

    def _poll_fingers(self) -> dict[tuple[int, int], tuple[float, float]] | None:
        if self.touch_module is None:
            return None
        try:
            device_count = self.touch_module.get_num_devices()
            if device_count <= 0:
                return None
            fingers: dict[tuple[int, int], tuple[float, float]] = {}
            for device_index in range(device_count):
                touch_id = int(self.touch_module.get_device(device_index))
                finger_count = self.touch_module.get_num_fingers(touch_id)
                for finger_index in range(finger_count):
                    finger = self.touch_module.get_finger(touch_id, finger_index)
                    if finger is None:
                        continue
                    key = (touch_id, int(finger["id"]))
                    fingers[key] = (
                        float(finger["x"]),
                        float(finger["y"]),
                    )
            return fingers
        except Exception:
            # Some SDL/pygame builds expose touch enumeration but raise an
            # implementation-specific exception while the app is resuming.
            # Event-driven input still works when polling is temporarily
            # unavailable, so the controller must not crash the game here.
            return None

    def _apply_polled_fingers(
        self,
        polled: dict[tuple[int, int], tuple[float, float]],
        released_this_frame: set[tuple[int, int]],
        size: tuple[int, int],
    ) -> None:
        polled = {
            key: position
            for key, position in polled.items()
            if key not in released_this_frame
        }
        for finger_key in tuple(self.live_fingers - set(polled)):
            # Some Android devices lose FINGERUP while the keyboard, a system
            # gesture, or a frame hitch is active.  The in-game drawer needs
            # the matching release to avoid keeping a list drag captured.
            if finger_key in self.ui_fingers:
                position = self.finger_positions.get(finger_key)
                if position is not None:
                    self._forward_ui_touch("up", finger_key, position, size)
            self._forget_finger(finger_key)
        for finger_key, position in polled.items():
            previous = self.finger_positions.get(finger_key)
            self._remember_finger(finger_key, *position)
            if finger_key in self.ui_fingers and previous != position:
                # Touch polling is the fallback for devices that intermittently
                # omit FINGERMOTION.  Forward it to the debugger just like the
                # event-driven path above.
                self._forward_ui_touch("move", finger_key, position, size)
                continue
            if self.edit_mode and finger_key in self.dragging_fingers:
                self._move_dragged_button(finger_key, position, size)

    def _desired_buttons(
        self, size: tuple[int, int],
    ) -> dict[tuple[int, int], tuple[str, ...] | None]:
        desired: dict[tuple[int, int], tuple[str, ...] | None] = {}
        for finger_key in self.live_fingers:
            if finger_key in self.suppressed_fingers:
                desired[finger_key] = None
                continue
            normalized = self.finger_positions.get(finger_key)
            if normalized is None:
                desired[finger_key] = None
                continue
            x = max(0, min(size[0] - 1, int(normalized[0] * size[0])))
            y = max(0, min(size[1] - 1, int(normalized[1] * size[1])))
            hit = self._hit_test(x, y, size, self.finger_buttons.get(finger_key))
            desired[finger_key] = self._as_buttons(hit) or None

        if self.dpad_style != "separate":
            # A D-pad is a single directional stick. A second finger on it is
            # ignored until lifted; action buttons remain fully multi-touch.
            dpad_fingers = [
                finger_key for finger_key, button in desired.items()
                if set(self._as_buttons(button)) & set(self.DIRECTION_BUTTONS)
            ]
            if len(dpad_fingers) > 1:
                owner = min(
                    dpad_fingers,
                    key=lambda key: self.finger_order.get(key, float("inf")),
                )
                for finger_key in dpad_fingers:
                    if finger_key != owner:
                        self.suppressed_fingers.add(finger_key)
                        desired[finger_key] = None

        # Opposite directions are never meaningful. If Android leaves an old
        # finger alive, the most recently pressed direction wins the axis.
        # The loser stays suppressed until that physical finger disappears;
        # otherwise it would press itself again as soon as the winner lifts.
        for opposites in ({"UP", "DOWN"}, {"LEFT", "RIGHT"}):
            candidates = [
                finger_key
                for finger_key, button in desired.items()
                if set(self._as_buttons(button)) & opposites
            ]
            directions = {
                direction
                for finger_key in candidates
                for direction in self._as_buttons(desired[finger_key])
                if direction in opposites
            }
            if len(directions) > 1:
                winner = max(
                    candidates,
                    key=lambda key: self.finger_order.get(key, -1),
                )
                winning_direction = next(
                    direction for direction in self._as_buttons(desired[winner])
                    if direction in opposites
                )
                for finger_key in candidates:
                    buttons = self._as_buttons(desired[finger_key])
                    if any(direction in opposites and direction != winning_direction
                           for direction in buttons):
                        filtered = tuple(
                            direction for direction in buttons
                            if direction not in opposites
                            or direction == winning_direction
                        )
                        if filtered:
                            desired[finger_key] = filtered
                        else:
                            self.suppressed_fingers.add(finger_key)
                            desired[finger_key] = None
        return desired

    def _sync_game_buttons(
        self, size: tuple[int, int], generated: list,
        allowed_buttons: frozenset[str] | None = None,
    ) -> None:
        desired = self._desired_buttons(size)
        if allowed_buttons is not None:
            desired = {
                finger_key: tuple(
                    button for button in self._as_buttons(buttons)
                    if button in allowed_buttons
                ) or None
                for finger_key, buttons in desired.items()
            }
        for finger_key in tuple(self.finger_buttons):
            if finger_key not in desired:
                self._change_finger(finger_key, None, generated)
        for finger_key in sorted(
            desired,
            key=lambda key: self.finger_order.get(key, -1),
        ):
            self._change_finger(finger_key, desired[finger_key], generated)

    def _button_half_extents(
        self,
        button: str,
        size: tuple[int, int],
    ) -> tuple[float, float]:
        layout = self._layout(size)
        if button == "DPAD":
            _, _, radius = layout["DPAD"]
            return radius, radius
        if button in self.DIRECTION_BUTTONS:
            _, _, button_size = layout[button]
            return button_size / 2, button_size / 2
        if button in self.ACTION_BUTTONS:
            _, _, radius = layout[button]
            return radius, radius
        left, top, right, bottom = layout["START"]
        return (right - left) / 2, (bottom - top) / 2

    def _set_button_position(
        self,
        button: str,
        normalized: tuple[float, float],
        size: tuple[int, int],
    ) -> None:
        width, height = size
        half_width, half_height = self._button_half_extents(button, size)
        min_x = (half_width + 2) / width
        max_x = 1.0 - min_x
        min_y = (half_height + 2) / height
        max_y = 1.0 - (half_height + 2) / height
        self.positions[button] = (
            max(min_x, min(max_x, normalized[0])),
            max(min_y, min(max_y, normalized[1])),
        )

    def _move_dragged_button(
        self,
        finger_key: tuple[int, int],
        normalized: tuple[float, float],
        size: tuple[int, int],
    ) -> None:
        button = self.dragging_fingers.get(finger_key)
        if button is None:
            return
        if button == "DPAD":
            self._set_dpad_center(normalized, size)
        else:
            self._set_button_position(button, normalized, size)

    def _set_dpad_center(
        self, normalized: tuple[float, float], size: tuple[int, int],
    ) -> None:
        width, height = size
        half_width, half_height = self._button_half_extents("DPAD", size)
        min_x = (half_width + 2) / width
        max_x = 1.0 - min_x
        min_y = (half_height + 2) / height
        max_y = 1.0 - (half_height + 2) / height
        self.dpad_center = (
            max(min_x, min(max_x, normalized[0])),
            max(min_y, min(max_y, normalized[1])),
        )

    def _profile_snapshot(self) -> dict:
        return {
            "opacity": self.opacity,
            "positions": dict(self.positions),
            "scales": dict(self.scales),
            "dpad_style": self.dpad_style,
            "dpad_center": self.dpad_center,
            "dpad_scale": self.dpad_scale,
        }

    def _restore_profile(self, snapshot: dict) -> None:
        self.opacity = snapshot["opacity"]
        self.positions = dict(snapshot["positions"])
        self.scales = dict(snapshot["scales"])
        self.dpad_style = snapshot["dpad_style"]
        self.dpad_center = snapshot["dpad_center"]
        self.dpad_scale = snapshot["dpad_scale"]

    def begin_editor(self) -> None:
        if self.edit_mode:
            return
        self._editor_snapshot = self._profile_snapshot()
        self._editor_result = None
        self.edit_mode = True
        self.toolbar_visible = True
        self.selected_control = (
            "DPAD" if self.dpad_style != "separate" else "UP"
        )
        self.suppressed_fingers.update(self.live_fingers)
        self._release_requested = True

    def cancel_editor(self) -> None:
        if not self.edit_mode:
            return
        self._finish_editor("cancel")

    def is_editor_active(self) -> bool:
        return self.edit_mode

    def consume_editor_result(self) -> str | None:
        result = self._editor_result
        self._editor_result = None
        return result

    def _finish_editor(self, result: str) -> None:
        if result == "save":
            self._save_preferences()
        elif self._editor_snapshot is not None:
            self._restore_profile(self._editor_snapshot)
        self.edit_mode = False
        self._editor_snapshot = None
        self._editor_result = result
        self.suppressed_fingers.update(self.live_fingers)
        self.dragging_fingers.clear()
        self._release_requested = True

    def _handle_editor_down(
        self,
        finger_key: tuple[int, int],
        x: int,
        y: int,
        size: tuple[int, int],
        generated: list,
    ) -> None:
        self.suppressed_fingers.add(finger_key)
        action = self._toolbar_hit(x, y, size)
        if action == "SHOW":
            self.toolbar_visible = True
        elif action == "HIDE":
            self.toolbar_visible = False
        elif action == "OPACITY_DOWN":
            self.opacity = self._clamp_opacity(self.opacity - self.OPACITY_STEP)
        elif action == "OPACITY_UP":
            self.opacity = self._clamp_opacity(self.opacity + self.OPACITY_STEP)
        elif action == "SIZE_DOWN":
            self._adjust_selected_scale(-self.SCALE_STEP)
        elif action == "SIZE_UP":
            self._adjust_selected_scale(self.SCALE_STEP)
        elif action == "STYLE":
            self._cycle_dpad_style()
        elif action == "RESET":
            self.positions = dict(self.DEFAULT_POSITIONS)
            self.opacity = self.DEFAULT_OPACITY
            self.scales = {
                button: self.DEFAULT_SCALE for button in self.BUTTONS
            }
            self.dpad_style = self.DEFAULT_DPAD_STYLE
            self.dpad_center = self._default_dpad_center()
            self.dpad_scale = self.DEFAULT_SCALE
            self.selected_control = "DPAD"
        elif action == "SAVE":
            self._finish_editor("save")
        elif action == "CANCEL":
            self._finish_editor("cancel")
        else:
            button = self._hit_test(x, y, size)
            if button is not None:
                selected = (
                    "DPAD"
                    if self.dpad_style != "separate"
                    and set(self._as_buttons(button)) & set(self.DIRECTION_BUTTONS)
                    else button
                )
                self.selected_control = selected
                self.dragging_fingers[finger_key] = selected

    def _cycle_dpad_style(self) -> None:
        index = self.DPAD_STYLES.index(self.dpad_style)
        self.dpad_style = self.DPAD_STYLES[(index + 1) % len(self.DPAD_STYLES)]
        self.selected_control = (
            "DPAD" if self.dpad_style != "separate" else "UP"
        )

    def _editable_controls(self) -> tuple[str, ...]:
        directions = (
            self.DIRECTION_BUTTONS if self.dpad_style == "separate" else ("DPAD",)
        )
        return directions + self.ACTION_BUTTONS + ("START",)

    def _select_next_control(self) -> None:
        controls = self._editable_controls()
        try:
            index = controls.index(self.selected_control)
        except ValueError:
            index = -1
        self.selected_control = controls[(index + 1) % len(controls)]

    def _adjust_selected_scale(self, delta: float) -> None:
        if self.selected_control == "DPAD":
            self.dpad_scale = self._clamp_scale(self.dpad_scale + delta)
        else:
            self.scales[self.selected_control] = self._clamp_scale(
                self.scales[self.selected_control] + delta
            )

    def translate(self, events: list, size: tuple[int, int]) -> list:
        translated: list = []
        generated: list = []
        released_this_frame: set[tuple[int, int]] = set()
        finger_down = getattr(self.pygame, "FINGERDOWN", -1)
        finger_motion = getattr(self.pygame, "FINGERMOTION", -1)
        finger_up = getattr(self.pygame, "FINGERUP", -1)
        focus_lost_types = {
            getattr(self.pygame, name, -10 - index)
            for index, name in enumerate(
                (
                    "WINDOWFOCUSLOST",
                    "APP_WILLENTERBACKGROUND",
                    "APP_DIDENTERBACKGROUND",
                )
            )
        }
        android_back = getattr(
            self.pygame, "K_AC_BACK", self.pygame.K_ESCAPE
        )

        for event in events:
            if event.type == finger_down:
                finger_key = self._event_finger_key(event)
                self._remember_finger(finger_key, event.x, event.y)
                normalized = self.finger_positions[finger_key]
                x = max(0, min(size[0] - 1, int(event.x * size[0])))
                y = max(0, min(size[1] - 1, int(event.y * size[1])))
                if self.edit_mode:
                    self._handle_editor_down(
                        finger_key, x, y, size, generated
                    )
                else:
                    hit_buttons = set(self._as_buttons(
                        self._hit_test(x, y, size)
                    ))
                    passthrough = self._ui_passthrough_buttons()
                    should_forward = not (hit_buttons & passthrough)
                    if should_forward and self._forward_ui_touch(
                            "down", finger_key, normalized, size):
                        self.ui_fingers.add(finger_key)
                        self.suppressed_fingers.add(finger_key)
                        continue
            elif event.type == finger_motion:
                finger_key = self._event_finger_key(event)
                if finger_key not in self.live_fingers:
                    # Android/SDL can deliver stale motion after launch/resume.
                    continue
                self.finger_positions[finger_key] = (
                    max(0.0, min(1.0, float(event.x))),
                    max(0.0, min(1.0, float(event.y))),
                )
                if finger_key in self.ui_fingers:
                    self._forward_ui_touch(
                        "move", finger_key, self.finger_positions[finger_key], size
                    )
                    continue
                if self.edit_mode and finger_key in self.dragging_fingers:
                    self._move_dragged_button(
                        finger_key,
                        self.finger_positions[finger_key],
                        size,
                    )
            elif event.type == finger_up:
                finger_key = self._event_finger_key(event)
                released_this_frame.add(finger_key)
                if finger_key in self.ui_fingers:
                    normalized = self.finger_positions.get(
                        finger_key, (float(event.x), float(event.y))
                    )
                    self._forward_ui_touch("up", finger_key, normalized, size)
                self._forget_finger(finger_key)
            elif event.type in focus_lost_types:
                self._release_all(generated)
                translated.append(event)
            elif (
                event.type in (self.pygame.KEYDOWN, self.pygame.KEYUP)
                and getattr(event, "key", None) == android_back
            ):
                generated.append(self._key_event(event.type, "BACK"))
            elif (
                event.type
                in (
                    self.pygame.MOUSEBUTTONDOWN,
                    self.pygame.MOUSEBUTTONUP,
                    self.pygame.MOUSEMOTION,
                )
                and getattr(event, "touch", False)
            ):
                # SDL emits compatibility mouse events for the same finger.
                continue
            else:
                translated.append(event)

        polled = self._poll_fingers()
        if polled is not None:
            self._apply_polled_fingers(polled, released_this_frame, size)

        if self._release_requested:
            self._release_buttons(generated)
            self._release_requested = False

        if self.edit_mode:
            self._release_buttons(generated)
        elif self._ui_capture_active():
            # Drawers may explicitly retain a narrow set of game buttons.  The
            # debugger uses this for the D-pad while consuming every other tap.
            self._sync_game_buttons(
                size, generated, self._ui_passthrough_buttons())
        else:
            self._sync_game_buttons(size, generated)

        translated.extend(generated)
        return translated

    def _font(self, pixel_size: int):
        pixel_size = max(8, pixel_size)
        font = self._font_cache.get(pixel_size)
        if font is None:
            font = self.pygame.font.Font(None, pixel_size)
            self._font_cache[pixel_size] = font
        return font

    def _draw_label(
        self,
        surface,
        text: str,
        center: tuple[int, int],
        size: int,
        alpha: int,
    ) -> None:
        rendered = self._font(size).render(text, True, (245, 247, 255))
        rendered.set_alpha(alpha)
        rect = rendered.get_rect(center=center)
        surface.blit(rendered, rect)

    def _draw_panel_button(
        self,
        surface,
        rect: tuple[int, int, int, int],
        text: str,
        alpha: int,
    ) -> None:
        left, top, right, bottom = rect
        panel_rect = self.pygame.Rect(left, top, right - left, bottom - top)
        self.pygame.draw.rect(
            surface,
            (25, 33, 49, alpha),
            panel_rect,
            border_radius=4,
        )
        self.pygame.draw.rect(
            surface,
            (230, 237, 247, alpha),
            panel_rect,
            width=1,
            border_radius=4,
        )
        self._draw_label(
            surface,
            text,
            panel_rect.center,
            max(8, panel_rect.height - 4),
            alpha,
        )

    def _draw_dpad(
        self, surface, layout: dict[str, tuple], idle: tuple, active: tuple,
        outline: tuple, selected_outline: tuple, unit: int, outline_alpha: int,
        dragging: set[str],
    ) -> None:
        if self.dpad_style == "separate":
            for button in self.DIRECTION_BUTTONS:
                cx, cy, button_size = layout[button]
                rect = self.pygame.Rect(0, 0, button_size, button_size)
                rect.center = (cx, cy)
                is_active = button in self.active_buttons or button in dragging
                self.pygame.draw.rect(
                    surface, active if is_active else idle, rect,
                    border_radius=max(3, button_size // 5),
                )
                self.pygame.draw.rect(
                    surface, outline, rect, width=max(1, unit // 120),
                    border_radius=max(3, button_size // 5),
                )
                if self.edit_mode and self.selected_control == button:
                    self.pygame.draw.rect(
                        surface, selected_outline, rect, width=2,
                        border_radius=max(3, button_size // 5),
                    )
                self._draw_label(
                    surface, self.BUTTON_LABELS[button], rect.center,
                    max(8, int(button_size * 0.55)), outline_alpha,
                )
            return

        cx, cy, radius = layout["DPAD"]
        dpad_active = any(button in self.active_buttons for button in self.DIRECTION_BUTTONS)
        dpad_active = dpad_active or "DPAD" in dragging
        fill = active if dpad_active else idle
        if self.dpad_style == "cross":
            arm_half = max(5, int(radius * 0.36))
            vertical = self.pygame.Rect(cx - arm_half, cy - radius, arm_half * 2, radius * 2)
            horizontal = self.pygame.Rect(cx - radius, cy - arm_half, radius * 2, arm_half * 2)
            for rect in (vertical, horizontal):
                self.pygame.draw.rect(surface, fill, rect, border_radius=max(3, arm_half // 2))
                self.pygame.draw.rect(surface, outline, rect, width=max(1, unit // 120), border_radius=max(3, arm_half // 2))
            label_radius = int(radius * 0.64)
        else:
            self.pygame.draw.circle(surface, fill, (cx, cy), radius)
            self.pygame.draw.circle(surface, outline, (cx, cy), radius, width=max(1, unit // 120))
            label_radius = int(radius * 0.62)
        if self.edit_mode and self.selected_control == "DPAD":
            self.pygame.draw.circle(surface, selected_outline, (cx, cy), radius + 2, width=2)
        for button, offset in (
            ("UP", (0, -label_radius)),
            ("DOWN", (0, label_radius)),
            ("LEFT", (-label_radius, 0)),
            ("RIGHT", (label_radius, 0)),
        ):
            self._draw_label(
                surface, self.BUTTON_LABELS[button],
                (cx + offset[0], cy + offset[1]), max(8, int(radius * 0.36)),
                outline_alpha,
            )

    @staticmethod
    def _merge_blit_regions(
        regions: list[tuple[int, int, int, int]],
        size: tuple[int, int],
    ) -> list[tuple[int, int, int, int]]:
        """Merge overlapping control bounds and clip them to the canvas."""
        width, height = size
        pending: list[list[int]] = []
        for left, top, right, bottom in regions:
            bounds = [
                max(0, left), max(0, top), min(width, right), min(height, bottom)
            ]
            if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                continue
            merged = True
            while merged:
                merged = False
                for index, current in enumerate(pending):
                    separated = (
                        bounds[2] < current[0] or current[2] < bounds[0]
                        or bounds[3] < current[1] or current[3] < bounds[1]
                    )
                    if not separated:
                        bounds = [
                            min(bounds[0], current[0]), min(bounds[1], current[1]),
                            max(bounds[2], current[2]), max(bounds[3], current[3]),
                        ]
                        pending.pop(index)
                        merged = True
                        break
            pending.append(bounds)
        return [
            (left, top, right - left, bottom - top)
            for left, top, right, bottom in pending
        ]

    def _control_blit_regions(
        self, size: tuple[int, int], layout: dict[str, tuple]
    ) -> list[tuple[int, int, int, int]]:
        padding = 4
        regions: list[tuple[int, int, int, int]] = []
        if self.dpad_style == "separate":
            for button in self.DIRECTION_BUTTONS:
                cx, cy, button_size = layout[button]
                radius = button_size // 2 + padding
                regions.append((cx - radius, cy - radius, cx + radius, cy + radius))
        else:
            cx, cy, radius = layout["DPAD"]
            radius += padding
            regions.append((cx - radius, cy - radius, cx + radius, cy + radius))
        for button in self.ACTION_BUTTONS:
            cx, cy, radius = layout[button]
            radius += padding
            regions.append((cx - radius, cy - radius, cx + radius, cy + radius))
        left, top, right, bottom = layout["START"]
        regions.append((left - padding, top - padding, right + padding, bottom + padding))
        if self.edit_mode:
            toolbar = self._toolbar_layout(size)
            regions.append((
                min(rect[0] for rect in toolbar.values()) - padding,
                min(rect[1] for rect in toolbar.values()) - padding,
                max(rect[2] for rect in toolbar.values()) + padding,
                max(rect[3] for rect in toolbar.values()) + padding,
            ))
        return self._merge_blit_regions(regions, size)

    def _cache_overlay_regions(self, overlay) -> None:
        """Build tight immutable sources after the editable overlay changes."""
        rle_accel = getattr(self.pygame, "RLEACCEL", 0)
        cached_regions: list[tuple[object, tuple[int, int]]] = []
        for left, top, width, height in self._overlay_blit_regions:
            region = overlay.subsurface((left, top, width, height)).copy()
            if rle_accel:
                # A global alpha of 255 preserves the original opacity while
                # allowing SDL to RLE-skip the transparent pixels around each
                # rounded button.  Never apply this to the mutable full canvas.
                region.set_alpha(255, rle_accel)
            cached_regions.append((region, (left, top)))
        self._overlay_region_surfaces = cached_regions

    def _blit_cached_overlay(self, surface) -> None:
        # A full-canvas per-pixel-alpha blit costs about 9 ms on the measured
        # Android SDL2 software renderer. Blend only the control pixels, from
        # tight RLE surfaces so transparent corners do not consume blend time.
        for region, position in self._overlay_region_surfaces:
            surface.blit(region, position)

    def draw(self, surface) -> None:
        capture_buttons = (
            self._ui_passthrough_buttons()
            if self._ui_capture_active() and not self.edit_mode
            else frozenset()
        )
        if self._ui_capture_active() and not self.edit_mode and not capture_buttons:
            return
        size = surface.get_size()
        if self._overlay_surface is None or self._overlay_size != size:
            self._overlay_surface = self.pygame.Surface(size, self.pygame.SRCALPHA)
            self._overlay_size = size
            self._overlay_state = None
            self._overlay_blit_regions = []
            self._overlay_region_surfaces = []
        overlay = self._overlay_surface
        dragging = set(self.dragging_fingers.values())
        overlay_state = (
            size, self.opacity, self.edit_mode, self.toolbar_visible, self.dpad_style,
            self.dpad_center, self.dpad_scale, self.selected_control,
            tuple(sorted(capture_buttons)),
            tuple(sorted(self.active_buttons)), tuple(sorted(dragging)),
            tuple((button, *self.positions[button], self.scales[button]) for button in self.BUTTONS),
        )
        if self._overlay_state == overlay_state:
            self._blit_cached_overlay(surface)
            return

        overlay.fill((0, 0, 0, 0))
        layout = self._layout(size)
        unit = min(size)
        idle_alpha = self.opacity
        active_alpha = min(255, self.opacity + 75)
        outline_alpha = min(255, self.opacity + 85)
        idle = (35, 45, 68, idle_alpha)
        active = (48, 132, 214, active_alpha)
        outline = (220, 229, 242, outline_alpha)
        selected_outline = (255, 219, 94, 245)

        self._draw_dpad(
            overlay, layout, idle, active, outline, selected_outline, unit,
            outline_alpha, dragging,
        )
        for button in (() if capture_buttons else self.ACTION_BUTTONS):
            bx, by, button_radius = layout[button]
            is_active = button in self.active_buttons or button in dragging
            self.pygame.draw.circle(overlay, active if is_active else idle, (bx, by), button_radius)
            self.pygame.draw.circle(overlay, outline, (bx, by), button_radius, width=max(1, unit // 120))
            if self.edit_mode and self.selected_control == button:
                self.pygame.draw.circle(overlay, selected_outline, (bx, by), button_radius + 2, width=2)
            self._draw_label(overlay, self.BUTTON_LABELS[button], (bx, by), max(10, int(button_radius * 1.20)), outline_alpha)

        if not capture_buttons:
            left, top, right, bottom = layout["START"]
            start_rect = self.pygame.Rect(left, top, right - left, bottom - top)
            start_active = "START" in self.active_buttons or "START" in dragging
            self.pygame.draw.rect(overlay, active if start_active else idle, start_rect, border_radius=max(3, start_rect.height // 2))
            self.pygame.draw.rect(overlay, outline, start_rect, width=max(1, unit // 120), border_radius=max(3, start_rect.height // 2))
            if self.edit_mode and self.selected_control == "START":
                self.pygame.draw.rect(overlay, selected_outline, start_rect, width=2, border_radius=max(3, start_rect.height // 2))
            self._draw_label(overlay, self.BUTTON_LABELS["START"], start_rect.center, max(8, int(start_rect.height * 0.78)), outline_alpha)

        if self.edit_mode:
            toolbar = self._toolbar_layout(size)
            panel_alpha = 215
            compact = size[0] < 330
            labels = self._toolbar_labels(compact)
            left = min(rect[0] for rect in toolbar.values()) - 2
            top = min(rect[1] for rect in toolbar.values()) - 2
            right = max(rect[2] for rect in toolbar.values()) + 2
            bottom = max(rect[3] for rect in toolbar.values()) + 2
            ruler = self.pygame.Rect(left, top, right - left, bottom - top)
            self.pygame.draw.rect(
                overlay, (12, 18, 31, panel_alpha), ruler, border_radius=5
            )
            for action, rect in toolbar.items():
                self._draw_panel_button(overlay, rect, labels[action], panel_alpha)

        self._overlay_state = overlay_state
        self._overlay_blit_regions = self._control_blit_regions(size, layout)
        self._cache_overlay_regions(overlay)
        self._blit_cached_overlay(surface)

    def _selected_scale(self) -> float:
        if self.selected_control == "DPAD":
            return self.dpad_scale
        return self.scales[self.selected_control]

    def _toolbar_labels(self, compact: bool) -> dict[str, str]:
        if compact:
            return {
                "SHOW": "SHOW",
                "HIDE": "H",
                "STYLE": self.dpad_style[0].upper(),
                "OPACITY_DOWN": "O-",
                "OPACITY_UP": "O+",
                "SIZE_DOWN": "S-",
                "SIZE_UP": "S+",
                "RESET": "RST",
                "CANCEL": "X",
                "SAVE": "OK",
            }
        return {
            "SHOW": "SHOW",
            "HIDE": "HIDE",
            "STYLE": self.dpad_style.upper(),
            "OPACITY_DOWN": "O-",
            "OPACITY_UP": "O+",
            "SIZE_DOWN": "S-",
            "SIZE_UP": "S+",
            "RESET": "RESET",
            "CANCEL": "CANCEL",
            "SAVE": "SAVE",
        }
