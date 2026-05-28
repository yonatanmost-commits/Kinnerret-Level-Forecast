# tests/test_daily_agent.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kinneret_app"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "daily_agent",
    Path(__file__).resolve().parent.parent / "Automation" / "daily_agent.py",
)
daily_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily_agent)


# ── health_check ───────────────────────────────────────────────────────────────

def test_health_check_fails_on_missing_olympics_json(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    (tmp_path / "Models").mkdir()
    issues = daily_agent.health_check()
    assert any("olympics_results.json" in i and "REQUIRED" in i for i in issues)


def test_health_check_fails_on_missing_winner_key(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "olympics_results.json").write_text(json.dumps({"models": {}}))
    issues = daily_agent.health_check()
    assert any("winner" in i and "REQUIRED" in i for i in issues)


def test_health_check_passes_with_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "models": {}})
    )
    issues = daily_agent.health_check()
    required_failures = [i for i in issues if "REQUIRED" in i]
    assert required_failures == []


# ── _write_report ──────────────────────────────────────────────────────────────

def test_write_report_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "REPORTS_DIR", tmp_path / "Reports")
    results = {
        "kinneret_level": {"status": "ok", "rows_added": 1, "detail": "(2026-05-28)"},
        "river_flow":     {"status": "failed", "rows_added": 0, "detail": "timeout"},
        "build_gold":     {"status": "ok", "detail": None},
        "train_winner":   {"status": "ok", "detail": None},
    }
    path = daily_agent._write_report(results, [], "2026-05-28")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "kinneret_level" in text
    assert "FAILED" in text
    assert "2026-05-28" in text


# ── _run_script ────────────────────────────────────────────────────────────────

def test_run_script_captures_failure(tmp_path):
    bad_script = tmp_path / "bad.py"
    bad_script.write_text("import sys; sys.exit(1)\n")
    result = daily_agent._run_script_path(bad_script)
    assert result["status"] == "failed"
