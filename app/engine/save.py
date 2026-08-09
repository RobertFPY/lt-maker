import os, shutil, glob, re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Tuple
import threading
import time

try:
    import cPickle as pickle
except ImportError:
    import pickle

from app.utilities import str_utils
from app.utilities.user_data import save_path
from app.data.database.database import DB

import app.engine.config as cf
from app.engine.objects.item import ItemObject
from app.engine.objects.skill import SkillObject

import logging

SAVE_THREAD = None
SAVE_IO_LOCK = threading.RLock()


def _record_profile(name: str, elapsed_ms: float) -> None:
    """Record optional load diagnostics without making save imports cyclic."""
    try:
        from app.engine.performance import RUNTIME_PROFILER
        RUNTIME_PROFILER.record(name, elapsed_ms)
    except ImportError:
        pass


def _read_save_data(save_loc: str) -> dict:
    """Read and unpickle a save with separate timings for the two costs."""
    read_started = time.perf_counter()
    with open(save_loc, 'rb') as fp:
        save_bytes = fp.read()
    _record_profile('save_load_read', (time.perf_counter() - read_started) * 1000.0)

    unpickle_started = time.perf_counter()
    save_data = pickle.loads(save_bytes)
    _record_profile('save_load_unpickle', (time.perf_counter() - unpickle_started) * 1000.0)
    return save_data


class SaveLoadError(RuntimeError):
    """A save job failed before it could atomically install the saved state."""


class SaveCompatibilityError(SaveLoadError):
    """A save cannot be restored without guessing authoritative state."""


class LoadDestination(str, Enum):
    """Authoritative destination published by a save-load transaction."""

    SAVED = 'saved'
    START_LEVEL = 'start_level'
    RESTART_LEVEL = 'restart_level'
    OVERWORLD = 'overworld'


@dataclass(frozen=True)
class LoadTransactionContext:
    """Immutable routing data for one authoritative load transaction.

    ``state_prefix`` contains already-live states that a reference-shaped
    caller keeps below the restored stack (notably Title Restart).  When
    ``preserve_existing_states`` is true, the transaction captures the active
    stack at entry instead. ``clear_existing_states`` ends a desktop caller's
    old stack only after file read succeeds. Android callers pass an explicit
    prefix so their opaque loader can never survive publication.
    """

    save_kind: Optional[str] = None
    save_slot: Optional[int] = None
    publish_save_slot: bool = False
    destination: LoadDestination = LoadDestination.SAVED
    clear_existing_states: bool = False
    preserve_existing_states: bool = True
    state_prefix: Tuple[object, ...] = ()
    level_nid: Optional[str] = None
    difficulty_mode_nid: Optional[str] = None

    @classmethod
    def for_slot(cls, save_slot: 'SaveSlot', **kwargs) -> 'LoadTransactionContext':
        return cls(
            save_kind=getattr(save_slot, 'kind', None),
            save_slot=getattr(save_slot, 'idx', None),
            publish_save_slot=True,
            **kwargs,
        )


@dataclass(frozen=True)
class _ValidatedControllerState:
    phase: Optional[Tuple[int, int]] = None
    initiative: Optional[Tuple[Tuple[str, ...], Tuple[float, ...], int]] = None


CONTROLLER_STATE_KEY = 'controller_state'


def _team_nid(team_idx: int) -> str:
    if (isinstance(team_idx, bool) or not isinstance(team_idx, int) or
            team_idx < 0 or team_idx >= len(DB.teams)):
        raise SaveLoadError('Phase controller contains an invalid team index')
    return DB.teams[team_idx].nid


def _capture_phase_state(game_state) -> dict:
    if game_state.phase is None:
        raise SaveLoadError('Cannot save phase compatibility without a phase controller')
    return {
        'current': _team_nid(game_state.phase.current),
        'previous': _team_nid(game_state.phase.previous),
    }


def capture_controller_compatibility(game_state, s_dict: dict, *, save_kind: str) -> None:
    """Attach only controller state required to resume this supported save.

    The ordinary non-initiative player-control payload remains byte-shape
    compatible with historical saves.  Chapter-start and overworld material
    are rebuilt/irrelevant respectively, so they intentionally carry no
    controller extension.
    """
    if not game_state.level or save_kind in ('start', 'overworld'):
        return

    if DB.constants.value('initiative'):
        tracker = game_state.initiative
        if tracker is None:
            raise SaveLoadError(
                'Cannot save initiative progress without an initiative tracker')
        s_dict[CONTROLLER_STATE_KEY] = {
            'phase': _capture_phase_state(game_state),
            'initiative': {
                'unit_line': list(tracker.unit_line),
                'initiative_line': list(tracker.initiative_line),
                'current_idx': tracker.current_idx,
            },
        }
        return

    player_idx = DB.teams.index('player')
    if game_state.phase and game_state.phase.current != player_idx:
        s_dict[CONTROLLER_STATE_KEY] = {
            'phase': _capture_phase_state(game_state),
        }


def _validate_phase_state(raw_phase) -> Tuple[int, int]:
    if not isinstance(raw_phase, dict):
        raise SaveCompatibilityError('Malformed phase compatibility state')
    current = raw_phase.get('current')
    previous = raw_phase.get('previous')
    if current not in DB.teams or previous not in DB.teams:
        raise SaveCompatibilityError(
            'Phase compatibility state references an unknown team')
    return DB.teams.index(current), DB.teams.index(previous)


def _validate_initiative_state(raw_initiative, s_dict: dict):
    if not isinstance(raw_initiative, dict):
        raise SaveCompatibilityError('Malformed initiative compatibility state')
    unit_line = raw_initiative.get('unit_line')
    initiative_line = raw_initiative.get('initiative_line')
    current_idx = raw_initiative.get('current_idx')
    if not isinstance(unit_line, list) or not isinstance(initiative_line, list):
        raise SaveCompatibilityError('Malformed initiative line data')
    if not unit_line or len(unit_line) != len(initiative_line):
        raise SaveCompatibilityError('Initiative lines must be nonempty and equal length')
    if len(set(unit_line)) != len(unit_line) or not all(
            isinstance(unit_nid, str) for unit_nid in unit_line):
        raise SaveCompatibilityError('Initiative unit line is invalid')
    saved_unit_nids = {
        unit_data.get('nid') for unit_data in s_dict.get('units', [])
        if isinstance(unit_data, dict)
    }
    unknown_units = [unit_nid for unit_nid in unit_line
                     if unit_nid not in saved_unit_nids]
    if unknown_units:
        raise SaveCompatibilityError(
            'Initiative state references unknown unit %s' % unknown_units[0])
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
               for value in initiative_line):
        raise SaveCompatibilityError('Initiative values must be numeric')
    if (isinstance(current_idx, bool) or not isinstance(current_idx, int) or
            current_idx < -1 or current_idx >= len(unit_line)):
        raise SaveCompatibilityError('Initiative current index is out of bounds')
    return tuple(unit_line), tuple(initiative_line), current_idx


def _validate_state_payload(s_dict: dict):
    state_data = s_dict.get('state')
    if (not isinstance(state_data, (list, tuple)) or len(state_data) != 2 or
            not isinstance(state_data[0], (list, tuple)) or
            not isinstance(state_data[1], (list, tuple))):
        raise SaveCompatibilityError('Malformed saved state-stack payload')
    return list(state_data[0]), list(state_data[1])


def _validate_controller_compatibility(
        s_dict: dict, context: LoadTransactionContext) -> _ValidatedControllerState:
    raw_controller = s_dict.get(CONTROLLER_STATE_KEY)
    if raw_controller is not None and not isinstance(raw_controller, dict):
        raise SaveCompatibilityError('Malformed controller compatibility state')

    phase_state = None
    initiative_state = None
    if raw_controller is not None:
        if 'phase' in raw_controller:
            phase_state = _validate_phase_state(raw_controller['phase'])
        if 'initiative' in raw_controller:
            initiative_state = _validate_initiative_state(
                raw_controller['initiative'], s_dict)

    rebuilds_chapter = context.destination in (
        LoadDestination.START_LEVEL, LoadDestination.RESTART_LEVEL)
    tactical_progress = bool(s_dict.get('level')) and not rebuilds_chapter and \
        context.destination != LoadDestination.OVERWORLD

    if DB.constants.value('initiative'):
        if tactical_progress and initiative_state is None:
            raise SaveCompatibilityError(
                'Legacy initiative progress has no exact tracker state')
        if initiative_state is not None and phase_state is None:
            raise SaveCompatibilityError(
                'Initiative compatibility state is missing phase state')
    elif initiative_state is not None:
        raise SaveCompatibilityError(
            'Initiative compatibility state conflicts with project settings')
    elif tactical_progress and phase_state is None and \
            context.save_kind == 'enemy_turn_change':
        if 'enemy' not in DB.teams or 'player' not in DB.teams:
            raise SaveCompatibilityError(
                'Legacy enemy turn-change save requires player and enemy teams')
        phase_state = DB.teams.index('enemy'), DB.teams.index('player')

    return _ValidatedControllerState(phase_state, initiative_state)


def _restore_controller_compatibility(
        game_state, compatibility: _ValidatedControllerState) -> None:
    if compatibility.initiative is not None:
        from app.engine.initiative import InitiativeTracker
        unit_line, initiative_line, current_idx = compatibility.initiative
        tracker = InitiativeTracker()
        tracker.unit_line = list(unit_line)
        tracker.initiative_line = list(initiative_line)
        tracker.current_idx = current_idx
        game_state.initiative = tracker
    if compatibility.phase is not None:
        if game_state.phase is None:
            raise SaveCompatibilityError(
                'Loaded world has no phase controller to restore')
        game_state.phase.current, game_state.phase.previous = compatibility.phase


def _validate_complete_world(game_state, s_dict: dict,
                             context: LoadTransactionContext) -> None:
    expects_level = bool(s_dict.get('level')) or context.destination in (
        LoadDestination.START_LEVEL, LoadDestination.RESTART_LEVEL)
    if expects_level:
        required = (
            'level', 'board', 'boundary', 'cursor', 'camera', 'map_view',
            'movement', 'phase', 'events', 'unit_registry', 'item_registry',
            'skill_registry', 'region_registry',
        )
        missing = [name for name in required if getattr(game_state, name, None) is None]
        if missing:
            raise SaveLoadError(
                'Loaded tactical world is incomplete: %s' % ', '.join(missing))
        board_fields = ('fog_of_war_grids', 'previously_visited_tiles', 'aura_grid')
        missing_board_fields = [name for name in board_fields
                                if not hasattr(game_state.board, name)]
        if missing_board_fields:
            raise SaveLoadError(
                'Loaded board is incomplete: %s' % ', '.join(missing_board_fields))
        if DB.constants.value('initiative') and game_state.initiative is None:
            raise SaveCompatibilityError(
                'Loaded initiative world has no initiative tracker')
    elif game_state.events is None or game_state.phase is None:
        raise SaveLoadError('Loaded non-tactical world is missing controllers')


def _destination_states(context: LoadTransactionContext) -> Tuple[str, ...]:
    if context.destination == LoadDestination.START_LEVEL:
        return ('start_level_asset_loading',)
    if context.destination == LoadDestination.OVERWORLD:
        return ('overworld',)
    return ()


def _record_restore_iter(game_state, s_dict: dict) -> None:
    phase_totals: Dict[str, float] = {}
    restore_iter = game_state.load_iter(s_dict, replace_state_machine=True)
    while True:
        started = time.perf_counter()
        try:
            phase = next(restore_iter)
        except StopIteration:
            break
        phase_totals[phase] = phase_totals.get(phase, 0.0) + \
            (time.perf_counter() - started) * 1000.0
    for phase, elapsed_ms in phase_totals.items():
        _record_profile('save_restore_' + phase, elapsed_ms)


def load_game_data(game_state, s_dict: dict, *,
                   context: Optional[LoadTransactionContext] = None) -> None:
    """Run one complete authoritative restore and publish its destination.

    All ``load_iter`` yields are drained inside this call.  The existing state
    machine remains authoritative until world/controller validation succeeds;
    then S/Q and the route destination are installed together exactly once.
    """
    context = context or LoadTransactionContext()
    previous_next_uids = ItemObject.next_uid, SkillObject.next_uid
    try:
        if not isinstance(context.destination, LoadDestination):
            raise SaveCompatibilityError('Unknown load destination')
        starting_states, temp_state = _validate_state_payload(s_dict)
        compatibility = _validate_controller_compatibility(s_dict, context)
        if context.difficulty_mode_nid is not None and \
                DB.difficulty_modes.get(context.difficulty_mode_nid) is None:
            raise SaveCompatibilityError('Unknown difficulty mode for restart')

        if context.clear_existing_states:
            # Desktop title/in-chapter routes historically end their current
            # states before hydration.  Keeping that operation inside the
            # transaction means a read/unpickle failure leaves them untouched.
            game_state.state.clear()
            game_state.state.process_temp_state()
        if context.preserve_existing_states:
            state_prefix = tuple(game_state.state.state)
        else:
            state_prefix = tuple(context.state_prefix)
        destination_states = _destination_states(context)
        state_data = (starting_states, temp_state)

        game_state.build_new()
        _record_restore_iter(game_state, s_dict)

        if context.destination in (
                LoadDestination.START_LEVEL, LoadDestination.RESTART_LEVEL):
            if context.difficulty_mode_nid is not None:
                from app.engine.objects.difficulty_mode import DifficultyModeObject
                game_state.current_mode = DifficultyModeObject.from_prefab(
                    DB.difficulty_modes.get(context.difficulty_mode_nid))
            level_nid = context.level_nid
            if level_nid is None:
                # Preserve the historical PrimitiveCounter lookup: a legacy
                # start/restart payload without this key resolves to level 0.
                level_nid = game_state.game_vars['_next_level_nid']
            if level_nid is None or DB.levels.get(str(level_nid)) is None:
                raise SaveCompatibilityError(
                    'Start/restart save has no valid destination level')
            chapter_start_state = (
                [state.name for state in state_prefix] + starting_states +
                list(destination_states),
                list(temp_state),
            )
            game_state.start_level(
                str(level_nid), chapter_start_state=chapter_start_state)
        elif context.destination != LoadDestination.OVERWORLD:
            _restore_controller_compatibility(game_state, compatibility)

        _validate_complete_world(game_state, s_dict, context)
        set_next_uids(game_state)
        if context.publish_save_slot:
            game_state.current_save_slot = context.save_slot
        game_state.install_state_machine(
            state_data,
            prefix_states=state_prefix,
            suffix_states=destination_states,
        )
    except Exception as exc:
        try:
            reset_failed_load(game_state)
        finally:
            # Item/skill restore constructors advance these process globals
            # before aura reconstruction can safely run.  They are part of
            # the transaction and must not leak when a later phase fails.
            ItemObject.next_uid, SkillObject.next_uid = previous_next_uids
        if isinstance(exc, SaveLoadError):
            raise
        raise SaveLoadError('Unable to restore save transaction') from exc


def reset_failed_load(game_state) -> None:
    """Discard every partial world field and establish a clean title session."""
    game_state.clear()
    # ``GameState.clear`` intentionally preserves several reusable controllers;
    # an initiative tracker is authoritative chapter progress, not reusable
    # title state.
    game_state.initiative = None
    prepare_for_load = getattr(game_state, 'prepare_for_load', None)
    if prepare_for_load:
        prepare_for_load()
    game_state.build_new()
    game_state.load_states(['title_start'])


class SaveLoadJob:
    """Read a save off-thread, then restore it in one main-thread transaction.

    Pickle deserialization does not touch pygame or the game singleton, so it
    remains worker-owned. Once those immutable bytes are ready, authoritative
    ``GameState`` hydration is drained synchronously; iterator phase names are
    retained for profiling only and never become frame boundaries.
    """

    def __init__(self, save_slot: 'SaveSlot', *,
                 context: Optional[LoadTransactionContext] = None) -> None:
        self.save_slot = save_slot
        self.context = context or LoadTransactionContext.for_slot(
            save_slot, preserve_existing_states=False)
        self.phase = 'waiting_to_read'
        self.error: Optional[BaseException] = None
        self._save_data: Optional[dict] = None
        self._thread: Optional[threading.Thread] = None
        self._read_finished = threading.Event()
        self._transaction_failed = False
        self.completed = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self.phase = 'reading'
        self._thread = threading.Thread(
            target=self._read_worker,
            name='save-load-reader',
            daemon=True,
        )
        self._thread.start()

    def _read_worker(self) -> None:
        try:
            self._save_data = _read_save_data(self.save_slot.save_loc)
        except BaseException as exc:  # Re-raised on the main thread with context.
            self.error = exc
        finally:
            self._read_finished.set()

    @property
    def is_reading(self) -> bool:
        return self._thread is not None and not self._read_finished.is_set()

    def advance(self, game_state, budget_ms: float = 8.0) -> bool:
        """Wait for worker I/O, then complete hydration without yielding a frame."""
        if self.completed:
            return True
        if self._thread is None:
            self.start()
        if not self._read_finished.is_set():
            return False
        if self.error:
            raise SaveLoadError('Unable to read save %s' % self.save_slot.save_loc) from self.error
        if self._save_data is None:
            raise SaveLoadError('Save reader completed without returning data')

        self.phase = 'restore'
        started = time.perf_counter()
        try:
            load_game_data(game_state, self._save_data, context=self.context)
        except Exception:
            self._save_data = None
            self.phase = 'failed'
            self._transaction_failed = True
            raise
        _record_profile(
            'save_restore_transaction',
            (time.perf_counter() - started) * 1000.0,
        )
        self._save_data = None
        self.completed = True
        self.phase = 'complete'
        return True

    def abort(self, game_state) -> None:
        """Return the singleton to a clean game, never a half-restored save."""
        self._save_data = None
        self.completed = False
        if not self._transaction_failed:
            reset_failed_load(game_state)
        self._transaction_failed = False

def GAME_NID():
    return str(DB.constants.value('game_nid'))

def _save_location(filename):
    return os.fspath(save_path(filename))

SUSPEND_LOC = _save_location(GAME_NID() + '-suspend.pmeta')

class SaveSlot():
    no_name = '--NO DATA--'

    def __init__(self, metadata_fn, idx):
        self.name = self.no_name
        self.playtime = 0
        self.realtime = 0
        self.kind = None  # Prep, Base, Suspend, Battle, Start
        self.mode = None
        self.idx = idx
        self.display_name = None

        self.meta_loc = metadata_fn
        self.save_loc = metadata_fn[:-4]

        self.read()

    def read(self):
        if os.path.exists(self.meta_loc):
            with open(self.meta_loc, 'rb') as fp:
                save_metadata = pickle.load(fp)
            self.name = save_metadata['level_title']
            self.playtime = save_metadata['playtime']
            realtime = save_metadata.get('realtime')
            # Old or interrupted saves can contain a null timestamp. Save
            # menus compare timestamps to select the newest slot, so keep
            # malformed legacy metadata sortable instead of crashing.
            self.realtime = realtime if isinstance(realtime, (int, float)) else 0
            self.kind = save_metadata['kind']
            self.mode = save_metadata.get('mode')
            self.display_name = save_metadata.get('disp')

    def get_name(self):
        if self.display_name:
            return self.display_name
        elif self.kind == 'turn_change':
            turn = int(re.findall(r'\d+', self.meta_loc)[-1])
            return self.name + (' - Turn %d' % turn)
        elif self.kind and cf.SETTINGS['debug']:
            return self.name + ' - ' + self.kind
        else:
            return self.name

    def __repr__(self):
        return '%d: %s' % (self.idx, self.get_name())

def dict_print(d):
    for k, v in d.items():
        if isinstance(v, dict):
            dict_print(v)
        else:
            s = "{0} : {1} ({2})".format(k, v, type(v))
            print(s)
            logging.error(s)

def _save_io(s_dict, meta_dict, old_slot, slot, force_loc=None, name=None):
    io_started = time.perf_counter()
    # Pickling is CPU/GIL heavy.  Serializing save jobs prevents two phase
    # changes from competing with the render loop at the same time.
    with SAVE_IO_LOCK:
        if name:
            save_loc = _save_location(name + '.p')
        elif force_loc:
            save_loc = _save_location(GAME_NID() + '-' + force_loc + '.p')
        elif slot is not None:
            save_loc = _save_location(GAME_NID() + '-' + str(slot) + '.p')
        meta_loc = save_loc + 'meta'

        logging.info("Saving to %s", save_loc)

        with open(save_loc, 'wb') as fp:
            try:
                pickle.dump(s_dict, fp, protocol=pickle.HIGHEST_PROTOCOL)
            except TypeError as e:
                # There's a surface somewhere in the dictionary of things to save...
                logging.error(e)
                dict_print(s_dict)
                print(e)
                for k, v in s_dict.items():
                    try:
                        pickle.dumps(v)
                    except TypeError as e2:
                        logging.error(e2)
                        print(e2)
                        logging.error("The offending object is in %s" % k)
                        print("The offending object is in %s" % k)
                        logging.error(v)
                        print(v)

        with open(meta_loc, 'wb') as fp:
            pickle.dump(meta_dict, fp, protocol=pickle.HIGHEST_PROTOCOL)

    # For restart
    if not force_loc:
        r_save = _save_location(GAME_NID() + '-restart' + str(slot) + '.p')
        r_save_meta = r_save + 'meta'
        # The restart save lets "Restart Level" replay this slot's chapter from
        # the start. Pick which save becomes that restart point, then copy it once.
        old_restart = old_restart_meta = None
        if old_slot is not None:
            old_restart = _save_location(GAME_NID() + '-restart' + str(old_slot) + '.p')
            old_restart_meta = old_restart + 'meta'

        if meta_dict['kind'] == 'start':
            # Start of a map is itself the restart point.
            restart_src, restart_src_meta = save_loc, meta_loc
        elif old_restart and os.path.exists(old_restart):
            # Carry the restart point forward from the slot we loaded from.
            restart_src, restart_src_meta = old_restart, old_restart_meta
        elif not os.path.exists(r_save):
            # Nothing to carry forward (e.g. started via Test Chapter, so
            # current_save_slot was None and no 'start' save was ever made).
            # Fall back to the current save so Restart Level still works.
            # NOTE: this seeds the restart point from this first save, not a
            # pristine chapter start, so Restart Level replays from here rather
            # than the true beginning. Only matters for the dev Test Chapter
            # path; normal play always seeds restart from the new-game 'start'.
            restart_src, restart_src_meta = save_loc, meta_loc
        else:
            # Keep this slot's existing restart point untouched.
            restart_src = restart_src_meta = None

        if restart_src and restart_src != r_save:
            shutil.copy(restart_src, r_save)
            shutil.copy(restart_src_meta, r_save_meta)

    # For preload
    if meta_dict['kind'] == 'start':
        preload_saves = glob.glob(_save_location(GAME_NID() + '-preload-' + str(meta_dict['level_nid']) + '-*.p'))
        nids = [p.split('-')[-1][:-2] for p in preload_saves]
        unique_nid = str(str_utils.get_next_int('0', nids))
        preload_save = _save_location(GAME_NID() + '-preload-' + str(meta_dict['level_nid']) + '-' + unique_nid + '.p')
        preload_save_meta = _save_location(GAME_NID() + '-preload-' + str(meta_dict['level_nid']) + '-' + unique_nid + '.pmeta')

        shutil.copy(save_loc, preload_save)
        shutil.copy(meta_loc, preload_save_meta)

    try:
        from app.engine.performance import RUNTIME_PROFILER
        RUNTIME_PROFILER.record('save_io', (time.perf_counter() - io_started) * 1000.0)
    except ImportError:
        pass


def save_io(s_dict, meta_dict, old_slot, slot, force_loc=None, name=None):
    """Serialize complete save jobs so Android never pickles two saves at once."""
    with SAVE_IO_LOCK:
        return _save_io(s_dict, meta_dict, old_slot, slot, force_loc, name)

def suspend_game(game_state, kind, slot: int = None, name=None, display_name=None):
    """
    Saves game state to file
    """
    logging.debug("Suspending game...")
    snapshot_started = time.perf_counter()
    s_dict, meta_dict = game_state.save()
    capture_controller_compatibility(game_state, s_dict, save_kind=kind)
    try:
        from app.engine.performance import RUNTIME_PROFILER
        RUNTIME_PROFILER.record('save_snapshot', (time.perf_counter() - snapshot_started) * 1000.0)
    except ImportError:
        pass
    logging.debug("Suspend state: %s", game_state.state.state_names())
    logging.debug("Suspend temp state: %s", game_state.state.temp_state)
    meta_dict['kind'] = kind
    meta_dict['time'] = datetime.now()
    meta_dict['disp'] = display_name
    old_save_slot = game_state.current_save_slot
    if slot is not None:
        game_state.current_save_slot = slot  # Where we are saving it to, so we can get it back later

    if kind == 'suspend':
        force_loc = 'suspend'
    else:
        force_loc = None

    global SAVE_THREAD
    SAVE_THREAD = threading.Thread(target=save_io, args=(s_dict, meta_dict, old_save_slot, slot, force_loc, name))
    SAVE_THREAD.start()

def load_game(game_state, save_slot: SaveSlot, *,
              context: Optional[LoadTransactionContext] = None):
    """
    Read a save and synchronously run the canonical load transaction.
    """
    save_loc = save_slot.save_loc
    logging.info("Loading from %s", save_loc)
    s_dict = _read_save_data(save_loc)
    context = context or LoadTransactionContext.for_slot(save_slot)
    load_game_data(game_state, s_dict, context=context)

def set_next_uids(game_state):
    if game_state.item_registry:
        ItemObject.next_uid = max(game_state.item_registry.keys()) + 1
    else:
        ItemObject.next_uid = 100
    if game_state.skill_registry:
        SkillObject.next_uid = max(game_state.skill_registry.keys()) + 1
    else:
        SkillObject.next_uid = 100
    logging.info("Setting next item uid: %d" % ItemObject.next_uid)
    logging.info("Setting next skill uid: %d" % SkillObject.next_uid)

def load_saves():
    save_slots = []
    for num in range(0, int(DB.constants.value('num_save_slots'))):
        meta_fp = _save_location(GAME_NID() + '-' + str(num) + '.pmeta')
        ss = SaveSlot(meta_fp, num)
        save_slots.append(ss)
    return save_slots

def load_restarts():
    save_slots = []
    for num in range(0, int(DB.constants.value('num_save_slots'))):
        meta_fp = _save_location(GAME_NID() + '-restart' + str(num) + '.pmeta')
        ss = SaveSlot(meta_fp, num)
        save_slots.append(ss)
    return save_slots

def get_all_saves():
    """
    Grabs all the turn_change saves
    """
    save_slots = []
    name = _save_location(GAME_NID() + '-turn_change-*-*.pmeta')
    for meta_fn in glob.glob(name):
        ss = SaveSlot(meta_fn, 0)
        save_slots.append(ss)
    save_slots = sorted(save_slots, key=lambda x: x.realtime, reverse=True)
    return save_slots

def remove_suspend():
    if not cf.SETTINGS['debug'] and os.path.exists(SUSPEND_LOC):
        os.remove(SUSPEND_LOC)

def delete_suspend():
    if os.path.exists(SUSPEND_LOC):
        os.remove(SUSPEND_LOC)

def delete_save(game_state, num: Optional[int] = None):
    """
    If num is not provided, deletes current save
    """
    if game_state.current_save_slot is not None:
        num = game_state.current_save_slot
    if num is None:
        logging.error("delete_save: num not provided and no current save slot")
        return
    meta_fn = _save_location(GAME_NID() + '-' + str(num) + '.pmeta')
    save_fn = _save_location(GAME_NID() + '-' + str(num) + '.p')
    r_save_fn = _save_location(GAME_NID() + '-restart' + str(num) + '.p')
    if os.path.exists(meta_fn):
        os.remove(meta_fn)
    if os.path.exists(save_fn):
        os.remove(save_fn)
    if os.path.exists(r_save_fn):
        os.remove(r_save_fn)

def get_save_title(save_slots):
    options = [save_slot.get_name() for save_slot in save_slots]
    colors = [DB.difficulty_modes.get(save_slot.mode).color if (save_slot.mode and DB.difficulty_modes.get(save_slot.mode)) else 'green' for save_slot in save_slots]
    return options, colors

def check_save_slots():
    global SAVE_SLOTS, RESTART_SLOTS
    SAVE_SLOTS = load_saves()
    RESTART_SLOTS = load_restarts()

SAVE_SLOTS = load_saves()
RESTART_SLOTS = load_restarts()
