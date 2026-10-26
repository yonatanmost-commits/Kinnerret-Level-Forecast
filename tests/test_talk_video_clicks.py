"""A mouse click on a video slide moves the talk on (originator 2026-10-25): "when i click it goes
back to the beginning instead of rolling ahead, even in between clicks on the same slide".

PowerPoint gives every inserted video a trigger of its own: a click ON the video pauses or
restarts it, and the click never reaches the slide. The videos fill the slide under the title, so
nearly every mouse click lands on one. Neither deck may keep those triggers (interactive
sequences); every click belongs to the main sequence.
"""
from pathlib import Path

import pytest

TALK = Path(__file__).resolve().parent.parent / "docs" / "talk"
DECKS = [TALK / "Kinneret_Talk_Submission.pptx", TALK / "Kinneret_Talk_Show.pptx"]


@pytest.mark.parametrize("deck", DECKS, ids=lambda p: p.stem)
def test_a_click_on_a_video_is_a_click_on_the_slide(deck):
    if not deck.exists():
        pytest.skip(f"{deck.name} isn't built")
    from pptx import Presentation
    for i, s in enumerate(Presentation(deck).slides, 1):
        x = s._element.xml
        assert 'nodeType="interactiveSeq"' not in x, f"{deck.name} slide {i}: a click on a video stays on the video"
