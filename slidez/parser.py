"""Parser: .sldz source -> Presentation (classes bound via the registry).

Grammar (indentation-based, 1 level = any wider indent than the parent):

    presentation := node*                     (top level: `Slides:` + slides)
    node        := bare_line | key [":" value] [child_block]
    bare_line   := text | "quoted text"       (grouped into elements at bind time)
    value       := "string" | number | true/false | [a, b] | bare words
    comment     := // line   /* block */

Errors are SlidezError with line numbers and suggestions where possible.
"""

from __future__ import annotations

import difflib
import re

from .ast import ELEMENTS, Presentation, Slide, SlidezError, Text, props_of

STYLE_KEYS = ("font", "size", "color", "background")

# property name -> checker(value) -> error message, or None if valid
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_pair(v):
    return isinstance(v, tuple) and len(v) == 2 and all(_is_num(x) for x in v)


def _validate_prop(target, snake, value, line):
    """Fail fast (with line number) on values that would crash at render."""
    where = f"line {line}: {type(target).__name__}"

    def err(expected):
        raise SlidezError(f"{where}: '{snake}' expects {expected}, got {value!r}")

    if value is None:
        return
    if snake in ("position", "dash"):
        if snake == "dash" and isinstance(value, tuple) and len(value) == 1:
            return  # [3] means gap == dash
        if not _check_pair(value):
            err("two numbers, e.g. [0.5, 0.5]")
    elif snake == "size":
        if isinstance(target, (Text, Slide)):
            if not _is_num(value):
                err("a number (font size)")
        elif not (isinstance(value, tuple) and value and all(_is_num(x) for x in value)):
            err("numbers, e.g. [0.5, 0.3]")
    elif snake in ("width", "border_width", "head_size", "radius",
                   "item_gap", "indent_step", "padding"):
        if not _is_num(value):
            err("a number")
    elif snake == "bold":
        if not isinstance(value, bool):
            err("true or false")
    elif snake == "column":
        if value not in (0, 1):
            err("0 or 1")
    elif snake == "align_h":
        if value not in ("left", "center", "right"):
            err("left, center or right")
    elif snake == "align_v":
        if value not in ("top", "center", "bottom"):
            err("top, center or bottom")
    elif snake in ("color", "border_color", "marker_color", "fill", "accent"):
        if isinstance(value, str) and value.startswith("#") \
                and not re.fullmatch(r"#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?", value):
            err("a color like #RRGGBB")


def _suggest(name: str, options) -> str:
    matches = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    return f" — did you mean '{matches[0]}'?" if matches else ""


def _pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


class Node:
    __slots__ = ("key", "value", "indent", "line", "group", "raw", "children")

    def __init__(self, key, value, indent, line, group, raw):
        self.key = key              # None for bare text lines
        self.value = value          # inline value / bare line text
        self.indent = indent
        self.line = line
        self.group = group          # bare lines in different groups don't merge
        self.raw = raw              # original line text (for text fallback)
        self.children = []


def _strip_comments(src: str) -> list[str]:
    """Replace // and /* */ comments with spaces, honoring double quotes."""
    out_lines = []
    in_block = False
    block_start = 0
    for lineno, raw in enumerate(src.splitlines(), 1):
        chars = list(raw)
        in_str = False
        i = 0
        while i < len(chars):
            c = chars[i]
            if in_block:
                if c == "*" and i + 1 < len(chars) and chars[i + 1] == "/":
                    chars[i] = chars[i + 1] = " "
                    in_block = False
                    i += 2
                    continue
                chars[i] = " "
                i += 1
            elif in_str:
                if c == "\\" and i + 1 < len(chars):
                    i += 2   # escaped char (\n, \", \t) — not a string end
                    continue
                if c == '"':
                    in_str = False
                i += 1
            elif c == '"':
                in_str = True
                i += 1
            elif c == "/" and i + 1 < len(chars) and chars[i + 1] == "/" and \
                    (i == 0 or chars[i - 1].isspace()):
                # // starts a comment only at line start or after whitespace,
                # so URLs in bare text (https://...) survive
                chars[i:] = [" "] * (len(chars) - i)
                break
            elif c == "/" and i + 1 < len(chars) and chars[i + 1] == "*":
                chars[i] = chars[i + 1] = " "
                in_block = True
                block_start = lineno
                i += 2
            else:
                i += 1
        if in_str:
            raise SlidezError(f"Unterminated string (line {lineno})")
        out_lines.append("".join(chars))
    if in_block:
        raise SlidezError(f"Unclosed /* comment (starts at line {block_start})")
    return out_lines


def _split_key(text: str, lineno: int):
    """Return (key, value_str) for 'Key: value' lines, or (None, text) for bare.

    Lines whose prefix before ':' is not an identifier (e.g. Russian text,
    URLs) are bare text.
    """
    in_str = False
    for i, c in enumerate(text):
        if c == '"' and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        elif c == ":" and not in_str:
            key = text[:i].strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                return key, text[i + 1:].strip()
            return None, text
    return None, text


def _unescape(s: str) -> str:
    """Process \\n, \\t, \\" and \\\\ left to right; other backslashes stay."""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt in ('"', "\\"):
                out.append(nxt)
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _parse_value(s: str, lineno: int):
    s = s.strip()
    if not s:
        return None
    if s.startswith('"'):
        # a fully quoted string, or a quoted fragment inside bare words
        i, end = 1, None
        while i < len(s):
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == '"':
                end = i
                break
            i += 1
        if end is None:
            raise SlidezError(f"Unterminated string (line {lineno}): {s[:40]}")
        if s[end + 1:].strip():
            return s   # e.g. `"//" for lines` — keep verbatim
        return _unescape(s[1:end])
    if s.startswith("["):
        if "]" not in s:
            raise SlidezError(f"Unclosed list (line {lineno}): {s[:40]}")
        if not s.endswith("]"):
            return s   # e.g. `[0.5, 0.5] and a note` — keep verbatim
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part, lineno) for part in inner.split(",")]
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _unquote_bare(text: str):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return _unescape(text[1:-1])
    return text


def _to_snake(key: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower()


def parse(source: str, base_dir) -> Presentation:
    """Parse .sldz source into a bound Presentation."""
    lines = []   # (indent, text, lineno, group)
    group = 0
    for lineno, raw in enumerate(_strip_comments(source), 1):
        if not raw.strip():
            group += 1
            continue
        stripped = raw.lstrip(" \t")
        indent_str = raw[: len(raw) - len(stripped)]
        if "\t" in indent_str:
            raise SlidezError(f"Tabs are not allowed for indentation (line {lineno})")
        indent = len(indent_str)
        lines.append((indent, stripped.strip(), lineno, group))

    root, _ = _parse_nodes(lines, 0, 0)
    return _bind(root, base_dir)


def _parse_nodes(lines, i, base_indent):
    nodes = []
    while i < len(lines):
        indent, text, lineno, group = lines[i]
        if indent < base_indent:
            break
        if indent > base_indent:
            raise SlidezError(f"Unexpected indent at line {lineno}")
        node = Node(None, None, indent, lineno, group, text)
        node.key, value_str = _split_key(text, lineno)
        if node.key is None:
            node.value = _unquote_bare(text)
        else:
            node.value = _parse_value(value_str, lineno)
        nodes.append(node)
        i += 1
        if i < len(lines) and lines[i][0] > indent:
            node.children, i = _parse_nodes(lines, i, lines[i][0])
    return nodes, i


def _bind(root_nodes, base_dir) -> Presentation:
    pres = Presentation(base_dir)
    for node in root_nodes:
        if node.key is None:
            raise SlidezError(
                f"Bare text at top level (line {node.line}) — text belongs inside a slide")
        if node.key == "Slides":
            if node.value is not None:
                raise SlidezError(f"'Slides:' takes no inline value (line {node.line})")
            for c in node.children:
                if c.key is None:
                    raise SlidezError(f"Bare text not allowed in Slides: block (line {c.line})")
                snake = _to_snake(c.key)
                if snake not in STYLE_KEYS:
                    raise SlidezError(
                        f"Unknown style key '{c.key}' in Slides: block (line {c.line})"
                        f"{_suggest(c.key, [_pascal(k) for k in STYLE_KEYS])}"
                        f" — expected one of: {', '.join(STYLE_KEYS)}")
                pres.style[snake] = _list_to_tuple(c.value)
            continue
        cls = ELEMENTS.get(node.key)
        if cls is not None and not issubclass(cls, Slide):
            raise SlidezError(
                f"'{node.key}' is an element, not a slide template (line {node.line})")
        if node.value is not None:
            raise SlidezError(
                f"line {node.line}: slides take no inline value"
                f" — put content on indented lines below '{node.key}:'")
        slide = (cls or Slide)(name=node.key)
        slide._line = node.line
        _bind_children(slide, node)
        pres.slides.append(slide)
    if not pres.slides:
        raise SlidezError("No slides found — the deck is empty")
    return pres


def _bind_children(target, node):
    """Bind child nodes: properties, sub-elements, bare text."""
    is_slide = isinstance(target, Slide)
    props = props_of(type(target))
    cur_node = None
    cur_el = None

    def close_bare():
        nonlocal cur_el
        if cur_el is not None:
            cur_el.finalize()
            cur_el = None

    def new_bare(c):
        nonlocal cur_el, cur_node
        close_bare()
        cur_el = Text()
        cur_el._line = c.line
        target.contents.append(cur_el)
        cur_el.add_bare(c)
        cur_node = c

    for c in node.children:
        if c.key is None:
            if is_slide:
                if cur_node is not None and cur_node.group == c.group:
                    cur_el.add_bare(c)
                else:
                    new_bare(c)
            else:
                target.add_bare(c)
            continue
        cur_node = None
        close_bare()
        snake = _to_snake(c.key)
        if snake in props:
            value = _list_to_tuple(c.value)
            _validate_prop(target, snake, value, c.line)
            setattr(target, snake, value)
        elif is_slide and c.key in ELEMENTS:
            el = ELEMENTS[c.key]()
            el._line = c.line
            if c.value is not None:
                el.set_inline(c.value)
            _bind_children(el, c)
            target.contents.append(el)
        elif not is_slide:
            # Inside an element, unknown keys are verbatim content (prose
            # and code with colons — any value type). Exception: a
            # structured value on a name that closely matches a real
            # property is almost certainly a typo, so fail loudly.
            if not isinstance(c.value, str) and _suggest(
                    c.key, [_pascal(p) for p in props]):
                raise SlidezError(
                    f"line {c.line}: unknown property '{c.key}' for"
                    f" {type(target).__name__}{_suggest(c.key, [_pascal(p) for p in props])}")
            c.value = c.raw if c.value is not None else c.key + ":"
            c.key = None
            target.add_bare(c)
        elif c.value is None and not c.children:
            # Slide-level 'Heap:' — bare text that matches a key name
            c.key, c.value = None, c.raw
            new_bare(c)
        else:
            options = list(ELEMENTS) + [_pascal(p) for p in props]
            raise SlidezError(
                f"line {c.line}: unknown '{c.key}' for {type(target).__name__}"
                f"{_suggest(c.key, options)} (a property or a registered element)")
    close_bare()
    target.finalize()


def _list_to_tuple(v):
    return tuple(v) if isinstance(v, list) else v
