import logging
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.engine.text_evaluator import TextEvaluator
from app.events import event_commands
from app.events.event_parser import EventParser, IteratorInfo
from app.events.triggers import GenericTrigger
from app.tests.mocks.mock_game import get_mock_game


class EventParserUnitTests(unittest.TestCase):
    def setUp(self):
        self.mock_game = get_mock_game()
        mock_unit = MagicMock()
        mock_unit.name = "Erika" # deliberate spelling
        get_unit = lambda name: mock_unit
        self.mock_game.get_unit = get_unit
        self.mock_game.level_vars = {"TimesRescued": 10}

        self.text_evaluator = TextEvaluator(logging.getLogger(), self.mock_game)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_conditional_handling(self):
        script_path = Path(__file__).parent / 'data' / 'parser' / 'conditionals.event'
        as_commands = [event_commands.parse_text_to_command(line)[0] for line in script_path.read_text().split('\n')]
        parser = EventParser('conditionals', as_commands, self.text_evaluator)

        # basic tests
        self.assertEqual(parser._find_end(1), 6)
        self.assertEqual(parser._jump_conditional(1), 2)
        self.assertEqual(parser._find_end(3), 6)

        # elif
        self.assertEqual(parser._jump_conditional(8), 12)
        self.assertEqual(parser._jump_conditional(9), 10)
        self.assertEqual(parser._jump_conditional(11), 12)
        self.assertEqual(parser._find_end(11), 15)

        # nested for
        self.assertEqual(parser._jump_conditional(18), 19)
        self.assertEqual(parser._find_end(19), 21)

    def test_event_parser_handles_conditionals(self):
        script_path = Path(__file__).parent / 'data' / 'parser' / 'second_conditional.event'
        as_commands = [event_commands.parse_text_to_command(line)[0] for line in script_path.read_text().split('\n')]
        parser = EventParser('conditionals', as_commands, self.text_evaluator)

        called_commands = []
        while not parser.finished():
            next_command = parser.fetch_next_command()
            if next_command:
                called_commands.append(next_command)
        self.assertEqual(len(called_commands), 1)
        self.assertTrue(isinstance(called_commands[0], event_commands.Speak))
        self.assertEqual(called_commands[0].parameters['Text'], '2')

    def test_parse_events(self):
        script_path = Path(__file__).parent / 'data' / 'parser' / 'test.event'
        as_commands = [event_commands.parse_text_to_command(line)[0] for line in script_path.read_text().split('\n')]
        parser = EventParser('test', as_commands, self.text_evaluator)

        # normal command
        mu_speak = parser.fetch_next_command()
        self.assertTrue(isinstance(mu_speak, event_commands.Speak))
        self.assertEqual(mu_speak.parameters['Speaker'], 'MU')
        self.assertEqual(mu_speak.parameters['Text'], 'I am a custom named character.')

        # eval
        seth_speak = parser.fetch_next_command()
        self.assertTrue(isinstance(seth_speak, event_commands.Speak))
        self.assertEqual(seth_speak.parameters['Speaker'], 'Seth')
        self.assertEqual(seth_speak.parameters['Text'], 'Princess Erika!')

        # variable
        rescue_speak = parser.fetch_next_command()
        self.assertTrue(isinstance(rescue_speak, event_commands.Speak))
        self.assertEqual(rescue_speak.parameters['Speaker'], 'MU')
        self.assertEqual(rescue_speak.parameters['Text'], "You've rescued me 10 times.")

        # if/else/processing
        iftrue_speak = parser.fetch_next_command()
        self.assertTrue(isinstance(iftrue_speak, event_commands.Speak))
        self.assertEqual(iftrue_speak.parameters['Speaker'], 'MU')
        self.assertEqual(iftrue_speak.parameters['Text'], "A bit ridiculous, isn't it?")

        # for
        eirika_for = parser.fetch_next_command()
        seth_for = parser.fetch_next_command()
        self.assertTrue(isinstance(eirika_for, event_commands.Speak))
        self.assertEqual(eirika_for.parameters['Speaker'], 'Eirika')
        self.assertEqual(eirika_for.parameters['Text'], "My name is Eirika.")
        self.assertTrue(isinstance(seth_for, event_commands.Speak))
        self.assertEqual(seth_for.parameters['Speaker'], 'Seth')
        self.assertEqual(seth_for.parameters['Text'], "My name is Seth.")

    def test_save_restore_iterators(self):
        TEST_NID = 'some_nid'
        TEST_LINE_NUM = 25
        TEST_ITEMS = ['a', 'b', 'c']
        iterator = IteratorInfo(TEST_NID, TEST_LINE_NUM, TEST_ITEMS)
        # advance twice
        iterator.iterator.next()
        iterator.iterator.next()
        self.assertEqual(iterator.iterator.get(), 'c')
        new_iterator = IteratorInfo.restore(iterator.save())
        self.assertEqual(new_iterator.nid, TEST_NID)
        self.assertEqual(new_iterator.line, TEST_LINE_NUM)
        self.assertEqual(new_iterator.iterator.items, TEST_ITEMS)
        self.assertEqual(new_iterator.iterator.get(), 'c')

    def test_save_restore_parser_state(self):
        script_path = Path(__file__).parent / 'data' / 'parser' / 'test.event'
        as_commands = [event_commands.parse_text_to_command(line)[0] for line in script_path.read_text().split('\n')]
        parser = EventParser('test', as_commands, self.text_evaluator)

        parser.fetch_next_command()
        parser.fetch_next_command()
        parser.fetch_next_command()
        parser.fetch_next_command()
        # parser just returned "speak;MU;A bit ridiculous, isn't it?"

        new_parser = EventParser.restore(parser.save(), self.text_evaluator)
        self.assertEqual(new_parser.nid, 'test')
        next_command = new_parser.fetch_next_command()
        self.assertTrue(isinstance(next_command, event_commands.Speak))
        self.assertEqual(next_command.parameters['Speaker'], 'Eirika')
        self.assertEqual(next_command.parameters['Text'], "My name is Eirika.")