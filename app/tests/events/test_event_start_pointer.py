import unittest
from unittest.mock import MagicMock

import pygame

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import engine, game_state
from app.events import event_commands
from app.events.event_test import (EventTestEvent, EventTestExitState,
                                   build_event_test_trigger)
from app.events.event_prefab import (
    EventPrefab,
    get_event_command_pointer_from_line,
)
from app.events.event_processor import EventProcessor
from app.events.mock_event import (
    IfStatementStrategy,
    MockEventProcessor,
    MockGame,
)


class EventStartPointerUnitTests(unittest.TestCase):
    def test_event_test_exit_state_requests_clean_quit(self):
        previous_fast_quit = engine.fast_quit
        engine.fast_quit = False
        try:
            EventTestExitState().begin()

            self.assertTrue(engine.fast_quit)
        finally:
            engine.fast_quit = previous_fast_quit

    def test_legacy_event_pointer_matches_source_line(self):
        source = (
            "# comment\n"
            "\n"
            "wait;100\n"
            "speak;Seth;Start here"
        )

        self.assertEqual(get_event_command_pointer_from_line(source, 0), 0)
        self.assertEqual(get_event_command_pointer_from_line(source, 2), 2)
        self.assertEqual(get_event_command_pointer_from_line(source, 3), 3)

    def test_legacy_processor_starts_at_selected_command(self):
        source = (
            "# comment\n"
            "speak;MU;Before\n"
            "\n"
            "speak;Seth;Selected"
        )
        text_evaluator = MagicMock()
        text_evaluator._evaluate_all.side_effect = lambda text, _context: text
        processor = EventProcessor('test_start_pointer', source, text_evaluator)
        processor.command_pointer = get_event_command_pointer_from_line(source, 3)

        selected_command = processor.fetch_next_command()

        self.assertTrue(isinstance(selected_command, event_commands.Speak))
        self.assertEqual(selected_command.parameters['SpeakerOrStyle'], 'Seth')
        self.assertEqual(selected_command.parameters['Text'], 'Selected')

    def test_python_event_pointer_counts_prior_event_commands(self):
        source = (
            "#pyev1\n"
            "# comment\n"
            "$speak \"MU\" \"First\"\n"
            "\n"
            "some_value = 1\n"
            "# another comment\n"
            "$speak \"Seth\" \"Second\""
        )

        self.assertEqual(get_event_command_pointer_from_line(source, 2), 1)
        self.assertEqual(get_event_command_pointer_from_line(source, 5), 2)
        self.assertEqual(get_event_command_pointer_from_line(source, 6), 2)

    def test_pointer_clamps_editor_line_to_source(self):
        source = "wait;100"

        self.assertEqual(get_event_command_pointer_from_line(source, -10), 0)
        self.assertEqual(get_event_command_pointer_from_line(source, 10), 0)

    def test_legacy_processor_reports_commands_before_selected_line(self):
        source = (
            "change_background;House\n"
            "add_portrait;Seth;Left\n"
            "speak;MU;Do not replay this dialogue\n"
            "speak;Seth;Selected"
        )
        text_evaluator = MagicMock()
        text_evaluator._evaluate_all.side_effect = lambda text, _context: text
        skipped_commands = []
        processor = MockEventProcessor(
            'test_preload_pointer', source, text_evaluator,
            IfStatementStrategy.ALWAYS_TRUE, 3, skipped_commands.append)

        selected_command = processor.fetch_next_command()

        self.assertEqual(
            [command.nid for command in skipped_commands],
            ['change_background', 'add_portrait', 'speak'])
        self.assertTrue(isinstance(selected_command, event_commands.Speak))
        self.assertEqual(selected_command.parameters['SpeakerOrStyle'], 'Seth')

    def test_mock_game_get_all_units_accepts_on_field_argument(self):
        self.assertEqual(MockGame().get_all_units(False), [])

    def test_event_test_fast_forward_executes_gameplay_commands(self):
        event = EventTestEvent.__new__(EventTestEvent)
        event.game = MagicMock()
        event.game.state.temp_state = []
        event.do_skip = False
        event.super_skip = False
        event.command_queue = []
        event.should_update = {}
        event.should_remain_blocked = []
        event.text_boxes = []
        event.state = 'processing'
        event.wait_time = 0
        event.transition_state = None
        event.skippable = set()
        event.run_command = MagicMock()
        command = MagicMock()
        command.nid = 'add_unit'

        event._fast_forward_command(command)

        event.run_command.assert_called_once_with(command)
        self.assertFalse(event.do_skip)
        self.assertFalse(event.super_skip)

    def test_event_test_fast_forward_suppresses_state_transitions(self):
        event = EventTestEvent.__new__(EventTestEvent)
        event.game = MagicMock()
        event.game.state.temp_state = ['event']
        event.do_skip = False
        event.super_skip = False
        event.command_queue = []
        event.should_update = {}
        event.should_remain_blocked = []
        event.text_boxes = []
        event.state = 'processing'
        event.wait_time = 0
        event.transition_state = None
        event.skippable = set()
        command = MagicMock()
        command.nid = 'prep'

        def request_menu(_command):
            event.game.state.temp_state.append('prep_main')

        event.run_command = MagicMock(side_effect=request_menu)
        event._fast_forward_command(command)

        self.assertEqual(event.game.state.temp_state, ['event'])
        event.run_command.assert_not_called()


class EventTestLevelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.display_was_initialized = pygame.display.get_init()
        if not cls.display_was_initialized:
            pygame.display.init()
            pygame.display.set_mode((1, 1))
        DB.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        RESOURCES.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        # RESOURCES.load resets the global sprite registry, so images must be
        # loaded after the project resources have been installed.
        from app.engine import sprites
        sprites.load_images()

    @classmethod
    def tearDownClass(cls):
        if not cls.display_was_initialized:
            pygame.display.quit()

    def setUp(self):
        # Build a real level without loading display states. The editor path
        # initializes pygame/sprites via driver.start() before loading states,
        # but this headless test only needs the actual map, board, and units.
        # Runtime systems import the singleton by reference, so exercise that
        # same object here while still bypassing display-state loading.
        self.game = game_state.game
        self.game.clear()
        self.game.build_new()
        self.game.start_level('0')
        self.game.game_vars['_chapter_test'] = True

    def tearDown(self):
        self.game.clear()

    def test_event_test_uses_real_level_map_and_units(self):
        self.assertIsNotNone(self.game.tilemap)
        self.assertIsNotNone(self.game.board)
        self.assertIsNotNone(self.game.get_unit('Eirika'))
        self.assertGreater(len(self.game.get_all_units(False)), 0)

    def test_python_event_query_runs_against_real_game(self):
        prefab = EventPrefab('python_event_test_query')
        prefab.level_nid = '0'
        prefab.source = (
            "#pyev1\n"
            "if has_item('Eirika', 'Rapier'):\n"
            "    $level_var 'HasRapier' True\n"
            "$speak 'Eirika' 'Selected'"
        )
        event = EventTestEvent(prefab, self.game, command_idx=1)

        command = event.processor.fetch_next_command()

        self.assertEqual(self.game.level_vars['HasRapier'], True)
        self.assertTrue(isinstance(command, event_commands.Speak))
        self.assertEqual(command.parameters['SpeakerOrStyle'], 'Eirika')

    def test_python_event_receives_selected_unit_context(self):
        unit = self.game.get_unit('Eirika')
        unit2 = self.game.get_unit('Seth')
        prefab = EventPrefab('python_event_test_context')
        prefab.level_nid = '0'
        prefab.source = (
            "#pyev1\n"
            "if (unit.nid == 'Eirika' and unit1 is unit "
            "and unit2.nid == 'Seth' and target is unit2 "
            "and position == unit.position):\n"
            "    $speak 'Eirika' 'Context works'"
        )
        trigger = build_event_test_trigger(self.game, 'Eirika', 'Seth')
        event = EventTestEvent(prefab, self.game, trigger=trigger)

        command = event.processor.fetch_next_command()

        self.assertIs(trigger.unit1, unit)
        self.assertIs(trigger.unit2, unit2)
        self.assertEqual(trigger.position, unit.position)
        self.assertTrue(isinstance(command, event_commands.Speak))
        self.assertEqual(command.parameters['Text'], 'Context works')

    def test_commands_before_caret_rebuild_real_game_state(self):
        prefab = EventPrefab('classic_event_test_catch_up')
        prefab.level_nid = '0'
        prefab.source = (
            "level_var;EventTestCatchUp;7\n"
            "speak;Eirika;Selected"
        )
        event = EventTestEvent(prefab, self.game, command_idx=1)

        selected_command = event.processor.fetch_next_command()

        self.assertEqual(self.game.level_vars['EventTestCatchUp'], 7)
        self.assertTrue(isinstance(selected_command, event_commands.Speak))


if __name__ == '__main__':
    unittest.main()
