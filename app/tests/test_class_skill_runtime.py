import importlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.data.resources.resources import RESOURCES
from app.data.database.database import DB
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import combat_calcs, item_system, skill_system
from app.engine.combat.simple_combat import SimpleCombat
from app.engine.combat.solver import CombatPhaseSolver


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class ClassSkillFollowUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resource_path = str(PROJECT / 'resources')
        if resource_path not in sys.path:
            sys.path.insert(0, resource_path)
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module(
            'custom_components.custom_skill_components')
        cls.custom_item_components = importlib.import_module(
            'custom_components.custom_item_components')
        cls.skills = json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        cls.by_nid = {skill['nid']: skill for skill in cls.skills}
        raw_data = json.loads((PROJECT / 'game_data' / 'raw_data.json').read_text(encoding='utf-8'))
        class_data = next(record for record in raw_data if record['nid'] == 'ClassData')
        cls.class_skills = {record['nid']: record['Class'] for record in class_data['lovalue']}

    def test_proc_follow_up_phases_are_added_once_to_the_static_phase_budget(self):
        """A class proc rolls only against non-proc phases, never recursively."""
        unit = object()
        target = object()
        item = object()
        target_item = object()

        with patch.object(item_system, 'can_double', return_value=True), \
                patch.object(skill_system, 'no_double', return_value=False), \
                patch.object(skill_system, 'prevent_self_follow_up', return_value=False), \
                patch.object(skill_system, 'prevent_foe_follow_up', return_value=False), \
                patch.object(skill_system, 'prevent_foe_natural_follow_up', return_value=False), \
                patch.object(skill_system, 'neutralize_follow_up_prevention', return_value=False), \
                patch.object(skill_system, 'neutralize_foe_follow_up_grants', return_value=False), \
                patch.object(skill_system, 'no_dynamic_attacks', return_value=False), \
                patch.object(skill_system, 'negate_no_dynamic_attacks', return_value=False), \
                patch.object(item_system, 'dynamic_attacks', return_value=0), \
                patch.object(skill_system, 'dynamic_attacks', return_value=1), \
                patch.object(skill_system, 'dynamic_early_attacks', return_value=1), \
                patch.object(skill_system, 'dynamic_follow_up_proc_count', return_value=2, create=True) as proc, \
                patch('app.engine.combat_calcs.outspeed', return_value=1), \
                patch('app.engine.combat_calcs.resolve_weapon', return_value=target_item):
            plan = combat_calcs.compute_attack_phase_plan(
                unit, target, item, target_item, 'attack', (0, 0))

        # base + natural + static normal + static early + two successful rolls
        self.assertEqual(6, plan.total_phases)
        self.assertEqual(1, plan.early_phases)
        proc.assert_called_once_with(unit, item, target, target_item, 'attack', (0, 0), 4)

    def test_class_follow_up_proc_rolls_once_per_eligible_phase(self):
        component = self.custom_components.ClassFollowUpProc({'chance': 50, 'skip_first': False})

        with patch.object(self.custom_components.static_random, 'get_combat',
                          side_effect=(0, 99, 49, 50)) as rolls:
            result = component.dynamic_follow_up_proc_count(
                object(), object(), object(), object(), 'attack', (0, 0), 4)

        self.assertEqual(2, result)
        self.assertEqual(4, rolls.call_count)

    def test_class_follow_up_proc_can_skip_the_first_eligible_phase(self):
        component = self.custom_components.ClassFollowUpProc({'chance': 50, 'skip_first': True})

        with patch.object(self.custom_components.static_random, 'get_combat',
                          side_effect=(0, 99, 49)) as rolls:
            result = component.dynamic_follow_up_proc_count(
                object(), object(), object(), object(), 'attack', (0, 0), 4)

        self.assertEqual(2, result)
        self.assertEqual(3, rolls.call_count)

    def test_class_follow_up_proc_is_initiator_only_when_requested(self):
        component = self.custom_components.ClassFollowUpProc(
            {'chance': 100, 'skip_first': False, 'initiator_only': True})

        with patch.object(self.custom_components.static_random, 'get_combat') as rolls:
            result = component.dynamic_follow_up_proc_count(
                object(), object(), object(), object(), 'defense', (0, 0), 2)

        self.assertEqual(0, result)
        rolls.assert_not_called()

    def test_bow_hunter_class_skills_use_the_phase_proc_contract(self):
        expected = {
            'Deadeye_Discipline_T2': (50, False, None),
            'Field_Archery_T2': (10, True, "1 if item_system.weapon_type(unit, item) == 'Bow' else 0"),
            'Marksmanship_T3': (50, False, 1),
            'Mobile_Ballistics_T3': (20, True, "1 if item_system.weapon_type(unit, item) == 'Bow' else 0"),
        }
        for nid, (chance, skip_first, range_value) in expected.items():
            components = dict(self.by_nid[nid]['components'])
            self.assertEqual({'chance': chance, 'skip_first': skip_first,
                              'initiator_only': True},
                             components['class_follow_up_proc'], nid)
            self.assertNotIn('combat_condition', components, nid)
            if range_value is None:
                self.assertNotIn('modify_maximum_range', components, nid)
                self.assertNotIn('eval_max_range', components, nid)
            elif isinstance(range_value, str):
                self.assertEqual(range_value, components['eval_max_range'], nid)
            else:
                self.assertEqual(range_value, components['modify_maximum_range'], nid)

        marksmanship = dict(self.by_nid['Marksmanship_T3']['components'])
        self.assertEqual("6 if mode == 'attack' else 0", marksmanship['raw_damage'])
        self.assertNotIn('attack_pre_proc', marksmanship)
        self.assertNotIn('proc_rate', marksmanship)

        self.assertEqual('Deadeye_Discipline_T2', self.class_skills['Sniper'])
        self.assertEqual('Field_Archery_T2', self.class_skills['Ranger'])
        self.assertEqual('Marksmanship_T3', self.class_skills['Marksman'])
        self.assertEqual('Mobile_Ballistics_T3', self.class_skills['Ranger_Knight'])

    def test_nomad_class_skills_apply_initiation_bonuses_and_tiered_debuffs(self):
        expected = {
            'Desert_Hunter_T1': (2, 3, False),
            'Desert_Hunter_T2': (4, 4, False),
            'Hunter_Instinct_T3': (4, 5, True),
        }
        for nid, (bonus, penalty, prevents_follow_up) in expected.items():
            components = dict(self.by_nid[nid]['components'])
            self.assertEqual("mode == 'attack'", components['combat_condition'], nid)
            self.assertEqual(bonus, components['damage'], nid)
            self.assertEqual(bonus, components['attack_speed'], nid)
            self.assertEqual(bonus, components['defense_speed'], nid)
            effect_nid = components['give_status_after_combat_until_next_action']
            effect = dict(self.by_nid[effect_nid]['components'])
            self.assertEqual([['STR', -penalty], ['MAG', -penalty], ['SPD', -penalty]],
                             effect['stat_change'], effect_nid)
            self.assertIn('lost_on_next_action', effect, effect_nid)
            self.assertIn('lost_on_end_chapter', effect, effect_nid)
            self.assertEqual(prevents_follow_up,
                             'prevent_foe_follow_up' in components, nid)

        self.assertEqual('Desert_Hunter_T1', self.class_skills['Nomad'])
        self.assertEqual('Desert_Hunter_T2', self.class_skills['Nomadic_Trooper'])
        self.assertEqual('Hunter_Instinct_T3', self.class_skills['Chieftain'])

    def test_path_of_the_dammed_summons_only_with_pre_cost_hp_and_an_empty_adjacent_tile(self):
        component = self.custom_components.ClassPathDamnedSummon('Global Summon Phantom 2')
        actions, playback = [], []
        legal_owner = SimpleNamespace(position=(4, 4), get_hp=lambda: 20)
        low_hp_owner = SimpleNamespace(position=(4, 4), get_hp=lambda: 19)

        target_system = SimpleNamespace(
            get_adjacent_positions=lambda _position: [(5, 4), (4, 5)])
        board = SimpleNamespace(
            get_unit=lambda pos: object() if pos == (5, 4) else None)
        events = SimpleNamespace(trigger_specific_event=unittest.mock.Mock())
        with patch.object(self.custom_components.game, 'target_system', target_system), \
                patch.object(self.custom_components.game, 'board', board), \
                patch.object(self.custom_components.game, 'events', events):
            component.on_upkeep(actions, playback, low_hp_owner)
            events.trigger_specific_event.assert_not_called()
            component.on_upkeep(actions, playback, legal_owner)

        events.trigger_specific_event.assert_called_once_with(
            'Global Summon Phantom 2', legal_owner, legal_owner, (4, 4),
            {'target_pos': (4, 5)})

        phantom_effect = dict(self.by_nid['Phantom_Personal_Effect']['components'])
        self.assertEqual('Global PhantomDefeated', phantom_effect['event_on_death'])
        events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(encoding='utf-8'))
        recovery = next(event for event in events if event['nid'] == 'Global PhantomDefeated')
        self.assertEqual(
            ["heal_unit;{eval:game.get_unit('{unit}').get_field('Summoner')};10"],
            recovery['_source'])

    def test_magic_triangle_shift_uses_users_combat_item_and_configured_resistance_reduction(self):
        component = self.custom_components.ClassMagicAdvantageShift(
            {'triangle_percent': 20, 'res_reduction_percent': 10,
             'ignore_foe_crit_advantage': True})
        user = SimpleNamespace(position=(0, 0))
        foe = SimpleNamespace(position=(1, 0), get_stat=lambda stat: 25)
        user_item, foe_item = object(), object()
        self_advantage = SimpleNamespace(hit=30, crit=0)
        foe_advantage = SimpleNamespace(hit=20, crit=15)

        with patch.object(self.custom_components.item_funcs, 'is_magic_in_combat',
                          return_value=True), \
                patch.object(self.custom_components.combat_calcs, 'compute_advantage',
                             side_effect=[self_advantage, foe_advantage, foe_advantage]):
            self.assertEqual(6, component.dynamic_accuracy(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            self.assertEqual(4, component.dynamic_avoid(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            self.assertEqual(15, component.dynamic_crit_avoid(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            self.assertEqual(2, component.dynamic_damage(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))

        with patch.object(self.custom_components.item_funcs, 'is_magic_in_combat',
                          return_value=False), \
                patch.object(self.custom_components.combat_calcs, 'compute_advantage') as advantage:
            self.assertEqual(0, component.dynamic_accuracy(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            self.assertEqual(0, component.dynamic_avoid(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            self.assertEqual(0, component.dynamic_crit_avoid(
                user, user_item, foe, foe_item, 'attack', (0, 0), 0))
            advantage.assert_not_called()

    def test_magic_triangle_shift_requires_the_foes_actual_magic_item_for_triangle_effects(self):
        component = self.custom_components.ClassMagicAdvantageShift(
            {'triangle_percent': 20, 'res_reduction_percent': 10,
             'ignore_foe_crit_advantage': True})
        user = SimpleNamespace(position=(0, 0))
        foe = SimpleNamespace(position=(1, 0), get_stat=lambda stat: 25)

        with patch.object(self.custom_components.item_funcs, 'is_magic_in_combat',
                          side_effect=lambda owner, item, target: owner is user), \
                patch.object(self.custom_components.combat_calcs, 'compute_advantage') as advantage:
            self.assertEqual(0, component.dynamic_accuracy(
                user, object(), foe, object(), 'attack', (0, 0), 0))
            self.assertEqual(0, component.dynamic_avoid(
                user, object(), foe, object(), 'attack', (0, 0), 0))
            self.assertEqual(0, component.dynamic_crit_avoid(
                user, object(), foe, object(), 'attack', (0, 0), 0))
            self.assertEqual(2, component.dynamic_damage(
                user, object(), foe, object(), 'attack', (0, 0), 0))
        advantage.assert_not_called()

    def test_initiator_first_attempt_damage_requires_attack_mode_and_first_attempt(self):
        component = self.custom_components.ClassInitiatorFirstAttemptDamage(10)
        unit = target = item = item2 = object()
        self.assertEqual(10, component.raw_damage(unit, item, target, item2, 'attack', (0, 0), 0))
        self.assertEqual(0, component.raw_damage(unit, item, target, item2, 'defense', (0, 0), 0))
        self.assertEqual(0, component.raw_damage(unit, item, target, item2, 'attack', (0, 1), 0))

    def test_raid_valkyria_first_attack_damage_does_not_require_a_ground_foe(self):
        component = self.custom_components.ClassRaidValkyria(
            {'ground_avoid': 15, 'first_attempt_damage': 10, 'isolated_spd': 5})
        flying = SimpleNamespace(tags=('Flying',))
        self.assertEqual(10, component.raw_damage(
            object(), object(), flying, object(), 'attack', (0, 0), 0))

    def test_air_superiority_applies_flying_combat_bonus_and_magic_follow_up_block(self):
        component = self.custom_components.ClassAirSuperiority(
            {'flying_foe_avoid_penalty': 15, 'crit': 15, 'isolated_skl': 5,
             'magic_block_status': 'Air_Superiority_Magic_Block'})
        user = SimpleNamespace(nid='class_air_user', position=(0, 0), skills=[], tags=(), dead=False,
                               is_dying=False, get_hp=lambda: 10)
        flying = SimpleNamespace(position=(1, 0), tags=('Flying',), dead=False,
                                  is_dying=False, get_hp=lambda: 10)
        with patch.object(self.custom_components.game, 'get_all_units', return_value=[user, flying]), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=False), \
                patch.object(self.custom_components.item_funcs, 'is_magic_in_combat', return_value=True), \
                patch.object(self.custom_components.action, 'AddSkill', return_value=object()) as add, \
                patch.object(self.custom_components.action, 'do') as do:
            self.assertEqual(15, component.dynamic_accuracy(
                user, object(), flying, object(), 'attack', (0, 0), 0))
            self.assertEqual(15, component.dynamic_crit_accuracy(
                user, object(), flying, object(), 'attack', (0, 0), 0))
            self.assertEqual({'SKL': 5}, component.stat_change(user))
            component.start_combat([], user, object(), flying, object(), 'attack')
        self.assertTrue(do.called)
        add.assert_called_once_with(user, 'Air_Superiority_Magic_Block', user)

    def test_air_superiority_blocks_the_foes_phase_after_simple_combat_start(self):
        component = self.custom_components.ClassAirSuperiority(
            {'flying_foe_avoid_penalty': 15, 'crit': 15, 'isolated_skl': 5,
             'magic_block_status': 'Air_Superiority_Magic_Block'})
        attacker = SimpleNamespace(nid='air_user', position=(0, 0), skills=[],
                                   tags=(), strike_partner=None)
        defender = SimpleNamespace(nid='foe', position=(1, 0), skills=[],
                                   tags=('Flying',), strike_partner=None)
        main_item, def_item, status = object(), object(), object()
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.full_playback = []
        combat.attacker, combat.main_item, combat.defender = attacker, main_item, defender
        combat.defenders, combat.def_items, combat.all_splash = [defender], [def_item], []

        def start_combat(_playback, unit, item, target, item2, mode):
            if unit is attacker:
                component.start_combat([], unit, item, target, item2, mode)

        with patch('app.engine.combat.simple_combat.resolve_weapon', return_value=def_item), \
                patch.object(skill_system, 'pre_combat'), \
                patch.object(skill_system, 'start_combat', side_effect=start_combat), \
                patch.object(item_system, 'start_combat'), \
                patch.object(self.custom_components.item_funcs, 'is_magic_in_combat', return_value=True), \
                patch.object(self.custom_components.action, 'AddSkill', return_value=status), \
                patch.object(self.custom_components.action, 'do',
                             side_effect=lambda _action: attacker.skills.append(status)):
            combat.start_combat()

        solver = CombatPhaseSolver(attacker, main_item, [main_item], [defender], [], [],
                                   defender, def_item)
        with patch.object(item_system, 'can_double', return_value=True), \
                patch.object(skill_system, 'no_double', return_value=False), \
                patch.object(skill_system, 'prevent_self_follow_up', return_value=False), \
                patch.object(skill_system, 'prevent_foe_follow_up',
                             side_effect=lambda unit: unit is attacker and status in unit.skills), \
                patch.object(skill_system, 'neutralize_follow_up_prevention', return_value=False):
            self.assertEqual(1, solver.get_attack_phase_plan(
                defender, attacker, def_item, main_item, 'defense', (0, 0)).total_phases)

        effect = dict(self.by_nid['Air_Superiority_Magic_Block']['components'])
        self.assertIn('lost_on_end_combat2', effect)

    def test_air_superiority_does_not_block_magic_follow_up_against_a_ground_foe(self):
        component = self.custom_components.ClassAirSuperiority(
            {'flying_foe_avoid_penalty': 10, 'crit': 10, 'isolated_skl': 0,
             'magic_block_status': 'Air_Superiority_Magic_Block'})
        user = SimpleNamespace(position=(0, 0), skills=[])
        ground_foe = SimpleNamespace(position=(1, 0), tags=())
        with patch.object(self.custom_components.item_funcs, 'is_magic_in_combat', return_value=True), \
                patch.object(self.custom_components.action, 'AddSkill') as add, \
                patch.object(self.custom_components.action, 'do') as do:
            component.start_combat([], user, object(), ground_foe, object(), 'attack')
        add.assert_not_called()
        do.assert_not_called()

    def test_phantom_heist_steal_allows_an_equipped_enemy_weapon(self):
        component = self.custom_item_components.LupinSteal()
        user = SimpleNamespace(team='player')
        spell = SimpleNamespace()
        equipped_weapon = object()
        defender = SimpleNamespace(get_weapon=lambda: equipped_weapon)

        with patch.object(self.custom_item_components.item_system, 'unstealable', return_value=False), \
                patch.object(self.custom_item_components.item_funcs, 'inventory_full', return_value=False):
            self.assertTrue(component.item_restrict(user, spell, defender, equipped_weapon))


if __name__ == '__main__':
    unittest.main()
