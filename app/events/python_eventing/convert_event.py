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
# Event-script expression -> Python expression
# ---------------------------------------------------------------------------

# {v:NAME}, {d:NAME}, {e:EXPR} -> v('NAME'), d('NAME'), e('EXPR')
# Các helper này nằm trong query_engine.func_dict được merge vào globals khi
# pyev1 chạy (xem app/engine/evaluate.py:get_context).
_VAR_GETTER_RE = re.compile(r"\{([vde]):([^{}]+)\}")


def _convert_script_expr_to_python(expr: str) -> str:
    """Chuyển 1 biểu thức event-script (`{v:X}`, `{d:X}`, `{e:X}`) sang
    biểu thức Python — sử dụng truy cập trực tiếp `game.level_vars` /
    `game.game_vars` vì các biến đó luôn có trong globals của pyev1
    (không phụ thuộc query_engine func_dict, vốn không phải lúc nào cũng load).

    Mapping:
        {v:X}    -> game.level_vars.get('X', game.game_vars.get('X'))
        {v:X,Y}  -> game.level_vars.get('X', game.game_vars.get('X', Y))
        {d:X}    -> game.level_vars.get('X')
        {e:EXPR} -> (EXPR)

    Cũng convert toán tử event-script `=` thành Python `==`.
    """
    if not expr:
        return expr

    def repl(match: "re.Match") -> str:
        kind = match.group(1)
        inner = match.group(2).strip()
        if kind == "e":
            return f"({inner})"
        if "," in inner:
            name, fallback = inner.split(",", 1)
            name = name.strip()
            fallback = fallback.strip()
            if kind == "v":
                return (
                    f"game.level_vars.get('{name}', "
                    f"game.game_vars.get('{name}', {fallback!r}))"
                )
            return f"game.level_vars.get('{name}', {fallback!r})"
        if kind == "v":
            return (
                f"game.level_vars.get('{inner}', "
                f"game.game_vars.get('{inner}'))"
            )
        return f"game.level_vars.get('{inner}')"

    converted = _VAR_GETTER_RE.sub(repl, expr)
    converted = re.sub(r"(?<![=!<>:])=(?!=)", "==", converted)
    return converted


def _convert_script_value_to_python(value: str) -> Tuple[str, bool]:
    """Convert 1 giá trị arg event-script sang biểu thức Python.

    Trả về `(converted, is_expression)`. `is_expression=True` -> không quote.
    """
    if not value:
        return "", False
    if _VAR_GETTER_RE.search(value):
        m = _VAR_GETTER_RE.fullmatch(value)
        if m:
            return _convert_script_expr_to_python(value), True
        # Hỗn hợp text + var -> dùng f-string
        def _fstr(m2):
            kind, inner = m2.group(1), m2.group(2).strip()
            if kind == "e":
                return "{" + f"({inner})" + "}"
            if "," in inner and kind == "v":
                name, fb = inner.split(",", 1)
                name = name.strip()
                fb = fb.strip()
                return (
                    "{"
                    f"game.level_vars.get('{name}', "
                    f"game.game_vars.get('{name}', {fb!r}))"
                    "}"
                )
            if kind == "v":
                return (
                    "{"
                    f"game.level_vars.get('{inner}', "
                    f"game.game_vars.get('{inner}'))"
                    "}"
                )
            return "{" f"game.level_vars.get('{inner}')" "}"
        body = _VAR_GETTER_RE.sub(_fstr, value)
        return f'f"{body}"', True
    if re.fullmatch(r"-?\d+", value):
        return value, True
    if re.fullmatch(r"-?\d+\.\d+", value):
        return value, True
    return value, False


# ---------------------------------------------------------------------------
# script -> python (pyev1)
# ---------------------------------------------------------------------------

def _command_to_pyev1_line(cmd: event_commands.EventCommand) -> str:
    """Chuyển 1 EventCommand đã parse thành dòng pyev1.

    - Required keyword (từ `cmd.keywords`): luôn dạng positional, theo thứ tự.
    - Optional keyword (từ `cmd.optional_keywords`): nếu được set và không
      rỗng, emit dạng `Key=Value`. Bỏ qua các optional rỗng. Điều này tránh
      sinh ra chuỗi `"" "" "" ""` không cần thiết và đúng convention pyev1.
    - Flags: gom sau `,`.
    """
    # Comment hoặc dòng rỗng giữ nguyên
    if isinstance(cmd, event_commands.Comment):
        if not cmd.display_values:
            return ""
        text = cmd.display_values[0]
        if not text:
            return ""
        return text if text.startswith("#") else f"# {text}"

    parts: List[str] = [f"${cmd.nid}"]
    args_part: List[str] = []
    flags_part: List[str] = sorted(cmd.chosen_flags)

    params = cmd.parameters or {}

    # Required keywords: positional. Bao gồm cả `*Text`/`*String` (variadic).
    for kwd in cmd.keywords:
        clean_kwd = kwd.lstrip("*")
        val = params.get(clean_kwd, params.get(kwd, ""))
        if val is None:
            val = ""
        converted, is_expr = _convert_script_value_to_python(str(val))
        args_part.append(converted if is_expr else _quote_for_python(str(val)))

    # Optional keywords: liền mạch sau required (chưa gặp gap nào) -> positional;
    # sau khi gặp 1 optional bị bỏ trống thì các optional có giá trị tiếp theo
    # mới chuyển sang dạng Key=Value.
    seen_gap = False
    for kwd in cmd.optional_keywords:
        clean_kwd = kwd.lstrip("*")
        has_value = (clean_kwd in params or kwd in params)
        if has_value:
            val = params.get(clean_kwd, params.get(kwd, ""))
            if val is None or val == "":
                has_value = False

        if not has_value:
            seen_gap = True
            continue

        val = params.get(clean_kwd, params.get(kwd, ""))
        converted, is_expr = _convert_script_value_to_python(str(val))
        token = converted if is_expr else _quote_for_python(str(val))
        if seen_gap:
            args_part.append(f"{clean_kwd}={token}")
        else:
            args_part.append(token)

    line = " ".join(parts + args_part)
    if flags_part:
        line += ", " + " ".join(flags_part)
    return line


INDENT_STR = "    "


def script_to_python(source: str) -> str:
    """Chuyển nội dung event script -> pyev1.

    Các flow-control command (`if`, `elif`, `else`, `for`, `end`, `endf`) được
    chuyển thành **Python statement** (không phải `$...`), đồng thời thân block
    được thụt lề bằng 4 spaces × độ sâu hiện tại.

    Tự động chèn `pass` cho block rỗng để code Python hợp lệ. Cũng convert
    `{v:NAME}`, `{d:NAME}`, `{e:EXPR}` trong cả expression flow-control và
    arg của command.
    """
    out_lines: List[str] = [PYEV1_HEADER]
    depth = 0  # số block đang mở
    # Stack đếm: với mỗi block đang mở, lưu chỉ số dòng "header" (if/elif/else/for)
    # và biến đếm số statement đã thêm vào block đó. Khi đóng block mà count==0
    # thì chèn `pass`.
    block_stack: List[List[int]] = []  # [count]

    def _bump_block_count():
        if block_stack:
            block_stack[-1][0] += 1

    def _close_one_block():
        nonlocal depth
        if not block_stack:
            return
        count = block_stack.pop()[0]
        if count == 0:
            out_lines.append(INDENT_STR * depth + "pass")
        depth = max(0, depth - 1)

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            out_lines.append("")
            continue
        cmd, _ = event_commands.parse_text_to_command(raw_line)
        if cmd is None:
            out_lines.append(INDENT_STR * depth + f"# [UNPARSED] {raw_line}")
            _bump_block_count()
            continue

        nid = cmd.nid

        # end/endf: đóng block, tự chèn pass nếu rỗng
        if nid in ("end", "endf"):
            _close_one_block()
            continue

        # elif/else: cùng cấp với if. Trước khi xuất, đóng block cũ (rỗng -> pass)
        if nid == "elif":
            # Đóng block hiện tại (vì elif tạo branch mới ở cùng cấp `if`)
            if block_stack:
                count = block_stack[-1][0]
                if count == 0:
                    outer = max(0, depth - 1)
                    out_lines.append(INDENT_STR * depth + "pass")
                block_stack[-1][0] = 0  # reset đếm cho branch mới
            expr = cmd.display_values[0] if cmd.display_values else ""
            expr = _convert_script_expr_to_python(expr)
            outer = max(0, depth - 1)
            out_lines.append(INDENT_STR * outer + f"elif {expr}:")
            continue
        if nid == "else":
            if block_stack:
                count = block_stack[-1][0]
                if count == 0:
                    out_lines.append(INDENT_STR * depth + "pass")
                block_stack[-1][0] = 0
            outer = max(0, depth - 1)
            out_lines.append(INDENT_STR * outer + "else:")
            continue

        # if: mở block mới
        if nid == "if":
            expr = cmd.display_values[0] if cmd.display_values else "False"
            expr = _convert_script_expr_to_python(expr)
            out_lines.append(INDENT_STR * depth + f"if {expr}:")
            depth += 1
            block_stack.append([0])
            continue

        # for: `for;NID;EXPR` -> `for NID in EXPR:`
        if nid == "for":
            vals = cmd.display_values
            var_nid = vals[0] if len(vals) >= 1 else "_item"
            expr = vals[1] if len(vals) >= 2 else "[]"
            expr = _convert_script_expr_to_python(expr)
            out_lines.append(INDENT_STR * depth + f"for {var_nid} in {expr}:")
            depth += 1
            block_stack.append([0])
            continue

        # Comment giữ nguyên, vẫn thụt lề theo depth
        if isinstance(cmd, event_commands.Comment):
            line = _command_to_pyev1_line(cmd)
            if line:
                out_lines.append(INDENT_STR * depth + line)
            else:
                out_lines.append("")
            # Comment KHÔNG tính là statement -> không bump count
            continue

        # Default: chuyển thành dòng `$...` với indent
        out_lines.append(INDENT_STR * depth + _command_to_pyev1_line(cmd))
        _bump_block_count()

    # Đóng nốt các block còn mở (khuyến nghị nguồn nên có end, nhưng phòng hờ)
    while block_stack:
        _close_one_block()

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


_FLOW_RE = re.compile(r"^\s*(if|elif|else|for)\b(.*?):\s*$")


def _measure_indent(line: str) -> int:
    """Trả về số ký tự indent ở đầu dòng (đếm space; tab = 4)."""
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4
        else:
            break
    return n


def python_to_script(source: str) -> str:
    """Chuyển pyev1 -> event script.

    Flow-control Python (`if EXPR:`, `elif EXPR:`, `else:`, `for X in Y:`) được
    chuyển ngược thành lệnh script `if;EXPR`, `elif;EXPR`, `else`, `for;X;Y`.
    Các `end`/`endf` tương ứng được tự động chèn dựa trên indent dedent.

    Các dòng Python khác (gán biến, gọi hàm thuần Python, list comprehension
    đứng riêng...) sẽ được đánh dấu `# [UNCONVERTIBLE]`.
    """
    lines = source.splitlines()
    out_lines: List[str] = []
    warnings = 0

    # Stack lưu (indent_level, kind) với kind ∈ {'if', 'for'}
    block_stack: List[Tuple[int, str]] = []

    def close_blocks_to(target_indent: int):
        """Đóng các block có indent > target_indent bằng end/endf phù hợp."""
        while block_stack and block_stack[-1][0] >= target_indent:
            _, kind = block_stack.pop()
            out_lines.append("endf" if kind == "for" else "end")

    for raw_line in lines:
        stripped = raw_line.strip()

        # Header / dòng trống
        if stripped == PYEV1_HEADER:
            continue
        if not stripped:
            out_lines.append("")
            continue

        # Comment thuần
        if stripped.startswith("#"):
            out_lines.append(stripped)
            continue

        cur_indent = _measure_indent(raw_line)

        # Nếu indent hiện tại nhỏ hơn block trên cùng -> đóng block
        # (trước khi xử lý dòng hiện tại). Với elif/else cùng cấp với if,
        # ta xử lý đặc biệt: KHÔNG đóng block đó.
        flow_match = _FLOW_RE.match(raw_line)
        if flow_match:
            kw = flow_match.group(1)
            tail = flow_match.group(2).strip()
            # elif/else: đóng các block sâu hơn (bên trong block if hiện tại),
            # nhưng không đóng chính block if đang mở ở cùng indent.
            if kw in ("elif", "else"):
                while block_stack and block_stack[-1][0] > cur_indent:
                    _, kind = block_stack.pop()
                    out_lines.append("endf" if kind == "for" else "end")
                if kw == "elif":
                    out_lines.append(f"elif;{tail}")
                else:
                    out_lines.append("else")
                # Không push thêm vào stack — tái dùng entry của if đã có
                continue
            # if / for: đóng các block ngang hoặc sâu hơn rồi mở block mới
            close_blocks_to(cur_indent)
            if kw == "if":
                out_lines.append(f"if;{tail}")
                block_stack.append((cur_indent, "if"))
            else:  # for
                # Cú pháp Python: `for VAR in EXPR`
                m = re.match(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s+in\s+(.+)$", tail)
                if m:
                    var_nid, expr = m.group(1), m.group(2).strip()
                    out_lines.append(f"for;{var_nid};{expr}")
                else:
                    out_lines.append(f"# [UNCONVERTIBLE] {raw_line}")
                    warnings += 1
                block_stack.append((cur_indent, "for"))
            continue

        # Đóng block khi gặp dòng có indent thấp hơn
        close_blocks_to(cur_indent)

        if stripped.startswith("$"):
            converted, ok = _pyev1_line_to_script(raw_line)
            if not ok:
                warnings += 1
            out_lines.append(converted)
        else:
            # Python logic thuần (gán biến, gọi hàm...) -> không convert
            out_lines.append(f"# [UNCONVERTIBLE] {stripped}")
            warnings += 1

    # Đóng nốt mọi block còn mở
    close_blocks_to(-1)

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


def _output_path_for(input_path: Path, target: str) -> Path:
    """Tính path output mặc định: cùng folder, thêm hậu tố theo định dạng đích."""
    suffix = ".pyev1" if target == "python" else ".script"
    stem = input_path.stem
    # Bỏ hậu tố cũ nếu có để tránh chain `.script.pyev1.script.pyev1...`
    for old in (".pyev1", ".script"):
        if stem.endswith(old):
            stem = stem[: -len(old)]
            break
    return input_path.with_name(f"{stem}{suffix}{input_path.suffix}")


def convert_file(input_path: Path, force_target: str = "auto") -> Tuple[Path, str]:
    """Convert một file và ghi ra cùng thư mục. Trả về (output_path, target)."""
    source = input_path.read_text(encoding="utf-8")
    if force_target == "auto":
        src_fmt = detect_format(source)
        target = "python" if src_fmt == "script" else "script"
    else:
        target = force_target
    result = convert(source, target)
    out_path = _output_path_for(input_path, target)
    out_path.write_text(result, encoding="utf-8")
    return out_path, target


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui() -> int:
    """Mở GUI tkinter. Hỗ trợ chọn nhiều file HOẶC paste text trực tiếp."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk, scrolledtext

    root = tk.Tk()
    root.title("Event Converter — script <-> pyev1")
    root.geometry("900x720")

    selected_files: List[Path] = []

    # --- Top: chế độ chuyển đổi ----------------------------------------------
    top = ttk.Frame(root, padding=10)
    top.pack(fill="x")
    ttk.Label(top, text="Chế độ:").pack(side="left")
    mode_var = tk.StringVar(value="auto")
    for label, value in (("Auto detect", "auto"), ("→ pyev1", "python"), ("→ script", "script")):
        ttk.Radiobutton(top, text=label, variable=mode_var, value=value).pack(side="left", padx=4)

    # --- File picker ---------------------------------------------------------
    file_frame = ttk.LabelFrame(root, text="1) Chọn file (có thể nhiều file)", padding=8)
    file_frame.pack(fill="x", padx=10, pady=5)

    files_label = ttk.Label(file_frame, text="(Chưa chọn file)", foreground="gray")
    files_label.pack(side="left", fill="x", expand=True)

    def pick_files():
        paths = filedialog.askopenfilenames(
            title="Chọn event file",
            filetypes=[("Text files", "*.txt *.event *.pyev1 *.script"), ("All", "*.*")],
        )
        if not paths:
            return
        selected_files.clear()
        selected_files.extend(Path(p) for p in paths)
        files_label.config(
            text=f"Đã chọn {len(selected_files)} file: " + ", ".join(p.name for p in selected_files[:3]) + ("..." if len(selected_files) > 3 else ""),
            foreground="black",
        )

    ttk.Button(file_frame, text="Chọn file...", command=pick_files).pack(side="right")

    # --- Text paste area -----------------------------------------------------
    paste_frame = ttk.LabelFrame(root, text="2) HOẶC dán event vào đây", padding=8)
    paste_frame.pack(fill="both", expand=True, padx=10, pady=5)
    input_text = scrolledtext.ScrolledText(paste_frame, height=12, font=("Consolas", 10), wrap="none")
    input_text.pack(fill="both", expand=True)

    # --- Output area ---------------------------------------------------------
    out_frame = ttk.LabelFrame(root, text="Kết quả (khi dùng paste)", padding=8)
    out_frame.pack(fill="both", expand=True, padx=10, pady=5)
    output_text = scrolledtext.ScrolledText(out_frame, height=12, font=("Consolas", 10), wrap="none")
    output_text.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="Sẵn sàng.")
    status_bar = ttk.Label(root, textvariable=status_var, anchor="w", relief="sunken")
    status_bar.pack(fill="x", side="bottom")

    # --- Convert action ------------------------------------------------------
    def do_convert():
        mode = mode_var.get()
        try:
            if selected_files:
                results = []
                for fp in selected_files:
                    out_path, target = convert_file(fp, force_target=mode)
                    results.append(f"{fp.name} → {out_path.name} ({target})")
                status_var.set(f"Convert xong {len(results)} file.")
                messagebox.showinfo("Hoàn tất", "\n".join(results))
                return

            pasted = input_text.get("1.0", "end").strip()
            if not pasted:
                messagebox.showwarning(
                    "Thiếu input",
                    "Vui lòng chọn file hoặc dán event vào ô bên trên.",
                )
                return

            if mode == "auto":
                src_fmt = detect_format(pasted)
                target = "python" if src_fmt == "script" else "script"
            else:
                target = mode
            result = convert(pasted, target)
            output_text.delete("1.0", "end")
            output_text.insert("1.0", result)
            status_var.set(f"Convert sang {target}. Kết quả {len(result)} ký tự.")
        except Exception as e:  # pylint: disable=broad-except
            status_var.set(f"Lỗi: {e}")
            messagebox.showerror("Lỗi convert", str(e))

    def clear_all():
        selected_files.clear()
        files_label.config(text="(Chưa chọn file)", foreground="gray")
        input_text.delete("1.0", "end")
        output_text.delete("1.0", "end")
        status_var.set("Đã xoá.")

    def copy_output():
        text = output_text.get("1.0", "end-1c")
        if not text:
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        status_var.set("Đã copy kết quả vào clipboard.")

    button_bar = ttk.Frame(root, padding=(10, 0, 10, 10))
    button_bar.pack(fill="x")
    ttk.Button(button_bar, text="Convert", command=do_convert).pack(side="left")
    ttk.Button(button_bar, text="Copy kết quả", command=copy_output).pack(side="left", padx=5)
    ttk.Button(button_bar, text="Xoá", command=clear_all).pack(side="left")

    root.mainloop()
    return 0


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv: List[str] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Không có argument -> mở GUI
    if not argv:
        return run_gui()

    parser = argparse.ArgumentParser(
        description="Chuyển đổi event qua lại giữa event script và pyev1."
    )
    parser.add_argument("input", type=Path, nargs="?", help="File input. Bỏ trống để mở GUI.")
    parser.add_argument(
        "--to",
        choices=("python", "script", "auto"),
        default="auto",
        help="Định dạng đích. 'auto' tự suy luận: nếu input là script -> python, ngược lại.",
    )
    parser.add_argument("-o", "--output", type=Path, help="File output (mặc định stdout)")
    parser.add_argument("--gui", action="store_true", help="Bắt buộc mở GUI")
    args = parser.parse_args(argv)

    if args.gui or args.input is None:
        return run_gui()

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
