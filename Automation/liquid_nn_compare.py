"""
liquid_nn_compare.py  -  Liquid neural network (CfC or LTC) vs the baseline GBR,
same two-stage forecasting sub-steps.

Mirrors 08_train_forecast_model.run_cv() step for step:
  * same gold table (load_data), same walk-forward folds (2021-2024)
  * Stage 1: S1_FEATURES -> inflow_obstacle_m3
  * Stage 2: S2_FEATURES (predicted_inflow_m3 = actual in train, S1 OOF in test)
             -> volume_change_Mm3, target fit in signed_log1p space
  * level_m is YESTERDAY's level for both models (see lag_level)
  * same row filter (dropna on the stage's features + target at day t),
    so the test rows and n are identical to the baseline
  * same metrics (R², MAE in Mm³/day)

The only change is the regressor: a liquid network from ncps -- CfC (closed-form)
or LTC (ODE-unfolded) -- reading a SEQ_LEN-day window of the stage's own feature list
ending at day t, instead of the single day-t row the GBR sees.

Run:  python Automation/liquid_nn_compare.py [--cell cfc|ltc] [--seeds 3] [--seq-len 14]
"""
import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from ncps.torch import CfC, LTC

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("train08", HERE / "08_train_forecast_model.py")
t08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t08)

from model_lib import (  # noqa: E402  (08 put HERE on sys.path)
    S1_FEATURES, S1_TARGET, S2_FEATURES, S2_TARGET,
    signed_log1p_transform, inv_signed_log1p_transform,
)

OUT_DIR = t08.BASE_DIR / "docs" / "experiments"
CELLS = {"cfc": CfC, "ltc": LTC}
torch.set_num_threads(int(__import__("os").environ.get("LNN_THREADS", 8)))


# ─────────────────────────────────────────────────────────────────────────────
# Liquid network regressor
# ─────────────────────────────────────────────────────────────────────────────

class _LiquidNet(nn.Module):
    def __init__(self, n_in: int, units: int, cell: str):
        super().__init__()
        self.rnn = CELLS[cell](n_in, units, batch_first=True, return_sequences=False)
        self.head = nn.Linear(units, 1)

    def forward(self, x):
        h, _ = self.rnn(x)
        return self.head(h).squeeze(-1)


class LiquidRegressor:
    """Sequence regressor: windows of standardised features -> scalar target.

    y is standardised internally; the caller handles any domain transform
    (log1p / signed_log1p) so the stage logic stays visible in run_cv_liquid.
    """

    def __init__(self, seq_len=14, units=32, epochs=80, lr=3e-3,
                 batch=128, patience=12, seed=0, cell="cfc"):
        self.seq_len, self.units, self.epochs = seq_len, units, epochs
        self.lr, self.batch, self.patience, self.seed = lr, batch, patience, seed
        self.cell = cell

    # frame: full date-contiguous feature frame; idx: positional rows to use
    def _windows(self, X: np.ndarray, idx: np.ndarray) -> np.ndarray:
        L = self.seq_len
        pad = np.zeros((L - 1, X.shape[1]), dtype=np.float32)
        Xp = np.vstack([pad, X])
        return np.stack([Xp[i:i + L] for i in idx])     # row i ends at day i

    def fit(self, X: np.ndarray, idx: np.ndarray, y: np.ndarray):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self.y_mu, self.y_sd = float(y.mean()), float(y.std() + 1e-8)
        W = torch.tensor(self._windows(X, idx), dtype=torch.float32)
        Y = torch.tensor((y - self.y_mu) / self.y_sd, dtype=torch.float32)

        # chronological early-stopping split: last ~365 training rows
        n_val = min(365, len(idx) // 5)
        Wt, Yt, Wv, Yv = W[:-n_val], Y[:-n_val], W[-n_val:], Y[-n_val:]

        self.net = _LiquidNet(X.shape[1], self.units, self.cell)
        opt = torch.optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        loss_fn = nn.HuberLoss(delta=1.0)
        best, best_state, bad = np.inf, None, 0
        for _ in range(self.epochs):
            self.net.train()
            perm = torch.randperm(len(Wt))
            for b in range(0, len(Wt), self.batch):
                j = perm[b:b + self.batch]
                opt.zero_grad()
                loss = loss_fn(self.net(Wt[j]), Yt[j])
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                opt.step()
            self.net.eval()
            with torch.no_grad():
                v = float(nn.functional.mse_loss(self.net(Wv), Yv))
            if v < best - 1e-4:
                best, bad = v, 0
                best_state = {k: t.clone() for k, t in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        self.net.load_state_dict(best_state)
        return self

    def predict(self, X: np.ndarray, idx: np.ndarray) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            W = torch.tensor(self._windows(X, idx), dtype=torch.float32)
            return self.net(W).numpy() * self.y_sd + self.y_mu


def _standardise(df: pd.DataFrame, feats: list, train_mask: np.ndarray) -> np.ndarray:
    """z-score with TRAIN-only stats; NaN -> 0 (= train mean), like GBR's impute."""
    X = df[feats].to_numpy(dtype=float)
    mu = np.nanmean(X[train_mask], axis=0)
    sd = np.nanstd(X[train_mask], axis=0) + 1e-8
    Z = (X - mu) / sd
    return np.nan_to_num(Z, nan=0.0).astype(np.float32)


def _member_cell(cell: str, s: int) -> str:
    """'mix' = a mixed society: members alternate CfC, LTC, CfC, ..."""
    return ("cfc", "ltc")[s % 2] if cell == "mix" else cell


def _ensemble(X, tr_idx, y_tr, te_idx, seeds, seq_len, cell):
    preds = [LiquidRegressor(seq_len=seq_len, seed=s, cell=_member_cell(cell, s))
             .fit(X, tr_idx, y_tr).predict(X, te_idx)
             for s in range(seeds)]
    return np.mean(preds, axis=0), preds


# ─────────────────────────────────────────────────────────────────────────────
# Walk-forward CV — the same sub-steps as t08.run_cv
# ─────────────────────────────────────────────────────────────────────────────

def run_cv_liquid(df: pd.DataFrame, seeds: int, seq_len: int, cell: str):
    print(f"\n=== Liquid NN ({cell.upper()}) walk-forward CV  seeds={seeds} seq_len={seq_len} ===")
    yrs = df["date"].dt.year.to_numpy()
    results, seed_r2 = [], {}

    for fold_name, train_yrs, test_yr in t08.CV_FOLDS:
        t0 = time.time()
        in_tr = np.isin(yrs, train_yrs)
        in_te = yrs == test_yr
        # history window may reach back into earlier years, never forward
        hist = yrs <= test_yr

        # ── Stage 1 ──────────────────────────────────────────────────────────
        ok1 = df[S1_FEATURES + [S1_TARGET]].notna().all(axis=1).to_numpy()
        tr1, te1 = np.where(in_tr & ok1)[0], np.where(in_te & ok1)[0]
        X1 = _standardise(df, S1_FEATURES, in_tr & ok1)
        X1[~hist] = 0.0
        y1 = df[S1_TARGET].to_numpy(dtype=float)
        p1, _ = _ensemble(X1, tr1, np.log1p(np.clip(y1[tr1], 0, None)), te1, seeds, seq_len, cell)
        p1 = np.clip(np.expm1(p1), 0, None)

        # ── Stage 2 ──────────────────────────────────────────────────────────
        d2 = df.copy()
        d2["predicted_inflow_m3"] = d2[S1_TARGET]          # actual = training proxy
        d2.loc[d2.index[in_te], "predicted_inflow_m3"] = np.nan
        d2.loc[d2.index[te1], "predicted_inflow_m3"] = p1   # S1 OOF in the test year
        ok2 = d2[S2_FEATURES + [S2_TARGET]].notna().all(axis=1).to_numpy()
        tr2, te2 = np.where(in_tr & ok2)[0], np.where(in_te & ok2)[0]
        X2 = _standardise(d2, S2_FEATURES, in_tr & ok2)
        X2[~hist] = 0.0
        y2 = d2[S2_TARGET].to_numpy(dtype=float)
        p2_t, per_seed = _ensemble(X2, tr2, signed_log1p_transform(y2[tr2]), te2, seeds, seq_len, cell)
        p2 = inv_signed_log1p_transform(p2_t)

        r = {
            "fold": fold_name, "n_test": int(len(te2)),
            "s1_r2": round(t08.r2(y1[te1], p1), 3),
            "s1_mae_Mm3": round(t08.mae(y1[te1], p1) / 1e6, 3),
            "s2_r2": round(t08.r2(y2[te2], p2), 3),
            "s2_mae_Mm3": round(t08.mae(y2[te2], p2), 3),
        }
        seed_r2[fold_name] = [round(t08.r2(y2[te2], inv_signed_log1p_transform(p)), 3)
                              for p in per_seed]
        results.append(r)
        print(f"  {fold_name}:  S1 R²={r['s1_r2']:.3f}  |  S2 R²={r['s2_r2']:.3f}  "
              f"MAE={r['s2_mae_Mm3']:.3f}  (n={r['n_test']}, per-seed S2 {seed_r2[fold_name]}, "
              f"{time.time() - t0:.0f}s)")
    return results, seed_r2


def lag_level(df: pd.DataFrame) -> pd.DataFrame:
    """level_m -> the previous day's level (no same-day leak of the S2 target)."""
    out = df.copy()
    out["level_m"] = df["level_m"].shift(1)
    return out


def _mean(rows, k):
    return round(float(np.mean([r[k] for r in rows])), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--seq-len", type=int, default=14)
    ap.add_argument("--cell", choices=sorted(CELLS) + ["mix"], default="cfc")
    ap.add_argument("--last-test-year", type=int, default=2024,
                    help="extend the walk-forward folds past 2024 (this run only; 08 is untouched)")
    a = ap.parse_args()

    t08.CV_FOLDS = [(str(y), list(range(2012, y)), y) for y in range(2021, a.last_test_year + 1)]
    df = t08.load_data()
    official, _ = t08.run_cv(df)        # the champion's CV as-is (same-day level_m)
    # S2's target is vol(level_t) - vol(level_t-1). A 14-day window holding same-day
    # level_m contains both, so the target is computable from the input. Both models
    # in the race therefore see YESTERDAY's level (what is known when forecasting t).
    df = lag_level(df)
    base, _ = t08.run_cv(df)            # GBR, parity input
    liq, seed_r2 = run_cv_liquid(df, a.seeds, a.seq_len, a.cell)

    print("\n=== Comparison (S2 = end-to-end volume change, S1 OOF inflow as input) ===")
    print(f"  {'fold':6} {'n':>5} | {'GBR S1':>7} {'LNN S1':>7} | {'GBR S2':>7} {'LNN S2':>7} | "
          f"{'GBR MAE':>8} {'LNN MAE':>8}")
    for b, l in zip(base, liq):
        assert b["fold"] == l["fold"] and b["n_test"] == l["n_test"], (b, l)
        print(f"  {b['fold']:6} {b['n_test']:>5} | {b['s1_r2']:7.3f} {l['s1_r2']:7.3f} | "
              f"{b['s2_r2']:7.3f} {l['s2_r2']:7.3f} | {b['s2_mae_Mm3']:8.3f} {l['s2_mae_Mm3']:8.3f}")
    print(f"  {'mean':6} {'':>5} | {_mean(base,'s1_r2'):7.3f} {_mean(liq,'s1_r2'):7.3f} | "
          f"{_mean(base,'s2_r2'):7.3f} {_mean(liq,'s2_r2'):7.3f} | "
          f"{_mean(base,'s2_mae_Mm3'):8.3f} {_mean(liq,'s2_mae_Mm3'):8.3f}")
    print(f"  (champion GBR as-is, same-day level_m: S2 R² {_mean(official,'s2_r2'):.3f}  "
          f"MAE {_mean(official,'s2_mae_Mm3'):.3f})")

    to = "" if a.last_test_year == 2024 else f"_to{a.last_test_year}"
    out_file = OUT_DIR / f"liquid_nn_cv_{a.cell}_s{a.seeds}{to}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "gold_last_date": str(df["date"].max().date()),
        "liquid_config": {"cell": f"{a.cell.upper()} (ncps)", "units": 32, "seq_len": a.seq_len,
                          "seeds": a.seeds, "members": [_member_cell(a.cell, i) for i in range(a.seeds)], "loss": "Huber", "early_stop": "last 365 train rows"},
        "level_input": "level_m lagged 1 day for both GBR and LNN (same-day level leaks the S2 target)",
        "champion_gbr_same_day_level": {"cv_results": official, "s2_r2_mean": _mean(official, "s2_r2"),
                                        "s2_mae_mean": _mean(official, "s2_mae_Mm3")},
        "baseline_gbr": {"cv_results": base, "s1_r2_mean": _mean(base, "s1_r2"),
                         "s2_r2_mean": _mean(base, "s2_r2"), "s2_mae_mean": _mean(base, "s2_mae_Mm3")},
        f"liquid_{a.cell}": {"cv_results": liq, "s2_r2_per_seed": seed_r2,
                       "s1_r2_mean": _mean(liq, "s1_r2"),
                       "s2_r2_mean": _mean(liq, "s2_r2"), "s2_mae_mean": _mean(liq, "s2_mae_Mm3")},
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {out_file.relative_to(t08.BASE_DIR)}")


if __name__ == "__main__":
    main()
