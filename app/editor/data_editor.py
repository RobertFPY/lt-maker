from PyQt5 import QtGui
from PyQt5.QtWidgets import QDialog, QGridLayout, QDialogButtonBox, QTabWidget, \
    QSizePolicy, QVBoxLayout
from PyQt5.QtCore import Qt

from app.data.resources.resources import RESOURCES
from app.data.database.database import DB

from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.editor.settings import MainSettingsController
from app.editor.settings.preference_definitions import Preference

def restore_db_and_resync(saved_data, main_editor):
    """Restore the DB from a snapshot, then re-broadcast the selected level.

    DB.restore() rebuilds DB.levels into brand-new objects. The level editor
    (and its sub-widgets) cache the live level object and only refresh on a
    'selected_level' broadcast, so without the re-broadcast they keep pointing
    at the old, now-orphaned level object. Subsequent unit edits then go to the
    orphan while the DB holds the stale copy, and the next refresh snaps the
    editor back to the stale state -- the "unit positions revert" bug.
    """
    DB.restore(saved_data)
    state_manager = main_editor.app_state_manager if main_editor else None
    if state_manager:
        current_level_nid = state_manager.state.selected_level
        # Sometimes the stored current level nid does not exist as a valid
        # level; check before broadcasting.
        if current_level_nid in DB.levels:
            state_manager.change_and_broadcast(
                'selected_level', current_level_nid)


class EditorWorkspace(QDialog):
    """Non-modal host for the database and resource editors.

    The old editor dialogs each owned a snapshot of the entire database.  That
    is safe while only one modal dialog can exist, but it is not safe once
    several editors are open: cancelling one dialog could restore its old
    snapshot over changes made in another dialog.  The workspace therefore
    owns one shared transaction and one set of OK/Cancel/Apply buttons for all
    open editor tabs.
    """

    def __init__(self, main_editor):
        super().__init__(main_editor)
        self.main_editor = main_editor
        self.settings = MainSettingsController()
        self.saved_data = None
        self.resource_types = set()
        self._editors = {}
        self._finishing = False

        self.setWindowTitle(self.tr('Editor Workspace'))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setModal(False)
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        self.tab_bar = QTabWidget(self)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tab_bar)

        self.buttonbox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply,
            Qt.Horizontal,
            self)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.buttonbox.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        layout.addWidget(self.buttonbox)

        geometry = self.settings.component_controller.get_geometry(
            self.__class__.__name__)
        if geometry:
            self.restoreGeometry(geometry)

    def _editor_key(self, editor):
        return '%s:%s' % (editor.__class__.__name__, editor._type())

    def _editor_title(self, editor):
        if hasattr(editor, 'tabs'):
            titles = [tab.windowTitle() for tab in editor.tabs]
            combined_title = ' / '.join(title for title in titles if title)
            if combined_title:
                return combined_title
        title = editor.windowTitle()
        if title:
            return title
        return editor._type()

    def add_editor(self, editor):
        key = self._editor_key(editor)
        existing = self._editors.get(key)
        if existing is not None:
            self.tab_bar.setCurrentWidget(existing)
            editor.deleteLater()
            self.show()
            self.raise_()
            self.activateWindow()
            return

        if self.saved_data is None:
            self.saved_data = DB.save()
            self.resource_types.clear()

        if getattr(editor, 'resource_types', None):
            self.resource_types.update(editor.resource_types)

        # The workspace supplies the shared buttons.  The dialog itself is
        # embedded as an ordinary widget so opening it never blocks MainEditor.
        editor.buttonbox.hide()
        editor.buttonbox.setEnabled(False)
        editor.setWindowFlags(Qt.Widget)
        editor.setParent(self.tab_bar)
        editor.editor_workspace = self
        editor.setProperty('editor_workspace_key', key)
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._editors[key] = editor
        index = self.tab_bar.addTab(editor, self._editor_title(editor))
        self.tab_bar.setCurrentIndex(index)

        self.show()
        self.raise_()
        self.activateWindow()

    def close_editor(self, editor):
        index = self.tab_bar.indexOf(editor)
        if index >= 0:
            self.close_tab(index)

    def close_tab(self, index):
        editor = self.tab_bar.widget(index)
        if editor is None:
            return
        key = editor.property('editor_workspace_key')
        editor.workspace_close()
        self.tab_bar.removeTab(index)
        self._editors.pop(key, None)
        editor.deleteLater()

    def _save_resources(self):
        current_proj = self.settings.get_current_project()
        if (self.resource_types and current_proj and
                current_proj != 'default.ltproj'):
            RESOURCES.save(current_proj, sorted(self.resource_types))

    def apply(self):
        if self.saved_data is None:
            return
        self._save_resources()
        for editor in self._editors.values():
            editor.save_geometry()
        self.saved_data = DB.save()

    def mark_project_saved(self):
        """Advance Cancel's restore point after MainEditor saved the project."""
        if self.saved_data is not None:
            self.saved_data = DB.save()

    def _close_all_tabs(self):
        while self.tab_bar.count():
            self.close_tab(self.tab_bar.count() - 1)

    def _finish_session(self):
        self._close_all_tabs()
        self.saved_data = None
        self.resource_types.clear()

    def accept(self):
        self.apply()
        self._finishing = True
        self._finish_session()
        self._save_geometry()
        super().accept()
        self._finishing = False

    def reject(self):
        if self.saved_data is not None:
            current_proj = self.settings.get_current_project()
            if self.resource_types and current_proj:
                RESOURCES.load(current_proj, CURRENT_SERIALIZATION_VERSION)
            restore_db_and_resync(self.saved_data, self.main_editor)
        self._finishing = True
        self._finish_session()
        self._save_geometry()
        super().reject()
        self._finishing = False

    def reset_for_project_change(self):
        """Discard editor widgets after MainEditor loaded another project.

        The project backend already handled saving/discarding the previous
        project, so restoring the workspace snapshot here would corrupt the
        newly-loaded project.
        """
        self._finishing = True
        self._finish_session()
        self._save_geometry()
        super().reject()
        self._finishing = False

    def _save_geometry(self):
        self.settings.component_controller.set_geometry(
            self.__class__.__name__, self.saveGeometry())

    def closeEvent(self, event):
        if not self._finishing and self.saved_data is not None:
            # Closing the workspace with the window X has the same safe
            # semantics as Cancel.
            self.reject()
            event.accept()
            return
        self._save_geometry()
        super().closeEvent(event)


class SingleDatabaseEditor(QDialog):
    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.window = parent
        self.main_editor = self.window

        self.set_up()

        self.tab = tab.create(self)
        self.grid.addWidget(self.tab, 0, 0, 1, 2)

        self.setWindowTitle(self.tab.windowTitle())

        # Restore Geometry
        self.settings = MainSettingsController()
        geometry = self.settings.component_controller.get_geometry(self._type())
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.component_controller.get_state(self._type())
        if state:
            self.tab.splitter.restoreState(state)

    def keyPressEvent(self, keypress: QtGui.QKeyEvent) -> None:
        if keypress.key() == self.settings.get_preference(Preference.EDITOR_CLOSE_BUTTON):
            workspace = getattr(self, 'editor_workspace', None)
            if workspace:
                workspace.close_editor(self)
            else:
                self.reject()
        else:
            pass

    def set_up(self):
        self.setStyleSheet("font: 10pt;")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)

        self.save()

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply, Qt.Horizontal, self)
        self.grid.addWidget(self.buttonbox, 1, 1)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.buttonbox.button(QDialogButtonBox.Apply).clicked.connect(self.apply)

    def on_tab_close(self):
        self.tab.on_tab_close()

    def accept(self):
        current_proj = self.settings.get_current_project()
        self.save_geometry()
        self.on_tab_close()
        # if current_proj:
        #     DB.serialize(current_proj)
        super().accept()

    def reject(self):
        self.restore()
        current_proj = self.settings.get_current_project()
        self.save_geometry()
        self.on_tab_close()
        # if current_proj:
        #     DB.serialize(current_proj)
        super().reject()

    def save(self):
        self.saved_data = DB.save()
        return self.saved_data

    def restore(self):
        restore_db_and_resync(self.saved_data, self.main_editor)

    def apply(self):
        self.save()

    def exec_(self):
        opener = getattr(self.main_editor, 'open_editor_tab', None)
        if opener:
            opener(self)
            return QDialog.Accepted
        return super().exec_()

    def workspace_close(self):
        self.save_geometry()
        if hasattr(self, 'tabs'):
            for tab in self.tabs:
                if hasattr(tab, 'on_tab_close'):
                    tab.on_tab_close()
        elif hasattr(self, 'tab') and hasattr(self.tab, 'on_tab_close'):
            self.tab.on_tab_close()

    def closeEvent(self, event):
        self.save_geometry()
        self.on_tab_close()
        super().closeEvent(event)

    def _type(self):
        return self.tab.__class__.__name__

    def save_geometry(self):
        self.settings.component_controller.set_geometry(self._type(), self.saveGeometry())
        self.settings.component_controller.set_state(self._type(), self.tab.splitter.saveState())

class MultiDatabaseEditor(SingleDatabaseEditor):
    def __init__(self, tabs, parent=None):
        QDialog.__init__(self, parent)
        self.window = parent
        self.main_editor = self.window

        self.set_up()

        self.tab_bar = QTabWidget(self)
        self.grid.addWidget(self.tab_bar, 0, 0, 1, 2)
        self.tabs = []
        for tab in tabs:
            new_tab = tab.create(self)
            self.tabs.append(new_tab)
            self.tab_bar.addTab(new_tab, new_tab.windowTitle())

        self.current_tab = self.tab_bar.currentWidget()
        self.tab_bar.currentChanged.connect(self.on_tab_changed)

        # Restore Geometry
        self.settings = MainSettingsController()
        geometry = self.settings.component_controller.get_geometry(self._type())
        if geometry:
            self.restoreGeometry(geometry)
        for tab in self.tabs:
            _type = tab.__class__.__name__
            state = self.settings.component_controller.get_state(_type)
            if state and tab.splitter:
                tab.splitter.restoreState(state)
            # Also handle the frame itself
            right_frame_type = _type + '_right_frame'
            state = self.settings.component_controller.get_state(right_frame_type)
            if state:
                tab.right_frame.restore_state(state)

    def on_tab_changed(self, idx):
        # Make each tab individually resizable
        for i in range(self.tab_bar.count()):
            if i == idx:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        new_tab = self.tab_bar.currentWidget()
        self.current_tab = new_tab
        self.current_tab.update_list()
        self.current_tab.reset()

    def _type(self):
        s = ''
        for tab in self.tabs:
            s += tab.__class__.__name__
        return s

    def on_tab_close(self, event=None):
        if event:
            for tab in self.tabs:
                tab.closeEvent(event)

    def save_geometry(self):
        self.settings.component_controller.set_geometry(self._type(), self.saveGeometry())
        for tab in self.tabs:
            _type = tab.__class__.__name__
            if hasattr(tab, 'splitter') and tab.splitter:
                self.settings.component_controller.set_state(_type, tab.splitter.saveState())
            if hasattr(tab, 'right_frame') and hasattr(tab.right_frame, 'save_state'):
                state = tab.right_frame.save_state()
                right_frame_type = _type + '_right_frame'
                if state:
                    self.settings.component_controller.set_state(right_frame_type, state)

    def closeEvent(self, event):
        self.save_geometry()
        self.on_tab_close(event)
        super().closeEvent(event)

class SingleResourceEditor(QDialog):
    def __init__(self, tab, resource_types=None, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.window = parent
        self.main_editor = parent
        self.resource_types = resource_types
        self.setStyleSheet("font: 10pt;")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)

        self.save()

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply, Qt.Horizontal, self)
        self.grid.addWidget(self.buttonbox, 1, 1)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.buttonbox.button(QDialogButtonBox.Apply).clicked.connect(self.apply)

        self.tab = tab.create(self, *args, **kwargs)
        self.grid.addWidget(self.tab, 0, 0, 1, 2)

        self.setWindowTitle(self.tab.windowTitle())

        # Restore Geometry
        self.settings = MainSettingsController()
        geometry = self.settings.component_controller.get_geometry(self._type())
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.component_controller.get_state(self._type())
        if state:
            self.tab.splitter.restoreState(state)

    def accept(self):
        current_proj = self.settings.get_current_project()
        # RESOURCES must be saved here because if we grabbed a file from somewhere else
        # on our computer not under the project tree, we must transfer it under the project
        # tree. The project does not and should not know the absolute path of every one of its
        # resources, just where the resources should be.
        if current_proj and current_proj != 'default.ltproj':
            RESOURCES.save(current_proj, self.resource_types)
        self.save_geometry()
        super().accept()
        self.close()

    def reject(self):
        current_proj = self.settings.get_current_project()
        if current_proj:
            RESOURCES.load(current_proj, CURRENT_SERIALIZATION_VERSION)
        restore_db_and_resync(self.saved_data, self.main_editor)
        self.save_geometry()
        super().reject()
        self.close()

    def apply(self):
        current_proj = self.settings.get_current_project()
        if current_proj and current_proj != 'default.ltproj':
            RESOURCES.save(current_proj, self.resource_types)
        self.save()
        self.save_geometry()

    def keyPressEvent(self, keypress: QtGui.QKeyEvent) -> None:
        if keypress.key() == self.settings.get_preference(Preference.EDITOR_CLOSE_BUTTON):
            workspace = getattr(self, 'editor_workspace', None)
            if workspace:
                workspace.close_editor(self)
            else:
                self.reject()
        else:
            pass

    def exec_(self):
        opener = getattr(self.main_editor, 'open_editor_tab', None)
        if opener:
            opener(self)
            return QDialog.Accepted
        return super().exec_()

    def workspace_close(self):
        self.save_geometry()
        if hasattr(self, 'tabs'):
            for tab in self.tabs:
                if hasattr(tab, 'on_tab_close'):
                    tab.on_tab_close()
        elif hasattr(self, 'tab') and hasattr(self.tab, 'on_tab_close'):
            self.tab.on_tab_close()

    def closeEvent(self, event):
        self.save_geometry()
        super().closeEvent(event)

    def _type(self):
        return self.tab.__class__.__name__

    def save(self):
        self.saved_data = DB.save()
        return self.saved_data

    def save_geometry(self):
        self.settings.component_controller.set_geometry(self._type(), self.saveGeometry())
        if hasattr(self.tab, 'splitter'):
            self.settings.component_controller.set_state(self._type(), self.tab.splitter.saveState())

class MultiResourceEditor(SingleResourceEditor):
    def __init__(self, tabs, resource_types, parent=None):
        QDialog.__init__(self, parent)
        self.window = parent
        self.main_editor = parent
        self.resource_types = resource_types
        self.setWindowTitle("Resource Editor")
        self.setStyleSheet("font: 10pt;")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)

        self.save()

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply, Qt.Horizontal, self)
        self.grid.addWidget(self.buttonbox, 1, 1)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.buttonbox.button(QDialogButtonBox.Apply).clicked.connect(self.apply)

        self.tab_bar = QTabWidget(self)
        self.grid.addWidget(self.tab_bar, 0, 0, 1, 2)
        self.tabs = []
        for tab in tabs:
            new_tab = tab.create(self)
            self.tabs.append(new_tab)
            self.tab_bar.addTab(new_tab, new_tab.windowTitle())

        self.current_tab = self.tab_bar.currentWidget()
        self.tab_bar.currentChanged.connect(self.on_tab_changed)

        # Restore Geometry
        self.settings = MainSettingsController()
        geometry = self.settings.component_controller.get_geometry(self._type())
        if geometry:
            self.restoreGeometry(geometry)
        for tab in self.tabs:
            _type = tab.__class__.__name__
            state = self.settings.component_controller.get_state(_type)
            if state and tab.splitter:
                tab.splitter.restoreState(state)
            # Also handle the frame itself
            right_frame_type = _type + '_right_frame'
            state = self.settings.component_controller.get_state(right_frame_type)
            if state:
                tab.right_frame.restore_state(state)

    def on_tab_changed(self, idx):
        # Make each tab individually resizable
        for i in range(self.tab_bar.count()):
            if i == idx:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        new_tab = self.tab_bar.currentWidget()
        self.current_tab = new_tab
        self.current_tab.update_list()
        self.current_tab.reset()

    def _type(self):
        s = ''
        for tab in self.tabs:
            s += tab.__class__.__name__
        return s

    def save_geometry(self):
        self.settings.component_controller.set_geometry(self._type(), self.saveGeometry())
        for tab in self.tabs:
            _type = tab.__class__.__name__
            if hasattr(tab, 'splitter') and tab.splitter:
                self.settings.component_controller.set_state(_type, tab.splitter.saveState())
            if hasattr(tab, 'right_frame') and hasattr(tab.right_frame, 'save_state'):
                state = tab.right_frame.save_state()
                right_frame_type = _type + '_right_frame'
                if state:
                    self.settings.component_controller.set_state(right_frame_type, state)

    def closeEvent(self, event):
        self.save_geometry()
        for tab in self.tabs:
            tab.closeEvent(event)
        super().closeEvent(event)

class NewMultiResourceEditor(MultiResourceEditor):
    def on_tab_changed(self, idx):
        # Make each tab individually resizable
        for i in range(self.tab_bar.count()):
            if i == idx:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                self.tab_bar.widget(i).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        new_tab = self.tab_bar.currentWidget()
        self.current_tab = new_tab
        self.current_tab.reset()
