"""Fonts available in .sldz (`Font: <name>`).

Add your own: `register_font(Font(("MyFont",), "fonts/MyFont.ttf"))`
in your plugin, import it in main.py.
Files resolve relative to the repo root, or use absolute paths.
"""

from slidez.ast import Font, register_font

F = "fonts/"

register_font(Font(("Default", "Liberation Sans"), F + "LiberationSans-Regular.ttf",
                   F + "LiberationSans-Bold.ttf"))
register_font(Font(("Manrope",), F + "Manrope-Regular.ttf", F + "Manrope-ExtraBold.ttf"))
register_font(Font(("Manrope SemiBold",), F + "Manrope-SemiBold.ttf", F + "Manrope-ExtraBold.ttf"))
register_font(Font(("Montserrat",), F + "Montserrat-Regular.ttf", F + "Montserrat-Bold.ttf"))
register_font(Font(("Montserrat SemiBold",), F + "Montserrat-SemiBold.ttf",
                   F + "Montserrat-ExtraBold.ttf"))
register_font(Font(("Arial",), F + "LiberationSans-Regular.ttf", F + "LiberationSans-Bold.ttf"))
register_font(Font(("Times New Roman", "Times"), F + "LiberationSerif-Regular.ttf",
                   F + "LiberationSerif-Bold.ttf"))
register_font(Font(("Mono", "Courier New"), F + "LiberationMono-Regular.ttf",
                   F + "LiberationMono-Bold.ttf"))
register_font(Font(("DejaVu Sans Mono",), F + "DejaVuSansMono.ttf"))
