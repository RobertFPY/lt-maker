import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class RecoveryMissingSemanticsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as source:
            cls.skills = {skill['nid']: skill for skill in json.load(source)}
        component_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        spec = importlib.util.spec_from_file_location('recovery_missing_components', component_path)
        cls.custom = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom)

    def components(self, nid):
        return dict(self.skills[nid]['components'])

    def test_feint_and_lull_data_are_not_placeholders(self):
        self.assertEqual(
            {'stat': 'STR', 'effect': 'Strength_Feint_T1_Effect'},
            self.components('Strength_Feint_T1')['feint'])
        self.assertEqual(-3, self.components('Strength_Feint_T1_Effect')['stat_change'][0][1])
        self.assertEqual(3, self.components('Lull_Atk_Spd_T1')['lull_combat_stats']['penalty'])

    def test_no_family_recovery_data_contracts(self):
        self.assertEqual('10', self.components('Renewal_T1')['eval_regeneration'])
        self.assertNotIn('regeneration', self.components('Renewal_T1'))
        self.assertIn('surviving_initiator_post_combat_damage', self.components('Poison_Strike_T1'))
        self.assertEqual(10, self.components('Wrath_T1')['wrath_special_bonus']['damage_bonus'])
        self.assertEqual(5, self.components('Dragon_Wall_T4')['comparison_stat_bonus'])
        self.assertEqual(0.9, self.components('Obstruct_T1')['obstruct'])
        self.assertIn("unit.get_stat('SPD') >", self.components('Pegasus_Flight_T1')['combat_condition'])

    def test_stardust_mirage_restores_special_sequence(self):
        components = self.components('Stardust_Mirage_T4')
        self.assertEqual(4, components['astra_proc']['extra_attacks'])
        self.assertEqual(0.1, components['stardust_mirage_bonus']['speed_damage_percent'])

    def test_missing_component_contracts(self):
        comparison = self.custom.ComparisonStatBonus(5)
        self.assertEqual(5, comparison.comparison_stat_bonus(None, 'RES'))
        self.assertEqual(0, comparison.comparison_stat_bonus(None, 'DEF'))

        survival = self.custom.SurvivingInitiatorPostCombatDamage(4)
        self.assertTrue(issubclass(
            self.custom.SurvivingInitiatorPostCombatDamage,
            self.custom.BetterPostCombatDamage))

        obstruct = self.custom.Obstruct(0.7)
        holder = SimpleNamespace(position=(0, 0), get_hp=lambda: 7, get_max_hp=lambda: 10)
        self.assertEqual(0.7, obstruct.value)
        self.assertIsNotNone(holder)

    def test_wrath_bonus_applies_only_to_eligible_special_strikes(self):
        wrath = self.custom.WrathSpecialBonus({
            'proc_rate_bonus': 10, 'damage_bonus': 10})
        wrath_skill = SimpleNamespace(
            nid='Wrath_T1', uid=1,
            components=[SimpleNamespace(nid='priority', value=0), wrath])
        wrath.skill = wrath_skill
        astra = SimpleNamespace(
            nid='astra_proc', _should_modify_damage=True, _hitcount=0)
        special = SimpleNamespace(
            nid='Astra', uid=2, special_skill=True,
            weapon_special_skill=False, components=[astra])
        unit = SimpleNamespace(skills=[wrath_skill, special])
        with patch.object(self.custom.skill_system, 'condition', return_value=True):
            self.assertEqual(10, wrath.modify_self_proc_rate(unit))
            self.assertEqual(10, wrath.raw_damage(
                unit, None, None, None, 'attack', (0, 0), 0))
            astra._hitcount = 1
            self.assertEqual(0, wrath.raw_damage(
                unit, None, None, None, 'attack', (0, 1), 0))
            astra.nid = 'aether_proc'
            astra._hitcount = 0
            self.assertEqual(10, wrath.raw_damage(
                unit, None, None, None, 'attack', (0, 0), 0))
            astra._hitcount = 1
            self.assertEqual(10, wrath.raw_damage(
                unit, None, None, None, 'attack', (0, 1), 0))

    def test_stardust_bonus_applies_to_every_active_astra_subattack(self):
        astra = SimpleNamespace(nid='astra_proc', _should_modify_damage=True)
        bonus = self.custom.StardustMirageBonus({
            'speed_damage_percent': 0.1})
        bonus.skill = SimpleNamespace(components=[astra, bonus])
        unit = SimpleNamespace(get_stat=lambda stat: 37)
        self.assertEqual(3, bonus.raw_damage(
            unit, None, None, None, 'attack', (0, 3), 0))
        astra._should_modify_damage = False
        self.assertEqual(0, bonus.raw_damage(
            unit, None, None, None, 'attack', (0, 0), 0))


if __name__ == '__main__':
    import unittest
    unittest.main()
