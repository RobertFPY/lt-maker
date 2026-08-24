import json
from pathlib import Path
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class SpecialSkillDataTests(TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as source:
            cls.skills = {skill['nid']: skill for skill in json.load(source)}

    def components(self, nid):
        return dict(self.skills[nid]['components'])

    def test_special_skill_inventory_includes_supernova_and_project_extensions(self):
        special = [skill for skill in self.skills.values()
                   if 'special_skill' in dict(skill['components'])]
        self.assertEqual(57, len(special))
        self.assertIn('Supernova_Ultra', self.skills)
        self.assertIn('White_Sun_T4', self.skills)
        self.assertIn('Divine_Judgment_Ultra', self.skills)

    def test_defense_piercers_use_explicit_retained_defense_values(self):
        expected = {
            'New_Moon_Effect': 0.7,
            'Moonbow_Effect': 0.5,
            'Luna_Effect': 0.3,
            'Black_Luna_Effect': 0.0,
        }
        for nid, retained in expected.items():
            components = self.components(nid)
            self.assertEqual(retained, components['special_defense_multiplier'])
            self.assertNotIn('dynamic_damage', components)

    def test_defensive_specials_store_damage_received_multiplier(self):
        expected = {
            'Buckler_Effect': 0.7,
            'Escutcheon_Effect': 0.5,
            'Pasvise_Effect': 0.3,
            'Holy_Vestments_Effect': 0.7,
            'Sacred_Cowl_Effect': 0.5,
            'Aegis_Effect': 0.3,
        }
        for nid, multiplier in expected.items():
            components = self.components(nid)
            self.assertEqual(multiplier, components['resist_multiplier'])
            self.assertNotIn('self_nihil', components)

    def test_special_piercers_and_assassination_have_their_distinct_neutralizers(self):
        for nid in ('True_Strike_Effect', 'Assassination_Effect', 'Impale_Effect', 'Deadeye_Effect'):
            self.assertIn('neutralize_foe_damage_reduction', self.components(nid))
        self.assertIn('neutralize_foe_death_prevention', self.components('Assassination_Effect'))
        self.assertNotIn('neutralize_foe_death_prevention', self.components('True_Strike_Effect'))
        self.assertNotIn('self_nihil', self.components('Miracle_Effect'))

    def test_aether_astra_and_deadeye_data_contracts(self):
        aether = self.components('Aether_T4')['aether_proc']
        self.assertEqual(0.7, aether['defense_ignore_percent'])
        self.assertEqual(0.7, aether['lifelink'])
        self.assertFalse(self.components('Flash_T1')['astra_proc'].get('disable_crit', False))
        for nid in ('Phatasm_T2', 'Astra_T3', 'Stardust_Mirage_T4'):
            self.assertTrue(self.components(nid)['astra_proc']['disable_crit'])
        self.assertEqual('SKILL', self.components('Deadeye_Ultra')['proc_rate'])
        self.assertNotIn('lost_on_end_combat2', self.components('Deadeye_Effect_1'))

    def test_bane_and_fatal_wound_are_terminal_proc_strikes(self):
        for nid in ('Bane_Effect', 'Fatal_Wound_Effect'):
            self.assertIn('end_combat_after_strike', self.components(nid))
            self.assertNotIn('gain_on_strike', self.components(nid))
        self.assertNotIn('give_status_after_hit', self.components('Bane_Effect'))
        self.assertEqual(['Fatal_Wound_Effect_2'],
                         self.components('Fatal_Wound_Effect')['give_statuses_after_hit'])
        self.assertIn('lost_on_endstep', self.components('Fatal_Wound_Effect_2'))
        self.assertNotIn('lost_on_end_combat2', self.components('Fatal_Wound_Effect_2'))
        self.assertIn('block_hp_recovery', self.components('Fatal_Wound_Effect_2'))

    def test_special_data_uses_correct_proc_and_dragonskin_contracts(self):
        self.assertEqual('HALF_SKILL', self.components('Stardust_Mirage_T4')['proc_rate'])
        self.assertNotIn('self_nihil', self.components('Lethality_T2'))
        self.assertEqual('Lethality_Tag_Override',
                         self.components('Divine_Judgment_Effect')['item_override'])
        self.assertNotIn('dynamic_damage_multiplier',
                         self.components('Divine_Judgment_Effect'))
        self.assertIn("Divine_Judgment_Effect",
                      self.components('Dragonskin_T4')['combat_condition'])

    def test_dragon_proc_effects_add_current_pre_defense_attack(self):
        expected = {
            'Dragon_Gaze_Effect': (0.3, 0.30000000000000004),
            'Dragon_Fang_Effect': (0.5, 0.30000000000000004),
            'Dragonic_Aura_Effect': (0.7, 0.5),
        }
        for nid, (percent, lifelink) in expected.items():
            with self.subTest(nid=nid):
                components = self.components(nid)
                self.assertEqual(f'base_value*{percent}', components['dynamic_damage'])
                self.assertNotIn('damage_multiplier', components)
                self.assertEqual(lifelink, components['lifelink'])

    def test_moon_bow_display_names_change_without_nid_changes(self):
        self.assertEqual('Moon Bow', self.skills['Moonbow_T2']['name'])
        self.assertEqual('Moon Bow', self.skills['Moonbow_Effect']['name'])


if __name__ == '__main__':
    import unittest
    unittest.main()
