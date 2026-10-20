"""
make_centaur.py - slide 3, "Centaur": the Old Centaur teased by Eros, in the Louvre.

Originator, 20 Oct: a centaur that speaks the deck's colours, then "the full image in the center"
(their mock-up). The photo (Wikimedia Commons, "Centaur & Cupid, Louvre Museum.jpg", by Wilfredo
Rodriguez, CC BY-SA 2.0, which asks for the credit line) is cream marble in a cream hall. It sits
whole and centred between the title rule and the bottom rule, its edges fading softly into the
page. The title is the show's ("Centaur", build_show.py), like every other slide's.

Run:  python docs/talk/make_centaur.py        # -> charts/centaur_slide.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

PHOTO = HERE / "images" / "centaur_louvre.jpg"
OUT = HERE / "charts" / "centaur_slide.png"
CREDIT = "Old Centaur teased by Eros, Louvre  ·  Photo: Wilfredo Rodriguez, CC BY-SA 2.0"
TOP, BOTTOM = T.TITLE_BAND, T.BOTTOM_RULE["y"] - 24      # the photo's room between the two rules
FEATHER = 40                                             # its soft edge, px


def draw(path: Path = OUT) -> Path:
    im = Image.open(PHOTO).convert("RGB")
    h = BOTTOM - TOP
    im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rectangle([FEATHER, FEATHER, im.width - FEATHER, im.height - FEATHER], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(FEATHER / 2))
    page = Image.new("RGB", (T.W, T.H), T.SURFACE)
    page.paste(im, ((T.W - im.width) // 2, TOP), mask)
    d = ImageDraw.Draw(page)
    font = ImageFont.truetype(str(T.FONT_LIGHT), round(T.CREDIT_PT * T.DPI / 72))
    d.text(T.CREDIT_XY, CREDIT, font=font, fill=T.INK_2, anchor="ls")       # baseline on the bottom rule's line
    path.parent.mkdir(parents=True, exist_ok=True)
    page.save(path)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    draw()
