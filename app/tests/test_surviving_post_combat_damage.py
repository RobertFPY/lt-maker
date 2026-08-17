import importlib.util
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class _Unit:
    def __init__(self, hp):
        self.hp = hp
        self.skills = []

    def get_hp(self):
        return self.hp

    def set_hp(self, hp):
        self.hp = hp


class SurvivingPostCombatDamageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skills_file)}
        component_path = os.path.join(
            PROJECT_PATH, 'resources', 'custom_components',
            'custom_skill_components.py')
        spec = importlib.util.spec_from_file_location(
            'surviving_post_combat_test_custom_skills', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def test_only_initiator_strike_skills_use_survival_component(self):
        for nid in ('Poison_Strike_T1', 'Poison_Strike_T2',
                    'Poison_Strike_T3', 'Assassins_Strike_T4',
                    'Occultists_Strike_T4'):
            with self.subTest(skill=nid):
                components = dict(self.skills[nid]['components'])
                self.assertIn('surviving_initiator_post_combat_damage',
                              components)
                self.assertNotIn('better_post_combat_damage', components)

    def test_damage_requires_a_living_initiator_and_cannot_kill(self):
        component = self.custom_skills.SurvivingInitiatorPostCombatDamage(7)
        component.skill = SimpleNamespace(data={}, components=[])
        user = _Unit(1)
        target = _Unit(5)

        def apply_hp_set(action_to_apply):
            if isinstance(action_to_apply, self.custom_skills.action.SetHP):
                action_to_apply.do()

        with patch.object(self.custom_skills.skill_system, 'check_enemy',
                          return_value=True), \
                patch.object(self.custom_skills.action, 'do',
                             side_effect=apply_hp_set):
            component.end_combat([], user, None, target, None, 'attack')
        self.assertEqual(1, target.get_hp())

        target.set_hp(10)
        user.set_hp(0)
        with patch.object(self.custom_skills.skill_system, 'check_enemy',
                          return_value=True), \
                patch.object(self.custom_skills.action, 'do',
                             side_effect=apply_hp_set):
            component.end_combat([], user, None, target, None, 'attack')
        self.assertEqual(10, target.get_hp())

        user.set_hp(1)
        with patch.object(self.custom_skills.skill_system, 'check_enemy',
                          return_value=True), \
                patch.object(self.custom_skills.action, 'do',
                             side_effect=apply_hp_set):
            component.end_combat([], user, None, target, None, 'defense')
        self.assertEqual(10, target.get_hp())


if __name__ == '__main__':
    unittest.main()
