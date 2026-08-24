import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import pygame


class AndroidStreamingControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.engine import sound
        cls.sound = sound

    def setUp(self):
        self.controller = object.__new__(self.sound.DefaultSoundController)
        self.controller.global_music_volume = 0.35
        self.controller._stream_preview_active = False
        self.controller._stream_preview_nid = None
        self.prefab = SimpleNamespace(
            nid='track',
            full_path='track.ogg',
            battle_full_path='track_battle.ogg',
            intro_full_path='track_intro.ogg',
        )
        self.music = MagicMock()
        self.resources_music = {'track': self.prefab}
        self.resource_patch = patch.object(
            self.sound.RESOURCES, 'music', self.resources_music
        )
        self.resource_patch.start()
        self.android_patch = patch.object(
            self.sound, 'is_android_render_optimization_enabled', return_value=True,
            create=True,
        )
        self.android_patch.start()
        self.android_runtime_patch = patch.object(
            self.sound, 'is_android_runtime', return_value=True,
            create=True,
        )
        self.android_runtime_patch.start()
        self.music_patch = patch.object(self.sound.pygame.mixer, 'music', self.music)
        self.music_patch.start()

    def tearDown(self):
        self.music_patch.stop()
        self.android_runtime_patch.stop()
        self.android_patch.stop()
        self.resource_patch.stop()

    def test_main_track_streams_without_intro(self):
        self.assertTrue(self.controller.play_streamed_preview('track'))
        self.music.stop.assert_called_once_with()
        self.music.unload.assert_called_once_with()
        self.music.load.assert_called_once_with('track.ogg')
        self.music.set_volume.assert_called_once_with(0.35)
        self.music.play.assert_called_once_with(loops=-1, fade_ms=100)
        self.assertTrue(self.controller._stream_preview_active)
        self.assertEqual('track', self.controller._stream_preview_nid)

    def test_android_preview_streams_when_render_caches_are_disabled(self):
        with patch.object(self.sound, 'is_android_runtime', return_value=True), \
                patch.object(
                    self.sound, 'is_android_render_optimization_enabled',
                    return_value=False,
                ):
            self.assertTrue(self.controller.play_streamed_preview('track'))

        self.music.load.assert_called_once_with('track.ogg')

    def test_gameplay_stream_plays_intro_once_then_loops_main_track(self):
        self.assertTrue(self.controller.play_streamed_music('track', fade_in=50))

        self.music.load.assert_called_once_with('track_intro.ogg')
        self.music.queue.assert_called_once_with('track.ogg', loops=-1)
        self.music.play.assert_called_once_with(loops=0, fade_ms=50)
        self.assertTrue(self.controller._stream_preview_active)
        self.assertEqual('track', self.controller._stream_preview_nid)

    def test_battle_track_starts_from_beginning(self):
        self.assertTrue(self.controller.play_streamed_preview('track', battle=True))
        self.music.load.assert_called_once_with('track_battle.ogg')
        self.music.play.assert_called_once_with(loops=-1, fade_ms=100)

    def test_stream_load_error_returns_false_for_legacy_fallback(self):
        self.music.load.side_effect = pygame.error('unsupported')
        self.assertFalse(self.controller.play_streamed_preview('track'))
        self.assertFalse(self.controller._stream_preview_active)

    def test_stream_load_error_keeps_legacy_channels_for_fallback(self):
        legacy_channel = MagicMock()
        self.controller.channel_stack = [legacy_channel]
        self.controller.song_stack = [object()]
        self.music.load.side_effect = pygame.error('unsupported')

        self.assertFalse(self.controller.play_streamed_preview('track'))

        legacy_channel.clear.assert_not_called()
        self.assertEqual(1, len(self.controller.song_stack))

    def test_stop_stream_unloads_and_clears_state(self):
        self.controller._stream_preview_active = True
        self.controller._stream_preview_nid = 'track'
        self.controller.stop_streamed_preview()
        self.music.stop.assert_called_once_with()
        self.music.unload.assert_called_once_with()
        self.assertFalse(self.controller._stream_preview_active)
        self.assertIsNone(self.controller._stream_preview_nid)

    def test_music_volume_update_reaches_active_stream(self):
        self.controller._stream_preview_active = True
        self.controller.channel_stack = []
        self.controller.set_music_volume(0.6)
        self.music.set_volume.assert_called_once_with(0.6)

    def test_battle_fallback_installs_legacy_song_before_crossfade(self):
        legacy_song = SimpleNamespace(nid='track')
        self.controller.fade_in = MagicMock(return_value=legacy_song)
        self.controller.battle_fade_in = MagicMock(return_value=legacy_song)

        self.assertTrue(self.controller.play_legacy_preview('track', battle=True))

        self.controller.fade_in.assert_called_once_with(
            'track', fade_in=100, from_start=True,
        )
        self.controller.battle_fade_in.assert_called_once_with(
            'track', fade=100, from_start=True,
        )


class AndroidSoundRoomRound2SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1]
        cls.base_source = (root / 'engine' / 'base.py').read_text(encoding='utf-8')
        cls.settings_source = (root / 'engine' / 'settings.py').read_text(encoding='utf-8')
        cls.settings_menu_source = (
            root / 'engine' / 'settings_menu.py'
        ).read_text(encoding='utf-8')
        cls.menus_source = (root / 'engine' / 'menus.py').read_text(encoding='utf-8')
        cls.sound_source = (root / 'engine' / 'sound.py').read_text(encoding='utf-8')
        cls.state_machine_source = (
            root / 'engine' / 'state_machine.py'
        ).read_text(encoding='utf-8')

    def test_soundroom_routes_stream_and_has_cleanup_paths(self):
        for token in (
            'play_preview', 'should_defer_preview', 'stop_streamed_preview',
            'is_android_render_optimization_enabled',
        ):
            self.assertIn(token, self.base_source)
        tree = ast.parse(self.base_source)
        soundroom = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'BaseSoundRoomState'
        )
        take_input = next(
            node for node in soundroom.body
            if isinstance(node, ast.FunctionDef) and node.name == 'take_input'
        )
        take_input_source = ast.get_source_segment(self.base_source, take_input)
        for token in (
            "event == 'SELECT'", "event == 'INFO'", "event == 'AUX'",
            "event == 'START'", "event == 'BACK'", 'battle=True',
            'play_music(music)', '_queue_stream_preview(music)',
            '_queue_stream_preview(music, battle=True)',
            'play_music(music, fade_in=50)',
        ):
            self.assertIn(token, take_input_source)
        self.assertNotIn('is_android_runtime()', take_input_source)
        pending_preview = next(
            node for node in soundroom.body
            if isinstance(node, ast.FunctionDef) and node.name == '_play_pending_stream_preview'
        )
        pending_preview_source = ast.get_source_segment(self.base_source, pending_preview)
        self.assertIn('play_preview(music, battle=battle)', pending_preview_source)
        self.assertNotIn('play_streamed_preview(', pending_preview_source)
        self.assertNotIn('play_legacy_preview(', pending_preview_source)
        self.assertIn("sound_thread.play_sfx('Error')", pending_preview_source)
        self.assertIn('self.playing = False', pending_preview_source)

    def test_soundroom_type_annotation_imports_nid_at_runtime(self):
        """Android evaluates BaseSoundRoomState annotations during import."""
        self.assertIn('from app.utilities.typing import NID', self.base_source)

    def test_android_stream_preview_is_deferred_until_after_a_present(self):
        for token in (
            '_pending_stream_preview', '_queue_stream_preview',
            '_play_pending_stream_preview', 'request_present',
        ):
            self.assertIn(token, self.base_source)

    def test_settings_and_soundroom_profile_stages_exist(self):
        for token in (
            'settings_background', 'settings_header', 'settings_body', 'settings_info',
        ):
            self.assertIn(token, self.settings_source)
        for token in (
            'soundroom_background', 'soundroom_menu', 'soundroom_title', 'soundroom_volume',
        ):
            self.assertIn(token, self.base_source)

    def test_android_panel_and_table_caches_are_guarded(self):
        for source in (self.settings_source, self.settings_menu_source, self.menus_source):
            self.assertIn('is_android_render_optimization_enabled()', source)
        self.assertIn('_android_bg_surf', self.settings_menu_source)
        self.assertIn('_android_bg_surf', self.menus_source)
        self.assertIn('_android_title_cache', self.base_source)
        self.assertIn('_android_static_surf', self.settings_menu_source)
        self.assertIn('draw_static', self.settings_menu_source)
        self.assertIn('draw_dynamic', self.settings_menu_source)

        menus_tree = ast.parse(self.menus_source)
        table = next(
            node for node in menus_tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'Table'
        )
        update_bg = next(
            node for node in table.body
            if isinstance(node, ast.FunctionDef) and node.name == 'update_bg'
        )
        self.assertIn('_invalidate_android_bg_cache', ast.get_source_segment(self.menus_source, update_bg))

    def test_sound_stream_profile_stage_and_lifecycle_stages_exist(self):
        self.assertIn('music_stream_load', self.sound_source)
        for token in (
            'state_start:', 'state_begin:', 'state_input:', 'state_end:',
            'state_finish:', 'state_transition_commit',
        ):
            self.assertIn(token, self.state_machine_source)


if __name__ == '__main__':
    unittest.main()
