import unittest
from unittest.mock import MagicMock, patch

from app.data.database.difficulty_modes import GrowthOption
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.engine import unit_funcs
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject


class PityGrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.data.database.database import DB
        DB.load('testing_proj.ltproj', CURRENT_SERIALIZATION_VERSION)

    def setUp(self):
        from app.data.database.database import DB
        self.unit = UnitObject.from_prefab(DB.units.get('Eirika'))
        self.unit.stats = {nid: 0 for nid in DB.stats.keys()}

    def _pity_levelup_with_zero_growths(self, level):
        rng = MagicMock()
        rng.randint.return_value = 99
        with patch('app.engine.unit_funcs.growth_rate', return_value=0), \
                patch('app.engine.unit_funcs.static_random.get_levelup', return_value=rng):
            return unit_funcs._pity_levelup(self.unit, level)

    def assert_pity_bonus_applied(self, stat_changes):
        for nid, change in stat_changes.items():
            self.assertEqual(change, 0 if nid in ('CON', 'MOV') else 1)

    def test_unique_player_gets_four_pity_levelups_from_recruitment(self):
        for level in range(1, 5):
            self.unit.level = level
            stat_changes = self._pity_levelup_with_zero_growths(level)
            self.assert_pity_bonus_applied(stat_changes)

        self.unit.level = 5
        stat_changes = self._pity_levelup_with_zero_growths(5)
        self.assertTrue(all(change == 0 for change in stat_changes.values()))

    def test_unique_player_recruited_at_level_four_starts_pity_at_four(self):
        prefab = MagicMock(level=4, klass=self.unit.klass)
        self.unit.level = 4
        with patch.object(unit_funcs.DB.units, 'get', return_value=prefab):
            for level in range(4, 8):
                self.unit.level = level
                stat_changes = self._pity_levelup_with_zero_growths(level)
                self.assert_pity_bonus_applied(stat_changes)

            self.unit.level = 8
            stat_changes = self._pity_levelup_with_zero_growths(8)
            self.assertTrue(all(change == 0 for change in stat_changes.values()))

    def test_generic_enemy_uses_pity_but_named_enemy_uses_random(self):
        self.unit.team = 'enemy'
        self.unit.generic = True
        generic_changes = self._pity_levelup_with_zero_growths(1)
        self.assert_pity_bonus_applied(generic_changes)

        self.unit.generic = False
        named_changes = self._pity_levelup_with_zero_growths(1)
        self.assertTrue(all(change == 0 for change in named_changes.values()))

    def test_pity_mode_overrides_generic_enemy_leveling_method(self):
        old_mode = game.current_mode
        try:
            game.current_mode = MagicMock(growths=GrowthOption.PITY)
            self.unit.team = 'enemy'
            self.unit.generic = True
            with patch.object(unit_funcs.DB.constants, 'value', return_value='Random'):
                self.assertEqual(
                    unit_funcs.get_leveling_method(self.unit),
                    GrowthOption.PITY)
        finally:
            game.current_mode = old_mode

    def test_player_growth_menu_only_exposes_random_and_pity(self):
        from app.engine.title_screen import PLAYER_SELECTABLE_GROWTH_OPTIONS

        self.assertEqual(
            [growth.value for growth in PLAYER_SELECTABLE_GROWTH_OPTIONS],
            ['Random', 'Pity'])


if __name__ == '__main__':
    unittest.main()
