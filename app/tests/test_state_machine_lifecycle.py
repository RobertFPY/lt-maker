import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine.state_machine import StateMachine
from app.events.event_state import EventState


class _State:
    def __init__(self, name, machine, trace, *, transparent=False,
                 begin_transition=None, start_transition=None,
                 start_repeat=False, draw_ready_in_start=False,
                 defer_render=False):
        self.name = name
        self.machine = machine
        self.trace = trace
        self.transparent = transparent
        self.begin_transition = begin_transition
        self.start_transition = start_transition
        self.start_repeat = start_repeat
        self.draw_ready_in_start = draw_ready_in_start
        self.defer_render = defer_render
        self.started = False
        self.processed = False
        self.draw_ready_data = False
        self.input_calls = 0
        self.update_calls = 0
        self.visual_update_calls = 0

    def start(self):
        self.trace.append((self.name, 'start'))
        if self.draw_ready_in_start:
            self.draw_ready_data = True
        if self.start_transition:
            self.machine.change(self.start_transition)
        return 'repeat' if self.start_repeat else None

    def begin(self):
        self.trace.append((self.name, 'begin'))
        self.draw_ready_data = True
        if self.begin_transition:
            self.machine.change(self.begin_transition)

    def take_input(self, _event):
        self.input_calls += 1

    def update(self):
        self.update_calls += 1

    def update_visuals(self):
        self.visual_update_calls += 1

    def should_defer_render(self):
        return self.defer_render

    def draw(self, surf):
        self.assert_draw_ready()
        self.trace.append((self.name, 'draw'))
        return surf

    def assert_draw_ready(self):
        if not self.draw_ready_data:
            raise AssertionError('draw ran before its state initialized drawing data')

    def end(self):
        self.trace.append((self.name, 'end'))

    def finish(self):
        self.trace.append((self.name, 'finish'))


class StateMachineLifecycleTests(unittest.TestCase):
    def _machine(self, specs):
        machine = StateMachine()
        trace = []
        machine.all_states = {
            name: (lambda state_name, spec=spec: _State(state_name, machine, trace, **spec))
            for name, spec in specs.items()
        }
        return machine, trace

    def test_final_update_draws_source_before_queued_state_is_committed(self):
        machine, trace = self._machine({
            'source': {'begin_transition': 'choice'},
            'choice': {},
        })
        machine.state.append(machine._new_state('source'))

        # The final Android fast-forward substep now draws here, before the
        # queued transition creates choice.  Choice cannot draw before begin.
        machine.update([], object(), draw=True)
        self.assertEqual('choice', machine.current())
        self.assertFalse(machine.current_state().started)
        self.assertEqual(
            [('source', 'start'), ('source', 'begin'), ('source', 'draw'),
             ('source', 'end')],
            trace)

        machine.update([], object(), draw=True)
        self.assertEqual(
            [('choice', 'start'), ('choice', 'begin'), ('choice', 'draw')],
            trace[-3:])

    def test_transparent_event_draws_paused_initialized_map(self):
        machine, trace = self._machine({
            'map': {},
            'event': {'transparent': True},
        })
        machine.state.append(machine._new_state('map'))
        machine.update([], object(), draw=True)

        # Changing state pauses map via end(), then pushes the transparent
        # event.  Map must remain drawable below the event overlay.
        machine.change('event')
        machine.update([], object(), draw=True)
        self.assertEqual('event', machine.current())
        map_state = machine.state[-2]
        self.assertFalse(map_state.processed)

        trace.clear()
        machine.update([], object(), draw=True)
        self.assertEqual(
            [('event', 'start'), ('event', 'begin'),
             ('event', 'draw')],
            [entry for entry in trace if entry[0] == 'event'])
        self.assertIn(('map', 'draw'), trace)
        self.assertLess(trace.index(('map', 'draw')), trace.index(('event', 'draw')))

    def test_started_transition_underlay_keeps_legacy_draw_order(self):
        machine, trace = self._machine({
            # Several real title/transition states initialize enough draw data
            # in start(), then deliberately push a transparent transition
            # before their first begin().
            'base': {
                'start_transition': 'transition',
                'start_repeat': True,
                'draw_ready_in_start': True,
            },
            'transition': {'transparent': True},
        })
        machine.state.append(machine._new_state('base'))

        machine.update([], object(), draw=True)
        self.assertEqual('transition', machine.current())
        machine.update([], object(), draw=True)

        self.assertIn(('base', 'draw'), trace)
        self.assertNotIn(('base', 'begin'), trace)
        self.assertIn(('transition', 'draw'), trace)

    def test_resumed_state_begins_again_before_its_next_top_draw(self):
        machine, trace = self._machine({
            'base': {},
            'overlay': {'transparent': True},
        })
        machine.state.append(machine._new_state('base'))
        machine.update([], object(), draw=True)
        base = machine.current_state()

        machine.change('overlay')
        machine.update([], object(), draw=True)
        machine.update([], object(), draw=True)

        machine.back()
        machine.update([], object(), draw=True)
        self.assertEqual('base', machine.current())
        self.assertFalse(base.processed)
        machine.update([], object(), draw=True)

        self.assertEqual(2, trace.count(('base', 'begin')))
        self.assertEqual(('base', 'draw'), trace[-1])

    def test_transparent_underlay_visuals_advance_without_a_draw(self):
        machine, _ = self._machine({
            'map': {},
            'event': {'transparent': True},
        })
        map_state = machine._new_state('map')
        event_state = machine._new_state('event')
        for state in (map_state, event_state):
            state.started = True
            state.processed = True
        machine.state = [map_state, event_state]

        machine.update([], object(), draw=False)

        self.assertEqual(1, map_state.visual_update_calls)
        self.assertEqual(1, event_state.visual_update_calls)

    def test_presentation_request_forces_one_deferred_draw(self):
        machine, trace = self._machine({'source': {}})
        source = machine._new_state('source')
        source.started = True
        source.processed = True
        source.draw_ready_data = True
        machine.state.append(source)
        machine.request_present('cursor')

        machine.update([], object(), draw=False)

        self.assertIn(('source', 'draw'), trace)
        self.assertTrue(machine.consume_presentation_barrier())
        self.assertFalse(machine.consume_presentation_barrier())

    def test_event_budget_yield_retains_last_presented_scene(self):
        machine, trace = self._machine({
            'map': {},
            'event': {'transparent': True, 'defer_render': True},
        })
        map_state = machine._new_state('map')
        event_state = machine._new_state('event')
        for state in (map_state, event_state):
            state.started = True
            state.processed = True
            state.draw_ready_data = True
        machine.state = [map_state, event_state]

        machine.update([], object(), draw=True)

        self.assertNotIn(('map', 'draw'), trace)
        self.assertNotIn(('event', 'draw'), trace)
        self.assertEqual(1, map_state.visual_update_calls)
        self.assertEqual(1, event_state.visual_update_calls)

    def test_presentation_request_overrides_event_budget_render_deferral(self):
        machine, trace = self._machine({'event': {'defer_render': True}})
        event_state = machine._new_state('event')
        event_state.started = True
        event_state.processed = True
        event_state.draw_ready_data = True
        machine.state.append(event_state)
        machine.request_present('event_transition')

        machine.update([], object(), draw=True)

        self.assertIn(('event', 'draw'), trace)
        self.assertTrue(machine.consume_presentation_barrier())

    def test_event_state_defers_only_a_processing_budget_yield(self):
        state = EventState('event')
        state.event = SimpleNamespace(
            state='processing', _android_process_yielded=True,
        )
        self.assertTrue(state.should_defer_render())

        state.event.state = 'waiting_for_present'
        self.assertFalse(state.should_defer_render())

        state.event.state = 'processing'
        state.event._android_process_yielded = False
        self.assertFalse(state.should_defer_render())

    def test_disabled_profiler_does_not_construct_stage_contexts(self):
        machine, _ = self._machine({'source': {}})
        machine.state.append(machine._new_state('source'))
        profiler = MagicMock(enabled=False)

        with patch('app.engine.state_machine.RUNTIME_PROFILER', profiler):
            machine.update([], object(), draw=True)

        profiler.section.assert_not_called()


if __name__ == '__main__':
    unittest.main()
