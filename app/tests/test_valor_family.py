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
from app.engine import skill_component_access, skill_system
from app.engine.combat import simple_combat
from app.engine.objects.skill import SkillObject


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'
FAMILY = 'Skill System Slot C/Valor Family'
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


class ValorFamilyTests(TestCase):
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
        return self.custom_components.ValorFamilyProvider(values)

    def test_static_inventory_and_project_load_are_exact(self):
        parents = self._family_skills()
        components = [self._components(parent) for parent in parents]
        providers = [component['valor_family_provider'] for component in components
                     if 'valor_family_provider' in component]
        self.assertEqual(21, len(parents))
        self.assertEqual(21, len(providers))
        self.assertEqual(0, sum('do_nothing' in component for component in components))
        self.assertEqual({0: 7, 1: 7, 2: 7}, {
            priority: sum(component.get('priority') == priority for component in components)
            for priority in (0, 1, 2)})
        self.assertEqual(7, sum(provider['scope'] == 'self' for provider in providers))
        self.assertEqual(14, sum(provider['scope'] == 'team_weapon' for provider in providers))
        self.assertEqual(14, sum(provider['multiplier'] == 1.5 for provider in providers))
        self.assertEqual(7, sum(provider['multiplier'] == 2.0 for provider in providers))
        for kind in ('Sword', 'Axe', 'Lance', 'Bow', 'Dagger', 'Staff'):
            self.assertEqual([kind], self._components(self.skills[f'{kind}_Valor_T2'])[
                'valor_family_provider']['weapon_types'])
        for tier in (2, 3):
            self.assertEqual(TOME_TYPES, self._components(self.skills[f'Tome_Valor_T{tier}'])[
                'valor_family_provider']['weapon_types'])
        self.assertIsNotNone(DB.skills.get('Sword_Valor_T1'))
        self.assertTrue(hasattr(skill_system, 'valor_family_multiplier'))
        self.assertIsNotNone(skill_component_access.get_component('valor_family_provider'))

    def test_provider_requires_actual_item_and_recipient_weapon_type(self):
        owner = RuntimeUnit('owner')
        recipient = RuntimeUnit('recipient')
        self_provider = self._provider(scope='self', multiplier=1.5)
        sword = self._provider(scope='team_weapon', weapon_types=['Sword'], multiplier=1.5)
        tome = self._provider(scope='team_weapon', weapon_types=TOME_TYPES, multiplier=2.0)
        with patch.object(self.custom_components.item_system, 'weapon_type',
                          side_effect=lambda unit, item: item.weapon_type):
            self.assertEqual(1.5, self_provider.valor_family_multiplier(owner, owner, None))
            self.assertEqual(1.0, self_provider.valor_family_multiplier(owner, recipient, None))
            self.assertEqual(1.0, sword.valor_family_multiplier(owner, recipient, None))
            self.assertEqual(1.5, sword.valor_family_multiplier(owner, recipient, RuntimeItem('Sword')))
            for weapon_type in TOME_TYPES:
                self.assertEqual(2.0, tome.valor_family_multiplier(owner, recipient, RuntimeItem(weapon_type)))
            self.assertEqual(1.0, tome.valor_family_multiplier(owner, recipient, RuntimeItem('Sword')))

    def test_live_provider_filter_and_enemy_relationships_use_maximum(self):
        recipient = RuntimeUnit('recipient', 'enemy')
        enemy2 = RuntimeUnit('enemy2', 'enemy2')
        stronger = RuntimeUnit('stronger', 'enemy2')
        player = RuntimeUnit('player', 'player')
        offmap = RuntimeUnit('offmap', 'enemy2', None)
        dead = RuntimeUnit('dead', 'enemy2')
        dying = RuntimeUnit('dying', 'enemy2')
        tile = RuntimeUnit('tile', 'enemy2', tags=('Tile',))
        for unit, multiplier in ((enemy2, 1.5), (player, 9.0), (offmap, 9.0),
                                 (dead, 9.0), (dying, 9.0), (tile, 9.0)):
            unit.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Axe'],
                                                       multiplier=multiplier), unit.nid)]
        stronger.skills = [OwnedSkill(self._provider(scope='team_weapon', weapon_types=['Axe'],
                                                      multiplier=2.0), 'stronger')]
        dead.dead = True
        dying.is_dying = True
        with patch.object(simple_combat, 'game', FieldGame(
                [recipient, enemy2, stronger, player, offmap, dead, dying, tile])), \
                patch.object(self.custom_components.item_system, 'weapon_type', return_value='Axe'), \
                patch.object(simple_combat.skill_system, 'check_ally', side_effect=lambda provider, target:
                             {provider.team, target.team} == {'enemy', 'enemy2'} or provider is target):
            self.assertEqual(2.0, simple_combat.get_valor_family_multiplier(recipient, RuntimeItem('Axe')))

    def test_handle_wexp_multiplies_normal_double_and_kill_without_touching_miss_or_no_wexp(self):
        unit = RuntimeUnit('unit')
        target = RuntimeUnit('target', 'enemy')
        item = RuntimeItem('Staff')
        hit = SimpleNamespace(nid='mark_hit', attacker=unit, defender=target, item=item)
        miss = SimpleNamespace(nid='mark_miss', attacker=unit, defender=target, item=item)

        def award(double=False, kill=False, no_wexp=False, misses=True, marks=(hit,)):
            combat = simple_combat.SimpleCombat.__new__(simple_combat.SimpleCombat)
            combat.no_wexp = no_wexp
            combat.full_playback = list(marks)
            combat.alerts = False
            combat.get_from_full_playback = lambda nid: [mark for mark in combat.full_playback if mark.nid == nid]
            if kill:
                target.is_dying = True
            awards = []
            with patch.object(simple_combat.DB.constants, 'value', side_effect=lambda nid: {
                    'miss_wexp': misses, 'double_wexp': double, 'kill_wexp': kill}.get(nid)), \
                    patch.object(simple_combat.item_system, 'wexp', return_value=1.0), \
                    patch.object(simple_combat.skill_system, 'wexp_multiplier', return_value=2.0), \
                    patch.object(simple_combat.skill_system, 'enemy_wexp_multiplier', return_value=0.5), \
                    patch.object(simple_combat, 'get_valor_family_multiplier', return_value=1.5), \
                    patch.object(simple_combat.action, 'GainWexp', side_effect=lambda *args: args), \
                    patch.object(simple_combat.action, 'execute', side_effect=awards.append):
                combat.handle_wexp(unit, item, target)
            target.is_dying = False
            return [award[2] for award in awards]

        self.assertEqual([1.5], award())
        self.assertEqual([1.5], award(double=True))
        self.assertEqual([3.0], award(kill=True))
        self.assertEqual([3.0], award(double=True, kill=True))
        self.assertEqual([1.5], award(marks=(hit, miss)))
        self.assertEqual([], award(marks=(miss,), misses=False))
        self.assertEqual([1.5], award(marks=(miss,), misses=True))
        self.assertEqual([], award(no_wexp=True))

    def test_two_t1_providers_award_exact_float_three_and_event_wexp_stays_outside(self):
        self.assertNotIn('valor_family_multiplier', inspect.getsource(__import__('app.events.event_commands',
                         fromlist=['event_commands'])))
        player = RuntimeUnit('player')
        enemy = RuntimeUnit('enemy', 'enemy')
        staff = RuntimeItem('Staff')
        player.skills = [OwnedSkill(self._provider(scope='self', multiplier=1.5), 'player_t1')]
        enemy.skills = [OwnedSkill(self._provider(scope='self', multiplier=1.5), 'enemy_t1')]
        player_mark = SimpleNamespace(nid='mark_hit', attacker=player, defender=enemy, item=staff)
        enemy_mark = SimpleNamespace(nid='mark_hit', attacker=enemy, defender=player, item=staff)
        awards = []
        combat = simple_combat.SimpleCombat.__new__(simple_combat.SimpleCombat)
        combat.alerts = False
        combat.full_playback = [player_mark, enemy_mark]
        combat.get_from_full_playback = lambda nid: [mark for mark in combat.full_playback if mark.nid == nid]
        with patch.object(simple_combat, 'game', FieldGame([player, enemy])), \
                patch.object(simple_combat.item_system, 'weapon_type', return_value='Staff'), \
                patch.object(simple_combat.DB.constants, 'value', side_effect=lambda nid: {
                    'miss_wexp': False, 'double_wexp': False, 'kill_wexp': False}.get(nid)), \
                patch.object(simple_combat.item_system, 'wexp', return_value=1.0), \
                patch.object(simple_combat.skill_system, 'wexp_multiplier', return_value=1.0), \
                patch.object(simple_combat.skill_system, 'enemy_wexp_multiplier', return_value=1.0), \
                patch.object(simple_combat.action, 'GainWexp', side_effect=lambda *args: args), \
                patch.object(simple_combat.action, 'execute', side_effect=awards.append):
            combat.handle_wexp(player, staff, enemy)
            combat.handle_wexp(enemy, staff, player)
        self.assertEqual([1.5, 1.5], [award[2] for award in awards])
        self.assertEqual(3.0, sum(award[2] for award in awards))


if __name__ == '__main__':
    import unittest
    unittest.main()
