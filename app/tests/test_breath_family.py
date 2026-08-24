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
FAMILY = 'Skill System Slot C/Breath Family'
MAIN_NIDS = (
    'Breath_of_Life_T1', 'Breath_of_Life_T2', 'Breath_of_Life_T3', 'Breath_of_Life_T4',
    'Savage_Blow_T1', 'Savage_Blow_T2', 'Savage_Blow_T3', 'Deadly_Miasma',
)


class RuntimeUnit:
    def __init__(self, nid, team, position=(0, 0), hp=20, max_hp=20):
        self.nid = nid
        self.team = team
        self.position = position
        self.hp = hp
        self.max_hp = max_hp
        self.dead = False
        self.is_dying = False
        self.tags = []
        self.skills = []
        self.equipped_weapon = None

    @property
    def all_skills(self):
        return self.skills

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp

    def set_hp(self, value):
        self.hp = max(0, min(self.max_hp, value))

    def get_mana(self):
        return 0

    def set_mana(self, value):
        pass

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


class Field:
    def __init__(self, units):
        self.units = {unit.position: unit for unit in units if unit.position is not None}

    def get_unit(self, position):
        return self.units.get(position)


class TargetSystem:
    @staticmethod
    def get_adjacent_positions(position):
        x, y = position
        return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


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

    def reverse(self):
        pass


class BreathFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)

        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(nid):
        return dict(BreathFamilyTests.skills[nid]['components'])

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    def _breath_component(self, upkeep_heal=0, post_combat_heal=7):
        return self.custom_components.BreathAdjacentHeal({
            'upkeep_heal': upkeep_heal,
            'post_combat_heal': post_combat_heal,
        })

    def _field_context(self, units):
        return patch.multiple(
            self.custom_components.game,
            board=Field(units),
            target_system=TargetSystem(),
        )

    def test_static_inventory_and_data_migration_match_breath_contract(self):
        mains = [nid for nid, category in self.categories.items() if category == FAMILY and nid in MAIN_NIDS]
        self.assertEqual(set(MAIN_NIDS), set(mains))
        self.assertEqual(8, len(mains))

        expected_healing = {
            'Breath_of_Life_T1': {'upkeep_heal': 0, 'post_combat_heal': 5},
            'Breath_of_Life_T2': {'upkeep_heal': 0, 'post_combat_heal': 6},
            'Breath_of_Life_T3': {'upkeep_heal': 0, 'post_combat_heal': 7},
            'Breath_of_Life_T4': {'upkeep_heal': 10, 'post_combat_heal': 7},
        }
        for nid, values in expected_healing.items():
            with self.subTest(nid=nid):
                self.assertEqual(values, self._components(nid)['breath_adjacent_heal'])
                self.assertNotIn('do_nothing', self._components(nid))

        for nid, damage in (('Savage_Blow_T1', 5), ('Savage_Blow_T2', 6),
                            ('Savage_Blow_T3', 7), ('Deadly_Miasma', 10)):
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertEqual("mode == 'attack'", components['combat_condition'])
                self.assertEqual(damage, components['post_combat_damage'])
                self.assertNotIn('do_nothing', components)
                self.assertNotIn('better_post_combat_damage', components)

        deadly = self._components('Deadly_Miasma')
        self.assertEqual(3, deadly['priority'])
        self.assertEqual('Deadly_Miasma_Effect', deadly['give_status_after_combat_until_next_action'])
        self.assertEqual('Savage Blow 3', self.skills['Savage_Blow_T3']['name'])
        self.assertEqual(9, sum(
            'better_post_combat_damage' in dict(skill['components'])
            for skill in self.skills.values()))

    def test_breath_heals_only_injured_adjacent_living_allies_and_caps_hp(self):
        source = RuntimeUnit('source', 'player')
        injured = RuntimeUnit('injured', 'player', (1, 0), hp=16)
        full = RuntimeUnit('full', 'player', (0, 1))
        enemy = RuntimeUnit('enemy', 'enemy', (-1, 0), hp=5)
        distant = RuntimeUnit('distant', 'player', (2, 0), hp=5)
        dying = RuntimeUnit('dying', 'player', (0, -1), hp=5)
        dying.is_dying = True
        component = self._breath_component(upkeep_heal=10)
        queued = []

        with self._field_context([source, injured, full, enemy, distant, dying]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: target.team == owner.team):
            component.on_upkeep(queued, [], source)

        self.assertEqual(1, len(queued))
        self.assertIs(injured, queued[0].unit)
        self.assertEqual(10, queued[0].num)
        queued[0].do()
        self.assertEqual(20, injured.hp)
        self.assertEqual(20, full.hp)
        self.assertEqual(5, enemy.hp)
        self.assertEqual(5, distant.hp)
        self.assertEqual(5, dying.hp)

    def test_breath_post_combat_runs_after_an_initiated_miss_but_not_in_defense(self):
        source = RuntimeUnit('source', 'player')
        ally = RuntimeUnit('ally', 'player', (1, 0), hp=10)
        foe = RuntimeUnit('foe', 'enemy', (2, 0), hp=20)
        component = self._breath_component(post_combat_heal=7)

        with self._field_context([source, ally, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: target.team == owner.team), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team != owner.team), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            component.end_combat([], source, None, foe, None, 'attack')
            self.assertEqual(17, ally.hp)
            component.end_combat([], source, None, foe, None, 'defense')

        self.assertEqual(17, ally.hp)

    def test_breath_post_combat_still_heals_adjacent_allies_when_the_user_is_dying(self):
        source = RuntimeUnit('source', 'player')
        source.is_dying = True
        ally = RuntimeUnit('ally', 'player', (1, 0), hp=10)
        foe = RuntimeUnit('foe', 'enemy', (2, 0), hp=20)
        component = self._breath_component(post_combat_heal=7)

        with self._field_context([source, ally, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: target.team == owner.team), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team != owner.team), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            component.end_combat([], source, None, foe, None, 'attack')

        self.assertEqual(17, ally.hp)

    def test_deadly_miasma_effect_debuffs_three_stats_and_expires_on_the_target_next_action(self):
        effect = self.skills['Deadly_Miasma_Effect']
        components = self._components('Deadly_Miasma_Effect')
        self.assertEqual([['SPD', -5], ['DEF', -5], ['RES', -5]], components['stat_change'])
        self.assertIn('hidden', components)
        self.assertIn('lost_on_next_action', components)
        self.assertIn('lost_on_end_chapter', components)
        self.assertEqual(FAMILY, self.categories['Deadly_Miasma_Effect'])

        source_skill = self._runtime_skill('Deadly_Miasma')
        source = RuntimeUnit('source', 'player')
        source.skills = [source_skill]
        target = RuntimeUnit('target', 'enemy')
        giver = source_skill.components.get('give_status_after_combat_until_next_action')
        with patch.object(game, 'skill_registry', {}), \
                patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'TriggerCharge', return_value=NoOpAction()), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            giver.end_combat([], source, None, target, None, 'attack')
            self.assertEqual(['Deadly_Miasma_Effect'], [skill.nid for skill in target.skills])
            self.assertEqual(-5, skill_system.stat_change(target, 'SPD'))
            self.assertEqual(-5, skill_system.stat_change(target, 'DEF'))
            self.assertEqual(-5, skill_system.stat_change(target, 'RES'))
            skill_system.on_wait(target, False)
        self.assertEqual([], target.skills)

    def test_core_post_combat_damage_is_nonlethal(self):
        source_skill = self._runtime_skill('Deadly_Miasma')
        source = RuntimeUnit('source', 'player')
        source.skills = [source_skill]
        target = RuntimeUnit('target', 'enemy', hp=4)
        damage = source_skill.components.get('post_combat_damage')
        with patch.object(action, 'TriggerCharge', return_value=NoOpAction()), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            damage.end_combat([], source, None, target, None, 'attack')
        self.assertEqual(1, target.hp)


if __name__ == '__main__':
    import unittest
    unittest.main()
