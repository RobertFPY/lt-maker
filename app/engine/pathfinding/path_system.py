from __future__ import annotations
from typing import TYPE_CHECKING, List, Set

from app.engine import (equations, skill_system)
from app.engine.movement import movement_funcs
from app.engine.pathfinding import pathfinding
from app.engine.game_state import GameState
from app.utilities.typing import Pos

if TYPE_CHECKING:
    from app.engine.objects.unit import UnitObject
    from app.engine.pathfinding.node import Node

class PathSystem():
    def __init__(self, game: GameState = None):
        if game:
            self.game = game
        else:
            from app.engine.game_state import game
            self.game = game

    def get_valid_moves(self, unit: UnitObject, force: bool = False, witch_warp: bool = True) -> Set[Pos]:
        """
        Given a unit, finds all positions on the map they can move to
        """
        # Assumes unit is on the map
        if not force and unit.finished:
            return set()
        mtype = movement_funcs.get_movement_group(unit)
        grid = self.game.board.get_movement_grid(mtype)
        bounds = self.game.board.bounds
        height = self.game.board.height
        start_pos = unit.position
        pathfinder = pathfinding.Djikstra(start_pos, grid, bounds, height, unit.team)
        movement_left = equations.parser.movement(unit) if force else unit.movement_left

        if skill_system.pass_through(unit):
            can_move_through = lambda team, adj: True
        else:
            can_move_through = self.game.board.can_move_through
        valid_moves = pathfinder.process(can_move_through, movement_left)
        valid_moves.add(unit.position)
        if witch_warp:
            witch_warp = set(skill_system.witch_warp(unit))
            valid_moves |= witch_warp
        return valid_moves

    def get_path(self, unit: UnitObject, position: Pos, ally_block: bool = False, 
                 use_limit: bool = False, free_movement: bool = False) -> List[Pos]:
        """
        Given a unit and a goal position, find the best path for the unit to get to that goal position
        Returns the path (a list of positions), with the goal position first and the start position last
        """
        mtype = movement_funcs.get_movement_group(unit)
        grid = self.game.board.get_movement_grid(mtype)
        start_pos = unit.position

        bounds = self.game.board.bounds
        height = self.game.board.height

        if skill_system.pass_through(unit) or free_movement:
            can_move_through = lambda team, adj: True
        else:
            if ally_block:
                can_move_through = self.game.board.can_move_through_ally_block
            else:
                can_move_through = self.game.board.can_move_through

        if free_movement:
            pathfinder = pathfinding.ThetaStar(start_pos, position, grid, bounds, height, unit.team)
        else:
            pathfinder = pathfinding.AStar(start_pos, position, grid, bounds, height, unit.team)

        limit = unit.movement_left if use_limit else None
        path = pathfinder.process(can_move_through, limit=limit)
        if path is None:
            return []
        return path

    def check_path(self, unit: UnitObject, path: List[Pos]) -> bool:
        """
        Determines whether path is possible for the unit to traverse
        Checks that all positions in path are adjacent to each other in the chain
        And that moving through these positions doesn't reduce unit's remaining movement points
        to less than 0
        Returns True if possible, False otherwise
        """
        movement = unit.movement_left
        prev_pos = None
        for pos in path[:-1]:  # Don't need to count the starting position
            if prev_pos and pos not in self.game.target_system.get_adjacent_positions(prev_pos):
                return False
            mcost = movement_funcs.get_mcost(unit, pos)
            movement -= mcost
            if movement < 0:
                return False
            prev_pos = pos
        return True

    def travel_algorithm(self, path: List[Pos], moves: int, unit: UnitObject, grid: List[Node]) -> Pos:
        """
        Given a long path, travels along that path as far as possible.
        Used by AI to travel along it's determined secondary path to the maximum extent
        """
        if not path:
            return unit.position

        moves_left = moves
        through_path = 0
        for position in path[::-1][1:]:  # Remove start position, travel backwards
            moves_left -= grid[position[0] * self.game.tilemap.height + position[1]].cost
            if moves_left >= 0:
                through_path += 1
            else:
                break
        # Don't move where a unit already is, and don't make through path < 0
        # Lower the through path by one, cause we can't move that far
        while through_path > 0 and any(other_unit.position == path[-(through_path + 1)] for other_unit in self.game.units if unit is not other_unit):
            through_path -= 1
        return path[-(through_path + 1)]  # Travel as far as we can
