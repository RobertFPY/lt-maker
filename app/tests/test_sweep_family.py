import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import combat_calcs, item_system, skill_system
from app.engine.objects.item import ItemObject
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
PHYSICAL_TYPES = ('Sword', 'Lance', 'Axe', 'Bow', 'Dagger')
MAGIC_TYPES = ('Fire', 'Wind', 'Thunder', 'Water', 'Earth', 'Anima', 'Light', 'Dark', 'Staff', 'Dragon')
COUNTER_CHILDREN = {
    'Windsweep_T1_Effect_2': (PHYSICAL_TYPES, 5),
    'Windsweep_T2_Effect': (PHYSICAL_TYPES, 3),
    'Windsweep_T3_Effect': (PHYSICAL_TYPES, 0),
    'Watersweep_T1_Effect_2': (MAGIC_TYPES, 5),
    'Watersweep_T2_Effect': (MAGIC_TYPES, 3),
    'Watersweep_T3_Effect': (MAGIC_TYPES, 0),
}


class RuntimeUnit:
    def __init__(self, nid, team, spd, skills=()):
        self.nid = nid
        self.team = team
        self.spd = spd
        self.skills = list(skills)
        self.position = (0, 0)
        self.equipped_weapon = None

    def get_stat(self, stat):
        return self.spd if stat == 'SPD' else 0

    def get_weapon(self):
        return self.equipped_weapon


class SweepFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }

    @staticmethod
    def _skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _weapon(nid):
        return ItemObject.from_prefab(DB.items.get(nid))

    def _activate(self, skill, unit, target, target_item, mode='attack'):
        skill_system.pre_combat([], unit, self._weapon('Hero_Sword'), target, target_item, mode)

    def test_counter_children_have_attack_only_type_filtered_strict_conditions(self):
        for nid, (weapon_types, bonus) in COUNTER_CHILDREN.items():
            with self.subTest(nid=nid):
                condition = dict(self.skills[nid]['components'])['combat_condition']
                threshold = (
                    f"unit.get_stat('SPD') > (target.get_stat('SPD') + {bonus})"
                    if bonus else "unit.get_stat('SPD') > target.get_stat('SPD')")
                self.assertEqual(
                    "mode == 'attack' and item2 and "
                    f"item_system.weapon_type(target, item2) in {weapon_types!r} and {threshold}",
                    condition)

    def test_prevention_is_attack_only_and_independent_of_speed_and_weapon_type(self):
        for nid in ('Windsweep_T1_Effect_1', 'Watersweep_T1_Effect_1'):
            with self.subTest(nid=nid):
                skill = self._skill(nid)
                unit = RuntimeUnit('user', 'player', 1, [skill])
                target = RuntimeUnit('foe', 'enemy', 99)
                self._activate(skill, unit, target, self._weapon('Hero_Lance'))
                self.assertTrue(skill_system.prevent_self_follow_up(unit))
                self._activate(skill, unit, target, self._weapon('Hero_Lance'), 'defense')
                self.assertFalse(skill_system.prevent_self_follow_up(unit))

    def test_counter_lock_requires_attack_speed_type_and_target_weapon(self):
        for nid, (weapon_types, bonus) in COUNTER_CHILDREN.items():
            with self.subTest(nid=nid):
                skill = self._skill(nid)
                unit = RuntimeUnit('user', 'player', 10 + bonus + 1, [skill])
                target = RuntimeUnit('foe', 'enemy', 10)
                matching = self._weapon('Hero_Sword' if weapon_types == PHYSICAL_TYPES else 'Fire')
                nonmatching = self._weapon('Fire' if weapon_types == PHYSICAL_TYPES else 'Hero_Sword')
                self._activate(skill, unit, target, matching)
                self.assertFalse(item_system.can_be_countered(unit, self._weapon('Hero_Sword')))
                self._activate(skill, unit, target, nonmatching)
                self.assertTrue(item_system.can_be_countered(unit, self._weapon('Hero_Sword')))
                self._activate(skill, unit, target, None)
                self.assertTrue(item_system.can_be_countered(unit, self._weapon('Hero_Sword')))
                self._activate(skill, unit, target, matching, 'defense')
                self.assertTrue(item_system.can_be_countered(unit, self._weapon('Hero_Sword')))
                unit.spd = target.spd + bonus
                self._activate(skill, unit, target, matching)
                self.assertTrue(item_system.can_be_countered(unit, self._weapon('Hero_Sword')))

    def test_watersweep_t1_wires_its_own_counter_child_and_parent_descriptions_are_magic(self):
        self.assertEqual(
            ['Watersweep_T1_Effect_1', 'Watersweep_T1_Effect_2'],
            dict(self.skills['Watersweep_T1']['components'])['multi_skill'])
        for tier in (1, 2, 3):
            parent = self.skills[f'Watersweep_T{tier}']
            child = self.skills['Watersweep_T1_Effect_2' if tier == 1 else f'Watersweep_T{tier}_Effect']
            self.assertEqual(child['desc'], parent['desc'])
            self.assertIn('Anima Magic, Light Magic, Dark Magic, Staff or Dragonstone', parent['desc'])

    def test_null_follow_up_restores_follow_ups_but_not_counter_lock(self):
        prevention = self._skill('Windsweep_T1_Effect_1')
        counter = self._skill('Windsweep_T1_Effect_2')
        null_follow = self._skill('Null_Follow_Up_T3')
        unit = RuntimeUnit('user', 'player', 20, [prevention, counter, null_follow])
        target = RuntimeUnit('foe', 'enemy', 10)
        weapon = self._weapon('Hero_Sword')
        target_weapon = self._weapon('Hero_Lance')
        self._activate(prevention, unit, target, target_weapon)
        self._activate(counter, unit, target, target_weapon)
        self.assertTrue(skill_system.prevent_self_follow_up(unit))
        self.assertTrue(skill_system.neutralize_follow_up_prevention(unit))
        with patch('app.engine.combat_calcs.outspeed', return_value=1), \
                patch('app.engine.combat_calcs.resolve_weapon', return_value=target_weapon):
            self.assertEqual(2, combat_calcs.compute_attack_phases(
                unit, target, weapon, target_weapon, 'attack', (0, 0)))
        self.assertFalse(item_system.can_be_countered(unit, weapon))

    def test_mystic_boost_restores_counterability_but_not_prevention_and_brave_count_is_unchanged(self):
        prevention = self._skill('Watersweep_T1_Effect_1')
        counter = self._skill('Watersweep_T1_Effect_2')
        attacker = RuntimeUnit('user', 'player', 20, [prevention, counter])
        defender = RuntimeUnit('foe', 'enemy', 10, [self._skill('Mystic_Boost_T1')])
        weapon = self._weapon('Hero_Sword')
        target_weapon = self._weapon('Fire')
        defender.equipped_weapon = target_weapon
        self._activate(prevention, attacker, defender, target_weapon)
        self._activate(counter, attacker, defender, target_weapon)
        self.assertTrue(skill_system.prevent_self_follow_up(attacker))
        self.assertFalse(skill_system.neutralize_follow_up_prevention(attacker))
        self.assertFalse(item_system.can_be_countered(attacker, weapon))
        self.assertTrue(skill_system.negate_cannot_be_countered(defender))
        attacker.position = None
        with patch('app.engine.combat_calcs.item_funcs.available', return_value=True), \
                patch.object(DB.constants, 'value', return_value=False):
            self.assertTrue(combat_calcs.can_counterattack(attacker, weapon, defender, target_weapon))
        self.assertEqual(2, combat_calcs.compute_multiattacks(attacker, defender, weapon, 'attack', (0, 0)))


if __name__ == '__main__':
    import unittest
    unittest.main()
