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


SLIDERS = [
    Slider("Week", "GRU", "GBR", "0.6 cm better", +1, "right"),   # given the week's weather (below)
    Slider("Year", "GRU", "GBR", "36 cm better", -1, "left"),   # 365 d, as on slide 8
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


def draw_slider(ax, s: Slider, L: T.Labels | None, i: int, p: float = 1.0) -> None:
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
    ax.plot([-TRACK, TRACK], [y, y], color=T.UNUSED, lw=10, solid_capstyle="round", zorder=1)
    kx = s.knob * KNOB_REACH * TRACK * p
    arrive = min(1.0, max(0.0, (p - 0.6) / 0.4))                # the last 40% of the way
    edge = mix(T.INK_2, T.USED if s.used else T.INK_2, arrive)
    if s.knob and p > 0:                                       # the winner's stretch, filled
        ax.plot([0, kx], [y, y], color=edge, lw=10, solid_capstyle="round", zorder=2, alpha=0.35)
    for side, label in ((-1, s.left), (1, s.right)):
        used = s.used == ("left" if side == -1 else "right")
        x = side * TRACK
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


if __name__ == "__main__":
    animate()
