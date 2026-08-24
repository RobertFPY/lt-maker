import importlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, skill_component_access, skill_system
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Rouse Family'
GROUPS = {
    'Atk_Spd': (('SPD',), True),
    'Atk_Def': (('DEF',), True),
    'Atk_Res': (('RES',), True),
    'Spd_Def': (('SPD', 'DEF'), False),
    'Spd_Res': (('SPD', 'RES'), False),
    'Def_Res': (('DEF', 'RES'), False),
}
VALUES = {1: 2, 2: 4, 3: 6}


class RuntimeUnit:
    def __init__(self, nid, team='player', position=(0, 0), tags=()):
        self.nid = nid
        self.team = team
        self.position = position
        self.tags = set(tags)
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.hp = 20
        self.mana = 0
        self.equipped_weapon = None

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
        self.nid = component.nid
        component.skill = self

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


class RouseFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(nid):
        return dict(RouseFamilyTests.skills[nid]['components'])

    @staticmethod
    def _owner(component, uid):
        return OwnedSkill(component, uid)

    def test_static_contract_migrates_exactly_eighteen_parents_and_effects(self):
        members = [nid for nid, category in self.categories.items() if category == FAMILY]
        parents = [nid for nid in members if not nid.endswith('_Effect')]
        effects = [nid for nid in members if nid.endswith('_Effect')]
        self.assertEqual(36, len(members))
        self.assertEqual(18, len(parents))
        self.assertEqual(18, len(effects))
        for group, (stats, damage) in GROUPS.items():
            for tier, amount in VALUES.items():
                parent_nid = f'Rouse_{group}_T{tier}'
                effect_nid = f'{parent_nid}_Effect'
                parent = self._components(parent_nid)
                effect = self._components(effect_nid)
                self.assertEqual({'status': effect_nid, 'group': group, 'rank': tier - 1},
                                 parent['rouse_self_at_upkeep'])
                self.assertNotIn('do_nothing', parent)
                self.assertEqual([[stat, amount] for stat in stats], effect['rouse_bonus']['stats'])
                self.assertEqual(amount if damage else 0, effect['rouse_bonus']['damage'])
                self.assertIn('hidden', effect)
                self.assertIn('lost_on_endstep', effect)
                self.assertIn('lost_on_end_chapter', effect)
                self.assertNotIn('damage dealts', self.skills[parent_nid]['desc'])
                self.assertIn('damage dealt', self.skills[parent_nid]['desc']) if damage else None

    def test_upkeep_needs_an_isolated_living_user_and_queues_once(self):
        component = self.custom_components.RouseSelfAtUpkeep({
            'status': 'Rouse_Atk_Spd_T2_Effect', 'group': 'Atk_Spd', 'rank': 1,
        })
        user = RuntimeUnit('user')
        adjacent = RuntimeUnit('adjacent', position=(1, 0))
        far = RuntimeUnit('far', position=(2, 0))
        enemy = RuntimeUnit('enemy', team='enemy', position=(0, 1))
        off_map = RuntimeUnit('off_map', position=None)
        dead = RuntimeUnit('dead', position=(0, -1))
        dead.dead = True
        dying = RuntimeUnit('dying', position=(-1, 0))
        dying.is_dying = True
        tile = RuntimeUnit('tile', position=(0, 2), tags=('Tile',))

        def queued_for(units, source=user):
            queued = []
            with patch.object(self.custom_components, 'game', FieldGame(units)), \
                    patch.object(self.custom_components.skill_system, 'check_ally',
                                 side_effect=lambda left, right: left.team == right.team):
                component.on_upkeep(queued, [], source)
            return queued

        self.assertEqual([], queued_for([user, adjacent]))
        self.assertEqual(['Rouse_Atk_Spd_T2_Effect'],
                         [entry.skill_obj.nid for entry in queued_for(
                             [user, far, enemy, off_map, dead, dying, tile])])
        user.skills = [SkillObject.from_prefab(DB.skills.get('Rouse_Atk_Spd_T2_Effect'))]
        self.assertEqual([], queued_for([user, far]))
        user.skills = []
        queued = queued_for([user, far])
        with patch.object(self.custom_components, 'game', FieldGame([user, far])), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=False):
            component.on_upkeep(queued, [], user)
        self.assertEqual(1, len(queued))
        user.dead = True
        self.assertEqual([], queued_for([user, far]))
        user.dead = False
        user.is_dying = True
        self.assertEqual([], queued_for([user, far]))
        user.is_dying = False
        user.tags.add('Tile')
        self.assertEqual([], queued_for([user, far]))

    def test_only_highest_active_rank_in_a_group_queues(self):
        low = self.custom_components.RouseSelfAtUpkeep({
            'status': 'Rouse_Atk_Spd_T1_Effect', 'group': 'Atk_Spd', 'rank': 0,
        })
        equal = self.custom_components.RouseSelfAtUpkeep({
            'status': 'Rouse_Atk_Spd_T1_Effect', 'group': 'Atk_Spd', 'rank': 0,
        })
        high = self.custom_components.RouseSelfAtUpkeep({
            'status': 'Rouse_Atk_Spd_T3_Effect', 'group': 'Atk_Spd', 'rank': 2,
        })
        user = RuntimeUnit('user')
        user.skills = [self._owner(low, 30), self._owner(equal, 20), self._owner(high, 10)]
        queued = []
        with patch.object(self.custom_components, 'game', FieldGame([user])):
            low.on_upkeep(queued, [], user)
            equal.on_upkeep(queued, [], user)
            high.on_upkeep(queued, [], user)
        self.assertEqual(['Rouse_Atk_Spd_T3_Effect'], [entry.skill_obj.nid for entry in queued])

    def test_bonus_selects_only_best_positive_rouse_per_stat_and_damage_then_stacks_other_effects(self):
        first = self.custom_components.RouseBonus({
            'stats': [['SPD', 2], ['DEF', 4]], 'damage': 2,
        })
        second = self.custom_components.RouseBonus({
            'stats': [['SPD', 6], ['RES', 4]], 'damage': 6,
        })
        tied = self.custom_components.RouseBonus({
            'stats': [['SPD', 6], ['DEF', 4]], 'damage': 6,
        })

        class OtherBonus(SkillComponent):
            nid = 'ordinary_bonus'

            def stat_change(self, unit):
                return {'SPD': 3}

            def modify_damage(self, unit, item):
                return 3

        unit = RuntimeUnit('user')
        unit.skills = [self._owner(first, 30), self._owner(second, 20), self._owner(tied, 10),
                       self._owner(OtherBonus(), 1)]
        self.assertEqual(9, skill_system.stat_change(unit, 'SPD'))
        self.assertEqual(4, skill_system.stat_change(unit, 'DEF'))
        self.assertEqual(4, skill_system.stat_change(unit, 'RES'))
        self.assertEqual(9, skill_system.modify_damage(unit, None))
        self.assertEqual({'SPD': 6, 'DEF': 4}, tied.stat_change(unit))
        self.assertEqual(6, tied.modify_damage(unit, None))

    def test_effects_expire_and_components_restore_after_resources_then_database_load(self):
        unit = RuntimeUnit('user')
        unit.skills = [SkillObject.from_prefab(DB.skills.get(nid)) for nid in (
            'Rouse_Atk_Spd_T1_Effect', 'Rouse_Atk_Spd_T2_Effect', 'Rouse_Atk_Spd_T3_Effect',
        )]
        self.assertEqual(6, skill_system.stat_change(unit, 'SPD'))
        self.assertEqual(6, skill_system.modify_damage(unit, None))
        queued = []
        skill_system.on_endstep(queued, [], unit)
        self.assertEqual(3, len(queued))
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars):
            for entry in queued:
                entry.reset_action = NoOpResetUnitVars(unit)
                entry.do()
        self.assertEqual([], unit.skills)
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        self.assertIsNotNone(skill_component_access.get_component('rouse_self_at_upkeep'))
        self.assertIsNotNone(skill_component_access.get_component('rouse_bonus'))
        self.assertIsNotNone(DB.skills.get('Rouse_Def_Res_T3_Effect'))


if __name__ == '__main__':
    import unittest
    unittest.main()
