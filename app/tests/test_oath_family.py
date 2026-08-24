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
FAMILY = 'Skill System Slot C/Oath Family'
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


class OathFamilyTests(TestCase):
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
        return dict(OathFamilyTests.skills[nid]['components'])

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
                parent_nid = f'{group}_Oath_T{tier}'
                effect_nid = f'{parent_nid}_Effect'
                parent = self._components(parent_nid)
                effect = self._components(effect_nid)
                self.assertEqual({'status': effect_nid, 'group': f'oath:{group.lower()}', 'rank': tier,
                                  'range': tier}, parent['oath_self_at_upkeep'])
                self.assertNotIn('do_nothing', parent)
                self.assertEqual([[stat, amount] for stat in stats], effect['oath_bonus']['stats'])
                self.assertEqual(amount if damage else 0, effect['oath_bonus']['damage'])
                self.assertTrue({'hidden', 'lost_on_endstep', 'lost_on_end_chapter'} <= effect.keys())
                self.assertNotIn('damage dealts', self.skills[parent_nid]['desc'])

    def test_upkeep_needs_valid_ally_within_configured_range_and_queues_once(self):
        user = RuntimeUnit('user')
        ally = RuntimeUnit('ally', position=(0, 0))
        component = self.custom_components.OathSelfAtUpkeep({
            'status': 'Atk_Spd_Oath_T2_Effect', 'group': 'oath:atk_spd', 'rank': 2, 'range': 2,
        })

        def queued_for(position, units=(user, ally)):
            ally.position = position
            queued = []
            with patch.object(self.custom_components, 'game', FieldGame(list(units))), \
                    patch.object(self.custom_components.skill_system, 'check_ally',
                                 side_effect=lambda left, right: left.team == right.team):
                component.on_upkeep(queued, [], user)
            return queued

        self.assertEqual(['Atk_Spd_Oath_T2_Effect'],
                         [entry.skill_obj.nid for entry in queued_for((0, 1))])
        self.assertEqual(['Atk_Spd_Oath_T2_Effect'],
                         [entry.skill_obj.nid for entry in queued_for((0, 2))])
        self.assertEqual([], queued_for((0, 3)))
        invalid = RuntimeUnit('tile', position=(1, 0), tags=('Tile',))
        self.assertEqual([], queued_for((0, 4), (user, invalid)))
        for invalid_unit in (
                RuntimeUnit('off_map', position=None),
                RuntimeUnit('dead', position=(1, 0)),
                RuntimeUnit('dying', position=(1, 0)),
                RuntimeUnit('zero_hp', position=(1, 0))):
            if invalid_unit.nid == 'dead':
                invalid_unit.dead = True
            elif invalid_unit.nid == 'dying':
                invalid_unit.is_dying = True
            elif invalid_unit.nid == 'zero_hp':
                invalid_unit.hp = 0
            self.assertEqual([], queued_for((0, 4), (user, invalid_unit)))
        enemy = RuntimeUnit('enemy', team='enemy', position=(1, 0))
        self.assertEqual([], queued_for((0, 4), (user, enemy)))
        queued = queued_for((0, 1))
        with patch.object(self.custom_components, 'game', FieldGame([user, ally])), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
            component.on_upkeep(queued, [], user)
        self.assertEqual(1, len(queued))
        user.skills = [SkillObject.from_prefab(DB.skills.get('Atk_Spd_Oath_T2_Effect'))]
        self.assertEqual([], queued_for((0, 1)))

    def test_runtime_ranges_one_two_and_three_use_manhattan_distance(self):
        user = RuntimeUnit('user')
        ally = RuntimeUnit('ally')
        for tier, distance in ((1, 1), (2, 2), (3, 3)):
            component = self.custom_components.OathSelfAtUpkeep({
                'status': f'Atk_Spd_Oath_T{tier}_Effect', 'group': 'oath:atk_spd',
                'rank': tier, 'range': distance,
            })
            with patch.object(self.custom_components, 'game', FieldGame([user, ally])), \
                    patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
                ally.position = (distance, 0)
                inside = []
                component.on_upkeep(inside, [], user)
                ally.position = (distance + 1, 0)
                outside = []
                component.on_upkeep(outside, [], user)
            self.assertEqual(1, len(inside))
            self.assertEqual([], outside)

    def test_only_highest_active_rank_in_group_queues_when_higher_condition_is_false(self):
        low = self.custom_components.OathSelfAtUpkeep({
            'status': 'Atk_Spd_Oath_T1_Effect', 'group': 'oath:atk_spd', 'rank': 1, 'range': 1,
        })
        high = self.custom_components.OathSelfAtUpkeep({
            'status': 'Atk_Spd_Oath_T3_Effect', 'group': 'oath:atk_spd', 'rank': 3, 'range': 3,
        })
        user = RuntimeUnit('user')
        ally = RuntimeUnit('ally', position=(1, 0))
        user.skills = [self._owner(low, 30), self._owner(high, 10)]
        queued = []
        with patch.object(self.custom_components, 'game', FieldGame([user, ally])), \
                patch.object(self.custom_components.skill_system, 'condition',
                             side_effect=lambda skill, unit: skill is not high.skill):
            low.on_upkeep(queued, [], user)
        self.assertEqual(['Atk_Spd_Oath_T1_Effect'], [entry.skill_obj.nid for entry in queued])

    def test_bonus_maxes_only_oath_and_stacks_rouse_and_other_effects(self):
        oath_low = self.custom_components.OathBonus({'stats': [['SPD', 2], ['DEF', 4]], 'damage': 2})
        oath_high = self.custom_components.OathBonus({'stats': [['SPD', 6], ['RES', 4]], 'damage': 6})
        oath_tied = self.custom_components.OathBonus({'stats': [['SPD', 6], ['DEF', 4]], 'damage': 6})
        rouse = self.custom_components.RouseBonus({'stats': [['SPD', 6]], 'damage': 6})

        class OtherBonus(SkillComponent):
            nid = 'ordinary_bonus'

            def stat_change(self, unit):
                return {'SPD': 3}

            def modify_damage(self, unit, item):
                return 3

        unit = RuntimeUnit('user')
        unit.skills = [self._owner(oath_low, 30), self._owner(oath_high, 20),
                       self._owner(oath_tied, 10), self._owner(rouse, 5),
                       self._owner(OtherBonus(), 1)]
        self.assertEqual(15, skill_system.stat_change(unit, 'SPD'))
        self.assertEqual(4, skill_system.stat_change(unit, 'DEF'))
        self.assertEqual(4, skill_system.stat_change(unit, 'RES'))
        self.assertEqual(15, skill_system.modify_damage(unit, None))
        self.assertEqual({'SPD': 6, 'DEF': 4}, oath_tied.stat_change(unit))

    def test_effects_expire_and_components_restore_after_resources_then_database_load(self):
        unit = RuntimeUnit('user')
        unit.skills = [SkillObject.from_prefab(DB.skills.get(nid)) for nid in (
            'Atk_Spd_Oath_T1_Effect', 'Atk_Spd_Oath_T2_Effect', 'Atk_Spd_Oath_T3_Effect',
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
        self.assertIsNotNone(skill_component_access.get_component('oath_self_at_upkeep'))
        self.assertIsNotNone(skill_component_access.get_component('oath_bonus'))
        self.assertIsNotNone(DB.skills.get('Def_Res_Oath_T3_Effect'))

    def test_rouse_regression_components_remain_available(self):
        self.assertIsNotNone(skill_component_access.get_component('rouse_self_at_upkeep'))
        self.assertIsNotNone(skill_component_access.get_component('rouse_bonus'))


if __name__ == '__main__':
    import unittest
    unittest.main()
