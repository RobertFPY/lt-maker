import logging
import unittest
from pathlib import Path
from app.events.event_prefab import EventCatalog, EventPrefab

from app.events.python_eventing.preprocessor import CannotUseYieldError, InvalidCommandError, MalformedTriggerScriptCall, NestedEventError, NoSaveInLoopError, Preprocessor

class PreprocessorUnitTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_preprocessor_catches_errors(self):
        script_path = Path(__file__).parent / 'data' / 'python_events' / 'preprocessor.pyevent'
        script_source = script_path.read_text()
        ppsr = Preprocessor()

        errors = ppsr.verify_event('preprocessor_test', script_source)
        error_lines = set([e.line_num for e in errors])
        self.assertIn(18, error_lines)
        self.assertIn(20, error_lines)
        self.assertIn(21, error_lines)
        self.assertEqual(len(error_lines), 3)
        self.assertEqual(errors[0].__class__, NestedEventError)
        self.assertEqual(errors[1].__class__, NestedEventError)
        self.assertEqual(errors[2].__class__, NestedEventError)
        self.assertEqual(errors[3].__class__, InvalidCommandError)

    def test_preprocessor_catches_bad_saves(self):
        script_path = Path(__file__).parent / 'data' / 'python_events' / 'preprocessor_save_in_for_loop.pyevent'
        script_source = script_path.read_text()
        script_prefab = EventPrefab('preprocessor_save_in_for_loop')
        script_prefab.source = script_source

        nested_script_path = Path(__file__).parent / 'data' / 'python_events' / 'save_in_trigger_script_in_for_loop.pyevent'
        nested_script_source = nested_script_path.read_text()
        nested_prefab = EventPrefab('save_in_trigger_script_in_for_loop')
        nested_prefab.source = nested_script_source

        catalog = EventCatalog([script_prefab, nested_prefab])
        ppsr = Preprocessor(catalog)

        errors = ppsr.verify_event('preprocessor_save_in_for_loop', script_source)
        self.assertEqual(errors[0].__class__, NoSaveInLoopError)
        self.assertEqual(errors[1].__class__, NoSaveInLoopError)
        self.assertEqual(errors[2].__class__, MalformedTriggerScriptCall)
        self.assertEqual(errors[3].__class__, MalformedTriggerScriptCall)

    def test_preprocessor_forbids_yields(self):
        script_path = Path(__file__).parent / 'data' / 'python_events' / 'preprocessor_yields.pyevent'
        script_source = script_path.read_text()
        ppsr = Preprocessor()

        errors = ppsr.verify_event('preprocessor_test', script_source)
        error_lines = set([e.line_num for e in errors])
        self.assertIn(4, error_lines)
        self.assertEqual(len(error_lines), 1)
        self.assertEqual(errors[0].__class__, CannotUseYieldError)