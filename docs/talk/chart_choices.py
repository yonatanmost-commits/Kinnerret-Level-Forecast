"""
chart_choices.py - slide 7, "How did we choose it?": one slider per test that picked the method.

Sparse by design (originator, v3): five full-width sliders, each with a one-word title above it,
one or two words at each end and no numbers there. The knob is a rounded box that holds the
result and sits toward the winner, or in the middle for a tie. Teal marks what is in use; a
diagnosis (neither end chosen) stays grey. Footnotes, the ERA5 marks and the dropped decoder
are in the speaker notes, not on the slide.

Numbers (confirmed by model-coach): week, given the week's actual weather (the app's 7-day runs
on a week forecast), final run at 7 d: GBR 2.0 vs GRU 2.6 cm, GRU-GBR +0.58 [+0.26, +0.89], clear,
and the gap holds to 30 d (+1.33 [+0.39, +2.38]); with only the seasonal forecast ahead they tie; reach a tie,
0.370 vs 0.366 (ERA5 bench); forecast GRU 0.873 -> 0.851 m at 365 d with Copernicus
SEAS5, -2.1 cm [-6.1, +1.6], not clear (CfC the same, -2.0), so the box sits only slightly over (final run); year (365 d) GRU 0.851 vs GBR 1.209, GRU-GBR -35.8 cm [-66.9, -8.6]
(final cfc_monthly run, SEAS5; the GRU is the product, aligned with slide 8); range 77-84% held by the GRU fan (final run) vs 61-72% from past errors (ERA5).

Run:  python docs/talk/chart_choices.py      # -> charts/choices_sliders.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

OUT = HERE / "charts" / "choices_sliders.png"


@dataclass
class Slider:
    title: str
    left: str
    right: str
    result: str          # what the knob box says
    knob: float          # -1 = fully left wins, 0 = tie, +1 = fully right wins
    used: str            # "left" or "right": the option in use today; "" = a diagnosis


SLIDERS = [   # GBR left, GRU right, as the models drawing above them (originator, 31 Oct)
    Slider("Week", "GBR", "GRU", "6 mm better", -1, "left"),   # given the week's weather (below)
    Slider("Year", "GBR", "GRU", "36 cm better", +1, "right"),   # 365 d, as on slide 8
    Slider("Reach", "Relay", "Direct", "tie", 0, "right"),
    Slider("Forecast", "Average year", "Copernicus", "2 cm better", +0.35, "right"),   # a lean, not clear
    # Range ("holds 77-84%") left the slide 2026-10-18 (originator): it gave away slide 12's 8 in 10
]

TRACK = 0.31         # half-length of a track, in slider-axes units (axes span -0.5..0.5);
                     # the end words sit beside the track ends, on its line
KNOB_REACH = 0.58    # a winner's box sits this share of the way out, clear of the end stops


def mix(a: str, b: str, f: float) -> tuple:
    """Colour a, moved share f of the way to colour b."""
    ca, cb = (tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)) for c in (a, b))
    return tuple(x + (y - x) * f for x, y in zip(ca, cb))


def draw_slider(ax, s: Slider, L: T.Labels | None, i: int, p: float = 1.0, track: float = TRACK,
                reach: float = KNOB_REACH) -> None:
    """One slider, its knob share p of the way from the middle to its result (originator, 23 Oct:
    "all start in the middle and each click moves an analog slider to its result"). The result
    fades into the knob over the last stretch, and the end in use turns teal as it arrives, so the
    end words are drawn in the picture (only the row names are native text)."""
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if L is not None:
        L.text(ax, f"row.{i}", -0.5, 0.88, s.title, 30, True, T.INK, ha="left", va="center")
    y = 0.38
    ax.plot([-track, track], [y, y], color=T.UNUSED, lw=10, solid_capstyle="round", zorder=1)
    kx = s.knob * reach * track * p
    arrive = min(1.0, max(0.0, (p - 0.6) / 0.4))                # the last 40% of the way
    edge = mix(T.INK_2, T.USED if s.used else T.INK_2, arrive)
    if s.knob and p > 0:                                       # the winner's stretch, filled
        ax.plot([0, kx], [y, y], color=edge, lw=10, solid_capstyle="round", zorder=2, alpha=0.35)
    for side, label in ((-1, s.left), (1, s.right)):
        used = s.used == ("left" if side == -1 else "right")
        x = side * track
        ax.plot([x], [y], "o", ms=10 + 8 * arrive if used else 10,
                color=mix(T.FAINT, T.USED, arrive) if used else T.FAINT, zorder=2)
        ax.text(x + side * 0.025, y, label, color=mix(T.INK_2, T.USED, arrive) if used else T.INK_2,
                fontproperties=T.font(used and arrive > 0.5, 28), ha="right" if side == -1 else "left",
                va="center")
    ax.text(kx, y, s.result, ha="center", va="center", color=T.INK, alpha=arrive, zorder=4,
            fontproperties=T.font(True, 28),
            bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.7", fc=T.SURFACE, ec=edge, lw=3.5))


def figure(progress: list[float], L: T.Labels | None):
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    # between the title rule and the bottom rule (originator, 20 Oct: "space it"), on the margins
    top, bottom = 1 - (T.TITLE_BAND + 25) / T.H, 1 - (T.BOTTOM_RULE["y"] - 40) / T.H
    h = (top - bottom) / len(SLIDERS)
    m = T.MARGIN_X / T.W
    for i, (s, p) in enumerate(zip(SLIDERS, progress)):
        ax = fig.add_axes([m, top - (i + 1) * h, 1 - 2 * m, h * 0.92])
        draw_slider(ax, s, L, i + 1, p)
    return fig


def draw(path: Path = OUT, progress: list[float] | None = None) -> Path:
    L = T.Labels()                                             # the row names are native text
    fig = figure(progress or [1.0] * len(SLIDERS), L)
    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


FPS, MOVE_S, HOLD_S = 30, 1.4, 0.4


def ease(f: float) -> float:
    return 3 * f * f - 2 * f * f * f


def animate() -> None:
    """Step 0 (charts/choices_sliders_0.png): every knob in the middle. Click k: slider k slides to
    its result, charts/choices_sliders_k.mp4 (its last frame is choices_sliders_k.png, for the
    review page); bare/choices_sliders_k.mp4 is the same without the row names, beside their
    labels.json, for the decks."""
    import shutil
    import subprocess
    import tempfile
    import numpy as np
    from PIL import Image
    n = len(SLIDERS)
    bare = OUT.parent / "bare"
    draw(OUT.with_name("choices_sliders_0.png"), [0.0] * n)
    steps, hold = int(MOVE_S * FPS), int(HOLD_S * FPS)
    for k in range(1, n + 1):
        draw(OUT.with_name(f"choices_sliders_{k}.png"), [1.0] * k + [0.0] * (n - k))
        with tempfile.TemporaryDirectory() as tmp:
            for kind, dest in (("bare", bare), ("full", OUT.parent)):
                for j in range(steps + hold):
                    prog = [1.0] * (k - 1) + [ease(min(1.0, j / steps))] + [0.0] * (n - k)
                    fig = figure(prog, T.Labels() if kind == "full" else None)
                    fig.canvas.draw()
                    Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3]).save(Path(tmp) / f"{j:04d}.png")
                    plt.close(fig)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                                str(Path(tmp) / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                                "-movflags", "+faststart", str(dest / f"choices_sliders_{k}.mp4")], check=True)
        print(f"saved charts/choices_sliders_{k}.mp4 ({MOVE_S + HOLD_S:.1f} s) and its bare twin")
    shutil.copyfile(OUT.with_name(f"choices_sliders_{n}.png"), OUT)
    shutil.copyfile(bare / f"choices_sliders_{n}.png", bare / OUT.name)
    shutil.copyfile(bare / f"choices_sliders_{n}.labels.json", bare / f"{OUT.stem}.labels.json")


# ---------------------------------------------------------------- 31 Oct: the sliders split out
# (originator: "its too hard so it splits out"). Week and Year go under the models (two clicks),
# Forecast under the Copernicus track (one click), and the reach race becomes its own Q&A slide,
# "The benchmark", with three sliders of its own. with_sliders() puts slider rows under ANY
# finished chart: it shrinks the chart (picture, bare twin and native labels alike) into the space
# above them, so the charts themselves don't change.

ROW_H = 105                       # px per one-line slider row
CONTENT = (T.TITLE_BAND, 1040)    # the band a chart's content may use, px from the top


def draw_row(ax, s: Slider, L: T.Labels | None, name: str, p: float = 1.0) -> None:
    """One slider on one line, in pixel units (ax spans the full width): its title on the left
    margin, the track in the middle, the knob share p of the way from the middle to its result.
    As draw_slider: at p = 0 an empty grey box in the middle; the result fades in and the end in
    use turns teal over the last stretch."""
    ax.set_xlim(0, T.W)
    ax.set_ylim(1, 0)
    ax.axis("off")
    y, x0, x1 = 0.5, 660, 1460
    c = (x0 + x1) / 2
    if L is not None:
        L.text(ax, name, T.MARGIN_X, y, s.title, 30, True, T.INK, ha="left", va="center")
    ax.plot([x0, x1], [y, y], color=T.UNUSED, lw=10, solid_capstyle="round", zorder=1)
    kx = c + s.knob * KNOB_REACH * (x1 - c) * p
    arrive = min(1.0, max(0.0, (p - 0.6) / 0.4))                # the last 40% of the way
    edge = mix(T.INK_2, T.USED if s.used else T.INK_2, arrive)
    if s.knob and p > 0:
        ax.plot([c, kx], [y, y], color=edge, lw=10, solid_capstyle="round", zorder=2, alpha=0.35)
    for side, label, x in ((-1, s.left, x0), (1, s.right, x1)):
        used = s.used == ("left" if side == -1 else "right")
        ax.plot([x], [y], "o", ms=10 + 8 * arrive if used else 10,
                color=mix(T.FAINT, T.USED, arrive) if used else T.FAINT, zorder=2)
        ax.text(x + side * 22, y, label, color=mix(T.INK_2, T.USED_TEXT, arrive) if used else T.INK_2,
                fontproperties=T.font(used and arrive > 0.5, 28), ha="right" if side == -1 else "left",
                va="center")
    ax.text(kx, y, s.result, ha="center", va="center", color=T.INK, alpha=arrive, zorder=4,
            fontproperties=T.font(True, 26),
            bbox=dict(boxstyle="round,pad=0.4,rounding_size=0.7", fc=T.SURFACE, ec=edge, lw=3.5))


class Under:
    """A finished chart (charts/x.png + bare/x.png + bare/x.labels.json) shrunk into the space
    above len(rows) one-line slider rows. One instance draws any state of the rows: a knob
    position per row, None = the row not shown yet."""

    def __init__(self, base: Path, rows: list[Slider]):
        import json
        import numpy as np
        from PIL import Image
        self.rows = rows
        y0, y1 = CONTENT
        self.k = (y1 - y0 - len(rows) * ROW_H - 10) / (y1 - y0)
        w, h = round(T.W * self.k), round((y1 - y0) * self.k)
        self.xoff, self.top = (T.W - w) // 2, y0 + h + 10
        meta = base.parent / "bare" / f"{base.stem}.labels.json"

        def shrunk(path: Path):
            im = Image.open(path).convert("RGB")
            page = Image.new("RGB", (T.W, T.H), T.SURFACE)
            page.paste(im.crop((0, y0, T.W, y1)).resize((w, h), Image.LANCZOS), (self.xoff, y0))
            return np.asarray(page)
        self.full = shrunk(base)
        self.bare = shrunk(base.parent / "bare" / base.name) if meta.exists() else self.full
        self.labels = []                                         # the chart's labels, moved and shrunk
        for lab in (json.loads(meta.read_text(encoding="utf-8"))["labels"] if meta.exists() else []):
            bx, k = lab["box"], self.k
            lab["box"] = [round(self.xoff + bx[0] * k, 1), round(y0 + (bx[1] - y0) * k, 1),
                          round(self.xoff + bx[2] * k, 1), round(y0 + (bx[3] - y0) * k, 1)]
            lab["pt"] = round(lab["pt"] * k, 2)
            if "pitch" in lab:
                lab["pitch"] = round(lab["pitch"] * k, 2)
            self.labels.append(lab)

    def figure(self, progress: list, kind: str, L: T.Labels | None = None):
        """kind "bare": the chart without its words, the row names through L (native text);
        "full": the chart with its words and the row names drawn in."""
        fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.imshow(self.bare if kind == "bare" else self.full, extent=(0, T.W, T.H, 0), interpolation="none")
        ax.axis("off")
        for i, (s, p) in enumerate(zip(self.rows, progress)):
            if p is None:
                continue
            r = fig.add_axes([0, 1 - (self.top + (i + 1) * ROW_H) / T.H, 1, ROW_H / T.H])
            draw_row(r, s, L, f"row.{i + 1}", p)
            if kind == "full":
                r.text(T.MARGIN_X, 0.5, s.title, color=T.INK, fontproperties=T.font(True, 30), ha="left",
                       va="center")
        return fig

    def still(self, progress: list, out: Path) -> Path:
        """out (full), bare/out and bare/out.labels.json (the chart's words + the rows' names)."""
        import json
        L = T.Labels()
        fig = self.figure(progress, "bare", L)
        L.save(fig, out)                                          # bare twin + the rows' labels
        plt.close(fig)
        fig = self.figure(progress, "full")
        fig.savefig(out, dpi=T.DPI, facecolor=T.SURFACE)
        plt.close(fig)
        sm = out.parent / "bare" / f"{out.stem}.labels.json"
        rows = json.loads(sm.read_text(encoding="utf-8"))["labels"]
        sm.write_text(json.dumps({"labels": self.labels + rows}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"saved {out.relative_to(ROOT)} (chart at {self.k:.0%})")
        return out

    def slide(self, before: list, i: int, out: Path) -> Path:
        """Row i slides from the middle to its result (the old slide-7 motion): out.mp4 and its
        bare twin, plus out.png = the last frame (still(), for the review page and the labels)."""
        import subprocess
        import tempfile
        import numpy as np
        from PIL import Image
        end = list(before)
        end[i] = 1.0
        self.still(end, out)
        steps, hold = int(MOVE_S * FPS), int(HOLD_S * FPS)
        with tempfile.TemporaryDirectory() as tmp:
            for kind, dest in (("bare", out.parent / "bare"), ("full", out.parent)):
                for j in range(steps + hold):
                    prog = list(before)
                    prog[i] = ease(min(1.0, j / steps))
                    fig = self.figure(prog, kind)
                    fig.canvas.draw()
                    Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3]).save(Path(tmp) / f"{j:04d}.png")
                    plt.close(fig)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                                str(Path(tmp) / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                                "-movflags", "+faststart", str(dest / f"{out.stem}.mp4")], check=True)
        print(f"saved {out.with_suffix('.mp4').relative_to(ROOT)} ({MOVE_S + HOLD_S:.1f} s) and its bare twin")
        return out


def with_sliders(base: Path, rows: list[Slider], shown: int, out: Path) -> Path:
    """`base` shrunk above len(rows) slider rows, the first `shown` of them at their results."""
    return Under(base, rows).still([1.0] * shown + [None] * (len(rows) - shown), out)


MODEL_ROWS = SLIDERS[:2]          # Week, Year: under "The models"
FORECAST_ROWS = SLIDERS[3:4]      # Forecast: under Copernicus's track

# The benchmark (Q&A): forecast straight from today's measured value (the benchmark), or step by
# step from the last forecast? Year: the network's relay vs direct, ERA5 bench, all horizons,
# 0.370 vs 0.366 m (CfC cell; no GRU relay was run). Week: the June bake-off (paper Table 2),
# R² of the 7-day volume change, 2021-24 folds: the lake change from today 0.77 vs rolled day by
# day 0.66 (gbr_s1_chain_s2_roll1); the river day by day, inflow R² 0.94 vs from today 0.86
# (gbr_s1_direct_s2_anchor).
BENCH_ROWS = [
    Slider("Year · neural network", "Day by day", "From today", "tie", 0, "right"),
    Slider("Week · lake change (R²)", "Day by day", "From today", "0.77 vs 0.66", +1, "right"),
    Slider("Week · river flow (R²)", "Day by day", "From today", "0.94 vs 0.86", -1, "left"),
]
JAFFA = HERE / "images" / "jaffa_f55.jpg"
JAFFA_CREDIT = "F-55, Jaffa Port · Photo: Baruch Niv, CC BY-SA 4.0"


def draw_benchmark(shown: int, path: Path) -> Path:
    """Q&A "The benchmark": the F-55 stone at Jaffa port (B&W) on the left, three sliders right."""
    import numpy as np
    from PIL import Image, ImageOps
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    x0, y0, pw, ph = T.MARGIN_X, T.TITLE_BAND + 40, 480, 800
    im = ImageOps.grayscale(Image.open(JAFFA))
    im = ImageOps.fit(im, (pw, ph), Image.LANCZOS, centering=(0.5, 0.55)).convert("RGB")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)
    ax.axis("off")
    ax.imshow(np.asarray(im), extent=(x0, x0 + pw, y0 + ph, y0), interpolation="none")
    L = T.Labels()
    L.text(ax, "credit", x0 + 14, y0 + ph - 18, JAFFA_CREDIT, 13, False, "#FFFFFF", ha="left", va="baseline")
    left, right = x0 + pw + 60, T.W - T.MARGIN_X
    hh = ph / len(BENCH_ROWS)
    for i, s in enumerate(BENCH_ROWS[:shown]):
        a = fig.add_axes([left / T.W, 1 - (y0 + (i + 1) * hh) / T.H, (right - left) / T.W, hh * 0.85 / T.H])
        draw_slider(a, s, L, i + 1, track=0.28, reach=0.42)
    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)}")
    return path


def split() -> None:
    """The 31 Oct frames. Models (originator, 31 Oct, second pass): 0 the drawing alone; 1 both
    sliders in the middle, no results (the comparisons open); 2 Week slides to its result
    (models_sliders_2.mp4); 3 Year slides (models_sliders_3.mp4). Then seas5_sliders_1..5 and
    benchmark_1..3."""
    c = OUT.parent
    m = Under(c / "models_explained.png", MODEL_ROWS)
    m.still([None, None], c / "models_sliders_0.png")
    m.still([0.0, 0.0], c / "models_sliders_1.png")
    m.slide([0.0, 0.0], 0, c / "models_sliders_2.png")
    m.slide([1.0, 0.0], 1, c / "models_sliders_3.png")
    for n, base in enumerate(["seas5_track_1.png", "seas5_track_2.png", "seas5_track_3.png", "seas5_track.png",
                              "seas5_track.png"], 1):
        with_sliders(c / base, FORECAST_ROWS, int(n == 5), c / f"seas5_sliders_{n}.png")
    for n in range(1, len(BENCH_ROWS) + 1):
        draw_benchmark(n, c / f"benchmark_{n}.png")


if __name__ == "__main__":
    if "--split" in sys.argv:
        split()
    else:
        animate()
