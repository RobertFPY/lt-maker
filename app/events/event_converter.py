from __future__ import annotations

import ast
import keyword
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Type

from app.events import event_commands
from app.events.event_commands import EventCommand
from app.events.event_structs import EOL
from app.events.event_version import EventVersion
from app.events.python_eventing.swscomp.swscompv1 import SWSCompilerV1


@dataclass(frozen=True)
class ConversionIssue:
    line: int
    message: str

    def __str__(self) -> str:
        return f"Line {self.line}: {self.message}"


@dataclass(frozen=True)
class ConversionResult:
    source_version: EventVersion
    target_version: EventVersion
    text: str
    issues: Tuple[ConversionIssue, ...] = ()

    @property
    def can_apply(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class _Block:
    kind: str
    indent: int
    variable: Optional[str] = None


_IF_RE = re.compile(r"^if\s+(.+):\s*$")
_ELIF_RE = re.compile(r"^elif\s+(.+):\s*$")
_ELSE_RE = re.compile(r"^else\s*:\s*$")
_FOR_RE = re.compile(r"^for\s+([A-Za-z_]\w*)\s+in\s+(.+):\s*$")
_CONTEXT_OBJECT_NAMES = (
    "created_unit", "unit1", "unit2", "target", "unit",
)


def convert_event_script(script: str, source_version: EventVersion) -> ConversionResult:
    if source_version == EventVersion.EVENT:
        return classic_to_python(script)
    if source_version == EventVersion.PYEV1:
        return python_to_classic(script)
    return ConversionResult(
        source_version,
        EventVersion.EVENT,
        script,
        (ConversionIssue(1, f"Unsupported event version: {source_version}"),),
    )


def classic_to_python(script: str) -> ConversionResult:
    output: List[str] = ["#pyev1"]
    issues: List[ConversionIssue] = []
    blocks: List[_Block] = []

    for line_number, source_line in enumerate(script.splitlines(), 1):
        stripped = source_line.strip()
        if not stripped:
            output.append("")
            continue
        if stripped.startswith("#"):
            output.append(_indent(len(blocks)) + stripped)
            continue

        command, _ = event_commands.parse_text_to_command(stripped, strict=True)
        if command is None:
            issues.append(ConversionIssue(line_number, "Invalid classic event command"))
            output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
            continue

        if command.nid == "if":
            expression, expression_issue = _classic_expression_to_python(
                command.parameters["Expression"], _active_variables(blocks)
            )
            if expression_issue:
                issues.append(ConversionIssue(line_number, expression_issue))
            output.append(_indent(len(blocks)) + f"if {expression}:")
            blocks.append(_Block("if", len(blocks)))
        elif command.nid == "elif":
            if not blocks or blocks[-1].kind != "if":
                issues.append(ConversionIssue(line_number, "elif has no matching if"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
                continue
            _ensure_python_suite_has_statement(output, len(blocks) - 1)
            expression, expression_issue = _classic_expression_to_python(
                command.parameters["Expression"], _active_variables(blocks)
            )
            if expression_issue:
                issues.append(ConversionIssue(line_number, expression_issue))
            output.append(_indent(len(blocks) - 1) + f"elif {expression}:")
        elif command.nid == "else":
            if not blocks or blocks[-1].kind != "if":
                issues.append(ConversionIssue(line_number, "else has no matching if"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
                continue
            _ensure_python_suite_has_statement(output, len(blocks) - 1)
            output.append(_indent(len(blocks) - 1) + "else:")
        elif command.nid == "end":
            if not blocks or blocks[-1].kind != "if":
                issues.append(ConversionIssue(line_number, "end has no matching if"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
                continue
            _ensure_python_suite_has_statement(output, len(blocks) - 1)
            blocks.pop()
        elif command.nid == "for":
            variable = command.parameters["Nid"]
            if not variable.isidentifier() or keyword.iskeyword(variable):
                issues.append(ConversionIssue(
                    line_number,
                    f"Loop name '{variable}' is not a valid Python identifier",
                ))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
                continue
            expression, expression_issue = _classic_expression_to_python(
                command.parameters["Expression"], _active_variables(blocks)
            )
            if expression_issue:
                issues.append(ConversionIssue(line_number, expression_issue))
            output.append(_indent(len(blocks)) + f"for {variable} in {expression}:")
            blocks.append(_Block("for", len(blocks), variable))
        elif command.nid == "endf":
            if not blocks or blocks[-1].kind != "for":
                issues.append(ConversionIssue(line_number, "endf has no matching for"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
                continue
            _ensure_python_suite_has_statement(output, len(blocks) - 1)
            blocks.pop()
        else:
            active_variables = _active_variables(blocks)
            converted, command_issues = _classic_command_to_python(
                command, active_variables, line_number
            )
            issues.extend(command_issues)
            output.append(_indent(len(blocks)) + converted)

    for block in reversed(blocks):
        issues.append(ConversionIssue(
            len(script.splitlines()) or 1,
            f"Unclosed {block.kind} block",
        ))

    converted_text = "\n".join(output)
    if not issues:
        issues.extend(_validate_generated_python(converted_text))

    return ConversionResult(
        EventVersion.EVENT,
        EventVersion.PYEV1,
        converted_text,
        tuple(issues),
    )


def python_to_classic(script: str) -> ConversionResult:
    output: List[str] = []
    issues: List[ConversionIssue] = []
    blocks: List[_Block] = []
    pending_trivia: List[str] = []
    saw_header = False

    for line_number, source_line in enumerate(script.splitlines(), 1):
        stripped = source_line.strip()
        if not saw_header and stripped == "#pyev1":
            saw_header = True
            continue
        if not stripped:
            pending_trivia.append("")
            continue
        if stripped.startswith("#"):
            pending_trivia.append(stripped)
            continue

        leading = source_line[:len(source_line) - len(source_line.lstrip())]
        if "\t" in leading:
            issues.append(ConversionIssue(line_number, "Tabs are not supported; use spaces"))
        indent = len(leading.expandtabs(4))
        is_branch = bool(_ELIF_RE.match(stripped) or _ELSE_RE.match(stripped))
        _close_python_blocks(output, blocks, indent, keep_if=is_branch)
        _flush_trivia(output, pending_trivia, len(blocks))

        # ``pass`` is a semantic no-op. The forward converter emits it only to
        # keep an otherwise-empty Python suite syntactically valid, while a
        # classic event can represent that same empty branch without a command.
        if stripped == "pass":
            continue

        if stripped.startswith("$"):
            active_variables = tuple(
                block.variable for block in blocks
                if block.kind == "for" and block.variable
            )
            converted, command_issues = _python_command_to_classic(
                stripped, active_variables, line_number
            )
            issues.extend(command_issues)
            output.append(_indent(len(blocks)) + converted)
            continue

        match = _IF_RE.match(stripped)
        if match:
            expression = _python_expression_to_classic(
                match.group(1), _active_variables(blocks)
            )
            output.append(_indent(len(blocks)) + f"if;{expression}")
            blocks.append(_Block("if", indent))
            continue

        match = _ELIF_RE.match(stripped)
        if match:
            if not blocks or blocks[-1].kind != "if" or blocks[-1].indent != indent:
                issues.append(ConversionIssue(line_number, "elif has no matching if"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
            else:
                expression = _python_expression_to_classic(
                    match.group(1), _active_variables(blocks)
                )
                output.append(_indent(len(blocks) - 1) + f"elif;{expression}")
            continue

        if _ELSE_RE.match(stripped):
            if not blocks or blocks[-1].kind != "if" or blocks[-1].indent != indent:
                issues.append(ConversionIssue(line_number, "else has no matching if"))
                output.append(_indent(len(blocks)) + f"# TODO: {stripped}")
            else:
                output.append(_indent(len(blocks) - 1) + "else")
            continue

        match = _FOR_RE.match(stripped)
        if match:
            variable, expression = match.groups()
            expression = _python_expression_to_classic(
                expression, _active_variables(blocks)
            )
            output.append(_indent(len(blocks)) + f"for;{variable};{expression}")
            blocks.append(_Block("for", indent, variable))
            continue

        issues.append(ConversionIssue(
            line_number,
            "Arbitrary Python statements cannot be represented by classic events",
        ))
        output.append(_indent(len(blocks)) + f"# TODO: {stripped}")

    _close_python_blocks(output, blocks, -1)
    _flush_trivia(output, pending_trivia, len(blocks))
    if not saw_header:
        issues.append(ConversionIssue(1, "Missing #pyev1 header"))

    return ConversionResult(
        EventVersion.PYEV1,
        EventVersion.EVENT,
        "\n".join(output),
        tuple(issues),
    )


def _classic_command_to_python(
    command: EventCommand,
    active_variables: Sequence[str],
    line_number: int,
) -> Tuple[str, List[ConversionIssue]]:
    issues: List[ConversionIssue] = []
    python_commands = event_commands.get_all_event_commands(EventVersion.PYEV1)
    if command.nid not in python_commands:
        issues.append(ConversionIssue(
            line_number,
            f"'{command.nid}' is not supported by Python Eventing",
        ))
        return f"# TODO: {command.to_plain_text()}", issues

    rendered: List[str] = []
    for parameter_name in command.keywords:
        clean_name = parameter_name.replace("*", "")
        value = command.parameters.get(clean_name)
        if value is None:
            issues.append(ConversionIssue(
                line_number,
                f"Missing required parameter '{clean_name}'",
            ))
            continue
        argument, argument_issue = _classic_value_to_python(
            str(value), command.get_validator_from_keyword(parameter_name), active_variables
        )
        if argument_issue:
            issues.append(ConversionIssue(line_number, argument_issue))
        rendered.append(argument)

    for parameter_name in command.optional_keywords:
        clean_name = parameter_name.replace("*", "")
        value = command.parameters.get(clean_name)
        if value in (None, ""):
            continue
        argument, argument_issue = _classic_value_to_python(
            str(value), command.get_validator_from_keyword(parameter_name), active_variables
        )
        if argument_issue:
            issues.append(ConversionIssue(line_number, argument_issue))
        rendered.append(f"{clean_name}={argument}")

    command_text = f"${command.nid}"
    if rendered:
        command_text += " " + " ".join(rendered)
    flags = _ordered_flags(command)
    if flags:
        command_text += ", " + " ".join(flags)
    return command_text, issues


def _classic_value_to_python(
    value: str,
    validator: Optional[str],
    active_variables: Sequence[str],
) -> Tuple[str, Optional[str]]:
    if validator == "Expression":
        expression, issue = _classic_expression_to_python(value, active_variables)
        if issue:
            return f"({expression})", issue
        return f"({expression})", None

    whole_tag = _classic_whole_tag_to_python(value)
    if whole_tag is not None:
        return whole_tag, None
    interpolation = _classic_interpolation_to_python(value, active_variables)
    if interpolation is not None:
        return interpolation, None
    return repr(value), None


def _classic_interpolation_to_python(
    value: str,
    active_variables: Sequence[str],
) -> Optional[str]:
    if not active_variables:
        return None
    variables = "|".join(re.escape(variable) for variable in active_variables)
    pattern = re.compile(r"\{(" + variables + r")\}")
    matches = list(pattern.finditer(value))
    if not matches:
        return None

    parts: List[str] = []
    cursor = 0
    for match in matches:
        if match.start() > cursor:
            parts.append(repr(value[cursor:match.start()]))
        parts.append(f"str({match.group(1)})")
        cursor = match.end()
    if cursor < len(value):
        parts.append(repr(value[cursor:]))
    return "(" + " + ".join(parts) + ")"


def _classic_expression_to_python(
    expression: str,
    active_variables: Sequence[str],
) -> Tuple[str, Optional[str]]:
    for variable in active_variables:
        expression = expression.replace(f"'{{{variable}}}'", f"str({variable})")
        expression = expression.replace(f'"{{{variable}}}"', f"str({variable})")
        expression = expression.replace(f"{{{variable}}}", variable)
    for name in _CONTEXT_OBJECT_NAMES:
        if name in active_variables:
            continue
        expression = expression.replace(f"'{{{name}}}'", f"{name}.nid")
        expression = expression.replace(f'"{{{name}}}"', f"{name}.nid")
        expression = expression.replace(f"{{{name}}}", f"{name}.nid")
    expression = re.sub(
        r"\{(?:v|var):([^{}]+)\}",
        lambda match: f"v({match.group(1)!r})",
        expression,
    )
    expression = re.sub(
        r"\{(?:e|eval):([^{}]+)\}",
        lambda match: f"({match.group(1)})",
        expression,
    )
    if re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", expression):
        return expression, "Expression contains an unsupported classic local interpolation"
    if re.search(r"\{(?:v|var|e|eval):", expression):
        return expression, "Expression contains nested classic interpolation that cannot be converted safely"
    try:
        ast.parse(expression, mode="eval")
    except SyntaxError:
        return expression, "Expression is not valid Python after conversion"
    return expression, None


def _classic_whole_tag_to_python(value: str) -> Optional[str]:
    variable_match = re.fullmatch(r"\{(?:v|var):([^{}]+)\}", value)
    if variable_match:
        return f"v({variable_match.group(1)!r})"
    eval_match = re.fullmatch(r"\{(?:e|eval):([^{}]+)\}", value)
    if eval_match:
        return f"({eval_match.group(1)})"
    local_match = re.fullmatch(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
    if local_match and local_match.group(1) in _CONTEXT_OBJECT_NAMES:
        return local_match.group(1)
    return None


def _python_expression_to_classic(
    expression: str,
    active_variables: Sequence[str],
) -> str:
    placeholders: Dict[str, str] = {}
    for index, variable in enumerate(reversed(active_variables)):
        placeholder = f"__LT_LOOP_VALUE_{index}__"
        expression = re.sub(
            rf"\bstr\(\s*{re.escape(variable)}\s*\)",
            placeholder,
            expression,
        )
        expression = re.sub(
            rf"(?<![\w.]){re.escape(variable)}(?!\w)",
            f"{{{variable}}}",
            expression,
        )
        placeholders[placeholder] = repr(f"{{{variable}}}")
    for placeholder, replacement in placeholders.items():
        expression = expression.replace(placeholder, replacement)
    for name in _CONTEXT_OBJECT_NAMES:
        if name in active_variables:
            continue
        expression = re.sub(
            rf"(?<![\w.]){re.escape(name)}\.nid(?!\w)",
            repr(f"{{{name}}}"),
            expression,
        )
    return expression


def _python_command_to_classic(
    line: str,
    active_variables: Sequence[str],
    line_number: int,
) -> Tuple[str, List[ConversionIssue]]:
    issues: List[ConversionIssue] = []
    tokens = SWSCompilerV1.parse_line(line)
    if tokens is None:
        return f"# TODO: {line}", [ConversionIssue(line_number, "Invalid Python event command")]

    command_type = event_commands.get_all_event_commands(EventVersion.PYEV1).get(tokens.command())
    if command_type is None:
        return f"# TODO: {line}", [ConversionIssue(
            line_number, f"Unknown Python event command '{tokens.command()}'"
        )]

    raw_arguments = [arg for arg in tokens.args() if arg not in ("", EOL)]
    raw_flags = [flag for flag in tokens.flags() if flag not in ("", EOL)]
    if command_type.nid == "say":
        return _python_say_to_classic(
            command_type, raw_arguments, raw_flags, active_variables, line_number
        )

    parameter_names = command_type.keywords + command_type.optional_keywords
    values: Dict[str, str] = {}
    keyword_mode = False
    positional_index = 0

    for raw_argument in raw_arguments:
        if "=" in raw_argument:
            possible_name, raw_value = raw_argument.split("=", 1)
            if possible_name in parameter_names:
                keyword_mode = True
                parameter_name = possible_name
            else:
                parameter_name = ""
                raw_value = raw_argument
        else:
            parameter_name = ""
            raw_value = raw_argument

        if not parameter_name:
            if keyword_mode:
                issues.append(ConversionIssue(
                    line_number, "Positional argument follows a keyword argument"
                ))
                continue
            if positional_index >= len(parameter_names):
                issues.append(ConversionIssue(line_number, "Too many command arguments"))
                continue
            parameter_name = parameter_names[positional_index]
            positional_index += 1

        validator = command_type.get_validator_from_keyword(parameter_name)
        converted, value_issue = _python_value_to_classic(
            raw_value, validator, active_variables
        )
        if value_issue:
            issues.append(ConversionIssue(line_number, value_issue))
        if converted is not None:
            values[parameter_name.replace("*", "")] = converted

    for required_name in command_type.keywords:
        if required_name.replace("*", "") not in values:
            issues.append(ConversionIssue(
                line_number,
                f"Missing required parameter '{required_name.replace('*', '')}'",
            ))

    classic_flags = _python_flags_to_classic(
        raw_flags, command_type, issues, line_number
    )
    return _serialize_classic_command(
        command_type.nid,
        parameter_names,
        values,
        classic_flags,
        command_type,
        issues,
        line_number,
    ), issues


def _python_say_to_classic(
    command_type: Type[EventCommand],
    raw_arguments: Sequence[str],
    raw_flags: Sequence[str],
    active_variables: Sequence[str],
    line_number: int,
) -> Tuple[str, List[ConversionIssue]]:
    issues: List[ConversionIssue] = []
    positional: List[str] = []
    keyword_values: Dict[str, str] = {}
    optional_names = command_type.optional_keywords

    for raw_argument in raw_arguments:
        if "=" in raw_argument and raw_argument.split("=", 1)[0] in optional_names:
            name, raw_value = raw_argument.split("=", 1)
            converted, value_issue = _python_value_to_classic(
                raw_value, command_type.get_validator_from_keyword(name), active_variables
            )
            if value_issue:
                issues.append(ConversionIssue(line_number, value_issue))
            if converted is not None:
                keyword_values[name] = converted
        elif keyword_values:
            issues.append(ConversionIssue(
                line_number, "Positional argument follows a keyword argument"
            ))
        else:
            positional.append(raw_argument)

    if len(positional) < 2:
        issues.append(ConversionIssue(line_number, "say requires a speaker and at least one text argument"))
        return f"# TODO: {' '.join(raw_arguments)}", issues

    speaker, speaker_issue = _python_value_to_classic(
        positional[0], "Speaker", active_variables
    )
    if speaker_issue:
        issues.append(ConversionIssue(line_number, speaker_issue))
    text_values: List[str] = []
    for raw_text in positional[1:]:
        text, text_issue = _python_value_to_classic(raw_text, "String", active_variables)
        if text_issue:
            issues.append(ConversionIssue(line_number, text_issue))
        if text is not None:
            text_values.append(text)

    values = {
        "SpeakerOrStyle": speaker or "",
        "Text": "{sub_break}".join(text_values),
        **keyword_values,
    }
    classic_flags = _python_flags_to_classic(
        raw_flags, command_type, issues, line_number
    )
    speak_type = event_commands.Speak
    return _serialize_classic_command(
        "speak",
        speak_type.keywords + speak_type.optional_keywords,
        values,
        classic_flags,
        speak_type,
        issues,
        line_number,
    ), issues


def _serialize_classic_command(
    command_nid: str,
    parameter_names: Sequence[str],
    values: Dict[str, str],
    flags: Sequence[str],
    command_type: Type[EventCommand],
    issues: List[ConversionIssue],
    line_number: int,
) -> str:
    clean_names = [name.replace("*", "") for name in parameter_names]
    present_indices = [
        index for index, name in enumerate(clean_names) if name in values
    ]
    last_index = max(present_indices, default=-1)

    for name in clean_names:
        if name in values and ";" in values[name]:
            issues.append(ConversionIssue(
                line_number,
                f"Parameter '{name}' contains ';', which classic events cannot preserve",
            ))

    # Prefer the original classic positional syntax. Fall back to named
    # parameters only when a value would otherwise be mistaken for a flag.
    valid_flags = set(command_type().flags)
    flag_collision = any(
        values.get(name) in valid_flags for name in clean_names[:last_index + 1]
    )
    parts = [command_nid]
    if flag_collision:
        parts.extend(
            f"{name}={values[name]}" for name in clean_names if name in values
        )
    else:
        parts.extend(
            values.get(name, "") for name in clean_names[:last_index + 1]
        )
    parts.extend(flags)
    return ";".join(parts)


def _python_value_to_classic(
    raw_value: str,
    validator: Optional[str],
    active_variables: Sequence[str],
) -> Tuple[Optional[str], Optional[str]]:
    raw_value = raw_value.strip()
    if validator == "Expression":
        try:
            ast.parse(raw_value, mode="eval")
        except SyntaxError:
            return raw_value, "Invalid Python expression"
        return _strip_redundant_outer_parentheses(raw_value), None

    symbolic = _python_interpolation_to_classic(raw_value, active_variables)
    if symbolic is not None:
        return symbolic, None
    try:
        value = ast.literal_eval(raw_value)
    except (ValueError, SyntaxError):
        return raw_value, f"Dynamic argument '{raw_value}' cannot be represented by a classic event"
    if value is None:
        return None, None
    if isinstance(value, str):
        return value, None
    return repr(value), None


def _python_interpolation_to_classic(
    raw_value: str,
    active_variables: Sequence[str],
) -> Optional[str]:
    try:
        node = ast.parse(raw_value, mode="eval").body
    except SyntaxError:
        return None

    def flatten(current: ast.AST) -> Optional[List[str]]:
        if isinstance(current, ast.Constant) and isinstance(current.value, str):
            return [current.value]
        tag = _classic_tag_from_python_node(current, active_variables)
        if tag is not None:
            return [tag]
        if (isinstance(current, ast.Call) and isinstance(current.func, ast.Name)
                and current.func.id == "str" and len(current.args) == 1
                and isinstance(current.args[0], ast.Name)
                and (current.args[0].id in active_variables
                     or current.args[0].id in _CONTEXT_OBJECT_NAMES)):
            return [f"{{{current.args[0].id}}}"]
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Add):
            left = flatten(current.left)
            right = flatten(current.right)
            if left is not None and right is not None:
                return left + right
        return None

    flattened = flatten(node)
    return "".join(flattened) if flattened is not None else None


def _classic_tag_from_python_node(
    node: ast.AST,
    active_variables: Sequence[str],
) -> Optional[str]:
    if isinstance(node, ast.Name):
        if node.id in active_variables or node.id in _CONTEXT_OBJECT_NAMES:
            return f"{{{node.id}}}"
    if (isinstance(node, ast.Attribute) and node.attr == "nid"
            and isinstance(node.value, ast.Name)
            and node.value.id in _CONTEXT_OBJECT_NAMES):
        return f"{{{node.value.id}}}"
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "v" and len(node.args) in (1, 2)
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)):
        return f"{{v:{node.args[0].value}}}"
    return None


def _strip_redundant_outer_parentheses(expression: str) -> str:
    stripped = expression.strip()
    while stripped.startswith("(") and stripped.endswith(")"):
        candidate = stripped[1:-1].strip()
        try:
            original_tree = ast.parse(stripped, mode="eval")
            candidate_tree = ast.parse(candidate, mode="eval")
        except SyntaxError:
            break
        if ast.dump(original_tree) != ast.dump(candidate_tree):
            break
        stripped = candidate
    return stripped


def _python_flags_to_classic(
    raw_flags: Sequence[str],
    command_type: Type[EventCommand],
    issues: List[ConversionIssue],
    line_number: int,
) -> List[str]:
    converted: List[str] = []
    valid_flags = set(command_type().flags)
    for raw_flag in raw_flags:
        flag = raw_flag
        try:
            literal = ast.literal_eval(raw_flag)
            if isinstance(literal, str):
                flag = literal
        except (ValueError, SyntaxError):
            pass
        if flag not in valid_flags:
            issues.append(ConversionIssue(line_number, f"Unknown flag '{flag}'"))
        converted.append(flag)
    return converted


def _ordered_flags(command: EventCommand) -> List[str]:
    ordered = [flag for flag in command.flags if flag in command.chosen_flags]
    ordered.extend(sorted(command.chosen_flags.difference(ordered)))
    return ordered


def _close_python_blocks(
    output: List[str],
    blocks: List[_Block],
    indent: int,
    keep_if: bool = False,
) -> None:
    while blocks:
        block = blocks[-1]
        should_close = block.indent > indent if keep_if else block.indent >= indent
        if not should_close:
            break
        blocks.pop()
        terminator = "end" if block.kind == "if" else "endf"
        output.append(_indent(len(blocks)) + terminator)


def _flush_trivia(output: List[str], pending: List[str], indent_level: int) -> None:
    for line in pending:
        output.append(_indent(indent_level) + line if line else "")
    pending.clear()


def _indent(level: int) -> str:
    return "    " * max(0, level)


def _ensure_python_suite_has_statement(output: List[str], header_indent: int) -> None:
    for line in reversed(output):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indentation = len(line) - len(line.lstrip(" "))
        if indentation == header_indent * 4 and stripped.endswith(":"):
            output.append(_indent(header_indent + 1) + "pass")
        return


def _validate_generated_python(script: str) -> List[ConversionIssue]:
    from app.events.python_eventing.compiler import Compiler

    try:
        Compiler.compile("Converted Event", script)
    except Exception as exc:
        line = getattr(exc, "lineno", None) or 1
        return [ConversionIssue(
            line,
            f"Generated Python Event failed compiler validation: {exc}",
        )]
    return []


def _active_variables(blocks: Sequence[_Block]) -> Tuple[str, ...]:
    return tuple(
        block.variable for block in blocks
        if block.kind == "for" and block.variable
    )
