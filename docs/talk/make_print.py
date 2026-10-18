"""
make_print.py - slide 11, "The limiting factor": the Degania Dam photo as a framed print.

The photo (images/degania_dam.jpg) is the JNF Photo Archive's picture 028867, "the dam on the
Jordan near Degania", public domain in Israel (copyright expired), via Wikimedia Commons. The
original is only 600 x 461, so it is shown as a print with a white border and a soft shadow,
not stretched full-bleed; a credit line sits under it. Commons dates it "1 January 1925", which is
a placeholder: the dam was built in the early 1930s, so no year is printed.

Run:  python docs/talk/make_print.py         # -> charts/degania_print.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

PHOTO = HERE / "images" / "degania_dam.jpg"
OUT = HERE / "charts" / "degania_print.png"
CREDIT = "Degania Dam, on the Jordan where it leaves the lake  ·  Photo: JNF Photo Archive"


def draw(path: Path = OUT) -> Path:
    photo = Image.open(PHOTO).convert("RGB")
    W, H = T.W, T.H
    page = Image.new("RGB", (W, H), T.SURFACE)
    ph = 670
    pw = round(ph * photo.width / photo.height)
    border = 18
    fw, fh = pw + 2 * border, ph + 2 * border
    x0, y0 = (W - fw) // 2, 205

    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle([x0 + 8, y0 + 18, x0 + fw + 8, y0 + fh + 18], fill=120)
    page.paste(Image.new("RGB", (W, H), "#3B342B"), (0, 0), shadow.filter(ImageFilter.GaussianBlur(22)))
    page.paste(Image.new("RGB", (fw, fh), "white"), (x0, y0))
    page.paste(photo.resize((pw, ph), Image.LANCZOS), (x0 + border, y0 + border))

    d = ImageDraw.Draw(page)
    font = ImageFont.truetype(str(T.FONT_LIGHT), 26)
    tw = d.textlength(CREDIT, font=font)
    d.text(((W - tw) / 2, y0 + fh + 34), CREDIT, font=font, fill=T.INK_2)
    path.parent.mkdir(parents=True, exist_ok=True)
    page.save(path)
    print(f"saved {path.name}")
    return path


FULL = HERE / "charts" / "degania_full.png"


def draw_full(path: Path = FULL) -> Path:
    """Full page (originator, 18 Oct): the photo cropped to 16:9 and enlarged about 3x, which its
    grain survives as an archive look; the top fades into the page colour so the slide title stays
    readable over the trees, and a small credit sits bottom right."""
    from PIL import ImageFilter as F
    im = Image.open(PHOTO).convert("RGB")
    w, h = im.size
    nh = round(w * 9 / 16)
    top = int((h - nh) * 0.35)                                   # keep the dam and the men, lose some sky
    im = im.crop((0, top, w, top + nh)).resize((T.W, T.H), Image.LANCZOS)
    im = im.filter(F.UnsharpMask(radius=2, percent=60, threshold=2))
    fade = Image.new("L", (T.W, T.H), 0)
    d = ImageDraw.Draw(fade)
    band = 300
    for y in range(band):
        d.line([(0, y), (T.W, y)], fill=int(250 * min(1.0, 1.35 * (1 - y / band)) ** 1.2))
    im.paste(Image.new("RGB", (T.W, T.H), T.SURFACE), (0, 0), fade)
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(T.FONT_LIGHT), 22)
    credit = "Degania Dam  ·  Photo: JNF Photo Archive"
    tw = d.textlength(credit, font=font)
    x, y = T.W - tw - 36, T.H - 50
    d.text((x + 2, y + 2), credit, font=font, fill="#000000")
    d.text((x, y), credit, font=font, fill="#FFFFFF")
    im.save(path)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    draw()
    draw_full()
