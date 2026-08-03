import os
import unittest
from unittest.mock import MagicMock, call, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from app.engine import debug_mode


class DebugPlatformRoutingTests(unittest.TestCase):
    def test_android_debug_menu_replaces_router_with_in_game_drawer(self):
        state = MagicMock()
        state.state_names.return_value = ['free', 'debug']
        debug_state = debug_mode.DebugState()

        with patch.dict(debug_mode.config.SETTINGS, {'debug': 1}), \
                patch.object(debug_mode.game, 'state', state), \
                patch('app.engine.debug_mode.is_android_runtime', return_value=True):
            self.assertEqual('repeat', debug_state.start())

        self.assertEqual(
            [call.state_names(), call.back(), call.change('android_debugger')],
            state.method_calls)

    def test_android_debug_menu_closes_option_menu_before_opening_drawer(self):
        state = MagicMock()
        state.state_names.return_value = ['free', 'option_menu', 'debug']
        debug_state = debug_mode.DebugState()

        with patch.dict(debug_mode.config.SETTINGS, {'debug': 1}), \
                patch.object(debug_mode.game, 'state', state), \
                patch('app.engine.debug_mode.is_android_runtime', return_value=True):
            self.assertEqual('repeat', debug_state.start())

        self.assertEqual(
            [call.state_names(), call.back(), call.back(),
             call.change('android_debugger')], state.method_calls)

    def test_desktop_debug_menu_keeps_browser_service(self):
        state = MagicMock()
        debug_state = debug_mode.DebugState()

        with patch.dict(debug_mode.config.SETTINGS, {'debug': 1}), \
                patch.object(debug_mode.game, 'state', state), \
                patch('app.engine.debug_mode.is_android_runtime', return_value=False), \
                patch('app.engine.runtime_debugger_service.ensure_window') as ensure_window:
            self.assertEqual('repeat', debug_state.start())

        ensure_window.assert_called_once_with()
        state.back.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
