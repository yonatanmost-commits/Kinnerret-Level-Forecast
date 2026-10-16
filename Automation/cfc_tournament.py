"""
cfc_tournament.py  -  CfC against itself: three ways to forecast the lake H days ahead.

One test bench for every method, on the ERA5 long table (2001-2025, no rain
intensity; see liquid_nn_era5_long.py):
  * test years 2010-2025, each trained on 2001 .. year-1
  * forecasts start every 7th day of the test year on which the level is known
    (the "last known day"), horizons 7/13/26/130/260/365 days
  * future weather two ways: obs (what happened) and clim (training-year
    day-of-year means, what a real forecast could use)
  * every single forecast is stored, so methods are compared start by start

Methods
  A  relay   - the two-stage one-day CfC rolled forward on its own predictions
               (liquid_nn_horizons.rollout, unchanged)
  A1 relay, one step - as A without the inflow step (control: B has no inflow step)
  G  the production two-stage GBR (train_08 settings), rolled forward exactly as A:
     the champion the CfC methods have to beat. Deterministic, so --seeds is ignored.
  B  direct  - a CfC reads the 60 days up to the start day; a small head adds the
               weather totals of each horizon's window and predicts all six volume
               changes at once. No prediction is ever fed back.
  C  ode     - a CfC encoder hands its state to a CfC decoder that steps through
               the future on an irregular time grid (daily to day 14, then about
               weekly), each step told its real length in days (timespans); driven
               by weather only, trained on the error of the whole path.

Winner rule (fixed before any result): lowest mean level MAE over the six
horizons with clim weather.

Run:  python Automation/cfc_tournament.py --method A|B|C [--seeds 3]
      python Automation/cfc_tournament.py --summary
Each finished test year is saved; a rerun skips it.

Memory check (how many past days the winner uses), outputs under CFC_OUT=.../memory:
  --enc-len L     history length; for A/A1 too (default 14 there, label A30 etc.)
  --occlude 7,14  test-time only: blank (zero) the standardised inputs older than k
                  days in the trained B/C nets' history window; no retraining.
                  Stored as weather "clim|k" / "obs|k" next to the full-window forecast.
  --c-full        C trained like B (every training day, 80 epochs, patience 10) instead
                  of the night-saving every-other-day / 60 / 8; label C60f.

IMS bench and calibration (B only):
  --table ims     the real gold table (IMS station weather, rain intensity in the history
                  and in A's features), test years 2021-2025; gaps <= 3 days interpolated.
  --bucket        history also carries the soil-moisture bucket (bucket_S, bucket_Q30,
                  longrange_state.soil_moisture_bucket, S_max 150 mm); label suffix b.
  --ensemble      past-winters ensemble: one extra forecast per earlier year Y, fed Y's
                  weather from the same day of year (past weather only), stored as weather
                  "ens|Y". No retraining; the report scores the median and the band.

Why does a week of history suffice? (B only)
  --no-state      history without level, volume change and the level-read flag (weather
                  and inflow stay); the level still converts dV to level. Label suffix n.
  --state-only    the opposite: history is level, volume change and the level-read flag
                  only (no weather, season or inflow). Label suffix s.
  --cell lstm     B's encoder is an LSTM (64 units, ~20k weights, the CfC cell ~23k)
                  instead of the CfC. Label suffix lstm.
  --cell gru      the same with a GRU (75 units, ~21k weights). Label suffix gru.

Environment: CFC_OUT (results folder), CFC_YEARS (comma list of test years), CFC_GOLD
(the gold table --table ims reads; default Gold Data/kinneret_gold_features.csv).

Seasonal forecast
  --seas5         adds weathers "seas5", "seas5c" (calibrated per lead month: SEAS5's rain
                  ratio stretched or shrunk by how its earlier forecasts matched the rain
                  that fell, earlier years only) and "seas5s" (calibrated on the season's
                  total rain instead, one ratio per forecast; seas5.season_calibrate):
                  average weather with the ECMWF SEAS5 forecast
                  months rescaled (rain x predicted ratio, temperature + anomaly; see
                  seas5.py). B, A, A1 and G. Needs Raw Data/SEAS5 (seas5_fetch.py).

Humidity check
  --no-humidity   drop every input derived from humidity (humidity, VPD, ET0, ET0 sums and
                  the rain-minus-ET0 balances), for B and the relay. The IMS stations'
                  humidity steps in 2012-13. Label suffix h.

Weather-source fight
  --table-from D  drop every row before date D (YYYY-MM-DD) from the table, so training,
                  scaling and climatology see the same span as another table (e.g. the
                  IMS table's 2012-09-01). Label unchanged: use a separate CFC_OUT.
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from ncps.torch import CfC

import liquid_nn_era5_long as L            # long ERA5 table + feature patching
import liquid_nn_horizons as Hz            # method A machinery
import seas5                               # SEAS5 seasonal forecast as weather ahead

t08, lnc = L.t08, L.lnc
OUT = Path(os.environ.get("CFC_OUT", t08.BASE_DIR / "docs" / "experiments" / "cfc_tournament"))
if "CFC_GOLD" in os.environ:                 # --table ims from another gold file (e.g. a branch's worktree)
    t08.GOLD_FILE = Path(os.environ["CFC_GOLD"])
HORIZONS = [7, 13, 26, 130, 260, 365]
HMAX = max(HORIZONS)
TEST_YEARS = [int(y) for y in os.environ["CFC_YEARS"].split(",")] if "CFC_YEARS" in os.environ     else list(range(2010, 2026))
EPOCH_CAP = int(os.environ.get("CFC_EPOCHS", 0))       # smoke tests only
EVERY = 7
ENC_L = 60                     # encoder history (days) for B and C; --enc-len sets it
FIRST_ANCHOR = 200             # fixed, so every history length scores the same starts
DM = ["temp_mean_C", "temp_max_C", "temp_min_C", "humidity_pct", "wind_speed_ms",
      "rainfall_mm", "radiation_MJm2", "vpd_kPa", "et0_mm"]
SUM_COLS = ["rainfall_mm", "et0_mm", "radiation_MJm2"]           # window totals
MEAN_COLS = ["temp_mean_C", "humidity_pct", "wind_speed_ms", "vpd_kPa"]   # window means
HUMIDITY_INPUTS = ("humidity", "vpd", "et0", "moisture_balance")   # name prefixes, --no-humidity
NO_HUMIDITY = False


def drop_humidity():
    """--no-humidity: drop every weather input derived from humidity."""
    global DM, SUM_COLS, MEAN_COLS, NO_HUMIDITY
    NO_HUMIDITY = True
    keep = lambda cols: [c for c in cols if not c.startswith(HUMIDITY_INPUTS)]
    DM, SUM_COLS, MEAN_COLS = keep(DM), keep(SUM_COLS), keep(MEAN_COLS)


def relay_features(feats: list) -> list:
    """The relay's (A, A1, G) feature list, less the humidity inputs under --no-humidity."""
    return [f for f in feats if not (NO_HUMIDITY and f.startswith(HUMIDITY_INPUTS))]
TABLE = "era5"                 # --table
EXTRA_ENC = []                 # history-only inputs added by --table ims / --bucket
HISTORY = "all"                # "all" | "weather" (--no-state) | "state" (--state-only)
CELL = "cfc"                   # --cell
TABLE_FROM = None              # --table-from
SEAS5 = None                   # --seas5: the SEAS5 ensemble-mean table
BUCKET_S_MAX = 150.0           # mm, as longrange_phaseb_eval / bucket_backport_eval
torch.set_num_threads(8)


# ─────────────────────────────────────────────────────────────────────────────
# The bench
# ─────────────────────────────────────────────────────────────────────────────

def tables():
    base = ims_table() if TABLE == "ims" else L.build_long_table()   # level_m = level(date)
    if TABLE_FROM:
        base = base[base["date"] >= pd.Timestamp(TABLE_FROM)].reset_index(drop=True)
    if "bucket_S" in EXTRA_ENC:
        base = add_bucket(base)
    lagged = lnc.lag_level(base)                     # level_m = level(date-1), method A's input
    return base, lagged


def ims_table() -> pd.DataFrame:
    """The gold table 08 trains on. Short weather gaps (<= 3 days) are interpolated so
    a horizon window is not dropped for one missing radiation reading."""
    df = t08.load_data().sort_values("date").reset_index(drop=True)
    cols = DM + [L.NO_INTENSITY]
    df[cols] = df[cols].interpolate(limit=3, limit_area="inside")
    return df


def add_bucket(df: pd.DataFrame) -> pd.DataFrame:
    from longrange_state import soil_moisture_bucket
    rain = df["rainfall_mm"].fillna(0.0).to_numpy()
    et = df["et0_mm"].fillna(df["et0_mm"].median()).to_numpy()
    S, Q = soil_moisture_bucket(rain, et, S_max=BUCKET_S_MAX, S0=0.5 * BUCKET_S_MAX)
    return df.assign(bucket_S=S, bucket_Q30=pd.Series(Q).rolling(30, min_periods=1).sum().to_numpy())


def anchors_for(base: pd.DataFrame, year: int) -> np.ndarray:
    yrs = base["date"].dt.year.to_numpy()
    cand = np.where(yrs == year)[0][::EVERY]
    return cand[base["level_m"].notna().to_numpy()[cand] & (cand >= FIRST_ANCHOR)]


def climatology(base: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
    return Hz.doy_climatology(base, train_mask)


def records(method, year, base, anchors, preds: dict) -> list:
    """preds[weather] = (A, HMAX) predicted level, column h-1 = day anchor+h."""
    lvl = base["level_m"].to_numpy()
    out = []
    for w, P in preds.items():
        for k, a in enumerate(anchors):
            for H in HORIZONS:
                if a + H >= len(base) or np.isnan(lvl[a + H]) or np.isnan(P[k, H - 1]):
                    continue
                out.append({"method": method, "weather": w, "year": year,
                            "start": str(base["date"].iat[a].date()), "H": H,
                            "level0": float(lvl[a]), "pred": float(P[k, H - 1]),
                            "obs": float(lvl[a + H])})
    return out


def references(base, anchors, year, train_mask) -> list:
    lvl = base["level_m"].to_numpy()
    s = base.set_index("date")["level_m"]
    s_tr = s[train_mask]
    P_pers = np.repeat(lvl[anchors][:, None], HMAX, axis=1)
    P_clim = np.empty((len(anchors), HMAX))
    for k, a in enumerate(anchors):
        d0 = base["date"].iat[a]
        for H in HORIZONS:
            chg = (s_tr.shift(-H) - s_tr)
            chg = chg[chg.index.dayofyear == d0.dayofyear].mean()
            P_clim[k, H - 1] = lvl[a] + chg
    return (records("persistence", year, base, anchors, {"-": P_pers}) +
            records("clim_change", year, base, anchors, {"-": P_clim}))


# ─────────────────────────────────────────────────────────────────────────────
# Method A - relay
# ─────────────────────────────────────────────────────────────────────────────

RELAY_MET = list(Hz.DAILY_MET)        # the relay's weather columns, before any table trims them


def relay_met(table: str) -> list:
    """Weather columns the relay swaps for climatology under "clim". Rain intensity is a
    model input only on the IMS table; there it must be swapped too, or the relay reads
    the real future intensity."""
    return [c for c in RELAY_MET if table == "ims" or c != L.NO_INTENSITY]


def run_A(base, lagged, year, anchors, seeds, one_step=False, seq_len=14, kind="lnn"):
    Hz.S1_FEATURES = relay_features(lnc.S1_FEATURES)                     # set by L.set_features
    # A1 (one-step relay) drops the inflow step: volume change straight from weather
    # and lake state, so A1 vs B isolates relay vs direct, and A vs A1 the inflow step
    Hz.S2_FEATURES = [f for f in relay_features(lnc.S2_FEATURES)
                      if not (one_step and f == "predicted_inflow_m3")]
    Hz.DAILY_MET = relay_met(TABLE)
    yrs = lagged["date"].dt.year.to_numpy()
    trm = yrs < year
    clim = Hz.doy_climatology(lagged, trm)
    dfx = Hz.extend(lagged, HMAX + 1, clim)
    bathy = t08.fit_vol2level_poly()
    m = Hz.TwoStage(kind, "cfc", seeds, seq_len).fit(lagged, trm)
    out = {w: Hz.rollout(m, dfx, anchors, HMAX, w, clim, bathy) for w in ("obs", "clim")}
    if SEAS5 is not None:                       # starts sharing a forecast roll out together
        days = lagged["date"].iloc[anchors]
        group = np.array([seas5.init_for(d) for d in days])
        for w in SEAS5_WEATHERS:
            anom = seas5_anomalies(base, year, w)
            P = np.empty((len(anchors), HMAX))
            for g in np.unique(group):
                k = np.where(group == g)[0]      # adjusted from the group's first start
                P[k] = Hz.rollout(m, dfx, anchors[k], HMAX, "clim",
                                  seas5.adjust_clim(clim, days.iat[k[0]], anom), bathy)
            out[w] = P
    return out


SEAS5_WEATHERS = ("seas5", "seas5c", "seas5s")


def seas5_anomalies(base, year, weather="seas5"):
    """SEAS5 anomalies for test year `year`: raw ("seas5"), calibrated month by month
    ("seas5c") or on the season total ("seas5s"), against the bench table's own rain
    (the weather the model was trained on), earlier years only."""
    anom = seas5.anomalies(SEAS5, year)
    rain = base.set_index("date")["rainfall_mm"]
    if weather == "seas5c":
        return seas5.calibrate(anom, seas5.calibration_slopes(anom, seas5.observed_ratio(rain, year), year))
    if weather == "seas5s":
        return seas5.season_calibrate(anom, rain, year)
    return anom


# ─────────────────────────────────────────────────────────────────────────────
# Shared inputs for B and C
# ─────────────────────────────────────────────────────────────────────────────

def encoder_matrix(base: pd.DataFrame) -> np.ndarray:
    """Per-day encoder inputs (unstandardised). Missing level/volume change stay
    NaN here; a 0/1 flag says whether the level was read that day."""
    f = base[DM + ["season_sin", "season_cos"]].copy()
    f["log_inflow"] = np.log1p(base["inflow_obstacle_m3"].clip(lower=0))
    if HISTORY == "state":
        f = f[[]]
    if HISTORY != "weather":
        f["level_m"] = base["level_m"]
        f["dvol"] = base["volume_change_Mm3"]
        f["level_seen"] = base["level_m"].notna().astype(float)
    for c in EXTRA_ENC:
        f[c] = base[c]
    return f.to_numpy(float)


class Scaler:
    def __init__(self, X):
        self.mu, self.sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0) + 1e-8

    def __call__(self, X):
        return np.nan_to_num((X - self.mu) / self.sd, nan=0.0).astype(np.float32)


def windows(Z: np.ndarray, anchors: np.ndarray, L_: int) -> np.ndarray:
    return np.stack([Z[a - L_ + 1:a + 1] for a in anchors])


def blanked(X: torch.Tensor, k) -> torch.Tensor:
    """History window with every day older than the last k set to 0 (the training
    mean, after scaling). k=None leaves it whole."""
    if k is None or k >= X.shape[1]:
        return X
    X = X.clone()
    X[:, :X.shape[1] - k] = 0.0
    return X


def tag(w, k):
    return w if k is None else f"{w}|{k}"


def future_weather(base, anchors, weather, clim, n_days):
    """(A, n_days, len(DM)) daily weather on days anchor+1 .. anchor+n_days."""
    W = np.full((len(anchors), n_days, len(DM)), np.nan)
    X = base[DM].to_numpy(float)
    d0 = base["date"].iloc[anchors].to_numpy()
    anom = seas5_anomalies(base, pd.Timestamp(d0[0]).year, weather) if weather in SEAS5_WEATHERS else None
    for k, a in enumerate(anchors):
        if weather == "obs":
            seg = X[a + 1:a + 1 + n_days]
            W[k, :len(seg)] = seg
        else:
            doy = pd.DatetimeIndex(d0[k] + np.arange(1, n_days + 1) * np.timedelta64(1, "D")).dayofyear
            ck = seas5.adjust_clim(clim, pd.Timestamp(d0[k]), anom) if anom is not None else clim
            W[k] = ck.loc[doy, DM].to_numpy(float)
    return W


def member_weather(base, anchors, year, n_days) -> dict:
    """{Y: (A, n_days, DM)}: for every earlier year Y, the weather that followed the
    anchor's day of year in Y. Only the past is used: the window ends on or before the
    anchor's own date. A window with any day outside the table stays NaN."""
    X = base[DM].to_numpy(float)
    pos = pd.Series(np.arange(len(base)), index=base["date"])
    out = {}
    for Y in range(int(base["date"].dt.year.min()), year):
        W = np.full((len(anchors), n_days, len(DM)), np.nan)
        for k, a in enumerate(anchors):
            p = pos.get(base["date"].iat[a] - pd.DateOffset(years=year - Y))
            if p is not None and p + n_days < len(X):
                assert p + n_days <= a, "a member window reached past the forecast start"
                W[k] = X[p + 1:p + 1 + n_days]
        out[Y] = W
    return out


def vol_targets(base, anchors, cutoff_pos):
    """(A, HMAX) volume change from the anchor to each later day; NaN where the
    level was not read or the day is at/after cutoff_pos (the test year)."""
    v = base["volume_Mm3"].to_numpy(float)
    Y = np.full((len(anchors), HMAX), np.nan)
    for k, a in enumerate(anchors):
        end = min(a + HMAX, cutoff_pos - 1, len(v) - 1)
        if end > a:
            Y[k, :end - a] = v[a + 1:end + 1] - v[a]
    return Y


def to_level(base, anchors, dvol_path, bathy):
    lvl0 = base["level_m"].to_numpy()[anchors][:, None]
    v0 = base["volume_Mm3"].to_numpy()[anchors][:, None]
    return lvl0 + np.polyval(bathy, v0 + dvol_path) - np.polyval(bathy, v0)


def train_anchors(base, year):
    yrs = base["date"].dt.year.to_numpy()
    cand = np.where((yrs < year) & base["level_m"].notna().to_numpy())[0]
    return cand[cand >= ENC_L - 1]


def fit_loop(net, batches_fn, n, seed, epochs=80, patience=10, lr=3e-3):
    """Generic masked-Huber training with a chronological last-15% validation split."""
    torch.manual_seed(seed); np.random.seed(seed)
    epochs = min(epochs, EPOCH_CAP) if EPOCH_CAP else epochs
    n_val = max(1, int(n * 0.15))
    tr_idx, va_idx = np.arange(n - n_val), np.arange(n - n_val, n)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    best, best_state, bad = np.inf, None, 0
    for _ in range(epochs):
        net.train()
        for j in np.array_split(np.random.permutation(tr_idx), max(1, len(tr_idx) // 128)):
            opt.zero_grad()
            loss = batches_fn(net, j)
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        net.eval()
        with torch.no_grad():
            v = float(batches_fn(net, va_idx))
        if v < best - 1e-4:
            best, bad = v, 0
            best_state = {k: t.clone() for k, t in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(best_state)
    return net


def masked_huber(pred, y, mask):
    l = nn.functional.huber_loss(pred, y, reduction="none", delta=1.0)
    return (l * mask).sum() / mask.sum().clamp(min=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Method B - direct from the last known day
# ─────────────────────────────────────────────────────────────────────────────

def window_summaries(W: np.ndarray) -> np.ndarray:
    """(A, n_days, DM) -> (A, 6 horizons x 7) totals and means of each horizon window."""
    si = [DM.index(c) for c in SUM_COLS]
    mi = [DM.index(c) for c in MEAN_COLS]
    n = len(si) + len(mi)
    cs = np.nancumsum(W, axis=1)
    out = []
    for H in HORIZONS:
        out.append(cs[:, H - 1, si])
        out.append(cs[:, H - 1, mi] / H)
    S = np.concatenate(out, axis=1)
    for i, H in enumerate(HORIZONS):                          # obs weather ran out
        S[np.isnan(W[:, :H]).any(axis=(1, 2)), i * n:(i + 1) * n] = np.nan
    return S


class DirectNet(nn.Module):
    def __init__(self, n_enc, n_sum, units=32):
        super().__init__()
        if CELL == "lstm":
            units = 64                                    # about the CfC cell's weight count
            self.enc = nn.LSTM(n_enc, units, batch_first=True)
        elif CELL == "gru":
            units = 75                                    # about the LSTM's weight count
            self.enc = nn.GRU(n_enc, units, batch_first=True)
        else:
            self.enc = CfC(n_enc, units, batch_first=True, return_sequences=False)
        self.head = nn.Sequential(nn.Linear(units + n_sum, 64), nn.GELU(), nn.Linear(64, len(HORIZONS)))

    def forward(self, x, s):
        if CELL == "lstm":
            _, (h, _) = self.enc(x)
            h = h[-1]
        elif CELL == "gru":
            _, h = self.enc(x)
            h = h[-1]
        else:
            h, _ = self.enc(x)
        return self.head(torch.cat([h, s], dim=1))


def run_B(base, year, anchors, seeds, occlude=(), ensemble=False):
    bathy = t08.fit_vol2level_poly()
    E = encoder_matrix(base)
    tr = train_anchors(base, year)
    yrs = base["date"].dt.year.to_numpy()
    cutoff = int(np.where(yrs == year)[0][0])
    sc_e = Scaler(E[yrs < year])
    Ze = sc_e(E)
    Wtr = future_weather(base, tr, "obs", None, HMAX)
    Str = window_summaries(Wtr)
    # training windows whose weather is complete (all are, inside the table)
    Ytr = vol_targets(base, tr, cutoff)[:, [h - 1 for h in HORIZONS]]
    keep = ~np.isnan(Ytr).all(axis=1)
    tr, Str, Ytr = tr[keep], Str[keep], Ytr[keep]
    sc_s = Scaler(Str)
    y_mu, y_sd = np.nanmean(Ytr, axis=0), np.nanstd(Ytr, axis=0) + 1e-8
    Xe = torch.tensor(windows(Ze, tr, ENC_L))
    Xs = torch.tensor(sc_s(Str))
    Yt = torch.tensor(np.nan_to_num((Ytr - y_mu) / y_sd), dtype=torch.float32)
    Mt = torch.tensor(~np.isnan(Ytr), dtype=torch.float32)
    loss = lambda net, j: masked_huber(net(Xe[j], Xs[j]), Yt[j], Mt[j])

    clim = climatology(base, yrs < year)
    Xa = torch.tensor(windows(Ze, anchors, ENC_L))
    S_raw = {w: window_summaries(future_weather(base, anchors, w, clim, HMAX))
             for w in ("obs", "clim") + (SEAS5_WEATHERS if SEAS5 is not None else ())}
    if ensemble:
        S_raw.update({f"ens|{Y}": window_summaries(W)
                      for Y, W in member_weather(base, anchors, year, HMAX).items()})
    S_test = {w: torch.tensor(sc_s(S)) for w, S in S_raw.items()}
    gone = {w: np.isnan(S[:, ::S.shape[1] // len(HORIZONS)])        # horizon windows with missing weather
            for w, S in S_raw.items()}
    preds = {(w, k): [] for k in (None, *occlude) for w in S_test}
    for s in range(seeds):
        net = fit_loop(DirectNet(Ze.shape[1], Xs.shape[1]), loss, len(tr), seed=s)
        net.eval()
        with torch.no_grad():
            for w, k in preds:
                preds[w, k].append(net(blanked(Xa, k), S_test[w]).numpy() * y_sd + y_mu)
    out = {}
    for (w, k), p in preds.items():
        dv = np.full((len(anchors), HMAX), np.nan)
        dv[:, [h - 1 for h in HORIZONS]] = np.where(gone[w], np.nan, np.mean(p, axis=0))
        out[tag(w, k)] = to_level(base, anchors, dv, bathy)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Method C - CfC state stepped through continuous time
# ─────────────────────────────────────────────────────────────────────────────

GRID = np.array(sorted(set(range(1, 15)) | set(range(14, HMAX + 1, 7)) | set(HORIZONS)))   # day offsets
SPANS = np.diff(np.concatenate([[0], GRID])).astype(np.float32)                      # days per step


def step_weather(W: np.ndarray) -> np.ndarray:
    """(A, HMAX, DM) daily -> (A, steps, DM + 1): mean weather over each step + its length."""
    out = np.empty((W.shape[0], len(GRID), len(DM) + 1), dtype=float)
    lo = 0
    for i, hi in enumerate(GRID):
        out[:, i, :len(DM)] = np.nanmean(W[:, lo:hi], axis=1)
        out[:, i, len(DM)] = hi - lo
        lo = hi
    return out


class OdeNet(nn.Module):
    def __init__(self, n_enc, n_dec, units=32):
        super().__init__()
        self.enc = CfC(n_enc, units, batch_first=True, return_sequences=False)
        self.dec = CfC(n_dec, units, batch_first=True, return_sequences=True)
        self.head = nn.Linear(units, 1)

    def forward(self, x, d, spans):
        _, h = self.enc(x)
        y, _ = self.dec(d, h, timespans=spans)
        return self.head(y).squeeze(-1)            # (A, steps): volume change since the anchor


def run_C(base, year, anchors, seeds, occlude=(), full=False):
    bathy = t08.fit_vol2level_poly()
    E = encoder_matrix(base)
    tr = train_anchors(base, year)
    tr = tr if full else tr[::2]                           # every other day keeps the night affordable
    yrs = base["date"].dt.year.to_numpy()
    cutoff = int(np.where(yrs == year)[0][0])
    sc_e = Scaler(E[yrs < year])
    Ze = sc_e(E)
    Dtr = step_weather(future_weather(base, tr, "obs", None, HMAX))
    Ytr = vol_targets(base, tr, cutoff)[:, GRID - 1]
    keep = ~np.isnan(Ytr).all(axis=1)
    tr, Dtr, Ytr = tr[keep], Dtr[keep], Ytr[keep]
    sc_d = Scaler(Dtr.reshape(-1, Dtr.shape[2]))
    y_sd = float(np.nanstd(Ytr)) + 1e-8
    Xe = torch.tensor(windows(Ze, tr, ENC_L))
    Xd = torch.tensor(sc_d(Dtr.reshape(-1, Dtr.shape[2])).reshape(Dtr.shape))
    Yt = torch.tensor(np.nan_to_num(Ytr / y_sd), dtype=torch.float32)
    Mt = torch.tensor(~np.isnan(Ytr), dtype=torch.float32)
    # every sample steps through the same grid; ncps squeezes timespans[:, t], so a
    # (1, steps) tensor gives one scalar span per step, shared across the batch
    spans = torch.tensor(SPANS)[None, :]
    loss = lambda net, j: masked_huber(net(Xe[j], Xd[j], spans), Yt[j], Mt[j])

    clim = climatology(base, yrs < year)
    Xa = torch.tensor(windows(Ze, anchors, ENC_L))
    D_test = {}
    for w in ("obs", "clim"):
        D = step_weather(future_weather(base, anchors, w, clim, HMAX))
        D_test[w] = torch.tensor(sc_d(D.reshape(-1, D.shape[2])).reshape(D.shape))
    preds = {(w, k): [] for k in (None, *occlude) for w in D_test}
    for s in range(seeds):
        net = fit_loop(OdeNet(Ze.shape[1], Xd.shape[2]), loss, len(tr), seed=s,
                       **({} if full else {"epochs": 60, "patience": 8}))
        net.eval()
        with torch.no_grad():
            for w, k in preds:
                preds[w, k].append(net(blanked(Xa, k), D_test[w], spans).numpy() * y_sd)
    out = {}
    for (w, k), p in preds.items():
        dv = np.full((len(anchors), HMAX), np.nan)
        dv[:, GRID - 1] = np.mean(p, axis=0)
        out[tag(w, k)] = to_level(base, anchors, dv, bathy)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Driver, checkpointing, summary
# ─────────────────────────────────────────────────────────────────────────────

def ckpt(name):
    return OUT / f"{name}.json"


def run_method(method, seeds, a_seq=14, occlude=(), c_full=False, ensemble=False):
    OUT.mkdir(parents=True, exist_ok=True)
    L.set_features(None if TABLE == "ims" else L.NO_INTENSITY)
    base, lagged = tables()
    if method == "G":
        label = "G"
    elif method in ("A", "A1"):                                       # A, A1 read 14 days
        label = method if a_seq == 14 else f"{method}_{a_seq}"
    else:
        label = (f"{method}{ENC_L}" + ("f" if c_full else "") + ("b" if "bucket_S" in EXTRA_ENC else "")
                 + {"all": "", "weather": "n", "state": "s"}[HISTORY] + (CELL if CELL != "cfc" else ""))
    label += "h" if NO_HUMIDITY else ""
    name = f"{label}_s{seeds}" + ("_occ" if occlude else "") + ("_ens" if ensemble else "")
    done = json.loads(ckpt(name).read_text(encoding="utf-8")) if ckpt(name).exists() else {}
    refs = json.loads(ckpt("references").read_text(encoding="utf-8")) if ckpt("references").exists() else {}
    for year in TEST_YEARS:
        anchors = anchors_for(base, year)
        if str(year) not in refs:
            refs[str(year)] = references(base, anchors, year, (base["date"].dt.year < year).to_numpy())
            ckpt("references").write_text(json.dumps(refs), encoding="utf-8")
        if str(year) in done:
            continue
        t0 = time.time()
        if method == "G":
            preds = run_A(base, lagged, year, anchors, seeds, kind="gbr")
        elif method in ("A", "A1"):
            preds = run_A(base, lagged, year, anchors, seeds, one_step=method == "A1", seq_len=a_seq)
        elif method == "B":
            preds = run_B(base, year, anchors, seeds, occlude, ensemble)
        else:
            preds = run_C(base, year, anchors, seeds, occlude, full=c_full)
        done[str(year)] = records(label, year, base, anchors, preds)
        ckpt(name).write_text(json.dumps(done), encoding="utf-8")
        e = pd.DataFrame(done[str(year)]).assign(err=lambda d: (d.pred - d.obs).abs())
        e = e[~e.weather.str.startswith("ens|")]
        print(f"  {label} {year}: {len(anchors)} starts, mean level MAE clim "
              f"{e[e.weather == 'clim'].groupby('H').err.mean().round(3).to_dict()}  "
              f"({time.time() - t0:.0f}s)", flush=True)


def load_all():
    rows = []
    for p in OUT.glob("*.json"):
        if p.name.startswith("summary"):
            continue
        for recs in json.loads(p.read_text(encoding="utf-8")).values():
            rows += recs
    d = pd.DataFrame(rows)
    d["key"] = d["method"] + "/" + d["weather"]
    d["err"] = d["pred"] - d["obs"]
    return d


def summary(only="", n_boot=2000):
    d = load_all()
    d = d[~d["weather"].str.startswith("ens|")]          # members are scored by the report
    if only:
        keep = set(only.split(",")) | {"persistence", "clim_change"}
        d = d[d["method"].isin(keep)]
    years = sorted(d["year"].unique())
    keys = sorted(d["key"].unique())
    # compare only forecasts every method made (same start, horizon)
    common = d.groupby(["start", "H"])["key"].nunique()
    common = common[common == len(keys)].index
    d = d.set_index(["start", "H"]).loc[common].reset_index()
    mae = d.groupby(["key", "H"])["err"].apply(lambda e: e.abs().mean()).unstack(0).round(3)
    bias = d.groupby(["key", "H"])["err"].mean().unstack(0).round(3)
    score = d[d.weather.isin(["clim", "-"])].groupby("key")["err"].apply(lambda e: e.abs().mean())
    per_year = d.groupby(["key", "year", "H"])["err"].apply(lambda e: e.abs().mean()).unstack(["key"])
    rng = np.random.default_rng(0)
    methods = [k for k in keys if k.endswith("/clim")]
    ci = {}
    for i, a in enumerate(methods):
        for b in methods[i + 1:]:
            diffs = []
            for _ in range(n_boot):
                ys = rng.choice(years, len(years))
                sub = pd.concat([per_year.xs(y, level="year") for y in ys])
                diffs.append(float((sub[a] - sub[b]).mean()))
            ci[f"{a} minus {b}"] = [round(float(np.percentile(diffs, q)), 3) for q in (5, 50, 95)]
    res = {"n_forecasts_compared": int(len(d)), "test_years": [int(y) for y in years],
           "mae_m": mae.to_dict(), "bias_m": bias.to_dict(),
           "mean_mae_over_horizons_clim": score.round(3).to_dict(),
           "winner_clim": score[[k for k in score.index if k.endswith("/clim")]].idxmin(),
           "bootstrap_mean_mae_diff_by_year_90pct": ci}
    print("\nLevel MAE (m), forecasts every method made:\n" + mae.to_string())
    print("\nMean over horizons (clim / references):\n" + score.round(3).to_string())
    print("\nWinner (clim):", res["winner_clim"])
    print("\nBootstrap over test years, mean MAE difference (5/50/95%):")
    for k, v in ci.items():
        print(f"  {k}: {v}")
    tag = "_".join(sorted({k.split("/")[0] for k in d["key"].unique() if k[0] in "ABC"}))
    (OUT / f"summary_{tag}.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["A", "A1", "B", "C", "G"])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--enc-len", type=int, default=None, help="history days (B/C default 60, A/A1 14)")
    ap.add_argument("--occlude", default="", help="B/C only: comma list of k, see the header")
    ap.add_argument("--c-full", action="store_true", help="C only: train like B, see the header")
    ap.add_argument("--table", choices=["era5", "ims"], default="era5")
    ap.add_argument("--bucket", action="store_true", help="history carries the soil bucket")
    ap.add_argument("--ensemble", action="store_true", help="B only: past-winters ensemble")
    hist = ap.add_mutually_exclusive_group()
    hist.add_argument("--no-state", action="store_true", help="B only: history without level/volume")
    hist.add_argument("--state-only", action="store_true", help="B only: history is level/volume only")
    ap.add_argument("--cell", choices=["cfc", "lstm", "gru"], default="cfc", help="B only: encoder cell")
    ap.add_argument("--table-from", default=None, help="drop table rows before this date")
    ap.add_argument("--seas5", action="store_true", help="add the SEAS5 seasonal-forecast weather")
    ap.add_argument("--no-humidity", action="store_true", help="drop humidity, VPD and ET0 inputs")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--only", default="", help="comma list of methods to include in --summary")
    a = ap.parse_args()
    global ENC_L, TABLE, TEST_YEARS, HISTORY, CELL, TABLE_FROM, SEAS5
    ENC_L = a.enc_len or 60
    TABLE = a.table
    if TABLE == "ims":
        EXTRA_ENC.append(L.NO_INTENSITY)
        if "CFC_YEARS" not in os.environ:
            TEST_YEARS = list(range(2021, 2026))
    if a.bucket:
        EXTRA_ENC.extend(["bucket_S", "bucket_Q30"])
    if (a.ensemble or a.no_state or a.state_only or a.cell != "cfc") and a.method != "B":
        ap.error("--ensemble, --no-state, --state-only and --cell need --method B")
    HISTORY = "weather" if a.no_state else "state" if a.state_only else "all"
    CELL = a.cell
    TABLE_FROM = a.table_from
    if a.no_humidity:
        drop_humidity()
    if a.seas5:
        if a.method == "C":
            ap.error("--seas5 is for A, A1, B and G")
        SEAS5 = seas5.load()
    occ = tuple(int(k) for k in a.occlude.split(",") if k)
    if occ and a.method not in ("B", "C"):
        ap.error("--occlude needs --method B or C")
    if a.summary:
        summary(a.only)
    else:
        run_method(a.method, a.seeds, a_seq=a.enc_len or 14, occlude=occ, c_full=a.c_full,
                   ensemble=a.ensemble)


if __name__ == "__main__":
    main()
