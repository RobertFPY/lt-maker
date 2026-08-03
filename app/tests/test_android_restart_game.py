import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.engine import general_states


class AndroidRestartGameTests(unittest.TestCase):
    def test_android_option_menu_replaces_quit_with_restart_game(self):
        fake_game = SimpleNamespace(
            current_mode=SimpleNamespace(permadeath=False),
            game_vars={}, unlocked_lore=[], is_roam=lambda: False)
        fake_db = SimpleNamespace(
            lore=[], constants=SimpleNamespace(
                get=lambda _nid: SimpleNamespace(value=False)))

        with patch('app.engine.general_states.game', fake_game), \
                patch('app.engine.general_states.DB', fake_db), \
                patch('app.engine.general_states.is_android_runtime', return_value=True), \
                patch('app.engine.general_states.save.SAVE_THREAD', None), \
                patch('app.engine.general_states.save.check_save_slots'), \
                patch('app.engine.general_states.save.SAVE_SLOTS', []):
            options, _info, _ignore, _events = general_states.OptionMenuState()._populate_options()

        self.assertIn('Restart Game', options)
        self.assertNotIn('Quit Game', options)


if __name__ == '__main__':
    unittest.main()
