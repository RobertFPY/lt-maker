import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import combat_calcs, skill_system


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


@dataclass(eq=False)
class MockItem:
    weapon_type: str
    components: list = field(default_factory=list)


@dataclass(eq=False)
class MockUnit:
    wexp: dict
    skills: list = field(default_factory=list)
    equipped_weapon: object = None


@dataclass(eq=False)
class MockSkill:
    nid: str
    uid: int
    components: list
    data: dict = field(default_factory=dict)


class TriangleModifier:
    nid = 'custom_triangle_multiplier'

    def __init__(self, value):
        self.value = value

    def defines(self, hook):
        return hook == 'modify_weapon_triangle'

    def modify_weapon_triangle(self, unit, item):
        return self.value


class CancelAffinityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skills_file:
            cls.skill_data = {skill['nid']: skill for skill in json.load(skills_file)}

        component_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        spec = importlib.util.spec_from_file_location('cancel_affinity_test_components', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def setUp(self):
        combat_calcs.compute_advantage.__wrapped__.cache_clear()

    def tearDown(self):
        combat_calcs.compute_advantage.__wrapped__.cache_clear()

    def _cancel_skill(self, tier, uid):
        component = self.custom_skills.CancelAffinity(tier)
        priority = SimpleNamespace(nid='priority', value=tier - 1,
                                   defines=lambda hook: False)
        skill = MockSkill('Cancel_Affinity_T%d' % tier, uid,
                          [priority, component])
        component.skill = skill
        return skill

    @staticmethod
    def _unit_with(skill):
        return MockUnit({'Axe': 1}, [skill])

    def _resolve(self, unit, has_disadvantage, self_skill=0.5, foe_skill=1.4):
        return skill_system.weapon_triangle_multiplier_override(
            unit, None, None, None, has_disadvantage, self_skill, foe_skill)

    def test_skill_data_wires_each_tier_to_cancel_affinity(self):
        for tier in (1, 2, 3):
            with self.subTest(tier=tier):
                components = dict(self.skill_data['Cancel_Affinity_T%d' % tier]['components'])
                self.assertEqual(tier, components['cancel_affinity'])
                self.assertNotIn('do_nothing', components)

    def test_tier_one_neutralizes_all_skill_triangle_modifiers(self):
        unit = self._unit_with(self._cancel_skill(1, 101))

        self.assertEqual((1.0, 1.0), self._resolve(unit, False))
        self.assertEqual((1.0, 1.0), self._resolve(unit, True))

    def test_tier_two_and_three_only_change_foe_skill_modifier_when_disadvantaged(self):
        tier_two = self._unit_with(self._cancel_skill(2, 102))
        self.assertEqual((1.0, 1.4), self._resolve(tier_two, False))
        self.assertEqual((1.0, 1.0), self._resolve(tier_two, True))

        tier_three = self._unit_with(self._cancel_skill(3, 103))
        self.assertEqual((1.0, 1.4), self._resolve(tier_three, False))
        self.assertEqual((1.0, 0.5), self._resolve(tier_three, True, foe_skill=1.5))

    def test_highest_priority_tier_wins_independent_of_skill_order(self):
        tier_three = self._cancel_skill(3, 203)
        tier_two = self._cancel_skill(2, 202)
        unit = MockUnit({'Axe': 1}, [tier_three, tier_two])

        self.assertEqual((1.0, 0.5), self._resolve(unit, True, foe_skill=1.5))

    def test_tier_one_preserves_direct_reaver_multiplier_while_cancelling_skill_override(self):
        cancel_skill = self._cancel_skill(1, 301)
        attacker = MockUnit({'Axe': 1}, [cancel_skill])
        defender = MockUnit({'Dagger': 1})
        axe_reaver = MockItem('Axe', [TriangleModifier(-2.0)])
        dagger = MockItem('Dagger')
        attacker.equipped_weapon = axe_reaver
        defender.equipped_weapon = dagger

        with patch('app.engine.item_system.weapon_type', lambda unit, item: item.weapon_type), \
                patch('app.engine.item_system.weapon_triangle_override', lambda unit, item: None), \
                patch('app.engine.item_system.ignore_weapon_advantage', lambda unit, item: False), \
                patch('app.engine.skill_system.item_override',
                      lambda unit, item: [TriangleModifier(3.0)] if unit is attacker else []):
            self.assertEqual(
                -2,
                combat_calcs.compute_advantage_attr(attacker, defender, axe_reaver, dagger, 'damage'))

    def test_without_cancel_affinity_direct_and_skill_multipliers_still_combine(self):
        attacker = MockUnit({'Axe': 1})
        defender = MockUnit({'Dagger': 1})
        axe_reaver = MockItem('Axe', [TriangleModifier(-2.0)])
        dagger = MockItem('Dagger')
        attacker.equipped_weapon = axe_reaver
        defender.equipped_weapon = dagger

        with patch('app.engine.item_system.weapon_type', lambda unit, item: item.weapon_type), \
                patch('app.engine.item_system.weapon_triangle_override', lambda unit, item: None), \
                patch('app.engine.item_system.ignore_weapon_advantage', lambda unit, item: False), \
                patch('app.engine.skill_system.item_override',
                      lambda unit, item: [TriangleModifier(3.0)] if unit is attacker else []):
            self.assertEqual(
                -6,
                combat_calcs.compute_advantage_attr(attacker, defender, axe_reaver, dagger, 'damage'))
