"""P7-T01 readiness-aligned fast-forward equivalence coverage."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

import pygame

from app.engine import config as cf
from app.engine import driver
from app.engine.input_manager import InputManager
from app.engine.trace import compare_records
from app.tests import recovery_trace_runner as runner


TRACE_OVERLAY = Path('app/engine/trace.py')


@contextmanager
def _fast_forward_outer_frames():
    """Run existing readiness-driven scripts through the real FF driver path."""
    with patch.object(runner, 'VirtualFrameDriver', runner.FastForwardScenarioFrameDriver), \
            patch.object(runner, 'RawInputFrameDriver', runner.FastForwardScenarioFrameDriver):
        yield


class FastForwardEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self._original_speed = cf.SETTINGS['fast_forward_speed']

    def tearDown(self):
        cf.SETTINGS['fast_forward_speed'] = self._original_speed

    def _capture_pair(self, capture):
        off_records = capture(TRACE_OVERLAY, 'recovery')
        with _fast_forward_outer_frames():
            on_records = capture(TRACE_OVERLAY, 'recovery')
        compare_records(off_records, on_records)

    def test_scenario_driver_holds_fast_forward_and_uses_real_driver_substeps(self):
        self.assertTrue(hasattr(runner, 'FastForwardScenarioFrameDriver'))

    def test_readiness_aligned_pairs_preserve_combat_movement_phase_and_restart(self):
        # Every input in these scripts is issued when its real state is ready;
        # no assertion depends on matching host-frame numbers.
        for capture in (
                runner.capture_scenario_5,
                runner.capture_scenario_6,
                runner.capture_scenario_7,
                runner.capture_scenario_8,
                runner.capture_scenario_13,
                runner.capture_scenario_15,
                runner.capture_scenario_18):
            with self.subTest(scenario=capture.__name__):
                self._capture_pair(capture)

    def test_speed_boundaries_preserve_simple_combat_trace(self):
        for speed in (200, 300, 800):
            with self.subTest(speed=speed):
                cf.SETTINGS['fast_forward_speed'] = speed
                self._capture_pair(runner.capture_scenario_6)

    def test_transient_key_text_and_click_edges_only_reach_first_substep(self):
        """A held fast-forward frame cannot replay any host transient input."""
        class StateMachine:
            def __init__(self, input_manager):
                self.input_manager = input_manager
                self.calls = []

            def current_state(self):
                return None

            def update(self, event, surf, draw=True):
                self.calls.append((event, self.input_manager.get_input_events()))
                return surf, False

        class Game:
            pass

        input_manager = InputManager()
        raw_cases = {
            'SELECT': pygame.event.Event(pygame.KEYDOWN,
                                         key=input_manager.key_map['SELECT']),
            'BACK': pygame.event.Event(pygame.KEYDOWN,
                                       key=input_manager.key_map['BACK']),
            'START': pygame.event.Event(pygame.KEYDOWN,
                                        key=input_manager.key_map['START']),
            'RIGHT': pygame.event.Event(pygame.KEYDOWN,
                                        key=input_manager.key_map['RIGHT']),
            'TEXT': pygame.event.Event(pygame.TEXTINPUT, text='x'),
            'CLICK': pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1),
        }
        for name, raw_event in raw_cases.items():
            with self.subTest(edge=name):
                input_manager.process_input([raw_event])
                game = Game()
                game.state = StateMachine(input_manager)
                driver.update_game_state_for_frame(
                    game, [], object(), 3, 16, input_manager=input_manager)
                self.assertEqual([raw_event], game.state.calls[0][1])
                self.assertEqual([[], []], [call[1] for call in game.state.calls[1:]])


if __name__ == '__main__':
    unittest.main()
