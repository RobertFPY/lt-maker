"""
GBA-emulator style "save state" system for lt-maker.

This is a SEPARATE layer on top of the existing save/suspend system. It does NOT
touch the normal save slots, suspend file, restart files, preload files or the
turnwheel. It writes to its own dedicated files so that nothing about the
vanilla save behavior changes.

It provides three flavors of save state, all sharing the same machinery:
  * Quick save / quick load  -> an automatic ring buffer (NUM_AUTO_SLOTS)
  * Auto snapshots           -> same ring buffer, taken at player phase start
  * Manual slots             -> NUM_MANUAL_SLOTS hand-picked slots (like 1-9)

Saving reuses ``save.save_io`` with an explicit ``force_loc`` so that the
restart/preload side effects in ``save_io`` are skipped entirely. Loading reuses
``save.load_game`` (build_new + load), which restores the entire game state,
including the state machine, so a save state can be restored inline mid-battle.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime

from app.data.database.database import DB
from app.engine import save

NUM_AUTO_SLOTS = 3
NUM_MANUAL_SLOTS = 9

# The kind tag stored in the metadata of a save state.
KIND = 'savestate'

# States during which it is safe to snapshot the whole game state.
# Outside of these, the game can hold pygame Surfaces / live combat / animation
# objects that cannot be pickled, so quick/auto saving must be blocked.
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
    'save_state_menu',
}


def _game_nid() -> str:
    return str(DB.constants.value('game_nid'))


def _force_loc(kind: str, idx: int) -> str:
    """The location suffix passed to save.save_io (file becomes
    saves/<GAME_NID>-<force_loc>.p)."""
    return 'savestate-%s-%d' % (kind, idx)


def _save_loc(kind: str, idx: int) -> str:
    return 'saves/%s-%s.p' % (_game_nid(), _force_loc(kind, idx))


def _meta_loc(kind: str, idx: int) -> str:
    return _save_loc(kind, idx) + 'meta'


def is_save_state_allowed(game) -> tuple[bool, str]:
    """Returns (allowed, reason). Snapshotting is only safe in a known-stable
    state, otherwise a Surface / live combat object could break pickling."""
    if game is None or not game.state:
        return False, "No active game"
    current = game.state.current()
    if current not in SAFE_STATES:
        return False, "Can't save state right now"
    return True, ""


def _write(game, kind: str, idx: int, display_name: str) -> bool:
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
        save.save_io(s_dict, meta_dict, None, None, force_loc=_force_loc(kind, idx))
        logging.info("Saved save-state to %s", _save_loc(kind, idx))
        return True
    except Exception as e:
        logging.exception("Failed to write save state (%s-%d): %s", kind, idx, e)
        return False


def _load(game, kind: str, idx: int) -> bool:
    """Loads a save state inline. Preserves the current main save slot id."""
    meta_loc = _meta_loc(kind, idx)
    if not os.path.exists(meta_loc):
        logging.warning("No save state at %s", meta_loc)
        return False
    try:
        # Preserve which real save slot we belong to so the normal save system
        # is unaffected by loading a save state.
        cur_slot = game.current_save_slot
        ss = save.SaveSlot(meta_loc, cur_slot)
        save.load_game(game, ss)
        logging.info("Loaded save-state from %s", _save_loc(kind, idx))
        return True
    except Exception as e:
        logging.exception("Failed to load save state (%s-%d): %s", kind, idx, e)
        return False


def get_slot(kind: str, idx: int) -> save.SaveSlot:
    """A SaveSlot for display purposes (reads .pmeta if it exists)."""
    return save.SaveSlot(_meta_loc(kind, idx), idx)


def slot_exists(kind: str, idx: int) -> bool:
    return os.path.exists(_meta_loc(kind, idx))


# ---------------------------------------------------------------------------
# Auto / quick (ring buffer)
# ---------------------------------------------------------------------------

def _auto_realtime(idx: int) -> float:
    ss = get_slot('auto', idx)
    return ss.realtime if slot_exists('auto', idx) else 0.0


def _next_auto_idx() -> int:
    """The ring-buffer slot to overwrite next: an empty slot if any, else the
    oldest one."""
    for idx in range(NUM_AUTO_SLOTS):
        if not slot_exists('auto', idx):
            return idx
    # All full: overwrite the oldest by realtime.
    return min(range(NUM_AUTO_SLOTS), key=_auto_realtime)


def latest_auto_idx() -> int | None:
    """The most recent populated auto slot, or None if there are none."""
    populated = [idx for idx in range(NUM_AUTO_SLOTS) if slot_exists('auto', idx)]
    if not populated:
        return None
    return max(populated, key=_auto_realtime)


def auto_save(game, display_name: str = "Auto Save") -> bool:
    """Take an automatic snapshot into the next ring-buffer slot. Silently
    skips if the current state isn't safe."""
    allowed, _ = is_save_state_allowed(game)
    if not allowed:
        return False
    return _write(game, 'auto', _next_auto_idx(), display_name)


def quick_save(game) -> bool:
    """Player-triggered quick save into the ring buffer."""
    return auto_save(game, display_name="Quick Save")


def quick_load(game) -> bool:
    """Load the most recent ring-buffer save state."""
    idx = latest_auto_idx()
    if idx is None:
        return False
    return _load(game, 'auto', idx)


def has_quick_save() -> bool:
    return latest_auto_idx() is not None


def list_auto_slots() -> list[save.SaveSlot]:
    return [get_slot('auto', idx) for idx in range(NUM_AUTO_SLOTS)]


# ---------------------------------------------------------------------------
# Manual slots
# ---------------------------------------------------------------------------

def save_to_manual(game, idx: int, display_name: str | None = None) -> bool:
    if not 0 <= idx < NUM_MANUAL_SLOTS:
        return False
    # display_name left as None so the slot list shows the level title.
    return _write(game, 'manual', idx, display_name)


def load_from_manual(game, idx: int) -> bool:
    if not 0 <= idx < NUM_MANUAL_SLOTS:
        return False
    return _load(game, 'manual', idx)


def list_manual_slots() -> list[save.SaveSlot]:
    return [get_slot('manual', idx) for idx in range(NUM_MANUAL_SLOTS)]
