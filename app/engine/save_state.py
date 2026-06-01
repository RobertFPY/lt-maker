"""
GBA-emulator style "save state" system for lt-maker.

This is a SEPARATE layer on top of the existing save/suspend system. It does NOT
touch the normal save slots, suspend file, restart files, preload files or the
turnwheel. It writes to its own dedicated files so that nothing about the
vanilla save behavior changes.

There are 9 hand-addressable slots (1-9), driven entirely by hotkeys:
    * Shift + F1..F9  -> quick save into slot 1..9
    * F1..F9          -> quick load from slot 1..9

There is no in-game menu; everything is hotkey driven (see driver.run).

Loading
-------
Loading rebuilds the entire game from the file and works at ANY time, even in
the middle of combat, an event, or unit movement. Before handing off to
``save.load_game`` we hard-reset the state machine stack so that whatever was
running (an event, a combat, a movement) is fully discarded instead of being
left underneath the restored states. (This is the fix for "load does nothing
until the event finishes".)

Saving
------
There are two snapshot sources, picked automatically per save:

1. Live snapshot (exact moment). ``game.save()`` does NOT pickle the live game
   object -- it builds a plain dict from each component's own ``save()`` method.
   In particular the running event is serialized through
   ``game.events.save() -> Event.save() -> processor.save()``, which stores the
   command pointer, so an event can be resumed at the exact command it was on.
   We therefore take a live snapshot whenever the whole state stack is
   *reconstructable* from that dict: the idle states below, optionally with one
   or more ``event`` states on top. This is what makes "save mid-event, load
   back into the middle of the event" work.

2. Rolling pre-action checkpoint (turnwheel-like fallback). Some states -- combat,
   movement, menus -- hold live pygame Surfaces / animation objects or have
   already mutated a unit's position, and are NOT fully captured by
   ``game.save()``. Snapshotting those directly would crash or restore a broken
   frame. For them we fall back to ``_checkpoint``: an in-memory snapshot of the
   most recent *idle* ("pre-action") state, refreshed by ``capture_checkpoint``
   whenever the game enters one of the idle ``CHECKPOINT_STATES``. A save taken
   during combat/movement therefore lands on the clean moment *before* that
   action, exactly like the turnwheel.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime

from app.data.database.database import DB
from app.engine import save

NUM_SLOTS = 9

# The kind tag stored in the metadata of a save state.
KIND = 'savestate'

# Idle, fully-picklable states that represent a clean "pre-action" moment. The
# rolling checkpoint is refreshed whenever the game enters one of these. We
# deliberately exclude 'move'/'movement'/'menu'/'combat'/event states so the
# checkpoint never captures a unit that has already left its original tile or a
# combat that is mid-resolution.
CHECKPOINT_STATES = {
    'free',
    'turn_change',
    'phase_change',
    'prep_main',
    'base_main',
    'overworld',
}

# In-memory snapshot of the latest idle state: a (s_dict, meta_dict) tuple, or
# None if we have not reached an idle state yet this session.
_checkpoint = None
# Name of the state for which _checkpoint was last taken, used for cheap edge
# detection so we only re-pickle on entering an idle state (not every frame).
_last_state = None
# (event_nid, command_index, event_stack_depth) of the last *clean* in-event
# command boundary the checkpoint was refreshed at. Used so the rolling
# checkpoint keeps advancing through a cutscene (one clean point per command)
# instead of being frozen at the idle state from before the event started.
_last_event_key = None
# engine time (ms) of the last in-event checkpoint refresh, used to throttle the
# per-command re-pickling so a burst of instantaneous commands can't stutter.
_last_event_refresh_time = 0
# Minimum gap between two in-event checkpoint refreshes.
_EVENT_REFRESH_THROTTLE_MS = 150

# States that may sit on TOP of the stack and still be live-snapshotted. Only
# 'event' qualifies beyond the idle CHECKPOINT_STATES: the event manager
# serializes each running event (including its command pointer), so a live
# snapshot taken while an event is on the stack resumes at the exact command it
# was on.
LIVE_SNAPSHOT_TOP_STATES = {'event'}


# States that carry live, in-progress action data which is NOT captured by
# game.save(). The state machine only serializes state *names* (see
# StateMachine.save) and rebuilds each state fresh, so any state whose meaning
# depends on transient, mid-action data would restore a broken frame: a unit
# frozen mid-move, a combat mid-resolution, a death animation mid-play, an AI
# mid-decision, etc. If any of these is anywhere on the stack we refuse the live
# snapshot and fall back to the rolling pre-action checkpoint (turnwheel-like).
#
# Note that ordinary map/menu states (free, phase_change, status_upkeep,
# objective_menu, ...) are NOT listed: they reconstruct faithfully from their
# name plus the saved game objects, exactly as the vanilla suspend system relies
# on. This is what lets an event running on top of, say, 'status_upkeep' or
# 'phase_change' be snapshotted and resumed in place.
UNSAFE_LIVE_SNAPSHOT_STATES = {
    'combat',
    'dying',
    'move',
    'movement',
    'move_camera',
    'ai',
    'overworld_movement',
    'free_roam',
    'free_roam_rationalize',
}


def _async_in_progress(game) -> bool:
    """True if a unit/camera move, screen transition, or other in-progress event
    async work is currently animating.

    This is the key guard for "save during movement". Event-driven movement does
    NOT push a 'move'/'movement' state -- it runs through ``game.movement`` while
    the top state stays ``'event'`` -- so a state-name check alone cannot see it.
    Crucially, ``action.Move.do()`` only calls ``game.movement.begin_move()``;
    the unit's final ``game.arrive()`` happens later in ``Move.execute()`` when
    the animation completes. A live snapshot taken mid-move would therefore store
    an event whose command pointer is already past the move command, while the
    movement itself (held only in the un-serialized movement system) is lost --
    the unit would never finish arriving and the event would resume corrupt. In
    that situation we must fall back to the rolling pre-action checkpoint.
    """
    movement = getattr(game, 'movement', None)
    if movement is not None:
        try:
            if len(movement) > 0:
                return True
        except TypeError:
            pass
    events_mgr = getattr(game, 'events', None)
    if events_mgr is not None:
        for ev in events_mgr.all_events:
            # Pending async callbacks (movement/camera/animation), an unblock
            # condition, or a mid-flight screen transition all mean the event is
            # not at a clean, fully-serializable command boundary.
            if getattr(ev, 'should_update', None):
                return True
            if getattr(ev, 'should_remain_blocked', None):
                return True
            if getattr(ev, 'transition_state', None):
                return True
    return False


def _can_live_snapshot(game) -> bool:
    """True if ``game.save()`` right now would capture the exact present moment
    in a way that can be loaded back faithfully.

    The state machine is saved by name and rebuilt, and a running event fully
    serializes its own command pointer, so the present moment can be snapshotted
    as long as the top of the stack is an idle state or a resumable ``event``
    AND nothing on the stack is a state that holds un-serialized in-progress
    action data (combat, movement, AI, ...). If an event was triggered on top of
    a live combat or during unit movement, that underlying state is in
    ``UNSAFE_LIVE_SNAPSHOT_STATES`` and we fall back to the rolling pre-action
    checkpoint instead.

    Finally, even when the stack itself looks safe, we refuse the live snapshot
    if any movement / camera pan / transition is mid-flight (see
    ``_async_in_progress``), because that animating work is not serialized.
    """
    if game is None or not game.state:
        return False
    names = game.state.state_names()
    if not names:
        return False
    top = names[-1]
    if top not in CHECKPOINT_STATES and top not in LIVE_SNAPSHOT_TOP_STATES:
        return False
    if any(n in UNSAFE_LIVE_SNAPSHOT_STATES for n in names):
        return False
    return not _async_in_progress(game)


def _game_nid() -> str:
    return str(DB.constants.value('game_nid'))


def _force_loc(idx: int) -> str:
    """The location suffix passed to save.save_io (file becomes
    saves/<GAME_NID>-savestate-<idx>.p)."""
    return 'savestate-%d' % idx


def _save_loc(idx: int) -> str:
    return 'saves/%s-%s.p' % (_game_nid(), _force_loc(idx))


def _meta_loc(idx: int) -> str:
    return _save_loc(idx) + 'meta'


def get_slot(idx: int) -> save.SaveSlot:
    """A SaveSlot for display purposes (reads .pmeta if it exists)."""
    return save.SaveSlot(_meta_loc(idx), idx)


def slot_exists(idx: int) -> bool:
    return os.path.exists(_meta_loc(idx))


# ---------------------------------------------------------------------------
# Rolling pre-action checkpoint
# ---------------------------------------------------------------------------

def _refresh_checkpoint(game, cur) -> None:
    global _checkpoint
    try:
        s_dict, meta_dict = game.save()
        _checkpoint = (s_dict, meta_dict)
        logging.debug("Save-state checkpoint refreshed at '%s'", cur)
    except Exception:
        logging.exception("Failed to capture save-state checkpoint at '%s'", cur)


def _current_event_key(game):
    """A cheap, hashable identity for the current clean command boundary of the
    top-most running event: (event nid, command pointer, event stack depth)."""
    events_mgr = getattr(game, 'events', None)
    if not events_mgr or not events_mgr.all_events:
        return None
    ev = events_mgr.all_events[-1]
    proc = getattr(ev, 'processor', None)
    idx = getattr(proc, 'curr_cmd_idx', None)
    return (ev.nid, idx, len(events_mgr.all_events))


def capture_checkpoint(game) -> None:
    """Refresh the in-memory pre-action checkpoint.

    Called once per frame by the driver. There are two refresh triggers:

    1. Entering an idle, fully-serializable state (edge-triggered on the frame
       the current state *changes into* one of CHECKPOINT_STATES). Cheap.

    2. Reaching a new, *clean* command boundary while an event is running
       (top state is 'event', nothing async is mid-flight). This keeps the
       fallback checkpoint advancing through a cutscene -- so a save taken
       during movement / a camera pan / a transition lands on the most recent
       clean point *inside* the event, instead of snapping all the way back to
       the idle state from before the event began. Throttled so a burst of
       instantaneous commands cannot stutter.
    """
    global _last_state, _last_event_key, _last_event_refresh_time
    if game is None or not game.state:
        return
    cur = game.state.current()

    # Case 1: entered a new idle state -> refresh and reset the event tracking.
    if cur != _last_state:
        _last_state = cur
        if cur in CHECKPOINT_STATES:
            _refresh_checkpoint(game, cur)
            _last_event_key = None
            return

    # Case 2: running event, sitting at a clean (fully-serializable) boundary.
    if cur == 'event' and _can_live_snapshot(game):
        key = _current_event_key(game)
        if key is not None and key != _last_event_key:
            from app.engine import engine
            now = engine.get_time()
            if now - _last_event_refresh_time >= _EVENT_REFRESH_THROTTLE_MS:
                _last_event_key = key
                _last_event_refresh_time = now
                _refresh_checkpoint(game, cur)


def has_checkpoint() -> bool:
    return _checkpoint is not None


# ---------------------------------------------------------------------------
# Writing / reading the slot files
# ---------------------------------------------------------------------------

def _write(idx: int, s_dict, meta_dict, display_name: str) -> bool:
    """Synchronously writes a snapshot to its dedicated slot file.

    Synchronous (unlike save.suspend_game which threads) so a quick load right
    after a quick save can never race the write. ``force_loc`` makes save_io
    write only our file and skip all restart/preload bookkeeping.
    """
    try:
        meta_dict = dict(meta_dict)
        meta_dict['kind'] = KIND
        meta_dict['time'] = datetime.now()
        meta_dict['disp'] = display_name
        save.save_io(s_dict, meta_dict, None, None, force_loc=_force_loc(idx))
        logging.info("Saved save-state to %s", _save_loc(idx))
        return True
    except Exception:
        logging.exception("Failed to write save state (%d)", idx)
        return False


def _load(game, idx: int) -> bool:
    """Loads a save state inline. Works mid-combat / mid-event because the whole
    game is rebuilt; the running state stack is hard-reset first."""
    meta_loc = _meta_loc(idx)
    if not os.path.exists(meta_loc):
        logging.warning("No save state at %s", meta_loc)
        return False
    try:
        cur_slot = game.current_save_slot
        ss = save.SaveSlot(meta_loc, cur_slot)
        # Hard-reset the state machine BEFORE loading. load_game/build_new do not
        # clear the state stack and load() only appends, so without this the
        # currently-running event/combat/movement states would remain underneath
        # the restored ones and the load would appear to "do nothing" until they
        # finish. We empty the stack directly (rather than via clear() +
        # process_temp_state) to avoid running end()/finish() on a live combat or
        # event that may reference surfaces we are about to throw away.
        game.state.state = []
        game.state.temp_state = []
        save.load_game(game, ss)
        # Keep our own dedicated slot id; loading must not disturb the normal
        # save slot the player is actually using.
        game.current_save_slot = cur_slot
        logging.info("Loaded save-state from %s", _save_loc(idx))
        return True
    except Exception:
        logging.exception("Failed to load save state (%d)", idx)
        return False


# ---------------------------------------------------------------------------
# Public hotkey API
# ---------------------------------------------------------------------------

def quick_save(game, idx: int) -> str:
    """Quick save into slot ``idx`` (0-based).

    Prefers a *live* snapshot of the exact present moment whenever the state
    stack is fully reconstructable (an idle state, optionally with one or more
    running ``event`` states on top) -- this is what lets a save taken in the
    middle of an event be loaded right back into the middle of that event.

    Otherwise (combat, movement, menus, ...) it falls back to the most recent
    clean pre-action checkpoint, which behaves like the turnwheel.

    Returns 'saved' on success, or 'failed' on a bad index or if there is no
    snapshot available yet (e.g. on the title screen).
    """
    if not 0 <= idx < NUM_SLOTS:
        return 'failed'
    if game is None or not game.state or game.state.current() in (None, 'title_start'):
        return 'failed'
    # Take a live snapshot of the exact moment when the whole stack can be
    # rebuilt from the save dict (idle, or an event on top of idle states).
    _checkpoint_now = None
    if _can_live_snapshot(game):
        try:
            _checkpoint_now = game.save()
        except Exception:
            logging.exception("Live snapshot failed; falling back to last checkpoint")
            _checkpoint_now = None
    # Fall back to the rolling pre-action checkpoint for everything else (combat,
    # movement, menus) or if the live snapshot raised.
    if _checkpoint_now is None:
        _checkpoint_now = _checkpoint
    if not _checkpoint_now:
        logging.warning("No snapshot available to save yet")
        return 'failed'
    s_dict, meta_dict = _checkpoint_now
    return 'saved' if _write(idx, s_dict, meta_dict, "Quick Save") else 'failed'


def quick_load(game, idx: int) -> bool:
    """Load a quick save from slot ``idx`` (0-based). Works at any time."""
    if not 0 <= idx < NUM_SLOTS:
        return False
    if not slot_exists(idx):
        return False
    return _load(game, idx)
