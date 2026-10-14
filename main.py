#!/usr/bin/env python3
"""Slidez compiler: .sldz -> PDF.

Usage:
    python main.py deck.sldz [-o out.pdf]
    python main.py deck.sldz --check     # verify only, no PDF written

To add your own templates/elements/fonts, write a plugin module with
@register / @register_font classes and add an import below.
"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

# --- plugins: add yours here ---
import plugins.basic            # common templates + elements
import plugins.fonts            # font families

from slidez.ast import (Image, Line, Rect, Ellipse, Arrow, Box, Text,
                        SlidezError, is_color, parse_color)
from slidez.parser import parse
from slidez.style import apply_style
from slidez.renderers.pdf import PDFRenderer

COLOR_PROPS = ("color", "border_color", "marker_color", "fill", "accent")
SHAPES = (Line, Rect, Ellipse, Arrow, Box)      # Size required
NEEDS_POSITION = (Rect, Ellipse, Arrow)         # no flow fallback


def _load_deck_theme(src_path: Path):
    """Convention: a theme.py sitting next to the deck is auto-imported,
    so each deck in presentations/ can carry its own plugin."""
    theme = src_path.parent / "theme.py"
    if not theme.exists():
        return
    import importlib.util
    name = "slidez_deck_theme_" + src_path.parent.name
    if name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(name, theme)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)


def verify(pres) -> str:
    """Deep checks beyond parsing/style: shapes complete, images exist,
    colors and backgrounds valid. Also collects non-fatal warnings
    (out-of-range Position/Size/Width) into pres.warnings."""
    ctx = SimpleNamespace(base_dir=pres.base_dir)
    images = 0
    for slide in pres.slides:
        bg = getattr(slide, "background", None)
        if bg:
            if is_color(bg):
                parse_color(bg)
            else:  # background image path
                p = Path(bg)
                if not p.is_absolute():
                    p = pres.base_dir / p
                if not p.exists():
                    line = getattr(slide, "_line", "?")
                    raise SlidezError(f"line {line}: background image not found: {p}")
        for el in slide.contents:
            line = getattr(el, "_line", "?")
            name = type(el).__name__
            if isinstance(el, SHAPES):
                if el.size is None:
                    raise SlidezError(f"line {line}: {name} requires Size")
                if el.position is None and isinstance(el, NEEDS_POSITION):
                    raise SlidezError(f"line {line}: {name} requires Position")
            if isinstance(el, Image):
                el.path(ctx)   # raises SlidezError with line if missing
                images += 1
            for prop in COLOR_PROPS:
                v = getattr(el, prop, None)
                if v:
                    parse_color(v)
            if el.position is not None and any(v < 0 or v > 1 for v in el.position):
                pres.warn(f"line {line}: {name}: Position {list(el.position)}"
                          " is outside 0-1 slide units — it will render off-slide")
            if el.size is not None and not isinstance(el, Text) \
                    and any(v < 0 or v > 1 for v in el.size):
                pres.warn(f"line {line}: {name}: Size {list(el.size)}"
                          " is outside 0-1 slide units — it will overflow the slide")
            if el.width is not None and (el.width < 0 or el.width > 1):
                pres.warn(f"line {line}: {name}: Width {el.width}"
                          " is outside 0-1 slide units — text will overflow its column")
    return images


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compile a .sldz presentation to PDF")
    ap.add_argument("input", help=".sldz source file")
    ap.add_argument("-o", "--output", help="output PDF path (default: <input>.pdf)")
    ap.add_argument("--check", "--dry-run", dest="check", action="store_true",
                    help="verify the deck only; don't write a PDF")
    args = ap.parse_args(argv)

    src_path = Path(args.input)
    if not src_path.exists():
        print(f"error: no such file: {src_path}", file=sys.stderr)
        return 1

    _load_deck_theme(src_path)
    try:
        pres = parse(src_path.read_text(encoding="utf-8"), src_path.parent)
        apply_style(pres)
        images = verify(pres)
        for w in pres.warnings:
            print(f"{src_path}: warning: {w}", file=sys.stderr)
        if args.check:
            plural = "" if len(pres.slides) == 1 else "s"
            imgs = "no images" if not images else f"{images} image{'s' if images != 1 else ''}"
            print(f"{src_path}: OK — {len(pres.slides)} slide{plural}, {imgs} (checked, no PDF written)")
            return 0
        out = args.output or str(src_path.with_suffix(".pdf"))
        PDFRenderer().render(pres, out)
    except (SlidezError, OSError, ValueError) as e:
        print(f"{src_path}: error: {e}", file=sys.stderr)
        return 1
    except RecursionError:
        print(f"{src_path}: error: deck structure too deeply nested", file=sys.stderr)
        return 1
    print(f"{out}: {len(pres.slides)} slides")
    return 0


if __name__ == "__main__":
    sys.exit(main())
