import json
from collections import defaultdict
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import aura_funcs, item_funcs, item_system, skill_system
from app.engine.objects.unit import UnitObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Guard Family'
PARENTS = (
    'Distant_Guard_T1', 'Distant_Guard_T2', 'Distant_Guard_T3',
    'Close_Guard_T1', 'Close_Guard_T2', 'Close_Guard_T3',
    'Joint_Distant_Guard', 'Joint_Close_Guard',
)


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


class GuardFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)

    @staticmethod
    def _components(nid):
        return dict(GuardFamilyTests.skills[nid]['components'])

    @staticmethod
    def _unit(nid, team, position):
        return UnitObject(nid, team=team, klass=DB.classes.get('Myrmidon').nid,
                          position=position)

    @staticmethod
    def _parent(owner, nid):
        return item_funcs.create_skill(owner, nid)

    def test_static_contract_has_eight_parents_eight_hidden_effects_and_correct_values(self):
        effects = tuple(f'{nid}_Effect' for nid in PARENTS)
        family_records = {nid for nid, category in self.categories.items() if category == FAMILY}
        self.assertEqual(set(PARENTS) | set(effects), family_records)
        for nid in PARENTS:
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertEqual(f'{nid}_Effect', components['aura'])
                self.assertEqual(2, components['aura_range'])
                self.assertEqual('ally', components['aura_target'])
                self.assertIn('hide_aura', components)
                self.assertNotIn('do_nothing', components)

        values = {
            'Distant_Guard_T1': 2, 'Distant_Guard_T2': 4, 'Distant_Guard_T3': 6,
            'Close_Guard_T1': 2, 'Close_Guard_T2': 4, 'Close_Guard_T3': 6,
            'Joint_Distant_Guard': 8, 'Joint_Close_Guard': 8,
        }
        for nid, value in values.items():
            with self.subTest(effect=nid):
                effect = self._components(f'{nid}_Effect')
                self.assertIn('hidden', effect)
                self.assertEqual(999, effect['stack'])
                self.assertEqual([['DEF', value], ['RES', value]], effect['stat_change'])
                self.assertIn("mode == 'defense'", effect['combat_condition'])
                self.assertIn('item2 and item_system.maximum_range(target, item2)', effect['combat_condition'])
                self.assertIn('utils.calculate_distance(unit.position, target.position)', effect['combat_condition'])

        for nid in ('Joint_Distant_Guard', 'Joint_Close_Guard'):
            components = self._components(nid)
            self.assertEqual([['DEF', 8], ['RES', 8]], components['stat_change'])
            self.assertIn("mode == 'defense'", components['combat_condition'])

    def test_aura_excludes_owner_and_enemies_and_includes_allies_within_two_spaces(self):
        owner = self._unit('owner', 'player', (2, 2))
        ally_one = self._unit('ally_one', 'player', (3, 2))
        ally_two = self._unit('ally_two', 'player', (4, 2))
        enemy = self._unit('enemy', 'enemy', (1, 2))
        outside = self._unit('outside', 'player', (5, 2))
        parent = self._parent(owner, 'Distant_Guard_T3')
        board = AuraBoard([owner, ally_one, ally_two, enemy, outside])
        field = AuraGame(board, [owner, ally_one, ally_two, enemy, outside],
                         [parent, parent.subskill])

        original_apply = aura_funcs.apply_aura
        with patch.object(aura_funcs, 'apply_aura', side_effect=lambda source, unit, child, target:
                          original_apply(source, unit, child, target, test=True)):
            aura_funcs.propagate_aura(owner, parent, field)

        self.assertNotIn(parent.subskill, owner.all_skills)
        self.assertIn(parent.subskill, ally_one.all_skills)
        self.assertIn(parent.subskill, ally_two.all_skills)
        self.assertNotIn(parent.subskill, enemy.all_skills)
        self.assertNotIn(parent.subskill, outside.all_skills)

    def test_guard_conditions_use_defense_mode_and_weapon_or_distance_with_no_weapon_safe(self):
        def is_active(nid, source_position, target_position, item2, maximum_range, mode):
            source = self._unit('source', 'player', source_position)
            target = self._unit('target', 'enemy', target_position)
            effect = self._parent(source, nid + '_Effect')
            source.add_skill(effect, 'test')
            with patch.object(item_system, 'maximum_range', return_value=maximum_range) as get_range:
                skill_system.pre_combat([], source, None, target, item2, mode)
                active = skill_system.condition(effect, source)
            return active, get_range

        active, get_range = is_active('Distant_Guard_T3', (0, 0), (2, 0), None, 99, 'defense')
        self.assertTrue(active)
        get_range.assert_not_called()
        active, _ = is_active('Distant_Guard_T3', (0, 0), (1, 0), object(), 2, 'defense')
        self.assertTrue(active)
        active, _ = is_active('Distant_Guard_T3', (0, 0), (2, 0), object(), 2, 'attack')
        self.assertFalse(active)

        active, get_range = is_active('Close_Guard_T3', (0, 0), (1, 0), None, 99, 'defense')
        self.assertTrue(active)
        get_range.assert_not_called()
        active, _ = is_active('Close_Guard_T3', (0, 0), (2, 0), object(), 1, 'defense')
        self.assertTrue(active)

    def test_joint_self_bonus_and_independent_aura_sources_stack(self):
        source = self._unit('source', 'player', (0, 0))
        foe = self._unit('foe', 'enemy', (2, 0))
        source.add_skill(self._parent(source, 'Joint_Distant_Guard'), 'test')
        skill_system.pre_combat([], source, None, foe, None, 'defense')
        self.assertEqual(8, skill_system.stat_change(source, 'DEF'))
        self.assertEqual(8, skill_system.stat_change(source, 'RES'))

        owner_one = self._unit('owner_one', 'player', (2, 2))
        owner_two = self._unit('owner_two', 'player', (2, 3))
        ally = self._unit('ally', 'player', (3, 2))
        first = self._parent(owner_one, 'Distant_Guard_T3')
        second = self._parent(owner_two, 'Distant_Guard_T3')
        aura_funcs.apply_aura(owner_one, ally, first.subskill, 'ally', test=True)
        aura_funcs.apply_aura(owner_two, ally, second.subskill, 'ally', test=True)
        foe = self._unit('foe_two', 'enemy', (5, 2))
        skill_system.pre_combat([], ally, None, foe, None, 'defense')
        self.assertEqual(2, sum(skill.nid == 'Distant_Guard_T3_Effect' for skill in ally.all_skills))
        self.assertEqual(12, skill_system.stat_change(ally, 'DEF'))
        self.assertEqual(12, skill_system.stat_change(ally, 'RES'))
        aura_funcs.remove_aura(ally, first.subskill, test=True)
        self.assertEqual(6, skill_system.stat_change(ally, 'DEF'))

    def test_aura_release_repopulate_and_post_combat_cleanup_leave_no_stale_guard_bonus(self):
        owner = self._unit('owner', 'player', (2, 2))
        old_ally = self._unit('old_ally', 'player', (3, 2))
        new_ally = self._unit('new_ally', 'player', (5, 2))
        parent = self._parent(owner, 'Close_Guard_T2')
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

        foe = self._unit('foe', 'enemy', (6, 2))
        skill_system.pre_combat([], new_ally, None, foe, None, 'defense')
        self.assertEqual(4, skill_system.stat_change(new_ally, 'DEF'))
        skill_system.post_combat([], new_ally, None, foe, None, 'defense')
        self.assertEqual(0, skill_system.stat_change(new_ally, 'DEF'))
        self.assertNotIn(parent.subskill, old_ally.all_skills)


if __name__ == '__main__':
    import unittest
    unittest.main()
