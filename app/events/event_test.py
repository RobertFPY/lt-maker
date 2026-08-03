from __future__ import annotations

from typing import Optional

from app.engine import engine
from app.engine.game_state import GameState
from app.engine.state import MapState
from app.events import event_commands, triggers
from app.events.event import Event
from app.events.event_prefab import EventPrefab
from app.events.event_version import EventVersion
from app.events.mock_event import (
    IfStatementStrategy,
    MockEventProcessor,
    MockPythonEventProcessor,
)
from app.events.python_eventing.utils import SAVE_COMMAND_NIDS


def build_event_test_trigger(
        game: GameState,
        unit_nid=None,
        unit2_nid=None) -> triggers.GenericTrigger:
    unit = game.get_unit(unit_nid) if unit_nid else None
    unit2 = game.get_unit(unit2_nid) if unit2_nid else None
    if unit_nid and not unit:
        raise ValueError(
            "Event Test could not find unit %s in the loaded level."
            % unit_nid)
    if unit2_nid and not unit2:
        raise ValueError(
            "Event Test could not find unit2 %s in the loaded level."
            % unit2_nid)
    position = unit.position if unit else unit2.position if unit2 else None
    return triggers.GenericTrigger(unit, unit2, position)


class EventTestExitState(MapState):
    """Map-backed sentinel that closes an editor Event Test cleanly.

    The regular ``free`` state is not an inert background: once the preview
    event is popped it starts turn-begin hooks, auto-end-turn, AI, and upkeep.
    Event Test only needs a map underneath the transparent Event state, so this
    sentinel draws that map and requests a clean quit as soon as the preview
    event has completed.
    """

    name = "event_test_exit"

    def begin(self):
        engine.fast_quit = True



class EventTestEvent(Event):
    """Editor event preview that runs against a real level and game state.

    Commands before the editor caret are fast-forwarded to reconstruct the
    level, unit, portrait, variable, and inventory state. The selected command
    and everything after it then run normally through the regular Event state.
    """

    _FAST_FORWARD_IGNORED_COMMANDS = frozenset(SAVE_COMMAND_NIDS | {"finish"})
    _MAX_QUEUED_COMMANDS = 10_000
    _MAX_UPDATES = 10_000
    is_editor_event_test = True

    def __init__(
            self,
            event_prefab: EventPrefab,
            game: GameState,
            command_idx: int = 0,
            if_statement_strategy: Optional[IfStatementStrategy] = None,
            trigger: Optional[triggers.EventTrigger] = None):
        super().__init__(event_prefab, trigger or triggers.GenericTrigger(), game)

        strategy = if_statement_strategy or IfStatementStrategy.ALWAYS_TRUE
        if event_prefab.version() != EventVersion.EVENT:
            self.processor = MockPythonEventProcessor(
                event_prefab.nid,
                event_prefab.source,
                game,
                command_idx,
                self._fast_forward_command,
                context=self.local_args,
            )
        else:
            self.processor = MockEventProcessor(
                event_prefab.nid,
                event_prefab.source,
                self.text_evaluator,
                strategy,
                command_idx,
                self._fast_forward_command,
            )

    def _fast_forward_command(
            self, command: event_commands.EventCommand) -> None:
        """Apply one command before the caret without replaying presentation.

        Save/prep/base and finish are deliberately not replayed while catching
        up: they leave the event preview or write editor test data to disk.
        They still work normally when they are at or after the selected line.
        """
        if command.nid in self._FAST_FORWARD_IGNORED_COMMANDS:
            return

        previous_skip = self.do_skip
        previous_super_skip = self.super_skip
        previous_temp_state_length = len(self.game.state.temp_state)
        self.do_skip = True
        self.super_skip = True
        try:
            if command.nid not in self.skippable:
                self.run_command(command)

            # Macro and multi-* commands may expand into real commands. Drain
            # them now so later setup commands see the resulting state.
            queued_count = 0
            while self.command_queue:
                queued_count += 1
                if queued_count > self._MAX_QUEUED_COMMANDS:
                    raise RuntimeError(
                        "Event Test generated too many commands while "
                        "fast-forwarding to the selected line.")
                queued_command = self.command_queue.pop(0)
                if (queued_command.nid not in self.skippable and
                        queued_command.nid not in
                        self._FAST_FORWARD_IGNORED_COMMANDS):
                    self.run_command(queued_command)

            # Movement and other asynchronous setup should finish immediately
            # in skip mode before the next prior command is reconstructed.
            update_count = 0
            while self.should_update:
                update_count += 1
                if update_count > self._MAX_UPDATES:
                    raise RuntimeError(
                        "Event Test could not finish a skipped command while "
                        "fast-forwarding to the selected line.")
                self.should_update = {
                    name: to_update
                    for name, to_update in self.should_update.items()
                    if not to_update(True)
                }
        finally:
            # Catch-up commands may request menus/combat/state transitions.
            # Keep their data mutations, but do not leave the map preview
            # before execution reaches the selected command.
            del self.game.state.temp_state[previous_temp_state_length:]
            self.do_skip = previous_skip
            self.super_skip = previous_super_skip
            self.state = "processing"
            self.wait_time = 0
            self.transition_state = None
            self.text_boxes.clear()
            self.should_remain_blocked.clear()
