
from __future__ import annotations
from dataclasses import dataclass
from typing import List

ERROR_TEMPLATE = \
"""
    Event "{event_name}", Line {lnum}:
        {line}
    {error_name}: {what}"""

STACK_ERROR_TEMPLATE = \
"""
    From event "{event_name}", Line {lnum}:
        {line}"""

@dataclass
class PreprocessorError(Exception):
    event_name: str | List[str]
    line_num: int | List[int]
    line: str | List[str]
    what = "generic preprocessor error"

    def __str__(self) -> str:
        if isinstance(self.event_name, list):
            # all three should be list
            msg = ''
            for i in range(len(self.event_name) - 1):
                msg += STACK_ERROR_TEMPLATE.format(event_name=self.event_name[i], lnum=self.line_num[i], line=self.line[i].strip())
            msg += ERROR_TEMPLATE.format(event_name=self.event_name[-1], lnum=self.line_num[-1], line=self.line[-1].strip(),
                                         error_name=self.__class__.__name__, what=self.what)
            return msg
        else:
            msg = ERROR_TEMPLATE.format(event_name=self.event_name, lnum=self.line_num, line=self.line.strip(),
                                        error_name=self.__class__.__name__, what=self.what)
            return msg

class NestedEventError(PreprocessorError):
    what = "all event function calls must be alone and outside function def"

class InvalidCommandError(PreprocessorError):
    what = "unknown event command"

class NoSaveInLoopError(PreprocessorError):
    what = "cannot use save event commands in for loops"

class MalformedTriggerScriptCall(PreprocessorError):
    what = 'trigger script must have non-variable valid event target'

class CannotUseYieldError(PreprocessorError):
    what = 'cannot use yield in python event scripting'

class InvalidPythonError(PreprocessorError):
    what = None
