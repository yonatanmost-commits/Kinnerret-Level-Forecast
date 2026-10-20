"""
shoot_app_light.py - the dashboard front page as a slide picture (light theme, big type).

Starts `streamlit run docs/talk/app_light.py` headless, opens it in Edge (Playwright), waits for
the lake picture, and saves:
  charts/app_front.png        16:9, 1600 x 900 CSS px at 1.2x -> 1920 x 1080

With "scroll" (slide 4, originator 20 Oct: full screen, light theme, a slow scroll through the
site): the WHOLE front page (app_light.py's FULL mode), 1280 CSS px wide at 1.5x, as one tall
picture (charts/app_full.png), then a 1920 x 1080 video panning down it (charts/app_scroll.mp4,
60 fps, eased): it rests on the top, scrolls, and rests on the bottom. charts/app_scroll.png is its
first frame, the picture the review page shows.

Run:
  python docs/talk/shoot_app_light.py
  python docs/talk/shoot_app_light.py scroll
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PORT = 8599
URL = f"http://localhost:{PORT}"


def wait_up(timeout: float = 60) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(URL, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("streamlit did not start")


SCROLL_S, REST_TOP_S, REST_END_S, FPS = 44.0, 4.0, 6.0, 60   # about 56 s: slide 4's narration
# The slide title's band: the page starts below it and scrolls up under it, solid page colour to
# BAND px, then a soft edge of FADE px (slide pixels, 1920 x 1080).
BAND, FADE = 200, 50
FOOT = 80                  # the same at the bottom, under the bottom rule and its lake


def main(scroll: bool = False) -> None:
    env = dict(os.environ, KN_TALK_FULL="1" if scroll else "0")
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(HERE / "app_light.py"),
         "--server.headless", "true", "--server.port", str(PORT),
         "--theme.base", "light", "--theme.backgroundColor", "#FBFAF7",
         "--theme.secondaryBackgroundColor", "#F3F1EB", "--theme.textColor", "#1D1D1B",
         "--theme.primaryColor", "#1BA898", "--browser.gatherUsageStats", "false"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        wait_up()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge")
            size, scale = ({"width": 1280, "height": 720}, 1.5) if scroll else ({"width": 1600, "height": 900}, 1.2)
            page = browser.new_page(viewport=size, device_scale_factor=scale)
            page.goto(URL, wait_until="networkidle")
            page.wait_for_selector("img[src^='data:image/svg+xml']", timeout=60000)
            if scroll:
                page.wait_for_selector(".js-plotly-plot", timeout=60000)
            page.wait_for_timeout(3500)          # let the enter animation and the charts settle
            out = HERE / "charts" / ("app_full.png" if scroll else "app_front.png")
            if scroll:                           # Streamlit scrolls inside its own container
                h = page.evaluate("document.querySelector('[data-testid=\"stMain\"]')?.scrollHeight"
                                  " || document.body.scrollHeight")
                page.set_viewport_size({"width": 1280, "height": int(h)})
                page.wait_for_timeout(2500)
            page.screenshot(path=str(out))
            errs = page.locator("[data-testid='stException']").count()
            browser.close()
        print(f"saved charts/{out.name}; app errors on page: {errs}")
    finally:
        server.terminate()
    if scroll:
        pan(HERE / "charts" / "app_full.png")


def pan(full: Path) -> None:
    """The tall page as a 1920 x 1080 video: rest, an eased scroll to the bottom, rest."""
    from PIL import Image
    sys.path.insert(0, str(HERE))
    import theme as T
    im = Image.open(full).convert("RGB")
    im = im.resize((1920, round(im.height * 1920 / im.width)), Image.LANCZOS)
    padded = Image.new("RGB", (1920, im.height + BAND + FOOT), T.SURFACE)
    padded.paste(im, (0, BAND))
    src = full.with_name("app_full_padded.png")
    padded.save(src)
    band = Image.new("RGBA", (1920, 1080), T.SURFACE)             # the still frame over the moving page
    alpha = Image.new("L", band.size, 0)
    alpha.paste(255, (0, 0, 1920, BAND))
    alpha.paste(255, (0, 1080 - FOOT, 1920, 1080))
    for k in range(FADE):
        a = round(255 * (1 - k / FADE) ** 1.5)
        alpha.paste(a, (0, BAND + k, 1920, BAND + k + 1))
        alpha.paste(a, (0, 1080 - FOOT - 1 - k, 1920, 1080 - FOOT - k))
    band.putalpha(alpha)
    top = full.with_name("app_band.png")
    band.save(top)
    travel = padded.height - 1080                        # px to scroll
    t0, t1 = REST_TOP_S, REST_TOP_S + SCROLL_S
    # smoothstep between t0 and t1: slow start, steady middle, slow stop
    u = f"clip((t-{t0})/{SCROLL_S},0,1)"
    y = f"{travel:.1f}*({u}*{u}*(3-2*{u}))"
    total = t1 + REST_END_S
    vid = HERE / "charts" / "app_scroll.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(src),
                    "-i", str(top), "-filter_complex",
                    f"[0:v]crop=1920:1080:0:'{y}'[p];[p][1:v]overlay=0:0,format=yuv420p",
                    "-t", f"{total}", "-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    str(vid)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-frames:v", "1",
                    str(vid.with_suffix(".png"))], check=True)
    print(f"saved charts/{vid.name} ({total:.0f} s, {travel:.0f} px of scroll) and its first frame")


if __name__ == "__main__":
    main(scroll=sys.argv[1:] == ["scroll"])
