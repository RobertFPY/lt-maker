import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.events import event_commands
from app.utilities import utils


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILIES = {
    'Strength': 'STR',
    'Magic': 'MAG',
    'Speed': 'SPD',
    'Defense': 'DEF',
    'Resistance': 'RES',
}
PENALTIES = {1: 3, 2: 5, 3: 7}
LIFETIME = {
    'lost_on_self': True,
    'lost_on_ally': True,
    'lost_on_enemy': True,
    'lost_on_splash': True,
    'only_if_initiated': False,
}


class Unit:
    def __init__(self, nid, team, position, hp, resistance):
        self.nid = nid
        self.team = team
        self.position = position
        self.hp = hp
        self.resistance = resistance

    def get_hp(self):
        return self.hp

    def get_stat(self, stat):
        if stat == 'RES':
            return self.resistance
        raise AssertionError(stat)


class Game:
    def __init__(self, units):
        self.units = units

    def get_unit(self, nid):
        return next(unit for unit in self.units if unit.nid == nid)


class OwnerRelativeTeams:
    @staticmethod
    def check_enemy(unit, other):
        return unit.team != other.team


class SabotageFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skill_file:
            cls.skills = {skill['nid']: skill for skill in json.load(skill_file)}
        with open(PROJECT / 'game_data' / 'events.json', encoding='utf-8') as event_file:
            cls.events = {event['nid']: event for event in json.load(event_file)}
        with open(PROJECT / 'game_data' / 'skills.category.json', encoding='utf-8') as category_file:
            cls.categories = json.load(category_file)

    def components(self, nid):
        return dict(self.skills[nid]['components'])

    def source(self, family):
        return self.events['Global SkillSabotage%s' % family]['_source']

    @staticmethod
    def event_expressions(source):
        loop = next(line for line in source if line.startswith('for;'))
        condition = next(line for line in source if line.startswith('if;'))
        return loop.split(';', 2)[2], condition.split(';', 1)[1]

    def test_parents_effects_and_categories_have_the_expected_contract(self):
        for family, stat in FAMILIES.items():
            with self.subTest(family=family):
                for tier, penalty in PENALTIES.items():
                    parent = 'Sabotage_%s_T%d' % (family, tier)
                    effect = '%s_Effect' % parent
                    self.assertEqual('Global SkillSabotage%s' % family,
                                     self.components(parent)['upkeep_event'])
                    self.assertEqual(tier - 1, self.components(parent)['priority'])
                    self.assertEqual([[stat, -penalty]],
                                     self.components(effect)['stat_change'])
                    self.assertEqual(LIFETIME,
                                     self.components(effect)['lost_on_end_combat2'])
                    self.assertIn('lost_on_next_action', self.components(effect))
                    self.assertIn('lost_on_end_chapter', self.components(effect))
                    self.assertNotIn('lost_on_endstep', self.components(effect))
                    self.assertEqual('Skill System Slot B/Sabotage Family',
                                     self.categories[parent])
                    self.assertEqual('Skill System Slot B/Sabotage Family',
                                     self.categories[effect])

    def test_events_parse_strictly_and_do_not_use_legacy_targeting(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                source = self.source(family)
                depth = 0
                for line in source:
                    command, error_index = event_commands.parse_text_to_command(line, strict=True)
                    self.assertIsNotNone(command, error_index)
                    if line.startswith('if;'):
                        depth += 1
                    elif line == 'end':
                        depth -= 1
                        self.assertGreaterEqual(depth, 0)
                self.assertEqual(0, depth)
                joined = '\n'.join(source)
                self.assertIn('game.units', joined)
                self.assertIn("get_stat('RES')", joined)
                self.assertIn('skill_system.check_enemy(unit, candidate)', joined)
                self.assertIn('utils.calculate_distance', joined)
                self.assertNotIn('game._current_level.units', joined)
                self.assertNotIn(".stats['RES']", joined)
                self.assertNotIn('get_enemies_within_distance', joined)

    def test_targeting_is_owner_relative_and_requires_exactly_one_space(self):
        owner = Unit('owner', 'player', (0, 0), 20, 10)
        enemy = Unit('enemy', 'enemy', (3, 3), 20, 6)
        enemy2 = Unit('enemy2', 'enemy2', (4, 3), 20, 7)
        equal_res = Unit('equal', 'enemy', (6, 3), 20, 7)
        player_ally = Unit('ally', 'player', (3, 4), 20, 1)
        dead = Unit('dead', 'enemy', (3, 2), 0, 1)
        off_map = Unit('off_map', 'enemy', None, 20, 1)
        game = Game([owner, enemy, enemy2, equal_res, player_ally, dead, off_map])
        namespace = {
            'game': game,
            'unit': owner,
            'skill_system': OwnerRelativeTeams,
            'utils': utils,
            'any': any,
        }

        for family in FAMILIES:
            with self.subTest(family=family):
                loop, condition = self.event_expressions(self.source(family))
                self.assertEqual(['enemy', 'enemy2', 'equal'], eval(loop, namespace))
                enemy_condition = condition.replace("'{loop_unit}'", "'enemy'")
                equal_condition = condition.replace("'{loop_unit}'", "'equal'")
                self.assertTrue(eval(enemy_condition, namespace))
                self.assertFalse(eval(equal_condition, namespace))

    def test_events_apply_only_the_strongest_effect_for_each_stat(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                source = '\n'.join(self.source(family))
                t1 = 'Sabotage_%s_T1_Effect' % family
                t2 = 'Sabotage_%s_T2_Effect' % family
                t3 = 'Sabotage_%s_T3_Effect' % family
                self.assertIn("has_skill(unit, 'Sabotage_%s_T3')" % family, source)
                self.assertIn("has_skill(unit, 'Sabotage_%s_T2')" % family, source)
                self.assertIn("has_skill(unit, 'Sabotage_%s_T1')" % family, source)
                self.assertIn('remove_skill;{loop_unit};%s;;no_banner' % t1, source)
                self.assertIn('remove_skill;{loop_unit};%s;;no_banner' % t2, source)
                self.assertIn('give_skill;{loop_unit};%s;;no_banner' % t3, source)
                self.assertIn('give_skill;{loop_unit};%s;;no_banner' % t2, source)
                self.assertIn('give_skill;{loop_unit};%s;;no_banner' % t1, source)
                self.assertNotIn('hidden_if_inactive', self.components(t1))
                self.assertNotIn('hidden_if_inactive', self.components(t2))
                self.assertNotIn('condition', self.components(t1))
                self.assertNotIn('condition', self.components(t2))


if __name__ == '__main__':
    unittest.main()
