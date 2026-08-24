import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import item_system, skill_component_access, skill_system
from app.engine.item_components import exp_components
from app.engine.objects.skill import SkillObject
from app.engine.skill_components.base_components import ExpMultiplier


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Experience Family'
DRAGON_UNITS = ['Martin', 'Bella', 'Nils', 'Ninian', 'Aenir', 'John', 'Bragigas']
TOME_TYPES = ['Light', 'Fire', 'Wind', 'Thunder', 'Water', 'Earth', 'Anima', 'Dark']


class RuntimeUnit:
    def __init__(self, nid, team='player', position=(0, 0), tags=()):
        self.nid = nid
        self.team = team
        self.position = position
        self.tags = set(tags)
        self.skills = []
        self.dead = False
        self.is_dying = False
        self.level = 1
        self.exp = 0
        self.equipped_weapon = None

    @property
    def all_skills(self):
        return self.skills


class OwnedSkill:
    def __init__(self, component, uid):
        self.components = [component]
        self.uid = uid
        self.grey_if_inactive = False
        self.hidden_if_inactive = False
        self.hidden = False
        self.is_terrain = False


class FieldGame:
    def __init__(self, units):
        self.units = units

    def get_all_units(self):
        return self.units


class RuntimeItem:
    def __init__(self, weapon_type):
        self.weapon_type = weapon_type


class ExperienceFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skills = {skill['nid']: skill for skill in json.loads(
            (PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))}
        cls.categories = json.loads((PROJECT / 'game_data' / 'skills.category.json').read_text(
            encoding='utf-8'))
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.custom_components = importlib.import_module('custom_components.custom_skill_components')

    @classmethod
    def _family_skills(cls):
        return [skill for nid, skill in cls.skills.items() if cls.categories.get(nid) == FAMILY]

    @staticmethod
    def _components(skill):
        return dict(skill['components'])

    def _provider(self, **values):
        return self.custom_components.ExperienceFamilyProvider(values)

    def _family_skill(self, nid):
        return SkillObject.from_prefab(DB.skills.get(nid))

    def test_static_inventory_is_exact_and_replaces_every_placeholder(self):
        parents = self._family_skills()
        components = [self._components(parent) for parent in parents]
        providers = [component['experience_family_provider'] for component in components
                     if 'experience_family_provider' in component]
        self.assertEqual(24, len(parents))
        self.assertEqual(24, len(providers))
        self.assertEqual(0, sum('do_nothing' in component for component in components))
        self.assertEqual({0: 8, 1: 8, 2: 8}, {
            priority: sum(component.get('priority') == priority for component in components)
            for priority in (0, 1, 2)})
        self.assertEqual(8, sum(provider['scope'] == 'self' for provider in providers))
        self.assertEqual(14, sum(provider['scope'] == 'team_weapon' for provider in providers))
        self.assertEqual(2, sum(provider['scope'] == 'team_units' for provider in providers))
        self.assertEqual(16, sum(provider['multiplier'] == 1.5 for provider in providers))
        self.assertEqual(8, sum(provider['multiplier'] == 2.0 for provider in providers))
        self.assertEqual(TOME_TYPES, self._components(self.skills['Tome_Exp_T2'])[
            'experience_family_provider']['weapon_types'])
        for nid in ('Dragon_Exp_T2', 'Dragon_Exp_T3'):
            self.assertEqual(DRAGON_UNITS, self._components(self.skills[nid])[
                'experience_family_provider']['eligible_unit_nids'])

    def test_provider_scopes_use_recipient_item_and_exact_dragon_nids(self):
        owner = RuntimeUnit('owner')
        recipient = RuntimeUnit('recipient')
        martin = RuntimeUnit('Martin')
        clone = RuntimeUnit('Martin_Clone')
        sword = RuntimeItem('Sword')
        tome = RuntimeItem('Dark')
        dragon = self._provider(scope='team_units', eligible_unit_nids=DRAGON_UNITS,
                                multiplier=2.0)
        weapon = self._provider(scope='team_weapon', weapon_types=['Sword'], multiplier=1.5)
        self_provider = self._provider(scope='self', multiplier=1.5)
        with patch.object(self.custom_components.item_system, 'weapon_type',
                          side_effect=lambda target, item: item.weapon_type):
            self.assertEqual(1.5, self_provider.experience_family_multiplier(owner, owner, None))
            self.assertEqual(1, self_provider.experience_family_multiplier(owner, recipient, None))
            self.assertEqual(1.5, weapon.experience_family_multiplier(owner, recipient, sword))
            self.assertEqual(1, weapon.experience_family_multiplier(owner, recipient, tome))
            self.assertEqual(2.0, dragon.experience_family_multiplier(owner, martin, None))
            self.assertEqual(1, dragon.experience_family_multiplier(owner, clone, None))

    def test_tome_scope_accepts_only_the_eight_configured_tome_types(self):
        owner = RuntimeUnit('owner')
        recipient = RuntimeUnit('recipient')
        tome = self._provider(scope='team_weapon', weapon_types=TOME_TYPES, multiplier=2.0)
        with patch.object(self.custom_components.item_system, 'weapon_type',
                          side_effect=lambda target, item: item.weapon_type):
            for weapon_type in TOME_TYPES:
                self.assertEqual(2.0, tome.experience_family_multiplier(
                    owner, recipient, RuntimeItem(weapon_type)))
            for weapon_type in ('Dragon', 'Default'):
                self.assertEqual(1, tome.experience_family_multiplier(
                    owner, recipient, RuntimeItem(weapon_type)))

    def test_live_allied_providers_max_stack_and_reject_invalid_or_hostile_sources(self):
        recipient = RuntimeUnit('recipient', 'player')
        valid = RuntimeUnit('valid', 'player')
        valid.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Sword'],
                                                  multiplier=1.5), 'valid')]
        stronger = RuntimeUnit('stronger', 'player')
        stronger.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Sword'],
                                                     multiplier=2.0), 'stronger')]
        off_map = RuntimeUnit('off_map', 'player', None)
        dead = RuntimeUnit('dead', 'player')
        dying = RuntimeUnit('dying', 'player')
        tile = RuntimeUnit('tile', 'player', tags=('Tile',))
        enemy = RuntimeUnit('enemy', 'enemy')
        for unit in (off_map, dead, dying, tile, enemy):
            unit.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Sword'],
                                                      multiplier=9.0), unit.nid)]
        dead.dead = True
        dying.is_dying = True
        sword = RuntimeItem('Sword')
        with patch.object(exp_components, 'game', FieldGame(
                [recipient, valid, stronger, off_map, dead, dying, tile, enemy])), \
                patch.object(self.custom_components.item_system, 'weapon_type',
                             return_value='Sword'), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda provider, target: provider.team == target.team):
            self.assertEqual(2.0, exp_components.get_experience_family_multiplier(recipient, sword))

    def test_enemy_and_enemy2_ally_relationships_are_respected(self):
        recipient = RuntimeUnit('enemy_recipient', 'enemy')
        enemy2_provider = RuntimeUnit('enemy2_provider', 'enemy2')
        player_provider = RuntimeUnit('player_provider', 'player')
        provider = self._provider(scope='team_weapon', weapon_types=['Axe'], multiplier=2.0)
        enemy2_provider.skills = [OwnedSkill(provider, 'enemy2')]
        player_provider.skills = [OwnedSkill(provider, 'player')]
        axe = RuntimeItem('Axe')
        allies = {('enemy2', 'enemy'), ('enemy', 'enemy2')}
        with patch.object(exp_components, 'game', FieldGame(
                [recipient, enemy2_provider, player_provider])), \
                patch.object(self.custom_components.item_system, 'weapon_type', return_value='Axe'), \
                patch.object(self.custom_components.skill_system, 'check_ally',
                             side_effect=lambda provider, target: provider.team == target.team
                             or (provider.team, target.team) in allies):
            self.assertEqual(2.0, exp_components.get_experience_family_multiplier(recipient, axe))

    def test_exp_modifier_composes_family_then_generic_and_keeps_enemy_kill_boss_rules(self):
        recipient = RuntimeUnit('recipient')
        recipient.skills = [OwnedSkill(ExpMultiplier(2.0), 'paragon')]
        provider = RuntimeUnit('provider')
        provider.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Staff'],
                                                     multiplier=1.5), 'provider')]
        enemy = RuntimeUnit('enemy', 'enemy')
        enemy.is_dying = True
        enemy.tags.add('Boss')
        staff = RuntimeItem('Staff')
        with patch.object(exp_components, 'game', FieldGame([recipient, provider])), \
                patch.object(self.custom_components.item_system, 'weapon_type', return_value='Staff'), \
                patch.object(self.custom_components.skill_system, 'check_ally', return_value=True), \
                patch.object(exp_components.DB.constants, 'value', side_effect=lambda nid: {
                    'kill_multiplier': 3, 'boss_bonus': 4}.get(nid)), \
                patch.object(skill_system, 'enemy_exp_multiplier', return_value=0.5):
            self.assertEqual(6, exp_components.modify_exp(2, recipient, None, staff))
            self.assertEqual(15, exp_components.modify_exp(2, recipient, enemy, staff))

    def test_t1_changes_fixed_normal_and_heal_item_exp_with_existing_rounding(self):
        unit = RuntimeUnit('unit')
        unit.skills = [OwnedSkill(self._provider(scope='self', multiplier=1.5), 't1')]
        enemy = RuntimeUnit('enemy', 'enemy')
        ally = RuntimeUnit('ally')
        item = RuntimeItem('Sword')
        fixed = exp_components.Exp(5)
        normal = exp_components.LevelExp()
        heal = exp_components.HealExp()
        fixed_mark = SimpleNamespace(nid='mark_hit', attacker=unit, defender=enemy, item=item)
        damage_mark = SimpleNamespace(nid='damage_hit', attacker=unit, defender=enemy, true_damage=1)
        heal_mark = SimpleNamespace(nid='heal_hit', attacker=unit, defender=ally, true_damage=4)
        with patch.object(exp_components, 'game', FieldGame([unit])), \
                patch.object(exp_components.skill_system, 'check_ally', return_value=True), \
                patch.object(exp_components.skill_system, 'check_enemy', return_value=True), \
                patch.object(exp_components.DB.constants, 'value', side_effect=lambda nid: {
                    'min_exp': 0, 'kill_multiplier': 1, 'boss_bonus': 0}.get(nid)), \
                patch.object(exp_components.DB.constants, 'get', return_value=SimpleNamespace(value=0)), \
                patch.object(normal, '_calc_exp', return_value=5), \
                patch.object(heal, '_calc_exp', return_value=5):
            self.assertEqual(7, fixed.exp([fixed_mark], unit, item))
            self.assertEqual(7, normal.exp([damage_mark], unit, item))
            self.assertEqual(7, heal.exp([heal_mark], unit, item))

    def test_exp_level_exp_and_heal_exp_pass_item_and_heal_has_no_enemy_multiplier(self):
        unit = RuntimeUnit('unit')
        target = RuntimeUnit('target')
        item = object()
        exp = exp_components.Exp(10)
        level_exp = exp_components.LevelExp()
        heal_exp = exp_components.HealExp()
        mark = SimpleNamespace(nid='mark_hit', attacker=unit, defender=target, item=item)
        damage = SimpleNamespace(nid='damage_hit', attacker=unit, defender=target, true_damage=1)
        heal = SimpleNamespace(nid='heal_hit', attacker=unit, defender=target, true_damage=4)
        with patch.object(exp_components, 'modify_exp', side_effect=lambda value, attacker, defender, arg:
                          value) as modify, \
                patch.object(exp_components.skill_system, 'check_enemy', return_value=True), \
                patch.object(exp_components.skill_system, 'check_ally', return_value=True), \
                patch.object(exp_components.DB.constants, 'value', return_value=0), \
                patch.object(exp_components.DB.constants, 'get', return_value=SimpleNamespace(value=0)), \
                patch.object(level_exp, '_calc_exp', return_value=5):
            exp.exp([mark], unit, item)
            level_exp.exp([damage], unit, item)
            heal_exp.exp([heal], unit, item)
        self.assertEqual([(10, unit, target, item), (5, unit, target, item), (0, unit, None, item)],
                         [call.args for call in modify.call_args_list])
        self.assertTrue(hasattr(skill_system, 'experience_family_multiplier'))
        self.assertIsNotNone(skill_component_access.get_component('experience_family_provider'))

    def test_event_gain_exp_and_wexp_paths_remain_outside_the_family_hook(self):
        from app.engine.combat import simple_combat
        from app.events import event_commands

        self.assertNotIn('experience_family_multiplier', inspect.getsource(event_commands))
        self.assertNotIn('experience_family_multiplier', inspect.getsource(simple_combat))


if __name__ == '__main__':
    import unittest
    unittest.main()
