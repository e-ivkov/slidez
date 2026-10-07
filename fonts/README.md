# Fonts in Slidez

How to use a built-in font, a font already on your machine, or add your
own. In a deck you only ever reference a **family name**:

```
Slides:
    Font: Manrope              # deck-wide default

Slide1:
    Text: "hello"
        Font: Georgia          # per-element override
        Bold: true             # uses the family's bold file
        Size: 24
```

A typo is reported with the full list of registered families — you never
get a silent fallback.

## The model

A family is registered by a plugin as a name (plus optional aliases) and
two TTF files — regular and bold:

```python
Font(("Name", "Alias"), "fonts/Name-Regular.ttf",   # regular
     "fonts/Name-Bold.ttf")                         # bold (optional)
```

- `Font: name` resolves case-insensitively, aliases included.
- Without a bold file, `Bold: true` just reuses the regular file.
- Registration lives in plugin modules imported by `main.py`
  (the built-ins are in `plugins/fonts.py`).

## Use a font from your machine

Give an **absolute path** — nothing needs to be copied into the repo:

```python
# plugins/fonts.py — or your own plugin imported in main.py
from slidez.ast import Font, register_font

register_font(Font(("Georgia",),
                   "/usr/share/fonts/TTF/Georgia-Regular.ttf",
                   "/usr/share/fonts/TTF/Georgia-Bold.ttf"))
```

Where fonts live:

| System | Path |
|---|---|
| Linux | `/usr/share/fonts`, `~/.local/share/fonts` — list with `fc-list \| grep -i georgia` |
| macOS | `/Library/Fonts`, `~/Library/Fonts` |
| Windows | `C:\Windows\Fonts` |

Keep machine fonts in a plugin you don't commit — decks that reference
them won't build elsewhere.

## Add your own font to the repo

1. Drop the `.ttf` files into `fonts/` (TrueType; fpdf2 does not support
   CFF/`.otf` outlines).
2. Register in `plugins/fonts.py`:

   ```python
   register_font(Font(("My Font", "MyFont"),
                      "fonts/MyFont-Regular.ttf",
                      "fonts/MyFont-Bold.ttf"))
   ```

3. Use it: `Font: My Font`.

Relative paths resolve from the **repository root** (unlike images, which
resolve next to the `.sldz` file).

Only ship fonts you may redistribute — OFL is ideal; note the source in
`fonts/LICENSES.md`.

## Variable fonts → static weights

Google Fonts and foundries ship variable fonts. fpdf2 renders only their
default instance, so instantiate the weights you need first (`fontTools`
is already installed as an fpdf2 dependency):

```python
from fontTools import ttLib
from fontTools.varLib.instancer import instantiateVariableFont

for weight, name in [(400, "Regular"), (700, "Bold")]:
    f = ttLib.TTFont("MyFont[wght].ttf")
    instantiateVariableFont(f, {"wght": weight},
                            inplace=True, updateFontNames=True)
    f.save(f"fonts/MyFont-{name}.ttf")
```

`inplace=True` matters — without it you silently save the untouched
default instance. Verify the result: the file's full name should read
`MyFont SemiBold`, not `MyFont Thin`.

## Bundled fonts

| Family | Files | License |
|---|---|---|
| Manrope | Regular, SemiBold, ExtraBold | SIL OFL 1.1 |
| Montserrat | Regular, SemiBold, Bold, ExtraBold | SIL OFL 1.1 |
| Liberation Sans / Serif | Regular, Bold | SIL OFL 1.1 |
| Liberation Mono / Courier New | Regular, Bold | SIL OFL 1.1 |
| DejaVu Sans Mono | Regular | Bitstream Vera |

Details and sources: [LICENSES.md](LICENSES.md).
