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


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
STATS = ('STR', 'MAG', 'SPD', 'DEF', 'RES')
LEGACY_EVENTS = {
    'Global SkillChillStrength', 'Global SkillChillMagic', 'Global SkillChillSpeed',
    'Global SkillChillDefense', 'Global SkillChillResistance',
}
CHILL_PARENTS = {
    'Strength': 'STR',
    'Magic': 'MAG',
    'Speed': 'SPD',
    'Defense': 'DEF',
    'Resistance': 'RES',
}


class RuntimeUnit:
    def __init__(self, nid, team, stat_values, position=(0, 0)):
        self.nid = nid
        self.team = team
        self.stat_values = stat_values
        self.position = position
        self.skills = []
        self.equipped_weapon = None
        self.stat_calls = []
        self.hp = 10
        self.mana = 0
        self.dead = False
        self.is_dying = False
        self.tags = []

    @property
    def all_skills(self):
        return self.skills

    def get_stat(self, stat):
        self.stat_calls.append(stat)
        return self.stat_values[stat]

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
        return None

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
        self.calls = 0

    def get_all_units(self):
        self.calls += 1
        return [
            unit for unit in self.units
            if unit.position is not None and not unit.dead and not unit.is_dying and 'Tile' not in unit.tags
        ]


class NoOpResetUnitVars:
    def __init__(self, unit):
        pass

    def execute(self):
        pass

    def reverse(self):
        pass


class ChillFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)

        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _components(nid):
        return dict(ChillFamilyTests.skills[nid]['components'])

    def _component(self, stat='SPD', status='Chill_Speed_T2_Effect', rank=2):
        return self.custom_components.ChillHighestStat({
            'stat': stat,
            'status': status,
            'rank': rank,
        })

    @staticmethod
    def _owner_skill(component):
        skill = SimpleNamespace(components=[component])
        component.skill = skill
        return skill

    def _run_upkeep(self, component, units):
        source = RuntimeUnit('source', 'player', {stat: 0 for stat in STATS})
        source.skills = [self._owner_skill(component)]
        field_game = FieldGame(units)
        actions = []
        with patch.object(self.custom_components, 'game', field_game), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team in ('enemy', 'enemy2')):
            component.on_upkeep(actions, [], source)
        return source, field_game, actions

    def test_migration_replaces_all_legacy_events_with_ranked_custom_components(self):
        mains = [nid for nid in self.skills if nid.startswith('Chill_') and not nid.endswith('_Effect')]
        effects = [nid for nid in self.skills if nid.startswith('Chill_') and nid.endswith('_Effect')]
        self.assertEqual(15, len(mains))
        self.assertEqual(15, len(effects))
        for family, stat in CHILL_PARENTS.items():
            for rank in range(1, 4):
                nid = f'Chill_{family}_T{rank}'
                with self.subTest(nid=nid):
                    components = self._components(nid)
                    self.assertEqual({
                        'stat': stat,
                        'status': f'{nid}_Effect',
                        'rank': rank,
                    }, components['chill_highest_stat'])
                    self.assertNotIn('upkeep_event', components)
                    self.assertTrue(self.skills[nid]['desc'].startswith('At the start of turn,'))
        for nid in effects:
            with self.subTest(nid=nid):
                components = self._components(nid)
                self.assertIn('stat_change', components)
                self.assertIn('lost_on_endstep', components)
                self.assertIn('lost_on_end_chapter', components)
                self.assertNotIn('lost_on_end_combat2', components)
                if nid.endswith('_T1_Effect') or nid.endswith('_T2_Effect'):
                    self.assertIn('condition', components)
                    self.assertIn('hidden_if_inactive', components)
        self.assertFalse(LEGACY_EVENTS & {event['nid'] for event in self.events})

    def test_highest_selection_uses_get_stat_including_bonus_and_penalty_with_stable_tie_break(self):
        component = self._component()
        bonus = RuntimeUnit('bonus', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 8, 'DEF': 0, 'RES': 0})
        penalty = RuntimeUnit('penalty', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 7, 'DEF': 0, 'RES': 0})
        tie = RuntimeUnit('tie', 'enemy2', {'STR': 0, 'MAG': 0, 'SPD': 8, 'DEF': 0, 'RES': 0})
        ally = RuntimeUnit('ally', 'player', {'STR': 0, 'MAG': 0, 'SPD': 99, 'DEF': 0, 'RES': 0})
        off_field = RuntimeUnit('off_field', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 100, 'DEF': 0, 'RES': 0}, position=None)
        dead = RuntimeUnit('dead', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 100, 'DEF': 0, 'RES': 0})
        dead.dead = True
        dying = RuntimeUnit('dying', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 100, 'DEF': 0, 'RES': 0})
        dying.is_dying = True
        tile = RuntimeUnit('tile', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 100, 'DEF': 0, 'RES': 0})
        tile.tags = ['Tile']
        source, field_game, actions = self._run_upkeep(
            component, [bonus, penalty, tie, ally, off_field, dead, dying, tile])

        self.assertEqual(1, field_game.calls)
        self.assertEqual(['SPD'], bonus.stat_calls)
        self.assertEqual(['SPD'], penalty.stat_calls)
        self.assertEqual(['SPD'], tie.stat_calls)
        self.assertEqual([], ally.stat_calls)
        self.assertEqual([], off_field.stat_calls)
        self.assertEqual([], dead.stat_calls)
        self.assertEqual([], dying.stat_calls)
        self.assertEqual([], tile.stat_calls)
        self.assertEqual(1, len(actions))
        self.assertEqual('bonus', actions[0].unit.nid)
        self.assertTrue(all(entry.skill_obj.nid == 'Chill_Speed_T2_Effect' for entry in actions))
        self.assertTrue(all(entry.initiator is source for entry in actions))

        component = self._component()
        less_penalized = RuntimeUnit('less_penalized', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': -1, 'DEF': 0, 'RES': 0})
        more_penalized = RuntimeUnit('more_penalized', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': -3, 'DEF': 0, 'RES': 0})
        _, _, actions = self._run_upkeep(component, [less_penalized, more_penalized])
        self.assertEqual(['less_penalized'], [entry.unit.nid for entry in actions])

    def test_real_team_relationships_select_only_foes_for_each_chill_owner(self):
        expected_foes = {
            'player': {'enemy', 'enemy2'},
            'enemy': {'player', 'enemy2', 'other'},
            'enemy2': {'player', 'enemy', 'other'},
        }
        for owner_team, foes in expected_foes.items():
            with self.subTest(owner_team=owner_team):
                component = self._component()
                source = RuntimeUnit(f'source_{owner_team}', owner_team, {stat: 0 for stat in STATS})
                source.skills = [self._owner_skill(component)]
                candidates = {
                    team: RuntimeUnit(
                        f'candidate_{team}', team,
                        {'STR': 0, 'MAG': 0, 'SPD': 10, 'DEF': 0, 'RES': 0})
                    for team in ('player', 'enemy', 'enemy2', 'other')
                }
                actions = []
                with patch.object(self.custom_components, 'game', FieldGame([source, *candidates.values()])):
                    component.on_upkeep(actions, [], source)

                self.assertEqual(1, len(actions))
                self.assertIn(actions[0].unit.team, foes)
                self.assertTrue(all(entry.unit is not source for entry in actions))
                self.assertEqual([], source.stat_calls)
                for team, candidate in candidates.items():
                    expected_calls = ['SPD'] if team in foes else []
                    self.assertEqual(expected_calls, candidate.stat_calls)

    def test_empty_field_and_higher_same_stat_rank_do_not_add_status(self):
        component = self._component()
        _, _, actions = self._run_upkeep(component, [])
        self.assertEqual([], actions)

        lower = self._component(rank=1, status='Chill_Speed_T1_Effect')
        higher = self._component(rank=3, status='Chill_Speed_T3_Effect')
        source = RuntimeUnit('source', 'player', {stat: 0 for stat in STATS})
        source.skills = [self._owner_skill(lower), self._owner_skill(higher)]
        foe = RuntimeUnit('foe', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 1, 'DEF': 0, 'RES': 0})
        actions = []
        with patch.object(self.custom_components, 'game', FieldGame([foe])), \
                patch.object(self.custom_components.skill_system, 'check_enemy', return_value=True):
            lower.on_upkeep(actions, [], source)
            higher.on_upkeep(actions, [], source)
        self.assertEqual(1, len(actions))
        self.assertEqual('Chill_Speed_T3_Effect', actions[0].skill_obj.nid)

    def test_real_status_add_survives_combat_and_is_removed_at_own_endstep(self):
        component = self._component()
        target = RuntimeUnit('target', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 5, 'DEF': 0, 'RES': 0})
        source, _, actions = self._run_upkeep(component, [target])
        self.assertEqual(1, len(actions))

        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), patch.object(game, 'skill_registry', {}):
            actions[0].reset_action = NoOpResetUnitVars(target)
            actions[0].do()
            effect = actions[0].skill_obj
            self.assertIn(effect, target.skills)

            skill_system.cleanup_combat([], target, None, source, None, 'defense')
            skill_system.post_combat([], target, None, source, None, 'defense')
            self.assertIn(effect, target.skills)

            endstep_actions = []
            skill_system.on_endstep(endstep_actions, [], target)
            self.assertEqual(1, len(endstep_actions))
            endstep_actions[0].do()
            self.assertNotIn(effect, target.skills)

    def test_effect_is_removed_at_end_chapter(self):
        component = self._component()
        target = RuntimeUnit('target', 'enemy', {'STR': 0, 'MAG': 0, 'SPD': 5, 'DEF': 0, 'RES': 0})
        _, _, actions = self._run_upkeep(component, [target])

        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars), patch.object(game, 'skill_registry', {}):
            actions[0].reset_action = NoOpResetUnitVars(target)
            actions[0].do()
            effect = actions[0].skill_obj
            self.assertIn(effect, target.skills)
            with self.assertLogs(level='WARNING') as warnings, \
                    patch.object(action, 'do', side_effect=lambda queued_action: queued_action.do()):
                skill_system.on_end_chapter(target, effect)
            self.assertNotIn(effect, target.skills)
            self.assertIn('not in', warnings.output[0])


if __name__ == '__main__':
    import unittest
    unittest.main()
