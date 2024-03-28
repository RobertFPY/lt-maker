import logging
import unittest
from unittest.mock import MagicMock
from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.validation.db_validation import DBChecker

from app.engine.text_evaluator import TextEvaluator
from app.tests.mocks.mock_game import get_mock_game


class BaseProjectIntegrityTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def testDefaultProjectNoWarningsOrErrors(self):
        DB.load('default.ltproj')
        RESOURCES.load('default.ltproj')
        checker = DBChecker(DB, RESOURCES)
        warnings = checker.validate_for_warnings()
        errors = checker.validate_for_errors()
        warnings = [str(warning) for warning in warnings]
        errors = [str(warning) for warning in warnings]
        self.assertTrue(len(warnings) == 0, str(warnings))
        self.assertTrue(len(errors) == 0, str(errors))

    def testTestingProjectNoWarningsOrErrors(self):
        DB.load('testing_proj.ltproj')
        RESOURCES.load('testing_proj.ltproj')
        checker = DBChecker(DB, RESOURCES)
        warnings = checker.validate_for_warnings()
        errors = checker.validate_for_errors()
        warnings = [str(warning) for warning in warnings]
        errors = [str(warning) for warning in warnings]
        self.assertTrue(len(warnings) == 0, str(warnings))
        self.assertTrue(len(errors) == 0, str(errors))