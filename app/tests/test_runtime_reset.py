import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine.runtime_reset import queue_return_to_title
from app.engine.title_screen import TitleStartState


class RuntimeResetTests(unittest.TestCase):
    def test_queues_title_after_clearing_active_states(self):
        state = MagicMock()
        game = SimpleNamespace(memory={'old': 'value'}, state=state)
        controller = MagicMock()

        with patch('app.engine.runtime_debugger_controller.get_controller',
                   return_value=controller):
            queue_return_to_title(game, direct_to_title_main=True)

        self.assertEqual({'_return_directly_to_title_menu': True}, game.memory)
        state.clear.assert_called_once_with()
        state.change.assert_called_once_with('title_start')
        controller.reset_runtime_state.assert_called_once_with()

    def test_title_start_opens_title_menu_for_restart_game(self):
        title_state = TitleStartState()
        title_state._events_triggered = False
        title_state._return_directly_to_title_menu = True
        fake_game = SimpleNamespace(state=MagicMock())
        fake_game.state.from_transition.return_value = False

        with patch('app.engine.title_screen.game', fake_game):
            self.assertEqual('repeat', title_state.begin())

        fake_game.state.change.assert_called_once_with('title_main')


if __name__ == '__main__':
    unittest.main()
