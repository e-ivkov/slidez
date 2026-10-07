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
import presentations.slidez_deck.theme   # the about-Slidez deck theme

from slidez.ast import (Image, Line, Rect, Ellipse, Arrow, SlidezError,
                        is_color, parse_color)
from slidez.parser import parse
from slidez.style import apply_style
from slidez.renderers.pdf import PDFRenderer

COLOR_PROPS = ("color", "border_color", "marker_color", "fill", "accent")
SHAPES = (Line, Rect, Ellipse, Arrow)
NEEDS_POSITION = (Rect, Ellipse, Arrow)


def verify(pres) -> str:
    """Deep checks beyond parsing/style: shapes complete, images exist,
    colors and backgrounds valid."""
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
            if isinstance(el, SHAPES):
                if el.size is None:
                    raise SlidezError(f"line {line}: {type(el).__name__} requires Size")
                if el.position is None and isinstance(el, NEEDS_POSITION):
                    raise SlidezError(f"line {line}: {type(el).__name__} requires Position")
            if isinstance(el, Image):
                el.path(ctx)   # raises SlidezError with line if missing
                images += 1
            for prop in COLOR_PROPS:
                v = getattr(el, prop, None)
                if v:
                    parse_color(v)
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

    try:
        pres = parse(src_path.read_text(encoding="utf-8"), src_path.parent)
        apply_style(pres)
        images = verify(pres)
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
    print(f"{out}: {len(pres.slides)} slides")
    return 0


if __name__ == "__main__":
    sys.exit(main())
