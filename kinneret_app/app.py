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
from theme import inject_theme, style_plotly, PALETTE

st.set_page_config(
    page_title="Kinneret Forecast",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()

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
if dist_lower >= 0:
    _chip_clr, _chip_bg = PALETTE["leaf"], "rgba(134,224,90,0.12)"
    _chip_txt = f"↑ {dist_lower:.2f} m above the red line"
else:
    _chip_clr, _chip_bg = PALETTE["ember"], "rgba(255,107,53,0.14)"
    _chip_txt = f"↓ {abs(dist_lower):.2f} m BELOW the red line"

st.markdown(
    f"""
    <div style="margin:0.2rem 0 1.4rem;">
      <div style="font-family:var(--mono);font-size:0.72rem;letter-spacing:0.3em;
                  text-transform:uppercase;color:{PALETTE['aqua']};margin-bottom:0.5rem;">
        Sea of Galilee &nbsp;/&nbsp; Lake Kinneret
      </div>
      <h1 style="margin:0;">Between Flood<br>&amp; Drought</h1>
      <div class="kn-subtitle" style="margin-top:1.1rem;">
        Water resource monitor &nbsp;·&nbsp; 7-day level forecast &nbsp;·&nbsp;
        Last reading {gold_max_date.strftime('%d %b %Y')}
      </div>
      <span style="display:inline-block;font-family:var(--mono);font-size:0.78rem;
                   font-weight:700;letter-spacing:0.04em;color:{_chip_clr};
                   background:{_chip_bg};border:1px solid {_chip_clr}55;
                   border-radius:999px;padding:0.34rem 0.95rem;">
        {_chip_txt}
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)

if current_level < LEVEL_LEGAL_MIN:
    st.error("⚠️  Lake is below the lower management (red) line.")

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
style_plotly(fig_spark, height=180)
st.plotly_chart(fig_spark, width='stretch', config={"displayModeBar": False})

# ── Year-over-year overlay ────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="kn-label">Year-over-Year Comparison</div>', unsafe_allow_html=True)

fig_yoy = go.Figure()

past_year_styles = {
    2020: ("rgba(11, 110, 107, 0.55)", "dot"),
    2021: ("rgba(20, 140, 130, 0.60)", "longdash"),
    2022: ("rgba(30, 170, 155, 0.65)", "dashdot"),
    2023: ("rgba(43, 200, 180, 0.70)", "dash"),
    2024: ("rgba(90, 220, 205, 0.78)", "longdashdot"),
    2025: ("rgba(140, 240, 225, 0.88)", "solid"),
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
        line=dict(color=COLOURS["predicted"], width=3.2),
        hovertemplate="2026 · Day %{x}: %{y:.3f} m<extra></extra>",
    ))

fig_yoy.add_hline(
    y=LEVEL_LEGAL_MIN, line_dash="dash", line_color=COLOURS["legal_min"], line_width=1.2,
    annotation_text="Red line −213.0 m",
    annotation_position="bottom right",
    annotation_font=dict(color=COLOURS["legal_min"], size=10),
)
fig_yoy.add_hline(
    y=LEVEL_LEGAL_MAX, line_dash="dash", line_color=COLOURS["legal_max"], line_width=1.2,
    annotation_text="Spill line −208.9 m",
    annotation_position="top right",
    annotation_font=dict(color=COLOURS["legal_max"], size=10),
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
style_plotly(fig_yoy, height=280)
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
