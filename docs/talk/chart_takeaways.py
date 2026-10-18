"""
chart_takeaways.py - slide 13, "What do I take home?": the three rules as plain text, one line each,
appearing one per click (originator, 2026-10-18: "simple text, one line per takeaway, 2-7 words per
line, takeaway style, appears per click").

Click 1: the heading only. Clicks 2-4: + one rule each, a teal number beside it. Click 5: + the
app's QR code (images/qr.png, the live app) and the credit line the Copernicus licence requires.
Each frame is the whole slide, so a click only adds; nothing moves.

Run:  python docs/talk/chart_takeaways.py      # -> charts/takeaways_1..5.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from PIL import Image                                                # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

HEADING = "Take home"
RULES = ["Decide how you'll judge, first",
         "Compare with the best, and nothing",
         "Wrong? Find out why. Say so."]
CREDIT = "Copernicus Climate Change Service information, 2026"
QR = HERE / "images" / "qr.png"
STEPS = len(RULES) + 2


def draw(step: int) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    fig.text(0.09, 0.80, HEADING, ha="left", va="center", color=T.INK_2, fontproperties=T.font(False, 44))
    for i, rule in enumerate(RULES):
        if step < i + 2:
            break
        y = 0.60 - i * 0.17
        fig.text(0.09, y, str(i + 1), ha="left", va="center", color=T.USED, fontproperties=T.font(True, 60))
        fig.text(0.15, y, rule, ha="left", va="center", color=T.INK, fontproperties=T.font(True, 54))
    if step == STEPS:
        ax = fig.add_axes([0.80, 0.70, 0.13, 0.13 * T.W / T.H])
        ax.imshow(Image.open(QR))
        ax.axis("off")
        fig.text(0.09, 0.06, CREDIT, ha="left", va="center", color=T.INK_2, fontproperties=T.font(False, 22))
    path = HERE / "charts" / f"takeaways_{step}.png"
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    for n in range(1, STEPS + 1):
        draw(n)
