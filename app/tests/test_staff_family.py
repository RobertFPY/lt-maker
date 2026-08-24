import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, combat_calcs, item_system, skill_system
from app.engine.game_state import game
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
WRATHFUL_PARENTS = tuple(f'Wrathfull_Staff_T{tier}' for tier in ('1', '2', '3', '4_1', '4_2'))
MYSTIC_PARENTS = tuple(f'Mystic_Boost_T{tier}' for tier in range(1, 4))


class RuntimeUnit:
    def __init__(self, nid, team, position=(0, 0)):
        self.nid = nid
        self.team = team
        self.position = position
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.tags = []
        self.equipped_weapon = None

    @property
    def all_skills(self):
        return self.skills

    def get_stat(self, stat):
        return {'DEF': 10, 'RES': 4}[stat]

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


class StaffFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(encoding='utf-8'))
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        # Custom component discovery depends on resources being available before DB loading.
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @classmethod
    def _components(cls, nid):
        return dict(cls.skills[nid]['components'])

    def test_mystic_only_neutralizes_wrathful_adaptive_formula_and_dazzling_counter_lock(self):
        attacker = RuntimeUnit('wrathful', 'enemy')
        defender = RuntimeUnit('mystic', 'player')
        attacker.skills = [SkillObject.from_prefab(DB.skills.get('Wrathfull_Staff_T3'))]
        defender.skills = [SkillObject.from_prefab(DB.skills.get('Mystic_Boost_T1'))]
        self.assertTrue(skill_system.adaptive_damage(attacker))
        self.assertTrue(skill_system.neutralize_foe_adaptive_damage(defender))
        self.assertTrue(skill_system.negate_cannot_be_countered(defender))
        formulas = {'WORSE_DEFENSE': 4, 'DEFENSE': 10}
        with patch.object(item_system, 'resist_formula', return_value='WORSE_DEFENSE'), \
                patch.object(skill_system, 'resist_formula', return_value=None), \
                patch.object(item_system, 'resist_formula_override', return_value=None), \
                patch.object(skill_system, 'resist_formula_override', return_value=None), \
                patch.object(skill_system.Defaults, 'resist_formula', return_value='DEFENSE'), \
                patch.object(combat_calcs.equations.parser, 'get', side_effect=lambda formula, unit: formulas[formula]), \
                patch.object(combat_calcs, 'get_weapon_rank_bonus', return_value=None), \
                patch.object(combat_calcs, 'get_support_rank_bonus', return_value=([], [])), \
                patch.object(item_system, 'modify_resist', return_value=0), \
                patch.object(skill_system, 'modify_resist', return_value=0):
            with patch.object(skill_system, 'adaptive_damage', return_value=True), \
                    patch.object(skill_system, 'neutralize_foe_adaptive_damage', return_value=True):
                self.assertEqual(10, combat_calcs.defense(attacker, defender, object(), object()))
                with patch.object(item_system, 'resist_formula_override', return_value='WORSE_DEFENSE'):
                    self.assertEqual(4, combat_calcs.defense(attacker, defender, object(), object()))
            with patch.object(skill_system, 'adaptive_damage', return_value=False), \
                    patch.object(skill_system, 'neutralize_foe_adaptive_damage', return_value=True):
                self.assertEqual(4, combat_calcs.defense(attacker, defender, object(), object()))
            with patch.object(skill_system, 'adaptive_damage', return_value=True), \
                    patch.object(skill_system, 'neutralize_foe_adaptive_damage', return_value=False):
                self.assertEqual(4, combat_calcs.defense(attacker, defender, object(), object()))

        for nid in MYSTIC_PARENTS:
            components = self._components(nid)
            self.assertIn('neutralize_foe_adaptive_damage', components)
            self.assertIn('negate_cannot_be_countered', components)
            self.assertIn('after combat', self.skills[nid]['desc'].lower())

    def test_mystic_bypasses_only_skill_counter_lock_not_base_item_lock(self):
        class CounterComponent:
            def __init__(self, value):
                self.value = value

            def defines(self, hook):
                return hook == 'can_be_countered'

            def can_be_countered(self, unit, item):
                return self.value

        attacker = SimpleNamespace(skills=[])
        normal_weapon = SimpleNamespace(components=[CounterComponent(True)])
        siege_weapon = SimpleNamespace(components=[CounterComponent(False)])
        dazzling_override = CounterComponent(False)
        with patch.object(skill_system, 'item_override',
                          return_value=[dazzling_override]):
            self.assertEqual((True, False),
                             combat_calcs._can_be_countered_sources(
                                 attacker, normal_weapon))
            self.assertEqual((False, False),
                             combat_calcs._can_be_countered_sources(
                                 attacker, siege_weapon))

    def test_staff_data_marks_only_the_five_wrathful_parents_and_preserves_parent_effects(self):
        adaptive = [
            skill['nid'] for skill in self.skills.values()
            if 'adaptive_damage' in dict(skill['components'])
        ]
        self.assertEqual(list(WRATHFUL_PARENTS), adaptive)
        for nid in WRATHFUL_PARENTS:
            self.assertEqual('WorseDefense_Weapons', self._components(nid)['item_override'])

        tempo = self._components('Wrathfull_Staff_T4_2')
        self.assertEqual('Wrathfull_Staff_T4_2_Effect', tempo['give_status_before_combat'])
        self.assertNotIn('dynamic_damage', tempo)
        self.assertIn('neutralize_foe_follow_up_grants', tempo)
        self.assertNotIn('dynamic_resist', self._components('Wrathfull_Staff_T4_2_Effect'))

    def test_dazzling_shift_and_discord_data_use_statuses_not_legacy_events(self):
        shift = self._components('Dazzling_Staff_T4_1')
        expression = shift['witch_warp_expression']
        for fragment in ('unit is not target', 'skill_system.check_ally(target, unit)',
                         'not unit.dead', 'not unit.is_dying', "'Tile' not in unit.tags",
                         'unit.position', 'utils.calculate_distance(unit.position, target.position) <= 9'):
            self.assertIn(fragment, expression)
        self.assertEqual('Dazzling_Staff_T4_1_Effect', shift['give_status_before_combat'])
        self.assertEqual(4, shift['defense_speed'])
        self.assertEqual('Cannot_Be_Countered_Override', shift['item_override'])
        shift_effect = self._components('Dazzling_Staff_T4_1_Effect')
        self.assertEqual('Skill System Slot B/Staff Family',
                         self.categories['Dazzling_Staff_T4_1_Effect'])
        self.assertEqual(4, shift_effect['attack_speed'])
        self.assertEqual([['SPD', -4]], shift_effect['stat_change'])
        self.assertIn('lost_on_end_combat2', shift_effect)

        discord = self._components('Dazzling_Staff_T4_2')
        self.assertEqual('Dazzling_Staff_T4_2_Effect', discord['upkeep_status_closest_enemy'])
        self.assertNotIn('upkeep_event', discord)
        self.assertNotIn('Global SkillDazzlingDiscord', {event['nid'] for event in self.events})

    def test_discord_upkeep_filters_invalid_targets_and_uses_closest_nid_tiebreaker(self):
        component = self.custom_components.UpkeepStatusClosestEnemy('Dazzling_Staff_T4_2_Effect')
        owner = RuntimeUnit('owner', 'player', (0, 0))
        ally = RuntimeUnit('ally', 'player', (1, 0))
        winner = RuntimeUnit('alpha', 'enemy', (1, 1))
        tied_loser = RuntimeUnit('zeta', 'enemy2', (2, 0))
        off_map = RuntimeUnit('off_map', 'enemy', None)
        dead = RuntimeUnit('dead', 'enemy', (1, 0)); dead.dead = True
        dying = RuntimeUnit('dying', 'enemy', (1, 0)); dying.is_dying = True
        tile = RuntimeUnit('tile', 'enemy', (1, 0)); tile.tags = ['Tile']
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame(
                [owner, ally, tied_loser, winner, off_map, dead, dying, tile])), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda source, target: target.team in ('enemy', 'enemy2')), \
                patch.object(action, 'AddSkill', side_effect=lambda target, nid, source:
                             SimpleNamespace(unit=target, skill_obj=SimpleNamespace(nid=nid), initiator=source)):
            component.on_upkeep(actions, [], owner)
        self.assertEqual(1, len(actions))
        self.assertIs(winner, actions[0].unit)
        self.assertEqual('Dazzling_Staff_T4_2_Effect', actions[0].skill_obj.nid)
        self.assertIs(owner, actions[0].initiator)

    def test_dazzling_shift_effect_is_removed_after_combat(self):
        target = RuntimeUnit('target', 'enemy')
        source = RuntimeUnit('source', 'player')
        effect = SkillObject.from_prefab(DB.skills.get('Dazzling_Staff_T4_1_Effect'))
        target.skills = [effect]
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), \
                patch.object(game, 'skill_registry', {}), \
                patch.object(action, 'do', side_effect=lambda queued: queued.do()):
            skill_system.cleanup_combat([], target, None, source, None, 'defense')
            skill_system.post_combat([], target, None, source, None, 'defense')
        self.assertNotIn(effect, target.skills)


if __name__ == '__main__':
    import unittest
    unittest.main()
