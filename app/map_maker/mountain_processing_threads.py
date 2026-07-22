from typing import Dict, Set

from PyQt5.QtCore import QThread, pyqtSignal

from app.utilities.typing import Pos

from app.map_maker.mountain_processing import NaiveBacktrackingProcess
from app.map_maker.mountain_processing_csp import CSPProcess

class _MountainProcessThread(QThread):
    """Runs a Qt-free mountain process (from mountain_processing.py)
    on a background Qt thread, re-exposing its progress as Qt signals"""
    waiting = pyqtSignal()

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self.process.waiting_callback = self.waiting.emit

    @property
    def group(self) -> Set[Pos]:
        return self.process.group

    @property
    def organization(self) -> Dict[Pos, Pos]:
        return self.process.organization

    @property
    def did_complete(self) -> bool:
        return self.process.did_complete

    def stop(self):
        self.process.stop()

    def run(self):
        self.process.process_group()

class NaiveBacktrackingThread(_MountainProcessThread):
    def __init__(self, tilemap, mountain_data, noneless_rules,
                 group: Set[Pos], gui_processing: bool = True, parent=None):
        process = NaiveBacktrackingProcess(tilemap, mountain_data, noneless_rules, group, gui_processing)
        super().__init__(process, parent)

class CSPThread(_MountainProcessThread):
    def __init__(self, tilemap, mountain_data, noneless_rules,
                 group: Set[Pos], gui_processing: bool = True, parent=None):
        process = CSPProcess(tilemap, mountain_data, noneless_rules, group, gui_processing)
        super().__init__(process, parent)
