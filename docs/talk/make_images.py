"""
make_images.py - the deck's pictures, in docs/talk/images/ (plan D11, D18).

Three kinds, one command:
  title.png        the app front page's lake picture, build_lake_svg(freeze level) from
                   kinneret_app/app_utils.py, with every text label removed (no number on the
                   title slide, spec R13), rasterized with resvg
  qr.png           QR code to the online app (segno). Until APP_URL is set it is a plain
                   placeholder square that says so - never a code that points nowhere
  <name>.png       metaphor pictures from Gemini, one per <name>.prompt.txt beside it; the prompt
                   file holds exactly what is sent, so a picture can be remade or reworded

Run:
  python docs/talk/make_images.py                  # make whatever is missing
  python docs/talk/make_images.py --only centaur   # (re)make one picture
  python docs/talk/make_images.py --force          # remake everything

GEMINI_API_KEY is read from the repo-root .env and never printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMAGES = HERE / "images"
LEDGER_PATH = HERE / "numbers_ledger.json"

APP_URL: str | None = "https://kinnerret-level-forecast-oxgcqpgurba4iyfxkwhkol.streamlit.app/"
GEMINI_MODEL = "gemini-3-pro-image"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
WIDTH_PX = 2000


# ─── title: the app's lake picture ──────────────────────────────────────────

def make_title(out: Path) -> Path:
    import resvg_py
    sys.path.insert(0, str(ROOT / "kinneret_app"))
    from app_utils import build_lake_svg
    level = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))["level.freeze_m"]["value"]
    svg = re.sub(r"<text\b.*?</text>", "", build_lake_svg(level), flags=re.S)
    out.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=WIDTH_PX)))
    from PIL import Image                       # trim the margin the labels used to fill
    img = Image.open(out)
    pad = WIDTH_PX // 40
    l, t, r, b = img.getchannel("A").getbbox()
    img.crop((l - pad, t - pad, r + pad, b + pad)).save(out)
    return out


# ─── QR code to the app ─────────────────────────────────────────────────────

def make_qr(out: Path) -> Path:
    if APP_URL:
        import segno
        segno.make(APP_URL, error="m").save(out, scale=20, border=2, dark="#0b0b0b", light="#fcfcfb")
        return out
    from PIL import Image, ImageDraw, ImageFont
    size = 600
    img = Image.new("RGB", (size, size), "#fcfcfb")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, size - 10, size - 10], outline="#a8a7a1", width=8)
    try:
        font = ImageFont.truetype("segoeui.ttf", 56)
    except OSError:
        font = ImageFont.load_default()
    d.multiline_text((size / 2, size / 2), "QR\napp link\nto come", fill="#52514e", font=font,
                     anchor="mm", align="center", spacing=12)
    img.save(out)
    return out


# ─── metaphor pictures: Gemini ──────────────────────────────────────────────

def _gemini_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*GEMINI_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
        if m:
            return m.group(1)
    raise SystemExit("GEMINI_API_KEY not found in .env")


def make_metaphor(prompt_file: Path, out: Path) -> Path:
    body = {"contents": [{"parts": [{"text": prompt_file.read_text(encoding="utf-8").strip()}]}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": "16:9"}}}
    req = urllib.request.Request(GEMINI_URL.format(model=GEMINI_MODEL),
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"x-goog-api-key": _gemini_key(),
                                          "Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=300))
    for part in resp["candidates"][0]["content"]["parts"]:
        data = part.get("inlineData") or part.get("inline_data")
        if data:
            out.write_bytes(base64.b64decode(data["data"]))
            return out
    raise SystemExit(f"{prompt_file.name}: Gemini returned no image")


# ─── main ───────────────────────────────────────────────────────────────────

def jobs() -> dict[str, callable]:
    found = {"title": make_title, "qr": make_qr}
    for p in sorted(IMAGES.glob("*.prompt.txt")):
        name = p.name[:-len(".prompt.txt")]
        found[name] = lambda out, p=p: make_metaphor(p, out)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="make just this picture (repeatable)")
    ap.add_argument("--force", action="store_true", help="remake pictures that already exist")
    args = ap.parse_args()
    IMAGES.mkdir(exist_ok=True)
    todo = jobs()
    for name in args.only or todo:
        if name not in todo:
            raise SystemExit(f"no picture called {name!r}; known: {', '.join(todo)}")
        out = IMAGES / f"{name}.png"
        if out.exists() and not (args.force or args.only):
            continue
        todo[name](out)
        print("made", out.relative_to(HERE))


if __name__ == "__main__":
    main()
