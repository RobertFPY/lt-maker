import json
from collections import Counter
from pathlib import Path
from unittest import TestCase

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import skill_system
from app.engine.objects.item import ItemObject
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
BREAKER_FAMILIES = ('Sword', 'Lance', 'Axe', 'Bow', 'Dagger', 'Tome')
TOME_TYPES = ('Fire', 'Wind', 'Thunder', 'Water', 'Earth', 'Anima', 'Light', 'Dark')
MATCHING_ITEMS = {
    'Sword': 'Bronze_Sword',
    'Lance': 'Bronze_Lance',
    'Axe': 'Bronze_Axe',
    'Bow': 'Bronze_Bow',
    'Dagger': 'Knife',
    'Tome': 'Ember',
}
TOME_ITEMS = {
    'Fire': 'Ember',
    'Wind': 'Breeze',
    'Thunder': 'Spark',
    'Water': 'Splash',
    'Earth': 'Pebble',
    'Anima': 'Bolting',
    'Light': 'Ray',
    'Dark': 'Miasma',
}


class RuntimeUnit:
    def __init__(self, nid, hp=100, skills=()):
        self.nid = nid
        self.team = 'player'
        self.hp = hp
        self.max_hp = 100
        self.skills = list(skills)
        self.position = (0, 0)
        self.equipped_weapon = None

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp

    def get_weapon(self):
        return self.equipped_weapon


class BreakerFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))

    @staticmethod
    def _skill(nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    @staticmethod
    def _weapon(nid):
        return ItemObject.from_prefab(DB.items.get(nid))

    def test_breakers_use_normal_grants_and_natural_follow_up_prevention(self):
        for family in BREAKER_FAMILIES:
            for tier, threshold in enumerate((.9, .7, .5), 1):
                nid = f'{family}breaker_T{tier}'
                with self.subTest(nid=nid):
                    components = dict(self.by_nid[nid]['components'])
                    self.assertEqual('1', components['dynamic_attacks'])
                    self.assertIn('prevent_foe_natural_follow_up', components)
                    self.assertNotIn('prevent_foe_follow_up', components)
                    self.assertNotIn('dynamic_early_attacks', components)
                    self.assertNotIn('desperation', components)
                    self.assertIn(f"unit.get_hp() > unit.get_max_hp() * {threshold}",
                                  components['combat_condition'])
                    self.assertEqual('Skill System Slot B/Breaker Family', self.categories[nid])
                    self.assertIn('by Speed comparison', self.by_nid[nid]['desc'])

    def test_breaker_weapon_type_conditions_cover_dagger_and_all_tomes(self):
        for tier in (1, 2, 3):
            dagger = dict(self.by_nid[f'Daggerbreaker_T{tier}']['components'])['combat_condition']
            tome = dict(self.by_nid[f'Tomebreaker_T{tier}']['components'])['combat_condition']
            with self.subTest(nid=f'Daggerbreaker_T{tier}'):
                self.assertIn("item_system.weapon_type(target, item2) == 'Dagger'", dagger)
                self.assertNotIn("'Knife'", dagger)
            with self.subTest(nid=f'Tomebreaker_T{tier}'):
                self.assertIn(f"in {TOME_TYPES!r}", tome)
                self.assertNotIn("'Staff'", tome)
                self.assertNotIn("'Dragon'", tome)

    def test_breaker_component_inventory_and_runtime_restore(self):
        breaker_nids = [
            f'{family}breaker_T{tier}'
            for family in BREAKER_FAMILIES
            for tier in (1, 2, 3)
        ]
        inventory = Counter(
            component[0]
            for nid in breaker_nids
            for component in self.by_nid[nid]['components']
        )
        self.assertEqual(18, len(breaker_nids))
        self.assertEqual(18, inventory['dynamic_attacks'])
        self.assertEqual(18, inventory['prevent_foe_natural_follow_up'])
        self.assertEqual(0, inventory['prevent_foe_follow_up'])
        self.assertIn(
            'prevent_foe_natural_follow_up',
            [component.nid for component in DB.skills.get('Swordbreaker_T1').components],
        )

    def test_breakers_activate_strictly_above_hp_threshold_in_both_combat_modes(self):
        for family in BREAKER_FAMILIES:
            foe_item = self._weapon(MATCHING_ITEMS[family])
            for tier, threshold in enumerate((90, 70, 50), 1):
                nid = f'{family}breaker_T{tier}'
                with self.subTest(nid=nid):
                    at_threshold_skill = self._skill(nid)
                    at_threshold = RuntimeUnit('user', threshold, [at_threshold_skill])
                    foe = RuntimeUnit('foe')
                    skill_system.pre_combat(
                        [], at_threshold, None, foe, foe_item, 'attack')
                    self.assertFalse(skill_system.condition(at_threshold_skill, at_threshold))

                    for mode in ('attack', 'defense'):
                        skill = self._skill(nid)
                        unit = RuntimeUnit('user', threshold + 1, [skill])
                        skill_system.pre_combat([], unit, None, foe, foe_item, mode)
                        self.assertTrue(skill_system.condition(skill, unit))
                        self.assertEqual(1, skill_system.dynamic_attacks(
                            unit, None, foe, foe_item, mode, (0, 0), 0))
                        self.assertTrue(skill_system.prevent_foe_natural_follow_up(unit))

    def test_dagger_and_tome_breakers_accept_only_their_expected_weapon_types(self):
        foe = RuntimeUnit('foe')
        for weapon_type, item_nid in TOME_ITEMS.items():
            with self.subTest(weapon_type=weapon_type):
                skill = self._skill('Tomebreaker_T3')
                unit = RuntimeUnit('user', 100, [skill])
                skill_system.pre_combat([], unit, None, foe, self._weapon(item_nid), 'attack')
                self.assertTrue(skill_system.condition(skill, unit))

        for nid, item_nid in (
                ('Tomebreaker_T3', 'Heal'),
                ('Tomebreaker_T3', 'Bronze_Sword'),
                ('Daggerbreaker_T3', 'Bronze_Sword')):
            with self.subTest(nid=nid, item=item_nid):
                skill = self._skill(nid)
                unit = RuntimeUnit('user', 100, [skill])
                skill_system.pre_combat([], unit, None, foe, self._weapon(item_nid), 'attack')
                self.assertFalse(skill_system.condition(skill, unit))


if __name__ == '__main__':
    import unittest
    unittest.main()
