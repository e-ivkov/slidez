"""Common slide templates.

A template is just a Slide subclass: override apply_style to set child
defaults, render/height to change layout. Use it in .sldz by class name:

    TitleSlide:
        My big title
        subtitle line
        company / date line
"""

from slidez.ast import Bullets, Image, Slide, SlidezError, Text, Title, register


@register
class TitleSlide(Slide):
    """Title slide: positions text children by role tag.

    Base roles: `Role: title` and `Role: subtitle`. A `Title` element
    defaults to the title; untagged Texts fill roles in order. Add roles
    in a subclass by extending `roles` and defining `<role>_pos`
    (plus optional `_scale`, `_width`, `_align_v`, `_align_h`).
    """
    roles = ("title", "subtitle")
    title_pos = (0.06, 0.34)
    title_align_v = "center"
    title_align_h = "left"
    title_width = 0.88
    title_scale = 2.0
    subtitle_pos = (0.06, 0.56)
    subtitle_align_v = "top"
    subtitle_align_h = "left"
    subtitle_width = 0.60
    subtitle_scale = 1.1

    def _role_conf(self, role):
        pos = getattr(self, role + "_pos", None)
        if pos is None:
            raise SlidezError(
                f"{type(self).__name__}: role '{role}' needs a"
                f" {role}_pos class attribute")
        return (pos,
                getattr(self, role + "_scale", 1.0),
                getattr(self, role + "_width", None),
                getattr(self, role + "_align_v", "top"),
                getattr(self, role + "_align_h", "left"))

    def apply_style(self, style):
        super().apply_style(style)
        texts = [el for el in self._flow_children() if isinstance(el, Text)]
        for el in texts:
            if el.role is None and isinstance(el, Title):
                el.role = "title"
            if el.role is not None and el.role not in self.roles:
                raise SlidezError(
                    f"Unknown Role '{el.role}' for {type(self).__name__}"
                    f" (expected one of: {', '.join(self.roles)})")
        free = [r for r in self.roles if r not in
                {el.role for el in texts if el.role}]
        for el in texts:
            if el.role is None and free:
                el.role = free.pop(0)
        for el in texts:
            if el.role is None:
                continue          # more texts than roles: leave in flow
            pos, scale, width, align_v, align_h = self._role_conf(el.role)
            if el.position is None:
                el.position = pos
            if el.align_v is None:
                el.align_v = align_v
            if el.align_h is None:
                el.align_h = align_h
            if el.width is None and width is not None:
                el.width = width
            if el.size is None:
                el.font = el.font.with_size(el.font.size * scale)


@register
class SectionSlide(TitleSlide):
    """Section intro: big centered title."""
    title_pos = (0.06, 0.42)
    title_align_v = "center"
    title_align_h = "center"
    title_scale = 2.8


@register
class BulletSlide(Slide):
    """Title on top, bullets below (the plain Slide flow already does this;
    subclass this to add e.g. an accent line or different spacing)."""


@register
class TwoColumnsSlide(Slide):
    """Flow children go into two columns, chosen with `Column: 0|1`."""
    gap = 40.0

    def render(self, ctx):
        self._draw_background(ctx)
        cols = ([], [])
        absolutes = []
        headers = []
        for el in self.contents:
            if el.position is not None:
                absolutes.append(el)
            elif isinstance(el, Title):
                headers.append(el)
            else:
                cols[el.column or 0].append(el)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        ctx.y = ctx.pad_t
        for el in headers:
            el.render(ctx)
        body_top = ctx.y + 14   # below the measured header block
        col_w = (ctx.content_w - self.gap) / 2
        for i, col in enumerate(cols):
            ctx.flow_x = ctx.pad_l + i * (col_w + self.gap)
            ctx.flow_w = col_w
            ctx.y = body_top
            for el in col:
                el.render(ctx)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        for el in absolutes:
            el.render(ctx)


@register
class ImageSideSlide(Slide):
    """Title on top; an Image fills one side, text flows on the other.

    The side image is the one tagged `Role: image` (or the first Image).
    Its `Size: [fraction]` (width fraction) is honored if set, otherwise
    `image_fraction` of the content width is used.
    """
    side = "left"
    image_fraction = 0.46
    image_align_v = "top"      # top | center within the body area
    body_pad = 12.0            # space below the header before body starts
    gap = 40.0

    def render(self, ctx):
        self._draw_background(ctx)
        headers, images, texts, absolutes = [], [], [], []
        for el in self.contents:
            if el.position is not None:
                absolutes.append(el)
            elif isinstance(el, Image):
                images.append(el)
            elif isinstance(el, Title):
                headers.append(el)
            else:
                texts.append(el)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        ctx.y = ctx.pad_t
        for el in headers:
            el.render(ctx)
        body_top = ctx.y + self.body_pad
        body_h = ctx.H - ctx.pad_b - body_top
        tagged = [im for im in images if im.role == "image"]
        img = (tagged or images or [None])[0]
        img_w = ((img.size[0] if img and img.size else self.image_fraction)
                 * ctx.content_w)
        text_w = ctx.content_w - img_w - self.gap
        if self.side == "left":
            img_x, txt_x = ctx.pad_l, ctx.pad_l + img_w + self.gap
        else:
            txt_x, img_x = ctx.pad_l, ctx.pad_l + text_w + self.gap
        if img:
            # size the image on the same basis as the slot (content width)
            px, py = ctx.image_size(img.path(ctx))
            w = img_w
            h = w * py / px
            if h > body_h:
                h = body_h
                w = h * px / py
            img_y = body_top if self.image_align_v == "top" \
                else body_top + (body_h - h) / 2
            ctx.image(img.path(ctx), img_x + (img_w - w) / 2, img_y, w, h)
        ctx.flow_x, ctx.flow_w = txt_x, text_w
        ctx.y = body_top
        for el in texts:
            el.render(ctx)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        for el in absolutes:
            el.render(ctx)
        for img in images[1:]:
            img.render(ctx)


@register
class ImageLeftSlide(ImageSideSlide):
    """Image on the left, text on the right."""
    side = "left"


@register
class ImageRightSlide(ImageSideSlide):
    """Image on the right, text on the left."""
    side = "right"


@register
class ImageSlide(Slide):
    """Title on top, the first Image centered in the remaining space."""

    def render(self, ctx):
        self._draw_background(ctx)
        ctx.flow_x, ctx.flow_w = ctx.pad_l, ctx.content_w
        ctx.y = ctx.pad_t
        images = []
        for el in self.contents:
            if el.position is None and isinstance(el, Image):
                images.append(el)
            else:
                el.render(ctx)
        for img in images:
            avail_h = ctx.H - ctx.pad_b - ctx.y
            w, h = img._fit(ctx, ctx.flow_w, avail_h)
            x = ctx.flow_x + (ctx.flow_w - w) / 2
            ctx.image(img.path(ctx), x, ctx.y, w, h)
            ctx.y += h + 12


# --- extra elements ---

@register
class Code(Text):
    """Monospace text block. Bare lines keep their relative indentation
    (4 spaces per level), `""` is an empty line. Default width 0.72;
    set `Fill: #hex` for a background box."""
    default_font = "Mono"
    fill = None
    padding = None
    width = 0.72

    def render_flow(self, ctx):
        font = self.font
        w = self._flow_width(ctx)
        pad = self.padding if self.padding is not None else font.size * 0.6
        lines = ctx.wrap(self._runs(), w - 2 * pad, font)
        h = len(lines) * ctx.line_height(font) + (2 * pad if self.fill else 0)
        x = ctx.flow_x + (ctx.flow_w - w) / 2 if self.align_h == "center" else ctx.flow_x
        if self.fill:
            ctx.fill_rect(x, ctx.y, w, h, self.fill, radius=6)
            ctx.text_block(lines, x + pad, ctx.y + pad, w - 2 * pad, font, self.color, "left")
        else:
            ctx.text_block(lines, x, ctx.y, w, font, self.color, "left")
        ctx.y += h + font.size * 0.7

    def height(self, ctx):
        font = self.font
        w = self._flow_width(ctx)
        pad = self.padding if self.padding is not None else font.size * 0.6
        lines = ctx.wrap(self._runs(), w - 2 * pad, font)
        return len(lines) * ctx.line_height(font) + (2 * pad if self.fill else 0) + font.size * 0.7
