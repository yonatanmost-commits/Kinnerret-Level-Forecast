"""
theme.py - the one place the talk's chart look lives (colours, fonts, slide size).

Every chart script imports from here, so the final theme is a change to this file and a redraw.
Current values: the lake-years animation's (make_lake_animation.py), the deck's starting look.
"""
from __future__ import annotations

from pathlib import Path

W, H, DPI = 1920, 1080, 120               # 16:9 slide, 16 x 9 in at 120 dpi

SURFACE = "#FBFAF7"                       # page
INK, INK_2, FAINT = "#1D1D1B", "#5F5D57", "#B9B5AB"
UNUSED = "#E6E1D6"                        # data that exists but isn't used (the empty basin)
# One teal family (originator, 20 Oct: "unify them"): marks, a darker shade of the same hue for
# teal text, the deep end of the water gradient, a soft fill and a light water.
USED = "#1BA898"                          # data the model uses, water, the frame's rules
USED_TEXT = "#158A7D"                     # teal words (USED darkened, same hue; readable on SURFACE)
USED_DEEP = "#0B6E6B"                     # the bottom of the water gradient
USED_LIGHT = "#8ED9CE"                    # light water: the Dead Sea, the coast's brushstroke
USED_SOFT = "#A9DDD5"                     # used in a supporting role (e.g. a forecast's own track record)
RED = "#C2410C"                           # the one red: the red line, dry, misses, the cut
SPILL = "#5F5D57"                         # the upper (spill) line: grey, so red keeps one meaning
AMBER = "#B7791F"                         # a past fault, now fixed (kept apart from the red)
GOOD, BAD = USED_TEXT, RED                # wet / dry wording

FONT_DIR = Path("C:/Windows/Fonts")
FONT_BOLD = FONT_DIR / "seguisb.ttf"      # Segoe UI Semibold: titles, key numbers, row names
FONT_LIGHT = FONT_DIR / "segoeuisl.ttf"   # Segoe UI Semilight: everything else


def font(bold: bool, size: float):
    """A matplotlib FontProperties for one of the two faces, size in points at slide scale."""
    from matplotlib.font_manager import FontProperties
    return FontProperties(fname=str(FONT_BOLD if bold else FONT_LIGHT), size=size)


TITLE_XY = (90, 60)                       # px from the top-left: the lake-years slide's title spot
TITLE_PT = 36


# The slide frame every titled slide shares (build_show.py draws it; px on the 1920 x 1080 slide).
# Originator, 20 Oct: a rule under the title from the far left, not all the way across, and a
# bottom rule from the right that stops short of the left, with a small lake at its right end.
# Pictures keep the title band (0..TITLE_BAND) and the strip under BOTTOM_RULE_Y free.
TITLE_BAND = 170
MARGIN_X = 90                                                 # left and right content edge, = the title's x
# both rules about 70% of the width (originator, 20 Oct: "a bit longer, about 70%")
TITLE_RULE = dict(y=152, x0=0, x1=1344, width=3.5)             # under the title, from the left edge
BOTTOM_RULE = dict(y=1040, x0=476, x1=1800, width=3.5)        # from the lake, leftwards
LAKE_ICON = dict(x=1812, y=1008, h=64)                        # the lake at the bottom rule's right end
CREDIT_XY, CREDIT_PT = (90, 1018), 18                         # credits: left, their baseline just above the bottom rule
SUBTITLE_XY, SUBTITLE_PT = (90, 178), 22                      # a slide's one subtitle: under the title rule


def title(fig, words: str) -> None:
    """The chart's title, in the title spot and title font shared by every slide."""
    x, y = TITLE_XY
    fig.text(x / W, 1 - y / H, words, ha="left", va="top", color=INK, fontproperties=font(True, TITLE_PT))


def text_centered(ax, x: float, y: float, words: str, size: float, bold: bool, color: str,
                  ha: str = "center", **kw) -> None:
    """Text optically centred on (x, y) in a y-down pixel axes: centre the cap height, not the
    ascender-to-descender box, so digits sit in the middle of their cell."""
    cap = 0.70 * size * DPI / 72                       # Segoe UI cap height ~0.70 em, in px
    ax.text(x, y + cap / 2, words, ha=ha, va="baseline", color=color,
            fontproperties=font(bold, size), **kw)
