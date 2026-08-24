import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.engine import action
from app.engine.game_state import GameState
from app.engine.item_components.target_components import EvalSpecialRange
from app.engine.objects.region import RegionObject
from app.engine.objects.skill import SkillObject
from app.engine.objects.unit import UnitObject
from app.engine.target_system import TargetSystem
from app.events.regions import RegionType
from app.utilities.data import Data


class CacheMemoizationTests(unittest.TestCase):
    def test_manhattan_sphere_cache_hit_and_forced_miss_are_equivalent(self):
        target_system = TargetSystem(game=SimpleNamespace())
        target_system._cached_base_manhattan_spheres.cache_clear()

        expected = target_system.find_manhattan_spheres({1, 3}, 4, -2)
        self.assertEqual(expected, target_system.find_manhattan_spheres({1, 3}, 4, -2))

        target_system._cached_base_manhattan_spheres.cache_clear()
        self.assertEqual(expected, target_system.find_manhattan_spheres({1, 3}, 4, -2))

    def test_eval_special_range_cache_hit_and_forced_miss_are_equivalent(self):
        EvalSpecialRange.calculate_range_restrict.cache_clear()

        expected = EvalSpecialRange.calculate_range_restrict('x == 0 or y == 0', 3)
        self.assertEqual(
            expected,
            EvalSpecialRange.calculate_range_restrict('x == 0 or y == 0', 3),
        )

        EvalSpecialRange.calculate_range_restrict.cache_clear()
        self.assertEqual(
            expected,
            EvalSpecialRange.calculate_range_restrict('x == 0 or y == 0', 3),
        )

    def test_visible_skill_cache_is_invalidated_by_public_skill_mutation(self):
        unit = UnitObject('cache_unit')
        first = SkillObject('first', 'First', '')
        second = SkillObject('second', 'Second', '')

        unit.add_skill(first, source='test')
        self.assertEqual([first], unit.skills)
        self.assertEqual([first], unit.skills)  # Cache hit

        unit.add_skill(second, source='test')
        self.assertEqual([first, second], unit.skills)

        unit.remove_skill(second, source='test')
        self.assertEqual([first], unit.skills)

    def test_region_query_cache_is_invalidated_by_region_action(self):
        # Construct only the query owner.  AddRegion is still used through its
        # public action path, including the action wrapper's publication hook.
        class RegionQueryGame:
            pass

        state = RegionQueryGame()
        state.level = SimpleNamespace(regions=Data())
        state.units = []
        state.on_alter_game_state = lambda: None
        state.get_region_under_pos = GameState.get_region_under_pos.__get__(
            state, RegionQueryGame)
        state.get_region_under_pos.cache_clear()

        region = RegionObject('cache_region', RegionType.EVENT)
        region.position = (2, 3)
        region.size = (1, 1)

        self.assertIsNone(state.get_region_under_pos((2, 3)))
        with patch.object(action, 'game', state):
            action.AddRegion(region).do()
            self.assertIs(region, state.get_region_under_pos((2, 3)))
            action.RemoveRegion(region).do()
        self.assertIsNone(state.get_region_under_pos((2, 3)))


if __name__ == '__main__':
    unittest.main()
