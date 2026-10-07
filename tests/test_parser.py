"""Parser and style cascade tests (stdlib unittest, no extra deps)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slidez import ELEMENTS, Font, SlidezError, parse, register, register_font
from slidez.style import apply_style
import plugins.basic  # noqa: F401  registers templates + Code
from plugins.basic import TitleSlide

register_font(Font(("TestSans",), "fonts/Manrope-Regular.ttf"))


@register
class CompanySlide(TitleSlide):
    """Test template: adds a company role on top of title/subtitle."""
    roles = TitleSlide.roles + ("company",)
    company_pos = (0.06, 0.70)
    company_scale = 0.9

DECK = """
Slides:
    Font: TestSans
    Size: 20
    Color: "#102030"

Slide1:
    Font: TestSans

    "quoted bare"

    first line
    second line

    Text: "shorthand"
    Title: "a title"

    Text: "with props"
        Position: [0.5, 0.5]
        AlignH: center

    Text:
        Contents: "block form"
        Size: 24

    Bullets:
        one
        two
            nested
        Marker: "-"

    Image: "media/x.png"

Slide2:
    // MyText: would fail, not registered
    Text: "ok"
"""


class TestParser(unittest.TestCase):
    def setUp(self):
        self.pres = parse(DECK, base_dir=Path("."))

    def test_structure(self):
        self.assertEqual(len(self.pres.slides), 2)
        self.assertEqual(self.pres.style["size"], 20)
        self.assertEqual(self.pres.style["color"], "#102030")

    def test_bare_grouping(self):
        texts = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Text"]
        quoted = [t for t in texts if t.contents == "quoted bare"]
        self.assertEqual(len(quoted), 1)
        multiline = [t for t in texts if t.contents == "first line\nsecond line"]
        self.assertEqual(len(multiline), 1)

    def test_shorthand_and_props(self):
        texts = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Text"]
        wp = [t for t in texts if t.contents == "with props"]
        self.assertEqual(wp[0].position, (0.5, 0.5))
        self.assertEqual(wp[0].align_h, "center")

    def test_block_form(self):
        texts = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Text"]
        bf = [t for t in texts if t.contents == "block form"]
        self.assertEqual(bf[0].size, 24)

    def test_bullets(self):
        b = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Bullets"][0]
        self.assertEqual(b.items, [(0, "one"), (0, "two"), (1, "nested")])
        self.assertEqual(b.marker, "-")

    def test_inline_value(self):
        img = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Image"][0]
        self.assertEqual(img.source, "media/x.png")

    def test_style_cascade(self):
        apply_style(self.pres)
        texts = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Text"]
        bf = [t for t in texts if t.contents == "block form"][0]
        self.assertEqual(bf.font.size, 24)          # own
        self.assertEqual(bf.font.family, "TestSans")
        sh = [t for t in texts if t.contents == "shorthand"][0]
        self.assertEqual(sh.font.size, 20)          # inherited from Slides
        title = [el for el in self.pres.slides[0].contents if type(el).__name__ == "Title"][0]
        self.assertEqual(title.font.size, 20)       # global style beats class default
        self.assertTrue(title.bold)

    def test_title_default_size(self):
        pres = parse('S:\n    Title: "t"', base_dir=Path("."))
        apply_style(pres)
        self.assertEqual(pres.slides[0].contents[0].font.size, 30)

    def test_custom_class(self):
        @register
        class MyText(ELEMENTS["Text"]):
            align_h = "center"
        pres = parse("S:\n    MyText: \"hi\"", base_dir=Path("."))
        el = pres.slides[0].contents[0]
        self.assertEqual(type(el).__name__, "MyText")
        self.assertEqual(el.contents, "hi")

    def test_comments_and_values(self):
        pres = parse('S: // trailing\n    Text: "x" /* inline */\n        Bold: true\n'
                     '        Dash: [3, 2]\n        Size: 2.5\n', base_dir=Path("."))
        t = pres.slides[0].contents[0]
        self.assertIs(t.bold, True)
        self.assertEqual(t.dash, (3, 2))
        self.assertEqual(t.size, 2.5)

    def test_unknown_key_becomes_text(self):
        # inside an element, unknown keys with string values are content
        pres = parse('S:\n    Text: "x"\n        Nope: something', base_dir=Path("."))
        self.assertEqual(pres.slides[0].contents[0].contents, "x\nNope: something")

    def test_unknown_element(self):
        with self.assertRaises(SlidezError):
            parse('S:\n    Bogus: "x"', base_dir=Path("."))

    def test_bad_indent(self):
        with self.assertRaises(SlidezError):
            parse('S:\n    Text: "x"\n          Size: 2\n       Bold: true', base_dir=Path("."))

    def test_tabs_rejected(self):
        with self.assertRaises(SlidezError):
            parse('S:\n\tText: "x"', base_dir=Path("."))

    def test_bare_indent_preserved(self):
        pres = parse('S:\n    Code:\n        line one\n            indented\n'
                     '        line two\n        ""\n        after blank', base_dir=Path("."))
        code = pres.slides[0].contents[0]
        self.assertEqual(code.contents,
                         "line one\n    indented\nline two\n\nafter blank")

    def test_code_lines_with_colons_verbatim(self):
        pres = parse('S:\n    Code:\n        ON orders(customer_id);\n'
                     '        Checkpoint: не блокирующий', base_dir=Path("."))
        self.assertEqual(pres.slides[0].contents[0].contents,
                         "ON orders(customer_id);\nCheckpoint: не блокирующий")


class TestTemplates(unittest.TestCase):
    def setUp(self):
        register_font(Font(("TestSans",), "fonts/Manrope-Regular.ttf"))
        import plugins.basic  # noqa: F401  registers templates

    def test_title_slide_roles(self):
        # order fallback: 1st=title, 2nd=subtitle; 3rd has no role -> flows
        deck = ('Slides:\n    Font: TestSans\n    Size: 20\n'
                'TitleSlide:\n    Text: "Big"\n    Text: "Sub"\n    Text: "Co"\n')
        pres = parse(deck, base_dir=Path("."))
        apply_style(pres)
        title, sub, co = pres.slides[0].contents
        self.assertEqual(title.position, (0.06, 0.34))
        self.assertEqual(title.align_v, "center")
        self.assertAlmostEqual(title.font.size, 40)   # 20 * title_scale
        self.assertEqual(sub.position, (0.06, 0.56))
        self.assertAlmostEqual(sub.font.size, 22)     # 20 * subtitle_scale
        self.assertIsNone(co.role)                    # base has 2 roles only
        self.assertIsNone(co.position)
        self.assertEqual(co.font.size, 20)            # untouched

    def test_title_slide_extra_role_via_subclass(self):
        deck = ('Slides:\n    Font: TestSans\n    Size: 20\n'
                'CompanySlide:\n    Text: "Big"\n    Text: "Sub"\n    Text: "Co"\n')
        pres = parse(deck, base_dir=Path("."))
        apply_style(pres)
        title, sub, co = pres.slides[0].contents
        self.assertEqual(co.role, "company")
        self.assertEqual(co.position, (0.06, 0.70))
        self.assertAlmostEqual(co.font.size, 18)      # 20 * company_scale

    def test_title_slide_role_tags(self):
        # explicit tags win over order
        deck = ('Slides:\n    Font: TestSans\n'
                'CompanySlide:\n    Text: "Sub"\n        Role: subtitle\n'
                '    Text: "Big"\n        Role: title\n'
                '    Text: "Co"\n        Role: company\n')
        pres = parse(deck, base_dir=Path("."))
        apply_style(pres)
        sub, big, co = pres.slides[0].contents   # document order
        self.assertEqual(big.role, "title")
        self.assertEqual(big.position, (0.06, 0.34))
        self.assertEqual(sub.position, (0.06, 0.56))
        self.assertEqual(co.position, (0.06, 0.70))

    def test_base_title_slide_rejects_extra_role(self):
        deck = 'TitleSlide:\n    Text: "x"\n        Role: company\n'
        pres = parse(deck, base_dir=Path("."))
        with self.assertRaises(SlidezError):
            apply_style(pres)

    def test_title_element_is_title_role(self):
        deck = 'TitleSlide:\n    Title: "T"\n    Text: "S"\n'
        pres = parse(deck, base_dir=Path("."))
        apply_style(pres)
        t, s = pres.slides[0].contents
        self.assertEqual(t.role, "title")
        self.assertEqual(s.role, "subtitle")

    def test_unknown_role_rejected(self):
        deck = 'TitleSlide:\n    Text: "x"\n        Role: bogus\n'
        pres = parse(deck, base_dir=Path("."))
        with self.assertRaises(SlidezError):
            apply_style(pres)

    def test_code_default_width(self):
        pres = parse('S:\n    Code:\n        x = 1', base_dir=Path("."))
        self.assertEqual(pres.slides[0].contents[0].width, 0.72)


class TestErrorReporting(unittest.TestCase):
    """Errors should be SlidezError, with line numbers and suggestions."""

    def assertErr(self, src, *fragments):
        with self.assertRaises(SlidezError) as cm:
            apply_style(parse(src, base_dir=Path(".")))
        msg = str(cm.exception)
        for frag in fragments:
            self.assertIn(frag, msg)
        return msg

    def test_unterminated_string(self):
        self.assertErr('S:\n    Text: "oops', "Unterminated string", "line 2")

    def test_unclosed_list(self):
        self.assertErr('S:\n    Text: "x"\n        Position: [0.5, 0.5',
                       "Unclosed list", "line 3")

    def test_unclosed_block_comment(self):
        self.assertErr('S:\n    Text: "a"\n/* never closed\nS2:\n    Text: "b"',
                       "Unclosed /* comment", "line 3")

    def test_bad_position_values(self):
        msg = self.assertErr('S:\n    Image: "m.png"\n        Position: [left, top]',
                             "line 3", "'position' expects two numbers")
        self.assertIn("'left'", msg)

    def test_bad_hex_color(self):
        self.assertErr('S:\n    Text: "x"\n        Color: "#GGHHII"',
                       "line 3", "expects a color")

    def test_bad_align(self):
        self.assertErr('S:\n    Text: "x"\n        AlignH: middle',
                       "line 3", "left, center or right")

    def test_bad_text_size(self):
        self.assertErr('S:\n    Text: "x"\n        Size: big',
                       "line 3", "'size' expects a number")

    def test_bad_bool(self):
        self.assertErr('S:\n    Text: "x"\n        Bold: yes',
                       "line 3", "true or false")

    def test_typo_property_suggested(self):
        msg = self.assertErr('S:\n    Text: "x"\n        Positon: [0.5, 0.5]',
                             "unknown property", "line 3")
        self.assertIn("Positon", msg)
        self.assertIn("Position", msg)  # the suggestion

    def test_typo_element_suggested(self):
        msg = self.assertErr('S:\n    Bullet: "x"', "unknown", "line 2")
        self.assertIn("Bullets", msg)

    def test_typo_style_key_suggested(self):
        msg = self.assertErr('Slides:\n    Fontt: Manrope\nS:\n    Text: "x"',
                             "Unknown style key", "line 2")
        self.assertIn("Font", msg)

    def test_empty_deck_rejected(self):
        self.assertErr("// nothing here\n", "No slides")

    def test_top_level_bare_text_rejected(self):
        self.assertErr("just some text\n", "line 1", "Bare text at top level")

    def test_unknown_font_has_line(self):
        # points at the element that carries the bad Font
        self.assertErr('S:\n    Text: "x"\n        Font: Nope',
                       "line 2", "Unknown font")

    def test_unknown_element_value_still_text(self):
        # string values stay verbatim content (code/prose with colons)
        pres = parse('S:\n    Code:\n        ON orders(customer_id);\n'
                     '        Note: hello', base_dir=Path("."))
        self.assertEqual(pres.slides[0].contents[0].contents,
                         "ON orders(customer_id);\nNote: hello")

    def test_cli_reports_error_cleanly(self):
        import tempfile
        import main as main_mod
        with tempfile.NamedTemporaryFile("w", suffix=".sldz", delete=False) as f:
            f.write('S:\n    Text: "oops')
            path = f.name
        self.assertEqual(main_mod.main([path]), 1)

    def test_cli_check_ok(self):
        import tempfile
        import main as main_mod
        with tempfile.NamedTemporaryFile("w", suffix=".sldz", delete=False) as f:
            f.write('S:\n    Text: "fine"')
            path = f.name
        self.assertEqual(main_mod.main([path, "--check"]), 0)
        self.assertFalse(Path(path).with_suffix(".pdf").exists())

    def test_cli_check_catches_missing_image(self):
        import tempfile
        import main as main_mod
        with tempfile.NamedTemporaryFile("w", suffix=".sldz", delete=False) as f:
            f.write('S:\n    Image: "ghost.png"')
            path = f.name
        self.assertEqual(main_mod.main([path, "--check"]), 1)


if __name__ == "__main__":
    unittest.main()
