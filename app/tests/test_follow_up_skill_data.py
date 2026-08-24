import json
from collections import Counter
from pathlib import Path
from unittest import TestCase

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class FollowUpSkillDataTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.categories = json.loads((PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}

    def test_migration_replaces_legacy_follow_up_components(self):
        inventory = Counter(
            component[0]
            for skill in self.skills
            for component in skill['components']
        )

        # Field Archery and Mobile Ballistics are approved Class Skill
        # follow-up grants in addition to the Slot B migration inventory.
        self.assertEqual(41, inventory['dynamic_attacks'])
        self.assertEqual("1 if mode == 'attack' else 0",
                         dict(self.by_nid['Field_Archery_T2']['components'])['dynamic_attacks'])
        self.assertEqual("1 if mode == 'attack' else 0",
                         dict(self.by_nid['Mobile_Ballistics_T3']['components'])['dynamic_attacks'])
        self.assertEqual("1 if mode == 'attack' else 0",
                         dict(self.by_nid['Mobile_Ballistics_T4']['components'])['dynamic_attacks'])
        self.assertEqual(11, inventory['dynamic_early_attacks'])
        # Hunter Instinct T3 and the temporary Air Superiority magic block are
        # approved Class Skill blanket foe blocks.
        self.assertEqual(18, inventory['prevent_foe_follow_up'])
        self.assertIn('prevent_foe_follow_up',
                      dict(self.by_nid['Hunter_Instinct_T3']['components']))
        self.assertEqual(18, inventory['prevent_foe_natural_follow_up'])
        self.assertEqual(6, inventory['prevent_self_follow_up'])
        self.assertEqual(10, inventory['neutralize_follow_up_prevention'])
        self.assertEqual(7, inventory['neutralize_foe_follow_up_grants'])
        self.assertEqual(1, inventory['cannot_double'])
        for legacy in ('desperation', 'Target_cannot_double', 'no_dynamic_attacks',
                       'negate_no_dynamic_attacks', 'NEGATE_cannot_double'):
            self.assertEqual(0, inventory[legacy], legacy)

    def test_alternating_follow_up_uses_additive_grant_and_blanket_foe_block(self):
        for nid in ('Odd_Follow_Up_T1', 'Odd_Follow_Up_T2', 'Odd_Follow_Up_T3',
                    'Even_Follow_Up_T1', 'Even_Follow_Up_T2', 'Even_Follow_Up_T3'):
            with self.subTest(nid=nid):
                components = dict(self.by_nid[nid]['components'])
                self.assertEqual('1', components['dynamic_attacks'])
                self.assertIn('prevent_foe_follow_up', components)

    def test_early_follow_up_families_no_longer_enable_global_desperation(self):
        early = ('Desperation_T1', 'Desperation_T2', 'Desperation_T3', 'Desperation_T4',
                 'Aerial_Assault_T1', 'Aerial_Assault_T2', 'Aerial_Assault_T3', 'Aerial_Assault_T4',
                 'Daring_Fighter_T1_Effect', 'Daring_Fighter_T2_Effect', 'Daring_Fighter_T3_Effect')
        for nid in early:
            with self.subTest(nid=nid):
                components = dict(self.by_nid[nid]['components'])
                self.assertEqual('1', components['dynamic_early_attacks'])
                self.assertNotIn('dynamic_attacks', components)
                self.assertNotIn('desperation', components)

    def test_runtime_loads_new_component_contracts_and_corrected_data(self):
        self.assertIn('prevent_foe_follow_up', [component.nid for component in DB.skills.get('Even_Follow_Up_T3').components])
        self.assertIn('dynamic_early_attacks', [component.nid for component in DB.skills.get('Desperation_T3').components])
        self.assertIn('prevent_self_follow_up', [component.nid for component in DB.skills.get('Cannot_Double').components])
        self.assertEqual('Skill System Slot B/Strike Family', self.categories['Vantage_T1_Hide'])
        for nid in ('Wary_Fighter_T1', 'Wary_Fighter_T2', 'Wary_Fighter_T3'):
            condition = dict(self.by_nid[nid]['components'])['combat_condition']
            self.assertIn('>', condition)
            self.assertNotIn('>=', condition)


if __name__ == '__main__':
    import unittest
    unittest.main()
