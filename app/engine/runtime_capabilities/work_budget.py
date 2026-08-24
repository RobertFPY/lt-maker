"""Platform policy for explicitly approved off-world preparation only."""

from dataclasses import dataclass

from app.engine.android_runtime import is_android_runtime


_ANDROID_TILEMAP_PREPARE_DEADLINE_NS = 4_000_000


@dataclass(frozen=True)
class OffWorldWorkBudget:
    enabled: bool
    deadline_ns: int


def tilemap_prepare_budget() -> OffWorldWorkBudget:
    """Return the immutable policy for pending tilemap construction."""
    if is_android_runtime():
        return OffWorldWorkBudget(True, _ANDROID_TILEMAP_PREPARE_DEADLINE_NS)
    return OffWorldWorkBudget(False, 0)
