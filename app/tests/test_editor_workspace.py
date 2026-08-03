import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QMainWindow

from app.editor import data_editor


class _FakeSettings:
    component_controller = type(
        '_ComponentController', (),
        {'get_geometry': lambda self, _name: None},
    )()


class EditorWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_workspace_is_not_a_child_window_of_main_editor(self):
        main_editor = QMainWindow()
        with patch.object(data_editor, 'MainSettingsController',
                          return_value=_FakeSettings()):
            workspace = data_editor.EditorWorkspace(main_editor)

        self.assertIsNone(workspace.parentWidget())
        self.assertIs(workspace.main_editor, main_editor)
        workspace.close()
        workspace.deleteLater()
        main_editor.deleteLater()
