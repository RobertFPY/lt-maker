import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


@dataclass(eq=False)
class MockItem:
    magic: bool = False


@dataclass(eq=False)
class MockSkill:
    nid: str
    uid: int
    components: list


@dataclass(eq=False)
class MockUnit:
    stat_bonuses: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)

    def stat_bonus(self, stat_nid):
        return self.stat_bonuses.get(stat_nid, 0)


class LullFamilyTests(TestCase):
    FAMILIES = {
        'Lull_Atk_Spd': {
            'affect_attack': True,
            'affect_speed': True,
            'affect_defense': False,
            'affect_resistance': False,
        },
        'Lull_Atk_Def': {
            'affect_attack': True,
            'affect_speed': False,
            'affect_defense': True,
            'affect_resistance': False,
        },
        'Lull_Atk_Res': {
            'affect_attack': True,
            'affect_speed': False,
            'affect_defense': False,
            'affect_resistance': True,
        },
        'Lull_Spd_Def': {
            'affect_attack': False,
            'affect_speed': True,
            'affect_defense': True,
            'affect_resistance': False,
        },
        'Lull_Spd_Res': {
            'affect_attack': False,
            'affect_speed': True,
            'affect_defense': False,
            'affect_resistance': True,
        },
    }
    TIER_PENALTIES = {1: 3, 2: 5, 3: 7}

    @classmethod
    def setUpClass(cls):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skills_file:
            cls.skill_data = {skill['nid']: skill for skill in json.load(skills_file)}

        component_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        spec = importlib.util.spec_from_file_location('lull_family_test_components', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def _component(self, value, priority=0, uid=100):
        component = self.custom_skills.LullCombatStats(value)
        priority_component = SimpleNamespace(
            nid='priority', value=priority, defines=lambda hook: False)
        skill = MockSkill('Lull_Test_%d' % uid, uid, [priority_component, component])
        component.skill = skill
        return component, skill

    def test_all_lull_records_use_one_component_with_expected_tier_and_family_flags(self):
        for family, flags in self.FAMILIES.items():
            for tier, penalty in self.TIER_PENALTIES.items():
                with self.subTest(family=family, tier=tier):
                    components = dict(self.skill_data['%s_T%d' % (family, tier)]['components'])
                    self.assertEqual({'penalty': penalty, **flags},
                                     components['lull_combat_stats'])
                    self.assertFalse({'resist', 'dynamic_resist', 'dynamic_damage',
                                      'dynamic_attack_speed'} & set(components))

    def test_attack_lull_uses_foe_strength_or_magic_bonus(self):
        component, skill = self._component({
            'penalty': 3, 'affect_attack': True,
            'affect_speed': False, 'affect_defense': False,
            'affect_resistance': False,
        })
        owner = MockUnit(skills=[skill])
        foe = MockUnit({'STR': 6, 'MAG': 4})

        with patch.object(self.custom_skills.item_funcs, 'is_magic',
                          lambda unit, item: item.magic):
            self.assertEqual(9, component.dynamic_resist(
                owner, MockItem(), foe, MockItem(False), 'defense', None, 0))
            self.assertEqual(7, component.dynamic_resist(
                owner, MockItem(), foe, MockItem(True), 'defense', None, 0))

    def test_defense_and_resistance_lulls_only_apply_to_matching_attack_type(self):
        defense_component, defense_skill = self._component({
            'penalty': 3, 'affect_attack': False,
            'affect_speed': False, 'affect_defense': True,
            'affect_resistance': False,
        })
        resistance_component, resistance_skill = self._component({
            'penalty': 3, 'affect_attack': False,
            'affect_speed': False, 'affect_defense': False,
            'affect_resistance': True,
        }, uid=101)
        foe = MockUnit({'DEF': 6, 'RES': 5})

        with patch.object(self.custom_skills.item_funcs, 'is_magic',
                          lambda unit, item: item.magic):
            self.assertEqual(9, defense_component.dynamic_damage(
                MockUnit(skills=[defense_skill]), MockItem(False), foe,
                MockItem(), 'attack', None, 0))
            self.assertEqual(0, defense_component.dynamic_damage(
                MockUnit(skills=[defense_skill]), MockItem(True), foe,
                MockItem(), 'attack', None, 0))
            self.assertEqual(8, resistance_component.dynamic_damage(
                MockUnit(skills=[resistance_skill]), MockItem(True), foe,
                MockItem(), 'attack', None, 0))
            self.assertEqual(0, resistance_component.dynamic_damage(
                MockUnit(skills=[resistance_skill]), MockItem(False), foe,
                MockItem(), 'attack', None, 0))

    def test_speed_lull_applies_in_both_double_directions_and_preserves_negative_bonus(self):
        component, skill = self._component({
            'penalty': 5, 'affect_attack': False,
            'affect_speed': True, 'affect_defense': False,
            'affect_resistance': False,
        })
        owner = MockUnit(skills=[skill])

        positive_foe = MockUnit({'SPD': 4})
        self.assertEqual(9, component.dynamic_attack_speed(
            owner, MockItem(), positive_foe, MockItem(), 'attack', None, 0))
        self.assertEqual(9, component.dynamic_defense_speed(
            owner, MockItem(), positive_foe, MockItem(), 'defense', None, 0))

        negative_foe = MockUnit({'SPD': -4})
        self.assertEqual(5, component.dynamic_attack_speed(
            owner, MockItem(), negative_foe, MockItem(), 'attack', None, 0))

    def test_only_highest_priority_lull_component_contributes(self):
        low_component, low_skill = self._component({
            'penalty': 3, 'affect_attack': False,
            'affect_speed': True, 'affect_defense': False,
            'affect_resistance': False,
        }, priority=0, uid=102)
        high_component, high_skill = self._component({
            'penalty': 7, 'affect_attack': False,
            'affect_speed': True, 'affect_defense': False,
            'affect_resistance': False,
        }, priority=2, uid=103)
        owner = MockUnit(skills=[high_skill, low_skill])
        foe = MockUnit({'SPD': 2})

        self.assertEqual(9, high_component.dynamic_attack_speed(
            owner, MockItem(), foe, MockItem(), 'attack', None, 0))
        self.assertEqual(0, low_component.dynamic_attack_speed(
            owner, MockItem(), foe, MockItem(), 'attack', None, 0))
