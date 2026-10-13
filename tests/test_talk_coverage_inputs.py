"""Truth test for the coverage slide's colours (intent/kinneret-talk-deck R39, D21; planner review of
d92d55b): a record is drawn in colour only when it feeds the model's table, so the "all sources
line up" line holds for every coloured bar.

Contract fixed here: data.<series>.start carries model_input (bool) and, when true, model_column,
a column of the gold table that holds that record; chart_data("coverage") gives each series
"used" equal to model_input.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TALK = ROOT / "docs" / "talk"
sys.path.insert(0, str(TALK))

GOLD = ROOT / "Gold Data" / "kinneret_gold_features.csv"
# What each record would be called in the gold table, if the model used it.
GOLD_NAMES = {"level": "level_m", "flow.obstacle_bridge": "obstacle", "flow.sede_nehemya": "sede",
              "flow.yarmuk": "yarmu", "flow.old_bridge": "old_bridge",
              "flow.baptism_site": "baptism", "weather": "rainfall_mm", "radiation": "radiation"}


def test_coverage_colours_follow_the_model_table():
    ledger = json.loads((TALK / "numbers_ledger.json").read_text(encoding="utf-8"))
    cols = list(pd.read_csv(GOLD, nrows=1).columns)
    from charts import chart_data
    used = {s["id"]: s["used"] for s in chart_data("coverage", ledger)["series"]}
    assert set(used) == set(GOLD_NAMES)
    for sid, name in GOLD_NAMES.items():
        e = ledger[f"data.{sid}.start"]
        in_gold = any(name in c.lower() for c in cols)
        assert e["model_input"] is in_gold, sid
        if in_gold:
            assert e["model_column"] in cols and name in e["model_column"].lower(), sid
        assert used[sid] is e["model_input"], sid
