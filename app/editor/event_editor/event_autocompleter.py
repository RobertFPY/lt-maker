from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import List, Optional, Tuple, Type

from PyQt5.QtCore import QStringListModel, Qt, pyqtSignal
from PyQt5.QtWidgets import QCompleter

from app.data.database.database import DB, Database
from app.data.resources.resources import RESOURCES, Resources
from app.editor.settings import MainSettingsController
from app.events import event_commands, event_validators
from app.utilities import str_utils
from app.utilities.typing import NID

class EventScriptFunctionHinter():
    @staticmethod
    @lru_cache(16)
    def _generate_hint_for_command(command: Type[event_commands.EventCommand], param: str) -> str:
        command = command()
        args = []
        args.append(command.nid)
        all_keywords = command.keywords + command.optional_keywords
        curr_keyword = None
        for idx, keyword in enumerate(all_keywords):
            if command.keyword_types:
                keyword_type = command.keyword_types[idx]
                hint_str = "%s=%s" % (keyword, keyword_type)
                if keyword == param:
                    hint_str = "<b>%s</b>" % hint_str
                    curr_keyword = keyword_type
                args.append(hint_str)
            else:
                hint_str = keyword
                if keyword == param:
                    hint_str = "<b>%s</b>" % hint_str
                    curr_keyword = keyword
                args.append(hint_str)
        if command.flags:
            hint_str = 'FLAGS'
            if param == 'FLAGS':
                hint_str = "<b>%s</b>" % hint_str
                curr_keyword = 'FLAGS'
            args.append(hint_str)
        hint_cmd_str = ';\u200b'.join(args)
        hint_cmd_str = '<div class="command_text">' + hint_cmd_str + '</div>'

        hint_desc = ''
        if curr_keyword == 'FLAGS':
            hint_desc = 'Must be one of: %s' % ', '.join(command.flags)
        else:
            validator = event_validators.get(curr_keyword)
            if validator:
                hint_desc = '<div class="desc_text">' + validator().desc + '</div>'

        style = """
            <style>
                .command_text {font-family: 'Courier New', Courier, monospace;}
                .desc_text {font-family: Arial, Helvetica, sans-serif;}
            </style>
        """

        hint_text = style + hint_cmd_str + '<hr>' + hint_desc
        return hint_text

    @staticmethod
    def generate_hint_for_line(line: str, cursor_pos: int):
        if cursor_pos != 0 and line[cursor_pos - 1] not in ';=':
            return None
        command = detect_command_under_cursor(line)
        param = detect_param_under_cursor(command, line, cursor_pos)
        return EventScriptFunctionHinter._generate_hint_for_command(command, param)


class EventScriptCompleter(QCompleter):
    insertText = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = MainSettingsController()
        self.setFilterMode(Qt.MatchContains)
        self.activated.connect(self.changeCompletion)

    def changeCompletion(self, completion):
        self.insertText.emit(completion)
        self.popup().hide()

    def handleKeyPressEvent(self, event) -> bool:
        if event.key() == self.settings.get_autocomplete_button(Qt.Key_Tab):
            if self.popup().isVisible() and len(self.popup().selectedIndexes()) > 0:
                # If completer is up, Tab/Enter can auto-complete
                completion = self.popup().selectedIndexes()[0].data(Qt.DisplayRole)
                self.changeCompletion(completion)
                return True # should not enter a tab
        elif event.key() == Qt.Key_Backspace:
            # autofill functionality, hides autofill windows
            if self.popup().isVisible():
                self.popup().hide()
        elif event.key() == Qt.Key_Escape:
            if self.popup().isVisible():
                self.popup().hide()
        return False

    def setTextToComplete(self, line: str, cursor_pos: int, level_nid: NID):
        # line is of the form, e.g.:
        # "remove_unit;E" -> User is in the middle of typing "Eirika"
        def arg_text_under_cursor(text: str, cursor_pos):
            before_text = text[0:cursor_pos]
            after_text = text[cursor_pos:]
            idx = before_text.rfind(';')
            before_arg = before_text[idx + 1:]
            idx = after_text.find(';')
            after_arg = after_text[0:idx]
            return (before_arg + after_arg)
        arg_under_cursor = arg_text_under_cursor(line, cursor_pos)
        # determine what dictionary to use for completion
        validator, flags = detect_type_under_cursor(line, cursor_pos, arg_under_cursor)
        autofill_dict = generate_wordlist_from_validator_type(validator, level_nid, arg_under_cursor, DB, RESOURCES)
        if flags:
            autofill_dict = autofill_dict + generate_flags_wordlist(flags)
        if len(autofill_dict) == 0:
            try:
                if self.popup().isVisible():
                    self.popup().hide()
            except: # popup doesn't exist?
                pass
            return False
        self.setModel(QStringListModel(autofill_dict, self))
        trimmed_line = line[0:cursor_pos]
        start_last_arg = max(max([trimmed_line.rfind(c) for c in ';,']), -1)
        completionPrefix = trimmed_line[start_last_arg + 1:]
        self.setCompletionPrefix(completionPrefix)
        self.popup().setCurrentIndex(self.completionModel().index(0, 0))
        return True

class ParseMode(Enum):
    COMMAND = 1
    ARGS = 2
    NESTED_ARG = 3
    FINISHED_ARGS = 4
    FLAGS = 5
    FINISHED = 6

@dataclass
class ParseInfo():
    command: Optional[Type[event_commands.EventCommand]]
    arg_under_cursor: str
    type_under_cursor: Optional[Type[event_validators.Validator]]
    final_mode: ParseMode = ParseMode.FINISHED

class PythonEventScriptCompleter(EventScriptCompleter):
    def get_parse_info(self, line: str, cursor_pos: int) -> Optional[ParseInfo]:
        if not line.startswith('$'):
            return None
        mode = ParseMode.COMMAND
        command = ''
        curr_arg = ''
        arg_list = []
        paren_depth = 0
        for i in range(cursor_pos):
            c = line[i]
            if mode == ParseMode.COMMAND:
                if c == '$':
                    continue
                elif c == '(':
                    mode = ParseMode.ARGS
                else:
                    command += c
            elif mode == ParseMode.ARGS:
                if c == ',':
                    arg_list.append(curr_arg.strip())
                    curr_arg = ''
                    continue
                elif c == '(':
                    mode = ParseMode.NESTED_ARG
                    curr_arg += c
                    paren_depth += 1
                elif c == ')':
                    mode = ParseMode.FINISHED_ARGS
                    curr_arg = ''
                else:
                    curr_arg += c
            elif mode == ParseMode.NESTED_ARG:
                if c == '(':
                    paren_depth += 1
                elif c == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        mode = ParseMode.ARGS
                curr_arg += c
            elif mode == ParseMode.FINISHED_ARGS:
                if curr_arg == '.FLAGS':
                    curr_arg = ''
                    mode = ParseMode.FLAGS
                    continue
                elif not '.FLAGS'.startswith(curr_arg):
                    mode = ParseMode.FINISHED
                    break
                curr_arg += c
            elif mode == ParseMode.FLAGS:
                if c == ',':
                    curr_arg = ''
                    continue
                curr_arg += c
        if mode == ParseMode.COMMAND: # not finished typing the command:
            return ParseInfo(None, command, event_validators.EventFunction, mode)
        command_t = event_commands.ALL_EVENT_COMMANDS.get(command)
        if not command_t:
            return None
        validator_nid = None
        if '=' in curr_arg:
            maybe_keyword, arg_text = curr_arg.split('=', 1)
            validator_nid = command_t.get_validator_from_keyword(maybe_keyword)
        else:
            arg_text = curr_arg
            arg_idx = len(arg_list)
            if arg_idx < len(command_t.get_keyword_types()):
                validator_nid = command_t.get_keyword_types()[arg_idx]
        validator = event_validators.get(validator_nid)
        arg_text = arg_text.strip()
        if arg_text.startswith(('"', "'")):
            quote = arg_text[0]
            arg_text.replace(quote, '')
        return ParseInfo(command_t, arg_text, validator, mode)

    def setTextToComplete(self, line: str, cursor_pos: int, level_nid: NID):
        line_info = self.get_parse_info(line, cursor_pos)
        if not line_info:
            return False
        if line_info.final_mode == ParseMode.FLAGS:
            autofill_dict = line_info.command().flags
            autofill_dict = [f'"{arg}"' for arg in autofill_dict]
        elif line_info.final_mode == ParseMode.FINISHED_ARGS:
            autofill_dict = ['.FLAGS']
        elif line_info.final_mode == ParseMode.FINISHED:
            return False
        else:
            validator = line_info.type_under_cursor
            autofill_dict = generate_wordlist_from_validator_type(validator, level_nid, line_info.arg_under_cursor, DB, RESOURCES)
            # wrap in quotes bc python. specifically don't do this for command names since they aren't string args
            if line_info.final_mode != ParseMode.COMMAND:
                autofill_dict = [f'"{arg}"' for arg in autofill_dict]
        if len(autofill_dict) == 0:
            try:
                if self.popup().isVisible():
                    self.popup().hide()
            except: # popup doesn't exist?
                pass
            return False
        self.setModel(QStringListModel(autofill_dict, self))
        self.setCompletionPrefix(line_info.arg_under_cursor)
        self.popup().setCurrentIndex(self.completionModel().index(0, 0))
        return True

def generate_wordlist_from_validator_type(validator: Type[event_validators.Validator], level: NID = None, arg: str = None,
                                          db: Database = None, resources: Resources = None) -> List[str]:
    if not validator:
        return []
    valid_entries = validator(db, resources).valid_entries(level, arg)
    autofill_dict = []
    for entry in valid_entries:
        if entry[0] is None:
            # no name, but has nid
            autofill_dict.append('{}'.format(entry[1]))
        else:
            # has name and nid
            autofill_dict.append('{name} ({nid})'.format(
                name=entry[0], nid=entry[1]))
    return autofill_dict

def generate_flags_wordlist(flags: List[str] = []) -> List[str]:
    flaglist = []
    if len(flags) > 0:
        # then we can also put flags in this slot
        for flag in flags:
            flaglist.append('FLAG({flag})'.format(flag=flag))
    return flaglist

def detect_command_under_cursor(line: str) -> Type[event_commands.EventCommand]:
    return event_commands.determine_command_type(line)

def detect_param_under_cursor(command: event_commands.EventCommand, line: str, cursor_pos: int):
    if isinstance(command, event_commands.Comment):
        return None
    as_tokens = line[:cursor_pos].split(';')
    if not as_tokens[0] in (command.nid, command.nickname): # should never happen
        return None
    if len(as_tokens) == 1:
        return None
    as_tokens = as_tokens[1:]
    all_keywords = command.keywords + command.optional_keywords

    curr_arg = as_tokens[-1]
    if '=' in curr_arg:
        param = curr_arg.split('=')[0]
        if param in all_keywords:
            return param
    curr_arg_idx = len(as_tokens) - 1
    if curr_arg_idx < len(all_keywords):
        return all_keywords[curr_arg_idx]
    return 'FLAGS'

def detect_type_under_cursor(line: str, cursor_pos: int, arg_under_cursor: str = None) -> Tuple[event_validators.Validator, List[str]]:
    # turn off typechecking for comments
    comment_index = line.find("#")
    if cursor_pos > comment_index and comment_index > 0:
        return (event_validators.Validator, [])

    if arg_under_cursor:
        # see if we're in the middle of a bracket/eval expression
        # filter out all paired brackets
        arg_under_cursor = str_utils.remove_all_matched(arg_under_cursor, '{', '}')
        eval_bracket = arg_under_cursor.rfind('{')
        eval_colon = arg_under_cursor.rfind(':')
        eval_end = arg_under_cursor.rfind('}')
        if eval_colon > eval_bracket and eval_bracket > eval_end:
            # get eval type
            eval_tag = arg_under_cursor[eval_bracket+1:eval_colon]
            return (event_validators.get(eval_tag), [])

    args = [arg.string for arg in event_commands.get_command_arguments(line)]
    arg_idx = -1
    while cursor_pos > 0:
        current_arg = args.pop()
        cursor_pos -= len(current_arg) + 1
        arg_idx += 1
    arg_idx -= 1

    flags = []
    # -1 is the command itself, and 0, 1, 2, etc. are the args
    if arg_idx <= -1:
        return (event_validators.EventFunction, [])
    try:
        command_type = detect_command_under_cursor(line)
        command = command_type()
        validator_name = None
        if arg_under_cursor and '=' in arg_under_cursor:
            arg_name = arg_under_cursor.split('=')[0]
            if command.get_index_from_keyword(arg_name) != 0:
                arg_idx = command.get_index_from_keyword(arg_name)
        if command:
            if arg_idx >= len(command.keywords):
                # no longer required keywords, now add optionals and flags
                flags = command.flags
                i = arg_idx - len(command.keywords)
                if i < len(command.optional_keywords):
                    validator_name = command.get_keyword_types()[arg_idx]
            else:
                validator_name = command.get_keyword_types()[arg_idx]
        if validator_name:
            validator = event_validators.get(validator_name)
        else:
            validator = event_validators.Validator
        return (validator, flags)
    except Exception as e:
        print(e)
        import traceback
        traceback.print_exc()
        return (event_validators.Validator, [])
