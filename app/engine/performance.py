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
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

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
        self._frame_started_ns = 0
        self._frame_thread_id: Optional[int] = None
        self._frame_stages: Dict[str, float] = {}
        self._frame_scopes: list[Dict[str, Any]] = []
        self._scope_stack: list[Dict[str, Any]] = []
        self._last_frame_scopes: Tuple[Dict[str, Any], ...] = ()
        self._next_scope_id = 0
        self._frames: collections.deque[float] = collections.deque(maxlen=300)
        self._frame_history: collections.deque[Dict[str, Any]] = collections.deque(
            maxlen=241)
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
        self._frame_thread_id = threading.get_ident()
        self._frame_started_ns = time.perf_counter_ns()
        self._frame_stages = {}
        self._frame_scopes = []
        self._scope_stack = []

    def latest_frame_scopes(self) -> Tuple[Dict[str, Any], ...]:
        """Return a read-only snapshot of the most recently completed frame.

        This intentionally exposes milliseconds for testability and log export,
        while collection uses nanoseconds to keep nested exclusive timings
        precise.
        """
        return tuple(dict(scope) for scope in self._last_frame_scopes)

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        # The frame scope stack is intentionally main-thread-only.  Android
        # preloads songs on a worker thread; allowing that worker to mutate
        # this shared stack corrupts nesting and can leave a main-thread scope
        # trying to pop an already-empty list.
        if (not self.enabled or
                threading.get_ident() != self._frame_thread_id):
            yield
            return
        parent = self._scope_stack[-1] if self._scope_stack else None
        scope = {
            'scope_id': self._next_scope_id,
            'name': name,
            'parent_scope_id': parent['scope_id'] if parent else None,
            'start_ns': time.perf_counter_ns(),
            'end_ns': 0,
            'inclusive_ns': 0,
            'exclusive_ns': 0,
            'child_inclusive_ns': 0,
            'invocation_count': 1,
            'thread_id': threading.get_ident(),
        }
        self._next_scope_id += 1
        self._frame_scopes.append(scope)
        self._scope_stack.append(scope)
        try:
            yield
        finally:
            scope['end_ns'] = time.perf_counter_ns()
            scope['inclusive_ns'] = scope['end_ns'] - scope['start_ns']
            scope['exclusive_ns'] = max(
                0, scope['inclusive_ns'] - scope['child_inclusive_ns'])
            self._scope_stack.pop()
            if parent:
                parent['child_inclusive_ns'] += scope['inclusive_ns']
            elapsed_ms = scope['inclusive_ns'] / 1_000_000.0
            self._frame_stages[name] = self._frame_stages.get(name, 0.0) + elapsed_ms

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
        frame_ms = (time.perf_counter_ns() - self._frame_started_ns) / 1_000_000.0
        with self._lock:
            completed_scopes = tuple({
                'scope_id': scope['scope_id'],
                'name': scope['name'],
                'parent_scope_id': scope['parent_scope_id'],
                'inclusive_ms': scope['inclusive_ns'] / 1_000_000.0,
                'exclusive_ms': scope['exclusive_ns'] / 1_000_000.0,
                'invocation_count': scope['invocation_count'],
                'thread_id': scope['thread_id'],
            } for scope in self._frame_scopes)
            self._last_frame_scopes = completed_scopes
            metadata = dict(counters or {})
            self._frame_history.append({
                'frame_ms': frame_ms,
                'scopes': completed_scopes,
                'metadata': metadata,
            })
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
                scopes = self._format_scope_tree(completed_scopes)
                metadata_text = " ".join(
                    f"{key}={value}" for key, value in sorted(metadata.items()))
                logging.warning(
                    "PERF slow-frame total=%.1fms scopes=%s metadata=%s",
                    frame_ms, scopes, metadata_text)
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

    @staticmethod
    def _format_scope_tree(scopes: Tuple[Dict[str, Any], ...]) -> str:
        """Make the slow-frame log actionable without emitting per-frame logs."""
        names = {scope['scope_id']: scope['name'] for scope in scopes}
        parents = {
            scope['scope_id']: scope['parent_scope_id'] for scope in scopes
        }
        return ", ".join(
            "%s=inc:%.1f/exc:%.1f" % (
                RuntimeProfiler._scope_path(scope, names, parents),
                scope['inclusive_ms'], scope['exclusive_ms'])
            for scope in scopes)

    @staticmethod
    def _scope_path(scope: Dict[str, Any], names: Mapping[int, str],
                    parents: Mapping[int, Optional[int]]) -> str:
        path = [scope['name']]
        parent_id = scope['parent_scope_id']
        while parent_id is not None:
            path.append(names[parent_id])
            parent_id = parents[parent_id]
        return '/'.join(reversed(path))


RUNTIME_PROFILER = RuntimeProfiler()
