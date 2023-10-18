from __future__ import annotations
from typing import FrozenSet, TYPE_CHECKING, List, Optional, Set, Tuple
from functools import lru_cache

from app.data.database.database import DB
from app.engine import (combat_calcs, item_funcs, item_system,
                        line_of_sight, skill_system)
from app.engine.movement import movement_funcs
from app.engine.game_state import GameState
from app.utilities import utils
from app.utilities.typing import Pos

if TYPE_CHECKING:
    from app.engine.objects.unit import UnitObject
    from app.engine.objects.item import ItemObject

class TargetSystem():
    def __init__(self, game: GameState = None):
        if game:
            self.game = game
        else:
            from app.engine.game_state import game
            self.game = game

    # Consider making these sections faster
    def get_shell(self, valid_moves: Set[Pos], potential_range: Set[int], bounds: Tuple[int, int, int, int], manhattan_restriction: set = None) -> Set[Pos]:
        valid_attacks = set()
        if manhattan_restriction:
            for valid_move in valid_moves:
                valid_attacks |= self.restricted_manhattan_spheres(potential_range, valid_move[0], valid_move[1], manhattan_restriction)
        else:
            for valid_move in valid_moves:
                valid_attacks |= self.find_manhattan_spheres(potential_range, valid_move[0], valid_move[1])
        return {pos for pos in valid_attacks if bounds[0] <= pos[0] <= bounds[2] and bounds[1] <= pos[1] <= bounds[3]}

    def restricted_manhattan_spheres(self, rng: Set[int], x: int, y: int, manhattan_restriction: Set[Pos]) -> Set[Pos]:
        sphere = self.cached_base_manhattan_spheres(frozenset(rng))
        sphere = {(a + x, b + y) for (a, b) in sphere if (a, b) in manhattan_restriction}
        return sphere

    # Consider making these sections faster -- use memory?
    def find_manhattan_spheres(self, rng: Set[int], x: int, y: int) -> Set[Pos]:
        sphere = self.cached_base_manhattan_spheres(frozenset(rng))
        sphere = {(a + x, b + y) for (a, b) in sphere}
        return sphere

    @lru_cache(1024)
    def cached_base_manhattan_spheres(self, rng: FrozenSet[int]) -> Set[Pos]:
        _range = range
        _abs = abs
        sphere = set()
        for r in rng:
            for i in _range(-r, r+1):
                magn = _abs(i)
                dx = i
                dy = r - magn
                sphere.add((dx, dy))
                sphere.add((dx, -dy))
        return sphere

    def get_nearest_open_tile(self, unit: UnitObject, position: Pos) -> Optional[Pos]:
        r = 0
        _abs = abs
        while r < 10:
            for x in range(-r, r + 1):
                magn = _abs(x)
                n1 = position[0] + x, position[1] + r - magn
                n2 = position[0] + x, position[1] - r + magn
                if movement_funcs.check_weakly_traversable(unit, n1) and not self.game.board.get_unit(n1) and not self.game.movement.check_if_occupied_in_future(n1):
                    return n1
                elif movement_funcs.check_weakly_traversable(unit, n2) and not self.game.board.get_unit(n2) and not self.game.movement.check_if_occupied_in_future(n2):
                    return n2
            r += 1
        return None

    def get_nearest_open_tile_rationalization(self, unit: UnitObject, position: Pos, taken_positions: Set[Pos]) -> Optional[Pos]:
        r = 0
        _abs = abs
        while r < 10:
            for x in range(-r, r + 1):
                magn = _abs(x)
                n1 = position[0] + x, position[1] + r - magn
                n2 = position[0] + x, position[1] - r + magn
                if movement_funcs.check_weakly_traversable(unit, n1) and not self.game.board.get_unit(n1) and n1 not in taken_positions:
                    return n1
                elif movement_funcs.check_weakly_traversable(unit, n2) and not self.game.board.get_unit(n2) and n2 not in taken_positions:
                    return n2
            r += 1
        return None

    def distance_to_closest_enemy(self, unit: UnitObject, pos: Optional[Pos] = None) -> int:
        if pos is None:
            pos = unit.position
        enemy_list = [u for u in self.game.units if u.position and skill_system.check_enemy(u, unit)]
        if not enemy_list:
            return 100  # No enemies
        dist_list = [utils.calculate_distance(enemy.position, pos) for enemy in enemy_list]
        return min(dist_list)

    def get_adjacent_positions(self, pos: Pos) -> List[Pos]:
        x, y = pos
        adjs = ((x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1))
        return [a for a in adjs if self.game.board.check_bounds(a)]

    def get_adj_units(self, unit: UnitObject) -> List[UnitObject]:
        adj_positions = self.get_adjacent_positions(unit.position)
        adj_units = [self.game.board.get_unit(pos) for pos in adj_positions]
        adj_units = [u for u in adj_units if u]
        return adj_units

    def get_adj_allies(self, unit: UnitObject) -> List[UnitObject]:
        adj_units = self.get_adj_units(unit)
        adj_allies = [u for u in adj_units if skill_system.check_ally(unit, u)]
        return adj_allies

    def is_tile(self, pos: Pos) -> bool:
        return self.game.board.get_unit(pos) and 'Tile' in self.game.board.get_unit(pos).tags

    def fog_of_war(self, unit: UnitObject, item: ItemObject) -> bool:
        return (unit.team == 'player' or DB.constants.value('ai_fog_of_war')) and not item_system.ignore_fog_of_war(unit, item)

    def check_fog_of_war(self, unit: UnitObject, pos: Pos) -> bool:
        """
        Returns True if unit can see position
        """
        return (pos == unit.position or
                self.game.board.in_vision(pos, unit.team) or
                self.is_tile(pos))

    def filter_splash_through_fog_of_war(self, unit, main_target_pos: Optional[Pos], 
                                         splash_positions: List[Pos]
                                         ) -> Tuple[Optional[Pos], List[Pos]]:
        """
        Returns only the main target pos and the splash positions that can be seen in fog of war
        """
        # Handle main target position first
        if main_target_pos:
            main_target_pos = main_target_pos if self.check_fog_of_war(unit, main_target_pos) else None
        splash_positions = [splash_pos for splash_pos in splash_positions if self.check_fog_of_war(unit, splash_pos)]
        return main_target_pos, splash_positions

    def get_attacks(self, unit: UnitObject, item: ItemObject = None, force: bool = False) -> Set[Pos]:
        """
        Determines all possible positions the unit could attack given the item's range
        from the unit's current position
        Does not attempt to determine if an enemy is actually in that place 
        or if the item could actually target that position (can't heal a full health unit, etc.)
        """
        if not force and unit.has_attacked:
            return set()
        if not item:
            item = unit.get_weapon()
        if not item:
            return set()
        no_attack_after_move = item_system.no_attack_after_move(unit, item) or skill_system.no_attack_after_move(unit)
        if no_attack_after_move and unit.has_moved_any_distance:
            return set()

        item_range = item_funcs.get_range(unit, item)
        if not item_range:
            return set()

        if max(item_range) >= 99:
            attacks = {(x, y) for x in range(self.game.tilemap.width) for y in range(self.game.tilemap.height)}
        else:
            manhattan_restriction = item_system.range_restrict(unit, item)
            attacks = self.get_shell({unit.position}, item_range, self.game.board.bounds, manhattan_restriction)

        return attacks
        
    def _get_all_attacks(self, unit: UnitObject, valid_moves: List[Tuple[int, int]],
                         items: List[ItemObject]) -> (Set[Tuple[int, int]], int):
        """
        Returns a set of all positions that the unit can attack at given a list of valid moves
        and the max range of all items they can use
        """
        attacks = set()
        max_range = 0
        for item in items:
            no_attack_after_move = item_system.no_attack_after_move(unit, item) or skill_system.no_attack_after_move(unit)
            if no_attack_after_move and unit.has_moved_any_distance:
                continue
            item_range = item_funcs.get_range(unit, item)
            if not item_range:  # Possible if you have a weapon with say range 2-3 but your maximum range is limited to 1
                continue
            max_range = max(max_range, max(item_range))
            if max_range >= 99:
                attacks = {(x, y) for x in range(self.game.tilemap.width) for y in range(self.game.tilemap.height)}
            else:
                manhattan_restriction = item_system.range_restrict(unit, item)
                if no_attack_after_move:
                    attacks |= self.get_shell({unit.position}, item_range, self.game.board.bounds, manhattan_restriction)
                else:
                    attacks |= self.get_shell(valid_moves, item_range, self.game.board.bounds, manhattan_restriction)
        return (attacks, max_range)

    def get_all_attacks_in_range(self, unit: UnitObject, valid_moves: List[Tuple[int, int]],
                                 items: List[ItemObject]) -> Set[Tuple[int, int]]:
        """
        Returns all possible attacks by a unit from any of their positions with any of their items.
        Considers target restrictions and vision restrictions.
        Does not consider line of sight.
        """
        attacks, _ = self._get_all_attacks(unit, valid_moves, items)
        all_valid_targets = set()
        for item in items:
            # A list of positions if the position
            # 1. Is a valid target
            # 2. Is not a restricted target
            pos_list = set()
            if item.sequence_item and item.subitems:
                item = item.subitems[0]
            for pos in item_system.valid_targets(unit, item):
                splash = item_system.splash(unit, item, pos)
                if self.fog_of_war(unit, item):
                    splash = self.filter_splash_through_fog_of_war(unit, *splash)
                if item_system.target_restrict(unit, item, *splash):
                    pos_list.add(pos)
            all_valid_targets |= pos_list
        return attacks.intersection(all_valid_targets)
        
    def _get_possible_attacks(self, unit: UnitObject, valid_moves: List[Tuple[int, int]], items: List[ItemObject]) -> Set[Tuple[int, int]]:
        """
        Returns all possible attacks by a unit from any of their positions with any of the items.
        Does not consider target restrictions or vision restrictions except line of sight.
        """
        items_standard, items_ignore_los = [], []
        for item in items:
            (items_standard, items_ignore_los)[item_system.ignore_line_of_sight(unit, item)].append(item)
        # First get all attacks by items that obey line of sight
        attacks, max_range = self._get_all_attacks(unit, valid_moves, items_standard)
        # max_range is used only for making line of sight calculation faster
        # Filter away those that aren't in line of sight
        if DB.constants.value('line_of_sight'):
            attacks = set(line_of_sight.line_of_sight(valid_moves, attacks, max_range))
        # Now get all attacks by items that ignore line of sight
        attacks2, _ = self._get_all_attacks(unit, valid_moves, items_ignore_los)
        attacks |= attacks2
        return attacks

    def get_possible_attacks(self, unit: UnitObject, valid_moves: List[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        Returns all possible attacks by a unit from any of their valid moves with any of their WEAPONS
        Does not consider target restrictions or vision restrictions except line of sight
        """
        return self._get_possible_attacks(unit, valid_moves, self.get_all_weapons(unit))

    def get_possible_spell_attacks(self, unit: UnitObject, valid_moves: List[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        Returns all possible attacks by a unit from any of their valid moves with any of their SPELLS
        Does not consider target restrictions or vision restrictions except line of sight
        """
        return self._get_possible_attacks(unit, valid_moves, self.get_all_spells(unit))

    # Uses all weapons the unit has access to to find its potential range
    def find_potential_range(self, unit, weapon=True, spell=False, boundary=False) -> set:
        if weapon and spell:
            items = [item for item in unit.items if item_funcs.available(unit, item) and
                     item_system.is_weapon(unit, item) or item_system.is_spell(unit, item)]
        elif weapon:
            items = self.get_all_weapons(unit)
        elif spell:
            items = self.get_all_spells(unit)
        else:
            return set()
        potential_range = set()
        for item in items:
            for rng in item_funcs.get_range(unit, item):
                potential_range.add(rng)
        return potential_range

    def targets_in_range(self, unit: UnitObject, item: ItemObject) -> set:
        """
        Given a unit and an item, finds a set of
        positions that are within range
        """
        possible_targets = item_system.valid_targets(unit, item)
        item_range = item_funcs.get_range(unit, item)
        return {t for t in possible_targets if utils.calculate_distance(unit.position, t) in item_range}

    def get_valid_targets(self, unit, item=None) -> set:
        """
        Determines all the valid targets given use of the item
        item_system.valid_targets takes care of range
        """
        if not item:
            item = unit.get_weapon()
        if not item:
            return set()
        if ((item_system.no_attack_after_move(unit, item) or skill_system.no_attack_after_move(unit))
            and unit.has_moved_any_distance):
            return set()
        # Check sequence item targeting
        if item.sequence_item:
            all_targets = set()
            for subitem in item.subitems:
                valid_targets = self.get_valid_targets(unit, subitem)
                if not valid_targets:
                    return set()
                all_targets |= valid_targets
            if not item_system.allow_same_target(unit, item) and len(all_targets) < sum(1 if item_system.allow_less_than_max_targets(unit, si) else item_system.num_targets(unit, si) for si in item.subitems):
                return set()

        # Handle regular item targeting
        all_targets = self.targets_in_range(unit, item)
        valid_targets = set()
        for position in all_targets:
            splash = item_system.splash(unit, item, position)
            if self.fog_of_war(unit, item):
                splash = self.filter_splash_through_fog_of_war(unit, *splash)
            if item_system.target_restrict(unit, item, *splash):
                valid_targets.add(position)
        # Line of Sight
        if DB.constants.value('line_of_sight') and not item_system.ignore_line_of_sight(unit, item):
            item_range = item_funcs.get_range(unit, item)
            if item_range:
                max_item_range = max(item_range)
                valid_moves = [unit.position]
                valid_targets = set(line_of_sight.line_of_sight(valid_moves, valid_targets, max_item_range))
            else: # I think this is impossible to happen, as it is checked in various places above in this function
                valid_targets = set()
        # Make sure we have enough targets to satisfy the item
        if not item_system.allow_same_target(unit, item) and \
                not item_system.allow_less_than_max_targets(unit, item) and \
                len(valid_targets) < item_system.num_targets(unit, item):
            return set()
        return valid_targets

    def get_valid_targets_recursive_with_availability_check(self, unit, item) -> set:
        if item.multi_item:
            items = [sitem for sitem in item_funcs.get_all_items_from_multi_item(unit, item) if item_funcs.available(unit, sitem)]
        else:
            items = [item] if item_funcs.available(unit, item) else []
        valid_targets = set()
        for sitem in items:
            valid_targets |= self.get_valid_targets(unit, sitem)
        return valid_targets

    def get_weapons(self, unit: UnitObject) -> List[ItemObject]:
        return [item for item in unit.items if item_funcs.is_weapon_recursive(unit, item) and item_funcs.available(unit, item)]

    def get_all_weapons(self, unit: UnitObject) -> List[ItemObject]:
        return [item for item in item_funcs.get_all_items(unit) if item_system.is_weapon(unit, item) and item_funcs.available(unit, item)]

    def get_all_targets_with_items(self, unit, items: List[ItemObject]) -> set:
        targets = set()
        for item in items:
            targets |= self.get_valid_targets(unit, item)
        return targets

    def get_all_weapon_targets(self, unit) -> set:
        weapons = self.get_all_weapons(unit)
        return self.get_all_targets_with_items(unit, weapons)

    def get_spells(self, unit: UnitObject) -> List[ItemObject]:
        return [item for item in unit.items if item_funcs.is_spell_recursive(unit, item) and item_funcs.available(unit, item)]

    def get_all_spells(self, unit):
        return [item for item in item_funcs.get_all_items(unit) if item_system.is_spell(unit, item) and item_funcs.available(unit, item)]

    def get_all_spell_targets(self, unit) -> set:
        spells = self.get_all_spells(unit)
        return self.get_all_targets_with_items(unit, spells)

    def find_strike_partners(self, attacker, defender, item):
        '''Finds and returns a tuple of strike partners for the specified units
        First item in tuple is attacker partner, second is target partner
        Returns a tuple of None if no valid partner'''
        if not DB.constants.value('pairup'):
            return None, None
        if not attacker or not defender:
            return None, None
        if skill_system.check_ally(attacker, defender): # If targeting an ally
            return None, None
        if attacker.traveler or defender.traveler: # Dual guard cancels
            return None, None
        if not item_system.is_weapon(attacker, item): # If you're healing someone else
            return None, None
        if attacker.team == defender.team: # If you are the same team. Catches components who define their own check_ally function
            return None, None

        attacker_partner = None
        defender_partner = None
        attacker_adj_allies = self.get_adj_allies(attacker)
        attacker_adj_allies = [ally for ally in attacker_adj_allies if ally.get_weapon() and not item_system.cannot_dual_strike(ally, ally.get_weapon())]
        defender_adj_allies = self.get_adj_allies(defender)
        defender_adj_allies = [ally for ally in defender_adj_allies if ally.get_weapon() and not item_system.cannot_dual_strike(ally, ally.get_weapon())]
        attacker_partner = self.strike_partner_formula(attacker_adj_allies, attacker, defender, 'attack', (0, 0))
        defender_partner = self.strike_partner_formula(defender_adj_allies, defender, attacker, 'defense', (0, 0))

        if item_system.cannot_dual_strike(attacker, item):
            attacker_partner = None
        if defender.get_weapon() and item_system.cannot_dual_strike(defender, defender.get_weapon()):
            defender_partner = None
        if DB.constants.value('player_pairup_only'):
            if attacker.team != 'player':
                attacker_partner = None
            if defender.team != 'player':
                defender_partner = None

        if attacker_partner is defender_partner:
            # If both attacker and defender have the same partner something is weird
            return None, None
        return attacker_partner, defender_partner

    def strike_partner_formula(self, allies: list, attacker, defender, mode, attack_info):
        '''
        This is the formula for the best choice to make
        when autoselecting strike partners
        '''
        if not allies:
            return None
        damage = [combat_calcs.compute_assist_damage(ally, defender, ally.get_weapon(), defender.get_weapon(), mode, attack_info) for ally in allies]
        accuracy = [utils.clamp(combat_calcs.compute_hit(ally, defender, ally.get_weapon(), defender.get_weapon(), mode, attack_info)/100., 0, 1) for ally in allies]
        score = [dam * acc for dam, acc in zip(damage, accuracy)]
        max_score = max(score)
        max_index = score.index(max_score)
        return allies[max_index]

    def get_possible_attack_positions(self, unit, target, moves, item) -> list:
        """
        Copied from AI controller and modified slightly to exclude taken positions
        Finds all valid squares given a target and possible moves
        """
        restriction = item_system.range_restrict(unit, item)
        if restriction:
            return self._get_possible_attack_positions_restriction(unit, target, moves, item, restriction)
        
        a = self.find_manhattan_spheres(item_funcs.get_range(unit, item), *target)
        b = set(moves)
        positions = list(a & b)
        return [pos for pos in positions if not self.game.board.get_unit(pos) or self.game.board.get_unit(pos) == unit]
    
    def _get_possible_attack_positions_restriction(self, unit, target, moves, item, restriction) -> list:
        positions = set()
        for move in moves:
            a = self.restricted_manhattan_spheres(item_funcs.get_range(unit, item), *move, restriction)
            if target in a:
                positions.add(move)
        return list(positions)