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


ASCENT, DESCENT = 2210 / 2048, 514 / 2048       # Segoe UI's line box, em (hhea): PowerPoint's single line


class Labels:
    """A chart's words that the show sets as native PowerPoint text (originator, 20 Oct: "so i can
    design some of it by hand"). Draw them through here instead of ax.text; save() writes the full
    picture as before (the review page), the picture without them in bare/, and their words,
    boxes and styles in bare/<stem>.labels.json for build_show.py."""

    def __init__(self):
        self.items = []                                           # (name, artist, bold, colour)

    def text(self, ax, name: str, x: float, y: float, words: str, size: float, bold: bool, color: str, **kw):
        a = ax.text(x, y, words, color=color, fontproperties=font(bold, size), **kw)
        self.items.append((name, a, bold, color))
        return a

    def centered(self, ax, name: str, x: float, y: float, words: str, size: float, bold: bool, color: str,
                 ha: str = "center", **kw):
        cap = 0.70 * size * DPI / 72                              # as text_centered
        return self.text(ax, name, x, y + cap / 2, words, size, bold, color, ha=ha, va="baseline", **kw)

    def lines(self, ax, name: str, x: float, y: float, rows: list[str], pitch: float, size: float, bold: bool,
              color: str, ha: str = "left", **kw):
        """Several lines as ONE label (one box to design by hand): line k's cap height centred on
        y + k * pitch px, as text_centered line by line would put it."""
        cap = 0.70 * size * DPI / 72
        a = self.text(ax, name, x, y + cap / 2 + (len(rows) - 1) * pitch, "\n".join(rows), size, bold, color,
                      ha=ha, va="baseline", **kw)                  # matplotlib anchors the LAST line's baseline
        if len(rows) > 1:                                          # the pitch is linear in linespacing: solve it
            r = ax.figure.canvas.get_renderer()

            def at(ls: float) -> float:
                a.set_linespacing(ls)
                ys = [v for *_, v in a._get_layout(r)[1]]
                return abs(ys[0] - ys[1])
            p1, p2 = at(1.0), at(2.0)
            a.set_linespacing(1.0 + (pitch - p1) / (p2 - p1))
        return a

    def pil(self, name: str, xy: tuple[float, float], words: str, size: float, bold: bool, color: str,
            anchor: str = "ls", shadow: str | None = None) -> None:
        """A single-line label for a PIL picture (photos, the lake animation): size in points at
        slide scale like font(), anchor as PIL's. Drawn by save_pil() on the full picture only."""
        self.items.append((name, dict(xy=xy, words=words, size=size, anchor=anchor, shadow=shadow), bold, color))

    def pil_font(self, size: float, bold: bool):
        from PIL import ImageFont
        return ImageFont.truetype(str(FONT_BOLD if bold else FONT_LIGHT), round(size * DPI / 72))

    def draw_pil(self, im) -> None:
        """The labels drawn onto a PIL picture, as the full (review) picture shows them."""
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        for _, p, bold, color in self.items:
            f = self.pil_font(p["size"], bold)
            x, y = p["xy"]
            if p["shadow"]:
                d.text((x + 2, y + 2), p["words"], font=f, fill=p["shadow"], anchor=p["anchor"])
            d.text((x, y), p["words"], font=f, fill=color, anchor=p["anchor"])

    def pil_labels(self) -> list[dict]:
        out = []
        for name, p, bold, color in self.items:
            f = self.pil_font(p["size"], bold)
            x, y = p["xy"]
            base = y + f.getbbox(p["words"], anchor=p["anchor"])[1] - f.getbbox(p["words"], anchor="ls")[1]
            x0, _, x1, _ = f.getbbox(p["words"], anchor=p["anchor"])
            em = round(p["size"] * DPI / 72)
            ha = {"l": "left", "m": "center", "r": "right"}[p["anchor"][0]]
            d = {"name": name, "text": p["words"], "box": [round(x + x0, 1), round(base - ASCENT * em, 1),
                                                           round(x + x1, 1), round(base + DESCENT * em, 1)],
                 "ha": ha, "pt": round(em * 0.5, 2), "bold": bold, "color": color, "lines": 1}
            if p["shadow"]:
                d["shadow"] = p["shadow"]
            out.append(d)
        return out

    def save_pil(self, im, path: Path) -> Path:
        """`im` without the words -> bare/, with them -> path; the words -> bare/<stem>.labels.json."""
        import json
        bare = path.parent / "bare"
        bare.mkdir(parents=True, exist_ok=True)
        im.save(bare / path.name)
        full = im.copy()
        self.draw_pil(full)
        full.save(path)
        (bare / f"{path.stem}.labels.json").write_text(json.dumps({"labels": self.pil_labels()}, indent=1,
                                                                  ensure_ascii=False), encoding="utf-8")
        return path

    def save(self, fig, path: Path, **kw) -> Path:
        import json
        names = [n for n, *_ in self.items]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            raise ValueError(f"{path.name}: label names used twice: {sorted(dup)}")
        kw.setdefault("dpi", DPI)
        kw.setdefault("facecolor", SURFACE)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, **kw)
        r = fig.canvas.get_renderer()
        labels = []
        for name, a, bold, color in self.items:
            if not a.get_visible() or not a.get_text():
                continue
            b = a.get_window_extent(r)                            # display px, y up
            # The box from the baselines and the FONT's ascent and descent, not the letters' (a box
            # round "WHO" has no descent and would centre it lower than "who" in PowerPoint).
            _, info, desc = a._get_layout(r)
            em = a.get_fontsize() * DPI / 72
            last = H - b.y0 - desc                                # the last line's baseline, y down
            first = last - (abs(info[0][-1] - info[-1][-1]) if len(info) > 1 else 0)
            labels.append({"name": name, "text": a.get_text(),
                           "box": [round(b.x0, 1), round(first - ASCENT * em, 1), round(b.x1, 1),
                                   round(last + DESCENT * em, 1)],
                           "ha": a.get_horizontalalignment(), "pt": round(a.get_fontsize() * DPI / 72 * 0.5, 2),
                           "bold": bold, "color": color, "lines": a.get_text().count("\n") + 1})
            if labels[-1]["lines"] > 1:                           # the line pitch, slide points
                ys = [y for *_, y in a._get_layout(r)[1]]
                labels[-1]["pitch"] = round(abs(ys[0] - ys[1]) * 0.5, 2)
            a.set_visible(False)
        bare = path.parent / "bare"
        bare.mkdir(exist_ok=True)
        fig.savefig(bare / path.name, **kw)
        for _, a, *_ in self.items:
            a.set_visible(True)
        (bare / f"{path.stem}.labels.json").write_text(json.dumps({"labels": labels}, indent=1, ensure_ascii=False),
                                                       encoding="utf-8")
        return path
