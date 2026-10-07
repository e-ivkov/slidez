"""PDF renderer on top of fpdf2: 960x540pt pages (16:9)."""

from __future__ import annotations

import re

from fpdf import FPDF

from ..ast import FONTS, SlidezError, resolve_font
from . import Renderer

PAGE_W, PAGE_H = 960.0, 540.0

NAMED_COLORS = {
    "black": "#000000", "white": "#FFFFFF", "red": "#E53935", "green": "#43A047",
    "blue": "#1E88E5", "yellow": "#FDD835", "orange": "#FB8C00", "purple": "#8E24AA",
    "gray": "#9E9E9E", "grey": "#9E9E9E", "cyan": "#00ACC1", "magenta": "#D81B60",
    "lime": "#C0CA33", "pink": "#EC407A", "brown": "#6D4C41",
}


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


class RenderContext:
    """Drawing/font/wrapping primitives passed to Element.render().

    Flow layout state: flow_x/flow_w (current column) and y (cursor).
    """

    line_factor = 1.30
    baseline_factor = 0.86   # baseline offset from line top, ~ascent

    def __init__(self, pdf: FPDF, base_dir, slide_index: int, total: int):
        self.pdf = pdf
        self.base_dir = base_dir
        self.slide_index = slide_index
        self.total = total
        self.fonts = FONTS             # lowercase name -> Font (for plugins)
        self.W, self.H = PAGE_W, PAGE_H
        self.pad_l, self.pad_r = 54.0, 54.0
        self.pad_t, self.pad_b = 40.0, 44.0
        self.content_w = self.W - self.pad_l - self.pad_r
        self.flow_x, self.flow_w = self.pad_l, self.content_w
        self.y = self.pad_t

    def get_font(self, name):
        """Resolve a family name (case-insensitive) to a registered Font."""
        return resolve_font(name)

    # --- fonts & text ---

    def set_font(self, font, bold=False):
        self.pdf.set_font(font.family, "B" if bold else "", font.size)

    def runs_width(self, runs, font) -> float:
        total = 0.0
        for text, bold in runs:
            self.set_font(font, bold)
            total += self.pdf.get_string_width(text)
        return total

    def wrap(self, runs, width: float, font) -> list[list[tuple[str, bool]]]:
        """Greedy word wrap of (text, bold) runs; newlines force breaks."""
        lines = []
        current: list[tuple[str, bool]] = []

        def flush():
            while current and current[-1][0].strip() == "":
                current.pop()
            if current:
                lines.append(current)
            return []

        for text, bold in runs:
            segments = text.split("\n")
            for si, seg in enumerate(segments):
                if si > 0:  # forced break
                    current = flush()
                if not seg:
                    lines.append([])   # explicit empty line
                    continue
                for piece in re.findall(r"\S+\s*|\s+", seg):
                    if piece.isspace():
                        # keep: spaces between words and line indentation
                        current.append((piece, bold))
                        continue
                    w = self.runs_width([(piece, bold)], font)
                    used = self.runs_width(current, font)
                    if current and used + w > width:
                        current = flush()
                    current.append((piece, bold))
        flush()
        return lines

    def line_height(self, font) -> float:
        return font.size * self.line_factor

    def baseline_offset(self, font) -> float:
        return font.size * self.baseline_factor

    def draw_runs(self, x, y_baseline, runs, font, color) -> float:
        """Draw runs on one baseline starting at x; returns width used."""
        r, g, b = parse_color(color)
        self.pdf.set_text_color(r, g, b)
        for text, bold in runs:
            self.set_font(font, bold)
            self.pdf.text(x, y_baseline, text)
            x += self.pdf.get_string_width(text)
        return x

    def text_block(self, lines, x, y, w, font, color, align_h="left") -> float:
        """Draw wrapped lines in a box (x, y, w); returns height."""
        lh = self.line_height(font)
        bo = self.baseline_offset(font)
        for i, line in enumerate(lines):
            line_w = self.runs_width(line, font)
            lx = x
            if align_h == "center":
                lx = x + (w - line_w) / 2
            elif align_h == "right":
                lx = x + w - line_w
            self.draw_runs(lx, y + i * lh + bo, line, font, color)
        return len(lines) * lh

    # --- shapes ---

    def _stroke(self, color, width, dash):
        r, g, b = parse_color(color)
        self.pdf.set_draw_color(r, g, b)
        self.pdf.set_line_width(width or 1.0)
        if dash:
            self.pdf.set_dash_pattern(dash=dash[0], gap=dash[1] if len(dash) > 1 else dash[0])
        else:
            self.pdf.set_dash_pattern()

    def draw_line(self, x1, y1, x2, y2, color, width=1.0, dash=None):
        self._stroke(color, width, dash)
        self.pdf.line(x1, y1, x2, y2)
        self.pdf.set_dash_pattern()

    def fill_rect(self, x, y, w, h, fill=None, radius=None, border=None, border_width=None):
        style = "D"
        if fill is not None:
            r, g, b = parse_color(fill)
            self.pdf.set_fill_color(r, g, b)
            style = "FD" if border is not None else "F"
        if border is not None:
            self._stroke(border, border_width or 1.0, None)
        self.pdf.rect(x, y, w, h, style=style,
                      round_corners=bool(radius), corner_radius=radius or 0)

    def ellipse(self, x, y, w, h, fill=None, border=None, border_width=None):
        style = "D"
        if fill is not None:
            r, g, b = parse_color(fill)
            self.pdf.set_fill_color(r, g, b)
            style = "FD" if border is not None else "F"
        if border is not None:
            self._stroke(border, border_width or 1.0, None)
        self.pdf.ellipse(x, y, w, h, style=style)

    def polygon(self, points, fill=None, border=None, border_width=None):
        style = "D"
        if fill is not None:
            r, g, b = parse_color(fill)
            self.pdf.set_fill_color(r, g, b)
            style = "FD" if border is not None else "F"
        if border is not None:
            self._stroke(border, border_width or 1.0, None)
        self.pdf.polygon(points, style=style)

    # --- images ---

    def image(self, path, x=None, y=None, w=None, h=None):
        self.pdf.image(str(path), x=x, y=y, w=w, h=h)

    def image_size(self, path) -> tuple[float, float]:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            return float(img.width), float(img.height)


class PDFRenderer(Renderer):
    name = "pdf"

    def render(self, pres, path: str):
        pdf = FPDF(unit="pt", format=(PAGE_W, PAGE_H))
        pdf.set_auto_page_break(False)
        pdf.set_margin(0)
        seen = set()
        for font in FONTS.values():
            if font.family.lower() in seen:
                continue
            seen.add(font.family.lower())
            pdf.add_font(font.family, "", str(font.path()))
            pdf.add_font(font.family, "B", str(font.path(bold=True)))
        total = len(pres.slides)
        for idx, slide in enumerate(pres.slides, 1):
            pdf.add_page()
            ctx = RenderContext(pdf, pres.base_dir, idx, total)
            slide.render(ctx)
        pdf.output(path)
        return path
