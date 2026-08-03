"""Shared, game-thread controller for the runtime debugger frontends.

The desktop debugger sends commands through its local HTTP adapter while the
Android debugger calls this controller directly.  Keeping game mutations here
prevents the two UIs from gradually developing different cheat behaviour.
"""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
from typing import Any, Dict, List, Optional

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.engine.game_state import game
from app.engine.runtime_debugger import RuntimeDebugger
from app.events import event_commands, event_validators
from app.events.event_structs import ParseMode
from app.events.event_version import EventVersion
from app.events.triggers import GenericTrigger


class RuntimeDebuggerController:
    """Own the debugger's game-thread state, catalogues, and operations."""

    def __init__(self) -> None:
        self._catalog: Dict[str, Any] = {
            'items': [], 'chapters': [], 'weathers': [], 'commands': [],
        }
        self._catalog_ready = False
        self._picked_position: Optional[Dict[str, int]] = None
        self._pick_revision = 0
        self._selected_unit_nid: Optional[str] = None
        self._notification: Optional[Dict[str, Any]] = None
        self._notification_revision = 0

    def reset_runtime_state(self) -> None:
        """Discard UI-only state when a new engine session begins."""
        self._picked_position = None
        self._pick_revision = 0
        self._selected_unit_nid = None
        self._notification = None
        self._notification_revision = 0

    def refresh_catalog(self) -> None:
        self._catalog = {
            'items': [{
                'nid': item.nid,
                'name': item.name or item.nid,
                'icon_nid': item.icon_nid,
                'icon_index': list(item.icon_index or (0, 0)),
                'uses': (
                    item.uses.value if item.uses else
                    item.c_uses.value if item.c_uses else None
                ),
            } for item in DB.items],
            'chapters': [
                {'nid': level.nid, 'name': level.name or level.nid}
                for level in DB.levels
            ],
            'weathers': (
                [{'nid': '', 'name': 'None (clear weather)'}] +
                [{'nid': weather, 'name': weather}
                 for weather in event_validators.Weather.valid]
            ),
            'commands': self._build_command_catalog(),
        }
        self._catalog_ready = True

    def catalog(self) -> Dict[str, Any]:
        if not self._catalog_ready:
            self.refresh_catalog()
        return self._catalog

    def build_snapshot(self, heartbeat: int = 0) -> Dict[str, Any]:
        """Build the same presentation snapshot consumed by the desktop UI."""
        catalog = self.catalog()
        level_nid = game.level.nid if game.level else None
        picking_position = (
            'debug_pick_position' in game.state.state_names() or
            'debug_pick_position' in game.state.temp_state
        )
        try:
            all_units = game.get_all_units()
        except (AttributeError, TypeError):
            all_units = []
        active_unit_nids = {unit.nid for unit in all_units}
        hovered_unit_nid = None
        cursor_position = None
        if game.cursor:
            cursor_position = list(game.cursor.position)
            if game.board:
                hovered_unit = game.board.get_unit(game.cursor.position)
                if hovered_unit and hovered_unit.nid in active_unit_nids:
                    hovered_unit_nid = hovered_unit.nid
                    self._selected_unit_nid = hovered_unit_nid
        try:
            money = game.get_money()
        except (AttributeError, KeyError, TypeError):
            money = None
        units = []
        for unit in all_units:
            try:
                units.append({
                    'nid': unit.nid,
                    'name': unit.name or unit.nid,
                    'team': unit.team,
                    'level': unit.level,
                    'hp': unit.get_hp(),
                    'max_hp': unit.get_max_hp(),
                    'position': list(unit.position) if unit.position else None,
                })
            except (AttributeError, KeyError, TypeError):
                continue
        units.sort(key=lambda unit: (unit['team'], unit['name'], unit['nid']))
        return {
            'runtime_active': True,
            'heartbeat': heartbeat,
            'picked_position': self._picked_position,
            'picking_position': picking_position,
            'notification': self._notification,
            'level': level_nid,
            'turncount': game.turncount,
            'money': money,
            'turnwheel': {
                'current_uses': game.game_vars.get('_current_turnwheel_uses', -1),
                'max_uses': game.game_vars.get('_max_turnwheel_uses', -1),
                'enabled': bool(game.game_vars.get('_turnwheel', False)),
            },
            'cursor_position': cursor_position,
            'hovered_unit_nid': hovered_unit_nid,
            'weather': [weather.nid for weather in game.tilemap.weather]
            if game.tilemap else [],
            'units': units,
            **catalog,
        }

    @staticmethod
    def _event_arg_name(command_type, arg_text: str, arg_idx: int) -> Optional[str]:
        if '=' in arg_text:
            maybe_keyword, _ = arg_text.split('=', 1)
            if command_type.get_validator_from_keyword(maybe_keyword):
                return maybe_keyword
        if arg_idx >= len(command_type.get_keywords()):
            return None
        return command_type.get_keyword_from_index(arg_idx)

    @staticmethod
    def _event_completion_words(arg_text: str) -> tuple[str, str]:
        word_to_match = re.split(r'[^a-zA-Z0-9_ ]', arg_text)[-1]
        word_to_replace = re.split(r"""[^a-zA-Z0-9_ "'{]""", arg_text)[-1]
        return word_to_match, word_to_replace

    def event_suggestions(self, line: str, source: str) -> Dict[str, Any]:
        parsed = event_commands.parse_event_line(line)
        arg_text = parsed.tokens[-1] if parsed.tokens else ''
        query, replacement = self._event_completion_words(arg_text)
        entries: List[Dict[str, str]] = []
        context = 'Command'

        def add_entry(name: Any, nid: Any, kind: str, entry_context: str) -> None:
            if nid is None:
                return
            value = str(nid)
            display_name = str(name) if name is not None else ''
            entries.append({
                'display': (f'{display_name} ({value})'
                            if display_name and display_name != value else value),
                'match': (f'{display_name} ({value})'
                          if display_name and display_name != value else value),
                'value': value,
                'kind': kind,
                'context': entry_context,
            })

        if parsed.mode() == ParseMode.COMMAND:
            for name, nid in event_validators.EventFunction(DB, RESOURCES).valid_entries():
                add_entry(name, nid, 'normal', context)
        else:
            command_type = event_commands.get_all_event_commands(EventVersion.EVENT).get(
                parsed.command())
            if command_type and parsed.mode() == ParseMode.ARGS:
                arg_name = self._event_arg_name(
                    command_type, arg_text, len(parsed.tokens) - 2)
                validator_nid = command_type.get_validator_from_keyword(arg_name)
                validator_type = event_validators.get(validator_nid)
                context = (f'{validator_nid} - {arg_name}'
                           if validator_nid and arg_name
                           else str(arg_name or 'Argument'))
                if validator_type:
                    level_nid = game.level.nid if game.level else None
                    for name, nid in validator_type(DB, RESOURCES).valid_entries(
                            level_nid, arg_text):
                        add_entry(name, nid, 'normal', context)
                    if validator_type.include_generic_completions and len(arg_text) >= 2:
                        words = Counter(source.replace('\n', ' ').replace(';', ' ').split())
                        words[arg_text] -= 1
                        for word, count in words.items():
                            if count > 0 and re.fullmatch(r'[A-Za-z_]+', word) and len(word) > 3:
                                generic_value = self._event_completion_words(word)[1]
                                add_entry(generic_value, generic_value, 'generic',
                                          f'Text in this command - {arg_name}')
                if arg_name in command_type.optional_keywords:
                    for flag in command_type().flags:
                        add_entry(f'FLAG({flag})', flag, 'flag',
                                  f'Flag - {command_type.nid}')
            elif command_type and parsed.mode() == ParseMode.FLAGS:
                context = f'Flag - {command_type.nid}'
                for flag in command_type().flags:
                    add_entry(f'FLAG({flag})', flag, 'flag', context)

        unique_entries: List[Dict[str, str]] = []
        seen = set()
        for entry in entries:
            identity = (entry['value'], entry['kind'])
            if identity not in seen:
                seen.add(identity)
                unique_entries.append(entry)
        lowered_query = query.lower()
        if lowered_query:
            unique_entries = [entry for entry in unique_entries
                              if lowered_query in entry['match'].lower()]
        unique_entries.sort(
            key=lambda entry: (
                (0.5 if entry['match'].lower().startswith(lowered_query) else 0) +
                SequenceMatcher(None, lowered_query, entry['match'].lower()).ratio()),
            reverse=True)
        for entry in unique_entries:
            entry.pop('match', None)
        return {
            'ok': True,
            'suggestions': unique_entries,
            'replace_length': len(replacement),
            'query': query,
            'context': context,
        }

    @staticmethod
    def _build_command_catalog() -> List[Dict[str, Any]]:
        commands = []
        seen = set()
        for command_type in event_commands.get_all_event_commands(EventVersion.EVENT).values():
            if command_type in seen or command_type.tag == event_commands.Tags.HIDDEN:
                continue
            seen.add(command_type)
            command = command_type()
            keyword_types = command.get_keyword_types()
            arguments = []
            for idx, keyword in enumerate(command.keywords + command.optional_keywords):
                keyword_type = keyword_types[idx] if idx < len(keyword_types) else keyword
                validator = event_validators.get(keyword_type)
                arguments.append({
                    'name': keyword,
                    'type': keyword_type,
                    'optional': idx >= len(command.keywords),
                    'description': str(getattr(validator, 'desc', '') or '').strip(),
                })
            signature = command.nid
            if arguments:
                signature += ';' + ';'.join(
                    f"{argument['name']}={argument['type']}" +
                    (' (optional)' if argument['optional'] else '')
                    for argument in arguments)
            template = command.nid
            if arguments:
                template += ';' + ';'.join(
                    f"[{argument['name']}]" if argument['optional']
                    else f"<{argument['name']}>"
                    for argument in arguments)
            commands.append({
                'nid': command.nid,
                'nickname': command.nickname,
                'category': command.tag.value,
                'signature': signature,
                'template': template,
                'arguments': arguments,
                'flags': command.flags,
                'description': str(command.desc or '').strip(),
            })
        commands.sort(key=lambda command: (command['category'], command['nid']))
        return commands

    def set_picked_position(self, position) -> None:
        self._pick_revision += 1
        self._picked_position = {
            'x': int(position[0]), 'y': int(position[1]),
            'revision': self._pick_revision,
        }

    def publish_notification(self, message: str, ok: bool = True) -> None:
        self._notification_revision += 1
        self._notification = {
            'message': message, 'ok': ok, 'revision': self._notification_revision,
        }

    def handle_hotkey(self, op: str) -> None:
        try:
            if op == 'max_selected':
                unit = RuntimeDebugger.selected_unit()
                if not unit and self._selected_unit_nid:
                    unit = game.get_unit(self._selected_unit_nid)
                if not unit:
                    raise ValueError('Move the game cursor onto a unit first.')
                result = self.dispatch('max_unit', {'nid': unit.nid})
            else:
                result = self.dispatch(op, {})
            self.publish_notification(result.get('message', 'Debugger hotkey completed.'), True)
        except Exception as exc:
            self.publish_notification(str(exc), False)

    @staticmethod
    def _get_unit(nid: str):
        unit = game.get_unit(nid)
        if not unit:
            raise ValueError(f'Unit {nid!r} is not loaded.')
        return unit

    @staticmethod
    def _unit_detail(unit) -> Dict[str, Any]:
        return {
            'nid': unit.nid,
            'name': unit.name or unit.nid,
            'team': unit.team,
            'klass': unit.klass,
            'position': list(unit.position) if unit.position else None,
            'inventory': [item.nid for item in unit.items],
            'fields': [{
                'key': debug_field.key,
                'label': debug_field.label,
                'value': debug_field.value,
                'minimum': debug_field.minimum,
                'maximum': debug_field.maximum,
            } for debug_field in RuntimeDebugger.editable_fields(unit)],
        }

    def dispatch(self, op: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if op == 'inspect_unit':
            return {'ok': True, 'detail': self._unit_detail(
                self._get_unit(str(args.get('nid', ''))))}
        if op == 'focus_unit':
            unit = self._get_unit(str(args.get('nid', '')))
            if not unit.position or not game.cursor:
                raise ValueError(f'{unit.nid} is not currently on the chapter map.')
            self._selected_unit_nid = unit.nid
            game.cursor.set_pos(unit.position)
            game.cursor.show()
            return {'ok': True, 'message': f'Game cursor moved to {unit.nid}.'}
        if op == 'set_field':
            unit = self._get_unit(str(args.get('nid', '')))
            field_key = str(args.get('key', ''))
            debug_field = next((field for field in RuntimeDebugger.editable_fields(unit)
                                if field.key == field_key), None)
            if not debug_field:
                raise ValueError(f'Unknown unit field {field_key!r}.')
            value = RuntimeDebugger.set_unit_field(unit, debug_field, int(args.get('value', 0)))
            return {'ok': True, 'message': f'{debug_field.label} set to {value}.'}
        if op == 'max_unit':
            unit = self._get_unit(str(args.get('nid', '')))
            RuntimeDebugger.max_out_unit(unit)
            return {'ok': True, 'message': f'Maxed {unit.nid}.'}
        if op == 'give_item':
            unit = self._get_unit(str(args.get('nid', '')))
            item_nid = str(args.get('item_nid', ''))
            uses = args.get('uses')
            if uses is not None:
                uses = int(uses)
            if not RuntimeDebugger.give_item(unit, item_nid, uses):
                raise ValueError(
                    f'Could not give item {item_nid!r}; check the item ID and inventory space.')
            uses_text = f' with {uses} use(s)' if uses is not None else ''
            return {'ok': True, 'message': f'Gave {item_nid}{uses_text} to {unit.nid}.'}
        if op == 'teleport':
            unit = self._get_unit(str(args.get('nid', '')))
            success, message = RuntimeDebugger.teleport(
                unit, (int(args.get('x', 0)), int(args.get('y', 0))))
            if not success:
                raise ValueError(message)
            return {'ok': True, 'message': message}
        if op == 'begin_pick_position':
            if not game.level or not game.cursor:
                raise ValueError('A chapter map must be active to pick a position.')
            picker_active = ('debug_pick_position' in game.state.state_names() or
                             'debug_pick_position' in game.state.temp_state)
            if not picker_active:
                game.state.change('debug_pick_position')
            return {'ok': True,
                    'message': 'Pick a tile in the game and press SELECT; BACK cancels.'}
        if op == 'max_players':
            count = RuntimeDebugger.max_out_units(RuntimeDebugger.player_units())
            return {'ok': True, 'message': f'Maxed {count} player unit(s).'}
        if op == 'max_enemies':
            count = RuntimeDebugger.max_out_units(RuntimeDebugger.enemy_units())
            return {'ok': True, 'message': f'Maxed {count} enemy unit(s).'}
        if op == 'enemy_hp':
            count = RuntimeDebugger.set_enemy_hp_to_one()
            return {'ok': True, 'message': f'Set HP to 1 for {count} enemy unit(s).'}
        if op == 'enemy_ai':
            count = RuntimeDebugger.disable_enemy_ai()
            return {'ok': True, 'message': f'Disabled AI for {count} enemy unit(s).'}
        if op == 'complete_chapter':
            RuntimeDebugger.complete_current_chapter()
            return {'ok': True, 'message': 'Completing current chapter...'}
        if op == 'go_chapter':
            level_nid = str(args.get('level_nid', ''))
            if not RuntimeDebugger.go_to_chapter(level_nid):
                raise ValueError(f'Unknown chapter {level_nid!r}.')
            return {'ok': True, 'message': f'Moving to chapter {level_nid}...'}
        if op == 'set_money':
            value = RuntimeDebugger.set_money(int(args.get('value', 0)))
            return {'ok': True, 'message': f'Money set to {value}.'}
        if op == 'set_turn_count':
            value = RuntimeDebugger.set_turn_count(int(args.get('value', 0)))
            return {'ok': True, 'message': f'Turn count set to {value}.'}
        if op == 'set_turnwheel':
            uses, enabled = RuntimeDebugger.set_turnwheel(
                int(args.get('uses', 0)), bool(args.get('enabled', False)))
            return {
                'ok': True,
                'message': 'Turnwheel %s; current and max uses set to %s.' % (
                    'enabled' if enabled else 'disabled',
                    'unlimited' if uses == -1 else str(uses)),
            }
        if op == 'set_weather':
            weather_nid = str(args.get('weather_nid', '')).strip().lower()
            if weather_nid and weather_nid not in event_validators.Weather.valid:
                raise ValueError(f'Unknown weather {weather_nid!r}.')
            RuntimeDebugger.set_weather(weather_nid or None)
            return {'ok': True,
                    'message': f"Weather changed to {weather_nid or 'None'}."}
        if op == 'event_suggestions':
            return self.event_suggestions(str(args.get('line', ''))[-8192:],
                                          str(args.get('source', ''))[-65536:])
        if op == 'event_command':
            script = str(args.get('script', '')).strip()
            parsed_command, _ = event_commands.parse_text_to_command(script)
            if not parsed_command:
                raise ValueError('Invalid event command.')
            unit_nid = args.get('nid')
            unit = game.get_unit(str(unit_nid)) if unit_nid else None
            position = unit.position if unit and unit.position else None
            game.events._add_event_from_script(
                'runtime_debugger', script,
                GenericTrigger(unit1=unit, position=position))
            return {'ok': True, 'message': 'Event command queued.'}
        raise ValueError(f'Unknown debugger operation {op!r}.')


CONTROLLER = RuntimeDebuggerController()


def get_controller() -> RuntimeDebuggerController:
    return CONTROLLER
