import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, combat_calcs, item_system, skill_system
from app.engine.objects.skill import SkillObject
from app.engine.skill_components.combat2_components import PreventFoeFollowUp
from app.utilities.data import Data


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class RuntimeUnit:
    def __init__(self, nid, team, hp=100, max_hp=100, skills=()):
        self.nid = nid
        self.team = team
        self.hp = hp
        self.max_hp = max_hp
        self.skills = list(skills)
        self.equipped_weapon = None
        self.position = (0, 0)

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp


class NullFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}

    def _components(self, nid):
        return dict(self.by_nid[nid]['components'])

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _single_component_skill(nid, component):
        return SkillObject(nid, nid, nid, components=Data([component]))

    def test_null_family_has_nine_main_skills_and_three_t4_children(self):
        main = (
            'Null_Follow_Up_T1', 'Null_Follow_Up_T2', 'Null_Follow_Up_T3',
            'Null_Follow_Up_T4_1', 'Null_Follow_Up_T4_2',
            'Null_C_Disrupt_T1', 'Null_C_Disrupt_T2', 'Null_C_Disrupt_T3',
            'Null_C_Disrupt_T4',
        )
        children = (
            'Null_Follow_Up_T4_1_Effect', 'Null_Follow_Up_T4_2_Effect',
            'Null_C_Disrupt_T4_Effect',
        )

        self.assertEqual(9, len(main))
        self.assertEqual(3, len(children))
        for nid in (*main, *children):
            self.assertIn(nid, self.by_nid)
            self.assertIsNotNone(DB.skills.get(nid))

    def test_null_follow_t1_t2_conditions_and_t3_t4_unconditional_neutral_hooks(self):
        self.assertEqual(
            'unit.get_hp() == unit.get_max_hp()',
            self._components('Null_Follow_Up_T1')['combat_condition'])
        self.assertEqual(
            'unit.get_hp() > unit.get_max_hp() * 0.5',
            self._components('Null_Follow_Up_T2')['combat_condition'])
        for nid in ('Null_Follow_Up_T3', 'Null_Follow_Up_T4_1', 'Null_Follow_Up_T4_2'):
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertNotIn('combat_condition', components)
                self.assertIn('neutralize_foe_follow_up_grants', components)
                self.assertIn('neutralize_follow_up_prevention', components)

    def test_null_follow_runtime_conditions_activate_the_real_neutralization_hooks(self):
        threshold_cases = (
            ('Null_Follow_Up_T1', 100, True),
            ('Null_Follow_Up_T1', 99, False),
            ('Null_Follow_Up_T2', 51, True),
            ('Null_Follow_Up_T2', 50, False),
        )
        for nid, hp, active in threshold_cases:
            with self.subTest(nid=nid, hp=hp):
                skill = self._runtime_skill(nid)
                unit = RuntimeUnit(nid, 'player', hp=hp, skills=[skill])
                skill_system.pre_combat([], unit, None, None, None, 'attack')

                self.assertEqual(active, skill_system.condition(skill, unit))
                self.assertEqual(active, skill_system.neutralize_foe_follow_up_grants(unit))
                self.assertEqual(active, skill_system.neutralize_follow_up_prevention(unit))

        for nid in ('Null_Follow_Up_T3', 'Null_Follow_Up_T4_1', 'Null_Follow_Up_T4_2'):
            with self.subTest(nid=nid):
                skill = self._runtime_skill(nid)
                unit = RuntimeUnit(nid, 'player', hp=1, skills=[skill])
                skill_system.pre_combat([], unit, None, None, None, 'attack')

                self.assertTrue(skill_system.condition(skill, unit))
                self.assertTrue(skill_system.neutralize_foe_follow_up_grants(unit))
                self.assertTrue(skill_system.neutralize_follow_up_prevention(unit))

    def test_null_follow_t3_resolver_neutralizes_foe_grants_but_preserves_natural_follow_up(self):
        unit = RuntimeUnit('user', 'player')
        target = RuntimeUnit('foe', 'enemy', skills=[self._runtime_skill('Null_Follow_Up_T3')])

        with patch.object(item_system, 'can_double', return_value=True), \
                patch('app.engine.combat_calcs.outspeed', return_value=1), \
                patch.object(item_system, 'dynamic_attacks', return_value=2), \
                patch.object(skill_system, 'dynamic_attacks', return_value=3), \
                patch.object(skill_system, 'dynamic_early_attacks', return_value=4):
            plan = combat_calcs.compute_attack_phase_plan(
                unit, target, object(), None, 'attack', (0, 0))

        self.assertEqual(2, plan.total_phases)
        self.assertEqual(0, plan.early_phases)

    def test_null_follow_t3_resolver_restores_user_follow_up_against_real_prevention(self):
        unit = RuntimeUnit('user', 'player', skills=[self._runtime_skill('Null_Follow_Up_T3')])
        target = RuntimeUnit(
            'foe', 'enemy',
            skills=[self._single_component_skill('FoePreventsFollowUp', PreventFoeFollowUp())])

        self.assertTrue(skill_system.prevent_foe_follow_up(target))
        self.assertTrue(skill_system.neutralize_follow_up_prevention(unit))
        with patch.object(item_system, 'can_double', return_value=True), \
                patch('app.engine.combat_calcs.outspeed', return_value=1), \
                patch('app.engine.combat_calcs.resolve_weapon', return_value=None), \
                patch.object(item_system, 'dynamic_attacks', return_value=0), \
                patch.object(skill_system, 'dynamic_attacks', return_value=0), \
                patch.object(skill_system, 'dynamic_early_attacks', return_value=0):
            plan = combat_calcs.compute_attack_phase_plan(
                unit, target, object(), None, 'attack', (0, 0))

        self.assertEqual(2, plan.total_phases)
        self.assertEqual(0, plan.early_phases)

    def test_null_c_t1_t2_conditions_and_t3_t4_unconditional_counter_null(self):
        self.assertEqual(
            'unit.get_hp() == unit.get_max_hp()',
            self._components('Null_C_Disrupt_T1')['combat_condition'])
        self.assertEqual(
            'unit.get_hp() > unit.get_max_hp() * 0.5',
            self._components('Null_C_Disrupt_T2')['combat_condition'])
        for nid in ('Null_C_Disrupt_T3', 'Null_C_Disrupt_T4'):
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertNotIn('combat_condition', components)
                self.assertIn('negate_cannot_be_countered', components)

    def test_resist_first_strike_only_reduces_first_strike_of_first_phase(self):
        component = next(
            component for component in DB.skills.get('Null_C_Disrupt_T4').components
            if component.nid == 'resist_first_strike')

        self.assertEqual(.7, component.resist_multiplier(None, None, None, None, None, (0, 0), 1))
        for attack_info in ((0, 1), (1, 0), (1, 1), (2, 0)):
            with self.subTest(attack_info=attack_info):
                self.assertEqual(1, component.resist_multiplier(None, None, None, None, None, attack_info, 1))

    def test_all_six_resist_first_strike_consumers_keep_values_and_only_affect_first_strike(self):
        expected_values = {
            'Quick_Riposte_T4': .75,
            'Null_C_Disrupt_T4': .7,
            'Dragons_Wrath_T1': .9,
            'Dragons_Wrath_T2': .85,
            'Dragons_Wrath_T3': .8,
            'Dragons_Wrath_T4': .75,
        }
        consumers = [
            skill['nid'] for skill in self.skills
            if 'resist_first_strike' in dict(skill['components'])
        ]
        self.assertEqual(list(expected_values), consumers)

        for nid, expected_value in expected_values.items():
            with self.subTest(nid=nid):
                component = next(
                    component for component in self._runtime_skill(nid).components
                    if component.nid == 'resist_first_strike')
                self.assertEqual(expected_value, component.value)
                self.assertEqual(expected_value, component.resist_multiplier(
                    None, None, None, None, None, (0, 0), 1))
                self.assertEqual(1, component.resist_multiplier(
                    None, None, None, None, None, (0, 1), 1))
                self.assertEqual(1, component.resist_multiplier(
                    None, None, None, None, None, (1, 0), 1))

    def test_null_c_disrupt_bypasses_only_the_uncounterable_item_gate(self):
        attacker = RuntimeUnit('attacker', 'enemy')
        defender = RuntimeUnit('defender', 'player', skills=[self._runtime_skill('Null_C_Disrupt_T3')])
        defender.position = (1, 0)
        weapon = object()
        target_system = SimpleNamespace(targets_in_range=lambda unit, item: {attacker.position})

        with patch('app.engine.combat_calcs.item_funcs.available', return_value=True), \
                patch.object(item_system, 'can_be_countered', return_value=False), \
                patch.object(item_system, 'can_counter', return_value=True), \
                patch.object(skill_system, 'can_counter', return_value=True), \
                patch.object(combat_calcs, 'game', SimpleNamespace(target_system=target_system)):
            self.assertTrue(combat_calcs.can_counterattack(attacker, weapon, defender, weapon))

        with patch('app.engine.combat_calcs.item_funcs.available', return_value=False):
            self.assertFalse(combat_calcs.can_counterattack(attacker, weapon, defender, weapon))

        with patch('app.engine.combat_calcs.item_funcs.available', return_value=True), \
                patch.object(item_system, 'can_be_countered', return_value=False), \
                patch.object(item_system, 'can_counter', return_value=False):
            self.assertFalse(combat_calcs.can_counterattack(attacker, weapon, defender, weapon))

        out_of_range_target_system = SimpleNamespace(targets_in_range=lambda unit, item: set())
        with patch('app.engine.combat_calcs.item_funcs.available', return_value=True), \
                patch.object(item_system, 'can_be_countered', return_value=False), \
                patch.object(item_system, 'can_counter', return_value=True), \
                patch.object(skill_system, 'can_counter', return_value=True), \
                patch.object(combat_calcs, 'game', SimpleNamespace(target_system=out_of_range_target_system)):
            self.assertFalse(combat_calcs.can_counterattack(attacker, weapon, defender, weapon))

    def test_null_follow_t4_parent_applies_expiring_child_status(self):
        parent = self._runtime_skill('Null_Follow_Up_T4_1')
        source = RuntimeUnit('source', 'player', skills=[parent])
        target = RuntimeUnit('target', 'enemy')

        with patch.object(action, 'AddSkill', return_value=SimpleNamespace()) as add_skill, \
                patch.object(action, 'TriggerCharge', return_value=SimpleNamespace()), \
                patch.object(action, 'do') as do_action:
            skill_system.start_combat([], source, None, target, None, 'attack')

        add_skill.assert_called_once_with(target, 'Null_Follow_Up_T4_1_Effect', source)
        self.assertEqual(2, do_action.call_count)

        child = self._runtime_skill('Null_Follow_Up_T4_1_Effect')
        expiration = child.components.get('lost_on_end_combat2')
        self.assertIsNotNone(expiration)
        with patch.object(action, 'RemoveSkill', return_value=SimpleNamespace()) as remove_skill, \
                patch.object(action, 'do') as do_action:
            expiration.cleanup_combat_unconditional([], target, None, source, None, 'defense')
            expiration.post_combat_unconditional([], target, None, source, None, 'defense')

        remove_skill.assert_called_once_with(target, child)
        self.assertEqual(1, do_action.call_count)

    def test_null_c_t4_and_t4_child_values(self):
        self.assertEqual(.7, self._components('Null_C_Disrupt_T4')['resist_first_strike'])
        self.assertEqual(
            [['SPD', -4], ['DEF', -4]],
            self._components('Null_Follow_Up_T4_1_Effect')['stat_change'])
        self.assertEqual(
            [['SPD', -4], ['RES', -4]],
            self._components('Null_Follow_Up_T4_2_Effect')['stat_change'])
        null_c_effect = self._components('Null_C_Disrupt_T4_Effect')
        self.assertEqual([['SPD', -4]], null_c_effect['stat_change'])
        self.assertEqual(-4, null_c_effect['damage'])
        for nid in ('Null_Follow_Up_T4_1', 'Null_Follow_Up_T4_2'):
            with self.subTest(nid=nid):
                self.assertEqual(.5, self._components(nid)['reduce_resist_multiplier'])


if __name__ == '__main__':
    import unittest
    unittest.main()
