import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app_utils import load_gold, PROJECT_ROOT, COLOURS
from kinneret_level import append_to_silver, fetch_new_levels

st.set_page_config(
    page_title="Data Sources · Kinneret",
    page_icon="📋",
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
</style>
""", unsafe_allow_html=True)

st.title("📋 Data Sources")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'Where every number in the pipeline comes from'
    '</div>',
    unsafe_allow_html=True,
)

gold = load_gold()

tab_met, tab_level, tab_jordan, tab_coverage = st.tabs([
    "Meteorological (IMS)",
    "Kinneret Level (IHS)",
    "Jordan River / Inflow",
    "Coverage Timeline",
])

# ── Tab A: Meteorological ─────────────────────────────────────────────────────
with tab_met:
    st.subheader("Israel Meteorological Service (IMS)")
    st.markdown("**Station:** Kinneret / Zemach area  |  **Update cadence:** Manual batch ingestion via `01_ingest_met_data.py`")

    st.markdown(f"**Coverage:** `{gold['date'].min().date()}` → `{gold['date'].max().date()}`")

    met_vars = pd.DataFrame([
        {"Variable": "temp_max_C",     "Description": "Daily maximum air temperature",       "Unit": "°C",    "Derivation": "Direct IMS measurement"},
        {"Variable": "temp_min_C",     "Description": "Daily minimum air temperature",       "Unit": "°C",    "Derivation": "Direct IMS measurement"},
        {"Variable": "humidity_pct",   "Description": "Mean relative humidity",              "Unit": "%",     "Derivation": "Direct IMS measurement"},
        {"Variable": "wind_speed_ms",  "Description": "Mean wind speed at 10 m",            "Unit": "m/s",   "Derivation": "Direct IMS measurement"},
        {"Variable": "rainfall_mm",    "Description": "Daily total precipitation",           "Unit": "mm",    "Derivation": "Direct IMS measurement"},
        {"Variable": "radiation_MJm2", "Description": "Global solar radiation",              "Unit": "MJ/m²", "Derivation": "Direct IMS measurement"},
        {"Variable": "et0_mm",         "Description": "Reference evapotranspiration (FAO-56)","Unit": "mm",   "Derivation": "FAO-56 Penman-Monteith from temp, humidity, wind, radiation"},
        {"Variable": "vpd_kPa",        "Description": "Vapour pressure deficit",             "Unit": "kPa",   "Derivation": "Computed from temp_mean and humidity_pct"},
        {"Variable": "daylength_hrs",  "Description": "Astronomical day length",             "Unit": "hours", "Derivation": "Computed from latitude (32.82°N) and day-of-year"},
    ])
    st.dataframe(met_vars, width='stretch', hide_index=True)

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Raw file sample (most recent IMS CSV)**")
    met_dir = PROJECT_ROOT / "Raw Data" / "Meteorological Data"
    if met_dir.exists():
        met_files = sorted(met_dir.glob("*.csv"))
        if met_files:
            try:
                sample = pd.read_csv(met_files[-1], nrows=5)
                st.dataframe(sample, width='stretch', hide_index=True)
                st.caption(f"File: `{met_files[-1].name}` | Total met files: {len(met_files)}")
            except Exception as e:
                st.warning(f"Could not read sample: {e}")
        else:
            st.info("No CSV files found in Meteorological Data folder.")
    else:
        st.info("Meteorological Data folder not found.")

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Derived feature notes**")
    st.markdown("""
- **VPD** (vapour pressure deficit) = saturation vapour pressure at mean temperature minus actual vapour pressure (computed from humidity). Drives evaporation demand.
- **ET₀** (reference evapotranspiration) uses the FAO-56 Penman-Monteith equation: requires temperature, humidity, wind speed, and solar radiation. Where radiation is missing, ET₀ is NaN and the model imputes with training-set median.
""")

# ── Tab B: Kinneret Level ─────────────────────────────────────────────────────
with tab_level:
    st.subheader("Israel Hydrological Service (IHS) — Lake Level")
    st.markdown("""
**Unit:** metres above mean sea level (m MSL) — **negative values** because the lake surface is below sea level.

**Station:** Miflas (primary gauge, northern shore)

**Missing-data policy:** Forward-filled for feature computation (lag / rolling features). Never imputed for training targets — missing target days are simply excluded from CV.
""")

    date_range = (gold["date"].max() - gold["date"].min()).days + 1
    missing_days = date_range - gold["level_m"].notna().sum()

    lc1, lc2, lc3 = st.columns(3)
    lc1.metric("Coverage start", str(gold["date"].min().date()))
    lc2.metric("Coverage end",   str(gold["date"].max().date()))
    lc3.metric("Missing days",   f"{missing_days} (~{missing_days/date_range*100:.1f}%)")

    silver_level = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Silver data sample**")
    if silver_level.exists():
        try:
            df_lvl = pd.read_csv(silver_level, nrows=5)
            st.dataframe(df_lvl, width='stretch', hide_index=True)
        except Exception as e:
            st.warning(f"Could not read silver level file: {e}")
    else:
        st.dataframe(
            gold[["date","level_m","volume_Mm3"]].dropna().tail(5),
            width='stretch', hide_index=True,
        )
        st.caption("(Showing from gold table — silver file not found at expected path)")

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    if st.button("Refresh Level Data", key="refresh_level"):
        with st.spinner("Fetching from kineret.org.il..."):
            try:
                df_new = fetch_new_levels(silver_level)
                n = append_to_silver(df_new, silver_level)
                if n > 0:
                    d_min = df_new["date"].min()
                    d_max = df_new["date"].max()
                    st.success(f"Added {n} new readings ({d_min} to {d_max})")
                    st.info("Re-run the pipeline (07 -> 08) to update the forecast model.")
                else:
                    st.success("Already up to date. No new readings.")
            except Exception as e:
                st.error(f"Fetch failed: {e}")

# ── Tab C: Jordan River ────────────────────────────────────────────────────────
with tab_jordan:
    st.subheader("IHS Gauge Stations — Jordan River / Obstacle Inflow")
    st.markdown("""
**Primary station:** Obstacle gauge (upstream of lake, primary inflow)

**Unit:** m³/day

**Processing:** Raw station files (Excel/CSV) consolidated and cleaned by `05_clean_jordan_river_flow.py`. Units verified against station metadata. Outliers removed with IQR method.
""")

    if "inflow_obstacle_m3" in gold.columns:
        inflow = gold["inflow_obstacle_m3"].dropna()
        jc1, jc2, jc3 = st.columns(3)
        jc1.metric("Mean inflow",   f"{inflow.mean()/1e6:.3f} Mm³/day")
        jc2.metric("Max inflow",    f"{inflow.max()/1e6:.2f} Mm³/day")
        jc3.metric("Missing days",  f"{gold['inflow_obstacle_m3'].isna().sum()}")

    st.warning(
        "**Baptist Site outflow gap:** Data from the Baptist Site gauge (southern outlet) "
        "is available only through **2025-06-23**. After this date, southern outflow is not "
        "incorporated into the model features."
    )

    jordan_silver = PROJECT_ROOT / "Silver Data" / "Jordan River Silver" / "jordan_river_daily_flow_clean.csv"
    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Silver data sample**")
    if jordan_silver.exists():
        try:
            df_j = pd.read_csv(jordan_silver, nrows=5)
            st.dataframe(df_j, width='stretch', hide_index=True)
            st.caption(f"File: `{jordan_silver.name}`")
        except Exception as e:
            st.warning(f"Could not read Jordan silver file: {e}")
    else:
        st.info("Jordan river silver file not found at expected path.")

# ── Tab D: Coverage Timeline ───────────────────────────────────────────────────
with tab_coverage:
    st.subheader("Data Coverage Timeline")

    sources = [
        {
            "name": "IMS Meteorological",
            "start": str(gold["date"].min().date()),
            "end":   str(gold["date"].max().date()),
            "color": "#1E90FF",
        },
        {
            "name": "Kinneret Level (IHS)",
            "start": str(gold["date"].min().date()),
            "end":   str(gold["date"].max().date()),
            "color": "#4FC3F7",
        },
        {
            "name": "Jordan River Inflow",
            "start": str(gold["date"].min().date()),
            "end":   str(gold["date"].max().date()),
            "color": "#66BB6A",
        },
        {
            "name": "Baptist Site Outflow",
            "start": str(gold["date"].min().date()),
            "end":   "2025-06-23",
            "color": "#FF7043",
        },
    ]

    fig_gantt = go.Figure()
    for i, src in enumerate(sources):
        duration_ms = (pd.Timestamp(src["end"]) - pd.Timestamp(src["start"])).total_seconds() * 1000
        fig_gantt.add_trace(go.Bar(
            x=[duration_ms],
            y=[src["name"]],
            base=[src["start"]],
            orientation="h",
            marker_color=src["color"],
            marker_opacity=0.82,
            name=src["name"],
            hovertemplate=(
                f"<b>{src['name']}</b><br>"
                f"Start: {src['start']}<br>"
                f"End: {src['end']}<extra></extra>"
            ),
        ))

    fig_gantt.update_layout(
        template="plotly_dark",
        barmode="stack",
        height=250,
        margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(
            type="date",
            tickformat="%Y",
            showgrid=True, gridcolor="rgba(255,255,255,0.05)",
            title="Year",
        ),
        yaxis=dict(showgrid=False, autorange="reversed"),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig_gantt.add_vline(
        x=pd.Timestamp("2025-06-23").timestamp() * 1000,
        line_dash="dot", line_color="#FF7043", line_width=1.2,
        annotation_text="Baptist Site cutoff",
        annotation_font=dict(color="#FF7043", size=9),
    )

    st.plotly_chart(fig_gantt, width='stretch')
    st.caption("Coloured bars = data available. Baptist Site outflow (orange) ends 2025-06-23.")
