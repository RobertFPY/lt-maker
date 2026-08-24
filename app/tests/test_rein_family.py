import importlib
import json
from collections import defaultdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import aura_funcs, item_funcs, skill_system
from app.engine.objects.unit import UnitObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Rein Family'
VALUES = {1: 3, 2: 4, 3: 5}
GROUPS = {
    'Atk_Spd': (('SPD',), True),
    'Atk_Def': (('DEF',), True),
    'Atk_Res': (('RES',), True),
    'Spd_Def': (('SPD', 'DEF'), False),
    'Spd_Res': (('SPD', 'RES'), False),
    'Def_Res': (('DEF', 'RES'), False),
}
PARENTS = tuple(f'{group}_Rein_T{tier}' for group in GROUPS for tier in VALUES)


class AuraBoard:
    def __init__(self, units):
        self.units = {unit.position: unit for unit in units}
        self.aura_grid = defaultdict(set)
        self.known_auras = defaultdict(set)
        self.bounds = (0, 0, 8, 8)

    def check_bounds(self, position):
        return all(0 <= position[index] <= 8 for index in (0, 1))

    def get_unit(self, position):
        return self.units.get(position)

    def reset_aura(self, child_skill):
        self.known_auras[child_skill.uid].clear()

    def add_aura(self, position, child_skill, target):
        self.aura_grid[position].add((child_skill.uid, target))
        self.known_auras[child_skill.uid].add(position)

    def remove_aura(self, position, child_skill):
        self.aura_grid[position] = {aura for aura in self.aura_grid[position]
                                    if aura[0] != child_skill.uid}
        self.known_auras[child_skill.uid].discard(position)

    def get_aura_positions(self, child_skill):
        return self.known_auras[child_skill.uid]


class AuraTargetSystem:
    @staticmethod
    def get_shell(positions, ranges, bounds):
        result = set()
        for x, y in positions:
            for distance in ranges:
                for dx in range(-distance, distance + 1):
                    dy = distance - abs(dx)
                    result.add((x + dx, y + dy))
                    result.add((x + dx, y - dy))
        return {position for position in result if bounds[0] <= position[0] <= bounds[2]
                and bounds[1] <= position[1] <= bounds[3]}


class AuraGame:
    def __init__(self, board, units, skills):
        self.board = board
        self.target_system = AuraTargetSystem()
        self._units = {unit.nid: unit for unit in units}
        self._skills = {skill.uid: skill for skill in skills}

    def get_skill(self, uid):
        return self._skills.get(uid)

    def get_unit(self, nid):
        return self._units.get(nid)


class ReinFamilyTests(TestCase):
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
        return dict(ReinFamilyTests.skills[nid]['components'])

    @staticmethod
    def _unit(nid, team):
        return UnitObject(nid, team=team, klass=DB.classes.get('Myrmidon').nid,
                          position=(0, 0))

    @staticmethod
    def _parent(owner, nid):
        return item_funcs.create_skill(owner, nid)

    def _apply(self, owner, target, nid):
        parent = self._parent(owner, nid)
        aura_funcs.apply_aura(owner, target, parent.subskill, 'enemy', test=True)
        return parent

    def test_static_contract_migrates_all_rein_parents_and_effects(self):
        effects = tuple(f'{nid}_Effect' for nid in PARENTS)
        members = [nid for nid, category in self.categories.items() if category == FAMILY]
        self.assertEqual(18, len(PARENTS))
        self.assertEqual(36, len(members))
        self.assertEqual(set(PARENTS) | set(effects), set(members))

        for group, (stats, has_damage) in GROUPS.items():
            for tier, amount in VALUES.items():
                parent_nid = f'{group}_Rein_T{tier}'
                effect_nid = f'{parent_nid}_Effect'
                parent = self._components(parent_nid)
                effect = self._components(effect_nid)
                self.assertEqual(effect_nid, parent['aura'])
                self.assertEqual(2, parent['aura_range'])
                self.assertEqual('enemy', parent['aura_target'])
                self.assertNotIn('do_nothing', parent)
                self.assertTrue({'hidden', 'stack', 'rein_penalty'} <= effect.keys())
                self.assertEqual(999, effect['stack'])
                self.assertEqual({
                    'group': f'rein:{group.lower()}',
                    'rank': tier,
                    'stats': [[stat, -amount] for stat in stats],
                    'damage': -amount if has_damage else 0,
                }, effect['rein_penalty'])
                self.assertNotIn('damage dealts', self.skills[parent_nid]['desc'])

    def test_same_owner_uses_highest_rein_rank_but_different_owners_stack(self):
        target = self._unit('target', 'enemy')
        owner_a = self._unit('owner_a', 'player')
        owner_b = self._unit('owner_b', 'player')
        self._apply(owner_a, target, 'Atk_Spd_Rein_T1')
        self._apply(owner_a, target, 'Atk_Spd_Rein_T3')
        self._apply(owner_a, target, 'Atk_Spd_Rein_T3')
        self.assertEqual(-5, skill_system.stat_change(target, 'SPD'))
        self.assertEqual(-5, skill_system.modify_damage(target, None))

        self._apply(owner_b, target, 'Atk_Spd_Rein_T2')
        self.assertEqual(-9, skill_system.stat_change(target, 'SPD'))
        self.assertEqual(-9, skill_system.modify_damage(target, None))

    def test_groups_stack_independently_and_aura_does_not_affect_allies(self):
        target = self._unit('target', 'enemy')
        ally = self._unit('ally', 'player')
        owner = self._unit('owner', 'player')
        atk_spd = self._apply(owner, target, 'Atk_Spd_Rein_T3')
        self._apply(owner, target, 'Atk_Def_Rein_T2')
        aura_funcs.apply_aura(owner, ally, atk_spd.subskill, 'enemy', test=True)

        self.assertEqual(-5, skill_system.stat_change(target, 'SPD'))
        self.assertEqual(-4, skill_system.stat_change(target, 'DEF'))
        self.assertEqual(-9, skill_system.modify_damage(target, None))
        self.assertEqual(0, skill_system.stat_change(ally, 'SPD'))
        self.assertEqual(0, skill_system.modify_damage(ally, None))

    def test_aura_propagates_only_to_foes_in_two_spaces_and_releases_cleanly(self):
        owner = self._unit('owner', 'player')
        owner.position = (2, 2)
        target = self._unit('target', 'enemy')
        target.position = (4, 2)
        far = self._unit('far', 'enemy')
        far.position = (5, 2)
        ally = self._unit('ally', 'player')
        ally.position = (3, 2)
        parent = self._parent(owner, 'Atk_Spd_Rein_T1')
        board = AuraBoard((owner, target, far, ally))
        field = AuraGame(board, (owner, target, far, ally), (parent, parent.subskill))

        original_apply = aura_funcs.apply_aura
        with patch.object(aura_funcs, 'apply_aura', side_effect=lambda source, unit, child, target_type:
                          original_apply(source, unit, child, target_type, test=True)), \
                patch.object(aura_funcs, 'remove_aura', side_effect=lambda unit, child:
                             unit.remove_skill(child, source=child.parent_skill.uid,
                                               source_type=aura_funcs.SourceType.AURA)):
            aura_funcs.propagate_aura(owner, parent, field)
            self.assertIn(parent.subskill, target.all_skills)
            self.assertNotIn(parent.subskill, far.all_skills)
            self.assertNotIn(parent.subskill, ally.all_skills)
            aura_funcs.release_aura(owner, parent, field)

        self.assertNotIn(parent.subskill, target.all_skills)

    def test_rein_penalty_restores_from_resources_before_database(self):
        self.assertIsNotNone(getattr(self.custom_components, 'ReinPenalty', None))
        self.assertIsNotNone(DB.skills.get('Def_Res_Rein_T3_Effect'))


if __name__ == '__main__':
    import unittest
    unittest.main()
