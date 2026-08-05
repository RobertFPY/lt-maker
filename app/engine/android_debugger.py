"""Touch-first in-game frontend for the runtime debugger on Android."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from app.constants import WINHEIGHT, WINWIDTH
from app.engine import engine
from app.engine.android_runtime import (
    dismiss_android_debug_input, get_android_visible_height,
    poll_android_debug_input, set_android_touch_consumer,
    show_android_debug_input, show_android_debug_input_error)
from app.engine.fluid_scroll import FluidScroll
from app.engine.fonts import FONT
from app.engine.game_state import game
from app.engine.input_manager import get_input_manager
from app.engine.runtime_debugger_controller import get_controller
from app.engine.sound import get_sound_thread
from app.engine.state import State


DebugEntry = Tuple[str, str, Any]


class AndroidDebuggerState(State):
    """A compact drawer that leaves the active game screen visible."""

    name = 'android_debugger'
    transparent = True
    blocks_fast_forward = True
    PANEL_WIDTH = 154
    ROW_HEIGHT = 13
    TAB_HEIGHT = 18
    HEADER_TOP = TAB_HEIGHT
    HEADER_HEIGHT = 23
    ROW_TOP = HEADER_TOP + HEADER_HEIGHT + 2
    FOOTER_HEIGHT = 12
    MAX_ROWS = (WINHEIGHT - ROW_TOP - FOOTER_HEIGHT - 1) // ROW_HEIGHT
    INPUT_MIN_HEIGHT = 27
    INPUT_MAX_HEIGHT = WINHEIGHT - 8
    INPUT_ICON_RAIL_WIDTH = 22
    INPUT_ICON_GAP = 2
    TABS = ('Quick', 'Unit', 'World', 'Event')

    def __init__(self, name=None):
        super().__init__(name=name)
        self.fluid = FluidScroll()
        self.controller = get_controller()
        self.page = 'quick'
        self.view = 'home'
        self.selection = 0
        self.scroll = 0
        self.selected_nid: Optional[str] = None
        self.unit_filter = ''
        self.item_filter = ''
        self.command_filter = ''
        self.event_script = ''
        self.pending_item: Optional[Dict[str, Any]] = None
        self.pending_chapter_nid: Optional[str] = None
        self.pending_chapter_operation = 'go_chapter'
        self.teleport_x = 0
        self.teleport_y = 0
        self.turnwheel_uses = -1
        self.turnwheel_enabled = False
        self.command_detail: Optional[Dict[str, Any]] = None
        self.confirmation: Optional[Tuple[str, str, Dict[str, Any], bool]] = None
        self.number_value = 0
        self.number_minimum = 0
        self.number_maximum = 0
        self.number_label = ''
        self.number_apply: Optional[Callable[[int], None]] = None
        self.number_return_view = 'home'
        self.text_return_view = 'home'
        self.text_value = ''
        self.text_composition = ''
        self.text_label = ''
        self.text_apply: Optional[Callable[[str], None]] = None
        self.text_numeric = False
        self.text_error = ''
        self.text_multiline = False
        self.text_cursor = 0
        self.text_scroll = 0
        self._native_text_request_id: Optional[str] = None
        self._next_native_text_request_id = 0
        self.confirmation_return_view = 'home'
        self._touch_finger: Optional[Tuple[int, int]] = None
        self._touch_last_y = 0
        self._touch_start_y = 0
        self._touch_drag_pixels = 0
        self._touch_dragging = False
        self._touch_scrollbar = False
        self._last_input_window_rect = None
        self.message = ''
        self.message_ok = True
        self.message_until = 0
        self.snapshot: Dict[str, Any] = {}
        self._last_snapshot_time = -9999
        self._snapshot_revision = 0
        self._panel_cache = None
        self._panel_cache_key = None

    @property
    def panel_x(self) -> int:
        return WINWIDTH - self.PANEL_WIDTH

    def start(self):
        self.controller.refresh_catalog()
        if game.cursor:
            game.cursor.show()
        self._refresh(force=True)
        self._sync_selection_from_snapshot()
        return None

    def begin(self):
        self.fluid.reset_on_change_state()
        set_android_touch_consumer(
            self._on_touch,
            passthrough_buttons=('UP', 'DOWN', 'LEFT', 'RIGHT'),
        )

    def end(self):
        self._stop_text_input()
        set_android_touch_consumer(None)

    def _refresh(self, force: bool = False) -> None:
        current_time = engine.get_true_time()
        if force or current_time - self._last_snapshot_time >= 250:
            self.snapshot = self.controller.build_snapshot()
            self._last_snapshot_time = current_time
            self._snapshot_revision += 1
            self.turnwheel_uses = self.snapshot.get('turnwheel', {}).get(
                'current_uses', self.turnwheel_uses)
            self.turnwheel_enabled = self.snapshot.get('turnwheel', {}).get(
                'enabled', self.turnwheel_enabled)
            self._sync_selection_from_snapshot()

    def _sync_selection_from_snapshot(self) -> None:
        hovered = self.snapshot.get('hovered_unit_nid')
        units = self.snapshot.get('units', [])
        available_nids = {unit['nid'] for unit in units}
        previous_nid = self.selected_nid
        if self.selected_nid not in available_nids:
            self.selected_nid = None
        if hovered in available_nids:
            self.selected_nid = hovered
        elif not self.selected_nid and units:
            self.selected_nid = units[0]['nid']
        if self.selected_nid and self.selected_nid != previous_nid:
            try:
                detail = self.controller.dispatch('inspect_unit', {'nid': self.selected_nid})
                position = detail['detail'].get('position')
                if position:
                    self.teleport_x, self.teleport_y = position
            except (KeyError, ValueError):
                self.selected_nid = None

    def _notify(self, message: str, ok: bool = True) -> None:
        self.message = message
        self.message_ok = ok
        self.message_until = engine.get_true_time() + 3000
        self.controller.publish_notification(message, ok)

    def _run(self, op: str, args: Optional[Dict[str, Any]] = None,
             close_after: bool = False) -> bool:
        try:
            transition_start = len(game.state.temp_state)
            result = self.controller.dispatch(op, args or {})
            # Commands such as Complete Chapter queue EventState.  The drawer
            # must be popped *before* that new state, otherwise EventState is
            # created and immediately popped without ever running.
            if close_after:
                game.state.temp_state.insert(transition_start, 'pop')
            self._notify(result.get('message', 'Done.'), True)
            self._refresh(force=True)
            self._sync_selection_from_snapshot()
            return True
        except (KeyError, TypeError, ValueError) as exc:
            self._notify(str(exc), False)
            return False

    def _entries(self) -> List[DebugEntry]:
        if self.view == 'confirm':
            label = self.confirmation[0] if self.confirmation else 'Confirm action?'
            return [(label, 'none', None), ('Yes', 'confirm_yes', None),
                    ('No', 'confirm_no', None)]
        if self.view == 'number':
            return [
                ('-10', 'number_delta', -10), ('-1', 'number_delta', -1),
                ('+1', 'number_delta', 1), ('+10', 'number_delta', 10),
                ('Manual input', 'number_manual_input', None),
                (f'Apply: {self.number_value}', 'number_apply', None),
                ('Cancel', 'number_cancel', None),
            ]
        if self.view == 'text':
            return []
        if self.view == 'unit_list':
            filtered = [unit for unit in self.snapshot.get('units', []) if self._matches(
                self.unit_filter, unit['nid'], unit['name'], unit['team'])]
            return [('Search units: ' + (self.unit_filter or 'All'), 'edit_unit_filter', None)] + [
                (f"{unit['name']} [{unit['team']}]", 'select_unit', unit['nid'])
                for unit in filtered
            ]
        if self.view == 'fields':
            if not self.selected_nid:
                return [('Select a unit first.', 'none', None)]
            try:
                detail = self.controller.dispatch(
                    'inspect_unit', {'nid': self.selected_nid})['detail']
            except (KeyError, ValueError):
                return [('Selected unit is unavailable.', 'none', None)]
            return [(f"{field['label']}: {field['value']}", 'edit_field', field)
                    for field in detail['fields']]
        if self.view == 'items':
            items = [item for item in self.snapshot.get('items', []) if self._matches(
                self.item_filter, item['nid'], item['name'])]
            return [('Search items: ' + (self.item_filter or 'All'), 'edit_item_filter', None)] + [
                (f"{item['name']} ({item['nid']})", 'choose_item', item)
                for item in items
            ]
        if self.view == 'teleport':
            return [
                (f'X: {self.teleport_x}', 'edit_teleport_x', None),
                (f'Y: {self.teleport_y}', 'edit_teleport_y', None),
                ('Pick tile on map', 'pick_tile', None),
                ('Teleport selected unit', 'teleport', None),
            ]
        if self.view == 'chapters':
            return [(f"{chapter['name']} ({chapter['nid']})", 'choose_chapter', chapter['nid'])
                    for chapter in self.snapshot.get('chapters', [])
                    if chapter['nid'] != self.snapshot.get('level')]
        if self.view == 'chapter_difficulties':
            current_difficulty = self.snapshot.get('difficulty_nid')
            difficulties = sorted(
                self.snapshot.get('difficulties', []),
                key=lambda difficulty: difficulty['nid'] != current_difficulty)
            return [(f"{difficulty['name']} ({difficulty['nid']})", 'choose_chapter_difficulty',
                     difficulty['nid']) for difficulty in difficulties]
        if self.view == 'weather':
            return [(weather['name'], 'choose_weather', weather['nid'])
                    for weather in self.snapshot.get('weathers', [])]
        if self.view == 'turnwheel':
            return [
                (f'Uses: {self.turnwheel_uses}', 'edit_turnwheel_uses', None),
                ('Enabled: ' + ('Yes' if self.turnwheel_enabled else 'No'),
                 'toggle_turnwheel', None),
                ('Apply turnwheel', 'apply_turnwheel', None),
            ]
        if self.view == 'commands':
            commands = [command for command in self.snapshot.get('commands', [])
                        if self._matches(self.command_filter, command['nid'],
                                         command.get('nickname', ''),
                                         command['category'], command['description'])]
            return [('Search commands: ' + (self.command_filter or 'All'),
                     'edit_command_filter', None)] + [
                (f"{command['category']}: {command['nid']}", 'select_command', command)
                for command in commands
            ]
        if self.view == 'command_detail':
            if not self.command_detail:
                return [('Select a command first.', 'none', None)]
            command = self.command_detail
            return [
                (command['signature'], 'none', None),
                ('Use template', 'use_template', command['template']),
                ('Edit command text', 'edit_event_script', None),
                ('Run command text', 'run_event', None),
            ]
        if self.page == 'quick':
            return [
                ('Max selected unit', 'max_selected', None),
                ('Max all player units', 'confirm_op', ('max_players', {}, False)),
                ('Max all enemy units', 'confirm_op', ('max_enemies', {}, False)),
                ('Set enemy HP to 1', 'confirm_op', ('enemy_hp', {}, False)),
                ('Disable enemy AI', 'confirm_op', ('enemy_ai', {}, False)),
                ('Complete current chapter', 'confirm_op', ('complete_chapter', {}, True)),
            ]
        if self.page == 'unit':
            selected = self.selected_nid or 'None'
            return [
                (f'Select unit: {selected}', 'show_units', None),
                ('Edit unit values', 'show_fields', None),
                ('Max selected unit', 'max_selected', None),
                ('Auto level +1', 'auto_level_selected', None),
                ('Give item', 'show_items', None),
                ('Teleport selected unit', 'show_teleport', None),
            ]
        if self.page == 'world':
            return [
                ('Go to chapter', 'show_chapters', None),
                ('Restart current chapter', 'show_restart_difficulties', None),
                (f"Money: {self.snapshot.get('money', 0)}", 'edit_money', None),
                (f"Turn count: {self.snapshot.get('turncount', 0)}", 'edit_turn', None),
                ('Turnwheel', 'show_turnwheel', None),
                ('Change weather', 'show_weather', None),
            ]
        return [
            ('Edit command: ' + self._fit(self.event_script or 'Empty', 18),
             'edit_event_script', None),
            ('Run command', 'run_event', None),
            ('Suggestions', 'show_suggestions', None),
            ('Browse commands', 'show_commands', None),
        ]

    @staticmethod
    def _matches(query: str, *values: str) -> bool:
        if not query:
            return True
        haystack = ' '.join(str(value or '') for value in values).lower()
        return query.lower() in haystack

    def _set_view(self, view: str) -> None:
        if self.view == 'text' and view != 'text':
            self._stop_text_input()
            self.text_composition = ''
            self._last_input_window_rect = None
        self.view = view
        self.selection = 0
        self.scroll = 0

    def _begin_number(self, label: str, value: int, minimum: int, maximum: int,
                      apply: Callable[[int], None]) -> None:
        self.number_return_view = self.view
        self.number_label = label
        self.number_value = max(minimum, min(maximum, int(value)))
        self.number_minimum = minimum
        self.number_maximum = maximum
        self.number_apply = apply
        self._set_view('number')

    def _begin_text(self, label: str, value: str,
                    apply: Callable[[str], None], multiline: bool = False) -> None:
        self.text_return_view = self.view
        self.text_label = label
        self.text_value = value
        self.text_composition = ''
        self.text_apply = apply
        self.text_numeric = False
        self.text_error = ''
        self.text_multiline = multiline
        self.text_cursor = len(value)
        self.text_scroll = 0
        self._set_view('text')
        self._start_text_input()

    def _begin_number_text(self) -> None:
        self.text_return_view = 'number'
        self.text_label = self.number_label
        self.text_value = str(self.number_value)
        self.text_composition = ''
        self.text_apply = None
        self.text_numeric = True
        self.text_error = ''
        self.text_multiline = False
        self.text_cursor = len(self.text_value)
        self.text_scroll = 0
        self._set_view('text')
        self._start_text_input()

    def _start_text_input(self) -> None:
        if self._native_text_request_id is not None:
            return
        self._next_native_text_request_id += 1
        request_id = str(self._next_native_text_request_id)
        if show_android_debug_input(
                request_id, self.text_value, multiline=self.text_multiline,
                numeric=self.text_numeric):
            self._native_text_request_id = request_id
            return
        try:
            self._sync_text_input_rect(force=True)
            start = getattr(engine.pygame.key, 'start_text_input', None)
            if start:
                start()
        except Exception:
            pass

    def _stop_text_input(self) -> None:
        if self._native_text_request_id is not None:
            request_id = self._native_text_request_id
            self._native_text_request_id = None
            dismiss_android_debug_input(request_id)
        try:
            stop = getattr(engine.pygame.key, 'stop_text_input', None)
            if stop:
                stop()
        except Exception:
            pass

    def _sync_text_input_rect(self, force: bool = False) -> None:
        """Keep SDL's IME target aligned with the moving text rectangle."""
        try:
            set_rect = getattr(engine.pygame.key, 'set_text_input_rect', None)
            if not set_rect:
                return
            rect = self._input_rect_in_window(self._input_layout()['input'])
            if force or rect != self._last_input_window_rect:
                set_rect(rect)
                self._last_input_window_rect = rect
        except Exception:
            pass

    def _finish_text(self, save: bool) -> bool:
        if save and self.text_numeric:
            # Older Android debug builds put a literal '?' in generated
            # number fields. Remove that legacy marker before validation.
            self.text_value = self.text_value.replace('?', '')
            try:
                value = int(self.text_value.strip())
            except ValueError:
                self.text_error = 'Enter a whole number.'
                return False
            if not self.number_minimum <= value <= self.number_maximum:
                self.text_error = 'Allowed: %s to %s.' % (
                    self.number_minimum, self.number_maximum)
                return False
            self.number_value = value
        elif save and self.text_apply:
            self.text_apply(self.text_value)
        self._stop_text_input()
        self.text_composition = ''
        self._set_view(self.text_return_view)
        return True

    def _request_confirmation(self, label: str, op: str,
                              args: Dict[str, Any], close_after: bool) -> None:
        self.confirmation_return_view = self.view
        self.confirmation = (label, op, args, close_after)
        self._set_view('confirm')

    def _go_back_view(self) -> None:
        if self.view == 'text':
            self._finish_text(False)
        elif self.view == 'number':
            self._set_view(self.number_return_view)
        elif self.view == 'confirm':
            self.confirmation = None
            self._set_view(self.confirmation_return_view)
        elif self.view == 'command_detail':
            self._set_view('commands')
        elif self.view != 'home':
            self._set_view('home')
        else:
            game.state.back()

    def _activate(self, entry: DebugEntry) -> None:
        _, action_name, payload = entry
        if action_name == 'none':
            return
        if action_name == 'confirm_yes' and self.confirmation:
            _, op, args, close_after = self.confirmation
            self.confirmation = None
            self._set_view(self.confirmation_return_view)
            self._run(op, args, close_after)
            return
        if action_name == 'confirm_no':
            self.confirmation = None
            self._set_view(self.confirmation_return_view)
            return
        if action_name == 'confirm_op':
            op, args, close_after = payload
            self._request_confirmation(entry[0], op, args, close_after)
            return
        if action_name == 'max_selected':
            if self.selected_nid:
                self._run('max_unit', {'nid': self.selected_nid})
            else:
                self._notify('Select a unit first.', False)
            return
        elif action_name == 'auto_level_selected':
            if self.selected_nid:
                self._run('auto_level_unit', {'nid': self.selected_nid})
            else:
                self._notify('Select a unit first.', False)
            return
        if action_name == 'show_units':
            self._set_view('unit_list')
        elif action_name == 'select_unit':
            self.selected_nid = payload
            self._run('focus_unit', {'nid': payload})
            self._set_view('home')
        elif action_name == 'edit_unit_filter':
            self._begin_text('Find unit', self.unit_filter,
                             lambda value: setattr(self, 'unit_filter', value))
        elif action_name == 'show_fields':
            self._set_view('fields')
        elif action_name == 'edit_field':
            if not self.selected_nid:
                self._notify('Select a unit first.', False)
                return
            field = payload
            self._begin_number(
                field['label'], field['value'], field['minimum'], field['maximum'],
                lambda value, field_key=field['key']:
                    self._run('set_field', {
                        'nid': self.selected_nid, 'key': field_key, 'value': value,
                    }))
        elif action_name == 'show_items':
            self._set_view('items')
        elif action_name == 'edit_item_filter':
            self._begin_text('Find item', self.item_filter,
                             lambda value: setattr(self, 'item_filter', value))
        elif action_name == 'choose_item':
            if not self.selected_nid:
                self._notify('Select a unit first.', False)
                return
            self.pending_item = payload
            uses = payload.get('uses')
            if uses is None:
                self._run('give_item', {
                    'nid': self.selected_nid, 'item_nid': payload['nid'],
                })
                self._set_view('home')
            else:
                self._begin_number(
                    'Item uses', uses, 0, 999,
                    lambda value: self._give_pending_item(value))
        elif action_name == 'show_teleport':
            self._set_view('teleport')
        elif action_name == 'edit_teleport_x':
            self._begin_number('Destination X', self.teleport_x, 0,
                               max(0, getattr(game.tilemap, 'width', 1) - 1),
                               lambda value: setattr(self, 'teleport_x', value))
        elif action_name == 'edit_teleport_y':
            self._begin_number('Destination Y', self.teleport_y, 0,
                               max(0, getattr(game.tilemap, 'height', 1) - 1),
                               lambda value: setattr(self, 'teleport_y', value))
        elif action_name == 'pick_tile':
            if self._run('begin_pick_position'):
                self._notify('Choose a tile, then press SELECT.', True)
        elif action_name == 'teleport':
            if self.selected_nid:
                self._run('teleport', {
                    'nid': self.selected_nid, 'x': self.teleport_x,
                    'y': self.teleport_y,
                })
            else:
                self._notify('Select a unit first.', False)
        elif action_name == 'show_chapters':
            self.pending_chapter_operation = 'go_chapter'
            self._set_view('chapters')
        elif action_name == 'choose_chapter':
            self.pending_chapter_nid = payload
            self._set_view('chapter_difficulties')
        elif action_name == 'show_restart_difficulties':
            level_nid = self.snapshot.get('level')
            if not level_nid:
                self._notify('A chapter map must be active to restart it.', False)
                return
            self.pending_chapter_operation = 'restart_chapter'
            self.pending_chapter_nid = level_nid
            self._set_view('chapter_difficulties')
        elif action_name == 'choose_chapter_difficulty':
            if self.pending_chapter_nid:
                if self.pending_chapter_operation == 'restart_chapter':
                    self._request_confirmation(
                        f'Restart {self.pending_chapter_nid} on {payload}?', 'restart_chapter',
                        {'difficulty_nid': payload}, True)
                else:
                    self._request_confirmation(
                        f'Go to {self.pending_chapter_nid} on {payload}?', 'go_chapter',
                        {'level_nid': self.pending_chapter_nid, 'difficulty_nid': payload}, True)
        elif action_name == 'edit_money':
            self._begin_number('Money', self.snapshot.get('money') or 0, 0, 9_999_999,
                               lambda value: self._run('set_money', {'value': value}))
        elif action_name == 'edit_turn':
            self._begin_number('Turn count', self.snapshot.get('turncount') or 0,
                               0, 9_999, lambda value: self._run(
                                   'set_turn_count', {'value': value}))
        elif action_name == 'show_turnwheel':
            self._set_view('turnwheel')
        elif action_name == 'edit_turnwheel_uses':
            self._begin_number('Turnwheel uses', self.turnwheel_uses, -1, 9_999,
                               lambda value: setattr(self, 'turnwheel_uses', value))
        elif action_name == 'toggle_turnwheel':
            self.turnwheel_enabled = not self.turnwheel_enabled
        elif action_name == 'apply_turnwheel':
            self._run('set_turnwheel', {
                'uses': self.turnwheel_uses, 'enabled': self.turnwheel_enabled,
            })
        elif action_name == 'show_weather':
            self._set_view('weather')
        elif action_name == 'choose_weather':
            self._request_confirmation('Change weather?', 'set_weather',
                                       {'weather_nid': payload}, False)
        elif action_name == 'edit_event_script':
            self._begin_text('Event command', self.event_script,
                             lambda value: setattr(self, 'event_script', value),
                             multiline=True)
        elif action_name == 'run_event':
            self._request_confirmation('Run this event command?', 'event_command', {
                'script': self.event_script, 'nid': self.selected_nid,
            }, True)
        elif action_name == 'show_suggestions':
            self._set_view('suggestions')
        elif action_name == 'insert_suggestion':
            value, replace_length = payload
            start = max(0, len(self.event_script) - int(replace_length))
            self.event_script = self.event_script[:start] + value
            self._set_view('home')
        elif action_name == 'show_commands':
            self._set_view('commands')
        elif action_name == 'edit_command_filter':
            self._begin_text('Find command', self.command_filter,
                             lambda value: setattr(self, 'command_filter', value))
        elif action_name == 'select_command':
            self.command_detail = payload
            self._set_view('command_detail')
        elif action_name == 'use_template':
            self.event_script = payload
            self._set_view('home')
            self._notify('Template inserted. Replace fields before running.', True)
        elif action_name == 'number_delta':
            self.number_value = max(
                self.number_minimum,
                min(self.number_maximum, self.number_value + int(payload)))
        elif action_name == 'number_manual_input':
            self._begin_number_text()
        elif action_name == 'number_apply':
            if self.number_apply:
                self.number_apply(self.number_value)
            self._set_view(self.number_return_view)
        elif action_name == 'number_cancel':
            self._set_view(self.number_return_view)

    def _give_pending_item(self, uses: int) -> None:
        if self.pending_item and self.selected_nid:
            self._run('give_item', {
                'nid': self.selected_nid,
                'item_nid': self.pending_item['nid'],
                'uses': uses,
            })
        self.pending_item = None

    def _suggestions(self) -> List[DebugEntry]:
        line = self.event_script.rsplit('\n', 1)[-1]
        try:
            result = self.controller.event_suggestions(line, self.event_script)
        except (KeyError, TypeError, ValueError) as exc:
            return [(str(exc), 'none', None)]
        return [(f"{entry['display']} [{entry['context']}]", 'insert_suggestion',
                 (entry['value'], result['replace_length']))
                for entry in result.get('suggestions', [])]

    def _on_touch(self, phase: str, position: Tuple[int, int],
                  finger: Tuple[int, int]) -> bool:
        # Consume every touch while the drawer is active so no touch can reach
        # the suspended game state or virtual fast-forward control.
        if phase == 'down':
            self._touch_finger = finger
            self._touch_last_y = position[1]
            self._touch_start_y = position[1]
            self._touch_drag_pixels = 0
            self._touch_dragging = False
            self._touch_scrollbar = False
            if self.view != 'text':
                entries = self._entry_list()
                track, _thumb = self._scrollbar_rects(entries)
                if track and track.collidepoint(position):
                    self._touch_scrollbar = True
                    self._touch_dragging = True
                    self._scroll_from_scrollbar(position[1], entries)
        elif phase == 'move' and finger == self._touch_finger and self.view != 'text':
            delta_y = position[1] - self._touch_last_y
            self._touch_last_y = position[1]
            entries = self._entry_list()
            if abs(position[1] - self._touch_start_y) >= 4:
                self._touch_dragging = True
            if self._touch_scrollbar:
                self._scroll_from_scrollbar(position[1], entries)
            else:
                # A long catalogue should cross many entries per swipe while
                # retaining one-row precision for short lists.
                multiplier = min(6.0, max(1.0, len(entries) / max(1, self.MAX_ROWS * 8)))
                self._touch_drag_pixels += delta_y * multiplier
                row_delta = int(self._touch_drag_pixels / self.ROW_HEIGHT)
                if row_delta:
                    self._scroll_entries(-row_delta, entries)
                    self._touch_drag_pixels -= row_delta * self.ROW_HEIGHT
        elif phase == 'up' and finger == self._touch_finger:
            was_dragging = self._touch_dragging
            self._touch_finger = None
            self._touch_drag_pixels = 0
            self._touch_dragging = False
            self._touch_scrollbar = False
            if not was_dragging:
                self._tap(position)
        return True

    def _tap(self, position: Tuple[int, int]) -> None:
        x, y = position
        if self.view == 'text':
            self._tap_text_input(x, y)
            return
        if x < self.panel_x:
            return
        if y < self.TAB_HEIGHT:
            tab_width = self.PANEL_WIDTH // len(self.TABS)
            tab_index = min(len(self.TABS) - 1, (x - self.panel_x) // tab_width)
            self.page = self.TABS[tab_index].lower()
            self._set_view('home')
            return
        if y < self.ROW_TOP:
            if x < self.panel_x + 24:
                self._go_back_view()
            elif x >= WINWIDTH - 24:
                game.state.back()
            return
        entries = self._visible_entries()
        index = (y - self.ROW_TOP) // self.ROW_HEIGHT
        if 0 <= index < len(entries):
            self.selection = self.scroll + index
            self._activate(entries[index])

    def _tap_text_input(self, x: int, y: int) -> None:
        if self._native_text_request_id is not None:
            return
        layout = self._input_layout()
        dialog = layout['dialog']
        if not dialog.collidepoint(x, y):
            return
        if layout['input'].collidepoint(x, y):
            self._start_text_input()
        elif layout['cancel'].collidepoint(x, y):
            self._finish_text(False)
        elif layout['save'].collidepoint(x, y):
            self._finish_text(True)

    def _consume_native_text_result(self) -> bool:
        """Apply one Save/Cancel action from the Android system editor."""
        request_id = self._native_text_request_id
        if request_id is None:
            return False
        result = poll_android_debug_input()
        if result is None:
            return False
        if result.request_id != request_id:
            # A result from a dismissed editor must never change a newer field.
            return True
        if result.action == 'cancel':
            self._finish_text(False)
            return True

        self.text_value = result.value[:4096]
        self.text_cursor = len(self.text_value)
        if not self._finish_text(True):
            show_android_debug_input_error(request_id, self.text_error)
        return True

    def _entry_list(self) -> List[DebugEntry]:
        return self._suggestions() if self.view == 'suggestions' else self._entries()

    def _scroll_entries(self, delta: int, entries: Optional[List[DebugEntry]] = None) -> None:
        entries = entries if entries is not None else self._entry_list()
        max_scroll = max(0, len(entries) - self.MAX_ROWS)
        self.scroll = max(0, min(max_scroll, self.scroll + delta))
        if entries:
            last_visible = min(len(entries) - 1, self.scroll + self.MAX_ROWS - 1)
            self.selection = max(self.scroll, min(last_visible, self.selection))

    def _scrollbar_rects(self, entries: List[DebugEntry]):
        max_scroll = max(0, len(entries) - self.MAX_ROWS)
        if not max_scroll:
            return None, None
        track = engine.pygame.Rect(
            WINWIDTH - 6, self.ROW_TOP, 4, self.MAX_ROWS * self.ROW_HEIGHT)
        thumb_height = max(10, int(track.height * self.MAX_ROWS / len(entries)))
        thumb_range = max(1, track.height - thumb_height)
        thumb_y = track.y + int(thumb_range * self.scroll / max_scroll)
        return track, engine.pygame.Rect(track.x, thumb_y, track.width, thumb_height)

    def _scroll_from_scrollbar(self, y: int, entries: List[DebugEntry]) -> None:
        track, thumb = self._scrollbar_rects(entries)
        if not track or not thumb:
            return
        max_scroll = max(0, len(entries) - self.MAX_ROWS)
        thumb_range = max(1, track.height - thumb.height)
        ratio = (y - track.y - thumb.height / 2) / thumb_range
        self.scroll = max(0, min(max_scroll, round(ratio * max_scroll)))
        last_visible = min(len(entries) - 1, self.scroll + self.MAX_ROWS - 1)
        self.selection = max(self.scroll, min(last_visible, self.selection))

    def _ensure_selection_visible(self, entries: List[DebugEntry]) -> None:
        if not entries:
            self.selection = 0
            self.scroll = 0
            return
        self.selection = min(max(0, self.selection), len(entries) - 1)
        max_scroll = max(0, len(entries) - self.MAX_ROWS)
        if self.selection < self.scroll:
            self.scroll = self.selection
        elif self.selection >= self.scroll + self.MAX_ROWS:
            self.scroll = self.selection - self.MAX_ROWS + 1
        self.scroll = min(max(0, self.scroll), max_scroll)

    @staticmethod
    def _font_width(font_name: str, text: str) -> int:
        try:
            return FONT[font_name].width(text)
        except (KeyError, AttributeError):
            return len(text) * 6

    def _input_layout(self):
        """Fallback pygame layout when Android's native overlay is unavailable."""
        visible_height = min(WINHEIGHT, get_android_visible_height(WINHEIGHT))
        error_height = 11 if self.text_error else 0
        desired_height = visible_height - 4 if self.text_multiline else self.INPUT_MIN_HEIGHT
        height = min(self.INPUT_MAX_HEIGHT, max(
            self.INPUT_MIN_HEIGHT + error_height, desired_height + error_height))
        height = min(height, max(self.INPUT_MIN_HEIGHT + error_height, visible_height - 2))
        dialog = engine.pygame.Rect(0, 0, WINWIDTH, height)
        input_bottom = dialog.bottom - 4 - error_height
        input_rect = engine.pygame.Rect(
            dialog.x + 4, dialog.y + 4,
            dialog.width - self.INPUT_ICON_RAIL_WIDTH - 8,
            max(12, input_bottom - (dialog.y + 4)))
        button_x = dialog.right - self.INPUT_ICON_RAIL_WIDTH + 2
        button_width = self.INPUT_ICON_RAIL_WIDTH - 4
        button_height = max(11, (dialog.height - 6 - self.INPUT_ICON_GAP) // 2)
        cancel = engine.pygame.Rect(button_x, dialog.y + 3, button_width, button_height)
        save = engine.pygame.Rect(
            button_x, cancel.bottom + self.INPUT_ICON_GAP,
            button_width, button_height)
        return {
            'dialog': dialog, 'input': input_rect, 'cancel': cancel,
            'save': save, 'error_y': input_rect.bottom + 1,
        }

    def _input_dialog_rect(self):
        return self._input_layout()['dialog']

    @staticmethod
    def _input_rect_in_window(rect):
        screen_width, screen_height = engine.get_screen_size()
        scale = min(screen_width / WINWIDTH, screen_height / WINHEIGHT)
        offset_x = (screen_width - int(WINWIDTH * scale)) // 2
        offset_y = (screen_height - int(WINHEIGHT * scale)) // 2
        return engine.pygame.Rect(
            offset_x + int(rect.x * scale), offset_y + int(rect.y * scale),
            max(1, int(rect.width * scale)), max(1, int(rect.height * scale)))

    def _insert_text(self, value: str) -> None:
        if value:
            self.text_value = (
                self.text_value[:self.text_cursor] + value + self.text_value[self.text_cursor:])[:4096]
            self.text_cursor = min(len(self.text_value), self.text_cursor + len(value))

    def _delete_before_cursor(self) -> None:
        if self.text_cursor:
            self.text_value = self.text_value[:self.text_cursor - 1] + self.text_value[self.text_cursor:]
            self.text_cursor -= 1

    def _visible_entries(self) -> List[DebugEntry]:
        entries = self._entry_list()
        max_scroll = max(0, len(entries) - self.MAX_ROWS)
        self.selection = min(max(0, self.selection), max(0, len(entries) - 1))
        self.scroll = min(max(0, self.scroll), max_scroll)
        return entries[self.scroll:self.scroll + self.MAX_ROWS]

    def take_input(self, event):
        self._refresh()
        if self.view == 'text':
            if self._native_text_request_id is not None:
                self._consume_native_text_result()
                return
            self._sync_text_input_rect()
            text_input = getattr(engine.pygame, 'TEXTINPUT', -1)
            for raw_event in get_input_manager().get_input_events():
                if raw_event.type == text_input:
                    self._insert_text(getattr(raw_event, 'text', ''))
                    self.text_composition = ''
                elif raw_event.type == engine.KEYDOWN:
                    if raw_event.key == engine.key_map['backspace']:
                        self._delete_before_cursor()
                    elif raw_event.key == engine.key_map['enter']:
                        if self.text_multiline:
                            self._insert_text('\n')
                        else:
                            self._finish_text(True)
                    elif raw_event.key == getattr(engine.pygame, 'K_LEFT', -1):
                        self.text_cursor = max(0, self.text_cursor - 1)
                    elif raw_event.key == getattr(engine.pygame, 'K_RIGHT', -1):
                        self.text_cursor = min(len(self.text_value), self.text_cursor + 1)
                    elif raw_event.key == getattr(engine.pygame, 'K_DELETE', -1):
                        self.text_value = self.text_value[:self.text_cursor] + self.text_value[self.text_cursor + 1:]
                elif raw_event.type == getattr(engine.pygame, 'TEXTEDITING', -1):
                    self.text_composition = getattr(raw_event, 'text', '')
            if event == 'BACK':
                self._go_back_view()
            return
        if event in ('UP', 'DOWN', 'LEFT', 'RIGHT') and game.cursor:
            game.cursor.take_input()
            self._refresh(force=True)
            return
        entries = self._entry_list()
        if event == 'BACK':
            self._go_back_view()
            return
        if event in ('LEFT', 'RIGHT') and self.view == 'home':
            current = self.TABS.index(self.page.title())
            delta = -1 if event == 'LEFT' else 1
            self.page = self.TABS[(current + delta) % len(self.TABS)].lower()
            self._set_view('home')
            return
        if event == 'UP' and entries:
            self.selection = (self.selection - 1) % len(entries)
            self._ensure_selection_visible(entries)
        elif event == 'DOWN' and entries:
            self.selection = (self.selection + 1) % len(entries)
            self._ensure_selection_visible(entries)
        elif event == 'SELECT' and entries:
            self._activate(entries[min(self.selection, len(entries) - 1)])

    def update(self):
        self._refresh()
        if self.view == 'text':
            if self._native_text_request_id is not None:
                self._consume_native_text_result()
            else:
                self._sync_text_input_rect()
        picked = self.snapshot.get('picked_position')
        if picked and self.view == 'teleport':
            self.teleport_x = picked['x']
            self.teleport_y = picked['y']

    @staticmethod
    def _fit(text: str, maximum_chars: int) -> str:
        return text if len(text) <= maximum_chars else text[:max(0, maximum_chars - 3)] + '...'

    def _draw_text(self, surface, text: str, position: Tuple[int, int],
                   selected: bool = False) -> None:
        font = FONT['text-yellow'] if selected else FONT['text']
        max_width = self.PANEL_WIDTH - 8
        display = str(text)
        while display and font.width(display) > max_width:
            display = display[:-1]
        if display != text:
            display = display[:-3] + '...' if len(display) >= 3 else '...'
        font.blit(display, surface, position)

    def _rebuild_panel_cache(self):
        panel = engine.create_surface((self.PANEL_WIDTH, WINHEIGHT), transparent=True)
        panel.fill((8, 16, 29, 235))
        draw = engine.pygame.draw
        draw.rect(panel, (107, 145, 198, 255), panel.get_rect(), width=1)
        tab_width = self.PANEL_WIDTH // len(self.TABS)
        for index, tab in enumerate(self.TABS):
            rect = engine.pygame.Rect(index * tab_width, 0, tab_width, self.TAB_HEIGHT)
            if tab.lower() == self.page:
                draw.rect(panel, (36, 83, 135, 255), rect)
            draw.rect(panel, (86, 119, 158, 255), rect, width=1)
            FONT['small-white'].blit(tab, panel, (rect.x + 3, 5))
        title = f"{self.page.title()} / {self.view.replace('_', ' ').title()}"
        FONT['small-white'].blit('< Back', panel, (3, self.HEADER_TOP + 2))
        FONT['small-white'].blit(self._fit(title, 18), panel, (31, self.HEADER_TOP + 2))
        FONT['small-white'].blit('X', panel, (self.PANEL_WIDTH - 10, self.HEADER_TOP + 2))
        if self.view != 'text':
            entries = self._visible_entries()
            for index, entry in enumerate(entries):
                y = self.ROW_TOP + index * self.ROW_HEIGHT
                selected = self.selection == self.scroll + index
                if selected:
                    draw.rect(panel, (30, 67, 107, 220),
                              (2, y - 1, self.PANEL_WIDTH - 4, self.ROW_HEIGHT))
                self._draw_text(panel, entry[0], (5, y), selected)
            if self.scroll:
                FONT['small-white'].blit('^', panel, (self.PANEL_WIDTH - 8, self.ROW_TOP))
            total_entries = self._entry_list()
            if self.scroll + self.MAX_ROWS < len(total_entries):
                FONT['small-white'].blit('v', panel, (self.PANEL_WIDTH - 8,
                                                      WINHEIGHT - self.FOOTER_HEIGHT - 2))
            track, thumb = self._scrollbar_rects(total_entries)
            if track and thumb:
                draw.rect(panel, (31, 49, 72, 255), track.move(-self.panel_x, 0))
                draw.rect(panel, (110, 157, 208, 255), thumb.move(-self.panel_x, 0))
        return panel

    def _panel_key(self):
        # Number and confirmation screens mutate in-place. They are uncommon
        # compared with the catalogue views, so favour correctness over a
        # cache that would need a separate invalidation for every button.
        if self.view in ('confirm', 'number', 'text'):
            return None
        return (
            self.page, self.view, self.selection, self.scroll,
            self._snapshot_revision, self.selected_nid,
            self.unit_filter, self.item_filter, self.command_filter,
            self.event_script, self.teleport_x, self.teleport_y,
            self.turnwheel_uses, self.turnwheel_enabled,
        )

    def draw(self, surf):
        cache_key = self._panel_key()
        if cache_key is None or self._panel_cache is None or \
                self._panel_cache_key != cache_key:
            self._panel_cache = self._rebuild_panel_cache()
            self._panel_cache_key = cache_key
        surf.blit(self._panel_cache, (self.panel_x, 0))
        if self.message and engine.get_true_time() < self.message_until:
            color = (47, 130, 78, 245) if self.message_ok else (132, 51, 65, 245)
            engine.pygame.draw.rect(
                surf, color,
                (self.panel_x + 2, WINHEIGHT - 12, self.PANEL_WIDTH - 4, 10))
            self._draw_text(surf, self.message,
                            (self.panel_x + 4, WINHEIGHT - 11), False)
        if self.view == 'text' and self._native_text_request_id is None:
            self._draw_input_dialog(surf)
        return surf

    def _draw_input_dialog(self, surf) -> None:
        draw = engine.pygame.draw
        layout = self._input_layout()
        dialog = layout['dialog']
        draw.rect(surf, (20, 28, 40, 170), (0, 0, WINWIDTH, WINHEIGHT))
        draw.rect(surf, (248, 248, 248, 255), dialog)
        draw.rect(surf, (40, 72, 105, 255), dialog, width=2)
        input_rect = layout['input']
        draw.rect(surf, (255, 255, 255, 255), input_rect)
        draw.rect(surf, (78, 116, 155, 255), input_rect, width=1)
        lines = self.text_value.split('\n') or ['']
        cursor_line = self.text_value[:self.text_cursor].count('\n')
        max_lines = max(1, (input_rect.height - 4) // 12)
        first_line = max(0, min(cursor_line - max_lines + 1, len(lines) - max_lines))
        for index, line in enumerate(lines[first_line:first_line + max_lines]):
            FONT['text-blue'].blit(self._fit(line, 30), surf,
                                   (input_rect.x + 3, input_rect.y + 2 + index * 12))
        if first_line <= cursor_line < first_line + max_lines:
            cursor_prefix = self.text_value[:self.text_cursor].rsplit('\n', 1)[-1]
            cursor_x = input_rect.x + 3 + min(FONT['text-blue'].width(cursor_prefix), input_rect.width - 6)
            cursor_y = input_rect.y + 2 + (cursor_line - first_line) * 12
            draw.line(surf, (25, 55, 90, 255), (cursor_x, cursor_y), (cursor_x, cursor_y + 10))
        if self.text_composition:
            FONT['text-grey'].blit(self._fit(self.text_composition, 30), surf,
                                   (input_rect.x + 3, input_rect.bottom - 11))
        if self.text_error:
            FONT['text-red'].blit(self._fit(self.text_error, 32), surf,
                                  (dialog.x + 7, layout['error_y']))
        for label, rect in (('X', layout['cancel']), ('V', layout['save'])):
            draw.rect(surf, (49, 85, 125, 255), rect)
            label_x = rect.centerx - self._font_width('small-white', label) // 2
            FONT['small-white'].blit(label, surf, (label_x, rect.centery - 4))
