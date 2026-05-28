import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from app_utils import load_gold, PROJECT_ROOT, COLOURS

st.set_page_config(
    page_title="Data Pipeline · Kinneret",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
.block-container { padding-top: 1.4rem; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }
.kn-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(30,144,255,0.22), transparent);
    margin: 1.2rem 0;
}
.kn-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.14em;
    color: #7BA3D4;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.etl-flow {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 1rem 0 1.2rem;
    flex-wrap: wrap;
}
.etl-box {
    background: #1A1D27;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    text-align: center;
    flex: 1;
    min-width: 120px;
}
.etl-arrow {
    font-size: 1.4rem;
    color: #3A4E7A;
    flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Data Pipeline")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'ETL chain · Script documentation · Data layer browser'
    '</div>',
    unsafe_allow_html=True,
)

# Pipeline flow diagram
st.markdown("""
<div class="etl-flow">
  <div class="etl-box" style="border-left:3px solid #6D4C41;">
    <div style="color:#A1887F;font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem;">BRONZE</div>
    <div style="color:#E0E0E0;">Raw CSVs / Excel</div>
    <div style="color:#6D4C41;font-size:0.7rem;margin-top:0.3rem;">Scripts 01–03</div>
  </div>
  <div class="etl-arrow">→</div>
  <div class="etl-box" style="border-left:3px solid #546E7A;">
    <div style="color:#80CBC4;font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem;">SILVER</div>
    <div style="color:#E0E0E0;">Cleaned CSVs / Parquets</div>
    <div style="color:#546E7A;font-size:0.7rem;margin-top:0.3rem;">Scripts 04–06</div>
  </div>
  <div class="etl-arrow">→</div>
  <div class="etl-box" style="border-left:3px solid #F9A825;">
    <div style="color:#FFD54F;font-size:0.65rem;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem;">GOLD</div>
    <div style="color:#E0E0E0;">Feature CSV (5,008 × 42)</div>
    <div style="color:#F9A825;font-size:0.7rem;margin-top:0.3rem;">Scripts 07–09</div>
  </div>
</div>
""", unsafe_allow_html=True)

gold = load_gold()
AUTOMATION = PROJECT_ROOT / "Automation"

# Script metadata
SCRIPTS = [
    {
        "file": "01_ingest_met_data.py",
        "purpose": "Read raw IMS CSV files, standardise column names",
        "inputs":  ["Raw Data/Meteorological Data/*.csv"],
        "outputs": ["In-memory long-format DataFrame → passed to 02"],
        "transforms": [
            "Reads all CSV files in Raw Data/Meteorological Data/",
            "Renames station-specific column names to standardised schema",
            "Outputs long-format DataFrame with columns: date, variable, value, station_id",
        ],
    },
    {
        "file": "02_pivot_wide_met_data.py",
        "purpose": "Pivot per-variable long format to one-row-per-date wide format",
        "inputs":  ["Long-format met DataFrame from 01"],
        "outputs": ["Silver Data/Meteorological/met_data_wide.csv"],
        "transforms": [
            "Groups by date, pivots variable column into separate columns",
            "Fills short gaps (1–2 days) via forward-fill",
            "Writes wide CSV with one row per day",
        ],
    },
    {
        "file": "03_aggregate_daily_met_data.py",
        "purpose": "Sub-daily to daily aggregation (if raw data is hourly/sub-daily)",
        "inputs":  ["Silver Data/Meteorological/met_data_wide.csv"],
        "outputs": ["Silver Data/Meteorological/met_data_daily.csv"],
        "transforms": [
            "Aggregates: max (temp_max), min (temp_min), mean (humidity, wind), sum (rainfall, radiation)",
            "Skipped if input is already daily",
        ],
    },
    {
        "file": "04_clean_daily_met_data.py",
        "purpose": "Outlier removal, QC flags, gap-filling",
        "inputs":  ["Silver Data/Meteorological/met_data_daily.csv"],
        "outputs": ["Silver Data/Meteorological/met_data_daily_clean.csv",
                    "Silver Data/Meteorological/met_data_daily_qc_log.csv"],
        "transforms": [
            "IQR-based outlier detection per variable (1.5× IQR fence)",
            "Outliers flagged and replaced with rolling median",
            "Forward-fill for gaps up to 3 days; longer gaps remain NaN",
            "QC log records all flagged/filled cells",
        ],
    },
    {
        "file": "05_clean_jordan_river_flow.py",
        "purpose": "Clean and consolidate multi-station Jordan River flow data",
        "inputs":  ["Raw Data/Jordan River Stations Raw Data/"],
        "outputs": ["Silver Data/Jordan River Silver/jordan_river_daily_flow_clean.csv"],
        "transforms": [
            "Reads Excel and CSV files from multiple IHS gauge stations",
            "Aligns date formats, removes duplicate rows",
            "Unit verification: raw data in m³/day (confirmed against station metadata)",
            "IQR outlier removal on daily flow values",
        ],
    },
    {
        "file": "06_ingest_kinneret_level.py",
        "purpose": "Read Miflas level files, convert to volume via bathymetric polynomial",
        "inputs":  ["Raw Data/Kinneret_Level/"],
        "outputs": ["Silver Data/Kinneret Level/kinneret_level.csv"],
        "transforms": [
            "Reads Miflas gauge CSV files (m MSL values)",
            "Applies bathymetric polynomial to convert level → volume (Mm³)",
            "Computes daily volume_change_Mm3 as first difference",
        ],
    },
    {
        "file": "07_build_gold_features.py",
        "purpose": "Join all silver tables and engineer 42 model features",
        "inputs":  ["All Silver Data/ files"],
        "outputs": ["Gold Data/kinneret_gold_features.csv"],
        "transforms": [
            "Date-aligned merge of met, level, and flow silver tables",
            "Rainfall rolling sums: 7-day, 14-day, 21-day + lags 1/2/3",
            "Moisture balance: rainfall - ET₀ (7-day, 14-day)",
            "Seasonality: sin/cos annual cycle, 4 RBF seasonal dummies, daylength",
            "Volume change lags: lag1, lag2 (autoregressive features for Stage 2)",
        ],
    },
    {
        "file": "07b_precalc_precip_intensity.py",
        "purpose": "Add precipitation intensity feature to gold table",
        "inputs":  ["Gold Data/kinneret_gold_features.csv"],
        "outputs": ["Gold Data/kinneret_gold_features.csv (updated)"],
        "transforms": [
            "Computes event intensity: rainfall_mm / (wet_days_in_window + 1)",
            "Joins to gold table in place",
        ],
    },
    {
        "file": "08_train_forecast_model.py",
        "purpose": "Walk-forward CV + final model training",
        "inputs":  ["Gold Data/kinneret_gold_features.csv"],
        "outputs": ["Models/stage1_inflow_rf.pkl", "Models/stage2_direct_gb.pkl",
                    "Models/model_metadata.json"],
        "transforms": [
            "4-fold walk-forward CV (test years: 2021, 2022, 2023, 2024)",
            "Stage 1: GBRegressor (250 trees, depth=4, lr=0.05) on inflow_obstacle_m3",
            "Stage 2 Direct: GBRegressor with anchor state + horizon_h feature",
            "Final models trained on full dataset; metadata JSON captures CV results and bathy coefficients",
        ],
    },
    {
        "file": "09_weekly_forecast.py",
        "purpose": "Two-stage 7-day lake level forecast",
        "inputs":  ["Models/*.pkl", "Models/model_metadata.json",
                    "Gold Data/kinneret_gold_features.csv", "forecast_input_template.csv"],
        "outputs": ["Console output (tabular forecast)"],
        "transforms": [
            "Loads 21 days of history for lag/rolling feature computation",
            "Stage 1: predicts daily inflow for each horizon (chained lags)",
            "Stage 2 Direct: predicts daily volume change using frozen anchor state",
            "Converts volume predictions to level via bathymetric polynomial",
        ],
    },
]

def _read_docstring(fname: str) -> str:
    path = AUTOMATION / fname
    if not path.exists():
        return f"Script not found at {path}"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return ast.get_docstring(tree) or "No module-level docstring."
    except Exception as e:
        return f"Could not parse script: {e}"


tab_scripts, tab_bronze, tab_silver, tab_gold = st.tabs(
    ["Scripts", "Bronze", "Silver", "Gold"]
)

# ── Tab: Scripts ───────────────────────────────────────────────────────────────
with tab_scripts:
    for sc in SCRIPTS:
        with st.expander(f"`{sc['file']}` — {sc['purpose']}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Inputs**")
                for inp in sc["inputs"]:
                    st.markdown(f"- `{inp}`")
            with c2:
                st.markdown("**Outputs**")
                for out in sc["outputs"]:
                    st.markdown(f"- `{out}`")

            st.markdown("**Key transforms**")
            for t in sc["transforms"]:
                st.markdown(f"- {t}")

            docstring = _read_docstring(sc["file"])
            st.markdown("**Module docstring**")
            st.code(docstring, language="text")

# ── Tab: Bronze ────────────────────────────────────────────────────────────────
with tab_bronze:
    bronze_dirs = {
        "Raw Data / Meteorological Data":       PROJECT_ROOT / "Raw Data" / "Meteorological Data",
        "Raw Data / Jordan River Stations":     PROJECT_ROOT / "Raw Data" / "Jordan River Stations Raw Data",
        "Raw Data / Kinneret Level":            PROJECT_ROOT / "Raw Data" / "Kinneret_Level",
    }
    for label, bdir in bronze_dirs.items():
        st.markdown(f"**{label}**")
        if bdir.exists():
            files = list(bdir.iterdir())
            if files:
                rows = []
                total_kb = 0
                for f in sorted(files):
                    if f.is_file():
                        kb = f.stat().st_size / 1024
                        total_kb += kb
                        rows.append({"Filename": f.name, "Size (KB)": round(kb, 1)})
                df_b = pd.DataFrame(rows)
                st.dataframe(df_b, width='stretch', hide_index=True, height=140)
                st.caption(f"{len(rows)} files · {total_kb:.0f} KB total")
            else:
                st.info("Directory is empty.")
        else:
            st.warning(f"Directory not found: `{bdir}`")
        st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

# ── Tab: Silver ────────────────────────────────────────────────────────────────
with tab_silver:
    silver_root = PROJECT_ROOT / "Silver Data"
    if silver_root.exists():
        silver_files = list(silver_root.rglob("*.csv")) + list(silver_root.rglob("*.parquet"))
        for sf in sorted(silver_files)[:12]:
            with st.expander(f"`{sf.relative_to(PROJECT_ROOT)}`"):
                try:
                    if sf.suffix == ".parquet":
                        df_s = pd.read_parquet(sf)
                    else:
                        df_s = pd.read_csv(sf)
                    st.caption(f"{len(df_s):,} rows × {len(df_s.columns)} columns")
                    st.dataframe(df_s.head(5), width='stretch', hide_index=True)

                    null_rates = df_s.isnull().mean() * 100
                    non_zero = null_rates[null_rates > 0]
                    if not non_zero.empty:
                        fig_null = go.Figure(go.Bar(
                            x=non_zero.index.tolist(),
                            y=non_zero.values,
                            marker_color="#EF5350",
                        ))
                        fig_null.update_layout(
                            template="plotly_dark", height=100,
                            margin=dict(l=10, r=10, t=5, b=20),
                            yaxis=dict(title="Null %", range=[0, 100]),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig_null, width='stretch', config={"displayModeBar": False})
                except Exception as e:
                    st.warning(f"Could not read: {e}")
    else:
        st.warning("Silver Data directory not found.")

# ── Tab: Gold ──────────────────────────────────────────────────────────────────
with tab_gold:
    COLUMN_GROUPS = {
        "Lake State":   ["level_m","volume_Mm3","volume_change_Mm3","volume_change_lag1_Mm3",
                         "volume_change_lag2_Mm3","predicted_inflow_m3"],
        "Met Raw":      ["temp_max_C","temp_min_C","temp_mean_C","humidity_pct",
                         "wind_speed_ms","rainfall_mm","radiation_MJm2"],
        "Met Derived":  ["et0_mm","vpd_kPa","et0_7d_mm","moisture_balance_7d_mm",
                         "moisture_balance_14d_mm","rainfall_7d_mm","rainfall_14d_mm",
                         "rainfall_21d_mm","rainfall_lag1_mm","rainfall_lag2_mm","rainfall_lag3_mm"],
        "River Flows":  ["inflow_obstacle_m3","inflow_lag1_m3","inflow_lag2_m3"],
        "Seasonality":  ["season_sin","season_cos","daylength_hrs","solar_declination_rad",
                         "rbf_spring_equinox","rbf_summer_solstice","rbf_autumn_equinox","rbf_winter_solstice"],
    }

    selected_groups = st.multiselect(
        "Column groups",
        list(COLUMN_GROUPS.keys()),
        default=["Lake State", "Met Raw"],
    )

    all_dates = gold["date"].dt.date
    date_min, date_max = all_dates.min(), all_dates.max()
    dr = st.slider(
        "Date range",
        min_value=date_min, max_value=date_max,
        value=(date_min, date_max),
    )

    show_cols = ["date"]
    for g in selected_groups:
        show_cols += [c for c in COLUMN_GROUPS.get(g, []) if c in gold.columns]
    show_cols = list(dict.fromkeys(show_cols))

    mask = (all_dates >= dr[0]) & (all_dates <= dr[1])
    display_df = gold.loc[mask, show_cols]

    st.caption(
        f"Showing {len(display_df):,} rows × {len(show_cols)} columns  |  "
        f"Full table: 5,008 rows × 42 columns"
    )
    st.dataframe(display_df, width='stretch', height=380, hide_index=True)

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="kn-label">Missing-Data Heatmap (null % per column per year)</div>', unsafe_allow_html=True)

    numeric_cols = gold.select_dtypes(include=np.number).columns.tolist()
    gold["_year"] = gold["date"].dt.year
    null_pivot = gold.groupby("_year")[numeric_cols].apply(lambda df: df.isnull().mean() * 100)
    null_pivot = null_pivot.loc[:, null_pivot.max() > 0]

    if not null_pivot.empty:
        fig_null = go.Figure(go.Heatmap(
            z=null_pivot.values,
            x=null_pivot.columns.tolist(),
            y=null_pivot.index.tolist(),
            colorscale=[[0,"#1A1D27"],[0.01,"#FF7043"],[1,"#B71C1C"]],
            zmin=0, zmax=100,
            colorbar=dict(title="Null %", thickness=12),
            hovertemplate="Year %{y} · %{x}: %{z:.1f}%<extra></extra>",
        ))
        fig_null.update_layout(
            template="plotly_dark", height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(tickangle=-45, tickfont=dict(size=8)),
            yaxis=dict(tickfont=dict(size=9)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_null, width='stretch')
        st.caption("Red cells indicate missing data. The Baptist Site outflow gap is visible in 2025+.")
    else:
        st.success("No missing data in selected columns.")

# ── Daily Refresh ──────────────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.subheader("Daily Data Refresh")
st.markdown(
    '<div class="kn-label">Fetch new data from all sources, rebuild gold, retrain champion</div>',
    unsafe_allow_html=True,
)

if st.button("Run Daily Refresh", key="daily_refresh"):
    agent_script = AUTOMATION / "daily_agent.py"
    with st.spinner("Running daily agent (may take a few minutes)..."):
        result = subprocess.run(
            [sys.executable, str(agent_script)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
    if result.returncode == 0:
        st.success("Daily agent completed successfully.")
    else:
        st.error("Daily agent finished with errors.")
    if result.stdout:
        st.code(result.stdout, language="text")
    if result.stderr:
        with st.expander("stderr"):
            st.code(result.stderr, language="text")
