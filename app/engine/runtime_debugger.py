from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.data.database.database import DB
from app.engine import action, item_funcs, unit_funcs
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.events.triggers import GenericTrigger
from app.utilities import utils
from app.utilities.typing import NID, Pos


@dataclass(frozen=True)
class DebugField:
    key: str
    label: str
    value: int
    minimum: int
    maximum: int


class RuntimeDebugger:
    """Game-thread operations used by the standalone runtime debugger."""

    @staticmethod
    def selected_unit() -> Optional[UnitObject]:
        if game.cursor and game.board:
            unit = game.board.get_unit(game.cursor.position)
            if unit and 'Tile' not in unit.tags:
                return unit
        return None

    @staticmethod
    def editable_fields(unit: UnitObject) -> List[DebugField]:
        klass = DB.classes.get(unit.klass)
        max_level = klass.max_level if klass else 999
        fields = [
            DebugField('level', 'Level', unit.level, 1, max_level),
            DebugField('exp', 'EXP', unit.exp, 0, 100),
            DebugField('hp', 'HP', unit.get_hp(), 0, unit.get_max_hp()),
            DebugField('mana', 'Mana', unit.get_mana(), 0, unit.get_max_mana()),
            DebugField('fatigue', 'Fatigue', unit.get_fatigue(), 0, 9999),
            DebugField('guard', 'Guard', unit.get_guard_gauge(), 0, unit.get_max_guard_gauge()),
            DebugField('movement', 'Move Left', unit.movement_left, 0, 999),
        ]
        if unit.position and game.tilemap:
            fields.extend([
                DebugField('position_x', 'Position X', unit.position[0], 0, game.tilemap.width - 1),
                DebugField('position_y', 'Position Y', unit.position[1], 0, game.tilemap.height - 1),
            ])
        for stat in DB.stats:
            fields.append(DebugField(
                f'stat:{stat.nid}', f'{stat.name or stat.nid} (Stat)',
                unit.stats.get(stat.nid, 0), -999, unit.get_stat_cap(stat.nid)))
        for stat in DB.stats:
            fields.append(DebugField(
                f'growth:{stat.nid}', f'{stat.name or stat.nid} (Growth)',
                unit.growths.get(stat.nid, 0), -999, 999))
        for stat in DB.stats:
            fields.append(DebugField(
                f'cap:{stat.nid}', f'{stat.name or stat.nid} (Cap Mod)',
                unit.stat_cap_modifiers.get(stat.nid, 0), -999, 999))
        for weapon in DB.weapons:
            fields.append(DebugField(
                f'wexp:{weapon.nid}', f'{weapon.name or weapon.nid} (WEXP)',
                unit.wexp.get(weapon.nid, 0), 0,
                unit_funcs.get_weapon_cap(unit, weapon.nid)))
        return fields

    @staticmethod
    def set_unit_field(unit: UnitObject, field: DebugField, value: int) -> int:
        value = int(utils.clamp(value, field.minimum, field.maximum))
        if field.key == 'level':
            action.do(action.SetLevel(unit, value))
        elif field.key == 'exp':
            action.do(action.SetExp(unit, value))
        elif field.key == 'hp':
            action.do(action.SetHP(unit, value))
        elif field.key == 'mana':
            action.do(action.SetMana(unit, value))
        elif field.key == 'fatigue':
            action.do(action.ChangeFatigue(unit, value - unit.get_fatigue()))
        elif field.key == 'guard':
            unit.set_guard_gauge(value)
            game.on_alter_game_state()
        elif field.key == 'movement':
            action.do(action.SetMovementLeft(unit, value))
        elif field.key == 'position_x':
            RuntimeDebugger.teleport(unit, (value, unit.position[1]))
            value = unit.position[0]
        elif field.key == 'position_y':
            RuntimeDebugger.teleport(unit, (unit.position[0], value))
            value = unit.position[1]
        elif field.key.startswith('stat:'):
            stat_nid = field.key.partition(':')[2]
            delta = value - unit.stats.get(stat_nid, 0)
            action.do(action.ApplyStatChanges(unit, {stat_nid: delta}, False))
        elif field.key.startswith('growth:'):
            stat_nid = field.key.partition(':')[2]
            delta = value - unit.growths.get(stat_nid, 0)
            action.do(action.ApplyGrowthChanges(unit, {stat_nid: delta}))
        elif field.key.startswith('cap:'):
            stat_nid = field.key.partition(':')[2]
            delta = value - unit.stat_cap_modifiers.get(stat_nid, 0)
            action.do(action.ChangeStatCapModifiers(unit, {stat_nid: delta}))
        elif field.key.startswith('wexp:'):
            weapon_nid = field.key.partition(':')[2]
            action.execute(action.SetWexp(unit, weapon_nid, value))
        return value

    @staticmethod
    def max_out_unit(unit: UnitObject) -> None:
        stat_changes = {
            stat.nid: unit.get_stat_cap(stat.nid) - unit.stats.get(stat.nid, 0)
            for stat in DB.stats
        }
        action.do(action.ApplyStatChanges(unit, stat_changes, False))

        klass = DB.classes.get(unit.klass)
        if klass:
            action.do(action.SetLevel(unit, klass.max_level))
        action.do(action.SetExp(unit, 100))

        for weapon in DB.weapons:
            if weapon.nid in unit.wexp:
                cap = unit_funcs.get_weapon_cap(unit, weapon.nid)
                action.execute(action.SetWexp(unit, weapon.nid, cap))

        action.do(action.SetHP(unit, unit.get_max_hp()))
        action.do(action.SetMana(unit, unit.get_max_mana()))
        unit.set_guard_gauge(unit.get_max_guard_gauge())
        game.on_alter_game_state()

    @staticmethod
    def max_out_units(units: List[UnitObject]) -> int:
        for unit in units:
            RuntimeDebugger.max_out_unit(unit)
        return len(units)

    @staticmethod
    def player_units() -> List[UnitObject]:
        return [
            unit for unit in game.get_all_units(False)
            if unit.team == 'player' and 'Tile' not in unit.tags
        ]

    @staticmethod
    def enemy_units() -> List[UnitObject]:
        return [
            unit for unit in game.get_all_units(False)
            if unit.team in DB.teams.enemies and 'Tile' not in unit.tags
        ]

    @staticmethod
    def set_enemy_hp_to_one() -> int:
        units = RuntimeDebugger.enemy_units()
        for unit in units:
            action.do(action.SetHP(unit, 1))
        return len(units)

    @staticmethod
    def disable_enemy_ai() -> int:
        units = RuntimeDebugger.enemy_units()
        for unit in units:
            action.do(action.ChangeAI(unit, 'None'))
            action.do(action.ChangeRoamAI(unit, 'None'))
            action.do(action.ChangeAIGroup(unit, None))
            unit.has_run_ai = True
        return len(units)

    @staticmethod
    def give_item(unit: UnitObject, item_nid: NID, uses: Optional[int] = None) -> bool:
        item = item_funcs.create_item(unit, item_nid)
        if not item:
            return False
        if uses is not None:
            uses = max(0, int(uses))
            if 'starting_uses' in item.data:
                action.do(action.SetObjData(item, 'starting_uses', uses))
                action.do(action.SetObjData(item, 'uses', uses))
            elif 'starting_c_uses' in item.data:
                action.do(action.SetObjData(item, 'starting_c_uses', uses))
                action.do(action.SetObjData(item, 'c_uses', uses))
            else:
                raise ValueError(f'{item_nid} does not use charges.')
        game.register_item(item)
        action.do(action.GiveItem(unit, item))
        if item not in unit.items:
            game.unregister_item(item)
            return False
        return True

    @staticmethod
    def can_teleport(unit: UnitObject, pos: Pos) -> Tuple[bool, str]:
        if not game.tilemap or not game.tilemap.check_bounds(pos):
            return False, 'Destination is outside the map.'
        occupant = game.board.get_unit(pos)
        if occupant and occupant is not unit:
            return False, f'{occupant.nid} already occupies that tile.'
        if not unit.position:
            return False, 'Selected unit is not currently on the map.'
        return True, ''

    @staticmethod
    def teleport(unit: UnitObject, pos: Pos) -> Tuple[bool, str]:
        valid, message = RuntimeDebugger.can_teleport(unit, pos)
        if not valid:
            return False, message
        if unit.position != pos:
            action.do(action.Teleport(unit, pos))
        return True, f'{unit.nid} moved to {pos}.'

    @staticmethod
    def set_money(value: int) -> int:
        value = max(0, int(value))
        action.do(action.GainMoney(game.current_party, value - game.get_money()))
        return game.get_money()

    @staticmethod
    def set_turn_count(value: int) -> int:
        game.turncount = max(0, int(value))
        game.on_alter_game_state()
        return game.turncount

    @staticmethod
    def set_turnwheel(uses: int, enabled: bool) -> Tuple[int, bool]:
        uses = max(-1, int(uses))
        enabled = bool(enabled)
        action.do(action.SetGameVar('_current_turnwheel_uses', uses))
        action.do(action.SetGameVar('_max_turnwheel_uses', uses))
        action.do(action.SetGameVar('_turnwheel', enabled))
        game.on_alter_game_state()
        return uses, enabled

    @staticmethod
    def set_weather(weather_nid: Optional[NID]) -> Optional[NID]:
        if not game.tilemap:
            raise ValueError('A chapter map must be active to change weather.')
        for weather in list(game.tilemap.weather):
            action.do(action.RemoveWeather(weather.nid, weather.pos))
        if weather_nid:
            action.do(action.AddWeather(weather_nid, None))
        game.on_alter_game_state()
        return weather_nid

    @staticmethod
    def _queue_event(script: str) -> None:
        trigger = GenericTrigger(
            unit1=RuntimeDebugger.selected_unit(),
            position=game.cursor.position if game.cursor else None)
        game.events._add_event_from_script('runtime_debugger', script, trigger)

    @staticmethod
    def complete_current_chapter() -> None:
        RuntimeDebugger._queue_event('win_game')

    @staticmethod
    def go_to_chapter(level_nid: NID) -> bool:
        if level_nid not in DB.levels:
            return False
        # Set the target inside the event that ends the current level.  If the
        # event is never started, no _goto_level redirect is left behind.
        RuntimeDebugger._queue_event(f'set_next_chapter;{level_nid}\nwin_game')
        return True
