import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, skill_system
from app.engine.game_state import game
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILIES = ('Attack', 'Speed', 'Defense', 'Resistance')


class RuntimeUnit:
    def __init__(self, nid, team, skills=()):
        self.nid = nid
        self.team = team
        self.skills = list(skills)
        self.position = None
        self.equipped_weapon = None

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


class NoOpAction:
    def do(self):
        pass


class SealFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.by_nid = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _components(prefab):
        return dict(prefab['components'])

    def test_project_migrates_every_seal_parent_and_post_effect(self):
        seal_parents = [
            skill for skill in self.by_nid.values()
            if skill['nid'].startswith('Seal_') and '_Effect' not in skill['nid']
        ]
        seal_effects = [
            skill for skill in self.by_nid.values()
            if skill['nid'].startswith('Seal_') and '_Effect' in skill['nid']
        ]
        self.assertEqual(16, len(seal_parents))
        self.assertEqual(20, len(seal_effects))
        self.assertEqual(
            16,
            sum('give_status_after_combat_until_next_action' in self._components(skill)
                for skill in seal_parents))
        self.assertFalse(any('give_status_after_combat' in self._components(skill) for skill in seal_parents))
        self.assertEqual(
            16,
            sum('lost_on_next_action' in self._components(skill) for skill in seal_effects))
        self.assertFalse(any('lost_on_endstep' in self._components(skill) for skill in seal_effects))
        self.assertEqual(
            4,
            sum('lost_on_end_combat2' in self._components(skill) for skill in seal_effects))
        self.assertEqual(
            'Seal_Attack_T4_Effect_1',
            self._components(self.by_nid['Seal_Attack_T4'])['give_status_before_combat'])

    def test_post_effects_keep_only_the_strongest_tier_in_each_family(self):
        conditions = 0
        for family in FAMILIES:
            for tier in range(1, 4):
                nid = f'Seal_{family}_T{tier}_Effect'
                components = self._components(self.by_nid[nid])
                stronger = [
                    f"not has_skill(unit, 'Seal_{family}_T{higher}_Effect{('_2' if higher == 4 else '')}')"
                    for higher in range(tier + 1, 5)
                ]
                with self.subTest(nid=nid):
                    self.assertEqual(' and '.join(stronger), components['condition'])
                    self.assertIn('hidden_if_inactive', components)
                conditions += 1
            self.assertNotIn(
                'condition', self._components(self.by_nid[f'Seal_{family}_T4_Effect_1']))
        self.assertEqual(12, conditions)

    def test_strongest_post_effect_wins_per_family_but_other_families_stack(self):
        unit = RuntimeUnit('target', 'enemy', [
            self._runtime_skill('Seal_Attack_T1_Effect'),
            self._runtime_skill('Seal_Attack_T3_Effect'),
            self._runtime_skill('Seal_Speed_T2_Effect'),
            self._runtime_skill('Seal_Attack_T4_Effect_1'),
        ])
        skill_system.pre_combat([], unit, None, None, None, 'attack')
        self.assertEqual(
            {'STR': -11, 'MAG': -11, 'SPD': -5},
            {stat: value for stat in ('STR', 'MAG', 'SPD')
             if (value := skill_system.stat_change(unit, stat))})
        self.assertNotIn(
            'condition', self._components(self.by_nid['Seal_Attack_T4_Effect_1']))

    def test_defensive_tactical_combat_skips_only_the_immediate_wait_and_reverses(self):
        source_skill = self._runtime_skill('Seal_Attack_T1')
        source = RuntimeUnit('source', 'enemy', [source_skill])
        target = RuntimeUnit('target', 'player')
        giver = source_skill.components.get('give_status_after_combat_until_next_action')
        executed = []

        def execute(queued_action):
            executed.append(queued_action)
            queued_action.do()

        combat = SimpleNamespace(finalizes_turn=True, event_combat=False)
        with patch.object(game, 'memory', {'current_combat': combat}), \
                patch.object(game, 'skill_registry', {}), \
                patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'TriggerCharge', return_value=NoOpAction()), \
                patch.object(action, 'do', side_effect=execute):
            giver.end_combat([], source, None, target, None, 'defense')
            effect = target.skills[0]
            self.assertTrue(effect.data['skip_current_wait'])

            skill_system.on_wait(target, False)
            self.assertIn(effect, target.skills)
            self.assertFalse(effect.data['skip_current_wait'])
            skipped_wait = executed[-1]
            skipped_wait.reverse()
            self.assertTrue(effect.data['skip_current_wait'])
            skipped_wait.do()

            skill_system.on_wait(target, False)
            self.assertNotIn(effect, target.skills)

    def test_event_and_base_combat_do_not_skip_the_next_wait(self):
        for current_combat in (
                SimpleNamespace(finalizes_turn=False, event_combat=False),
                SimpleNamespace(finalizes_turn=True, event_combat=True),
                None):
            with self.subTest(current_combat=current_combat):
                source_skill = self._runtime_skill('Seal_Speed_T1')
                source = RuntimeUnit('source', 'enemy', [source_skill])
                target = RuntimeUnit('target', 'player')
                giver = source_skill.components.get('give_status_after_combat_until_next_action')
                with patch.object(game, 'memory', {'current_combat': current_combat}), \
                        patch.object(game, 'skill_registry', {}), \
                        patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                        patch.object(action, 'TriggerCharge', return_value=NoOpAction()), \
                        patch.object(action, 'do', side_effect=lambda queued: queued.do()):
                    giver.end_combat([], source, None, target, None, 'defense')
                    effect = target.skills[0]
                    self.assertFalse(effect.data['skip_current_wait'])
                    skill_system.on_wait(target, False)
                    self.assertNotIn(effect, target.skills)


if __name__ == '__main__':
    import unittest
    unittest.main()
