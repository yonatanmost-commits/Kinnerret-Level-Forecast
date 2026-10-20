"""
make_map_morph.py - slide 1, one click on "And it matters right now": the two 2027 lakes of the
lake animation merge into one Kinneret, it shrinks to its true place on a map, and around it a
marker draws the Jordan into the lake from the north and on down to the Dead Sea, which fills
with light water, then a brush of the same light water paints the coast from north to south.

Starts on the lake animation's last frame (charts/lake_years.png): its words, dashed lines and
question mark fade first, while the two lakes' water eases back to the 11 Nov 2026 level and the
lakes slide together. The one lake then shrinks onto the map and turns flat teal (the gauge view's
grey "empty" part means nothing on a map). Physical geography only: no borders, no labels
(originator, 20 Oct: the word "Mediterranean" dropped). The lake keeps the animation's traced outline, fitted to its Natural Earth box;
the river, Dead Sea (north basin) and coast are Natural Earth 1:10m lines (docs/talk/data/
slide1_map.json), drawn as one marker stroke with a slight wobble and uneven width.

Run:
  python docs/talk/make_map_morph.py              # -> charts/slide1_map.mp4 (+ .gif, last frame .png)
  python docs/talk/make_map_morph.py --preview 1 2.5 5 9   # stills only, for review
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_lake_animation as LA                                    # noqa: E402
from make_lake_animation import (FPS, H, LEFT, RIGHT, SCALE_1, SCALE_2, SS, SURFACE, TOP_2,  # noqa: E402
                                 VB_X, VB_Y, W, Place, _rgba, ease, s)

OUT = HERE / "charts" / "slide1_map.mp4"
MAP = json.loads((HERE / "data" / "slide1_map.json").read_text())
LAKE, MARKER = LA.T.USED, "#2F3437"                              # theme USED, dark slate
SEA = LA.T.USED_LIGHT                                              # the Dead Sea's fill and the sea's wash

# the map: equirectangular, x squeezed by cos(32 N); lat 33.40 .. 31.10 fills the height
LAT_TOP, LAT_BOTTOM, LON_W, LON_E = 33.40, 31.10, 33.85, 35.65
MAP_TOP, MAP_BOTTOM = 185, 1010                                    # under the title rule, over the bottom one
K = (MAP_BOTTOM - MAP_TOP) / (LAT_TOP - LAT_BOTTOM)                # px per degree of latitude
KX = K * np.cos(np.radians(32.0))
X0 = W / 2 - (LON_E - LON_W) * KX / 2


def proj(pts) -> np.ndarray:
    p = np.asarray(pts, float)
    return np.c_[X0 + (p[:, 0] - LON_W) * KX, MAP_TOP + (LAT_TOP - p[:, 1]) * K]


# timing, seconds
FADE = (0.0, 0.6)          # the 2027 words, lines and question mark
MERGE = (0.2, 1.7)         # water back to 11.11.2026, the two lakes slide into one
SHRINK = (1.7, 3.3)        # the lake to its map place, turning map teal
UPPER = (3.3, 3.8)         # the upper Jordan, from the north into the lake
JORDAN = (3.8, 4.9)
DEAD_SEA = (4.8, 5.6)
SEA_FILL = (5.5, 6.4)      # the Dead Sea fills with light water once its outline is drawn
COAST = (5.4, 7.8)         # the coast: a light-water brush, not the marker
END = 9.4
WASH = 150                 # the sea's watercolour wash: how far west of the coast it bleeds, px
WASH_BLUR = 22             # its soft, pulled-out edge


def phase(t: float, span: tuple[float, float]) -> float:
    return min(1.0, max(0.0, (t - span[0]) / (span[1] - span[0])))


def mix(c1: str, c2: str, u: float) -> str:
    a, b = (np.array(LA._rgba(c)[:3]) for c in (c1, c2))
    return "#%02X%02X%02X" % tuple(np.round(a + (b - a) * u).astype(int))


# ─── the lake's map place, and the marker strokes ───────────────────────────

def outline_box(layer: Image.Image) -> tuple[float, float, float, float, float]:
    """The traced outline's extent in SVG units, and the x of its southern tip (the outlet)."""
    a = np.asarray(layer.getchannel("A")) > 128
    rows, cols = np.where(a)
    u = SCALE_1 * SS
    tip_x = cols[rows >= rows.max() - 3].mean()
    return (VB_X + cols.min() / u, VB_X + cols.max() / u, VB_Y + rows.min() / u,
            VB_Y + rows.max() / u, VB_X + tip_x / u)


def map_place(box) -> tuple[Place, np.ndarray]:
    """The Place that lays the traced outline over the Natural Earth lake's box, and the outlet."""
    x0, x1, y0, y1, tip = box
    g = proj(MAP["kinneret"])
    scale = (g[:, 1].max() - g[:, 1].min()) / (y1 - y0)          # match the north-south length
    top = g[:, 1].min() - (y0 - VB_Y) * scale
    cx_box = (g[:, 0].min() + g[:, 0].max()) / 2
    p = Place(0, top, scale)
    p.cx = cx_box - (p.x((x0 + x1) / 2) - p.cx)                  # centre the outline on the box
    return p, np.array([p.x(tip), p.top + (y1 - VB_Y) * scale])


def on_lake(pt: np.ndarray, layer: Image.Image, at: Place) -> np.ndarray:
    """The point of the traced lake, laid at `at`, nearest to pt (screen px)."""
    rows, cols = np.where(np.asarray(layer.getchannel("A")) > 128)
    u = SCALE_1 * SS
    xs = at.x(VB_X + cols / u)
    ys = at.top + (rows / u) * at.scale
    i = np.argmin(np.hypot(xs - pt[0], ys - pt[1]))
    return np.array([xs[i], ys[i]])


def resample(p: np.ndarray, step: float) -> np.ndarray:
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    d = np.arange(0, seg[-1], step)
    return np.c_[np.interp(d, seg, p[:, 0]), np.interp(d, seg, p[:, 1])]


def smooth(p: np.ndarray, k: int, closed=False) -> np.ndarray:
    if k <= 1:
        return p
    w = np.ones(k) / k
    if closed:
        q = np.r_[p[-k:], p, p[:k]]
        return np.c_[np.convolve(q[:, 0], w, "same"), np.convolve(q[:, 1], w, "same")][k:-k]
    q = np.r_[np.repeat(p[:1], k, 0), p, np.repeat(p[-1:], k, 0)]
    out = np.c_[np.convolve(q[:, 0], w, "same"), np.convolve(q[:, 1], w, "same")][k:-k]
    out[0], out[-1] = p[0], p[-1]
    return out


def marker(p: np.ndarray, seed: int, closed=False, k=5) -> tuple[np.ndarray, np.ndarray]:
    """A hand-drawn version of a line: smoothed, resampled every 2 px, nudged sideways by a slow
    wobble, with a stroke width that swells and thins along the way."""
    rng = np.random.default_rng(seed)
    p = smooth(resample(p, 2.0), k, closed)
    t = np.diff(p, axis=0, append=p[-1:] + (p[-1:] - p[-2:-1]))
    n = np.c_[-t[:, 1], t[:, 0]] / np.maximum(np.hypot(*t.T), 1e-9)[:, None]
    d = np.arange(len(p)) * 2.0
    wob = sum(a * np.sin(d / L + rng.uniform(0, 6.3)) for a, L in ((1.4, 37), (0.8, 13), (0.5, 7)))
    width = 6.2 + 0.9 * np.sin(d / 55 + rng.uniform(0, 6.3)) + 0.4 * np.sin(d / 17 + rng.uniform(0, 6.3))
    return p + n * wob[:, None], width


def draw_stroke(d: ImageDraw.ImageDraw, p: np.ndarray, width: np.ndarray, u: float,
                colour: str = MARKER) -> None:
    """The first u of a marker stroke, round-capped (a dot at every point)."""
    n = int(round(u * len(p)))
    for i in range(n):
        r = s(width[i]) / 2
        x, y = s(p[i, 0]), s(p[i, 1])
        d.ellipse([x - r, y - r, x + r, y + r], fill=_rgba(colour))
        if i:
            d.line([(s(p[i - 1, 0]), s(p[i - 1, 1])), (x, y)], fill=_rgba(colour), width=round(2 * r))


# ─── frames ─────────────────────────────────────────────────────────────────

def context() -> dict:
    S, _, info = LA.stops()
    C = LA._context(S, info)
    flat = LA.render(f'<path d="{LA.lake_path()}" fill="{LAKE}"/>', SCALE_1)
    box = outline_box(C["layers"]["home"][0])
    home_map, outlet = map_place(box)
    jordan = proj(MAP["jordan"])
    off = outlet - jordan[0]                                     # start the river at the outline's tip
    jordan += off * np.clip(1 - np.linspace(0, 1, len(jordan)) / 0.15, 0, 1)[:, None]
    upper = proj(MAP["upper_jordan"])
    off = on_lake(upper[-1], flat, home_map) - upper[-1]         # end the inflow on the outline
    upper += off * np.clip((np.linspace(0, 1, len(upper)) - 0.7) / 0.3, 0, 1)[:, None]
    strokes = {"upper_jordan": marker(upper, 4, k=5),
               "jordan": marker(jordan, 1, k=9),
               "dead_sea": marker(proj(MAP["dead_sea"]), 2, closed=True, k=3),
               "coast": marker(proj(MAP["coast"]), 3, k=5)}
    return dict(C=C, info=info, now=S[-1]["level"], flat=flat, map=home_map, strokes=strokes,
                dead_sea=proj(MAP["dead_sea"]), wash=wash(strokes["coast"][0]))


def wash(coast: np.ndarray) -> Image.Image:
    """The sea as a watercolour wash west of the coast (originator, 20 Oct): strongest at the
    shore, thinning westward, a slightly uneven paper-grain alpha, the edge blurred out into the
    page. Drawn once at the supersampled size; the pen reveals it from north to south."""
    size = (round(s(W)), round(s(H)))
    a = Image.new("L", size, 0)
    d = ImageDraw.Draw(a)
    steps = 30
    for j in range(steps, -1, -1):                               # far west first, the shore last
        off = WASH * j / steps
        d.line([(s(x - off), s(y)) for x, y in coast], fill=round(215 * (1 - j / steps) ** 1.4 + 30),
               width=round(s(WASH / steps + 2)))
    rng = np.random.default_rng(7)
    grain = Image.fromarray((rng.uniform(0.82, 1.0, (size[1] // 8, size[0] // 8)) * 255).astype(np.uint8))
    grain = grain.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(s(3)))
    a = Image.fromarray((np.asarray(a, float) * np.asarray(grain, float) / 255).astype(np.uint8))
    a = a.filter(ImageFilter.GaussianBlur(s(WASH_BLUR)))
    out = Image.new("RGBA", size, SEA)
    out.putalpha(a)
    return out


def draw(t: float, X: dict) -> Image.Image:
    C, info, F = X["C"], X["info"], X["C"]["F"]
    img = Image.new("RGBA", (round(s(W)), round(s(H))), SURFACE)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    a = 1 - ease(phase(t, FADE))
    m, k = ease(phase(t, MERGE)), ease(phase(t, SHRINK))
    now = X["now"]
    centre = Place(W / 2, TOP_2, SCALE_2)

    if k == 0:                                                   # the two lakes, merging
        for which, at, color in (("best", LEFT, LA.BEST), ("worst", RIGHT, LA.WORST)):
            lvl = now + info[which][1] * (1 - m)
            p = LA.between(at, centre, m)
            LA.draw_lake(img, C["layers"]["home"], p, lvl, SCALE_1,
                         surface=mix(color, LA.SURFACE_LINE, m))
            if a > 0:
                x1, x2 = p.x(LA.LINE_X1), p.x(LA.LINE_X2)
                for line_lvl, col in ((LA.LEVEL_LEGAL_MAX, LA.SPILL), (LA.LEVEL_LEGAL_MIN, LA.RED)):
                    LA.dashed(d, p.y(line_lvl), x1, x2, _rgba(col, a), width=2.5, dash=18, gap=10)
                LA.dashed(d, p.y(now), x1, x2, _rgba(LA.INK_2, a), width=1.6)
                LA.text(d, (x2 + 12, p.y(now)), "11.11.2026", F["note"], _rgba(LA.INK_2, a), "lm")
                base = TOP_2 + LA.VB_H * SCALE_2 + 34
                year, dl = info[which]
                LA.text(d, (at.cx, base), f"like {year - 1}/{str(year)[2:]}", F["scen"],
                        _rgba(color, a), "mm")
                LA.text(d, (at.cx, base + 64), f"{dl:+.2f} m in a year".replace("-", "−"),
                        F["scen_note"], _rgba(LA.INK_2, a), "mm")
        if a > 0:
            LA.frame_chrome(d, F, a)
            LA.text(d, (W / 2, H * 0.64), "11.11.2027", F["q_date"], _rgba(LA.INK, a), "mm")
            LA.text(d, (W / 2, H * 0.42), "?", F["q"], _rgba(LA.INK, a), "mm")
    else:                                                        # one lake, to the map
        p = LA.between(centre, X["map"], k)
        LA.draw_lake(img, C["layers"]["home"], p, now, SCALE_1)
        f = p.scale / SCALE_1
        flat = X["flat"].resize((round(X["flat"].width * f), round(X["flat"].height * f)), Image.LANCZOS)
        flat.putalpha(flat.getchannel("A").point(lambda v: round(v * k)))
        img.alpha_composite(flat, (round(s(p.left())), round(s(p.top))))

    u = phase(t, COAST)
    if u > 0:                                                    # the wash follows the pen down the coast
        c = X["strokes"]["coast"][0]
        pen = c[min(len(c) - 1, int((0.5 - 0.5 * np.cos(np.pi * u)) * len(c)))]
        reveal = Image.new("L", img.size, 0)
        ImageDraw.Draw(reveal).rectangle([0, 0, img.size[0], s(pen[1] + 40)], fill=255)
        reveal = reveal.filter(ImageFilter.GaussianBlur(s(30)))
        w = X["wash"].copy()
        w.putalpha(Image.fromarray((np.asarray(w.getchannel("A"), float) * np.asarray(reveal, float) / 255)
                                   .astype(np.uint8)))
        img.alpha_composite(w)
    fa = ease(phase(t, SEA_FILL))
    if fa > 0:                                                   # under the strokes: the Dead Sea's water
        sea = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sea).polygon([(s(x), s(y)) for x, y in X["dead_sea"]], fill=_rgba(SEA, fa))
        img.alpha_composite(sea)
    for name, span in (("upper_jordan", UPPER), ("jordan", JORDAN), ("dead_sea", DEAD_SEA),
                       ("coast", COAST)):
        u = phase(t, span)
        if u > 0:
            draw_stroke(d, *X["strokes"][name], 0.5 - 0.5 * np.cos(np.pi * u),   # pen eases in and out
                        MARKER)                                      # the coast stays a black line
    img.alpha_composite(over)
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


def _render_chunk(args) -> int:
    times, start, tmp = args
    X = context()
    for i, t in enumerate(times, start):
        draw(t, X).save(f"{tmp}/f{i:05d}.png", compress_level=1)
    return len(times)


def main(preview: list[float] | None = None) -> None:
    if preview:
        X = context()
        for sec in preview:
            out = HERE / "charts" / f"slide1_map_{sec:04.1f}s.png"
            draw(sec, X).save(out)
            print("saved", out.name)
        return
    from concurrent.futures import ProcessPoolExecutor
    times = list(np.arange(round(END * FPS)) / FPS)
    with tempfile.TemporaryDirectory() as tmp:
        size = -(-len(times) // 16)
        chunks = [(times[i:i + size], i, tmp) for i in range(0, len(times), size)]
        with ProcessPoolExecutor() as pool:
            done = sum(pool.map(_render_chunk, chunks))
        Image.open(f"{tmp}/f{len(times) - 1:05d}.png").save(OUT.with_suffix(".png"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", f"{tmp}/f%05d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "16", "-preset", "slow", "-movflags", "+faststart", str(OUT)],
                       check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", f"{tmp}/f%05d.png", "-vf",
                        "fps=20,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                        "-loop", "-1", str(OUT.with_suffix(".gif"))], check=True)   # plays once
    print(f"{done} frames, {done / FPS:.1f} s -> {OUT}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=float, nargs="*", help="only save stills at these seconds")
    main(ap.parse_args().preview)
