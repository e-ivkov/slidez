# Slidez

[![ci](https://github.com/e-ivkov/slidez/actions/workflows/ci.yml/badge.svg)](https://github.com/e-ivkov/slidez/actions/workflows/ci.yml)

A minimalistic language for writing presentations and a compiler from it to a
single portable PDF. No browser, no HTML/CSS — just text, small Python core,
and plugins.

```
Slides:
    Font: Manrope

Slide1:
    Title: Why Slidez
    Bullets:
        text file in, PDF out
        templates and fonts are plain Python subclasses
            write your own in 10 lines
```

## Quick start

```
git clone https://github.com/e-ivkov/slidez.git
cd slidez
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py example.sldz
.venv/bin/python main.py deck.sldz --check   # verify only, no PDF written
.venv/bin/python main.py presentations/slidez_deck/deck.sldz  # the about-Slidez deck
.venv/bin/python -m unittest discover -s tests
```

`--check` (alias `--dry-run`) parses, applies the style cascade, and
validates shapes (missing `Size`/`Position`), image paths, backgrounds and
colors — catching every deck error without rendering.

The about-deck is the full showcase: it uses every element (shapes, code,
images), roles, two-column and image-side templates, a chrome mixin for its
footer — and its look comes entirely from its own plugin
(`presentations/slidez_deck/theme.py`), including a custom `Stat` element.

## Language

YAML-like, indentation-based, no dashes. `//` line and `/* */` block
comments. Values: `"strings"` (with `\n` escapes), numbers, `true/false`,
`[a, b]` lists, `#RRGGBB` colors, `left|center|right` enums.

- **Top level**: `Slides:` sets global style; every other key starts a slide,
  in document order. The key is looked up in the class registry: use your own
  template class name (`TitleSlide:`) or anything else for a plain `Slide`.
- **Inside a slide**: bare lines become a multiline `Text` (blank line
  separates); `Key:` lines become elements (any registered class) or style
  properties (`Font`, `Size`, `Color`, `Background` cascade to children).
- **Inside an element**: `Key: value` sets a property (`Position`, `AlignH`,
  ...). Unknown keys are treated as verbatim text — bullet items and code
  lines may freely contain colons, numbers or booleans (`Score: 100`). A
  structured value on a name close to a real property is reported as a typo
  instead. Deeper-indented bare lines keep their relative indentation
  (4 spaces per level); `""` is an empty line.
- `//` comments only start at the beginning of a line or after whitespace,
  so bare URLs (`https://...`) are safe.
- String escapes: `\n`, `\t`, `\"` and `\\` (use `\\` in Windows paths).
- Backticks for verbatim: `` `C:\new\table.png` `` values (nothing is
  escaped or parsed) and ` ``` ` fenced blocks for multi-line content —
  code, deck-source samples, anything. Inside a fence no line is parsed.
- Rule of thumb: plain prose and simple code need no quoting — the parser
  disambiguates (URLs, colons in text). When in doubt, backtick it.
- `**bold**` spans inside text. `Position`/`Size` are in 0-1 slide units.
- Colors: `#RRGGBB` or names (`white`, `red`, ...) — including for
  `Background`; a non-color `Background` is an image path.
- Errors are reported at parse time with line numbers and did-you-mean
  hints: `line 3: unknown property 'Positon' for Text — did you mean 'Position'?`

Core elements (`slidez/ast.py`): `Text`, `Title`, `Bullets`, `Image`, `Line`,
`Rect`, `Ellipse`, `Arrow`. Common element properties: `Position`, `Size`,
`Width`, `AlignH`, `AlignV`, `Color`, `BorderColor`, `BorderWidth`, `Column`,
`Role` (tag an element for a template, e.g. `Role: title`, `Role: image`).

Code blocks don't need escaped strings — just indent them, or fence them:

```
Slide:
    Code:
        def render_flow(self, ctx):
            ctx.text_block(lines, x, y, w,
                           font, color)
```

For code that itself looks like deck source (`Font:`, `Size:` at line
starts), use a fence — content between the ` ``` ` lines is verbatim.

## Plugins (templates, elements, fonts)

Everything stylistic lives in plugins; the core stays tiny. Write a module,
add an import in `main.py`, done — **see [plugins/README.md](plugins/README.md)
for the full plugin-writing guide** (fonts, custom elements, templates,
chrome mixins, and the `ctx` drawing API cheat-sheet).

```python
# plugins/my_style.py
from slidez.ast import Slide, Text, Title, register

@register
class SectionSlide(Slide):          # use as "SectionSlide:" in .sldz
    background = "#101820"
    def apply_style(self, style):
        super().apply_style(style)
        for el in self.contents:
            if isinstance(el, Title) and el.size is None:
                el.font = el.font.with_size(64)
```

- **Template** = `Slide` subclass (layout, chrome, defaults).
  See `plugins/basic.py`: `TitleSlide` (positions `Role: title|subtitle`
  tagged texts; subclasses can add roles), `SectionSlide`, `BulletSlide`,
  `TwoColumnsSlide`, `ImageLeftSlide`/`ImageRightSlide` (image tagged
  `Role: image` or the first one, on one side; `Size: [fraction]` sets
  image width; text flows the other side), `ImageSlide`, `Code`. See
  `presentations/slidez_deck/theme.py` for a mixin with footer/page
  numbers and deck-specific overrides.
- **Element** = `Element` subclass with class attributes as properties.
- **Font** = `register_font(Font(("MyFont",), "fonts/MyFont.ttf", bold_file=...))`.

## Project layout

```
main.py                 CLI: python main.py deck.sldz [-o out.pdf]
slidez/ast.py           elements, Slide, Presentation, Font, registries
slidez/parser.py        indentation-based parser
slidez/style.py         style cascade (Slides: -> slide -> element)
slidez/renderers/       Renderer interface + PDF renderer (fpdf2, 960x540pt)
plugins/                basic templates + fonts
fonts/                  bundled TTFs (see fonts/LICENSES.md)
presentations/slidez_deck/  about-deck: .sldz + media + theme plugin
tests/                  parser/style unittests
```

## Fonts

`fonts/` bundles Manrope, Montserrat, Liberation and DejaVu files under their
respective licenses (OFL / Bitstream Vera) — see `fonts/LICENSES.md`.
**[fonts/README.md](fonts/README.md)** explains how to use a font from your
machine, add your own, and turn variable fonts into static weights.

## License

MIT — see [LICENSE](LICENSE). Bundled fonts keep their own licenses.

## Notes

- Renderer interface is deliberately abstract (`slidez/renderers/`): a
  viewer or HTML export can be added without touching the core.
