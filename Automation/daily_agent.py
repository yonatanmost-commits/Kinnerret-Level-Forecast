import json
import subprocess
import sys
from datetime import date
from pathlib import Path

AUTOMATION   = Path(__file__).resolve().parent
PROJECT_ROOT = AUTOMATION.parent
REPORTS_DIR  = PROJECT_ROOT / "Reports"

sys.path.insert(0, str(PROJECT_ROOT / "kinneret_app"))

from kinneret_level import append_to_silver, fetch_new_levels
from jordan_flow    import append_to_flow_raw, fetch_new_flows
from met_update     import append_to_met_silver, fetch_new_met

KINNERET_LEVEL_SILVER = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
FLOW_RAW_SILVER       = PROJECT_ROOT / "Silver Data" / "Jordan River Silver" / "jordan_river_daily_flow.csv"
MET_SILVER            = PROJECT_ROOT / "Silver Data" / "Meteorological" / "met_data_daily.csv"


def health_check() -> list:
    issues = []
    olympics_path = PROJECT_ROOT / "Models" / "olympics_results.json"
    if not olympics_path.exists():
        issues.append("REQUIRED: Models/olympics_results.json missing")
    else:
        try:
            with open(olympics_path, encoding="utf-8") as f:
                data = json.load(f)
            if "winner" not in data:
                issues.append("REQUIRED: olympics_results.json has no 'winner' key")
        except Exception as e:
            issues.append(f"REQUIRED: olympics_results.json unreadable: {e}")

    for path, label in [
        (PROJECT_ROOT / "Gold Data" / "kinneret_gold_features.csv", "Gold Data/kinneret_gold_features.csv"),
        (PROJECT_ROOT / "Models" / "stage1_inflow_rf.pkl", "Models/stage1_inflow_rf.pkl"),
        (PROJECT_ROOT / "Models" / "stage2_volume_rf.pkl", "Models/stage2_volume_rf.pkl"),
    ]:
        if not path.exists():
            issues.append(f"WARN: {label} missing")

    return issues


def _run_script_path(script_path: Path, *args: str) -> dict:
    cmd = [sys.executable, str(script_path)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output")[:500]
        return {"status": "failed", "detail": detail}
    return {"status": "ok", "detail": None}


def _run_script(script_name: str, *args: str) -> dict:
    return _run_script_path(AUTOMATION / script_name, *args)


def _write_report(results: dict, health_issues: list, today: str) -> Path:
    lines = [f"=== Daily Agent Report - {today} ===", ""]

    lines += ["HEALTH"]
    if not health_issues:
        lines.append("  All checks passed.")
    else:
        for issue in health_issues:
            lines.append(f"  {issue}")

    lines += ["", "DATA FETCH"]
    for key in ["kinneret_level", "river_flow", "met"]:
        r = results.get(key)
        if r is None:
            continue
        n = r.get("rows_added", 0) or 0
        detail = r.get("detail") or ""
        if r["status"] == "ok":
            lines.append(f"  {key:<16} : ok        +{n} rows  {detail}")
        else:
            lines.append(f"  {key:<16} : FAILED    {detail}")

    lines += ["", "PIPELINE"]
    for key in ["05_clean_flow", "04_clean_met", "build_gold", "07b_precip", "train_winner"]:
        r = results.get(key)
        if r is None:
            continue
        if r["status"] == "ok":
            lines.append(f"  {key:<16} : ok")
        elif r["status"] == "skipped":
            lines.append(f"  {key:<16} : skipped   {r.get('detail','')}")
        else:
            lines.append(f"  {key:<16} : FAILED    {r.get('detail','')}")

    report_text = "\n".join(lines)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"daily_agent_{today}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def run() -> dict:
    results = {}

    # Step 1: Kinneret level
    try:
        df = fetch_new_levels(KINNERET_LEVEL_SILVER)
        n = append_to_silver(df, KINNERET_LEVEL_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["kinneret_level"] = {"status": "ok", "rows_added": n, "detail": detail}
    except Exception as e:
        results["kinneret_level"] = {"status": "failed", "rows_added": 0, "detail": str(e)}

    # Step 2: River flow
    try:
        df = fetch_new_flows(FLOW_RAW_SILVER)
        n = append_to_flow_raw(df, FLOW_RAW_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["river_flow"] = {"status": "ok", "rows_added": n, "detail": detail}
        results["05_clean_flow"] = _run_script("05_clean_jordan_river_flow.py")
    except Exception as e:
        results["river_flow"] = {"status": "failed", "rows_added": 0, "detail": str(e)}
        results["05_clean_flow"] = {"status": "skipped", "detail": "river_flow failed"}

    # Step 3: Met data
    try:
        df = fetch_new_met(MET_SILVER)
        n = append_to_met_silver(df, MET_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["met"] = {"status": "ok", "rows_added": n, "detail": detail}
        results["04_clean_met"] = _run_script("04_clean_daily_met_data.py")
    except Exception as e:
        results["met"] = {"status": "failed", "rows_added": 0, "detail": str(e)}
        results["04_clean_met"] = {"status": "skipped", "detail": "met failed"}

    # Step 4: Build gold (always attempt)
    results["build_gold"] = _run_script("07_build_gold_features.py")

    # Step 4b: Precipitation intensity feature (runs after 07, updates gold in place)
    if results["build_gold"]["status"] == "ok":
        results["07b_precip"] = _run_script("07b_precalc_precip_intensity.py")
    else:
        results["07b_precip"] = {"status": "skipped", "detail": "build_gold failed"}

    # Step 5: Train winner (only if gold + 07b succeeded)
    if results["build_gold"]["status"] == "ok" and results["07b_precip"]["status"] == "ok":
        results["train_winner"] = _run_script(
            "08_train_forecast_model.py", "--winner-only"
        )
    else:
        results["train_winner"] = {
            "status": "skipped", "detail": "build_gold or 07b_precip failed"
        }

    return results


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    today = str(date.today())

    health_issues = health_check()
    required_failures = [i for i in health_issues if i.startswith("REQUIRED")]

    if required_failures:
        report_path = _write_report({}, health_issues, today)
        print(f"HEALTH FAILED. See: {report_path}")
        print("\n".join(required_failures))
        sys.exit(1)

    results = run()
    report_path = _write_report(results, health_issues, today)

    with open(report_path, encoding="utf-8") as f:
        print(f.read())
    print(f"\nReport saved: {report_path}")

    if any(v["status"] == "failed" for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
