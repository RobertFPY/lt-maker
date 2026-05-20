"""
Bộ chuyển đổi qua lại giữa **event script** (format `nid;arg1;arg2`) và
**Python eventing pyev1** (`$nid "arg1" "arg2" ..., flag`).

Cách dùng:

    # Auto-detect chiều dựa trên header `#pyev1`
    python -m app.events.python_eventing.convert_event input.txt

    # Ép chiều
    python -m app.events.python_eventing.convert_event input.txt --to python
    python -m app.events.python_eventing.convert_event input.txt --to script

    # Output ra file thay vì stdout
    python -m app.events.python_eventing.convert_event input.txt -o out.txt

Chú ý:
    * Chiều **script -> python** chuyển 1-1: mọi dòng đều ra được.
    * Chiều **python -> script** chỉ chuyển được các dòng `$...` (event command)
      và comment `#`. Các construct Python (if/for/biến/eval) sẽ KHÔNG được
      bảo toàn — script in cảnh báo `# [UNCONVERTIBLE]` cho mỗi dòng như vậy
      để bạn xử lý thủ công.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Các import dưới đây giả định bạn chạy script từ root project (lt-maker).
from app.events import event_commands
from app.events.python_eventing.swscomp.swscompv1 import SWSCompilerV1


PYEV1_HEADER = "#pyev1"

# Các pattern dòng "rõ ràng là Python" để cảnh báo khi convert ngược về script.
# Không bắt hết được mọi case, chỉ heuristic.
_PY_CONSTRUCT_RE = re.compile(
    r"""^\s*(
        if\b | elif\b | else\s*: | for\b | while\b | def\b | class\b |
        return\b | break\b | continue\b | pass\b | import\b | from\b |
        with\b | try\b | except\b | finally\b | raise\b | yield\b |
        [A-Za-z_][A-Za-z_0-9]*\s*=(?!=)        # variable assignment
    )""",
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _needs_quoting(value: str) -> bool:
    """Token cần được bọc trong dấu nháy khi xuất pyev1?"""
    if value == "":
        return True
    # Chứa space, dấu phẩy, dấu ngoặc, dấu nháy => phải quote
    return bool(re.search(r'[\s,()\[\]{}"\']', value))


def _quote_for_python(value: str) -> str:
    """Bọc value bằng dấu nháy phù hợp cho pyev1.

    Ưu tiên `"..."`. Nếu value chứa `"` mà không chứa `'` thì dùng `'...'`.
    Nếu chứa cả 2 -> dùng curly quotes cho `"` bên trong (an toàn parser).
    """
    if not _needs_quoting(value):
        # Vẫn quote cho rõ ràng và đồng nhất; nhưng giữ nguyên các giá trị
        # thuần số/identifier để code đẹp.
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
            return f'"{value}"'
        if re.fullmatch(r"-?\d+(\.\d+)?", value):
            return f'"{value}"'
        return f'"{value}"'

    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"

    # Cả hai đều có. Đổi `"` bên trong thành curly U+201C/U+201D (parser SWS
    # coi đây là ký tự thường, không kết chuỗi) và bọc bằng `"..."`.
    safe = value.replace('"', "\u201c")
    return f'"{safe}"'


def _strip_quotes(token: str) -> str:
    """Bỏ dấu nháy bao ngoài (nếu có) khỏi token đã parse từ pyev1."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


# ---------------------------------------------------------------------------
# script -> python (pyev1)
# ---------------------------------------------------------------------------

def _command_to_pyev1_line(cmd: event_commands.EventCommand) -> str:
    """Chuyển 1 EventCommand đã parse thành dòng pyev1."""
    # Comment hoặc dòng rỗng giữ nguyên
    if isinstance(cmd, event_commands.Comment):
        if not cmd.display_values:
            return ""
        text = cmd.display_values[0]
        if not text:
            return ""
        return text if text.startswith("#") else f"# {text}"

    parts: List[str] = [f"${cmd.nid}"]

    # Dùng display_values vì giữ nguyên thứ tự gốc và format `Key=Value`
    args_part: List[str] = []
    flags_part: List[str] = []
    for raw in cmd.display_values:
        if raw in cmd.chosen_flags:
            flags_part.append(raw)
            continue
        if "=" in raw and raw.split("=", 1)[0] in (cmd.keywords + cmd.optional_keywords):
            key, val = raw.split("=", 1)
            args_part.append(f"{key}={_quote_for_python(val)}")
        else:
            args_part.append(_quote_for_python(raw))

    line = " ".join(parts + args_part)
    if flags_part:
        line += ", " + " ".join(flags_part)
    return line


def script_to_python(source: str) -> str:
    """Chuyển nội dung event script -> pyev1."""
    out_lines: List[str] = [PYEV1_HEADER]
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            out_lines.append("")
            continue
        cmd, _ = event_commands.parse_text_to_command(raw_line)
        if cmd is None:
            out_lines.append(f"# [UNPARSED] {raw_line}")
            continue
        out_lines.append(_command_to_pyev1_line(cmd))
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# python (pyev1) -> script
# ---------------------------------------------------------------------------

def _pyev1_line_to_script(line: str) -> Tuple[str, bool]:
    """Chuyển 1 dòng pyev1 sang event script.

    Trả về (line, ok). `ok=False` nghĩa là dòng không thể convert tự động
    (ví dụ Python construct) — caller có thể thêm tiền tố cảnh báo.
    """
    stripped = line.strip()

    # Header và pyev1 directive bị bỏ qua trong output script
    if stripped == PYEV1_HEADER:
        return ("", True)

    # Empty
    if not stripped:
        return ("", True)

    # Comment thuần
    if stripped.startswith("#"):
        # Bỏ `#` đi và prefix `comment;` để tương thích parser script,
        # hoặc giữ nguyên nếu user muốn comment-style. Engine hỗ trợ cả 2,
        # nhưng `#...` thân thiện hơn -> giữ nguyên.
        return (stripped, True)

    if stripped.startswith("$"):
        tokens_obj = SWSCompilerV1.parse_line(line)
        if tokens_obj is None or not tokens_obj.tokens:
            return (f"# [UNPARSED] {line}", False)

        # tokens_obj.tokens có thể có một entry trailing rỗng do parser; lọc
        raw_tokens = [t for t in tokens_obj.tokens if t and t != "EOL"]
        if not raw_tokens:
            return (f"# [UNPARSED] {line}", False)

        flag_idx = getattr(tokens_obj, "_flag_idx", 99)
        nid = raw_tokens[0]
        rest = raw_tokens[1:]

        args: List[str] = []
        flags: List[str] = []
        for i, tok in enumerate(rest, start=1):
            value = _strip_quotes(tok)
            # Keyword=Value: giữ nguyên key, strip quote khỏi value
            if "=" in value and re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", value):
                k, v = value.split("=", 1)
                value = f"{k}={_strip_quotes(v)}"
            if i >= flag_idx:
                flags.append(value)
            else:
                args.append(value)

        parts = [nid] + args + flags
        return (";".join(parts), True)

    # Dòng còn lại = Python logic thuần. Không convert được.
    return (f"# [UNCONVERTIBLE] {line}", False)


def python_to_script(source: str) -> str:
    """Chuyển pyev1 -> event script. Cảnh báo các dòng không convert được."""
    out_lines: List[str] = []
    warnings = 0
    for raw_line in source.splitlines():
        converted, ok = _pyev1_line_to_script(raw_line)
        if not ok:
            warnings += 1
        out_lines.append(converted)
    if warnings:
        sys.stderr.write(
            f"[convert_event] WARNING: {warnings} dòng không convert được "
            f"sang event script (Python logic). Đã đánh dấu '# [UNCONVERTIBLE]'.\n"
        )
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Auto detect & CLI
# ---------------------------------------------------------------------------

def detect_format(source: str) -> str:
    """Trả về 'python' hoặc 'script'."""
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == PYEV1_HEADER:
            return "python"
        # Heuristic: dòng đầu có nhiều `;` -> script
        if ";" in stripped and not stripped.startswith("#"):
            return "script"
        if stripped.startswith("$"):
            return "python"
        if _PY_CONSTRUCT_RE.match(stripped):
            return "python"
        # Dòng comment ở đầu thì xem dòng tiếp
    return "script"


def convert(source: str, target: str) -> str:
    if target == "python":
        return script_to_python(source)
    if target == "script":
        return python_to_script(source)
    raise ValueError(f"Unknown target: {target}")


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chuyển đổi event qua lại giữa event script và pyev1."
    )
    parser.add_argument("input", type=Path, help="File input (event script hoặc pyev1)")
    parser.add_argument(
        "--to",
        choices=("python", "script", "auto"),
        default="auto",
        help="Định dạng đích. 'auto' tự suy luận: nếu input là script -> python, ngược lại.",
    )
    parser.add_argument("-o", "--output", type=Path, help="File output (mặc định stdout)")
    args = parser.parse_args(argv)

    source = args.input.read_text(encoding="utf-8")

    if args.to == "auto":
        src_fmt = detect_format(source)
        target = "python" if src_fmt == "script" else "script"
    else:
        target = args.to

    result = convert(source, target)

    if args.output:
        args.output.write_text(result, encoding="utf-8")
        sys.stderr.write(f"[convert_event] Đã ghi {len(result)} ký tự vào {args.output}\n")
    else:
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
