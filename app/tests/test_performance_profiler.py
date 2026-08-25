import gc
import logging
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.engine import driver
from app.engine.performance import RuntimeProfiler
from app.utilities import static_random


class RuntimeProfilerTests(unittest.TestCase):
    def tearDown(self) -> None:
        static_random.set_seed(0)

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

    def test_enabled_profiler_real_worker_scope_cannot_corrupt_main_scope_tree(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        profiler.slow_frame_ms = 100000
        profiler.begin_frame()
        main_thread_id = threading.get_ident()
        worker_calls = []

        def worker() -> None:
            with profiler.section('worker'):
                worker_calls.append(threading.get_ident())

        with profiler.section('outer'):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
            with profiler.section('inner'):
                pass

        profiler.finish_frame()
        scopes = profiler.latest_frame_scopes()
        self.assertEqual(1, len(worker_calls))
        self.assertNotEqual(main_thread_id, worker_calls[0])
        self.assertEqual(('outer', 'inner'), tuple(scope['name'] for scope in scopes))
        self.assertEqual((None, 0), tuple(scope['parent_scope_id'] for scope in scopes))
        self.assertEqual(main_thread_id, profiler._frame_thread_id)
        self.assertEqual([], profiler._scope_stack)

    def test_profiler_on_off_preserves_rng_and_ordered_gameplay_effects(self):
        def run(profiler_enabled):
            profiler = RuntimeProfiler()
            profiler.enabled = profiler_enabled
            profiler.interval_seconds = 100000
            logical_state = {'hp': 100, 'actions': []}
            static_random.set_seed(1701)

            def gameplay_update() -> None:
                damage = static_random.get_combat()
                logical_state['actions'].append('damage')
                logical_state['hp'] -= damage
                logical_state['actions'].append('cleanup')

            profiler.begin_frame()
            if profiler.enabled:
                with profiler.section('combat.update'):
                    gameplay_update()
            else:
                gameplay_update()
            profiler.finish_frame()
            return logical_state, static_random.get_combat_random_state()

        profiler_off = run(False)
        profiler_on = run(True)
        self.assertEqual(profiler_off, profiler_on)

    def test_disabled_profiler_executes_wrapped_body_and_count_without_gameplay_effect(self):
        profiler = RuntimeProfiler()
        profiler.enabled = False
        logical_state = {'actions': [], 'rng': static_random.get_combat_random_state()}
        with patch.object(logging, 'warning') as warning:
            profiler.begin_frame()
            with profiler.section('event.command'):
                logical_state['actions'].append('command')
            profiler.count('command')
            profiler.finish_frame()

        self.assertEqual(['command'], logical_state['actions'])
        self.assertEqual(static_random.get_combat_random_state(), logical_state['rng'])
        self.assertEqual((), profiler.latest_frame_scopes())
        warning.assert_not_called()

    def test_gc_callback_changes_only_profiler_owned_counters(self):
        profiler = RuntimeProfiler()
        profiler.enabled = True
        logical_state = {'actions': ['attack'], 'rng': static_random.get_combat_random_state()}
        callback_was_registered = profiler._on_gc in gc.callbacks
        if not callback_was_registered:
            gc.callbacks.append(profiler._on_gc)
        try:
            started = profiler._gc_started
            finished = profiler._gc_finished
            profiler._on_gc('start', {})
            profiler._on_gc('stop', {})
            self.assertEqual(started + 1, profiler._gc_started)
            self.assertEqual(finished + 1, profiler._gc_finished)
            self.assertEqual({'actions': ['attack'], 'rng': logical_state['rng']}, logical_state)
        finally:
            if not callback_was_registered:
                gc.callbacks.remove(profiler._on_gc)
        self.assertEqual(callback_was_registered, profiler._on_gc in gc.callbacks)

    def test_profiler_branches_call_same_gameplay_operations(self):
        root = Path(__file__).parents[1]
        state_machine = (root / 'engine' / 'state_machine.py').read_text(encoding='utf-8')
        update_body = state_machine[state_machine.index('def update'):]
        for statement in (
                'start_output = state.start()',
                'begin_output = state.begin()',
                'input_output = state.take_input(event)',
                'update_output = state.update()',
                'state.end()',
                'self.process_temp_state()'):
            self.assertEqual(2, update_body.count(statement))

        event = (root / 'events' / 'event.py').read_text(encoding='utf-8')
        self.assertEqual(1, event.count('self.run_command(command)'))
        driver_source = (root / 'engine' / 'driver.py').read_text(encoding='utf-8')
        self.assertEqual(1, driver_source.count(
            'surf, updates_run = update_game_state_for_frame('))

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

    def test_map_combat_profiles_solver_inside_begin_phase(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        begin_phase = source.index("elif self.state == 'begin_phase':")
        solver = source.index("RUNTIME_PROFILER.section('combat.solver_do')")
        proc_visuals = source.index("elif self.state == 'proc_animations':")
        self.assertNotIn("elif self.state == 'solve_phase':", source)
        self.assertLess(begin_phase, solver)
        self.assertLess(solver, proc_visuals)

    def test_map_combat_keeps_visual_setup_with_solver_update(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        solver = source.index("RUNTIME_PROFILER.section('combat.solver_do')")
        health_bars = source.index("RUNTIME_PROFILER.section('combat.health_bar_build')")
        self.assertNotIn("elif self.state == 'setup_phase_visuals':", source)
        self.assertLess(solver, health_bars)

    def test_animation_combat_keeps_solver_and_visual_destination_in_begin_phase(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')

        begin_phase = source.index("elif self.state == 'begin_phase':")
        solver = source.index('self.state_machine.do()', begin_phase)
        visual_setup = source.index('self.get_actors()', solver)
        combat_effect = source.index("elif self.state == 'combat_effect':", solver)
        self.assertNotIn("elif self.state == 'solve_phase':", source)
        self.assertNotIn("elif self.state == 'setup_phase_visuals':", source)
        self.assertLess(begin_phase, solver)
        self.assertLess(solver, visual_setup)
        self.assertLess(visual_setup, combat_effect)

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

    def test_animation_combat_groups_start_hooks_with_visual_init(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        init_state = source.index("if self.state == 'init':", update)
        start_hook = source.index('self.start_combat()', init_state)
        attacker_sprite = source.index(
            "self.attacker.sprite.change_state('combat_attacker')", start_hook)
        stats = source.index('self._set_stats(self.playback)', attacker_sprite)
        red_cursor = source.index("elif self.state == 'red_cursor':", stats)
        self.assertNotIn("self.state == 'init_visuals'", source)
        self.assertLess(init_state, start_hook)
        self.assertLess(start_hook, attacker_sprite)
        self.assertLess(attacker_sprite, stats)
        self.assertLess(stats, red_cursor)

    def test_animation_combat_groups_cursor_setup_before_initial_stats(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        init_state = source.index("if self.state == 'init':", update)
        cursor = source.index('game.cursor.set_pos(self.view_pos)', init_state)
        refresh = source.index('self._set_stats(self.playback)', cursor)
        self.assertNotIn("self.state == 'init_stats'", source)
        self.assertLess(cursor, refresh)

    def test_animation_combat_groups_arena_pairing_after_stats(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        arena = source.index("elif self.state == 'arena_init':", update)
        refresh = source.index('self._set_stats(self.playback)', arena)
        pairing = source.index('self.pair_battle_animations(0)', refresh)
        fade = source.index("elif self.state == 'arena_fade_in':", pairing)
        self.assertNotIn("self.state == 'arena_visuals'", source)
        self.assertNotIn("self.state == 'arena_pair_animations'", source)
        self.assertLess(arena, refresh)
        self.assertLess(refresh, pairing)
        self.assertLess(pairing, fade)

    def test_animation_combat_groups_transform_decision_with_battle_music(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        music = source.index("elif self.state == 'battle_music':", update)
        load_music = source.index('self.start_battle_music()', music)
        transform_check = source.index(
            'self.left_battle_anim.is_transform()', load_music)
        transform_start = source.index(
            'self.left_battle_anim.initiate_transform()', transform_check)
        transform_wait = source.index("elif self.state == 'transform':", transform_start)
        self.assertNotIn("self.state == 'check_transform'", source)
        self.assertNotIn("self.state == 'initiate_transform'", source)
        self.assertLess(music, load_music)
        self.assertLess(load_music, transform_check)
        self.assertLess(transform_check, transform_start)
        self.assertLess(transform_start, transform_wait)

    def test_android_streamed_battle_music_restores_cached_map_track(self):
        from app.engine.combat import animation_combat as animation_combat_module
        from app.engine.combat.animation_combat import AnimationCombat
        from app.engine.sound import StreamedBattleMusic

        combat = AnimationCombat.__new__(AnimationCombat)
        combat.battle_music = StreamedBattleMusic('map_track', False)
        sound_thread = Mock()

        with patch.object(animation_combat_module.DB.constants, 'value', return_value=True), \
                patch.object(
                    animation_combat_module, 'get_sound_thread',
                    return_value=sound_thread,
                ):
            combat.finish()

        sound_thread.finish_battle_music.assert_called_once_with(
            combat.battle_music, from_start=True,
        )

    def test_animation_combat_keeps_selection_and_delegates_battle_backend(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        start = source.index('def start_battle_music')
        finish = source.index('def left_team', start)
        battle_music = source[start:finish]

        self.assertIn('get_sound_thread().start_battle_music(', battle_music)
        self.assertNotIn('is_android_runtime()', battle_music)
        self.assertNotIn('play_streamed_music(', battle_music)

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

    def test_animation_combat_runs_solver_after_begin_phase_end_check(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')
        update = source.index('def update')
        begin_phase = source.index("elif self.state == 'begin_phase':", update)
        terminal_check = source.index(
            'if not self.state_machine.get_state():', begin_phase)
        solver = source.index('self.state_machine.do()', terminal_check)
        visual_setup = source.index('self.get_actors()', solver)
        self.assertNotIn("self.state == 'solve_phase'", source)
        self.assertNotIn("self.state == 'setup_phase_visuals'", source)
        self.assertLess(begin_phase, terminal_check)
        self.assertLess(terminal_check, solver)
        self.assertLess(solver, visual_setup)

    def test_animation_combat_retains_only_presentation_resource_staging(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')

        for state in (
            'pair_entrance_animations', 'rebuild_transform_animations',
            'repair_transform_animations', 'setup_pre_proc',
            'setup_delayed_death',
            'rebuild_revert_animations',
        ):
            self.assertIn("self.state == '%s'" % state, source)

        for state in (
            'init_visuals', 'init_stats', 'arena_visuals',
            'arena_pair_animations', 'start_event', 'check_transform',
            'initiate_transform', 'solve_phase', 'setup_phase_visuals',
            'setup_phase_followup', 'setup_hit_effect',
            'resume_hit_animation', 'end_combat_focus',
            'end_combat_camera', 'cleanup1', 'finish_combat', 'cleanup2',
            'repair_revert_animations', 'initiate_revert_transforms',
        ):
            self.assertNotIn("self.state == '%s'" % state, source)

    def test_animation_combat_finishes_and_cleans_up_in_terminal_states(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'animation_combat.py').read_text(encoding='utf-8')

        fade_start = source.index("elif self.state == 'fade_out':")
        arena_start = source.index("elif self.state == 'arena_out':", fade_start)
        terminal_end = source.index('if self.state != current_state:', arena_start)
        for terminal_source in (
                source[fade_start:arena_start],
                source[arena_start:terminal_end]):
            finish = terminal_source.index('self.finish()')
            cleanup = terminal_source.index('self.clean_up2()')
            end_skip = terminal_source.index('self.end_skip()')
            done = terminal_source.index('return True')
            self.assertLess(finish, cleanup)
            self.assertLess(cleanup, end_skip)
            self.assertLess(end_skip, done)

    def test_map_combat_applies_actions_with_playback_effects(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        anim_state = source.index("elif self.state == 'anim':")
        hp_wait = source.index("elif self.state == 'hp_bar_wait':")
        playback = source.index('self._handle_playback()', anim_state)
        apply_actions = source.index('self._apply_actions()', playback)
        self.assertNotIn("elif self.state == 'apply_actions':", source)
        self.assertLess(anim_state, playback)
        self.assertLess(playback, apply_actions)
        self.assertLess(apply_actions, hp_wait)

    def test_map_combat_groups_cleanup0_with_terminal_detection(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'map_combat.py').read_text(encoding='utf-8')

        begin_phase = source.index("elif self.state == 'begin_phase':")
        proc_visuals = source.index("elif self.state == 'proc_animations':")
        cleanup = source.index('self.clean_up0()', begin_phase)
        self.assertNotIn("elif self.state == 'cleanup0':", source)
        self.assertLess(begin_phase, cleanup)
        self.assertLess(cleanup, proc_visuals)

    def test_simple_combat_resolves_phases_in_constructor(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'simple_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_body = source[constructor:update]
        self.assertIn('while self.state_machine.get_state()', constructor_body)
        self.assertNotIn("if self.state == 'combat':", source[update:])

    def test_simple_combat_runs_start_hooks_before_solver(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'simple_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_body = source[constructor:update]
        hooks = constructor_body.index('self.start_combat()')
        event = constructor_body.index('self.start_event()')
        solver = constructor_body.index('while self.state_machine.get_state()')
        self.assertLess(hooks, event)
        self.assertLess(event, solver)

    def test_base_combat_drains_all_phases_in_first_update(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'base_combat.py').read_text(encoding='utf-8')

        update = source.index('def update')
        update_body = source[update:]
        self.assertIn('while self.state_machine.get_state()', update_body)
        self.assertIn("if self.state == 'init':", update_body)
        self.assertNotIn("if self.state == 'combat':", update_body)
        solver = update_body.index('self.state_machine.do()')
        apply_actions = update_body.index('self._apply_actions()', solver)
        advance = update_body.index('self.state_machine.setup_next_state()', apply_actions)
        self.assertLess(solver, apply_actions)
        self.assertLess(apply_actions, advance)

    def test_base_combat_runs_start_hooks_in_constructor(self):
        source = (Path(__file__).parents[1] / 'engine' / 'combat' /
                  'base_combat.py').read_text(encoding='utf-8')

        constructor = source.index('def __init__')
        update = source.index('def update')
        constructor_end = source.index('def start_combat', constructor)
        constructor_body = source[constructor:constructor_end]
        hooks = constructor_body.index('self.start_combat()')
        event = constructor_body.index('self.start_event()')
        self.assertLess(hooks, event)
        self.assertNotIn("if self.state == 'start_event':", source[update:])
        self.assertNotIn("if self.state == 'combat':", source[update:])


if __name__ == '__main__':
    unittest.main()
