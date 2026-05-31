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

Saving (pre-action checkpoint, turnwheel-like)
----------------------------------------------
The game can only be pickled in a stable state: in the middle of combat / an
event / movement it holds live pygame Surfaces and animation objects that
cannot be pickled, and the unit's position has already been mutated toward its
destination. Trying to snapshot "right now" therefore either crashes or records
a half-applied action (unit already at the target tile, combat half-resolved).

Instead we continuously keep an in-memory snapshot of the most recent *idle*
("pre-action") state -- the map free state, prep/base menus, the overworld, and
phase boundaries. ``capture_checkpoint`` refreshes this snapshot every time the
game enters one of those idle states. A quick save then writes that checkpoint.

The result behaves like the turnwheel: a save always lands on the clean moment
*before* the current action, so loading puts a unit back on its original tile
and never restores a broken mid-combat frame.
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

def capture_checkpoint(game) -> None:
    """Refresh the in-memory pre-action checkpoint when entering an idle state.

    Called once per frame by the driver. Cheap: it only serializes the game on
    the frame the current state *changes into* one of CHECKPOINT_STATES, not on
    every frame spent there.
    """
    global _checkpoint, _last_state
    if game is None or not game.state:
        return
    cur = game.state.current()
    if cur == _last_state:
        return
    _last_state = cur
    if cur not in CHECKPOINT_STATES:
        return
    try:
        s_dict, meta_dict = game.save()
        _checkpoint = (s_dict, meta_dict)
        logging.debug("Save-state checkpoint refreshed at '%s'", cur)
    except Exception:
        logging.exception("Failed to capture save-state checkpoint at '%s'", cur)


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

    Writes the most recent clean pre-action checkpoint. If the game is currently
    in an idle state we refresh the checkpoint first so saving while idle records
    exactly the present moment.

    Returns 'saved' on success, or 'failed' on a bad index or if there is no
    checkpoint yet (e.g. on the title screen).
    """
    if not 0 <= idx < NUM_SLOTS:
        return 'failed'
    if game is None or not game.state or game.state.current() in (None, 'title_start'):
        return 'failed'
    # If we are idle right now, make the checkpoint reflect this exact moment.
    if game.state.current() in CHECKPOINT_STATES:
        try:
            _checkpoint_now = game.save()
        except Exception:
            logging.exception("Live checkpoint failed; falling back to last checkpoint")
            _checkpoint_now = _checkpoint
    else:
        _checkpoint_now = _checkpoint
    if not _checkpoint_now:
        logging.warning("No pre-action checkpoint available to save yet")
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