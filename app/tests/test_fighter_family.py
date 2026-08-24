import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, combat_calcs, item_system, skill_system
from app.engine.game_state import game
from app.engine.objects.skill import SkillObject
from app.engine.skill_components.combat2_components import PreventFoeFollowUp
from app.utilities.data import Data


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
STAT_NIDS = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')
SLICK_EFFECT_NID = 'Slick_Neutralized_Penalty_Effect'
SLICK_DATA_KEY = 'slick_neutralized_self_penalties'


class RuntimeUnit:
    def __init__(self, nid, team, hp=100, max_hp=100, bonuses=None, skills=()):
        self.nid = nid
        self.team = team
        self.hp = hp
        self.max_hp = max_hp
        self.bonuses = bonuses or {stat: 0 for stat in STAT_NIDS}
        self.skills = list(skills)
        self.stats = {stat: 10 for stat in STAT_NIDS}
        self.equipped_weapon = None
        self.position = (0, 0)

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp

    def stat_bonus(self, stat):
        return self.bonuses[stat]

    @property
    def all_skills(self):
        return self.skills

    def add_skill(self, skill, source=None, source_type=None, test=False):
        if test:
            return None
        self.skills.append(skill)
        return None

    def remove_skill(self, skill, source=None, source_type=None, test=False):
        if skill not in self.skills:
            return False
        if test:
            return True
        self.skills.remove(skill)
        return source, source_type

    def autoequip(self):
        pass


class NoOpResetUnitVars:
    def __init__(self, unit):
        pass

    def execute(self):
        pass

    def reverse(self):
        pass


class FighterFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))

        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(nid):
        return dict(FighterFamilyTests.by_nid[nid]['components'])

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _single_component_skill(nid, component):
        return SkillObject(nid, nid, nid, components=Data([component]))

    def test_wary_uses_strict_thresholds_slot_b_fighter_categories_and_both_preventions(self):
        cases = (
            ('Wary_Fighter_T1', .9),
            ('Wary_Fighter_T2', .7),
            ('Wary_Fighter_T3', .5),
        )
        for nid, threshold in cases:
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertEqual(
                    f"unit.get_hp() > unit.get_max_hp() * {threshold}",
                    components['combat_condition'])
                self.assertIn('prevent_self_follow_up', components)
                self.assertIn('prevent_foe_follow_up', components)
                self.assertEqual('Skill System Slot B/Fighter Family', self.categories[nid])
                self.assertEqual(
                    f"If unit's HP is above {int(threshold * 100)}%, unit and foe cannot make a follow-up attack.",
                    self.by_nid[nid]['desc'])

    def test_wary_threshold_and_prevention_hooks_apply_only_above_threshold(self):
        for nid, threshold in (
                ('Wary_Fighter_T1', 90), ('Wary_Fighter_T2', 70), ('Wary_Fighter_T3', 50)):
            with self.subTest(nid=nid):
                skill = self._runtime_skill(nid)
                at_threshold = RuntimeUnit(nid, 'player', hp=threshold, skills=[skill])
                above_threshold = RuntimeUnit(nid, 'player', hp=threshold + 1, skills=[skill])
                skill_system.pre_combat([], at_threshold, None, None, None, 'attack')
                self.assertFalse(skill_system.condition(skill, at_threshold))
                self.assertFalse(skill_system.prevent_self_follow_up(at_threshold))
                self.assertFalse(skill_system.prevent_foe_follow_up(at_threshold))
                skill_system.pre_combat([], above_threshold, None, None, None, 'attack')
                self.assertTrue(skill_system.condition(skill, above_threshold))
                self.assertTrue(skill_system.prevent_self_follow_up(above_threshold))
                self.assertTrue(skill_system.prevent_foe_follow_up(above_threshold))

    def test_wary_prevention_blocks_natural_and_granted_follow_ups(self):
        unit = RuntimeUnit('wary', 'player', hp=100, skills=[self._runtime_skill('Wary_Fighter_T3')])
        target = RuntimeUnit('target', 'enemy')
        skill_system.pre_combat([], unit, None, target, None, 'attack')
        with patch.object(item_system, 'can_double', return_value=True), \
                patch('app.engine.combat_calcs.outspeed', return_value=1), \
                patch.object(item_system, 'dynamic_attacks', return_value=1), \
                patch.object(skill_system, 'dynamic_attacks', return_value=1), \
                patch.object(skill_system, 'dynamic_early_attacks', return_value=0):
            plan = combat_calcs.compute_attack_phase_plan(
                unit, target, object(), None, 'attack', (0, 0))
        self.assertEqual(1, plan.total_phases)

    def test_daring_early_children_only_activate_for_attack_below_their_strict_thresholds(self):
        for nid, threshold in (
                ('Daring_Fighter_T1_Effect', 40),
                ('Daring_Fighter_T2_Effect', 60),
                ('Daring_Fighter_T3_Effect', 80)):
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertEqual(
                    f"mode == 'attack' and unit.get_hp() < unit.get_max_hp()*{threshold / 100:g}",
                    components['combat_condition'])
                self.assertEqual('1', components['dynamic_early_attacks'])
                skill = self._runtime_skill(nid)
                attack = RuntimeUnit(nid, 'player', hp=threshold - 1, skills=[skill])
                defense = RuntimeUnit(nid, 'player', hp=threshold - 1, skills=[skill])
                at_threshold = RuntimeUnit(nid, 'player', hp=threshold, skills=[skill])
                skill_system.pre_combat([], attack, None, None, None, 'attack')
                self.assertTrue(skill_system.condition(skill, attack))
                self.assertEqual(1, skill_system.dynamic_early_attacks(
                    attack, None, None, None, 'attack', (0, 0), 0))
                skill_system.pre_combat([], defense, None, None, None, 'defense')
                self.assertFalse(skill_system.condition(skill, defense))
                skill_system.pre_combat([], at_threshold, None, None, None, 'attack')
                self.assertFalse(skill_system.condition(skill, at_threshold))

    def test_slick_snapshot_neutralizes_only_existing_negative_penalties_without_base_stat_mutation(self):
        source = self.custom_components.SlickNeutralizeSelfPenalties()
        unit = RuntimeUnit(
            'slick', 'player', bonuses={'STR': -4, 'MAG': 3, 'SKL': 0, 'SPD': -2,
                                        'LCK': 1, 'DEF': -1, 'RES': 5})
        effect_skill = SimpleNamespace(data={SLICK_DATA_KEY: {}})
        add_skill = SimpleNamespace(skill_obj=effect_skill)
        original_stats = unit.stats.copy()
        with patch.object(action, 'AddSkill', return_value=add_skill) as make_effect, \
                patch.object(action, 'do') as do_action:
            source.start_combat([], unit, None, None, None, 'defense')

        self.assertEqual({'STR': 4, 'MAG': 0, 'SKL': 0, 'SPD': 2,
                          'LCK': 0, 'DEF': 1, 'RES': 0}, effect_skill.data[SLICK_DATA_KEY])
        make_effect.assert_called_once_with(unit, SLICK_EFFECT_NID, unit)
        do_action.assert_called_once_with(add_skill)
        self.assertEqual(original_stats, unit.stats)

    def test_slick_effect_is_idempotent_reads_only_instance_snapshot_and_expires_after_combat(self):
        source = self.custom_components.SlickNeutralizeSelfPenalties()
        unit = RuntimeUnit('slick', 'player', bonuses={stat: -2 for stat in STAT_NIDS})
        unit.skills.append(SimpleNamespace(nid=SLICK_EFFECT_NID))
        with patch.object(action, 'AddSkill') as make_effect, patch.object(action, 'do') as do_action:
            source.start_combat([], unit, None, None, None, 'defense')
        make_effect.assert_not_called()
        do_action.assert_not_called()

        effect = self.custom_components.SlickNeutralizedPenaltyStatChange()
        effect.skill = SimpleNamespace(data={SLICK_DATA_KEY: {
            'STR': 4, 'MAG': 0, 'SKL': 3, 'SPD': 0, 'LCK': 1, 'DEF': 0, 'RES': 2,
        }})
        self.assertEqual(
            {'STR': 4, 'MAG': 0, 'SKL': 3, 'SPD': 0, 'LCK': 1, 'DEF': 0, 'RES': 2},
            effect.stat_change(None))

        effect_prefab = self._components(SLICK_EFFECT_NID)
        self.assertIn('hidden', effect_prefab)
        self.assertIn('slick_neutralized_penalty_stat_change', effect_prefab)
        self.assertEqual(
            {'lost_on_self': True, 'lost_on_ally': True, 'lost_on_enemy': True},
            effect_prefab['lost_on_end_combat2'])
        self.assertEqual('Skill System Slot B/Fighter Family', self.categories[SLICK_EFFECT_NID])

    def test_slick_runtime_neutralizes_penalties_restores_them_after_cleanup_and_keeps_follow_up(self):
        source = RuntimeUnit(
            'slick', 'player', hp=100,
            bonuses={'STR': -4, 'MAG': 3, 'SKL': 0, 'SPD': -2, 'LCK': 1, 'DEF': -1, 'RES': 5},
            skills=[self._runtime_skill('Slick_Fighter_T3')])
        target = RuntimeUnit('target', 'enemy')
        original_stats = source.stats.copy()
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda act: act.do()), \
                patch.object(game, 'skill_registry', {}):
            skill_system.pre_combat([], source, None, target, None, 'defense')
            skill_system.start_combat([], source, None, target, None, 'defense')
            effects = [skill for skill in source.skills if skill.nid == SLICK_EFFECT_NID]
            self.assertEqual(1, len(effects))
            self.assertEqual({'STR': 4, 'MAG': 0, 'SKL': 0, 'SPD': 2,
                              'LCK': 0, 'DEF': 1, 'RES': 0}, effects[0].data[SLICK_DATA_KEY])
            self.assertEqual(1, skill_system.dynamic_attacks(
                source, None, target, None, 'defense', (0, 0), 0))
            self.assertEqual(original_stats, source.stats)
            skill_system.cleanup_combat([], source, None, target, None, 'defense')
            skill_system.post_combat([], source, None, target, None, 'defense')
            self.assertFalse(any(skill.nid == SLICK_EFFECT_NID for skill in source.skills))

    def test_slick_component_is_attached_to_exactly_three_parents_and_wily_remains_single_dull_consumer(self):
        slick_consumers = [
            skill['nid'] for skill in self.skills
            if 'slick_neutralize_self_penalties' in dict(skill['components'])
        ]
        self.assertEqual(
            ['Slick_Fighter_T1', 'Slick_Fighter_T2', 'Slick_Fighter_T3'], slick_consumers)
        for nid in slick_consumers:
            components = self._components(nid)
            self.assertEqual('1', components['dynamic_attacks'])
            self.assertIn("mode == 'defense'", components['combat_condition'])

        wily_consumers = [
            skill['nid'] for skill in self.skills
            if skill['nid'].startswith('Wily_Fighter')
            and 'dull_wily_neutralize_bonuses' in dict(skill['components'])
        ]
        self.assertEqual(['Wily_Fighter_Effect_1'], wily_consumers)

    def test_daring_shared_neutralizer_remains_attack_only(self):
        components = self._components('Daring_Fighter_Effect')
        self.assertEqual("mode == 'attack'", components['combat_condition'])
        self.assertIn('neutralize_follow_up_prevention', components)


if __name__ == '__main__':
    import unittest
    unittest.main()
