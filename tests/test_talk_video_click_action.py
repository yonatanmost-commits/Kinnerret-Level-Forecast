"""A mouse click on a video moves the talk on, not back to the video's start (originator
2026-10-26: "you got the bug back in where i click and it jumps to the start").

Removing the videos' interactive sequences (test_talk_video_clicks.py) was not enough: PowerPoint
also gives every inserted video an action setting of its own, "play on click"
(<a:hlinkClick action="ppaction://media"/> on the shape). A click on the video then replays it
from 0:00 and never reaches the slide. No video in either deck may keep that action.
"""
from pathlib import Path

import pytest

TALK = Path(__file__).resolve().parent.parent / "docs" / "talk"
DECKS = [TALK / "Kinneret_Talk_Submission.pptx", TALK / "Kinneret_Talk_Show.pptx"]


@pytest.mark.parametrize("deck", DECKS, ids=lambda p: p.stem)
def test_a_click_on_a_video_does_not_replay_it(deck):
    if not deck.exists():
        pytest.skip(f"{deck.name} isn't built")
    from pptx import Presentation
    for i, s in enumerate(Presentation(deck).slides, 1):
        assert "ppaction://media" not in s._element.xml, \
            f"{deck.name} slide {i}: a click on a video replays it instead of moving the talk on"
