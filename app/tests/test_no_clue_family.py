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
FAMILY = 'Skill System Slot C/No Clue Family'
PARENTS = ('Inspiration_T1', 'Inspiration_T2', 'Inspiration_T3')
VALUES = {'Inspiration_T1': 2, 'Inspiration_T2': 3, 'Inspiration_T3': 4}


class AuraBoard:
    def __init__(self, units):
        self.units = {unit.position: unit for unit in units}
        self.aura_grid = defaultdict(set)
        self.known_auras = defaultdict(set)
        self.bounds = (0, 0, 8, 8)

    def check_bounds(self, position):
        return all(0 <= position[idx] <= 8 for idx in (0, 1))

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


class NoClueFamilyTests(TestCase):
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
        return dict(NoClueFamilyTests.skills[nid]['components'])

    @staticmethod
    def _unit(nid, team, position):
        return UnitObject(nid, team=team, klass=DB.classes.get('Myrmidon').nid,
                          position=position)

    @staticmethod
    def _parent(owner, nid):
        return item_funcs.create_skill(owner, nid)

    def test_static_contract_has_three_aura_parents_and_three_stacking_effects(self):
        effects = {f'{nid}_Effect' for nid in PARENTS}
        family_records = {nid for nid, category in self.categories.items() if category == FAMILY}
        self.assertEqual(set(PARENTS) | effects, family_records)

        for nid, value in VALUES.items():
            with self.subTest(nid=nid):
                parent = self._components(nid)
                effect = self._components(f'{nid}_Effect')
                self.assertEqual(f'{nid}_Effect', parent['aura'])
                self.assertEqual(2, parent['aura_range'])
                self.assertEqual('ally', parent['aura_target'])
                self.assertEqual(value, effect['damage'])
                self.assertEqual(value, effect['resist'])
                self.assertIn('hidden', effect)
                self.assertEqual(999, effect['stack'])
                self.assertIn(f'deal {value} extra damage', self.skills[nid]['desc'].lower())

    def test_aura_excludes_owner_and_foes_and_respects_two_space_range(self):
        owner = self._unit('owner', 'player', (2, 2))
        ally_one = self._unit('ally_one', 'player', (3, 2))
        ally_two = self._unit('ally_two', 'player', (4, 2))
        foe = self._unit('foe', 'enemy', (1, 2))
        outside = self._unit('outside', 'player', (5, 2))
        parent = self._parent(owner, 'Inspiration_T3')
        board = AuraBoard([owner, ally_one, ally_two, foe, outside])
        field = AuraGame(board, [owner, ally_one, ally_two, foe, outside],
                         [parent, parent.subskill])

        original_apply = aura_funcs.apply_aura
        with patch.object(aura_funcs, 'apply_aura', side_effect=lambda source, unit, child, target:
                          original_apply(source, unit, child, target, test=True)):
            aura_funcs.propagate_aura(owner, parent, field)

        self.assertNotIn(parent.subskill, owner.all_skills)
        self.assertIn(parent.subskill, ally_one.all_skills)
        self.assertIn(parent.subskill, ally_two.all_skills)
        self.assertNotIn(parent.subskill, foe.all_skills)
        self.assertNotIn(parent.subskill, outside.all_skills)
        self.assertEqual(4, skill_system.modify_damage(ally_one, None))
        self.assertEqual(4, skill_system.modify_resist(ally_one, None))

    def test_identical_and_mixed_tier_sources_stack_and_one_source_can_withdraw(self):
        owner_one = self._unit('owner_one', 'player', (2, 2))
        owner_two = self._unit('owner_two', 'player', (2, 3))
        owner_three = self._unit('owner_three', 'player', (3, 3))
        ally = self._unit('ally', 'player', (3, 2))
        first = self._parent(owner_one, 'Inspiration_T2')
        second = self._parent(owner_two, 'Inspiration_T2')
        third = self._parent(owner_three, 'Inspiration_T3')
        for owner, child in ((owner_one, first.subskill), (owner_two, second.subskill),
                             (owner_three, third.subskill)):
            aura_funcs.apply_aura(owner, ally, child, 'ally', test=True)

        self.assertEqual(3, sum(skill.nid.startswith('Inspiration_') for skill in ally.all_skills))
        self.assertEqual(10, skill_system.modify_damage(ally, None))
        self.assertEqual(10, skill_system.modify_resist(ally, None))
        aura_funcs.remove_aura(ally, first.subskill, test=True)
        self.assertEqual(7, skill_system.modify_damage(ally, None))
        self.assertEqual(7, skill_system.modify_resist(ally, None))


if __name__ == '__main__':
    import unittest
    unittest.main()
