"""Test-owned deterministic scenario helpers for P1-T03.

The PC-reference process imports this module by absolute path while its own
checkout remains first on ``sys.path``.  The Trace V1 module is supplied as a
read-only observer overlay; no reference source files are altered.
"""
from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from app.engine import config as cf
from app.constants import FRAMERATE


T = TypeVar('T')

PC_REFERENCE_REVISION = '9314f54b49f4552b5a3d023b4da0012ce7dfbc89'
SCENARIO_1_ID = '01_new_game_first_playable_map'
SCENARIO_1_SEED = 1701
SCENARIO_2_ID = '02_existing_save_load'
SCENARIO_4_ID = '04_restart_current_chapter'
SCENARIO_5_ID = '05_standard_map_combat'
SCENARIO_6_ID = '06_simple_combat'
SCENARIO_7_ID = '07_animation_combat'
SCENARIO_8_ID = '08_base_combat'
SCENARIO_9_ID = '09_skill_proc_hooks'
SCENARIO_9_SEED = 0
SCENARIO_10_ID = '10_item_durability_and_broken'
SCENARIO_11_ID = '11_promotion_class_change'
SCENARIO_12_ID = '12_aura_lifecycle'
SCENARIO_13_ID = '13_fog_move_cancel_wait'
SCENARIO_14_ID = '14_tilemap_change'
SCENARIO_15_ID = '15_phase_transition'
SCENARIO_16_ID = '16_fast_forward_equivalence'
SCENARIO_17_ID = '17_observer_idle_hybrid'
SCENARIO_18_ID = '18_game_over_restart'


def run_new_game_with_seed(game, seed: int, capture: Callable[[], T]) -> T:
    """Run ``build_new`` through its authoritative deterministic input.

    ``GameState.build_new`` owns static-RNG initialization.  Restoring the
    configuration in ``finally`` prevents a scenario from leaking its seed to
    another capture in either process.
    """
    previous_seed = cf.SETTINGS['random_seed']
    try:
        cf.SETTINGS['random_seed'] = seed
        game.build_new()
        return capture()
    finally:
        cf.SETTINGS['random_seed'] = previous_seed


class VirtualFrameDriver:
    """Test-owned deterministic equivalent of the outer driver frame loop."""
    def __enter__(self):
        from app.engine import engine
        self._engine = engine
        self._original = {key: engine.constants[key]
                          for key in ('current_time', 'last_time', 'delta_t')}
        engine.constants['current_time'] = 0
        engine.constants['last_time'] = 0
        engine.constants['delta_t'] = 0
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._engine.constants.update(self._original)

    def step(self, game, surf) -> None:
        constants = self._engine.constants
        constants['last_time'] = constants['current_time']
        constants['current_time'] += FRAMERATE
        constants['delta_t'] = FRAMERATE
        _surf, repeat = game.state.update([], surf)
        while repeat:
            _surf, repeat = game.state.update([], surf)


class RawInputFrameDriver(VirtualFrameDriver):
    """Deterministic outer-frame driver using real raw InputManager edges."""
    def __init__(self, input_manager):
        self.input_manager = input_manager

    def __enter__(self):
        super().__enter__()
        self._original_get_true_time = self._engine.get_true_time
        self._original_input = {
            'keys_pressed': dict(self.input_manager.keys_pressed),
            'joys_pressed': dict(self.input_manager.joys_pressed),
            'key_down_events': self.input_manager.key_down_events[:],
            'key_up_events': self.input_manager.key_up_events[:],
            'input_events': list(getattr(self.input_manager, 'input_events', [])),
            'transient_input_consumed': getattr(
                self.input_manager, 'transient_input_consumed', None),
        }
        # With one simulation update per outer frame, deterministic host time
        # and virtual game time advance together.  This preserves FluidScroll's
        # wall-clock contract without host sleeps or fast-forward substeps.
        self._engine.get_true_time = lambda: self._engine.constants['current_time']
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._engine.get_true_time = self._original_get_true_time
        self.input_manager.keys_pressed.clear()
        self.input_manager.keys_pressed.update(self._original_input['keys_pressed'])
        self.input_manager.joys_pressed.clear()
        self.input_manager.joys_pressed.update(self._original_input['joys_pressed'])
        self.input_manager.key_down_events[:] = self._original_input['key_down_events']
        self.input_manager.key_up_events[:] = self._original_input['key_up_events']
        if hasattr(self.input_manager, 'input_events'):
            self.input_manager.input_events = self._original_input['input_events']
        if self._original_input['transient_input_consumed'] is not None:
            self.input_manager.transient_input_consumed = \
                self._original_input['transient_input_consumed']
        super().__exit__(exc_type, exc_value, traceback)

    def _raw_event(self, button: str, pressed: bool):
        event_type = self._engine.KEYDOWN if pressed else self._engine.KEYUP
        return self._engine.pygame.event.Event(
            event_type, key=self.input_manager.key_map[button], mod=0, unicode='')

    def step_edges(self, game, surf, edges=()) -> None:
        constants = self._engine.constants
        constants['last_time'] = constants['current_time']
        constants['current_time'] += FRAMERATE
        constants['delta_t'] = FRAMERATE
        raw_events = [self._raw_event(button, pressed) for button, pressed in edges]
        logical_event = self.input_manager.process_input(raw_events)
        _surf, repeat = game.state.update(logical_event, surf)
        if hasattr(self.input_manager, 'consume_transient_input'):
            self.input_manager.consume_transient_input()
        while repeat:
            _surf, repeat = game.state.update([], surf)

    def press(self, game, surf, button: str) -> None:
        self.step_edges(game, surf, ((button, True),))
        self.step_edges(game, surf, ((button, False),))


class FastForwardFrameDriver(RawInputFrameDriver):
    """Run real fast-forward substeps while keeping host time per outer frame."""
    def __enter__(self):
        super().__enter__()
        self._host_time = 0
        self._engine.get_true_time = lambda: self._host_time
        return self

    def run_outer_frame(self, game, surf, updates: int) -> None:
        from app.engine import driver

        constants = self._engine.constants
        constants['last_time'] = constants['current_time']
        constants['current_time'] += FRAMERATE
        constants['delta_t'] = FRAMERATE
        self._host_time += FRAMERATE
        if not hasattr(driver, 'update_game_state_for_frame'):
            _surf, repeat = game.state.update([], surf)
            while repeat:
                _surf, repeat = game.state.update([], surf)
            return
        driver.update_game_state_for_frame(
            game, [], surf, updates, FRAMERATE, input_manager=self.input_manager)


def _load_trace_overlay(trace_path: Path):
    """Load Trace V1 from the recovery checkout without importing its app.

    The module's engine imports resolve through the target checkout already on
    ``sys.path``.  On the PC reference the only compatibility addition is the
    missing read-only growth-RNG accessor used by Trace V1.
    """
    from app.utilities import static_random

    if not hasattr(static_random, 'get_growth_random_state'):
        static_random.get_growth_random_state = lambda: static_random.r.growth_random.state
    specification = importlib.util.spec_from_file_location('recovery_trace_v1_overlay', trace_path)
    if specification is None or specification.loader is None:
        raise RuntimeError('cannot load Trace V1 overlay: %s' % trace_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _runner_revision() -> str:
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, text=True,
                            capture_output=True)
    return result.stdout.strip()


def _load_project(project_path: str) -> None:
    # Tilemap construction calls ``Surface.convert`` during ``build_new``.
    # Use the same minimal dummy display convention as engine integration tests.
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    import pygame
    from app.data.database.database import DB
    from app.data.resources.resources import RESOURCES
    from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION

    if not pygame.display.get_init():
        pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    DB.load(project_path, CURRENT_SERIALIZATION_VERSION)
    RESOURCES.load(project_path, CURRENT_SERIALIZATION_VERSION)
    from app.engine import fonts, sprites
    sprites.load_images()
    fonts.load_fonts(headless=True)


def _load_testing_project() -> None:
    _load_project('testing_proj.ltproj')


def _prepare_playable_game(game, *, initial_states: Optional[list[str]] = None) -> None:
    """Reset the scenario game and install its locked initial state contract."""
    game.clear()
    if initial_states is None:
        initial_states = ['free']
    if initial_states:
        game.load_states(initial_states)


@contextmanager
def _isolated_save_storage():
    """Give the title restart flow its real save files without touching user saves."""
    previous_root = os.environ.get('LT_USER_DATA_DIR')
    with tempfile.TemporaryDirectory(prefix='p1-t03-s18-') as temporary_root:
        os.environ['LT_USER_DATA_DIR'] = temporary_root
        Path(temporary_root, 'saves').mkdir()
        # The PC reference predates ``LT_USER_DATA_DIR`` and retains relative
        # ``saves/`` paths.  Leave its project cwd intact so build_new can load
        # reference-relative tilemaps; recovery instead uses this temporary
        # user-data root.  Both still call their native save APIs and formats.
        try:
            yield
        finally:
            if previous_root is None:
                os.environ.pop('LT_USER_DATA_DIR', None)
            else:
                os.environ['LT_USER_DATA_DIR'] = previous_root


@contextmanager
def _observe_skill_combat_hooks(trace):
    """Observe selected dispatches without changing their arguments or order."""
    from app.engine import skill_system

    hook_names = ('pre_combat', 'start_combat', 'start_sub_combat', 'cleanup_combat',
                  'end_combat', 'post_combat')
    observer = trace.HookObserver({('skill', hook_name) for hook_name in hook_names})
    originals = {hook_name: getattr(skill_system, hook_name) for hook_name in hook_names}

    def wrap(hook_name, original):
        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            if hook_name == 'start_sub_combat':
                unit_index, target_index, mode_index = 2, 4, 6
                context = {'mode': args[mode_index] if len(args) > mode_index else None,
                           'attack_info': args[7] if len(args) > 7 else None}
            else:
                unit_index, target_index, mode_index = 1, 3, 5
                context = {'mode': args[mode_index] if len(args) > mode_index else None}
            observer.observe(
                'skill', hook_name,
                subjects={'unit_nid': getattr(args[unit_index], 'nid', None),
                          'target_nid': getattr(args[target_index], 'nid', None)},
                context=context,
                phase=hook_name, gameplay_result=result)
            return result
        return observed

    try:
        for hook_name, original in originals.items():
            setattr(skill_system, hook_name, wrap(hook_name, original))
        yield observer
    finally:
        for hook_name, original in originals.items():
            setattr(skill_system, hook_name, original)


@contextmanager
def _idle_observer(mode: str):
    """Exercise a real recovery observer, then leave it before tracing state."""
    if mode == 'disabled':
        yield
        return
    if mode == 'debugger_idle':
        from app.engine import runtime_debugger_service
        from app.engine.runtime_debugger_controller import get_controller

        original_debug = cf.SETTINGS['debug']
        try:
            cf.SETTINGS['debug'] = True
            get_controller().reset_runtime_state()
            runtime_debugger_service.start()
            runtime_debugger_service.update()
            yield
        finally:
            runtime_debugger_service.stop(close_window=True)
            cf.SETTINGS['debug'] = original_debug
        return
    if mode == 'profiler_idle':
        from app.engine.performance import RUNTIME_PROFILER

        original_enabled = RUNTIME_PROFILER.enabled
        original_callback = RUNTIME_PROFILER._on_gc in gc.callbacks
        original_state = {
            '_frame_started_ns': RUNTIME_PROFILER._frame_started_ns,
            '_frame_thread_id': RUNTIME_PROFILER._frame_thread_id,
            '_frame_stages': dict(RUNTIME_PROFILER._frame_stages),
            '_frame_scopes': [dict(scope) for scope in RUNTIME_PROFILER._frame_scopes],
            '_scope_stack': [dict(scope) for scope in RUNTIME_PROFILER._scope_stack],
            '_last_frame_scopes': tuple(dict(scope) for scope in RUNTIME_PROFILER._last_frame_scopes),
            '_next_scope_id': RUNTIME_PROFILER._next_scope_id,
            '_frames': RUNTIME_PROFILER._frames.copy(),
            '_frame_history': RUNTIME_PROFILER._frame_history.copy(),
            '_stage_totals': RUNTIME_PROFILER._stage_totals.copy(),
            '_stage_samples': {name: samples.copy()
                               for name, samples in RUNTIME_PROFILER._stage_samples.items()},
            '_event_counts': RUNTIME_PROFILER._event_counts.copy(),
            '_last_report': RUNTIME_PROFILER._last_report,
            '_gc_started': RUNTIME_PROFILER._gc_started,
            '_gc_finished': RUNTIME_PROFILER._gc_finished,
            '_last_counters': RUNTIME_PROFILER._last_counters,
        }
        try:
            RUNTIME_PROFILER.enabled = True
            if not original_callback:
                gc.callbacks.append(RUNTIME_PROFILER._on_gc)
            RUNTIME_PROFILER.begin_frame()
            with RUNTIME_PROFILER.section('recovery_s17_idle_observer'):
                pass
            RUNTIME_PROFILER.finish_frame({'scenario': SCENARIO_17_ID})
            yield
        finally:
            RUNTIME_PROFILER.enabled = original_enabled
            if not original_callback:
                gc.callbacks.remove(RUNTIME_PROFILER._on_gc)
            for name, value in original_state.items():
                setattr(RUNTIME_PROFILER, name, value)
        return
    raise ValueError('unknown scenario 17 observer mode: %s' % mode)


def capture_scenario_1(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Capture the terminal state of real chapter 0 after a deterministic new game."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import game_state

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_1_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_seed_1701_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        recorder.checkpoint('player.control.ready', game, context={'level_nid': '0'})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_2(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Restore a real in-memory save assembled by the reference engine API."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import game_state

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game, initial_states=[])
    recorder = trace.TraceRecorder(SCENARIO_2_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_seed_1701_in_memory_save_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        save_payload, _metadata = game.save()
        game.clear()
        game.load(save_payload)
        recorder.checkpoint('save.restore.complete', game, context={'level_nid': '0'})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_4(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Use the PC restart-slot save/load path, not later debugger helpers."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import game_state, save

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game, initial_states=[])
    recorder = trace.TraceRecorder(SCENARIO_4_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_restart_slot_seed_1701_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        save_payload, metadata = game.save()
        metadata['kind'] = 'start'
        save.save_io(save_payload, metadata, None, 0)
        restart_slot = save.load_restarts()[0]
        save.load_game(game, restart_slot)
        recorder.checkpoint('restart.complete', game, context={'level_nid': '0', 'slot': 0})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_5(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Complete a real player MapCombat, including its normal EXP presentation."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import engine, game_state
    from app.engine.combat import interaction

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_5_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'testing_proj_chapter_0_eirika_map_combat_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker, defender = game.get_unit('Eirika'), game.get_unit('102')
        interaction.start_combat(attacker, defender.position, attacker.get_weapon(),
                                 force_no_animation=True)
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    recorder.checkpoint('combat.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'defender_nid': '102'})
                    return recorder.finish()
        raise RuntimeError('scenario 5 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_6(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Complete real ``SimpleCombat`` through the normal combat state flow."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import engine, game_state
    from app.engine.combat import interaction

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_6_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'testing_proj_chapter_0_eirika_simple_combat_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker, defender = game.get_unit('Eirika'), game.get_unit('102')
        interaction.start_combat(attacker, defender.position, attacker.get_weapon(), skip=True)
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    recorder.checkpoint('combat.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'defender_nid': '102'})
                    return recorder.finish()
        raise RuntimeError('scenario 6 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_7(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Complete a real battle-animation combat without synthetic inputs."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import engine, game_state
    from app.engine.combat import interaction
    from app.engine.combat.animation_combat import AnimationCombat

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_7_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_animation_combat_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker, defender = game.get_unit('Eirika'), game.get_unit('102')
        interaction.start_combat(attacker, defender.position, attacker.get_weapon(),
                                 force_animation=True)
        if not game.combat_instance or not isinstance(game.combat_instance[0], AnimationCombat):
            raise RuntimeError('scenario 7 fixture did not construct AnimationCombat')
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    recorder.checkpoint('combat.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'defender_nid': '102'})
                    return recorder.finish()
        raise RuntimeError('scenario 7 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_8(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Use a real base/prep item through ``BaseCombat`` and normal cleanup."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import engine, game_state
    from app.engine.combat import interaction
    from app.engine.combat.base_combat import BaseCombat

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_8_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_vulnerary_base_combat_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker = game.get_unit('Eirika')
        item = next(item for item in attacker.items if item.nid == 'Vulnerary')
        interaction.start_combat(attacker, None, item)
        if not game.combat_instance or not isinstance(game.combat_instance[0], BaseCombat):
            raise RuntimeError('scenario 8 fixture did not construct BaseCombat')
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    recorder.checkpoint('combat.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'item_nid': 'Vulnerary'})
                    return recorder.finish()
        raise RuntimeError('scenario 8 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_9(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Use DB-defined proc skills and observe real combat lifecycle hooks."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import action, engine, game_state
    from app.engine.combat import interaction

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_9_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_luna_seed_0_v1',
                    'seed': SCENARIO_9_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker, defender = game.get_unit('Eirika'), game.get_unit('102')
        action.do(action.AddSkill(attacker, 'Luna'))
        surface = engine.create_surface((1, 1))
        with _observe_skill_combat_hooks(trace) as observer, VirtualFrameDriver() as frames:
            recorder.hook_observer = observer
            interaction.start_combat(attacker, defender.position, attacker.get_weapon(), skip=True)
            combat = game.combat_instance[0]
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    attack_proc_count = sum(brush.nid == 'attack_proc' for brush in combat.full_playback)
                    if attack_proc_count != 1:
                        raise RuntimeError('scenario 9 expected exactly one real skill proc, got %d' %
                                           attack_proc_count)
                    observed = {call['hook_name'] for call in observer.calls}
                    required = {'pre_combat', 'start_combat', 'start_sub_combat',
                                'cleanup_combat', 'end_combat', 'post_combat'}
                    if not required <= observed:
                        raise RuntimeError('scenario 9 did not observe required skill hooks: %s' %
                                           sorted(required - observed))
                    recorder.checkpoint('combat.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'defender_nid': '102',
                                                 'attack_proc_count': attack_proc_count})
                    return recorder.finish()
        raise RuntimeError('scenario 9 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_9_SEED, capture)
    finally:
        game.clear()


def capture_scenario_10(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Consume a real one-use item and verify normal broken-item cleanup."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import action, engine, game_state, item_funcs, item_system
    from app.engine.combat import interaction
    from app.engine.combat.base_combat import BaseCombat

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_10_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_angelic_robe_one_use_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker = game.get_unit('Eirika')
        item = item_funcs.create_item(attacker, 'Angelic_Robe')
        action.do(action.GiveItem(attacker, item))
        interaction.start_combat(attacker, None, item)
        if not game.combat_instance or not isinstance(game.combat_instance[0], BaseCombat):
            raise RuntimeError('scenario 10 fixture did not construct BaseCombat')
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    if (item.data['uses'] != 0 or not item_system.is_broken(attacker, item) or
                            item_funcs.available(attacker, item) or item in attacker.items):
                        raise RuntimeError('scenario 10 did not complete normal broken-item cleanup')
                    recorder.checkpoint('item.broken.cleanup.complete', game,
                                        context={'attacker_nid': 'Eirika', 'item_nid': 'Angelic_Robe',
                                                 'uses_after': item.data['uses'],
                                                 'broken': item_system.is_broken(attacker, item),
                                                 'available': item_funcs.available(attacker, item),
                                                 'removed_from_inventory': item not in attacker.items})
                    return recorder.finish()
        raise RuntimeError('scenario 10 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_11(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Use the single-route Lunar Brace promotion without inventing a choice."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import action, engine, game_state, item_funcs
    from app.engine.combat import interaction

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_11_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_lunar_brace_single_route_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        attacker = game.get_unit('Eirika')
        action.do(action.SetLevel(attacker, 10))
        item = item_funcs.create_item(attacker, 'Lunar_Brace')
        action.do(action.GiveItem(attacker, item))
        interaction.start_combat(attacker, None, item)
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(2000):
                frames.step(game, surface)
                names = game.state.state_names()
                if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                        names and names[-1] == 'free' and not game.exp_instance):
                    if attacker.klass != 'Eirika_Great_Lord' or item in attacker.items:
                        raise RuntimeError('scenario 11 did not complete Lunar Brace promotion')
                    recorder.checkpoint('promotion.complete', game,
                                        context={'unit_nid': 'Eirika', 'from_class': 'Eirika_Lord',
                                                 'to_class': attacker.klass,
                                                 'item_consumed': item not in attacker.items})
                    return recorder.finish()
        raise RuntimeError('scenario 11 did not complete within 2000 virtual frames')

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_12(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Propagate a DB aura, restore it through load, then tear it down."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import action, game_state

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_12_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_inspiration_aura_save_load_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def has_child(unit) -> bool:
        return any(skill.nid == 'Inspiration_child' for skill in unit.skills)

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        source, recipient = game.get_unit('Eirika'), game.get_unit('Seth')
        action.do(action.AddSkill(source, 'Inspiration'))
        if not has_child(recipient):
            raise RuntimeError('scenario 12 did not propagate Inspiration to Seth')
        recorder.checkpoint('aura.propagated', game,
                            context={'source_nid': 'Eirika', 'recipient_nid': 'Seth',
                                     'child_skill_nid': 'Inspiration_child'})

        save_payload, _metadata = game.save()
        game.clear()
        game.load(save_payload)
        source, recipient = game.get_unit('Eirika'), game.get_unit('Seth')
        if not has_child(recipient):
            raise RuntimeError('scenario 12 did not rebuild aura after load')
        recorder.checkpoint('aura.load.complete', game,
                            context={'source_nid': 'Eirika', 'recipient_nid': 'Seth',
                                     'child_skill_nid': 'Inspiration_child'})

        action.do(action.RemoveSkill(source, 'Inspiration'))
        if has_child(recipient):
            raise RuntimeError('scenario 12 did not tear down aura child skill')
        recorder.checkpoint('aura.teardown.complete', game,
                            context={'source_nid': 'Eirika', 'recipient_nid': 'Seth',
                                     'child_skill_removed': True})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_13(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Exercise fog-aware move preview, cancel, and an explicit Wait input."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import action, engine, game_state
    from app.engine.input_manager import get_input_manager

    _load_project('default.ltproj')
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_13_ID, game=game)
    recorder.begin({'reference_revision': PC_REFERENCE_REVISION,
                    'runner_revision': _runner_revision(),
                    'platform_profile': platform_profile,
                    'input_fixture_id': 'default_proj_chapter_0_eirika_fog_move_cancel_wait_seed_1701_v1',
                    'seed': SCENARIO_1_SEED})

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        action.do(action.SetLevelVar('_fog_of_war', True))
        action.do(action.SetLevelVar('_fog_of_war_radius', 1))
        if not game.get_current_fog_info().is_active:
            raise RuntimeError('scenario 13 did not enable fog through the level-var action path')
        unit = game.get_unit('Eirika')
        origin = unit.position
        surface = engine.create_surface((1, 1))
        input_manager = get_input_manager()
        with RawInputFrameDriver(input_manager) as frames:
            frames.step_edges(game, surface)
            game.cursor.set_pos(origin)
            frames.press(game, surface, 'SELECT')
            if game.state.current() != 'move':
                raise RuntimeError('scenario 13 did not enter move preview through FreeState input')
            recorder.checkpoint('fog.move.preview', game,
                                context={'unit_nid': 'Eirika', 'origin': origin,
                                         'fog_active': game.get_current_fog_info().is_active})

            frames.press(game, surface, 'BACK')
            if game.state.current() != 'free' or game.cursor.cur_unit is not None or unit.position != origin:
                raise RuntimeError('scenario 13 move cancel did not restore free map control')
            recorder.checkpoint('fog.move.cancel.complete', game,
                                context={'unit_nid': 'Eirika', 'position': unit.position})

            game.cursor.set_pos(origin)
            frames.press(game, surface, 'SELECT')
            frames.press(game, surface, 'SELECT')
            menu_state = game.state.current_state()
            if game.state.current() != 'menu' or menu_state.menu.get_current() is None:
                raise RuntimeError('scenario 13 did not reach the real unit menu')
            for _input_step in range(4):
                frames.press(game, surface, 'DOWN')
            if menu_state.menu.get_current() != 'Wait':
                raise RuntimeError('scenario 13 raw InputManager schedule did not select Wait')
            frames.press(game, surface, 'SELECT')
            if game.state.current() != 'free' or not unit.finished:
                raise RuntimeError('scenario 13 Wait input did not commit the unit action')
            recorder.checkpoint('fog.wait.complete', game,
                                context={'unit_nid': 'Eirika', 'position': unit.position,
                                         'finished': unit.finished})
            return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_14(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Complete a real event-owned tilemap change before taking its trace."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import game_state
    from app.events import event_functions, triggers
    from app.events.event import Event
    from app.events.event_prefab import EventPrefab

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_14_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_prologue_to_magvel_tilemap_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        if game.level.tilemap.nid != 'Prologue':
            raise RuntimeError('scenario 14 did not start on Prologue tilemap')
        prefab = EventPrefab('recovery_s14_tilemap_change')
        event = Event(prefab, triggers.GenericTrigger(), game)
        event_functions.change_tilemap(event, 'Magvel')
        update = event.should_update.get('tilemap_change')
        # The PC reference completes this event command synchronously.  Recovery
        # owns the same command transaction through a queued event callback.
        # Observe both only after their real command path has reached terminal
        # completion; no synthetic tilemap/board mutation is introduced here.
        if update:
            for _frame in range(512):
                if update(True):
                    break
            else:
                raise RuntimeError('scenario 14 tilemap job did not complete through its event callback')
        if game.level.tilemap.nid != 'Magvel':
            raise RuntimeError('scenario 14 did not commit the replacement tilemap')
        recorder.checkpoint('tilemap.change.commit', game,
                            context={'from_tilemap_nid': 'Prologue', 'tilemap_nid': 'Magvel'})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_15(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Advance a real phase transition through its completed map-state boundary."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import engine, game_state

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_15_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_player_to_enemy_phase_seed_1701_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        if game.phase.get_current() != 'other':
            raise RuntimeError('scenario 15 did not begin at the chapter-start other phase')
        game.phase.next()
        game.state.change('phase_change')
        surface = engine.create_surface((1, 1))
        with VirtualFrameDriver() as frames:
            for _frame in range(256):
                frames.step(game, surface)
                if game.state.current() == 'free' and game.phase.get_current() == 'player':
                    break
            else:
                raise RuntimeError('scenario 15 phase transition did not commit within frame cap')
        recorder.checkpoint('phase.transition.complete', game,
                            context={'from_phase': 'other', 'phase': 'player'})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_16(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Compare real fast-forward OFF/ON execution under the same combat input."""
    trace = _load_trace_overlay(trace_path)
    from app.engine import driver, engine, game_state
    from app.engine.combat import interaction
    from app.engine.input_manager import get_input_manager

    _load_testing_project()
    game = game_state.game
    supports_fast_forward = hasattr(driver, 'get_fast_forward_steps')

    def run_variant(enabled: bool) -> list[dict[str, Any]]:
        _prepare_playable_game(game)
        recorder = trace.TraceRecorder(SCENARIO_16_ID, game=game)
        recorder.begin({
            'reference_revision': PC_REFERENCE_REVISION,
            'runner_revision': _runner_revision(),
            'platform_profile': platform_profile,
            'input_fixture_id': 'testing_proj_chapter_0_simple_combat_fast_forward_v1',
            'seed': SCENARIO_1_SEED,
        })

        def capture() -> list[dict[str, Any]]:
            game.start_level('0')
            attacker, defender = game.get_unit('Eirika'), game.get_unit('102')
            interaction.start_combat(attacker, defender.position, attacker.get_weapon(), skip=True)
            surface = engine.create_surface((1, 1))
            input_manager = get_input_manager()
            with FastForwardFrameDriver(input_manager) as frames:
                if enabled:
                    input_manager.process_input([frames._raw_event('FAST_FORWARD', True)])
                for _frame in range(2000):
                    steps = (driver.get_fast_forward_steps(input_manager)
                             if supports_fast_forward else 1)
                    if enabled and steps <= 1:
                        raise RuntimeError('scenario 16 raw FAST_FORWARD input did not enable fast-forward')
                    frames.run_outer_frame(game, surface, steps)
                    names = game.state.state_names()
                    if (not game.state.temp_state and 'combat' not in names and 'exp' not in names and
                            names and names[-1] == 'free' and not game.exp_instance):
                        recorder.checkpoint('fast_forward.comparison.end', game,
                                            context={'attacker_nid': 'Eirika', 'defender_nid': '102'})
                        return recorder.finish()
            raise RuntimeError('scenario 16 did not complete within 2000 virtual frames')

        try:
            return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
        finally:
            game.clear()

    off_records = run_variant(False)
    if supports_fast_forward:
        on_records = run_variant(True)
        trace.compare_records(off_records, on_records)
    return off_records


def capture_scenario_17(trace_path: Path, platform_profile: str,
                        observer_mode: str = 'disabled') -> list[dict[str, Any]]:
    """Capture the observer-free logical result after a real idle observer path."""
    if platform_profile == 'pc_reference' and observer_mode != 'disabled':
        raise RuntimeError('scenario 17 never simulates an enabled observer on the PC reference')
    trace = _load_trace_overlay(trace_path)
    from app.engine import game_state

    _load_testing_project()
    game = game_state.game
    _prepare_playable_game(game)
    recorder = trace.TraceRecorder(SCENARIO_17_ID, game=game)
    recorder.begin({
        'reference_revision': PC_REFERENCE_REVISION,
        'runner_revision': _runner_revision(),
        'platform_profile': platform_profile,
        'input_fixture_id': 'testing_proj_chapter_0_observer_idle_seed_1701_v1',
        'seed': SCENARIO_1_SEED,
    })

    def capture() -> list[dict[str, Any]]:
        game.start_level('0')
        recorder.checkpoint('observer.disabled.baseline', game,
                            context={'level_nid': '0', 'phase': game.phase.get_current()})
        with _idle_observer(observer_mode):
            pass
        recorder.checkpoint('observer.idle.complete', game,
                            context={'level_nid': '0', 'phase': game.phase.get_current()})
        return recorder.finish()

    try:
        return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
    finally:
        game.clear()


def capture_scenario_18(trace_path: Path, platform_profile: str) -> list[dict[str, Any]]:
    """Run the DB-owned Eirika loss event through title Restart Level."""
    trace = _load_trace_overlay(trace_path)
    runner_revision = _runner_revision()
    _load_project('default.ltproj')

    with _isolated_save_storage():
        from app.engine import engine, game_state, save
        from app.engine.input_manager import get_input_manager
        from app.events import triggers

        game = game_state.game
        _prepare_playable_game(game)
        recorder = trace.TraceRecorder(SCENARIO_18_ID, game=game)
        recorder.begin({
            'reference_revision': PC_REFERENCE_REVISION,
            'runner_revision': runner_revision,
            'platform_profile': platform_profile,
            'input_fixture_id': 'default_proj_chapter_0_death_eirika_restart_slot_seed_1701_v1',
            'seed': SCENARIO_1_SEED,
        })

        def drive_until(frames, surface, predicate, description: str, limit: int = 1024) -> None:
            for _frame in range(limit):
                frames.step(game, surface)
                if predicate():
                    return
            raise RuntimeError('scenario 18 did not reach %s within %d virtual frames' %
                               (description, limit))

        def capture() -> list[dict[str, Any]]:
            game.start_level('0')
            save_payload, metadata = game.save()
            metadata['kind'] = 'start'
            save.save_io(save_payload, metadata, None, 0)
            save.check_save_slots()
            if save.SAVE_SLOTS[0].kind != 'start' or save.RESTART_SLOTS[0].kind != 'start':
                raise RuntimeError('scenario 18 did not create a real start/restart slot')

            eirika = game.get_unit('Eirika')
            death_trigger = triggers.CombatDeath(eirika, None, eirika.position)
            if not game.events.trigger(death_trigger):
                raise RuntimeError('scenario 18 CombatDeath did not dispatch Global DeathEirika')
            if game.events.event_stack[-1].nid != 'Global DeathEirika':
                raise RuntimeError('scenario 18 selected a non-reference death event')

            surface = engine.create_surface((1, 1))
            input_manager = get_input_manager()
            with RawInputFrameDriver(input_manager) as frames:
                for _frame in range(1024):
                    event_state = game.state.current_state()
                    if (game.state.current() == 'event' and
                            getattr(getattr(event_state, 'event', None), 'state', None) == 'dialog'):
                        frames.press(game, surface, 'SELECT')
                    else:
                        frames.step(game, surface)
                    if game.state.current() == 'game_over' and not game.state.temp_state:
                        recorder.checkpoint('game_over.transition.commit', game,
                                            context={'event_nid': 'Global DeathEirika'})
                        break
                else:
                    raise RuntimeError('scenario 18 did not reach the real game_over state')

                drive_until(
                    frames, surface,
                    lambda: (game.state.current() == 'game_over' and
                             getattr(game.state.current_state(), 'state', None) == 'stasis'),
                    'GameOverState stasis')
                frames.press(game, surface, 'SELECT')
                drive_until(frames, surface,
                            lambda: game.state.current() == 'title_start' and not game.state.temp_state,
                            'committed title_start')
                recorder.checkpoint('game_over.title_start.commit', game,
                                    context={'event_nid': 'Global DeathEirika'})

                drive_until(
                    frames, surface,
                    lambda: (game.state.current() == 'title_start' and
                             game.state.current_state().processed and not game.state.temp_state),
                    'title_start input readiness')
                frames.press(game, surface, 'SELECT')
                drive_until(
                    frames, surface,
                    lambda: (game.state.current() == 'title_main' and
                             getattr(game.state.current_state(), 'state', None) == 'normal' and
                             not game.state.temp_state),
                    'title_main Restart Level menu')
                title_main = game.state.current_state()
                if title_main.menu.get_current() != 'Load Game':
                    raise RuntimeError('scenario 18 title menu did not begin at Load Game')
                frames.press(game, surface, 'DOWN')
                if title_main.menu.get_current() != 'Restart Level':
                    raise RuntimeError('scenario 18 raw title input did not select Restart Level')
                frames.press(game, surface, 'SELECT')
                drive_until(
                    frames, surface,
                    lambda: (game.state.current() == 'title_restart' and
                             getattr(game.state.current_state(), 'state', None) == 'normal' and
                             not game.state.temp_state),
                    'title_restart slot menu')
                title_restart = game.state.current_state()
                if title_restart.menu.current_index != 0:
                    raise RuntimeError('scenario 18 restart menu did not select its real slot 0')
                frames.press(game, surface, 'SELECT')
                drive_until(
                    frames, surface,
                    lambda: (game.state.current() == 'free' and not game.state.temp_state and
                             game.get_unit('Eirika') is not None),
                    'restarted playable map control', limit=2048)
                recorder.checkpoint('restart.complete', game,
                                    context={'level_nid': '0', 'slot': 0,
                                             'source_event_nid': 'Global DeathEirika'})
                return recorder.finish()

        try:
            return run_new_game_with_seed(game, SCENARIO_1_SEED, capture)
        finally:
            game.clear()


SCENARIOS = {
    SCENARIO_1_ID: capture_scenario_1,
    SCENARIO_2_ID: capture_scenario_2,
    SCENARIO_4_ID: capture_scenario_4,
    SCENARIO_5_ID: capture_scenario_5,
    SCENARIO_6_ID: capture_scenario_6,
    SCENARIO_7_ID: capture_scenario_7,
    SCENARIO_8_ID: capture_scenario_8,
    SCENARIO_9_ID: capture_scenario_9,
    SCENARIO_10_ID: capture_scenario_10,
    SCENARIO_11_ID: capture_scenario_11,
    SCENARIO_12_ID: capture_scenario_12,
    SCENARIO_13_ID: capture_scenario_13,
    SCENARIO_14_ID: capture_scenario_14,
    SCENARIO_15_ID: capture_scenario_15,
    SCENARIO_16_ID: capture_scenario_16,
    SCENARIO_17_ID: capture_scenario_17,
    SCENARIO_18_ID: capture_scenario_18,
}


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8', newline='\n') as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=True, sort_keys=True,
                                         separators=(',', ':')) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description='P1-T03 Trace V1 scenario capture')
    parser.add_argument('--scenario', choices=tuple(SCENARIOS), required=True)
    parser.add_argument('--trace-overlay', type=Path, required=True)
    parser.add_argument('--platform-profile', required=True)
    parser.add_argument('--observer-mode',
                        choices=('disabled', 'debugger_idle', 'profiler_idle'),
                        default='disabled')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    capture = SCENARIOS[arguments.scenario]
    if arguments.scenario == SCENARIO_17_ID:
        records = capture(arguments.trace_overlay, arguments.platform_profile,
                          arguments.observer_mode)
    elif arguments.observer_mode != 'disabled':
        parser.error('--observer-mode applies only to scenario 17')
    else:
        records = capture(arguments.trace_overlay, arguments.platform_profile)
    write_jsonl(records, arguments.output)


if __name__ == '__main__':
    main()
