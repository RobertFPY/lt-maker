import json
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import skill_system


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class RuntimeUnit:
    def __init__(self, nid, team, res=0, hp=20, position=(0, 0)):
        self.nid = nid
        self.team = team
        self.res = res
        self.hp = hp
        self.position = position
        self.dead = False
        self.is_dying = False
        self.tags = []
        self.skills = []

    @property
    def all_skills(self):
        return self.skills

    def get_stat(self, stat):
        return self.res if stat == 'RES' else 0

    def get_hp(self):
        return self.hp

    def stat_bonus(self, stat):
        return 0


class PloyFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.events = json.loads((PROJECT / 'game_data' / 'events.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    def test_stat_ploys_use_ranked_component_and_not_do_nothing(self):
        for stat in ('Strength', 'Magic', 'Speed', 'Defense', 'Resistance'):
            for tier in range(1, 4):
                components = dict(self.skills[f'{stat}_Ploy_T{tier}']['components'])
                self.assertIn('ranked_stat_ploy', components)
                self.assertNotIn('do_nothing', components)

    def test_panic_and_stall_use_hp_ranked_components_without_legacy_events(self):
        for nid, component in (
                ('Panic_Ploy_T1', 'panic_ploy_during_combat'),
                ('Panic_Ploy_T2', 'panic_ploy_during_combat'),
                ('Panic_Ploy_T3', 'panic_ploy_during_combat'),
                ('Stall_Ploy_T1', 'stall_ploy_after_combat'),
                ('Stall_Ploy_T2', 'stall_ploy_after_combat'),
                ('Stall_Ploy_T3', 'stall_ploy_after_combat')):
            components = dict(self.skills[nid]['components'])
            self.assertIn(component, components)
            self.assertNotIn('combat_condition', components)
            self.assertNotIn('event_before_combat', components)
            self.assertNotIn('event_after_combat', components)
        event_nids = {event['nid'] for event in self.events}
        self.assertFalse({'Global PanicPloySkill', 'Global PanicPloySkill2',
                          'Global StallPloySkill', 'Global StallPloySkill2'} & event_nids)

    def test_stat_ploy_orders_eligible_foes_by_resistance_and_uses_runtime_enemy_relationship(self):
        source = RuntimeUnit('source', 'player', res=10)
        high = RuntimeUnit('high', 'enemy', res=9)
        low = RuntimeUnit('low', 'enemy2', res=8)
        ally = RuntimeUnit('ally', 'player', res=1)
        component = self.custom_components.RankedStatPloy({
            'stat': 'STR', 'status': 'Strength_Ploy_T3_Effect', 'rank': 3,
        })
        game = SimpleNamespace(get_all_units=lambda: [source, high, low, ally])
        with patch.object(self.custom_components, 'game', game), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team in ('enemy', 'enemy2')):
            request = component.ranked_upkeep_request(source)

        self.assertEqual([high, low], request.targets)
        self.assertEqual(1, request.max_targets)

        first_tie = RuntimeUnit('z_first_in_game_order', 'enemy', res=9)
        second_tie = RuntimeUnit('a_second_in_game_order', 'enemy', res=9)
        game = SimpleNamespace(get_all_units=lambda: [source, first_tie, second_tie])
        with patch.object(self.custom_components, 'game', game), \
                patch.object(self.custom_components.skill_system, 'check_enemy', return_value=True):
            request = component.ranked_upkeep_request(source)
        self.assertEqual([first_tie, second_tie], request.targets)

    def test_panic_and_stall_fall_back_to_lower_tier_when_higher_hp_gap_fails(self):
        source = RuntimeUnit('source', 'player', hp=10)
        target = RuntimeUnit('target', 'enemy', hp=25)
        for component_type in (self.custom_components.PanicPloyDuringCombat,
                               self.custom_components.StallPloyAfterCombat):
            with self.subTest(component_type=component_type.__name__):
                low = component_type({'rank': 1, 'hp_gap': 5, 'status': 'effect'})
                medium = component_type({'rank': 2, 'hp_gap': 10, 'status': 'effect'})
                high = component_type({'rank': 3, 'hp_gap': 15, 'status': 'effect'})
                source.skills = [SimpleNamespace(components=[low]), SimpleNamespace(components=[medium]),
                                 SimpleNamespace(components=[high])]
                self.assertFalse(high._is_winner(source, target))
                self.assertTrue(medium._is_winner(source, target))
                self.assertFalse(low._is_winner(source, target))

    def test_stall_skips_dead_or_dying_targets(self):
        source = RuntimeUnit('source', 'player', hp=10)
        target = RuntimeUnit('target', 'enemy', hp=25)
        component = self.custom_components.StallPloyAfterCombat({
            'rank': 2, 'hp_gap': 10, 'status': 'Stall_Ploy_Effect',
        })
        source.skills = [SimpleNamespace(components=[component])]
        target.is_dying = True
        with patch.object(self.custom_components.skill_system, 'check_enemy', return_value=True), \
                patch.object(self.custom_components.action, 'AddSkill') as add_skill:
            component.end_combat([], source, None, target, None, 'attack')
        add_skill.assert_not_called()

    def test_stall_movement_cap_uses_the_lowest_active_cap(self):
        first = self.custom_components.MovementCap(3)
        second = self.custom_components.MovementCap(1)
        self.assertTrue(first.defines('movement_cap'))
        unit = RuntimeUnit('unit', 'enemy')
        unit.equipped_weapon = None
        first_skill = type('OwnedSkill', (), {})()
        second_skill = type('OwnedSkill', (), {})()
        first_skill.components = [first]
        second_skill.components = [second]
        unit.skills = [first_skill, second_skill]
        self.assertEqual(1, skill_system.movement_cap(unit))

    def test_save_interceptor_does_not_contribute_a_movement_cap(self):
        save = self.custom_components.SaveInterceptor()
        save.ignore_conditional = True
        cap = self.custom_components.MovementCap(1)
        cap.ignore_conditional = True
        unit = RuntimeUnit('unit', 'enemy')
        unit.equipped_weapon = None

        self.assertFalse(save.defines('movement_cap'))
        unit.skills = [SimpleNamespace(components=[save])]
        self.assertEqual(1000, skill_system.movement_cap(unit))

        unit.skills = [SimpleNamespace(components=[save]), SimpleNamespace(components=[cap])]
        self.assertEqual(1, skill_system.movement_cap(unit))

    def test_panic_and_stall_descriptions_match_their_hp_gap_contracts(self):
        for nid_prefix, effect in (
                ('Panic_Ploy', "convert foe's bonus into penalty for the entire combat."),
                ('Stall_Ploy', "restrict foe's movement to 1 for 1 turn.")):
            for tier, hp_gap in enumerate((5, 10, 15), start=1):
                with self.subTest(nid_prefix=nid_prefix, tier=tier):
                    self.assertEqual(
                        f"If user's HP < (foe's HP -{hp_gap}), {effect}",
                        self.skills[f'{nid_prefix}_T{tier}']['desc'])

        effect_components = dict(self.skills['Stall_Ploy_Effect']['components'])
        self.assertEqual(1, effect_components['movement_cap'])
        self.assertIn('lost_on_next_action', effect_components)
        self.assertIn('lost_on_end_chapter', effect_components)
