from __future__ import annotations

import os
import pickle
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

if not pygame.display.get_init():
    pygame.display.init()
if pygame.display.get_surface() is None:
    pygame.display.set_mode((1, 1))

# Match engine startup import order and avoid the text/icon import cycle.
from app.engine import battle_animation  # noqa: F401
from app.engine import save


class RestartPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.location = lambda filename: os.path.join(self.temp_dir.name, filename)

    @staticmethod
    def _metadata(level_nid: str, *, kind: str = 'battle') -> dict:
        return {
            'kind': kind,
            'level_nid': level_nid,
            'level_title': level_nid,
            'playtime': 0,
            'realtime': 0,
            'mode': 'Normal',
        }

    def test_suspend_freezes_current_chapter_pristine_snapshot_before_worker(self):
        progress = {'level': {'nid': 'chapter-2'}, 'marker': 'mid-chapter'}
        snapshot = {'level': {'nid': 'chapter-2'}, 'marker': 'pristine'}
        fake_game = SimpleNamespace(
            chapter_start_snapshot=snapshot,
            level=SimpleNamespace(nid='chapter-2'),
            current_save_slot=None,
            state=SimpleNamespace(state_names=lambda: ['free'], temp_state=[]),
            save=Mock(return_value=(progress, self._metadata('chapter-2'))),
        )
        thread = Mock()

        with patch.object(save, 'capture_controller_compatibility'), \
                patch.object(save.threading, 'Thread', return_value=thread) as thread_class:
            save.suspend_game(fake_game, 'battle', slot=1)

        restart_payload = thread_class.call_args.kwargs['args'][6]
        self.assertEqual('pristine', restart_payload[0]['marker'])
        snapshot['marker'] = 'mutated-after-save-request'
        self.assertEqual('pristine', restart_payload[0]['marker'])
        self.assertEqual('start', restart_payload[1]['kind'])
        self.assertEqual('chapter-2', restart_payload[1]['level_nid'])

    def test_slot_b_restart_is_pristine_snapshot_not_current_progress(self):
        progress = {'level': {'nid': 'chapter-2'}, 'marker': 'mid-chapter'}
        pristine = {'level': {'nid': 'chapter-2'}, 'marker': 'pristine'}
        restart_metadata = self._metadata('chapter-2', kind='start')

        with patch.object(save, '_save_location', side_effect=self.location):
            save._save_io(
                progress, self._metadata('chapter-2'), old_slot=0, slot=1,
                restart_payload=(pristine, restart_metadata))

        with open(self.location(save.GAME_NID() + '-restart1.p'), 'rb') as fp:
            restart_data = pickle.load(fp)
        with open(self.location(save.GAME_NID() + '-restart1.pmeta'), 'rb') as fp:
            restart_meta = pickle.load(fp)
        self.assertEqual('pristine', restart_data['marker'])
        self.assertEqual('start', restart_meta['kind'])
        self.assertEqual('chapter-2', restart_meta['level_nid'])

    def test_stale_restart_is_removed_when_no_pristine_source_is_valid(self):
        stale_data = {'level': {'nid': 'chapter-1'}, 'marker': 'stale'}
        stale_meta = self._metadata('chapter-1', kind='start')
        progress = {'level': {'nid': 'chapter-2'}, 'marker': 'mid-chapter'}

        with patch.object(save, '_save_location', side_effect=self.location):
            restart_path = self.location(save.GAME_NID() + '-restart1.p')
            with open(restart_path, 'wb') as fp:
                pickle.dump(stale_data, fp)
            with open(restart_path + 'meta', 'wb') as fp:
                pickle.dump(stale_meta, fp)

            save._save_io(
                progress, self._metadata('chapter-2'), old_slot=0, slot=1,
                restart_payload=None)

        self.assertFalse(os.path.exists(restart_path))
        self.assertFalse(os.path.exists(restart_path + 'meta'))

    def test_valid_same_chapter_persistent_restart_can_be_carried_forward(self):
        pristine = {'level': {'nid': 'chapter-2'}, 'marker': 'pristine'}
        restart_meta = self._metadata('chapter-2', kind='start')
        progress = {'level': {'nid': 'chapter-2'}, 'marker': 'mid-chapter'}

        with patch.object(save, '_save_location', side_effect=self.location):
            old_restart = self.location(save.GAME_NID() + '-restart0.p')
            with open(old_restart, 'wb') as fp:
                pickle.dump(pristine, fp)
            with open(old_restart + 'meta', 'wb') as fp:
                pickle.dump(restart_meta, fp)

            save._save_io(progress, self._metadata('chapter-2'), old_slot=0, slot=1)

        with open(self.location(save.GAME_NID() + '-restart1.p'), 'rb') as fp:
            self.assertEqual('pristine', pickle.load(fp)['marker'])

    def test_title_restart_rejects_stale_slot_and_routes_valid_slot_canonically(self):
        from app.engine import title_screen

        state = title_screen.TitleRestartState.__new__(title_screen.TitleRestartState)
        state.state = 'normal'
        state.fluid = Mock(update=Mock(return_value=False), get_directions=Mock(return_value=[]))
        state.menu = Mock(current_index=0)
        restart_slot = SimpleNamespace(
            kind='start', save_loc='restart.p', level_nid='chapter-2', idx=0)
        main_slot = SimpleNamespace(kind='battle', level_nid='chapter-2', idx=0)
        fake_game = SimpleNamespace(memory={}, state=Mock())

        with patch.object(title_screen, 'game', fake_game), \
                patch.object(title_screen.save, 'RESTART_SLOTS', [restart_slot]), \
                patch.object(title_screen.save, 'SAVE_SLOTS', [main_slot]), \
                patch.object(title_screen, 'is_android_runtime', return_value=False), \
                patch.object(title_screen, 'get_sound_thread', return_value=Mock()), \
                patch.object(title_screen.save, 'restart_slot_matches_chapter', return_value=True), \
                patch.object(title_screen.save, 'load_game') as load_game, \
                patch.object(title_screen.save, 'remove_suspend'):
            state.take_input('SELECT')

        context = load_game.call_args.kwargs['context']
        self.assertEqual(save.LoadDestination.RESTART_LEVEL, context.destination)
        load_game.assert_called_once_with(fake_game, restart_slot, context=context)

        with patch.object(title_screen, 'game', fake_game), \
                patch.object(title_screen.save, 'RESTART_SLOTS', [restart_slot]), \
                patch.object(title_screen.save, 'SAVE_SLOTS', [main_slot]), \
                patch.object(title_screen, 'is_android_runtime', return_value=False), \
                patch.object(title_screen, 'get_sound_thread') as sounds, \
                patch.object(title_screen.save, 'restart_slot_matches_chapter', return_value=False), \
                patch.object(title_screen.save, 'load_game') as load_game:
            state.take_input('SELECT')

        load_game.assert_not_called()
        sounds.return_value.play_sfx.assert_called_once_with('Error')

    def test_android_title_restart_uses_the_same_validated_restart_source(self):
        from app.engine import title_screen

        state = title_screen.TitleRestartState.__new__(title_screen.TitleRestartState)
        state.state = 'normal'
        state.fluid = Mock(update=Mock(return_value=False), get_directions=Mock(return_value=[]))
        state.menu = Mock(current_index=0)
        state._start_android_load = Mock(return_value='repeat')
        restart_slot = SimpleNamespace(
            kind='start', save_loc='restart.p', level_nid='chapter-2', idx=0)
        main_slot = SimpleNamespace(kind='battle', level_nid='chapter-2', idx=0)
        fake_game = SimpleNamespace(memory={}, state=Mock())

        with patch.object(title_screen, 'game', fake_game), \
                patch.object(title_screen.save, 'RESTART_SLOTS', [restart_slot]), \
                patch.object(title_screen.save, 'SAVE_SLOTS', [main_slot]), \
                patch.object(title_screen, 'is_android_runtime', return_value=True), \
                patch.object(title_screen, 'get_sound_thread', return_value=Mock()), \
                patch.object(title_screen.save, 'restart_slot_matches_chapter', return_value=True):
            self.assertEqual('repeat', state.take_input('SELECT'))

        state._start_android_load.assert_called_once_with(
            restart_slot,
            transition_from='Restart Level',
            next_action='restart_level',
            remove_suspend=True,
            level_nid='chapter-2',
        )

    def test_title_current_save_uses_the_same_slot_on_desktop_and_android(self):
        from app.engine import title_screen

        save_slot = SimpleNamespace(
            kind='battle', save_loc='current-progress.p', level_nid='chapter-2', idx=0)

        desktop = title_screen.TitleLoadState.__new__(title_screen.TitleLoadState)
        desktop.state = 'normal'
        desktop.fluid = Mock(update=Mock(return_value=False), get_directions=Mock(return_value=[]))
        desktop.menu = Mock(current_index=0)
        desktop.save_slots = [save_slot]
        desktop_game = SimpleNamespace(memory={}, state=Mock())
        with patch.object(title_screen, 'game', desktop_game), \
                patch.object(title_screen, 'is_android_runtime', return_value=False), \
                patch.object(title_screen, 'get_sound_thread', return_value=Mock()), \
                patch.object(title_screen.save, 'load_game') as load_game, \
                patch.object(title_screen.save, 'remove_suspend'):
            desktop.take_input('SELECT')

        desktop_context = load_game.call_args.kwargs['context']
        load_game.assert_called_once_with(desktop_game, save_slot, context=desktop_context)
        self.assertEqual(save.LoadDestination.SAVED, desktop_context.destination)

        android = title_screen.TitleLoadState.__new__(title_screen.TitleLoadState)
        android.state = 'normal'
        android.fluid = Mock(update=Mock(return_value=False), get_directions=Mock(return_value=[]))
        android.menu = Mock(current_index=0)
        android.save_slots = [save_slot]
        android._start_android_load = Mock(return_value='repeat')
        android_game = SimpleNamespace(memory={}, state=Mock())
        with patch.object(title_screen, 'game', android_game), \
                patch.object(title_screen, 'is_android_runtime', return_value=True), \
                patch.object(title_screen, 'get_sound_thread', return_value=Mock()):
            self.assertEqual('repeat', android.take_input('SELECT'))

        android._start_android_load.assert_called_once_with(
            save_slot,
            transition_from='Load Game',
            next_action=None,
            remove_suspend=True,
        )

    def test_title_overworld_restart_uses_main_save_not_restart_slot(self):
        from app.engine import title_screen

        state = title_screen.TitleRestartState.__new__(title_screen.TitleRestartState)
        state.state = 'normal'
        state.fluid = Mock(update=Mock(return_value=False), get_directions=Mock(return_value=[]))
        state.menu = Mock(current_index=0)
        restart_slot = SimpleNamespace(kind='start', save_loc='restart.p', idx=0)
        main_slot = SimpleNamespace(kind='overworld', save_loc='overworld.p',
                                    level_nid=None, idx=0)
        fake_game = SimpleNamespace(memory={}, state=Mock())

        with patch.object(title_screen, 'game', fake_game), \
                patch.object(title_screen.save, 'RESTART_SLOTS', [restart_slot]), \
                patch.object(title_screen.save, 'SAVE_SLOTS', [main_slot]), \
                patch.object(title_screen, 'is_android_runtime', return_value=False), \
                patch.object(title_screen, 'get_sound_thread', return_value=Mock()), \
                patch.object(title_screen.save, 'load_game') as load_game, \
                patch.object(title_screen.save, 'remove_suspend'):
            state.take_input('SELECT')

        context = load_game.call_args.kwargs['context']
        load_game.assert_called_once_with(fake_game, main_slot, context=context)
        self.assertEqual(save.LoadDestination.OVERWORLD, context.destination)

    def test_game_over_input_hands_off_to_title_before_restart_selection(self):
        from app.engine import game_over

        state = game_over.GameOverState.__new__(game_over.GameOverState)
        state.state = 'stasis'
        fake_game = SimpleNamespace(memory={}, state=Mock())
        with patch.object(game_over, 'game', fake_game):
            state.take_input('SELECT')

        self.assertEqual('title_start', fake_game.memory['next_state'])
        fake_game.state.change.assert_called_once_with('transition_to')

    def test_restart_persistence_failure_removes_selectable_partial_pair(self):
        restart_data = {'level': {'nid': 'chapter-2'}, 'marker': 'pristine'}
        restart_meta = self._metadata('chapter-2', kind='start')
        restart_path = self.location('restart.p')

        with patch.object(save.os, 'replace', side_effect=OSError('disk full')):
            self.assertFalse(save._write_restart_payload(
                restart_path, (restart_data, restart_meta)))

        self.assertFalse(os.path.exists(restart_path))
        self.assertFalse(os.path.exists(restart_path + 'meta'))


if __name__ == '__main__':
    unittest.main()
