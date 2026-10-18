"""
build_show.py - the talk as a self-running PowerPoint: one PowerPoint slide per click, each with
its narration, playing on entry and advancing when the narration ends.

Source of truth: review/deck.html (the SLIDES list: image, frames, script). The Q&A backups are
left out. A slide with frames gets one PowerPoint slide per frame, narrated by the matching
paragraph; a slide without frames gets one PowerPoint slide narrated by all its paragraphs. A
slide with no picture yet (image: null) gets a plain card with its question, marked "picture to
come". "[n]" step markers are never read; "[pause]" becomes two seconds of silence.

Narration: Gemini TTS through the TTL skill (~/.claude/skills/TTL/tts.py), one MP3 per click in
show/audio/. A clip is only re-made when its text changed (the text sits beside it as .txt).

Run:  python docs/talk/build_show.py narrate      # make the missing or changed MP3s
      python docs/talk/build_show.py build        # -> docs/talk/Kinneret_Talk_Show.pptx (PowerPoint, COM)
      python docs/talk/build_show.py text         # print the segments and word counts, no API call
"""
from __future__ import annotations

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
VOICE = "Charon"
STYLE = "Read this aloud as a speaker giving a calm, warm conference talk, at a natural pace:"
VIDS = SHOW / "video"
# An animated picture is shown as its video, with the voice mixed in: the frames of a slide that
# share one animation become ONE PowerPoint slide, and each paragraph starts at its beat in the
# (played) video. Optional (speed, until): play the video that much faster up to that second.
# The lake (originator, 2026-10-18): the animation runs on to the split, and the one click is the
# map. Its year-by-year part (to 53 s, where the lake splits) plays 1.4x so the shorter script
# has no long silence; the split plays at its own pace. Beats on the played video: the island
# from the start; "today it sits below the red line" ending on the 11 Nov 2026 stop (52 s / 1.4);
# "which winter is coming?" as the lake splits (53 s / 1.4).
VIDEOS = {"charts/lake_years.gif": ("charts/lake_years.mp4", (2.0, 29.4, 38.0), (1.4, 53.0)),
          "charts/slide1_map.gif": ("charts/slide1_map.mp4", (0.5,), None)}
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
            groups = [([f], [p]) for f, p in zip(frames, paras)]
        else:
            groups = [([s.get("image")], paras)]
        for k, (img, ps) in enumerate(groups, 1):
            pauses = sum(p == "[pause]" for p in ps)
            text = " ".join(p for p in ps if p != "[pause]")
            segs.append({"id": f"s{int(s['n']):02d}_c{k}", "n": s["n"], "q": s["q"], "click": k,
                         "clicks": len(groups), "image": img[0], "text": text, "pause": pauses * PAUSE_S})
    return segs


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


def narrate(standin: bool = False) -> None:
    """Gemini for every missing or changed clip, and for stand-ins. With standin=True, the built-in
    voice fills whatever Gemini can't (its free tier stops after a dozen or so clips a day)."""
    AUDIO.mkdir(parents=True, exist_ok=True)
    gemini = not standin
    for g in segments():
        txt, mp3 = AUDIO / f"{g['id']}.txt", AUDIO / f"{g['id']}.mp3"
        mark = mp3.with_suffix(".standin")
        same = mp3.exists() and txt.exists() and txt.read_text(encoding="utf-8") == g["text"]
        if same and (standin or not mark.exists()):
            continue
        txt.write_text(g["text"], encoding="utf-8")
        print(f"narrating {g['id']} ({len(g['text'].split())} words)", flush=True)
        if gemini:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            r = subprocess.run([sys.executable, str(TTS), str(txt), "-o", str(mp3), "--voice", VOICE,
                                "--style", STYLE], env=env, cwd=HERE.parent.parent)
            if r.returncode == 0:
                mark.unlink(missing_ok=True)
                continue
            sys.exit("Gemini TTS failed (quota?): rerun later, or 'narrate --standin' for the built-in voice")
        offline(txt, mp3)


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
    end = max(c + duration(m) for c, m in zip(cues, clips)) + 0.3
    vdur = duration(HERE / video)
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
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(HERE / video)]
    for m in clips:
        cmd += ["-i", str(m)]
    cmd += ["-filter_complex", f"{play}[vs]tpad=stop_mode=clone:stop_duration={hold:.2f}[v];{mix}",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", str(out)]
    subprocess.run(cmd, check=True)
    return out


def build() -> None:
    import win32com.client
    segs = segments()
    missing = [g["id"] for g in segs if not (AUDIO / f"{g['id']}.mp3").exists()]
    if missing:
        sys.exit(f"no narration yet for {missing}: run 'narrate' first")
    W, H = 960, 540                                              # points, 16:9
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Add(WithWindow=False)
    pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight = W, H
    total = 0.0
    slides_ = groups(segs)
    for i, grp in enumerate(slides_, 1):
        g = grp[0]
        sl = pres.Slides.Add(i, 12)                              # ppLayoutBlank
        sl.FollowMasterBackground = False
        sl.Background.Fill.ForeColor.RGB = 0xF7FAFB              # theme SURFACE #FBFAF7 as BGR
        if g["image"] in VIDEOS:                                 # the animation, voice mixed in
            media = compose(grp)
            snd = sl.Shapes.AddMediaObject2(str(media), False, True, 0, 0, W, H)
            secs = duration(media) + GAP_S
        else:
            img = fill(HERE / g["image"], g["id"]) if g["image"] else card(g)
            sl.Shapes.AddPicture(str(img), False, True, 0, 0, W, H)
            media = AUDIO / f"{g['id']}.mp3"
            snd = sl.Shapes.AddMediaObject2(str(media), False, True, 0, 0, 32, 32)
            snd.Left, snd.Top = -100, -100                       # off the slide: the icon never shows
            snd.AnimationSettings.PlaySettings.HideWhileNotPlaying = True
            secs = duration(media) + g["pause"] + GAP_S
        snd.AnimationSettings.PlaySettings.PlayOnEntry = True
        total += secs
        tr = sl.SlideShowTransition
        tr.EntryEffect = 3849 if g["click"] > 1 else 1793        # fade smoothly within a slide, fade between
        tr.Duration = 0.4 if g["click"] > 1 else 0.7
        tr.AdvanceOnClick = True
        tr.AdvanceOnTime = True
        tr.AdvanceTime = round(secs, 1)
        clicks = f"click {g['click']}" + (f"-{grp[-1]['click']}" if len(grp) > 1 else "")
        sl.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = (
            f"Slide {g['n']} · {g['q']} · {clicks} of {g['clicks']}\n\n" + "\n\n".join(x["text"] for x in grp))
        print(f"{g['id']:8s} {secs:5.1f} s", flush=True)
    pres.SaveAs(str(OUT))
    pres.Close()
    print(f"saved {OUT.name}: {len(slides_)} PowerPoint slides, {total / 60:.1f} min")


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
        narrate(standin="--standin" in sys.argv)
    else:
        {"build": build, "text": text}[cmd]()
