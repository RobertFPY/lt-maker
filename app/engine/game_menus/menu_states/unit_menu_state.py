from typing import Tuple

from app.engine import background
from app.engine.fluid_scroll import FluidScroll
from app.engine.game_menus.menu_components.unit_menu.unit_menu import \
    UnitMenuUI
from app.engine.game_state import game
from app.engine.android_runtime import is_android_runtime
from app.engine.objects.overworld.overworld_entity import OverworldEntityTypes
from app.engine.objects.unit import UnitObject
from app.engine.performance import RUNTIME_PROFILER
from app.engine.sound import get_sound_thread
from app.engine.state import State
from app.utilities.direction import Direction


class UnitMenuState(State):
    name = 'unit_menu'
    bg = None
    surfaces = []

    def start(self):
        self.fluid = FluidScroll()
        self.bg = background.create_background('settings_background')
        self.in_level = game.level is not None
        # if in level, all deploy units
        # else, all party units
        with RUNTIME_PROFILER.section('unit_menu_collect_units'):
            if self.in_level: # player is in a level, get deployed
                self.all_player_units = game.get_player_units_and_travelers()
            elif (game.is_displaying_overworld() and
                  game.overworld_controller.selected_entity and
                  game.overworld_controller.selected_entity.dtype == OverworldEntityTypes.PARTY): # overworld, get all party units
                self.all_player_units = game.get_units_in_party(game.overworld_controller.selected_entity.prefab.nid)
            else: # all player units, everywhere, who are playable
                self.all_player_units = []
                for party_nid in game.parties.keys():
                    self.all_player_units += game.get_units_in_party(party_nid)

        with RUNTIME_PROFILER.section('unit_menu_build'):
            self.ui_display = UnitMenuUI(self.all_player_units)

        game.state.change('transition_in')
        return 'repeat'

    def begin(self):
        self.fluid.reset_on_change_state()

    @staticmethod
    def _page_direction_for_event(event: str):
        if event == 'INFO':  # R on Android
            return Direction.LEFT if is_android_runtime() else Direction.RIGHT
        if event == 'AUX':  # L on Android
            return Direction.RIGHT if is_android_runtime() else Direction.LEFT
        return None

    @staticmethod
    def _page_direction_for_horizontal(direction: Direction):
        if not is_android_runtime():
            return None
        if direction == Direction.LEFT:
            return Direction.RIGHT
        if direction == Direction.RIGHT:
            return Direction.LEFT
        return None

    def take_input(self, event):
        first_push = self.fluid.update()
        directions = self.fluid.get_directions()

        if 'DOWN' in directions:
            if self.ui_display.move_cursor(Direction.DOWN):
                get_sound_thread().play_sfx('Select 6')
        elif 'UP' in directions:
            if self.ui_display.move_cursor(Direction.UP):
                get_sound_thread().play_sfx('Select 6')
        elif 'LEFT' in directions:
            page_direction = self._page_direction_for_horizontal(Direction.LEFT)
            moved = (
                self.ui_display.change_page(page_direction)
                if page_direction else self.ui_display.move_cursor(Direction.LEFT)
            )
            if moved:
                get_sound_thread().play_sfx('Select 6')
        elif 'RIGHT' in directions:
            page_direction = self._page_direction_for_horizontal(Direction.RIGHT)
            moved = (
                self.ui_display.change_page(page_direction)
                if page_direction else self.ui_display.move_cursor(Direction.RIGHT)
            )
            if moved:
                get_sound_thread().play_sfx('Select 6')

        if event == 'BACK':
            get_sound_thread().play_sfx('Select 4')
            if not game.is_roam():
                selected = self.ui_display.cursor_hover()
                if isinstance(selected, UnitObject):
                    if self.in_level:
                        if selected.position:
                            game.cursor.set_pos(selected.position)
                        elif game.get_rescuers_position(selected):
                            game.cursor.set_pos(game.get_rescuers_position(selected))
            game.state.change('transition_pop')

        elif event == 'SELECT':
            get_sound_thread().play_sfx('Select 2')
            selected = self.ui_display.cursor_hover()
            if isinstance(selected, UnitObject):
                if self.in_level:
                    if selected.position:
                        game.cursor.set_pos(selected.position)
                    elif game.get_rescuers_position(selected):
                        game.cursor.set_pos(game.get_rescuers_position(selected))
                    game.state.back()
                    game.state.back()
            elif isinstance(selected, Tuple):
                self.ui_display.sort_data(selected)

        elif event in ('INFO', 'AUX'):
            if self.ui_display.change_page(self._page_direction_for_event(event)):
                get_sound_thread().play_sfx('Select 6')

    def draw(self, surf):
        if self.bg:
            self.bg.draw(surf)
        with RUNTIME_PROFILER.section('unit_menu_draw'):
            self.ui_display.draw(surf)
        return surf
