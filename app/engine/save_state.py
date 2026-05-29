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

Saving reuses ``save.save_io`` with an explicit ``force_loc`` so that the
restart/preload side effects in ``save_io`` are skipped entirely. Loading reuses
``save.load_game`` (build_new + load), which restores the entire game state,
including the state machine, so a save state can be restored inline at any time,
even in the middle of combat or an event (the current state is fully discarded).

Deferred snapshots
------------------
Loading can happen at any moment because it rebuilds the whole game. Saving,
however, requires a picklable game state -- in the middle of combat or an event
the game holds live pygame Surfaces / animation objects that cannot be pickled.

To still let the player "save anytime", a quick save requested while the game is
in an unsafe state is *deferred*: the requested slot is remembered and the
snapshot is taken automatically at the next safe boundary (e.g. as soon as the
combat or event finishes and control returns to a stable state). The driver
calls :func:`flush_pending` once per frame to perform any deferred snapshot.
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

# States during which it is safe to snapshot the whole game state.
# Outside of these, the game can hold pygame Surfaces / live combat / animation
# objects that cannot be pickled, so an immediate snapshot must be deferred.
SAFE_STATES = {
    'free',
    'option_menu',
    'option_child',
    'menu',
    'move',
    'turn_change',
    'phase_change',
    'prep_main',
    'prep_formation',
    'prep_formation_select',
    'prep_items',
    'prep_market',
    'prep_manage',
    'prep_pick_units',
    'base_main',
    'objective_menu',
    'unit_menu',
    'overworld',
}

# Slot index (0-based) whose snapshot has been deferred until a safe boundary,
# or None if there is nothing pending.
_pending_save_idx: int | None = None


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


def is_save_state_allowed(game) -> bool:
    """Whether the whole game state can be safely pickled right now. Outside of a
    known-stable state a Surface / live combat object could break pickling."""
    if game is None or not game.state:
        return False
    return game.state.current() in SAFE_STATES


def get_slot(idx: int) -> save.SaveSlot:
    """A SaveSlot for display purposes (reads .pmeta if it exists)."""
    return save.SaveSlot(_meta_loc(idx), idx)


def slot_exists(idx: int) -> bool:
    return os.path.exists(_meta_loc(idx))


def _write(game, idx: int, display_name: str) -> bool:
    """Synchronously writes a save state to its dedicated file.

    Synchronous (unlike save.suspend_game which threads) so that an immediate
    quick load right after a quick save can never race the write. Uses
    force_loc so that save_io skips the restart/preload bookkeeping.
    """
    try:
        s_dict, meta_dict = game.save()
        meta_dict['kind'] = KIND
        meta_dict['time'] = datetime.now()
        meta_dict['disp'] = display_name
        # old_slot/slot = None and force_loc set -> save_io writes only our file
        # and performs no restart/preload copying.
        save.save_io(s_dict, meta_dict, None, None, force_loc=_force_loc(idx))
        logging.info("Saved save-state to %s", _save_loc(idx))
        return True
    except Exception as e:
        logging.exception("Failed to write save state (%d): %s", idx, e)
        return False


def _load(game, idx: int) -> bool:
    """Loads a save state inline. Preserves the current main save slot id."""
    meta_loc = _meta_loc(idx)
    if not os.path.exists(meta_loc):
        logging.warning("No save state at %s", meta_loc)
        return False
    try:
        # Preserve which real save slot we belong to so the normal save system
        # is unaffected by loading a save state.
        cur_slot = game.current_save_slot
        ss = save.SaveSlot(meta_loc, cur_slot)
        save.load_game(game, ss)
        logging.info("Loaded save-state from %s", _save_loc(idx))
        return True
    except Exception as e:
        logging.exception("Failed to load save state (%d): %s", idx, e)
        return False


# ---------------------------------------------------------------------------
# Public hotkey API
# ---------------------------------------------------------------------------

def quick_save(game, idx: int) -> str:
    """Request a quick save into ``idx`` (0-based).

    Returns one of:
      * 'saved'    -> snapshot was written immediately
      * 'deferred' -> game is in an unsafe state; the snapshot will be taken at
                      the next safe boundary via flush_pending()
      * 'failed'   -> bad index or the write itself failed
    """
    global _pending_save_idx
    if not 0 <= idx < NUM_SLOTS:
        return 'failed'
    if game is None or not game.state or game.state.current() in (None, 'title_start'):
        return 'failed'
    if is_save_state_allowed(game):
        ok = _write(game, idx, "Quick Save")
        return 'saved' if ok else 'failed'
    # Unsafe state (combat, event, animation, ...): defer to the next boundary.
    _pending_save_idx = idx
    logging.info("Deferring save state for slot %d until a safe boundary", idx)
    return 'deferred'


def quick_load(game, idx: int) -> bool:
    """Load a quick save from ``idx`` (0-based). Works at any time because the
    entire game state is rebuilt from the file."""
    global _pending_save_idx
    if not 0 <= idx < NUM_SLOTS:
        return False
    if not slot_exists(idx):
        return False
    # A pending save is meaningless once we jump to a different snapshot.
    _pending_save_idx = None
    return _load(game, idx)


def has_pending_save() -> bool:
    return _pending_save_idx is not None


def pending_slot() -> int | None:
    return _pending_save_idx


def cancel_pending() -> None:
    global _pending_save_idx
    _pending_save_idx = None


def flush_pending(game) -> int | None:
    """If a save was deferred and the game has reached a safe state, write it now.

    Called once per frame by the driver. Returns the (0-based) slot index that
    was just written, or None if nothing happened.
    """
    global _pending_save_idx
    if _pending_save_idx is None:
        return None
    if not is_save_state_allowed(game):
        return None
    idx = _pending_save_idx
    _pending_save_idx = None
    if _write(game, idx, "Quick Save"):
        return idx
    return None
