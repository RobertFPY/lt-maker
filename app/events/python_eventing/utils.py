from typing import Any, Dict, List, Optional, Set, Tuple, Type

from .. import event_commands
    
EVENT_INSTANCE = "EC"

FORBIDDEN_PYTHON_COMMANDS: List[event_commands.EventCommand] = [event_commands.Comment, event_commands.If, event_commands.Elif, event_commands.Else,
                                                                event_commands.End, event_commands.For, event_commands.Endf, event_commands.LoopUnits]
FORBIDDEN_PYTHON_COMMAND_NIDS: List[str] = [cmd.nid for cmd in FORBIDDEN_PYTHON_COMMANDS] + [cmd.nickname for cmd in FORBIDDEN_PYTHON_COMMANDS]
SAVE_COMMANDS: List[event_commands.EventCommand] = [event_commands.BattleSave, event_commands.Prep, event_commands.Base]
SAVE_COMMAND_NIDS: Set[str] = set([cmd.nid for cmd in SAVE_COMMANDS] + [cmd.nickname for cmd in SAVE_COMMANDS])
EVENT_CALL_COMMANDS: List[event_commands.EventCommand] = [event_commands.TriggerScript, event_commands.TriggerScriptWithArgs]
EVENT_CALL_COMMAND_NIDS: Set[str] = set([cmd.nid for cmd in EVENT_CALL_COMMANDS] + [cmd.nickname for cmd in EVENT_CALL_COMMANDS])

DO_NOT_EXECUTE_SENTINEL = -1

class ResumeCheck():
    def __init__(self, line_no_to_catch: int) -> None:
        self.catching_up = True
        self.line_no = line_no_to_catch

    def check_set_caught_up(self, line_no):
        is_catching_up = self.catching_up
        if line_no == self.line_no:
            self.catching_up = False
        return is_catching_up