"""Tests for the Expert Commentary dashboard page (page 8)."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAGE = PROJECT_ROOT / "kinneret_app" / "pages" / "8_Expert_Commentary.py"
RESULTS_FILE = PROJECT_ROOT / "docs" / "olympics_results.json"


def _run():
    at = AppTest.from_file(str(PAGE))
    at.run()
    return at


def test_page_renders_without_exception():
    at = _run()
    assert not at.exception, f"page raised: {at.exception}"


def _all_markdown_text(at):
    return "\n".join(m.value for m in at.markdown)


def test_page_has_byline():
    at = _run()
    text = _all_markdown_text(at)
    assert "Wade Storm" in text


def test_page_shows_live_champion_r2():
    """The current champion R2 from the live results file must appear on the page."""
    at = _run()
    text = _all_markdown_text(at)
    with open(RESULTS_FILE, encoding="utf-8") as f:
        d = json.load(f)
    r2 = d["models"][d["winner"]]["cv_vol_r2_mean"]
    assert f"{r2:.3f}" in text, f"expected live R2 {r2:.3f} on page"
