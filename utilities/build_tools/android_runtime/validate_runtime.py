from __future__ import annotations

import ast
import configparser
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from prepare_runtime import RUNTIME_ROOT, STAGING_DIR, normalize_project_name, prepare, sha256
from preflight import load_toolchain_manifest, resolve_project, supported_android_arches


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_entrypoint_behaviour(staging: Path) -> str:
    main_path = staging / "main.py"
    source = main_path.read_text(encoding="utf-8")
    old_argument = os.environ.get("ANDROID_ARGUMENT")
    try:
        os.environ["ANDROID_ARGUMENT"] = str(staging)
        namespace: dict[str, object] = {
            "__file__": str(main_path),
            "__name__": "android_runtime_validation",
        }
        exec(compile(source, str(main_path), "exec"), namespace)
    finally:
        if old_argument is None:
            os.environ.pop("ANDROID_ARGUMENT", None)
        else:
            os.environ["ANDROID_ARGUMENT"] = old_argument

    require(
        namespace["BASE_DIR"] == staging.resolve(),
        "Android entrypoint did not select the validated ANDROID_ARGUMENT root",
    )

    observed: dict[str, object] = {}

    class FakePygameImage:
        @staticmethod
        def load(source_file, name_hint):
            observed["source_name"] = source_file.name
            observed["name_hint"] = name_hint
            observed["header"] = source_file.read(8)
            return object()

    class FakePygame:
        image = FakePygameImage()

    class FakeEngine:
        pygame = FakePygame()

        @staticmethod
        def image_load(*_args, **_kwargs):
            raise AssertionError("Android stream loader did not intercept image_load")

    fake_engine = FakeEngine()
    namespace["install_android_image_loader"](fake_engine)
    fake_engine.image_load("sprites/NamingScreen.png")
    require(
        Path(observed["source_name"]).is_absolute(),
        "Android image loader did not open an absolute path",
    )
    require(
        observed["name_hint"] == "NamingScreen.png",
        "Android image loader did not pass pygame an explicit filename hint",
    )
    require(
        observed["header"] == b"\x89PNG\r\n\x1a\n",
        "Android image loader did not read the packaged NamingScreen PNG",
    )

    class FakeJoystickDevice:
        @staticmethod
        def get_name():
            return "Android Accelerometer"

    class FakeJoystickModule:
        initialized = True
        quit_calls = 0

        @classmethod
        def get_init(cls):
            return cls.initialized

        @staticmethod
        def get_count():
            return 1

        @staticmethod
        def Joystick(_index):
            return FakeJoystickDevice()

        @classmethod
        def quit(cls):
            cls.quit_calls += 1
            cls.initialized = False

    joystick_diagnostics = namespace["isolate_android_joystick"](
        SimpleNamespace(pygame=SimpleNamespace(joystick=FakeJoystickModule))
    )
    require(
        joystick_diagnostics["discovered_count"] == 1
        and joystick_diagnostics["discovered_names"] == ["Android Accelerometer"]
        and not joystick_diagnostics["initialized_after"]
        and FakeJoystickModule.quit_calls == 1,
        "Android joystick isolation did not record and shut down joystick input",
    )

    observed_display: dict[str, object] = {}

    class FakeDisplay:
        @staticmethod
        def Info():
            return SimpleNamespace(current_w=2048, current_h=920)

        @staticmethod
        def set_mode(size, flags, vsync=0):
            observed_display["size"] = size
            observed_display["flags"] = flags
            observed_display["vsync"] = vsync
            return "wide-display"

    class FakeWidePygame:
        FULLSCREEN = 1
        SCALED = 2
        display = FakeDisplay()

    def original_build_display(_size):
        raise AssertionError("Wide touch canvas unexpectedly used fallback display")

    fake_wide_engine = SimpleNamespace(
        pygame=FakeWidePygame(),
        build_display=original_build_display,
    )
    old_hardware_scale = os.environ.get("LT_HARDWARE_SCALE")
    try:
        os.environ["LT_HARDWARE_SCALE"] = "1"
        namespace["install_android_wide_touch_canvas"](fake_wide_engine)
        wide_display = fake_wide_engine.build_display((240, 160))
    finally:
        if old_hardware_scale is None:
            os.environ.pop("LT_HARDWARE_SCALE", None)
        else:
            os.environ["LT_HARDWARE_SCALE"] = old_hardware_scale
    require(
        wide_display == "wide-display"
        and observed_display["size"] == (356, 160)
        and observed_display["flags"]
        == FakeWidePygame.FULLSCREEN | FakeWidePygame.SCALED
        and observed_display["vsync"] == 0,
        "Android display did not expose the full 2048x920 screen as a wide logical canvas",
    )

    fps_overlay = namespace["AndroidFpsOverlay"](SimpleNamespace())
    for frame in range(61):
        fps_label = fps_overlay.record_frame(frame / 60)
    require(
        fps_label == "FPS 60",
        f"Android display FPS counter measured an unexpected value: {fps_label}",
    )
    require(
        fps_overlay.label_position((356, 160), (240, 160), (30, 8))
        == (14, 3),
        "Android display FPS counter is not anchored in the left letterbox",
    )
    return namespace["RUNTIME_VERSION"]


def validate_touch_controls(staging: Path) -> None:
    source_path = staging / "android_controls.py"
    source = source_path.read_text(encoding="utf-8")
    require(
        "dispatch_android_touch" in source,
        "Android controls do not route captured touches to in-game overlays",
    )
    require(
        "is_android_touch_consumer_active" in source,
        "Android controls do not release/hide gameplay controls for an overlay",
    )
    require(
        "_edit_button_rect" not in source,
        "Floating EDIT button still exists outside Options > Controls",
    )
    require(
        "def begin_editor" in source and "def consume_editor_result" in source,
        "Android controls do not expose the Options editor lifecycle",
    )
    namespace: dict[str, object] = {
        "__file__": str(source_path),
        "__name__": "android_controls_validation",
    }
    exec(
        compile(source, str(source_path), "exec"),
        namespace,
    )

    class FakeEventFactory:
        @staticmethod
        def Event(event_type, **attributes):
            return SimpleNamespace(type=event_type, **attributes)

    draw_counts = {"render": 0, "rect": 0, "circle": 0}

    class FakeRenderedLabel:
        def set_alpha(self, _alpha):
            pass

        @staticmethod
        def get_rect(center):
            return SimpleNamespace(center=center)

    class FakeFont:
        def render(self, _text, _antialias, _color):
            draw_counts["render"] += 1
            return FakeRenderedLabel()

    class FakeFontModule:
        @staticmethod
        def Font(_path, _pixel_size):
            return FakeFont()

    class FakeSurface:
        def __init__(self, size, _flags=0):
            self._size = size
            self.blit_count = 0
            self.blit_areas = []
            self.blit_calls = []
            self.alpha_calls = []

        def get_size(self):
            return self._size

        def fill(self, _color):
            pass

        def blit(self, _source, _position, _area=None, special_flags=0):
            self.blit_count += 1
            self.blit_calls.append(
                (_source, _position, _area, special_flags)
            )
            if _area is not None:
                self.blit_areas.append(_area)

        def subsurface(self, area):
            return FakeSurface((area[2], area[3]))

        def copy(self):
            return FakeSurface(self._size)

        def set_alpha(self, alpha, flags=0):
            self.alpha_calls.append((alpha, flags))

    class FakeRect:
        def __init__(self, left, top, width, height):
            self.left = left
            self.top = top
            self.width = width
            self.height = height

        @property
        def center(self):
            return (
                self.left + self.width // 2,
                self.top + self.height // 2,
            )

        @center.setter
        def center(self, value):
            self.left = value[0] - self.width // 2
            self.top = value[1] - self.height // 2

    class FakeDraw:
        @staticmethod
        def rect(_surface, _color, _rect, **_kwargs):
            draw_counts["rect"] += 1

        @staticmethod
        def circle(_surface, _color, _center, _radius, **_kwargs):
            draw_counts["circle"] += 1

    class FakePygame:
        KEYDOWN = 1
        KEYUP = 2
        FINGERDOWN = 3
        FINGERMOTION = 4
        FINGERUP = 5
        MOUSEBUTTONDOWN = 6
        MOUSEBUTTONUP = 7
        MOUSEMOTION = 8
        WINDOWFOCUSLOST = 9
        K_ESCAPE = 27
        K_AC_BACK = 1001
        SRCALPHA = 1 << 8
        RLEACCEL = 1 << 9
        event = FakeEventFactory()
        font = FakeFontModule()
        draw = FakeDraw()
        Surface = FakeSurface
        Rect = FakeRect

    key_map = {
        button: 100 + index
        for index, button in enumerate(
            (
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
        )
    }
    controls = namespace["AndroidTouchControls"](FakePygame(), key_map)
    size = (240, 160)
    layout = controls._layout(size)
    select_x, select_y, _ = layout["SELECT"]
    select_down = SimpleNamespace(
        type=FakePygame.FINGERDOWN,
        finger_id=1,
        x=select_x / size[0],
        y=select_y / size[1],
    )
    first_press = controls.translate([select_down], size)
    require(
        len(first_press) == 1
        and first_press[0].type == FakePygame.KEYDOWN
        and first_press[0].key == key_map["SELECT"],
        "Touch SELECT did not produce the configured SELECT keydown",
    )

    second_press = controls.translate(
        [SimpleNamespace(**{**vars(select_down), "finger_id": 2})],
        size,
    )
    require(
        not second_press,
        "A second finger on one virtual button produced a duplicate keydown",
    )
    first_release = controls.translate(
        [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=1, x=0.0, y=0.0)],
        size,
    )
    require(
        not first_release,
        "Releasing one of two fingers released a still-held virtual button",
    )
    final_release = controls.translate(
        [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=2, x=0.0, y=0.0)],
        size,
    )
    require(
        len(final_release) == 1
        and final_release[0].type == FakePygame.KEYUP
        and final_release[0].key == key_map["SELECT"],
        "Final finger release did not produce SELECT keyup",
    )
    fast_forward_x, fast_forward_y, _ = layout["FAST_FORWARD"]
    fast_forward_press = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERDOWN,
                finger_id=30,
                x=fast_forward_x / size[0],
                y=fast_forward_y / size[1],
            )
        ],
        size,
    )
    require(
        len(fast_forward_press) == 1
        and fast_forward_press[0].type == FakePygame.KEYDOWN
        and fast_forward_press[0].key == key_map["FAST_FORWARD"],
        "Touch fast-forward did not produce the configured FAST_FORWARD keydown",
    )
    fast_forward_release = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERUP,
                finger_id=30,
                x=fast_forward_x / size[0],
                y=fast_forward_y / size[1],
            )
        ],
        size,
    )
    require(
        not fast_forward_release
        and "FAST_FORWARD" in controls.active_buttons,
        "Releasing touch fast-forward did not keep toggle mode enabled",
    )
    fast_forward_second_press = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERDOWN,
                finger_id=31,
                x=fast_forward_x / size[0],
                y=fast_forward_y / size[1],
            )
        ],
        size,
    )
    require(
        len(fast_forward_second_press) == 1
        and fast_forward_second_press[0].type == FakePygame.KEYUP
        and fast_forward_second_press[0].key == key_map["FAST_FORWARD"]
        and "FAST_FORWARD" not in controls.active_buttons,
        "Second touch fast-forward did not disable toggle mode",
    )
    fast_forward_second_release = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERUP,
                finger_id=31,
                x=fast_forward_x / size[0],
                y=fast_forward_y / size[1],
            )
        ],
        size,
    )
    require(
        not fast_forward_second_release,
        "Releasing disabled fast-forward produced duplicate input",
    )
    dpad_x, dpad_y, dpad_radius = layout["DPAD"]
    down_x = dpad_x
    down_y = dpad_y + int(dpad_radius * 0.65)
    orphan_motion = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERMOTION,
                finger_id=99,
                x=down_x / size[0],
                y=down_y / size[1],
            )
        ],
        size,
    )
    require(
        not orphan_motion and "DOWN" not in controls.active_buttons,
        "Orphan finger motion incorrectly created a held DOWN key",
    )
    controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERDOWN,
                finger_id=3,
                x=0.5,
                y=0.5,
            )
        ],
        size,
    )
    live_motion = controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERMOTION,
                finger_id=3,
                x=down_x / size[0],
                y=down_y / size[1],
            )
        ],
        size,
    )
    require(
        len(live_motion) == 1
        and live_motion[0].type == FakePygame.KEYDOWN
        and live_motion[0].key == key_map["DOWN"],
        "A live finger moving onto DOWN did not produce keydown",
    )
    controls.translate(
        [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=3, x=0.0, y=0.0)],
        size,
    )
    back_event = controls.translate(
        [SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_AC_BACK)],
        size,
    )
    require(
        len(back_event) == 1 and back_event[0].key == key_map["BACK"],
        "Android Back was not mapped to LT BACK",
    )

    # Android's polling fallback must preserve debugger drag gestures when
    # SDL omits FINGERMOTION or FINGERUP.  The validator runs from the
    # build-cache root, while the packaged engine lives under staging/app.
    # Import that staged module explicitly so this check does not accidentally
    # validate the source checkout (or fail because ``app`` is off sys.path).
    staged_package_root = staging / "app" / "engine" / "android_runtime.py"
    # The focused unit test exercises the controls template by itself; its
    # Android bridge therefore comes from this checkout.  A real packaging
    # validation always has the bridge under ``staging``.
    runtime_root = staging if staged_package_root.is_file() else Path(__file__).resolve().parents[3]
    runtime_root = runtime_root.resolve()
    staged_root = str(runtime_root)
    staged_modules = {
        module_name: sys.modules.pop(module_name)
        for module_name in ("app.engine.android_runtime", "app.engine", "app")
        if module_name in sys.modules
    }
    sys.path.insert(0, staged_root)
    try:
        android_runtime = importlib.import_module("app.engine.android_runtime")
        require(
            Path(android_runtime.__file__).resolve().is_relative_to(runtime_root),
            "Android touch validator imported android_runtime outside its validation package",
        )
        set_android_touch_consumer = android_runtime.set_android_touch_consumer
    except Exception:
        for module_name in ("app.engine.android_runtime", "app.engine", "app"):
            sys.modules.pop(module_name, None)
        sys.modules.update(staged_modules)
        raise
    finally:
        sys.path.remove(staged_root)

    class FakeTouchModule:
        def __init__(self):
            self.positions = {(0, 55): (0.40, 0.40)}

        def get_num_devices(self):
            return 1

        @staticmethod
        def get_device(_index):
            return 0

        def get_num_fingers(self, _touch_id):
            return len(self.positions)

        def get_finger(self, _touch_id, index):
            finger_id, position = list(self.positions.items())[index]
            return {"id": finger_id[1], "x": position[0], "y": position[1]}

    captured_ui_touches = []
    set_android_touch_consumer(
        lambda phase, position, finger: captured_ui_touches.append(
            (phase, position, finger)) or True)
    try:
        poller = FakeTouchModule()
        captured_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map, touch_module=poller)
        captured_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, touch_id=0, finger_id=55,
                x=0.40, y=0.40)],
            size,
        )
        poller.positions[(0, 55)] = (0.72, 0.40)
        captured_controls.translate([], size)
        poller.positions.clear()
        captured_controls.translate([], size)

        require(
            [event[0] for event in captured_ui_touches] == ["down", "move", "up"],
            "Polled Android touch fallback did not forward debugger move/up events",
        )

        captured_ui_touches.clear()
        set_android_touch_consumer(
            lambda phase, position, finger: captured_ui_touches.append(
                (phase, position, finger)) or True,
            passthrough_buttons=("UP", "DOWN", "LEFT", "RIGHT"),
        )
        passthrough_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map)
        passthrough_layout = passthrough_controls._layout(size)
        passthrough_x, passthrough_y, passthrough_radius = passthrough_layout["DPAD"]
        passthrough_events = passthrough_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, touch_id=0, finger_id=56,
                x=passthrough_x / size[0],
                y=(passthrough_y - passthrough_radius * 0.65) / size[1])],
            size,
        )
        require(
            len(passthrough_events) == 1
            and passthrough_events[0].key == key_map["UP"]
            and not captured_ui_touches,
            "Debugger touch capture did not leave the virtual D-pad active",
        )
    finally:
        set_android_touch_consumer(None)
        for module_name in ("app.engine.android_runtime", "app.engine", "app"):
            sys.modules.pop(module_name, None)
        sys.modules.update(staged_modules)
    draw_controls = namespace["AndroidTouchControls"](FakePygame(), key_map)
    destination = FakeSurface(size)
    draw_controls.draw(destination)
    first_draw = dict(draw_counts)
    require(
        first_draw["render"] > 0
        and first_draw["rect"] > 0
        and first_draw["circle"] > 0,
        "Initial touch overlay draw did not render its controls",
    )
    require(
        destination.blit_calls
        and all(call[2] is None for call in destination.blit_calls)
        and sum(
            call[0].get_size()[0] * call[0].get_size()[1]
            for call in destination.blit_calls
        )
        < size[0] * size[1] // 2,
        "Touch overlay still alpha-blits most of the full logical canvas",
    )
    first_region_sources = [call[0] for call in destination.blit_calls]
    require(
        all(source.alpha_calls == [(255, FakePygame.RLEACCEL)]
            for source in first_region_sources),
        "Touch overlay cache did not RLE-enable its immutable cropped regions",
    )
    draw_controls.draw(destination)
    require(
        draw_counts == first_draw,
        "Unchanged touch overlay rerendered text or geometry",
    )
    require(
        [id(call[0]) for call in destination.blit_calls[len(first_region_sources):]]
        == [id(source) for source in first_region_sources],
        "Unchanged touch overlay rebuilt its cropped render cache",
    )
    draw_controls.active_buttons.add("SELECT")
    draw_controls.draw(destination)
    require(
        draw_counts["render"] > first_draw["render"]
        and draw_counts["circle"] > first_draw["circle"],
        "Touch overlay cache did not invalidate after button state changed",
    )
    require(
        [id(call[0]) for call in destination.blit_calls[-len(first_region_sources):]]
        != [id(source) for source in first_region_sources],
        "Changed touch overlay reused stale cropped render surfaces",
    )

    # A newer opposite direction must win and the stale loser must remain
    # suppressed after the winner lifts. This is the reported DOWN-vs-UP bug.
    opposite_controls = namespace["AndroidTouchControls"](
        FakePygame(), key_map
    )
    opposite_controls.dpad_style = "separate"
    opposite_layout = opposite_controls._layout(size)
    opposite_events = []
    for finger_id, button in ((10, "DOWN"), (11, "UP")):
        button_x, button_y, _ = opposite_layout[button]
        opposite_events.append(
            opposite_controls.translate(
                [
                    SimpleNamespace(
                        type=FakePygame.FINGERDOWN,
                        finger_id=finger_id,
                        x=button_x / size[0],
                        y=button_y / size[1],
                    )
                ],
                size,
            )
        )
    require(
        len(opposite_events[1]) == 2
        and opposite_events[1][0].type == FakePygame.KEYUP
        and opposite_events[1][0].key == key_map["DOWN"]
        and opposite_events[1][1].type == FakePygame.KEYDOWN
        and opposite_events[1][1].key == key_map["UP"],
        "Newest opposite direction did not release DOWN before pressing UP",
    )
    winner_release = opposite_controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERUP,
                finger_id=11,
                x=0.0,
                y=0.0,
            )
        ],
        size,
    )
    require(
        len(winner_release) == 1
        and winner_release[0].type == FakePygame.KEYUP
        and winner_release[0].key == key_map["UP"]
        and "DOWN" not in opposite_controls.active_buttons,
        "Stale DOWN reactivated after the newer UP finger was released",
    )
    opposite_controls.translate(
        [
            SimpleNamespace(
                type=FakePygame.FINGERUP,
                finger_id=10,
                x=0.0,
                y=0.0,
            )
        ],
        size,
    )

    class FakeTouch:
        def __init__(self):
            self.fingers = []

        @staticmethod
        def get_num_devices():
            return 1

        @staticmethod
        def get_device(_device_index):
            return 77

        def get_num_fingers(self, _touch_id):
            return len(self.fingers)

        def get_finger(self, _touch_id, finger_index):
            return self.fingers[finger_index]

    fake_touch = FakeTouch()
    polled_controls = namespace["AndroidTouchControls"](
        FakePygame(), key_map, touch_module=fake_touch
    )
    polled_controls.dpad_style = "separate"
    polled_layout = polled_controls._layout(size)
    polled_down_x, polled_down_y, _ = polled_layout["DOWN"]
    fake_touch.fingers = [
        {
            "id": 501,
            "x": polled_down_x / size[0],
            "y": polled_down_y / size[1],
            "pressure": 1.0,
        }
    ]
    polled_press = polled_controls.translate([], size)
    require(
        len(polled_press) == 1
        and polled_press[0].type == FakePygame.KEYDOWN
        and polled_press[0].key == key_map["DOWN"],
        "Polled SDL finger state did not press DOWN",
    )
    fake_touch.fingers = []
    polled_release = polled_controls.translate([], size)
    require(
        len(polled_release) == 1
        and polled_release[0].type == FakePygame.KEYUP
        and polled_release[0].key == key_map["DOWN"],
        "Missing FINGERUP was not recovered from authoritative SDL finger state",
    )

    with tempfile.TemporaryDirectory() as temporary_dir:
        preferences_path = Path(temporary_dir) / "android_controls.json"
        editable_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map, preferences_path=preferences_path
        )
        editable_controls.begin_editor()
        require(
            editable_controls.edit_mode,
            "Options bridge did not enter layout mode",
        )
        expanded_toolbar = editable_controls._toolbar_layout(size)
        require(
            "HIDE" in expanded_toolbar and "SELECT_NEXT" not in expanded_toolbar,
            "Editor toolbar did not use the new single-ruler controls",
        )
        ruler_left = min(rect[0] for rect in expanded_toolbar.values())
        ruler_right = max(rect[2] for rect in expanded_toolbar.values())
        require(
            abs(ruler_left - (size[0] - ruler_right)) <= 1,
            "Editor ruler is not centered on the canvas",
        )
        hide_rect = expanded_toolbar["HIDE"]
        editable_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN,
                finger_id=20,
                x=(hide_rect[0] + hide_rect[2]) / 2 / size[0],
                y=(hide_rect[1] + hide_rect[3]) / 2 / size[1],
            )],
            size,
        )
        require(
            not editable_controls.toolbar_visible
            and set(editable_controls._toolbar_layout(size)) == {"SHOW"},
            "HIDE did not collapse the ruler to its SHOW tab",
        )
        show_rect = editable_controls._toolbar_layout(size)["SHOW"]
        editable_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN,
                finger_id=201,
                x=(show_rect[0] + show_rect[2]) / 2 / size[0],
                y=(show_rect[1] + show_rect[3]) / 2 / size[1],
            )],
            size,
        )
        require(
            editable_controls.toolbar_visible,
            "SHOW did not restore the editor ruler",
        )

        editable_layout = editable_controls._layout(size)
        editable_x, editable_y, _ = editable_layout["SELECT"]
        editable_controls.translate(
            [
                SimpleNamespace(
                    type=FakePygame.FINGERDOWN,
                    finger_id=21,
                    x=editable_x / size[0],
                    y=editable_y / size[1],
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERMOTION,
                    finger_id=21,
                    x=0.62,
                    y=0.60,
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERUP,
                    finger_id=21,
                    x=0.62,
                    y=0.60,
                ),
            ],
            size,
        )
        require(
            editable_controls.positions["SELECT"] == (0.62, 0.60),
            "Dragging SELECT did not update its normalized position",
        )

        opacity_rect = editable_controls._toolbar_layout(size)["OPACITY_DOWN"]
        opacity_x = (opacity_rect[0] + opacity_rect[2]) // 2
        opacity_y = (opacity_rect[1] + opacity_rect[3]) // 2
        editable_controls.translate(
            [
                SimpleNamespace(
                    type=FakePygame.FINGERDOWN,
                    finger_id=22,
                    x=opacity_x / size[0],
                    y=opacity_y / size[1],
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERUP,
                    finger_id=22,
                    x=opacity_x / size[0],
                    y=opacity_y / size[1],
                ),
            ],
            size,
        )
        require(
            editable_controls.opacity
            == editable_controls.DEFAULT_OPACITY
            - editable_controls.OPACITY_STEP,
            "Opacity minus control did not update opacity",
        )

        size_up_rect = editable_controls._toolbar_layout(size)["SIZE_UP"]
        size_up_x = (size_up_rect[0] + size_up_rect[2]) // 2
        size_up_y = (size_up_rect[1] + size_up_rect[3]) // 2
        editable_controls.translate(
            [
                SimpleNamespace(
                    type=FakePygame.FINGERDOWN,
                    finger_id=23,
                    x=size_up_x / size[0],
                    y=size_up_y / size[1],
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERUP,
                    finger_id=23,
                    x=size_up_x / size[0],
                    y=size_up_y / size[1],
                ),
            ],
            size,
        )
        require(
            editable_controls.scales["SELECT"] > editable_controls.DEFAULT_SCALE,
            "Selected control size did not update",
        )

        style_rect = editable_controls._toolbar_layout(size)["STYLE"]
        style_x = (style_rect[0] + style_rect[2]) // 2
        style_y = (style_rect[1] + style_rect[3]) // 2
        editable_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=24,
                x=style_x / size[0], y=style_y / size[1],
            )], size,
        )
        require(
            editable_controls.dpad_style == "round",
            "D-pad style did not advance from cross to round",
        )

        done_rect = editable_controls._toolbar_layout(size)["SAVE"]
        done_x = (done_rect[0] + done_rect[2]) // 2
        done_y = (done_rect[1] + done_rect[3]) // 2
        editable_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=25,
                x=done_x / size[0], y=done_y / size[1],
            )], size,
        )
        require(
            not editable_controls.edit_mode and preferences_path.is_file(),
            "SAVE did not leave layout mode and persist preferences",
        )
        require(
            editable_controls.consume_editor_result() == "save",
            "Saved editor session did not notify its Options state",
        )
        restored_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map, preferences_path=preferences_path
        )
        require(
            restored_controls.positions["SELECT"] == (0.62, 0.60)
            and restored_controls.opacity == editable_controls.opacity
            and restored_controls.dpad_style == "round"
            and restored_controls.scales["SELECT"] == editable_controls.scales["SELECT"],
            "Saved virtual-control profile was not restored",
        )
        restored_opacity = restored_controls.opacity
        restored_controls.begin_editor()
        restored_controls.opacity = restored_controls.MIN_OPACITY
        restored_controls.cancel_editor()
        require(
            restored_controls.opacity == restored_opacity
            and restored_controls.consume_editor_result() == "cancel",
            "Cancel did not restore the editor draft",
        )

        legacy_path = Path(temporary_dir) / "legacy_android_controls.json"
        legacy_path.write_text(
            json.dumps({
                "schema_version": 2,
                "opacity": 120,
                "positions": {"UP": [0.20, 0.50], "DOWN": [0.20, 0.82]},
            }),
            encoding="utf-8",
        )
        legacy_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map, preferences_path=legacy_path
        )
        require(
            legacy_controls.dpad_style == "separate"
            and legacy_controls.opacity == 120,
            "Schema 2 preferences did not preserve the prior separate layout",
        )

        wide_size = (356, 160)
        wide_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map
        )
        wide_controls.begin_editor()
        wide_layout = wide_controls._layout(wide_size)
        wide_select_x, wide_select_y, _ = wide_layout["SELECT"]
        wide_controls.translate(
            [
                SimpleNamespace(
                    type=FakePygame.FINGERDOWN,
                    finger_id=41,
                    x=wide_select_x / wide_size[0],
                    y=wide_select_y / wide_size[1],
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERMOTION,
                    finger_id=41,
                    x=0.99,
                    y=0.60,
                ),
                SimpleNamespace(
                    type=FakePygame.FINGERUP,
                    finger_id=41,
                    x=0.99,
                    y=0.60,
                ),
            ],
            wide_size,
        )
        moved_select_x, _, moved_select_radius = wide_controls._layout(
            wide_size
        )["SELECT"]
        game_right = (wide_size[0] + 240) // 2
        require(
            moved_select_x - moved_select_radius > game_right,
            "SELECT could not be dragged fully into the right letterbox area",
        )

        unrestricted_controls = namespace["AndroidTouchControls"](
            FakePygame(), key_map
        )
        unrestricted_controls.begin_editor()
        unrestricted_controls._set_button_position(
            "SELECT", (0.50, 0.0), size
        )
        _, select_top_y, select_radius = unrestricted_controls._layout(size)["SELECT"]
        require(
            select_top_y < 42 and select_top_y - select_radius >= 0,
            "Editor still reserves the old Cancel/Save rows above SELECT",
        )
        unrestricted_controls._set_dpad_center((0.50, 0.0), size)
        _, dpad_top_y, dpad_radius = unrestricted_controls._layout(size)["DPAD"]
        require(
            dpad_top_y < 42 and dpad_top_y - dpad_radius >= 0,
            "Editor still reserves the old Cancel/Save rows above the D-pad",
        )

        dpad_controls = namespace["AndroidTouchControls"](FakePygame(), key_map)
        dpad_layout = dpad_controls._layout(size)
        dpad_x, dpad_y, dpad_radius = dpad_layout["DPAD"]
        dpad_press = dpad_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=60,
                x=dpad_x / size[0], y=(dpad_y + dpad_radius * 0.65) / size[1],
            )], size,
        )
        require(
            len(dpad_press) == 1 and dpad_press[0].key == key_map["DOWN"],
            "Cross D-pad did not emit the expected cardinal direction",
        )
        dpad_controls.translate(
            [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=60, x=0.0, y=0.0)],
            size,
        )
        dpad_controls.dpad_style = "round"
        round_layout = dpad_controls._layout(size)
        round_x, round_y, round_radius = round_layout["DPAD"]
        neutral = dpad_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=61,
                x=round_x / size[0], y=round_y / size[1],
            )], size,
        )
        require(not neutral, "Round D-pad center dead-zone emitted input")
        round_right = dpad_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERMOTION, finger_id=61,
                x=(round_x + round_radius * 0.65) / size[0], y=round_y / size[1],
            )], size,
        )
        require(
            len(round_right) == 1 and round_right[0].key == key_map["RIGHT"],
            "Round D-pad sector did not emit the expected direction",
        )

        dpad_controls.translate(
            [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=61, x=0.0, y=0.0)],
            size,
        )
        round_diagonal = dpad_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=62,
                x=(round_x + round_radius * 0.55) / size[0],
                y=(round_y - round_radius * 0.55) / size[1],
            )], size,
        )
        require(
            {event.key for event in round_diagonal
             if event.type == FakePygame.KEYDOWN}
            == {key_map["UP"], key_map["RIGHT"]},
            "Round D-pad northeast sector did not emit both directions",
        )
        dpad_controls.translate(
            [SimpleNamespace(type=FakePygame.FINGERUP, finger_id=62, x=0.0, y=0.0)],
            size,
        )
        dpad_controls.dpad_style = "cross"
        cross_diagonal = dpad_controls.translate(
            [SimpleNamespace(
                type=FakePygame.FINGERDOWN, finger_id=63,
                x=(round_x - round_radius * 0.55) / size[0],
                y=(round_y + round_radius * 0.55) / size[1],
            )], size,
        )
        require(
            {event.key for event in cross_diagonal
             if event.type == FakePygame.KEYDOWN}
            == {key_map["DOWN"], key_map["LEFT"]},
            "Cross D-pad southwest corner did not emit both directions",
        )


def main(
    project: str = "default",
    prepared: bool = False,
    staging_path: Path | None = None,
    spec_path: Path | None = None,
) -> None:
    staging = (
        (staging_path or STAGING_DIR).resolve()
        if prepared
        else prepare(project, staging_dir=staging_path)
    )
    recipe_dir = RUNTIME_ROOT / "p4a-recipes" / "pygame-ce"

    python_files = sorted(staging.rglob("*.py"))
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    ast.parse((recipe_dir / "__init__.py").read_text(encoding="utf-8"))

    prohibited = (
        staging / "app" / "extensions",
        staging / "app" / "map_maker",
        staging / "app" / "tests",
    )
    require(not any(path.exists() for path in prohibited), "Editor/test code leaked into staging")
    require(
        (staging / "app" / "editor" / "lib" / "math" / "math_utils.py").is_file(),
        "Runtime math helper imported by grid_choice is missing",
    )
    require(not (staging / "app" / "dark_theme.py").exists(), "PyQt dark_theme leaked")

    manifest_path = staging / "runtime_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_project_dir = resolve_project(project).name
    require(
        manifest["project_dir"] == expected_project_dir,
        f"Prepared project mismatch: expected {expected_project_dir}",
    )
    project_dir = staging / manifest["project_dir"]
    metadata = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))
    require(not metadata.get("has_fatal_errors"), "Selected LT project has fatal errors")
    require((staging / "favicon.ico").is_file(), "Runtime favicon missing")
    require((staging / "android_icon.png").is_file(), "Android PNG icon missing")
    require((staging / "android_presplash.png").is_file(), "Android presplash missing")
    require(
        (staging / "app" / "engine" / "android_debugger.py").is_file(),
        "Android in-game debugger state is missing",
    )
    driver_source = (staging / "app" / "engine" / "driver.py").read_text(encoding="utf-8")
    require("icon_path='favicon.ico'" in driver_source, "driver.start icon override missing")
    require(
        "working_directory=None" in driver_source,
        "driver.start working-directory override missing",
    )
    require(
        "os.chdir(working_directory)" in driver_source,
        "driver.start does not restore the working directory after SDL setup",
    )
    main_source = (staging / "main.py").read_text(encoding="utf-8")
    require(
        '"runtime_debugger", False' in main_source,
        "Android runtime does not read the explicit in-game debugger build flag",
    )
    require(
        "working_directory=str(BASE_DIR)" in main_source,
        "Android entrypoint does not pin the runtime working directory",
    )
    for android_root_variable in (
        "ANDROID_ARGUMENT",
        "ANDROID_APP_PATH",
        "ANDROID_UNPACK",
    ):
        require(
            android_root_variable in main_source,
            f"Android entrypoint does not inspect {android_root_variable}",
        )
    require(
        '(candidate / "runtime_manifest.json").is_file()' in main_source,
        "Android runtime-root detection does not validate the manifest",
    )
    require("return None" in main_source, "Runtime-root detection has an unsafe fallback")
    require(
        '"sprites" / "NamingScreen.png"' in main_source,
        "Android runtime-root detection does not validate NamingScreen",
    )
    require(
        "normalize_runtime_assets(RESOURCES)" in main_source,
        "Android entrypoint does not normalize sprite/platform paths",
    )
    require(
        "pygame.image.load(image_stream, image_path.name)" in main_source,
        "Android entrypoint does not use the stream image loader",
    )
    require(
        'os.environ.setdefault("LT_HARDWARE_SCALE", "1")' in main_source,
        "Android entrypoint does not request SDL hardware scaling",
    )
    require(
        'os.environ.setdefault("LT_ANDROID_RUNTIME", "1")' in main_source,
        "Android entrypoint does not explicitly enable Android-only engine paths",
    )
    require(
        'os.environ.setdefault("LT_ANDROID_RENDER_OPT", "1")' in main_source,
        "Android entrypoint does not enable Android render optimisations",
    )
    require(
        'os.environ["SDL_RENDER_VSYNC"] = "0"' in main_source,
        "Android entrypoint does not explicitly disable the SDL vsync limiter",
    )
    require(
        'os.environ.setdefault("LT_PRECISE_FRAME_PACING", "1")'
        not in main_source,
        "Android entrypoint still enables CPU-heavy busy-loop frame pacing",
    )
    require(
        "install_android_wide_touch_canvas(driver.engine)" in main_source,
        "Android entrypoint does not install the full-screen logical touch canvas",
    )
    require(
        '"FAST_FORWARD",' in main_source,
        "Android entrypoint does not map the virtual fast-forward button",
    )
    require(
        'os.environ.setdefault("SDL_ACCELEROMETER_AS_JOYSTICK", "0")'
        in main_source,
        "Android entrypoint does not disable SDL accelerometer joystick emulation",
    )
    require(
        'os.environ.setdefault("LT_DISABLE_JOYSTICK", "1")' in main_source,
        "Android entrypoint does not disable LT joystick polling",
    )
    require(
        "isolate_android_joystick(driver.engine)" in main_source,
        "Android entrypoint does not shut down the SDL joystick module",
    )
    engine_source = (staging / "app" / "engine" / "engine.py").read_text(
        encoding="utf-8"
    )
    require(
        "os.environ.get('LT_DISABLE_JOYSTICK') == '1'" in engine_source,
        "Engine joystick availability is not gated for the Android runtime",
    )
    require(
        "install_android_touch_controls(driver.engine, cf.SETTINGS)" in main_source,
        "Android entrypoint does not install virtual touch controls",
    )
    require(
        "register_android_virtual_controls(controls)" in main_source,
        "Android entrypoint does not expose controls to Options",
    )
    android_runtime_source = (staging / "app" / "engine" / "android_runtime.py").read_text(
        encoding="utf-8"
    )
    require(
        "get_android_virtual_controls" in android_runtime_source,
        "Engine has no Android virtual-controls bridge",
    )
    settings_source = (staging / "app" / "engine" / "settings.py").read_text(
        encoding="utf-8"
    )
    require(
        "AndroidControlsEditorState" in settings_source,
        "Settings does not provide an Android virtual-controls editor state",
    )
    require(
        "fps_overlay.draw(new_surf, surf.get_size())" in main_source,
        "Android entrypoint does not draw real display FPS in the letterbox",
    )
    require(
        "Traceback tail:" in main_source,
        "Android fatal screen does not expose the traceback location",
    )
    require(
        "new_surf.fill((0, 0, 0))" in main_source,
        "Expanded touch canvas is not cleared before drawing translucent controls",
    )
    require(
        manifest["phase"] == 4 and manifest["schema_version"] == 2,
        "Runtime manifest is not marked as phase 4 schema 2",
    )
    require(
        (staging / "android_preflight.json").is_file(),
        "Phase 4 preflight report is missing from staging",
    )
    preflight = json.loads(
        (staging / "android_preflight.json").read_text(encoding="utf-8")
    )
    require(preflight.get("passed") is True, "Packaged preflight report did not pass")
    validate_touch_controls(staging)
    typing_shim = staging / "typing_extensions.py"
    require(typing_shim.is_file(), "Android typing_extensions shim missing")
    typing_shim_source = typing_shim.read_text(encoding="utf-8")
    require("Protocol" in typing_shim_source, "Protocol shim missing")
    require("override" in typing_shim_source, "override shim missing")
    require((staging / "resources").is_dir(), "Standard resources missing")
    require((staging / "sprites").is_dir(), "Standard sprites missing")

    for relative_path, file_metadata in manifest["files"].items():
        path = staging / relative_path
        require(path.is_file(), f"Manifest path is missing: {relative_path}")
        require(sha256(path) == file_metadata["sha256"], f"Hash mismatch: {relative_path}")

    config = configparser.ConfigParser(interpolation=None)
    config.read(spec_path or RUNTIME_ROOT / "buildozer.spec", encoding="utf-8")
    app = config["app"]
    runtime_version = validate_entrypoint_behaviour(staging)
    toolchain = load_toolchain_manifest()
    require(
        runtime_version == toolchain["runtime_version"],
        "Entrypoint runtime version does not match toolchain manifest",
    )
    require(
        app["version"] == manifest["build"]["version_name"],
        "Configured APK version does not match staged build manifest",
    )
    require(
        app["android.numeric_version"] == str(manifest["build"]["version_code"]),
        "Configured APK version code does not match staged build manifest",
    )
    require(
        f"{app['package.domain']}.{app['package.name']}"
        == manifest["build"]["package_id"],
        "Configured APK package ID does not match staged build manifest",
    )
    require(
        app["android.api"] == str(toolchain["android_api"]),
        "android.api does not match toolchain manifest",
    )
    requested_arch = manifest["build"]["arch"]
    require(
        requested_arch in supported_android_arches(toolchain),
        f"Unsupported staged Android ABI: {requested_arch}",
    )
    require(
        app["android.archs"] == requested_arch,
        "Configured APK ABI does not match staged build manifest",
    )
    require(app["p4a.bootstrap"] == "sdl2", "Runtime APK must use SDL2")
    for requirement in (
        "hostpython3==3.11.9",
        "python3==3.11.9",
        "pygame-ce==2.3.2",
        "android",
    ):
        require(requirement in app["requirements"], f"Requirement pin missing: {requirement}")
    patch_name = "setup-setuptools-distutils-spawn.patch"
    require(patch_name in (recipe_dir / "__init__.py").read_text(encoding="utf-8"), "pygame-ce patch not registered")
    require((recipe_dir / patch_name).is_file(), "pygame-ce patch file missing")
    print(
        "ANDROID_RUNTIME_STATIC_OK "
        f"phase=4 project={manifest['project_dir']} "
        f"files={len(manifest['files'])}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="default")
    parser.add_argument("--prepared", action="store_true")
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--spec", type=Path)
    args = parser.parse_args()
    main(args.project, args.prepared, args.staging, args.spec)
