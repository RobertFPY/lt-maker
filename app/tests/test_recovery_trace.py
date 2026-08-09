from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.engine.state_machine import StateMachine
from app.engine.trace import (
    HookObserver,
    TraceComparisonError,
    TraceInvariantError,
    TraceNormalizationError,
    TraceRecorder,
    SemanticRegistry,
    canonical_hash,
    compare_records,
    capture_logical_state,
    normalize,
)
from app.data.database.item_components import ItemComponent
from app.data.database.skill_components import SkillComponent
from app.engine.objects.item import ItemObject
from app.engine.objects.region import RegionObject
from app.engine.objects.skill import SkillObject
from app.engine.objects.tilemap import LayerObject, TileMapObject
from app.engine.objects.unit import UnitObject, UnitSkill
from app.engine.roam.roam_info import RoamInfo
from app.engine.source_type import SourceType
from app.events.regions import RegionType
from app.utilities import static_random
from app.utilities.data import Data
from app.utilities.grid import Grid


class _State:
    def __init__(self, name, machine):
        self.name = name
        self.machine = machine
        self.started = False
        self.processed = False
        self.transparent = False

    def start(self):
        return None

    def begin(self):
        return None

    def take_input(self, _event):
        return None

    def update(self):
        return None

    def update_visuals(self):
        return None

    def draw(self, surf):
        return surf

    def end(self):
        return None

    def finish(self):
        return None


class RecoveryTraceTests(unittest.TestCase):
    def _game(self, *, shared_skill=None, pending=None):
        shared_skill = shared_skill or SimpleNamespace(nid='aura_speed', uid=99,
                                                       components=[], source=None)
        unit_a = SimpleNamespace(
            nid='amy', klass='lord', level=2, exp=10, position=(1, 2), hp=18,
            mana=3, fatigue=0, guard_gauge=1, finished=False, dead=False,
            has_moved=False, has_attacked=False, traveler=None, lead_unit=None,
            team='player', party='player', stats={'STR': 5}, growths={'STR': 40},
            growth_points={'STR': 0}, wexp={'Sword': 15}, items=[], skills=[shared_skill],
            equipped_weapon=None, equipped_accessory=None,
        )
        unit_b = SimpleNamespace(
            nid='bea', klass='mage', level=1, exp=0, position=None, hp=16,
            mana=6, fatigue=0, guard_gauge=0, finished=False, dead=False,
            has_moved=False, has_attacked=False, traveler=None, lead_unit=None,
            team='player', party='player', stats={}, growths={}, growth_points={},
            wexp={}, items=[], skills=[shared_skill], equipped_weapon=None,
            equipped_accessory=None,
        )
        active_event = SimpleNamespace(
            nid='active', trigger=SimpleNamespace(nid='turn_start'),
            processor=SimpleNamespace(command_pointer=4, commands=[
                SimpleNamespace(nid='comment'), SimpleNamespace(nid='set'),
                SimpleNamespace(nid='set'), SimpleNamespace(nid='wait'),
                SimpleNamespace(nid='finish'),
            ]),
        )
        queued_event = SimpleNamespace(
            nid='queued', trigger=SimpleNamespace(nid='generic'),
            processor=SimpleNamespace(command_pointer=1, commands=[
                SimpleNamespace(nid='set'), SimpleNamespace(nid='finish'),
            ]),
        )
        return SimpleNamespace(
            state=SimpleNamespace(state=[SimpleNamespace(name='free')],
                                  temp_state=list(pending or [])),
            level=SimpleNamespace(nid='chapter_1', tilemap=SimpleNamespace(nid='map', width=2, height=1)),
            overworld_controller=None, current_party='player', turncount=3,
            phase=SimpleNamespace(current='player'), units=[unit_b, unit_a],
            game_vars={'_supports': True}, level_vars={'turn': 3},
            board=SimpleNamespace(bounds=(0, 0, 2, 1), previously_visited_tiles={(0, 0)},
                                  fog_of_war_grids={}, aura_grid={}, units={(1, 2): unit_a}),
            events=SimpleNamespace(all_events=[active_event, queued_event], event_stack=[queued_event]),
            _trace_active_event=active_event,
            already_triggered_events={'intro'}, current_save_slot=1,
        )

    def test_canonical_hash_ignores_mapping_and_set_insertion_order(self):
        self.assertEqual(canonical_hash({'a': {2, 1}, 'b': {'x': 1}}),
                         canonical_hash({'b': {'x': 1}, 'a': {1, 2}}))

    def test_capture_preserves_shared_skill_alias_with_local_reference(self):
        state = capture_logical_state(self._game())
        skills = [unit['skills'][0] for unit in state['units']]
        self.assertEqual(skills[0], skills[1])
        records = [obj for obj in state['object_graph']['objects']
                   if obj['kind'] == 'skill']
        self.assertEqual(1, len(records))
        self.assertNotIn('uid', records[0])

    def test_event_stack_is_active_then_lifo_pending(self):
        state = capture_logical_state(self._game())
        frames = state['events']['execution_stack']
        self.assertEqual(['active', 'queued'], [frame['event_nid'] for frame in frames])
        self.assertEqual(['active', 'pending'], [frame['role'] for frame in frames])
        self.assertEqual(4, frames[0]['processor']['command_ordinal'])

    def test_terminal_checkpoint_rejects_pending_transition(self):
        recorder = TraceRecorder('pending')
        with self.assertRaises(TraceInvariantError):
            recorder.checkpoint('level.load.complete', self._game(pending=['event']))

    def test_pending_exception_requires_the_exact_approved_queue(self):
        recorder = TraceRecorder('pending')
        checkpoint = recorder.checkpoint(
            'event.command.complete', self._game(pending=['event']),
            pending_exception_id='scenario.event.pending', allowed_pending=['event'])
        self.assertEqual('scenario.event.pending', checkpoint['context']['pending_exception_id'])
        with self.assertRaises(TraceInvariantError):
            recorder.checkpoint(
                'event.command.complete', self._game(pending=['event']),
                pending_exception_id='scenario.event.pending', allowed_pending=['free'])

    def test_save_payload_checkpoint_hashes_memory_not_filesystem(self):
        recorder = TraceRecorder('save')
        checkpoint = recorder.save_payload_captured(self._game(), {'units': ['amy']})
        self.assertEqual('save.payload.captured', checkpoint['checkpoint_id'])
        self.assertIn('save_payload_hash', checkpoint['context'])

    def test_header_and_comparator_reject_first_logical_difference(self):
        recorder = TraceRecorder('comparison')
        recorder.begin({'reference_revision': 'pc-ref', 'input_fixture_id': 'scenario'})
        expected = recorder.finish()
        self.assertEqual('trace_header', expected[0]['kind'])
        self.assertEqual(expected, compare_records(expected, expected))
        actual = [dict(record) for record in expected]
        actual[0] = dict(actual[0], scenario_id='other')
        with self.assertRaises(TraceComparisonError):
            compare_records(expected, actual)

    def test_comparator_ignores_only_header_provenance(self):
        expected = [{'kind': 'trace_header', 'schema_version': 1, 'scenario_id': 's',
                      'input_fixture_id': 'i', 'reference_revision': 'r', 'runner_revision': 'pc',
                      'platform_profile': 'pc_reference', 'serializer': 'logical-trace-v1'}]
        actual = [dict(expected[0], runner_revision='recovered', platform_profile='android')]
        self.assertEqual(actual, compare_records(expected, actual))

    def test_semantic_registry_requires_explicit_adapter(self):
        registry = SemanticRegistry()
        registry.register(int, lambda value: {'amount': value})
        self.assertEqual({'amount': 3}, registry.normalize(3))
        with self.assertRaises(TraceNormalizationError):
            registry.normalize(object())

    def test_hook_observer_records_once_and_rejects_unknown_hook(self):
        observer = HookObserver({('item', 'on_hit')})
        calls = []

        def original(value):
            calls.append(value)
            return value + 1

        wrapped = observer.wrap('item', 'on_hit', original,
                                subjects={'unit_ref': 'unit@amy'}, phase='combat')
        self.assertEqual(3, wrapped(2))
        self.assertEqual([2], calls)
        self.assertEqual(1, len(observer.calls))
        with self.assertRaises(TraceNormalizationError):
            observer.observe('item', 'unknown', subjects={}, context={}, phase='combat')

    def test_unknown_action_or_playback_value_fails_loudly(self):
        recorder = TraceRecorder('unknown-delta')
        with self.assertRaises(TraceNormalizationError):
            recorder.checkpoint('combat.cleanup.complete', self._game(),
                                delta={'actions': [object()]})

    def test_state_machine_is_inert_without_recorder_and_emits_when_injected(self):
        machine = StateMachine()
        machine.all_states = {'source': lambda name: _State(name, machine),
                              'target': lambda name: _State(name, machine)}
        machine.state.append(machine._new_state('source'))
        machine.change('target')
        machine.process_temp_state()
        self.assertEqual('target', machine.current())

        events = []
        machine.set_trace_recorder(SimpleNamespace(
            state_transition_committed=lambda state_machine: events.append(state_machine.current()),
        ))
        machine.change('source')
        machine.process_temp_state()
        self.assertEqual(['source'], events)


class _Action:
    def __init__(self, amount):
        self.amount = amount


class _Playback:
    def __init__(self, nid):
        self.nid = nid


class RecoveryTraceR2AcceptanceTests(unittest.TestCase):
    def _base_game(self, units=None):
        return SimpleNamespace(
            state=SimpleNamespace(state=[SimpleNamespace(name='free')], temp_state=[],
                                  current=lambda: 'free', current_state=lambda: None),
            level=None, board=None, units=units or [], current_party='player', turncount=1,
            phase=SimpleNamespace(current=2, get_current=lambda: 'enemy'),
            game_vars={}, level_vars={}, events=SimpleNamespace(event_stack=[], all_events=[]),
            already_triggered_events=set(), skill_registry={}, region_registry={},
            overworld_controller=None,
        )

    def test_r2_1_real_unit_action_pairup_and_skill_source_state(self):
        parent = SkillObject('aura_parent', 'Aura', '')
        child = SkillObject('aura_child', 'Child', '')
        unit = UnitObject('amy')
        unit.klass, unit.level, unit.exp = 'lord', 4, 55
        unit.stats, unit.growths, unit.growth_points, unit.wexp = ({'STR': 8}, {'STR': 40}, {'STR': 20}, {'Sword': 30})
        unit.current_hp, unit.current_mana = 17, 6
        unit.current_fatigue, unit.current_guard_gauge = 3, 9
        unit.set_action_state((True, True, True, True, True, True, True, True))
        unit.traveler, unit.lead_unit, unit.built_guard = 'bea', True, True
        unit.strike_partner = UnitObject('partner')
        unit._skills = [UnitSkill(parent, 'personal', SourceType.PERSONAL),
                        UnitSkill(child, parent.uid, SourceType.AURA)]
        game = self._base_game([unit])
        game.skill_registry = {parent.uid: parent, child.uid: child}

        result = capture_logical_state(game)['units'][0]

        self.assertEqual({'finished': True, 'attacked': True, 'traded': True, 'moved': True,
                          'rescued': True, 'dropped': True, 'taken': True, 'given': True},
                         result['action_state'])
        self.assertEqual((17, 6, 3, 9), (result['hp'], result['mana'], result['fatigue'], result['guard']))
        self.assertEqual(('bea', True, True, 'partner'),
                         (result['traveler'], result['lead_unit'], result['built_guard'], result['strike_partner']))
        self.assertEqual('aura', result['skills'][1]['source_type'])
        self.assertIn('ref', result['skills'][1]['source'])

    def test_r2_2_real_item_skill_components_and_alias_relationships(self):
        # Keep synthetic Component subclasses inside the one test that needs
        # them. The production component catalog discovers subclasses globally;
        # module-level fixtures would therefore leak into unrelated discovery
        # tests before this test ever runs.
        class _Uses(ItemComponent):
            nid = 'uses'

        class _Marker(SkillComponent):
            nid = 'marker'

        child_item = ItemObject('gem', 'Gem', '')
        parent_item = ItemObject(
            'sword', 'Sword', '',
            components=Data([_Uses({'remaining': 3, 'max': 5, 'source_type': SourceType.ITEM})]))
        parent_item.data = {'uses': 3}
        parent_item.subitems = [child_item]
        child_item.parent_item = parent_item
        parent_item.command_item = child_item
        parent_skill = SkillObject('parent', 'Parent', '', components=Data([_Marker({'charges': [1, 2]})]))
        parent_skill.data = {'counter': 2, 'flags': {'active', 'linked'}}
        child_skill = SkillObject('child', 'Child', '')
        parent_skill.subskill, child_skill.parent_skill = child_skill, parent_skill
        unit = UnitObject('amy')
        unit.items = [parent_item, child_item]
        unit._skills = [UnitSkill(parent_skill), UnitSkill(child_skill)]
        game = self._base_game([unit])
        game.skill_registry = {parent_skill.uid: parent_skill, child_skill.uid: child_skill}

        objects = capture_logical_state(game)['object_graph']['objects']
        sword = next(obj for obj in objects if obj['nid'] == 'sword')
        parent = next(obj for obj in objects if obj['nid'] == 'parent')
        self.assertEqual([['uses', {'max': 5, 'remaining': 3, 'source_type': 'item'}]],
                         sword['logical_fields']['components'])
        self.assertEqual(sword['references']['subitems'][0], sword['references']['command_item'])
        self.assertEqual({'counter': 2, 'flags': ['active', 'linked']}, parent['logical_fields']['data'])
        self.assertEqual([['marker', {'charges': [1, 2]}]], parent['logical_fields']['components'])
        self.assertEqual(parent['references']['subskill'],
                         next(obj for obj in objects if obj['nid'] == 'child')['local_id'])
        parent_item.components = Data([_Uses(object())])
        with self.assertRaises(TraceNormalizationError):
            capture_logical_state(game)

    def test_r2_3_rng_capture_is_exact_and_non_consuming(self):
        static_random.set_seed(77)
        before = (static_random.get_seed(), static_random.get_combat_random_state(),
                  static_random.get_growth_random_state(), static_random.get_other_random_state())
        captured = capture_logical_state(self._base_game())['rng']
        after = (static_random.get_seed(), static_random.get_combat_random_state(),
                 static_random.get_growth_random_state(), static_random.get_other_random_state())
        self.assertEqual(before, (captured['seed'], captured['combat_state'],
                                  captured['growth_state'], captured['other_state']))
        self.assertEqual(before, after)

    def test_r2_4_phase_uses_logical_team_api(self):
        result = capture_logical_state(self._base_game())['turn']
        self.assertEqual('enemy', result['phase'])
        self.assertEqual('enemy', result['active_team'])

    def test_r2_5_board_captures_terrain_aura_fog_region_and_occupancy(self):
        tilemap = TileMapObject()
        tilemap.nid, tilemap.width, tilemap.height = 'map', 2, 1
        layer = LayerObject('base', False, tilemap)
        layer.terrain = {(0, 0): 'Plains', (1, 0): 'Forest'}
        tilemap.layers = Data([layer])
        unit = UnitObject('amy')
        aura = SkillObject('aura_child', 'Aura', '')
        unit_grid, aura_grid, fog_grid = Grid((2, 1)), Grid((2, 1)), Grid((2, 1))
        unit_grid.append([unit]); unit_grid.append([])
        aura_grid.append({(aura.uid, 'Ally')}); aura_grid.append({(aura.uid, 'Ally')})
        fog_grid.append({'amy'}); fog_grid.append(set())
        board = SimpleNamespace(width=2, height=1, unit_grid=unit_grid, aura_grid=aura_grid,
                                known_auras={aura.uid: {(0, 0), (1, 0)}},
                                fog_of_war_grids={'player': fog_grid}, previously_visited_tiles={(0, 0)},
                                bounds=(0, 0, 1, 0),
                                in_vision=lambda pos, team: bool(fog_grid.get(pos)))
        region = RegionObject('zone', RegionType.EVENT, (1, 0), (1, 1), sub_nid='event')
        game = self._base_game([unit])
        game.level = SimpleNamespace(nid='chapter', tilemap=tilemap, regions=Data([region]))
        game.board, game.skill_registry = board, {aura.uid: aura}

        result = capture_logical_state(game)['board']
        plains_only = TileMapObject(); plains_only.nid, plains_only.width, plains_only.height = 'map', 2, 1
        plains_layer = LayerObject('base', False, plains_only); plains_layer.terrain = {(0, 0): 'Plains', (1, 0): 'Plains'}
        plains_only.layers = Data([plains_layer])
        self.assertNotEqual(
            result['tile_grid_hash'],
            canonical_hash({'dimensions': [2, 1],
                            'tiles': [[0, 0, 'Plains', 'base'], [1, 0, 'Plains', 'base']]}))
        self.assertEqual([[0, 0, 'amy']], result['occupancy'])
        self.assertEqual([[0, 0], [1, 0]], [entry[:2] for entry in result['aura_sources']])
        self.assertTrue(all('aura_child' in entry[2] for entry in result['aura_sources']))
        self.assertEqual([[0, 0]], result['fog_visible'])
        self.assertEqual('zone', result['regions'][0]['nid'])

    def test_r2_6_comparator_reports_identity_context_and_nested_path(self):
        header = {'kind': 'trace_header', 'schema_version': 1, 'scenario_id': 's',
                  'input_fixture_id': 'i', 'reference_revision': 'r', 'serializer': 'logical-trace-v1'}
        checkpoint = {'kind': 'checkpoint', 'checkpoint_id': 'a', 'context': {'unit': 'amy'},
                      'state_hash': 'x', 'delta_hash': 'y', 'logical_state': {'units': [{'hp': 10}]},
                      'semantic_delta': {'actions': []}}
        with self.assertRaisesRegex(TraceComparisonError, '/scenario_id'):
            compare_records([header], [dict(header, scenario_id='other')])
        with self.assertRaisesRegex(TraceComparisonError, '/checkpoint_id'):
            compare_records([header, checkpoint], [header, dict(checkpoint, checkpoint_id='b')])
        with self.assertRaisesRegex(TraceComparisonError, '/context/unit'):
            compare_records([header, checkpoint], [header, dict(checkpoint, context={'unit': 'bea'})])
        changed = dict(checkpoint, logical_state={'units': [{'hp': 9}]})
        with self.assertRaisesRegex(TraceComparisonError, '/logical_state/units/0/hp.*near'):
            compare_records([header, checkpoint], [header, changed])
        changed = dict(checkpoint, semantic_delta={'actions': [{'type': 'damage'}]})
        with self.assertRaisesRegex(TraceComparisonError, '/semantic_delta/actions'):
            compare_records([header, checkpoint], [header, changed])

    def test_r2_7_action_and_playback_use_distinct_injected_registries(self):
        actions, playback = SemanticRegistry(), SemanticRegistry()
        actions.register(_Action, lambda value: {'type': 'damage', 'amount': value.amount})
        playback.register(_Playback, lambda value: {'type': value.nid})
        recorder = TraceRecorder('combat', action_registry=actions, playback_registry=playback)
        result = recorder.checkpoint('combat.cleanup.complete', self._base_game(),
                                     delta={'actions': [_Action(4)], 'combat_playback': [_Playback('hit')]})
        self.assertEqual([{'amount': 4, 'type': 'damage'}], result['semantic_delta']['actions'])
        self.assertEqual([{'type': 'hit'}], result['semantic_delta']['combat_playback'])
        explicit = recorder.checkpoint(
            'combat.cleanup.complete', self._base_game(),
            delta={'normalized_actions': [{'type': 'heal', 'amount': 2}],
                   'normalized_combat_playback': [{'type': 'miss'}]})
        self.assertEqual([{'amount': 2, 'type': 'heal'}], explicit['semantic_delta']['actions'])
        self.assertEqual([{'type': 'miss'}], explicit['semantic_delta']['combat_playback'])
        with self.assertRaises(TraceNormalizationError):
            recorder.checkpoint('combat.cleanup.complete', self._base_game(), delta={'actions': [object()]})
        with self.assertRaises(TraceNormalizationError):
            recorder.checkpoint('combat.cleanup.complete', self._base_game(),
                                delta={'combat_playback': [object()]})

    def test_r2_8_save_payload_normalizes_roam_info_before_io(self):
        payload = {
            'units': [{'nid': 'amy', 'items': [1], 'skills': [2]}],
            'items': [{'uid': 1, 'nid': 'sword', 'data': {'uses': 3}}],
            'skills': [{'uid': 2, 'nid': 'vantage', 'components': [('priority', 1)]}],
            'terrain_status_registry': {(1, 2): 2},
            'regions': [{'nid': 'zone', 'position': (1, 0)}],
            'game_vars': {'_chapter_win': False}, 'level_vars': {'turn': 3},
            'state': (['free'], []), 'events': {'event_stack': []},
            'market_items': {'Vulnerary'}, 'talk_hidden': {('amy', 'bea')},
            'fog_state': {(0, 0), (1, 0)}, 'roam_info': RoamInfo(True, 'amy'),
        }
        recorder = TraceRecorder('save')
        result = recorder.save_payload_captured(self._base_game(), payload)
        self.assertEqual(canonical_hash(payload), result['context']['save_payload_hash'])
        self.assertEqual({'roam': True, 'roam_unit_nid': 'amy'}, normalize(payload)['roam_info'])
        self.assertNotIn('path', result['context'])
        with self.assertRaises(TraceNormalizationError):
            canonical_hash({'unknown': object()})


if __name__ == '__main__':
    unittest.main()
