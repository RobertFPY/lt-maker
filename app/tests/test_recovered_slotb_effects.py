from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import combat_calcs, item_system, skill_system
from app.engine.combat import playback as pb


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


def inert_component(nid, value=None):
    return SimpleNamespace(nid=nid, value=value, defines=lambda hook: False)


def mock_skill(nid, components=None, *, special=False, weapon_special=False, uid=0):
    return SimpleNamespace(
        nid=nid,
        uid=uid,
        components=components or [],
        data={},
        special_skill=object() if special else None,
        weapon_special_skill=object() if weapon_special else None,
    )


class RuntimeUnit:
    def __init__(self, nid, team, hp, bonuses=None, position=(0, 0)):
        self.nid = nid
        self.team = team
        self._hp = hp
        self._bonuses = bonuses or {}
        self.position = position
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.tags = []
        self.equipped_weapon = None

    @property
    def all_skills(self):
        return self.skills

    def get_hp(self):
        return self._hp

    def stat_bonus(self, stat):
        return self._bonuses.get(stat, 0)


class FakeAddSkill:
    def __init__(self, unit, skill_nid, initiator=None):
        self.unit = unit
        self.skill_obj = SimpleNamespace(nid=skill_nid, data={})

    def do(self):
        self.unit.skills.append(self.skill_obj)


class TriangleModifier:
    nid = 'triangle_modifier'

    def __init__(self, value):
        self.value = value

    def defines(self, hook):
        return hook == 'modify_weapon_triangle'

    def modify_weapon_triangle(self, unit, item):
        return self.value


class TriangleItem:
    def __init__(self, weapon_type, components=None):
        self.weapon_type = weapon_type
        self.components = components or []


class TriangleUnit:
    def __init__(self, skill=None):
        self.wexp = {'Axe': 1, 'Dagger': 1}
        self.skills = [skill] if skill else []
        self.equipped_weapon = None


class RecoveredSlotBEffectsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom = importlib.import_module('custom_components.custom_skill_components')

    @staticmethod
    def _apply(actions):
        for act in actions:
            act.do()

    @staticmethod
    def _priority_skill(nid, priority, component, uid):
        skill = mock_skill(
            nid,
            [inert_component('priority', priority), component],
            uid=uid,
        )
        component.skill = skill
        return skill

    def test_cancel_affinity_tiers_restore_recovery_contract(self):
        for tier in (1, 2, 3):
            with self.subTest(tier=tier):
                components = dict(self.skills[f'Cancel_Affinity_T{tier}']['components'])
                self.assertEqual(tier, components['cancel_affinity'])
                self.assertNotIn('do_nothing', components)

        component = self.custom.CancelAffinity(3)
        unit = SimpleNamespace(skills=[self._priority_skill(
            'Cancel_Affinity_T3', 2, component, 3)])
        with patch.object(skill_system, 'condition', return_value=True):
            self.assertEqual(
                (1.0, 0.5),
                skill_system.weapon_triangle_multiplier_override(
                    unit, None, None, None, True, 0.5, 1.5),
            )
            self.assertEqual(
                (1.0, 1.5),
                skill_system.weapon_triangle_multiplier_override(
                    unit, None, None, None, False, 0.5, 1.5),
            )

        attacker = TriangleUnit(unit.skills[0])
        defender = TriangleUnit()
        axe_reaver = TriangleItem('Axe', [TriangleModifier(-2.0)])
        dagger = TriangleItem('Dagger')
        attacker.equipped_weapon = axe_reaver
        defender.equipped_weapon = dagger
        combat_calcs.compute_advantage.__wrapped__.cache_clear()
        with patch.object(item_system, 'weapon_type',
                          side_effect=lambda owner, item: item.weapon_type), \
                patch.object(item_system, 'weapon_triangle_override',
                             return_value=None), \
                patch.object(item_system, 'ignore_weapon_advantage',
                             return_value=False), \
                patch.object(skill_system, 'item_override',
                             side_effect=lambda owner, item:
                             [TriangleModifier(3.0)] if owner is attacker else []), \
                patch.object(skill_system, 'condition', return_value=True):
            self.assertEqual(
                -2,
                combat_calcs.compute_advantage_attr(
                    attacker, defender, axe_reaver, dagger, 'damage'),
            )
        combat_calcs.compute_advantage.__wrapped__.cache_clear()

    def test_special_spiral_arms_refreshes_and_expires_through_next_action(self):
        expected = {
            1: (10, "mode == 'attack'"),
            2: (10, None),
            3: (20, None),
        }
        for tier, (rate, condition) in expected.items():
            with self.subTest(tier=tier):
                components = dict(self.skills[f'Special_Spiral_T{tier}']['components'])
                self.assertEqual(rate, components['special_spiral_bonus'])
                self.assertNotIn('do_nothing', components)
                self.assertEqual(condition, components.get('combat_condition'))

        spiral = self.custom.SpecialSpiralBonus(10)
        spiral_skill = self._priority_skill('Special_Spiral_T1', 0, spiral, 10)
        spiral.init(spiral_skill)
        special = mock_skill(
            'New_Moon_T1',
            [inert_component('attack_proc', 'New_Moon_Effect')],
            special=True,
        )
        unit = SimpleNamespace(skills=[spiral_skill, special], equipped_weapon=None)
        playback = [pb.AttackProc(unit, mock_skill('New_Moon_Effect'))]

        spiral.start_combat([], unit, None, None, None, 'attack')
        actions = []
        with patch.object(self.custom.skill_system, 'condition', return_value=True):
            spiral.after_strike(actions, playback, unit, None, None, None,
                                'attack', (0, 0), None)
        self._apply(actions)
        self.assertEqual(10, spiral.modify_self_proc_rate(unit))

        with patch.object(self.custom.action, 'do', side_effect=lambda act: act.do()):
            spiral.end_combat(playback, unit, None, None, None, 'attack')
            spiral.on_wait(unit, True)
        self.assertTrue(spiral_skill.data['special_spiral_active'])

        spiral.start_combat([], unit, None, None, None, 'attack')
        with patch.object(self.custom.action, 'do', side_effect=lambda act: act.do()):
            spiral.end_combat([], unit, None, None, None, 'attack')
        self.assertFalse(spiral_skill.data['special_spiral_active'])

    def test_special_spiral_t2_arms_from_defensive_special_callback(self):
        spiral = self.custom.SpecialSpiralBonus(10)
        spiral_skill = self._priority_skill('Special_Spiral_T2', 1, spiral, 11)
        spiral.init(spiral_skill)
        special = mock_skill(
            'Defensive_Special',
            [inert_component('defense_proc', 'Defensive_Special_Effect')],
            special=True,
        )
        unit = SimpleNamespace(skills=[spiral_skill, special], equipped_weapon=None)
        playback = [pb.DefenseProc(unit, mock_skill('Defensive_Special_Effect'))]

        actions = []
        with patch.object(self.custom.skill_system, 'condition', return_value=True):
            spiral.after_take_strike(
                actions, playback, unit, None, None, None,
                'defense', (0, 0), None)
        self._apply(actions)
        self.assertTrue(spiral_skill.data['special_spiral_active'])

        low = self.custom.SpecialSpiralBonus(10)
        low_skill = self._priority_skill('Special_Spiral_T1', 0, low, 12)
        low.init(low_skill)
        high = self.custom.SpecialSpiralBonus(20)
        high_skill = self._priority_skill('Special_Spiral_T3', 2, high, 13)
        high.init(high_skill)
        low_skill.data['special_spiral_active'] = True
        high_skill.data['special_spiral_active'] = True
        stacked_unit = SimpleNamespace(skills=[low_skill, high_skill])
        self.assertEqual(0, low.modify_self_proc_rate(stacked_unit))
        self.assertEqual(20, high.modify_self_proc_rate(stacked_unit))

    def test_sword_and_shield_pulse_accumulate_only_on_their_own_strikes(self):
        for prefix, condition in (
                ('Sword_Pulser', "mode == 'attack'"),
                ('Shield_Pulse', "mode == 'defense'")):
            for tier, rate in ((1, 3), (2, 4), (3, 5)):
                with self.subTest(prefix=prefix, tier=tier):
                    components = dict(self.skills[f'{prefix}_T{tier}']['components'])
                    self.assertEqual(condition, components['combat_condition'])
                    self.assertEqual(rate, components['special_skill_pulse'])
                    self.assertNotIn('do_nothing', components)

        pulse = self.custom.SpecialSkillPulse(3)
        pulse_skill = mock_skill('Sword_Pulser_T1')
        pulse.skill = pulse_skill
        pulse.init(pulse_skill)
        special = mock_skill(
            'New_Moon_T1',
            [inert_component('attack_proc', 'New_Moon_Effect')],
            special=True,
        )
        unit = SimpleNamespace(skills=[pulse_skill, special])
        proc = [pb.AttackProc(unit, mock_skill('New_Moon_Effect'))]

        pulse.start_combat([], unit, None, None, None, 'attack')
        actions = []
        pulse.after_strike(actions, proc, unit, None, None, None,
                           'attack', (0, 0), None)
        self._apply(actions)
        actions = []
        pulse.after_strike(actions, proc, unit, None, None, None,
                           'attack', (0, 1), None)
        self._apply(actions)
        self.assertEqual(3, pulse_skill.data['special_skill_pulse_bonus'])

        actions = []
        pulse.after_strike(actions, proc + [pb.AttackProc(
            unit, mock_skill('New_Moon_Effect'))], unit, None, None, None,
            'attack', (1, 0), None)
        self._apply(actions)
        self.assertEqual(0, pulse_skill.data['special_skill_pulse_bonus'])

        shield = self.custom.SpecialSkillPulse(4)
        shield_skill = mock_skill('Shield_Pulse_T2')
        shield.skill = shield_skill
        shield.init(shield_skill)
        shield_unit = SimpleNamespace(skills=[shield_skill, special])
        shield_proc = [pb.AttackProc(
            shield_unit, mock_skill('New_Moon_Effect'))]
        shield.start_combat([], shield_unit, None, None, None, 'defense')
        actions = []
        shield.after_take_strike(
            actions, shield_proc, shield_unit, None, None, None,
            'defense', (0, 0), None)
        self._apply(actions)
        actions = []
        shield.after_take_strike(
            actions, shield_proc, shield_unit, None, None, None,
            'defense', (0, 1), None)
        self._apply(actions)
        self.assertEqual(4, shield_skill.data['special_skill_pulse_bonus'])
        actions = []
        shield.after_strike(
            actions, shield_proc, shield_unit, None, None, None,
            'defense', (1, 0), None)
        self._apply(actions)
        self.assertEqual(4, shield_skill.data['special_skill_pulse_bonus'])

    def test_sudden_panic_uses_current_next_action_lifecycle(self):
        expected = {1: (5, 3), 2: (3, 5), 3: (1, 7)}
        for tier, (hp_gap, radius) in expected.items():
            with self.subTest(tier=tier):
                components = dict(self.skills[f'Sudden_Panic_T{tier}']['components'])
                self.assertEqual(
                    {'rank': tier, 'hp_gap': hp_gap, 'radius': radius,
                     'status': 'Sudden_Panic_Effect'},
                    components['sudden_panic_before_combat'],
                )
                self.assertNotIn('do_nothing', components)
                self.assertNotIn('event_before_combat', components)
                self.assertIn('start of combat',
                              self.skills[f'Sudden_Panic_T{tier}']['desc'].lower())

        effect_components = dict(self.skills['Sudden_Panic_Effect']['components'])
        self.assertIn('sudden_panic_bonus_conversion_effect', effect_components)
        self.assertIn('lost_on_next_action', effect_components)
        self.assertIn('lost_on_end_chapter', effect_components)
        self.assertEqual(
            'Skill System Slot B/No Family',
            self.categories['Sudden_Panic_Effect'],
        )

        owner = RuntimeUnit('owner', 'player', 20)
        target = RuntimeUnit('target', 'enemy', 10, {'STR': 6, 'SKL': -4})
        same_team = RuntimeUnit('same', 'enemy', 10, position=(3, 0))
        other_team = RuntimeUnit('other', 'enemy2', 10, position=(1, 0))
        component = self.custom.SuddenPanicBeforeCombat({
            'rank': 3, 'hp_gap': 1, 'radius': 7,
            'status': 'Sudden_Panic_Effect',
        })
        parent = mock_skill('Sudden_Panic_T3', [component], uid=30)
        component.skill = parent
        owner.skills = [parent]

        with patch.object(self.custom.game, 'get_all_units',
                          return_value=[owner, target, other_team]), \
                patch.object(self.custom.skill_system, 'check_enemy',
                             side_effect=lambda unit, foe: unit.team != foe.team), \
                patch.object(self.custom.action, 'AddSkill', FakeAddSkill), \
                patch.object(self.custom.action, 'do',
                             side_effect=lambda act: act.do()):
            component.pre_combat([], owner, None, target, None, 'attack')
        self.assertEqual([], target.skills)

        with patch.object(self.custom.game, 'get_all_units',
                          return_value=[owner, target, same_team, other_team]), \
                patch.object(self.custom.skill_system, 'check_enemy',
                             side_effect=lambda unit, foe: unit.team != foe.team), \
                patch.object(self.custom.action, 'AddSkill', FakeAddSkill), \
                patch.object(self.custom.action, 'do',
                             side_effect=lambda act: act.do()):
            component.pre_combat([], owner, None, target, None, 'attack')
        self.assertEqual(1, len(target.skills))
        self.assertEqual(
            {'STR': 6, 'MAG': 0, 'SKL': 0, 'SPD': 0,
             'LCK': 0, 'DEF': 0, 'RES': 0},
            target.skills[0].data['sudden_panic_bonuses'],
        )
        self.assertFalse(target.skills[0].data['skip_current_wait'])

        effect = self.custom.SuddenPanicBonusConversionEffect()
        effect.skill = target.skills[0]
        self.assertEqual(-12, effect.stat_change(target)['STR'])
        self.assertEqual(0, effect.stat_change(target)['SKL'])

        target.skills.clear()
        combat = SimpleNamespace(finalizes_turn=True, event_combat=False)
        with patch.dict(self.custom.game.memory,
                        {'current_combat': combat}, clear=False), \
                patch.object(self.custom.game, 'get_all_units',
                             return_value=[owner, target, same_team]), \
                patch.object(self.custom.skill_system, 'check_enemy',
                             side_effect=lambda unit, foe: unit.team != foe.team), \
                patch.object(self.custom.action, 'AddSkill', FakeAddSkill), \
                patch.object(self.custom.action, 'do',
                             side_effect=lambda act: act.do()):
            component.pre_combat([], owner, None, target, None, 'defense')
        self.assertTrue(target.skills[0].data['skip_current_wait'])


if __name__ == '__main__':
    import unittest
    unittest.main()
