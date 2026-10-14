"""
make_lake_animation.py - the opening slide's lake, day by day, 11 Nov 2018 -> 11 Nov 2026 -> 2027?

The lake is the same picture as slide 1 (build_lake_svg's outline, light-deck basin), centred,
framed like a gauge station: a title at top left, the running month and year at top right, a
level staff in metres beside the lake with the upper and lower red lines named on it, and the
data source at the bottom. The water follows the true daily level, softened by a 3-week smoothing
that still lands exactly on every 11 Nov value. On each 11 Nov it eases to a stop and leaves a
dashed line behind with the date and the level; it eases out again, and the year labels glide to
their new places. The last month, to 11 Nov 2026 (the talk's day), is a projection: no rain after
the last measured day, the lake keeps falling at its last-14-day rate.

Then the lake splits in two for 11 Nov 2027: the left lake fills by the best 11 Nov -> 11 Nov
year of the last decade, the right one drains by the worst, and a question mark appears.

Timing is fixed by the recorded narration (charts/lake_years_narrated.mp4): every beat keeps the
second it had in the accepted 30 fps cut, so the narration track is re-laid on the new picture.
The picture is drawn at twice the size and scaled down, so the water and lines move by sub-pixel
steps.

Levels: Gold Data/kinneret_gold_features.csv (level_m); missing days linearly interpolated.

Run:
  python docs/talk/make_lake_animation.py   # -> charts/lake_years.mp4 (+ _narrated.mp4, .gif, last frame .png)
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "kinneret_app"))
from app_utils import (LEVEL_LEGAL_MAX, LEVEL_LEGAL_MIN, LEVEL_MAX, LEVEL_MIN,  # noqa: E402
                       build_lake_svg)

OUT = HERE / "charts" / "lake_years.mp4"
NARRATED = HERE / "charts" / "lake_years_narrated.mp4"
W, H, FPS, SS = 1920, 1080, 60, 2             # SS: drawn at twice the size, then scaled down
SURFACE, INK, INK_2, FAINT = "#FBFAF7", "#1D1D1B", "#5F5D57", "#B9B5AB"
EMPTY_BASIN, OUTLINE, SURFACE_LINE = "#E6E1D6", "#2BD9C4", "#1BA898"
SPILL, RED = "#4C9A4F", "#D2542F"             # upper and lower red lines, sober enough to name
BEST, WORST = "#1F8A70", "#C2410C"            # the two 2027 scenario lakes
FONT = "C:/Windows/Fonts/"

# The lake in SVG user units: the viewBox we render, and build_lake_svg's level -> y mapping
VB_X, VB_Y, VB_W, VB_H = 38, 62, 118, 200
LAKE_CX = 96.5                                # horizontal middle of the outline (x 43-150)
LAKE_TOP_Y, LAKE_BOTTOM_Y = 73.50, 194.85
LINE_X1, LINE_X2 = 52, 141                    # dashed lines span the lake body

# Where the lake sits: one centred lake, then two smaller ones (left = best, right = worst)
SCALE_1, TOP_1 = 4.4, 110                     # px per unit -> lake ~ 880 px tall
SCALE_2, TOP_2 = 3.3, 150
CX_1, CX_LEFT, CX_RIGHT = W / 2, W * 0.26, W * 0.74
LABEL_GAP = 20                                # label column starts this far right of the lake
GAUGE_X = 630                                 # the level staff's line
GAUGE_FROM, GAUGE_TO = -215, -208             # one tick per metre

FIRST_YEAR = 2018
DECADE = range(2016, 2026)                    # the ten 11 Nov -> 11 Nov years ending 11 Nov 2025
SMOOTH_DAYS = 21
DAYS_PER_FRAME_30 = 2.5                       # the accepted cut's pace, at 30 fps
EASE_SHARE = 0.22                             # share of each journey spent speeding up / slowing
LABEL_STEP = 7.0                              # px a year label may move per frame
# the accepted cut's beats, in 30 fps frames (narration sync)
INTRO_30, FADE_30, HOLD_FIRST_30, HOLD_30, HOLD_LAST_30 = 22, 12, 45, 24, 60
APART_30, SPLIT_30, HOLD_END_30, Q_DELAY_30, Q_FADE_30 = 42, 75, 150, 24, 18


def level_y(lvl: float, clamp: bool = True) -> float:
    frac = (lvl - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
    if clamp:
        frac = min(1.0, frac)                 # may go below the old low
    return LAKE_BOTTOM_Y - frac * (LAKE_BOTTOM_Y - LAKE_TOP_Y)


def gauge_ticks() -> list[float]:
    return [float(v) for v in range(GAUGE_FROM, GAUGE_TO + 1)]


class Place:
    """Where one lake sits on the 1920 x 1080 frame: its horizontal middle, top and scale."""

    def __init__(self, cx: float, top: float, scale: float):
        self.cx, self.top, self.scale = cx, top, scale

    def left(self) -> float:
        return self.cx - (LAKE_CX - VB_X) * self.scale

    def x(self, u: float) -> float:
        return self.left() + (u - VB_X) * self.scale

    def y(self, lvl: float, clamp: bool = True) -> float:
        return self.top + (level_y(lvl, clamp) - VB_Y) * self.scale


HOME, LEFT, RIGHT = Place(CX_1, TOP_1, SCALE_1), Place(CX_LEFT, TOP_2, SCALE_2), \
    Place(CX_RIGHT, TOP_2, SCALE_2)
LABEL_X = HOME.x(VB_X + VB_W) + LABEL_GAP


def between(a: Place, b: Place, t: float) -> Place:
    return Place(a.cx + (b.cx - a.cx) * t, a.top + (b.top - a.top) * t,
                 a.scale + (b.scale - a.scale) * t)


# ─── the numbers ────────────────────────────────────────────────────────────

def stops() -> tuple[list[dict], pd.Series, dict]:
    """The 11 Nov stops, the daily path 11 Nov 2018 -> 11 Nov 2026 (true, then projected), and
    the best and worst 11 Nov -> 11 Nov change of the last decade."""
    g = pd.read_csv(ROOT / "Gold Data" / "kinneret_gold_features.csv", parse_dates=["date"])
    lvl = g.set_index("date")["level_m"].dropna()
    nov = lambda y: float(lvl[pd.Timestamp(f"{y}-11-11")])  # noqa: E731
    out = [{"year": y, "level": nov(y), "projected": False} for y in range(FIRST_YEAR, 2026)]
    last_day, last = lvl.index.max(), float(lvl.iloc[-1])
    recent = lvl[lvl.index >= last_day - pd.Timedelta(days=14)]
    rate = (recent.iloc[-1] - recent.iloc[0]) / (recent.index[-1] - recent.index[0]).days
    days = (pd.Timestamp("2026-11-11") - last_day).days
    proj = last + rate * days
    out.append({"year": 2026, "level": float(proj), "projected": True, "note": "if no rain falls"})
    true = lvl[f"{FIRST_YEAR}-11-11":].resample("D").mean().interpolate("time")
    ahead = pd.date_range(last_day + pd.Timedelta(days=1), "2026-11-11", freq="D")
    path = pd.concat([true, pd.Series(last + rate * np.arange(1, len(ahead) + 1), index=ahead)])
    delta = {y: nov(y) - nov(y - 1) for y in DECADE}
    best, worst = max(delta, key=delta.get), min(delta, key=delta.get)
    return out, path, {"best": (best, delta[best]), "worst": (worst, delta[worst]),
                       "last_day": last_day.date(), "last": last, "rate_mm_day": rate * 1000,
                       "days": days, "projection": proj}


def soften(path: pd.Series, anchors: list[int]) -> np.ndarray:
    """Smooth the daily path, then bend it back so it passes exactly through every 11 Nov."""
    raw = path.to_numpy()
    sm = path.rolling(SMOOTH_DAYS, center=True, min_periods=1).mean().to_numpy()
    fix = np.interp(np.arange(len(raw)), anchors, raw[anchors] - sm[anchors])
    return sm + fix


# ─── the timeline: one state per video frame, no drawing ────────────────────

@dataclass
class Frame:
    kind: str                                  # "years" | "apart" | "split"
    pos: float = 0.0                           # fractional day index into the daily path
    level: float = 0.0
    day: object = None
    projected: bool = False
    shown: list = field(default_factory=list)  # (stop index, alpha) for every line reached
    current: int | None = None
    label_ys: dict = field(default_factory=dict)
    t: float = 0.0                             # apart / split progress, 0..1
    label_a: float = 0.0                       # split: scenario labels
    q: float = 0.0                             # split: the question mark


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def journey(n: int) -> np.ndarray:
    """n in-between positions (0..1, exclusive) for one 11 Nov -> 11 Nov journey. Speed rises
    along a half cosine, holds, and falls the same way, so the water leaves and reaches each
    stop at rest."""
    u = (np.arange(n + 1) + 0.5) / (n + 1)
    r = EASE_SHARE
    v = np.ones_like(u)
    v[u < r] = 0.5 * (1 - np.cos(np.pi * u[u < r] / r))
    v[u > 1 - r] = 0.5 * (1 - np.cos(np.pi * (1 - u[u > 1 - r]) / r))
    c = np.cumsum(v)
    return c[:-1] / c[-1]


def _label_targets(S: list[dict], shown: list) -> dict:
    ys = [HOME.y(S[k]["level"]) for k, _ in shown]
    below = [44 if S[k].get("note") else 0 for k, _ in shown]
    return dict(zip((k for k, _ in shown), spread(ys, below, 50)))


def timeline(S: list[dict], path: pd.Series, info: dict) -> list[Frame]:
    days = path.index
    at = [days.get_loc(pd.Timestamp(f"{st['year']}-11-11")) for st in S]
    levels = soften(path, at)
    x2 = FPS // 30                             # new frames per accepted-cut frame
    frames: list[Frame] = []

    def years(pos: float, shown: list, cur):
        lv = float(np.interp(pos, np.arange(len(levels)), levels))
        day = days[int(round(pos))]
        frames.append(Frame("years", pos, lv, day, day.date() > info["last_day"], shown, cur))

    def pause(k: int, hold30: int) -> None:
        done = [(j, 1.0) for j in range(k)]
        for i in range(FADE_30 * x2):
            years(at[k], done + [(k, ease((i + 1) / (FADE_30 * x2)))], k)
        for _ in range(hold30 * x2):
            years(at[k], done + [(k, 1.0)], k)

    for _ in range(INTRO_30 * x2):             # water alone, then the first year appears
        years(at[0], [], None)
    pause(0, HOLD_FIRST_30)
    for k in range(1, len(S)):
        n = (round((at[k] - at[k - 1]) / DAYS_PER_FRAME_30) - 1) * x2
        for u in journey(n):
            years(at[k - 1] + (at[k] - at[k - 1]) * u, [(j, 1.0) for j in range(k)], None)
        pause(k, HOLD_LAST_30 if k == len(S) - 1 else HOLD_30)

    # year labels glide towards their places; a new label appears at its own place
    ys: dict = {}
    for f in frames:
        target = _label_targets(S, f.shown)
        ys = {k: (ys[k] + float(np.clip(target[k] - ys[k], -LABEL_STEP, LABEL_STEP))
                  if k in ys else target[k]) for k in target}
        f.label_ys = dict(ys)

    last = frames[-1]
    n_apart, n_split, n_fade, n_end = (APART_30 * x2, SPLIT_30 * x2, FADE_30 * x2,
                                       HOLD_END_30 * x2)
    for i in range(n_apart):
        frames.append(Frame("apart", level=last.level, day=last.day, projected=True,
                            shown=last.shown, label_ys=last.label_ys,
                            t=ease((i + 1) / n_apart)))
    for i in range(n_split):
        frames.append(Frame("split", level=last.level, t=ease((i + 1) / n_split)))
    for i in range(n_fade):
        frames.append(Frame("split", level=last.level, t=1.0, label_a=(i + 1) / n_fade))
    for i in range(n_end):
        q = min(1.0, (i - Q_DELAY_30 * x2) / (Q_FADE_30 * x2)) if i >= Q_DELAY_30 * x2 else 0.0
        frames.append(Frame("split", level=last.level, t=1.0, label_a=1.0, q=ease(max(q, 0))))
    return frames


def spread(ys: list[float], below: list[float], min_gap: float) -> list[float]:
    """Push label centres apart so none overlap; keeps their order and stays near the lines.
    below: extra room a label needs under it (its note line)."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = [ys[i] for i in order]
    for _ in range(400):
        moved = False
        for k in range(1, len(pos)):
            need = min_gap + below[order[k - 1]]
            if pos[k] - pos[k - 1] < need - 1e-6:
                push = (need - (pos[k] - pos[k - 1])) / 2
                pos[k - 1] -= push
                pos[k] += push
                moved = True
        if not moved:
            break
    out = [0.0] * len(ys)
    for k, i in enumerate(order):
        out[i] = pos[k]
    return out


# ─── drawing: everything at SS x the frame, in frame pixels via s() ─────────

def s(v: float) -> float:
    return v * SS


def lake_path() -> str:
    return re.search(r'<path d="([^"]+)"', build_lake_svg(-211.0)).group(1)


def render(body: str, scale: float) -> Image.Image:
    import resvg_py
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB_X} {VB_Y} {VB_W} {VB_H}">'
           f'<defs><linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0%" stop-color="#67F2DE"/><stop offset="100%" stop-color="#0B6E6B"/>'
           f'</linearGradient></defs>{body}</svg>')
    png = resvg_py.svg_to_bytes(svg_string=svg, width=round(VB_W * scale * SS))
    return Image.open(BytesIO(bytes(png))).convert("RGBA")


_CTX: dict = {}


def _context(S: list[dict], info: dict) -> dict:
    """Layers and fonts, made once per process."""
    if not _CTX:
        d = lake_path()
        layers = {}
        for name, scale in (("home", SCALE_1), ("small", SCALE_2)):
            layers[name] = (render(f'<path d="{d}" fill="{EMPTY_BASIN}"/>', scale),
                            render(f'<path d="{d}" fill="url(#wg)"/>', scale),
                            render(f'<path d="{d}" fill="none" stroke="{OUTLINE}" '
                                   f'stroke-width="0.8"/>', scale))
        f = lambda name, size: ImageFont.truetype(FONT + name, round(s(size)))  # noqa: E731
        _CTX.update(S=S, info=info, layers=layers, F={
            "title": f("seguisb.ttf", 40), "sub": f("segoeuisl.ttf", 28),
            "month": f("seguisb.ttf", 28), "year": f("seguisb.ttf", 96),
            "date": f("segoeuisl.ttf", 30), "val": f("segoeuisl.ttf", 34),
            "val_b": f("seguisb.ttf", 40), "note": f("segoeuisl.ttf", 24),
            "tick": f("segoeuisl.ttf", 26), "line": f("segoeuisl.ttf", 22),
            "foot": f("segoeuisl.ttf", 22), "q": f("seguisb.ttf", 260),
            "q_date": f("seguisb.ttf", 60), "scen": f("seguisb.ttf", 72),
            "scen_note": f("segoeuisl.ttf", 28)})
    return _CTX


def _rgba(hex6: str, a: float = 1.0) -> tuple[int, int, int, int]:
    h = hex6.lstrip("#")[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(255 * max(0.0, min(1.0, a)))


def dashed(d: ImageDraw.ImageDraw, y: float, x1: float, x2: float, color, width=2.0,
           dash=14, gap=9) -> None:
    x = x1
    while x < x2:
        d.line([(s(x), s(y)), (s(min(x + dash, x2)), s(y))], fill=color, width=round(s(width)))
        x += dash + gap


def text(d, xy, words, font, fill, anchor="la") -> None:
    d.text((s(xy[0]), s(xy[1])), words, font=font, fill=fill, anchor=anchor)


def draw_lake(img: Image.Image, layers, at: Place, water_level: float, base_scale: float,
              surface=SURFACE_LINE) -> None:
    """The basin, the water up to its level (the edge one sub-pixel row soft) with its surface
    line inside the lake's outline, then the outline."""
    basin, water, outline = layers
    f = at.scale / base_scale
    size = (round(basin.width * f), round(basin.height * f))
    pos = (round(s(at.left())), round(s(at.top)))
    cut = s((level_y(water_level) - VB_Y) * at.scale)
    sized = [lay.resize(size, Image.LANCZOS) if abs(f - 1) > 1e-6 else lay
             for lay in (basin, water, outline)]
    mask = Image.new("L", size, 0)
    row = int(np.floor(cut))
    mask.paste(255, (0, max(0, row + 1), size[0], size[1]))
    if 0 <= row < size[1]:
        mask.paste(round(255 * (1 - (cut - row))), (0, row, size[0], row + 1))
    w = sized[1].copy()
    w.putalpha(Image.composite(w.getchannel("A"), Image.new("L", size, 0), mask))
    band = Image.new("L", size, 0)                     # the surface line, clipped to the lake
    half = s(1.3)
    lo, hi = cut - half, cut + half
    for r in range(max(0, int(np.floor(lo))), min(size[1], int(np.ceil(hi)) + 1)):
        cover = max(0.0, min(r + 1, hi) - max(r, lo))
        band.paste(round(255 * min(1.0, cover)), (0, r, size[0], r + 1))
    band = ImageChops.multiply(band, sized[0].getchannel("A"))
    line = Image.new("RGBA", size, surface)
    line.putalpha(band)
    img.alpha_composite(sized[0], pos)
    img.alpha_composite(w, pos)
    img.alpha_composite(line, pos)
    img.alpha_composite(sized[2], pos)


def frame_chrome(d, F, a: float) -> None:
    """Title and source: the same on every frame."""
    text(d, (90, 60), "Lake Kinneret", F["title"], _rgba(INK, a))
    text(d, (90, 112), "Level on 11 November, each year", F["sub"], _rgba(INK_2, a))
    text(d, (90, H - 56), "Level: Kinneret Authority, kineret.org.il",
         F["foot"], _rgba(INK_2, a))


def gauge(d, F, at: Place, a: float) -> None:
    """The level staff: a line with a tick and a value per metre, and the two red lines named."""
    ticks = gauge_ticks()
    y0, y1 = at.y(ticks[-1], clamp=False), at.y(ticks[0], clamp=False)
    d.line([(s(GAUGE_X), s(y0)), (s(GAUGE_X), s(y1))], fill=_rgba(FAINT, a), width=round(s(2)))
    for v in ticks:
        y = at.y(v, clamp=False)
        d.line([(s(GAUGE_X - 12), s(y)), (s(GAUGE_X), s(y))], fill=_rgba(FAINT, a),
               width=round(s(2)))
        text(d, (GAUGE_X - 22, y), f"{v:.0f}".replace("-", "\u2212"), F["tick"],
             _rgba(INK_2, a), "rm")
    text(d, (GAUGE_X - 22, y0 - 40), "m", F["tick"], _rgba(INK_2, a), "rm")
    for lvl, col, name in ((LEVEL_LEGAL_MAX, SPILL, "upper red line"),
                           (LEVEL_LEGAL_MIN, RED, "lower red line")):
        y = at.y(lvl)
        dashed(d, y, GAUGE_X, at.x(LINE_X2), _rgba(col, a), width=2.5, dash=18, gap=10)
        text(d, (GAUGE_X + 14, y - 8), name, F["line"], _rgba(col, a), "ld")


def clock(d, F, f: Frame, a: float) -> None:
    text(d, (W - 90, 70), f.day.strftime("%B").upper(), F["month"], _rgba(INK_2, a), "ra")
    text(d, (W - 90, 100), f.day.strftime("%Y"), F["year"], _rgba(INK, a), "ra")
    if f.projected:
        text(d, (W - 90, 222), "projection, no rain", F["note"], _rgba(INK_2, a), "ra")


def draw_years(f: Frame, C: dict) -> Image.Image:
    S, F = C["S"], C["F"]
    fade = 1.0 - min(1.0, f.t / 0.45) if f.kind == "apart" else 1.0   # labels go first
    img = Image.new("RGBA", (round(s(W)), round(s(H))), SURFACE)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    places = [HOME] if f.kind == "years" else [between(HOME, LEFT, f.t), between(HOME, RIGHT, f.t)]
    for p in places:
        draw_lake(img, C["layers"]["home"], p, f.level, SCALE_1)
    frame_chrome(d, F, 1.0)
    gauge(d, F, places[0], fade)
    clock(d, F, f, fade)
    at = places[0]
    x_end = at.x(VB_X + VB_W) + 6
    for k, alpha in f.shown:
        a = alpha * fade
        newest = k == f.current
        y, ly = at.y(S[k]["level"]), f.label_ys[k]
        col = _rgba(INK if newest else FAINT, a)
        dashed(d, y, at.x(LINE_X1), x_end, col, width=2.5 if newest else 1.6)
        d.line([(s(x_end), s(y)), (s(LABEL_X - 8), s(ly))], fill=col, width=round(s(1.6)))
        tcol = _rgba(INK if newest else INK_2, a)
        text(d, (LABEL_X, ly), f"11.11.{S[k]['year']}", F["date"], tcol, "lm")
        val = f"{S[k]['level']:.2f} m".replace("-", "\u2212")
        val = ("\u2248 " + val) if S[k]["projected"] else val
        text(d, (LABEL_X + 170, ly), val, F["val_b" if newest else "val"], tcol, "lm")
        if S[k].get("note"):
            text(d, (LABEL_X + 170, ly + 38), S[k]["note"], F["note"], _rgba(INK_2, a), "lm")
    img.alpha_composite(over)
    return img


def draw_split(f: Frame, C: dict) -> Image.Image:
    info, F = C["info"], C["F"]
    img = Image.new("RGBA", (round(s(W)), round(s(H))), SURFACE)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    now = f.level
    for which, at, color in (("best", LEFT, BEST), ("worst", RIGHT, WORST)):
        year, dl = info[which]
        lvl = now + dl * f.t
        draw_lake(img, C["layers"]["home"], at, lvl, SCALE_1, surface=color)
        x1, x2 = at.x(LINE_X1), at.x(LINE_X2)
        for line_lvl, col in ((LEVEL_LEGAL_MAX, SPILL), (LEVEL_LEGAL_MIN, RED)):
            dashed(d, at.y(line_lvl), x1, x2, _rgba(col), width=2.5, dash=18, gap=10)
        dashed(d, at.y(now), x1, x2, _rgba(INK_2), width=1.6)          # where both start
        text(d, (x2 + 12, at.y(now)), "11.11.2026", F["note"], _rgba(INK_2), "lm")
        if f.label_a > 0:
            base = TOP_2 + VB_H * SCALE_2 + 34
            text(d, (at.cx, base), f"like {year - 1}/{str(year)[2:]}", F["scen"],
                 _rgba(color, f.label_a), "mm")
            text(d, (at.cx, base + 62), f"{dl:+.2f} m in a year".replace("-", "\u2212"),
                 F["scen_note"], _rgba(INK_2, f.label_a), "mm")
    frame_chrome(d, F, 1.0)
    text(d, (W / 2, H * 0.64), "11.11.2027", F["q_date"], _rgba(INK), "mm")
    if f.q > 0:
        text(d, (W / 2, H * 0.42), "?", F["q"], _rgba(INK, f.q), "mm")
    img.alpha_composite(over)
    return img


def draw(f: Frame, C: dict) -> Image.Image:
    big = draw_years(f, C) if f.kind in ("years", "apart") else draw_split(f, C)
    return big.convert("RGB").resize((W, H), Image.LANCZOS)


# ─── rendering, in parallel ─────────────────────────────────────────────────

def _render_chunk(args) -> int:
    S, info, frames, start, tmp = args
    C = _context(S, info)
    for i, f in enumerate(frames, start):
        draw(f, C).save(f"{tmp}/f{i:05d}.png", compress_level=1)
    return len(frames)


def main(preview: list[float] | None = None) -> None:
    from concurrent.futures import ProcessPoolExecutor
    S, path, info = stops()
    print("stops:", [(st["year"], round(st["level"], 3)) for st in S])
    print("decade best", info["best"], "worst", info["worst"])
    print(f"projection: last measured {info['last_day']} {info['last']:.3f} m, "
          f"{info['rate_mm_day']:.1f} mm/day x {info['days']} days -> {info['projection']:.3f} m")
    frames = timeline(S, path, info)
    if preview:                                 # stills at the given seconds, for review
        C = _context(S, info)
        for sec in preview:
            out = HERE / "charts" / f"lake_years_{sec:05.1f}s.png"
            draw(frames[min(len(frames) - 1, round(sec * FPS))], C).save(out)
            print("saved", out.name)
        return
    with tempfile.TemporaryDirectory() as tmp:
        n = 16
        size = -(-len(frames) // n)
        chunks = [(S, info, frames[i:i + size], i, tmp) for i in range(0, len(frames), size)]
        with ProcessPoolExecutor() as pool:
            done = sum(pool.map(_render_chunk, chunks))
        Image.open(f"{tmp}/f{len(frames) - 1:05d}.png").save(OUT.with_suffix(".png"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", f"{tmp}/f%05d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "16", "-preset", "slow", "-movflags", "+faststart", str(OUT)],
                       check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", f"{tmp}/f%05d.png", "-vf",
                        "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                        str(OUT.with_suffix(".gif"))], check=True)
    if NARRATED.exists():                       # the recorded narration, re-laid on the new cut
        tmp_out = NARRATED.with_name("lake_years_narrated.new.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT), "-i", str(NARRATED),
                        "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest",
                        "-movflags", "+faststart", str(tmp_out)], check=True)
        tmp_out.replace(NARRATED)
    print(f"{done} frames, {done / FPS:.1f} s -> {OUT}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=float, nargs="*", help="only save stills at these seconds")
    a = ap.parse_args()
    main(a.preview)
