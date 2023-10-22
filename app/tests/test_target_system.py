import unittest
from unittest.mock import MagicMock, Mock, patch, call
from app.engine.item_components.target_components import EvalSpecialRange, MaximumRange, MinimumRange, TargetsEnemies
from app.engine.objects.item import ItemObject
from app.engine.game_board import GameBoard

from app.engine.target_system import TargetSystem
from app.tests.mocks.mock_game import get_mock_game
from app.engine.objects.unit import UnitObject

class TargetSystemUnitTests(unittest.TestCase):
    def setUp(self):
        from app.data.database.database import DB
        DB.load('testing_proj.ltproj')
        self.game = get_mock_game()
        self.target_system = self.create_target_system()

        self.game.board = GameBoard(MagicMock())
        self.game.board.bounds = (0, 0, 99, 99)
        self.game.units = []

        self.player_unit = UnitObject('player')         
        self.player_unit.team = 'player'

        self.ally_unit = UnitObject('ally')
        self.ally_unit.team = 'player'

        self.enemy_unit = UnitObject('enemy')
        self.enemy_unit.team = 'enemy'

    def mock_weapon(self, target_pos, min_range, max_range):
        sword = ItemObject('weapon', 'weapon', 'a test weapon')
        targeting_component = TargetsEnemies()
        if target_pos:
            targeting_component.valid_targets = Mock(return_value=set([target_pos]))
        else:
            targeting_component.valid_targets = Mock(return_value=set())
        min_range_component = MinimumRange(value=min_range)
        max_range_component = MaximumRange(value=max_range)
        sword.components = [targeting_component, min_range_component, max_range_component]
        return sword

    def create_target_system(self):
        return TargetSystem(game=self.game)
    
    def test_targets_in_range_adjacent(self):
        '''
        An adjacent enemy should be a valid target
        '''
        self.player_unit.position = (0, 0)
        self.enemy_unit.position = (0, 1)
        self.game.units.append(self.player_unit)
        self.game.units.append(self.enemy_unit)

        weapon = self.mock_weapon(self.enemy_unit.position, 1, 1)
        
        self.assertEqual(len(self.target_system.targets_in_range(self.player_unit, weapon)), 1)

    def test_targets_in_range_adjacent_ally(self):
        '''
        An adjacent ally is not a valid target to attack
        '''
        self.player_unit.position = (0, 0)
        self.ally_unit.position = (0, 1)
        self.game.units.append(self.player_unit)
        self.game.units.append(self.ally_unit)

        weapon = self.mock_weapon(None, 1, 1)

        self.assertEqual(len(self.target_system.targets_in_range(self.player_unit, weapon)), 0)

    def test_targets_in_range_too_far(self):
        '''
        This enemy is too far from the player's position
        '''
        self.player_unit.position = (0, 0)
        self.enemy_unit.position = (0, 3)
        self.game.units.append(self.player_unit)
        self.game.units.append(self.enemy_unit)

        weapon = self.mock_weapon(self.enemy_unit.position, 1, 1)

        self.assertEqual(len(self.target_system.targets_in_range(self.player_unit, weapon)), 0)

    def _setup_board(self) -> list:
        valid_moves = [(0, 2), (1, 1), (0, 1), (0, 0)]
        self.game.board.unit_grid = [[self.player_unit], [self.enemy_unit], [], [], [], []]
        self.game.board.team_grid = [['player'], ['enemy'], [], [], [], []]
        self.game.board.height = 3
        return valid_moves

    def test_get_possible_attack_positions(self):
        self.player_unit.position = (0, 0)
        self.enemy_unit.position = (0, 1)
        self.game.units.append(self.player_unit)
        self.game.units.append(self.enemy_unit)

        valid_moves = self._setup_board()

        weapon = self.mock_weapon(self.enemy_unit.position, 1, 1)

        expected_positions = {(0, 2), (0, 0), (1, 1)}
        possible_positions = self.target_system.get_possible_attack_positions(self.player_unit, (0, 1), valid_moves, weapon)
        self.assertEqual(set(possible_positions), expected_positions)

    def test_get_possible_attack_positions_range_restrict(self):
        self.player_unit.position = (0, 0)
        self.enemy_unit.position = (0, 1)
        self.game.units.append(self.player_unit)
        self.game.units.append(self.enemy_unit)

        valid_moves = self._setup_board()

        weapon = self.mock_weapon(self.enemy_unit.position, 1, 1)
        eval_special_range = EvalSpecialRange(value='y > 0')
        weapon.components.append(eval_special_range)

        expected_positions = [(0, 0)]
        self.assertEqual(self.target_system.get_possible_attack_positions(self.player_unit, (0, 1), valid_moves, weapon), expected_positions)


if __name__ == '__main__':
    unittest.main()