"""
build_show.py - the talk as a self-running PowerPoint: one PowerPoint slide per click, each with
its narration, playing on entry and advancing when the narration ends.

Source of truth: review/deck.html (the SLIDES list: image, frames, script). The Q&A backups are
left out. A slide with frames gets one PowerPoint slide per frame, narrated by the matching
paragraph; a slide without frames gets one PowerPoint slide narrated by all its paragraphs. A
slide with no picture yet (image: null) gets a plain card with its question, marked "picture to
come". "[n]" step markers are never read; "[pause]" becomes two seconds of silence.

Narration: one MP3 per click in show/audio/, one voice for the whole talk. Default: Microsoft's
online neural voices (edge-tts, no key, no quota; en-US-AndrewNeural). Also: Gemini TTS through the
TTL skill (free tier: about a dozen clips a day), or Windows' built-in voice. A clip is re-made
when its text or its engine:voice changed (.txt and .voice beside it).

Run:  python docs/talk/build_show.py narrate      # Edge voice: missing or changed MP3s
      python docs/talk/build_show.py narrate edge en-GB-RyanNeural   # another voice (re-voices all)
      python docs/talk/build_show.py narrate gemini                  # Gemini (daily quota)
      python docs/talk/build_show.py build        # -> docs/talk/Kinneret_Talk_Show.pptx (PowerPoint, COM)
      python docs/talk/build_show.py video        # -> Kinneret_Talk.mp4 + Kinneret_Talk_narration.mp3
      python docs/talk/build_show.py text         # print the segments and word counts, no API call
"""
from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECK = HERE / "review" / "deck.html"
SHOW = HERE / "show"
AUDIO = SHOW / "audio"
CARDS = SHOW / "cards"
OUT = HERE / os.environ.get("SHOW_OUT", "Kinneret_Talk_Show.pptx")
TTS = Path.home() / ".claude" / "skills" / "TTL" / "tts.py"
VOICE = "Charon"                  # Gemini
EDGE_VOICE = "en-US-AndrewNeural"  # Microsoft (originator, 18 Oct: option 1; samples in show/samples)
EDGE_RATE = "-5%"
STYLE = "Read this aloud as a speaker giving a calm, warm conference talk, at a natural pace:"
VIDS = SHOW / "video"
# An animated picture is shown as its video, with the voice mixed in: the frames of a slide that
# share one animation become ONE PowerPoint slide, and each paragraph starts at its beat in the
# (played) video; a beat ("end", t) instead ENDS that paragraph at t (never before the one ahead
# of it is done). Optional (speed, until): play the video that much faster up to that second.
# The lake (originator, 2026-10-18): the animation runs on to the split, and the one click is the
# map. v3, "too slow, too little": its year-by-year part (to 53 s, where the lake splits) plays
# 2x, the split at its own pace, about 35 s in all. Beats on the played video: 2018 and the
# island from the start; "below the red line again" ending on the 11 Nov 2026 stop (52 s / 2);
# "a year from now?" as the lake splits (53 s / 2).
VIDEOS = {"charts/lake_years.gif": ("charts/lake_years.mp4", (1.0, ("end", 26.0), 26.6), (2.0, 53.0)),
          "charts/slide1_map.gif": ("charts/slide1_map.mp4", (0.5,), None),
          # slide 4 (originator, 20 Oct): the app full screen, light, scrolling slowly under the title
          "charts/app_scroll.png": ("charts/app_scroll.mp4", (0.5,), None)}
PAUSE_S = 2.0                     # a "[pause]" in the script
GAP_S = 0.6                       # silence after each clip before the show moves on


def slides() -> list[dict]:
    """The talk's slides from deck.html, in order, without the Q&A backups."""
    t = DECK.read_text(encoding="utf-8")
    a = t.index("const SLIDES")
    b = t.index("\n];", a)
    js = "const S = " + t[a + len("const SLIDES = "):b + 3] + "\nprocess.stdout.write(JSON.stringify(S));"
    out = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, encoding="utf-8",
                         check=True)                     # stdin: the list is too long for a command line
    return [s for s in json.loads(out.stdout) if s.get("n") != "Q&A"]


def segments() -> list[dict]:
    """One entry per click: slide number, click, picture, text to read, extra pause."""
    segs = []
    for s in slides():
        paras = [re.sub(r"^\[\d+\]\s*", "", p).strip() for p in s["script"]]
        frames = s.get("frames")
        if frames:
            groups = []
            for f, p in zip(frames, paras):                      # a frame identical to the one before
                if groups and same_picture(groups[-1][0][0], f):  # is no click (slide 2's last two, 20 Oct)
                    groups[-1][1].append(p)
                else:
                    groups.append(([f], [p]))
        else:
            groups = [([s.get("image")], paras)]
        for k, (img, ps) in enumerate(groups, 1):
            pauses = sum(p == "[pause]" for p in ps)
            text = "\n\n".join(p for p in ps if p != "[pause]")   # paragraphs stay paragraphs in the notes
            segs.append({"id": f"s{int(s['n']):02d}_c{k}", "n": s["n"], "q": s["q"], "click": k,
                         "clicks": len(groups), "image": img[0], "text": text, "pause": pauses * PAUSE_S,
                         "title": s.get("title")})
    return segs


def same_picture(a: str, b: str) -> bool:
    return a == b and a not in VIDEOS or (a != b and (HERE / a).read_bytes() == (HERE / b).read_bytes())


def offline(txt: Path, mp3: Path) -> None:
    """A stand-in clip from Windows' built-in voice, marked so a later Gemini run replaces it."""
    wav = mp3.with_suffix(".wav")
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak([IO.File]::ReadAllText('{txt}')); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(mp3)],
                   check=True)
    wav.unlink()
    mp3.with_suffix(".standin").touch()


def edge(txt: Path, mp3: Path, voice: str) -> None:
    """Microsoft's online neural voices through the edge-tts package: no key, no daily quota."""
    import asyncio
    import edge_tts
    for attempt in range(3):                                     # the service drops a request now and then
        try:
            asyncio.run(edge_tts.Communicate(txt.read_text(encoding="utf-8"), voice, rate=EDGE_RATE).save(str(mp3)))
            return
        except edge_tts.exceptions.NoAudioReceived:
            if attempt == 2:
                raise


def gemini(txt: Path, mp3: Path, voice: str) -> None:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(TTS), str(txt), "-o", str(mp3), "--voice", voice,
                        "--style", STYLE], env=env, cwd=HERE.parent.parent)
    if r.returncode:
        sys.exit("Gemini TTS failed (quota?): rerun later, or narrate with the edge engine")


ENGINES = {"edge": (edge, EDGE_VOICE), "gemini": (gemini, VOICE),
           "standin": (lambda txt, mp3, voice: offline(txt, mp3), "windows")}


def narrate(engine: str = "edge", voice: str | None = None) -> None:
    """One voice for the whole talk: a clip is re-made when its text changed or when it was voiced
    by another engine or voice (the engine:voice tag sits beside it as .voice)."""
    AUDIO.mkdir(parents=True, exist_ok=True)
    make, default = ENGINES[engine]
    voice = voice or default
    tag = f"{engine}:{voice}"
    for g in segments():
        if not g["text"]:                                        # nothing to say yet
            continue
        txt, mp3, vt = (AUDIO / f"{g['id']}{ext}" for ext in (".txt", ".mp3", ".voice"))
        same = (mp3.exists() and txt.exists() and txt.read_text(encoding="utf-8") == g["text"]
                and vt.exists() and vt.read_text(encoding="utf-8") == tag)
        if same:
            continue
        txt.write_text(g["text"], encoding="utf-8")
        print(f"narrating {g['id']} ({len(g['text'].split())} words, {tag})", flush=True)
        make(txt, mp3, voice)
        vt.write_text(tag, encoding="utf-8")
        mp3.with_suffix(".standin").unlink(missing_ok=True)


def duration(mp3: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(mp3)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def card(g: dict) -> Path:
    """A plain card for a slide whose picture isn't made yet: its question, large."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(HERE))
    import theme as T
    CARDS.mkdir(parents=True, exist_ok=True)
    path = CARDS / f"{g['id']}.png"
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    fig.text(0.5, 0.52, g["q"], ha="center", va="center", color=T.INK, fontproperties=T.font(True, 64))
    fig.text(0.5, 0.36, "picture to come", ha="center", va="center", color=T.INK_2,
             fontproperties=T.font(False, 30))
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    return path


def fill(img: Path, sid: str) -> Path:
    """A picture that isn't 16:9 (the centaur photo is 3:2), cropped evenly to fill the slide."""
    from PIL import Image
    im = Image.open(img)
    w, h = im.size
    if abs(w / h - 16 / 9) < 0.01 or getattr(im, "n_frames", 1) > 1:    # 16:9 already, or an animation
        return img
    CARDS.mkdir(parents=True, exist_ok=True)
    nh = round(w * 9 / 16)
    if nh <= h:
        box = (0, (h - nh) // 2, w, (h - nh) // 2 + nh)
    else:
        nw = round(h * 16 / 9)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    out = CARDS / f"{sid}{img.suffix}"
    im.crop(box).save(out, quality=92)
    return out


def groups(segs: list[dict]) -> list[list[dict]]:
    """PowerPoint slides: consecutive clicks on the same animation are one slide; others one each."""
    out = []
    for g in segs:
        if out and g["image"] in VIDEOS and out[-1][-1]["image"] == g["image"] \
                and out[-1][-1]["n"] == g["n"]:
            out[-1].append(g)
        else:
            out.append([g])
    return out


def compose(grp: list[dict]) -> Path:
    """The animation's video with its paragraphs laid on at their beats; the last frame is held
    while the voice still runs."""
    video, cues, speed = VIDEOS[grp[0]["image"]]
    clips = [AUDIO / f"{g['id']}.mp3" for g in grp]
    if len(cues) != len(clips):
        sys.exit(f"{video}: {len(cues)} beats for {len(clips)} paragraphs")
    VIDS.mkdir(parents=True, exist_ok=True)
    out = VIDS / f"{grp[0]['id']}.mp4"
    starts, free = [], 0.0
    for c, m in zip(cues, clips):
        s = c[1] - duration(m) if isinstance(c, (tuple, list)) else c
        s = max(s, free)
        starts.append(s)
        free = s + duration(m) + 0.4
    cues = starts
    end = max(c + duration(m) for c, m in zip(cues, clips)) + 0.3
    src = native(HERE / video)[0]                                # without its native words
    vdur = duration(src)
    if speed:
        k, until = speed
        play = (f"[0:v]trim=0:{until},setpts=(PTS-STARTPTS)/{k}[v1];"
                f"[0:v]trim={until},setpts=PTS-STARTPTS[v2];[v1][v2]concat=n=2:v=1:a=0[vs];")
        vdur = until / k + (vdur - until)
    else:
        play = "[0:v]null[vs];"
    hold = max(0.0, end - vdur)
    mix = "".join(f"[{i + 1}]adelay={int(c * 1000)}[a{i}];" for i, c in enumerate(cues))
    mix += "".join(f"[a{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[a]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    for m in clips:
        cmd += ["-i", str(m)]
    cmd += ["-filter_complex", f"{play}[vs]tpad=stop_mode=clone:stop_duration={hold:.2f}[v];{mix}",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", str(out)]
    subprocess.run(cmd, check=True)
    return out


TITLE_X, TITLE_Y, TITLE_PT = 45, 18, 40      # points on a 960 x 540 slide: top left, the theme's title spot
PT = 0.5                                     # slide points per px of the 1920 x 1080 pictures


# The lake icon fills over the talk (originator, 20 Oct): it starts at the red line on slide 1
# and rises in equal steps to the upper line on slide 12, a full lake by the end.
ICON_FROM, ICON_TO, ICON_SLIDES = -213.0, -208.9, 12          # the lower and upper red lines, m


def icon_levels() -> dict[int, float]:
    """Talk slide number -> the icon's water level."""
    step = (ICON_TO - ICON_FROM) / (ICON_SLIDES - 1)
    return {n: ICON_FROM + step * (n - 1) for n in range(1, ICON_SLIDES + 1)}


@functools.cache
def lake_icon(level: float) -> Path:
    """The small lake at the end of the bottom rule: the app's outline, water up to `level`."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Polygon, Rectangle
    sys.path.insert(0, str(HERE))
    import theme as T
    from chart_fan import lake_outline
    out = CARDS / f"lake_icon_{level:.2f}.png"
    CARDS.mkdir(parents=True, exist_ok=True)
    x, lvl, units = lake_outline()
    h = T.LAKE_ICON["h"]
    w = h * (x.max() - x.min()) / ((lvl.max() - lvl.min()) * units)
    fig = plt.figure(figsize=(w * 4 / 100, h * 4 / 100), dpi=100)          # drawn at 4x
    ax = fig.add_axes([0.04, 0.03, 0.92, 0.94])
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(lvl.min(), lvl.max())
    ax.axis("off")
    lake = Polygon(np.c_[x, lvl], closed=True, fc=T.UNUSED, ec="none")
    ax.add_patch(lake)
    water = Rectangle((x.min(), lvl.min()), x.max() - x.min(), level - lvl.min(), fc=T.USED, ec="none")
    ax.add_patch(water)
    water.set_clip_path(lake)
    ax.plot(x, lvl, color=T.USED, lw=5)
    fig.savefig(out, transparent=True)
    plt.close(fig)
    return out


@functools.cache
def rules() -> Path:
    """The two rules, as one transparent picture (the staff-gauge ticks were tried and dropped, 20 Oct)."""
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(HERE))
    import theme as T
    out = CARDS / "frame_rules.png"
    CARDS.mkdir(parents=True, exist_ok=True)
    k = 2                                                         # drawn at twice the size
    im = Image.new("RGBA", (T.W * k, T.H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for r in (T.TITLE_RULE, T.BOTTOM_RULE):
        y, w = r["y"], r["width"]
        d.rectangle([r["x0"] * k, (y - w / 2) * k, r["x1"] * k, (y + w / 2) * k], fill=T.USED)
    im.resize((T.W, T.H), Image.LANCZOS).save(out)
    return out


def frame(sl, n: int) -> None:
    """The theme's frame: the gauge rules, and the lake at the bottom rule's end at slide n's level."""
    sys.path.insert(0, str(HERE))
    import theme as T
    r = sl.Shapes.AddPicture(str(rules()), False, True, 0, 0, T.W * PT, T.H * PT)
    r.Name = "!!rules"
    r.Tags.Add("owner", "build")
    k = T.LAKE_ICON
    icon = sl.Shapes.AddPicture(str(lake_icon(round(icon_levels()[n], 2))), False, True, k["x"] * PT, k["y"] * PT)
    icon.LockAspectRatio = True
    icon.Height = k["h"] * PT
    icon.Name = "!!lake"                                          # Morph pairs the "!!" names across slides
    icon.Tags.Add("owner", "build")


def bgr(hex_: str) -> int:
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return r + (g << 8) + (b << 16)


def style_text(rng, pt: float, bold: bool, bgr: int) -> None:
    rng.Font.Name = "Segoe UI Semibold" if bold else "Segoe UI Semilight"
    rng.Font.Size = pt
    rng.Font.Color.RGB = bgr                                     # PowerPoint colours are BGR


FADE_IN, WITH_PREVIOUS, AFTER_PREVIOUS, MEDIA_PLAY = 10, 2, 3, 83   # PowerPoint animation constants
MORPH = 3954                                                     # ppEffectMorphByObject (3953 is an Origami, 20 Oct)


def native(path: Path) -> tuple[Path, list[dict]]:
    """The picture (or video) without its native words, and those words, when the chart made them
    (theme.Labels: bare/<name> + bare/<stem>.labels.json); otherwise the picture as it is."""
    bare = path.parent / "bare" / path.name
    meta = path.parent / "bare" / f"{path.stem}.labels.json"
    if bare.exists() and meta.exists():
        return bare, json.loads(meta.read_text(encoding="utf-8"))["labels"]
    return path, []


def labels_of(image: str | None) -> list[dict]:
    if not image:
        return []
    return native(HERE / (VIDEOS[image][0] if image in VIDEOS else image))[1]


def join_videos(steps: list[list[dict]]) -> list[list[dict]]:
    """Back-to-back animations of one slide as ONE video (slide 1: the lake, then the map). Two
    videos jump: PowerPoint snaps the first back to its opening frame before the second fades in.
    The joined step keeps each part's words and the second it starts at ("parts")."""
    out = []
    for grp in steps:
        prev = out[-1] if out else None
        if prev and grp[0]["image"] in VIDEOS and (prev[0].get("video") or prev[0]["image"] in VIDEOS):
            a = prev[0].get("video") or compose(prev)
            b = compose(grp)
            joined = VIDS / f"{prev[0]['id']}_joined.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-i", str(b), "-filter_complex",
                            "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
                            str(joined)], check=True)
            parts = prev[0].get("parts") or [(labels_of(prev[0]["image"]), 0.0)]
            parts = parts + [(labels_of(grp[0]["image"]), duration(a))]
            out[-1] = [dict(prev[0], video=joined, parts=parts)] + prev[1:] + grp
        else:
            out.append(grp)
    return out


# Native text (originator, 20 Oct: "so i can design some of it by hand"). The build owns what it
# tags "build" (pictures, sound, frame) and remakes it every time. A text box it tags "label" is
# shared: its place, size and look are the hand's; its words follow the chart unless they were
# changed by hand. Anything untagged is the hand's alone and is left as it is.
OWNER, SRC, GEOM, TALK_TAG = "owner", "src", "geom", "talk"
ALIGN = {"left": 1, "center": 2, "right": 3}                 # ppAlignLeft / Center / Right
ANCHOR = {"top": 1, "middle": 3}                             # msoAnchorTop / Middle


def title_spec(words: str, W: float) -> dict:
    return {"name": "!!title", "text": words, "geom": [TITLE_X, TITLE_Y, W - 2 * TITLE_X, 60], "ha": "left",
            "va": "top", "pt": TITLE_PT, "bold": True, "color": "#1D1D1B", "lines": 1}


def geom(spec: dict) -> list[float]:
    """Left, top, width, height in points: a chart's box (px on the 1920 x 1080 picture) or as given."""
    if "geom" in spec:
        return [round(v, 1) for v in spec["geom"]]
    x0, y0, x1, y1 = spec["box"]
    return [round(v * PT, 1) for v in (x0, y0, x1 - x0, y1 - y0)]


def words_of(shape) -> str:
    return shape.TextFrame.TextRange.Text.replace("\r", "\n").replace("\x0b", "\n")


def new_box(sl, spec: dict):
    l, t, w, h = geom(spec)
    tb = sl.Shapes.AddTextbox(1, l, t, w, h)
    tb.Name = spec["name"]
    tf = tb.TextFrame
    tf.MarginLeft = tf.MarginTop = tf.MarginRight = tf.MarginBottom = 0   # the text edge IS the box
    tf.WordWrap = False
    tf.AutoSize = 0                                          # ppAutoSizeNone: the box stays where it is put
    tf.VerticalAnchor = ANCHOR[spec.get("va", "middle")]
    tf.TextRange.Text = spec["text"].replace("\n", "\r")
    style_text(tf.TextRange, spec["pt"], spec["bold"], bgr(spec["color"]))
    p = tf.TextRange.ParagraphFormat
    p.Alignment = ALIGN[spec["ha"]]
    if spec.get("lines", 1) > 1:                             # the chart's line pitch
        p.LineRuleWithin = 0
        p.SpaceWithin = spec.get("pitch", round(spec["pt"] * 1.2, 1))
    tb.Left, tb.Top, tb.Width, tb.Height = l, t, w, h        # typing may have resized it
    return tb


def merge_box(shape, spec: dict, where: str, warnings: list[str]) -> None:
    """A label box from the last build: the chart's new words and place, unless set by hand."""
    old_src, new = shape.Tags(SRC), spec["text"]
    if words_of(shape) == old_src:
        if new != old_src:
            shape.TextFrame.TextRange.Text = new.replace("\n", "\r")
    elif new != old_src:
        warnings.append(f"{where} '{spec['name']}': kept your words {words_of(shape)!r}; "
                        f"the chart now says {new!r}")
    now = [shape.Left, shape.Top, shape.Width, shape.Height]
    placed = [float(v) for v in shape.Tags(GEOM).split(",")]
    if all(abs(a - b) < 0.5 for a, b in zip(now, placed)):  # not moved by hand: follow the chart
        shape.Left, shape.Top, shape.Width, shape.Height = geom(spec)


def tag(shape, **kv) -> None:
    for k, v in kv.items():
        shape.Tags.Add(k, v)


def spans(shown: list[tuple[float, list[dict]]]) -> dict[str, list]:
    """name -> [label, second it appears, second it goes (None: stays)], from (second, labels) steps."""
    out, prev = {}, set()
    for t, labels in shown:
        names = {d["name"] for d in labels}
        for d in labels:
            out.setdefault(d["name"], [d, t, None])
        for nm in prev - names:
            if out[nm][2] is None:
                out[nm][2] = t
        prev = names
    return out


def open_show(app, out: Path, W: float, H: float):
    """The last build of the show, to update; or a new one. A show the build never tagged (before
    20 Oct) is started afresh: nothing in it was placed by hand."""
    if out.exists():
        if out.with_name("~$" + out.name).exists():
            sys.exit(f"{out.name} is open in PowerPoint (or its lock file ~${out.name} was left behind): "
                     f"close it first, or build to another file with SHOW_OUT")
        pres = app.Presentations.Open(str(out), WithWindow=False)
        if any(sl.Tags(TALK_TAG) for sl in pres.Slides):
            return pres, True
        pres.Close()
        print(f"{out.name} was made before native text: building it afresh")
    pres = app.Presentations.Add(WithWindow=False)
    pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight = W, H
    return pres, False


def build(out: Path = OUT, segs: list[dict] | None = None, audio: Path = AUDIO) -> list[str]:
    """One PowerPoint slide per talk slide (originator, 20 Oct: no duplicated slides for clicks).
    Each click is a timed step inside the slide: its picture fades in over the last one and its
    narration plays; an animation is one video with the voice mixed in. The steps hang off the
    slide's start (the first after the transition, the rest with it, each at its own delay).
    A chart's native words are text boxes that fade in and out with the pictures that carry them,
    and hand edits to them survive a rebuild (see OWNER above). Title, rules and lake sit on top.
    Returns the warnings: hand-set words the chart has since changed."""
    import win32com.client
    segs = segs if segs is not None else segments()
    missing = [g["id"] for g in segs if g["text"] and not (audio / f"{g['id']}.mp3").exists()]
    if missing:
        sys.exit(f"no narration yet for {missing}: run 'narrate' first")
    W, H = 960, 540                                              # points, 16:9
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres, update = open_show(app, out, W, H)
    warnings: list[str] = []
    try:
        total = 0.0
        talk = []                                                # the steps, grouped by talk slide
        for grp in groups(segs):
            if talk and talk[-1][0][0]["n"] == grp[0]["n"]:
                talk[-1].append(grp)
            else:
                talk.append([grp])
        ns = {s[0][0]["n"] for s in talk}
        mine = {}
        for sl in list(pres.Slides):
            n = sl.Tags(TALK_TAG)
            if n and n not in ns:                                # a talk slide that left the talk
                sl.Delete()
            elif n:
                mine[n] = sl
        for i, steps in enumerate(talk, 1):
            steps = join_videos(steps)
            g = steps[0][0]
            sl = mine.get(g["n"])
            if sl is None:
                sl = pres.Slides.Add(min(i, pres.Slides.Count + 1), 12)   # ppLayoutBlank
                tag(sl, **{TALK_TAG: g["n"]})
            sl.MoveTo(min(i, pres.Slides.Count))
            sl.FollowMasterBackground = False
            sl.Background.Fill.ForeColor.RGB = 0xF7FAFB          # theme SURFACE #FBFAF7 as BGR
            seq = sl.TimeLine.MainSequence
            for k in range(seq.Count, 0, -1):                    # the timing is rebuilt
                seq.Item(k).Delete()
            for sh in [sh for sh in sl.Shapes if sh.Tags(OWNER) == "build"]:
                sh.Delete()
            boxes = {sh.Name: sh for sh in sl.Shapes if sh.Tags(OWNER) == "label"}
            t = 0.0
            shown = []                                           # (second, labels) per step
            for k, grp in enumerate(steps):
                s0 = grp[0]
                if s0.get("video") or s0["image"] in VIDEOS:     # the animation, voice mixed in
                    media = s0.get("video") or compose(grp)
                    shape = player = sl.Shapes.AddMediaObject2(str(media), False, True, 0, 0, W, H)
                    tag(shape, **{OWNER: "build"})
                    secs = duration(media) + GAP_S
                else:
                    img = fill(native(HERE / s0["image"])[0], s0["id"]) if s0["image"] else card(s0)
                    shape = sl.Shapes.AddPicture(str(img), False, True, 0, 0, W, H)
                    clip = audio / f"{s0['id']}.mp3"
                    player = sl.Shapes.AddMediaObject2(str(clip), False, True, 0, 0, 32, 32)
                    player.Left, player.Top = -100, -100         # off the slide: the icon never shows
                    # (no PlaySettings here: touching them adds PowerPoint's own play effect to the
                    # sequence and every later delay slips, measured 20 Oct)
                    tag(shape, **{OWNER: "build"})
                    tag(player, **{OWNER: "build"})
                    secs = duration(clip) + s0["pause"] + GAP_S
                if k:                                            # the new picture fades in over the last
                    e = seq.AddEffect(shape, FADE_IN, 0, WITH_PREVIOUS)
                    e.Timing.Duration = 0.4
                    e.Timing.TriggerDelayTime = round(t, 2)
                e = seq.AddEffect(player, MEDIA_PLAY, 0, WITH_PREVIOUS if k else AFTER_PREVIOUS)
                e.Timing.TriggerDelayTime = round(t, 2)
                for labels, off in s0.get("parts") or [(labels_of(s0["image"]), 0.0)]:
                    shown.append((t + off, labels))
                t += secs
            want = spans(shown)
            if g["title"]:                                       # the boldest, biggest thing on the slide
                want["!!title"] = [title_spec(g["title"], W), 0.0, None]
            where = f"slide {g['n']}"
            for name, sh in list(boxes.items()):                 # words the chart no longer has
                if name not in want:
                    if words_of(sh) != sh.Tags(SRC):
                        warnings.append(f"{where} '{name}': the chart dropped it, and your words "
                                        f"{words_of(sh)!r} with it")
                    sh.Delete()
                    del boxes[name]
            for name, (spec, t_in, t_out) in want.items():
                if name in boxes:
                    sh = boxes[name]
                    merge_box(sh, spec, where, warnings)
                else:
                    sh = new_box(sl, spec)
                tag(sh, **{OWNER: "label", SRC: spec["text"], GEOM: ",".join(str(v) for v in geom(spec))})
                for at, leave in ((t_in, False), (t_out, True)):
                    if at:                                       # 0 / None: there from the start / to the end
                        e = seq.AddEffect(sh, FADE_IN, 0, WITH_PREVIOUS)
                        e.Exit = -1 if leave else 0              # msoTrue: fade out
                        e.Timing.Duration = 0.4
                        e.Timing.TriggerDelayTime = round(at, 2)
            for sh in [sh for sh in sl.Shapes if sh.Tags(OWNER) != "build"]:
                sh.ZOrder(0)                                     # msoBringToFront: words above the pictures
            if g["title"]:
                frame(sl, int(g["n"]))
            total += t
            tr = sl.SlideShowTransition
            tr.EntryEffect = MORPH                               # between slides (originator, 20 Oct)
            tr.Duration = 1.0
            tr.AdvanceOnClick = True
            tr.AdvanceOnTime = True
            tr.AdvanceTime = round(t, 1)
            clicks = [x for grp in steps for x in grp]
            sl.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = (
                f"Slide {g['n']} · {g['q']} · {len(clicks)} click(s)\n\n" + "\n\n".join(x["text"] for x in clicks))
            print(f"slide {g['n']:>2s}: {len(steps)} step(s), {len(want)} text box(es), {t:5.1f} s", flush=True)
        if update:
            pres.Save()
        else:
            pres.SaveAs(str(out))
    finally:
        pres.Close()
    for w in warnings:
        print("WARNING", w)
    print(f"saved {out.name}: {len(talk)} PowerPoint slides, {total / 60:.1f} min")
    return warnings


VIDEO = HERE / "Kinneret_Talk.mp4"
NARRATION = HERE / "Kinneret_Talk_narration.mp3"


def video() -> None:
    """The built show as a 1080p video with PowerPoint's own renderer (timings and narration), and
    its sound track as one MP3."""
    import time
    import win32com.client
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(str(OUT), ReadOnly=True, WithWindow=False)
    pres.CreateVideo(str(VIDEO), True, 5, 1080, 30, 90)
    while pres.CreateVideoStatus in (1, 2):                      # in progress, or queued
        time.sleep(5)
    status = pres.CreateVideoStatus
    pres.Close()
    if status != 3:                                              # ppMediaTaskStatusDone
        sys.exit(f"PowerPoint could not make the video (status {status})")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(VIDEO), "-vn", "-ac", "1",
                    "-b:a", "96k", str(NARRATION)], check=True)
    print(f"saved {VIDEO.name} and {NARRATION.name}: {duration(VIDEO) / 60:.1f} min")


def text() -> None:
    w = 0
    for g in segments():
        n = len(g["text"].split())
        w += n
        print(f"{g['id']:8s} {n:4d}  {g['image']}")
    print(f"total {w} words")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "text"
    if cmd == "narrate":
        args = sys.argv[2:]
        narrate(args[0] if args else "edge", args[1] if len(args) > 1 else None)
    else:
        {"build": build, "video": video, "text": text}[cmd]()
