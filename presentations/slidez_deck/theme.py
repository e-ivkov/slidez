"""Slidez deck theme — the deck about Slidez, styled by a Slidez plugin.

Everything here is ordinary plugin code (see plugins/README.md):
a chrome mixin for footer/page numbers, template subclasses combining it,
and one custom element (Stat) written from scratch.
"""

from plugins.basic import ImageSideSlide, SectionSlide, TitleSlide, TwoColumnsSlide
from slidez.ast import Element, Slide, Text, Title, register, resolve_font

ACCENT = "#4CC38A"
BLUE = "#61AFEF"
MUTED = "#9AA7B0"
FOOTER_H = 516.0


class SlidezChrome:
    """Footer with wordmark, accent rule and page number on every slide.

    Also gives Titles their own look: Manrope bold, larger, brighter.
    """
    background = "media/bg_content.jpg"
    footer = True
    title_size = 40
    title_color = "#F5F8FA"

    def apply_style(self, style):
        explicit_font = {id(el): el.font for el in self.contents
                         if isinstance(el, Title)}
        super().apply_style(style)
        for el in self.contents:
            if not (isinstance(el, Title) and el.position is None):
                continue
            if not isinstance(explicit_font.get(id(el)), str):
                el.font = resolve_font("Manrope").with_size(el.font.size)
            if el.size is None:
                el.font = el.font.with_size(self.title_size)
            el.bold = True
            if el.color is None:
                el.color = self.title_color

    def render(self, ctx):
        super().render(ctx)
        if not self.footer:
            return
        ctx.draw_line(ctx.pad_l, FOOTER_H, ctx.W - ctx.pad_r, FOOTER_H,
                      "#232B33", 1.0)
        small = ctx.get_font("Manrope").with_size(11)
        ctx.text_block([[("slidez", True)]], ctx.pad_l, FOOTER_H + 10, 120,
                       small, ACCENT)
        num = ctx.get_font("Montserrat").with_size(11)
        w = ctx.runs_width([("n / n", False)], num)
        page = f"{ctx.slide_index} / {ctx.total}"
        ctx.text_block([[(page, False)]], ctx.W - ctx.pad_r - w, FOOTER_H + 10,
                       w, num, MUTED)


@register
class SlidezSlide(SlidezChrome, Slide):
    """Standard content slide."""


@register
class SlidezSection(SlidezChrome, SectionSlide):
    """Section intro: big centered title."""


@register
class SlidezTwoColumns(SlidezChrome, TwoColumnsSlide):
    """Two columns, chosen per element with `Column: 0|1`."""


@register
class SlidezImageRight(SlidezChrome, ImageSideSlide):
    """Text flows left, the `Role: image` (or first) image fills the right."""
    side = "right"


@register
class SlidezImageLeft(SlidezChrome, ImageSideSlide):
    side = "left"


@register
class SlidezTitleSlide(TitleSlide):
    """Deck opener/closer: adds a company line under Title + Subtitle."""
    background = "media/bg_title.jpg"

    roles = TitleSlide.roles + ("company",)
    title_pos = (0.30, 0.40)
    title_align_v = "center"
    title_align_h = "left"
    title_scale = 4.2            # 24 -> ~100pt
    subtitle_pos = (0.30, 0.56)
    subtitle_scale = 1.1
    subtitle_width = 0.42
    company_pos = (0.30, 0.78)
    company_width = 0.42
    company_scale = 0.8


@register
class Stat(Element):
    """Big number + caption. A from-scratch element (see plugins/README.md)."""
    number = ""
    caption = ""
    accent = ACCENT

    def set_inline(self, value):
        self.number = value

    def render_flow(self, ctx):
        big = ctx.get_font("Manrope").with_size(46)
        cap = ctx.get_font("Montserrat").with_size(15)
        num_runs = [(self.number, True)]
        w = max(ctx.runs_width(num_runs, big),
                ctx.runs_width([(self.caption, False)], cap))
        x = ctx.flow_x + (ctx.flow_w - w) / 2
        ctx.text_block([num_runs], x, ctx.y, w, big, self.accent, "center")
        ctx.text_block([[(self.caption, False)]], x, ctx.y + 58, w, cap,
                       self.color or MUTED, "center")
        ctx.y += 96

    def height(self, ctx):
        return 96
