import ast
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Type

from app.events.event_structs import EventCommandTokens
from app.utilities.str_utils import SHIFT_NEWLINE

from .. import event_commands

EVENT_INSTANCE = "EC"
EVENT_GEN_NAME = "_lt_event_gen"

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

def to_py_event_command(tokens: EventCommandTokens) -> Tuple[str, int]:
    """returns command text, and indent"""
    command = tokens.command()
    args = ','.join(tokens.args()).replace(SHIFT_NEWLINE, ' ')
    # flags are always strings
    flags = ','.join([f'"{flag}"' for flag in tokens.flags()])
    return "%s(%s).set_flags(%s)" % (command, args, flags), tokens.start_idx

def event_command_from_pyev_tokens(tokens: EventCommandTokens) -> Optional[event_commands.EventCommand]:
    """Best-effort reconstruction of an EventCommand from a parsed pyev command line.

    Used by the event inspector so searches like find_all_calls_of_command also cover
    Python-style ($-prefixed) event scripts, which are otherwise opaque to it. Positional
    args are mapped onto the command's keywords; string literals are unquoted via
    ast.literal_eval, while anything dynamic (variables, f-strings, expressions, tuples)
    is left as its raw source text so the command type is at least discoverable.
    Returns None if the leading token isn't a known event command.
    """
    command_t = event_commands.ALL_EVENT_COMMANDS.get(tokens.command())
    if not command_t:
        return None
    keywords = command_t.keywords + command_t.optional_keywords
    parameters: Dict[str, str] = {}
    for idx, arg in enumerate(tokens.args()):
        if idx >= len(keywords):
            break
        arg = arg.strip()
        try:
            value = ast.literal_eval(arg)
        except (ValueError, SyntaxError):
            value = arg
        # Keep parameters as strings, matching classic (non-python) event parameters;
        # non-string literals are preserved as their raw source instead.
        parameters[keywords[idx]] = value if isinstance(value, str) else arg
    return command_t(parameters=parameters)

def create_null_event() -> Generator:
    yield DO_NOT_EXECUTE_SENTINEL, None
