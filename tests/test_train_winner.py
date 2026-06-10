# tests/test_train_winner.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))
import importlib.util

# Import without executing __main__ block
_spec = importlib.util.spec_from_file_location(
    "train_08",
    Path(__file__).resolve().parent.parent / "Automation" / "08_train_forecast_model.py",
)
train_08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_08)


def test_train_winner_only_raises_when_json_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "BASE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        train_08.train_winner_only()


def test_train_winner_only_raises_on_unknown_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "BASE_DIR", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "olympics_results.json").write_text(
        json.dumps({"winner": "unknown_model", "models": {}})
    )
    monkeypatch.setattr(train_08, "load_data", lambda: __import__("pandas").DataFrame())
    with pytest.raises(ValueError, match="unknown_model"):
        train_08.train_winner_only()


def test_train_winner_only_dispatches_correct_trainer(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "BASE_DIR", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "models": {}})
    )
    import pandas as pd, numpy as np
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=10)})
    monkeypatch.setattr(train_08, "load_data", lambda: df)
    called = []
    monkeypatch.setattr(train_08, "run_cv", lambda df: ([], pd.Series(np.nan, index=df.index)))
    monkeypatch.setattr(train_08, "train_final", lambda df, oof: called.append("gbr") or (None, None, None))
    # Persistence writes to the real Models/ dir — stub it; covered separately below.
    monkeypatch.setattr(train_08, "_persist_winner_metrics", lambda *a, **kw: None)
    train_08.train_winner_only()
    assert called == ["gbr"]


@pytest.mark.parametrize("winner,fn_name,cv_name", [
    ("xgboost", "train_final_xgb", "run_cv_xgb"),
    ("lgbm",    "train_final_lgb", "run_cv_lgb"),
])
def test_train_winner_only_dispatches_other_winners(tmp_path, monkeypatch, winner, fn_name, cv_name):
    monkeypatch.setattr(train_08, "BASE_DIR", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "olympics_results.json").write_text(
        json.dumps({"winner": winner, "models": {}})
    )
    import pandas as pd, numpy as np
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=10),
        "inflow_obstacle_m3": np.zeros(10),
    })
    monkeypatch.setattr(train_08, "load_data", lambda: df)
    called = []
    # Stub the heavy/real-IO collaborators so this stays a pure dispatch test.
    monkeypatch.setattr(train_08, "fit_vol2level_poly", lambda: [0.0, 0.0, 0.0])
    monkeypatch.setattr(train_08, cv_name, lambda df, bathy: [])
    monkeypatch.setattr(train_08, "_persist_winner_metrics", lambda *a, **kw: None)
    monkeypatch.setattr(train_08, fn_name, lambda *a, **kw: called.append(fn_name))
    train_08.train_winner_only()
    assert called == [fn_name]


def test_persist_winner_metrics_writes_both_files(tmp_path, monkeypatch):
    """_persist_winner_metrics updates model_metadata.json and the winner's
    olympics entry with the fresh CV mean, without clobbering unrelated keys."""
    monkeypatch.setattr(train_08, "BASE_DIR", tmp_path)
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path / "Models")
    (tmp_path / "Models").mkdir()
    (tmp_path / "Models" / "model_metadata.json").write_text(
        json.dumps({"bathy_vol2level_coeffs": [1, 2, 3], "cv_s2_mean_r2": 0.111})
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "generated_at": "2026-06-01",
                    "models": {"baseline_gbr": {"cv_vol_r2_mean": 0.111}}})
    )
    import pandas as pd
    df = pd.DataFrame({"date": pd.date_range("2026-05-01", periods=3)})
    cv = [{"fold": "2024", "n_test": 5, "s1_r2": 0.9, "s2_r2": 0.8, "s2_mae_Mm3": 0.5}]
    train_08._persist_winner_metrics("baseline_gbr", cv, df)

    meta = json.loads((tmp_path / "Models" / "model_metadata.json").read_text())
    assert meta["cv_s2_mean_r2"] == 0.8
    assert meta["bathy_vol2level_coeffs"] == [1, 2, 3]   # preserved
    assert meta["cv_results"][0]["s2_mae_Mm3"] == 0.5    # normalised schema
    oly = json.loads((tmp_path / "docs" / "olympics_results.json").read_text())
    assert oly["models"]["baseline_gbr"]["cv_vol_r2_mean"] == 0.8
    assert oly["generated_at"] == "2026-06-01"           # full-bake date untouched
    assert "winner_retrained_at" in oly
