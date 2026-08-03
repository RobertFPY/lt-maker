"""Low-overhead runtime performance sampling for Android builds.

The profiler is deliberately opt-in.  It aggregates frames in memory and only
emits one log line per interval (or a slow-frame record), so turning it on does
not recreate the per-frame logging problem it is intended to diagnose.
"""

from __future__ import annotations

import collections
import gc
import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Dict, Iterator, Mapping, Optional

from app.engine.android_runtime import is_android_runtime


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() not in ("", "0", "false", "no")


class RuntimeProfiler:
    """Collect frame-stage timings without allocating a log record per frame."""

    def __init__(self) -> None:
        self.enabled = is_android_runtime() and _env_flag("LT_ANDROID_PROFILE")
        self.interval_seconds = float(os.environ.get("LT_PROFILE_INTERVAL", "5"))
        self.slow_frame_ms = float(os.environ.get("LT_PROFILE_SLOW_FRAME_MS", "100"))
        self._lock = threading.Lock()
        self._frame_started = 0.0
        self._frame_stages: Dict[str, float] = {}
        self._frames: collections.deque[float] = collections.deque(maxlen=300)
        self._stage_totals: collections.Counter[str] = collections.Counter()
        self._stage_samples: Dict[str, collections.deque[float]] = {}
        self._event_counts: collections.Counter[str] = collections.Counter()
        self._last_report = time.monotonic()
        self._gc_started = 0
        self._gc_finished = 0
        self._last_counters: Mapping[str, object] = {}
        if self.enabled:
            gc.callbacks.append(self._on_gc)

    def _on_gc(self, phase: str, info: Mapping[str, int]) -> None:
        if phase == "start":
            self._gc_started += 1
        elif phase == "stop":
            self._gc_finished += 1

    def begin_frame(self) -> None:
        if not self.enabled:
            return
        self._frame_started = time.perf_counter()
        self._frame_stages = {}

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            self._frame_stages[name] = self._frame_stages.get(name, 0.0) + elapsed

    def record(self, name: str, elapsed_ms: float) -> None:
        """Record work outside the game loop, such as decoding or save I/O."""
        if self.enabled:
            logging.warning("PERF %s=%.1fms", name, elapsed_ms)

    def count(self, name: str, amount: int = 1) -> None:
        """Count a hot-path event for the next aggregate report.

        This deliberately avoids constructing a logging record per event.  It
        is suitable for diagnostic metadata such as selected combat frames.
        """
        if self.enabled:
            self._event_counts[name] += amount

    def finish_frame(self, counters: Optional[Mapping[str, object]] = None) -> None:
        if not self.enabled:
            return
        frame_ms = (time.perf_counter() - self._frame_started) * 1000.0
        with self._lock:
            self._frames.append(frame_ms)
            self._stage_totals.update(self._frame_stages)
            for name, elapsed in self._frame_stages.items():
                self._stage_samples.setdefault(
                    name, collections.deque(maxlen=300)
                ).append(elapsed)
            if counters:
                self._last_counters = counters
            now = time.monotonic()
            report_due = now - self._last_report >= self.interval_seconds
            if frame_ms >= self.slow_frame_ms:
                stages = ", ".join(
                    f"{name}={elapsed:.1f}" for name, elapsed in sorted(self._frame_stages.items())
                )
                logging.warning("PERF slow-frame total=%.1fms %s", frame_ms, stages)
            if not report_due or not self._frames:
                return
            frames = sorted(self._frames)
            p95 = frames[min(len(frames) - 1, int(len(frames) * 0.95))]
            average = sum(frames) / len(frames)
            stage_average = ", ".join(
                f"{name}=avg:{elapsed / len(frames):.1f}/p95:{self._percentile(self._stage_samples[name], 0.95):.1f}"
                for name, elapsed in sorted(self._stage_totals.items())
            )
            counters_text = " ".join(f"{key}={value}" for key, value in self._last_counters.items())
            event_text = " ".join(
                f"{name}={count}" for name, count in sorted(self._event_counts.items())
            )
            logging.warning(
                "PERF %d frames avg=%.1fms p95=%.1fms max=%.1fms gc=%d/%d %s %s %s",
                len(frames), average, p95, frames[-1], self._gc_started, self._gc_finished,
                stage_average, event_text, counters_text,
            )
            self._frames.clear()
            self._stage_totals.clear()
            self._stage_samples.clear()
            self._event_counts.clear()
            self._gc_started = 0
            self._gc_finished = 0
            self._last_report = now

    @staticmethod
    def _percentile(samples: collections.deque[float], percentile: float) -> float:
        ordered = sorted(samples)
        return ordered[min(len(ordered) - 1, int(len(ordered) * percentile))]


RUNTIME_PROFILER = RuntimeProfiler()
