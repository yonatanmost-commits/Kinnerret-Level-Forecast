"""The opening lake animation, refined (originator 2026-10-14: smoother, better type, a frame).

The recorded narration (charts/lake_years_narrated.mp4) is timed to the accepted cut, so the new
cut keeps every beat at the same second. Motion is smooth: the water eases out of each 11 Nov
stop as well as into it, and the year labels glide to their new places instead of jumping.

Contract fixed here, in docs/talk/make_lake_animation.py:
- stops() -> (stops, daily path, info), as before.
- FPS: frames per second of the cut.
- timeline(stops, path, info) -> list of frames, one per video frame, each with:
    kind      "years" (the one lake), "apart" (one lake becoming two), "split" (the two lakes)
    pos       years frames: the fractional day index into the daily path being shown
    current   years frames: the stop whose line is appearing or held, else None
    label_ys  years frames: {stop index: label centre y in px on the 1080-px frame}
- gauge_ticks() -> the level ruler's tick levels in metres.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs" / "talk"))

# the accepted cut (30 fps, 1842 frames), measured 2026-10-14: the second each beat starts
STOP_STARTS = [22, 224, 405, 586, 767, 948, 1129, 1310, 1491]      # frames at 30 fps
APART_START, SPLIT_START, TOTAL = 1563, 1605, 1842


@pytest.fixture(scope="module")
def anim():
    import make_lake_animation as m
    S, path, info = m.stops()
    return m, S, path, info, m.timeline(S, path, info)


def test_every_beat_lands_on_the_narrations_second(anim):
    m, S, _, _, frames = anim
    tol = 1.0 / 30                                                   # one frame of the old cut
    assert abs(len(frames) / m.FPS - TOTAL / 30) <= tol
    for k, old in enumerate(STOP_STARTS):
        new = next(i for i, f in enumerate(frames) if f.kind == "years" and f.current == k)
        assert abs(new / m.FPS - old / 30) <= tol, f"stop {S[k]['year']} moved in time"
    apart = next(i for i, f in enumerate(frames) if f.kind == "apart")
    split = next(i for i, f in enumerate(frames) if f.kind == "split")
    assert abs(apart / m.FPS - APART_START / 30) <= tol
    assert abs(split / m.FPS - SPLIT_START / 30) <= tol


def test_the_water_eases_out_of_each_stop_and_never_lurches(anim):
    m, S, _, _, frames = anim
    years = [f for f in frames if f.kind == "years"]
    steps = np.diff([f.pos for f in years])
    moving = []                                                      # runs of frames in motion
    run = []
    for s in steps:
        if s > 1e-9:
            run.append(s)
        elif run:
            moving.append(run)
            run = []
    assert len(moving) == len(S) - 1, f"expected {len(S) - 1} journeys, found {len(moving)}"
    for run in moving:
        peak = max(run)
        assert run[0] <= 0.35 * peak, "the water jumps away from a stop"
        assert run[-1] <= 0.35 * peak, "the water slams into a stop"
        assert max(abs(np.diff(run))) <= 0.12 * peak, "the water lurches mid-journey"


def test_year_labels_glide_rather_than_jump(anim):
    m, _, _, _, frames = anim
    years = [f for f in frames if f.kind == "years"]
    worst = 0.0
    for a, b in zip(years, years[1:]):
        for k in set(a.label_ys) & set(b.label_ys):
            worst = max(worst, abs(a.label_ys[k] - b.label_ys[k]))
    assert worst <= 8.0, f"a year label jumps {worst:.0f} px between frames"


def test_the_gauge_spans_every_level_shown(anim):
    m, S, _, info, _ = anim
    from app_utils import LEVEL_LEGAL_MAX
    ticks = m.gauge_ticks()
    assert ticks == sorted(ticks) and len(ticks) >= 5
    assert min(ticks) <= min(s["level"] for s in S)
    assert max(ticks) >= LEVEL_LEGAL_MAX
    assert all(abs(b - a - 1.0) < 1e-9 for a, b in zip(ticks, ticks[1:])), "one tick per metre"
