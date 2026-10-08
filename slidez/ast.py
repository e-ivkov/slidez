"""Slidez core: the class tree the language maps onto, plus registries.

Every construct in a .sldz file resolves to a class registered here.
To add your own elements, templates (Slide subclasses) or fonts, subclass
and @register / @register_font them in a plugin module, then import that
module in main.py.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ELEMENTS: dict[str, type] = {}   # class name -> Element/Slide subclass
FONTS: dict[str, "Font"] = {}    # lowercase name/alias -> Font


class SlidezError(Exception):
    pass


def register(cls):
    """Class decorator: make an Element or Slide subclass usable in .sldz by its class name."""
    ELEMENTS[cls.__name__] = cls
    return cls


def register_font(font):
    """Register a Font under its name and aliases (case-insensitive)."""
    for name in font.names:
        FONTS[name.lower()] = font
    return font


def resolve_font(name) -> "Font":
    font = FONTS.get(str(name).lower())
    if font is None:
        raise SlidezError(
            f"Unknown font '{name}'. Registered fonts: {', '.join(sorted(FONTS))}")
    return font


NAMED_COLORS = {
    "black": "#000000", "white": "#FFFFFF", "red": "#E53935", "green": "#43A047",
    "blue": "#1E88E5", "yellow": "#FDD835", "orange": "#FB8C00", "purple": "#8E24AA",
    "gray": "#9E9E9E", "grey": "#9E9E9E", "cyan": "#00ACC1", "magenta": "#D81B60",
    "lime": "#C0CA33", "pink": "#EC407A", "brown": "#6D4C41",
}


def is_color(v) -> bool:
    """True for values the language treats as colors (#hex or names)."""
    return isinstance(v, str) and (v.startswith("#") or v.strip().lower() in NAMED_COLORS)


def parse_color(c) -> tuple[int, int, int]:
    if isinstance(c, (tuple, list)) and len(c) == 3:
        return tuple(int(v) for v in c)
    s = NAMED_COLORS.get(str(c).strip().lower(), c)
    s = str(s).strip()
    if not s.startswith("#"):
        raise SlidezError(f"Invalid color '{c}' (expected '#RRGGBB' or a named color)")
    h = s[1:]
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise SlidezError(f"Invalid color '{c}' (expected '#RRGGBB' or a named color)")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise SlidezError(f"Invalid color '{c}' (bad hex digits)")


def props_of(cls) -> dict[str, object]:
    """Language-settable properties of a class: public non-callable class attrs."""
    out = {}
    for c in reversed(cls.__mro__):
        for k, v in vars(c).items():
            if k.startswith(("_", "default_")) or callable(v) or isinstance(v, (property, classmethod, staticmethod)):
                continue
            out[k] = v
    return out


def bold_runs(text: str) -> list[tuple[str, bool]]:
    """Split text into (text, bold) runs on **bold** markers."""
    return [(part, i % 2 == 1) for i, part in enumerate(text.split("**")) if part]


class Font:
    """A font family: regular + bold TTF files and a default size (pt)."""

    def __init__(self, names, file=None, bold_file=None, size=18.0):
        self.names = (names,) if isinstance(names, str) else tuple(names)
        self.file = file
        self.bold_file = bold_file or file
        self.size = size

    @property
    def family(self) -> str:
        return self.names[0]

    def path(self, bold=False) -> Path:
        p = Path(self.bold_file if bold else self.file)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise SlidezError(f"Font file not found: {p}")
        return p

    def with_size(self, size: float) -> "Font":
        f = copy.copy(self)
        f.size = size
        return f

    def __repr__(self):
        return f"Font({self.family!r}, size={self.size})"


class Element:
    """Base for everything on a slide.

    Class attributes are the language properties (PascalCase in .sldz,
    snake_case here). None means "not set" -> inherited via style cascade.
    Elements without a Position are placed by the slide's flow layout.
    """

    position = None      # (x, y) in 0-1 slide units
    size = None          # (w, h) in 0-1 slide units (shapes, images)
    align_h = None       # left | center | right
    align_v = None       # top | center | bottom (absolute text anchor)
    color = None
    border_color = None
    border_width = None
    width = None         # wrap width for text, 0-1 slide units
    column = None        # 0 | 1 for TwoColumnsSlide
    dash = None          # (on, off) dash pattern for lines, pt
    role = None          # tag for templates, e.g. Role: title / image

    # --- binding hooks (called by the parser) ---

    def set_inline(self, value):
        raise SlidezError(f"{type(self).__name__} takes no inline value")

    def add_bare(self, node, level=0):
        raise SlidezError(f"{type(self).__name__} takes no bare text content")

    def finalize(self):
        pass

    # --- lifecycle ---

    def apply_style(self, style: dict):
        pass

    def render(self, ctx):
        if self.position is not None:
            self.render_abs(ctx)
        else:
            self.render_flow(ctx)

    def render_abs(self, ctx):
        raise SlidezError(f"{type(self).__name__} requires a Position")

    def render_flow(self, ctx):
        pass

    def height(self, ctx) -> float:
        """Vertical space this element needs in flow (for template layout)."""
        return 0.0

    def _need(self, *props) -> None:
        """Raise a helpful error for a missing required property."""
        for p in props:
            if getattr(self, p) is None:
                line = getattr(self, "_line", None)
                where = f"line {line}: " if line else ""
                raise SlidezError(
                    f"{where}{type(self).__name__} requires"
                    f" {' and '.join(p.capitalize() for p in props)}")


def _flat_lines(node, level=0):
    """Flatten a bare node subtree to text lines, keeping relative indent.

    Deeper lines are verbatim content whether or not they parse as
    'Key: value' — code snippets often look like deck source.
    """
    text = node.value if node.key is None else node.raw
    yield "    " * level + (text or "")
    for child in node.children:
        yield from _flat_lines(child, level + 1)


@register
class Text(Element):
    contents = ""
    font = None           # family name until apply_style, then a Font
    size = None
    bold = None

    default_size = None   # used when neither element nor style sets a size
    default_font = None   # family override (e.g. Code -> Mono)
    default_bold = False

    def set_inline(self, value):
        self.contents = value

    def add_bare(self, node, level=0):
        # deeper-indented bare lines keep their relative indentation
        # (4 spaces per level; "" is an empty line)
        self._lines.extend(_flat_lines(node, level))

    def finalize(self):
        lines = getattr(self, "_lines", None)
        if lines:
            if self.contents:
                self.contents += "\n"
            self.contents += "\n".join(lines)
            self._lines = []

    def __init__(self):
        self._lines = []

    def apply_style(self, style: dict):
        family = (self.font if self.font is not None
                  else getattr(self, "default_font", None)
                  or style.get("font"))
        try:
            font = resolve_font(family)
        except SlidezError as e:
            line = getattr(self, "_line", None)
            raise SlidezError(f"line {line}: {e}") if line else e
        size = self.size
        if size is None:
            size = style.get("size")
        if size is None:
            size = getattr(self, "default_size", None) or font.size
        self.font = font.with_size(size)
        if self.color is None:
            self.color = style.get("color") or "#000000"
        if self.bold is None:
            self.bold = getattr(self, "default_bold", False)

    # --- rendering ---

    def _runs(self):
        return bold_runs(self.contents)

    def _flow_width(self, ctx) -> float:
        """Wrap width in flow: own Width (page fraction), capped by the column."""
        w = self.width * ctx.W if self.width else ctx.flow_w
        return min(w, ctx.flow_w)

    def render_flow(self, ctx):
        font = self.font
        w = self._flow_width(ctx)
        lines = ctx.wrap(self._runs(), w, font)
        h = len(lines) * ctx.line_height(font)
        x = ctx.flow_x
        if self.align_h == "center":
            x += (ctx.flow_w - w) / 2
        elif self.align_h == "right":
            x += ctx.flow_w - w
        ctx.text_block(lines, x, ctx.y, w, font, self.color, self.align_h or "left")
        ctx.y += h + font.size * 0.7

    def render_abs(self, ctx):
        font = self.font
        px, py = self.position[0] * ctx.W, self.position[1] * ctx.H
        if self.width:
            # explicit box: lines aligned inside it, px/py is its top-left
            w = self.width * ctx.W
            lines = ctx.wrap(self._runs(), w, font)
            align_h = self.align_h or "left"
        else:
            # no box: px/py anchors the text block (left/center/right,
            # top/center/bottom) and lines keep their \n breaks
            lines = [bold_runs(seg) for seg in self.contents.split("\n")]
            w = max((ctx.runs_width(line, font) for line in lines), default=0.0)
            align_h = self.align_h or "left"
            if align_h == "center":
                px -= w / 2
            elif align_h == "right":
                px -= w
        h = len(lines) * ctx.line_height(font)
        y = py
        if self.align_v == "center":
            y = py - h / 2
        elif self.align_v == "bottom":
            y = py - h
        ctx.text_block(lines, px, y, w, font, self.color, align_h)

    def height(self, ctx) -> float:
        font = self.font
        w = self._flow_width(ctx)
        lines = ctx.wrap(self._runs(), w, font)
        return len(lines) * ctx.line_height(font) + font.size * 0.7


@register
class Title(Text):
    default_size = 30
    default_bold = True


@register
class Bullets(Text):
    marker = "\u2022"
    sub_marker = "\u2013"  # marker for nested levels
    marker_color = None
    item_gap = None       # extra vertical space between items, pt
    indent_step = None    # per-level indent, pt (default ~1.1em)

    def __init__(self):
        super().__init__()
        self.items = []   # list of (level, text)

    def _mark(self, level):
        return self.marker if level == 0 else self.sub_marker

    def add_bare(self, node, level=0):
        self.items.append((level, node.value))
        for child in node.children:
            if child.key is None:
                self.add_bare(child, level + 1)

    def apply_style(self, style: dict):
        super().apply_style(style)
        if self.marker_color is None:
            self.marker_color = self.color

    def render_flow(self, ctx):
        font = self.font
        lh = ctx.line_height(font)
        step = self.indent_step if self.indent_step is not None else font.size * 1.1
        gap = self.item_gap or 0.0
        for level, text in self.items:
            x = ctx.flow_x + level * step
            avail = ctx.flow_w - level * step
            mark = self._mark(level)
            mark_w = ctx.runs_width([(mark, False)], font)
            pad = font.size * 0.35
            runs = bold_runs(text)
            lines = ctx.wrap(runs, avail - mark_w - pad, font)
            ctx.draw_runs(x, ctx.y + ctx.baseline_offset(font),
                          [(mark, False)], font, self.marker_color)
            ctx.text_block(lines, x + mark_w + pad, ctx.y,
                           avail - mark_w - pad, font, self.color, "left")
            ctx.y += len(lines) * lh + gap
        ctx.y += font.size * 0.25

    def render_abs(self, ctx):
        # flow the items starting at the anchor point (top-left)
        x0 = self.position[0] * ctx.W
        saved = (ctx.flow_x, ctx.flow_w, ctx.y)
        ctx.flow_x = x0
        ctx.flow_w = self.width * ctx.W if self.width else ctx.W - x0 - ctx.pad_r / 2
        ctx.y = self.position[1] * ctx.H
        self.render_flow(ctx)
        ctx.flow_x, ctx.flow_w, ctx.y = saved

    def height(self, ctx) -> float:
        font = self.font
        lh = ctx.line_height(font)
        step = self.indent_step if self.indent_step is not None else font.size * 1.1
        gap = self.item_gap or 0.0
        total = 0.0
        for level, text in self.items:
            x = ctx.flow_x + level * step
            avail = ctx.flow_w - level * step
            mark_w = ctx.runs_width([(self._mark(level), False)], font)
            pad = font.size * 0.35
            lines = ctx.wrap(bold_runs(text), avail - mark_w - pad, font)
            total += len(lines) * lh + gap
        return total + font.size * 0.25


@register
class Image(Element):
    source = ""

    def set_inline(self, value):
        self.source = value

    def path(self, ctx) -> Path:
        if not self.source:
            line = getattr(self, "_line", None)
            where = f"line {line}: " if line else ""
            raise SlidezError(f"{where}{type(self).__name__} requires a file path")
        p = Path(self.source)
        if not p.is_absolute():
            p = ctx.base_dir / p
        if not p.exists():
            line = getattr(self, "_line", None)
            where = f"line {line}: " if line else ""
            raise SlidezError(f"{where}image not found: {p}")
        if not p.is_file():
            raise SlidezError(f"not a file: {p}")
        return p

    def _fit(self, ctx, max_w, max_h=None):
        """Return (w, h) in pt fitting into max_w/max_h, keeping aspect."""
        px, py = ctx.image_size(self.path(ctx))
        w = self.size[0] * ctx.W if self.size else max_w
        h = w * py / px
        if max_h and h > max_h:
            h = max_h
            w = h * px / py
        return w, h

    def render_flow(self, ctx):
        max_h = ctx.H - ctx.pad_b - ctx.y
        w, h = self._fit(ctx, ctx.flow_w, max(50.0, max_h))
        x = ctx.flow_x + (ctx.flow_w - w) / 2
        ctx.image(self.path(ctx), x, ctx.y, w, h)
        ctx.y += h + 12

    def render_abs(self, ctx):
        px, py = self.position[0] * ctx.W, self.position[1] * ctx.H
        if self.size:
            w = self.size[0] * ctx.W
            px_img, py_img = ctx.image_size(self.path(ctx))
            h = self.size[1] * ctx.H if len(self.size) > 1 and self.size[1] else w * py_img / px_img
        else:
            w, h = self._fit(ctx, 0.5 * ctx.W)
        ctx.image(self.path(ctx), px, py, w, h)

    def height(self, ctx) -> float:
        max_h = ctx.H - ctx.pad_b - ctx.y
        w, h = self._fit(ctx, ctx.flow_w, max(50.0, max_h))
        return h + 12


@register
class Line(Element):
    """A line from Position to Position + Size (0-1 slide units)."""

    def render_abs(self, ctx):
        self._need("size")
        x1, y1 = self.position[0] * ctx.W, self.position[1] * ctx.H
        x2 = x1 + self.size[0] * ctx.W
        y2 = y1 + self.size[1] * ctx.H
        ctx.draw_line(x1, y1, x2, y2, self.color or "#808080",
                      self.border_width or 1.0, self.dash)

    def render_flow(self, ctx):
        ctx.draw_line(ctx.flow_x, ctx.y, ctx.flow_x + ctx.flow_w, ctx.y,
                      self.color or "#808080", self.border_width or 1.0, self.dash)
        ctx.y += 14

    def height(self, ctx) -> float:
        return 14


@register
class Rect(Element):
    radius = None         # rounded corner radius, pt

    def render_abs(self, ctx):
        self._need("size")
        x, y = self.position[0] * ctx.W, self.position[1] * ctx.H
        w, h = self.size[0] * ctx.W, self.size[1] * ctx.H
        ctx.fill_rect(x, y, w, h, self.color, self.radius,
                      self.border_color, self.border_width)


@register
class Ellipse(Element):

    def render_abs(self, ctx):
        self._need("size")
        x, y = self.position[0] * ctx.W, self.position[1] * ctx.H
        w, h = self.size[0] * ctx.W, self.size[1] * ctx.H
        ctx.ellipse(x, y, w, h, self.color, self.border_color, self.border_width)


@register
class Arrow(Element):
    """Arrow from Position to Position + Size, with a triangular head."""
    head_size = None      # head length in pt

    def render_abs(self, ctx):
        import math
        self._need("size")
        x1, y1 = self.position[0] * ctx.W, self.position[1] * ctx.H
        x2 = x1 + self.size[0] * ctx.W
        y2 = y1 + self.size[1] * ctx.H
        color = self.color or "#404040"
        lw = self.border_width or 1.5
        head = self.head_size or 7.0
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        bx, by = x2 - ux * head, y2 - uy * head
        ctx.draw_line(x1, y1, bx, by, color, lw, self.dash)
        px, py = -uy, ux
        ctx.polygon([(x2, y2),
                     (bx + px * head * 0.45, by + py * head * 0.45),
                     (bx - px * head * 0.45, by - py * head * 0.45)], fill=color)


@register
class Slide:
    """One slide; base template: background + top-down flow of children.

    font/size/color set here cascade to all child elements.
    Subclass and override apply_style/render to make your own template.
    """

    background = None
    font = None
    size = None
    color = None

    def __init__(self, name=""):
        self.name = name
        self.contents = []

    def finalize(self):
        pass   # elements finalize themselves when their block closes

    def apply_style(self, style: dict):
        own = {k: getattr(self, k) for k in ("font", "size", "color")
               if getattr(self, k) is not None}
        if self.background is None:
            self.background = style.get("background")
        child_style = {**style, **own}
        for el in self.contents:
            el.apply_style(child_style)

    def render(self, ctx):
        self._draw_background(ctx)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        ctx.y = ctx.pad_t
        for el in self.contents:
            el.render(ctx)

    def _draw_background(self, ctx):
        if not self.background:
            return
        bg = self.background
        if is_color(bg):
            ctx.fill_rect(0, 0, ctx.W, ctx.H, bg)
        else:  # image path, relative to the .sldz file
            p = Path(bg)
            if not p.is_absolute():
                p = ctx.base_dir / p
            ctx.image(p, 0, 0, ctx.W, ctx.H)

    def _flow_children(self):
        return [el for el in self.contents if el.position is None]


class Presentation:
    def __init__(self, base_dir: Path):
        self.slides = []
        self.style = {}
        self.base_dir = Path(base_dir)

    def apply_style(self):
        if not FONTS:
            raise SlidezError(
                "no fonts registered — import a font plugin first"
                " (e.g. `import plugins.fonts` in main.py)")
        fallback_font = "Default" if "default" in FONTS else next(iter(FONTS.values())).family
        style = {"font": fallback_font, "size": None, "color": None, "background": None}
        style.update(self.style)
        for slide in self.slides:
            slide.apply_style(style)
