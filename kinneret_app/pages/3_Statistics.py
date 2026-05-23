import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from app_utils import load_gold, COLOURS


def _distplot(data_list, labels, colors, bin_size=None):
    fig = go.Figure()
    for arr_raw, label, color in zip(data_list, labels, colors):
        arr = np.asarray(arr_raw, dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) < 5:
            continue
        bs = bin_size if (bin_size and bin_size > 0) else max((arr.max() - arr.min()) / 40, 1e-9)
        fig.add_trace(go.Histogram(
            x=arr, name=label, marker_color=color, opacity=0.45,
            xbins=dict(size=bs), histnorm="probability density",
        ))
        n = len(arr)
        bw = 1.06 * arr.std() * n**(-0.2)
        if bw > 0:
            x_kde = np.linspace(arr.min() - 3 * bw, arr.max() + 3 * bw, 300)
            diff = x_kde[:, None] - arr[None, :]
            kde = np.exp(-0.5 * (diff / bw) ** 2).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))
            fig.add_trace(go.Scatter(
                x=x_kde, y=kde, name=f"{label} KDE", mode="lines",
                line=dict(color=color, width=2), showlegend=False,
            ))
    return fig

st.set_page_config(
    page_title="Statistics & EDA · Kinneret",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
.block-container { padding-top: 1.4rem; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }
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
    margin: 1.2rem 0;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 Statistics & EDA")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'Interactive exploration of the gold feature table'
    '</div>',
    unsafe_allow_html=True,
)

gold = load_gold()
numeric_cols = gold.select_dtypes(include=np.number).columns.tolist()

# Column groupings
GROUPS = {
    "Seasonality":  ["season_sin","season_cos","solar_declination_rad","daylength_hrs",
                     "rbf_spring_equinox","rbf_summer_solstice","rbf_autumn_equinox","rbf_winter_solstice"],
    "Met Raw":      ["temp_max_C","temp_min_C","temp_mean_C","humidity_pct",
                     "wind_speed_ms","rainfall_mm","radiation_MJm2"],
    "Met Derived":  ["et0_mm","vpd_kPa","et0_7d_mm","et0_rolling14",
                     "moisture_balance_7d_mm","moisture_balance_14d_mm",
                     "rainfall_7d_mm","rainfall_14d_mm","rainfall_21d_mm",
                     "rainfall_lag1_mm","rainfall_lag2_mm","rainfall_lag3_mm"],
    "River Flows":  ["inflow_obstacle_m3","inflow_lag1_m3","inflow_lag2_m3",
                     "volume_change_Mm3","volume_change_lag1_Mm3","volume_change_lag2_Mm3"],
    "Lake State":   ["level_m","volume_Mm3","predicted_inflow_m3"],
}

def group_of(col):
    for g, cols in GROUPS.items():
        if col in cols:
            return g
    return "Other"

tab1, tab2, tab3, tab4 = st.tabs(
    ["Feature Profiler", "Correlation", "Distributions", "Seasonal Patterns"]
)

# ── Tab 1: Feature Profiler ───────────────────────────────────────────────────
with tab1:
    summary_rows = []
    for col in numeric_cols:
        s = gold[col].dropna()
        if len(s) == 0:
            continue
        summary_rows.append({
            "Column":   col,
            "Group":    group_of(col),
            "Non-null": int(s.count()),
            "Mean":     round(float(s.mean()), 4),
            "Std":      round(float(s.std()),  4),
            "Min":      round(float(s.min()),  4),
            "P25":      round(float(s.quantile(0.25)), 4),
            "Median":   round(float(s.median()), 4),
            "P75":      round(float(s.quantile(0.75)), 4),
            "Max":      round(float(s.max()),  4),
            "Skew":     round(float(s.skew()), 3),
            "Kurt":     round(float(s.kurtosis()), 3),
        })
    summary_df = pd.DataFrame(summary_rows)

    selected_col = st.selectbox("Select a feature to inspect:", numeric_cols,
                                index=numeric_cols.index("level_m") if "level_m" in numeric_cols else 0)
    st.dataframe(summary_df, width='stretch', hide_index=True, height=220)

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    col_data = gold[selected_col].dropna()

    pc1, pc2 = st.columns(2)
    with pc1:
        # Histogram + KDE
        fig_hist = _distplot(
            [col_data.values.tolist()], [selected_col],
            [COLOURS["predicted"]],
            bin_size=(col_data.max() - col_data.min()) / 40 if col_data.std() > 0 else 1,
        )
        fig_hist.update_layout(
            template="plotly_dark", height=220,
            margin=dict(l=10, r=10, t=10, b=20),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_hist, width='stretch')

    with pc2:
        # Box plot
        fig_box = go.Figure(go.Box(
            y=col_data, name=selected_col,
            marker_color=COLOURS["predicted"],
            boxmean="sd",
        ))
        fig_box.update_layout(
            template="plotly_dark", height=220,
            margin=dict(l=10, r=10, t=10, b=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_box, width='stretch')

    # Monthly time series
    monthly = gold[["date", selected_col]].copy()
    monthly["month"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
    monthly_agg = monthly.groupby("month")[selected_col].mean().reset_index()
    fig_ts = go.Figure(go.Scatter(
        x=monthly_agg["month"], y=monthly_agg[selected_col],
        mode="lines", line=dict(color=COLOURS["predicted"], width=1.5),
    ))
    fig_ts.update_layout(
        template="plotly_dark", height=180, title=f"{selected_col} — Monthly Mean",
        margin=dict(l=10, r=10, t=30, b=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_ts, width='stretch')

# ── Tab 2: Correlation ────────────────────────────────────────────────────────
with tab2:
    corr_cols = [c for c in numeric_cols if gold[c].notna().sum() > 100]
    corr = gold[corr_cols].corr()

    fig_corr = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        colorbar=dict(thickness=12, len=0.8),
        hovertemplate="%{y} vs %{x}: %{z:.3f}<extra></extra>",
    ))
    fig_corr.update_layout(
        template="plotly_dark", height=500,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(tickfont=dict(size=8), tickangle=-45),
        yaxis=dict(tickfont=dict(size=8)),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_corr, width='stretch')

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="kn-label">Feature Pair Scatter</div>', unsafe_allow_html=True)

    sc1, sc2 = st.columns(2)
    with sc1:
        feat_a = st.selectbox("Feature A", corr_cols,
                              index=corr_cols.index("rainfall_7d_mm") if "rainfall_7d_mm" in corr_cols else 0)
    with sc2:
        feat_b = st.selectbox("Feature B", corr_cols,
                              index=corr_cols.index("inflow_obstacle_m3") if "inflow_obstacle_m3" in corr_cols else 1)

    pair = gold[["date", feat_a, feat_b]].dropna()
    pair["season"] = pair["date"].dt.month.apply(
        lambda m: "winter" if m in [10,11,12,1,2,3] else "summer"
    )
    r_val = float(np.corrcoef(pair[feat_a], pair[feat_b])[0, 1])

    fig_sc = go.Figure()
    for season, colour in [("winter", COLOURS["winter"]), ("summer", COLOURS["summer"])]:
        mask = pair["season"] == season
        fig_sc.add_trace(go.Scatter(
            x=pair.loc[mask, feat_a], y=pair.loc[mask, feat_b],
            mode="markers", name=season.capitalize(),
            marker=dict(color=colour, size=3, opacity=0.5),
        ))
    # Trendline
    m, b = np.polyfit(pair[feat_a], pair[feat_b], 1)
    x_rng = np.linspace(pair[feat_a].min(), pair[feat_a].max(), 100)
    fig_sc.add_trace(go.Scatter(
        x=x_rng, y=m * x_rng + b, mode="lines",
        line=dict(color="#BDBDBD", width=1.5, dash="dot"),
        name=f"Trend (r={r_val:.3f})", showlegend=True,
    ))
    fig_sc.update_layout(
        template="plotly_dark", height=280,
        margin=dict(l=10, r=10, t=10, b=20),
        xaxis_title=feat_a, yaxis_title=feat_b,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_sc, width='stretch')
    st.caption(f"Pearson r = {r_val:.4f} | n = {len(pair):,}")

# ── Tab 3: Distributions ──────────────────────────────────────────────────────
with tab3:
    dc1, dc2 = st.columns([1, 3])
    with dc1:
        group_choice = st.radio("Column group", list(GROUPS.keys()) + ["Other"])
        grp_cols = [c for c in numeric_cols if group_of(c) == group_choice]
        if not grp_cols:
            grp_cols = numeric_cols
        dist_col = st.selectbox("Column", grp_cols)

        log_transform  = st.checkbox("Log transform (log1p)")
        split_season   = st.checkbox("Split by season")

    with dc2:
        dist_data = gold[dist_col].dropna()
        if log_transform and (dist_data > 0).all():
            dist_data = np.log1p(dist_data)
            xlabel = f"log1p({dist_col})"
        else:
            xlabel = dist_col

        if split_season:
            gold["_season"] = gold["date"].dt.month.apply(
                lambda m: "winter" if m in [10,11,12,1,2,3] else "summer"
            )
            winter_d = gold.loc[gold["_season"]=="winter", dist_col].dropna()
            summer_d = gold.loc[gold["_season"]=="summer", dist_col].dropna()
            if log_transform:
                winter_d = np.log1p(winter_d[winter_d > 0])
                summer_d = np.log1p(summer_d[summer_d > 0])
            fig_dist = _distplot(
                [winter_d.values.tolist(), summer_d.values.tolist()],
                ["Winter (Oct-Mar)", "Summer (Apr-Sep)"],
                [COLOURS["winter"], COLOURS["summer"]],
                bin_size=(dist_data.max()-dist_data.min())/40 if dist_data.std()>0 else 1,
            )
            fig_dist.update_layout(barmode="overlay")
        else:
            fig_dist = _distplot(
                [dist_data.values.tolist()], [xlabel],
                [COLOURS["predicted"]],
                bin_size=(dist_data.max()-dist_data.min())/40 if dist_data.std()>0 else 1,
            )

        fig_dist.update_layout(
            template="plotly_dark", height=280,
            margin=dict(l=10, r=10, t=10, b=20),
            xaxis_title=xlabel,
            legend=dict(orientation="h", yanchor="bottom", y=1.01),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_dist, width='stretch')

        raw = gold[dist_col].dropna()
        st.caption(
            f"n={len(raw):,} | Mean={raw.mean():.3f} | Std={raw.std():.3f} | "
            f"Skew={raw.skew():.3f} | Kurt={raw.kurtosis():.3f}"
        )

# ── Tab 4: Seasonal Patterns ──────────────────────────────────────────────────
with tab4:
    gold["_year"]  = gold["date"].dt.year
    gold["_month"] = gold["date"].dt.month

    # Heatmap 1: level by year-month
    if "level_m" in gold.columns:
        level_pivot = gold.pivot_table(values="level_m", index="_year", columns="_month", aggfunc="mean")
        level_pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        fig_h1 = go.Figure(go.Heatmap(
            z=level_pivot.values,
            x=level_pivot.columns.tolist(),
            y=level_pivot.index.tolist(),
            colorscale="RdBu",
            zmid=float(gold["level_m"].mean()),
            colorbar=dict(thickness=12),
            hovertemplate="Year %{y} %{x}: %{z:.2f} m<extra></extra>",
        ))
        fig_h1.update_layout(
            template="plotly_dark", height=220,
            title="Monthly Mean Lake Level (m MSL)",
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_h1, width='stretch')

    # Heatmap 2: inflow by year-month
    if "inflow_obstacle_m3" in gold.columns:
        inflow_pivot = gold.pivot_table(values="inflow_obstacle_m3", index="_year", columns="_month", aggfunc="mean")
        inflow_pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        fig_h2 = go.Figure(go.Heatmap(
            z=inflow_pivot.values,
            x=inflow_pivot.columns.tolist(),
            y=inflow_pivot.index.tolist(),
            colorscale="Blues",
            colorbar=dict(thickness=12),
            hovertemplate="Year %{y} %{x}: %{z:,.0f} m³/day<extra></extra>",
        ))
        fig_h2.update_layout(
            template="plotly_dark", height=220,
            title="Monthly Mean Jordan River Inflow (m³/day)",
            margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_h2, width='stretch')

    # Seasonal decomposition
    if "level_m" in gold.columns:
        st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="kn-label">Seasonal Decomposition — Level</div>', unsafe_allow_html=True)

        lvl_ts = gold[["date","level_m"]].dropna().set_index("date").sort_index()
        trend  = lvl_ts["level_m"].rolling(365, min_periods=30, center=True).mean()
        resid  = lvl_ts["level_m"] - trend

        fig_decomp = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            subplot_titles=("Original", "Trend (365-day rolling)", "Residual"),
            vertical_spacing=0.08,
        )
        fig_decomp.add_trace(go.Scatter(x=lvl_ts.index, y=lvl_ts["level_m"],
                                        mode="lines", line=dict(color=COLOURS["predicted"], width=1),
                                        name="Original"), row=1, col=1)
        fig_decomp.add_trace(go.Scatter(x=trend.index, y=trend,
                                        mode="lines", line=dict(color="#66BB6A", width=1.5),
                                        name="Trend"), row=2, col=1)
        fig_decomp.add_trace(go.Scatter(x=resid.index, y=resid,
                                        mode="lines", line=dict(color="#FF7043", width=0.8),
                                        name="Residual"), row=3, col=1)

        fig_decomp.update_layout(
            template="plotly_dark", height=400,
            margin=dict(l=10, r=10, t=30, b=20),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_decomp, width='stretch')
