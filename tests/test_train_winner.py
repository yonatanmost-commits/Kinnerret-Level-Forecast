# tests/test_train_winner.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))
import importlib.util, types

# Import without executing __main__ block
_spec = importlib.util.spec_from_file_location(
    "train_08",
    Path(__file__).resolve().parent.parent / "Automation" / "08_train_forecast_model.py",
)
train_08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_08)


def test_train_winner_only_raises_when_json_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        train_08.train_winner_only()


def test_train_winner_only_raises_on_unknown_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    (tmp_path / "olympics_results.json").write_text(
        json.dumps({"winner": "unknown_model", "models": {}})
    )
    monkeypatch.setattr(train_08, "load_data", lambda: __import__("pandas").DataFrame())
    with pytest.raises(ValueError, match="unknown_model"):
        train_08.train_winner_only()


def test_train_winner_only_dispatches_correct_trainer(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    (tmp_path / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "models": {}})
    )
    import pandas as pd, numpy as np
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=10)})
    monkeypatch.setattr(train_08, "load_data", lambda: df)
    called = []
    monkeypatch.setattr(train_08, "run_cv", lambda df: ([], pd.Series(np.nan, index=df.index)))
    monkeypatch.setattr(train_08, "train_final", lambda df, oof: called.append("gbr") or (None, None, None))
    train_08.train_winner_only()
    assert called == ["gbr"]
