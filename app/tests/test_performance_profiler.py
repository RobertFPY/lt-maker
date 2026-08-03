import logging
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import driver
from app.engine.performance import RuntimeProfiler


class RuntimeProfilerTests(unittest.TestCase):
    def test_disabled_profiler_does_not_emit_records(self):
        profiler = RuntimeProfiler()
        profiler.enabled = False
        with patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            with profiler.section('map_compose'):
                pass
            profiler.finish_frame({'units': 1})
        warning.assert_not_called()

    def test_enabled_profiler_reports_aggregate_without_per_frame_output(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.interval_seconds = 0
        profiler.slow_frame_ms = 100000
        with patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            profiler.count('combat_frame_surface')
            with profiler.section('map_compose'):
                pass
            profiler.finish_frame({'units': 3, 'on_map': 2})
        self.assertEqual(1, warning.call_count)
        self.assertIn('PERF', warning.call_args.args[0])
        self.assertIn('p95', warning.call_args.args[0])
        self.assertIn('combat_frame_surface=1', warning.call_args.args[-2])

    def test_enabled_profiler_keeps_hierarchical_inclusive_and_exclusive_timings(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 1
        with patch('app.engine.performance.time.perf_counter_ns',
                   side_effect=(0, 10_000_000, 20_000_000, 40_000_000,
                                50_000_000, 100_000_000)), \
                patch.object(logging, 'warning'):
            profiler.begin_frame()
            with profiler.section('outer'):
                with profiler.section('inner'):
                    pass
            profiler.finish_frame({'state': 'combat'})

        scopes = profiler.latest_frame_scopes()
        self.assertEqual(('outer', 'inner'), tuple(scope['name'] for scope in scopes))
        self.assertEqual((None, 0), tuple(scope['parent_scope_id'] for scope in scopes))
        self.assertEqual((40.0, 20.0), tuple(scope['inclusive_ms'] for scope in scopes))
        self.assertEqual((20.0, 20.0), tuple(scope['exclusive_ms'] for scope in scopes))

    def test_slow_frame_output_includes_scope_path_and_metadata(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 1
        with patch('app.engine.performance.time.perf_counter_ns',
                   side_effect=(0, 10_000_000, 30_000_000, 50_000_000)), \
                patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            with profiler.section('combat.update'):
                pass
            profiler.finish_frame({'state': 'combat', 'level': 'Chapter1'})

        message = warning.call_args.args[0]
        details = warning.call_args.args[1:]
        self.assertIn('PERF slow-frame', message)
        self.assertIn('combat.update', details[-2])
        self.assertIn('state=combat', details[-1])
        self.assertIn('level=Chapter1', details[-1])

    def test_driver_supplies_slow_frame_context_without_reading_game_state(self):
        command = SimpleNamespace(nid='change_tilemap')
        processor = SimpleNamespace(command_pointer=2, commands=[command, command])
        event = SimpleNamespace(
            nid='intro', processor=processor,
            _profile_command_nid='change_tilemap', _profile_command_index=2,
        )
        combat = SimpleNamespace(state='begin_phase')
        state = SimpleNamespace(combat=combat, event=event)
        game = SimpleNamespace(
            units=[SimpleNamespace(position=(1, 2)), SimpleNamespace(position=None)],
            state=SimpleNamespace(
                current=lambda: 'event',
                current_state=lambda: state,
                state_names=lambda: ['free', 'event'],
            ),
            tilemap=SimpleNamespace(nid='castle', animations=[], weather=[]),
            level=SimpleNamespace(nid='Chapter1', regions={'gate': object()}),
        )

        counters = driver._performance_counters(game)

        self.assertEqual(['free', 'event'], counters['state_stack'])
        self.assertEqual('intro', counters['event_nid'])
        self.assertEqual('change_tilemap', counters['event_command'])
        self.assertEqual(2, counters['event_command_index'])
        self.assertEqual('Chapter1', counters['level'])
        self.assertEqual('castle', counters['tilemap'])
        self.assertEqual(1, counters['regions'])

    def test_phase_change_and_music_have_actionable_child_scopes(self):
        root = Path(__file__).parents[1]
        phase_state = (root / 'engine' / 'general_states.py').read_text(
            encoding='utf-8')
        phase_music = (root / 'engine' / 'phase.py').read_text(encoding='utf-8')

        for scope in (
            'phase_change.save_snapshot', 'phase_change.fade_out_music',
            'phase_change.transition_setup', 'phase_change.reset_units',
            'phase_change.resolve_next_music', 'phase_change.music_fade_in',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % scope, phase_state)
        self.assertIn("RUNTIME_PROFILER.section('phase.music_fade_in')", phase_music)


if __name__ == '__main__':
    unittest.main()
