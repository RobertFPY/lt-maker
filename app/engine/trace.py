"""Deterministic logical tracing used only by recovery tests.

The recorder is deliberately opt-in.  It owns no engine globals and performs
no I/O; P1-T03 is responsible for reference fixture generation.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable, Mapping, Optional


class TraceNormalizationError(TypeError):
    pass


class TraceInvariantError(RuntimeError):
    pass


class TraceComparisonError(AssertionError):
    pass


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [normalize(entry) for entry in value]
    if isinstance(value, (set, frozenset)):
        normalized = [normalize(entry) for entry in value]
        return sorted(normalized, key=canonical_json)
    raise TraceNormalizationError('unsupported trace value: %s' % type(value).__name__)


def canonical_json(value: Any) -> str:
    return json.dumps(normalize(value), ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def compare_records(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strict in-memory comparator; P1-T03 supplies reviewed fixture files."""
    if len(expected) != len(actual):
        raise TraceComparisonError('checkpoint count differs: %d != %d' % (len(expected), len(actual)))
    provenance = {'runner_revision', 'platform_profile'}
    for index, (expected_record, actual_record) in enumerate(zip(expected, actual)):
        if index == 0:
            expected_record = {k: v for k, v in expected_record.items() if k not in provenance}
            actual_record = {k: v for k, v in actual_record.items() if k not in provenance}
        if canonical_json(expected_record) != canonical_json(actual_record):
            raise TraceComparisonError('first trace difference at record %d' % index)
    return actual


def _nid(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return getattr(value, 'nid', None)


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return dict(value) if hasattr(value, 'items') else {}


class _ObjectGraph:
    def __init__(self) -> None:
        self._refs: dict[int, str] = {}
        self.objects: list[dict[str, Any]] = []

    def reference(self, value: Any, kind: str, path: str) -> Optional[str]:
        if value is None:
            return None
        key = id(value)  # capture-only deduplication; never serialized
        if key in self._refs:
            return self._refs[key]
        discriminator = str(_nid(value) or kind)
        local_id = '%s@%s@%s' % (kind, path, discriminator)
        self._refs[key] = local_id
        record = {'local_id': local_id, 'kind': kind, 'nid': _nid(value),
                  'logical_fields': {}, 'references': {}}
        self.objects.append(record)
        record['logical_fields'], record['references'] = self._fields(value, kind, path)
        return local_id

    def _fields(self, value: Any, kind: str, path: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if kind == 'item':
            fields = {'owner_nid': getattr(value, 'owner_nid', None),
                      'droppable': getattr(value, 'droppable', None),
                      'data': getattr(value, 'data', {})}
            fields['components'] = [(component.nid, component.value)
                                    for component in getattr(value, 'components', [])]
            parent = getattr(value, 'parent_item', None)
            refs = {'parent_item': self.reference(parent, 'item', path + '/parent'),
                    'subitems': [self.reference(item, 'item', path + '/subitems/%d' % idx)
                                 for idx, item in enumerate(getattr(value, 'subitems', []) or [])],
                    'command_item': self.reference(getattr(value, 'command_item', None), 'item', path + '/command')}
            return normalize(fields), refs
        if kind == 'skill':
            fields = {'owner_nid': getattr(value, 'owner_nid', None),
                      'initiator_nid': getattr(value, 'initiator_nid', None),
                      'data': getattr(value, 'data', {}),
                      'components': [(component.nid, component.value)
                                     for component in getattr(value, 'components', [])]}
            return normalize(fields), {'parent_skill': self.reference(getattr(value, 'parent_skill', None), 'skill', path + '/parent'),
                                        'subskill': self.reference(getattr(value, 'subskill', None), 'skill', path + '/subskill')}
        if kind == 'event':
            return {}, {}
        raise TraceNormalizationError('unknown graph object kind: %s' % kind)


def _unit_snapshot(unit: Any, graph: _ObjectGraph) -> dict[str, Any]:
    nid = str(getattr(unit, 'nid'))
    item_refs = [graph.reference(item, 'item', 'units/%s/items/%d' % (nid, idx))
                 for idx, item in enumerate(getattr(unit, 'items', []) or [])]
    skill_wrappers = getattr(unit, '_skills', None)
    if skill_wrappers is not None:
        skill_refs = [{'ref': graph.reference(wrapper.get(), 'skill', 'units/%s/skills/%d' % (nid, idx)),
                       'source': normalize(wrapper.source), 'source_type': normalize(wrapper.source_type)}
                      for idx, wrapper in enumerate(skill_wrappers)]
    else:
        skill_refs = [graph.reference(skill, 'skill', 'units/%s/skills/%d' % (nid, idx))
                      for idx, skill in enumerate(getattr(unit, 'skills', []) or [])]
    return normalize({
        'nid': nid, 'team': _nid(getattr(unit, 'team', None)), 'party': _nid(getattr(unit, 'party', None)),
        'class': _nid(getattr(unit, 'klass', getattr(unit, 'class_nid', None))),
        'level': getattr(unit, 'level', None), 'exp': getattr(unit, 'exp', None),
        'position': getattr(unit, 'position', None), 'hp': getattr(unit, 'current_hp', None),
        'mana': getattr(unit, 'current_mana', None), 'fatigue': getattr(unit, 'current_fatigue', None),
        'guard': getattr(unit, 'current_guard_gauge', None),
        'finished': getattr(unit, '_finished', getattr(unit, 'finished', None)), 'dead': getattr(unit, 'dead', None),
        'has_moved': getattr(unit, '_has_moved', getattr(unit, 'has_moved', None)), 'has_attacked': getattr(unit, '_has_attacked', getattr(unit, 'has_attacked', None)),
        'traveler': _nid(getattr(unit, 'traveler', None)), 'lead_unit': _nid(getattr(unit, 'lead_unit', None)),
        'stats': _dict(getattr(unit, 'stats', None)), 'growths': _dict(getattr(unit, 'growths', None)),
        'growth_points': _dict(getattr(unit, 'growth_points', None)), 'wexp': _dict(getattr(unit, 'wexp', None)),
        'inventory': item_refs, 'skills': skill_refs,
        'equipped_weapon': graph.reference(getattr(unit, 'equipped_weapon', None), 'item',
                                             'units/%s/equipped_weapon' % nid),
        'equipped_accessory': graph.reference(getattr(unit, 'equipped_accessory', None), 'item',
                                                'units/%s/equipped_accessory' % nid),
    })


def _event_frame(event: Any, graph: _ObjectGraph, role: str, ordinal: int) -> dict[str, Any]:
    processor = getattr(event, 'processor', None)
    ordinal = getattr(processor, 'command_pointer', None)
    command_nid = None
    commands = getattr(processor, 'commands', None)
    if isinstance(ordinal, int) and commands and 0 <= ordinal < len(commands):
        command_nid = getattr(commands[ordinal], 'nid', None)
    return {'event_ref': graph.reference(event, 'event', 'events/%s/%d' % (role, ordinal)),
            'event_nid': getattr(event, 'nid', None),
            'trigger_nid': _nid(getattr(event, 'trigger', None)), 'role': role,
            'processor': {'command_ordinal': ordinal, 'command_nid': command_nid},
            'caller_event_ref': getattr(event, '_trace_caller_event_ref', None),
            'caller_command_ordinal': getattr(event, '_trace_caller_command_ordinal', None)}


def capture_logical_state(game: Any) -> dict[str, Any]:
    from app.utilities import static_random
    graph = _ObjectGraph()
    state_machine = getattr(game, 'state', None)
    units = sorted(getattr(game, 'units', []) or [], key=lambda unit: str(getattr(unit, 'nid', '')))
    level = getattr(game, 'level', None)
    board = getattr(game, 'board', None)
    occupancy = []
    unit_grid = getattr(board, 'unit_grid', None)
    if unit_grid is not None:
        for pos in ((x, y) for x in range(getattr(board, 'width', 0)) for y in range(getattr(board, 'height', 0))):
            for unit in unit_grid.get(pos) or []:
                occupancy.append([pos[0], pos[1], _nid(unit)])
    else:
        for pos, unit in sorted(_dict(getattr(board, 'units', None)).items(), key=lambda entry: entry[0]):
            occupancy.append([pos[0], pos[1], _nid(unit)])

    events = getattr(game, 'events', None)
    active = getattr(game, '_trace_active_event', None)
    if active is None and state_machine and hasattr(state_machine, 'current_state'):
        active = getattr(state_machine.current_state(), 'event', None)
    frames = []
    seen = set()
    if active is not None:
        frames.append(_event_frame(active, graph, 'active', 0))
        seen.add(id(active))
    for ordinal, event in enumerate(reversed(getattr(events, 'event_stack', []) or [])):
        if id(event) not in seen:
            frames.append(_event_frame(event, graph, 'pending', ordinal))
            seen.add(id(event))
    for ordinal, event in enumerate(getattr(events, 'all_events', []) or []):
        if id(event) not in seen:
            frames.append(_event_frame(event, graph, 'retained', ordinal))
            seen.add(id(event))

    tilemap = getattr(level, 'tilemap', None)
    return normalize({
        'state_stack': {'active': [getattr(state, 'name', None) for state in getattr(state_machine, 'state', []) or []],
                        'pending': list(getattr(state_machine, 'temp_state', []) or [])},
        'world': {'mode': getattr(state_machine, 'current', lambda: None)(),
                  'level_nid': _nid(level),
                  'overworld_nid': _nid(getattr(game, 'overworld_controller', None)),
                  'current_party': _nid(getattr(game, 'current_party', None))},
        'turn': {'turncount': getattr(game, 'turncount', None),
                 'phase': getattr(getattr(game, 'phase', None), 'get_current', lambda: None)(),
                 'active_team': getattr(getattr(game, 'phase', None), 'get_current', lambda: None)()},
        'object_graph': {'objects': graph.objects}, 'units': [_unit_snapshot(unit, graph) for unit in units],
        'variables': {'game': _dict(getattr(game, 'game_vars', None)), 'level': _dict(getattr(game, 'level_vars', None))},
        'rng': {'seed': static_random.get_seed(), 'combat_state': static_random.get_combat_random_state(),
                'growth_state': static_random.r.growth_random.state,
                'other_state': static_random.get_other_random_state()},
        'board': {'tilemap_nid': _nid(tilemap), 'dimensions': [getattr(tilemap, 'width', None), getattr(tilemap, 'height', None)],
                  'tile_grid_hash': canonical_hash({'nid': _nid(tilemap), 'width': getattr(tilemap, 'width', None), 'height': getattr(tilemap, 'height', None)}),
                  'occupancy': occupancy, 'aura_sources': [],
                  'fog_visible': [], 'fog_visited': list(getattr(board, 'previously_visited_tiles', []) or []),
                  'bounds': getattr(board, 'bounds', None), 'regions': []},
        'events': {'already_triggered': sorted(getattr(game, 'already_triggered_events', []) or []),
                   'execution_stack': frames},
        'completion': {'save_restore': getattr(game, '_trace_save_restore', None),
                       'restart': getattr(game, '_trace_restart', None)},
    })


class HookObserver:
    def __init__(self, allowed: Iterable[tuple[str, str]]) -> None:
        self.allowed = set(allowed)
        self.calls: list[dict[str, Any]] = []

    def observe(self, dispatcher: str, hook_name: str, *, subjects: Mapping[str, Any],
                context: Mapping[str, Any], phase: str, gameplay_result: Any = None) -> None:
        if (dispatcher, hook_name) not in self.allowed:
            raise TraceNormalizationError('unmapped correctness-critical hook: %s.%s' % (dispatcher, hook_name))
        self.calls.append(normalize({'sequence': len(self.calls), 'dispatcher': dispatcher,
                                     'hook_name': hook_name, 'subjects': dict(subjects),
                                     'context': dict(context), 'lifecycle_phase': phase,
                                     'result': gameplay_result}))

    def wrap(self, dispatcher: str, hook_name: str, original: Callable[..., Any], *,
             subjects: Mapping[str, Any], phase: str, context: Optional[Mapping[str, Any]] = None) -> Callable[..., Any]:
        def observed(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            self.observe(dispatcher, hook_name, subjects=subjects, context=context or {},
                         phase=phase, gameplay_result=result)
            return result
        return observed


class SemanticRegistry:
    def __init__(self) -> None:
        self.adapters: dict[type, Callable[[Any], Mapping[str, Any]]] = {}

    def register(self, kind: type, adapter: Callable[[Any], Mapping[str, Any]]) -> None:
        self.adapters[kind] = adapter

    def normalize(self, value: Any) -> dict[str, Any]:
        adapter = self.adapters.get(type(value))
        if adapter is None:
            raise TraceNormalizationError('unmapped semantic type: %s' % type(value).__name__)
        return normalize(dict(adapter(value)))


class TraceRecorder:
    def __init__(self, scenario_id: str, game: Any = None, hook_observer: HookObserver = None) -> None:
        self.scenario_id = scenario_id
        self.game = game
        self.hook_observer = hook_observer
        self.records: list[dict[str, Any]] = []
        self.transition_commits: list[dict[str, Any]] = []
        self.header: Optional[dict[str, Any]] = None

    def begin(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        self.header = normalize({'kind': 'trace_header', 'schema_version': 1,
                                 'scenario_id': self.scenario_id,
                                 'serializer': 'logical-trace-v1', **dict(metadata)})
        return self.header

    def finish(self) -> list[dict[str, Any]]:
        if self.header is None:
            raise TraceInvariantError('trace header was not started')
        return [self.header, *self.records]

    def checkpoint(self, checkpoint_id: str, game: Any, *, context: Mapping[str, Any] = None,
                   delta: Mapping[str, Any] = None, pending_exception_id: str = None,
                   allowed_pending: Iterable[Any] = None) -> dict[str, Any]:
        state = capture_logical_state(game)
        pending = state['state_stack']['pending']
        if pending and (pending_exception_id is None or list(allowed_pending or []) != pending):
            raise TraceInvariantError('terminal checkpoint has pending state transitions')
        semantic_delta = {'actions': [], 'combat_playback': [], 'triggered_events': [], 'hook_calls': []}
        if delta:
            semantic_delta.update(delta)
        if self.hook_observer:
            semantic_delta['hook_calls'] = self.hook_observer.calls[:]
            self.hook_observer.calls.clear()
        normalized_context = dict(context or {})
        if pending_exception_id is not None:
            normalized_context['pending_exception_id'] = pending_exception_id
        record = {'kind': 'checkpoint', 'sequence': len(self.records), 'checkpoint_id': checkpoint_id,
                  'context': normalize(normalized_context), 'logical_state': state,
                  'semantic_delta': normalize(semantic_delta), 'state_hash': canonical_hash(state),
                  'delta_hash': canonical_hash(semantic_delta)}
        self.records.append(record)
        return record

    def save_payload_captured(self, game: Any, payload: Any) -> dict[str, Any]:
        return self.checkpoint('save.payload.captured', game,
                               context={'save_payload_hash': canonical_hash(payload)})

    def state_transition_committed(self, state_machine: Any) -> None:
        self.transition_commits.append({'active': [getattr(state, 'name', None) for state in state_machine.state],
                                        'pending': list(state_machine.temp_state)})
        if self.game is not None:
            self.checkpoint('state.transition.commit', self.game)
