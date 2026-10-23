"""The PowerPoint we hand in (originator 2026-10-23): "a clean powerpoint, no narration no timed
animation, by mouse click only"; the background on a master slide with the page colour and the top
line, the bottom blue line gone, the small lake per slide (not on the master); short notes so a
reader understands the slides; the app slide before the centaur.

Built by docs/talk/build_clean.py -> docs/talk/Kinneret_Talk_Submission.pptx.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "talk" / "Kinneret_Talk_Submission.pptx"

pytestmark = pytest.mark.skipif(not DECK.exists(), reason="the clean deck isn't built")


@pytest.fixture(scope="module")
def prs():
    from pptx import Presentation
    return Presentation(DECK)


def test_twelve_slides_with_the_app_before_the_centaur(prs):
    titles = [s.shapes.title.text for s in prs.slides]
    assert len(titles) == 12
    assert titles[:4] == ["Lake Kinneret", "The gap", "The project", "Centaur"]


def test_no_sound_and_no_timings(prs):
    for i, s in enumerate(prs.slides, 1):
        x = s._element.xml
        assert "advTm" not in x, f"slide {i} advances on a timer"
        delays = re.findall(r'<p:cTn [^>]*delay="(\d+)"', x)
        assert all(d == "0" for d in delays), f"slide {i}: timed delays {delays}"
        for rel in s.part.rels.values():
            assert "audio" not in rel.reltype, f"slide {i} has sound"
            if "video" in rel.reltype or "media" in rel.reltype:
                assert "mp4" in rel.target_ref


def test_steps_wait_for_a_click(prs):
    for i, s in enumerate(prs.slides, 1):
        x = s._element.xml
        auto = re.findall(r'nodeType="(afterEffect|withEffect)"', x)
        clicks = x.count('nodeType="clickEffect"')
        if auto:
            assert clicks, f"slide {i}: effects run with no click"


def test_the_master_carries_the_page_and_the_top_rule_only(prs):
    m = prs.slide_master
    names = [sh.name for sh in m.shapes]
    assert "title bar" in names
    assert not any("bottom" in n.lower() for n in names)
    assert 'val="FBFAF7"' in m._element.xml                        # the page colour
    for s in prs.slides:
        assert s.slide_layout.name == "Kinneret title"
        assert "!!lake" in [sh.name for sh in s.shapes]             # the lake stays on the slide


def test_short_reader_notes_on_every_slide(prs):
    for i, s in enumerate(prs.slides, 1):
        notes = s.notes_slide.notes_text_frame.text.strip()
        assert 25 <= len(notes.split()) <= 120, f"slide {i}: {len(notes.split())} words of notes"
        assert "[" not in notes, f"slide {i}: script markers in the notes"
