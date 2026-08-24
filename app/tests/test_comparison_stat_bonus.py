import importlib.util
import json
import os
import unittest
from types import SimpleNamespace


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class ComparisonStatBonusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}
        with open(os.path.join(PROJECT_PATH, 'game_data', 'events.json'),
                  encoding='utf-8') as events_file:
            cls.events = json.load(events_file)
        component_path = os.path.join(
            PROJECT_PATH, 'resources', 'custom_components',
            'custom_skill_components.py')
        spec = importlib.util.spec_from_file_location(
            'comparison_stat_bonus_test_custom_skills', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def test_high_dragon_wall_provides_res_comparison_bonus(self):
        components = dict(self.skills['Dragon_Wall_T4']['components'])
        self.assertEqual(5, components['comparison_stat_bonus'])
        self.assertIn('skill_system.comparison_stat_bonus',
                      components['combat_condition'])

        component = self.custom_skills.ComparisonStatBonus(5)
        self.assertEqual(5, component.comparison_stat_bonus(None, 'RES'))
        self.assertEqual(0, component.comparison_stat_bonus(None, 'DEF'))

    def test_all_res_comparisons_use_the_shared_bonus_hook(self):
        for tier in range(1, 5):
            condition = dict(self.skills['Dragon_Wall_T%d' % tier][
                'components'])['combat_condition']
            self.assertIn('skill_system.comparison_stat_bonus', condition)

        res_comparison_events = [
            event for event in self.events
            if "unit.get_stat('RES')" in '\n'.join(event.get('_source', []))]
        for event in res_comparison_events:
            with self.subTest(event=event['nid']):
                self.assertIn('skill_system.comparison_stat_bonus',
                              '\n'.join(event['_source']))


if __name__ == '__main__':
    unittest.main()
