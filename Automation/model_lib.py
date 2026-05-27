"""
model_lib.py  -  Shared utilities for the Kinneret weekly forecast pipeline.

Contains:
  - RFRegressor : minimal numpy-only Random Forest (no scikit-learn required)
  - Met derivation helpers : VPD, ET0 (FAO-56), seasonality features
  - enrich_forecast_df() : derives all model features from raw forecast columns
  - Feature-list constants (single source of truth for training + inference)
"""
from __future__ import annotations

import pickle
import numpy as np
import pandas as pd
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Lake / site constants  (must match 07_build_gold_features.py exactly)
# ─────────────────────────────────────────────────────────────────────────────
LATITUDE  = 32.82      # °N, centre of Lake Kinneret
ELEVATION = -212.0     # m MSL (approx mean level, used for atm. pressure)

RBF_GAMMA   = -np.log(0.05) / 45 ** 2
RBF_CENTRES = {
    "spring_equinox":  80,   # ≈ Mar 21
    "summer_solstice": 172,  # ≈ Jun 21
    "autumn_equinox":  264,  # ≈ Sep 21
    "winter_solstice": 355,  # ≈ Dec 21
}


# ─────────────────────────────────────────────────────────────────────────────
# Feature lists  (single source of truth — training and inference must agree)
# ─────────────────────────────────────────────────────────────────────────────
S1_FEATURES = [
    # Rainfall: current day + 3-day lags + rolling windows (antecedent moisture)
    "rainfall_mm",
    "rainfall_lag1_mm",
    "rainfall_lag2_mm",
    "rainfall_lag3_mm",
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    # Moisture balance (rainfall - ET0): net catchment wetness proxy
    "moisture_balance_7d_mm",
    "moisture_balance_14d_mm",
    # Temperature / evaporation proxies
    "temp_mean_C",
    "temp_min_C",
    "humidity_pct",
    "vpd_kPa",
    "et0_mm",
    # Inflow lags (autocorr lag1=0.967, lag2=0.926 — strongest single predictor)
    "inflow_lag1_m3",
    "inflow_lag2_m3",
    # Seasonality
    "season_sin",
    "season_cos",
]
S1_TARGET = "inflow_obstacle_m3"

S2_FEATURES = [
    # Stage-1 output (predicted inflow replaces actual at inference time)
    "predicted_inflow_m3",
    # Met drivers of evaporation and direct lake-surface response
    "rainfall_mm",
    "rainfall_7d_mm",
    "rainfall_21d_mm",
    "temp_mean_C",
    "temp_max_C",
    "humidity_pct",
    "wind_speed_ms",
    "vpd_kPa",
    "et0_mm",
    "et0_7d_mm",
    "radiation_MJm2",
    # Seasonality
    "season_sin",
    "season_cos",
    "daylength_hrs",
    # Lake state (level + volume-change momentum)
    "level_m",
    "volume_change_lag1_Mm3",
    "volume_change_lag2_Mm3",
]
S2_TARGET = "volume_change_Mm3"


# ─────────────────────────────────────────────────────────────────────────────
# Direct multi-step Stage-2 feature sets
# ─────────────────────────────────────────────────────────────────────────────

# Met features come from the FORECAST day (t+h at inference time)
S2_MET_FEATURES = [
    "predicted_inflow_m3",
    "rainfall_mm", "rainfall_7d_mm", "rainfall_21d_mm",
    "temp_mean_C", "temp_max_C",
    "humidity_pct", "wind_speed_ms", "vpd_kPa", "et0_mm", "et0_7d_mm",
    "radiation_MJm2",
    "season_sin", "season_cos", "daylength_hrs",
]
# Anchor state comes from DAY 0 (before the forecast window — never updated).
# horizon_h tells the model how many days ahead it is predicting.
S2_DIRECT_FEATURES = S2_MET_FEATURES + [
    "level_m_anchor",       # actual level at anchor day
    "dvol_lag1_anchor",     # actual volume change at anchor day (lag1 for day 1)
    "horizon_h",            # 1 … 7 (which day of the forecast week)
]
S2_DIRECT_TARGET = "volume_change_Mm3"

# Direct multi-step Stage-1 feature set.
# Replaces chained inflow lags with a fixed anchor inflow at day 0.
S1_DIRECT_FEATURES = [
    "rainfall_mm",
    "rainfall_lag1_mm",
    "rainfall_lag2_mm",
    "rainfall_lag3_mm",
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    "moisture_balance_7d_mm",
    "moisture_balance_14d_mm",
    "temp_mean_C",
    "temp_min_C",
    "humidity_pct",
    "vpd_kPa",
    "et0_mm",
    "inflow_anchor_m3",   # actual inflow at anchor day (day 0); never chained
    "horizon_h",          # 1 … 7 (which forecast day)
    "season_sin",
    "season_cos",
]
# S1_DIRECT_TARGET is the same as S1_TARGET = "inflow_obstacle_m3"


# ─────────────────────────────────────────────────────────────────────────────
# Target transforms  (applied before fitting, inverted after predicting)
# ─────────────────────────────────────────────────────────────────────────────

def log_transform(y: np.ndarray) -> np.ndarray:
    """
    Log transform for strictly-positive targets (e.g. inflow, skew=2.22).
    Clips to 1.0 m³ minimum to avoid log(0).
    """
    return np.log(np.clip(np.asarray(y, dtype=float), 1.0, None))


def inv_log_transform(y: np.ndarray) -> np.ndarray:
    """Inverse of log_transform."""
    return np.exp(np.asarray(y, dtype=float))


def signed_log1p_transform(y: np.ndarray) -> np.ndarray:
    """
    Signed log1p transform for targets that can be negative
    (e.g. volume change, skew=4.82).

        f(x) = sign(x) * log1p(|x|)

    Compresses large positive flood events while preserving the sign
    of net-loss days.  Smooth and invertible everywhere.
    """
    y = np.asarray(y, dtype=float)
    return np.sign(y) * np.log1p(np.abs(y))


def inv_signed_log1p_transform(y: np.ndarray) -> np.ndarray:
    """Inverse of signed_log1p_transform."""
    y = np.asarray(y, dtype=float)
    return np.sign(y) * np.expm1(np.abs(y))


# ─────────────────────────────────────────────────────────────────────────────
# Random Forest  (pure numpy, no external ML dependencies)
# ─────────────────────────────────────────────────────────────────────────────

class _Node:
    """A single decision-tree node (internal split or leaf)."""
    __slots__ = ["feat", "thr", "left", "right", "val"]

    def __init__(self, val: float = 0.0):
        self.feat: int   = -1    # feature index; -1 = leaf
        self.thr:  float = 0.0
        self.left        = None
        self.right       = None
        self.val:  float = val   # leaf prediction


def _best_split(X: np.ndarray, y: np.ndarray,
                feats: np.ndarray, min_leaf: int):
    """
    Find the best (feature, threshold) split using a cumulative-sum trick
    so each feature is scored in O(n) time after an initial O(n log n) sort.

    Returns (best_feat, best_thr).  Returns (-1, 0.0) if no valid split.
    """
    n         = len(y)
    best_score = float(np.var(y) * n)   # baseline: no improvement
    best_feat, best_thr = -1, 0.0

    for f in feats:
        order = np.argsort(X[:, f], kind="mergesort")
        xs    = X[order, f]
        ys    = y[order]

        cs   = np.cumsum(ys)
        cs2  = np.cumsum(ys ** 2)
        n_l  = np.arange(1, n, dtype=float)
        n_r  = n - n_l

        # Valid splits: enough samples on each side, and a real value gap
        valid = (n_l >= min_leaf) & (n_r >= min_leaf) & (np.diff(xs) > 0)
        if not valid.any():
            continue

        s_l  = cs[:-1];    s_r  = cs[-1]  - s_l
        s2_l = cs2[:-1];   s2_r = cs2[-1] - s2_l

        # Weighted variance score (lower is better)
        score         = (s2_l - s_l ** 2 / n_l) + (s2_r - s_r ** 2 / n_r)
        score[~valid] = np.inf

        i = int(np.argmin(score))
        if score[i] < best_score:
            best_score = score[i]
            best_feat  = f
            best_thr   = float(xs[i])

    return best_feat, best_thr


def _build(X: np.ndarray, y: np.ndarray,
           depth: int, max_depth: int, min_leaf: int,
           n_feat: int, rng: np.random.Generator) -> _Node:
    """Recursively grow one regression tree."""
    node = _Node(val=float(y.mean()))
    if depth >= max_depth or len(y) < 2 * min_leaf:
        return node

    feats           = rng.choice(X.shape[1], size=min(n_feat, X.shape[1]), replace=False)
    feat, thr       = _best_split(X, y, feats, min_leaf)
    if feat == -1:
        return node

    mask = X[:, feat] <= thr
    if mask.all() or (~mask).all():
        return node

    node.feat, node.thr = feat, thr
    node.left  = _build(X[mask],  y[mask],  depth + 1, max_depth, min_leaf, n_feat, rng)
    node.right = _build(X[~mask], y[~mask], depth + 1, max_depth, min_leaf, n_feat, rng)
    return node


def _predict_tree(node: _Node, X: np.ndarray) -> np.ndarray:
    """
    Predict all rows in X using a single tree.
    Uses an iterative partition approach — groups of row indices flow left/right
    at each node rather than processing rows one at a time.
    """
    pred  = np.empty(len(X))
    stack = [(node, np.arange(len(X)))]
    while stack:
        nd, idx = stack.pop()
        if not len(idx):
            continue
        if nd.feat == -1:
            pred[idx] = nd.val
        else:
            go = X[idx, nd.feat] <= nd.thr
            stack.append((nd.left,  idx[go]))
            stack.append((nd.right, idx[~go]))
    return pred


class RFRegressor:
    """
    Minimal numpy-only Random Forest regressor.

    API mirrors sklearn so it can be swapped with GradientBoostingRegressor
    later if scikit-learn becomes available.

    Parameters
    ----------
    n_estimators : number of trees
    max_depth    : maximum depth per tree
    min_leaf     : minimum samples per leaf
    max_features : int | 'sqrt' | 'third'
    subsample    : row bagging fraction per tree
    random_state : reproducibility seed
    """

    def __init__(self,
                 n_estimators: int    = 150,
                 max_depth:    int    = 6,
                 min_leaf:     int    = 8,
                 max_features: object = "sqrt",
                 subsample:    float  = 0.8,
                 random_state: int    = 42):
        self.n_estimators = n_estimators
        self.max_depth    = max_depth
        self.min_leaf     = min_leaf
        self.max_features = max_features
        self.subsample    = subsample
        self.random_state = random_state
        self.trees_:         list             = []
        self.median_:        np.ndarray | None = None   # for NaN imputation
        self.feature_names_: list | None      = None

    # ------------------------------------------------------------------
    def _n_feat(self, nc: int) -> int:
        if self.max_features == "sqrt":  return max(1, int(nc ** 0.5))
        if self.max_features == "third": return max(1, nc // 3)
        return max(1, int(self.max_features))

    def _impute(self, X: np.ndarray) -> np.ndarray:
        X = X.copy()
        for j in range(X.shape[1]):
            nans = np.isnan(X[:, j])
            if nans.any():
                X[nans, j] = self.median_[j]
        return X

    # ------------------------------------------------------------------
    def fit(self, X, y, feature_names=None):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.median_        = np.nanmedian(X, axis=0)
        self.feature_names_ = feature_names
        X   = self._impute(X)
        rng = np.random.default_rng(self.random_state)
        nf  = self._n_feat(X.shape[1])
        nr  = max(1, int(len(y) * self.subsample))
        self.trees_ = []
        for i in range(self.n_estimators):
            idx = rng.choice(len(y), size=nr, replace=True)
            self.trees_.append(
                _build(X[idx], y[idx], 0, self.max_depth, self.min_leaf, nf, rng)
            )
            if (i + 1) % 50 == 0:
                print(f"    [{i+1}/{self.n_estimators} trees grown]", flush=True)
        return self

    def predict(self, X) -> np.ndarray:
        X = self._impute(np.asarray(X, dtype=float))
        return np.stack([_predict_tree(t, X) for t in self.trees_]).mean(axis=0)

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=4)

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return pickle.load(f)




# ─────────────────────────────────────────────────────────────────────────────
# Gradient Boosting Regressor  (pure numpy — equivalent to sklearn GBR)
# ─────────────────────────────────────────────────────────────────────────────

class GBRegressor:
    """
    Minimal numpy-only Gradient Boosting Regressor.

    Sequentially fits shallow regression trees to the negative gradient
    (residuals) of MSE loss.  Equivalent to sklearn GradientBoostingRegressor
    with loss='squared_error'.

    Parameters
    ----------
    n_estimators  : number of boosting rounds
    max_depth     : tree depth (keep shallow: 3-5 works best for GB)
    min_leaf      : minimum samples per leaf
    learning_rate : shrinkage factor applied to each tree
    subsample     : row subsampling fraction per round (stochastic GB)
    random_state  : reproducibility seed
    """

    def __init__(self,
                 n_estimators: int   = 400,
                 max_depth:    int   = 4,
                 min_leaf:     int   = 10,
                 learning_rate: float = 0.05,
                 subsample:    float  = 0.8,
                 random_state: int   = 42):
        self.n_estimators  = n_estimators
        self.max_depth     = max_depth
        self.min_leaf      = min_leaf
        self.learning_rate = learning_rate
        self.subsample     = subsample
        self.random_state  = random_state
        self.trees_:          list             = []
        self.init_pred_:      float            = 0.0
        self.median_:         np.ndarray | None = None
        self.feature_names_:  list | None      = None

    def _impute(self, X: np.ndarray) -> np.ndarray:
        X = X.copy()
        for j in range(X.shape[1]):
            nans = np.isnan(X[:, j])
            if nans.any():
                X[nans, j] = self.median_[j]
        return X

    def fit(self, X, y, feature_names=None):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.median_        = np.nanmedian(X, axis=0)
        self.feature_names_ = feature_names
        X   = self._impute(X)

        rng    = np.random.default_rng(self.random_state)
        n_feat = max(1, int(X.shape[1] ** 0.5))
        nr     = max(1, int(len(y) * self.subsample))

        # Initialise with the mean (constant model)
        self.init_pred_ = float(y.mean())
        y_hat = np.full(len(y), self.init_pred_)

        self.trees_ = []
        for i in range(self.n_estimators):
            residuals = y - y_hat                       # negative MSE gradient
            idx  = rng.choice(len(y), size=nr, replace=False)
            tree = _build(X[idx], residuals[idx],
                          0, self.max_depth, self.min_leaf, n_feat, rng)
            update  = _predict_tree(tree, X)
            y_hat  += self.learning_rate * update
            self.trees_.append(tree)
            if (i + 1) % 100 == 0:
                print(f"    [{i+1}/{self.n_estimators} rounds]", flush=True)
        return self

    def predict(self, X) -> np.ndarray:
        X     = self._impute(np.asarray(X, dtype=float))
        y_hat = np.full(len(X), self.init_pred_)
        for tree in self.trees_:
            y_hat += self.learning_rate * _predict_tree(tree, X)
        return y_hat

    def save(self, path):
        import pickle
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=4)

    @classmethod
    def load(cls, path):
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

# ─────────────────────────────────────────────────────────────────────────────
# Met derivation helpers  (FAO-56 formulas, identical to 07_build_gold_features)
# ─────────────────────────────────────────────────────────────────────────────

def saturation_vapor_pressure(T):
    """es in kPa for T in °C  (FAO-56 eq. 11)."""
    return 0.6108 * np.exp(17.27 * T / (T + 237.3))


def compute_vpd(temp_mean_C, humidity_pct):
    """Vapor pressure deficit in kPa."""
    T  = np.asarray(temp_mean_C, dtype=float)
    RH = np.asarray(humidity_pct, dtype=float)
    es = saturation_vapor_pressure(T)
    ea = es * RH / 100.0
    return np.clip(es - ea, 0, None)


def compute_et0(temp_mean_C, temp_max_C, temp_min_C,
                humidity_pct, wind_speed_ms, radiation_MJm2, doy):
    """
    FAO-56 Penman-Monteith ET0 (mm/day).
    radiation_MJm2 may be NaN — ET0 will be NaN for those rows.
    """
    T   = np.asarray(temp_mean_C,   dtype=float)
    Tx  = np.asarray(temp_max_C,    dtype=float)
    Tn  = np.asarray(temp_min_C,    dtype=float)
    RH  = np.asarray(humidity_pct,  dtype=float)
    u10 = np.asarray(wind_speed_ms, dtype=float)
    Rs  = np.asarray(radiation_MJm2, dtype=float)
    J   = np.asarray(doy,            dtype=float)
    lat = np.radians(LATITUDE)

    # Wind at 2 m  (FAO-56 eq. 47, measured at 10 m)
    u2    = u10 * (4.87 / np.log(67.8 * 10 - 5.42))
    # Atmospheric pressure and psychrometric constant
    P     = 101.3 * ((293 - 0.0065 * ELEVATION) / 293) ** 5.26
    gamma = 0.000665 * P
    # Vapour pressures
    es    = (saturation_vapor_pressure(Tx) + saturation_vapor_pressure(Tn)) / 2.0
    ea    = saturation_vapor_pressure(T) * RH / 100.0
    # Slope of saturation vapour pressure curve
    delta = 4098.0 * saturation_vapor_pressure(T) / (T + 237.3) ** 2

    # Extraterrestrial radiation Ra
    dr    = 1 + 0.033 * np.cos(2 * np.pi / 365 * J)
    decl  = 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)
    oms   = np.arccos(np.clip(-np.tan(lat) * np.tan(decl), -1, 1))
    Ra    = (24 * 60 / np.pi) * 0.0820 * dr * (
                oms * np.sin(lat) * np.sin(decl)
                + np.cos(lat) * np.cos(decl) * np.sin(oms))

    # Net radiation
    Rso  = (0.75 + 2e-5 * ELEVATION) * Ra
    Rns  = np.where(np.isnan(Rs), np.nan, 0.77 * Rs)
    rsr  = np.where(Rso > 0, np.clip(Rs / Rso, 0.3, 1.0), np.nan)
    sig  = 4.903e-9
    Rnl  = sig * ((Tx + 273.16) ** 4 + (Tn + 273.16) ** 4) / 2 \
               * (0.34 - 0.14 * np.sqrt(np.clip(ea, 0, None))) \
               * (1.35 * rsr - 0.35)
    Rn   = np.where(np.isnan(Rns), np.nan, Rns - Rnl)

    # PM equation  (soil heat flux G = 0 for daily step)
    num   = 0.408 * delta * Rn + gamma * (900.0 / (T + 273)) * u2 * (es - ea)
    denom = delta + gamma * (1 + 0.34 * u2)
    et0   = np.where(denom == 0, np.nan, num / denom)
    return np.where(et0 < 0, 0.0, et0)


def add_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add season_sin/cos, solar_declination_rad, daylength_hrs, and four
    RBF columns to *df* (which must have a 'doy' column).
    Returns a copy.
    """
    df  = df.copy()
    J   = df["doy"].values.astype(float)
    lat = np.radians(LATITUDE)

    df["season_sin"]           = np.sin(2 * np.pi * J / 365.25)
    df["season_cos"]           = np.cos(2 * np.pi * J / 365.25)
    decl                       = 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)
    df["solar_declination_rad"] = decl
    oms                        = np.arccos(np.clip(-np.tan(lat) * np.tan(decl), -1, 1))
    df["daylength_hrs"]        = (24 / np.pi) * oms

    for name, centre in RBF_CENTRES.items():
        dist          = np.abs(J - centre)
        dist          = np.minimum(dist, 365 - dist)
        df["rbf_" + name] = np.exp(-RBF_GAMMA * dist ** 2)

    return df


def enrich_forecast_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive all meteorological model features from raw forecast columns.

    Required input columns:
        date, temp_max_C, temp_min_C, rainfall_mm, humidity_pct, wind_speed_ms
    Optional:
        radiation_MJm2  (ET0 will be NaN if absent; model imputes with median)

    Returns enriched copy with temp_mean_C, doy, vpd_kPa, et0_mm, and
    all seasonality columns added.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["temp_mean_C"] = (df["temp_max_C"] + df["temp_min_C"]) / 2.0
    df["doy"]         = df["date"].dt.dayofyear
    df["vpd_kPa"]     = compute_vpd(df["temp_mean_C"], df["humidity_pct"])

    rad = df["radiation_MJm2"] if "radiation_MJm2" in df.columns else pd.Series(np.nan, index=df.index)
    df["et0_mm"] = compute_et0(
        df["temp_mean_C"], df["temp_max_C"], df["temp_min_C"],
        df["humidity_pct"], df["wind_speed_ms"], rad, df["doy"],
    )
    df = add_seasonality(df)
    return df
