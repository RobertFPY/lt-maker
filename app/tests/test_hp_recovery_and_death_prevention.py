from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import importlib
from pathlib import Path

from app.engine import action, skill_system
from app.engine.item_components.utility_components import Heal


class HPUnit:
    def __init__(self, hp=10, max_hp=20):
        self.hp = hp
        self.max_hp = max_hp
        self.skills = []

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp

    def set_hp(self, hp):
        self.hp = max(0, min(self.max_hp, hp))


class HPRecoveryAndDeathPreventionTests(TestCase):
    def test_positive_change_hp_is_zeroed_when_recovery_is_blocked_but_damage_is_not(self):
        unit = HPUnit()
        with patch.object(skill_system, 'block_hp_recovery', return_value=True):
            heal = action.ChangeHP(unit, 5)
            damage = action.ChangeHP(unit, -4)

        self.assertEqual(0, heal.num)
        self.assertEqual(-4, damage.num)
        heal.do()
        self.assertEqual(10, unit.get_hp())
        damage.do()
        self.assertEqual(6, unit.get_hp())

    def test_new_recovery_and_death_prevention_hooks_default_to_false(self):
        unit = HPUnit()
        self.assertFalse(skill_system.block_hp_recovery(unit))
        self.assertFalse(skill_system.block_death_prevention(unit))

    def test_staff_heal_emits_no_heal_playback_when_recovery_is_blocked(self):
        healer = HPUnit()
        target = HPUnit()
        component = Heal(5)
        component._get_heal_amount = lambda _unit, _target: 5
        component._get_rank_heal_bonus = lambda _unit, _item: 0
        actions, playback = [], []
        with patch.object(skill_system, 'block_hp_recovery', return_value=True):
            component.on_hit(actions, playback, healer, object(), target, None, None, 'attack', (0, 0))
        self.assertEqual(0, actions[0].num)
        self.assertEqual([], playback)

    def test_all_four_death_prevention_paths_honor_the_block(self):
        project = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
        import sys
        custom_path = str(project / 'resources')
        if custom_path not in sys.path:
            sys.path.insert(0, custom_path)
        custom = importlib.import_module('custom_components.custom_skill_components')
        core = importlib.import_module('app.engine.skill_components.combat2_components')
        unit = HPUnit(hp=0)
        with patch.object(skill_system, 'block_death_prevention', return_value=True), \
                patch.object(action, 'do') as execute:
            core.Miracle().cleanup_combat([], unit, None, None, None, 'attack')
            core.TrueMiracle().after_take_strike([], [], unit, None, None, None, 'attack', (0, 0), None)
            custom.FullMiracle().cleanup_combat([], unit, None, None, None, 'attack')
            custom.TrueMiracleEvent().after_take_strike([], [], unit, None, None, None, 'attack', (0, 0), None)
        execute.assert_not_called()

    def test_assassination_style_neutralizer_bypasses_every_death_prevention_path(self):
        project = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
        import sys
        custom_path = str(project / 'resources')
        if custom_path not in sys.path:
            sys.path.insert(0, custom_path)
        custom = importlib.import_module('custom_components.custom_skill_components')
        core = importlib.import_module('app.engine.skill_components.combat2_components')
        unit = HPUnit(hp=0)
        attacker = HPUnit()
        with patch.object(skill_system, 'block_death_prevention', return_value=False), \
                patch.object(skill_system, 'neutralize_foe_death_prevention', return_value=True), \
                patch.object(action, 'do') as execute:
            core.Miracle().cleanup_combat([], unit, None, attacker, None, 'attack')
            core.TrueMiracle().after_take_strike([], [], unit, None, attacker, None, 'attack', (0, 0), None)
            custom.FullMiracle().cleanup_combat([], unit, None, attacker, None, 'attack')
            custom.TrueMiracleEvent().after_take_strike([], [], unit, None, attacker, None, 'attack', (0, 0), None)
        execute.assert_not_called()

    def test_full_miracle_recovers_only_to_one_when_recovery_is_blocked(self):
        project = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
        import sys
        custom_path = str(project / 'resources')
        if custom_path not in sys.path:
            sys.path.insert(0, custom_path)
        custom = importlib.import_module('custom_components.custom_skill_components')
        component = custom.FullMiracle()
        component.skill = SimpleNamespace()
        unit = HPUnit(hp=0)
        with patch.object(skill_system, 'block_death_prevention', return_value=False), \
                patch.object(skill_system, 'block_hp_recovery', return_value=True), \
                patch.object(custom.action, 'do') as execute, \
                patch.object(custom, 'game', SimpleNamespace(death=SimpleNamespace(miracle=lambda _unit: None))), \
                patch.object(custom.action, 'TriggerCharge', return_value=SimpleNamespace()):
            component.cleanup_combat([], unit, None, None, None, 'attack')
        self.assertIsInstance(execute.call_args_list[0].args[0], action.SetHP)
        self.assertEqual(1, execute.call_args_list[0].args[0].new_hp)


if __name__ == '__main__':
    import unittest
    unittest.main()
