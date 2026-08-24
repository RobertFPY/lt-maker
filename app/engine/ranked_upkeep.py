"""Temporary per-upkeep planner for mutually exclusive ranked status skills."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass
class RankedUpkeepRequest:
    source_unit: Any
    component: Any
    group: str
    rank: int
    targets: list[Any]
    max_targets: Optional[int] = None
    target_bands: Optional[list[list[Any]]] = None


class RankedUpkeepContext:
    """Pre-computes target claims so rank is independent of upkeep pop order."""
    def __init__(self, sources: Iterable[Any], all_units: Iterable[Any]):
        self.sources = list(sources)
        self.all_units = list(all_units)
        self._source_order = {id(unit): index for index, unit in enumerate(self.sources)}
        self._assignments: dict[tuple[int, int], list[Any]] = {}

    @staticmethod
    def _effect_group(unit: Any) -> Iterable[str]:
        for skill in getattr(unit, 'skills', ()):
            for component in getattr(skill, 'components', ()):
                if getattr(component, 'nid', None) == 'exclusive_upkeep_effect':
                    value = getattr(component, 'value', {}) or {}
                    group = value.get('group') if isinstance(value, dict) else None
                    if group:
                        yield group

    def _claimed_targets(self) -> dict[tuple[str, str], set[int]]:
        claimed: dict[tuple[str, str], set[int]] = {}
        for source in self.sources:
            team = getattr(source, 'team', None)
            for target in self.all_units:
                for group in self._effect_group(target):
                    claimed.setdefault((team, group), set()).add(id(target))
        return claimed

    def plan(self, requests: Optional[Iterable[RankedUpkeepRequest]] = None) -> None:
        if requests is None:
            requests = self._discover_requests()
        claimed = self._claimed_targets()
        ordered = sorted(
            requests,
            key=lambda request: (-request.rank, self._source_order.get(id(request.source_unit), 10 ** 6),
                                 getattr(request.source_unit, 'nid', ''), id(request.component)),
        )
        self._assignments.clear()
        for request in ordered:
            key = (getattr(request.source_unit, 'team', None), request.group)
            already_claimed = claimed.setdefault(key, set())
            if request.target_bands is None:
                available = [target for target in request.targets if id(target) not in already_claimed]
                selected = available if request.max_targets is None else available[:request.max_targets]
            else:
                selected = []
                for band in request.target_bands:
                    selected = [target for target in band if id(target) not in already_claimed]
                    if selected:
                        break
            self._assignments[(id(request.source_unit), id(request.component))] = selected
            already_claimed.update(id(target) for target in selected)

    def _discover_requests(self) -> list[RankedUpkeepRequest]:
        from app.engine import skill_system

        requests = []
        for unit in self.sources:
            for skill in getattr(unit, 'skills', ()):
                for component in getattr(skill, 'components', ()):
                    if not getattr(component, 'ignore_conditional', False) and \
                            not skill_system.condition(skill, unit):
                        continue
                    get_request = getattr(component, 'ranked_upkeep_request', None)
                    if get_request:
                        request = get_request(unit)
                        if request and request.group:
                            requests.append(request)
        return requests

    def targets_for(self, source_unit: Any, component: Any) -> list[Any]:
        return list(self._assignments.get((id(source_unit), id(component)), ()))


_context: Optional[RankedUpkeepContext] = None


def begin_upkeep(sources: Iterable[Any], all_units: Iterable[Any]) -> RankedUpkeepContext:
    global _context
    _context = RankedUpkeepContext(sources, all_units)
    _context.plan()
    return _context


def current() -> Optional[RankedUpkeepContext]:
    return _context


def end_upkeep() -> None:
    global _context
    _context = None
