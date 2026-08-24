import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, item_system
from app.engine import skill_system
from app.engine.game_state import game
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
STAT_NIDS = ('STR', 'MAG', 'SKL', 'SPD', 'LCK', 'DEF', 'RES')
EFFECT_NID = 'Dull_Wily_Neutralized_Bonus_Effect'
DATA_KEY = 'dull_wily_neutralized_bonuses'


class BonusUnit:
    def __init__(self, bonuses, nid='target', team='enemy'):
        self.nid = nid
        self.team = team
        self.bonuses = bonuses
        self.skills = []
        self.stats = {stat: 10 for stat in STAT_NIDS}
        self.position = None
        self.equipped_weapon = None

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


class DullFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        cls.events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)

        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(skill):
        return dict(skill['components'])

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    def test_all_sources_use_the_custom_snapshot_component_and_no_legacy_events(self):
        source_nids = (
            'Dull_Close_T1', 'Dull_Close_T2', 'Dull_Close_T3',
            'Dull_Ranged_T1', 'Dull_Ranged_T2', 'Dull_Ranged_T3',
            'Wily_Fighter_Effect_1',
        )
        for nid in source_nids:
            with self.subTest(nid=nid):
                components = self._components(self.skills[nid])
                self.assertIn('dull_wily_neutralize_bonuses', components)
                self.assertNotIn('event_before_combat', components)
                self.assertNotIn('event_after_combat', components)

        self.assertNotIn('Global WilyFighterSkill', {event['nid'] for event in self.events})
        self.assertNotIn('Global WilyFighterSkill2', {event['nid'] for event in self.events})

    def test_dull_conditions_accept_matching_weapon_range_or_combat_distance(self):
        for nid in ('Dull_Close_T1', 'Dull_Close_T2', 'Dull_Close_T3'):
            with self.subTest(nid=nid):
                condition = self._components(self.skills[nid])['combat_condition']
                self.assertIn('item_system.maximum_range(target, item2) == 1', condition)
                self.assertIn('item2 and item_system.maximum_range', condition)
                self.assertIn('utils.calculate_distance(unit.position, target.position) == 1', condition)
                self.assertIn(' or ', condition)

        for nid in ('Dull_Ranged_T1', 'Dull_Ranged_T2', 'Dull_Ranged_T3'):
            with self.subTest(nid=nid):
                condition = self._components(self.skills[nid])['combat_condition']
                self.assertIn('item_system.maximum_range(target, item2) > 1', condition)
                self.assertIn('item2 and item_system.maximum_range', condition)
                self.assertIn('utils.calculate_distance(unit.position, target.position) > 1', condition)
                self.assertIn(' or ', condition)

        self.assertNotIn('get_hp()', self._components(self.skills['Dull_Ranged_T3'])['combat_condition'])

    def test_dull_conditions_short_circuit_without_weapon_and_accept_weapon_or_distance(self):
        def condition_is_active(nid, source_position, target_position, item2, maximum_range):
            source = BonusUnit({stat: 0 for stat in STAT_NIDS}, nid='source', team='player')
            source.position = source_position
            source.skills = [self._runtime_skill(nid)]
            target = BonusUnit({stat: 0 for stat in STAT_NIDS})
            target.position = target_position
            with patch.object(item_system, 'maximum_range', return_value=maximum_range) as get_range:
                skill_system.pre_combat([], source, None, target, item2, 'attack')
                active = skill_system.condition(source.skills[0], source)
            return active, get_range

        close_without_weapon, close_range = condition_is_active(
            'Dull_Close_T3', (0, 0), (1, 0), None, 99)
        self.assertTrue(close_without_weapon)
        close_range.assert_not_called()

        close_by_weapon, close_range = condition_is_active(
            'Dull_Close_T3', (0, 0), (2, 0), object(), 1)
        self.assertTrue(close_by_weapon)
        close_range.assert_called_once()

        ranged_without_weapon, ranged_range = condition_is_active(
            'Dull_Ranged_T3', (0, 0), (2, 0), None, 0)
        self.assertTrue(ranged_without_weapon)
        ranged_range.assert_not_called()

        ranged_by_weapon, ranged_range = condition_is_active(
            'Dull_Ranged_T3', (0, 0), (1, 0), object(), 2)
        self.assertTrue(ranged_by_weapon)
        ranged_range.assert_called_once()

    def test_neutralization_snapshots_only_positive_bonuses_without_mutating_base_stats_or_vars(self):
        source = self.custom_components.DullWilyNeutralizeBonuses()
        target = BonusUnit({'STR': 4, 'MAG': -3, 'SKL': 0, 'SPD': 2, 'LCK': 1, 'DEF': -1, 'RES': 5})
        source_unit = SimpleNamespace()
        effect_skill = SimpleNamespace(data={DATA_KEY: {}})
        add_skill = SimpleNamespace(skill_obj=effect_skill)
        original_stats = target.stats.copy()

        with patch.object(action, 'AddSkill', return_value=add_skill) as make_effect, \
                patch.object(action, 'do') as do_action:
            source.start_combat([], source_unit, None, target, None, 'attack')

        expected = {'STR': 4, 'MAG': 0, 'SKL': 0, 'SPD': 2, 'LCK': 1, 'DEF': 0, 'RES': 5}
        make_effect.assert_called_once_with(target, EFFECT_NID, source_unit)
        do_action.assert_called_once_with(add_skill)
        self.assertEqual(expected, effect_skill.data[DATA_KEY])
        self.assertEqual(original_stats, target.stats)

    def test_neutralization_is_idempotent_per_target_combat_and_effect_reads_instance_data(self):
        source = self.custom_components.DullWilyNeutralizeBonuses()
        target = BonusUnit({stat: 3 for stat in STAT_NIDS})
        target.skills.append(SimpleNamespace(nid=EFFECT_NID))

        with patch.object(action, 'AddSkill') as make_effect, patch.object(action, 'do') as do_action:
            source.start_combat([], SimpleNamespace(), None, target, None, 'attack')

        make_effect.assert_not_called()
        do_action.assert_not_called()

        effect = self.custom_components.DullWilyNeutralizedBonusEffect()
        effect.skill = SimpleNamespace(data={
            DATA_KEY: {'STR': 4, 'MAG': 0, 'SKL': 3, 'SPD': 0, 'LCK': 1, 'DEF': 0, 'RES': 2},
        })
        self.assertEqual(
            {'STR': -4, 'MAG': 0, 'SKL': -3, 'SPD': 0, 'LCK': -1, 'DEF': 0, 'RES': -2},
            effect.stat_change(None))

    def test_real_start_combat_adds_one_effect_then_cleanup_allows_the_next_combat(self):
        source_unit = BonusUnit({stat: 0 for stat in STAT_NIDS}, nid='source', team='player')
        source_unit.skills = [self._runtime_skill('Wily_Fighter_Effect_1')]
        target = BonusUnit({'STR': 4, 'MAG': -3, 'SKL': 0, 'SPD': 2, 'LCK': 1, 'DEF': -1, 'RES': 5})
        original_stats = target.stats.copy()

        add_effect_snapshots = []
        original_add_skill_do = action.AddSkill.do

        def inspect_add_skill_data(add_skill):
            add_effect_snapshots.append(add_skill.skill_obj.data[DATA_KEY].copy())
            original_add_skill_do(add_skill)

        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda act: act.do()), \
                patch.object(action.AddSkill, 'do', new=inspect_add_skill_data), \
                patch.object(game, 'skill_registry', {}):
            skill_system.start_combat([], source_unit, None, target, None, 'attack')
            effects = [skill for skill in target.skills if skill.nid == EFFECT_NID]
            self.assertEqual(1, len(effects))
            self.assertEqual(
                {'STR': 4, 'MAG': 0, 'SKL': 0, 'SPD': 2, 'LCK': 1, 'DEF': 0, 'RES': 5},
                effects[0].data[DATA_KEY])
            self.assertEqual(effects[0].data[DATA_KEY], add_effect_snapshots[0])
            self.assertEqual(original_stats, target.stats)

            skill_system.start_combat([], source_unit, None, target, None, 'attack')
            self.assertEqual(1, sum(skill.nid == EFFECT_NID for skill in target.skills))

            skill_system.cleanup_combat([], target, None, source_unit, None, 'defense')
            skill_system.post_combat([], target, None, source_unit, None, 'defense')
            self.assertFalse(any(skill.nid == EFFECT_NID for skill in target.skills))

            target.bonuses['STR'] = 1
            skill_system.start_combat([], source_unit, None, target, None, 'attack')
            next_effects = [skill for skill in target.skills if skill.nid == EFFECT_NID]
            self.assertEqual(1, len(next_effects))
            self.assertEqual(1, next_effects[0].data[DATA_KEY]['STR'])

    def test_hidden_effect_is_categorized_and_contains_the_instance_stat_component(self):
        effect = self.skills[EFFECT_NID]
        components = self._components(effect)
        self.assertIn('hidden', components)
        self.assertIn('dull_wily_neutralized_bonus_effect', components)
        self.assertEqual(
            {'lost_on_self': True, 'lost_on_ally': True, 'lost_on_enemy': True},
            components['lost_on_end_combat2'])
        self.assertEqual('Skill System Slot B/Dull Family', self.categories[EFFECT_NID])
        for nid in ('Dull_Close_T1', 'Dull_Close_T2', 'Dull_Close_T3',
                    'Dull_Ranged_T1', 'Dull_Ranged_T2', 'Dull_Ranged_T3'):
            with self.subTest(nid=nid):
                self.assertEqual('Skill System Slot B/Dull Family', self.categories[nid])


if __name__ == '__main__':
    import unittest
    unittest.main()
