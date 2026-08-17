import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


@dataclass(eq=False)
class MockSkill:
    nid: str
    uid: int
    components: list
    active: bool = True


@dataclass(eq=False)
class MockUnit:
    nid: str
    team: str
    position: tuple | None = (0, 0)
    hp: int = 20
    stat_bonuses: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)

    def get_hp(self):
        return self.hp

    def stat_bonus(self, stat_nid):
        return self.stat_bonuses.get(stat_nid, 0)


class FeintFamilyTests(TestCase):
    STATS = {
        'Strength': 'STR',
        'Magic': 'MAG',
        'Speed': 'SPD',
        'Defense': 'DEF',
        'Resistance': 'RES',
    }
    TIER_PENALTIES = {1: 3, 2: 5, 3: 7}

    @classmethod
    def setUpClass(cls):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skill_file:
            cls.skill_data = {skill['nid']: skill for skill in json.load(skill_file)}
        with open(PROJECT / 'game_data' / 'items.json', encoding='utf-8') as item_file:
            cls.item_data = {item['nid']: item for item in json.load(item_file)}
        with open(PROJECT / 'game_data' / 'skills.category.json', encoding='utf-8') as category_file:
            cls.categories = json.load(category_file)

        skill_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        skill_spec = importlib.util.spec_from_file_location('feint_test_custom_skills', skill_path)
        cls.custom_skills = importlib.util.module_from_spec(skill_spec)
        skill_spec.loader.exec_module(cls.custom_skills)

        item_path = PROJECT / 'resources' / 'custom_components' / 'custom_item_components.py'
        item_spec = importlib.util.spec_from_file_location('feint_test_custom_items', item_path)
        cls.custom_items = importlib.util.module_from_spec(item_spec)
        item_spec.loader.exec_module(cls.custom_items)

    def _feint(self, stat, effect, priority=0, uid=100):
        component = self.custom_skills.Feint({'stat': stat, 'effect': effect})
        priority_component = SimpleNamespace(nid='priority', value=priority)
        skill = MockSkill('Feint_%s_%s' % (stat, uid), uid,
                          [priority_component, component])
        component.skill = skill
        return component, skill

    def _resolve(self, rally, actor, target, units):
        added = []

        def add_skill(foe, effect, owner):
            return (foe, effect, owner)

        with patch.object(self.custom_items, 'game', SimpleNamespace(units=units)), \
             patch.object(self.custom_items.skill_system, 'check_ally',
                          lambda unit, other: unit.team == other.team), \
             patch.object(self.custom_items.skill_system, 'check_enemy',
                          lambda unit, other: unit.team != other.team), \
             patch.object(self.custom_items.skill_system, 'condition',
                          lambda skill, unit: skill.active), \
             patch.object(self.custom_items.action, 'AddSkill', add_skill), \
             patch.object(self.custom_items.action, 'do', added.append):
            rally.start_combat([], actor, None, target, None, 'attack')
            rally.on_hit([], [], actor, None, target, None, target.position,
                         'attack', (0, 0))
            rally.end_combat([], actor, None, target, None, 'attack')
        return added

    def test_data_contains_all_feint_parents_effects_and_categories(self):
        for name, stat in self.STATS.items():
            for tier, penalty in self.TIER_PENALTIES.items():
                with self.subTest(name=name, tier=tier):
                    nid = '%s_Feint_T%d' % (name, tier)
                    effect_nid = '%s_Effect' % nid
                    parent_components = dict(self.skill_data[nid]['components'])
                    effect_components = dict(self.skill_data[effect_nid]['components'])
                    self.assertEqual({'stat': stat, 'effect': effect_nid},
                                     parent_components['feint'])
                    self.assertEqual(tier - 1, parent_components['priority'])
                    self.assertEqual([[stat, -penalty]], effect_components['stat_change'])
                    self.assertEqual({
                        'lost_on_self': True,
                        'lost_on_ally': True,
                        'lost_on_enemy': True,
                        'lost_on_splash': True,
                        'only_if_initiated': False,
                    }, effect_components['lost_on_end_combat2'])
                    self.assertIn('lost_on_next_action', effect_components)
                    self.assertIn('lost_on_end_chapter', effect_components)
                    self.assertEqual('Skill System Slot B/Feint Family',
                                     self.categories[nid])
                    self.assertEqual('Skill System Slot B/Feint Family',
                                     self.categories[effect_nid])

    def test_component_contracts_use_stat_and_effect_options(self):
        self.assertEqual({
            'stat': self.custom_skills.ComponentType.Stat,
            'effect': self.custom_skills.ComponentType.Skill,
        }, self.custom_skills.Feint.options)
        self.assertEqual('feint', self.custom_skills.Feint.nid)
        self.assertEqual('lost_on_next_action', self.custom_skills.LostOnNextAction.nid)
        self.assertEqual('rally_assist', self.custom_items.RallyAssist.nid)

    def test_effect_tiers_suppress_weaker_same_stat_effects(self):
        for name in self.STATS:
            t1 = dict(self.skill_data['%s_Feint_T1_Effect' % name]['components'])
            t2 = dict(self.skill_data['%s_Feint_T2_Effect' % name]['components'])
            t3 = dict(self.skill_data['%s_Feint_T3_Effect' % name]['components'])
            self.assertEqual(
                "not has_skill(unit, '%s_Feint_T2_Effect') and not has_skill(unit, '%s_Feint_T3_Effect')" % (name, name),
                t1['condition'])
            self.assertEqual("not has_skill(unit, '%s_Feint_T3_Effect')" % name,
                             t2['condition'])
            self.assertNotIn('condition', t3)
            self.assertIn('hidden_if_inactive', t1)
            self.assertIn('hidden_if_inactive', t2)

    def test_internal_rally_is_the_only_feint_trigger_item(self):
        components = dict(self.item_data['Internal_Rally_Feint_Test']['components'])
        self.assertEqual('Rally (Feint Test)', self.item_data['Internal_Rally_Feint_Test']['name'])
        self.assertEqual(1, components['min_range'])
        self.assertEqual(1, components['max_range'])
        self.assertTrue({'spell', 'target_ally', 'rally_assist', 'no_ai'} <= set(components))
        marked = {nid for nid, item in self.item_data.items()
                  if 'rally_assist' in dict(item['components'])}
        self.assertEqual({'Internal_Rally_Feint_Test'}, marked)
        for nid in ('Heal', 'Mend', 'Barrier'):
            self.assertNotIn('rally_assist', dict(self.item_data[nid]['components']))

    def test_rally_resolves_for_actor_and_recipient(self):
        actor_component, actor_skill = self._feint('STR', 'Actor_Effect', uid=10)
        target_component, target_skill = self._feint('MAG', 'Target_Effect', uid=11)
        actor = MockUnit('actor', 'player', skills=[actor_skill])
        recipient = MockUnit('recipient', 'player', skills=[target_skill])
        foe = MockUnit('foe', 'enemy', stat_bonuses={'STR': 4, 'MAG': 5})

        added = self._resolve(self.custom_items.RallyAssist(), actor, recipient,
                              [actor, recipient, foe])
        self.assertEqual([(foe, 'Actor_Effect', actor),
                          (foe, 'Target_Effect', recipient)], added)

    def test_rally_uses_highest_priority_same_stat_and_uid_tiebreak(self):
        low_component, low_skill = self._feint('SPD', 'Low', priority=0, uid=10)
        high_component, high_skill = self._feint('SPD', 'High', priority=2, uid=11)
        same_component, same_skill = self._feint('SPD', 'Uid_Wins', priority=2, uid=12)
        actor = MockUnit('actor', 'player', skills=[low_skill, high_skill, same_skill])
        recipient = MockUnit('recipient', 'player')
        foe = MockUnit('foe', 'enemy', stat_bonuses={'SPD': 1})

        added = self._resolve(self.custom_items.RallyAssist(), actor, recipient,
                              [actor, recipient, foe])
        self.assertEqual([(foe, 'Uid_Wins', actor)], added)

    def test_rally_targets_highest_positive_bonus_and_keeps_first_tie(self):
        component, skill = self._feint('DEF', 'Defense_Effect')
        actor = MockUnit('actor', 'player', skills=[skill])
        recipient = MockUnit('recipient', 'player')
        first_tie = MockUnit('first', 'enemy', stat_bonuses={'DEF': 5})
        second_tie = MockUnit('second', 'enemy', stat_bonuses={'DEF': 5})
        raw_stat_only = MockUnit('raw', 'enemy', stat_bonuses={'DEF': 4},
                                 stats={'DEF': 99})

        added = self._resolve(self.custom_items.RallyAssist(), actor, recipient,
                              [actor, recipient, raw_stat_only, first_tie, second_tie])
        self.assertEqual([(first_tie, 'Defense_Effect', actor)], added)

    def test_rally_skips_no_bonus_allies_dead_and_off_map_units(self):
        component, skill = self._feint('RES', 'Resistance_Effect')
        actor = MockUnit('actor', 'player', skills=[skill])
        recipient = MockUnit('recipient', 'player')
        no_bonus = MockUnit('none', 'enemy', stat_bonuses={'RES': 0})
        negative = MockUnit('negative', 'enemy', stat_bonuses={'RES': -2})
        ally = MockUnit('ally', 'player', stat_bonuses={'RES': 9})
        dead = MockUnit('dead', 'enemy', hp=0, stat_bonuses={'RES': 10})
        off_map = MockUnit('off_map', 'enemy', position=None, stat_bonuses={'RES': 11})

        added = self._resolve(self.custom_items.RallyAssist(), actor, recipient,
                              [actor, recipient, no_bonus, negative, ally, dead, off_map])
        self.assertEqual([], added)

    def test_rally_requires_successful_ally_hit_and_deduplicates_owner(self):
        component, skill = self._feint('STR', 'Effect')
        actor = MockUnit('actor', 'player', skills=[skill])
        foe = MockUnit('foe', 'enemy', stat_bonuses={'STR': 3})
        rally = self.custom_items.RallyAssist()
        added = []
        with patch.object(self.custom_items, 'game',
                          SimpleNamespace(units=[actor, foe])), \
             patch.object(self.custom_items.skill_system, 'check_ally',
                          lambda unit, other: unit.team == other.team), \
             patch.object(self.custom_items.skill_system, 'check_enemy',
                          lambda unit, other: unit.team != other.team), \
             patch.object(self.custom_items.skill_system, 'condition',
                          lambda skill, unit: True), \
             patch.object(self.custom_items.action, 'AddSkill',
                          lambda target, effect, owner: (target, effect, owner)), \
             patch.object(self.custom_items.action, 'do', added.append):
            rally.start_combat([], actor, None, foe, None, 'attack')
            rally.on_hit([], [], actor, None, foe, None, foe.position,
                         'attack', (0, 0))
            rally.end_combat([], actor, None, foe, None, 'attack')
            self.assertEqual([], added)

            rally.start_combat([], actor, None, actor, None, 'attack')
            rally.on_hit([], [], actor, None, actor, None, actor.position,
                         'attack', (0, 0))
            rally.end_combat([], actor, None, actor, None, 'attack')
        self.assertEqual([(foe, 'Effect', actor)], added)

    def test_rally_clears_temporary_hits_when_feint_resolution_raises(self):
        actor = MockUnit('actor', 'player')
        recipient = MockUnit('recipient', 'player')
        rally = self.custom_items.RallyAssist()

        with patch.object(self.custom_items.skill_system, 'check_ally',
                          lambda unit, other: unit.team == other.team), \
             patch.object(self.custom_items.RallyAssist, '_resolve_feints',
                          side_effect=RuntimeError('resolver failed')):
            rally.start_combat([], actor, None, recipient, None, 'attack')
            rally.on_hit([], [], actor, None, recipient, None,
                         recipient.position, 'attack', (0, 0))
            with self.assertRaisesRegex(RuntimeError, 'resolver failed'):
                rally.end_combat([], actor, None, recipient, None, 'attack')

        self.assertEqual([], rally._hit_targets)

    def test_lost_on_next_action_removes_the_effect_and_cleans_up_chapter_end(self):
        component = self.custom_skills.LostOnNextAction()
        skill = MockSkill('Effect', 100, [component])
        component.skill = skill
        unit = MockUnit('foe', 'enemy', skills=[skill])
        removed = []
        with patch.object(self.custom_skills.action, 'RemoveSkill',
                          lambda target, effect: (target, effect)), \
             patch.object(self.custom_skills.action, 'do', removed.append):
            component.on_wait(unit, True)
            component.on_end_chapter_unconditional(unit, skill)
        self.assertEqual([(unit, skill), (unit, skill)], removed)
