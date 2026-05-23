import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta
from app_utils import (
    load_gold, load_models, run_forecast_from_df,
    COLOURS, LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX, PROJECT_ROOT,
)

st.set_page_config(
    page_title="Historical Forecast · Kinneret",
    page_icon="🔍",
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
    margin: 1.4rem 0;
}
.anchor-box {
    background: #1A1D27;
    border: 1px solid rgba(30,144,255,0.2);
    border-radius: 8px;
    padding: 0.8rem 1.1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.82rem;
    color: #B0C4E8;
    margin-bottom: 0.8rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🔍 Historical Forecast Validation")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'Run the model on any past week · Compare predictions to actual readings'
    '</div>',
    unsafe_allow_html=True,
)

gold = load_gold()
gb1, gb2_direct, meta = load_models()

gold_min = gold["date"].min().date()
gold_max = gold["date"].max().date()
max_anchor = gold_max - timedelta(days=8)

# ── Controls ──────────────────────────────────────────────────────────────────
col_ctrl, col_info = st.columns([2, 3])

with col_ctrl:
    anchor_date = st.date_input(
        "Anchor date (Day 0 — forecast runs Days 1–7 after this date)",
        value=date(2024, 1, 15),
        min_value=gold_min + timedelta(days=21),
        max_value=max_anchor,
    )

    anchor_ts = pd.Timestamp(anchor_date)
    anchor_row = gold[gold["date"] <= anchor_ts].dropna(subset=["level_m", "volume_Mm3"])

    if len(anchor_row):
        anchor_level  = float(anchor_row.iloc[-1]["level_m"])
        anchor_volume = float(anchor_row.iloc[-1]["volume_Mm3"])
        st.markdown(
            f'<div class="anchor-box">'
            f'Anchor state on {anchor_date.strftime("%d %b %Y")}<br>'
            f'<span style="color:#1E90FF;font-size:1.05rem;">{anchor_level:+.3f} m MSL</span>'
            f'&nbsp;&nbsp;·&nbsp;&nbsp;{anchor_volume:,.0f} Mm³'
            f'</div>',
            unsafe_allow_html=True,
        )

    run_btn = st.button("Run Forecast ▶", type="primary", width='stretch')

# ── Forecast execution ────────────────────────────────────────────────────────
if run_btn:
    with st.spinner("Running two-stage forecast..."):
        # Build history (21 days up to and including anchor date)
        history_df = (
            gold[gold["date"] <= anchor_ts]
            .tail(21)
            .reset_index(drop=True)
        )

        # Build forecast_df: next 7 days from gold (actual weather)
        fc_start = anchor_ts + pd.Timedelta(days=1)
        fc_end   = anchor_ts + pd.Timedelta(days=7)
        fc_gold  = gold[(gold["date"] >= fc_start) & (gold["date"] <= fc_end)].copy()

        if len(fc_gold) < 7:
            st.warning(
                f"Only {len(fc_gold)} days of actual data found after anchor date "
                f"(need 7). Results may be incomplete."
            )

        # Rename gold columns to match forecast_df schema
        fc_cols = {
            "temp_max_C": "temp_max_C",
            "temp_min_C": "temp_min_C",
            "rainfall_mm": "rainfall_mm",
            "humidity_pct": "humidity_pct",
            "wind_speed_ms": "wind_speed_ms",
            "radiation_MJm2": "radiation_MJm2",
        }
        forecast_df = fc_gold[["date"] + [c for c in fc_cols if c in fc_gold.columns]].copy()

        # Run forecast
        results, s_lvl, s_vol, e_lvl, e_vol = run_forecast_from_df(
            forecast_df, history_df, gb1, gb2_direct, meta
        )

        res_df = pd.DataFrame(results)
        res_df["date"] = pd.to_datetime(res_df["date"])

        # Join actuals from gold
        actuals = gold[["date", "level_m", "inflow_obstacle_m3"]].copy()
        actuals = actuals.rename(columns={
            "level_m": "actual_level_m",
            "inflow_obstacle_m3": "actual_inflow_m3",
        })
        res_df = res_df.merge(actuals, on="date", how="left")

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

    # ── Accuracy summary ──────────────────────────────────────────────────────
    valid_level  = res_df.dropna(subset=["actual_level_m"])
    valid_inflow = res_df.dropna(subset=["actual_inflow_m3"])

    mae_level  = float(np.mean(np.abs(valid_level["pred_level_m"] - valid_level["actual_level_m"]))) if len(valid_level) else float("nan")
    mae_inflow = float(np.mean(np.abs(valid_inflow["pred_inflow_Mm3"] - valid_inflow["actual_inflow_m3"] / 1e6))) if len(valid_inflow) else float("nan")
    pred_delta  = e_lvl - s_lvl if (e_lvl and s_lvl) else float("nan")
    actual_delta = (float(valid_level.iloc[-1]["actual_level_m"]) - float(valid_level.iloc[0]["actual_level_m"])) if len(valid_level) >= 2 else float("nan")

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric(
            "Stage 1 · Inflow MAE",
            f"{mae_inflow:.3f} Mm³/day" if not np.isnan(mae_inflow) else "N/A",
            help=f"Based on {len(valid_inflow)} of 7 days with actual data",
        )
    with mc2:
        st.metric(
            "Stage 2 · Level MAE",
            f"{mae_level:.3f} m" if not np.isnan(mae_level) else "N/A",
            help=f"Based on {len(valid_level)} of 7 days with actual readings",
        )
    with mc3:
        if not np.isnan(pred_delta) and not np.isnan(actual_delta):
            st.metric(
                "Weekly Level Change",
                f"Pred {pred_delta:+.3f} m",
                delta=f"Actual {actual_delta:+.3f} m",
            )
        else:
            st.metric("Weekly Level Change", f"Pred {pred_delta:+.3f} m" if not np.isnan(pred_delta) else "N/A")

    n_avail = len(valid_level)
    st.caption(f"MAE computed on {n_avail} of 7 days with available actual readings.")

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

    # ── Stage 1: Inflow ───────────────────────────────────────────────────────
    with st.expander("Stage 1 — Inflow Predictions", expanded=True):
        fig_inflow = go.Figure()
        dates_str  = res_df["date"].dt.strftime("%b %d")
        offset     = 0.2

        fig_inflow.add_trace(go.Bar(
            x=res_df["date"] - pd.Timedelta(hours=9),
            y=res_df["pred_inflow_Mm3"],
            name="Predicted Inflow",
            marker_color=COLOURS["predicted"],
            width=0.35 * 86400000,
            hovertemplate="%{x|%b %d}: %{y:.3f} Mm³<extra>Predicted</extra>",
        ))
        if "actual_inflow_m3" in res_df.columns:
            actual_inflow_mm3 = res_df["actual_inflow_m3"] / 1e6
            fig_inflow.add_trace(go.Bar(
                x=res_df["date"] + pd.Timedelta(hours=9),
                y=actual_inflow_mm3,
                name="Actual Inflow",
                marker_color=COLOURS["actual"],
                width=0.35 * 86400000,
                hovertemplate="%{x|%b %d}: %{y:.3f} Mm³<extra>Actual</extra>",
            ))

        fig_inflow.update_layout(
            template="plotly_dark",
            barmode="group",
            height=220,
            margin=dict(l=10, r=10, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            xaxis=dict(tickformat="%b %d", showgrid=False),
            yaxis=dict(title="Inflow (Mm³/day)", showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_inflow, width='stretch')

        # Error table
        tbl = res_df[["day", "date", "pred_inflow_Mm3", "actual_inflow_m3"]].copy()
        tbl["date"] = tbl["date"].dt.strftime("%Y-%m-%d")
        tbl["actual_Mm3"] = tbl["actual_inflow_m3"] / 1e6
        tbl["error_pct"] = (
            (tbl["pred_inflow_Mm3"] - tbl["actual_Mm3"]).abs() / tbl["actual_Mm3"].abs() * 100
        ).where(tbl["actual_Mm3"].notna())
        tbl = tbl[["day", "date", "pred_inflow_Mm3", "actual_Mm3", "error_pct"]]
        tbl.columns = ["Day", "Date", "Pred Inflow (Mm³)", "Actual Inflow (Mm³)", "Error %"]
        tbl["Pred Inflow (Mm³)"] = tbl["Pred Inflow (Mm³)"].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        tbl["Actual Inflow (Mm³)"] = tbl["Actual Inflow (Mm³)"].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        tbl["Error %"] = tbl["Error %"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        st.dataframe(tbl, width='stretch', hide_index=True)

    # ── Stage 2: Level ────────────────────────────────────────────────────────
    with st.expander("Stage 2 — Level Predictions", expanded=True):
        mae_band = 0.654 / 300  # rough level uncertainty from Mm3 MAE

        fig_level = go.Figure()

        # Confidence band
        fig_level.add_trace(go.Scatter(
            x=pd.concat([res_df["date"], res_df["date"].iloc[::-1]]),
            y=pd.concat([
                res_df["pred_level_m"] + mae_band,
                res_df["pred_level_m"].iloc[::-1] - mae_band,
            ]),
            fill="toself",
            fillcolor=COLOURS["band"],
            line=dict(color="rgba(0,0,0,0)"),
            name="Uncertainty band",
            showlegend=True,
            hoverinfo="skip",
        ))

        fig_level.add_trace(go.Scatter(
            x=res_df["date"],
            y=res_df["pred_level_m"],
            mode="lines+markers",
            name="Predicted Level",
            line=dict(color=COLOURS["predicted"], width=2.2),
            marker=dict(size=5),
            hovertemplate="%{x|%b %d}: %{y:+.3f} m<extra>Predicted</extra>",
        ))

        if "actual_level_m" in res_df.columns and res_df["actual_level_m"].notna().any():
            fig_level.add_trace(go.Scatter(
                x=res_df["date"],
                y=res_df["actual_level_m"],
                mode="lines+markers",
                name="Actual Level",
                line=dict(color=COLOURS["actual"], width=1.8, dash="dot"),
                marker=dict(size=5),
                hovertemplate="%{x|%b %d}: %{y:+.3f} m<extra>Actual</extra>",
            ))

        fig_level.add_hline(y=LEVEL_LEGAL_MIN, line_dash="dash", line_color="#EF5350",
                            line_width=1, annotation_text="Lower Mgmt",
                            annotation_font=dict(color="#EF5350", size=9))
        fig_level.add_hline(y=LEVEL_LEGAL_MAX, line_dash="dash", line_color="#66BB6A",
                            line_width=1, annotation_text="Upper Mgmt",
                            annotation_font=dict(color="#66BB6A", size=9))

        fig_level.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(l=10, r=10, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            xaxis=dict(tickformat="%b %d", showgrid=False),
            yaxis=dict(title="Level (m MSL)", showgrid=True, gridcolor="rgba(255,255,255,0.04)"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_level, width='stretch')

        # Results table
        rtbl = res_df[["day", "date", "pred_level_m", "actual_level_m"]].copy()
        rtbl["date"] = rtbl["date"].dt.strftime("%Y-%m-%d")
        rtbl["error_m"] = (rtbl["pred_level_m"] - rtbl["actual_level_m"]).abs()
        rtbl.columns = ["Day", "Date", "Pred Level (m)", "Actual Level (m)", "Error (m)"]
        for col in ["Pred Level (m)", "Actual Level (m)", "Error (m)"]:
            rtbl[col] = rtbl[col].apply(lambda x: f"{x:+.3f}" if pd.notna(x) else "—")
        st.dataframe(rtbl, width='stretch', hide_index=True)
