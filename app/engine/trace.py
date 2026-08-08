"""Deterministic logical tracing used only by recovery tests.

The recorder is deliberately opt-in.  It owns no engine globals and performs
no I/O; P1-T03 is responsible for reference fixture generation.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
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
    if isinstance(value, Enum):
        return getattr(value, 'nid', value.value if isinstance(value.value, (str, int, float, bool)) else value.name)
    from app.engine.roam.roam_info import RoamInfo
    if isinstance(value, RoamInfo):
        return {'roam': value.roam, 'roam_unit_nid': value.roam_unit_nid}
    if isinstance(value, Mapping):
        return {_mapping_key(key): normalize(entry)
                for key, entry in sorted(value.items(), key=lambda pair: _mapping_key(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize(entry) for entry in value]
    if isinstance(value, (set, frozenset)):
        normalized = [normalize(entry) for entry in value]
        return sorted(normalized, key=canonical_json)
    raise TraceNormalizationError('unsupported trace value: %s' % type(value).__name__)


def _mapping_key(value: Any) -> str:
    normalized = normalize(value)
    if isinstance(normalized, str):
        return normalized
    return json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def canonical_json(value: Any) -> str:
    return json.dumps(normalize(value), ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def _first_difference(expected: Any, actual: Any, path: str = '') -> Optional[tuple[str, Any, Any]]:
    if type(expected) is not type(actual):
        return path or '/', expected, actual
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            pointer = (path + '/' + str(key).replace('~', '~0').replace('/', '~1'))
            if key not in expected or key not in actual:
                return pointer, expected.get(key, '<missing>'), actual.get(key, '<missing>')
            difference = _first_difference(expected[key], actual[key], pointer)
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return path + '/length', len(expected), len(actual)
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = _first_difference(left, right, path + '/' + str(index))
            if difference:
                return difference
        return None
    if expected != actual:
        return path or '/', expected, actual
    return None


def compare_records(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare logical trace identity while ignoring only approved provenance."""
    if len(expected) != len(actual):
        raise TraceComparisonError('checkpoint count differs: %d != %d' % (len(expected), len(actual)))
    provenance = {'runner_revision', 'platform_profile'}
    required_header = ('kind', 'schema_version', 'scenario_id', 'input_fixture_id',
                       'reference_revision', 'serializer')
    if not expected or not actual:
        raise TraceComparisonError('trace header missing')
    for field in required_header:
        if field not in expected[0] or field not in actual[0]:
            raise TraceComparisonError('required header field missing: /%s' % field)
    for index, (expected_record, actual_record) in enumerate(zip(expected, actual)):
        if index == 0:
            expected_record = {k: v for k, v in expected_record.items() if k not in provenance}
            actual_record = {k: v for k, v in actual_record.items() if k not in provenance}
        difference = _first_difference(normalize(expected_record), normalize(actual_record))
        if difference:
            path, left, right = difference
            context = ({'checkpoint_id': expected_record.get('checkpoint_id'),
                        'context': expected_record.get('context')} if index else
                       {'scenario_id': expected[0].get('scenario_id')})
            raise TraceComparisonError('record %d %s expected=%r actual=%r near=%r' %
                                       (index, path, left, right, context))
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
        self._uid_refs: dict[int, str] = {}
        self._uid_objects: dict[int, Any] = {}
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
        uid = getattr(value, 'uid', None)
        if isinstance(uid, int):
            self._uid_refs[uid] = local_id
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

    def source(self, value: Any) -> Any:
        if isinstance(value, int) and value not in self._uid_refs and value in self._uid_objects:
            source_obj = self._uid_objects[value]
            self.reference(source_obj, 'skill', 'skill_sources/%s' % (_nid(source_obj) or 'skill'))
        if isinstance(value, int) and value in self._uid_refs:
            return {'ref': self._uid_refs[value]}
        return normalize(value)


def _unit_snapshot(unit: Any, graph: _ObjectGraph) -> dict[str, Any]:
    nid = str(getattr(unit, 'nid'))
    item_refs = [graph.reference(item, 'item', 'units/%s/items/%d' % (nid, idx))
                 for idx, item in enumerate(getattr(unit, 'items', []) or [])]
    skill_wrappers = getattr(unit, '_skills', None)
    if skill_wrappers is not None:
        skill_refs = []
        for idx, wrapper in enumerate(skill_wrappers):
            ref = graph.reference(wrapper.get(), 'skill', 'units/%s/skills/%d' % (nid, idx))
            skill_refs.append({'ref': ref, 'source': graph.source(wrapper.source),
                               'source_type': normalize(wrapper.source_type)})
    else:
        skill_refs = [graph.reference(skill, 'skill', 'units/%s/skills/%d' % (nid, idx))
                      for idx, skill in enumerate(getattr(unit, 'skills', []) or [])]
    action_names = ('finished', 'attacked', 'traded', 'moved', 'rescued', 'dropped', 'taken', 'given')
    action_state = dict(zip(action_names, getattr(unit, 'get_action_state', lambda: (None,) * 8)()))
    return normalize({
        'nid': nid, 'team': _nid(getattr(unit, 'team', None)), 'party': _nid(getattr(unit, 'party', None)),
        'class': _nid(getattr(unit, 'klass', getattr(unit, 'class_nid', None))),
        'level': getattr(unit, 'level', None), 'exp': getattr(unit, 'exp', None),
        'position': getattr(unit, 'position', None), 'hp': getattr(unit, 'current_hp', None),
        'mana': getattr(unit, 'current_mana', None), 'fatigue': getattr(unit, 'current_fatigue', None),
        'guard': getattr(unit, 'current_guard_gauge', None),
        'action_state': action_state, 'dead': getattr(unit, 'dead', None),
        'traveler': _nid(getattr(unit, 'traveler', None)),
        'lead_unit': bool(getattr(unit, 'lead_unit', False)),
        'built_guard': bool(getattr(unit, 'built_guard', False)),
        'strike_partner': _nid(getattr(unit, 'strike_partner', None)),
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


def _board_snapshot(game: Any, board: Any, tilemap: Any, graph: _ObjectGraph,
                    active_team: Any) -> dict[str, Any]:
    width = getattr(tilemap, 'width', getattr(board, 'width', 0)) or 0
    height = getattr(tilemap, 'height', getattr(board, 'height', 0)) or 0
    positions = [(x, y) for x in range(width) for y in range(height)]
    tile_grid = [[x, y, tilemap.get_terrain((x, y)), tilemap.get_layer((x, y))]
                 for x, y in positions] if tilemap and hasattr(tilemap, 'get_terrain') else []
    occupancy = []
    unit_grid = getattr(board, 'unit_grid', None)
    if unit_grid is not None:
        for x, y in positions:
            occupancy.extend([[x, y, _nid(unit)] for unit in unit_grid.get((x, y)) or []])

    aura_sources = []
    aura_grid = getattr(board, 'aura_grid', None)
    if aura_grid is not None:
        for x, y in positions:
            for uid, target in sorted(aura_grid.get((x, y)) or [], key=lambda entry: (entry[0], entry[1])):
                source = graph.source(uid)
                if not isinstance(source, dict) or 'ref' not in source:
                    raise TraceNormalizationError('unmapped aura skill uid')
                aura_sources.append([x, y, source['ref']])

    fog_visible = []
    in_vision = getattr(board, 'in_vision', None)
    if callable(in_vision):
        fog_visible = [[x, y] for x, y in positions if in_vision((x, y), active_team)]

    regions = []
    region_values = getattr(getattr(game, 'level', None), 'regions', None)
    if region_values is None:
        region_values = (getattr(game, 'region_registry', {}) or {}).values()
    for region in sorted(region_values or [],
                         key=lambda value: (tuple(value.position or (-1, -1)), str(value.nid))):
        regions.append(normalize({'nid': region.nid, 'type': region.region_type,
                                  'position': region.position, 'size': region.size,
                                  'sub_nid': region.sub_nid, 'time_left': region.time_left,
                                  'condition': region.condition, 'only_once': region.only_once,
                                  'interrupt_move': region.interrupt_move, 'data': getattr(region, 'data', {})}))
    return {'tilemap_nid': _nid(tilemap), 'dimensions': [width, height],
            'tile_grid_hash': canonical_hash({'dimensions': [width, height], 'tiles': tile_grid}),
            'occupancy': occupancy,
            'aura_sources': aura_sources, 'fog_visible': fog_visible,
            'fog_visited': sorted([list(pos) for pos in getattr(board, 'previously_visited_tiles', set())]),
            'bounds': getattr(board, 'bounds', None), 'regions': regions}


def capture_logical_state(game: Any) -> dict[str, Any]:
    from app.utilities import static_random
    graph = _ObjectGraph()
    skill_registry = getattr(game, 'skill_registry', {}) or {}
    for skill in skill_registry.values():
        uid = getattr(skill, 'uid', None)
        if isinstance(uid, int):
            graph._uid_objects[uid] = skill
    state_machine = getattr(game, 'state', None)
    units = sorted(getattr(game, 'units', []) or [], key=lambda unit: str(getattr(unit, 'nid', '')))
    level = getattr(game, 'level', None)
    board = getattr(game, 'board', None)
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
    active_team = getattr(getattr(game, 'phase', None), 'get_current', lambda: None)()
    return normalize({
        'state_stack': {'active': [getattr(state, 'name', None) for state in getattr(state_machine, 'state', []) or []],
                        'pending': list(getattr(state_machine, 'temp_state', []) or [])},
        'world': {'mode': getattr(state_machine, 'current', lambda: None)(),
                  'level_nid': _nid(level),
                  'overworld_nid': _nid(getattr(game, 'overworld_controller', None)),
                  'current_party': _nid(getattr(game, 'current_party', None))},
        'turn': {'turncount': getattr(game, 'turncount', None),
                 'phase': active_team, 'active_team': active_team},
        'object_graph': {'objects': graph.objects}, 'units': [_unit_snapshot(unit, graph) for unit in units],
        'variables': {'game': _dict(getattr(game, 'game_vars', None)), 'level': _dict(getattr(game, 'level_vars', None))},
        'rng': {'seed': static_random.get_seed(), 'combat_state': static_random.get_combat_random_state(),
                'growth_state': static_random.get_growth_random_state(),
                'other_state': static_random.get_other_random_state()},
        'board': _board_snapshot(game, board, tilemap, graph, active_team),
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
    def __init__(self, scenario_id: str, game: Any = None, hook_observer: HookObserver = None,
                 action_registry: SemanticRegistry = None,
                 playback_registry: SemanticRegistry = None) -> None:
        self.scenario_id = scenario_id
        self.game = game
        self.hook_observer = hook_observer
        self.action_registry = action_registry or SemanticRegistry()
        self.playback_registry = playback_registry or SemanticRegistry()
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
        """Capture a checkpoint.

        Raw action/playback objects use their injected registries. Callers with
        reviewed primitive records must use ``normalized_actions`` or
        ``normalized_combat_playback`` explicitly.
        """
        state = capture_logical_state(game)
        pending = state['state_stack']['pending']
        if pending and (pending_exception_id is None or list(allowed_pending or []) != pending):
            raise TraceInvariantError('terminal checkpoint has pending state transitions')
        delta = dict(delta or {})
        semantic_delta = {
            'actions': [self.action_registry.normalize(value) for value in delta.pop('actions', [])],
            'combat_playback': [self.playback_registry.normalize(value)
                                for value in delta.pop('combat_playback', [])],
            'triggered_events': normalize(delta.pop('triggered_events', [])),
            'hook_calls': normalize(delta.pop('hook_calls', [])),
        }
        for explicit_key, target_key in (('normalized_actions', 'actions'),
                                         ('normalized_combat_playback', 'combat_playback')):
            for record in delta.pop(explicit_key, []):
                if not isinstance(record, Mapping):
                    raise TraceNormalizationError('%s requires mapping records' % explicit_key)
                semantic_delta[target_key].append(normalize(record))
        if delta:
            raise TraceNormalizationError('unknown semantic delta fields: %s' % sorted(delta))
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
