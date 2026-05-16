from typing import Any, Dict

from PyQt5.QtWidgets import QMessageBox

from app.utilities.typing import NID

from app.map_maker.editor.autogenerate_map import AutogenerateMapDialog
from app.map_maker.terrain import Terrain

from app.dungeon_maker import themes
from app.dungeon_maker import terrain_generation

class AutogenerateIndoorMap(AutogenerateMapDialog):
    def __init__(self, current: Dict[NID, Any], parent=None):
        super().__init__(current, themes.theme_presets, themes.get_theme, themes.theme_parameters, parent)
        self.setWindowTitle("Autogenerate Indoor Map")

    def _handle_previous_theme(self):
        self.previous_theme = self.settings.component_controller.get_state(self.__class__.__name__)
        if self.previous_theme:
            self.previous_theme['floor_lower'] = Terrain((self.previous_theme['floor_lower'], False))
            self.previous_theme['floor_upper'] = Terrain((self.previous_theme['floor_upper'], False))

    def generate(self):
        theme = self.get_parameters()
        dungeon_tilemap = terrain_generation.generate_terrain(theme, self.random_seed_box.edit.value())
        if dungeon_tilemap:
            # Update the current with the dungeon tilemap values
            self.tilemap.set_new_terrain_grid(
                (dungeon_tilemap.width, dungeon_tilemap.height), dungeon_tilemap.terrain_grid)
        else:
            QMessageBox.information(self, "Map Generation Failed", "Unable to generate a map. Check your connectivity rules!")

    @classmethod
    def customize(cls, parent=None):
        default_theme_parameters = themes.get_default_theme()
        dialog = cls(default_theme_parameters, parent)
        dialog.show()
        dialog.raise_()
        # dialog.exec_()
        # Set previous

    def closeEvent(self, event):
        super().closeEvent(event)
        current_theme = self.get_parameters()
        current_theme['floor_lower'] = current_theme['floor_lower'].value
        current_theme['floor_upper'] = current_theme['floor_upper'].value
        self.settings.component_controller.set_state(self.__class__.__name__, current_theme)
