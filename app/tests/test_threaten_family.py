import importlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, skill_component_access, skill_system
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Threaten Family'
STANDARD_PARENTS = {
    'Threaten_Attack_T1': (('STR',), 0),
    'Threaten_Strength_T2': (('STR',), 0), 'Threaten_Strength_T3': (('STR',), 0),
    'Threaten_Magic_T1': (('MAG',), 0), 'Threaten_Magic_T2': (('MAG',), 0), 'Threaten_Magic_T3': (('MAG',), 0),
    'Threaten_Speed_T1': (('SPD',), 0), 'Threaten_Speed_T2': (('SPD',), 0), 'Threaten_Speed_T3': (('SPD',), 0),
    'Threaten_Def_T1': (('DEF',), 0), 'Threaten_Def_T2': (('DEF',), 0), 'Threaten_Defense_T3': (('DEF',), 0),
    'Threaten_Resistance_T1': (('RES',), 0), 'Threaten_Resistance_T2': (('RES',), 0), 'Threaten_Resistance_T3': (('RES',), 0),
    'Threaten_Atk_Spd_T1': (('SPD',), -3), 'Threaten_Atk_Spd_T2': (('SPD',), -4),
    'Threaten_Atk_Def_T1': (('DEF',), -3), 'Threaten_Atk_Def_T2': (('DEF',), -4),
    'Threaten_Atk_Res_T1': (('RES',), -3), 'Threaten_Atk_Res_T2': (('RES',), -4),
    'Threaten_Spd_Def_T1': (('SPD', 'DEF'), 0), 'Threaten_Spd_Def_T2': (('SPD', 'DEF'), 0),
    'Threaten_Def_Res_T1': (('DEF', 'RES'), 0), 'Threaten_Def_Res_T2': (('DEF', 'RES'), 0),
}
MENACE_PARENTS = {
    'Attack_Speed_Menace': (('SPD',), -6),
    'Attack_Defense_Menace': (('DEF',), -6),
    'Attack_Resistance_Menace': (('RES',), -6),
    'Speed_Defense_Menace': (('SPD', 'DEF'), 0),
    'Defense_Resistance_Menace': (('DEF', 'RES'), 0),
}


class RuntimeUnit:
    def __init__(self, nid, team, position=(0, 0), tags=()):
        self.nid = nid
        self.team = team
        self.position = position
        self.tags = set(tags)
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.equipped_weapon = None
        self.hp = 20
        self.mana = 0

    @property
    def all_skills(self):
        return self.skills

    def add_skill(self, skill, source=None, source_type=None, test=False):
        if not test:
            self.skills.append(skill)

    def remove_skill(self, skill, source=None, source_type=None, test=False):
        if skill not in self.skills:
            return False
        if not test:
            self.skills.remove(skill)
        return source, source_type

    def autoequip(self):
        pass

    def get_hp(self):
        return self.hp

    def set_hp(self, hp):
        self.hp = hp

    def get_mana(self):
        return self.mana

    def set_mana(self, mana):
        self.mana = mana


class OwnedSkill:
    def __init__(self, component, uid):
        self.components = [component]
        self.uid = uid

    def __hash__(self):
        return hash(self.uid)


class FieldGame:
    def __init__(self, units):
        self.units = units

    def get_all_units(self):
        return self.units


class NoOpResetUnitVars:
    def __init__(self, unit):
        pass

    def execute(self):
        pass

    def reverse(self):
        pass


class ThreatenFamilyTests(TestCase):
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
        return dict(ThreatenFamilyTests.skills[nid]['components'])

    @staticmethod
    def _runtime_skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _owner_skill(component, uid):
        skill = OwnedSkill(component, uid)
        component.skill = skill
        return skill

    def test_static_contract_migrates_all_parents_and_creates_exact_effects(self):
        family = [nid for nid, category in self.categories.items() if category == FAMILY]
        parents = [nid for nid in family if not nid.endswith('_Effect')]
        effects = [nid for nid in family if nid.endswith('_Effect')]
        self.assertEqual(65, len(family))
        self.assertEqual(30, len(parents))
        self.assertEqual(35, len(effects))
        self.assertEqual('Threaten Strength 1', self.skills['Threaten_Attack_T1']['name'])
        self.assertEqual('At the start of turn, inflicts -4 Defense to Foes within 2 spaces through their next action.',
                         self.skills['Threaten_Def_T2']['desc'])
        self.assertEqual(
            [0, 1, 2],
            [dict(self.skills[nid]['components'])['priority'] for nid in (
                'Threaten_Def_T1', 'Threaten_Def_T2', 'Threaten_Defense_T3')])

        for nid, (stats, damage) in STANDARD_PARENTS.items():
            components = self._components(nid)
            self.assertIn('threaten_foes_at_upkeep', components)
            self.assertNotIn('do_nothing', components)
            self.assertNotIn('upkeep_aoe_skill_gain', components)
            effect = self._components(f'{nid}_Effect')
            self.assertEqual([[stat, -3 if components['threaten_foes_at_upkeep']['rank'] == 0
                               else -4 if components['threaten_foes_at_upkeep']['rank'] == 1 else -5]
                              for stat in stats], effect['threaten_penalty']['stats'])
            self.assertEqual(damage, effect['threaten_penalty']['damage'])
            self.assertIn('hidden', effect)
            self.assertIn('lost_on_next_action', effect)
            self.assertIn('lost_on_end_chapter', effect)

        for nid, (stats, damage) in MENACE_PARENTS.items():
            components = self._components(nid)
            self.assertEqual(4, components['menace_at_upkeep']['range'])
            self.assertNotIn('do_nothing', components)
            foe = self._components(f'{nid}_Foe_Effect')
            user = self._components(f'{nid}_User_Effect')
            self.assertEqual([[stat, -6] for stat in stats], foe['threaten_penalty']['stats'])
            self.assertEqual(damage, foe['threaten_penalty']['damage'])
            self.assertEqual([[stat, 6] for stat in stats], user['stat_change'])
            self.assertEqual(-damage, user['damage'])
            self.assertIn('lost_on_next_action', foe)
            self.assertIn('lost_on_endstep', user)
            self.assertIn('lost_on_end_chapter', foe)
            self.assertIn('lost_on_end_chapter', user)

    def test_threaten_targets_only_valid_foes_in_range_and_deduplicates(self):
        component = self.custom_components.ThreatenFoesAtUpkeep({
            'status': 'Threaten_Speed_T2_Effect', 'range': 2, 'group': 'speed', 'rank': 1,
        })
        source = RuntimeUnit('source', 'player', (2, 2))
        valid = RuntimeUnit('valid', 'enemy', (4, 2))
        same_tile = RuntimeUnit('same_tile', 'enemy', (2, 2))
        far = RuntimeUnit('far', 'enemy', (5, 2))
        ally = RuntimeUnit('ally', 'player', (3, 2))
        off_map = RuntimeUnit('off_map', 'enemy', None)
        dead = RuntimeUnit('dead', 'enemy', (1, 2)); dead.dead = True
        dying = RuntimeUnit('dying', 'enemy', (2, 1)); dying.is_dying = True
        tile = RuntimeUnit('tile', 'enemy', (3, 2), ('Tile',))
        duplicate = RuntimeUnit('duplicate', 'enemy', (2, 3))
        duplicate.skills = [self._runtime_skill('Threaten_Speed_T2_Effect')]
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([
                source, valid, same_tile, far, ally, off_map, dead, dying, tile, duplicate])):
            component.on_upkeep(actions, [], source)
        self.assertEqual(['valid'], [queued.unit.nid for queued in actions])
        component.on_upkeep(actions, [], source)
        self.assertEqual(['valid'], [queued.unit.nid for queued in actions])

    def test_threaten_uses_real_team_relationships_and_higher_rank_only_suppresses(self):
        for team, expected in {
                'player': {'enemy', 'enemy2'},
                'enemy': {'player', 'enemy2', 'other'},
                'enemy2': {'player', 'enemy', 'other'},
        }.items():
            with self.subTest(team=team):
                component = self.custom_components.ThreatenFoesAtUpkeep({
                    'status': 'Threaten_Speed_T1_Effect', 'range': 2, 'group': 'speed', 'rank': 0,
                })
                source = RuntimeUnit('source', team, (0, 0))
                units = [source] + [RuntimeUnit(other, other, (1, 0))
                                    for other in ('player', 'enemy', 'enemy2', 'other') if other != team]
                actions = []
                with patch.object(self.custom_components, 'game', FieldGame(units)):
                    component.on_upkeep(actions, [], source)
                self.assertEqual(expected, {queued.unit.team for queued in actions})

        low = self.custom_components.ThreatenFoesAtUpkeep({
            'status': 'Threaten_Speed_T1_Effect', 'range': 2, 'group': 'speed', 'rank': 0,
        })
        equal = self.custom_components.ThreatenFoesAtUpkeep({
            'status': 'Threaten_Speed_T1_Effect', 'range': 2, 'group': 'speed', 'rank': 0,
        })
        high = self.custom_components.ThreatenFoesAtUpkeep({
            'status': 'Threaten_Speed_T2_Effect', 'range': 2, 'group': 'speed', 'rank': 1,
        })
        source = RuntimeUnit('source', 'player')
        foe = RuntimeUnit('foe', 'enemy', (1, 0))
        source.skills = [self._owner_skill(low, 3), self._owner_skill(equal, 2), self._owner_skill(high, 1)]
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([source, foe])):
            low.on_upkeep(actions, [], source)
            equal.on_upkeep(actions, [], source)
            high.on_upkeep(actions, [], source)
        self.assertEqual(['Threaten_Speed_T2_Effect'], [queued.skill_obj.nid for queued in actions])

    def test_menace_needs_foe_then_debuffs_foes_and_buffs_user_once(self):
        component = self.custom_components.MenaceAtUpkeep({
            'foe_status': 'Attack_Speed_Menace_Foe_Effect',
            'user_status': 'Attack_Speed_Menace_User_Effect', 'range': 4,
        })
        source = RuntimeUnit('source', 'player')
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([source])):
            component.on_upkeep(actions, [], source)
        self.assertEqual([], actions)

        close = RuntimeUnit('close', 'enemy', (4, 0))
        far = RuntimeUnit('far', 'enemy', (5, 0))
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([source, close, far])):
            component.on_upkeep(actions, [], source)
        self.assertEqual({('close', 'Attack_Speed_Menace_Foe_Effect'),
                          ('source', 'Attack_Speed_Menace_User_Effect')},
                         {(queued.unit.nid, queued.skill_obj.nid) for queued in actions})
        component.on_upkeep(actions, [], source)
        self.assertEqual(2, len(actions))

    def test_penalty_aggregates_each_stat_and_damage_by_most_negative_then_lowest_uid(self):
        first = self.custom_components.ThreatenPenalty({
            'stats': [['STR', -3], ['SPD', -6]], 'damage': -2,
        })
        second = self.custom_components.ThreatenPenalty({
            'stats': [['STR', -5], ['DEF', -4]], 'damage': -4,
        })
        tied = self.custom_components.ThreatenPenalty({
            'stats': [['STR', -5]], 'damage': -4,
        })
        unit = RuntimeUnit('unit', 'player')
        unit.skills = [self._owner_skill(first, 30), self._owner_skill(second, 20), self._owner_skill(tied, 10)]
        self.assertEqual(-5, skill_system.stat_change(unit, 'STR'))
        self.assertEqual(-6, skill_system.stat_change(unit, 'SPD'))
        self.assertEqual(-4, skill_system.stat_change(unit, 'DEF'))
        self.assertEqual(-4, skill_system.modify_damage(unit, None))
        self.assertEqual({'DEF': -4}, second.stat_change(unit))
        self.assertEqual({'STR': -5}, tied.stat_change(unit))
        self.assertEqual(-4, tied.modify_damage(unit, None))

    def test_effect_lifetimes_and_project_restore_register_components(self):
        foe = RuntimeUnit('foe', 'enemy')
        foe.skills = [self._runtime_skill('Threaten_Speed_T1_Effect')]
        user = RuntimeUnit('user', 'player')
        user.skills = [self._runtime_skill('Attack_Speed_Menace_User_Effect')]
        queued = []
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            skill_system.on_wait(foe, False)
        self.assertEqual([], foe.skills)
        skill_system.on_endstep(queued, [], user)
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars):
            for queued_action in queued:
                queued_action.reset_action = NoOpResetUnitVars(user)
                queued_action.do()
        self.assertEqual([], user.skills)
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        for nid in ('threaten_foes_at_upkeep', 'menace_at_upkeep', 'threaten_penalty'):
            self.assertIsNotNone(skill_component_access.get_component(nid))
        self.assertIsNotNone(DB.skills.get('Attack_Speed_Menace_User_Effect'))


if __name__ == '__main__':
    import unittest
    unittest.main()
