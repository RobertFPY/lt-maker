import logging
import math
import os
import collections
from datetime import datetime
import time
from app import lt_log
from app.utilities import file_utils

from app.constants import WINWIDTH, WINHEIGHT, VERSION, FPS, FRAMERATE
from app.engine import engine
from app.engine.performance import RUNTIME_PROFILER

import app.engine.config as cf

_profile = "LT_PROFILE" in os.environ
_default_profile_threshold = 0
_profile_threshold = _default_profile_threshold
_base_window_title = ''
_fps_title_visible = False
_last_fps_title_update = 0.0
FPS_TITLE_UPDATE_INTERVAL = 0.25
if "LT_PROFILE_THRESHOLD" in os.environ:
    try:
        _profile_threshold = float(os.environ["LT_PROFILE_THRESHOLD"])
    except ValueError:
        _profile = False
        print(f'could not parse {os.environ["LT_PROFILE_THRESHOLD"]} as float')

def start(title, from_editor=False, icon_path='favicon.ico', working_directory=None):
    global _base_window_title, _fps_title_visible, _last_fps_title_update
    if from_editor:
        engine.constants['standalone'] = False
    engine.init()
    if working_directory:
        os.chdir(working_directory)
    icon = engine.image_load(icon_path)
    engine.set_icon(icon)

    from app.engine import sprites
    # Sprite decoding must be explicit here instead of happening while
    # app.engine.sprites is imported. Custom components can import action.py
    # while resources are still loading, before Android has installed its
    # absolute-path image loader.
    from app.engine import game_counters
    # Reset the animation counters for a new engine start
    # otherwise, the animation counters would be at a large number instead of 0
    # if you already started the engine this session
    game_counters.ANIMATION_COUNTERS.reset()

    from app.engine import battle_animation
    # Clear out old battle animations that we might have tested with earlier,
    # because they could have changed.
    battle_animation.battle_anim_registry.clear()

    # Hack to get icon to show up in windows
    try:
        import ctypes
        myappid = u'rainlash.lextalionis.ltmaker.current' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        print("Maybe not Windows? (but that's OK)")

    engine.DISPLAYSURF = engine.build_display(engine.get_screensize(True))
    # Decoding is intentionally deferred until the display format is known.
    # convert()/convert_alpha() here makes the common blit path avoid a
    # per-blit format conversion on SDL2 Android software surfaces.
    sprites.load_images(force=from_editor, optimize_for_display=True)
    if working_directory:
        os.chdir(working_directory)
    
    # must happen after pygame.display.set_mode
    # is called in engine.build_display
    from app.engine import fonts
    fonts.load_fonts()
    
    engine.update_time()
    _base_window_title = title + ' - v' + VERSION
    _fps_title_visible = False
    _last_fps_title_update = 0.0
    engine.set_title(_base_window_title)
    print("Version: %s" % VERSION)

screenshot = False
def save_screenshot(raw_events: list, surf):
    global screenshot
    for e in raw_events:
        if e.type == engine.KEYDOWN and e.key == engine.key_map['`']:
            screenshot = True
            if not os.path.isdir('screenshots'):
                os.mkdir('screenshots')
        elif e.type == engine.KEYUP and e.key == engine.key_map['`']:
            screenshot = False
        elif e.type == engine.KEYDOWN and e.key == engine.key_map['f12']:
            if not os.path.isdir('screenshots'):
                os.mkdir('screenshots')
            current_time = str(datetime.now()).replace(' ', '_').replace(':', '.')
            engine.save_surface(surf, 'screenshots/LT_%s.png' % current_time)
    if screenshot:
        current_time = str(datetime.now()).replace(' ', '_').replace(':', '.')
        engine.save_surface(surf, 'screenshots/LT_%s.bmp' % current_time)

def update_fps_title(fps_records, enabled: bool):
    global _fps_title_visible, _last_fps_title_update
    if not _base_window_title:
        return
    if not enabled:
        if _fps_title_visible:
            engine.set_title(_base_window_title)
            _fps_title_visible = False
        return

    current_time = time.monotonic()
    if _fps_title_visible and current_time - _last_fps_title_update < FPS_TITLE_UPDATE_INTERVAL:
        return

    total_time = sum(fps_records)
    if total_time > 0:
        num_frames = len(fps_records)
        fps = int(num_frames / (total_time / 1000))
        max_frame = max(fps_records)
        min_fps = 1000 // max_frame
    else:  # On the very first frame, can't figure out what the FPS is yet.
        fps, min_fps = "--", "--"

    engine.set_title(f'{_base_window_title} | FPS: {fps} | Min FPS: {min_fps}')
    _fps_title_visible = True
    _last_fps_title_update = current_time

def draw_soft_reset(surf, remaining_time: int):
    from app.engine.fonts import FONT
    FONT['chapter-yellow'].blit(str(remaining_time), surf, (surf.get_width()//2 - 4, surf.get_height()//2 - 4))

def check_soft_reset(game, inp) -> bool:
    return game.state.current() != 'title_start' and \
        inp.is_pressed('SELECT') and inp.is_pressed('BACK') and \
        inp.is_pressed('START')

def poll_events(inp):
    """Poll the OS once and never pass the QUIT sentinel to InputManager."""
    with RUNTIME_PROFILER.section('input_poll'):
        raw_events = engine.get_events()
    if raw_events == engine.QUIT:
        return raw_events, None
    with RUNTIME_PROFILER.section('input_process'):
        event = inp.process_input(raw_events)
    return raw_events, event

def check_main_menu_reset(raw_events: list) -> bool:
    return any(
        event.type == engine.KEYDOWN and
        event.key == engine.key_map['r'] and
        getattr(event, 'mod', 0) & engine.KMOD_CTRL
        for event in raw_events
    )

def reset_to_main_menu(game):
    """Immediately discard the active runtime state and return to the title."""
    from app.engine.runtime_reset import queue_return_to_title
    queue_return_to_title(game)
    game.state.process_temp_state()

def check_runtime_debugger(runtime_debugger, raw_events: list) -> bool:
    if not runtime_debugger or not cf.SETTINGS['debug']:
        return False
    handled = False
    hotkeys = {
        engine.key_map['1']: 'max_selected',
        engine.key_map['2']: 'max_players',
        engine.key_map['3']: 'max_enemies',
        engine.key_map['4']: 'enemy_hp',
        engine.key_map['5']: 'enemy_ai',
        engine.key_map['0']: 'complete_chapter',
    }
    for event in raw_events:
        if event.type != engine.KEYDOWN:
            continue
        if event.key == engine.key_map['f11']:
            runtime_debugger.ensure_window()
            handled = True
        elif getattr(event, 'mod', 0) & engine.KMOD_CTRL and event.key in hotkeys:
            runtime_debugger.handle_hotkey(hotkeys[event.key])
            handled = True
    return handled

def get_fast_forward_steps(inp) -> int:
    if not inp.is_pressed('FAST_FORWARD'):
        return 1
    speed = cf.SETTINGS.get('fast_forward_speed', cf.DEFAULT_FAST_FORWARD_SPEED)
    speed = cf.normalize_fast_forward_speed(speed)
    return speed // 100

MAX_FAST_FORWARD_STEP_MS = 34

def get_fast_forward_step_ms(host_delta: int) -> int:
    """Bound extra virtual-time steps without tying them to a 60 FPS host."""
    if host_delta <= 0:
        return FRAMERATE
    return min(host_delta, MAX_FAST_FORWARD_STEP_MS)

def blocks_fast_forward(game) -> bool:
    current_state = game.state.current_state()
    return bool(current_state and getattr(current_state, 'blocks_fast_forward', False))

def update_game_state(game, event, surf, draw=True, input_manager=None):
    if input_manager is None:
        from app.engine.input_manager import get_input_manager
        input_manager = get_input_manager()
    surf, repeat = game.state.update(event, surf, draw=draw)
    # A host frame has one OS input snapshot.  State transitions can require
    # several immediate updates and fast-forward can add more simulation
    # updates, but neither may replay key edges, clicks, or text input.
    input_manager.consume_transient_input()
    while repeat:  # Let the game traverse through state chains
        surf, repeat = game.state.update([], surf, draw=draw)
    return surf

def update_game_state_for_frame(game, event, surf, num_game_updates: int, game_step_ms: int,
                                input_manager=None):
    # Fast-forward simulates several updates from one host frame. Rendering
    # every intermediate update is invisible (only the final surface is
    # presented) and expensive, especially for map composition. Keep the draw
    # inside StateMachine.update to preserve its established lifecycle order.
    deferred_render = num_game_updates > 1
    # Choice and other interactive states explicitly block fast-forward. If
    # one is already current, permit one normal update and draw it.
    planned_updates = (
        1 if deferred_render and blocks_fast_forward(game)
        else num_game_updates)
    updates_run = 0
    draws_run = 0
    for update_idx in range(planned_updates):
        if update_idx and blocks_fast_forward(game):
            break
        if update_idx:
            engine.advance_time(game_step_ms)
        update_event = event if update_idx == 0 else []
        # A fast-forwarded frame simulates several steps but renders only the
        # final one. Crucially, the draw remains inside
        # StateMachine.update(), after start/begin/update and before queued
        # transitions are committed -- exactly the lifecycle position used by
        # desktop.  A state pushed by this final step is therefore not drawn
        # until its own normal update runs on the next host frame.
        draw_this_update = not deferred_render or update_idx == planned_updates - 1
        surf = update_game_state(
            game, update_event, surf,
            draw=draw_this_update, input_manager=input_manager)
        updates_run += 1
        presentation_barrier = bool(
            hasattr(game.state, 'consume_presentation_barrier') and
            game.state.consume_presentation_barrier())
        if draw_this_update:
            draws_run += 1
        elif presentation_barrier:
            draws_run += 1
        if presentation_barrier:
            break
    # If a substep entered a state that blocks fast-forward, it can end this
    # host frame before the planned final draw.  Retaining the last surface
    # for one frame is safe; the next frame is planned as one normal update
    # and will draw the newly-entered state in lifecycle order.
    game._last_fast_forward_draws = draws_run
    return surf, updates_run


def _performance_counters(game, requested_updates=1, updates_run=1,
                          fast_forward_step_ms=FRAMERATE):
    """Cheap counters that reveal scene growth in profiling logs."""
    units = getattr(game, 'units', ())
    positioned = sum(1 for unit in units if getattr(unit, 'position', None))
    tilemap = getattr(game, 'tilemap', None)
    level = getattr(game, 'level', None)
    state_machine = getattr(game, 'state', None)
    current_state = state_machine.current_state() if state_machine else None
    counters = {
        'state': state_machine.current() if state_machine else None,
        'state_stack': state_machine.state_names() if state_machine else (),
        'units': len(units),
        'on_map': positioned,
        'anims': len(getattr(tilemap, 'animations', ())) if tilemap else 0,
        'weather': len(getattr(tilemap, 'weather', ())) if tilemap else 0,
        'level': getattr(level, 'nid', None),
        'tilemap': getattr(tilemap, 'nid', None),
        'regions': len(getattr(level, 'regions', ())) if level else 0,
    }
    active_event = getattr(current_state, 'event', None)
    if active_event:
        counters['event_nid'] = getattr(active_event, 'nid', None)
        processor = getattr(active_event, 'processor', None)
        command_index = getattr(active_event, '_profile_command_index', None)
        if command_index is None:
            command_index = getattr(processor, 'command_pointer', None)
        if command_index is None:
            command_index = getattr(processor, 'curr_cmd_idx', None)
        counters['event_command_index'] = command_index
        counters['event_command'] = getattr(
            active_event, '_profile_command_nid', None)
        if counters['event_command'] is None:
            commands = getattr(processor, 'commands', ())
            if isinstance(command_index, int) and 0 <= command_index < len(commands):
                counters['event_command'] = getattr(commands[command_index], 'nid', None)
    if RUNTIME_PROFILER.enabled:
        counters.update({
            'ff_requested': requested_updates,
            'ff_updates': updates_run,
            'ff_draws': getattr(game, '_last_fast_forward_draws', 1),
            'ff_presents': 1,
            'ff_step_ms': fast_forward_step_ms,
        })
        combat = getattr(current_state, 'combat', None)
        if combat and hasattr(combat, 'state'):
            counters['combat_phase'] = combat.state
            battle_anim = getattr(combat, 'current_battle_anim', None)
            if battle_anim:
                counters['combat_pose'] = battle_anim.current_pose
                counters['combat_frame'] = battle_anim.frame_count
                counters['combat_effects'] = (
                    len(battle_anim.child_effects) +
                    len(battle_anim.under_child_effects))
    return counters

def run(game):
    from app.engine.sound import get_sound_thread
    from app.engine.game_counters import ANIMATION_COUNTERS
    from app.engine.input_manager import get_input_manager

    ANIMATION_COUNTERS.reset()

    get_sound_thread().reset()
    get_sound_thread().set_music_volume(cf.SETTINGS['music_volume'])
    get_sound_thread().set_sfx_volume(cf.SETTINGS['sound_volume'])

    surf = engine.create_surface((WINWIDTH, WINHEIGHT))
    clock = engine.Clock()
    fps_records = collections.deque(maxlen=FPS)
    inp = get_input_manager()

    _error_mode = False
    _error_msg = ''
    _soft_reset_start_time: int = None  # UTC time.time()
    SOFT_RESET_TIME = 3  # seconds
    runtime_debugger = None
    if cf.SETTINGS['debug']:
        try:
            from app.engine.runtime_debugger_controller import get_controller
            get_controller().reset_runtime_state()
            from app.engine.android_runtime import is_android_runtime
            if not is_android_runtime():
                from app.engine import runtime_debugger_service
                runtime_debugger = runtime_debugger_service
                # Every desktop debug runtime starts without a debugger window.
                runtime_debugger_service.stop(close_window=True)
        except Exception:
            logging.exception('Could not reset runtime debugger.')
    while True:
        start = time.perf_counter_ns()
        RUNTIME_PROFILER.begin_frame()

        with RUNTIME_PROFILER.section('time_input'):
            with RUNTIME_PROFILER.section('time_update'):
                engine.update_time()
            raw_events, event = poll_events(inp)
        fps_records.append(engine.get_delta())
        # print(engine.get_delta())

        if raw_events == engine.QUIT:
            break
        check_runtime_debugger(runtime_debugger, raw_events)

        if check_main_menu_reset(raw_events):
            _soft_reset_start_time = None
            _error_mode = False
            reset_to_main_menu(game)
            continue

        # Handle soft reset
        if check_soft_reset(game, inp):
            # Set the start time if not already set
            if not _soft_reset_start_time:
                _soft_reset_start_time = time.time()
            if time.time() - SOFT_RESET_TIME >= _soft_reset_start_time:
                _soft_reset_start_time = None
                _error_mode = False
                reset_to_main_menu(game)
                continue
        else:
            _soft_reset_start_time = None

        # game loop. catch and log any errors in this loop.
        num_game_updates = 1
        updates_run = 1
        game_step_ms = FRAMERATE
        if _error_mode:
            surf = engine.write_system_msg(surf, _error_msg)
            if inp.is_pressed('SELECT') or inp.is_pressed('BACK'):
                log_file = lt_log.get_log_fname()
                if log_file:
                    file_utils.startfile(log_file)
        else:
            try:
                if runtime_debugger:
                    try:
                        runtime_debugger.update()
                    except Exception:
                        logging.exception('Runtime debugger update failed.')
                num_game_updates = get_fast_forward_steps(inp)
                # Use the host-frame delta so normal 30-60 FPS rendering still
                # reaches the requested gameplay speed. Bound only the extra
                # substeps so a single loading hitch cannot be multiplied into
                # a giant virtual-time jump before the next present.
                game_step_ms = get_fast_forward_step_ms(engine.get_delta())
                with RUNTIME_PROFILER.section('state_update_draw'):
                    surf, updates_run = update_game_state_for_frame(
                        game, event, surf, num_game_updates, game_step_ms,
                        input_manager=inp)
                # print("States:\t\t\t", game.state.state)

                update_fps_title(fps_records, bool(cf.SETTINGS['display_fps']))
                if _soft_reset_start_time:
                    draw_soft_reset(surf, math.ceil(SOFT_RESET_TIME - (time.time() - _soft_reset_start_time)))
            except Exception as e:
                logging.exception("Game crashed with exception.")
                log_file_loc = lt_log.get_log_dir() or ''
                _error_msg = "Game crashed with exception:\n%s\nPlease press either the **SELECT** or **BACK** keys to open the log file. Please send the contents of the log file to the game developer to resolve this issue.\nLogs can be found in **%s**" % (str(e).strip(), str(log_file_loc))
                _error_mode = True
                # If we're in editor/debug mode, just throw the error normally
                if cf.SETTINGS['debug']:
                    if runtime_debugger:
                        runtime_debugger.stop(close_window=True)
                    raise e

        with RUNTIME_PROFILER.section('sound'):
            get_sound_thread().update(raw_events)

        with RUNTIME_PROFILER.section('present_compose'):
            engine.push_display(surf, engine.get_screensize(), engine.DISPLAYSURF)
        with RUNTIME_PROFILER.section('present_swap'):
            engine.update_display()

        save_screenshot(raw_events, surf)

        end = time.perf_counter_ns()
        ms_elapsed = (end - start) / 1e6
        if _profile and ms_elapsed > _profile_threshold:
            if _profile_threshold != _default_profile_threshold:
                print(f"Engine took longer than {_profile_threshold}ms: {ms_elapsed}", flush=True)
            else:
                print(f"Engine took: {ms_elapsed}", flush=True)

        with RUNTIME_PROFILER.section('frame_wait'):
            game.playtime += clock.tick()
        RUNTIME_PROFILER.finish_frame(
            _performance_counters(game, num_game_updates, updates_run,
                                  game_step_ms))

    if runtime_debugger:
        runtime_debugger.stop(close_window=True)

def run_in_isolation(obj):
    """
    Requires that the object has
    1) take_input function that takes in the event
    2) update function
    3) draw function that returns the surface to be drawn
    """
    from app.engine.sound import get_sound_thread
    from app.engine.input_manager import get_input_manager

    get_sound_thread().reset()
    get_sound_thread().set_music_volume(cf.SETTINGS['music_volume'])
    get_sound_thread().set_sfx_volume(cf.SETTINGS['sound_volume'])

    surf = engine.create_surface((WINWIDTH, WINHEIGHT))
    clock = engine.Clock()
    inp = get_input_manager()
    while True:
        engine.update_time()

        raw_events, event = poll_events(inp)
        if raw_events == engine.QUIT:
            break

        num_game_updates = get_fast_forward_steps(inp)
        game_step_ms = get_fast_forward_step_ms(engine.get_delta())
        deferred_render = num_game_updates > 1
        for update_idx in range(num_game_updates):
            if update_idx:
                engine.advance_time(game_step_ms)
            update_event = event if update_idx == 0 else []
            obj.take_input(update_event)
            if update_idx == 0:
                inp.consume_transient_input()
            obj.update()
            if not deferred_render or update_idx == num_game_updates - 1:
                surf = obj.draw(surf)

        get_sound_thread().update(raw_events)

        engine.push_display(surf, engine.get_screensize(), engine.DISPLAYSURF)
        save_screenshot(raw_events, surf)

        engine.update_display()
        clock.tick()

def run_combat(mock_combat):
    run_in_isolation(mock_combat)

def run_event(event):
    run_in_isolation(event)
