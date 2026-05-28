import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta
from app_utils import (
    load_gold, load_models, run_forecast_from_df, vol_to_level,
    COLOURS, LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX, PROJECT_ROOT,
)
from ims_forecast import fetch_tiberias_7day

st.set_page_config(
    page_title="Live Forecast · Kinneret",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
.block-container { padding-top: 1.4rem; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }
[data-testid="metric-container"] {
    background: #1A1D27;
    border: 1px solid rgba(30,144,255,0.18);
    border-left: 3px solid rgba(30,144,255,0.5);
    border-radius: 8px;
    padding: 0.8rem 1rem 0.6rem;
    margin-bottom: 0.5rem;
}
[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 1.4rem !important;
    color: #E8EEFF !important;
}
[data-testid="stMetricLabel"] > div {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #5B88C5 !important;
}
.kn-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(30,144,255,0.22), transparent);
    margin: 1.4rem 0;
}
.kn-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.14em;
    color: #7BA3D4;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.state-banner {
    background: #1A1D27;
    border: 1px solid rgba(30,144,255,0.2);
    border-radius: 8px;
    padding: 0.75rem 1.1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.83rem;
    color: #B0C4E8;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🔮 Live Forecast — Next 7 Days")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'Enter next week\'s weather forecast · Model predicts lake level trajectory'
    '</div>',
    unsafe_allow_html=True,
)

gold = load_gold()
gb1, gb2_direct, meta = load_models()
bathy = meta.get("bathy_vol2level_coeffs", [])

last_valid = gold.dropna(subset=["level_m", "volume_Mm3"]).iloc[-1]
last_date  = gold["date"].max()
last_level = float(last_valid["level_m"])
last_vol   = float(last_valid["volume_Mm3"])

fc_start = last_date + pd.Timedelta(days=1)
fc_dates = [fc_start + pd.Timedelta(days=i) for i in range(7)]

# ── Current state banner ───────────────────────────────────────────────────────
st.markdown(
    f'<div class="state-banner">'
    f'<b>Current state:</b> &nbsp; Last reading: {last_date.date().strftime("%d %b %Y")} &nbsp;·&nbsp; '
    f'Level: <span style="color:#1E90FF">{last_level:+.3f} m MSL</span> &nbsp;·&nbsp; '
    f'Volume: {last_vol:,.0f} Mm³<br>'
    f'<b>Forecasting:</b> &nbsp; '
    f'{fc_dates[0].strftime("%d %b")} &rarr; {fc_dates[-1].strftime("%d %b %Y")}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Default / template weather data ───────────────────────────────────────────
def _default_fc_df() -> pd.DataFrame:
    template_path = PROJECT_ROOT / "forecast_input_template.csv"
    if template_path.exists():
        try:
            df = pd.read_csv(template_path)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").head(7).reset_index(drop=True)
            df["date"] = fc_dates[:len(df)]
            return df
        except Exception:
            pass
    return pd.DataFrame({
        "date":           fc_dates,
        "temp_max_C":     [28.0] * 7,
        "temp_min_C":     [18.0] * 7,
        "rainfall_mm":    [0.0]  * 7,
        "humidity_pct":   [55.0] * 7,
        "wind_speed_ms":  [3.0]  * 7,
        "radiation_MJm2": [22.0] * 7,
    })

def _last7_df() -> pd.DataFrame:
    cutoff = last_date - pd.Timedelta(days=7)
    hist7 = gold[gold["date"] > cutoff].copy().reset_index(drop=True)
    hist7["date"] = fc_dates[:len(hist7)]
    return hist7[["date","temp_max_C","temp_min_C","rainfall_mm",
                  "humidity_pct","wind_speed_ms","radiation_MJm2"]]

# Session-state for editor
if "fc_data" not in st.session_state:
    st.session_state.fc_data = _default_fc_df()

# ── Buttons ────────────────────────────────────────────────────────────────────
b1, b2, b3, b4 = st.columns(4)
with b1:
    if st.button("Load template", width='stretch'):
        st.session_state.fc_data = _default_fc_df()
        st.rerun()
with b2:
    if st.button("Clear (zeros)", width='stretch'):
        df_zero = pd.DataFrame({
            "date": fc_dates, "temp_max_C": [0.0]*7, "temp_min_C": [0.0]*7,
            "rainfall_mm": [0.0]*7, "humidity_pct": [50.0]*7,
            "wind_speed_ms": [2.0]*7, "radiation_MJm2": [0.0]*7,
        })
        st.session_state.fc_data = df_zero
        st.rerun()
with b3:
    if st.button("Use last 7 days as test", width='stretch'):
        st.session_state.fc_data = _last7_df()
        st.rerun()
with b4:
    if st.button("Fetch from IMS", width='stretch'):
        with st.spinner("Fetching IMS forecast…"):
            try:
                st.session_state.fc_data = fetch_tiberias_7day(fc_dates)
                st.rerun()
            except Exception as e:
                st.error(f"IMS fetch failed: {e}")

# ── Weather input editor ───────────────────────────────────────────────────────
st.markdown('<div class="kn-label">Weather Forecast Input</div>', unsafe_allow_html=True)

editor_df = st.session_state.fc_data.copy()
editor_df["date"] = editor_df["date"].apply(
    lambda d: d.date() if hasattr(d, "date") else d
)

edited = st.data_editor(
    editor_df,
    width='stretch',
    hide_index=True,
    column_config={
        "date":           st.column_config.DateColumn("Date", disabled=True),
        "temp_max_C":     st.column_config.NumberColumn("Max Temp (°C)", format="%.1f"),
        "temp_min_C":     st.column_config.NumberColumn("Min Temp (°C)", format="%.1f"),
        "rainfall_mm":    st.column_config.NumberColumn("Rain (mm)", format="%.1f"),
        "humidity_pct":   st.column_config.NumberColumn("Humidity (%)", format="%.1f"),
        "wind_speed_ms":  st.column_config.NumberColumn("Wind (m/s)", format="%.1f"),
        "radiation_MJm2": st.column_config.NumberColumn("Radiation (MJ/m²)", format="%.1f"),
    },
)
edited["date"] = pd.to_datetime(edited["date"])

# ── Run button ─────────────────────────────────────────────────────────────────
run_col, _ = st.columns([1, 3])
with run_col:
    run_btn = st.button("Run Forecast ▶", type="primary", width='stretch')

# ── What-if sliders ────────────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="kn-label">What-If Scenario</div>', unsafe_allow_html=True)

sc1, sc2 = st.columns(2)
with sc1:
    rain_mult = st.slider(
        "Rainfall multiplier",
        min_value=0.0, max_value=3.0, value=1.0, step=0.1,
        help="Scale all 7 days' rainfall by this factor",
    )
with sc2:
    temp_offset = st.slider(
        "Temperature offset (°C)",
        min_value=-5.0, max_value=5.0, value=0.0, step=0.5,
        help="Add this offset to max/min temperatures",
    )

has_whatif = (rain_mult != 1.0) or (temp_offset != 0.0)

# ── Forecast engine ────────────────────────────────────────────────────────────
def _run(fc_df: pd.DataFrame):
    history_df = gold.tail(21).reset_index(drop=True)
    return run_forecast_from_df(fc_df, history_df, gb1, gb2_direct, meta)

if run_btn:
    st.session_state.base_results = None
    st.session_state.whatif_results = None

    with st.spinner("Running base forecast..."):
        try:
            res, s_lvl, s_vol, e_lvl, e_vol = _run(edited)
            st.session_state.base_results = (res, s_lvl, s_vol, e_lvl, e_vol)
        except Exception as ex:
            st.error(f"Forecast failed: {ex}")

    if has_whatif and st.session_state.base_results:
        with st.spinner("Running what-if scenario..."):
            wi_df = edited.copy()
            wi_df["rainfall_mm"] = wi_df["rainfall_mm"] * rain_mult
            wi_df["temp_max_C"]  = wi_df["temp_max_C"]  + temp_offset
            wi_df["temp_min_C"]  = wi_df["temp_min_C"]  + temp_offset
            try:
                wi_res, *_ = _run(wi_df)
                st.session_state.whatif_results = wi_res
            except Exception as ex:
                st.warning(f"What-if scenario failed: {ex}")

# ── Display results ────────────────────────────────────────────────────────────
if "base_results" in st.session_state and st.session_state.base_results:
    res, s_lvl, s_vol, e_lvl, e_vol = st.session_state.base_results
    res_df = pd.DataFrame(res)
    res_df["date"] = pd.to_datetime(res_df["date"])

    delta_level = e_lvl - s_lvl
    if   delta_level >  0.01: trend = "▲ RISING"
    elif delta_level < -0.01: trend = "▼ FALLING"
    else:                     trend = "— STABLE"

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

    # Summary metrics
    sm1, sm2, sm3, sm4 = st.columns(4)
    with sm1:
        st.metric("Anchor Level",      f"{s_lvl:+.3f} m MSL")
    with sm2:
        st.metric("End-of-Week Level", f"{e_lvl:+.3f} m MSL")
    with sm3:
        st.metric("Weekly Change",     f"{delta_level:+.3f} m")
    with sm4:
        st.metric("Trend",             trend)

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

    # Stage 1 — inflow bar chart
    with st.expander("Stage 1 — Predicted Inflow", expanded=True):
        fig_inf = go.Figure(go.Bar(
            x=res_df["date"],
            y=res_df["pred_inflow_Mm3"],
            marker_color=COLOURS["predicted"],
            hovertemplate="%{x|%b %d}: %{y:.3f} Mm³/day<extra></extra>",
        ))
        fig_inf.update_layout(
            template="plotly_dark", height=200,
            margin=dict(l=10, r=10, t=8, b=25),
            xaxis=dict(tickformat="%b %d", showgrid=False),
            yaxis=dict(title="Inflow (Mm³/day)", showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_inf, width='stretch')

        # Lag-chain table
        chain_rows = []
        lag1_init = gold.dropna(subset=["inflow_obstacle_m3"]).iloc[-1]["inflow_obstacle_m3"]
        lag1 = lag1_init
        for r in res:
            chain_rows.append({
                "Day": r["day"],
                "Date": r["date"],
                "Input lag1 (Mm³)": f"{lag1/1e6:.3f}",
                "Pred Inflow (Mm³)": f"{r['pred_inflow_Mm3']:.3f}",
            })
            lag1 = r["pred_inflow_Mm3"] * 1e6
        st.dataframe(pd.DataFrame(chain_rows), width='stretch', hide_index=True)

    # Stage 2 — level chart
    with st.expander("Stage 2 — Level Prediction", expanded=True):
        # Uncertainty band: propagate 0.654 Mm3/day MAE approximately
        level_uncertainty = 0.654 / 300

        # Naïve baseline (flat from anchor)
        baseline_dates = [res_df["date"].min() - pd.Timedelta(days=1)] + list(res_df["date"])
        baseline_vals  = [s_lvl] * len(baseline_dates)

        fig_lvl = go.Figure()

        # Confidence band
        fig_lvl.add_trace(go.Scatter(
            x=pd.concat([res_df["date"], res_df["date"].iloc[::-1]]),
            y=pd.concat([
                res_df["pred_level_m"] + level_uncertainty,
                (res_df["pred_level_m"] - level_uncertainty).iloc[::-1],
            ]),
            fill="toself",
            fillcolor=COLOURS["band"],
            line=dict(color="rgba(0,0,0,0)"),
            name="Uncertainty band",
            hoverinfo="skip",
        ))

        # Baseline
        fig_lvl.add_trace(go.Scatter(
            x=baseline_dates, y=baseline_vals,
            mode="lines", name="Flat baseline",
            line=dict(color="#BDBDBD", width=1.2, dash="dot"),
            hoverinfo="skip",
        ))

        # Base forecast
        fig_lvl.add_trace(go.Scatter(
            x=res_df["date"], y=res_df["pred_level_m"],
            mode="lines+markers", name="Base forecast",
            line=dict(color=COLOURS["predicted"], width=2.5),
            marker=dict(size=5),
            hovertemplate="%{x|%b %d}: %{y:+.3f} m<extra>Base</extra>",
        ))

        # What-if overlay
        if "whatif_results" in st.session_state and st.session_state.whatif_results:
            wi_df = pd.DataFrame(st.session_state.whatif_results)
            wi_df["date"] = pd.to_datetime(wi_df["date"])
            fig_lvl.add_trace(go.Scatter(
                x=wi_df["date"], y=wi_df["pred_level_m"],
                mode="lines+markers", name="What-if forecast",
                line=dict(color="#FF7043", width=2, dash="dash"),
                marker=dict(size=4),
                hovertemplate="%{x|%b %d}: %{y:+.3f} m<extra>What-if</extra>",
            ))

        fig_lvl.add_hline(y=LEVEL_LEGAL_MIN, line_dash="dash", line_color="#EF5350",
                          line_width=1, annotation_text="Lower Mgmt -213.0 m",
                          annotation_font=dict(color="#EF5350", size=9))
        fig_lvl.add_hline(y=LEVEL_LEGAL_MAX, line_dash="dash", line_color="#66BB6A",
                          line_width=1, annotation_text="Upper Mgmt -208.9 m",
                          annotation_font=dict(color="#66BB6A", size=9))

        # Annotation box
        fig_lvl.add_annotation(
            x=res_df["date"].iloc[-1], y=res_df["pred_level_m"].iloc[-1],
            text=f"End: {e_lvl:+.3f} m  {trend}",
            showarrow=True, arrowhead=2, arrowcolor=COLOURS["predicted"],
            bgcolor="#1A1D27", bordercolor=COLOURS["predicted"],
            font=dict(color="#E0E0E0", size=10),
            xanchor="left",
        )

        fig_lvl.update_layout(
            template="plotly_dark", height=300,
            margin=dict(l=10, r=10, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            xaxis=dict(tickformat="%b %d", showgrid=False),
            yaxis=dict(title="Level (m MSL)", showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_lvl, width='stretch')

        # Results table for download
        dl_df = res_df[["day","date","rain_mm","temp_mean_C","pred_inflow_Mm3",
                         "pred_dvol_Mm3","cum_dvol_Mm3","pred_level_m","pred_volume_Mm3"]].copy()
        dl_df["date"] = dl_df["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(dl_df.rename(columns={
            "day":"Day","date":"Date","rain_mm":"Rain (mm)","temp_mean_C":"Temp (C)",
            "pred_inflow_Mm3":"Inflow (Mm3)","pred_dvol_Mm3":"dVol (Mm3)",
            "cum_dvol_Mm3":"Cum dVol","pred_level_m":"Level (m)","pred_volume_Mm3":"Volume (Mm3)",
        }), width='stretch', hide_index=True)

        st.download_button(
            label="Download forecast CSV",
            data=dl_df.to_csv(index=False).encode("utf-8"),
            file_name=f"kinneret_forecast_{fc_dates[0].strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
