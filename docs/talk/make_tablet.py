"""
make_tablet.py - slide 4, "The app": the app's front page in a tablet, as a mock-up.

The screenshot (images/app_screen.png, the live app's front page, last reading 18 Oct 2026, given
by the originator) sits in a dark, rounded tablet in landscape, with a soft shadow, on the deck's
page colour. Streamlit's own "Deploy" button and menu (developer chrome, top right) are painted
over with the page's background. The space at top left stays free for the slide title.

Run:  python docs/talk/make_tablet.py        # -> charts/app_tablet.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

SCREEN = HERE / "images" / "app_screen.png"
OUT = HERE / "charts" / "app_tablet.png"
SS = 2                                     # drawn at twice the size, then scaled down
DEV_CHROME = (1690, 8, 1915, 82)           # the Deploy button and menu, in screenshot pixels
BODY, EDGE, CAMERA = "#1C1C1E", "#3A3A3C", "#2C2C2E"


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=255)
    return m


def draw(path: Path = OUT) -> Path:
    shot = Image.open(SCREEN).convert("RGB")
    bg = shot.getpixel((DEV_CHROME[0] - 40, DEV_CHROME[1] + 30))
    ImageDraw.Draw(shot).rectangle(DEV_CHROME, fill=bg)

    W, H = T.W * SS, T.H * SS
    page = Image.new("RGB", (W, H), T.SURFACE)
    sh = 730 * SS                                                # screen height on the slide
    sw = round(sh * shot.width / shot.height)
    bez = 30 * SS
    tw, th = sw + 2 * bez, sh + 2 * bez
    x0, y0 = (W - tw) // 2, 185 * SS                             # below the title band

    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 10 * SS, y0 + 26 * SS, x0 + tw + 10 * SS, y0 + th + 26 * SS],
                                             56 * SS, fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(28 * SS))
    page.paste(Image.new("RGB", (W, H), "#3B342B"), (0, 0), shadow)

    body = Image.new("RGB", (tw, th), BODY)
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([0, 0, tw - 1, th - 1], 56 * SS, outline=EDGE, width=3 * SS)
    cy = th // 2                                                 # the camera, on the left bezel
    d.ellipse([bez // 2 - 5 * SS, cy - 5 * SS, bez // 2 + 5 * SS, cy + 5 * SS], fill=CAMERA)
    page.paste(body, (x0, y0), rounded_mask((tw, th), 56 * SS))

    screen = shot.resize((sw, sh), Image.LANCZOS)
    page.paste(screen, (x0 + bez, y0 + bez), rounded_mask((sw, sh), 14 * SS))

    path.parent.mkdir(parents=True, exist_ok=True)
    page.resize((T.W, T.H), Image.LANCZOS).save(path)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    draw()
