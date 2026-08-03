from dataclasses import dataclass
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.data.database.database import DB
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import combat_calcs


PROJECT = Path(__file__).resolve().parents[2] / "Fire Emblem Tales of The Golden Knight.ltproj"


@dataclass(eq=False)
class MockItem:
    weapon_type: str


@dataclass(eq=False)
class MockUnit:
    wexp: dict


class GoldenKnightWeaponTriangleTests(TestCase):
    ELEMENTS = ("Fire", "Wind", "Earth", "Thunder", "Water")
    MAGIC = ("Light", "Fire", "Wind", "Thunder", "Water", "Earth", "Anima", "Dark")
    TRIANGLE_TYPES = ("Sword", "Dagger", "Lance", "Axe", "Bow", "Staff") + MAGIC

    @classmethod
    def setUpClass(cls):
        DB.load(str(PROJECT), CURRENT_SERIALIZATION_VERSION)

    def setUp(self):
        self.patchers = [
            patch("app.engine.item_system.weapon_type", lambda unit, item: item.weapon_type if item else None),
            patch("app.engine.item_system.weapon_triangle_override", lambda unit, item: None),
            patch("app.engine.item_system.ignore_weapon_advantage", lambda unit, item: False),
            patch("app.engine.item_system.modify_weapon_triangle", lambda unit, item: 1),
        ]
        for patcher in self.patchers:
            patcher.start()
        combat_calcs.compute_advantage.__wrapped__.cache_clear()

    def tearDown(self):
        combat_calcs.compute_advantage.__wrapped__.cache_clear()
        for patcher in self.patchers:
            patcher.stop()

    def assert_triangle(self, attacker_type, defender_type, damage, accuracy):
        attacker = MockUnit({attacker_type: 1})
        defender = MockUnit({defender_type: 1})
        attacker_item = MockItem(attacker_type)
        defender_item = MockItem(defender_type)
        self.assertEqual(
            damage,
            combat_calcs.compute_advantage_attr(
                attacker, defender, attacker_item, defender_item, "damage"))
        self.assertEqual(
            accuracy,
            combat_calcs.compute_advantage_attr(
                attacker, defender, attacker_item, defender_item, "accuracy"))

    def expected_triangle_sign(self, attacker_type, defender_type):
        if "Staff" in (attacker_type, defender_type) or attacker_type == defender_type:
            return 0

        if attacker_type in self.ELEMENTS and defender_type in self.ELEMENTS:
            defender_index = self.ELEMENTS.index(defender_type)
            if attacker_type == self.ELEMENTS[defender_index - 1]:
                return 1
            attacker_index = self.ELEMENTS.index(attacker_type)
            if defender_type == self.ELEMENTS[attacker_index - 1]:
                return -1
            return 0

        if attacker_type in self.MAGIC and defender_type in self.MAGIC:
            magic_group = {
                "Light": 0,
                "Fire": 1, "Wind": 1, "Thunder": 1,
                "Water": 1, "Earth": 1, "Anima": 1,
                "Dark": 2,
            }
            attacker_group = magic_group[attacker_type]
            defender_group = magic_group[defender_type]
            if attacker_group == defender_group:
                return 0
            return 1 if (attacker_group - defender_group) % 3 == 1 else -1

        tier_one_group = {
            "Axe": 0, "Bow": 0,
            "Lance": 1, "Dagger": 1,
            "Sword": 2,
            **{magic_type: 2 for magic_type in self.MAGIC},
        }
        attacker_group = tier_one_group[attacker_type]
        defender_group = tier_one_group[defender_type]
        if attacker_group == defender_group:
            return 0
        return 1 if (attacker_group - defender_group) % 3 == 2 else -1

    def test_complete_matrix_matches_three_tier_priority(self):
        for attacker_type in self.TRIANGLE_TYPES:
            for defender_type in self.TRIANGLE_TYPES:
                with self.subTest(attacker=attacker_type, defender=defender_type):
                    sign = self.expected_triangle_sign(attacker_type, defender_type)
                    self.assert_triangle(attacker_type, defender_type, sign, sign * 15)

    def test_tier_one_weapon_groups(self):
        self.assert_triangle("Axe", "Dagger", 1, 15)
        self.assert_triangle("Bow", "Lance", 1, 15)
        self.assert_triangle("Lance", "Sword", 1, 15)
        self.assert_triangle("Dagger", "Fire", 1, 15)
        self.assert_triangle("Sword", "Bow", 1, 15)
        self.assert_triangle("Fire", "Axe", 1, 15)
        self.assert_triangle("Fire", "Lance", -1, -15)
        self.assert_triangle("Staff", "Sword", 0, 0)

    def test_tier_two_magic_triangle(self):
        self.assert_triangle("Dark", "Fire", 1, 15)
        self.assert_triangle("Fire", "Light", 1, 15)
        self.assert_triangle("Light", "Dark", 1, 15)

    def test_tier_three_element_cycle_and_neutral_matchup(self):
        self.assert_triangle("Fire", "Wind", 1, 15)
        self.assert_triangle("Wind", "Earth", 1, 15)
        self.assert_triangle("Earth", "Thunder", 1, 15)
        self.assert_triangle("Thunder", "Water", 1, 15)
        self.assert_triangle("Water", "Fire", 1, 15)
        self.assert_triangle("Thunder", "Fire", 0, 0)

    def test_only_higher_weapon_rank_receives_rank_bonus(self):
        sword = MockItem("Sword")
        axe = MockItem("Axe")
        rank_a = MockUnit({"Sword": 181})
        another_rank_a = MockUnit({"Axe": 249})
        rank_b = MockUnit({"Axe": 121})

        higher_bonus = combat_calcs.get_weapon_rank_bonus(rank_a, sword, rank_b, axe)
        self.assertEqual((3, 0), (higher_bonus.damage, higher_bonus.accuracy))
        self.assertIsNone(
            combat_calcs.get_weapon_rank_bonus(rank_b, axe, rank_a, sword))
        self.assertIsNone(
            combat_calcs.get_weapon_rank_bonus(rank_a, sword, another_rank_a, axe))

    def test_staff_rank_bonus_has_heal_value(self):
        staff = MockItem("Staff")
        rank_ss = MockUnit({"Staff": 331})
        bonus = combat_calcs.get_weapon_rank_bonus(rank_ss, staff)
        self.assertEqual((4, 10), (bonus.heal, bonus.accuracy))

    def test_complete_weapon_rank_bonus_table(self):
        rank_wexp = {"C": 71, "B": 121, "A": 181, "S": 251, "SS": 331}
        sword_dagger = {
            "C": (1, 0, 0), "B": (2, 0, 0), "A": (3, 0, 0),
            "S": (4, 5, 0), "SS": (5, 5, 0),
        }
        lance_bow_magic = {
            "C": (1, 0, 0), "B": (1, 5, 0), "A": (2, 5, 0),
            "S": (3, 10, 0), "SS": (4, 10, 0),
        }
        axe = {
            "C": (0, 5, 0), "B": (0, 10, 0), "A": (1, 10, 0),
            "S": (2, 10, 0), "SS": (2, 15, 0),
        }
        staff = {
            "C": (0, 0, 1), "B": (0, 5, 1), "A": (0, 5, 2),
            "S": (0, 5, 3), "SS": (0, 10, 4),
        }
        expected_by_type = {
            "Sword": sword_dagger,
            "Dagger": sword_dagger,
            "Lance": lance_bow_magic,
            "Bow": lance_bow_magic,
            "Axe": axe,
            "Staff": staff,
            **{magic_type: lance_bow_magic for magic_type in self.MAGIC},
        }

        for weapon_type, expected_by_rank in expected_by_type.items():
            item = MockItem(weapon_type)
            for rank, expected in expected_by_rank.items():
                with self.subTest(weapon_type=weapon_type, rank=rank):
                    unit = MockUnit({weapon_type: rank_wexp[rank]})
                    bonus = combat_calcs.get_weapon_rank_bonus(unit, item)
                    self.assertEqual(
                        expected,
                        (bonus.damage, bonus.accuracy, bonus.heal))
