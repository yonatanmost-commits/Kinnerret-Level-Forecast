"""
compose_coverage.py - the data-sources slide: the coverage chart with each agency's logo beside
the records it supplies (Claude Design "Kinneret Deck", slide "Data sources", 2026-10-14; replaces
the watercolour backdrop of plan D21 and the fountain picture).

The chart is the builder's drawn layer, charts/coverage_layer.png, laid on the deck's plain surface
untouched, so every plotted date stays a ledger value. Down the right edge, a thin rule spans each
agency's rows and its logo sits beside it, multiplied onto the surface so a logo's white box
disappears:
  Kinneret Drainage Authority   lake level
  Hydrological Service          the Jordan and Yarmuk records
  Meteorological Service        weather and the sun's radiation

Run:
  python docs/talk/charts.py               # (re)draws charts/coverage_layer.png from the ledger
  python docs/talk/compose_coverage.py     # -> charts/coverage_slide.png, 1920 x 1080
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from build_deck import SURFACE
from compose_sources import load

HERE = Path(__file__).resolve().parent
LAYER = HERE / "charts" / "coverage_layer.png"
OUT = HERE / "charts" / "coverage_slide.png"

W, H = 1920, 1080
CHART_BOX = (80, 110, 1600, 840)                  # x, y, w, h: the layer, scaled to fit
RULE_X, RULE_W, RULE = 1700, 3, "#c9c4b8"
LOGO_X = 1724
# per agency: its rule (top, height) beside its rows, and its logo (file, top, height)
AGENCIES = [
    ((326, 60), ("kinneret_drainage_logo.png", 310, 92)),
    ((404, 300), ("hydro_logo.png", 490, 130)),
    ((722, 112), ("ims_logo.svg", 740, 76)),
]


def main() -> None:
    page = Image.new("RGB", (W, H), "#" + SURFACE)
    x, y, w, h = CHART_BOX
    layer = Image.open(LAYER).convert("RGBA").resize((w, h), Image.LANCZOS)
    page.paste(layer, (x, y), layer)
    draw = ImageDraw.Draw(page)
    for (top, height), (name, logo_top, logo_h) in AGENCIES:
        draw.rectangle((RULE_X, top, RULE_X + RULE_W - 1, top + height - 1), fill=RULE)
        logo = load(name, logo_h)
        flat = Image.new("RGB", logo.size, "white")
        flat.paste(logo, (0, 0), logo)                  # transparent parts -> white
        box = (LOGO_X, logo_top, LOGO_X + logo.width, logo_top + logo.height)
        page.paste(ImageChops.multiply(page.crop(box), flat), box[:2])
    page.save(OUT)
    print(f"saved {OUT.relative_to(HERE.parent.parent)} ({W} x {H})")


if __name__ == "__main__":
    main()
