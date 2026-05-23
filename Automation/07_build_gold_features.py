# -*- coding: utf-8 -*-
"""
07_build_gold_features.py  -  Gold Feature Engineering

Merges all silver data sources and engineers model-ready features.
Date range: 2012-09-01 onwards (earliest date with good multi-source coverage).

Feature groups
--------------
  A. Seasonality
       sin/cos day-of-year encoding, solar declination, daylength,
       radial basis functions around the four seasonal pivot days.

  B. Met / Weather  (lev_kinneret station priority; multi-station mean fallback)
       Temperature, humidity, wind speed, radiation (tzamach only).
       Vapor pressure deficit (VPD), Penman-Monteith ET0.
       Precipitation rolling sums (7d, 14d infiltration proxy).
       Peak 1-hour rainfall intensity from 10-minute wide table.

  C. Kinneret level & volume
       Level, volume (polynomial fit to bathymetric curve), level daily
       change, volume daily/2-day/3-day change.

  D. River flows
       OBSTACLE BRIDGE (main inflow) and BAPTISM SITE (outflow).
       Net inflow, 1-day and 2-day lags, 7-day moving average.

Inputs
------
  Silver Data/Meteorological/met_data_daily_clean.csv
  Silver Data/Meteorological/met_data_wide.csv        (10-min, rain cols only)
  Silver Data/Jordan River Silver/jordan_river_daily_flow_clean.csv
  Silver Data/Kinneret Level/kinneret_level.csv
  Raw Data/Kinneret_Level/Lake Kinneret Bathymetric and Hypsometric Curve.csv

Output
------
  Gold Data/kinneret_gold_features.csv

Usage
-----
    python Automation/07_build_gold_features.py
"""

import pathlib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = pathlib.Path(__file__).resolve().parent.parent
SILVER_MET  = BASE_DIR / "Silver Data" / "Meteorological"
SILVER_FLOW = BASE_DIR / "Silver Data" / "Jordan River Silver"
SILVER_LAKE = BASE_DIR / "Silver Data" / "Kinneret Level"
RAW_BATHY   = BASE_DIR / "Raw Data" / "Kinneret_Level" / "Lake Kinneret Bathymetric and Hypsometric Curve.csv"
GOLD_DIR    = BASE_DIR / "Gold Data"
OUT_FILE    = GOLD_DIR / "kinneret_gold_features.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
START_DATE  = "2012-09-01"
LATITUDE    = 32.82                  # degrees N, centre of Lake Kinneret
ELEVATION   = -212.0                 # m (approximate mean lake level for atm. pressure)
KINNERET_STATIONS = [
    "beit_tzaida", "kfar_nachum", "lev_kinneret", "tiberias", "tzamach"
]
PRIORITY_STATION  = "lev_kinneret"
RADIATION_STATION = "tzamach"        # only station with solar radiation sensor

# RBF gamma: decays to ~0.05 at 45 days from centre (captures ~3-month season)
RBF_GAMMA   = -np.log(0.05) / 45**2
RBF_CENTRES = {                       # approximate day-of-year for each pivot
    "spring_equinox": 80,             # Mar 21
    "summer_solstice": 172,           # Jun 21
    "autumn_equinox":  264,           # Sep 21
    "winter_solstice": 355,           # Dec 21
}


# ===========================================================================
# A.  Seasonality
# ===========================================================================

def add_seasonality(df):
    """Add sin/cos encoding, declination, daylength, and RBF columns."""
    lat_rad = np.radians(LATITUDE)
    J = df["doy"].values.astype(float)

    # --- Sin / Cos encoding ---
    df["season_sin"] = np.sin(2 * np.pi * J / 365.25)
    df["season_cos"] = np.cos(2 * np.pi * J / 365.25)

    # --- Solar declination (radians) and daylength ---
    # FAO-56: delta = 0.409 * sin(2*pi/365 * J - 1.39)
    decl = 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)
    df["solar_declination_rad"] = decl

    # Sunset hour angle
    cos_ws = -np.tan(lat_rad) * np.tan(decl)
    cos_ws = np.clip(cos_ws, -1, 1)           # clamp for polar edge cases
    omega_s = np.arccos(cos_ws)
    df["daylength_hrs"] = (24 / np.pi) * omega_s

    # --- Radial Basis Functions ---
    for name, centre in RBF_CENTRES.items():
        # Wrap distance so Dec 21 <-> Jan 1 are treated as close
        dist = np.abs(J - centre)
        dist = np.minimum(dist, 365 - dist)
        df["rbf_" + name] = np.exp(-RBF_GAMMA * dist**2)

    return df


# ===========================================================================
# B.  Met / Weather
# ===========================================================================

def consensus_col(met, param_suffix):
    """
    Return a Series for param_suffix:
      - Use PRIORITY_STATION column if available and non-NaN
      - Fill remaining NaNs with the mean of all other stations
    """
    priority_col = PRIORITY_STATION + "_" + param_suffix
    other_cols = [
        s + "_" + param_suffix for s in KINNERET_STATIONS
        if s != PRIORITY_STATION and s + "_" + param_suffix in met.columns
    ]
    if priority_col in met.columns:
        result = met[priority_col].copy()
    else:
        result = pd.Series(np.nan, index=met.index)

    if other_cols:
        fallback = met[other_cols].mean(axis=1)
        result = result.where(result.notna(), fallback)

    return result


def saturation_vapor_pressure(T):
    """es in kPa for temperature T in Celsius (FAO-56 eq. 11)."""
    return 0.6108 * np.exp(17.27 * T / (T + 237.3))


def add_met_features(df, met):
    """Merge consensus met columns and compute VPD and ET0."""
    # --- Core met parameters ---
    df["temp_mean_C"]    = consensus_col(met, "temperature_C_mean").values
    df["temp_max_C"]     = consensus_col(met, "temperature_C_max").values
    df["temp_min_C"]     = consensus_col(met, "temperature_C_min").values
    df["humidity_pct"]   = consensus_col(met, "relative_humidity_pct_mean").values
    df["wind_speed_ms"]  = consensus_col(met, "wind_speed_ms_mean").values
    df["rainfall_mm"]    = consensus_col(met, "rainfall_mm_sum").values

    # Radiation: tzamach only (no fallback — other stations lack sensors)
    rad_col = RADIATION_STATION + "_global_radiation_MJm2"
    df["radiation_MJm2"] = met[rad_col].values if rad_col in met.columns else np.nan

    # --- VPD ---
    es = saturation_vapor_pressure(df["temp_mean_C"])
    ea = es * df["humidity_pct"] / 100.0
    df["vpd_kPa"] = (es - ea).clip(lower=0)

    # --- ET0  (FAO-56 Penman-Monteith) ---
    df = _add_et0(df, ea)

    # --- Infiltration proxy: rolling rainfall sums ---
    df["rainfall_7d_mm"]  = df["rainfall_mm"].rolling(7,  min_periods=1).sum()
    df["rainfall_14d_mm"] = df["rainfall_mm"].rolling(14, min_periods=1).sum()
    df["rainfall_21d_mm"] = df["rainfall_mm"].rolling(21, min_periods=1).sum()

    # --- Rolling ET0 (cumulative lake evaporation proxy) ---
    df["et0_7d_mm"]  = df["et0_mm"].rolling(7,  min_periods=3).sum()
    df["et0_14d_mm"] = df["et0_mm"].rolling(14, min_periods=5).sum()

    # --- Moisture balance (rainfall - ET0): net catchment wetness ---
    df["moisture_balance_7d_mm"]  = df["rainfall_7d_mm"]  - df["et0_7d_mm"]
    df["moisture_balance_14d_mm"] = df["rainfall_14d_mm"] - df["et0_14d_mm"]

    return df, ea


def _add_et0(df, ea):
    """
    FAO-56 Penman-Monteith ET0 (mm/day).

    Uses:  T_mean, T_max, T_min, RH, wind at measurement height,
           global radiation (tzamach), latitude and elevation constants.
    Wind is assumed measured at 10 m and converted to 2 m reference height.
    """
    T    = df["temp_mean_C"].values
    Tmax = df["temp_max_C"].values
    Tmin = df["temp_min_C"].values
    RH   = df["humidity_pct"].values
    u10  = df["wind_speed_ms"].values
    Rs   = df["radiation_MJm2"].values      # MJ/m2/day
    J    = df["doy"].values.astype(float)
    lat  = np.radians(LATITUDE)

    # Wind speed at 2 m (FAO-56 eq. 47)
    u2 = u10 * (4.87 / np.log(67.8 * 10 - 5.42))

    # Atmospheric pressure at elevation (kPa)
    P = 101.3 * ((293 - 0.0065 * ELEVATION) / 293) ** 5.26

    # Psychrometric constant
    gamma = 0.000665 * P

    # Saturation vapour pressure from Tmax and Tmin (FAO-56 eq. 12)
    es = (saturation_vapor_pressure(Tmax) + saturation_vapor_pressure(Tmin)) / 2.0
    # ea already passed in
    ea_arr = ea.values

    # Slope of saturation vapour pressure curve
    delta = 4098.0 * saturation_vapor_pressure(T) / (T + 237.3) ** 2

    # --- Net radiation ---
    # Inverse relative Earth-Sun distance
    dr = 1 + 0.033 * np.cos(2 * np.pi / 365 * J)
    # Solar declination
    decl = 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)
    # Sunset hour angle
    cos_ws = np.clip(-np.tan(lat) * np.tan(decl), -1, 1)
    omega_s = np.arccos(cos_ws)

    # Extraterrestrial radiation Ra (MJ/m2/day), FAO-56 eq. 21
    Gsc = 0.0820
    Ra = (24 * 60 / np.pi) * Gsc * dr * (
        omega_s * np.sin(lat) * np.sin(decl)
        + np.cos(lat) * np.cos(decl) * np.sin(omega_s)
    )

    # Clear-sky radiation Rso
    Rso = (0.75 + 2e-5 * ELEVATION) * Ra

    # Net shortwave: Rns = (1 - albedo) * Rs
    Rns = 0.77 * np.where(np.isnan(Rs), np.nan, Rs)

    # Net longwave: Rnl (FAO-56 eq. 39)
    sigma = 4.903e-9   # MJ/K4/m2/day
    Tmax_K = Tmax + 273.16
    Tmin_K = Tmin + 273.16
    rs_rso = np.where(Rso > 0, np.clip(Rs / Rso, 0.3, 1.0), np.nan)
    Rnl = sigma * ((Tmax_K**4 + Tmin_K**4) / 2) * (
        0.34 - 0.14 * np.sqrt(np.clip(ea_arr, 0, None))
    ) * (1.35 * rs_rso - 0.35)

    Rn = np.where(np.isnan(Rns), np.nan, Rns - Rnl)

    # PM equation (G=0 for daily)
    num   = 0.408 * delta * Rn + gamma * (900 / (T + 273)) * u2 * (es - ea_arr)
    denom = delta + gamma * (1 + 0.34 * u2)
    et0   = num / denom

    et0_clean = np.where(denom == 0, np.nan, et0)
    df["et0_mm"] = np.where(et0_clean < 0, 0.0, et0_clean)
    return df


def add_precip_intensity(df, cache_path):
    """
    Merge pre-computed peak 1-hour rainfall intensity (mm/hr).
    Cache file is generated by running this script's companion step, or by
    loading met_data_wide.csv directly (see inline note in main).
    """
    pi = pd.read_csv(cache_path)
    pi_map = pi.set_index("date")["precip_intensity_mm_hr"]
    df["precip_intensity_mm_hr"] = df["date"].map(pi_map)
    return df


# ===========================================================================
# C.  Kinneret level & volume
# ===========================================================================

def build_volume_poly(bathy_path):
    """
    Fit a degree-2 polynomial: volume (Mm3) = f(water_level_m_MSL).
    Returns numpy poly1d object.
    """
    raw = pd.read_csv(bathy_path, encoding="utf-8-sig")
    # The CSV has two volume columns; detect which one holds numeric Mm3 values
    # (the other holds percentages like "100%").  In some file exports the
    # columns are labelled correctly; in others they are swapped.
    def _to_numeric_vol(series):
        return pd.to_numeric(
            series.astype(str).str.replace("%", "").str.replace(",", "").str.strip(),
            errors="coerce",
        )

    vol_mm3  = _to_numeric_vol(raw["Volume (Mm3)"])
    vol_pct  = _to_numeric_vol(raw["Volume (%)"])
    # Choose whichever column has larger values (Mm3 >> percentage)
    raw["vol"] = vol_mm3 if vol_mm3.max() > vol_pct.max() else vol_pct
    coeffs = np.polyfit(raw["Water Level (m MSL)"], raw["vol"], 2)
    poly   = np.poly1d(coeffs)

    # Diagnostics
    fitted = poly(raw["Water Level (m MSL)"])
    ss_res = np.sum((raw["vol"] - fitted) ** 2)
    ss_tot = np.sum((raw["vol"] - raw["vol"].mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    print("  Bathymetric polynomial (deg-2)  R2 = %.5f" % r2)
    print("  Coefficients: " + str(coeffs))
    return poly


def add_level_features(df, level_df, vol_poly):
    """Merge level, compute volume and change features."""
    level_map = level_df.set_index("date")["kinneret_level"]
    df["level_m"]  = df["date"].map(level_map)
    df["volume_Mm3"] = vol_poly(df["level_m"])

    df["level_change_m"]       = df["level_m"].diff(1)
    df["volume_change_Mm3"]    = df["volume_Mm3"].diff(1)
    df["volume_change_2d_Mm3"] = df["volume_Mm3"].diff(2)
    df["volume_change_3d_Mm3"] = df["volume_Mm3"].diff(3)

    # Lags of volume change (momentum / autocorrelation signal)
    df["volume_change_lag1_Mm3"] = df["volume_change_Mm3"].shift(1)
    df["volume_change_lag2_Mm3"] = df["volume_change_Mm3"].shift(2)

    return df


# ===========================================================================
# D.  River flows
# ===========================================================================

OBSTACLE = "JORDAN - OBSTACLE BRIDGE"
BAPTISM  = "JORDAN - BAPTISM SITE"

def add_flow_features(df, flow_df):
    """Merge river flow features for the two relevant stations."""
    flow_df = flow_df.copy()
    flow_df["date"] = pd.to_datetime(flow_df["Date"]).dt.strftime("%Y-%m-%d")
    flow_map_obs = flow_df.set_index("date")[OBSTACLE]
    flow_map_bap = flow_df.set_index("date")[BAPTISM]

    df["inflow_obstacle_m3"]  = df["date"].map(flow_map_obs)
    df["outflow_baptism_m3"]  = df["date"].map(flow_map_bap)

    # Net inflow: upstream inflow minus downstream outflow
    df["net_inflow_m3"] = df["inflow_obstacle_m3"] - df["outflow_baptism_m3"]

    # Inflow lags (highly autocorrelated — strong predictor for Stage 1)
    df["inflow_lag1_m3"] = df["inflow_obstacle_m3"].shift(1)
    df["inflow_lag2_m3"] = df["inflow_obstacle_m3"].shift(2)

    # Lags (1 day = 24 hr, 2 days = 48 hr)
    df["net_inflow_lag1_m3"] = df["net_inflow_m3"].shift(1)
    df["net_inflow_lag2_m3"] = df["net_inflow_m3"].shift(2)

    # 7-day moving average (centred on current day, trailing to avoid leakage)
    df["net_inflow_7d_ma_m3"] = (
        df["net_inflow_m3"].rolling(7, min_periods=1).mean()
    )

    return df


# ===========================================================================
# Main
# ===========================================================================

def main():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load silver files ---
    print("Loading silver files ...")
    met   = pd.read_csv(SILVER_MET / "met_data_daily_clean.csv", encoding="utf-8-sig")
    flow  = pd.read_csv(SILVER_FLOW / "jordan_river_daily_flow_clean.csv")
    level = pd.read_csv(SILVER_LAKE / "kinneret_level.csv")
    met["date"]   = met["date"].astype(str)
    level["date"] = level["date"].astype(str)

    # Reindex met to the gold spine for vectorised ops
    met = met.sort_values("date").reset_index(drop=True)

    # --- Build date spine ---
    all_dates = pd.date_range(start=START_DATE, end=pd.Timestamp.today().normalize(), freq="D")
    df = pd.DataFrame({"date": all_dates.strftime("%Y-%m-%d")})
    df["doy"] = all_dates.day_of_year
    print("  Date spine: %s to %s  (%d days)" % (df["date"].iloc[0], df["date"].iloc[-1], len(df)))

    # Align met to spine
    met_aligned = df[["date"]].merge(met, on="date", how="left")

    # --- A. Seasonality ---
    print("Adding seasonality features ...")
    df = add_seasonality(df)

    # --- B. Met features ---
    print("Adding met / weather features ...")
    df, ea = add_met_features(df, met_aligned)

    print("Adding precipitation intensity ...")
    cache_path = SILVER_MET / "precip_intensity_daily.csv"
    if cache_path.exists():
        df = add_precip_intensity(df, cache_path)
    else:
        print("  SKIPPED (precip_intensity_daily.csv not found)")
        print("  Run: python Automation/07b_precalc_precip_intensity.py to generate it.")
        df["precip_intensity_mm_hr"] = np.nan

    # --- C. Level & volume ---
    print("Fitting bathymetric polynomial and adding level/volume features ...")
    vol_poly = build_volume_poly(RAW_BATHY)
    df = add_level_features(df, level, vol_poly)

    # --- D. River flows ---
    print("Adding river flow features ...")
    df = add_flow_features(df, flow)

    # --- Tidy: drop doy helper ---
    df = df.drop(columns=["doy"])

    # --- Column order: output targets on the far right ---
    output_cols = [
        "level_m", "volume_Mm3",
        "level_change_m",
        "volume_change_Mm3", "volume_change_2d_Mm3", "volume_change_3d_Mm3",
    ]
    other_cols = [c for c in df.columns if c not in output_cols]
    df = df[other_cols + output_cols]

    # --- Save ---
    print("Saving gold table ...")
    df.to_csv(OUT_FILE, index=False, encoding="utf-8")

    # --- Summary ---
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    fill_rates   = df[numeric_cols].notna().mean().sort_values(ascending=False)

    print("")
    print("-" * 60)
    print("Output : " + str(OUT_FILE))
    print("Shape  : %d rows x %d cols" % df.shape)
    print("Range  : %s  to  %s" % (df["date"].iloc[0], df["date"].iloc[-1]))
    print("")
    print("Feature fill rates (top / bottom):")
    for col, rate in fill_rates.head(8).items():
        print("  %-40s  %.1f%%" % (col, rate * 100))
    print("  ...")
    for col, rate in fill_rates.tail(5).items():
        print("  %-40s  %.1f%%" % (col, rate * 100))
    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
