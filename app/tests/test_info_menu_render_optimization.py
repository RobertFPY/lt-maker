import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine.info_menu.info_menu_state import InfoMenuState
from app.engine.info_menu.info_menu_portrait import InfoMenuPortrait
from app.engine import dialog, help_menu, icons
from app.utilities.enums import HAlignment


class InfoMenuRenderOptimizationTests(unittest.TestCase):
    def _build_stat_dialog(self):
        state = help_menu.StatDialog.__new__(help_menu.StatDialog)
        state.help_surf = object()
        state._cached_help_surf = None
        state.transition_in = False
        state.transition_out = 0
        state.dlg = Mock()
        state.dlg.is_done_or_wait.return_value = True
        state.dlg.y_offset = 0
        state.dlg.draw_cursor_flag = False
        state.dlg.tagged_text.get_cycle_period.return_value = 1
        state.top_left = Mock(return_value=(12, 16))
        state.final_draw = Mock(side_effect=lambda surf, *_args: surf)
        return state

    def test_static_stat_help_panel_is_rendered_once(self):
        state = self._build_stat_dialog()
        target = object()
        rendered = object()

        with patch(
            'app.engine.help_menu.engine.copy_surface', return_value=rendered
        ) as copy_surface, patch(
            'app.engine.help_menu.engine.get_time', return_value=100
        ):
            first = state.draw(target, (20, 24))
            second = state.draw(target, (20, 24))

        self.assertIs(first, target)
        self.assertIs(second, target)
        copy_surface.assert_called_once_with(state.help_surf)
        state.dlg.draw.assert_called_once_with(rendered)
        self.assertIs(state._cached_help_surf, rendered)
        self.assertEqual(state.final_draw.call_count, 2)

    def test_animated_stat_help_panel_is_not_cached(self):
        for case in ('typewriter', 'text_effect', 'wait_cursor', 'transition'):
            with self.subTest(case=case):
                state = self._build_stat_dialog()
                if case == 'typewriter':
                    state.dlg.is_done_or_wait.return_value = False
                elif case == 'text_effect':
                    state.dlg.tagged_text.get_cycle_period.return_value = 2
                elif case == 'wait_cursor':
                    state.dlg.draw_cursor_flag = True
                elif case == 'transition':
                    state.transition_in = True

                with patch(
                    'app.engine.help_menu.engine.copy_surface',
                    side_effect=[object(), object()],
                ) as copy_surface, patch(
                    'app.engine.help_menu.engine.get_time', return_value=100
                ):
                    state.draw(object(), (20, 24))
                    state.draw(object(), (20, 24))

                self.assertEqual(copy_surface.call_count, 2)
                self.assertEqual(state.dlg.draw.call_count, 2)
                self.assertIsNone(state._cached_help_surf)

    def test_static_help_final_composition_is_reused(self):
        state = self._build_stat_dialog()
        del state.final_draw
        state.h_surf = object()
        rendered_help = object()
        state._cached_help_surf = rendered_help
        state._cached_final_surf = None
        state._cached_help_logo = None
        target = SimpleNamespace(blit=Mock())
        composed = SimpleNamespace(blit=Mock())
        help_logo = object()

        with patch(
            'app.engine.help_menu.engine.copy_surface', return_value=composed
        ) as copy_surface, patch.object(
            help_menu.SPRITES, 'get', return_value=help_logo
        ) as get_logo:
            state.final_draw(target, (12, 16), 100, rendered_help)
            state.final_draw(target, (12, 16), 116, rendered_help)

        copy_surface.assert_called_once_with(state.h_surf)
        composed.blit.assert_any_call(rendered_help, (0, 3))
        composed.blit.assert_any_call(help_logo, (9, 0))
        self.assertEqual(target.blit.call_count, 2)
        target.blit.assert_called_with(composed, (12, 16))
        self.assertEqual(get_logo.call_count, 2)
        self.assertIs(state._cached_final_surf, composed)

    def test_backgroundless_dialog_skips_transparent_alpha_pass(self):
        state = dialog.Dialog.__new__(dialog.Dialog)
        state.background = object()
        state._background_is_visible = False
        state.state = dialog.DialogState.DONE
        state.portrait = None
        state.tail = None
        state.speaker = None
        state.draw_cursor_flag = False
        state.draw_text = Mock(return_value=(0, 0))
        target = object()

        with patch(
            'app.engine.dialog.image_mods.make_translucent'
        ) as make_translucent:
            result = state.draw(target)

        self.assertIs(result, target)
        make_translucent.assert_not_called()
        state.draw_text.assert_called_once_with(target)

    def test_glowing_stat_palette_swap_uses_tight_surface(self):
        target = Mock()
        glow_surface = Mock()
        font = Mock()
        font.width.return_value = 12
        font.height = 8
        font._width = 8
        font.default_color = 'green'
        font.font_info.palettes = {
            'green': [(1, 2, 3, 255), (4, 5, 6, 255)],
        }

        with patch(
            'app.engine.icons.engine.create_surface', return_value=glow_surface
        ) as create_surface, patch(
            'app.engine.icons.image_mods.color_convert_alpha'
        ) as color_convert, patch(
            'app.engine.icons.engine.get_time', return_value=0
        ):
            result = icons.draw_glow(
                target, font, '12', (47, 24), HAlignment.RIGHT)

        self.assertIs(result, target)
        create_surface.assert_called_once_with((28, 8), transparent=True)
        font.blit.assert_called_once_with('12', glow_surface, (8, 0))
        color_convert.assert_called_once()
        target.blit.assert_called_once_with(glow_surface, (27, 24))

    def test_steady_slide_draws_directly_without_full_screen_alpha_surfaces(self):
        state = InfoMenuState.__new__(InfoMenuState)
        state.transparency = 0
        state.scroll_offset_x = 0
        state.scroll_offset_y = 0
        state.state = 'personal_data'
        state.growth_flag = False
        state.personal_data_surf = object()
        state.unit = SimpleNamespace(team='player')
        state.draw_stat_surf = Mock()
        state.draw_personal_data_surf = Mock()
        state._draw_slide_header = Mock()
        destination = object()

        with patch(
            'app.engine.info_menu.info_menu_state.engine.create_surface'
        ) as create_surface, patch.object(
            InfoMenuState, 'get_available_states', return_value=['personal_data']
        ), patch.object(
            InfoMenuState, 'draw_top_arrows'
        ), patch.object(
            InfoMenuState, 'draw_fatigue_surf'
        ), patch.object(
            InfoMenuState, 'create_fatigue_surf'
        ), patch.object(
            InfoMenuState, 'create_personal_data_surf'
        ), patch.object(
            InfoMenuState, 'draw_growths_surf'
        ), patch(
            'app.engine.info_menu.info_menu_state.DB.constants.value',
            return_value=False,
        ):
            state.draw_slide(destination)

        create_surface.assert_not_called()
        state.draw_personal_data_surf.assert_called_once_with(destination)
        state._draw_slide_header.assert_called_once_with(destination)

    def test_portrait_composition_is_reused_until_blink_frame_changes(self):
        portrait = InfoMenuPortrait.__new__(InfoMenuPortrait)
        portrait.should_blink = False
        portrait.blink_counter = SimpleNamespace(count=0)
        portrait.main_portrait = Mock()
        composed = Mock()
        portrait.main_portrait.copy.return_value = composed
        portrait.mouth_section = object()
        portrait.portrait = SimpleNamespace(get_mouth_coord=lambda: (0, 0))
        portrait._cached_blink_frame = None
        portrait._cached_image = None

        first = portrait.create_image()
        second = portrait.create_image()

        self.assertIs(first, second)
        portrait.main_portrait.copy.assert_called_once_with()
        composed.blit.assert_called_once_with(portrait.mouth_section, (0, 0))

    def test_android_steady_portrait_cache_is_tight_and_blink_keyed(self):
        source = (Path(__file__).parents[1] / 'engine' / 'info_menu' / 'info_menu_state.py').read_text(
            encoding='utf-8'
        )

        self.assertIn('is_android_render_optimization_enabled()', source)
        self.assertIn('self._android_portrait_cache = self.portrait_surf.copy()', source)
        self.assertIn('cache_key = (id(self.portrait_surf), id(im), portrait_pos)', source)


if __name__ == '__main__':
    unittest.main()
