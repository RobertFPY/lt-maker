from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import importlib
import json
from pathlib import Path
import sys

from app.engine import combat_calcs, skill_system
from app.engine.combat import playback as pb
from app.engine.skill_components.advanced_components import AetherProc, AstraProc
from app.engine.skill_components.combat2_components import GiveStatusAfterHit, Lifelink
from app.utilities.enums import Strike


class SpecialSkillRuntimeTests(TestCase):
    def test_lifelink_uses_only_damage_from_current_strike(self):
        unit = SimpleNamespace(skills=[], get_hp=lambda: 10)
        target = SimpleNamespace(get_hp=lambda: 100)
        item = object()
        component = Lifelink(0.7)
        component.skill = SimpleNamespace()
        playback = [
            pb.DamageHit(unit, item, target, 10, 10),
            pb.MarkHit(unit, target, unit, item),
            pb.DamageHit(unit, item, target, 20, 20),
            pb.MarkHit(unit, target, unit, item),
        ]
        actions = []

        component.after_strike(actions, playback, unit, item, target, None,
                               'attack', (0, 1), Strike.HIT)

        self.assertEqual(14, actions[0].num)

    def test_lifelink_and_status_after_hit_ignore_a_miss_after_prior_hit(self):
        unit = SimpleNamespace(skills=[])
        target = SimpleNamespace(get_hp=lambda: 100)
        item = object()
        playback = [
            pb.DamageHit(unit, item, target, 10, 10),
            pb.MarkHit(unit, target, unit, item),
        ]
        lifelink = Lifelink(0.7)
        lifelink.skill = SimpleNamespace()
        lifelink_actions = []
        lifelink.after_strike(lifelink_actions, playback, unit, item, target, None,
                              'attack', (0, 1), Strike.MISS)
        self.assertEqual([], lifelink_actions)

        status = GiveStatusAfterHit('Deadeye_Effect_1')
        status.skill = SimpleNamespace()
        status_actions = []
        status.after_strike(status_actions, playback, unit, item, target, None,
                            'attack', (0, 1), Strike.MISS)
        self.assertEqual([], status_actions)

    def test_colossus_heal_requires_current_proc_strike_to_be_lethal(self):
        project_resources = str(Path(__file__).resolve().parents[2]
                                / 'Fire Emblem Tales of The Golden Knight.ltproj'
                                / 'resources')
        if project_resources not in sys.path:
            sys.path.insert(0, project_resources)
        custom = importlib.import_module('custom_components.custom_skill_components')
        unit = SimpleNamespace(skills=[], get_hp=lambda: 10)
        target = SimpleNamespace(get_hp=lambda: 20)
        item = object()
        lethal_playback = [
            pb.DamageHit(unit, item, target, 20, 20),
            pb.MarkHit(unit, target, unit, item),
        ]
        component = custom.HealOnStrikeKill(10)
        actions = []
        component.after_strike(actions, lethal_playback, unit, item, target, None,
                               'attack', (0, 0), Strike.HIT)
        self.assertEqual(10, actions[0].num)

        nonlethal_playback = [
            pb.DamageHit(unit, item, target, 10, 10),
            pb.MarkHit(unit, target, unit, item),
        ]
        actions = []
        component.after_strike(actions, nonlethal_playback, unit, item, target, None,
                               'attack', (0, 1), Strike.HIT)
        self.assertEqual([], actions)

    def test_damage_reduction_neutralizer_skips_only_final_percentage_and_flat_layers(self):
        unit = SimpleNamespace()
        target = SimpleNamespace()
        common = {
            'damage': 100,
            'defense': 0,
            'dynamic_damage': 0,
            'dynamic_resist': 0,
            'damage_multiplier': 1,
            'defense_multiplier': 1,
            'reduce_resist_multiplier': 0,
            'raw_damage': 0,
        }
        with patch.object(combat_calcs, 'damage', return_value=common['damage']), \
                patch.object(combat_calcs, 'defense', return_value=common['defense']), \
                patch.object(combat_calcs, 'compute_advantage_attr', return_value=0), \
                patch.object(combat_calcs, 'get_support_rank_bonus', return_value=([], [])), \
                patch.object(combat_calcs, 'resolve_weapon', return_value=None), \
                patch.object(combat_calcs.item_system, 'dynamic_damage', return_value=common['dynamic_damage']), \
                patch.object(skill_system, 'dynamic_damage', return_value=common['dynamic_damage']), \
                patch.object(skill_system, 'dynamic_resist', return_value=common['dynamic_resist']), \
                patch.object(skill_system, 'defense_multiplier', return_value=common['defense_multiplier']), \
                patch.object(skill_system, 'damage_multiplier', return_value=common['damage_multiplier']), \
                patch.object(skill_system, 'crit_anyway', return_value=False), \
                patch.object(skill_system, 'reduce_resist_multiplier', return_value=common['reduce_resist_multiplier']), \
                patch.object(skill_system, 'raw_damage', return_value=common['raw_damage']), \
                patch.object(combat_calcs.DB.constants, 'value', return_value=0), \
                patch.object(combat_calcs.DB.constants, 'get', return_value=SimpleNamespace(value=0)):
            with patch.object(skill_system, 'neutralize_foe_damage_reduction', return_value=False), \
                    patch.object(skill_system, 'resist_multiplier', return_value=0.5), \
                    patch.object(skill_system, 'flat_damage_reduction', return_value=10):
                self.assertEqual(40, combat_calcs.compute_damage(
                    unit, target, object(), None, 'attack', (0, 0)))
            with patch.object(skill_system, 'neutralize_foe_damage_reduction', return_value=True), \
                    patch.object(skill_system, 'resist_multiplier') as resist, \
                    patch.object(skill_system, 'flat_damage_reduction') as flat:
                self.assertEqual(100, combat_calcs.compute_damage(
                    unit, target, object(), None, 'attack', (0, 0)))
                resist.assert_not_called()
                flat.assert_not_called()

    def test_new_special_hooks_default_to_safe_values(self):
        unit = SimpleNamespace(skills=[])
        self.assertFalse(skill_system.neutralize_foe_damage_reduction(unit))
        self.assertFalse(skill_system.neutralize_foe_death_prevention(unit))
        self.assertEqual(0, skill_system.flat_damage_reduction(
            unit, None, None, None, 'attack', (0, 0), 0))
        self.assertFalse(skill_system.end_combat_after_strike(
            unit, None, None, None, 'attack', (0, 0)))

    def test_astra_crit_policy_is_active_only_during_proc(self):
        component = AstraProc({'disable_crit': True})
        component._should_modify_damage = True
        self.assertTrue(component.prevent_critical(None, None, None))
        component._should_modify_damage = False
        self.assertFalse(component.prevent_critical(None, None, None))

    def test_aether_first_strike_pierces_and_second_strike_heals_only_on_hit(self):
        component = AetherProc({
            'defense_ignore_percent': 0.7,
            'lifelink': 0.7,
        })
        component._should_modify_damage = True
        component._hitcount = 0
        self.assertAlmostEqual(0.3, component.defense_multiplier(
            None, None, None, None, 'attack', (0, 0), 20))
        component._hitcount = 1
        self.assertEqual(1, component.defense_multiplier(
            None, None, None, None, 'attack', (0, 1), 20))
        component.skill = SimpleNamespace()
        component.after_strike([], [], SimpleNamespace(), None, SimpleNamespace(), None,
                               'attack', (0, 1), 'miss')

    def test_dragon_proc_effects_add_pre_defense_attack_instead_of_multiplying_final_damage(self):
        project = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
        with open(project / 'game_data' / 'skills.json', encoding='utf-8') as source:
            skills = {skill['nid']: skill for skill in json.load(source)}

        unit = SimpleNamespace()
        target = SimpleNamespace()
        base_attack = 40
        defense = 30
        expected_damage = {
            'Dragon_Gaze_Effect': 22,
            'Dragon_Fang_Effect': 30,
            'Dragonic_Aura_Effect': 38,
        }
        for nid, expected in expected_damage.items():
            components = dict(skills[nid]['components'])
            dynamic_formula = components.get('dynamic_damage', '0')
            dynamic_damage = int(eval(dynamic_formula, {'__builtins__': {}},
                                      {'base_value': base_attack}))
            damage_multiplier = components.get('damage_multiplier', 1)
            with patch.object(combat_calcs, 'damage', return_value=base_attack), \
                    patch.object(combat_calcs, 'defense', return_value=defense), \
                    patch.object(combat_calcs, 'compute_advantage_attr', return_value=0), \
                    patch.object(combat_calcs, 'get_support_rank_bonus', return_value=([], [])), \
                    patch.object(combat_calcs, 'resolve_weapon', return_value=None), \
                    patch.object(combat_calcs.item_system, 'dynamic_damage', return_value=0), \
                    patch.object(skill_system, 'dynamic_damage', return_value=dynamic_damage), \
                    patch.object(skill_system, 'dynamic_resist', return_value=0), \
                    patch.object(skill_system, 'defense_multiplier', return_value=1), \
                    patch.object(skill_system, 'damage_multiplier', return_value=damage_multiplier), \
                    patch.object(skill_system, 'crit_anyway', return_value=False), \
                    patch.object(skill_system, 'neutralize_foe_damage_reduction', return_value=False), \
                    patch.object(skill_system, 'reduce_resist_multiplier', return_value=0), \
                    patch.object(skill_system, 'resist_multiplier', return_value=1), \
                    patch.object(skill_system, 'flat_damage_reduction', return_value=0), \
                    patch.object(skill_system, 'raw_damage', return_value=0), \
                    patch.object(combat_calcs.DB.constants, 'value', return_value=0), \
                    patch.object(combat_calcs.DB.constants, 'get', return_value=SimpleNamespace(value=0)):
                self.assertEqual(expected, combat_calcs.compute_damage(
                    unit, target, object(), None, 'attack', (0, 0)))


if __name__ == '__main__':
    import unittest
    unittest.main()
