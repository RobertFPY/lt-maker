"""Regression contracts for the Android performance round-three hot paths."""

from __future__ import annotations

import ast
from collections import OrderedDict
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

# Engine modules create alpha-converted surfaces at import time.  CI and WSL
# runs do not have a window manager, so initialise a tiny dummy display first.
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

if not pygame.display.get_init():
    pygame.display.init()
if pygame.display.get_surface() is None:
    pygame.display.set_mode((1, 1))

from app.engine import battle_animation
from app.engine import general_states
from app.engine import save as save_module
from app.engine.combat import animation_combat
from app.engine import highlight as highlight_module
from app.engine.game_menus.menu_components.unit_menu import unit_menu as unit_menu_module
from app.engine.highlight import HighlightController
from app.engine.state import MapState
from app.events import event as event_module
from app.engine.game_menus.menu_components.unit_menu.unit_menu import (
    SORT_TYPE, UnitMenuUI,
)
from app.engine.game_menus.menu_components.unit_menu.unit_table import UnitTableGeometry
from app.utilities.direction import Direction


ROOT = Path(__file__).parents[1]


def _class_method_source(source: str, class_name: str, method_name: str) -> str:
    tree = ast.parse(source)
    target_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in target_class.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


class AndroidRoundThreePerformanceContracts(unittest.TestCase):
    def test_title_seeds_smoke_directly_only_for_android_render_path(self):
        source = (ROOT / 'engine' / 'title_screen.py').read_text(encoding='utf-8')
        start = _class_method_source(source, 'TitleStartState', 'start')

        self.assertIn('is_android_render_optimization_enabled()', start)
        self.assertIn('particles.seed_title_smoke(', start)
        self.assertIn('self.particles.prefill()', start)

    def test_title_particle_seed_has_a_dedicated_non_prefill_helper(self):
        source = (ROOT / 'engine' / 'particles.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        helper = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == 'seed_title_smoke'
        )
        helper_source = ast.get_source_segment(source, helper)

        self.assertNotIn('.prefill()', helper_source)
        self.assertIn('particle_pool.acquire()', helper_source)
        self.assertIn('system.particles.append(', helper_source)

    def test_event_skips_empty_overlay_trees_but_keeps_populated_ones(self):
        source = (ROOT / 'events' / 'event.py').read_text(encoding='utf-8')
        draw = _class_method_source(source, 'Event', 'draw')

        self.assertIn('_draw_overlay_if_present', draw)
        self.assertIn('event_overlay_ui', source)
        self.assertIn('event_foreground_overlay_ui', source)

    def test_soundroom_uses_cropped_title_and_opt_in_table_static_cache(self):
        base_source = (ROOT / 'engine' / 'base.py').read_text(encoding='utf-8')
        menus_source = (ROOT / 'engine' / 'menus.py').read_text(encoding='utf-8')
        draw_title = _class_method_source(
            base_source, 'BaseSoundRoomState', 'draw_sound_room_title'
        )
        table_draw = _class_method_source(menus_source, 'Table', 'draw')

        self.assertIn('cache_static_options = True', base_source)
        self.assertIn('get_bounding_rect()', draw_title)
        self.assertIn('_draw_android_static_options', table_draw)
        self.assertIn('_draw_android_dynamic_options', table_draw)

    def test_input_profile_breaks_clock_poll_and_processing_apart(self):
        source = (ROOT / 'engine' / 'driver.py').read_text(encoding='utf-8')

        for section in ('time_update', 'input_poll', 'input_process'):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % section, source)

    def test_title_load_uses_android_job_without_changing_desktop_load_api(self):
        title_source = (ROOT / 'engine' / 'title_screen.py').read_text(encoding='utf-8')
        save_source = (ROOT / 'engine' / 'save.py').read_text(encoding='utf-8')
        machine_source = (ROOT / 'engine' / 'state_machine.py').read_text(encoding='utf-8')

        take_input = _class_method_source(title_source, 'TitleLoadState', 'take_input')
        self.assertIn('is_android_runtime()', take_input)
        self.assertIn('_start_android_load(', take_input)
        self.assertIn('class SaveLoadJob', save_source)
        self.assertIn('def load_game(', save_source)
        self.assertIn("'title_load_job': title_screen.TitleLoadJobState", machine_source)

    def test_in_chapter_load_uses_worker_job_only_on_android(self):
        general_source = (ROOT / 'engine' / 'general_states.py').read_text(encoding='utf-8')
        machine_source = (ROOT / 'engine' / 'state_machine.py').read_text(encoding='utf-8')
        take_input = _class_method_source(general_source, 'InChapterLoadState', 'take_input')

        self.assertIn('is_android_runtime()', take_input)
        self.assertIn('_start_android_load(', take_input)
        self.assertIn("'in_chapter_load_job': general_states.InChapterLoadJobState", machine_source)

    def test_in_chapter_job_leaves_authoritative_publication_to_core(self):
        state = general_states.InChapterLoadJobState.__new__(general_states.InChapterLoadJobState)
        state.job = SimpleNamespace(
            completed=True,
            advance=Mock(return_value=True),
            abort=Mock(),
        )
        state.save_slot = SimpleNamespace(kind='battle')
        state.error = None
        state.finished = False
        fake_game = SimpleNamespace(
            memory={}, install_state_machine=Mock(), load_states=Mock())

        with patch.object(general_states, 'game', fake_game), \
             patch.object(general_states.save, 'remove_suspend'):
            self.assertEqual('repeat', state.update())

        state.job.advance.assert_called_once_with(fake_game, budget_ms=8.0)
        fake_game.install_state_machine.assert_not_called()
        fake_game.load_states.assert_not_called()
        self.assertTrue(state.finished)

    def test_title_and_game_over_stream_music_on_android(self):
        title_source = (ROOT / 'engine' / 'title_screen.py').read_text(encoding='utf-8')
        game_over_source = (ROOT / 'engine' / 'game_over.py').read_text(encoding='utf-8')
        title_music = _class_method_source(title_source, 'TitleStartState', '_start_title_music')
        game_over_start = _class_method_source(game_over_source, 'GameOverState', 'start')

        self.assertIn('is_android_runtime()', title_music)
        self.assertIn('play_streamed_music(', title_music)
        self.assertIn('is_android_runtime', game_over_source)
        self.assertIn('play_streamed_music(', game_over_start)


class AndroidHighlightCacheTests(unittest.TestCase):
    @staticmethod
    def _controller():
        controller = HighlightController.__new__(HighlightController)
        controller.images = {'attack': object(), 'aura': object(), 'move': object()}
        controller.highlights = {name: set() for name in controller.images}
        controller.transitions = {name: HighlightController.starting_cutoff for name in controller.images}
        controller.revision = 0
        controller._android_cache_surf = None
        controller._android_cache_key = None
        controller.current_hover = None
        controller.formation_highlights = []
        return controller

    def test_highlight_mutations_invalidate_the_android_cache_revision(self):
        controller = self._controller()
        controller.add_highlight((1, 2), 'attack')
        first_revision = controller.revision
        controller.remove_aura_highlights()
        controller.show_formation([(3, 4)])
        controller.hide_formation()

        self.assertGreater(controller.revision, first_revision)
        self.assertIsNone(controller._android_cache_surf)
        self.assertEqual([], controller.formation_highlights)

    def test_cache_key_changes_when_camera_cull_changes(self):
        controller = self._controller()
        controller._draw_android_static_highlights = Mock()
        target = Mock()
        first_cache, second_cache = Mock(), Mock()
        fake_game = SimpleNamespace(level=SimpleNamespace(regions=[]))

        with patch.object(highlight_module, 'game', fake_game), patch.object(
            highlight_module.engine,
            'create_surface',
            side_effect=[first_cache, second_cache],
        ) as create_surface:
            controller._draw_android_cached(target, (0, 0, 240, 160))
            controller._draw_android_cached(target, (0, 0, 240, 160))
            controller._draw_android_cached(target, (16, 0, 240, 160))

        self.assertEqual(2, create_surface.call_count)
        self.assertEqual(2, controller._draw_android_static_highlights.call_count)


class AndroidUnitMenuLazyTests(unittest.TestCase):
    @staticmethod
    def _menu():
        name_column = SimpleNamespace(stat_name='Name', sort_by=lambda unit: unit.name)
        level_column = SimpleNamespace(stat_name='Lv', sort_by=lambda unit: unit.level)
        menu = UnitMenuUI.__new__(UnitMenuUI)
        menu._android_optimized = True
        menu.sort_by = 'Name'
        menu.sort_direction = SORT_TYPE.DESCENDING
        menu.data = [
            SimpleNamespace(nid=str(idx), name=name, level=idx)
            for idx, name in enumerate(('E', 'D', 'C', 'B', 'A', 'H', 'G', 'F'))
        ]
        menu._android_pages = [('Character', [name_column, level_column])]
        menu._android_page = 0
        menu._android_scroll = 0
        menu._android_cursor_pos = (0, 0)
        menu._android_data_revision = 0
        return menu

    def test_android_unit_menu_scrolls_only_the_visible_window(self):
        menu = self._menu()
        for _ in range(7):
            self.assertTrue(menu.move_cursor(Direction.DOWN))

        self.assertEqual((0, 7), menu._android_cursor_pos)
        self.assertEqual(1, menu._android_scroll)
        self.assertEqual('G', menu.cursor_hover().name)

    def test_android_unit_menu_sorts_only_after_header_selection(self):
        menu = self._menu()
        menu.sort_data(('Name', lambda unit: unit.name))

        self.assertEqual(1, menu._android_data_revision)
        self.assertEqual('H', menu.data[0].name)

    def test_android_page_buttons_change_page_without_losing_selected_row(self):
        menu = self._menu()
        menu._android_pages.append(('Stats', menu._android_pages[0][1]))
        menu._android_cursor_pos = (0, 5)

        self.assertTrue(menu.change_page(Direction.RIGHT))
        self.assertEqual(1, menu._android_page)
        self.assertEqual((0, 5), menu._android_cursor_pos)
        self.assertFalse(menu.change_page(Direction.RIGHT))

        self.assertTrue(menu.change_page(Direction.LEFT))
        self.assertEqual(0, menu._android_page)
        self.assertFalse(menu.change_page(Direction.LEFT))

    def test_android_page_number_is_inside_the_top_bar_left_of_sort_box(self):
        menu = self._menu()
        menu._android_sort_box_pos = (164, 5)

        self.assertEqual((160, 9), menu._android_page_number_position())

    def test_android_title_is_centered_vertically_inside_its_frame(self):
        menu = self._menu()
        menu._android_title_box = SimpleNamespace(get_width=lambda: 103,
                                                  get_height=lambda: 33)
        with patch.dict(unit_menu_module.FONT, {
                'chapter-grey': SimpleNamespace(height=16)}):
            self.assertEqual((51, 8), menu._android_title_position())

    def test_android_l_goes_next_and_r_goes_previous(self):
        from app.engine.game_menus.menu_states.unit_menu_state import UnitMenuState

        with patch(
                'app.engine.game_menus.menu_states.unit_menu_state.is_android_runtime',
                return_value=True):
            self.assertEqual(Direction.RIGHT,
                             UnitMenuState._page_direction_for_event('AUX'))
            self.assertEqual(Direction.LEFT,
                             UnitMenuState._page_direction_for_event('INFO'))
            self.assertEqual(Direction.RIGHT,
                             UnitMenuState._page_direction_for_horizontal(Direction.LEFT))
            self.assertEqual(Direction.LEFT,
                             UnitMenuState._page_direction_for_horizontal(Direction.RIGHT))

    def test_desktop_keeps_existing_l_r_page_order(self):
        from app.engine.game_menus.menu_states.unit_menu_state import UnitMenuState

        with patch(
                'app.engine.game_menus.menu_states.unit_menu_state.is_android_runtime',
                return_value=False):
            self.assertEqual(Direction.LEFT,
                             UnitMenuState._page_direction_for_event('AUX'))
            self.assertEqual(Direction.RIGHT,
                             UnitMenuState._page_direction_for_event('INFO'))
            self.assertIsNone(
                UnitMenuState._page_direction_for_horizontal(Direction.LEFT))

    def test_android_geometry_uses_each_page_declared_column_widths(self):
        geometry = UnitTableGeometry()
        character_page = [
            SimpleNamespace(width=width)
            for width in ('30%', '16%', '16%', '16%', '16%')
        ]
        weapon_page = [SimpleNamespace(width='12%') for _ in range(8)]

        self.assertEqual(
            [45, 24, 24, 24, 24],
            [column.width for column in geometry.columns_for_page(character_page)],
        )
        self.assertEqual(
            [18] * 8,
            [column.width for column in geometry.columns_for_page(weapon_page)],
        )
        self.assertNotEqual(
            geometry.columns_for_page(character_page)[1].left,
            geometry.columns_for_page(weapon_page)[1].left,
        )

    def test_content_cache_reuses_selection_window_and_keeps_four_views(self):
        menu = self._menu()
        menu._android_content_cache = OrderedDict()
        menu._build_android_content = Mock(return_value=(object(), object()))

        menu._android_content_for_current_view()
        menu._android_cursor_pos = (0, 1)
        menu._android_content_for_current_view()
        self.assertEqual(1, menu._build_android_content.call_count)

        menu._android_scroll = 1
        menu._android_content_for_current_view()
        menu._android_content_for_current_view()
        self.assertEqual(2, menu._build_android_content.call_count)

        for sort_by in ('Lv', 'Exp', 'HP'):
            menu.sort_by = sort_by
            menu._android_content_for_current_view()

        self.assertEqual(5, menu._build_android_content.call_count)
        self.assertEqual(4, len(menu._android_content_cache))

    def test_selection_is_behind_content_and_clipped_to_one_row(self):
        geometry = UnitTableGeometry()
        menu = UnitMenuUI.__new__(UnitMenuUI)
        menu._android_optimized = True
        menu._android_geometry = geometry
        menu._android_cursor_pos = (0, 1)
        menu._android_scroll = 0
        menu._draw_android_fixed_layers = lambda surf: surf.fill((20, 20, 20, 255))
        menu._draw_android_sprites = lambda surf: surf.fill(
            (255, 0, 0, 255),
            (
                geometry.table_left + geometry.HIGHLIGHT_LEFT + 2,
                geometry.table_top + geometry.highlight_y(0) + 1,
                1, 1,
            ),
        )
        menu._draw_android_overlays = lambda surf: None

        top_content = pygame.Surface((240, 32), pygame.SRCALPHA)
        table_content = pygame.Surface(geometry.table_size, pygame.SRCALPHA)
        table_content.fill(
            (0, 255, 0, 255),
            (geometry.HIGHLIGHT_LEFT + 1, geometry.highlight_y(0) + 1, 1, 1),
        )
        menu._android_content_for_current_view = lambda: (top_content, table_content)
        selection = pygame.Surface(
            (geometry.highlight_width, geometry.ROW_HEIGHT), pygame.SRCALPHA,
        )
        selection.fill((100, 100, 255, 255))
        menu._android_get_highlight_surf = lambda: selection

        target = pygame.Surface((240, 160), pygame.SRCALPHA)
        menu.draw(target)

        row_y = geometry.table_top + geometry.highlight_y(0) + 1
        text_point = (geometry.table_left + geometry.HIGHLIGHT_LEFT + 1, row_y)
        sprite_point = (geometry.table_left + geometry.HIGHLIGHT_LEFT + 2, row_y)
        background_point = (geometry.table_left + geometry.HIGHLIGHT_LEFT + 3, row_y)
        outside_row = (background_point[0], row_y - 2)
        self.assertEqual((0, 255, 0), target.get_at(text_point)[:3])
        self.assertEqual((255, 0, 0), target.get_at(sprite_point)[:3])
        self.assertEqual((100, 100, 255), target.get_at(background_point)[:3])
        self.assertEqual((20, 20, 20), target.get_at(outside_row)[:3])

    def test_only_visible_sprites_animate_without_rebuilding_content(self):
        class AnimatedSprite:
            def __init__(self, frames):
                self.calls = []
                self.frames = frames
                self.phase = 0

            def create_image(self, state, stationary=False, copy=True):
                self.calls.append((state, stationary, copy))
                return self.frames[self.phase]

        menu = self._menu()
        menu._android_geometry = UnitTableGeometry()
        menu._android_content_cache = OrderedDict()
        menu._build_android_content = Mock(return_value=(object(), object()))
        red = pygame.Surface((64, 48), pygame.SRCALPHA)
        blue = pygame.Surface((64, 48), pygame.SRCALPHA)
        red.fill((255, 0, 0, 255))
        blue.fill((0, 0, 255, 255))
        sprites = []
        for unit in menu.data:
            sprite = AnimatedSprite((red, blue))
            unit.sprite = sprite
            sprites.append(sprite)

        menu._android_content_for_current_view()
        target = pygame.Surface((240, 160), pygame.SRCALPHA)
        menu._draw_android_sprites(target)
        first_pixel = target.get_at((1, 32))[:3]
        for sprite in sprites:
            sprite.phase = 1
        target.fill((0, 0, 0, 0))
        menu._draw_android_sprites(target)
        second_pixel = target.get_at((1, 32))[:3]
        menu._android_content_for_current_view()

        self.assertNotEqual(first_pixel, second_pixel)
        self.assertEqual(1, menu._build_android_content.call_count)
        self.assertEqual([('passive', False, False)] * 2, sprites[0].calls)
        self.assertEqual([], sprites[6].calls)
        self.assertEqual([], sprites[7].calls)

    def test_source_keeps_desktop_path_and_limits_android_rows_to_six(self):
        menu_source = (
            ROOT / 'engine' / 'game_menus' / 'menu_components' / 'unit_menu' / 'unit_menu.py'
        ).read_text(encoding='utf-8')
        table_source = (
            ROOT / 'engine' / 'game_menus' / 'menu_components' / 'unit_menu' / 'unit_table.py'
        ).read_text(encoding='utf-8')

        self.assertIn('ANDROID_VISIBLE_ROWS = 6', menu_source)
        self.assertIn('if self._android_optimized:', menu_source)
        self.assertIn('_build_android_content', menu_source)
        self.assertIn("unit_menu_content_cache_build", menu_source)
        self.assertIn("unit_menu_content_blit", menu_source)
        self.assertIn("unit_menu_sprites", menu_source)
        self.assertNotIn('_android_cached_render', menu_source)
        self.assertNotIn('visible_page_only', table_source)
        self.assertIn('class UnitTableGeometry', table_source)


class SaveLoadJobTests(unittest.TestCase):
    def test_worker_only_reads_and_unpickles_before_main_thread_restore(self):
        slot = SimpleNamespace(save_loc='slot.p', idx=3)
        job = save_module.SaveLoadJob(slot)
        payload = {'state': 'payload'}

        with patch.object(save_module, '_read_save_data', return_value=payload) as read:
            job._read_worker()

        read.assert_called_once_with('slot.p')
        self.assertTrue(job._read_finished.is_set())
        self.assertIs(payload, job._save_data)

    def test_synchronous_load_game_keeps_the_existing_desktop_contract(self):
        slot = SimpleNamespace(save_loc='slot.p', idx=4, kind='battle')
        payload = {'state': (['free'], [])}
        game_state = Mock()

        with patch.object(save_module, '_read_save_data', return_value=payload) as read, \
             patch.object(save_module, 'load_game_data') as transaction:
            save_module.load_game(game_state, slot)

        read.assert_called_once_with('slot.p')
        context = transaction.call_args.kwargs['context']
        self.assertEqual('battle', context.save_kind)
        self.assertEqual(4, context.save_slot)
        self.assertTrue(context.preserve_existing_states)
        transaction.assert_called_once_with(game_state, payload, context=context)

    def test_main_thread_job_installs_restored_save_only_after_iterator_finishes(self):
        slot = SimpleNamespace(save_loc='slot.p', idx=7, kind='battle')
        context = save_module.LoadTransactionContext.for_slot(
            slot, preserve_existing_states=False)
        job = save_module.SaveLoadJob(slot, context=context)
        payload = {'state': (['free'], [])}
        job._thread = Mock()
        job._save_data = payload
        job._read_finished.set()
        game_state = Mock()
        with patch.object(save_module, 'load_game_data') as transaction:
            complete = job.advance(game_state, budget_ms=100.0)

        self.assertTrue(complete)
        transaction.assert_called_once_with(game_state, payload, context=context)
        self.assertIsNone(job._save_data)
        self.assertEqual('complete', job.phase)

    def test_android_job_default_context_replaces_the_loader_stack(self):
        slot = SimpleNamespace(save_loc='slot.p', idx=8, kind='battle')
        job = save_module.SaveLoadJob(slot)

        self.assertFalse(job.context.preserve_existing_states)
        self.assertEqual(8, job.context.save_slot)
        self.assertEqual('battle', job.context.save_kind)

    def test_failed_atomic_load_can_be_aborted_back_to_a_clean_game(self):
        job = save_module.SaveLoadJob(
            SimpleNamespace(save_loc='slot.p', idx=1, kind='battle'))
        game_state = SimpleNamespace(
            clear=Mock(), build_new=Mock(), load_states=Mock())
        job._save_data = {'partially': 'restored'}

        job.abort(game_state)

        self.assertIsNone(job._save_data)
        game_state.clear.assert_called_once_with()
        game_state.build_new.assert_called_once_with()
        game_state.load_states.assert_called_once_with(['title_start'])


class TitleLoadJobStateTests(unittest.TestCase):
    def test_title_input_starts_a_worker_job_and_returns_before_restore(self):
        from app.engine import title_screen

        state = title_screen.TitleLoadState.__new__(title_screen.TitleLoadState)
        state.menu = object()
        slot = SimpleNamespace(save_loc='slot.p', idx=1)
        job = Mock()
        fake_game = SimpleNamespace(memory={}, state=SimpleNamespace(change=Mock()))

        with patch.object(title_screen, 'game', fake_game), \
             patch.object(title_screen.save, 'SaveLoadJob',
                          return_value=job) as job_class:
            result = state._start_android_load(
                slot, transition_from='Load Game', next_action='start_level',
                remove_suspend=True,
            )

        self.assertEqual('repeat', result)
        job.start.assert_called_once_with()
        fake_game.state.change.assert_called_once_with('title_load_job')
        self.assertIs(fake_game.memory['_save_load_job'], job)
        self.assertEqual('start_level', fake_game.memory['_save_load_context']['next_action'])
        load_context = job_class.call_args.kwargs['context']
        self.assertEqual(save_module.LoadDestination.START_LEVEL,
                         load_context.destination)
        self.assertFalse(load_context.preserve_existing_states)

    def test_complete_load_only_commits_title_presentation_handoff(self):
        from app.engine import title_screen

        state = title_screen.TitleLoadJobState.__new__(title_screen.TitleLoadJobState)
        state.context = {
            'next_action': 'start_level', 'transition_from': 'Load Game',
            'title_menu': object(), 'remove_suspend': False,
        }
        fake_game = SimpleNamespace(
            memory={},
            game_vars={'_next_level_nid': 'chapter'},
            install_state_machine=Mock(), load_states=Mock(), start_level=Mock(),
            state=SimpleNamespace(change=Mock(), process_temp_state=Mock()),
        )

        with patch.object(title_screen, 'game', fake_game):
            state._complete_load()

        fake_game.start_level.assert_not_called()
        fake_game.install_state_machine.assert_not_called()
        fake_game.load_states.assert_not_called()
        fake_game.state.change.assert_called_once_with('title_wait')
        fake_game.state.process_temp_state.assert_called_once_with()


class AndroidCombatCompositionTests(unittest.TestCase):
    @staticmethod
    def _surface(size, color=(0, 0, 0, 0), transparent=True):
        surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        surface.fill(color)
        return surface

    @staticmethod
    def _opaque_surface(size, transparent=False):
        if transparent:
            return pygame.Surface(size, pygame.SRCALPHA, 32)
        return pygame.Surface(size)

    @classmethod
    def _combat(cls, darken, pairup):
        class HealthBar:
            def __init__(self, color):
                self.color = color

            def draw(self, surface, x, y):
                surface.fill(self.color, (x, y, 20, 3))

        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        combat.combat_surf = cls._surface((240, 160))
        combat.left_bar = cls._surface((120, 45), (220, 40, 40, 255))
        combat.right_bar = cls._surface((120, 45), (40, 40, 220, 255))
        combat.left_item = None
        combat.right_item = None
        combat.left_stats = None
        combat.right_stats = None
        combat.left_hp_bar = HealthBar((255, 255, 255, 255))
        combat.right_hp_bar = HealthBar((255, 255, 0, 255))
        combat.left_name = cls._surface((32, 10), (0, 220, 0, 255))
        combat.right_name = cls._surface((32, 10), (0, 180, 0, 255))
        combat.lp_name = cls._surface((24, 8), (0, 120, 0, 255))
        combat.rp_name = cls._surface((24, 8), (0, 100, 0, 255))
        combat.lp_battle_anim = object() if pairup else None
        combat.rp_battle_anim = object() if pairup else None
        combat.shake_offset = (0, 0)
        combat.bar_offset = 1
        combat.name_offset = 1
        combat.darken_ui_background = darken
        combat.left = SimpleNamespace(
            team='left', get_guard_gauge=lambda: 1, get_max_guard_gauge=lambda: 3,
        )
        combat.right = SimpleNamespace(
            team='right', get_guard_gauge=lambda: 2, get_max_guard_gauge=lambda: 4,
        )
        combat.get_color = lambda team: team
        combat.draw_stats = Mock()
        combat._android_cached_bars = Mock(
            side_effect=lambda _crit: (combat.left_bar.copy(), combat.right_bar.copy())
        )
        return combat

    def _assert_equivalent_composition(self, *, darken, pairup, crit=0):
        class NumberFont:
            def blit_center(self, _text, surface, _pos):
                surface.fill((255, 255, 255, 255), (17, 0, 1, 1))

        combat = self._combat(darken, pairup)
        legacy = self._surface((240, 160))
        android = self._surface((240, 160))

        def constant(name):
            return {'pairup': pairup, 'attack_stance_only': False}.get(name, False)

        with patch.object(animation_combat.DB.constants, 'value', side_effect=constant), \
             patch.object(animation_combat, 'FONT', {'number_small2': NumberFont()}), \
             patch.object(animation_combat.SPRITES, 'get', side_effect=lambda _name: self._surface((36, 10), (120, 120, 120, 255))), \
             patch.object(animation_combat.engine, 'create_surface', side_effect=self._opaque_surface):
            combat._draw_legacy_final_ui(legacy, crit)
            legacy_darken = combat.darken_ui_background
            combat.darken_ui_background = darken
            combat._draw_android_final_ui(android, crit)

        self.assertEqual(legacy_darken, combat.darken_ui_background)
        self.assertEqual(
            pygame.image.tostring(legacy, 'RGBA'),
            pygame.image.tostring(android, 'RGBA'),
        )

    def test_direct_composition_matches_legacy_for_ordinary_and_tinted_ui(self):
        for darken in (0, 1, -3):
            with self.subTest(darken=darken):
                self._assert_equivalent_composition(darken=darken, pairup=False)

    def test_direct_composition_matches_legacy_for_critical_ui(self):
        self._assert_equivalent_composition(darken=1, pairup=False, crit=7)

    def test_direct_composition_matches_legacy_for_pairup_guard_gauges(self):
        self._assert_equivalent_composition(darken=1, pairup=True)

    def test_cached_health_bars_rebuild_only_the_changed_side_and_stay_bounded(self):
        class HealthBar:
            def __init__(self):
                self.displayed_val = 10
                self.draw_calls = 0

            def get_max_val(self):
                return 20

            def big_number(self):
                return False

            def draw(self, surface, _left, _top):
                self.draw_calls += 1
                surface.fill((255, 255, 255, 255), (0, 0, 1, 1))

        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        combat._android_bar_layers = {'left': OrderedDict(), 'right': OrderedDict()}
        left_base = self._surface((24, 12), (80, 0, 0, 255))
        right_base = self._surface((24, 12), (0, 0, 80, 255))
        left_hp, right_hp = HealthBar(), HealthBar()

        left_first = combat._android_cached_health_bar('left', left_base, left_hp, 0, 0)
        right_first = combat._android_cached_health_bar('right', right_base, right_hp, 0, 0)
        self.assertIs(left_first, combat._android_cached_health_bar('left', left_base, left_hp, 0, 0))
        self.assertIs(right_first, combat._android_cached_health_bar('right', right_base, right_hp, 0, 0))
        self.assertEqual(1, left_hp.draw_calls)
        self.assertEqual(1, right_hp.draw_calls)

        left_hp.displayed_val = 9
        self.assertIsNot(left_first, combat._android_cached_health_bar('left', left_base, left_hp, 0, 0))
        self.assertIs(right_first, combat._android_cached_health_bar('right', right_base, right_hp, 0, 0))
        for value in range(20):
            left_hp.displayed_val = value
            combat._android_cached_health_bar('left', left_base, left_hp, 0, 0)
        self.assertLessEqual(len(combat._android_bar_layers['left']), 8)

    def test_batched_ui_strips_reuse_pixels_when_only_positions_change(self):
        class NumberFont:
            def blit_center(self, _text, surface, _pos):
                surface.fill((255, 255, 255, 255), (17, 0, 1, 1))

        combat = self._combat(darken=0, pairup=True)
        left_base, right_base = combat.left_bar.copy(), combat.right_bar.copy()
        combat._android_cached_bars = Mock(return_value=(left_base, right_base))
        target = self._surface((240, 160))

        def constant(name):
            return {'pairup': True, 'attack_stance_only': False}.get(name, False)

        with patch.object(animation_combat.DB.constants, 'value', side_effect=constant), \
             patch.object(animation_combat, 'FONT', {'number_small2': NumberFont()}), \
             patch.object(animation_combat.SPRITES, 'get', side_effect=lambda _name: self._surface((36, 10), (120, 120, 120, 255))), \
             patch.object(animation_combat.engine, 'create_surface', side_effect=self._opaque_surface) as create_surface:
            combat._draw_android_final_ui(target, crit=0)
            first_bar_strip = next(iter(combat._android_bar_strip_layers.values()))[0]
            first_name_strip = next(iter(combat._android_name_strip_layers.values()))
            first_create_count = create_surface.call_count

            combat.shake_offset = (4, -2)
            combat.bar_offset = 0
            combat.name_offset = 0
            combat._draw_android_final_ui(target, crit=0)

        self.assertIs(first_bar_strip, next(iter(combat._android_bar_strip_layers.values()))[0])
        self.assertIs(first_name_strip, next(iter(combat._android_name_strip_layers.values())))
        self.assertEqual(1, len(combat._android_bar_strip_layers))
        self.assertEqual(1, len(combat._android_name_strip_layers))
        self.assertEqual(first_create_count, create_surface.call_count)

    def test_cached_layer_uses_colorkey_rle_only_for_binary_alpha_and_no_rebuild_on_hit(self):
        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        source = self._surface((8, 8))
        source.fill((11, 22, 33, 255), (2, 2, 3, 3))
        layer = animation_combat._AndroidCombatUILayer(source)
        with patch.object(animation_combat.engine, 'create_surface', side_effect=self._surface) as create_surface:
            first = combat._android_layer_variant(layer, 0)
            second = combat._android_layer_variant(layer, 0)
        self.assertIs(first, second)
        self.assertEqual(1, create_surface.call_count)
        self.assertIsNotNone(first.get_colorkey())

        alpha_source = self._surface((2, 2))
        alpha_source.set_at((0, 0), (12, 34, 56, 128))
        self.assertIs(alpha_source, combat._android_prepare_cached_surface(alpha_source))

        global_alpha_source = self._surface((2, 2), (12, 34, 56, 255))
        global_alpha_source.set_alpha(128)
        self.assertIs(global_alpha_source, combat._android_prepare_cached_surface(global_alpha_source))

    def test_opaque_cached_layer_is_converted_to_an_opaque_display_surface(self):
        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        source = self._surface((3, 2), (11, 22, 33, 255))

        def opaque_surface(size):
            return pygame.Surface(size)

        with patch.object(animation_combat.engine, 'create_surface', side_effect=opaque_surface) as create_surface:
            prepared = combat._android_prepare_cached_surface(source)

        self.assertIsNot(source, prepared)
        self.assertEqual(1, create_surface.call_count)
        self.assertFalse(prepared.get_flags() & pygame.SRCALPHA)
        self.assertEqual((11, 22, 33, 255), prepared.get_at((0, 0)))

    def test_advantage_arrow_cache_tracks_animation_frame_without_touching_bar_cache(self):
        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        combat._android_arrow_layers = OrderedDict()
        combat._android_bar_layers = {'left': OrderedDict(), 'right': OrderedDict()}
        arrow_sheet = self._surface((21, 20))
        arrow_sheet.fill((255, 0, 0, 255), (0, 0, 7, 10))
        arrow_sheet.fill((0, 0, 255, 255), (7, 0, 7, 10))
        attacker = defender = object()
        counters = SimpleNamespace(arrow_counter=SimpleNamespace(count=0))

        with patch.object(animation_combat, 'ANIMATION_COUNTERS', counters), \
             patch.object(animation_combat.SPRITES, 'get', return_value=arrow_sheet), \
             patch.object(animation_combat.AnimationCombat, '_android_advantage_direction', return_value='up'):
            first = combat._android_advantage_arrow_layer(attacker, defender, object(), object())
            counters.arrow_counter.count = 1
            second = combat._android_advantage_arrow_layer(attacker, defender, object(), object())

        self.assertNotEqual(pygame.image.tostring(first.raw, 'RGBA'), pygame.image.tostring(second.raw, 'RGBA'))
        self.assertFalse(combat._android_bar_layers['left'])
        self.assertFalse(combat._android_bar_layers['right'])


class AndroidBattleAnimationRenderTests(unittest.TestCase):
    def test_android_frame_lookup_keeps_legacy_copy_semantics(self):
        source = pygame.Surface((3, 2), pygame.SRCALPHA, 32)
        source.fill((10, 20, 30, 255))
        animation = battle_animation.BattleAnimation.__new__(battle_animation.BattleAnimation)
        animation.image_directory = {'frame': source}
        animation.right = True
        animation._android_lr_offset = 0
        animation._android_frame_cache = {}
        animation.lr_offset = []
        animation.effect_offset = (0, 0)
        animation.personal_offset = (0, 0)
        animation.at_range = False
        animation.ignore_pan = False
        frame = SimpleNamespace(nid='frame', offset=(0, 0))

        with patch.object(battle_animation, 'is_android_render_optimization_enabled', return_value=True):
            image, _offset = animation.get_image(frame, (0, 0), 0, 0, False)

        self.assertIsNot(source, image)
        image.fill((200, 100, 50, 255))
        self.assertEqual((10, 20, 30, 255), source.get_at((0, 0)))

    def test_android_frame_metadata_is_aggregated_without_hot_path_logging(self):
        animation = battle_animation.BattleAnimation.__new__(battle_animation.BattleAnimation)
        animation.right = True
        animation.combat_anim_nid = 'MercenaryIke'
        animation.anim_prefab = SimpleNamespace(nid='Sword')
        animation._android_logged_frame_keys = set()
        image = SimpleNamespace(
            get_colorkey=lambda: pygame.Color(1, 2, 3, 255),
            get_size=lambda: (2, 2),
            get_flags=lambda: 0,
            get_width=lambda: 2,
            get_height=lambda: 2,
        )
        frame = SimpleNamespace(nid='frame')

        with patch.object(battle_animation, 'is_android_render_optimization_enabled', return_value=True), \
             patch.object(battle_animation.RUNTIME_PROFILER, 'enabled', True), \
             patch.object(battle_animation.RUNTIME_PROFILER, 'count') as count, \
             patch.object(battle_animation.logging, 'warning') as warning:
            animation._log_android_frame_surface(frame, image)
            animation._log_android_frame_surface(frame, image)

        count.assert_called_once_with('combat_frame_surface')
        warning.assert_not_called()


class AndroidCombatUnderlayTests(unittest.TestCase):
    def test_map_underlay_stays_enabled_for_a_noncovering_panorama_frame(self):
        combat = animation_combat.AnimationCombat.__new__(animation_combat.AnimationCombat)
        combat.battle_background = SimpleNamespace(
            fade_state='normal',
            counter=0,
            panorama=SimpleNamespace(images=[pygame.Surface((120, 80))]),
        )

        self.assertTrue(combat.map_underlay_visible())

    def test_normal_combat_panorama_skips_the_hidden_map_underlay(self):
        state = general_states.CombatState.__new__(general_states.CombatState)
        combat = SimpleNamespace(
            viewbox=None,
            draw=Mock(),
            map_underlay_visible=Mock(return_value=False),
        )
        state.is_animation_combat = True
        state.combat = combat
        target = pygame.Surface((240, 160), pygame.SRCALPHA, 32)

        with patch.object(MapState, 'draw', side_effect=lambda surf, culled_rect=None: surf) as map_draw:
            state.draw(target)

        combat.map_underlay_visible.assert_called_once_with()
        map_draw.assert_not_called()
        combat.draw.assert_called_once_with(target)

    def test_combat_transition_keeps_drawing_the_visible_map_underlay(self):
        state = general_states.CombatState.__new__(general_states.CombatState)
        combat = SimpleNamespace(
            viewbox=(4, 8, 24, 32),
            draw=Mock(),
            map_underlay_visible=Mock(return_value=True),
        )
        state.is_animation_combat = True
        state.combat = combat
        state.fuzz_background = pygame.Surface((240, 160), pygame.SRCALPHA, 32)
        target = pygame.Surface((240, 160), pygame.SRCALPHA, 32)

        with patch.object(MapState, 'draw', side_effect=lambda surf, culled_rect=None: surf) as map_draw:
            state.draw(target)

        map_draw.assert_called_once_with(target, culled_rect=combat.viewbox)
        combat.draw.assert_called_once_with(target)


class AndroidEventBudgetTests(unittest.TestCase):
    @staticmethod
    def _make_budgeted_event():
        event = event_module.Event.__new__(event_module.Event)
        first = SimpleNamespace(nid='give_item')
        second = SimpleNamespace(nid='give_skill')
        event.state = 'processing'
        event.command_queue = [first, second]
        event.processor = SimpleNamespace(fetch_next_command=Mock())
        event.logger = SimpleNamespace(debug=Mock())
        event.do_skip = False
        event.skippable = set()
        event.run_command = Mock()
        return event, first, second

    def test_android_event_processor_yields_between_commands_at_the_frame_budget(self):
        event, first, second = self._make_budgeted_event()

        with patch.object(event_module, 'is_android_render_optimization_enabled', return_value=True), \
             patch.object(event_module.time, 'perf_counter', side_effect=(0.0, 0.003)), \
             patch.object(event_module.RUNTIME_PROFILER, 'count') as count:
            event.process()

        event.run_command.assert_called_once_with(first)
        self.assertEqual([second], event.command_queue)
        count.assert_called_once_with('event_budget_yield')

    def test_event_state_machine_does_not_reenter_a_budgeted_processor(self):
        event, first, second = self._make_budgeted_event()
        event.prev_state = None
        event.finished = Mock(return_value=False)

        with patch.object(event_module, 'is_android_render_optimization_enabled', return_value=True), \
             patch.object(event_module.time, 'perf_counter', side_effect=(0.0, 0.003)), \
             patch.object(event_module.RUNTIME_PROFILER, 'count'):
            event._update_state()

        event.run_command.assert_called_once_with(first)
        self.assertEqual([second], event.command_queue)


if __name__ == '__main__':
    unittest.main()
