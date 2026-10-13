"""
compose_sources.py - the data-sources slide picture: Gemini's fountain scene + the three real logos.

The scene (images/sources_base.jpg) was made by hand in Gemini from images/sources.prompt.txt with
images/centaur.png as the style reference: one fountain wall, three spouts, one basin, and behind
each spout its source - rain (left), river (middle), the lake with its gauge (right). Image models
garble logos, so the scene has none; the real ones are laid on here, each in the open sky above
its own source:
  rain   - Israel Meteorological Service      images/logos/ims_logo.svg
  river  - Hydrological Service of Israel     images/logos/hydro_logo.png
  level  - Kinneret Drainage and Streams Authority (kineret.org.il, the app's level source)
                                              images/logos/kinneret_drainage_logo.png

Run:
  python docs/talk/compose_sources.py      # -> images/sources.png, 1920 x 1080
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
IMAGES = HERE / "images"
LOGOS = IMAGES / "logos"
OUT = IMAGES / "sources.png"
W, H = 1920, 1080

# per logo: centre as shares of the scene picture (x, y), each in clear sky above its source,
# and height as a share of the picture height (sized by eye so the three weigh about the same:
# the square, dark IMS block smallest and tucked in by the cloud, the slim drop tallest)
PLACES = {
    "ims_logo.svg": (0.345, 0.13, 0.100),               # just left of the rain cloud
    "hydro_logo.png": (0.640, 0.15, 0.180),             # above the river
    "kinneret_drainage_logo.png": (0.920, 0.14, 0.160), # above the gauge staff
}


def load(name: str, height: int) -> Image.Image:
    path = LOGOS / name
    if path.suffix == ".svg":
        import resvg_py
        png = resvg_py.svg_to_bytes(svg_path=str(path), height=height * 2)
        img = Image.open(BytesIO(bytes(png))).convert("RGBA")
    else:
        img = Image.open(path).convert("RGBA")
    return img.resize((round(img.width * height / img.height), height), Image.LANCZOS)


def main() -> None:
    scene = Image.open(IMAGES / "sources_base.jpg").convert("RGBA")
    scale = H / scene.height                   # fill the height; trim the empty left edge
    scene = scene.resize((round(scene.width * scale), H), Image.LANCZOS)
    trim = scene.width - W
    scene = scene.crop((trim, 0, scene.width, H))
    for name, (fx, fy, fh) in PLACES.items():
        logo = load(name, round(fh * H))
        cx, cy = fx * (scene.width + trim) - trim, fy * H
        scene.alpha_composite(logo, (round(cx - logo.width / 2), round(cy - logo.height / 2)))
    scene.convert("RGB").save(OUT)
    print(f"saved {OUT.relative_to(HERE.parent.parent)} ({W} x {H})")


if __name__ == "__main__":
    main()
