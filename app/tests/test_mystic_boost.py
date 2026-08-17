import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine.combat_calcs import can_counterattack
from app.engine.game_state import game


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


@dataclass(eq=False)
class CounterComponent:
    allowed: bool
    nid: str = 'cannot_be_countered'

    def defines(self, hook):
        return hook == 'can_be_countered'

    def can_be_countered(self, unit, item):
        return self.allowed


@dataclass(eq=False)
class CounterItem:
    components: list = field(default_factory=list)
    override_components: list = field(default_factory=list)
    available: bool = True
    can_counter: bool = True
    min_range: int = 1
    max_range: int = 1


@dataclass(eq=False)
class CounterUnit:
    position: tuple = (0, 0)
    negates_cannot_be_countered: bool = False
    skills: list = field(default_factory=list)


@dataclass(eq=False)
class MockSkill:
    nid: str
    uid: int
    components: list
    active: bool = True


@dataclass(eq=False)
class MockUnit:
    skills: list = field(default_factory=list)


class MysticBoostTests(TestCase):
    WRATHFUL = (
        'Wrathfull_Staff_T1', 'Wrathfull_Staff_T2', 'Wrathfull_Staff_T3',
        'Wrathfull_Staff_T4_1', 'Wrathfull_Staff_T4_2',
    )
    MYSTIC_HEALING = {
        'Mystic_Boost_T1': 5,
        'Mystic_Boost_T2': 6,
        'Mystic_Boost_T3': 7,
    }

    @classmethod
    def setUpClass(cls):
        from app.data.database.database import DB
        DB.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)
        DB.constants.get('line_of_sight').set_value(False)

        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skills_file:
            cls.skill_data = {skill['nid']: skill for skill in json.load(skills_file)}

        component_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        spec = importlib.util.spec_from_file_location('mystic_boost_test_components', component_path)
        cls.custom_skills = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_skills)

    def setUp(self):
        game.target_system = SimpleNamespace(
            targets_in_range=lambda unit, item: [(0, 0)])

    def _counterattack(self, base_allowed, skill_allowed, mystic=False):
        attacker = CounterUnit(position=(0, 0))
        defender = CounterUnit(position=(0, 1),
                               negates_cannot_be_countered=mystic)
        aweapon = CounterItem(
            components=[CounterComponent(base_allowed)],
            override_components=[CounterComponent(skill_allowed)]
            if skill_allowed is not None else [])
        dweapon = CounterItem(components=[CounterComponent(True)])

        def current_combined_value(unit, item):
            values = [component.can_be_countered(unit, item)
                      for component in item.components + item.override_components]
            return all(values)

        with patch('app.engine.item_funcs.available', lambda unit, item: item.available), \
             patch('app.engine.item_system.can_be_countered', current_combined_value), \
             patch('app.engine.item_system.can_counter', lambda unit, item: item.can_counter), \
             patch('app.engine.item_system.ignore_line_of_sight', lambda unit, item: False), \
             patch('app.engine.skill_system.item_override',
                   lambda unit, item: item.override_components), \
             patch('app.engine.skill_system.negate_cannot_be_countered',
                   lambda unit: unit.negates_cannot_be_countered), \
             patch('app.engine.skill_system.can_counter', lambda unit: True), \
             patch('app.engine.skill_system.distant_counter', lambda unit: False), \
             patch('app.engine.skill_system.close_counter', lambda unit: False):
            return can_counterattack(attacker, aweapon, defender, dweapon)

    def _neutralizer(self, priority=0, uid=100):
        component = self.custom_skills.NeutralizeLowerDefRes()
        priority_component = SimpleNamespace(nid='priority', value=priority)
        skill = MockSkill('Mystic_Test_%d' % uid, uid,
                          [priority_component, component])
        component.skill = skill
        return component, skill

    def _wrathful_source(self, active=True, uid=200):
        marker = self.custom_skills.LowerDefResSource()
        skill = MockSkill('Wrathful_Test_%d' % uid, uid, [marker], active)
        marker.skill = skill
        return skill

    def _neutralize_resist(self, component, owner, foe, foe_magic,
                           resolved_formula='WORSE_DEFENSE'):
        equation_values = {
            'DEFENSE': 10,
            'MAGIC_DEFENSE': 8,
            'WORSE_DEFENSE': 4,
        }
        with patch.object(self.custom_skills.item_funcs, 'is_magic',
                          lambda unit, item: foe_magic), \
             patch.object(self.custom_skills.skill_system, 'condition',
                          lambda skill, unit, item: skill.active), \
             patch.object(self.custom_skills.combat_calcs,
                          'resolve_defensive_formula',
                          return_value=resolved_formula), \
             patch.object(self.custom_skills.equations.parser, 'get',
                          lambda formula, unit: equation_values[formula]):
            return component.dynamic_resist(
                owner, CounterItem(), foe, CounterItem(), 'defense', None, 0)

    def test_mystic_only_bypasses_dazzling_skill_override(self):
        self.assertFalse(self._counterattack(True, False, mystic=False))
        self.assertTrue(self._counterattack(True, False, mystic=True))

    def test_mystic_does_not_bypass_intrinsic_spell_or_siege_restriction(self):
        self.assertFalse(self._counterattack(False, None, mystic=True))

    def test_neutralizer_restores_physical_and_magic_defense_from_worse_defense(self):
        component, mystic = self._neutralizer()
        owner = MockUnit(skills=[mystic])
        foe = MockUnit(skills=[self._wrathful_source()])

        self.assertEqual(6, self._neutralize_resist(
            component, owner, foe, foe_magic=False))
        self.assertEqual(4, self._neutralize_resist(
            component, owner, foe, foe_magic=True))

    def test_neutralizer_requires_active_worse_defense_source_and_highest_priority(self):
        low_component, low_mystic = self._neutralizer(priority=0, uid=101)
        high_component, high_mystic = self._neutralizer(priority=2, uid=102)
        owner = MockUnit(skills=[low_mystic, high_mystic])
        inactive_foe = MockUnit(skills=[self._wrathful_source(active=False)])
        active_foe = MockUnit(skills=[self._wrathful_source()])

        self.assertEqual(0, self._neutralize_resist(
            high_component, owner, inactive_foe, foe_magic=False))
        self.assertEqual(0, self._neutralize_resist(
            high_component, owner, active_foe, foe_magic=False,
            resolved_formula='DEFENSE'))
        self.assertEqual(0, self._neutralize_resist(
            low_component, owner, active_foe, foe_magic=False))
        self.assertEqual(6, self._neutralize_resist(
            high_component, owner, active_foe, foe_magic=False))

    def test_skill_data_marks_only_wrathful_sources_and_mystic_neutralizers(self):
        marked_sources = {
            nid for nid, skill in self.skill_data.items()
            if 'lower_def_res_source' in dict(skill['components'])}
        neutralizers = {
            nid for nid, skill in self.skill_data.items()
            if 'neutralize_lower_def_res' in dict(skill['components'])}
        self.assertEqual(set(self.WRATHFUL), marked_sources)
        self.assertEqual(set(self.MYSTIC_HEALING), neutralizers)

        for nid in self.WRATHFUL:
            with self.subTest(nid=nid):
                components = dict(self.skill_data[nid]['components'])
                self.assertIn('lower_def_res_source', components)

        for nid, healing in self.MYSTIC_HEALING.items():
            with self.subTest(nid=nid):
                components = dict(self.skill_data[nid]['components'])
                self.assertIn('neutralize_lower_def_res', components)
                self.assertIn('negate_cannot_be_countered', components)
                self.assertEqual(healing, components['post_combat_healing'])

        t4_1 = dict(self.skill_data['Wrathfull_Staff_T4_1']['components'])
        t4_2 = dict(self.skill_data['Wrathfull_Staff_T4_2']['components'])
        self.assertIn('dynamic_damage', t4_1)
        self.assertIn('give_status_before_combat', t4_1)
        self.assertIn('dynamic_damage', t4_2)
        self.assertIn('no_dynamic_attacks', t4_2)
