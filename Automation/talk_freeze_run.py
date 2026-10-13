"""
talk_freeze_run.py - Measure every number the Kinneret Conference talk may use, on one data freeze.

Writes docs/talk/numbers_ledger.json: a flat JSON of key -> {value, display, unit, source, date,
kind}. kind "freeze" = measured here on the freeze (date = the freeze date); kind "historical" =
copied from a dated stored result (date = when it was originally measured). Then runs the truth
tests (tests/test_talk_truth.py) and, only if they pass, writes docs/talk/truth_stamp.json with
the ledger's hash, which the deck builder checks (plan D8).

What is measured (intent/kinneret-talk-deck plan D3-D5, D17):
  - the 8 Model Olympics configurations, walk-forward CV (folds 2021-2024), timed; the GRU's CV
    is ported unchanged from the last commit before its retirement (4f9e553^)
  - two baselines on the champion's own fold rows: zero change, and the seasonal average
  - the hook's level facts: freeze-date level, red line, "lowest since" year, the level series
  - two winter scenarios: the driest and wettest of the last 20 winters (plan D18)
  - the champion R² history: every committed docs/olympics_results.json (historical) + the freeze
  - the frontier: 14-30-day long-range skill (historical, perfect-prognosis) and the red-line
    crossing hindcast (re-run on the freeze)

It never trains final models and never writes Models/ or docs/olympics_results.json: it calls
only the run_cv* functions, and points the training module's MODELS_DIR at a temp dir as a guard.

Run (alone - the GRU takes ~15 min on CPU and the machine is low on memory):
  python Automation/talk_freeze_run.py                       # everything, freeze 2026-10-11
  python Automation/talk_freeze_run.py --freeze 2026-10-11
  python Automation/talk_freeze_run.py --keep-models         # re-measure all but the 8 models,
                                                             # reusing them from the ledger
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
AUTO = ROOT / "Automation"
sys.path.insert(0, str(AUTO))

import redline_backtest as rb  # noqa: E402
from redline_backtest import OBS_WINDOW, SCALE_CLAMP, load_daily, recession_by_doy  # noqa: E402

TALK_DIR = ROOT / "docs" / "talk"
LEDGER_PATH = TALK_DIR / "numbers_ledger.json"
STAMP_PATH = TALK_DIR / "truth_stamp.json"
LEVEL_FILE = "Silver Data/Kinneret Level/kinneret_level.csv"
ERA5_FILE = "Silver Data/Meteorological/era5_kinneret_daily.csv"
OLYMPICS_FILE = "docs/olympics_results.json"
LONGRANGE_FILE = "docs/longrange_phaseb_results.json"
THIS = "Automation/talk_freeze_run.py"
TRUTH_TESTS = ["tests/test_talk_truth.py", "tests/test_talk_opening.py"]

DEFAULT_FREEZE = "2026-10-11"
HOOK_FIRST_YEAR = 2020        # the year-over-year overlay starts here, as on the app's front page
SCENARIO_WINTERS = 20         # dry/wet winter scenarios: the last 20 complete winters
RED_LINE = -213.0
FOLDS = ["2021", "2022", "2023", "2024"]
MODELS = ["baseline_gbr", "xgboost", "lgbm", "gru", "gbr_max_chain",
          "gbr_s1_direct_s2_anchor", "gbr_single_stage", "gbr_s1_chain_s2_roll1"]

# Crossing hindcast (plan D17)
CROSSING_FROM = "2006-01-01"
LAST_RAIN_MM = 5
CROSSING_CAP_DAYS = 400
BANDS = [("0_7", 0, 7), ("7_14", 7, 14), ("14_30", 14, 30), ("30_60", 30, 60),
         ("60_90", 60, 90), ("90_120", 90, 120), ("120_plus", 120, 10**6)]

# Why the champion's R² moved at each committed snapshot (plan D7, spec R12/R22). Keyed by
# commit; the first snapshot is the starting point. cause_type is "model" or "data".
HISTORY_CAUSES = {
    "c3a72b3": ("data", "starting point: two-stage gradient boosting, first tracked score"),
    "ac2ede5": ("data", "Wade Storm: the missing 2023 rain fixed, plus the six Signal Harvest fixes"),
    "56d0555": ("model", "rain sums over the last 30 and 45 days added (wetness memory)"),
    "2da9bd7": ("data", "lake radiation restored from a backup weather source"),
    "55d6a44": ("data", "retrained on newer data, no change"),
    "bae3e37": ("data", "retrained on newer data while a quality filter was skipped"),
    "6b27d62": ("data", "quality filter restored: bad readings removed again"),
}
FREEZE_CAUSE = ("data", "re-measured on the talk's data freeze")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ─── ledger helpers ─────────────────────────────────────────────────────────

def month_year(date: str) -> str:
    d = dt.date.fromisoformat(date)
    return f"{MONTHS[d.month - 1]} {d.year}"


def long_date(date: str) -> str:
    d = dt.date.fromisoformat(date)
    return f"{d.day} {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][d.month - 1]} {d.year}"


class Ledger:
    def __init__(self, freeze: str):
        self.freeze = freeze
        self.entries: dict[str, dict] = {}

    def freeze_entry(self, key, value, display, unit, source, **extra):
        self.entries[key] = dict(value=value, display=display, unit=unit, source=source,
                                 date=self.freeze, kind="freeze", **extra)

    def historical(self, key, value, display, unit, source, date, when=None, **extra):
        # A historical number always carries its date wherever it is shown (spec A2): `when`
        # (default "Mon YYYY") is appended unless the display already names the date's year.
        if date[:4] not in display:
            display = f"{display} ({when or month_year(date)})"
        self.entries[key] = dict(value=value, display=display,
                                 unit=unit, source=source, date=date, kind="historical", **extra)

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.entries, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def fmt_r2(x: float) -> str:
    return f"{x:.2f}"


def fmt_runtime(seconds: float) -> str:
    return f"{seconds / 60:.0f} min" if seconds >= 90 else f"{seconds:.0f} s"


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def commit_date(sha: str) -> str:
    return git("log", "-1", "--format=%ad", "--date=short", sha).strip()


# ─── the training module, imported read-only ────────────────────────────────

def load_training_module():
    spec = importlib.util.spec_from_file_location(
        "_08_train_forecast_model", AUTO / "08_train_forecast_model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_08_train_forecast_model"] = mod
    spec.loader.exec_module(mod)
    # Guard: nothing this script calls writes models, but if anything ever did, it lands in a
    # throwaway dir, never in the production Models/ (a past test clobbered model_metadata.json).
    mod.MODELS_DIR = Path(tempfile.mkdtemp(prefix="talk_freeze_models_"))
    return mod


def run_cv_gru(tf, df: pd.DataFrame, bathy_coeffs: list):
    """Walk-forward CV for the GRU, ported unchanged from 4f9e553^ (plan D4)."""
    from gru_model import GRUTrainer
    print("\n=== GRU CV (4 folds × 150 epochs — expect ~15 min on CPU) ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in tf.CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()

        trainer = GRUTrainer(epochs=150, lr=1e-3, batch_size=64)
        trainer.fit(tr)

        all_dvol_pred, all_dvol_true = [], []
        preds_rows = []

        for h in range(1, 8):
            p_inf, p_dv, anc_dates, dv_true = trainer.predict_horizon(
                df, horizon=h, test_year=test_yr)
            if len(p_dv) == 0:
                continue

            all_dvol_pred.extend(p_dv.tolist())
            all_dvol_true.extend(dv_true.tolist())

            for i, ad in enumerate(anc_dates):
                preds_rows.append({
                    "date":      pd.Timestamp(ad),
                    "horizon_h": float(h),
                    "pred_dvol": float(p_dv[i]),
                })

        s2_r2_val = tf.r2(np.array(all_dvol_true), np.array(all_dvol_pred))
        s2_mae_val = tf.mae(np.array(all_dvol_true), np.array(all_dvol_pred))

        preds_df = pd.DataFrame(preds_rows)
        drift = tf._mean_7d_drift(df, preds_df, bathy_coeffs)

        cv_results.append({
            "fold": fold_name, "n_test": int(len(all_dvol_true)),
            "s1_r2": None,
            "s2_r2": round(s2_r2_val, 3),
            "s2_mae": round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results


# ─── 1. the eight models and the two baselines ──────────────────────────────

CACHE_DIR = TALK_DIR / "freeze_cache"     # gitignored; lets a killed run resume


def _cached_cv(freeze: str, model: str, runner):
    """Run one model's timed CV, or reuse its result from an earlier run on the same freeze and
    the same gold table bytes (the machine is low on memory and a long run can be killed)."""
    gold = hashlib.sha256((ROOT / "Gold Data" / "kinneret_gold_features.csv").read_bytes()).hexdigest()
    path = CACHE_DIR / f"{freeze}_{gold[:12]}_{model}.json"
    if path.exists():
        hit = json.loads(path.read_text(encoding="utf-8"))
        print(f"  (reusing {model} from {path.name})", flush=True)
        return hit["cv"], hit["seconds"]
    t0 = time.perf_counter()
    cv = runner()
    seconds = time.perf_counter() - t0
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cv": cv, "seconds": seconds}, indent=2), encoding="utf-8")
    return cv, seconds

def measure_models(led: Ledger, tf, df: pd.DataFrame):
    bathy = tf.fit_vol2level_poly()
    runners = {
        "baseline_gbr":            lambda: tf.run_cv(df)[0],
        "xgboost":                 lambda: tf.run_cv_xgb(df, bathy),
        "lgbm":                    lambda: tf.run_cv_lgb(df, bathy),
        "gru":                     lambda: run_cv_gru(tf, df, bathy),
        "gbr_max_chain":           lambda: tf.run_cv_max_chain(df, bathy),
        "gbr_s1_direct_s2_anchor": lambda: tf.run_cv_s1_direct_s2_anchor(df, bathy),
        "gbr_single_stage":        lambda: tf.run_cv_single_stage(df, bathy),
        "gbr_s1_chain_s2_roll1":   lambda: tf.run_cv_s1_chain_s2_roll1(df, bathy),
    }
    src = f"{THIS} (walk-forward CV, folds 2021-2024, gold table cut at the freeze)"
    champion_cv = None
    for m in MODELS:
        cv, seconds = _cached_cv(led.freeze, m, runners[m])
        by_fold = {r["fold"]: r["s2_r2"] for r in cv}
        assert sorted(by_fold) == FOLDS, f"{m}: folds {sorted(by_fold)}"
        maes = [r.get("s2_mae_Mm3", r.get("s2_mae")) for r in cv]
        mean = round(float(np.mean(list(by_fold.values()))), 3)
        led.freeze_entry(f"olympics.{m}.r2_mean", mean, fmt_r2(mean), "R²", src)
        for f in FOLDS:
            led.freeze_entry(f"olympics.{m}.r2_{f}", by_fold[f], fmt_r2(by_fold[f]), "R²", src)
        mae_mean = round(float(np.mean(maes)), 3)
        led.freeze_entry(f"olympics.{m}.mae_mean", mae_mean, f"{mae_mean:.2f}", "Mm³/day", src)
        led.freeze_entry(f"olympics.{m}.runtime_s", round(seconds, 1), fmt_runtime(seconds), "s",
                         f"{THIS} (wall-clock time of the 4-fold CV on this machine)")
        print(f"  -> {m}: R² {mean}  runtime {seconds:.0f} s", flush=True)
        if m == "baseline_gbr":
            champion_cv = cv

    # The champion = baseline_gbr (the standing Olympics winner).
    c_r2 = led.entries["olympics.baseline_gbr.r2_mean"]["value"]
    c_mae = led.entries["olympics.baseline_gbr.mae_mean"]["value"]
    csrc = f"{THIS} (champion = baseline_gbr, two-stage gradient boosting)"
    led.freeze_entry("champion.r2", c_r2, fmt_r2(c_r2), "R²", csrc)
    led.freeze_entry("champion.mae", c_mae, f"{c_mae:.2f}", "Mm³/day", csrc)
    for r in champion_cv:
        led.freeze_entry(f"champion.n_{r['fold']}", r["n_test"], str(r["n_test"]), "days", csrc)

    measure_baselines(led, tf, df)


def champion_fold_rows(tf, df: pd.DataFrame, test_yr: int) -> pd.DataFrame:
    """The exact test rows run_cv scores Stage 2 on (same dropna chain, no fitting)."""
    te = df[df["date"].dt.year == test_yr].copy()
    s1_te = te.dropna(subset=tf.S1_FEATURES + [tf.S1_TARGET])
    te["predicted_inflow_m3"] = np.nan
    te.loc[s1_te.index, "predicted_inflow_m3"] = 1.0   # present where Stage 1 predicts
    return te.dropna(subset=tf.S2_FEATURES + [tf.S2_TARGET])


def measure_baselines(led: Ledger, tf, df: pd.DataFrame):
    """Zero change ("the lake stays the same") and the seasonal average, on the champion's
    fold rows (plan D5). Seasonal = each day-of-year's mean volume change over the fold's
    training years only."""
    target = tf.S2_TARGET
    scores = {"zero_change": [], "seasonal": []}
    for fold_name, train_yrs, test_yr in tf.CV_FOLDS:
        rows = champion_fold_rows(tf, df, test_yr)
        y = rows[target].values

        train = df[df["date"].dt.year.isin(train_yrs)].dropna(subset=[target])
        doy_mean = train.groupby(train["date"].dt.dayofyear)[target].mean()
        doy_mean = doy_mean.reindex(range(1, 367)).interpolate(limit_direction="both")
        seasonal = doy_mean.loc[rows["date"].dt.dayofyear].values

        for name, pred in (("zero_change", np.zeros_like(y)), ("seasonal", seasonal)):
            scores[name].append((fold_name, len(rows), tf.r2(y, pred), tf.mae(y, pred)))

    src = {"zero_change": f"{THIS} (zero change: predicts no volume change, champion's CV rows)",
           "seasonal": f"{THIS} (seasonal average by day of year from each fold's training years, champion's CV rows)"}
    for name, folds in scores.items():
        r2_mean = round(float(np.mean([round(f[2], 3) for f in folds])), 3)
        mae_mean = round(float(np.mean([round(f[3], 3) for f in folds])), 3)
        led.freeze_entry(f"baseline.{name}.r2", r2_mean, fmt_r2(r2_mean), "R²", src[name])
        led.freeze_entry(f"baseline.{name}.mae", mae_mean, f"{mae_mean:.2f}", "Mm³/day", src[name])
        for fold_name, n, r2v, _ in folds:
            led.freeze_entry(f"baseline.{name}.n_{fold_name}", n, str(n), "days", src[name])
            led.freeze_entry(f"baseline.{name}.r2_{fold_name}", round(r2v, 3), fmt_r2(r2v), "R²",
                             src[name])
        print(f"  -> {name}: R² {r2_mean}  MAE {mae_mean}", flush=True)

    margin = round(led.entries["champion.r2"]["value"] - led.entries["baseline.zero_change.r2"]["value"], 3)
    led.freeze_entry("margin.zero_change.r2", margin, fmt_r2(margin), "R²",
                     f"{THIS} (champion R² minus zero-change R²)")
    margin_s = round(led.entries["champion.r2"]["value"] - led.entries["baseline.seasonal.r2"]["value"], 3)
    led.freeze_entry("margin.seasonal.r2", margin_s, fmt_r2(margin_s), "R²",
                     f"{THIS} (champion R² minus seasonal-average R²)")


# ─── 2. the hook: the lake level ────────────────────────────────────────────

def lowest_since(daily: pd.Series, when: pd.Timestamp):
    today = daily[when]
    for y in range(when.year - 1, daily.index.min().year - 1, -1):
        t = pd.Timestamp(year=y, month=when.month, day=when.day)
        if t in daily.index and daily[t] <= today:
            return y
    return None


def measure_level(led: Ledger):
    fd = pd.Timestamp(led.freeze)
    raw = pd.read_csv(ROOT / LEVEL_FILE, parse_dates=["date"]).set_index("date")["kinneret_level"]
    if fd not in raw.index:
        raise SystemExit(f"no measured level on the freeze date {led.freeze} in {LEVEL_FILE}")
    level = float(raw[fd])
    daily = load_daily()
    daily = daily[daily.index <= fd]
    src = f"{LEVEL_FILE} (Water Authority daily level)"

    led.freeze_entry("freeze_date", led.freeze, long_date(led.freeze), "date",
                     f"{THIS} (the one data freeze every measured number shares)")
    led.freeze_entry("level.freeze_m", level, f"{level:.2f}", "m", src)
    led.freeze_entry("level.red_line_m", RED_LINE, f"{RED_LINE:.0f}", "m",
                     "the lower red line, Water Authority operating rule")
    below_cm = round((RED_LINE - level) * 100)
    led.freeze_entry("level.below_red_line_cm", below_cm, f"{below_cm}", "cm",
                     f"{src} (red line minus the freeze-date level)")
    year = lowest_since(daily, fd)
    led.freeze_entry("level.lowest_since_year", year, str(year), "year",
                     f"{src} (latest earlier year at or below this level on the same calendar date)")
    led.freeze_entry("level.first_year", int(raw.index.min().year), str(raw.index.min().year),
                     "year", src)

    # The hook's year-over-year overlay (plan D18): daily from 1 January of HOOK_FIRST_YEAR,
    # ending on the freeze date.
    recent = daily[daily.index >= pd.Timestamp(HOOK_FIRST_YEAR, 1, 1)]
    series = [[d.strftime("%Y-%m-%d"), round(float(v), 3)] for d, v in recent.items()]
    led.freeze_entry("level.series", series, "level series", "m", f"{src} (daily, interpolated)")
    print(f"  -> level {level} m on {led.freeze}, lowest since {year}", flush=True)


def measure_scenarios(led: Ledger):
    """Two winters for the coming one, both real past winters, never a forecast (plan D18, A20).
    A winter's change = the level on 31 May minus the level on the freeze calendar date (it can be
    negative); over the last SCENARIO_WINTERS complete winters, dry = smallest, wet = largest."""
    fd = pd.Timestamp(led.freeze)
    daily = load_daily()
    last = fd.year - 1 if fd >= pd.Timestamp(fd.year, 5, 31) else fd.year - 2
    changes = {}
    for y in range(last - SCENARIO_WINTERS + 1, last + 1):
        start, end = pd.Timestamp(y, fd.month, fd.day), pd.Timestamp(y + 1, 5, 31)
        changes[y] = float(daily[end] - daily[start])
    freeze_m = led.entries["level.freeze_m"]["value"]
    window = f"{last - SCENARIO_WINTERS + 1}-{last + 1}"
    for name, y in (("dry", min(changes, key=changes.get)), ("wet", max(changes, key=changes.get))):
        season, date = f"{y}–{y + 1}", f"{y + 1}-05-31"   # both years: the display shows its date
        change, spring = round(changes[y], 3), round(freeze_m + changes[y], 3)
        src = (f"{LEVEL_FILE} ({'smallest' if name == 'dry' else 'largest'} winter change of the "
               f"{SCENARIO_WINTERS} winters {window}: level on 31 May minus the level on {fd:%d %b})")
        when = f"winter {season}"
        led.historical(f"scenario.{name}.season", season, season, "winter", src, date)
        led.historical(f"scenario.{name}.change_m", change, f"{change:+.2f} m", "m", src, date,
                       when=when)
        led.historical(f"scenario.{name}.spring_m", spring, f"{spring:.2f} m", "m",
                       f"{src}; freeze level plus that rise", date, when=when)
        print(f"  -> {name} winter {season}: change {change:+} m, spring {spring} m", flush=True)


# ─── 3. the champion's R² history ───────────────────────────────────────────

def measure_history(led: Ledger):
    shas = git("log", "--format=%h", "--", OLYMPICS_FILE).split()
    for seq, sha in enumerate(reversed(shas)):   # oldest first; seq orders same-day commits
        try:
            blob = json.loads(git("show", f"{sha}:{OLYMPICS_FILE}"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if sha not in HISTORY_CAUSES:
            raise SystemExit(f"R² snapshot {sha} has no cause label in HISTORY_CAUSES")
        r2v = blob["models"]["baseline_gbr"]["cv_vol_r2_mean"]
        ctype, cause = HISTORY_CAUSES[sha]
        led.historical(f"history.{sha}.r2", r2v, f"{r2v:.3f}", "R²",
                       f"git:{sha}:{OLYMPICS_FILE}#models.baseline_gbr.cv_vol_r2_mean",
                       commit_date(sha), sha=sha, seq=seq, cause=cause, cause_type=ctype)
    led.entries["champion.r2"].update(cause=FREEZE_CAUSE[1], cause_type=FREEZE_CAUSE[0])


# ─── 4. the frontier ────────────────────────────────────────────────────────

def measure_longrange(led: Ledger):
    """14-30-day skill, copied from the stored long-range evaluation (plan D17)."""
    lr = json.loads((ROOT / LONGRANGE_FILE).read_text(encoding="utf-8"))
    sha = git("log", "-1", "--format=%h", "--", LONGRANGE_FILE).strip()
    date = commit_date(sha)
    for season in ("wet", "dry"):
        for label, field in (("temp_bucket", "SS_tempbucket_vs_clim"), ("temp", "SS_temp_vs_clim")):
            val = lr["headline"][season][field]
            led.historical(f"frontier.{season}.{label}_ss", val, f"{val:+.2f}", "skill vs seasonal average",
                           f"{LONGRANGE_FILE}#headline.{season}.{field}", date,
                           perfect_prognosis=True,
                           measured_note=f"measured 2026-06-22 (paper §4.3); first committed {date}")


def crossing_days(daily: pd.Series) -> list[pd.Timestamp]:
    below = daily < RED_LINE
    return list(daily.index[below & ~below.shift(1, fill_value=True)])


def days_to_cross(level: float, start: pd.Timestamp, rate: pd.Series, scale: float):
    for k in range(1, CROSSING_CAP_DAYS + 1):
        start = start + pd.Timedelta(days=1)
        level += rate[start.dayofyear] * scale
        if level < RED_LINE:
            return k
    return None


def measure_crossings(led: Ledger):
    """Red-line crossing hindcast (plan D17): for every crossing of -213.0 m since 2006, re-issue
    the summer method every day from the last rain to the day before the crossing, and score the
    predicted crossing date against the real one by days of warning."""
    fd = pd.Timestamp(led.freeze)
    daily = load_daily()
    daily = daily[daily.index <= fd]
    rain = pd.read_csv(ROOT / ERA5_FILE, parse_dates=["date"], encoding="utf-8-sig") \
        .set_index("date")["rainfall_mm"]
    crossings = [c for c in crossing_days(daily[daily.index >= CROSSING_FROM])]

    rows = []                                     # (lead days, scaled k, unscaled k); k None = never
    for cross in crossings:
        wet = rain[(rain.index < cross) & (rain >= LAST_RAIN_MM)]
        if wet.empty:
            raise SystemExit(f"no rain >= {LAST_RAIN_MM} mm before crossing {cross.date()}")
        last_rain = wet.index.max()
        rate = recession_by_doy(daily, exclude_year=cross.year)
        for t in pd.date_range(last_rain, cross - pd.Timedelta(days=1)):
            win_start = t - pd.Timedelta(days=OBS_WINDOW)
            obs_rate = (float(daily[t]) - float(daily[win_start])) / OBS_WINDOW
            clim_win = np.mean([rate[d.dayofyear] for d in pd.date_range(win_start, t)])
            scale = float(np.clip(obs_rate / clim_win, *SCALE_CLAMP)) if clim_win < -1e-4 else 1.0
            rows.append(((cross - t).days,
                         days_to_cross(float(daily[t]), t, rate, scale),
                         days_to_cross(float(daily[t]), t, rate, 1.0)))
    f = pd.DataFrame(rows, columns=["lead", "scaled", "unscaled"])
    for m in ("scaled", "unscaled"):
        f[f"err_{m}"] = (f[m] - f["lead"]).abs()   # NaN where the forecast never crossed

    src = (f"{THIS} (crossing hindcast: {LEVEL_FILE} + {ERA5_FILE}; leave-one-year-out "
           f"recession from {rb.__name__}.py, issued daily from the last rain >= {LAST_RAIN_MM} mm)")
    never = {m: int(f[m].isna().sum()) for m in ("scaled", "unscaled")}
    led.freeze_entry("crossing.n", len(crossings), str(len(crossings)), "crossings", src)
    led.freeze_entry("crossing.never_crossed", never["scaled"], str(never["scaled"]), "forecasts", src,
                     note=f"scaled forecasts that never reached the red line within {CROSSING_CAP_DAYS} days")
    led.freeze_entry("crossing.unscaled.never_crossed", never["unscaled"], str(never["unscaled"]),
                     "forecasts", src)
    led.freeze_entry("crossing.issued", len(f), str(len(f)), "forecasts", src)
    led.freeze_entry("crossing.last_rain_mm", LAST_RAIN_MM, str(LAST_RAIN_MM), "mm", src)
    led.freeze_entry("crossing.first_year", int(crossings[0].year), str(crossings[0].year), "year", src)

    # Per band of days of warning, (lo, hi]. Each method alone over the forecasts it brought to the
    # line, its misses, and - for any scaled-vs-unscaled comparison - both methods over only the
    # forecasts BOTH brought to the line ("paired"), since the two miss different forecasts.
    for band, lo, hi in BANDS:
        b = f[(f["lead"] > lo) & (f["lead"] <= hi)]
        both = b.dropna(subset=["scaled", "unscaled"])
        led.freeze_entry(f"crossing.issued_{band}", len(b), str(len(b)), "forecasts", src)
        led.freeze_entry(f"crossing.paired.n_{band}", len(both), str(len(both)), "forecasts", src)
        for m in ("scaled", "unscaled"):
            val = round(float(b[f"err_{m}"].mean()), 1)
            led.freeze_entry(f"crossing.{m}.mae_{band}", val, f"{val:.0f}", "days", src,
                             n=int(b[m].notna().sum()))
            miss = int(b[m].isna().sum())
            led.freeze_entry(f"crossing.{m}.never_{band}", miss, str(miss), "forecasts", src)
            pv = round(float(both[f"err_{m}"].mean()), 1)
            led.freeze_entry(f"crossing.paired.{m}.mae_{band}", pv, f"{pv:.0f}", "days",
                             src + " (paired: forecasts both methods brought to the line)",
                             n=len(both))
    print("  -> crossings", len(crossings), "issued", len(f), "never", never, flush=True)
    for band, _, _ in BANDS:
        e = led.entries
        print(f"     {band:>8}: issued {e[f'crossing.issued_{band}']['value']:>4}  "
              f"miss s/u {e[f'crossing.scaled.never_{band}']['value']:>3}/{e[f'crossing.unscaled.never_{band}']['value']:>3}  "
              f"paired n {e[f'crossing.paired.n_{band}']['value']:>4}  "
              f"paired MAE s/u {e[f'crossing.paired.scaled.mae_{band}']['value']}/{e[f'crossing.paired.unscaled.mae_{band}']['value']}",
              flush=True)


# ─── 5. truth tests and the stamp ───────────────────────────────────────────

def run_truth_tests_and_stamp():
    r = subprocess.run([sys.executable, "-m", "pytest", *TRUTH_TESTS, "-q"],
                       cwd=ROOT)
    if r.returncode != 0:
        if STAMP_PATH.exists():
            STAMP_PATH.unlink()
        raise SystemExit("truth tests FAILED: no truth stamp written; the deck will not build")
    STAMP_PATH.write_text(json.dumps({
        "ledger_sha256": hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest(),
        "stamped_at": dt.datetime.now().isoformat(timespec="seconds"),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"truth tests passed; stamped {STAMP_PATH.relative_to(ROOT)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", default=DEFAULT_FREEZE)
    ap.add_argument("--keep-models", action="store_true",
                    help="reuse the 8 models and baselines from the current ledger (same freeze only)")
    args = ap.parse_args()

    led = Ledger(args.freeze)
    measure_level(led)
    measure_scenarios(led)
    if args.keep_models:
        old = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        if old["freeze_date"]["value"] != args.freeze:
            raise SystemExit("--keep-models needs a ledger on the same freeze date")
        for k, e in old.items():
            if k.split(".")[0] in ("olympics", "champion", "baseline", "margin"):
                led.entries[k] = {f: v for f, v in e.items() if f not in ("cause", "cause_type")}
    else:
        tf = load_training_module()
        df = tf.load_data()
        df = df[df["date"] <= pd.Timestamp(args.freeze)].reset_index(drop=True)
        print(f"gold table cut at {args.freeze}: {len(df):,} rows "
              f"({df['date'].min().date()} to {df['date'].max().date()})", flush=True)
        measure_models(led, tf, df)
    measure_history(led)
    measure_longrange(led)
    measure_crossings(led)

    led.entries = dict(sorted(led.entries.items()))
    led.write(LEDGER_PATH)
    print(f"wrote {LEDGER_PATH.relative_to(ROOT)} ({len(led.entries)} entries)")
    run_truth_tests_and_stamp()


if __name__ == "__main__":
    main()
