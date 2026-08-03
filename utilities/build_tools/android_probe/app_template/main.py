from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

import pygame


BASE_DIR = Path(__file__).resolve().parent
REPORT_PREFIX = "LT_ANDROID_PROBE "
LOG_INTERVAL_SECONDS = 2.0


def app_storage_dir() -> Path:
    try:
        from android.storage import app_storage_path

        root = Path(app_storage_path())
    except Exception:
        root = BASE_DIR / "probe_user_data"
    root.mkdir(parents=True, exist_ok=True)
    return root


class ProbeReport:
    def __init__(self) -> None:
        self.path = app_storage_dir() / "lt_android_probe_report.json"
        self.checks: dict[str, dict[str, object]] = {}
        self.active_fingers: dict[int, tuple[float, float]] = {}
        self.max_simultaneous_fingers = 0
        self.started_at = time.time()
        self.last_log_at = 0.0
        self.previous_run_loaded = False
        self._load_previous_run()

    def _load_previous_run(self) -> None:
        try:
            previous = json.loads(self.path.read_text(encoding="utf-8"))
            self.previous_run_loaded = bool(previous.get("checks"))
        except (OSError, ValueError, TypeError):
            self.previous_run_loaded = False

    def set(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks[name] = {
            "passed": bool(passed),
            "detail": detail,
        }
        self.persist()

    def touch_down(self, finger_id: int, x: float, y: float) -> None:
        self.active_fingers[finger_id] = (x, y)
        self.max_simultaneous_fingers = max(
            self.max_simultaneous_fingers, len(self.active_fingers)
        )
        self.set("finger_event", True, "FINGERDOWN received")
        self.set(
            "multi_touch",
            self.max_simultaneous_fingers >= 2,
            f"maximum simultaneous fingers: {self.max_simultaneous_fingers}",
        )

    def touch_move(self, finger_id: int, x: float, y: float) -> None:
        if finger_id in self.active_fingers:
            self.active_fingers[finger_id] = (x, y)

    def touch_up(self, finger_id: int) -> None:
        self.active_fingers.pop(finger_id, None)

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "python": sys.version,
            "pygame": pygame.version.ver,
            "platform": sys.platform,
            "android_argument": os.environ.get("ANDROID_ARGUMENT"),
            "android_private": os.environ.get("ANDROID_PRIVATE"),
            "started_at": self.started_at,
            "updated_at": time.time(),
            "previous_run_loaded": self.previous_run_loaded,
            "max_simultaneous_fingers": self.max_simultaneous_fingers,
            "checks": self.checks,
        }

    def persist(self) -> None:
        payload = self.payload()
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary_path.replace(self.path)
        now = time.monotonic()
        if now - self.last_log_at >= LOG_INTERVAL_SECONDS:
            print(REPORT_PREFIX + json.dumps(payload, sort_keys=True), flush=True)
            self.last_log_at = now


def run_startup_checks(report: ProbeReport) -> pygame.Surface:
    payload = json.loads((BASE_DIR / "probe_data.json").read_text(encoding="utf-8"))
    report.set("bundled_json", payload.get("probe") == "lt-android")

    module_path = BASE_DIR / "dynamic_probe.py"
    spec = importlib.util.spec_from_file_location("lt_android_dynamic_probe", module_path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to create import spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dynamic_value = module.probe_value()
    report.set(
        "dynamic_import",
        dynamic_value == payload["expected_dynamic_value"],
        dynamic_value,
    )

    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.font.init()

    flags = pygame.FULLSCREEN | getattr(pygame, "SCALED", 0)
    try:
        display = pygame.display.set_mode((480, 270), flags)
        report.set("scaled_display", True, str(display.get_size()))
    except pygame.error as exc:
        display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        report.set("scaled_display", False, f"fallback used: {exc}")
    pygame.display.set_caption("LT Android Probe")

    image = pygame.image.load(str(BASE_DIR / "probe.png")).convert_alpha()
    report.set("bundled_png", image.get_size() == (128, 128), str(image.get_size()))

    pixel_surface = pygame.Surface((16, 16), pygame.SRCALPHA, 32)
    pixels = pygame.PixelArray(pixel_surface)
    pixels[0, 0] = (255, 0, 255, 255)
    del pixels
    pixel_ok = pixel_surface.get_at((0, 0))[:3] == (255, 0, 255)
    report.set("pixel_array", pixel_ok)

    blend_surface = pygame.Surface((16, 16), pygame.SRCALPHA, 32)
    blend_surface.fill((16, 32, 64, 255))
    blend_surface.blit(
        pixel_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD
    )
    report.set("rgba_blend", blend_surface.get_at((0, 0))[0] > 16)

    font = pygame.font.Font(None, 28)
    rendered = font.render("LT Android", True, (255, 255, 255))
    report.set("font", rendered.get_width() > 0)

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        sound = pygame.mixer.Sound(str(BASE_DIR / "probe.ogg"))
        channel = sound.play()
        report.set("ogg_mixer", channel is not None, "bundled OGG loaded and played")
    except Exception as exc:
        report.set("ogg_mixer", False, repr(exc))

    report.set("private_storage", report.path.exists(), str(report.path))
    report.set(
        "previous_run_persisted",
        report.previous_run_loaded,
        "This becomes PASS after the second launch",
    )
    return display


def lifecycle_event_types() -> tuple[set[int], set[int]]:
    background = {
        value
        for value in (
            getattr(pygame, "APP_WILLENTERBACKGROUND", None),
            getattr(pygame, "APP_DIDENTERBACKGROUND", None),
        )
        if isinstance(value, int)
    }
    foreground = {
        value
        for value in (
            getattr(pygame, "APP_WILLENTERFOREGROUND", None),
            getattr(pygame, "APP_DIDENTERFOREGROUND", None),
        )
        if isinstance(value, int)
    }
    return background, foreground


def draw(display: pygame.Surface, report: ProbeReport) -> None:
    width, height = display.get_size()
    display.fill((13, 18, 28))
    title_font = pygame.font.Font(None, max(28, height // 12))
    body_font = pygame.font.Font(None, max(18, height // 22))
    display.blit(title_font.render("LT Android pygame-ce probe", True, (240, 245, 255)), (16, 12))

    y = 12 + title_font.get_height() + 8
    for name in sorted(report.checks):
        item = report.checks[name]
        passed = bool(item["passed"])
        color = (80, 220, 130) if passed else (255, 190, 70)
        line = f"{'PASS' if passed else 'WAIT'}  {name}: {item['detail']}"
        display.blit(body_font.render(line[:110], True, color), (16, y))
        y += body_font.get_height() + 2

    for finger_id, (x, y_norm) in report.active_fingers.items():
        center = (int(x * width), int(y_norm * height))
        pygame.draw.circle(display, (80, 170, 255), center, max(20, height // 14), 5)
        label = body_font.render(str(finger_id), True, (255, 255, 255))
        display.blit(label, label.get_rect(center=center))

    footer = "Touch with two fingers; background and reopen; Back exits"
    display.blit(
        body_font.render(footer, True, (180, 195, 220)),
        (16, height - body_font.get_height() - 12),
    )
    pygame.display.flip()


def main() -> None:
    report = ProbeReport()
    try:
        display = run_startup_checks(report)
        clock = pygame.time.Clock()
        background_events, foreground_events = lifecycle_event_types()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.FINGERDOWN:
                    report.touch_down(event.finger_id, event.x, event.y)
                elif event.type == pygame.FINGERMOTION:
                    report.touch_move(event.finger_id, event.x, event.y)
                elif event.type == pygame.FINGERUP:
                    report.touch_up(event.finger_id)
                elif event.type in background_events:
                    report.set("lifecycle_background", True, pygame.event.event_name(event.type))
                    if pygame.mixer.get_init():
                        pygame.mixer.pause()
                elif event.type in foreground_events:
                    report.set("lifecycle_foreground", True, pygame.event.event_name(event.type))
                    if pygame.mixer.get_init():
                        pygame.mixer.unpause()
                elif event.type == pygame.KEYDOWN and event.key in {
                    pygame.K_ESCAPE,
                    getattr(pygame, "K_AC_BACK", pygame.K_ESCAPE),
                }:
                    report.set("android_back", True, str(event.key))
                    running = False
            draw(display, report)
            clock.tick(60)
    except BaseException as exc:
        report.set("fatal", False, repr(exc))
        print(REPORT_PREFIX + traceback.format_exc(), flush=True)
        raise
    finally:
        report.persist()
        pygame.quit()


if __name__ == "__main__":
    main()

