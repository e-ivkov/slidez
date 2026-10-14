"""Fuzz Talk deck theme — dark slate, footer chrome, custom Callout element.

Everything here is ordinary plugin code (plugins/README.md): a chrome
mixin, template subclasses, a from-scratch text element and a Stat tweak.
"""

from plugins.basic import SectionSlide, TitleSlide, TwoColumnsSlide
from presentations.slidez_deck.theme import Stat
from slidez.ast import Slide, Text, Title, bold_runs, register

INK = "#E7EDF5"
MUTED = "#8CA0B3"
BG = "#0D1524"
CARD = "#18263E"
ACCENT = "#7C9CFF"
GREEN = "#4CC38A"
RED = "#E5484D"
FOOTER_H = 512.0


class FuzzChrome:
    """Dark background, light default text, footer rule + page number."""

    background = BG
    footer = True

    def apply_style(self, style):
        # dark slides: default text color must flip to light
        super().apply_style({**style, "color": style.get("color") or INK})

    def render(self, ctx):
        ctx.pad_b = 66          # keep the flow clear of the footer
        super().render(ctx)
        if not self.footer:
            return
        ctx.draw_line(ctx.pad_l, FOOTER_H, ctx.W - ctx.pad_r, FOOTER_H,
                      "#223350", 1.0)
        small = ctx.get_font("Manrope").with_size(11)
        ctx.text_block([[("fuzz talk", True)]], ctx.pad_l, FOOTER_H + 12, 120,
                       small, MUTED)
        num = ctx.get_font("Montserrat").with_size(11)
        w = ctx.runs_width([("n / n", False)], num)
        page = f"{ctx.slide_index} / {ctx.total}"
        ctx.text_block([[(page, False)]], ctx.W - ctx.pad_r - w, FOOTER_H + 12,
                       w, num, MUTED)


@register
class FuzzSlide(FuzzChrome, Slide):
    """Standard content slide."""


@register
class FuzzSection(FuzzChrome, SectionSlide):
    """Section intro: big centered title."""


@register
class FuzzColumns(FuzzChrome, TwoColumnsSlide):
    """Two columns, chosen per element with `Column: 0|1`."""


@register
class FuzzTitle(TitleSlide):
    """Opener: chrome-free, two lines."""

    background = BG
    title_pos = (0.08, 0.38)
    title_align_h = "left"
    title_scale = 3.6            # 20 -> 72pt
    subtitle_pos = (0.08, 0.60)
    subtitle_scale = 1.15
    subtitle_width = 0.7

    def apply_style(self, style):
        super().apply_style({**style, "color": style.get("color") or INK})


@register
class FuzzStat(Stat):
    """Stat recolored for this deck's accent."""

    accent = ACCENT


@register
class Callout(Text):
    """Accent-edged card: first line is the heading, the rest is body."""
    fill = CARD
    accent = ACCENT
    width = 0.92

    def _geometry(self, ctx):
        font = self.font
        w = min(self.width * ctx.W, ctx.flow_w) if self.width else ctx.flow_w
        pad = 14.0
        head, _, body = self.contents.partition("\n")
        body_lines = ctx.wrap(bold_runs(body), w - 2 * pad - 10, font) if body else []
        h = ctx.line_height(font) + len(body_lines) * ctx.line_height(font) + 2 * pad
        return w, pad, head, body_lines, h

    def render_flow(self, ctx):
        font = self.font
        w, pad, head, body_lines, h = self._geometry(ctx)
        x = ctx.flow_x + (ctx.flow_w - w) / 2
        ctx.fill_rect(x, ctx.y, w, h, self.fill, radius=8)
        ctx.fill_rect(x, ctx.y, 4, h, self.accent)
        ctx.text_block([bold_runs(head)], x + pad + 6, ctx.y + pad, w, font,
                       self.accent)
        if body_lines:
            ctx.text_block(body_lines, x + pad + 6, ctx.y + pad + ctx.line_height(font),
                           w, font, self.color)
        ctx.y += h + 16

    def height(self, ctx):
        return self._geometry(ctx)[4] + 16
