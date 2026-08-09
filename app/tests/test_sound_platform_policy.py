from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


class SoundPlatformPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.engine import sound
        cls.sound = sound

    def setUp(self):
        self.controller = object.__new__(self.sound.DefaultSoundController)

    def test_desktop_music_uses_only_existing_legacy_fade(self):
        self.controller.play_streamed_music = MagicMock(return_value=True)
        self.controller.fade_in = MagicMock(return_value=SimpleNamespace(nid='track'))

        with patch.object(self.sound, 'is_android_runtime', return_value=False):
            streamed = self.controller.play_music('track', fade_in=50)

        self.assertFalse(streamed)
        self.controller.play_streamed_music.assert_not_called()
        self.controller.fade_in.assert_called_once_with('track', fade_in=50)

    def test_android_stream_success_does_not_also_fade_legacy_music(self):
        self.controller.play_streamed_music = MagicMock(return_value=True)
        self.controller.fade_in = MagicMock()

        with patch.object(self.sound, 'is_android_runtime', return_value=True):
            streamed = self.controller.play_music('track', fade_in=50)

        self.assertTrue(streamed)
        self.controller.play_streamed_music.assert_called_once_with(
            'track', fade_in=50,
        )
        self.controller.fade_in.assert_not_called()

    def test_android_stream_failure_uses_legacy_fade_once(self):
        self.controller.play_streamed_music = MagicMock(return_value=False)
        self.controller.fade_in = MagicMock(return_value=SimpleNamespace(nid='track'))

        with patch.object(self.sound, 'is_android_runtime', return_value=True):
            streamed = self.controller.play_music('track', fade_in=50)

        self.assertFalse(streamed)
        self.controller.play_streamed_music.assert_called_once_with(
            'track', fade_in=50,
        )
        self.controller.fade_in.assert_called_once_with('track', fade_in=50)

    def test_level_song_preparation_policy_keeps_desktop_flush_synchronous(self):
        self.controller.flush = MagicMock()
        self.controller.load_songs = MagicMock()

        with patch.object(self.sound, 'is_android_runtime', return_value=False):
            worker = self.controller.prepare_level_songs({'track'})

        self.controller.flush.assert_called_once_with()
        self.assertIsNotNone(worker)
        worker.join()
        self.controller.load_songs.assert_called_once_with({'track'})

    def test_android_level_song_preparation_keeps_flush_and_preload_in_worker(self):
        self.controller.flush = MagicMock()
        self.controller.load_songs = MagicMock()
        workers = []

        class FakeThread:
            def __init__(self, target, args=()):
                self.target = target
                self.args = args
                self.started = False
                workers.append(self)

            def start(self):
                self.started = True

        with patch.object(self.sound, 'is_android_runtime', return_value=True), \
                patch.object(self.sound.threading, 'Thread', FakeThread):
            worker = self.controller.prepare_level_songs({'track'})

        self.assertIs(worker, workers[0])
        self.assertTrue(worker.started)
        self.controller.flush.assert_not_called()
        self.controller.load_songs.assert_not_called()
        worker.target(*worker.args)
        self.controller.flush.assert_called_once_with()
        self.controller.load_songs.assert_called_once_with({'track'})

    def test_android_battle_stream_returns_restore_handle_without_legacy_fade(self):
        self.controller.get_current_song = MagicMock(
            return_value=SimpleNamespace(nid='map_track'))
        self.controller.play_streamed_music = MagicMock(return_value=True)
        self.controller.battle_fade_in = MagicMock()

        with patch.object(self.sound, 'is_android_runtime', return_value=True):
            playback = self.controller.start_battle_music('track', from_start=True)

        self.assertIsInstance(playback, self.sound.StreamedBattleMusic)
        self.assertEqual('map_track', playback.return_nid)
        self.assertFalse(playback.return_streamed)
        self.controller.play_streamed_music.assert_called_once_with(
            'track', battle=True, fade_in=50, play_intro=False,
        )
        self.controller.battle_fade_in.assert_not_called()

    def test_streamed_battle_finish_restores_legacy_map_track_once(self):
        self.controller.stop_streamed_music = MagicMock()
        self.controller.fade_in = MagicMock()
        self.controller.battle_fade_back = MagicMock()
        playback = self.sound.StreamedBattleMusic('map_track', False)

        self.controller.finish_battle_music(playback, from_start=True)

        self.controller.stop_streamed_music.assert_called_once_with()
        self.controller.fade_in.assert_called_once_with(
            'map_track', fade_in=50, from_start=True,
        )
        self.controller.battle_fade_back.assert_not_called()

    def test_android_preview_uses_stream_then_existing_legacy_fallback_once(self):
        self.controller.play_streamed_preview = MagicMock(return_value=False)
        self.controller.play_legacy_preview = MagicMock(return_value=True)

        with patch.object(self.sound, 'is_android_runtime', return_value=True):
            started = self.controller.play_preview('track', battle=True)

        self.assertTrue(started)
        self.controller.play_streamed_preview.assert_called_once_with('track', battle=True)
        self.controller.play_legacy_preview.assert_called_once_with('track', battle=True)

    def test_sound_policy_module_has_no_gameplay_critical_imports(self):
        from pathlib import Path

        source = (Path(__file__).parents[1] / 'engine' / 'sound.py').read_text(
            encoding='utf-8')
        for forbidden in (
                'app.engine.game_state', 'app.engine.combat', 'app.events',
                'app.engine.save', 'app.engine.state_machine',
                'runtime_debugger_controller'):
            self.assertNotIn(forbidden, source)

    def test_event_and_tilemap_scheduling_sources_remain_outside_audio_policy(self):
        from pathlib import Path

        root = Path(__file__).parents[1]
        event_source = (root / 'events' / 'event.py').read_text(encoding='utf-8')
        event_functions_source = (root / 'events' / 'event_functions.py').read_text(
            encoding='utf-8')
        job_source = (root / 'engine' / 'jobs' / 'tilemap_change_job.py').read_text(
            encoding='utf-8')

        self.assertIn('android_process_budget_seconds = 0.002', event_source)
        self.assertIn('_android_process_yielded', event_source)
        self.assertIn('_android_tilemap_pending', event_functions_source)
        self.assertIn('FRAME_BUDGET_NS = 4_000_000', job_source)


if __name__ == '__main__':
    unittest.main()
