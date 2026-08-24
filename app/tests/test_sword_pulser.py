import importlib.util
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine.combat import playback as pb
from app.engine.objects.skill import SkillObject
from app.engine.skill_components.advanced_components import AstraProc
from app.utilities.data import Data


PROJECT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Fire Emblem Tales of The Golden Knight.ltproj')


class SwordPulserTests(unittest.TestCase):
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
            'sword_pulser_test_custom_skills', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    @staticmethod
    def _apply(actions):
        for act in actions:
            act.do()

    @staticmethod
    def _skill(nid, components=None, special=False, weapon_special=False):
        return SimpleNamespace(
            nid=nid,
            components=components or [],
            data={},
            special_skill=object() if special else None,
            weapon_special_skill=object() if weapon_special else None)

    def _pulse_component(self, value=3, nid='Sword_Pulser_T1'):
        pulse_skill = self._skill(nid)
        component = self.custom_skills.SpecialSkillPulse(value)
        component.skill = pulse_skill
        component.init(pulse_skill)
        return component, pulse_skill

    def _standard_special(self):
        return self._skill(
            'New_Moon_T1',
            [SimpleNamespace(nid='attack_proc', value='New_Moon_Effect')],
            special=True)

    def _wrath_component(self, priority=0, rate_bonus=10, damage_bonus=10):
        wrath_skill = self._skill(
            'Wrath_T%d' % (priority + 1),
            [SimpleNamespace(nid='priority', value=priority,
                             defines=lambda hook: False)])
        component = self.custom_skills.WrathSpecialBonus({
            'proc_rate_bonus': rate_bonus,
            'damage_bonus': damage_bonus,
        })
        component.skill = wrath_skill
        wrath_skill.components.append(component)
        return component, wrath_skill

    def test_sword_pulser_data_uses_attack_combat_condition_and_tier_rate(self):
        for tier, rate in ((1, 3), (2, 4), (3, 5)):
            with self.subTest(tier=tier):
                components = dict(self.skill_data[
                    'Sword_Pulser_T%d' % tier]['components'])
                self.assertEqual("mode == 'attack'",
                                 components['combat_condition'])
                self.assertEqual(rate, components['special_skill_pulse'])
                self.assertNotIn('do_nothing', components)

    def test_shield_pulse_data_uses_defense_combat_condition_and_tier_rate(self):
        for tier, rate in ((1, 3), (2, 4), (3, 5)):
            with self.subTest(tier=tier):
                components = dict(self.skill_data[
                    'Shield_Pulse_T%d' % tier]['components'])
                self.assertEqual("mode == 'defense'",
                                 components['combat_condition'])
                self.assertEqual(rate, components['special_skill_pulse'])

    def test_first_special_arms_and_later_misses_accumulate_then_reset(self):
        component, pulse_skill = self._pulse_component()
        special = self._standard_special()
        effect = self._skill('New_Moon_Effect')
        unit = SimpleNamespace(skills=[pulse_skill, special])

        first_actions = []
        component.after_strike(
            first_actions, [pb.AttackProc(unit, effect)], unit, None, None,
            None, 'attack', (0, 0), None)
        self._apply(first_actions)
        self.assertTrue(pulse_skill.data['special_skill_pulse_armed'])
        self.assertEqual(0, pulse_skill.data['special_skill_pulse_bonus'])

        for expected_bonus in (3, 6):
            actions = []
            component.after_strike(actions, [], unit, None, None, None,
                                   'attack', (0, 0), None)
            self._apply(actions)
            self.assertEqual(expected_bonus,
                             pulse_skill.data['special_skill_pulse_bonus'])

        reset_actions = []
        component.after_strike(
            reset_actions, [pb.AttackProc(unit, effect)], unit, None, None,
            None, 'attack', (0, 0), None)
        self._apply(reset_actions)
        self.assertTrue(pulse_skill.data['special_skill_pulse_armed'])
        self.assertEqual(0, pulse_skill.data['special_skill_pulse_bonus'])

    def test_bonus_persists_across_combats_but_only_applies_when_condition_is_on(self):
        component, pulse_skill = self._pulse_component()
        special = self._standard_special()
        effect = self._skill('New_Moon_Effect')
        unit = SimpleNamespace(skills=[pulse_skill, special])

        actions = []
        component.after_strike(actions, [pb.AttackProc(unit, effect)], unit,
                               None, None, None, 'attack', (0, 0), None)
        self._apply(actions)
        actions = []
        component.after_strike(actions, [], unit, None, None, None,
                               'attack', (0, 0), None)
        self._apply(actions)

        self.assertEqual(3, pulse_skill.data['special_skill_pulse_bonus'])
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=False):
            self.assertEqual(0, component.modify_self_proc_rate(unit))
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=True):
            self.assertEqual(3, component.modify_self_proc_rate(unit))

    def test_only_special_proc_playback_arms_or_resets_the_bonus(self):
        component, pulse_skill = self._pulse_component()
        non_special = self._skill(
            'Passive_Proc',
            [SimpleNamespace(nid='attack_proc', value='Passive_Effect')])
        special = self._standard_special()
        unit = SimpleNamespace(skills=[pulse_skill, non_special, special])

        actions = []
        component.after_strike(
            actions, [pb.AttackProc(unit, self._skill('Passive_Effect'))],
            unit, None, None, None, 'attack', (0, 0), None)
        self._apply(actions)
        self.assertFalse(pulse_skill.data['special_skill_pulse_armed'])
        self.assertEqual(0, pulse_skill.data['special_skill_pulse_bonus'])

    def test_existing_proc_in_cumulative_playback_does_not_reset_new_strike(self):
        component, pulse_skill = self._pulse_component()
        special = self._standard_special()
        effect = self._skill('New_Moon_Effect')
        unit = SimpleNamespace(skills=[pulse_skill, special])
        playback = [pb.AttackProc(unit, effect)]

        component.start_combat([], unit, None, None, None, 'attack')
        actions = []
        component.after_strike(actions, playback, unit, None, None, None,
                               'attack', (0, 0), None)
        self._apply(actions)

        actions = []
        component.after_strike(actions, playback, unit, None, None, None,
                               'attack', (0, 1), None)
        self._apply(actions)
        self.assertEqual(3, pulse_skill.data['special_skill_pulse_bonus'])

    def test_shield_pulse_counts_foe_strikes_not_user_counterattacks(self):
        component, pulse_skill = self._pulse_component(
            4, nid='Shield_Pulse_T2')
        special = self._standard_special()
        effect = self._skill('New_Moon_Effect')
        unit = SimpleNamespace(skills=[pulse_skill, special])

        component.start_combat([], unit, None, None, None, 'defense')
        actions = []
        component.after_take_strike(
            actions, [pb.AttackProc(unit, effect)], unit, None, None, None,
            'defense', (0, 0), None)
        self._apply(actions)

        actions = []
        component.after_take_strike(actions, [], unit, None, None, None,
                                    'defense', (0, 1), None)
        self._apply(actions)
        self.assertEqual(4, pulse_skill.data['special_skill_pulse_bonus'])

        actions = []
        component.after_strike(actions, [], unit, None, None, None,
                               'defense', (1, 0), None)
        self._apply(actions)
        self.assertEqual(4, pulse_skill.data['special_skill_pulse_bonus'])

        actions = []
        component.after_take_strike(
            actions, [pb.AttackProc(unit, effect)], unit, None, None, None,
            'defense', (0, 2), None)
        self._apply(actions)
        self.assertEqual(0, pulse_skill.data['special_skill_pulse_bonus'])

    def test_astra_follow_up_strike_without_new_activation_accumulates(self):
        component, pulse_skill = self._pulse_component(5)
        astra = self._skill(
            'Astra_T3', [SimpleNamespace(nid='astra_proc', value=None)],
            special=True)
        unit = SimpleNamespace(skills=[pulse_skill, astra])

        actions = []
        component.after_strike(actions, [pb.AttackProc(unit, astra)], unit,
                               None, None, None, 'attack', (0, 0), None)
        self._apply(actions)
        actions = []
        component.after_strike(actions, [], unit, None, None, None,
                               'attack', (0, 1), None)
        self._apply(actions)
        self.assertEqual(5, pulse_skill.data['special_skill_pulse_bonus'])

    def test_pulse_state_is_serialized_in_skill_data(self):
        components = Data()
        component = self.custom_skills.SpecialSkillPulse(3)
        components.append(component)
        skill = SkillObject('Sword_Pulser_T1', 'Sword Pulser', '',
                            components=components)
        component.init(skill)
        skill.data['special_skill_pulse_armed'] = True
        skill.data['special_skill_pulse_bonus'] = 9

        saved = skill.save()
        self.assertEqual(
            {'special_skill_pulse_armed': True,
             'special_skill_pulse_bonus': 9},
            saved['data'])

    def test_wrath_data_uses_the_combined_rate_and_damage_component(self):
        for tier, rate in ((1, 10), (2, 15), (3, 20)):
            with self.subTest(tier=tier):
                components = dict(self.skill_data['Wrath_T%d' % tier]['components'])
                self.assertEqual(
                    {'proc_rate_bonus': rate, 'damage_bonus': 10},
                    components['wrath_special_bonus'])
                self.assertNotIn('modify_self_proc_rate', components)

    def test_wrath_rate_obeys_the_captured_combat_condition(self):
        component, wrath_skill = self._wrath_component(rate_bonus=15)
        unit = SimpleNamespace(skills=[wrath_skill])

        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=False):
            self.assertEqual(0, component.modify_self_proc_rate(unit))
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=True):
            self.assertEqual(15, component.modify_self_proc_rate(unit))

    def test_wrath_adds_damage_to_standard_special_activation_only(self):
        component, wrath_skill = self._wrath_component()
        proc = SimpleNamespace(nid='attack_proc', _did_action=True)
        special = self._skill('New_Moon_T1', [proc], special=True)
        unit = SimpleNamespace(skills=[wrath_skill, special])

        self.assertEqual(10, component.raw_damage(
            unit, None, None, None, 'attack', (0, 0), 0))
        proc._did_action = False
        self.assertEqual(0, component.raw_damage(
            unit, None, None, None, 'attack', (0, 1), 0))

    def test_wrath_raw_damage_uses_the_dispatcher_combat_condition_gate(self):
        from app.engine import skill_system

        component, wrath_skill = self._wrath_component()
        proc = SimpleNamespace(nid='attack_proc', _did_action=True,
                               defines=lambda hook: False)
        special = self._skill('New_Moon_T1', [proc], special=True)
        unit = SimpleNamespace(
            skills=[wrath_skill, special], equipped_weapon=None)

        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=False):
            self.assertEqual(0, skill_system.raw_damage(
                unit, None, None, None, 'attack', (0, 0), 0))
        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=True):
            self.assertEqual(10, skill_system.raw_damage(
                unit, None, None, None, 'attack', (0, 0), 0))

    def test_wrath_only_affects_first_astra_style_strike(self):
        component, wrath_skill = self._wrath_component()
        astra_proc = SimpleNamespace(
            nid='astra_proc', _should_modify_damage=True, _hitcount=0)
        special = self._skill('Astra_T3', [astra_proc], special=True)
        unit = SimpleNamespace(skills=[wrath_skill, special])

        self.assertEqual(10, component.raw_damage(
            unit, None, None, None, 'attack', (0, 0), 0))
        for hitcount in (1, 2, 3, 4):
            with self.subTest(hitcount=hitcount):
                astra_proc._hitcount = hitcount
                self.assertEqual(0, component.raw_damage(
                    unit, None, None, None, 'attack', (0, hitcount), 0))

    def test_wrath_affects_both_aether_strikes_and_no_later_strike(self):
        component, wrath_skill = self._wrath_component()
        aether_proc = SimpleNamespace(
            nid='aether_proc', _should_modify_damage=True, _hitcount=0)
        special = self._skill('Aether_T4', [aether_proc], special=True)
        unit = SimpleNamespace(skills=[wrath_skill, special])

        for hitcount in (0, 1):
            with self.subTest(hitcount=hitcount):
                aether_proc._hitcount = hitcount
                self.assertEqual(10, component.raw_damage(
                    unit, None, None, None, 'attack', (0, hitcount), 0))
        aether_proc._hitcount = 2
        self.assertEqual(0, component.raw_damage(
            unit, None, None, None, 'attack', (0, 2), 0))

    def test_wrath_highest_priority_version_wins_without_blocking_other_bonus(self):
        low_component, low_wrath = self._wrath_component(
            priority=0, rate_bonus=10, damage_bonus=10)
        high_component, high_wrath = self._wrath_component(
            priority=2, rate_bonus=20, damage_bonus=10)
        proc = SimpleNamespace(nid='attack_proc', _did_action=True)
        special = self._skill('New_Moon_T1', [proc], special=True)
        unit = SimpleNamespace(skills=[low_wrath, high_wrath, special])

        with patch.object(self.custom_skills.skill_system, 'condition',
                          return_value=True):
            self.assertEqual(0, low_component.modify_self_proc_rate(unit))
            self.assertEqual(20, high_component.modify_self_proc_rate(unit))
        self.assertEqual(0, low_component.raw_damage(
            unit, None, None, None, 'attack', (0, 0), 0))
        self.assertEqual(10, high_component.raw_damage(
            unit, None, None, None, 'attack', (0, 0), 0))

    def test_stardust_data_and_bonus_cover_all_five_strikes(self):
        components = dict(self.skill_data['Stardust_Mirage_T4']['components'])
        self.assertEqual(
            {'extra_attacks': 4, 'damage_percent': 0.5,
             'show_proc_effects': True, 'disable_crit': True},
            components['astra_proc'])
        self.assertEqual(
            {'speed_damage_percent': 0.1},
            components['stardust_mirage_bonus'])

        astra_proc = AstraProc(components['astra_proc'])
        astra_proc._should_modify_damage = True
        stardust_skill = self._skill(
            'Stardust_Mirage_T4', [astra_proc], special=True)
        component = self.custom_skills.StardustMirageBonus(
            components['stardust_mirage_bonus'])
        component.skill = stardust_skill
        stardust_skill.components.append(component)
        unit = SimpleNamespace(
            skills=[stardust_skill], get_stat=lambda stat: 27)

        for hitcount in range(5):
            with self.subTest(hitcount=hitcount):
                astra_proc._hitcount = hitcount
                self.assertEqual(2, component.raw_damage(
                    unit, None, None, None, 'attack', (0, hitcount), 0))
                self.assertTrue(astra_proc.prevent_critical(
                    unit, None, None))

        astra_proc._should_modify_damage = False
        self.assertEqual(0, component.raw_damage(
            unit, None, None, None, 'attack', (0, 5), 0))
        self.assertFalse(astra_proc.prevent_critical(unit, None, None))


if __name__ == '__main__':
    unittest.main()
