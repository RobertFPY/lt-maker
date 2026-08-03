import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine.runtime_debugger import DebugField
from app.engine.runtime_debugger_controller import RuntimeDebuggerController
from app.engine.game_state import GameState


class RuntimeDebuggerControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = RuntimeDebuggerController()

    def test_picker_and_notification_are_frontend_independent(self):
        self.controller.set_picked_position((7, 12))
        self.controller.publish_notification('Picked tile.', True)

        self.assertEqual(
            {'x': 7, 'y': 12, 'revision': 1}, self.controller._picked_position)
        self.assertEqual('Picked tile.', self.controller._notification['message'])

        self.controller.reset_runtime_state()

        self.assertIsNone(self.controller._picked_position)
        self.assertIsNone(self.controller._notification)

    def test_set_field_dispatch_uses_shared_runtime_operation(self):
        unit = SimpleNamespace(nid='Eirika')
        field = DebugField('hp', 'HP', 10, 0, 30)
        with patch.object(self.controller, '_get_unit', return_value=unit), \
                patch(
                    'app.engine.runtime_debugger_controller.RuntimeDebugger.editable_fields',
                    return_value=[field],
                ), patch(
                    'app.engine.runtime_debugger_controller.RuntimeDebugger.set_unit_field',
                    return_value=23,
                ) as set_field:
            result = self.controller.dispatch(
                'set_field', {'nid': 'Eirika', 'key': 'hp', 'value': 23})

        set_field.assert_called_once_with(unit, field, 23)
        self.assertEqual({'ok': True, 'message': 'HP set to 23.'}, result)

    def test_give_item_dispatch_preserves_optional_uses(self):
        unit = SimpleNamespace(nid='Eirika')
        with patch.object(self.controller, '_get_unit', return_value=unit), \
                patch(
                    'app.engine.runtime_debugger_controller.RuntimeDebugger.give_item',
                    return_value=True,
                ) as give_item:
            result = self.controller.dispatch(
                'give_item', {'nid': 'Eirika', 'item_nid': 'Vulnerary', 'uses': 3})

        give_item.assert_called_once_with(unit, 'Vulnerary', 3)
        self.assertEqual(
            {'ok': True, 'message': 'Gave Vulnerary with 3 use(s) to Eirika.'},
            result,
        )

    def test_game_state_active_unit_filter_matches_debugger_scope(self):
        on_map = SimpleNamespace(
            nid='OnMap', position=(0, 0), dead=False, is_dying=False, tags=[])
        dead = SimpleNamespace(
            nid='Dead', position=(1, 0), dead=True, is_dying=False, tags=[])
        dying = SimpleNamespace(
            nid='Dying', position=(2, 0), dead=False, is_dying=True, tags=[])
        off_map = SimpleNamespace(
            nid='OffMap', position=None, dead=False, is_dying=False, tags=[])
        tile = SimpleNamespace(
            nid='Tile', position=(3, 0), dead=False, is_dying=False, tags=['Tile'])

        result = GameState.get_all_units(SimpleNamespace(
            units=[on_map, dead, dying, off_map, tile]))

        self.assertEqual([on_map], result)

    def test_snapshot_requests_only_active_units_from_game_state(self):
        unit = SimpleNamespace(
            nid='Eirika', name='Eirika', team='player', level=1,
            position=(0, 0), tags=[],
            get_hp=lambda: 18, get_max_hp=lambda: 18,
        )
        state = SimpleNamespace(state_names=lambda: [], temp_state=[])
        fake_game = SimpleNamespace(
            level=None, state=state, cursor=None, board=None, turncount=1,
            game_vars={}, tilemap=None, get_money=lambda: 0,
            get_all_units=MagicMock(return_value=[unit]),
        )
        with patch('app.engine.runtime_debugger_controller.game', fake_game), \
                patch.object(self.controller, 'catalog', return_value={}):
            snapshot = self.controller.build_snapshot()

        fake_game.get_all_units.assert_called_once_with()
        self.assertEqual(['Eirika'], [entry['nid'] for entry in snapshot['units']])


if __name__ == '__main__':
    unittest.main()
