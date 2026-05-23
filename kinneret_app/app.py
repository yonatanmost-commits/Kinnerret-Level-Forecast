import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import base64
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date
from app_utils import (
    load_gold, build_lake_svg,
    LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX,
    COLOURS,
)

st.set_page_config(
    page_title="Kinneret Forecast",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Syne:wght@700;800&display=swap');

.block-container { padding-top: 1.4rem; padding-bottom: 2.5rem; }

h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: -0.01em;
}

[data-testid="metric-container"] {
    background: #1A1D27;
    border: 1px solid rgba(30,144,255,0.18);
    border-left: 3px solid rgba(30,144,255,0.55);
    border-radius: 8px;
    padding: 0.85rem 1.1rem 0.65rem;
    margin-bottom: 0.55rem;
}

[data-testid="stMetricLabel"] > div {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #5B88C5 !important;
}

[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 1.6rem !important;
    font-weight: 400 !important;
    color: #E8EEFF !important;
}

[data-testid="stMetricDelta"] svg { display: none; }

.kn-subtitle {
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.2em;
    color: #7BA3D4;
    text-transform: uppercase;
    margin-top: -0.9rem;
    margin-bottom: 1.8rem;
}

.kn-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.14em;
    color: #7BA3D4;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}

.kn-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(30,144,255,0.22), transparent);
    margin: 1.6rem 0;
}

.kn-nav-hint {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: #3A4E7A;
    letter-spacing: 0.08em;
    margin-bottom: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── Data ──────────────────────────────────────────────────────────────────────
gold  = load_gold()
valid = gold.dropna(subset=["level_m", "volume_Mm3"])
last  = valid.iloc[-1]

current_level  = float(last["level_m"])
current_volume = float(last["volume_Mm3"])
gold_max_date  = gold["date"].max().date()
days_since     = (date.today() - gold_max_date).days

cutoff_30   = gold["date"].max() - pd.Timedelta(days=30)
prev_30     = valid[valid["date"] <= cutoff_30]
level_30ago  = float(prev_30.iloc[-1]["level_m"])   if len(prev_30) else current_level
volume_30ago = float(prev_30.iloc[-1]["volume_Mm3"]) if len(prev_30) else current_volume

delta_level  = current_level  - level_30ago
delta_volume = current_volume - volume_30ago

dist_lower = current_level - LEVEL_LEGAL_MIN
dist_upper = LEVEL_LEGAL_MAX - current_level

# Rough Mm3 buffer (approx 220 Mm3 per metre at current level)
buffer_mm3 = abs(dist_lower) * 220

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌊 Kinneret Level Forecast")
st.markdown(
    f'<div class="kn-subtitle">'
    f'Lake Kinneret &nbsp;·&nbsp; Water Resource Monitor &nbsp;·&nbsp; '
    f'Last reading: {gold_max_date.strftime("%d %b %Y")}'
    f'</div>',
    unsafe_allow_html=True,
)

if current_level < LEVEL_LEGAL_MIN:
    st.error("⚠️  Lake is below the lower management line!")

# ── Lake gauge + metrics ──────────────────────────────────────────────────────
col_lake, col_metrics = st.columns([1, 2], gap="large")

with col_lake:
    st.markdown('<div class="kn-label">Current Level</div>', unsafe_allow_html=True)
    _svg_b64 = base64.b64encode(build_lake_svg(current_level).encode()).decode()
    st.markdown(
        f'<img src="data:image/svg+xml;base64,{_svg_b64}" '
        f'style="width:100%;height:auto;display:block;"/>',
        unsafe_allow_html=True,
    )

with col_metrics:
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

    delta_sign = "+" if delta_level >= 0 else ""
    st.metric(
        label="Lake Level",
        value=f"{current_level:.3f} m MSL",
        delta=f"{delta_sign}{delta_level:.2f} m (30 days)",
    )

    vol_sign = "+" if delta_volume >= 0 else ""
    st.metric(
        label="Volume",
        value=f"{current_volume:,.0f} Mm³",
        delta=f"{vol_sign}{delta_volume:.0f} Mm³ (30 days)",
    )

    st.metric(
        label="Days Since Last Reading",
        value=f"{days_since}",
    )

    st.markdown('<div style="height:0.3rem"></div>', unsafe_allow_html=True)

    if dist_lower >= 0:
        st.success(
            f"↑ {dist_lower:.2f} m above Lower Mgmt Line  "
            f"(≈ {buffer_mm3:.0f} Mm³ buffer)"
        )
    else:
        st.error(
            f"↓ {abs(dist_lower):.2f} m BELOW Lower Mgmt Line"
        )

    st.info(f"↓ {dist_upper:.2f} m below Spill Level")

# ── 30-day sparkline ──────────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="kn-label">30-Day Level Trend & Daily Volume Change</div>', unsafe_allow_html=True)

spark = gold.dropna(subset=["level_m"]).tail(30).copy().reset_index(drop=True)
spark["dvol"] = spark["volume_Mm3"].diff()

lvl_pad = 0.05
lvl_min = spark["level_m"].min() - lvl_pad
lvl_max = spark["level_m"].max() + lvl_pad

fig_spark = make_subplots(specs=[[{"secondary_y": True}]])

fig_spark.add_trace(go.Scatter(
    x=spark["date"],
    y=spark["level_m"],
    mode="lines",
    name="Level (m)",
    line=dict(color=COLOURS["predicted"], width=2),
    hovertemplate="%{x|%d %b}: %{y:.3f} m<extra>Level</extra>",
), secondary_y=False)

dvol_df = spark.dropna(subset=["dvol"])
fig_spark.add_trace(go.Bar(
    x=dvol_df["date"],
    y=dvol_df["dvol"],
    name="ΔVol (Mm³/day)",
    marker_color=[COLOURS["rising"] if v >= 0 else COLOURS["falling"] for v in dvol_df["dvol"]],
    opacity=0.55,
    hovertemplate="%{x|%d %b}: %{y:+.1f} Mm³<extra>ΔVol</extra>",
), secondary_y=True)

fig_spark.update_layout(
    template="plotly_dark",
    height=180,
    margin=dict(l=10, r=10, t=4, b=30),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, font=dict(size=10)),
    xaxis=dict(tickformat="%d %b", showgrid=False, tickfont=dict(size=10)),
    barmode="relative",
)
fig_spark.update_yaxes(
    range=[lvl_min, lvl_max],
    title_text="Level (m MSL)", title_font=dict(size=10),
    tickfont=dict(size=9), showgrid=True, gridcolor="rgba(255,255,255,0.05)",
    secondary_y=False,
)
fig_spark.update_yaxes(
    title_text="ΔVol (Mm³/day)", title_font=dict(size=10),
    tickfont=dict(size=9), showgrid=False,
    secondary_y=True,
)
st.plotly_chart(fig_spark, width='stretch', config={"displayModeBar": False})

# ── Year-over-year overlay ────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="kn-label">Year-over-Year Comparison</div>', unsafe_allow_html=True)

fig_yoy = go.Figure()

past_year_styles = {
    2020: ("rgba(15,  55, 120, 0.55)", "dot"),
    2021: ("rgba(25,  80, 155, 0.60)", "longdash"),
    2022: ("rgba(35, 105, 185, 0.65)", "dashdot"),
    2023: ("rgba(50, 130, 205, 0.70)", "dash"),
    2024: ("rgba(70, 155, 220, 0.75)", "longdashdot"),
    2025: ("rgba(100,180, 235, 0.85)", "solid"),
}
for yr, (clr, dash) in past_year_styles.items():
    yr_df = gold[gold["date"].dt.year == yr].dropna(subset=["level_m"])
    if yr_df.empty:
        continue
    fig_yoy.add_trace(go.Scatter(
        x=yr_df["date"].dt.dayofyear,
        y=yr_df["level_m"],
        mode="lines",
        name=str(yr),
        line=dict(color=clr, width=1.2, dash=dash),
        hovertemplate=f"{yr} · Day %{{x}}: %{{y:.3f}} m<extra></extra>",
    ))

df_2026 = gold[gold["date"].dt.year == 2026].dropna(subset=["level_m"])
if not df_2026.empty:
    fig_yoy.add_trace(go.Scatter(
        x=df_2026["date"].dt.dayofyear,
        y=df_2026["level_m"],
        mode="lines",
        name="2026",
        line=dict(color="#1E90FF", width=2.8),
        hovertemplate="2026 · Day %{x}: %{y:.3f} m<extra></extra>",
    ))

fig_yoy.add_hline(
    y=LEVEL_LEGAL_MIN, line_dash="dash", line_color="#EF5350", line_width=1,
    annotation_text="Lower Mgmt −213.0 m",
    annotation_position="bottom right",
    annotation_font=dict(color="#EF5350", size=10),
)
fig_yoy.add_hline(
    y=LEVEL_LEGAL_MAX, line_dash="dash", line_color="#66BB6A", line_width=1,
    annotation_text="Upper Mgmt −208.9 m",
    annotation_position="top right",
    annotation_font=dict(color="#66BB6A", size=10),
)

fig_yoy.update_layout(
    template="plotly_dark",
    height=280,
    margin=dict(l=10, r=10, t=12, b=30),
    xaxis=dict(
        title=dict(text="Day of Year", font=dict(size=11)),
        tickmode="array",
        tickvals=[1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335],
        ticktext=["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"],
        showgrid=True, gridcolor="rgba(255,255,255,0.04)",
        tickfont=dict(size=10),
    ),
    yaxis=dict(
        title=dict(text="Level (m MSL)", font=dict(size=11)),
        showgrid=True, gridcolor="rgba(255,255,255,0.04)",
        tickfont=dict(size=10),
    ),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
        font=dict(size=10), bgcolor="rgba(0,0,0,0)",
    ),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_yoy, width='stretch')

# ── Quick-nav ─────────────────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.subheader("Explore the Dashboard")
st.markdown(
    '<div class="kn-nav-hint">Select a page to dive deeper into the data and model</div>',
    unsafe_allow_html=True,
)

nc1, nc2, nc3 = st.columns(3)
with nc1:
    st.page_link("pages/1_Data_Sources.py",       label="📋  Data Sources",       help="Where the data comes from")
    st.page_link("pages/4_Model_Info.py",          label="🧠  Model Info",          help="Architecture and CV performance")
with nc2:
    st.page_link("pages/2_Pipeline.py",            label="⚙️  Data Pipeline",       help="ETL scripts and data layers")
    st.page_link("pages/5_Forecast_Historical.py", label="🔍  Historical Forecast", help="Validate the model on any past week")
with nc3:
    st.page_link("pages/3_Statistics.py",          label="📊  Statistics & EDA",    help="Explore the feature table")
    st.page_link("pages/6_Forecast_Live.py",       label="🔮  Live Forecast",       help="Predict the next 7 days")
