import logging
import unittest
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
