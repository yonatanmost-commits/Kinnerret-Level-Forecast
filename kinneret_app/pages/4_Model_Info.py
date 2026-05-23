import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from app_utils import load_gold, load_models, PROJECT_ROOT, COLOURS

sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
from model_lib import S1_FEATURES, S2_DIRECT_FEATURES

st.set_page_config(
    page_title="Model Info · Kinneret",
    page_icon="🧠",
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
.arch-box {
    background: #1A1D27;
    border: 1px solid rgba(30,144,255,0.2);
    border-radius: 8px;
    padding: 1rem 1.1rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    color: #B0C4E8;
    height: 100%;
}
.arch-box h4 {
    font-family: 'Syne', sans-serif !important;
    font-size: 0.95rem;
    color: #1E90FF;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🧠 Model Info")
st.markdown(
    '<div style="font-family:\'DM Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:#7BA3D4;text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'Two-stage gradient boosting architecture · CV results · Feature importance · Residuals'
    '</div>',
    unsafe_allow_html=True,
)

gold = load_gold()
gb1, gb2_direct, meta = load_models()

# ── Section 1: Architecture ───────────────────────────────────────────────────
st.markdown('<div class="kn-label">Architecture Overview</div>', unsafe_allow_html=True)

ac1, ac2 = st.columns(2)

s1_r2  = meta.get("cv_s1_mean_r2",  0.914)
s1_mae = meta.get("cv_s1_mean_mae", 0.094)
s2_r2  = meta.get("cv_s2_mean_r2",  0.689)
s2_mae = meta.get("cv_s2_mean_mae", 0.654)

with ac1:
    with st.expander("Stage 1 — Inflow Predictor", expanded=True):
        st.markdown(f"""
**Input:** {len(S1_FEATURES)} features — rainfall lags, ET₀, VPD, seasonality, inflow autocorrelation

**Model:** GBRegressor · 250 trees · depth=4 · lr=0.05

**Output:** `predicted_inflow_m3` (m³/day)

**CV Performance:**
R² = `{s1_r2:.3f}` &nbsp;·&nbsp; MAE = `{s1_mae:.3f} Mm³/day`
""")
        st.code("  ".join(S1_FEATURES), language=None)

with ac2:
    with st.expander("Stage 2 — Volume Change (Direct)", expanded=True):
        st.markdown(f"""
**Input:** {len(S2_DIRECT_FEATURES)} features — met + Stage 1 inflow + **anchor state** (level₀, ΔVol₀) + horizon_h (1–7)

**Model:** GBRegressor · 250 trees · depth=4 · lr=0.05

**Output:** `volume_change_Mm3` per horizon

**CV Performance:**
R² = `{s2_r2:.3f}` &nbsp;·&nbsp; MAE = `{s2_mae:.3f} Mm³/day`
""")
        st.code("  ".join(S2_DIRECT_FEATURES), language=None)

st.info(
    "**Direct multi-step design:** The anchor state (level and ΔVol at Day 0) is frozen "
    "for the entire 7-day window. The model receives `horizon_h` (1–7) as a feature, "
    "so it learns that later horizons are harder. This eliminates cumulative chaining "
    "error — predictions for Day 7 are not built on top of Day 6 predictions."
)

st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

# ── Section 2: CV Results ─────────────────────────────────────────────────────
st.markdown('<div class="kn-label">Cross-Validation Results (Walk-Forward)</div>', unsafe_allow_html=True)

s1_folds_default = [
    {"year": 2021, "r2": 0.934, "mae": 0.097, "n": 352},
    {"year": 2022, "r2": 0.948, "mae": 0.090, "n": 340},
    {"year": 2023, "r2": 0.833, "mae": 0.100, "n": 311},
    {"year": 2024, "r2": 0.943, "mae": 0.089, "n": 346},
]
s2_folds_default = [
    {"year": 2021, "r2": 0.569, "mae": 0.698, "n": 352},
    {"year": 2022, "r2": 0.864, "mae": 0.577, "n": 340},
    {"year": 2023, "r2": 0.564, "mae": 0.681, "n": 311},
    {"year": 2024, "r2": 0.760, "mae": 0.661, "n": 346},
]
s1_folds = meta.get("cv_s1_folds", s1_folds_default)
s2_folds = meta.get("cv_s2_folds", s2_folds_default)

cv1, cv2 = st.columns(2)

def _cv_chart(folds, title, mean_r2, mean_mae):
    years = [str(f["year"]) for f in folds]
    r2s   = [f["r2"]  for f in folds]
    maes  = [f["mae"] for f in folds]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=years, y=r2s, name="R²",
                         marker_color=COLOURS["predicted"], opacity=0.85), secondary_y=False)
    fig.add_trace(go.Scatter(x=years, y=maes, name="MAE",
                             mode="lines+markers", line=dict(color=COLOURS["actual"], width=2),
                             marker=dict(size=7)), secondary_y=True)
    fig.add_hline(y=mean_r2, line_dash="dot", line_color="#66BB6A", line_width=1,
                  annotation_text=f"Mean R²={mean_r2:.3f}", secondary_y=False,
                  annotation_font=dict(color="#66BB6A", size=9))
    fig.update_layout(
        template="plotly_dark", height=220, title=title,
        margin=dict(l=10, r=10, t=35, b=20),
        legend=dict(
            orientation="v", xanchor="right", x=0.99,
            yanchor="top", y=0.99,
            bgcolor="rgba(20,25,40,0.7)", bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1, font=dict(size=10),
        ),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(title_text="R²", secondary_y=False)
    fig.update_yaxes(title_text="MAE", secondary_y=True)
    return fig

with cv1:
    st.plotly_chart(_cv_chart(s1_folds, "Stage 1 — Inflow", s1_r2, s1_mae), width='stretch')
with cv2:
    st.plotly_chart(_cv_chart(s2_folds, "Stage 2 — Volume Change", s2_r2, s2_mae), width='stretch')

st.caption(
    "2021 and 2023 are the hardest folds (drought-to-recovery transitions). "
    "The model trained on drier antecedent conditions generalises less well to anomalous wet years."
)

st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

# ── Section 3: Feature Importance ─────────────────────────────────────────────
st.markdown('<div class="kn-label">Feature Importance (Split-Count Proxy)</div>', unsafe_allow_html=True)

def _accumulate_node(node, arr):
    if node.feat == -1:
        return
    if 0 <= node.feat < len(arr):
        arr[node.feat] += 1
    _accumulate_node(node.left,  arr)
    _accumulate_node(node.right, arr)

def feature_importances(gb, feature_names):
    arr = np.zeros(len(feature_names))
    for tree in gb.trees_:
        _accumulate_node(tree, arr)
    total = arr.sum()
    if total > 0:
        arr /= total
    return pd.Series(arr, index=feature_names).sort_values(ascending=False)

as_pct = st.checkbox("Show as percentage", value=False)
divisor = 100.0 if as_pct else 1.0
fmt_str = ".1f" if as_pct else ".4f"
suffix  = "%" if as_pct else ""

fi1, fi2 = st.columns(2)

with fi1:
    imp1 = feature_importances(gb1, S1_FEATURES) * (100 if as_pct else 1)
    fig_fi1 = go.Figure(go.Bar(
        x=imp1.values[::-1], y=imp1.index[::-1].tolist(),
        orientation="h", marker_color=COLOURS["predicted"],
        hovertemplate="%{y}: %{x:" + fmt_str + "}" + suffix + "<extra></extra>",
    ))
    fig_fi1.update_layout(
        template="plotly_dark", height=340, title="Stage 1 Importance",
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_title="Normalised importance" + (" (%)" if as_pct else ""),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_fi1, width='stretch')

with fi2:
    imp2 = feature_importances(gb2_direct, S2_DIRECT_FEATURES) * (100 if as_pct else 1)
    fig_fi2 = go.Figure(go.Bar(
        x=imp2.values[::-1], y=imp2.index[::-1].tolist(),
        orientation="h", marker_color=COLOURS["predicted"],
        hovertemplate="%{y}: %{x:" + fmt_str + "}" + suffix + "<extra></extra>",
    ))
    fig_fi2.update_layout(
        template="plotly_dark", height=340, title="Stage 2 Direct Importance",
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_title="Normalised importance" + (" (%)" if as_pct else ""),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_fi2, width='stretch')

st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)

# ── Section 4: Residual Analysis ──────────────────────────────────────────────
st.markdown('<div class="kn-label">Residual Analysis (CV Period 2021–2024)</div>', unsafe_allow_html=True)

with st.spinner("Computing residuals on CV period..."):
    cv_gold = gold[gold["date"].dt.year.isin([2021,2022,2023,2024])].copy()
    s2_feat_cols = [c for c in S2_DIRECT_FEATURES if c in cv_gold.columns]
    target_col   = "volume_change_Mm3"

    if target_col in cv_gold.columns and len(s2_feat_cols) == len(S2_DIRECT_FEATURES):
        cv_valid = cv_gold.dropna(subset=s2_feat_cols + [target_col])
        X_cv = cv_valid[s2_feat_cols].values.astype(float)
        y_cv = cv_valid[target_col].values.astype(float)
        y_pred_cv = gb2_direct.predict(X_cv)
        residuals = y_cv - y_pred_cv

        season_col = cv_valid["date"].dt.month.apply(
            lambda m: "Winter" if m in [10,11,12,1,2,3] else "Summer"
        )

        fig_resid = make_subplots(
            rows=3, cols=1,
            subplot_titles=(
                "Predicted vs Actual Volume Change (Mm³)",
                "Residual Distribution",
                "Residuals Over Time",
            ),
            vertical_spacing=0.1,
        )

        # Scatter
        for s, clr in [("Winter", COLOURS["winter"]), ("Summer", COLOURS["summer"])]:
            mask = season_col == s
            fig_resid.add_trace(go.Scatter(
                x=y_pred_cv[mask], y=y_cv[mask],
                mode="markers", name=s,
                marker=dict(color=clr, size=2.5, opacity=0.4),
            ), row=1, col=1)
        diag = np.linspace(y_cv.min(), y_cv.max(), 50)
        fig_resid.add_trace(go.Scatter(x=diag, y=diag, mode="lines",
                                       line=dict(color="#BDBDBD", width=1, dash="dot"),
                                       name="Perfect", showlegend=False), row=1, col=1)
        r2_cv = 1 - np.var(residuals) / np.var(y_cv)
        mae_cv = np.mean(np.abs(residuals))
        fig_resid.add_annotation(
            x=0.98, y=0.05, xref="x domain", yref="y domain",
            text=f"R²={r2_cv:.3f}  MAE={mae_cv:.3f}",
            showarrow=False, font=dict(color="#E0E0E0", size=10),
            bgcolor="#1A1D27", row=1, col=1,
        )

        # Histogram
        fig_resid.add_trace(go.Histogram(
            x=residuals, nbinsx=60,
            marker_color=COLOURS["predicted"], opacity=0.75, name="Residuals",
        ), row=2, col=1)

        # Residuals over time
        fig_resid.add_trace(go.Scatter(
            x=cv_valid["date"], y=residuals,
            mode="lines", line=dict(color=COLOURS["actual"], width=0.7),
            name="Residual", showlegend=False,
        ), row=3, col=1)
        fig_resid.add_hline(y=0, line_dash="dot", line_color="#BDBDBD", row=3, col=1)

        fig_resid.update_layout(
            template="plotly_dark", height=600,
            margin=dict(l=10, r=10, t=40, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_resid, width='stretch')
    else:
        missing = [c for c in S2_DIRECT_FEATURES if c not in cv_gold.columns]
        st.warning(
            f"Cannot compute residuals: missing columns in gold table: {missing[:5]}. "
            "Some Stage 2 features (e.g. level_m_anchor, horizon_h) are only available "
            "at inference time and not stored in the gold CSV."
        )
