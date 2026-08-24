import importlib
import json
import os
import unittest
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION

PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class _Unit:
    def __init__(self, nid, position, hp=20, dead=False, is_dying=False):
        self.nid = nid
        self.position = position
        self.hp = hp
        self.dead = dead
        self.is_dying = is_dying

    def get_hp(self):
        return self.hp

    def set_hp(self, hp):
        self.hp = hp


class _Board:
    def __init__(self, units, bounds=(0, 0, 5, 5)):
        self.units = units
        self.bounds = bounds

    def check_bounds(self, position):
        left, top, right, bottom = self.bounds
        return left <= position[0] <= right and top <= position[1] <= bottom

    def get_unit(self, position):
        return next((unit for unit in self.units if unit.position == position), None)


class MovementFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'items.json'),
                  encoding='utf-8') as items_file:
            cls.items = {item['nid']: item for item in json.load(items_file)}
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.category.json'),
                  encoding='utf-8') as categories_file:
            cls.skill_categories = json.load(categories_file)
        RESOURCES.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)
        DB.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)
        cls.components = importlib.import_module('custom_components.custom_item_components')

    def setUp(self):
        self.user = _Unit('user', (2, 2))
        self.foe = _Unit('foe', (3, 2))
        self.board = _Board([self.user, self.foe])
        self.actions = []
        self.patches = [
            patch.object(self.components.game, 'board', self.board),
            patch.object(self.components.skill_system, 'ignore_forced_movement', return_value=False),
            patch.object(self.components.movement_funcs, 'get_mcost', return_value=1),
            patch.object(self.components.action, 'do', side_effect=self._apply_action),
        ]
        for patched in self.patches:
            patched.start()

    def tearDown(self):
        for patched in reversed(self.patches):
            patched.stop()

    def _apply_action(self, movement_action):
        self.actions.append(movement_action)
        if hasattr(movement_action, 'new_pos'):
            movement_action.unit.position = movement_action.new_pos
        elif hasattr(movement_action, 'new_hp'):
            movement_action.unit.set_hp(movement_action.new_hp)

    @staticmethod
    def _component_nids(prefab):
        return [component_nid for component_nid, _ in prefab['components']]

    def test_project_wires_each_movement_skill_to_one_local_component(self):
        expected = {
            'Hit_and_Run_T1': ('Hit_and_Run', 'backdash_initiate'),
            'Knock_Back_T1': ('Knock_Back', 'shove_on_end_combat_initiate'),
            'Knock_Back_T2': ('Knock_Back_Plus', 'shove_on_end_combat_initiate_plus'),
            'Drag_Back_T1': ('Drag_Back', 'draw_back_on_end_combat_initiate'),
            'Lunge_T1': ('Lunge', 'swap_on_end_combat_initiate_alive'),
        }
        for skill_nid, (item_nid, component_nid) in expected.items():
            with self.subTest(skill_nid=skill_nid):
                skill_components = self._component_nids(self.skills[skill_nid])
                self.assertEqual(1, skill_components.count('item_override'))
                self.assertEqual([component_nid], [nid for nid in self._component_nids(self.items[item_nid]) if nid in {
                    'backdash_initiate', 'shove_on_end_combat_initiate',
                    'shove_on_end_combat_initiate_plus', 'draw_back_on_end_combat_initiate',
                    'swap_on_end_combat_initiate_alive'}])
        self.assertEqual(set(expected), {
            nid for nid, category in self.skill_categories.items()
            if category == 'Skill System Slot B/Movement Family'})

    def test_resources_then_database_instantiates_lunges_local_component(self):
        RESOURCES.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)
        DB.load(PROJECT_PATH, CURRENT_SERIALIZATION_VERSION)

        component = DB.items.get('Lunge').components.get(
            'swap_on_end_combat_initiate_alive')
        self.assertIsNotNone(component)
        self.assertEqual('swap_on_end_combat_initiate_alive', component.nid)

    def test_hit_and_run_moves_living_user_once_after_combat_even_when_foe_dies(self):
        self.foe.hp = 0
        component = self.components.BackdashInitiate(1)

        component.end_combat([], self.user, None, self.foe, None, 'attack')
        component.end_combat([], self.user, None, self.foe, None, 'defense')

        self.assertEqual((1, 2), self.user.position)
        self.assertEqual(1, len(self.actions))
        self.assertIsInstance(self.actions[0], self.components.action.ForcedMovement)
        self.assertFalse(hasattr(self.components.BackdashInitiate, 'target_restrict'))
        self.assertFalse(hasattr(self.components.BackdashInitiate, 'on_hit'))

        self.user.position = (2, 2)
        self.actions.clear()
        self.board.units.append(_Unit('blocker', (1, 2)))
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual((2, 2), self.user.position)
        self.assertEqual([], self.actions)

    def test_knock_back_requires_living_positioned_units_and_ignores_movement_stat(self):
        component = self.components.ShoveOnEndCombatInitiate(1)
        with patch.object(self.components.movement_funcs, 'get_mcost', return_value=2):
            component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual((4, 2), self.foe.position)

        self.actions.clear()
        self.foe.position = (3, 2)
        self.foe.dead = True
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual([], self.actions)

    def test_knock_back_plus_only_damages_an_impassable_destination(self):
        component = self.components.ShoveOnEndCombatInitiatePlus({'space': 1, 'damage': 10})
        self.board.bounds = (0, 0, 3, 5)
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual(20, self.foe.hp)
        self.assertEqual([], self.actions)

        self.board.bounds = (0, 0, 5, 5)
        blocker = _Unit('blocker', (4, 2))
        self.board.units.append(blocker)
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual(20, self.foe.hp)
        self.assertEqual([], self.actions)

        self.board.units.remove(blocker)
        with patch.object(self.components.movement_funcs, 'get_mcost', return_value=99):
            component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual(10, self.foe.hp)
        self.assertIsInstance(self.actions[0], self.components.action.SetHP)

        self.actions.clear()
        self.foe.hp = 5
        with patch.object(self.components.movement_funcs, 'get_mcost', return_value=99):
            component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual(1, self.foe.hp)

    def test_forced_movement_immunity_prevents_actions(self):
        component = self.components.ShoveOnEndCombatInitiate(1)
        with patch.object(self.components.skill_system, 'ignore_forced_movement', return_value=True):
            component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual((3, 2), self.foe.position)
        self.assertEqual([], self.actions)

    def test_drag_back_is_atomic_and_allows_foe_to_fill_the_users_vacated_tile(self):
        component = self.components.DrawBackOnEndCombatInitiate(1)
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual((1, 2), self.user.position)
        self.assertEqual((2, 2), self.foe.position)
        self.assertEqual(2, len(self.actions))
        self.assertTrue(all(isinstance(act, self.components.action.Teleport) for act in self.actions))

        with patch.object(self.components.action.game, 'leave'), \
                patch.object(self.components.action.game, 'arrive', side_effect=lambda unit, pos: setattr(unit, 'position', pos)), \
                patch.object(self.components.action.UpdateFogOfWar, 'reverse'):
            for move_action in reversed(self.actions):
                move_action.reverse()
        self.assertEqual((2, 2), self.user.position)
        self.assertEqual((3, 2), self.foe.position)

        self.user.position, self.foe.position = (2, 2), (3, 2)
        self.actions.clear()
        blocker = _Unit('blocker', (1, 2))
        self.board.units.append(blocker)
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual((2, 2), self.user.position)
        self.assertEqual((3, 2), self.foe.position)
        self.assertEqual([], self.actions)

    def test_lunge_swaps_only_living_positioned_units_after_initiated_combat(self):
        component = self.components.SwapOnEndCombatInitiateAlive()
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual(1, len(self.actions))
        self.assertIsInstance(self.actions[0], self.components.action.Swap)

        self.actions.clear()
        self.user.dead = True
        component.end_combat([], self.user, None, self.foe, None, 'attack')
        self.assertEqual([], self.actions)


if __name__ == '__main__':
    unittest.main()
