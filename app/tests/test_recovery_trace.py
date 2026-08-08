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
)


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
                     'platform_profile': 'pc_reference'}]
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


if __name__ == '__main__':
    unittest.main()
