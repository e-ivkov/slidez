# Writing Slidez plugins

A plugin is a plain Python module. There is no plugin API to learn — you
subclass the same classes the core uses and register them. Put your module
anywhere importable and reference it in `main.py`:

```python
# main.py
import plugins.fonts        # builtin: font families
import plugins.basic        # builtin: templates + elements
import my_plugin            # <-- yours
```

Anything `@register`-ed becomes usable in `.sldz` by its class name.
There are three things you can add: **fonts**, **elements**, **slides
(templates)**. All examples below are complete working plugins.

```python
# my_plugin.py — common imports
from slidez.ast import (Element, Font, Image, Slide, SlidezError,
                        Text, Title, register, register_font)
```

---

## 1. Fonts

```python
register_font(Font(("My Font", "MyFont"),          # name + aliases
                   "fonts/MyFont-Regular.ttf",     # relative to repo root
                   "fonts/MyFont-Bold.ttf"))       # bold variant (optional)
```

Use in a deck: `Font: My Font`. Case-insensitive; aliases resolve too.
The renderer preloads every registered family automatically.

## 2. Elements

### 2a. The one-liner: defaults via inheritance

Class attributes double as language properties (PascalCase in `.sldz`,
snake_case in Python). Subclass, tweak — done:

```python
@register
class Quote(Text):
    font = "Times New Roman"
    size = 22
    color = "#404A55"
    italic_note = None          # any new attr becomes `Note:` in .sldz
```

```
Quote: "Simple, heteroplastic power."
    Note: "G. K. Chesterton"
```

### 2b. Custom rendering

Override `render_abs` (when the user gave a `Position`) and/or
`render_flow` (placed by the slide's flow). Drawing goes through the
`ctx` object (cheat-sheet at the bottom):

```python
@register
class Badge(Element):
    text = ""
    fill = "#1E88E5"

    def set_inline(self, value):          # Element: "value" part
        self.text = value

    def render_flow(self, ctx):
        font = ctx.get_font("Default").with_size(14)
        w = ctx.runs_width([(self.text, True)], font) + 24
        ctx.fill_rect(ctx.flow_x, ctx.y, w, 20, self.fill, radius=10)
        ctx.draw_runs(ctx.flow_x + 12, ctx.y + 14.5,
                      [(self.text, True)], font, "#FFFFFF")
        ctx.y += 28                        # advance the flow cursor!

    def height(self, ctx):                 # what templates measure
        return 28
```

### 2c. Eating bare lines

Elements can consume indented bare lines from the deck:

```python
@register
class KeyValue(Text):
    """Key: value lines become a two-column listing."""
    def add_bare(self, node, level=0):
        k, _, v = node.value.partition(": ")
        self._lines.append((k.strip(), v.strip()))
        for child in node.children:        # deeper lines keep nesting
            if child.key is None:
                self.add_bare(child, level + 1)

    def finalize(self):                    # runs when the block closes
        self.pairs = list(self._lines)     # Text.finalize would join str lines
        self._lines = []
```

`set_inline` handles `MyThing: "value"`, `add_bare` handles child lines,
`finalize()` runs exactly once when the element's block closes — join or
validate your collected lines there (see `Text.finalize`).

## 3. Templates (Slide subclasses)

A template controls layout, chrome and child defaults. Three tools,
used alone or together:

### 3a. Style pass — set child defaults, position by role

Runs after parsing, before rendering; fonts/colors are resolved here.

```python
@register
class QuoteSlide(Slide):
    background = "#101820"

    def apply_style(self, style):
        super().apply_style(style)                 # always call first
        for el in self._flow_children():
            if isinstance(el, Title) and el.size is None:
                el.font = el.font.with_size(40)    # bump unset sizes
            if el.color is None:
                el.color = "#D0D8DE"
```

Tag-based selection: elements can carry `Role: xxx` (`el.role`), and
`Position` you set yourself in `apply_style` makes them absolute:

```python
    # inside apply_style, after super():
    for el in self.contents:
        if el.role == "watermark":
            el.position = (0.88, 0.93)             # -> rendered absolutely
            el.size = 12 if el.size is None else el.size
```

See `TitleSlide` in `plugins/basic.py` for the full pattern: it defines
`roles = ("title", "subtitle")` with `<role>_pos` (required) and optional
`_scale/_width/_align_v/_align_h` attributes, tag validation with a
helpful error, and order fallback. Subclasses extend it — this is exactly
how the about-deck's opener adds a third slot:

```python
@register
class SlidezTitleSlide(TitleSlide):
    background = "media/bg_title.jpg"
    roles = TitleSlide.roles + ("company",)
    company_pos = (0.30, 0.78)
    company_scale = 0.8
    # ...plus overrides for title_*/subtitle_*
```

### 3b. Render pass — own layout

Reflow children yourself with the column state `ctx.flow_x/flow_w/ctx.y`,
then let elements draw. Steal from `TwoColumnsSlide` / `ImageSideSlide`:

```python
@register
class ChatSlide(Slide):
    def render(self, ctx):
        self._draw_background(ctx)                 # honors color or image
        ctx.y = ctx.pad_t
        for el in self.contents:
            if el.position is not None:            # user-placed: skip flow
                el.render(ctx)
                continue
            ctx.flow_x = ctx.pad_l + (0 if el.column == 0 else 420)
            ctx.flow_w = 400
            el.render(ctx)                         # element advances ctx.y
```

### 3c. Chrome mixin — shared decorations (footer, page numbers)

```python
class MyChrome:
    def render(self, ctx):
        super().render(ctx)                        # MRO does the magic
        ctx.text_block([[("© Me 2026", False)]], 800, 514, 100,
                       ctx.get_font("Default").with_size(9), "#888888")

@register
class MySlide(MyChrome, Slide): ...
@register
class MyTwoColumns(MyChrome, TwoColumnsSlide): ...
```

`ctx.slide_index` (1-based) and `ctx.total` are available for numbering.
Real example: `SlidezChrome` in `presentations/slidez_deck/theme.py`
(footer, accent rule, page counter).

---

## How the pieces fit

```
.sldz text
   |  parser (you rarely touch this)
   v
Presentation -> Slide -> Element tree          classes = yours
   |  apply_style(style dict)  top-down: fonts resolved, defaults applied
   v
Renderer -> Slide.render(ctx) -> Element.render(ctx)   ctx = drawing API
```

**Style cascade** (`Slides:` block -> slide -> element): a value set
lower always wins; `None` means inherit. In `apply_style(style)` you get
the merged dict (`font`, `size`, `color`, `background`) — always
`super().apply_style(style)` first, then mutate children.

**Property rules**: public, non-callable class attrs are language
properties. Prefix with `_` to hide, with `default_` for "class default,
not a language property" (`default_font`, `default_size`, `default_bold`
are honored by `Text`).

**Geometry**: `Position`/`Size`/`Width` are 0-1 fractions of the slide
(960x540 pt). Everything you draw in `render` is in points.

## ctx cheat-sheet

| | |
|---|---|
| `ctx.W, ctx.H` | slide size in pt (960, 540) |
| `ctx.pad_l/r/t/b` | page margins, pt |
| `ctx.flow_x, ctx.flow_w, ctx.y` | current flow column + cursor |
| `ctx.slide_index, ctx.total` | numbering for chrome |
| `ctx.base_dir` | deck directory (resolve media paths against it) |
| `ctx.fonts` | registered families (dict, lowercase names) |
| `ctx.get_font(name)` | resolve a family name to a `Font`, then `.with_size(n)` |
| `ctx.wrap(runs, w, font)` | wrap `[(text, bold), ...]` into lines |
| `ctx.runs_width(runs, font)` | measured width, pt |
| `ctx.text_block(lines, x, y, w, font, color, align_h)` | draw wrapped lines, returns height |
| `ctx.draw_runs(x, baseline_y, runs, font, color)` | one line of mixed bold runs |
| `ctx.line_height(font)` / `ctx.baseline_offset(font)` | line metrics |
| `ctx.fill_rect(x, y, w, h, fill, radius, border, bw)` | rect (any arg optional) |
| `ctx.ellipse(...)`, `ctx.polygon(pts, fill, ...)` | shapes |
| `ctx.draw_line(x1, y1, x2, y2, color, width, dash)` | line |
| `ctx.image(path, x, y, w, h)` / `ctx.image_size(path)` | images |

Colors: `"#RRGGBB"` strings or names (`red`, `white`, ...).

## Checklist for a new plugin

1. Module imports clean? `python -c "import my_plugin"`
2. Registered names don't collide? (`ELEMENTS`, `FONTS` in `slidez.ast`)
3. Deck uses it: `python main.py deck.sldz`
4. Optional: a unittest next to it — `parse()` a small deck string,
   `apply_style()`, assert on the tree (see `tests/test_parser.py`).
