"""
app_utils.py - Shared utilities for the Kinneret dashboard.

Imported by every page. Provides:
  - PROJECT_ROOT  : absolute path to the project root
  - load_gold()   : cached gold feature DataFrame
  - load_models() : cached (gb1, gb2_direct, meta) tuple
  - run_forecast_from_df() : thin forecast wrapper
  - vol_to_level() : bathymetric polynomial
  - Constants: LEVEL_MIN/MAX, LEVEL_LEGAL_MIN/MAX, COLOURS
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTOMATION   = PROJECT_ROOT / "Automation"
GOLD_FILE    = PROJECT_ROOT / "Gold Data" / "kinneret_gold_features.csv"
MODELS_DIR   = PROJECT_ROOT / "Models"

# Ensure Automation/ is importable (for model_lib)
if str(AUTOMATION) not in sys.path:
    sys.path.insert(0, str(AUTOMATION))

from model_lib import GBRegressor  # noqa: E402

# Level constants
LEVEL_MIN        = -214.87   # historical all-time low (2001)
LEVEL_MAX        = -208.89   # historical all-time high
LEVEL_LEGAL_MIN  = -213.00   # lower management line
LEVEL_LEGAL_MAX  = -208.90   # upper spill line

# Chart colour palette
COLOURS = {
    "predicted": "#1E90FF",
    "actual":    "#FF7043",
    "winter":    "#4FC3F7",
    "summer":    "#EF5350",
    "rising":    "#66BB6A",
    "falling":   "#EF5350",
    "stable":    "#BDBDBD",
    "legal_min": "#EF5350",
    "legal_max": "#66BB6A",
    "band":      "rgba(30, 144, 255, 0.15)",
}


# Data loaders

@st.cache_data
def load_gold() -> pd.DataFrame:
    """Load kinneret_gold_features.csv once per session."""
    df = pd.read_csv(GOLD_FILE, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_resource
def load_models():
    """Load trained models and metadata once at startup."""
    gb1        = GBRegressor.load(MODELS_DIR / "stage1_inflow_rf.pkl")
    gb2_direct = GBRegressor.load(MODELS_DIR / "stage2_direct_gb.pkl")
    with open(MODELS_DIR / "model_metadata.json", encoding="utf-8") as f:
        meta = json.load(f)
    return gb1, gb2_direct, meta


# Forecast wrapper

def _load_forecast_module():
    """Import 09_weekly_forecast.py via importlib (numeric filename workaround)."""
    path = AUTOMATION / "09_weekly_forecast.py"
    spec = importlib.util.spec_from_file_location("wf09", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_forecast_from_df(forecast_df: pd.DataFrame,
                         history_df:  pd.DataFrame,
                         gb1, gb2_direct, meta) -> tuple:
    """
    Run the two-stage forecast.

    Returns (results, start_level, start_volume, end_level, end_volume).
    results is a list of 7 dicts with keys:
        day, date, rain_mm, temp_mean_C,
        pred_inflow_Mm3, pred_dvol_Mm3, cum_dvol_Mm3,
        pred_level_m, pred_volume_Mm3

    Actuals are NOT included here.
    Page 5 joins them from the gold table after calling this function.
    """
    wf = _load_forecast_module()
    return wf.run_forecast(forecast_df, history_df, gb1, gb2_direct, meta)


# Bathymetric helper

def vol_to_level(volume_Mm3: float, coeffs: list) -> float:
    """Convert volume (Mm3) to level (m MSL) via bathymetric polynomial."""
    return float(np.polyval(coeffs, volume_Mm3))


# SVG gauge helper

def build_lake_svg(current_level: float) -> str:
    """
    Return an inline SVG of the real Kinneret outline (traced in Inkscape),
    filled with a teal gradient up to current_level.

    Source path coordinate space: 0 0 210 297 (A4 mm).
    Lake occupies approximately x:43-149, y:87-256.
    viewBox is cropped tightly to the lake with small margins.
    """
    # Real Kinneret outline path (from Kinneret Outline.svg)
    LAKE_PATH = (
        "m 66.402564,86.964313 c -0.792221,1.404392 -2.376664,4.213178 -4.249209,7.490131 "
        "-1.872545,3.276953 -4.033129,7.021966 -6.078842,10.788186 -2.045714,3.76622 "
        "-3.889056,7.382 -5.422931,10.59436 -1.533875,3.21235 -2.758207,6.02111 "
        "-3.469884,8.25476 -0.711677,2.23364 -0.936253,4.10511 -0.976521,5.97714 "
        "-0.04027,1.87203 0.10377,3.74452 0.391855,5.32897 0.288085,1.58446 "
        "0.720197,2.8808 1.332375,4.21319 0.612179,1.33238 1.404382,2.70073 "
        "2.016558,3.52897 0.612176,0.82823 1.044291,1.11631 1.836524,2.12461 "
        "0.792233,1.0083 1.944533,2.73675 2.592714,3.67301 0.64818,0.93626 "
        "0.79222,1.0803 0.972271,1.26035 0.180051,0.18005 0.396109,0.39611 "
        "1.260367,0.57616 0.864257,0.18005 2.376665,0.32409 3.288089,0.4582 "
        "0.911424,0.13411 1.296349,0.28808 1.560839,0.86922 0.26449,0.58114 "
        "0.408529,1.58941 0.480548,2.2736 0.07202,0.68419 0.07202,1.04428 "
        "0.429822,1.74115 0.357802,0.69688 0.972264,1.58443 1.6036,2.56839 "
        "0.631336,0.98395 1.279504,2.06423 1.675616,3.54066 0.396111,1.47643 "
        "0.540148,3.34892 0.837175,5.55796 0.297027,2.20904 0.747026,4.75452 "
        "1.288666,7.05025 0.54164,2.29573 1.218048,4.48105 1.938211,6.21032 "
        "0.720162,1.72927 1.484035,3.00239 2.400712,4.19916 0.916677,1.19677 "
        "1.986102,2.31712 3.208338,3.64121 1.222236,1.32409 2.597209,2.85184 "
        "3.819441,4.4051 1.222232,1.55325 2.291666,3.13194 3.340156,4.8999 "
        "1.04849,1.76796 2.138876,3.84488 3.015102,6.05468 0.876227,2.2098 "
        "1.538257,4.55237 1.966731,6.84443 0.428473,2.29205 0.636569,4.68515 "
        "0.778813,5.98994 0.142244,1.30478 0.218634,1.52122 0.244095,3.51373 "
        "0.02546,1.99251 -2e-6,5.76096 0.630219,8.89929 0.630221,3.13834 "
        "1.916074,5.64639 3.256031,7.82665 1.339957,2.18027 2.733926,4.03261 "
        "4.110633,5.39994 1.376707,1.36733 2.736056,2.24955 3.924402,2.79421 "
        "1.18834,0.54465 2.20561,0.75171 3.36886,0.83578 1.16325,0.0841 "
        "2.47242,0.0452 3.71267,-0.16528 1.24026,-0.21043 2.41154,-0.59237 "
        "3.82475,-1.1271 1.41321,-0.53472 3.06829,-1.22222 4.40531,-1.98847 "
        "1.33703,-0.76625 2.3935,-1.64235 3.88936,-3.29519 1.49586,-1.65285 "
        "3.43102,-4.08236 5.03318,-6.23057 1.60216,-2.14821 2.92148,-4.08894 "
        "4.62546,-6.87787 1.70398,-2.78892 3.79253,-6.42587 5.61105,-9.37872 "
        "1.81852,-2.95285 3.36693,-5.22144 4.46524,-6.96794 1.09832,-1.7465 "
        "1.74649,-2.97083 2.36748,-4.66583 0.621,-1.69501 1.24234,-3.96108 "
        "1.75108,-5.76034 0.50874,-1.79926 0.90484,-3.1316 1.39098,-5.63434 "
        "0.48614,-2.50273 1.06229,-6.17569 1.46911,-8.63686 0.40682,-2.46116 "
        "0.6443,-3.71041 0.69938,-4.69154 0.0551,-0.98113 -0.0722,-1.69408 "
        "-0.5815,-2.97997 -0.50927,-1.2859 -1.40045,-3.14466 -1.90972,-4.50694 "
        "-0.50926,-1.36228 -0.63657,-2.228 -0.50925,-3.20834 0.12732,-0.98033 "
        "0.50926,-2.07522 1.12,-2.95061 0.61074,-0.8754 1.41318,-1.50231 "
        "1.91627,-2.15953 0.50308,-0.65722 0.70679,-1.34471 0.83145,-1.90517 "
        "0.12466,-0.56047 0.17824,-1.06944 0.19229,-1.76954 0.014,-0.7001 "
        "-0.0114,-1.59129 0.0412,-2.79292 0.0526,-1.20164 0.18318,-2.71366 "
        "0.44654,-4.29792 0.26337,-1.58425 0.65947,-3.2407 1.16362,-5.09523 "
        "0.50414,-1.85453 1.11631,-3.90709 1.57131,-5.54655 0.45499,-1.63946 "
        "0.7652,-2.91679 0.96532,-4.37472 0.20013,-1.45792 0.29015,-3.09634 "
        "0.11009,-4.64929 -0.18005,-1.55295 -0.63017,-3.02034 -1.31543,-4.74593 "
        "-0.68526,-1.72559 -1.61594,-3.73152 -2.08579,-5.01809 -0.46985,-1.28657 "
        "-0.47885,-1.85371 -0.29429,-2.5064 0.18455,-0.65269 0.56265,-1.39088 "
        "1.30987,-2.30915 0.74722,-0.91827 1.86351,-2.01655 2.66474,-2.92581 "
        "0.80123,-0.90927 1.28736,-1.62945 1.64746,-2.35867 0.3601,-0.72921 "
        "0.59416,-1.4674 0.67519,-2.30464 0.081,-0.83725 0.009,-1.7735 "
        "-0.0613,-2.6019 -0.0703,-0.82839 -0.14404,-1.60243 -0.65393,-3.42623 "
        "-0.5099,-1.8238 -1.45593,-4.69723 -2.71832,-7.73817 -1.26239,-3.040939 "
        "-2.84106,-6.249207 -4.20334,-8.782791 -1.36228,-2.533584 -2.50809,-4.392342 "
        "-3.6794,-5.996524 -1.17131,-1.604181 -2.36804,-2.953688 -3.46296,-3.895821 "
        "-1.09491,-0.942134 -2.08796,-1.476852 -3.59022,-2.646792 -1.50225,-1.16994 "
        "-3.47567,-2.940953 -4.88254,-4.042915 -1.40687,-1.101963 -2.24713,-1.534825 "
        "-3.20201,-1.802188 -0.95487,-0.267363 -2.0243,-0.369213 -2.76102,-0.770268 "
        "-0.73671,-0.401054 -1.10763,-1.043976 -1.95514,-1.772857 -0.84751,-0.728882 "
        "-2.17156,-1.543682 -3.66116,-2.091138 -1.4896,-0.547456 -3.14466,-0.827543 "
        "-4.79977,-0.967589 -1.65511,-0.140046 -3.31016,-0.140046 -4.48147,0.01273 "
        "-1.1713,0.152781 -1.85879,0.458332 -2.38078,0.802084 -0.52199,0.343752 "
        "-0.87847,0.725693 -1.09491,1.133106 -0.21643,0.407412 -0.29282,0.840274 "
        "-0.76825,1.133867 -0.47544,0.293594 -1.3368,0.4456 -2.31495,0.776239 "
        "-0.97816,0.33064 -2.07306,0.839896 -3.09193,1.466696 -1.01886,0.626801 "
        "-1.998827,1.400454 -2.883499,2.067384 -0.884672,0.66693 -1.674007,1.227103 "
        "-2.679807,1.850953 -1.0058,0.62385 -2.227998,1.311336 -3.599438,1.670661 "
        "-1.37144,0.359325 -2.89204,0.390474 -4.102489,1.054243 -1.210449,0.66377 "
        "-2.110682,1.960107 -3.237823,2.810277 -1.127141,0.850169 -2.481118,1.25413 "
        "-4.170293,2.025859 -1.689176,0.77173 -3.713439,1.911175 -5.170043,2.532922 "
        "-1.456604,0.621747 -2.345469,0.725769 -3.294062,0.683253 -0.948594,-0.04252 "
        "-1.956855,-0.231566 -2.780593,-0.330595 -0.823737,-0.09903 -1.462902,-0.108032 "
        "-1.782491,-0.112533 -0.319589,-0.0045 -0.319576,-0.0045 -1.111798,1.399896 z"
    )

    # Exact lake bounds (computed by sampling bezier curves from the path)
    LAKE_TOP_Y    = 73.50   # y when lake is at LEVEL_MAX (-208.89 m)
    LAKE_BOTTOM_Y = 194.85  # y when lake is at LEVEL_MIN (-214.87 m)
    LAKE_HEIGHT   = LAKE_BOTTOM_Y - LAKE_TOP_Y

    def _level_y(lvl: float) -> float:
        frac = (lvl - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
        frac = max(0.0, min(1.0, frac))
        return LAKE_BOTTOM_Y - frac * LAKE_HEIGHT

    water_y     = _level_y(current_level)
    legal_max_y = _level_y(LEVEL_LEGAL_MAX)
    legal_min_y = _level_y(LEVEL_LEGAL_MIN)

    # ViewBox large enough to contain the full lake path + right-side labels.
    # Lake path actual bounds extend to ~x:130, y:258 (bezier overrun included).
    # Origin chosen to centre the lake with even margins all around.
    VB = "20 55 175 235"   # x:20-195, y:55-290
    LX1, LX2 = 52, 125    # reference-line x span across the lake body
    TX = LX2 + 32          # label x = 157, with breathing room from lake edge
    FS_SM, FS_LG = 6.5, 8.0   # font sizes scaled for the wider coordinate window
    SW = 0.9               # stroke width

    return f"""<svg viewBox="{VB}" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:auto;display:block;">
  <defs>
    <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#4FC3F7"/>
      <stop offset="100%" stop-color="#006064"/>
    </linearGradient>
    <clipPath id="wc">
      <rect x="0" y="{water_y:.2f}" width="300" height="300"/>
    </clipPath>
  </defs>

  <!-- Lake body (empty) -->
  <path d="{LAKE_PATH}" fill="#1A1D27" stroke="#1E90FF" stroke-width="{SW}"/>

  <!-- Water fill -->
  <path d="{LAKE_PATH}" fill="url(#wg)" clip-path="url(#wc)"/>

  <!-- Water surface line -->
  <line x1="{LX1}" y1="{water_y:.2f}" x2="{LX2}" y2="{water_y:.2f}"
        stroke="#4FC3F7" stroke-width="{SW}" stroke-dasharray="5 2.5"/>

  <!-- Upper management line (green) — extends to label -->
  <line x1="{LX1}" y1="{legal_max_y:.2f}" x2="{TX - 1}" y2="{legal_max_y:.2f}"
        stroke="#66BB6A" stroke-width="{SW}" stroke-dasharray="6 3"/>
  <text x="{TX}" y="{legal_max_y + 2:.2f}" fill="#66BB6A" font-size="{FS_SM}"
        font-family="monospace" text-anchor="start">-208.9</text>

  <!-- Lower management line (red) — extends to label -->
  <line x1="{LX1}" y1="{legal_min_y:.2f}" x2="{TX - 1}" y2="{legal_min_y:.2f}"
        stroke="#EF5350" stroke-width="{SW}" stroke-dasharray="6 3"/>
  <text x="{TX}" y="{legal_min_y + 2:.2f}" fill="#EF5350" font-size="{FS_SM}"
        font-family="monospace" text-anchor="start">-213.0</text>

  <!-- Current level label centred on lake -->
  <text x="88" y="{water_y - 3:.2f}" fill="#E0E0E0" font-size="{FS_LG}"
        font-family="monospace" text-anchor="middle" font-weight="bold">{current_level:.2f} m</text>
</svg>"""
