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
from app.engine.objects.unit import UnitObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Armored Movement Family'
PARENTS = ('Armor_Mach_T1', 'Armor_Mach_T2', 'Armor_Mach_T3',
           'Armored_Stride_T1', 'Armored_Stride_T2', 'Armored_Stride_T3')
EFFECTS = ('Armor_Mach_Movement_Effect', 'Armored_Stride_Movement_Effect')


class RuntimeUnit:
    def __init__(self, nid, team='player', position=(2, 2), tags=(), hp=20, maximum_hp=20):
        self.nid = nid
        self.team = team
        self.position = position
        self.tags = set(tags)
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.hp = hp
        self.maximum_hp = maximum_hp
        self.mana = 0
        self.equipped_weapon = None

    @property
    def all_skills(self):
        return self.skills

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.maximum_hp

    def set_hp(self, hp):
        self.hp = hp

    def get_mana(self):
        return self.mana

    def set_mana(self, mana):
        self.mana = mana

    def add_skill(self, skill, source=None, source_type=None, test=False):
        if test:
            return None
        self.skills.append(skill)

    def remove_skill(self, skill, source=None, source_type=None, test=False):
        if skill not in self.skills:
            return False
        if test:
            return True
        self.skills.remove(skill)
        return source, source_type

    def autoequip(self):
        pass


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


class ArmoredMovementFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(nid):
        return dict(ArmoredMovementFamilyTests.skills[nid]['components'])

    @staticmethod
    def _owner(component):
        skill = SimpleNamespace(nid='parent', components=[component])
        component.skill = skill
        return skill

    def _run(self, component, source, units):
        source.skills = [self._owner(component)]
        actions = []
        with patch.object(self.components, 'game', FieldGame([source, *units])), \
                patch.object(self.components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: owner.team == target.team):
            component.on_upkeep(actions, [], source)
        return actions

    def test_project_contract_has_six_givers_two_hidden_effects_and_exact_tiers(self):
        family = {nid for nid, category in self.categories.items() if category == FAMILY}
        self.assertEqual(set(PARENTS) | set(EFFECTS), family)
        expected = {
            'Armor_Mach_T1': ('armor_mach_at_upkeep', {'hp': 'full', 'range': 3, 'bonus': 1, 'rank': 1}),
            'Armor_Mach_T2': ('armor_mach_at_upkeep', {'hp': 'above_half', 'range': 3, 'bonus': 1, 'rank': 2}),
            'Armor_Mach_T3': ('armor_mach_at_upkeep', {'hp': 'any', 'range': 4, 'bonus': 2, 'rank': 3}),
            'Armored_Stride_T1': ('armored_stride_at_upkeep', {'hp': 'full', 'range': 3, 'bonus': 1, 'rank': 1}),
            'Armored_Stride_T2': ('armored_stride_at_upkeep', {'hp': 'above_half', 'range': 3, 'bonus': 1, 'rank': 2}),
            'Armored_Stride_T3': ('armored_stride_at_upkeep', {'hp': 'any', 'range': 4, 'bonus': 2, 'rank': 3}),
        }
        for nid, (component, value) in expected.items():
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertEqual(value, components[component])
                self.assertNotIn('do_nothing', components)
                self.assertNotIn('amored', self.skills[nid]['desc'])
                self.assertNotIn('  ', self.skills[nid]['desc'])
        for nid in EFFECTS:
            components = self._components(nid)
            self.assertIn('hidden', components)
            self.assertIn('temporary_movement_bonus', components)
            self.assertIn('lost_on_endstep', components)
            self.assertIn('lost_on_end_chapter', components)

    def test_armor_mach_targets_all_valid_armored_allies_and_not_non_armored(self):
        component = self.components.ArmorMachAtUpkeep(
            {'hp': 'full', 'range': 3, 'bonus': 1, 'rank': 1})
        source = RuntimeUnit('source', tags=())  # User armor tag is intentionally irrelevant.
        valid_one = RuntimeUnit('valid_one', position=(3, 2), tags=('Armor',))
        valid_edge = RuntimeUnit('valid_edge', position=(5, 2), tags=('Armor',))
        beyond = RuntimeUnit('beyond', position=(6, 2), tags=('Armor',))
        non_armored = RuntimeUnit('non_armored', position=(2, 3), tags=('Horse',))
        enemy = RuntimeUnit('enemy', team='enemy', position=(1, 2), tags=('Armor',))
        off_map = RuntimeUnit('off_map', position=None, tags=('Armor',))
        dead = RuntimeUnit('dead', position=(2, 1), tags=('Armor',)); dead.dead = True
        dying = RuntimeUnit('dying', position=(1, 3), tags=('Armor',)); dying.is_dying = True
        tile = RuntimeUnit('tile', position=(3, 1), tags=('Armor', 'Tile'))
        zero_hp = RuntimeUnit('zero_hp', position=(1, 1), tags=('Armor',), hp=0)
        actions = self._run(component, source, [valid_one, valid_edge, beyond, non_armored, enemy, off_map, dead, dying, tile, zero_hp])
        self.assertEqual({'source', 'valid_one', 'valid_edge'}, {entry.unit.nid for entry in actions})
        self.assertTrue(all(entry.skill_obj.nid == EFFECTS[0] for entry in actions))
        self.assertTrue(all(entry.skill_obj.data['movement_bonus'] == 1 for entry in actions))

    def test_real_team_relationships_do_not_grant_armor_mach_to_foes(self):
        component = self.components.ArmorMachAtUpkeep(
            {'hp': 'any', 'range': 3, 'bonus': 1, 'rank': 1})
        source = RuntimeUnit('source', 'player', tags=())
        ally = RuntimeUnit('ally', 'player', position=(3, 2), tags=('Armor',))
        enemy = RuntimeUnit('enemy', 'enemy', position=(1, 2), tags=('Armor',))
        enemy_two = RuntimeUnit('enemy_two', 'enemy2', position=(2, 3), tags=('Armor',))
        actions = []
        source.skills = [self._owner(component)]
        with patch.object(self.components, 'game', FieldGame([source, ally, enemy, enemy_two])):
            component.on_upkeep(actions, [], source)
        self.assertEqual({'source', 'ally'}, {entry.unit.nid for entry in actions})

    def test_hp_boundaries_and_stride_any_ally_blocking_are_strict(self):
        for hp, maximum_hp, expected in ((20, 20, True), (10, 20, False), (11, 20, False)):
            with self.subTest(mach_hp=(hp, maximum_hp)):
                component = self.components.ArmorMachAtUpkeep(
                    {'hp': 'full', 'range': 3, 'bonus': 1, 'rank': 1})
                source = RuntimeUnit('source', hp=hp, maximum_hp=maximum_hp)
                target = RuntimeUnit('target', position=(3, 2), tags=('Armor',))
                self.assertEqual(expected, bool(self._run(component, source, [target])))
        for hp, expected in ((10, False), (11, True)):
            with self.subTest(stride_hp=hp):
                component = self.components.ArmoredStrideAtUpkeep(
                    {'hp': 'above_half', 'range': 3, 'bonus': 1, 'rank': 2})
                source = RuntimeUnit('source', hp=hp, maximum_hp=20)
                self.assertEqual(expected, bool(self._run(component, source, [])))
        component = self.components.ArmoredStrideAtUpkeep(
            {'hp': 'any', 'range': 4, 'bonus': 2, 'rank': 3})
        source = RuntimeUnit('source')
        any_tag_ally = RuntimeUnit('horse_ally', position=(3, 2), tags=('Horse',))
        distant_ally = RuntimeUnit('distant', position=(7, 2), tags=('Armor',))
        self.assertEqual([], self._run(component, source, [any_tag_ally, distant_ally]))
        self.assertEqual(1, len(self._run(component, source, [distant_ally])))

    def test_same_line_uses_highest_qualified_tier_with_lower_fallback(self):
        source = RuntimeUnit('source')
        tier_two = self.components.ArmoredStrideAtUpkeep(
            {'hp': 'above_half', 'range': 3, 'bonus': 1, 'rank': 2})
        tier_three = self.components.ArmoredStrideAtUpkeep(
            {'hp': 'any', 'range': 4, 'bonus': 2, 'rank': 3})
        source.skills = [self._owner(tier_two), self._owner(tier_three)]
        blocking_at_four = RuntimeUnit('blocker', position=(6, 2))
        actions = []
        with patch.object(self.components, 'game', FieldGame([source, blocking_at_four])), \
                patch.object(self.components.skill_system, 'check_ally', return_value=True):
            tier_two.on_upkeep(actions, [], source)
            tier_three.on_upkeep(actions, [], source)
        self.assertEqual(1, len(actions))
        self.assertEqual(1, actions[0].skill_obj.data['movement_bonus'])

    def test_effects_use_max_per_line_stack_across_lines_and_cleanup(self):
        mach_two = SkillObject.from_prefab(DB.skills.get(EFFECTS[0]))
        stride = SkillObject.from_prefab(DB.skills.get(EFFECTS[1]))
        mach_two.data['movement_bonus'] = 2
        stride.data['movement_bonus'] = 2
        target = UnitObject('target', team='player', klass=DB.classes.get('Myrmidon').nid,
                            position=(2, 2), _tags=set())
        target.stats['MOV'] = 5
        for effect in (mach_two, stride):
            target.add_skill(effect)
        self.assertEqual(4, skill_system.stat_change(target, 'MOV'))
        self.assertEqual(9, target.get_movement())
        self.assertFalse(target.has_moved)
        self.assertEqual(9, target.movement_left)
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            endstep = []
            skill_system.on_endstep(endstep, [], target)
            for queued in endstep:
                queued.do()
        self.assertEqual([], target.skills)

    def test_same_effect_line_replaces_only_with_a_stronger_cross_source_bonus(self):
        component = self.components.ArmorMachAtUpkeep(
            {'hp': 'any', 'range': 4, 'bonus': 2, 'rank': 3})
        source = RuntimeUnit('source')
        target = RuntimeUnit('target')
        existing = SkillObject.from_prefab(DB.skills.get(EFFECTS[0]))
        existing.data['movement_bonus'] = 1
        target.skills = [existing]
        actions = []
        component._grant(actions, target, source)
        self.assertEqual(2, len(actions))
        self.assertIsInstance(actions[0], action.RemoveSkill)
        self.assertEqual(2, actions[1].skill_obj.data['movement_bonus'])
        existing.data['movement_bonus'] = 2
        actions.clear()
        component._grant(actions, target, source)
        self.assertEqual([], actions)

    def test_effect_is_removed_at_end_chapter_and_resources_load_registers_components(self):
        target = RuntimeUnit('target')
        effect = SkillObject.from_prefab(DB.skills.get(EFFECTS[0]))
        target.skills = [effect]
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            skill_system.on_end_chapter(target, effect)
        self.assertEqual([], target.skills)
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        from app.engine import skill_component_access
        self.assertIsNotNone(skill_component_access.get_component('temporary_movement_bonus'))
        self.assertIsNotNone(skill_component_access.get_component('armor_mach_at_upkeep'))
        self.assertIsNotNone(skill_component_access.get_component('armored_stride_at_upkeep'))


if __name__ == '__main__':
    import unittest
    unittest.main()
