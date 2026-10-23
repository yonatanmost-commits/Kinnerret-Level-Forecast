"""
build_clean.py - the talk as the PowerPoint we hand in (originator, 23 Oct): to Adnan for review,
then to the conference. No narration and no timings: every step waits for a mouse click, videos
too. The notes are short plain words a reader can follow (deck.html's `reader`), not the script.

The frame lives on the master: the page colour and the bar under the title (the bottom rule is
gone: originator, 23 Oct, "it makes the bottom area too compressed"). The small lake stays on each
slide, an SVG rising from the red line on slide 1 to full on slide 12, as in the show.

Source of truth: review/deck.html, the same pictures and native words as build_show.py. Every
picture and video is cropped to start under the title rule, so the master's rule always shows.
Each run builds the deck afresh; hand edits are diffed and folded back into the source.

Run:  python docs/talk/build_clean.py   # -> docs/talk/Kinneret_Talk_Submission.pptx (PowerPoint, COM)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_show as B                                          # noqa: E402  segments, pictures, native words
import theme as T                                               # noqa: E402

OUT = HERE / os.environ.get("CLEAN_OUT", "Kinneret_Talk_Submission.pptx")
CLIPS = B.SHOW / "clean"
W, H = 960, 540                                                 # points, 16:9
BAND_PX = 154                                                   # the title rule's lower edge (y 152 + half its width)
ON_CLICK, WITH_PREVIOUS, AFTER_PREVIOUS = 1, 2, 3               # msoAnimTrigger*
APPEAR, FADE = 1, B.FADE_IN                                     # msoAnimEffect*
LATIN = 1                                                       # msoThemeLatin
FADE_SMOOTHLY = 1793                                            # ppEffectFadeSmoothly
START_HOLD_S = 0.15                                             # the first-frame still leaves this long after play


def under_band(img: Path, sid: str) -> Path:
    """The picture from the title rule down (the charts keep that band empty; the Degania photo
    loses a strip of sky)."""
    from PIL import Image
    CLIPS.mkdir(parents=True, exist_ok=True)
    im = Image.open(img)
    k = im.height / T.H
    out = CLIPS / f"{sid}{img.suffix}"
    im.crop((0, round(BAND_PX * k), im.width, im.height)).save(out)
    return out


def silent(image: str) -> tuple[Path, Path, Path]:
    """The animation as it plays on the slide: without its native words, at the show's speed,
    without sound, from the title rule down; and its first and last frames."""
    video, _, speed = B.VIDEOS[image]
    src = B.native(HERE / video)[0]
    CLIPS.mkdir(parents=True, exist_ok=True)
    out = CLIPS / f"{Path(video).stem}.mp4"
    if speed:
        k, until = speed
        play = (f"[0:v]trim=0:{until},setpts=(PTS-STARTPTS)/{k}[v1];"
                f"[0:v]trim={until},setpts=PTS-STARTPTS[v2];[v1][v2]concat=n=2:v=1:a=0[vs];")
    else:
        play = "[0:v]null[vs];"
    crop = f"[vs]crop=iw:ih-ih*{BAND_PX}/{T.H}:0:ih*{BAND_PX}/{T.H}[v]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", play + crop,
                    "-map", "[v]", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-movflags", "+faststart", str(out)], check=True)
    first, last = out.with_name(f"{out.stem}_first.png"), out.with_name(f"{out.stem}_last.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-frames:v", "1", "-update", "1",
                    str(first)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", str(out), "-frames:v", "1",
                    "-update", "1", str(last)], check=True)
    return out, first, last


def master(pres):
    """The page colour, the theme's fonts and colours, the rule under the title, and one layout:
    the title in the spot every slide shares."""
    m = pres.SlideMaster
    m.Background.Fill.Solid()
    m.Background.Fill.ForeColor.RGB = B.bgr(T.SURFACE)
    th = m.Theme
    th.ThemeFontScheme.MajorFont(LATIN).Name = "Segoe UI Semibold"
    th.ThemeFontScheme.MinorFont(LATIN).Name = "Segoe UI Semilight"
    for i, c in enumerate([T.INK, "#FFFFFF", T.INK_2, T.SURFACE, T.USED, T.RED, T.USED_DEEP, T.AMBER,
                           T.USED_LIGHT, T.FAINT, T.USED_TEXT, T.INK_2], 1):   # dk1 lt1 dk2 lt2 accent1-6 hlink folHlink
        th.ThemeColorScheme.Colors(i).RGB = B.bgr(c)
    B.title_bar(m.Shapes)                                        # the originator's bar (23 Oct)
    layout = next(cl for cl in m.CustomLayouts if cl.Name == "Title Only")
    for cl in list(m.CustomLayouts):
        if cl.Name != "Title Only":
            cl.Delete()
    layout.Name = "Kinneret title"
    for place in (m.Shapes, layout.Shapes):
        for sh in list(place):
            if sh.Type == 14 and sh.PlaceholderFormat.Type == 1:   # msoPlaceholder, ppPlaceholderTitle
                title_style(sh)
            elif sh.Type == 14 and place is layout.Shapes:          # date, footer, number: none
                sh.Delete()
    return layout


def title_style(sh) -> None:
    sh.Left, sh.Top, sh.Width, sh.Height = B.TITLE_X, B.TITLE_Y, W - 2 * B.TITLE_X, 60
    tf = sh.TextFrame
    tf.MarginLeft = tf.MarginTop = tf.MarginRight = tf.MarginBottom = 0
    tf.AutoSize = 0
    tf.WordWrap = True
    tf.VerticalAnchor = 1                                        # top
    r = tf.TextRange
    r.Font.Name = "Segoe UI Semibold"                            # = the theme's heading font
    r.Font.Size = B.TITLE_PT
    r.Font.Bold = False                                          # Semibold is the weight
    r.Font.Color.RGB = B.bgr(T.INK)
    r.ParagraphFormat.Alignment = 1


def lake(sl, n: int) -> None:
    """The small lake, bottom right, at slide n's level (an SVG; PowerPoint keeps a PNG beside it)."""
    k = T.LAKE_ICON
    icon = sl.Shapes.AddPicture(str(B.lake_icon(round(B.icon_levels()[n], 2), "svg")), False, True,
                                k["x"] * B.PT, k["y"] * B.PT)
    icon.LockAspectRatio = True
    icon.Height = k["h"] * B.PT
    icon.Name = "!!lake"                                         # Morph pairs it across slides: the lake rises
    icon.AlternativeText = "A small lake icon that fills up over the talk"


def effect(seq, shape, kind: int, trigger: int, exit_: bool = False):
    e = seq.AddEffect(shape, kind, 0, trigger)
    if exit_:
        e.Exit = -1
    if kind == FADE:
        e.Timing.Duration = 0.4
    return e


def talk_slides() -> list[list[list[dict]]]:
    """Talk slides in order, each a list of steps (one click each), as build_show groups them."""
    talk = []
    for grp in B.groups(B.segments()):
        if talk and talk[-1][0][0]["n"] == grp[0]["n"]:
            talk[-1].append(grp)
        else:
            talk.append([grp])
    return talk


def build(out: Path = OUT) -> None:
    import win32com.client
    if out.with_name("~$" + out.name).exists():
        sys.exit(f"{out.name} is open in PowerPoint: close it first, or build to another file with CLEAN_OUT")
    reader = {s["n"]: s.get("reader", "") for s in B.slides()}
    top, hgt = BAND_PX * B.PT, H - BAND_PX * B.PT
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Add(WithWindow=False)
    try:
        pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight = W, H
        layout = master(pres)
        had_video = False                                        # did the slide before this one play a video?
        for i, steps in enumerate(talk_slides(), 1):
            g = steps[0][0]
            sl = pres.Slides.AddSlide(i, layout)
            sl.Shapes.Title.TextFrame.TextRange.Text = g["title"]
            seq = sl.TimeLine.MainSequence
            pics, shown = [], []
            for k, grp in enumerate(steps):                      # the pictures, bottom to top
                s0 = grp[0]
                if s0["image"] in B.VIDEOS:
                    # No jump back (originator, 23 Oct): PowerPoint shows a stopped video's poster
                    # frame, during the transition too, so the poster is the LAST frame; the first
                    # frame is a still on top that leaves on the click that starts the video.
                    clip, first, last = silent(s0["image"])
                    shape = sl.Shapes.AddMediaObject2(str(clip), False, True, 0, top, W, hgt)
                    shape.MediaFormat.SetDisplayPictureFromFile(str(last))
                    end = sl.Shapes.AddPicture(str(first), False, True, 0, top, W, hgt)
                    end.Name = f"step {k + 1} start"
                    end.AlternativeText = f"First frame of the animation: {g['title']}"
                else:
                    img = under_band(B.fill(B.native(HERE / s0["image"])[0], s0["id"]), s0["id"])
                    shape = sl.Shapes.AddPicture(str(img), False, True, 0, top, W, hgt)
                    end = None
                    shape.AlternativeText = f"{g['title']}, step {k + 1}"
                shape.Name = f"step {k + 1}"
                dx, dy = B.moved(g["n"], shape.Name)                 # a hand move (B.HAND_MOVES)
                shape.Left, shape.Top = shape.Left + dx, shape.Top + dy
                pics.append((shape, end, s0["image"] in B.VIDEOS))
                shown.append((k, B.labels_of(s0["image"])))
            want = B.spans(shown)                                # name -> [label, step in, step out]
            for name, w in want.items():
                w[0] = dict(w[0], move=B.moved(g["n"], name))
            boxes = {name: B.new_box(sl, spec) for name, (spec, *_) in want.items()}
            for k, (shape, end, is_video) in enumerate(pics):   # one click per step, in order
                if is_video:                                     # end = the first-frame still on top
                    if k:                                        # a later video: still and video come in
                        effect(seq, end, APPEAR, ON_CLICK)       # together, the still hiding the poster
                        effect(seq, shape, APPEAR, WITH_PREVIOUS)
                    effect(seq, shape, B.MEDIA_PLAY, WITH_PREVIOUS if k else ON_CLICK)
                    gone = effect(seq, end, APPEAR, WITH_PREVIOUS, exit_=True)
                    gone.Timing.TriggerDelayTime = START_HOLD_S  # the video is running under it by then
                elif k:
                    effect(seq, shape, FADE, ON_CLICK)
                for name, (_, t_in, t_out) in want.items():
                    if t_in == k and k:
                        effect(seq, boxes[name], FADE, WITH_PREVIOUS)
                    if t_out == k:
                        effect(seq, boxes[name], FADE, WITH_PREVIOUS, exit_=True)
            sl.Shapes.Title.ZOrder(0)
            after_video, had_video = had_video, any(v for *_, v in pics)
            lake(sl, int(g["n"]))
            tr = sl.SlideShowTransition
            # After a slide with a video, a plain fade: Morph redraws the outgoing slide from its
            # shapes (the first-frame still included), a fade from what is on screen (23 Oct, tested)
            tr.EntryEffect = FADE_SMOOTHLY if after_video else B.MORPH
            tr.Duration = 1.0
            tr.AdvanceOnClick = True
            tr.AdvanceOnTime = False
            sl.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = reader[g["n"]]
            print(f"slide {g['n']:>2s} {g['title']!r}: {len(steps)} step(s), {len(boxes)} text box(es)", flush=True)
        pres.SaveAs(str(out))
    finally:
        pres.Close()
    print(f"saved {out.name}")


if __name__ == "__main__":
    build()
