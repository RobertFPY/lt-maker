import importlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import action, skill_component_access, skill_system
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Opening Family'
STATS = ('STR', 'MAG', 'SPD', 'DEF', 'RES')
PREFIXES = {
    'STR': 'Strength',
    'MAG': 'Magic',
    'SPD': 'Speed',
    'DEF': 'Defense',
    'RES': 'Resistance',
}


class RuntimeUnit:
    def __init__(self, nid, team, stat_values, position=(0, 0), tags=()):
        self.nid = nid
        self.team = team
        self.stat_values = stat_values
        self.position = position
        self.tags = set(tags)
        self.skills = []
        self.equipped_weapon = None
        self.dead = False
        self.is_dying = False
        self.hp = 20

    @property
    def all_skills(self):
        return self.skills

    def get_stat(self, stat):
        return self.stat_values[stat]

    def get_hp(self):
        return self.hp

    def set_hp(self, hp):
        self.hp = hp

    def get_mana(self):
        return 0

    def set_mana(self, mana):
        pass

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


class OpeningFamilyTests(TestCase):
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
        return dict(OpeningFamilyTests.skills[skill]['components'])

    def test_static_contract_has_fifteen_ranked_parents_and_effects(self):
        parents = [nid for nid, category in self.categories.items()
                   if category == FAMILY and not nid.endswith('_Effect')]
        effects = [nid for nid, category in self.categories.items()
                   if category == FAMILY and nid.endswith('_Effect')]
        self.assertEqual(15, len(parents))
        self.assertEqual(15, len(effects))
        for stat, prefix in PREFIXES.items():
            for rank, value in ((1, 3), (2, 4), (3, 5)):
                parent_nid = f'{prefix}_Opening_T{rank}'
                effect_nid = f'{parent_nid}_Effect'
                parent = self._components(parent_nid)
                effect = self._components(effect_nid)
                self.assertEqual({'stat': stat, 'status': effect_nid, 'rank': rank},
                                 parent['opening_highest_stat'])
                self.assertEqual([[stat, value]], effect['stat_change'])
                self.assertEqual({'group': f'opening:{stat}', 'rank': rank},
                                 effect['exclusive_upkeep_effect'])
                self.assertIn('hidden', effect)
                self.assertIn('lost_on_endstep', effect)
                self.assertIn('lost_on_end_chapter', effect)
                if rank < 3:
                    higher = ' and '.join(
                        f"not has_skill(unit, '{prefix}_Opening_T{other}_Effect')"
                        for other in range(rank + 1, 4))
                    self.assertEqual(higher, effect['condition'])
                else:
                    self.assertNotIn('condition', effect)

    def test_component_groups_all_ties_and_filters_to_valid_allies_excluding_user(self):
        component = self.custom_components.OpeningHighestStat({
            'stat': 'STR', 'status': 'Strength_Opening_T3_Effect', 'rank': 3,
        })
        values = {stat: 0 for stat in STATS}
        source = RuntimeUnit('source', 'player', values | {'STR': 99})
        top_one = RuntimeUnit('top_one', 'player', values | {'STR': 20})
        top_two = RuntimeUnit('top_two', 'player', values | {'STR': 20})
        lower = RuntimeUnit('lower', 'player', values | {'STR': 18})
        enemy = RuntimeUnit('enemy', 'enemy', values | {'STR': 40})
        off_map = RuntimeUnit('off_map', 'player', values | {'STR': 50}, position=None)
        dead = RuntimeUnit('dead', 'player', values | {'STR': 50})
        dead.dead = True
        tile = RuntimeUnit('tile', 'player', values | {'STR': 50}, tags=('Tile',))
        with patch.object(self.custom_components, 'game', FieldGame(
                [source, top_one, top_two, lower, enemy, off_map, dead, tile])), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: owner.team == target.team):
            request = component.ranked_upkeep_request(source)

        self.assertEqual([top_one, top_two, lower], request.targets)
        self.assertEqual([[top_one, top_two], [lower]], request.target_bands)
        self.assertEqual('opening:STR', request.group)

    def test_component_is_restored_after_resources_then_database_load(self):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        self.assertIsNotNone(skill_component_access.get_component('opening_highest_stat'))
        self.assertIsNotNone(DB.skills.get('Strength_Opening_T3_Effect'))

    def test_higher_rank_claims_top_tie_then_lower_rank_claims_next_band_and_stats_are_independent(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext

        values = {stat: 0 for stat in STATS}
        high_source = RuntimeUnit('high_source', 'player', values)
        low_source = RuntimeUnit('low_source', 'player', values)
        top_one = RuntimeUnit('top_one', 'player', values | {'STR': 20, 'MAG': 20})
        top_two = RuntimeUnit('top_two', 'player', values | {'STR': 20, 'MAG': 20})
        lower = RuntimeUnit('lower', 'player', values | {'STR': 18, 'MAG': 10})
        high = self.custom_components.OpeningHighestStat({
            'stat': 'STR', 'status': 'Strength_Opening_T3_Effect', 'rank': 3,
        })
        low = self.custom_components.OpeningHighestStat({
            'stat': 'STR', 'status': 'Strength_Opening_T1_Effect', 'rank': 1,
        })
        magic = self.custom_components.OpeningHighestStat({
            'stat': 'MAG', 'status': 'Magic_Opening_T2_Effect', 'rank': 2,
        })
        with patch.object(self.custom_components, 'game', FieldGame(
                [high_source, low_source, top_one, top_two, lower])), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda owner, target: owner.team == target.team):
            requests = [low.ranked_upkeep_request(low_source),
                        high.ranked_upkeep_request(high_source),
                        magic.ranked_upkeep_request(low_source)]
        context = RankedUpkeepContext([low_source, high_source],
                                      [high_source, low_source, top_one, top_two, lower])
        context.plan(requests)

        self.assertEqual([top_one, top_two], context.targets_for(high_source, high))
        self.assertEqual([lower], context.targets_for(low_source, low))
        self.assertEqual([top_one, top_two], context.targets_for(low_source, magic))

    def test_effects_keep_only_highest_tier_bonus_and_expire_at_recipient_endstep(self):
        target = RuntimeUnit('target', 'player', {stat: 0 for stat in STATS})
        target.skills = [SkillObject.from_prefab(DB.skills.get(nid)) for nid in (
            'Strength_Opening_T1_Effect',
            'Strength_Opening_T2_Effect',
            'Strength_Opening_T3_Effect',
        )]
        self.assertEqual(5, skill_system.stat_change(target, 'STR'))

        queued = []
        with patch.object(action, 'ResetUnitVars', NoOpResetUnitVars):
            skill_system.on_endstep(queued, [], target)
            self.assertEqual(3, len(queued))
            for queued_action in queued:
                queued_action.do()
        self.assertEqual([], target.skills)


if __name__ == '__main__':
    import unittest
    unittest.main()
