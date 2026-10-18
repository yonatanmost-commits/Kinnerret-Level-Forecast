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


def draw_slider(ax, s: Slider) -> None:
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(-0.5, 0.88, s.title, ha="left", va="center", color=T.INK,
            fontproperties=T.font(True, 30))
    y = 0.38
    ax.plot([-TRACK, TRACK], [y, y], color=T.UNUSED, lw=10, solid_capstyle="round", zorder=1)
    kx = s.knob * KNOB_REACH * TRACK
    edge = T.USED if s.used else T.INK_2
    if s.knob:                                                 # the winner's stretch, filled
        ax.plot([0, kx], [y, y], color=edge, lw=10, solid_capstyle="round", zorder=2, alpha=0.35)
    for side, label in ((-1, s.left), (1, s.right)):
        used = s.used == ("left" if side == -1 else "right")
        col = T.USED if used else T.INK_2
        x = side * TRACK
        ax.plot([x], [y], "o", ms=18 if used else 10, color=col if used else T.FAINT, zorder=2)
        ax.text(x + side * 0.025, y, label, ha="right" if side == -1 else "left", va="center",
                color=col, fontproperties=T.font(used, 28))
    ax.text(kx, y, s.result, ha="center", va="center", color=T.INK, zorder=4,
            fontproperties=T.font(True, 28),
            bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.7", fc=T.SURFACE, ec=edge, lw=3.5))


def draw(path: Path = OUT) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    top, bottom = 0.86, 0.04                                   # leave the top band for the question
    h = (top - bottom) / len(SLIDERS)
    for i, s in enumerate(SLIDERS):
        ax = fig.add_axes([0.05, top - (i + 1) * h, 0.90, h * 0.95])
        draw_slider(ax, s)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
