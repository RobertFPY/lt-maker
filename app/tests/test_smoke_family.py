import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import item_system, skill_system
from app.engine.objects.unit import UnitObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
SMOKE_PARENTS = (
    *(f'{stat}_Smoke_T{tier}' for stat in ('Str', 'Mag', 'Spd', 'Def', 'Res') for tier in range(1, 4)),
    'Atk_Smoke', 'Spd_Smoke_T4', 'Def_Res_Smoke_T3',
    *(f'Panic_Smoke_T{tier}' for tier in range(1, 5)),
    *(f'Fatal_Smoke_T{tier}' for tier in range(1, 5)),
)


class RuntimeUnit:
    def __init__(self, nid, team, position=(0, 0), hp=20):
        self.nid = nid
        self.team = team
        self.position = position
        self.hp = hp
        self.dead = False
        self.is_dying = False
        self.tags = []
        self.skills = []

    def get_hp(self):
        return self.hp


class SmokeFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.categories = json.loads(
            (PROJECT / 'game_data' / 'skills.category.json').read_text(encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    def test_all_smoke_parents_are_migrated_to_the_shared_distributor(self):
        self.assertEqual(26, len(SMOKE_PARENTS))
        for nid in SMOKE_PARENTS:
            with self.subTest(nid=nid):
                components = dict(self.skills[nid]['components'])
                self.assertIn('smoke_after_combat', components)
                self.assertNotIn('do_nothing', components)

    def test_smoke_effects_are_hidden_and_in_the_smoke_category(self):
        effect_nids = [nid for nid, category in self.categories.items()
                       if category == 'Skill System Slot C/Smoke Family' and nid not in SMOKE_PARENTS]
        self.assertEqual(25, len(effect_nids))
        for nid in effect_nids:
            self.assertIn('hidden', dict(self.skills[nid]['components']))

    def test_parent_mapping_covers_rank_gates_radii_and_compound_effects(self):
        parents = {nid: dict(self.skills[nid]['components']) for nid in SMOKE_PARENTS}
        for stat in ('Str', 'Mag', 'Spd', 'Def', 'Res'):
            for tier in range(1, 4):
                config = parents[f'{stat}_Smoke_T{tier}']['smoke_after_combat']
                self.assertEqual(f'stat:{stat.upper()}', config['group'])
                self.assertEqual(tier, config['rank'])
                self.assertEqual(2, config['foe_radius'])

        self.assertEqual(4, parents['Spd_Smoke_T4']['smoke_after_combat']['rank'])
        self.assertEqual(['Panic_Smoke_Effect', 'Panic_Smoke_T4_Penalty_Effect'],
                         parents['Panic_Smoke_T4']['smoke_after_combat']['foe_statuses'])
        for tier in (1, 2):
            self.assertTrue(parents[f'Panic_Smoke_T{tier}']['smoke_after_combat']['requires_initiation'])
            self.assertTrue(parents[f'Fatal_Smoke_T{tier}']['smoke_after_combat']['requires_initiation'])
        for tier in range(1, 5):
            self.assertIn('fatal_smoke_during_combat', parents[f'Fatal_Smoke_T{tier}'])

        self.assertIn('neutralize_foe_follow_up_grants',
                      dict(self.skills['Atk_Smoke_User_Effect']['components']))
        self.assertEqual(0.8, dict(self.skills['Spd_Smoke_T4_User_Effect']['components'])['resist_multiplier'])
        self.assertEqual(6, dict(self.skills['Def_Res_Smoke_T3_Ally_Effect']['components'])['damage'])

    def test_effect_lifetimes_and_penalty_shapes_match_the_contract(self):
        next_action = ('Atk_Smoke_Foe_Effect', 'Def_Res_Smoke_T3_Foe_Effect',
                       *(f'{stat}_Smoke_T{tier}_Effect' for stat in ('Str', 'Mag', 'Spd', 'Def', 'Res') for tier in range(1, 4)))
        for nid in next_action:
            components = dict(self.skills[nid]['components'])
            self.assertIn('lost_on_next_action', components)
            self.assertIn('lost_on_end_chapter', components)

        for nid in ('Atk_Smoke_User_Effect', 'Spd_Smoke_T4_User_Effect',
                    'Def_Res_Smoke_T3_Ally_Effect', 'Panic_Smoke_Effect',
                    'Panic_Smoke_T4_Penalty_Effect', 'Fatal_Smoke_Effect',
                    'Fatal_Smoke_T4_Death_Block_Effect'):
            self.assertIn('lost_on_endstep', dict(self.skills[nid]['components']))

        for nid in ('Str_Smoke_T1_Effect', 'Def_Res_Smoke_T3_Foe_Effect',
                    'Panic_Smoke_T4_Penalty_Effect'):
            penalty = dict(self.skills[nid]['components'])['smoke_penalty']
            self.assertTrue(all(isinstance(pair, list) and len(pair) == 2 for pair in penalty['stats']))

    def test_dead_primary_is_an_aoe_center_but_does_not_receive_a_status(self):
        component = self.custom_components.SmokeAfterCombat({
            'group': 'test', 'rank': 1, 'requires_initiation': False,
            'foe_radius': 2, 'foe_statuses': ['Smoke_Test_Effect'],
            'ally_radius': 0, 'ally_statuses': [],
        })
        source = RuntimeUnit('source', 'player')
        source.skills = [SimpleNamespace(components=[component])]
        primary = RuntimeUnit('primary', 'enemy', (2, 0), hp=0)
        primary.dead = True
        nearby = RuntimeUnit('nearby', 'enemy', (3, 0))
        queued = []
        game = SimpleNamespace(get_all_units=lambda: [source, primary, nearby])
        with patch.object(self.custom_components, 'game', game), \
                patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team.startswith('enemy')), \
                patch.object(self.custom_components.action, 'AddSkill',
                             side_effect=lambda unit, nid, source: queued.append((unit.nid, nid)) or SimpleNamespace(skill_obj=None)), \
                patch.object(self.custom_components.action, 'do'):
            component.end_combat([], source, None, primary, None, 'attack')
        self.assertEqual([('nearby', 'Smoke_Test_Effect')], queued)

    def test_ranked_smoke_uses_highest_eligible_tier_and_allows_initiation_fallback(self):
        source = RuntimeUnit('source', 'player')
        low = self.custom_components.SmokeAfterCombat({
            'group': 'panic', 'rank': 1, 'requires_initiation': False,
            'foe_radius': 1, 'foe_statuses': [], 'ally_radius': 0, 'ally_statuses': [],
        })
        high = self.custom_components.SmokeAfterCombat({
            'group': 'panic', 'rank': 2, 'requires_initiation': True,
            'foe_radius': 2, 'foe_statuses': [], 'ally_radius': 0, 'ally_statuses': [],
        })
        source.skills = [SimpleNamespace(components=[low]), SimpleNamespace(components=[high])]
        with patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components, 'game', SimpleNamespace(memory={'current_combat': SimpleNamespace(attacker=object())})):
            self.assertTrue(low._is_winner(source, 'defense'))
            self.assertFalse(high._is_winner(source, 'defense'))
        with patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components, 'game', SimpleNamespace(memory={'current_combat': SimpleNamespace(attacker=source)})):
            self.assertFalse(low._is_winner(source, 'attack'))
            self.assertTrue(high._is_winner(source, 'attack'))

    def test_initiation_is_limited_to_the_actual_lead_attacker_not_a_partner(self):
        component = self.custom_components.SmokeAfterCombat({
            'group': 'panic', 'rank': 1, 'requires_initiation': True,
            'foe_radius': 1, 'foe_statuses': [], 'ally_radius': 0, 'ally_statuses': [],
        })
        lead = RuntimeUnit('lead', 'player')
        partner = RuntimeUnit('partner', 'player')
        partner.skills = [SimpleNamespace(components=[component])]
        with patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components, 'game', SimpleNamespace(memory={'current_combat': SimpleNamespace(attacker=lead)})):
            self.assertFalse(component._is_winner(partner, 'attack'))
        lead.skills = [SimpleNamespace(components=[component])]
        with patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components, 'game', SimpleNamespace(memory={'current_combat': SimpleNamespace(attacker=lead)})):
            self.assertTrue(component._is_winner(lead, 'attack'))

    def test_distributor_includes_primary_foe_and_only_living_enemy_units_in_radius(self):
        component = self.custom_components.SmokeAfterCombat({
            'group': 'test', 'rank': 1, 'requires_initiation': False,
            'foe_radius': 2, 'foe_statuses': ['Smoke_Test_Effect'],
            'ally_radius': 0, 'ally_statuses': [],
        })
        source = RuntimeUnit('source', 'player')
        source.skills = [SimpleNamespace(components=[component])]
        primary = RuntimeUnit('primary', 'enemy', (2, 0))
        nearby = RuntimeUnit('nearby', 'enemy2', (3, 0))
        far = RuntimeUnit('far', 'enemy', (5, 0))
        ally = RuntimeUnit('ally', 'player', (2, 1))
        dead = RuntimeUnit('dead', 'enemy', (2, 1), hp=0)
        dead.dead = True
        game = SimpleNamespace(get_all_units=lambda: [source, primary, nearby, far, ally, dead])
        queued = []

        with patch.object(self.custom_components, 'game', game), \
                patch.object(self.custom_components.skill_system, 'check_enemy',
                             side_effect=lambda owner, target: target.team in ('enemy', 'enemy2')), \
                patch.object(self.custom_components.skill_system, 'condition', return_value=True), \
                patch.object(self.custom_components.action, 'AddSkill',
                             side_effect=lambda unit, nid, source: queued.append((unit.nid, nid)) or SimpleNamespace(skill_obj=None)), \
                patch.object(self.custom_components.action, 'do'):
            component.end_combat([], source, None, primary, None, 'attack')

        self.assertEqual({('primary', 'Smoke_Test_Effect'), ('nearby', 'Smoke_Test_Effect')}, set(queued))

    def test_panic_adjusts_the_raw_combined_skill_weapon_and_accessory_bonus(self):
        panic = self.custom_components.SmokePanicBonusConversion()
        unit = SimpleNamespace(equipped_weapon=object(), equipped_accessory=object())
        with patch.object(skill_system, 'stat_change', return_value=3), \
                patch.object(item_system, 'stat_change', side_effect=lambda _u, item, _stat:
                             2 if item is unit.equipped_weapon else 1), \
                patch.object(skill_system, 'stat_bonus_adjustment', side_effect=lambda _u, stat, base:
                             panic.stat_bonus_adjustment(_u, stat, base)):
            self.assertEqual(-6, UnitObject.stat_bonus(unit, 'STR'))


if __name__ == '__main__':
    import unittest
    unittest.main()
