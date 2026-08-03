import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from app.engine import android_debugger, engine


class AndroidDebuggerTextInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = android_debugger.AndroidDebuggerState()

    def test_text_entry_uses_native_text_input_without_drawer_keyboard(self):
        apply = MagicMock()
        with patch('app.engine.android_debugger.show_android_debug_input',
                   return_value=True) as show_input:
            self.state._begin_text('Find unit', '', apply)

        show_input.assert_called_once_with(
            '1', '', multiline=False, numeric=False)
        self.assertEqual('text', self.state.view)
        self.assertEqual('1', self.state._native_text_request_id)
        self.assertFalse(hasattr(self.state, '_draw_keyboard'))
        self.assertFalse(hasattr(self.state, '_tap_keyboard'))

    def test_text_entry_keeps_pygame_input_as_a_desktop_fallback(self):
        apply = MagicMock()
        with patch('app.engine.android_debugger.show_android_debug_input',
                   return_value=False), \
                patch.object(engine.pygame.key, 'start_text_input') as start_input:
            self.state._begin_text('Find unit', '', apply)

        start_input.assert_called_once_with()
        self.assertIsNone(self.state._native_text_request_id)

    def test_text_input_handles_ime_commit_and_ignores_keydown_unicode(self):
        self.state.view = 'text'
        self.state.text_value = ''
        self.state._refresh = MagicMock()
        events = [
            SimpleNamespace(type=engine.pygame.TEXTINPUT, text='đ'),
            SimpleNamespace(type=engine.KEYDOWN, key=9999, unicode='d'),
            SimpleNamespace(type=engine.pygame.TEXTEDITING, text='ấ'),
        ]
        input_manager = SimpleNamespace(get_input_events=lambda: events)

        with patch('app.engine.android_debugger.get_input_manager',
                   return_value=input_manager):
            self.state.take_input(None)

        self.assertEqual('đ', self.state.text_value)
        self.assertEqual('ấ', self.state.text_composition)

    def test_selection_is_cleared_when_no_longer_on_map(self):
        self.state.selected_nid = 'OffMap'
        self.state.snapshot = {'hovered_unit_nid': None, 'units': []}
        self.state.controller = MagicMock()

        self.state._sync_selection_from_snapshot()

        self.assertIsNone(self.state.selected_nid)
        self.state.controller.dispatch.assert_not_called()

    def test_selection_moves_to_eligible_hovered_unit(self):
        self.state.selected_nid = 'OffMap'
        self.state.snapshot = {
            'hovered_unit_nid': 'Eirika',
            'units': [{'nid': 'Eirika'}],
        }
        self.state.controller = MagicMock()
        self.state.controller.dispatch.return_value = {
            'detail': {'position': [4, 6]}}

        self.state._sync_selection_from_snapshot()

        self.assertEqual('Eirika', self.state.selected_nid)
        self.assertEqual((4, 6), (self.state.teleport_x, self.state.teleport_y))
        self.state.controller.dispatch.assert_called_once_with(
            'inspect_unit', {'nid': 'Eirika'})

    def test_begin_keeps_virtual_dpad_available(self):
        self.state.fluid = MagicMock()
        with patch.object(android_debugger, 'set_android_touch_consumer') as setter:
            self.state.begin()

        self.assertEqual(('UP', 'DOWN', 'LEFT', 'RIGHT'),
                         setter.call_args.kwargs['passthrough_buttons'])
        self.assertEqual(self.state._on_touch.__func__,
                         setter.call_args.args[0].__func__)

    def test_direction_moves_map_cursor_and_refreshes_hovered_unit(self):
        cursor = MagicMock()
        self.state._refresh = MagicMock()
        self.state.view = 'home'

        with patch.object(android_debugger.game, 'cursor', cursor):
            self.state.take_input('UP')

        cursor.take_input.assert_called_once_with()
        self.state._refresh.assert_called_with(force=True)

    def test_close_after_pops_drawer_before_queued_event(self):
        fake_game = SimpleNamespace(state=SimpleNamespace(temp_state=[]))
        self.state.controller = MagicMock()
        def queue_event(*_args, **_kwargs):
            fake_game.state.temp_state.append('event')
            return {'message': 'Queued.'}
        self.state.controller.dispatch.side_effect = queue_event
        self.state._refresh = MagicMock()
        self.state._sync_selection_from_snapshot = MagicMock()

        with patch('app.engine.android_debugger.game', fake_game):
            self.state._run('complete_chapter', close_after=True)

        self.assertEqual(['pop', 'event'], fake_game.state.temp_state)

    def test_drag_scrolls_without_activating_an_entry(self):
        self.state._entry_list = MagicMock(return_value=[
            (str(index), 'none', None) for index in range(20)])
        self.state._activate = MagicMock()
        point = (self.state.panel_x + 20, self.state.ROW_TOP + 30)

        self.state._on_touch('down', point, (1, 1))
        self.state._on_touch('move', (point[0], point[1] - 30), (1, 1))
        self.state._on_touch('up', (point[0], point[1] - 30), (1, 1))

        self.assertGreater(self.state.scroll, 0)
        self.state._activate.assert_not_called()

    def test_manual_number_input_rejects_invalid_then_accepts_value(self):
        apply = MagicMock()
        with patch.object(self.state, '_start_text_input'), \
                patch.object(self.state, '_stop_text_input'):
            self.state._begin_number('Money', 10, 0, 99, apply)
            self.state._begin_number_text()
            self.state.text_value = 'bad'
            self.state._finish_text(True)
            self.assertEqual('text', self.state.view)
            self.assertTrue(self.state.text_error)

            self.state.text_value = '42?'
            self.state._finish_text(True)

        self.assertEqual('number', self.state.view)
        self.assertEqual(42, self.state.number_value)
        self.assertEqual('42', self.state.text_value)
        apply.assert_not_called()

    def test_manual_number_input_returns_to_its_original_view_after_save(self):
        apply = MagicMock()
        self.state.view = 'fields'
        with patch.object(self.state, '_start_text_input'), \
                patch.object(self.state, '_stop_text_input'):
            self.state._begin_number('HP', 10, 0, 99, apply)
            self.state._begin_number_text()
            self.state.text_value = '42'
            self.state._finish_text(True)
            self.state._go_back_view()

        self.assertEqual('fields', self.state.view)
        self.assertEqual(42, self.state.number_value)

    def test_manual_number_input_returns_to_its_original_view_after_cancel(self):
        apply = MagicMock()
        self.state.view = 'fields'
        with patch.object(self.state, '_start_text_input'), \
                patch.object(self.state, '_stop_text_input'):
            self.state._begin_number('HP', 10, 0, 99, apply)
            self.state._begin_number_text()
            self.state._finish_text(False)
            self.state._go_back_view()

        self.assertEqual('fields', self.state.view)

    def test_native_save_applies_text_and_closes_the_overlay(self):
        apply = MagicMock()
        self.state.view = 'fields'
        result = SimpleNamespace(request_id='1', action='save', value='Eirika')
        with patch('app.engine.android_debugger.show_android_debug_input',
                   return_value=True), \
                patch('app.engine.android_debugger.poll_android_debug_input',
                      return_value=result), \
                patch('app.engine.android_debugger.dismiss_android_debug_input') as dismiss:
            self.state._begin_text('Find unit', '', apply)
            self.state._consume_native_text_result()

        apply.assert_called_once_with('Eirika')
        dismiss.assert_called_once_with('1')
        self.assertEqual('fields', self.state.view)

    def test_native_invalid_number_stays_open_and_displays_an_error(self):
        apply = MagicMock()
        result = SimpleNamespace(request_id='1', action='save', value='bad')
        with patch('app.engine.android_debugger.show_android_debug_input',
                   return_value=True), \
                patch('app.engine.android_debugger.poll_android_debug_input',
                      return_value=result), \
                patch('app.engine.android_debugger.show_android_debug_input_error') as show_error:
            self.state._begin_number('HP', 10, 0, 99, apply)
            self.state._begin_number_text()
            self.state._consume_native_text_result()

        self.assertEqual('text', self.state.view)
        self.assertEqual('1', self.state._native_text_request_id)
        self.assertEqual('Enter a whole number.', self.state.text_error)
        show_error.assert_called_once_with('1', 'Enter a whole number.')

    def test_fallback_layout_uses_full_width_without_a_label_row(self):
        self.state.text_label = 'HP'
        self.state.text_value = ''
        with patch('app.engine.android_debugger.get_android_visible_height',
                   return_value=160):
            empty_layout = self.state._input_layout()

        self.assertEqual((0, 0), empty_layout['dialog'].topleft)
        self.assertEqual(android_debugger.WINWIDTH, empty_layout['dialog'].width)
        self.assertEqual(4, empty_layout['input'].top)
        self.assertLess(empty_layout['input'].right, empty_layout['dialog'].right)

    def test_fallback_input_buttons_are_vertical_and_use_their_own_hit_rectangles(self):
        self.state.text_label = 'Find unit'
        self.state.text_value = ''
        layout = self.state._input_layout()
        self.assertEqual(layout['cancel'].centerx, layout['save'].centerx)
        self.assertLess(layout['cancel'].bottom, layout['save'].top)

        self.state._finish_text = MagicMock()
        self.state._tap_text_input(*layout['cancel'].center)
        self.state._finish_text.assert_called_once_with(False)

    def test_input_dialog_moves_into_visible_area_above_keyboard(self):
        with patch('app.engine.android_debugger.engine.get_screen_size',
                   return_value=(240, 160)), \
                patch('app.engine.android_debugger.get_android_visible_height',
                      return_value=80):
            dialog = self.state._input_dialog_rect()

        self.assertEqual(0, dialog.y)
        self.assertLessEqual(dialog.bottom, 80)

    def test_scrollbar_reaches_the_end_of_a_long_list_in_one_drag(self):
        entries = [(str(index), 'none', None) for index in range(500)]
        self.state._entry_list = MagicMock(return_value=entries)
        self.state._activate = MagicMock()
        track, _thumb = self.state._scrollbar_rects(entries)
        point = (track.centerx, track.top)

        self.state._on_touch('down', point, (1, 1))
        self.state._on_touch('move', (track.centerx, track.bottom - 1), (1, 1))
        self.state._on_touch('up', (track.centerx, track.bottom - 1), (1, 1))

        self.assertGreaterEqual(self.state.scroll, len(entries) - self.state.MAX_ROWS - 1)
        self.state._activate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
