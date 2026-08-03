from __future__ import annotations

from collections import deque
import json
import logging
import os
from pathlib import Path
import sys
import textwrap
import time
import traceback


RUNTIME_VERSION = "0.4.0"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def runtime_base_candidates() -> list[Path]:
    raw_candidates = (
        os.environ.get("ANDROID_ARGUMENT"),
        os.environ.get("ANDROID_APP_PATH"),
        os.environ.get("ANDROID_UNPACK"),
        str(Path(__file__).resolve().parent),
        str(Path.cwd() / "app"),
        str(Path.cwd()),
    )
    candidates: list[Path] = []
    for raw_candidate in raw_candidates:
        if not raw_candidate:
            continue
        candidate = Path(raw_candidate).resolve()
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def find_runtime_base() -> Path | None:
    candidates = runtime_base_candidates()
    for candidate in candidates:
        if (
            (candidate / "runtime_manifest.json").is_file()
            and (candidate / "sprites" / "NamingScreen.png").is_file()
            and (candidate / "resources" / "platforms" / "Arena-Melee.png").is_file()
        ):
            return candidate
    return None


DETECTED_BASE_DIR = find_runtime_base()
BASE_DIR = DETECTED_BASE_DIR or Path.cwd().resolve()
MANIFEST_PATH = BASE_DIR / "runtime_manifest.json"
REPORT_PREFIX = "LT_ANDROID_RUNTIME "


def resolve_runtime_asset_path(path: str | os.PathLike[str]) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = BASE_DIR / resolved
    return resolved.resolve()


def runtime_save_dir() -> Path:
    configured = os.environ.get("LT_USER_DATA_DIR")
    if configured:
        return Path(configured) / "saves"
    # ``run()`` changes into BASE_DIR before this helper is called. Keep the
    # desktop fallback relative; Android supplies the persistent root above.
    return Path("saves")


def configure_android_user_data() -> Path:
    """Bind Android player data to private app storage before engine startup."""
    android_private = os.environ.get("ANDROID_PRIVATE")
    if not android_private:
        raise RuntimeError(
            "ANDROID_PRIVATE is unavailable; refusing to store player data "
            "inside the replaceable APK runtime"
        )
    private_root = Path(android_private).resolve()
    if not private_root.is_dir():
        raise RuntimeError(
            "ANDROID_PRIVATE is not an accessible directory: "
            f"{private_root}"
        )
    user_data_root = private_root / "user_data"
    # A pre-existing value could point into files/app, so Android must not
    # inherit it from the launcher environment.
    os.environ["LT_USER_DATA_DIR"] = str(user_data_root)
    return user_data_root


def normalize_runtime_assets(resources: object) -> tuple[int, int]:
    from app.sprites import SPRITES

    sprite_count = 0
    missing: list[str] = []
    for sprite in SPRITES.values():
        if not sprite.full_path:
            continue
        sprite_path = resolve_runtime_asset_path(sprite.full_path)
        sprite.full_path = str(sprite_path)
        sprite_count += 1
        if not sprite_path.is_file():
            missing.append(str(sprite_path))

    platform_count = 0
    for nid, platform_path in list(resources.platforms.items()):
        resolved_platform = resolve_runtime_asset_path(platform_path)
        resources.platforms[nid] = str(resolved_platform)
        platform_count += 1
        if not resolved_platform.is_file():
            missing.append(str(resolved_platform))

    if missing:
        raise FileNotFoundError(
            "Runtime asset normalization found missing files: "
            + ", ".join(missing[:5])
        )
    return sprite_count, platform_count


def install_android_image_loader(engine_module: object) -> None:
    if getattr(engine_module, "_lt_android_stream_loader", False):
        return

    original_image_load = engine_module.image_load

    def android_image_load(fn, convert=False, convert_alpha=False):
        if hasattr(fn, "read"):
            return original_image_load(
                fn, convert=convert, convert_alpha=convert_alpha
            )
        image_path = resolve_runtime_asset_path(os.fspath(fn))
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Android image asset missing: {image_path}; cwd={Path.cwd()}"
            )
        with image_path.open("rb") as image_stream:
            image = engine_module.pygame.image.load(image_stream, image_path.name)
        if convert:
            image = image.convert()
        elif convert_alpha:
            image = image.convert_alpha()
        return image

    engine_module.image_load = android_image_load
    engine_module._lt_android_stream_loader = True


def isolate_android_joystick(engine_module: object) -> dict[str, object]:
    """Record then shut down SDL joystick input before InputManager is built."""
    joystick_module = engine_module.pygame.joystick
    was_initialized = bool(joystick_module.get_init())
    discovered_count = 0
    discovered_names: list[str] = []
    if was_initialized:
        discovered_count = int(joystick_module.get_count())
        for index in range(discovered_count):
            try:
                discovered_names.append(joystick_module.Joystick(index).get_name())
            except Exception as exc:
                discovered_names.append(f"<unreadable:{type(exc).__name__}>")
    joystick_module.quit()
    return {
        "initialized_before": was_initialized,
        "discovered_count": discovered_count,
        "discovered_names": discovered_names,
        "initialized_after": bool(joystick_module.get_init()),
        "engine_input_enabled": False,
    }


def expanded_logical_size(
    game_size: tuple[int, int],
    physical_size: tuple[int, int],
) -> tuple[int, int]:
    """Keep the game resolution while exposing the whole physical screen."""
    game_width, game_height = game_size
    physical_width, physical_height = physical_size
    if min(game_width, game_height, physical_width, physical_height) <= 0:
        return game_size
    if physical_width * game_height > game_width * physical_height:
        return (
            max(
                game_width,
                round(game_height * physical_width / physical_height),
            ),
            game_height,
        )
    return (
        game_width,
        max(
            game_height,
            round(game_width * physical_height / physical_width),
        ),
    )


def install_android_wide_touch_canvas(engine_module: object) -> None:
    """Expand SDL's logical canvas into the letterbox while retaining SCALED."""
    original_build_display = engine_module.build_display
    pygame = engine_module.pygame

    def build_display_with_wide_touch_canvas(size):
        if (
            os.environ.get("LT_HARDWARE_SCALE") != "1"
            or not hasattr(pygame, "SCALED")
        ):
            return original_build_display(size)
        try:
            display_info = pygame.display.Info()
            physical_size = (
                int(display_info.current_w),
                int(display_info.current_h),
            )
            logical_size = expanded_logical_size(size, physical_size)
            display = pygame.display.set_mode(
                logical_size,
                pygame.FULLSCREEN | pygame.SCALED,
                vsync=0,
            )
            logging.info(
                "Android wide touch canvas initialized: game=%s logical=%s physical=%s",
                size,
                logical_size,
                physical_size,
            )
            return display
        except Exception:
            logging.exception(
                "Android wide touch canvas failed; using engine display fallback"
            )
            return original_build_display(size)

    engine_module.build_display = build_display_with_wide_touch_canvas


class AndroidFpsOverlay:
    """Measure completed display frames and render FPS in the left letterbox."""

    UPDATE_INTERVAL = 0.25
    SAMPLE_COUNT = 120

    def __init__(self, pygame_module: object) -> None:
        self.pygame = pygame_module
        self.frame_times: deque[float] = deque(maxlen=self.SAMPLE_COUNT)
        self.last_update: float | None = None
        self.label = "FPS --"
        self._font = None
        self._rendered_label = None
        self._rendered_text = ""

    def record_frame(self, now: float | None = None) -> str:
        now = time.monotonic() if now is None else float(now)
        self.frame_times.append(now)
        if (
            self.last_update is not None
            and now - self.last_update < self.UPDATE_INTERVAL
        ):
            return self.label

        if len(self.frame_times) >= 2:
            elapsed = self.frame_times[-1] - self.frame_times[0]
            if elapsed > 0:
                fps = (len(self.frame_times) - 1) / elapsed
                self.label = f"FPS {fps:.0f}"
        self.last_update = now
        return self.label

    @staticmethod
    def label_position(
        canvas_size: tuple[int, int],
        game_size: tuple[int, int],
        label_size: tuple[int, int],
    ) -> tuple[int, int]:
        canvas_width, _ = canvas_size
        game_width, _ = game_size
        label_width, _ = label_size
        left_letterbox = max(0, (canvas_width - game_width) // 2)
        if left_letterbox >= label_width + 4:
            return max(2, (left_letterbox - label_width) // 2), 3
        return 3, 3

    def draw(self, surface: object, game_size: tuple[int, int]) -> None:
        label = self.record_frame()
        if self._font is None:
            # The Android logical display is about 160 px high. A 12 px font
            # remains readable without covering the game viewport.
            self._font = self.pygame.font.Font(None, 12)
        if self._rendered_label is None or self._rendered_text != label:
            try:
                fps = float(label.split()[-1])
            except ValueError:
                color = (220, 225, 232)
            else:
                if fps >= 55:
                    color = (105, 235, 135)
                elif fps >= 30:
                    color = (255, 220, 90)
                else:
                    color = (255, 105, 105)
            self._rendered_label = self._font.render(label, True, color)
            self._rendered_text = label
        position = self.label_position(
            surface.get_size(),
            game_size,
            self._rendered_label.get_size(),
        )
        surface.blit(self._rendered_label, position)


def install_android_touch_controls(engine_module: object, settings: dict) -> object:
    from android_controls import AndroidTouchControls
    try:
        from pygame._sdl2 import touch as touch_module
    except (AttributeError, ImportError):
        touch_module = None

    key_map = {
        button: settings[f"key_{button}"]
        for button in (
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
    }
    controls = AndroidTouchControls(
        engine_module.pygame,
        key_map,
        preferences_path=runtime_save_dir() / "android_controls.json",
        touch_module=touch_module,
    )
    for event_type in (
        getattr(engine_module.pygame, "FINGERDOWN", None),
        getattr(engine_module.pygame, "FINGERMOTION", None),
        getattr(engine_module.pygame, "FINGERUP", None),
        getattr(engine_module.pygame, "MOUSEBUTTONDOWN", None),
        getattr(engine_module.pygame, "MOUSEBUTTONUP", None),
        getattr(engine_module.pygame, "MOUSEMOTION", None),
    ):
        if event_type is not None:
            engine_module.pygame.event.clear(event_type)
    original_get_events = engine_module.get_events
    original_push_display = engine_module.push_display
    fps_overlay = AndroidFpsOverlay(engine_module.pygame)

    def get_events_with_touch_controls():
        events = original_get_events()
        if events == engine_module.QUIT:
            return events
        return controls.translate(events, engine_module.get_screen_size())

    def push_display_with_touch_controls(surf, size, new_surf):
        # The expanded logical canvas includes the phone's former letterbox.
        # Clear it every frame so translucent controls do not accumulate or
        # leave trails while the user drags them outside the game viewport.
        new_surf.fill((0, 0, 0))
        original_push_display(surf, size, new_surf)
        controls.draw(new_surf)
        fps_overlay.draw(new_surf, surf.get_size())

    engine_module.get_events = get_events_with_touch_controls
    engine_module.push_display = push_display_with_touch_controls
    controls.fps_overlay = fps_overlay
    # Settings lives in the shared engine and cannot import this Android-only
    # template. Register the live controller through its narrow runtime bridge.
    from app.engine.android_runtime import register_android_virtual_controls
    register_android_virtual_controls(controls)
    return controls


class BootReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.started_at = time.time()
        self.stages: dict[str, dict[str, object]] = {}

    def set(self, name: str, passed: bool, detail: str = "") -> None:
        self.stages[name] = {
            "passed": bool(passed),
            "detail": detail,
            "time": time.time(),
        }

    def flush(self) -> None:
        payload = {
            "schema_version": 1,
            "runtime_version": RUNTIME_VERSION,
            "started_at": self.started_at,
            "updated_at": time.time(),
            "python": sys.version,
            "platform": sys.platform,
            "cwd": str(Path.cwd()),
            "android_argument": os.environ.get("ANDROID_ARGUMENT"),
            "android_app_path": os.environ.get("ANDROID_APP_PATH"),
            "android_private": os.environ.get("ANDROID_PRIVATE"),
            "android_unpack": os.environ.get("ANDROID_UNPACK"),
            "runtime_base": str(BASE_DIR),
            "stages": self.stages,
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self.path)
        print(REPORT_PREFIX + json.dumps(payload, sort_keys=True), flush=True)


def show_fatal_screen(message: str) -> None:
    try:
        import pygame

        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_surface():
            display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            display = pygame.display.get_surface()
        display_width, display_height = display.get_size()
        font_size = max(10, min(18, display_height // 14))
        font = pygame.font.Font(None, font_size)
        clock = pygame.time.Clock()
        lines = [f"LT Android phase 4 failed [{RUNTIME_VERSION}]"]
        wrap_width = max(32, display_width // max(5, font_size // 2))
        for raw_line in message.splitlines():
            lines.extend(textwrap.wrap(raw_line, width=wrap_width) or [""])
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key in {
                    pygame.K_ESCAPE,
                    getattr(pygame, "K_AC_BACK", pygame.K_ESCAPE),
                }:
                    running = False
            display.fill((48, 12, 18))
            y = 4
            line_height = font.get_height() + 1
            visible_lines = max(1, (display_height - y) // line_height)
            for line in lines[:visible_lines]:
                display.blit(font.render(line, True, (255, 230, 230)), (4, y))
                y += line_height
            pygame.display.flip()
            clock.tick(30)
    except Exception:
        print(REPORT_PREFIX + "fatal screen unavailable", flush=True)


def run() -> None:
    # SDL2 lists the built-in Android accelerometer as a joystick by default.
    # Disable both that SDL device and LT's joystick polling before pygame/app
    # modules are imported. Touch controls remain the sole Android game input.
    os.environ.setdefault("SDL_ACCELEROMETER_AS_JOYSTICK", "0")
    os.environ["SDL_RENDER_VSYNC"] = "0"
    # Engine code is shared with desktop.  These opt-in flags ensure mobile
    # profiling and render optimisations can never change a PC launch.
    os.environ.setdefault("LT_ANDROID_RUNTIME", "1")
    os.environ.setdefault("LT_ANDROID_RENDER_OPT", "1")
    os.environ.setdefault("LT_DISABLE_JOYSTICK", "1")
    os.environ.setdefault("LT_HARDWARE_SCALE", "1")
    # This branch is producing a diagnostics APK.  The profiler aggregates in
    # memory and emits one WARNING summary per five seconds, not per frame.
    os.environ.setdefault("LT_ANDROID_PROFILE", "1")
    configure_android_user_data()
    os.chdir(BASE_DIR)
    saves_dir = runtime_save_dir()
    saves_dir.mkdir(parents=True, exist_ok=True)
    report = BootReport(saves_dir / "android_runtime_boot.json")
    report.set("bootstrap_started", True, str(BASE_DIR))

    try:
        if DETECTED_BASE_DIR is None:
            checked = ", ".join(str(path) for path in runtime_base_candidates())
            raise FileNotFoundError(
                f"Android runtime root not found; checked: {checked}"
            )
        naming_screen = BASE_DIR / "sprites" / "NamingScreen.png"
        with naming_screen.open("rb") as naming_stream:
            naming_header = naming_stream.read(len(PNG_SIGNATURE))
        if naming_header != PNG_SIGNATURE:
            raise ValueError(
                f"Invalid NamingScreen PNG header: {naming_header!r}"
            )
        report.set(
            "builtin_sprite_probe",
            True,
            f"{naming_screen}; bytes={naming_screen.stat().st_size}",
        )
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        project_dir = BASE_DIR / manifest["project_dir"]
        report.set("manifest_loaded", project_dir.is_dir(), str(project_dir))

        from app import lt_log
        from app.data.database.database import DB
        from app.data.metadata import Metadata
        from app.data.resources.resources import RESOURCES
        from app.data.serialization.dataclass_serialization import dataclass_from_dict
        from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
        from app.engine import config as cf
        from app.engine import driver, game_state

        cf.SETTINGS.update(
            {
                # APK signing mode and the in-game debugger are independent.
                # A developer explicitly opts in through android.json.
                "debug": int(bool(manifest.get("build", {}).get(
                    "runtime_debugger", False))),
                "display_fps": 0,
                "fullscreen": 1,
                "screen_size": 1,
                "mouse": 0,
            }
        )
        report.set("engine_imports", True, "runtime modules imported without PyQt")
        report.set("logger", lt_log.create_logger(), str(lt_log.get_log_dir()))

        metadata_path = project_dir / "metadata.json"
        metadata = dataclass_from_dict(
            Metadata, json.loads(metadata_path.read_text(encoding="utf-8"))
        )
        if metadata.has_fatal_errors:
            raise ValueError(f"Fatal project validation errors: {project_dir.name}")
        report.set(
            "project_metadata",
            True,
            f"{project_dir.name}; serialization={metadata.serialization_version}",
        )

        RESOURCES.load(str(project_dir), CURRENT_SERIALIZATION_VERSION)
        report.set("resources_loaded", True, project_dir.name)
        sprite_count, platform_count = normalize_runtime_assets(RESOURCES)
        report.set(
            "absolute_asset_paths",
            True,
            f"sprites={sprite_count}; platforms={platform_count}",
        )
        DB.load(str(project_dir), CURRENT_SERIALIZATION_VERSION)
        report.set("database_loaded", True, project_dir.name)

        title = DB.constants.value("title")
        runtime_icon = BASE_DIR / "android_icon.png"
        report.set("runtime_icon", runtime_icon.is_file(), str(runtime_icon))
        if not runtime_icon.is_file():
            raise FileNotFoundError(f"Missing Android runtime icon: {runtime_icon}")
        install_android_image_loader(driver.engine)
        install_android_wide_touch_canvas(driver.engine)
        report.set(
            "stream_image_loader",
            True,
            "Python file streams with explicit filename hints",
        )
        driver.start(
            title,
            icon_path=str(runtime_icon),
            working_directory=str(BASE_DIR),
        )
        game_display_size = driver.engine.get_screensize(True)
        logical_display_size = driver.engine.get_screen_size()
        report.set(
            "wide_touch_canvas",
            logical_display_size != game_display_size,
            f"game={game_display_size}; logical={logical_display_size}",
        )
        joystick_diagnostics = isolate_android_joystick(driver.engine)
        report.set(
            "joystick_isolation",
            (
                os.environ.get("SDL_ACCELEROMETER_AS_JOYSTICK") == "0"
                and os.environ.get("LT_DISABLE_JOYSTICK") == "1"
                and not joystick_diagnostics["initialized_after"]
            ),
            json.dumps(joystick_diagnostics, sort_keys=True),
        )
        touch_controls = install_android_touch_controls(driver.engine, cf.SETTINGS)
        report.set(
            "touch_controls",
            touch_controls is not None,
            "SDL finger state reconciled every frame; opposite-direction loser "
            "suppressed until release; editable positions and opacity persisted; "
            "full-screen layout canvas; multitouch dpad+A/B/X/Y/Start/Fast Forward; "
            "Android Back mapped to BACK; real display FPS shown in left letterbox",
        )
        report.set(
            "runtime_working_directory",
            Path.cwd() == BASE_DIR,
            str(Path.cwd()),
        )
        if Path.cwd() != BASE_DIR:
            raise RuntimeError(
                f"Android runtime working directory changed unexpectedly: {Path.cwd()}"
            )
        report.set("display_started", True, str(driver.engine.get_screen_size()))
        logical_size = driver.engine.get_screen_size()
        report.set(
            "hardware_scaling",
            (
                logical_size[0] >= game_display_size[0]
                and logical_size[1] >= game_display_size[1]
                and (
                    logical_size[0] == game_display_size[0]
                    or logical_size[1] == game_display_size[1]
                )
            ),
            f"logical_display={logical_size}; game={game_display_size}",
        )
        try:
            display_vsync = driver.engine.pygame.display.is_vsync()
        except Exception as exc:
            display_vsync = f"unknown ({type(exc).__name__}: {exc})"
        try:
            display_refresh = (
                driver.engine.pygame.display.get_current_refresh_rate()
            )
        except Exception as exc:
            display_refresh = f"unknown ({type(exc).__name__}: {exc})"
        report.set(
            "frame_pacing",
            os.environ.get("LT_PRECISE_FRAME_PACING") != "1",
            "single 60 FPS limiter using sleeping pygame Clock.tick; "
            f"vsync={display_vsync}; refresh={display_refresh}",
        )
        game = game_state.start_game()
        report.set("game_state_created", True, type(game).__name__)
        report.set("game_loop_started", True, title)
        report.flush()
        driver.run(game)
        report.set("game_loop_returned", True, "normal return")
        report.flush()
    except SystemExit as exc:
        report.set("clean_exit", True, repr(exc))
        report.flush()
    except BaseException as exc:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        report.set("fatal", False, detail)
        report.flush()
        logging.exception("LT Android phase 4 boot failed")
        print(REPORT_PREFIX + detail, flush=True)
        naming_screen = BASE_DIR / "sprites" / "NamingScreen.png"
        traceback_tail = detail.splitlines()[-12:]
        fatal_detail = "\n".join(
            [
                f"Error: {type(exc).__name__}: {exc}",
                f"NamingScreen: exists={naming_screen.is_file()} "
                f"bytes={naming_screen.stat().st_size if naming_screen.is_file() else 0}",
                f"Base: {BASE_DIR}",
                f"CWD: {Path.cwd()}",
                "Traceback tail:",
                *traceback_tail,
            ]
        )
        show_fatal_screen(fatal_detail)


if __name__ == "__main__":
    run()
