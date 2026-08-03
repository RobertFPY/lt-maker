import unittest
from unittest.mock import patch

from app.engine.movement.movement_component import MovementComponent
from app.engine.movement.unit_path_movement_component import UnitPathMovementComponent


class _FakeSprite:
    def __init__(self):
        self.offset = [0, 0]
        self.net_positions = []
        self.reset_count = 0

    def handle_net_position(self, net_position):
        self.net_positions.append(net_position)

    def reset(self):
        self.reset_count += 1
        self.offset[:] = [0, 0]


class _FakeUnit:
    def __init__(self):
        self.position = (0, 0)
        self.sprite = _FakeSprite()
        self.consumed_movement = []

    def consume_movement(self, cost):
        self.consumed_movement.append(cost)


def _component(path):
    component = UnitPathMovementComponent.__new__(UnitPathMovementComponent)
    unit = _FakeUnit()
    MovementComponent.__init__(component, unit)
    component.path = list(path)
    component.goal = component.path[0] if component.path else None
    component.event = False
    component.speed = 120
    component._last_update = 0
    return component


class UnitPathMovementTimingTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch('app.engine.movement.unit_path_movement_component.movement_funcs.check_position', return_value=True),
            patch('app.engine.movement.unit_path_movement_component.movement_funcs.get_mcost', return_value=1),
            patch('app.engine.movement.unit_path_movement_component.movement_funcs.handle_terrain_traversal'),
        ]
        for patched in self.patches:
            patched.start()

    def tearDown(self):
        for patched in reversed(self.patches):
            patched.stop()

    def test_remainder_is_preserved_after_a_tile_boundary(self):
        component = _component([(3, 0), (2, 0), (1, 0)])

        component.update(130)

        self.assertEqual((1, 0), component.unit.position)
        self.assertEqual(120, component._last_update)
        self.assertEqual([1, 0], component.unit.sprite.offset)

    def test_movement_result_is_independent_of_frame_partitioning(self):
        one_frame = _component([(3, 0), (2, 0), (1, 0)])
        split_frames = _component([(3, 0), (2, 0), (1, 0)])

        one_frame.update(130)
        split_frames.update(65)
        split_frames.update(130)

        self.assertEqual(one_frame.unit.position, split_frames.unit.position)
        self.assertEqual(one_frame._last_update, split_frames._last_update)
        self.assertEqual(one_frame.unit.sprite.offset, split_frames.unit.sprite.offset)

    def test_hitch_consumes_completed_tiles_and_retains_next_segment_progress(self):
        component = _component([(4, 0), (3, 0), (2, 0), (1, 0)])

        component.update(250)

        self.assertEqual((2, 0), component.unit.position)
        self.assertEqual(240, component._last_update)
        self.assertEqual([1, 0], component.unit.sprite.offset)
        self.assertEqual([1, 1], component.unit.consumed_movement)

    def test_obstacle_stops_a_multi_tile_catch_up_in_order(self):
        component = _component([(2, 0), (1, 0)])
        finish_calls = []

        def finish(surprise=False):
            finish_calls.append(surprise)
            component.active = False

        component.finish = finish
        with patch(
                'app.engine.movement.unit_path_movement_component.movement_funcs.check_position',
                side_effect=(True, False)):
            component.update(240)

        self.assertEqual((1, 0), component.unit.position)
        self.assertEqual([True], finish_calls)
        self.assertFalse(component.active)


if __name__ == '__main__':
    unittest.main()
