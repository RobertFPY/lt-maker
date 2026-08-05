import logging
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine import driver
from app.engine.performance import RuntimeProfiler


class RuntimeProfilerTests(unittest.TestCase):
    def test_disabled_profiler_does_not_emit_records(self):
        profiler = RuntimeProfiler()
        profiler.enabled = False
        with patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            with profiler.section('map_compose'):
                pass
            profiler.finish_frame({'units': 1})
        warning.assert_not_called()

    def test_enabled_profiler_reports_aggregate_without_per_frame_output(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.interval_seconds = 0
        profiler.slow_frame_ms = 100000
        with patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            profiler.count('combat_frame_surface')
            with profiler.section('map_compose'):
                pass
            profiler.finish_frame({'units': 3, 'on_map': 2})
        self.assertEqual(1, warning.call_count)
        self.assertIn('PERF', warning.call_args.args[0])
        self.assertIn('p95', warning.call_args.args[0])
        self.assertIn('combat_frame_surface=1', warning.call_args.args[-2])

    def test_enabled_profiler_keeps_hierarchical_inclusive_and_exclusive_timings(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 1
        with patch('app.engine.performance.time.perf_counter_ns',
                   side_effect=(0, 10_000_000, 20_000_000, 40_000_000,
                                50_000_000, 100_000_000)), \
                patch.object(logging, 'warning'):
            profiler.begin_frame()
            with profiler.section('outer'):
                with profiler.section('inner'):
                    pass
            profiler.finish_frame({'state': 'combat'})

        scopes = profiler.latest_frame_scopes()
        self.assertEqual(('outer', 'inner'), tuple(scope['name'] for scope in scopes))
        self.assertEqual((None, 0), tuple(scope['parent_scope_id'] for scope in scopes))
        self.assertEqual((40.0, 20.0), tuple(scope['inclusive_ms'] for scope in scopes))
        self.assertEqual((20.0, 20.0), tuple(scope['exclusive_ms'] for scope in scopes))

    def test_enabled_profiler_ignores_worker_scopes_during_a_main_thread_frame(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 100000
        profiler.begin_frame()

        with profiler.section('main'):
            with patch('app.engine.performance.threading.get_ident', return_value=-1):
                with profiler.section('worker'):
                    pass

        profiler.finish_frame()
        self.assertEqual(('main',), tuple(
            scope['name'] for scope in profiler.latest_frame_scopes()))

    def test_slow_frame_output_includes_scope_path_and_metadata(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 1
        with patch('app.engine.performance.time.perf_counter_ns',
                   side_effect=(0, 10_000_000, 30_000_000, 50_000_000)), \
                patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            with profiler.section('combat.update'):
                pass
            profiler.finish_frame({'state': 'combat', 'level': 'Chapter1'})

        message = warning.call_args.args[0]
        details = warning.call_args.args[1:]
        self.assertIn('PERF slow-frame', message)
        self.assertIn('combat.update', details[-2])
        self.assertIn('state=combat', details[-1])
        self.assertIn('level=Chapter1', details[-1])

    def test_driver_supplies_slow_frame_context_without_reading_game_state(self):
        command = SimpleNamespace(nid='change_tilemap')
        processor = SimpleNamespace(command_pointer=2, commands=[command, command])
        event = SimpleNamespace(
            nid='intro', processor=processor,
            _profile_command_nid='change_tilemap', _profile_command_index=2,
        )
        combat = SimpleNamespace(state='begin_phase')
        state = SimpleNamespace(combat=combat, event=event)
        game = SimpleNamespace(
            units=[SimpleNamespace(position=(1, 2)), SimpleNamespace(position=None)],
            state=SimpleNamespace(
                current=lambda: 'event',
                current_state=lambda: state,
                state_names=lambda: ['free', 'event'],
            ),
            tilemap=SimpleNamespace(nid='castle', animations=[], weather=[]),
            level=SimpleNamespace(nid='Chapter1', regions={'gate': object()}),
        )

        counters = driver._performance_counters(game)

        self.assertEqual(['free', 'event'], counters['state_stack'])
        self.assertEqual('intro', counters['event_nid'])
        self.assertEqual('change_tilemap', counters['event_command'])
        self.assertEqual(2, counters['event_command_index'])
        self.assertEqual('Chapter1', counters['level'])
        self.assertEqual('castle', counters['tilemap'])
        self.assertEqual(1, counters['regions'])

    def test_phase_change_and_music_have_actionable_child_scopes(self):
        root = Path(__file__).parents[1]
        phase_state = (root / 'engine' / 'general_states.py').read_text(
            encoding='utf-8')
        phase_music = (root / 'engine' / 'phase.py').read_text(encoding='utf-8')

        for scope in (
            'phase_change.save_snapshot', 'phase_change.fade_out_music',
            'phase_change.transition_setup', 'phase_change.reset_units',
            'phase_change.resolve_next_music', 'phase_change.music_fade_in',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % scope, phase_state)
        self.assertIn("RUNTIME_PROFILER.section('phase.music_fade_in')", phase_music)

    def test_music_cache_load_has_actionable_child_scopes(self):
        source = (Path(__file__).parents[1] / 'engine' / 'sound.py').read_text(
            encoding='utf-8')

        for scope in ('sound.song_object_create', 'sound.cache_insert'):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % scope, source)

    def test_title_save_menu_has_actionable_child_scopes(self):
        source = (Path(__file__).parents[1] / 'engine' / 'title_screen.py').read_text(
            encoding='utf-8')

        for scope in (
            'title_save_background', 'title_save_particles', 'title_save_menu',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % scope, source)

    def test_map_combat_breaks_solver_and_visual_setup_into_child_scopes(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        for scope in (
            'combat.start_hooks', 'combat.start_event', 'combat.solver_do',
            'combat.health_bar_build', 'combat.proc_animation_build',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % scope, source)

    def test_map_combat_defers_solver_to_its_own_update_state(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        self.assertIn("self.set_state('solve_phase')", source)
        solve_state = source.index("elif self.state == 'solve_phase':")
        solver = source.index("RUNTIME_PROFILER.section('combat.solver_do')")
        self.assertLess(solve_state, solver)

    def test_map_combat_defers_visual_setup_until_after_solver(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        solver = source.index("RUNTIME_PROFILER.section('combat.solver_do')")
        visual_setup = source.index("elif self.state == 'setup_phase_visuals':")
        health_bars = source.index("RUNTIME_PROFILER.section('combat.health_bar_build')")
        self.assertLess(solver, visual_setup)
        self.assertLess(visual_setup, health_bars)

    def test_animation_combat_defers_visual_setup_until_after_solver(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')

        begin_phase = source.index("elif self.state == 'begin_phase':")
        visual_setup = source.index("elif self.state == 'setup_phase_visuals':")
        solver = source.index('self.state_machine.do()', begin_phase)
        self.assertLess(begin_phase, solver)
        self.assertLess(solver, visual_setup)

    def test_animation_combat_stages_initial_paint_setup_before_combat_init(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_body = source[constructor:update]
        self.assertNotIn('self.initial_paint_setup()', constructor_body)
        self.assertIn("if self.state in ('paint_setup', 'arena_paint_setup'):",
                      source[update:])

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'paint_setup'
        combat.arena_combat = False
        combat.initial_paint_setup = Mock()
        combat._set_stats = Mock()
        combat.playback = []
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat.initial_paint_setup.assert_called_once_with()
        combat._set_stats.assert_called_once_with([])
        self.assertEqual('init', combat.state)

    def test_animation_combat_stages_battle_animation_loading_before_paint_setup(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_body = source[constructor:update]
        self.assertNotIn('self.setup_battle_animations()', constructor_body)
        self.assertIn("if self.state in ('animation_setup', 'arena_animation_setup'):",
                      source[update:])

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'animation_setup'
        combat.arena_combat = False
        combat.setup_battle_animations = Mock()
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat.setup_battle_animations.assert_called_once_with()
        self.assertEqual('paint_setup', combat.state)

    def test_animation_combat_stages_start_hooks_before_visual_init(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        init_state = source.index("if self.state == 'init':", update)
        visual_state = source.index("elif self.state == 'init_visuals':", init_state)
        start_hook = source.index('self.start_combat()', init_state)
        self.assertLess(init_state, start_hook)
        self.assertLess(start_hook, visual_state)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'init'
        combat.start_combat = Mock()
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat.start_combat.assert_called_once_with()
        self.assertEqual('init_visuals', combat.state)

    def test_animation_combat_stages_initial_stats_after_cursor_setup(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        visuals = source.index("elif self.state == 'init_visuals':", update)
        stats = source.index("elif self.state == 'init_stats':", visuals)
        refresh = source.index('self._set_stats(self.playback)', stats)
        self.assertLess(visuals, stats)
        self.assertLess(stats, refresh)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'init_stats'
        combat._set_stats = Mock()
        combat.playback = []
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat._set_stats.assert_called_once_with([])
        self.assertEqual('red_cursor', combat.state)

    def test_animation_combat_stages_arena_pairing_after_stats(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        stats = source.index("elif self.state == 'arena_visuals':", update)
        pairing = source.index("elif self.state == 'arena_pair_animations':", stats)
        refresh = source.index('self._set_stats(self.playback)', stats)
        self.assertLess(stats, refresh)
        self.assertLess(refresh, pairing)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'arena_visuals'
        combat._set_stats = Mock()
        combat.playback = []
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat._set_stats.assert_called_once_with([])
        self.assertEqual('arena_pair_animations', combat.state)

    def test_animation_combat_stages_transform_check_after_battle_music(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        music = source.index("elif self.state == 'battle_music':", update)
        transform_check = source.index("elif self.state == 'check_transform':", music)
        load_music = source.index('self.start_battle_music()', music)
        self.assertLess(music, load_music)
        self.assertLess(load_music, transform_check)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'battle_music'
        combat.start_battle_music = Mock()
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat.start_battle_music.assert_called_once_with()
        self.assertEqual('check_transform', combat.state)

    def test_android_streamed_battle_music_restores_cached_map_track(self):
        from app.engine.combat import animation_combat as animation_combat_module
        from app.engine.combat.animation_combat import (
            AnimationCombat, _AndroidStreamedBattleMusic,
        )

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.battle_music = _AndroidStreamedBattleMusic('map_track', False)
        sound_thread = Mock()

        with patch.object(animation_combat_module.DB.constants, 'value', return_value=True), \
                patch.object(
                    animation_combat_module, 'get_sound_thread',
                    return_value=sound_thread,
                ):
            combat.finish()

        sound_thread.stop_streamed_music.assert_called_once_with()
        sound_thread.fade_in.assert_called_once_with(
            'map_track', fade_in=50, from_start=True,
        )

    def test_animation_combat_uses_android_stream_for_battle_track(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        start = source.index('def start_battle_music')
        finish = source.index('def left_team', start)
        battle_music = source[start:finish]

        self.assertIn('is_android_runtime()', battle_music)
        self.assertIn('play_streamed_music(', battle_music)
        self.assertIn('battle=True', battle_music)

    def test_animation_combat_stages_transform_rebuild_before_repairing(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        transform = source.index("elif self.state == 'transform':", update)
        rebuild = source.index("elif self.state == 'rebuild_transform_animations':", transform)
        repair = source.index("elif self.state == 'repair_transform_animations':", rebuild)
        self.assertLess(transform, rebuild)
        self.assertLess(rebuild, repair)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'transform'
        combat.left_battle_anim = Mock()
        combat.left_battle_anim.done.return_value = True
        combat.right_battle_anim = Mock()
        combat.right_battle_anim.done.return_value = True
        combat.lp_battle_anim = None
        combat.rp_battle_anim = None
        combat.last_update = 0

        self.assertFalse(combat.update())
        self.assertEqual('rebuild_transform_animations', combat.state)

    def test_animation_combat_stages_pre_proc_setup_after_readiness_check(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        pre_proc = source.index("elif self.state == 'pre_proc':", update)
        setup = source.index("elif self.state == 'setup_pre_proc':", pre_proc)
        self.assertLess(pre_proc, setup)

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'pre_proc'
        combat.left_battle_anim = Mock()
        combat.left_battle_anim.done.return_value = True
        combat.right_battle_anim = Mock()
        combat.right_battle_anim.done.return_value = True
        combat.proc_icons = []
        combat.last_update = 0

        self.assertFalse(combat.update())
        self.assertEqual('setup_pre_proc', combat.state)

    def test_animation_combat_stages_solver_after_begin_phase_end_check(self):
        from app.engine.combat.animation_combat import AnimationCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        begin_phase = source.index("elif self.state == 'begin_phase':", update)
        solve_phase = source.index("elif self.state == 'solve_phase':", begin_phase)
        solver = source.index('self.state_machine.do()', solve_phase)
        self.assertLess(begin_phase, solve_phase)
        self.assertLess(solve_phase, solver)

        state_machine = Mock()
        state_machine.get_state.return_value = True
        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'begin_phase'
        combat.state_machine = state_machine
        combat.last_update = 0

        self.assertFalse(combat.update())
        state_machine.do.assert_not_called()
        self.assertEqual('solve_phase', combat.state)

    def test_animation_combat_stages_remaining_heavy_operations(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')

        for state in (
            'pair_entrance_animations', 'start_event', 'initiate_transform',
            'setup_phase_followup', 'setup_hit_effect',
            'resume_hit_animation', 'setup_delayed_death',
            'end_combat_focus', 'end_combat_camera', 'cleanup1',
            'rebuild_revert_animations', 'repair_revert_animations',
            'initiate_revert_transforms', 'finish_combat', 'cleanup2',
        ):
            self.assertIn("self.state == '%s'" % state, source)

    def test_animation_combat_stages_final_cleanup_after_finish(self):
        from app.engine.combat.animation_combat import AnimationCombat

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.state = 'finish_combat'
        combat.finish = Mock()
        combat.last_update = 0

        self.assertFalse(combat.update())
        combat.finish.assert_called_once_with()
        self.assertEqual('cleanup2', combat.state)

        combat.clean_up2 = Mock()
        combat.end_skip = Mock()
        self.assertTrue(combat.update())
        combat.clean_up2.assert_called_once_with()
        combat.end_skip.assert_called_once_with()

    def test_map_combat_defers_actions_until_after_playback_effects(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        anim_state = source.index("elif self.state == 'anim':")
        action_state = source.index("elif self.state == 'apply_actions':")
        playback = source.index('self._handle_playback()', anim_state)
        apply_actions = source.index('self._apply_actions()', action_state)
        self.assertLess(anim_state, action_state)
        self.assertLess(playback, action_state)
        self.assertLess(action_state, apply_actions)

    def test_map_combat_defers_cleanup0_until_after_solver_exhaustion(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        begin_phase = source.index("elif self.state == 'begin_phase':")
        cleanup_state = source.index("elif self.state == 'cleanup0':")
        cleanup = source.index('self.clean_up0()', cleanup_state)
        self.assertLess(begin_phase, cleanup_state)
        self.assertLess(cleanup_state, cleanup)

    def test_simple_combat_resolves_phases_from_update_not_constructor(self):
        from app.engine.combat.simple_combat import SimpleCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'simple_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_end = source.index('def start_combat', constructor)
        constructor_body = source[constructor:constructor_end]
        self.assertNotIn('while self.state_machine.get_state()', constructor_body)
        self.assertIn("if self.state == 'combat':", source[update:])

        state_machine = Mock()
        state_machine.get_state.side_effect = [True, False]
        state_machine.do.return_value = (['action'], ['playback'])
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.state = 'combat'
        combat.state_machine = state_machine
        combat.full_playback = []
        combat._apply_actions = Mock()
        combat.clean_up0 = Mock()
        combat.clean_up1 = Mock()
        combat.clean_up2 = Mock()

        self.assertFalse(combat.update())
        self.assertEqual(['playback'], combat.full_playback)
        combat._apply_actions.assert_called_once_with()
        state_machine.setup_next_state.assert_called_once_with()

        self.assertFalse(combat.update())
        self.assertEqual('cleanup0', combat.state)
        self.assertFalse(combat.update())
        combat.clean_up0.assert_called_once_with()

    def test_simple_combat_stages_start_hooks_before_solver(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'simple_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_body = source[constructor:update]
        self.assertNotIn('self.start_combat()', constructor_body)
        self.assertNotIn('self.start_event()', constructor_body)
        self.assertIn("if self.state == 'init':", source[update:])
        self.assertIn("if self.state == 'start_event':", source[update:])

        from app.engine.combat.simple_combat import SimpleCombat
        combat = SimpleCombat.__new__(SimpleCombat)
        combat.state = 'init'
        combat.start_combat = Mock()
        combat.start_event = Mock()

        self.assertFalse(combat.update())
        combat.start_combat.assert_called_once_with()
        self.assertEqual('start_event', combat.state)
        self.assertFalse(combat.update())
        combat.start_event.assert_called_once_with()
        self.assertEqual('combat', combat.state)

    def test_base_combat_resolves_one_phase_per_update(self):
        from app.engine.combat.base_combat import BaseCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'base_combat.py').read_text(encoding='utf-8')

        update = source.index('def update')
        update_body = source[update:]
        self.assertNotIn('while self.state_machine.get_state()', update_body)
        self.assertIn("if self.state == 'init':", update_body)
        self.assertIn("if self.state == 'cleanup0':", update_body)

        state_machine = Mock()
        state_machine.get_state.side_effect = [True, False]
        state_machine.do.return_value = (['action'], ['playback'])
        combat = BaseCombat.__new__(BaseCombat)
        combat.state = 'combat'
        combat.state_machine = state_machine
        combat.full_playback = []
        combat._apply_actions = Mock()
        combat.clean_up0 = Mock()

        self.assertFalse(combat.update())
        self.assertEqual(['playback'], combat.full_playback)
        combat._apply_actions.assert_called_once_with()
        self.assertFalse(combat.update())
        self.assertEqual('cleanup0', combat.state)
        self.assertFalse(combat.update())
        combat.clean_up0.assert_called_once_with()

    def test_base_combat_stages_start_hooks_before_solver(self):
        from app.engine.combat.base_combat import BaseCombat

        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'base_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_end = source.index('def start_combat', constructor)
        constructor_body = source[constructor:constructor_end]
        self.assertNotIn('self.start_combat()', constructor_body)
        self.assertNotIn('self.start_event()', constructor_body)
        self.assertIn("if self.state == 'init':", source[update:])
        self.assertIn("if self.state == 'start_event':", source[update:])

        combat = BaseCombat.__new__(BaseCombat)
        combat.state = 'init'
        combat.start_combat = Mock()
        combat.start_event = Mock()

        self.assertFalse(combat.update())
        combat.start_combat.assert_called_once_with()
        self.assertEqual('start_event', combat.state)
        self.assertFalse(combat.update())
        combat.start_event.assert_called_once_with()
        self.assertEqual('combat', combat.state)


if __name__ == '__main__':
    unittest.main()
