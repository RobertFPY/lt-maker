import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, skill_component_access, skill_system
from app.engine.game_state import game
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Hone Family'
STAT_PARENTS = {
    'Hone_Strength': 'STR',
    'Hone_Magic': 'MAG',
    'Hone_Speed': 'SPD',
    'Fortify_Defense': 'DEF',
    'Fortify_Resistance': 'RES',
}
MOVEMENT_PARENTS = {
    'Hone_Armor': ('Hone_Movement_Effect', 'Armor'),
    'Hone_Cavalry': ('Hone_Movement_Effect', 'Horse'),
    'Hone_Fliers': ('Hone_Movement_Effect', 'Flying'),
    'Fone_Dragons': ('Hone_Movement_Effect', 'Dragon'),
    'Fortify_Armor': ('Fortify_Movement_Effect', 'Armor'),
    'Fortify_Cavalry': ('Fortify_Movement_Effect', 'Horse'),
    'Fortify_Fliers': ('Fortify_Movement_Effect', 'Flying'),
    'Fortify_Dragons': ('Fortify_Movement_Effect', 'Dragon'),
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

    def get_hp(self):
        return self.hp

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


class HoneFamilyTests(TestCase):
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
    def _components(skill):
        return dict(HoneFamilyTests.skills[skill]['components'])

    def _component(self, status='Hone_Speed_T2_Effect', tags=()):
        return self.custom_components.HoneAllyStatus({
            'status': status,
            'range': 2,
            'required_tags': list(tags),
        })

    def test_static_contract_has_23_consumers_17_effects_and_exact_values(self):
        parents = [nid for nid, category in self.categories.items()
                   if category == FAMILY and not nid.endswith('_Effect')]
        effects = [nid for nid, category in self.categories.items()
                   if category == FAMILY and nid.endswith('_Effect')]
        self.assertEqual(23, len(parents))
        self.assertEqual(17, len(effects))
        self.assertEqual(40, len(parents) + len(effects))
        self.assertEqual('Hone Dragons', self.skills['Fone_Dragons']['name'])

        parent_components = [self._components(nid) for nid in parents]
        self.assertEqual(23, sum('hone_ally_status' in components for components in parent_components))
        self.assertEqual(0, sum('do_nothing' in components for components in parent_components))
        self.assertEqual(15, sum(components['hone_ally_status']['range'] == 2
                                 for components in parent_components))
        self.assertEqual(8, sum(components['hone_ally_status']['range'] == 1
                                for components in parent_components))
        self.assertEqual(8, sum(bool(components['hone_ally_status']['required_tags'])
                                for components in parent_components))
        self.assertEqual(8, sum(self._components(nid).get('priority') == 2
                                for nid in MOVEMENT_PARENTS))

        for prefix, stat in STAT_PARENTS.items():
            for tier, value in ((1, 3), (2, 4), (3, 5)):
                effect = self._components(f'{prefix}_T{tier}_Effect')
                self.assertEqual([[stat, value]], effect['stat_change'])
        self.assertEqual(6, self._components('Hone_Movement_Effect')['damage'])
        self.assertEqual([['SPD', 6]], self._components('Hone_Movement_Effect')['stat_change'])
        self.assertEqual([['DEF', 6], ['RES', 6]],
                         self._components('Fortify_Movement_Effect')['stat_change'])
        for effect in effects:
            components = self._components(effect)
            self.assertIn('hidden', components)
            self.assertIn('lost_on_endstep', components)
            self.assertIn('lost_on_end_chapter', components)

    def test_upkeep_queues_only_living_on_map_other_allies_within_shell_and_matching_tags(self):
        component = self._component(tags=('Horse',))
        source = RuntimeUnit('source', 'player', (2, 2), ('Horse',))
        valid = RuntimeUnit('valid', 'player', (3, 2), ('Horse',))
        edge = RuntimeUnit('edge', 'player', (4, 2), ('Horse',))
        wrong_tag = RuntimeUnit('wrong_tag', 'player', (2, 3), ('Armor',))
        enemy = RuntimeUnit('enemy', 'enemy', (2, 1), ('Horse',))
        off_map = RuntimeUnit('off_map', 'player', None, ('Horse',))
        dead = RuntimeUnit('dead', 'player', (1, 2), ('Horse',))
        dead.dead = True
        dying = RuntimeUnit('dying', 'player', (2, 0), ('Horse',))
        dying.is_dying = True
        tile = RuntimeUnit('tile', 'player', (1, 3), ('Horse', 'Tile'))
        beyond = RuntimeUnit('beyond', 'player', (5, 2), ('Horse',))
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([
                source, valid, edge, wrong_tag, enemy, off_map, dead, dying, tile, beyond])), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: owner.team == target.team):
            component.on_upkeep(actions, [], source)

        self.assertEqual({'valid', 'edge'}, {entry.unit.nid for entry in actions})
        self.assertTrue(all(entry.skill_obj.nid == 'Hone_Speed_T2_Effect' for entry in actions))
        self.assertTrue(all(entry.initiator is source for entry in actions))

    def test_empty_tags_apply_to_any_valid_ally_and_same_status_is_not_queued_twice(self):
        component = self._component(tags=())
        source = RuntimeUnit('source', 'player', (2, 2))
        first = RuntimeUnit('first', 'player', (3, 2), ('Armor',))
        duplicate = RuntimeUnit('duplicate', 'player', (2, 3))
        duplicate.skills = [SkillObject.from_prefab(DB.skills.get('Hone_Speed_T2_Effect'))]
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([source, first, duplicate])), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
            component.on_upkeep(actions, [], source)
        self.assertEqual(['first'], [entry.unit.nid for entry in actions])

    def test_untiered_movement_hones_remain_outside_ranked_exclusivity(self):
        from app.engine import ranked_upkeep

        component = self._component('Hone_Movement_Effect', tags=('Horse',))
        source = RuntimeUnit('source', 'player', (2, 2), ('Horse',))
        target = RuntimeUnit('target', 'player', (3, 2), ('Horse',))
        actions = []
        ranked_upkeep.begin_upkeep([], [])
        try:
            with patch.object(self.custom_components, 'game', FieldGame([source, target])), \
                    patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
                component.on_upkeep(actions, [], source)
        finally:
            ranked_upkeep.end_upkeep()
        self.assertEqual(['target'], [entry.unit.nid for entry in actions])

    def test_effects_suppress_lower_tiers_and_movement_specialization_and_expire(self):
        target = RuntimeUnit('target', 'player')
        effect_nids = ('Hone_Speed_T1_Effect', 'Hone_Speed_T2_Effect', 'Hone_Speed_T3_Effect',
                       'Hone_Movement_Effect')
        target.skills = [SkillObject.from_prefab(DB.skills.get(nid)) for nid in effect_nids]
        self.assertEqual(6, skill_system.stat_change(target, 'SPD'))
        self.assertEqual(6, skill_system.modify_damage(target, None))
        queued = []
        skill_system.on_endstep(queued, [], target)
        self.assertEqual(4, len(queued))
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars):
            for entry in queued:
                entry.reset_action = NoOpResetUnitVars(target)
                entry.do()
        self.assertEqual([], target.skills)

    def test_effect_is_removed_at_end_chapter(self):
        target = RuntimeUnit('target', 'player')
        effect = SkillObject.from_prefab(DB.skills.get('Fortify_Movement_Effect'))
        target.skills = [effect]
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(action, 'do', side_effect=lambda queued_action: queued_action.do()):
            skill_system.on_end_chapter(target, effect)
        self.assertEqual([], target.skills)

    def test_resources_then_database_restore_registers_component_and_effects(self):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        self.assertIsNotNone(skill_component_access.get_component('hone_ally_status'))
        self.assertIsNotNone(DB.skills.get('Hone_Movement_Effect'))
        self.assertIsNotNone(DB.skills.get('Fortify_Movement_Effect'))


if __name__ == '__main__':
    import unittest
    unittest.main()
