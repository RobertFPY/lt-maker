import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import skill_system
from app.engine.skill_components import movement_components


PROJECT = Path(__file__).resolve().parents[2] / 'Fire Emblem Tales of The Golden Knight.ltproj'


class WarpUnit:
    def __init__(self, nid, team, tags, hp=100, max_hp=100, position=(0, 0),
                 dead=False, is_dying=False):
        self.nid = nid
        self.team = team
        self.tags = tags
        self.hp = hp
        self.max_hp = max_hp
        self.position = position
        self.dead = dead
        self.is_dying = is_dying
        self.skills = []

    def get_hp(self):
        return self.hp

    def get_max_hp(self):
        return self.max_hp


class WarpBoard:
    def __init__(self, occupied=()):
        self.occupied = set(occupied)

    def get_unit(self, position):
        return object() if position in self.occupied else None


class WarpTargetSystem:
    @staticmethod
    def get_adjacent_positions(position):
        x, y = position
        return [(x + 1, y), (x, y + 1), (x - 1, y)]


class WarpGame:
    def __init__(self, units, occupied=()):
        self.units = units
        self.board = WarpBoard(occupied)
        self.target_system = WarpTargetSystem()


class FlierFamilyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        RESOURCES.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)
        cls.skills = {
            skill['nid']: skill
            for skill in json.loads((PROJECT / 'game_data' / 'skills.json').read_text(encoding='utf-8'))
        }

    def _expression(self, nid):
        return dict(self.skills[nid]['components'])['witch_warp_expression']

    def _warp_positions(self, nid, owner, anchors, occupied=(), blocked=()):
        component = movement_components.WitchWarpExpression(self._expression(nid))
        component.skill = SimpleNamespace(nid=nid)
        field_game = WarpGame(anchors, occupied)

        def evaluate_expression(expression, anchor, source, _position, local_args=None):
            return eval(expression, {'skill_system': skill_system}, {
                'unit': anchor,
                'target': source,
                'skill': local_args['skill'],
            })

        with patch('app.engine.evaluate.evaluate', side_effect=evaluate_expression), \
                patch.object(movement_components, 'game', field_game), \
                patch.object(movement_components.movement_funcs, 'check_weakly_traversable',
                             side_effect=lambda _unit, position: position not in blocked):
            return component.witch_warp(owner)

    def test_flier_inventory_and_owner_hp_tiers_are_preserved(self):
        nids = tuple(self.skills)
        flier_nids = tuple(nid for nid in nids if nid.startswith(('Aerobatics_', 'Flier_Formation_')))
        self.assertEqual(6, len(flier_nids))
        self.assertEqual(3, sum(nid.startswith('Aerobatics_') for nid in flier_nids))
        self.assertEqual(3, sum(nid.startswith('Flier_Formation_') for nid in flier_nids))
        self.assertTrue(all('witch_warp_expression' in dict(self.skills[nid]['components']) for nid in flier_nids))

        for family in ('Aerobatics', 'Flier_Formation'):
            self.assertEqual(
                'unit.get_hp() == unit.get_max_hp()',
                dict(self.skills[f'{family}_T1']['components'])['condition'])
            self.assertEqual(
                'unit.get_hp() > unit.get_max_hp() * 0.5',
                dict(self.skills[f'{family}_T2']['components'])['condition'])
            self.assertNotIn('condition', dict(self.skills[f'{family}_T3']['components']))

    def test_flier_formation_only_uses_eligible_living_allies(self):
        owner = WarpUnit('owner', 'player', ['Flying'])
        valid = WarpUnit('valid', 'player', ['Flying'], hp=81, position=(2, 0))
        enemy = WarpUnit('enemy', 'enemy', ['Flying'], position=(4, 0))
        at_threshold = WarpUnit('threshold', 'player', ['Flying'], hp=80, position=(6, 0))
        dead = WarpUnit('dead', 'player', ['Flying'], position=(8, 0), dead=True)
        dying = WarpUnit('dying', 'player', ['Flying'], position=(10, 0), is_dying=True)
        tile = WarpUnit('tile', 'player', ['Flying', 'Tile'], position=(12, 0))
        off_field = WarpUnit('off_field', 'player', ['Flying'], position=None)

        positions = self._warp_positions(
            'Flier_Formation_T3', owner,
            [owner, valid, enemy, at_threshold, dead, dying, tile, off_field],
            occupied={(3, 0)}, blocked={(2, 1)})

        self.assertEqual([(1, 0)], positions)

    def test_aerobatics_requires_an_eligible_living_ally_above_eighty_percent_hp(self):
        owner = WarpUnit('owner', 'player', ['Flying'])
        valid = WarpUnit('valid', 'player', ['Armor'], hp=81, position=(2, 0))
        low_infantry = WarpUnit('low_infantry', 'player', ['Infantry'], hp=80, position=(4, 0))
        enemy_horse = WarpUnit('enemy_horse', 'enemy', ['Horse'], hp=100, position=(6, 0))
        dead_horse = WarpUnit('dead_horse', 'player', ['Horse'], position=(8, 0), dead=True)
        flying = WarpUnit('flying', 'player', ['Flying'], position=(10, 0))

        positions = self._warp_positions(
            'Aerobatics_T3', owner,
            [owner, valid, low_infantry, enemy_horse, dead_horse, flying],
            occupied={(3, 0)}, blocked={(2, 1)})

        self.assertEqual([(1, 0)], positions)

    def test_all_tiers_store_the_ally_safe_warp_expressions(self):
        aerobatics = (
            "unit is not target and skill_system.check_ally(target, unit) and not unit.dead and "
            "not unit.is_dying and 'Tile' not in unit.tags and ('Infantry' in unit.tags or "
            "'Armor' in unit.tags or 'Horse' in unit.tags) and unit.get_hp() > "
            "unit.get_max_hp() * 0.8"
        )
        flier_formation = (
            "unit is not target and skill_system.check_ally(target, unit) and not unit.dead and "
            "not unit.is_dying and 'Tile' not in unit.tags and 'Flying' in unit.tags and "
            "unit.get_hp() > unit.get_max_hp() * 0.8"
        )
        for tier in range(1, 4):
            with self.subTest(family='Aerobatics', tier=tier):
                self.assertEqual(aerobatics, self._expression(f'Aerobatics_T{tier}'))
            with self.subTest(family='Flier Formation', tier=tier):
                self.assertEqual(flier_formation, self._expression(f'Flier_Formation_T{tier}'))


if __name__ == '__main__':
    import unittest
    unittest.main()
