import importlib.util
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine.combat import playback as pb
from app.engine.objects.skill import SkillObject
from app.engine.skill_components.advanced_components import get_modified_proc_rate
from app.utilities.data import Data


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class SpecialSpiralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PROJECT_PATH, 'game_data', 'skills.json'),
                  encoding='utf-8') as skills_file:
            cls.skill_data = {skill['nid']: skill
                              for skill in json.load(skills_file)}

        component_path = os.path.join(
            PROJECT_PATH, 'resources', 'custom_components',
            'custom_skill_components.py')
        spec = importlib.util.spec_from_file_location(
            'special_spiral_test_custom_skills', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    @staticmethod
    def _apply(actions):
        for act in actions:
            act.do()

    @staticmethod
    def _component(nid, value=None):
        return SimpleNamespace(
            nid=nid,
            value=value,
            defines=lambda hook: False)

    def _skill(self, nid, components=None, special=False, weapon_special=False):
        return SimpleNamespace(
            nid=nid,
            components=components or [],
            data={},
            special_skill=object() if special else None,
            weapon_special_skill=object() if weapon_special else None)

    @staticmethod
    def _unit(skills):
        return SimpleNamespace(skills=skills)

    def _spiral_component(self, tier=1, value=None):
        rate = value if value is not None else (20 if tier == 3 else 10)
        spiral_skill = self._skill(
            'Special_Spiral_T%d' % tier,
            [self._component('priority', tier - 1)])
        component = self.custom_skills.SpecialSpiralBonus(rate)
        component.skill = spiral_skill
        spiral_skill.components.append(component)
        component.init(spiral_skill)
        return component, spiral_skill

    def _standard_special(self):
        return self._skill(
            'New_Moon_T1',
            [self._component('attack_proc', 'New_Moon_Effect')],
            special=True)

    @staticmethod
    def _start(component, unit, mode='attack'):
        component.start_combat([], unit, None, None, None, mode)

    def _end(self, component, unit, mode='attack'):
        with patch.object(self.custom_skills.action, 'do',
                          side_effect=lambda act: act.do()):
            component.end_combat([], unit, None, None, None, mode)

    def _wait(self, component, unit):
        with patch.object(self.custom_skills.action, 'do',
                          side_effect=lambda act: act.do()):
            component.on_wait(unit, True)

    def _trigger(self, component, unit, special, mode='attack', defense=False,
                 condition=True):
        actions = []
        playback_skill = special
        for special_component in special.components:
            if (special_component.nid in (
                    'attack_proc', 'attack_proc_with_target', 'defense_proc',
                    'defense_proc_with_target')
                    and special_component.value):
                playback_skill = self._skill(special_component.value)
                break
        playback = ([pb.DefenseProc(unit, playback_skill)] if defense
                    else [pb.AttackProc(unit, playback_skill)])
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=condition):
            component.after_strike(
                actions, playback, unit, None, None, None, mode, (0, 0),
                None)
        self._apply(actions)

    def test_data_wires_tiers_to_special_spiral_component(self):
        expected = {
            1: (10, "mode == 'attack'"),
            2: (10, None),
            3: (20, None),
        }
        for tier, (rate, condition) in expected.items():
            with self.subTest(tier=tier):
                components = dict(self.skill_data[
                    'Special_Spiral_T%d' % tier]['components'])
                self.assertEqual(rate, components['special_spiral_bonus'])
                self.assertNotIn('do_nothing', components)
                if condition is None:
                    self.assertNotIn('combat_condition', components)
                else:
                    self.assertEqual(condition, components['combat_condition'])

    def test_t1_only_arms_when_user_initiates(self):
        component, spiral_skill = self._spiral_component(tier=1)
        special = self._standard_special()
        unit = self._unit([spiral_skill, special])

        self._start(component, unit, 'defense')
        self._trigger(component, unit, special, 'defense', defense=True,
                      condition=False)
        self.assertFalse(spiral_skill.data['special_spiral_active'])

        self._start(component, unit, 'attack')
        self._trigger(component, unit, special, 'attack', condition=True)
        self.assertTrue(spiral_skill.data['special_spiral_active'])

    def test_t2_and_t3_arm_from_standard_weapon_astra_and_aether_specials(self):
        for tier, special, playback_mode in (
                (2, self._standard_special(), 'attack'),
                (2, self._skill(
                    'Weapon_Special',
                    [self._component('defense_proc', 'Weapon_Special_Effect')],
                    weapon_special=True), 'defense'),
                (3, self._skill('Astra_T3', [self._component('astra_proc')],
                                 special=True), 'attack'),
                (3, self._skill('Aether_T4', [self._component('aether_proc')],
                                 special=True), 'attack')):
            with self.subTest(tier=tier, special=special.nid):
                component, spiral_skill = self._spiral_component(tier=tier)
                unit = self._unit([spiral_skill, special])
                self._start(component, unit, playback_mode)
                self._trigger(
                    component, unit, special, playback_mode,
                    defense=playback_mode == 'defense')
                self.assertTrue(spiral_skill.data['special_spiral_active'])

    def test_non_special_proc_does_not_arm_bonus(self):
        component, spiral_skill = self._spiral_component(tier=2)
        passive_proc = self._skill(
            'Passive_Proc',
            [self._component('attack_proc', 'Passive_Proc_Effect')])
        unit = self._unit([spiral_skill, passive_proc])

        self._start(component, unit)
        self._trigger(component, unit, passive_proc)
        self.assertFalse(spiral_skill.data['special_spiral_active'])

    def test_application_combat_is_ignored_then_next_combat_expires_bonus(self):
        component, spiral_skill = self._spiral_component()
        special = self._standard_special()
        unit = self._unit([spiral_skill, special])

        self._start(component, unit)
        self._trigger(component, unit, special)
        self.assertEqual(10, component.modify_self_proc_rate(unit))
        self._end(component, unit, 'attack')
        self.assertTrue(spiral_skill.data['special_spiral_active'])
        self.assertTrue(spiral_skill.data['special_spiral_skip_next_wait'])

        self._wait(component, unit)
        self.assertTrue(spiral_skill.data['special_spiral_active'])
        self.assertFalse(spiral_skill.data['special_spiral_skip_next_wait'])

        self._start(component, unit)
        self._end(component, unit, 'attack')
        self.assertFalse(spiral_skill.data['special_spiral_active'])
        self.assertEqual(0, component.modify_self_proc_rate(unit))

    def test_next_defense_combat_and_noncombat_wait_consume_bonus(self):
        component, spiral_skill = self._spiral_component(tier=2)
        special = self._standard_special()
        unit = self._unit([spiral_skill, special])

        self._start(component, unit, 'defense')
        self._trigger(component, unit, special, 'defense', defense=True)
        self._end(component, unit, 'defense')
        self.assertTrue(spiral_skill.data['special_spiral_active'])
        self.assertFalse(spiral_skill.data['special_spiral_skip_next_wait'])

        self._start(component, unit, 'defense')
        self._end(component, unit, 'defense')
        self.assertFalse(spiral_skill.data['special_spiral_active'])

        self._start(component, unit, 'defense')
        self._trigger(component, unit, special, 'defense', defense=True)
        self._end(component, unit, 'defense')
        self._wait(component, unit)
        self.assertFalse(spiral_skill.data['special_spiral_active'])

    def test_retrigger_refreshes_bonus_for_another_action(self):
        component, spiral_skill = self._spiral_component()
        special = self._standard_special()
        unit = self._unit([spiral_skill, special])

        self._start(component, unit)
        self._trigger(component, unit, special)
        self._end(component, unit, 'attack')
        self._wait(component, unit)

        self._start(component, unit)
        self._trigger(component, unit, special)
        self._end(component, unit, 'attack')
        self._wait(component, unit)
        self.assertTrue(spiral_skill.data['special_spiral_active'])

        self._start(component, unit)
        self._end(component, unit, 'attack')
        self.assertFalse(spiral_skill.data['special_spiral_active'])

    def test_highest_spiral_tier_wins_and_stacks_with_wrath(self):
        low_component, low_skill = self._spiral_component(tier=1)
        high_component, high_skill = self._spiral_component(tier=3)
        low_skill.data['special_spiral_active'] = True
        high_skill.data['special_spiral_active'] = True
        wrath_skill = self._skill(
            'Wrath_T1', [self._component('priority', 0)])
        wrath_component = self.custom_skills.WrathSpecialBonus({
            'proc_rate_bonus': 10,
            'damage_bonus': 10,
        })
        wrath_component.skill = wrath_skill
        wrath_skill.components.append(wrath_component)
        proc_skill = self._skill(
            'Proc', [SimpleNamespace(
                nid='proc_rate', defines=lambda hook: hook == 'proc_rate',
                proc_rate=lambda unit: 30)])
        unit = self._unit([low_skill, high_skill, wrath_skill])

        self.assertEqual(0, low_component.modify_self_proc_rate(unit))
        self.assertEqual(20, high_component.modify_self_proc_rate(unit))
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=True):
            self.assertEqual(60, get_modified_proc_rate(unit, proc_skill))

    def test_spiral_state_serializes_in_skill_data(self):
        components = Data()
        component = self.custom_skills.SpecialSpiralBonus(10)
        components.append(component)
        skill = SkillObject('Special_Spiral_T1', 'Special Spiral', '',
                            components=components)
        component.init(skill)
        skill.data['special_spiral_active'] = True
        skill.data['special_spiral_skip_next_wait'] = True

        self.assertEqual(
            {'special_spiral_active': True,
             'special_spiral_skip_next_wait': True},
            skill.save()['data'])


if __name__ == '__main__':
    unittest.main()
