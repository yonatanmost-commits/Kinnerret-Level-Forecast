"""The 'which model when' slide, "The choice" (originator, 5 Nov 2026): "when the input was
estimated, the neural network was better ... when to choose classic ML, and when to try the
network". A table like "The errors": two blocks (the real weather, a seasonal forecast), each with
the trees and the network, at a week, a month, 6 months and a year; teal only where the win is
clear. Every cell is computed from the backtest, so a rerun redraws it.
Originator, 5 Nov (later): "put the copernicus slide back in, remove the error slide, mark the 2.0 and
the 55 and 85, because they are a real problem, no one has the real weather 6 months ahead so dont
highlight the 8.0 and 41"; then, told 55 vs 64 is not a clear win: "keep only the 2.0 and 85 thats
best for the talk". So teal marks a CLEAR win only with the weather you'd really have (the real
weather for a week; the seasonal forecast from a month on).
"The choice" takes the errors slide's place; "The errors" becomes a hidden Q&A backup.
"""
import sys
from pathlib import Path

import pytest

TALK = Path(__file__).resolve().parents[1] / "docs" / "talk"
sys.path.insert(0, str(TALK))


@pytest.fixture(scope="module")
def table():
    import chart_choice
    return chart_choice.table()


def test_cells_shared_with_the_errors_slide_are_identical(table):
    import chart_choice
    import chart_models
    errors = {name: cells for name, _, cells in chart_models.MODELS}     # week known, then forecast
    for model, name in (("trees", "GBR"), ("network", "GRU")):
        assert chart_choice.fmt(table["known"][model][0]["cm"]) == errors[name][0]
        for c in (1, 2, 3):
            assert chart_choice.fmt(table["forecast"][model][c]["cm"]) == errors[name][c]


def test_the_cells_shown_on_5_nov_on_the_17_oct_backtest(table):
    # the table checked in chat on 5 Nov (paired starts); holds until the weekend rerun replaces
    # cfc_monthly. The network's 6 months with a forecast is 55.485 cm: "55" (the errors slide had 56)
    shown = {"known": {"trees": ["2.0", "8.0", "41", "77"], "network": ["2.6", "9.3", "58", "86"]},
             "forecast": {"trees": ["2.7", "12", "64", "121"], "network": ["2.9", "12", "55", "85"]}}
    import chart_choice
    if chart_choice.backtest_stamp() != "2026-10-17":
        pytest.skip("backtest rerun: the 5 Nov cells no longer apply")
    for w in shown:
        for m in shown[w]:
            assert [chart_choice.fmt(c["cm"]) for c in table[w][m]] == shown[w][m]


def test_teal_marks_a_clear_win_only_with_the_weather_you_would_have(table):
    for w in table:
        for c in range(4):
            real = (w == "known") == (c == 0)                     # a week: real weather; later: forecast
            for m in ("trees", "network"):
                assert table[w][m][c]["marked"] == (real and table[w][m][c]["clear"]), (w, m, c)


def test_the_marked_cells_on_the_17_oct_backtest_are_2_0_and_85(table):
    import chart_choice
    if chart_choice.backtest_stamp() != "2026-10-17":
        pytest.skip("backtest rerun")
    marked = [chart_choice.fmt(table[w][m][c]["cm"]) for w in table for m in table[w] for c in range(4)
              if table[w][m][c]["marked"]]
    assert marked == ["2.0", "85"]


def test_clear_means_the_bootstrap_interval_excludes_zero(table):
    for w in table:
        for c in range(4):
            lo, hi = table[w]["trees"][c]["ci"]                   # network minus trees, 90% interval
            assert table[w]["trees"][c]["clear"] == (lo > 0) and table[w]["network"][c]["clear"] == (hi < 0)


def test_known_input_favours_the_trees_and_a_forecast_the_network_a_year_ahead(table):
    assert sum(c["clear"] for c in table["known"]["trees"]) >= 3
    assert table["forecast"]["network"][3]["clear"]


def test_both_frames_are_drawn():
    for n in (1, 2):
        assert (TALK / "charts" / f"choice_{n}.png").exists()


def test_slide_order_copernicus_back_and_the_errors_a_backup():
    import build_show as B
    talk = [s["title"] for s in B.slides()]
    i = talk.index("The models")
    assert talk[i:i + 5] == ["The models", "The forecast", "The method", "The choice", "The horizon"]
    assert "The errors" not in talk
    backups = [s["title"] for s in B.slides(backups=True) if s.get("backup")]
    assert "The errors" in backups and "The forecast" not in backups
    assert [s["n"] for s in B.slides()] == [str(k) for k in range(1, len(talk) + 1)]
