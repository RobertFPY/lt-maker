"""Android-only runtime switches.

The engine source is shared by desktop and the Android package.  Keep every
mobile-specific optimisation behind these dynamic environment checks so a
desktop launch follows its existing code path exactly.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Callable, Iterable, NamedTuple, Optional, Protocol, Tuple


AndroidTouchConsumer = Callable[[str, Tuple[int, int], Tuple[int, int]], bool]
_touch_consumer: Optional[AndroidTouchConsumer] = None
_touch_passthrough_buttons: frozenset[str] = frozenset()


class AndroidVirtualControls(Protocol):
    """Small engine-facing contract for the Android bootstrap's touch overlay.

    The concrete controller lives in the Android runtime template, not in the
    shared engine.  Keeping this protocol narrow lets Options open its editor
    without importing Android-only bootstrap code on desktop.
    """

    def begin_editor(self) -> None:
        ...

    def cancel_editor(self) -> None:
        ...

    def is_editor_active(self) -> bool:
        ...

    def consume_editor_result(self) -> Optional[str]:
        ...


_virtual_controls: Optional[AndroidVirtualControls] = None


class AndroidDebugInputResult(NamedTuple):
    """A completed native debugger edit returned by the Java overlay."""

    request_id: str
    action: str
    value: str


def _flag(name: str) -> bool:
    return os.environ.get(name, "").lower() not in ("", "0", "false", "no")


def is_android_runtime() -> bool:
    """Whether the Python-for-Android bootstrap explicitly enabled mobile mode."""
    return _flag("LT_ANDROID_RUNTIME")


def is_android_render_optimization_enabled() -> bool:
    """Whether Android may use its render/update split and render caches."""
    return is_android_runtime() and _flag("LT_ANDROID_RENDER_OPT")


def register_android_virtual_controls(
        controls: Optional[AndroidVirtualControls]) -> None:
    """Expose the live Android touch overlay to engine states.

    Desktop never registers an implementation, so callers must handle a
    ``None`` result from :func:`get_android_virtual_controls`.
    """
    global _virtual_controls
    _virtual_controls = controls


def get_android_virtual_controls() -> Optional[AndroidVirtualControls]:
    return _virtual_controls


def set_android_touch_consumer(
        consumer: Optional[AndroidTouchConsumer], *,
        passthrough_buttons: Iterable[str] = ()) -> None:
    """Register the topmost engine UI that wants raw Android touch input.

    The Android bootstrap owns SDL finger events.  It calls this narrow bridge
    before translating those fingers into LT's virtual gamepad so overlays can
    receive taps without leaking a simultaneous gameplay button press.
    """
    global _touch_consumer, _touch_passthrough_buttons
    _touch_consumer = consumer
    _touch_passthrough_buttons = (
        frozenset(passthrough_buttons) if consumer else frozenset()
    )


def dispatch_android_touch(
        phase: str, position: Tuple[int, int], finger: Tuple[int, int]) -> bool:
    if not _touch_consumer:
        return False
    return bool(_touch_consumer(phase, position, finger))


def is_android_touch_consumer_active() -> bool:
    return _touch_consumer is not None


def get_android_touch_passthrough_buttons() -> frozenset[str]:
    """Virtual buttons that remain active while a raw-touch UI owns the screen."""
    return _touch_passthrough_buttons


def _get_android_debug_input_overlay() -> Optional[Any]:
    """Return the optional Java overlay without importing PyJNIus on desktop."""
    if not is_android_runtime():
        return None
    try:
        from jnius import autoclass
        return autoclass('org.lextalionis.android.LtDebugInputOverlay')
    except Exception:
        return None


def show_android_debug_input(request_id: str, value: str, *, multiline: bool,
                             numeric: bool) -> bool:
    """Open the system-font Android editor above the SDL canvas.

    A false return deliberately leaves callers on pygame's existing text-input
    fallback, which keeps the shared desktop runtime independent of PyJNIus.
    """
    overlay = _get_android_debug_input_overlay()
    if overlay is None:
        return False
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        return bool(overlay.show(activity, str(request_id), str(value), multiline, numeric))
    except Exception:
        return False


def poll_android_debug_input() -> Optional[AndroidDebugInputResult]:
    """Consume one Save/Cancel result from the Android editor, if present."""
    overlay = _get_android_debug_input_overlay()
    if overlay is None:
        return None
    try:
        payload = overlay.pollResult()
        if payload is None:
            return None
        request_id, action, encoded_value = str(payload).split('\t', 2)
        if action not in ('save', 'cancel'):
            return None
        value = base64.b64decode(encoded_value.encode('ascii'), validate=True).decode('utf-8')
        return AndroidDebugInputResult(request_id, action, value)
    except Exception:
        return None


def show_android_debug_input_error(request_id: str, message: str) -> None:
    """Display validation feedback without dismissing the native editor."""
    overlay = _get_android_debug_input_overlay()
    if overlay is None:
        return
    try:
        overlay.showError(str(request_id), str(message))
    except Exception:
        pass


def dismiss_android_debug_input(request_id: Optional[str] = None) -> None:
    """Remove the native editor during success, cancellation, or state cleanup."""
    overlay = _get_android_debug_input_overlay()
    if overlay is None:
        return
    try:
        if request_id is None:
            overlay.dismissAll()
        else:
            overlay.dismiss(str(request_id))
    except Exception:
        pass


def get_android_ime_inset_ratio() -> float:
    """Return the fraction of the Android window covered by the IME.

    ``pygame.display.get_surface()`` is a *logical* SDL canvas while Android
    reports the keyboard in physical pixels.  Returning a ratio prevents the
    two coordinate systems from being compared directly.  API 30 and newer
    use ``WindowInsets.Type.ime``; older devices fall back to the visible
    display frame.
    """
    if not is_android_runtime():
        return 0.0
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        view = activity.getWindow().getDecorView()
        root_height = max(1, int(view.getRootView().getHeight()))
        try:
            insets = view.getRootWindowInsets()
            inset_type = autoclass('android.view.WindowInsets$Type')
            ime_bottom = int(insets.getInsets(inset_type.ime()).bottom)
        except Exception:
            rect = autoclass('android.graphics.Rect')()
            view.getWindowVisibleDisplayFrame(rect)
            ime_bottom = max(0, root_height - int(rect.height()))
        ratio = ime_bottom / root_height
        # Small navigation/status-bar changes should not make the modal jump.
        return max(0.0, min(0.95, ratio)) if ratio >= 0.10 else 0.0
    except Exception:
        return 0.0


def get_android_visible_height(default_height: int) -> int:
    """Return the logical canvas height that remains above the Android IME."""
    return max(1, round(default_height * (1.0 - get_android_ime_inset_ratio())))
