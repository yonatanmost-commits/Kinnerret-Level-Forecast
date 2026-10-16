"""Acceptance tests for Automation/cfc_bands.py: forecast ranges from the errors of
earlier forecasts, with no look-ahead."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Automation"))
import cfc_bands as cb  # noqa: E402


def recs(years, H=7, step=7, resid=lambda y, d: 0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for y in years:
        for d in pd.date_range(f"{y}-01-01", f"{y}-12-31", freq=f"{step}D"):
            pred = float(rng.normal())
            rows.append({"year": y, "start": d.strftime("%Y-%m-%d"), "H": H,
                         "pred": pred, "obs": pred + resid(y, d)})
    return pd.DataFrame(rows)


def test_band_uses_only_outcomes_known_at_the_start():
    # 2010-2013 errors are 0; 2014's are +100. A 2014 start may only see outcomes
    # already observed by its start day, so its 7-day band stays near zero width
    # except through 2014 outcomes that ended before it.
    df = recs(range(2010, 2015), resid=lambda y, d: 100.0 if y == 2014 else 0.0)
    out = cb.bands(df, levels=(0.8,), doy_window=10, min_years=3)
    first = out[(out.year == 2014)].sort_values("start").iloc[0]
    assert abs(first.hi_80 - first.pred) < 1e-9 and abs(first.lo_80 - first.pred) < 1e-9


def test_long_horizon_excludes_outcomes_after_the_start():
    # H=365: a start on 2014-03-05 has seen outcomes of starts up to 2013-03-05 only.
    # Errors are 0 for starts up to 2013-03-05 and +50 after; the band must stay at 0.
    df = recs(range(2009, 2015), H=365,
              resid=lambda y, d: 50.0 if d >= pd.Timestamp("2013-03-06") else 0.0)
    out = cb.bands(df, levels=(0.9,), doy_window=30, min_years=3)
    row = out[out.start == "2014-03-05"].iloc[0]
    assert abs(row.hi_90 - row.pred) < 1e-9


def test_season_window_excludes_other_seasons():
    # January errors +10, July errors -10; a January band must not reach below pred.
    df = recs(range(2010, 2015), resid=lambda y, d: 10.0 if d.month == 1 else (-10.0 if d.month == 7 else 0.0))
    out = cb.bands(df, levels=(0.9,), doy_window=20, min_years=3)
    jan = out[(out.year == 2014) & (pd.to_datetime(out.start).dt.month == 1)]
    assert (jan.lo_90 >= jan.pred - 1e-9).all()


def test_too_few_years_gives_no_band():
    df = recs(range(2010, 2014))
    out = cb.bands(df, levels=(0.8,), doy_window=30, min_years=3)
    # a year's own earlier, already observed starts count, so 2012's later starts have 3 years
    assert out[out.year <= 2011]["lo_80"].isna().all()
    assert out[out.year == 2013]["lo_80"].notna().all()


def test_coverage_matches_level_for_steady_errors():
    df = recs(range(2000, 2016), resid=lambda y, d: float(np.random.default_rng(hash((y, d.dayofyear)) % 2**32).normal()))
    out = cb.bands(df, levels=(0.5, 0.8), doy_window=45, min_years=5).dropna()
    for p in (0.5, 0.8):
        inside = ((out.obs >= out[f"lo_{int(p * 100)}"]) & (out.obs <= out[f"hi_{int(p * 100)}"])).mean()
        assert abs(inside - p) < 0.06, (p, inside)


def test_scenario_members_set_the_band_when_errors_are_zero():
    # three past-winter scenarios per forecast, a model with no error: the 90% band is
    # the members' 5-95% range
    base = recs(range(2010, 2015))
    members = pd.concat([base.assign(pred=base.pred + d) for d in (-1.0, 0.0, 1.0)])
    errors = base.assign(obs=base.pred)                       # known-weather error 0
    out = cb.bands(members, levels=(0.9,), doy_window=30, min_years=3, errors=errors)
    row = out[out.year == 2014].iloc[0]
    # each scenario repeats once per pooled (zero) error, so a third of the draws sit at
    # -1 and a third at +1: the 5..95% band is the scenarios' full range around the median
    assert abs(row.lo_90 - (row.pred - 1.0)) < 1e-9 and abs(row.hi_90 - (row.pred + 1.0)) < 1e-9
    assert len(out) == len(base)                              # one row per forecast


def test_self_correction_restores_coverage_when_errors_grow():
    # errors widen year by year, so the past understates the future; the self-correcting
    # band (gamma > 0) must cover closer to 80% than the plain one
    rng = np.random.default_rng(1)
    df = recs(range(2000, 2016), resid=lambda y, d: float(rng.normal(scale=1 + 0.3 * (y - 2000))))
    def cov(g):
        o = cb.bands(df, levels=(0.8,), doy_window=45, min_years=3, gamma=g).dropna(subset=["lo_80"])
        return ((o.obs >= o.lo_80) & (o.obs <= o.hi_80)).mean()
    assert abs(cov(0.01) - 0.8) < abs(cov(0.0) - 0.8)


def test_member_weights_tilt_the_band():
    # two scenarios per forecast, -1 and +1; giving +1 all the weight moves the band up to it
    base = recs(range(2010, 2015))
    lo = base.assign(pred=base.pred - 1.0, weight=1e-9)
    hi = base.assign(pred=base.pred + 1.0, weight=1.0)
    errors = base.assign(obs=base.pred)                                    # model error 0
    out = cb.bands(pd.concat([lo, hi]), levels=(0.8,), doy_window=30, min_years=3, errors=errors)
    row = out[out.year == 2014].iloc[0]
    assert abs(row.lo_80 - (row.obs + 1.0)) < 1e-6 and abs(row.hi_80 - (row.obs + 1.0)) < 1e-6
    assert abs(row.pred - (row.obs + 1.0)) < 1e-6                         # weighted median


def test_equal_weights_change_nothing():
    base = recs(range(2010, 2015))
    members = pd.concat([base.assign(pred=base.pred + d) for d in (-1.0, 0.0, 1.0)])
    errors = base.assign(obs=base.pred + 0.1)
    a = cb.bands(members, levels=(0.8,), errors=errors)
    b = cb.bands(members.assign(weight=2.5), levels=(0.8,), errors=errors)
    assert np.allclose(a.dropna().lo_80, b.dropna().lo_80) and np.allclose(a.dropna().hi_80, b.dropna().hi_80)


def test_threshold_probabilities_come_from_the_weighted_scenarios():
    # scenarios at -1, 0, +1 around pred with weights 1, 1, 2 and no model error:
    # P(level < pred + 0.5) = (1 + 1) / 4
    base = recs(range(2010, 2015))
    members = pd.concat([base.assign(pred=base.pred + d, weight=w) for d, w in ((-1.0, 1.0), (0.0, 1.0), (1.0, 2.0))])
    errors = base.assign(obs=base.pred)
    row0 = base[base.year == 2014].iloc[0]
    out = cb.bands(members, levels=(0.8,), doy_window=30, min_years=3, errors=errors,
                   thresholds={"mid": row0.pred + 0.5, "low": row0.pred - 5, "high": row0.pred + 5})
    row = out[(out.year == 2014) & (out.start == row0.start)].iloc[0]
    assert abs(row.p_mid - 0.5) < 1e-9 and row.p_low == 0.0 and row.p_high == 1.0
