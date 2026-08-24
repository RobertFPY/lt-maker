import json
from collections import defaultdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import aura_funcs, item_funcs, skill_system
from app.engine.objects.skill import SkillObject
from app.engine.objects.unit import UnitObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Spur Family'
TAGS = {
    'Armor': 'Armor',
    'Cavalry': 'Horse',
    'Fliers': 'Flying',
    'Dragons': 'Dragon',
}
PARENTS = (
    'Spur_Strength_T1', 'Spur_Strength_T2', 'Spur_Strength_T3',
    'Spur_Magic_T1', 'Spur_Magic_T2', 'Spur_Magic_T3',
    'Spur_Speed_T1', 'Spur_Speed_T2', 'Spur_Speed_T3',
    'Spur_Defense_T1', 'Spur_Defense_T2', 'Spur_Defense_T3',
    'Spur_Resistance_T1', 'Spur_Resistance_T2', 'Spur_Resistance_T3',
    'Spur_Atk_Spd_T1', 'Spur_Atk_Spd_T2',
    'Spur_Atk_Def_T1', 'Spur_Atk_Def_T2',
    'Spur_Atk_Res_T1', 'Spur_Atk_Res_T2',
    'Spur_Spd_Def_T1', 'Spur_Spd_Def_T2',
    'Spur_Spd_Res_T1', 'Spur_Spd_Res_T2',
    'Spur_Def_Res_T1', 'Spur_Def_Res_T2',
    'Goad_Armor', 'Ward_Armor', 'Goad_Cavalry', 'Ward_Cavalry',
    'Goad_Fliers', 'Ward_Fliers', 'Goad_Dragons', 'Ward_Dragons',
    'Drive_Atk_T1', 'Drive_Atk_T2', 'Drive_Spd_T1', 'Drive_Spd_T2',
    'Drive_Def_T1', 'Drive_Def_T2', 'Drive_Res_T1', 'Drive_Res_T2',
)


class AuraBoard:
    def __init__(self, units):
        self.units = {unit.position: unit for unit in units}
        self.aura_grid = defaultdict(set)
        self.known_auras = defaultdict(set)
        self.bounds = (0, 0, 8, 8)

    def check_bounds(self, position):
        return all((0 <= position[idx] <= 8 for idx in (0, 1)))

    def get_unit(self, position):
        return self.units.get(position)

    def reset_aura(self, child_skill):
        self.known_auras[child_skill.uid].clear()

    def add_aura(self, position, child_skill, target):
        self.aura_grid[position].add((child_skill.uid, target))
        self.known_auras[child_skill.uid].add(position)

    def remove_aura(self, position, child_skill):
        self.aura_grid[position] = {
            aura for aura in self.aura_grid[position] if aura[0] != child_skill.uid
        }
        self.known_auras[child_skill.uid].discard(position)

    def get_auras(self, position):
        return self.aura_grid[position]

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


class SpurFamilyTests(TestCase):
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

    @staticmethod
    def _components(nid):
        return dict(SpurFamilyTests.skills[nid]['components'])

    @staticmethod
    def _unit(nid, team, position, tags=()):
        return UnitObject(nid, team=team, klass=DB.classes.get('Myrmidon').nid,
                          position=position, _tags=set(tags))

    @staticmethod
    def _parent(owner, nid):
        return item_funcs.create_skill(owner, nid)

    def test_static_contract_has_43_parents_43_hidden_effects_and_exact_values(self):
        effects = tuple(f'{nid}_Effect' for nid in PARENTS)
        family_records = [nid for nid, category in self.categories.items() if category == FAMILY]
        self.assertEqual(43, len(PARENTS))
        self.assertEqual(86, len(family_records))
        self.assertEqual(set(PARENTS) | set(effects), set(family_records))

        parents = [self._components(nid) for nid in PARENTS]
        children = [self._components(nid) for nid in effects]
        self.assertEqual(43, sum(parent.get('aura') == f'{nid}_Effect'
                                 for nid, parent in zip(PARENTS, parents)))
        self.assertEqual(43, sum(parent.get('aura_target') == 'ally' for parent in parents))
        self.assertEqual(27, sum(parent.get('aura_range') == 1 for parent in parents))
        self.assertEqual(16, sum(parent.get('aura_range') == 2 for parent in parents))
        self.assertTrue(all('do_nothing' not in parent for parent in parents))
        self.assertTrue(all('hidden' in child and child.get('stack') == 999
                            for child in children))
        self.assertEqual(41, sum('stat_change' in child for child in children))
        self.assertEqual(12, sum('damage' in child for child in children))
        self.assertEqual(8, sum('condition' in child for child in children))
        self.assertEqual(8, sum(parent.get('priority') == 2
                                for nid, parent in zip(PARENTS, parents)
                                if nid.startswith(('Goad_', 'Ward_'))))

        for stat, family in (('STR', 'Strength'), ('MAG', 'Magic'), ('SPD', 'Speed'),
                             ('DEF', 'Defense'), ('RES', 'Resistance')):
            for tier, value in ((1, 3), (2, 4), (3, 5)):
                self.assertEqual([[stat, value]],
                                 self._components(f'Spur_{family}_T{tier}_Effect')['stat_change'])
        for suffix, stats in {
                'Atk_Spd': ('SPD',), 'Atk_Def': ('DEF',), 'Atk_Res': ('RES',),
                'Spd_Def': ('SPD', 'DEF'), 'Spd_Res': ('SPD', 'RES'),
                'Def_Res': ('DEF', 'RES'),
        }.items():
            for tier, value in ((1, 3), (2, 4)):
                effect = self._components(f'Spur_{suffix}_T{tier}_Effect')
                if suffix.startswith('Atk_'):
                    self.assertEqual(value, effect['damage'])
                self.assertEqual([[stat, value] for stat in stats], effect['stat_change'])
        for group, tag in TAGS.items():
            goad = self._components(f'Goad_{group}_Effect')
            ward = self._components(f'Ward_{group}_Effect')
            self.assertEqual(f"'{tag}' in unit.tags", goad['condition'])
            self.assertEqual(f"'{tag}' in unit.tags", ward['condition'])
            self.assertEqual(4, goad['damage'])
            self.assertEqual([['SPD', 4]], goad['stat_change'])
            self.assertEqual([['DEF', 4], ['RES', 4]], ward['stat_change'])
        for tier, value in ((1, 3), (2, 4)):
            self.assertEqual(value, self._components(f'Drive_Atk_T{tier}_Effect')['damage'])
            self.assertEqual([['SPD', value]], self._components(f'Drive_Spd_T{tier}_Effect')['stat_change'])
            self.assertEqual([['DEF', value]], self._components(f'Drive_Def_T{tier}_Effect')['stat_change'])
            self.assertEqual([['RES', value]], self._components(f'Drive_Res_T{tier}_Effect')['stat_change'])
            self.assertIn('Resistance', self.skills[f'Drive_Res_T{tier}']['desc'])

    def test_aura_excludes_source_and_enemies_and_respects_range(self):
        owner = self._unit('owner', 'player', (2, 2))
        ally = self._unit('ally', 'player', (3, 2))
        enemy = self._unit('enemy', 'enemy', (1, 2))
        distant = self._unit('distant', 'player', (4, 2))
        parent = self._parent(owner, 'Spur_Strength_T1')
        board = AuraBoard([owner, ally, enemy, distant])
        field = AuraGame(board, [owner, ally, enemy, distant], [parent, parent.subskill])

        original_apply = aura_funcs.apply_aura
        with patch.object(aura_funcs, 'apply_aura',
                          side_effect=lambda source, unit, child, target:
                          original_apply(source, unit, child, target, test=True)):
            aura_funcs.propagate_aura(owner, parent, field)

        self.assertNotIn(parent.subskill, owner.all_skills)
        self.assertIn(parent.subskill, ally.all_skills)
        self.assertNotIn(parent.subskill, enemy.all_skills)
        self.assertNotIn(parent.subskill, distant.all_skills)
        self.assertEqual(3, skill_system.stat_change(ally, 'STR'))

    def test_tag_filters_apply_only_to_matching_units_and_real_values_stack(self):
        for group, tag in TAGS.items():
            with self.subTest(group=group):
                owner = self._unit(f'owner_{group}', 'player', (2, 2))
                valid = self._unit(f'valid_{group}', 'player', (3, 2), (tag,))
                invalid = self._unit(f'invalid_{group}', 'player', (3, 3))
                goad = self._parent(owner, f'Goad_{group}')
                ward = self._parent(owner, f'Ward_{group}')
                for target in (valid, invalid):
                    aura_funcs.apply_aura(owner, target, goad.subskill, 'ally', test=True)
                    aura_funcs.apply_aura(owner, target, ward.subskill, 'ally', test=True)
                self.assertEqual(4, skill_system.modify_damage(valid, None))
                self.assertEqual(4, skill_system.stat_change(valid, 'SPD'))
                self.assertEqual(4, skill_system.stat_change(valid, 'DEF'))
                self.assertEqual(4, skill_system.stat_change(valid, 'RES'))
                self.assertEqual(0, skill_system.modify_damage(invalid, None))
                self.assertEqual(0, skill_system.stat_change(invalid, 'SPD'))
                self.assertEqual(0, skill_system.stat_change(invalid, 'DEF'))
                self.assertEqual(0, skill_system.stat_change(invalid, 'RES'))

        owner_a = self._unit('owner_a', 'player', (2, 2))
        owner_b = self._unit('owner_b', 'player', (2, 3))
        ally = self._unit('ally', 'player', (3, 2))
        first = self._parent(owner_a, 'Drive_Atk_T2')
        second = self._parent(owner_b, 'Drive_Atk_T2')
        aura_funcs.apply_aura(owner_a, ally, first.subskill, 'ally', test=True)
        aura_funcs.apply_aura(owner_b, ally, second.subskill, 'ally', test=True)
        self.assertEqual(2, sum(skill.nid == 'Drive_Atk_T2_Effect' for skill in ally.all_skills))
        self.assertEqual(8, skill_system.modify_damage(ally, None))
        aura_funcs.remove_aura(ally, first.subskill, test=True)
        self.assertEqual([second.subskill], ally.all_skills)
        self.assertEqual(4, skill_system.modify_damage(ally, None))

    def test_move_release_repopulate_and_slot_priority_keep_aura_state_clean(self):
        owner = self._unit('owner', 'player', (2, 2))
        old_ally = self._unit('old_ally', 'player', (3, 2))
        new_ally = self._unit('new_ally', 'player', (5, 2))
        parent = self._parent(owner, 'Drive_Res_T2')
        board = AuraBoard([owner, old_ally, new_ally])
        field = AuraGame(board, [owner, old_ally, new_ally], [parent, parent.subskill])
        original_apply = aura_funcs.apply_aura
        original_remove = aura_funcs.remove_aura
        with patch.object(aura_funcs, 'apply_aura',
                          side_effect=lambda source, unit, child, target, test=False:
                          original_apply(source, unit, child, target, test=True)), \
                patch.object(aura_funcs, 'remove_aura',
                             side_effect=lambda unit, child: original_remove(unit, child, test=True)):
            aura_funcs.propagate_aura(owner, parent, field)
            self.assertIn(parent.subskill, old_ally.all_skills)
            aura_funcs.release_aura(owner, parent, field)
            self.assertNotIn(parent.subskill, old_ally.all_skills)
            owner.position = (4, 2)
            board.units = {owner.position: owner, old_ally.position: old_ally,
                           new_ally.position: new_ally}
            aura_funcs.repopulate_aura(owner, parent, field)
            aura_funcs.pull_auras(new_ally, field, test=True)

        self.assertNotIn(parent.subskill, old_ally.all_skills)
        self.assertIn(parent.subskill, new_ally.all_skills)
        self.assertEqual(4, skill_system.stat_change(new_ally, 'RES'))

        spur = SkillObject.from_prefab(DB.skills.get('Spur_Strength_T2'))
        goad = SkillObject.from_prefab(DB.skills.get('Goad_Armor'))
        selected = max((spur, goad), key=lambda skill: skill.priority.int())
        self.assertIs(goad, selected)
        self.assertEqual(1, spur.priority.int())
        self.assertEqual(2, goad.priority.int())


if __name__ == '__main__':
    import unittest
    unittest.main()
