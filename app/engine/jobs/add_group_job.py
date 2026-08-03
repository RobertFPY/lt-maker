from __future__ import annotations

import time
from typing import Callable, Iterable, Optional

from app.engine.performance import RUNTIME_PROFILER


class AddGroupJob:
    """Place a unit group in bounded event-update slices."""

    FRAME_BUDGET_NS = 4_000_000
    COMPLETE = 'COMPLETE'
    FAILED = 'FAILED'

    def __init__(self, unit_nids: Iterable[str], place_unit: Callable[[str], None]) -> None:
        self.unit_nids = list(unit_nids)
        self.place_unit = place_unit
        self.index = 0
        self.state = 'PLACE_UNIT_BATCH'
        self.error: Optional[Exception] = None

    @property
    def is_finished(self) -> bool:
        return self.state in (self.COMPLETE, self.FAILED)

    @property
    def failed(self) -> bool:
        return self.state == self.FAILED

    def update(self, should_skip: bool) -> bool:
        deadline_ns = (2**63 - 1 if should_skip
                       else time.perf_counter_ns() + self.FRAME_BUDGET_NS)
        return self.step(deadline_ns)

    def step(self, deadline_ns: int) -> bool:
        while not self.is_finished and time.perf_counter_ns() < deadline_ns:
            try:
                self.run_one_operation()
            except Exception as error:
                self.error = error
                self.state = self.FAILED
        return self.is_finished

    def run_one_operation(self) -> None:
        if self.index >= len(self.unit_nids):
            self.state = self.COMPLETE
            return
        unit_nid = self.unit_nids[self.index]
        self.index += 1
        with RUNTIME_PROFILER.section('add_group.place_unit'):
            self.place_unit(unit_nid)
        if self.index >= len(self.unit_nids):
            self.state = self.COMPLETE
