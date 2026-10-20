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

# The deck's colours, painted lightly on the grey print (originator, 20 Oct: "teal for the water"):
# the greys run from a warm ink through sand to the page colour, and the river under the dam is
# washed in teal. Stops are (grey level, colour).
TONES = [(0, "#26302E"), (110, "#6E675B"), (190, "#D8D0BF"), (255, T.SURFACE)]
# the river below the dam, in slide pixels (1920 x 1080), traced on the cropped photo
WATER = [(905, 676), (1185, 668), (1290, 700), (1400, 750), (1520, 810), (1600, 875), (1720, 935),
         (1920, 965), (1920, 1080), (1520, 1080), (1330, 990), (1170, 880), (1040, 780)]
WATER_ALPHA = 0.5
TREES = (0, 0, 1920, 640)               # the tree line above the banks: its dark tones turn faintly sage
TREE_ALPHA = 0.35


def tint(grey: Image.Image) -> Image.Image:
    """A grey picture through the deck's tone ramp, with the river washed teal."""
    lut = []
    for c in range(3):
        for v in range(256):
            for (a, ca), (b, cb) in zip(TONES, TONES[1:]):
                if a <= v <= b:
                    x = (v - a) / (b - a)
                    lo, hi = int(ca[1 + 2 * c:3 + 2 * c], 16), int(cb[1 + 2 * c:3 + 2 * c], 16)
                    lut.append(round(lo + (hi - lo) * x))
                    break
    toned = Image.merge("RGB", [grey.point(lut[256 * c:256 * (c + 1)]) for c in range(3)])
    # teal water keeps the photo's light and dark: the grey scaled between deep and light teal
    water = Image.merge("RGB", [grey.point(lambda v, lo=lo, hi=hi: round(lo + (hi - lo) * v / 255))
                                for lo, hi in zip((0x0B, 0x4F, 0x4C), (0xC9, 0xEE, 0xE7))])
    mask = Image.new("L", grey.size, 0)
    ImageDraw.Draw(mask).polygon(WATER, fill=round(255 * WATER_ALPHA))
    mask = mask.filter(ImageFilter.GaussianBlur(28))
    toned.paste(water, (0, 0), mask)
    sage = Image.merge("RGB", [grey.point(lambda v, lo=lo, hi=hi: round(lo + (hi - lo) * v / 255))
                               for lo, hi in zip((0x1E, 0x36, 0x2E), (0xE4, 0xE6, 0xD8))])
    leaves = grey.point(lambda v: round(255 * TREE_ALPHA * max(0.0, 1 - v / 140)))   # the darker, the greener
    box = Image.new("L", grey.size, 0)
    ImageDraw.Draw(box).rectangle(TREES, fill=255)
    toned.paste(sage, (0, 0), Image.composite(leaves, box, box).filter(ImageFilter.GaussianBlur(6)))
    return toned


def draw_full(path: Path = FULL) -> Path:
    """Full page (originator, 18 Oct): the photo cropped to 16:9 and enlarged about 3x, which its
    grain survives as an archive look; the top fades into the page colour so the slide title stays
    readable over the trees, and a small credit sits bottom right."""
    from PIL import ImageFilter as F
    im = Image.open(PHOTO).convert("RGB")
    w, h = im.size
    nh = round(w * 9 / 16)
    top = int((h - nh) * 0.35)                                   # keep the dam and the men, lose some sky
    from PIL import ImageOps
    im = im.crop((0, top, w, top + nh)).convert("L")
    im = ImageOps.autocontrast(im, cutoff=0.1)                   # a faded print: a touch more of the grey range
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS) # enlarge in two steps, sharpening between
    im = im.filter(F.UnsharpMask(radius=1.0, percent=110, threshold=4))
    im = im.resize((T.W, T.H), Image.LANCZOS)
    im = im.filter(F.UnsharpMask(radius=1.6, percent=70, threshold=4))
    im = tint(im)
    fade = Image.new("L", (T.W, T.H), 0)
    d = ImageDraw.Draw(fade)
    band = 300
    for y in range(band):
        d.line([(0, y), (T.W, y)], fill=int(250 * min(1.0, 1.35 * (1 - y / band)) ** 1.2))
    im.paste(Image.new("RGB", (T.W, T.H), T.SURFACE), (0, 0), fade)
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(T.FONT_LIGHT), round(T.CREDIT_PT * T.DPI / 72))
    credit = "Degania Dam  ·  Photo: JNF Photo Archive"
    x, y = T.CREDIT_XY                                           # the theme's credit spot, bottom left
    d.text((x + 2, y + 2), credit, font=font, fill="#000000", anchor="ls")
    d.text((x, y), credit, font=font, fill="#FFFFFF", anchor="ls")
    im.save(path)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    draw()
    draw_full()
