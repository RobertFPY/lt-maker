from __future__ import annotations

from typing import List

from app.constants import WINHEIGHT, WINWIDTH
from app.data.database.database import DB
from app.engine import config, engine
from app.engine.android_runtime import is_android_runtime
from app.engine.fonts import FONT
from app.engine.game_state import game
from app.engine.graphics.text.text_renderer import render_text, text_width
from app.engine.input_manager import get_input_manager
from app.engine.objects.unit import UnitObject
from app.engine.sound import get_sound_thread
from app.engine.sprites import SPRITES
from app.engine.state import MapState
from app.events import event_commands
from app.events.triggers import GenericTrigger
from app.utilities.enums import HAlignment
from app.utilities.typing import NID


class DebugState(MapState):
    """Route the debug menu to the platform-appropriate frontend."""

    def start(self):
        if config.SETTINGS['debug']:
            if is_android_runtime():
                # The state machine applies queued transitions in order.  Pop
                # this short-lived router and the command menu that launched it
                # before pushing the persistent map drawer.
                state_names = game.state.state_names()
                game.state.back()
                if len(state_names) >= 2 and state_names[-2] == 'option_menu':
                    game.state.back()
                game.state.change('android_debugger')
                return 'repeat'
            else:
                from app.engine import runtime_debugger_service
                runtime_debugger_service.ensure_window()
        game.state.back()
        return 'repeat'


class DebugPositionPickerState(MapState):
    """Map cursor mode used by the independent debugger's teleport picker."""

    name = 'debug_pick_position'
    panel_width = WINWIDTH // 2 - 2
    panel_height = 32
    panel_alpha = 144

    def begin(self):
        game.cursor.show()
        game.cursor.fluid.reset_on_change_state()
        self.hud_panel = engine.create_surface(
            (self.panel_width, self.panel_height), transparent=True)
        engine.fill(self.hud_panel, (0, 0, 0, self.panel_alpha))

    def take_input(self, event):
        game.cursor.take_input()
        if event == 'BACK':
            get_sound_thread().play_sfx('Select 4')
            game.state.back()
        elif event == 'SELECT':
            from app.engine.runtime_debugger_controller import get_controller
            get_controller().set_picked_position(game.cursor.position)
            get_sound_thread().play_sfx('Select 1')
            game.state.back()

    def draw(self, surf):
        surf = super().draw(surf)
        position = game.cursor.position
        units = [
            unit for unit in game.board.get_units(position)
            if 'Tile' not in unit.tags
        ] if game.board else []

        terrain_nid = game.get_terrain_nid(game.tilemap, position)
        terrain = DB.terrain.get(terrain_nid)
        terrain_text = f'{terrain_nid}: {terrain.name}' if terrain else str(terrain_nid)

        regions = [
            region.nid for region in game.level.regions
            if region.contains(position)
        ] if game.level else []
        region_text = ', '.join(regions) or 'None'

        left = 0
        right = WINWIDTH - self.panel_width
        bottom = WINHEIGHT - self.panel_height
        for panel_position in ((left, 0), (right, 0), (left, bottom), (right, bottom)):
            surf.blit(self.hud_panel, panel_position)

        render_text(
            surf, ['small'], ['Position: ', f'X={position[0]}, Y={position[1]}'],
            ['white', 'blue'], (4, 3))
        render_text(
            surf, ['small'], ['Tile: ', self._fit_value(terrain_text, 'Tile: ')],
            ['white', 'blue'], (4, 17))

        if units:
            unit = units[0]
            extra_units = f' +{len(units) - 1}' if len(units) > 1 else ''
            unit_value = self._fit_value(f'{unit.nid}{extra_units}', 'Unit: ')
            unit_detail = self._fit_value(
                f'{unit.team}  HP {unit.get_hp()}/{unit.get_max_hp()}', 'Team/HP: ')
        else:
            unit_value = 'None'
            unit_detail = 'Empty tile'
        render_text(
            surf, ['small'], ['Unit: ', unit_value],
            ['white', 'blue'], (right + 4, 3))
        render_text(
            surf, ['small'], ['Team/HP: ', unit_detail],
            ['white', 'blue'], (right + 4, 17))

        render_text(
            surf, ['small'], ['Region: ', self._fit_value(region_text, 'Region: ')],
            ['white', 'blue'], (4, bottom + 3))
        render_text(
            surf, ['small'], ['Cursor: ', 'Move to inspect tile'],
            ['white', 'blue'], (4, bottom + 17))

        render_text(
            surf, ['small'], ['SELECT', ': send tile'],
            ['yellow', 'white'], (right + 4, bottom + 3))
        render_text(
            surf, ['small'], ['BACK', ': cancel'],
            ['yellow', 'white'], (right + 4, bottom + 17))
        return surf

    def _fit_value(self, value: str, label: str) -> str:
        font = FONT['small-white']
        max_width = self.panel_width - 8 - font.width(label)
        if font.width(value) <= max_width:
            return value
        suffix = '...'
        while value and font.width(value + suffix) > max_width:
            value = value[:-1]
        return value + suffix

    def end(self):
        game.cursor.hide()


class DebugConsoleState(MapState):
    name = 'debug_console'
    num_back: int = 4
    backspace_time: int = 80
    current_command: str = ''
    commands = config.get_debug_commands()
    bg = SPRITES.get('debug_bg').convert_alpha()
    quit_commands: List[str] = ['q', 'exit', '']

    def begin(self):
        game.cursor.show()
        self.current_command = ''
        self.buffer_count = 0
        self.backspace_down = 0
        back_key_name = engine.get_key_name(get_input_manager().key_map['BACK'])
        if back_key_name not in self.quit_commands:
            self.quit_commands.append(back_key_name)
        self.overflow = False

    def take_input(self, event):
        current_time = engine.get_true_time()
        game.cursor.take_input()

        for pg_event in get_input_manager().get_input_events():
            if pg_event.type == engine.KEYDOWN:
                if pg_event.key == engine.key_map['enter']:
                    self.parse_command(self.current_command)
                    if self.current_command not in self.quit_commands:
                        self.commands.append(self.current_command)
                    self.current_command = ''
                    self.buffer_count = 0
                elif pg_event.key == engine.key_map['backspace']:
                    self.current_command = self.current_command[:-1]
                    self.backspace_down = current_time
                elif pg_event.key == engine.key_map['pageup'] and self.commands:
                    self.buffer_count += 1
                    if self.buffer_count >= len(self.commands):
                        self.buffer_count = 0
                    self.current_command = self.commands[-self.buffer_count]
                else:
                    self.current_command += pg_event.unicode
                self.overflow = text_width('text', self.current_command) >= WINWIDTH
            elif pg_event.type == engine.KEYUP and pg_event.key == engine.key_map['backspace']:
                self.backspace_down = 0

        if self.backspace_down and current_time - self.backspace_down > self.backspace_time:
            self.current_command = self.current_command[:-1]
            self.backspace_down = current_time
            self.overflow = text_width('text', self.current_command) >= WINWIDTH

    def parse_command(self, command):
        if command in self.quit_commands:
            get_sound_thread().play_sfx('Select 4')
            game.state.back()
            return
        event_command, _ = event_commands.parse_text_to_command(command)
        if not event_command:
            return
        game.events._add_event_from_script(
            'debug_console', str(command),
            GenericTrigger(unit1=game.cursor.get_hover(), position=game.cursor.position))

    def draw(self, surf):
        surf = super().draw(surf)
        self.draw_bg(surf)
        self.draw_hover_info(surf)
        for idx, command in enumerate(reversed(self.commands[-self.num_back:])):
            FONT['text'].blit(command, surf, (0, WINHEIGHT - idx * 16 - 32))
        if self.overflow:
            FONT['text'].blit_right(self.current_command, surf, (WINWIDTH, WINHEIGHT - 16))
        else:
            FONT['text'].blit(self.current_command, surf, (0, WINHEIGHT - 16))
        return surf

    def draw_bg(self, surf):
        surf.blit(self.bg, (0, 0 - (4 * 16)))
        surf.blit(self.bg, (0, WINHEIGHT - (5 * 16)))

    def draw_hover_info(self, surf):
        if game.is_displaying_overworld():
            return
        unit: UnitObject = game.cursor.get_hover()
        if unit:
            unit_position_info = [unit.nid, ': ', str(unit.position)]
            colors: List[NID | None] = ['white', 'white', 'blue']
        else:
            unit_position_info = [str(game.cursor.position)]
            colors = ['blue']
        render_text(
            surf, ['text'], unit_position_info, colors,
            topleft=(WINWIDTH, 0), align=HAlignment.RIGHT)

    def end(self):
        game.cursor.hide()
        config.save_debug_commands(self.commands[-20:])
