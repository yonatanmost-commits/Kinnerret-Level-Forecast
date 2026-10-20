"""
chart_prior_work.py - slide 2, "Hasn't anyone done this already?": who forecasts what, as a
two-column table (WHO, HOW) built up over four clicks.

Each name has its body's official logo beside it (images/logos/), the names kept so the logos
only support them. No row for us: the gap is said aloud. The Great Lakes row, the model for
what is missing here, carries the one colour accent, a soft teal tint. Rows not yet shown keep
their space, so the table never moves between clicks. The title spot stays empty (the slide
question is the title).

Run:  python docs/talk/chart_prior_work.py   # -> charts/slide2_table_1..4.png + slide2_table.png
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import numpy as np                                                   # noqa: E402
from PIL import Image                                                # noqa: E402
from matplotlib.patches import FancyBboxPatch                        # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

OUT = HERE / "charts"
ROWS = [  # (logo, who in bold, who's light second line, how); "|" is a hand-placed line break
    ("iolr_logo.jpg", "Kinneret Limnological|Laboratory", "", "Physical model: rain → springs → Jordan"),
    ("hydro_logo.png", "Hydrological Service", "", "This winter's rain → next year's water"),
    ("hydro_logo.png", "Hydrological Service", "+ weather model", "Tomorrow's rain → the Jordan, days ahead"),
    ("water_authority_logo.jpeg", "Water Authority", "", "What-ifs: an average winter ends here,|a dry one here"),
    ("usace_logo.png", "Great Lakes, USA", "(US Army Corps of Engineers)",
     "The lake's level itself:|monthly, 6 months ahead, with a range"),
]
SHOWN = {1: 3, 2: 4, 3: 5, 4: 5}           # click -> rows on screen
ACCENT = 4                                 # the Great Lakes row

X0, X_HOW, X1 = 90, 950, 1830              # table edges and the HOW column
LOGOS = HERE / "images" / "logos"
LOGO_H, LOGO_W = 76, 180                   # logos this tall, or this wide if wider, centred
X_WHO = X0 + 24 + LOGO_W + 26             # names start right of the logo column
TOP = 190                                  # below the title spot
PT, HEAD_PT = 28, 24
LINE = PT * 1.25 * T.DPI / 72              # px between lines in a cell
PAD = 22                                   # px above and below a row's text


def put_logo(ax, name: str, cx: float, cy: float) -> None:
    """A logo LOGO_H tall (narrower than LOGO_W) centred on (cx, cy), resized by PIL to its exact
    pixel size. A JPEG's white box is multiplied onto the page colour; a PNG keeps its own
    transparency."""
    im = Image.open(LOGOS / name).convert("RGBA")
    ink = (np.asarray(im.convert("RGB")).min(axis=2) < 245) & (np.asarray(im.getchannel("A")) > 10)
    rows, cols = np.where(ink)
    im = im.crop((cols.min(), rows.min(), cols.max() + 1, rows.max() + 1))
    h = min(LOGO_H, LOGO_W * im.height / im.width)
    w = h * im.width / im.height
    a = np.asarray(im.resize((round(w), round(h)), Image.LANCZOS), float) / 255
    if name.endswith((".jpg", ".jpeg")):
        a[..., :3] *= np.array([int(T.SURFACE[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    x0, y0 = round(cx - w / 2), round(cy - h / 2)              # whole pixels: one image px per screen px
    ax.imshow(a, extent=(x0, x0 + a.shape[1], y0 + a.shape[0], y0), interpolation="none", zorder=3)


def draw(click: int, path: Path) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)
    ax.axis("off")

    T.text_centered(ax, X0 + 24, TOP + 30, "WHO", HEAD_PT, True, T.INK_2, ha="left")
    T.text_centered(ax, X_HOW, TOP + 30, "HOW", HEAD_PT, True, T.INK_2, ha="left")
    y = TOP + 70
    ax.plot([X0, X1], [y, y], color=T.INK_2, lw=2)
    for i, (logo, who, who2, how) in enumerate(ROWS):
        how_lines = how.split("|")                               # breaks placed by hand
        who_lines = [(w, True) for w in who.split("|")] + ([(who2, False)] if who2 else [])
        n = max(len(how_lines), len(who_lines))
        h = 2 * PAD + n * LINE
        if i < SHOWN[click]:
            if i == ACCENT:
                ax.add_patch(FancyBboxPatch((X0, y + 8), X1 - X0, h - 16,
                                            boxstyle="round,pad=0,rounding_size=20",
                                            facecolor=T.USED_SOFT, edgecolor="none", alpha=0.45))
            top = y + h / 2 - (n - 1) * LINE / 2
            for k, (words, bold) in enumerate(who_lines):
                T.text_centered(ax, X_WHO, top + k * LINE, words, PT, bold, T.INK, ha="left")
            put_logo(ax, logo, X0 + 24 + LOGO_W / 2, y + h / 2)
            for k, words in enumerate(how_lines):
                T.text_centered(ax, X_HOW, top + k * LINE, words, PT, False, T.INK, ha="left")
            if i < SHOWN[click] - 1 and i + 1 != ACCENT:
                ax.plot([X0, X1], [y + h] * 2, color=T.FAINT, lw=1.5)
        y += h

    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.name}  (table ends at y={y:.0f})")
    return path


if __name__ == "__main__":
    for click in SHOWN:
        last = draw(click, OUT / f"slide2_table_{click}.png")
    shutil.copy(last, OUT / "slide2_table.png")
