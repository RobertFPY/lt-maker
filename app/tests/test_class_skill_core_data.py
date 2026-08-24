import json
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import combat_calcs, skill_system
from app.engine.skill_components import advanced_components


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
SOURCE_ROWS = Path(__file__).with_name('data') / 'class_skill_source_rows.json'


class ClassSkillCoreDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        component_path = PROJECT / 'resources' / 'custom_components' / 'custom_skill_components.py'
        spec = importlib.util.spec_from_file_location(
            'golden_knight_class_skill_components', component_path)
        cls.custom_components = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.custom_components)
        skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in skills}
        raw_data = json.loads((PROJECT / 'game_data' / 'raw_data.json').read_text(encoding='utf-8'))
        class_data = next(record for record in raw_data if record['nid'] == 'ClassData')
        cls.class_skills = {record['nid']: record['Class'] for record in class_data['lovalue']}
        classes = json.loads((PROJECT / 'game_data' / 'classes.json').read_text(encoding='utf-8'))
        cls.classes = {klass['nid']: klass for klass in classes}
        items = json.loads((PROJECT / 'game_data' / 'items.json').read_text(encoding='utf-8'))
        cls.items = {item['nid']: item for item in items}
        cls.source_rows = json.loads(SOURCE_ROWS.read_text(encoding='utf-8'))

    def components(self, nid):
        return dict(self.by_nid[nid]['components'])

    def test_class_skill_source_manifest_counts_and_blank_rows_have_explicit_placeholders(self):
        self.assertEqual(221, len(self.source_rows))
        required = {'row', 'className', 'tier', 'skill', 'description',
                    'source_row', 'class_name', 'tier_label', 'rank',
                    'skill_name', 'class_nids', 'canonical_prefab_nid',
                    'mapping_status', 'implementation'}
        self.assertTrue(all(required <= set(row) for row in self.source_rows))
        described = [row for row in self.source_rows if row['description'].strip()]
        blank = [row for row in self.source_rows if not row['description'].strip()]
        self.assertEqual(186, len(described))
        self.assertEqual(35, len(blank))
        project_names = {skill['name'] for skill in self.by_nid.values()}
        self.assertEqual([], sorted({row['skill'] for row in blank} - project_names))
        blank_prefabs = [skill for skill in self.by_nid.values()
                         if skill['name'] in {row['skill'] for row in blank}]
        self.assertTrue(all('do_nothing' not in dict(skill['components'])
                            for skill in blank_prefabs))
        placeholders = [skill for skill in blank_prefabs
                        if 'class_source_placeholder' in dict(skill['components'])]
        self.assertEqual(31, len(placeholders))
        self.assertTrue(all(
            skill['desc'] == 'Effect pending: Class List has no description.'
            for skill in placeholders))

    def test_every_described_source_skill_has_a_named_non_placeholder_prefab(self):
        """The checked-in Class List manifest is a hard catalog contract."""
        described = {row['skill'] for row in self.source_rows if row['description'].strip()}
        by_name = {}
        for skill in self.by_nid.values():
            by_name.setdefault(skill['name'], []).append(skill)
        missing = sorted(name for name in described if name not in by_name)
        self.assertEqual([], missing)
        for name in described:
            prefabs = by_name[name]
            self.assertTrue(any('class_source_placeholder' not in dict(prefab['components'])
                                for prefab in prefabs), name)

    def test_source_manifest_is_a_complete_explicit_crosswalk(self):
        described = [row for row in self.source_rows if row['description'].strip()]
        mapped = [row for row in described if row['mapping_status'] == 'mapped']
        self.assertEqual(151, len(mapped))
        self.assertEqual(199, sum(len(row['class_nids']) for row in mapped))
        self.assertTrue(all(row['implementation'] == 'implemented' for row in described))
        self.assertTrue(all(
            (row['mapping_status'] == 'mapped') == bool(row['class_nids'])
            for row in self.source_rows))
        self.assertFalse(any(row['implementation'] == 'source_pending_mapping'
                             for row in described))

        aliases = {
            'Axe Rider': 'Axe Raider', 'Falcon Knight': 'Falcoknight',
            'Forest Knight': 'Ranger Knight', 'Figher': 'Fighter',
            'Rougue': 'Rogue',
        }
        def normalize(value):
            return ''.join(char.lower() for char in value if char.isalnum())
        for row in described:
            base = row['class_name'].removeprefix('Elite ')
            base = aliases.get(base, base)
            elite = row['class_name'].startswith('Elite ')
            candidates = []
            for nid in self.classes:
                base_nid = nid.removesuffix('_Elite')
                while True:
                    suffix = next((suffix for suffix in
                                   ('_Female', 'Female', '_Melee', 'Melee',
                                    '_Range', 'Range')
                                   if base_nid.endswith(suffix)), None)
                    if not suffix:
                        break
                    base_nid = base_nid[:-len(suffix)]
                if (normalize(base_nid) == normalize(base)
                        and ('_Elite' in nid) == elite
                        and not nid.endswith(('_Bandit', '_Gazabin'))):
                    candidates.append(nid)
            if row['mapping_status'] == 'class_absent':
                self.assertEqual([], candidates, row['class_name'])
            else:
                self.assertTrue(set(candidates).issubset(row['class_nids']),
                                row['class_name'])

        by_class = {row['class_name']: row for row in described}
        self.assertEqual(['Valkyria'], by_class['Valkyria']['class_nids'])
        self.assertEqual('Raid_of_the_Valkyria_T3',
                         by_class['Valkyria']['canonical_prefab_nid'])
        self.assertEqual(['Valkyria_Elite'], by_class['Elite Valkyria']['class_nids'])
        self.assertEqual('Raid_of_the_Valkyria_T4',
                         by_class['Elite Valkyria']['canonical_prefab_nid'])
        self.assertEqual(['TrueBlade', 'Tsukage'], by_class['Trueblade']['class_nids'])
        self.assertEqual('Passionate_Duelist_T3',
                         by_class['Trueblade']['canonical_prefab_nid'])
        self.assertEqual(['Swordmaster', 'SwordmasterFemale'],
                         by_class['Swordmaster']['class_nids'])
        self.assertEqual('Master_Duelist_Swordmaster_T2',
                         by_class['Swordmaster']['canonical_prefab_nid'])

    def test_every_source_row_canonical_prefab_exists(self):
        missing = sorted(
            row['canonical_prefab_nid'] for row in self.source_rows
            if row['canonical_prefab_nid'] not in self.by_nid)
        self.assertEqual([], missing)

    def test_mapped_class_data_uses_each_source_row_canonical_prefab(self):
        mismatches = sorted(
            (class_nid, self.class_skills.get(class_nid), row['canonical_prefab_nid'])
            for row in self.source_rows
            if row['mapping_status'] == 'mapped'
            for class_nid in row['class_nids']
            if self.class_skills.get(class_nid) != row['canonical_prefab_nid'])
        self.assertEqual([], mismatches)

    def test_repaired_class_assignments_keep_the_approved_tiers(self):
        expected = {
            'Bow_Rider': 'Precision_Volley_T1',
            'Axe_Raider_Elite': 'Battlecry_Charge_T2',
            'Sword_Rider_Elite': 'Rapid_Assault_T2',
            'Lance_Rider_Elite': 'Solid_Shield_T2',
            'Axe_Paladin_Elite': 'Warcry_Charge_T3',
            'Sword_Paladin_Elite': 'Swift_Raid_T3',
            'Lance_Paladin_Elite': 'Diamond_Formation_T3',
            'Bow_Paladin_Elite': 'Static_Volley_T3',
            'Great_Knight_Elite': 'Warcry_Charge_T4',
            'Glory_Knight_Elite': 'Swift_Raid_T4',
            'Duke_Knight_Elite': 'Diamond_Formation_T4',
            'Axe_Wyvern_Rider_Elite': 'Diving_Strike_T2',
            'Lance_Wyvern_Rider_Elite': 'Aerial_Armor_T2',
            'Axe_Wyvern_Knight_Elite': 'Crushing_Dive_T3',
            'Lance_Wyvern_Knight_Elite': 'Aerial_Guard_T3',
            'Axe_Wyvern_Lord_Elite': 'Sky_Strike_T3',
            'Lance_Wyvern_Lord_Elite': 'Sky_Guard_T3',
            'Archer_Elite': 'Deadeye_Discipline_T2',
            'Pegasus_Knight_Elite': 'Air_Raid_T2',
            'Falcoknight_Elite': 'Raid_of_the_Valkyria_T3',
            'Fighter': 'Calculated_Risk_T1',
            'Fighter_Female': 'Calculated_Risk_T1',
            'Warrior': 'Deadly_Wager_T2',
            'Reaver': 'Fatal_Gambit_T3',
            'Fighter_Elite': 'Deadly_Wager_T2',
            'Warrior_Elite': 'Fatal_Gambit_T3',
            'Mounted_Brigand': 'Howling_Charge_T2',
            'Mounted_Berserker': 'War_Cry_T3',
            'Druid_Elite': 'Hex_T2',
            'Necromancer_Elite': 'Path_of_the_Dammed_T3',
            'Mage_Elite': 'Forcus_Channelling_T2',
            'Wizard_Elite': 'Arcane_Burst_T3',
            'Sage_Elite': 'Omniscient_Arcane_T3',
        }
        self.assertEqual(expected, {nid: self.class_skills[nid] for nid in expected})

    def test_class_absent_rows_keep_real_parent_prefabs_without_class_assignment(self):
        class_absent = [row for row in self.source_rows
                        if row['mapping_status'] == 'class_absent']
        self.assertEqual(70, len(class_absent))
        self.assertTrue(all(not row['class_nids'] for row in class_absent))
        self.assertTrue(all(
            self.by_nid[row['canonical_prefab_nid']]['name'] == row['skill']
            and not row['canonical_prefab_nid'].endswith('_Effect')
            for row in class_absent))
        by_class = {row['class_name']: row for row in class_absent}
        self.assertEqual('Master_Duelist_Dread_Fighter_T3',
                         by_class['Dread Fighter']['canonical_prefab_nid'])
        self.assertEqual('Newborn_Dragon_Personal',
                         by_class['Villager (Martin)']['canonical_prefab_nid'])
        self.assertEqual('Wyvern_Force_Personal',
                         by_class['Wyvern Lord (Michalis)']['canonical_prefab_nid'])

    def test_corrected_class_skill_prefab_contracts(self):
        self.assertEqual(10, self.components('Magic_Has_No_Equal_T4')
                         ['class_initiator_first_attempt_damage'])
        self.assertNotIn('class_first_attempt_damage',
                         self.components('Magic_Has_No_Equal_T4'))
        self.assertEqual(
            {'ground_avoid': 15, 'first_attempt_damage': 10, 'isolated_spd': 5},
            self.components('Raid_of_the_Valkyria_T3')['class_raid_valkyria'])
        for nid in ('Arcane_Reprisal_T1', 'Arcane_Reprisal_T2',
                    'Arcane_Retort_T3', 'Arcane_Retort_T4'):
            self.assertIn('end of the next turn', self.by_nid[nid]['desc'], nid)
            self.assertNotIn('next action', self.by_nid[nid]['desc'], nid)
        self.assertEqual(20, self.components('Raid_of_the_Valkyria_T4')
                         ['class_raid_valkyria']['ground_avoid'])

        dutiful = self.components('Dutiful_Soldier_T3')
        self.assertEqual(6, dutiful['damage'])
        self.assertEqual(6, dutiful['resist'])
        self.assertNotIn('combat_condition', dutiful)
        dutiful_ally_effect = self.components(dutiful['aura'])
        self.assertEqual(6, dutiful_ally_effect['damage'])
        self.assertEqual(6, dutiful_ally_effect['resist'])
        self.assertNotIn('combat_condition', dutiful_ally_effect)

        for rank, hit, damage in ((3, 5, 6), (4, 10, 8)):
            parent = self.components(f'Apostate_Aura_T{rank}')
            effect = self.components(parent['hone_ally_status']['status'])
            self.assertEqual({'range': 1, 'required_tags': [],
                              'group': 'apostate_aura', 'rank': rank,
                              'status': f'Apostate_Aura_T{rank}_Effect'},
                             parent['hone_ally_status'])
            self.assertEqual(hit, effect['class_first_attempt_hit'])
            self.assertEqual(damage, effect['class_first_attempt_damage'])
            self.assertEqual({'group': 'hone:apostate_aura', 'rank': rank},
                             effect['exclusive_upkeep_effect'])
            self.assertIn('lost_on_endstep', effect)
            self.assertIn('lost_on_end_chapter', effect)
            self.assertIn('hidden', effect)

        for nid in ('Arcane_Reprisal_T1_Effect', 'Arcane_Reprisal_T2_Effect',
                    'Arcane_Retort_T3_Effect', 'Arcane_Retort_T4_Effect'):
            effect = self.components(nid)
            self.assertNotIn('lost_on_next_action', effect)
            self.assertEqual(2, effect['end_time'])
            self.assertIn('lost_on_end_chapter', effect)

    def test_available_elite_class_mappings_use_their_source_prefabs(self):
        expected = {
            'Axe_Marshall_Elite_Melee': 'Grand_Breach_T4',
            'Axe_Marshall_Elite_Range': 'Grand_Breach_T4',
            'Lance_Marshall_Elite_Melee': 'Imperial_Phalanx_T4',
            'Lance_Marshall_Elite_Range': 'Imperial_Phalanx_T4',
            'Sword_Marshall_Elite_Melee': 'Aegis_Doctrine_T4',
            'Sword_Marshall_Elite_Range': 'Aegis_Doctrine_T4',
            'Axe_Dragon_Knight_Elite': 'Crushing_Dive_T4',
            'Lance_Dragon_Knight_Elite': 'Aerial_Guard_T4',
            'Lance_Dragon_Lord_Elite': 'Dragon_Guard_T4',
            'Marksman_Elite': 'Longbow_Mastery_T4',
            'Reaver_Elite': 'All_In_T3',
            'Grand_Wizard_Elite': 'Magic_Has_No_Equal_T4',
            'Grand_Sage_Elite': 'Power_of_Knowledge_T4',
            'Pontifex_Elite': 'Sacred_Aura_T4',
            'Dark_Knight_Elite': 'Arcane_Retort_T4',
            'Sage_Knight_Elite': 'Grand_Arcane_Aegis_T4',
        }
        self.assertEqual(expected, {nid: self.class_skills[nid] for nid in expected})
        self.assertEqual(3, self.components('All_In_T3')['priority'])
        self.assertEqual(3, self.components('Dutiful_Soldier_T3')['priority'])

    def test_existing_physical_class_skill_values_match_class_list(self):
        roar_effect = self.components('Roar_T1')['give_status_before_combat']
        self.assertEqual([['DEF', -5]], self.components(roar_effect)['stat_change'])
        self.assertEqual([['STR', 4], ['SPD', -2]], self.components('Heavy_Blade_T1')['stat_change'])
        self.assertEqual([['STR', 6], ['SPD', -3]], self.components('Heavy_Blade_T2')['stat_change'])
        self.assertEqual([['STR', 8], ['SPD', -4]], self.components('Ultra_Heavy_Blade_T3')['stat_change'])

        for nid, bonus in (
                ('Sturdy_Stance_T1', 4),
                ('Sturdy_Stance_T2', 6),
                ('Sturdy_Formation_T3', 8)):
            components = self.components(nid)
            self.assertEqual(bonus, components['damage'], nid)
            self.assertEqual(bonus, components['resist'], nid)
            self.assertEqual("mode == 'defense'", components['combat_condition'], nid)

        self.assertEqual(20, self.components('Duelist_Blow_T2')['avoid'])

    def test_thief_techniques_source_prefab_only_grants_listed_effects(self):
        components = self.components('Thief_Techniques_T1')
        self.assertEqual({'class_skill', 'class_skill2', 'locktouch', 'priority'}, set(components))

    def test_arcane_aegis_and_master_duelist_keep_their_intentional_name_contracts(self):
        aegis = self.by_nid['Arcane_Aegis_T2']
        aegis_plus = self.by_nid['Arcane_Aegis_T3']
        self.assertEqual('Arcane Aegis', aegis['name'])
        self.assertEqual('Arcane Aegis+', aegis_plus['name'])
        self.assertEqual(7, self.components('Arcane_Aegis_T2_Effect')['resist'])
        self.assertEqual(10, self.components('Arcane_Aegis_T3_Effect')['resist'])
        self.assertEqual("mode == 'defense'", self.components('Arcane_Aegis_T2_Effect')['combat_condition'])
        self.assertEqual("mode == 'defense'", self.components('Arcane_Aegis_T3_Effect')['combat_condition'])

        swordmaster = self.by_nid['Master_Duelist_Swordmaster_T2']
        dread_fighter = self.by_nid['Master_Duelist_Dread_Fighter_T3']
        self.assertEqual('Master Duelist', swordmaster['name'])
        self.assertEqual('Master Duelist', dread_fighter['name'])
        self.assertEqual(25, self.components(swordmaster['nid'])['avoid'])
        self.assertEqual(20, self.components(dread_fighter['nid'])['avoid'])
        self.assertEqual('Master_Duelist_Swordmaster_T2', self.class_skills['Swordmaster'])
        self.assertEqual('Master_Duelist_Swordmaster_T2', self.class_skills['SwordmasterFemale'])
        self.assertEqual('Arcane_Aegis_T2', self.class_skills['Mage_KnightFemale'])
        self.assertEqual('Arcane_Aegis_T3', self.class_skills['Sage_Knight'])

    def test_swordmaster_and_passionate_duelist_use_the_magic_sword_rules(self):
        components = self.components('Master_Duelist_Swordmaster_T2')
        self.assertIn('class_magic_sword_melee_crit', components)
        passionate = self.components('Passionate_Duelist_T3')
        self.assertIn('class_normal_sword_range', passionate)

    def test_magic_sword_rules_allow_melee_crit_and_block_ranged_normal_sword_crits(self):
        magic_sword = SimpleNamespace(magic=True, magic_at_range=False)
        normal_sword = SimpleNamespace(magic=False, magic_at_range=False)
        unit = SimpleNamespace(position=(0, 0))
        melee_target = SimpleNamespace(position=(1, 0))
        ranged_target = SimpleNamespace(position=(2, 0))
        magic_rule = self.custom_components.ClassMagicSwordMeleeCrit()
        normal_rule = self.custom_components.ClassNormalSwordRange()

        with patch.object(self.custom_components.item_system, 'weapon_type', return_value='Sword'):
            self.assertTrue(magic_rule.allow_critical(unit, magic_sword, melee_target))
            self.assertFalse(magic_rule.allow_critical(unit, magic_sword, ranged_target))
            self.assertEqual(1, normal_rule.modify_maximum_range(unit, normal_sword))
            self.assertTrue(normal_rule.prevent_critical(unit, normal_sword, ranged_target))
            self.assertFalse(normal_rule.prevent_critical(unit, normal_sword, melee_target))

    def test_crit_calculation_uses_the_new_allow_and_prevent_contracts(self):
        unit, target, item, item2 = object(), object(), object(), object()
        with patch.object(skill_system, 'prevent_critical', return_value=False), \
                patch.object(skill_system, 'allow_critical', return_value=True), \
                patch.object(combat_calcs, 'crit_accuracy', return_value=12) as crit_accuracy, \
                patch.object(combat_calcs, 'resolve_weapon', return_value=item2), \
                patch.object(combat_calcs, 'compute_advantage_attr', return_value=0), \
                patch.object(combat_calcs, 'get_support_rank_bonus', return_value=([], [])), \
                patch.object(combat_calcs, 'crit_avoid', return_value=0), \
                patch.object(combat_calcs.item_system, 'dynamic_crit_accuracy', return_value=0), \
                patch.object(skill_system, 'dynamic_crit_accuracy', return_value=0), \
                patch.object(skill_system, 'dynamic_crit_avoid', return_value=0), \
                patch.object(skill_system, 'crit_multiplier', return_value=1):
            self.assertEqual(12, combat_calcs.compute_crit(unit, target, item, item2, 'attack', (0, 0)))
        crit_accuracy.assert_called_once_with(unit, item, allow_without_item_crit=True)

        with patch.object(skill_system, 'prevent_critical', return_value=True):
            self.assertEqual(0, combat_calcs.compute_crit(unit, target, item, item2, 'attack', (0, 0)))

    def test_air_raid_first_attack_bonus_is_not_reused_by_brave_or_later_phases(self):
        component = self.custom_components.ClassFirstAttemptDamage(8)
        unit = target = item = item2 = object()
        self.assertEqual(8, component.raw_damage(unit, item, target, item2, 'attack', (0, 0), 0))
        self.assertEqual(0, component.raw_damage(unit, item, target, item2, 'attack', (0, 1), 0))
        self.assertEqual(0, component.raw_damage(unit, item, target, item2, 'attack', (1, 0), 0))
        self.assertEqual(8, self.components('Air_Raid_T2')['class_first_attempt_damage'])

    def test_light_blessing_uses_only_the_lowest_hp_adjacent_ally_at_upkeep(self):
        component = self.custom_components.ClassLowestHpAdjacentHeal(10)
        user = SimpleNamespace(position=(0, 0))
        first = SimpleNamespace(position=(1, 0), dead=False, is_dying=False, tags=(),
                                get_hp=lambda: 4, get_max_hp=lambda: 20, nid='first')
        second = SimpleNamespace(position=(0, 1), dead=False, is_dying=False, tags=(),
                                 get_hp=lambda: 4, get_max_hp=lambda: 20, nid='second')
        higher = SimpleNamespace(position=(1, 1), dead=False, is_dying=False, tags=(),
                                 get_hp=lambda: 9, get_max_hp=lambda: 20, nid='higher')
        with patch.object(self.custom_components.game, 'get_all_units', return_value=[user, first, second, higher]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
            self.assertIs(first, component._target(user))

        self.assertEqual(5, self.components('Light_Blessing_T1')['class_lowest_hp_adjacent_heal'])
        self.assertEqual(10, self.components('Light_Blessing_T2')['class_lowest_hp_adjacent_heal'])
        self.assertEqual(15, self.components('Divine_Blessing_T3')['class_lowest_hp_adjacent_heal'])

    def test_field_terrain_cost_only_reduces_terrain_already_traversable_by_user(self):
        component = self.custom_components.ClassTraversableTerrainCost()
        unit = SimpleNamespace(get_movement=lambda: 6)
        self.assertEqual(1, component.modify_movement_cost(unit, (0, 0), object(), 5))
        self.assertEqual(9, component.modify_movement_cost(unit, (0, 0), object(), 9))

    def test_field_puppet_prefabs_have_the_required_temporary_runtime_contract(self):
        for rank, movement in ((2, 6), (3, 9)):
            klass = self.classes[f'Class_Puppet_T{rank}']
            self.assertEqual(10, klass['bases']['HP'])
            self.assertEqual(movement, klass['bases']['MOV'])
            self.assertTrue(all(
                value == 0 for stat, value in klass['bases'].items()
                if stat not in ('HP', 'MOV')))
            self.assertEqual([], [entry for entry in klass['wexp_gain'].values()
                                  if entry[0]])
            self.assertIn([1, 'Class_Puppet_Explosion'], klass['learned_skills'])

            components = dict(self.items[f'Class_Puppet_T{rank}']['components'])
            self.assertEqual(
                {'class': f'Class_Puppet_T{rank}', 'movement': movement, 'rank': rank},
                components['class_puppet_summon'])

        explosion = self.components('Class_Puppet_Explosion')
        self.assertEqual(10, explosion['class_puppet_explosion'])
        self.assertIn('hidden', explosion)
        self.assertEqual('Field_Instinct_T1', self.class_skills['Hunter'])
        self.assertEqual('Field_Instinct_T1', self.class_skills['HunterFemale'])
        self.assertEqual('Class_Puppet_T2', self.components('Field_Examination_T2')['ability'])
        self.assertEqual('Class_Puppet_T3', self.components('Field_Specialist_T3')['ability'])

    def test_puppet_explosion_only_hits_adjacent_enemies_and_can_mark_them_for_death(self):
        component = self.custom_components.ClassPuppetExplosion(10)
        puppet = SimpleNamespace(position=(0, 0), dead=False, is_dying=False, tags=())
        adjacent_hp = [10]
        adjacent_foe = SimpleNamespace(position=(1, 0), dead=False, is_dying=False, tags=(),
                                       get_hp=lambda: adjacent_hp[0])
        distant_foe = SimpleNamespace(position=(2, 0), dead=False, is_dying=False, tags=(),
                                      get_hp=lambda: 10)
        ally = SimpleNamespace(position=(0, 1), dead=False, is_dying=False, tags=(),
                               get_hp=lambda: 10)
        changes = []
        def apply_change(act):
            changes.append(act)
            if act.unit is adjacent_foe:
                adjacent_hp[0] += act.num
        death = SimpleNamespace(should_die=lambda _target: None)
        with patch.object(self.custom_components.game, 'get_all_units',
                          return_value=[puppet, adjacent_foe, distant_foe, ally]), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda _unit, target: target in (adjacent_foe, distant_foe)), \
                patch.object(self.custom_components.action, 'do',
                             side_effect=apply_change), \
                patch.object(self.custom_components.game, 'death', death), \
                patch.object(death, 'should_die') as should_die:
            component.on_death(puppet)

        self.assertEqual(1, len(changes))
        self.assertIs(adjacent_foe, changes[0].unit)
        self.assertEqual(-10, changes[0].num)
        should_die.assert_called_once_with(adjacent_foe)

    def test_dark_gift_offers_the_healthiest_adjacent_ally_once_per_turn(self):
        component = self.custom_components.ClassDarkGiftIntercept(
            {'hp_threshold': 20, 'rank': 4, 'proc_rate_bonus': 5, 'heal_multiplier': 0.7})
        component.skill = SimpleNamespace(data={'save_intercept_last_turn': None})
        owner = SimpleNamespace(nid='owner', position=(0, 0), dead=False, is_dying=False,
                                tags=(), get_hp=lambda: 3, get_max_hp=lambda: 20)
        lower = SimpleNamespace(nid='lower', position=(1, 0), dead=False, is_dying=False,
                                tags=(), get_hp=lambda: 12, get_max_hp=lambda: 20)
        highest = SimpleNamespace(nid='highest', position=(0, 1), dead=False, is_dying=False,
                                  tags=(), get_hp=lambda: 18, get_max_hp=lambda: 20)
        with patch.object(self.custom_components.game, 'turncount', 7, create=True), \
                patch.object(self.custom_components.game, 'get_all_units',
                             return_value=[owner, lower, highest]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
            offer = component.save_intercept_offers(owner, object(), owner, object(), 2)
            self.assertIs(highest, offer.provider)
            self.assertEqual('any', offer.kind)
            self.assertFalse(offer.requires_armored)
            self.assertTrue(offer.consume_once_per_turn)
            self.assertEqual(5, component.modify_debuff_proc_rate(owner, highest))
            self.assertFalse(component.defines('modify_self_proc_rate'))
            self.assertEqual(0.7, component.heal_multiplier(owner, highest))
            component.skill.data['save_intercept_last_turn'] = 7
            self.assertIsNone(component.save_intercept_offers(owner, object(), owner, object(), 2))

    def test_dark_gift_is_debuff_only_and_has_four_source_tiers(self):
        with open(PROJECT / 'game_data' / 'skills.json', encoding='utf-8') as skills_file:
            skills = json.load(skills_file)
        dark_gifts = [skill for skill in skills if skill['nid'] in
                      ('Dark_Gift_T1', 'Dark_Gift_T2', 'Abyss_Gift_T3', 'Abyss_Gift_T4')]
        self.assertEqual(4, len(dark_gifts))
        configs = {
            skill['nid']: next(value for nid, value in skill['components']
                               if nid == 'class_dark_gift_intercept')
            for skill in dark_gifts
        }
        self.assertEqual(
            {'Dark_Gift_T1': (5, .7), 'Dark_Gift_T2': (10, .7),
             'Abyss_Gift_T3': (15, .75), 'Abyss_Gift_T4': (15, .75)},
            {nid: (config['proc_rate_bonus'], config['heal_multiplier'])
             for nid, config in configs.items()})
        self.assertTrue(all('Special activation rate' not in skill['desc'] for skill in dark_gifts))
        self.assertTrue(all('debuff/status proc rate' in skill['desc'] for skill in dark_gifts))

    def test_dark_gift_does_not_modify_generic_special_proc_rate(self):
        dark_gift = self.custom_components.ClassDarkGiftIntercept(
            {'hp_threshold': 20, 'rank': 4, 'proc_rate_bonus': 5, 'heal_multiplier': .7})
        dark_skill = SimpleNamespace(components=[dark_gift])
        dark_gift.skill = dark_skill
        unit = SimpleNamespace(skills=[dark_skill])
        special = SimpleNamespace(components=[])

        self.assertEqual(100, advanced_components.get_modified_proc_rate(unit, special))
        with patch.object(skill_system, 'condition', return_value=True):
            self.assertEqual(105, advanced_components.get_modified_debuff_proc_rate(unit, special))

    def test_phalanx_requires_two_adjacent_armored_allies_and_uses_only_highest_rank(self):
        high = self.custom_components.ClassPhalanxFormation(
            {'status': 'Class_Phalanx_Formation_Effect', 'rank': 2})
        low = self.custom_components.ClassPhalanxFormation(
            {'status': 'Class_Phalanx_Formation_Effect', 'rank': 1})
        owner = SimpleNamespace(position=(0, 0), dead=False, is_dying=False, tags=('Armor',),
                                get_hp=lambda: 20, skills=[])
        high.skill = SimpleNamespace(components=[high])
        low.skill = SimpleNamespace(components=[low])
        owner.skills = [high.skill, low.skill]
        armor_one = SimpleNamespace(position=(1, 0), dead=False, is_dying=False, tags=('Armor',),
                                    get_hp=lambda: 20, skills=[])
        armor_two = SimpleNamespace(position=(0, 1), dead=False, is_dying=False, tags=('Armor',),
                                    get_hp=lambda: 20, skills=[])
        nonarmor = SimpleNamespace(position=(-1, 0), dead=False, is_dying=False, tags=(),
                                   get_hp=lambda: 20, skills=[])
        with patch.object(self.custom_components.game, 'get_all_units',
                          return_value=[owner, armor_one, armor_two, nonarmor]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True):
            self.assertTrue(high._is_highest(owner))
            self.assertFalse(low._is_highest(owner))
            self.assertEqual([owner, armor_one, armor_two], high._formation_targets(owner))

    def test_phalanx_redirects_one_per_ten_damage_to_healthiest_adjacent_armor_without_killing(self):
        component = self.custom_components.ClassPhalanxRedirect()
        protected = SimpleNamespace(position=(0, 0), dead=False, is_dying=False, tags=('Armor',),
                                    get_hp=lambda: 20)
        highest = SimpleNamespace(position=(1, 0), dead=False, is_dying=False, tags=('Armor',),
                                  get_hp=lambda: 3)
        lower = SimpleNamespace(position=(0, 1), dead=False, is_dying=False, tags=('Armor',),
                                get_hp=lambda: 2)
        foe = SimpleNamespace(position=(1, 1), dead=False, is_dying=False, tags=(), get_hp=lambda: 20)
        incoming = self.custom_components.action.ChangeHP(protected, -29)
        actions = [incoming]
        with patch.object(self.custom_components.game, 'get_all_units',
                          return_value=[protected, highest, lower, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda _unit, candidate: candidate in (highest, lower)):
            component.after_take_strike(actions, [], protected, None, foe, None, 'defense', (0, 0), None)

        self.assertEqual(-27, incoming.num)
        redirect = actions[-1]
        self.assertIs(highest, redirect.unit)
        self.assertEqual(-2, redirect.num)

    def test_indoor_class_bonus_does_not_gate_the_phalanx_formation(self):
        component = self.custom_components.ClassIndoorHitAvoid({'bonus': 15})
        unit = SimpleNamespace(position=(0, 0))
        tilemap = SimpleNamespace(get_terrain=lambda _position: 'Arena')
        with patch.object(self.custom_components.game, '_current_level',
                          SimpleNamespace(tilemap=tilemap)):
            self.assertEqual(15, component.modify_accuracy(unit, None))
            self.assertEqual(15, component.modify_avoid(unit, None))
        tilemap = SimpleNamespace(get_terrain=lambda _position: 'Plains')
        with patch.object(self.custom_components.game, '_current_level',
                          SimpleNamespace(tilemap=tilemap)):
            self.assertEqual(0, component.modify_accuracy(unit, None))
            self.assertEqual(0, component.modify_avoid(unit, None))

    def test_phalanx_prefabs_and_class_mappings_match_the_three_source_tiers(self):
        expected = {
            'Phalanx_Guard_T1': ('Phalanx Guard', 5, 1),
            'Phalanx_Guard_T2': ('Phalanx Guard+', 10, 2),
            'Imperial_Phalanx_T3': ('Imperial Phalanx', 15, 3),
            'Imperial_Phalanx_T4': ('Imperial Phalanx+', 20, 4),
        }
        for nid, (name, bonus, rank) in expected.items():
            skill = self.by_nid[nid]
            components = dict(skill['components'])
            self.assertEqual(name, skill['name'])
            self.assertEqual(bonus, components['class_indoor_hit_avoid']['bonus'])
            self.assertEqual(rank, components['class_phalanx_formation']['rank'])
        self.assertEqual('Phalanx_Guard_T1', self.class_skills['Armored_Lance_Melee'])
        self.assertEqual('Phalanx_Guard_T1', self.class_skills['Armored_Lance_Range'])
        self.assertEqual('Phalanx_Guard_T2', self.class_skills['Lance_General_Melee'])
        self.assertEqual('Phalanx_Guard_T2', self.class_skills['Armored_Lance_Elite_Range'])
        self.assertEqual('Imperial_Phalanx_T3', self.class_skills['Lance_Marshall_Range'])
        self.assertEqual('Imperial_Phalanx_T3', self.class_skills['Lance_General_Elite_Melee'])
        self.assertEqual('Imperial_Phalanx_T4', self.class_skills['Lance_Marshall_Elite_Melee'])
        self.assertEqual('Imperial_Phalanx_T4', self.class_skills['Lance_Marshall_Elite_Range'])

    def test_shield_discipline_uses_the_formation_gate_and_source_tiers(self):
        expected = {
            'Shield_Discipline_T1': ('Shield Discipline', 5, 1),
            'Shield_Discipline_T2': ('Shield Discipline+', 10, 2),
            'Aegis_Doctrine_T3': ('Aegis Doctrine', 15, 3),
        }
        for nid, (name, bonus, rank) in expected.items():
            skill = self.by_nid[nid]
            components = dict(skill['components'])
            self.assertEqual(name, skill['name'])
            self.assertEqual(bonus, components['class_indoor_hit_avoid']['bonus'])
            self.assertEqual(rank, components['class_phalanx_formation']['rank'])
        self.assertEqual('Shield_Discipline_T1', self.class_skills['Armored_Sword_Melee'])
        self.assertEqual('Shield_Discipline_T2', self.class_skills['Sword_General_Range'])
        self.assertEqual('Aegis_Doctrine_T3', self.class_skills['Sword_Marshall_Melee'])
        self.assertEqual('Aegis_Doctrine_T3', self.class_skills['Sword_General_Elite_Range'])

    def test_formation_crit_avoid_is_ten(self):
        component = self.custom_components.ClassFormationCritAvoid()
        self.assertEqual(10, component.modify_crit_avoid(SimpleNamespace(), None))

    def test_siege_breaker_first_attempt_is_final_damage_and_consumes_on_miss(self):
        component = self.custom_components.ClassSiegeBreakerFirstStrike()
        component.skill = SimpleNamespace(data={})
        component.init(component.skill)
        unit = SimpleNamespace()
        self.assertEqual(1.05, component.damage_multiplier(unit, None, object(), None, 'attack', (0, 0), 19))
        with patch.object(self.custom_components.action, 'do', side_effect=lambda act: act.do()):
            component.after_strike([], [], unit, None, object(), None, 'attack', (0, 0),
                                   self.custom_components.Strike.MISS)
        self.assertTrue(component.skill.data['siege_breaker_consumed'])
        self.assertEqual(1, component.damage_multiplier(unit, None, object(), None, 'attack', (1, 0), 19))

    def test_siege_breaker_resets_for_its_owner_at_upkeep(self):
        component = self.custom_components.ClassSiegeBreakerFirstStrike()
        component.skill = SimpleNamespace(data={})
        component.init(component.skill)
        component.skill.data['siege_breaker_consumed'] = True
        with patch.object(self.custom_components.action, 'do', side_effect=lambda act: act.do()):
            component.on_upkeep([], [], object())
        self.assertFalse(component.skill.data['siege_breaker_consumed'])

    def test_siege_breaker_prefabs_cover_only_three_source_tiers(self):
        expected = {
            'Siege_Breaker_T1': ('Siege Breaker', 5, 1),
            'Siege_Breaker_T2': ('Siege Breaker+', 10, 2),
            'Grand_Breach_T3': ('Grand Breach', 15, 3),
        }
        for nid, (name, bonus, rank) in expected.items():
            skill = self.by_nid[nid]
            components = dict(skill['components'])
            self.assertEqual(name, skill['name'])
            self.assertEqual(bonus, components['class_indoor_hit_avoid']['bonus'])
            self.assertEqual(rank, components['class_phalanx_formation']['rank'])
        self.assertEqual('Siege_Breaker_T1', self.class_skills['Armored_Axe_Melee'])
        self.assertEqual('Siege_Breaker_T2', self.class_skills['Axe_General_Range'])
        self.assertEqual('Grand_Breach_T3', self.class_skills['Axe_Marshall_Melee'])
        self.assertEqual('Grand_Breach_T3', self.class_skills['Axe_General_Elite_Range'])

    def test_cavalry_components_keep_outdoor_bonus_separate_from_combat_effects(self):
        outdoor = self.custom_components.ClassOutdoorHitAvoid({'bonus': 10})
        unit = SimpleNamespace(position=(0, 0), previous_position=(0, 0),
                               dead=False, is_dying=False, tags=(), get_hp=lambda: 10)
        target = SimpleNamespace(position=(1, 0), get_hp=lambda: 20)
        with patch.object(self.custom_components.game, '_current_level',
                          SimpleNamespace(tilemap=SimpleNamespace(
                              get_terrain=lambda _position: '1'))):
            self.assertEqual(10, outdoor.modify_accuracy(unit, None))
            self.assertEqual(10, outdoor.modify_avoid(unit, None))
        with patch.object(self.custom_components.game, '_current_level',
                          SimpleNamespace(tilemap=SimpleNamespace(
                              get_terrain=lambda _position: 'Arena'))):
            self.assertEqual(0, outdoor.modify_accuracy(unit, None))

        battlecry = self.custom_components.ClassBattlecryCharge()
        self.assertEqual(1.1, battlecry.damage_multiplier(
            unit, None, target, None, 'attack', (0, 0), 20))
        self.assertEqual(1, battlecry.damage_multiplier(
            unit, None, target, None, 'defense', (0, 0), 20))

    def test_cavalry_first_foe_strike_effects_require_their_distinct_gates(self):
        user = SimpleNamespace(position=(5, 0), previous_position=(0, 0),
                               dead=False, is_dying=False, tags=(), get_hp=lambda: 20)
        foe = SimpleNamespace(position=(6, 0), dead=False, is_dying=False, tags=(), get_hp=lambda: 20)
        rapid = self.custom_components.ClassRapidAssault()
        with patch.object(self.custom_components.game, 'get_all_units', return_value=[user, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=False):
            self.assertEqual(.7, rapid.resist_multiplier(
                user, None, foe, None, 'defense', (0, 0), 20))
            self.assertEqual(1, rapid.resist_multiplier(
                user, None, foe, None, 'defense', (0, 1), 20))
            self.assertEqual(1, rapid.resist_multiplier(
                user, None, foe, None, 'attack', (0, 0), 20))

        horse_one = SimpleNamespace(position=(4, 0), dead=False, is_dying=False,
                                    tags=('Horse',), get_hp=lambda: 20)
        armor_two = SimpleNamespace(position=(5, 1), dead=False, is_dying=False,
                                    tags=('Armor',), get_hp=lambda: 20)
        shield = self.custom_components.ClassSolidShield()
        with patch.object(self.custom_components.game, 'get_all_units',
                          return_value=[user, foe, horse_one, armor_two]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda _unit, candidate: candidate in (horse_one, armor_two)):
            self.assertEqual(.7, shield.resist_multiplier(
                user, None, foe, None, 'defense', (0, 0), 20))
            self.assertEqual(1, shield.resist_multiplier(
                user, None, foe, None, 'defense', (1, 0), 20))

    def test_precision_volley_only_crits_when_user_did_not_move_and_initiates(self):
        component = self.custom_components.ClassPrecisionVolley()
        stationary = SimpleNamespace(position=(0, 0), previous_position=(0, 0))
        moved = SimpleNamespace(position=(1, 0), previous_position=(0, 0))
        self.assertEqual(30, component.dynamic_crit_accuracy(
            stationary, None, object(), None, 'attack', (0, 0), 0))
        self.assertEqual(0, component.dynamic_crit_accuracy(
            moved, None, object(), None, 'attack', (0, 0), 0))
        self.assertEqual(0, component.dynamic_crit_accuracy(
            stationary, None, object(), None, 'defense', (0, 0), 0))

    def test_cavalry_source_prefabs_have_all_named_tiers_and_component_contracts(self):
        families = {
            ('Battlecry_Charge_T1', 'Battlecry_Charge_T2', 'Warcry_Charge_T3', 'Warcry_Charge_T4'):
                ('Battlecry Charge', 'Battlecry Charge+', 'Warcry Charge', 'Warcry Charge+',
                 'class_battlecry_charge', (5, 10, 15, 20)),
            ('Rapid_Assault_T1', 'Rapid_Assault_T2', 'Swift_Raid_T3', 'Swift_Raid_T4'):
                ('Rapid Assault', 'Rapid Assault+', 'Swift Raid', 'Swift Raid+',
                 'class_rapid_assault', (5, 10, 15, 20)),
            ('Solid_Shield_T1', 'Solid_Shield_T2', 'Diamond_Formation_T3', 'Diamond_Formation_T4'):
                ('Solid Shield', 'Solid Shield+', 'Diamond Formation', 'Diamond Formation+',
                 'class_solid_shield', (5, 10, 15, 20)),
            ('Precision_Volley_T1', 'Precision_Volley_T2', 'Static_Volley_T3', 'Static_Volley_T4'):
                ('Precision Volley', 'Precision Volley+', 'Static Volley', 'Static Volley+',
                 'class_precision_volley', (5, 10, 5, 20)),
        }
        for nids, (name1, name2, name3, name4, effect, bonuses) in families.items():
            for nid, name, bonus in zip(nids, (name1, name2, name3, name4), bonuses):
                components = self.components(nid)
                self.assertEqual(name, self.by_nid[nid]['name'])
                self.assertEqual(bonus, components['class_outdoor_hit_avoid']['bonus'])
                self.assertIn(effect, components)

    def test_cavalry_class_list_crosswalk_only_maps_explicit_class_names(self):
        self.assertEqual('Battlecry_Charge_T1', self.class_skills['Axe_Raider'])
        self.assertEqual('Rapid_Assault_T1', self.class_skills['Sword_Rider'])
        self.assertEqual('Solid_Shield_T1', self.class_skills['Lance_Rider'])
        self.assertEqual('Battlecry_Charge_T2', self.class_skills['Axe_Paladin'])
        self.assertEqual('Rapid_Assault_T2', self.class_skills['Sword_Paladin'])
        self.assertEqual('Solid_Shield_T2', self.class_skills['Lance_Paladin'])
        self.assertEqual('Precision_Volley_T1', self.class_skills['Bow_Rider'])
        self.assertEqual('Precision_Volley_T2', self.class_skills['Bow_Paladin'])
        self.assertEqual('Warcry_Charge_T3', self.class_skills['Great_Knight'])
        self.assertEqual('Swift_Raid_T3', self.class_skills['Glory_Knight'])
        self.assertEqual('Diamond_Formation_T3', self.class_skills['Duke_Knight'])
        self.assertNotIn('Arch_Knight', self.class_skills)

    def test_wyvern_components_use_true_adjacent_allies_and_first_attempt_only(self):
        user = SimpleNamespace(position=(0, 0), dead=False, is_dying=False,
                               tags=(), get_hp=lambda: 20)
        ally = SimpleNamespace(position=(1, 0), dead=False, is_dying=False,
                                tags=(), get_hp=lambda: 20)
        foe = SimpleNamespace(position=(2, 0), dead=False, is_dying=False,
                              tags=(), get_hp=lambda: 20)
        pack = self.custom_components.ClassAdjacentHitAvoid({'bonus': 10})
        with patch.object(self.custom_components.game, 'get_all_units', return_value=[user, ally, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda _unit, candidate: candidate is ally):
            self.assertEqual(10, pack.modify_accuracy(user, None))
            self.assertEqual(10, pack.modify_avoid(user, None))

        damage = self.custom_components.ClassIsolatedFirstAttemptDamage(5)
        resist = self.custom_components.ClassIsolatedFirstStrikeResist(.8)
        with patch.object(self.custom_components.game, 'get_all_units', return_value=[user, foe]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=False):
            self.assertEqual(5, damage.raw_damage(user, None, foe, None, 'attack', (0, 0), 0))
            self.assertEqual(0, damage.raw_damage(user, None, foe, None, 'attack', (0, 1), 0))
            self.assertEqual(.8, resist.resist_multiplier(user, None, foe, None, 'defense', (0, 0), 10))
            self.assertEqual(1, resist.resist_multiplier(user, None, foe, None, 'defense', (1, 0), 10))

    def test_wyvern_quick_burn_fades_once_per_initiated_combat(self):
        burn = self.custom_components.ClassQuickBurnHitAvoid(10)
        skill = SimpleNamespace(data={})
        burn.skill = skill
        burn.init(skill)
        self.assertEqual(10, burn.modify_accuracy(SimpleNamespace(), None))
        with patch.object(self.custom_components.action, 'do', side_effect=lambda act: act.do()):
            burn.start_combat([], SimpleNamespace(), object(), object(), object(), 'attack')
        self.assertEqual(9, burn.modify_accuracy(SimpleNamespace(), None))
        burn.start_combat([], SimpleNamespace(), object(), object(), object(), 'defense')
        self.assertEqual(9, burn.modify_avoid(SimpleNamespace(), None))
        for _ in range(20):
            with patch.object(self.custom_components.action, 'do', side_effect=lambda act: act.do()):
                burn.start_combat([], SimpleNamespace(), object(), object(), object(), 'attack')
        self.assertEqual(0, burn.modify_accuracy(SimpleNamespace(), None))

    def test_existing_wyvern_and_quick_burn_prefabs_no_longer_double_count_bonus(self):
        for nid, bonus in (('Wyvern_Pack_T1', 5), ('Wyvern_Pack_T2', 10),
                           ('Dragon_Pack_T3', 15), ('Dragon_Pack_T4', 20)):
            components = self.components(nid)
            self.assertEqual(bonus, components['class_adjacent_hit_avoid']['bonus'])
            self.assertNotIn('combat_condition', components)
        for nid in ('Quick_Burn_T2', 'Quick_Burn_T3', 'Dragon_Burn_T4'):
            components = self.components(nid)
            self.assertEqual(0, components['hit'])
            self.assertEqual(0, components['avoid'])

    def test_wyvern_source_prefabs_preserve_adjacent_and_isolated_contracts(self):
        expected = {
            'Diving_Strike_T1': ('class_adjacent_hit_avoid', 5, 'class_isolated_first_attempt_damage', 3),
            'Diving_Strike_T2': ('class_adjacent_hit_avoid', 10, 'class_isolated_first_attempt_damage', 3),
            'Crushing_Dive_T3': ('class_adjacent_hit_avoid', 15, 'class_isolated_first_attempt_damage', 7),
            'Aerial_Armor_T1': ('class_adjacent_hit_avoid', 5, 'class_isolated_first_strike_resist', .85),
            'Aerial_Armor_T2': ('class_adjacent_hit_avoid', 10, 'class_isolated_first_strike_resist', .85),
            'Aerial_Guard_T3': ('class_adjacent_hit_avoid', 15, 'class_isolated_first_strike_resist', .75),
            'Sky_Strike_T2': ('class_quick_burn_hit_avoid', 10, 'class_isolated_first_attempt_damage', 5),
            'Sky_Strike_T3': ('class_quick_burn_hit_avoid', 15, 'class_isolated_first_attempt_damage', 7),
            'Sky_Guard_T2': ('class_quick_burn_hit_avoid', 10, 'class_isolated_first_strike_resist', .8),
            'Sky_Guard_T3': ('class_quick_burn_hit_avoid', 15, 'class_isolated_first_strike_resist', .75),
        }
        for nid, (bonus_component, bonus, isolated_component, isolated_value) in expected.items():
            components = self.components(nid)
            configured_bonus = components[bonus_component]
            if isinstance(configured_bonus, dict):
                configured_bonus = configured_bonus['bonus']
            self.assertEqual(bonus, configured_bonus, nid)
            self.assertEqual(isolated_value, components[isolated_component], nid)

    def test_infernal_dominion_slow_burn_caps_and_scales_damage_and_skill_rate(self):
        component = self.custom_components.ClassInfernalDominion()
        with patch.object(self.custom_components.game, 'turncount', 1, create=True):
            self.assertEqual(2, component.modify_accuracy(SimpleNamespace(), None))
            self.assertEqual(0, component.raw_damage(None, None, None, None, 'attack', (0, 0), 0))
        with patch.object(self.custom_components.game, 'turncount', 10, create=True):
            self.assertEqual(20, component.modify_avoid(SimpleNamespace(), None))
            self.assertEqual(4, component.raw_damage(None, None, None, None, 'attack', (0, 0), 0))
            self.assertEqual(4, component.modify_self_proc_rate(SimpleNamespace()))
        with patch.object(self.custom_components.game, 'turncount', 99, create=True):
            self.assertEqual(20, component.modify_accuracy(SimpleNamespace(), None))

    def test_wyvern_class_list_crosswalk_only_maps_explicit_base_nids(self):
        expected = {
            'Axe_Wyvern_Rider': 'Diving_Strike_T1',
            'Lance_Wyvern_Rider': 'Aerial_Armor_T1',
            'Axe_Wyvern_Knight': 'Diving_Strike_T2',
            'Lance_Wyvern_Knight': 'Aerial_Armor_T2',
            'Axe_Wyvern_Lord': 'Sky_Strike_T2',
            'Lance_Wyvern_Lord': 'Sky_Guard_T2',
            'Axe_Dragon_Knight': 'Crushing_Dive_T3',
            'Lance_Dragon_Knight': 'Aerial_Guard_T3',
            'Axe_Dragon_Lord': 'Sky_Strike_T3',
            'Lance_Dragon_Lord': 'Sky_Guard_T3',
            'Wicked_Knight': 'Infernal_Dominion_T3',
        }
        self.assertEqual(expected, {nid: self.class_skills[nid] for nid in expected})
        self.assertNotIn('Axe_Malig_Knight', self.class_skills)
        self.assertNotIn('Lance_Malig_Knight', self.class_skills)

    def test_elite_magic_class_overrides_preserve_the_one_tier_upgrade(self):
        """These workbook descriptions are copied from the base class, not authority."""
        rows = {row['class_name']: row for row in self.source_rows}
        expected = {
            'Elite Shaman': ('Shaman', 'Hex_T2', 2),
            'Elite Summoner': ('Summoner', 'Call_of_the_Haunted_T3', 3),
            'Elite Warlock': ('Warlock', 'Super_Hex_T4', 4),
        }
        for elite_name, (base_name, prefab, tier) in expected.items():
            row = rows[elite_name]
            self.assertEqual(prefab, row['canonical_prefab_nid'])
            self.assertEqual({
                'rule': 'elite_skill_plus_one_tier',
                'base_source_row': rows[base_name]['source_row'],
                'effective_skill_tier': tier,
                'description_authority': 'canonical_prefab',
            }, row['authority_override'])

    def test_remaining_class_skill_prefabs_match_the_approved_runtime_contract(self):
        air = self.components('Air_Control_T2')
        self.assertEqual({
            'flying_foe_avoid_penalty': 10,
            'crit': 10,
            'isolated_skl': 0,
            'magic_block_status': 'Air_Superiority_Magic_Block',
        }, air['class_air_superiority'])
        self.assertNotIn('avoid', air)
        self.assertNotIn('combat_condition', air)

        self.assertEqual(20, self.components('Duelist_Blow_T1')['avoid'])
        for nid, proc_rate in (('Worthy_Opponent_T1', 5),
                               ('Worthy_Opponent_T2', 10),
                               ('Admirable_Warrior_T3', 15)):
            components = self.components(nid)
            self.assertEqual(proc_rate, components['modify_self_proc_rate'], nid)
            self.assertEqual(proc_rate, components['modify_enemy_proc_rate'], nid)

        self.assertEqual(.25, self.components('Rupture_T3')['class_critical_kill_lifelink'])
        for nid, event in (('Call_of_the_Haunted_T2', 'Global Summon Phantom'),
                           ('Call_of_the_Haunted_T3', 'Global Summon Phantom 2')):
            components = self.components(nid)
            self.assertEqual(event, components['class_path_damned_summon'], nid)
            self.assertNotIn('ability', components, nid)
            self.assertNotIn('condition', components, nid)

        for tier, bonus in ((1, 4), (2, 6)):
            parent = self.components(f'Profane_Aura_T{tier}')
            effect = self.components(parent['hone_ally_status']['status'])
            self.assertEqual(bonus, effect['class_first_attempt_damage'])
            self.assertEqual({'group': 'hone:profane_aura', 'rank': tier},
                             effect['exclusive_upkeep_effect'])
            self.assertIn('lost_on_strike', effect)
            self.assertIn('lost_on_endstep', effect)
            self.assertIn('lost_on_end_chapter', effect)

        for tier, bonus in ((2, 4), (3, 6)):
            components = self.components(f'Strictly_Discipline_T{tier}')
            self.assertEqual(bonus, components['damage'])
            self.assertEqual(bonus, components['resist'])

        divine = self.components('Divine_Blessing_T4')
        self.assertEqual(15, divine['class_lowest_hp_adjacent_heal'])
        self.assertEqual('Divine_Blessing_T4_Effect',
                         divine['give_ally_status_after_combat_if_full_hp'])
        self.assertEqual([['RES', 5]], self.components('Divine_Blessing_T4_Effect')['stat_change'])
        plus = self.components('Divine_Blessing_Plus_T4')
        self.assertEqual(15, plus['class_lowest_hp_adjacent_heal'])
        self.assertEqual([['RES', 10]],
                         self.components('Divine_Blessing_Plus_T4_Effect')['stat_change'])
        self.assertEqual('Divine_Blessing_Plus_T4', self.class_skills['Saint_Elite'])


if __name__ == '__main__':
    unittest.main()
