import json
from collections import Counter
from pathlib import Path
from unittest import TestCase

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class SlotASkillDataTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.categories = json.loads((PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}
        cls.slot_a = [skill for skill in cls.skills if 'slota_skill' in dict(skill['components'])]

    def components(self, nid):
        return dict(self.by_nid[nid]['components'])

    def test_static_slot_a_inventory(self):
        all_components = Counter(component[0] for skill in self.skills for component in skill['components'])
        faires = [skill for skill in self.slot_a if skill['nid'].endswith('faire_T1') or
                  skill['nid'].endswith('faire_T2') or skill['nid'].endswith('faire_T3')]
        fury = [skill for skill in self.slot_a if skill['nid'].startswith('Fury_')]
        self.assertEqual(137, len(self.slot_a))
        self.assertEqual(16, sum('Bond' in skill['nid'] for skill in self.slot_a))
        self.assertEqual(12, sum('Solo' in skill['nid'] for skill in self.slot_a))
        self.assertEqual(4, len(fury))
        self.assertEqual(18, len(faires))
        self.assertEqual(0, sum('hit' in dict(skill['components']) for skill in faires))
        self.assertEqual(18, sum('raw_damage' in dict(skill['components']) for skill in faires))
        self.assertEqual(0, sum('target.get_weapon()' in str(skill['components']) for skill in self.slot_a))
        self.assertEqual(0, sum('get_allies_within_distance' in str(skill['components']) for skill in self.slot_a))
        self.assertEqual(0, sum('better_post_combat_damage' in dict(skill['components']) for skill in fury))
        self.assertEqual(4, sum('recoil' in dict(skill['components']) for skill in fury))
        self.assertEqual(1, sum(skill['nid'] == 'Counter_T1' for skill in self.slot_a))
        self.assertEqual(1, sum('hidden' in dict(self.by_nid['Counter_Effect']['components']) for _ in [0]))
        self.assertEqual(0, sum('do_nothing' in dict(skill['components']) for skill in self.slot_a))
        self.assertEqual(0, sum(component is None for skill in DB.skills for component in skill.components))
        self.assertGreater(all_components['slota_skill'], 0)

    def test_bond_and_solo_use_combat_allies_without_counting_user(self):
        for skill in self.slot_a:
            nid = skill['nid']
            components = dict(skill['components'])
            if 'Bond' in nid:
                distance = 2 if nid.endswith('_T4') else 1
                self.assertEqual(
                    'len(get_combat_allies_within_distance(unit, %d)) > 0' % distance,
                    components['combat_condition'], nid)
            elif 'Solo' in nid:
                self.assertEqual('len(get_combat_allies_within_distance(unit, 1)) == 0',
                                 components['combat_condition'], nid)

    def test_actual_combat_item_is_used_for_magic_and_triangle_expressions(self):
        for skill in self.slot_a:
            text = str(skill['components'])
            self.assertNotIn('target.get_weapon()', text, skill['nid'])
        expected_magic = "item2 and item_funcs.is_magic_in_combat(target, item2, unit)"
        for nid in ('Armored_Blow_T1', 'Warding_Blow_T1', 'Earth_Boost_T1', 'Water_Boost_T1',
                    'Warding_Stance_T1', 'Steady_Stance_T1', 'Atk_Def_Bond_T1',
                    'Atk_Res_Bond_T1', 'Atk_Def_Solo_T1', 'Atk_Res_Solo_T1'):
            self.assertIn('is_magic_in_combat(target, item2, unit)', str(self.components(nid)), nid)
        for nid in ('Triangle_Adept_T1', 'Triangle_Adept_T2', 'Triangle_Adept_T3'):
            expression = self.components(nid)['dynamic_damage_multiplier']
            self.assertIn('compute_advantage(unit, target, item, item2)', expression)
            self.assertNotIn('target.get_weapon()', expression)
        self.assertIn(expected_magic, self.components('Warding_Blow_T1')['combat_condition'])

    def test_fury_fortress_and_life_and_death_contracts(self):
        for nid, damage in zip(('Fury_T1', 'Fury_T2', 'Fury_T3', 'Fury_T4'), (2, 4, 6, 8)):
            components = self.components(nid)
            self.assertEqual(damage, components['recoil'])
            self.assertNotIn('better_post_combat_damage', components)
        for nid in ('Fortress_Def_T2', 'Fortress_Def_T3'):
            self.assertIn(['STR', -3], self.components(nid)['stat_change'])
        for nid in ('Fortress_Res_T2', 'Fortress_Res_T3'):
            self.assertIn(['MAG', -3], self.components(nid)['stat_change'])
        life = self.components('Life_and_Death_T4')['stat_change']
        self.assertEqual([['STR', 7], ['MAG', 7], ['SPD', 7], ['DEF', -7], ['RES', -7]], life)
        self.assertIn('Str/Mag/Spd', self.by_nid['Life_and_Death_T4']['desc'])

    def test_stance_t4_keeps_crit_and_gates_only_resist_by_actual_damage_type(self):
        for nid in ('Warding_Stance_T4', 'Steady_Stance_T4'):
            components = self.components(nid)
            self.assertEqual("mode == 'defense'", components['combat_condition'])
            self.assertEqual(20, components['crit'])
            self.assertIn('6 if item2 and', components['dynamic_resist'])
            self.assertIn('is_magic_in_combat(target, item2, unit)', components['dynamic_resist'])
            self.assertNotIn('resist', components)

    def test_weapon_faire_is_damage_only_and_checks_the_used_item(self):
        types = {'Swordfaire': "'Sword'", 'Lancefaire': "'Lance'", 'Axefaire': "'Axe'",
                 'Bowfaire': "'Bow'", 'Knifefaire': "'Knife'", 'Tomefaire': "'Anima', 'Light', 'Dark'"}
        for prefix, expected_type in types.items():
            for tier, damage in zip((1, 2, 3), ('5', '10', '15')):
                nid = '%s_T%d' % (prefix, tier)
                skill = self.by_nid[nid]
                components = self.components(nid)
                self.assertEqual(damage, components['raw_damage'], nid)
                self.assertNotIn('hit', components, nid)
                self.assertIn('item and item_system.weapon_type(unit, item)', components['condition'], nid)
                self.assertIn(expected_type, components['condition'], nid)
                self.assertIn("'TrueDamage' not in item.tags", components['condition'], nid)
                self.assertNotIn('unit.get_weapon()', components['condition'], nid)
        self.assertEqual('Axefaire', self.by_nid['Axefaire_T3']['name'])
        self.assertEqual('Bowfaire', self.by_nid['Bowfaire_T3']['name'])
        self.assertIn('knives', self.by_nid['Knifefaire_T1']['desc'])

    def test_counter_is_slot_a_physical_close_range_only_and_effect_is_hidden(self):
        counter = self.components('Counter_T1')
        self.assertEqual(
            "item2 and not item_funcs.is_magic_in_combat(target, item2, unit) and 1 <= utils.calculate_distance(unit.position, target.position) <= 2",
            counter['combat_condition'])
        self.assertEqual('Counter_Effect', counter['give_status_before_combat'])
        self.assertEqual(['Dragonskin_T4'], counter['negated_by_skills'])
        effect = self.components('Counter_Effect')
        self.assertEqual(-1, effect['lifelink'])
        self.assertIn('hidden', effect)
        self.assertEqual('Hidden Game Mechanics', self.categories['Counter_Effect'])
        self.assertIn('lost_on_end_combat2', effect)

    def test_warding_blow_display_name_is_corrected_without_changing_nids(self):
        for tier in range(1, 5):
            self.assertEqual('Warding Blow', self.by_nid['Warding_Blow_T%d' % tier]['name'])


if __name__ == '__main__':
    import unittest
    unittest.main()
