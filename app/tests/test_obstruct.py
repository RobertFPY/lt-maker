import importlib.util
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine.pathfinding import node, pathfinding
from app.utilities.grid import BoundedGrid


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class ObstructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}
        component_path = os.path.join(
            PROJECT_PATH, 'resources', 'custom_components',
            'custom_skill_components.py')
        spec = importlib.util.spec_from_file_location(
            'obstruct_test_custom_skills', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def test_tiers_use_standard_feh_hp_thresholds(self):
        for tier, threshold in ((1, 0.9), (2, 0.7), (3, 0.5)):
            with self.subTest(tier=tier):
                components = dict(self.skills['Obstruct_T%d' % tier][
                    'components'])
                self.assertEqual(threshold, components['obstruct'])
                self.assertNotIn('do_nothing', components)

    def test_obstruct_blocks_enemy_without_pass_at_threshold(self):
        component = self.custom_skills.Obstruct(0.7)
        holder = SimpleNamespace(
            position=(2, 2), get_hp=lambda: 7, get_max_hp=lambda: 10)
        mover = SimpleNamespace()
        with patch.object(self.custom_skills.skill_system, 'check_enemy',
                          return_value=True), \
                patch.object(self.custom_skills.skill_system, 'pass_through',
                             return_value=False):
            self.assertTrue(component.obstructs_movement(holder, mover))
        with patch.object(self.custom_skills.skill_system, 'check_enemy',
                          return_value=True), \
                patch.object(self.custom_skills.skill_system, 'pass_through',
                             return_value=True):
            self.assertFalse(component.obstructs_movement(holder, mover))

    def test_obstructed_tile_is_a_valid_endpoint_but_not_a_through_tile(self):
        grid = BoundedGrid((5, 1), (0, 0, 4, 0))
        for x in range(5):
            grid.append(node.Node(x, 0, True, 1))
        pathfinder = pathfinding.Djikstra((0, 0), grid)
        valid_moves = pathfinder.process(
            lambda pos: True, 4,
            can_continue_through=lambda pos: pos != (1, 0))
        self.assertIn((1, 0), valid_moves)
        self.assertNotIn((2, 0), valid_moves)


if __name__ == '__main__':
    unittest.main()
