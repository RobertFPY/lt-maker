import json
import os
from typing import List, Tuple

from PyQt5.QtCore import QSettings, QDir
from PyQt5.QtCore import Qt

from app.editor.settings.preference_definitions import Preference

from .project_history_controller import ProjectHistoryController, ProjectHistoryEntry
from .component_settings_controller import ComponentSettingsController


class MainSettingsController():
    """
    Provides an interface for interacting with editor settings.
    Contains general application-wide settings. Also contains
    specific setting controllers for more tailored settings.
    """

    def __init__(self, company='rainlash', product='Lex Talionis'):
        QSettings.setDefaultFormat(QSettings.IniFormat)
        self.state = QSettings(company, product)
        self.component_controller = ComponentSettingsController(
            company, product)
        self.project_history_controller = ProjectHistoryController(
            company, product)

    def fileName(self):
        return self.state.fileName()

    """========== General Settings =========="""

    def set_current_project(self, value):
        self.state.setValue("current_proj", value)

    def get_current_project(self, fallback=""):
        return self.state.value("current_proj", fallback, type=str)

    def set_last_open_path(self, value):
        self.state.setValue("last_open_path", value)

    def get_last_open_path(self, fallback=""):
        if not fallback:
            fallback = QDir.currentPath()
        return str(self.state.value("last_open_path", fallback, type=str))

    def append_or_bump_project(self, project_name: str, project_path: str):
        self.project_history_controller.append_or_bump_project(
            project_name, project_path)

    def get_last_ten_projects(self) -> List[ProjectHistoryEntry]:
        return self.project_history_controller.get_last_ten_projects()

    """========== General UI Settings =========="""

    def set_default_anim_background(self, value):
        self.state.setValue('default_anim_background', value)

    def get_default_anim_background(self, fallback=True):
        return self.state.value('default_anim_background', fallback, type=bool)

    """========== General Saving Settings =========="""
    # Necessarily broken out of the generic accessor to enable non-editor data objects to access this preference
    def get_save_chunks_preference(self):
        return self.state.value('save_chunks', False, type=bool)

    """========== Generic Preference Accessors =========="""
    def get_preference(self, pref: Preference):
        """
        Generic getter that handles any Preference enum value.
        """
        from app.editor.settings.preference_definitions import PREFERENCE_TYPE_TO_STORAGE_TYPE
        defn = pref.definition
        # Determine storage type and default value for QSettings
        storage_type = PREFERENCE_TYPE_TO_STORAGE_TYPE.get(defn.pref_type, str)
        storage_default = defn.default_value
        return self.state.value(defn.setting_name, storage_default, type=storage_type)

    def set_preference(self, pref: Preference, value):
        """
        Generic setter that handles any Preference enum value.
        """
        defn = pref.definition
        self.state.setValue(defn.setting_name, value)
