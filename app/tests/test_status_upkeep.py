import unittest
from unittest.mock import Mock

from app.engine.status_upkeep import StatusUpkeepState


class StatusUpkeepStateTests(unittest.TestCase):
    def test_get_next_unit_skips_unit_removed_after_queue_was_built(self):
        state = StatusUpkeepState()
        on_map_unit = Mock(position=(4, 5))
        removed_unit = Mock(position=None)
        state.units = [on_map_unit, removed_unit]
        state.is_traveler = Mock(return_value=False)

        result = state.get_next_unit()

        self.assertIs(result, on_map_unit)
        state.is_traveler.assert_called_once_with(removed_unit)

    def test_get_next_unit_returns_none_when_queue_only_has_removed_units(self):
        state = StatusUpkeepState()
        removed_unit = Mock(position=None)
        state.units = [removed_unit]
        state.is_traveler = Mock(return_value=False)

        result = state.get_next_unit()

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
