"""
7_Model_Olympics.py  —  Model Benchmark Comparison

Loads Models/olympics_results.json and displays a four-model scorecard,
winner announcement, per-fold R² chart, and architecture notes.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_utils import PROJECT_ROOT, COLOURS
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    COLOURS = {}

RESULTS_FILE = PROJECT_ROOT / "Models" / "olympics_results.json"

st.set_page_config(page_title="Model Olympics", page_icon="🏅", layout="wide")

# ── CSS (matches project design system) ───────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700&family=DM+Mono&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif; }
.kn-label {
    font-size:0.78rem; color:#7BA3D4; text-transform:uppercase;
    letter-spacing:0.08em; font-family:'DM Mono',monospace; margin-bottom:4px;
}
.kn-divider {
    border:none; border-top:1px solid rgba(30,144,255,0.22); margin:1.2rem 0;
}
.winner-box {
    background:rgba(255,215,0,0.08); border:1px solid #FFD700;
    border-radius:8px; padding:1rem 1.4rem; margin:0.8rem 0;
}
.winner-name { font-family:'Syne',sans-serif; font-size:1.4rem;
               color:#FFD700; font-weight:700; }
.delta-pos { color:#66BB6A; font-weight:600; }
.delta-neg { color:#EF5350; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏅 Model Olympics</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#7BA3D4;font-size:0.72rem;">'
    'Walk-forward CV benchmark — held-out years 2021–2024'
    '</p>', unsafe_allow_html=True)
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)

# ── Load results ──────────────────────────────────────────────────────────────
if not RESULTS_FILE.exists():
    st.warning(
        "Results not found. Run `python Automation/08_train_forecast_model.py` "
        "to train all models and generate the benchmark."
    )
    st.stop()

with open(RESULTS_FILE, encoding="utf-8") as f:
    results = json.load(f)

models   = results["models"]
winner   = results["winner"]
gen_date = results.get("generated_at", "unknown")

DISPLAY_NAMES = {
    "baseline_gbr": "Baseline GBR",
    "xgboost":      "XGBoost",
    "lgbm":         "LightGBM",
    "gru":          "GRU (multi-task)",
}

# ── 1. Scoreboard ─────────────────────────────────────────────────────────────
st.markdown('<p class="kn-label">Scoreboard</p>', unsafe_allow_html=True)

rows = []
for key, entry in models.items():
    rows.append({
        "Model":          DISPLAY_NAMES.get(key, key),
        "CV R² (vol Δ)":  entry.get("cv_vol_r2_mean"),
        "CV MAE (Mm³/d)": entry.get("cv_vol_mae_mean"),
        "7-day drift (m)":entry.get("cv_7d_drift_mean_m"),
        "Inflow R²":      entry.get("cv_inflow_r2_mean"),
        "_key":           key,
        "_is_winner":     key == winner,
    })

def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.3f}"

def _row_html(row):
    bg    = "rgba(255,215,0,0.10)" if row["_is_winner"] else "transparent"
    color = "#FFD700" if row["_is_winner"] else "#E0E0E0"
    crown = " 🏅" if row["_is_winner"] else ""
    cells = [
        f'<td style="color:{color}">{row["Model"]}{crown}</td>',
        f'<td style="color:{color};text-align:right">{_fmt(row["CV R² (vol Δ)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["CV MAE (Mm³/d)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["7-day drift (m)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["Inflow R²"])}</td>',
    ]
    return f'<tr style="background:{bg}">{"".join(cells)}</tr>'

header = "<tr>" + "".join(
    f'<th style="color:#7BA3D4;text-align:{"right" if i else "left"}">{h}</th>'
    for i, h in enumerate(["Model", "CV R² (vol Δ)", "CV MAE (Mm³/d)",
                            "7-day drift (m)", "Inflow R²"])
) + "</tr>"

table_html = (
    '<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;'
    'font-size:0.85rem">'
    f"<thead>{header}</thead><tbody>"
    + "".join(_row_html(r) for r in rows)
    + "</tbody></table>"
)
st.markdown(table_html, unsafe_allow_html=True)
st.markdown(f'<p style="color:#7BA3D4;font-size:0.7rem;margin-top:4px">'
            f'Generated: {gen_date}</p>', unsafe_allow_html=True)

# ── 2. Winner announcement ────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Champion</p>', unsafe_allow_html=True)

win_entry  = models[winner]
base_entry = models.get("baseline_gbr", {})
r2_delta   = (win_entry.get("cv_vol_r2_mean") or 0) - (base_entry.get("cv_vol_r2_mean") or 0)
mae_delta  = (win_entry.get("cv_vol_mae_mean") or 0) - (base_entry.get("cv_vol_mae_mean") or 0)

r2_sign    = "+" if r2_delta >= 0 else ""
mae_sign   = "+" if mae_delta >= 0 else ""
r2_class   = "delta-pos" if r2_delta >= 0 else "delta-neg"
mae_class  = "delta-neg" if mae_delta >= 0 else "delta-pos"

if winner != "baseline_gbr":
    st.markdown(f"""
    <div class="winner-box">
      <div class="winner-name">{DISPLAY_NAMES.get(winner, winner)}</div>
      <div style="margin-top:0.5rem;font-size:0.9rem;color:#E0E0E0">
        R² = <strong>{_fmt(win_entry.get("cv_vol_r2_mean"))}</strong>
        &nbsp;|&nbsp;
        MAE = <strong>{_fmt(win_entry.get("cv_vol_mae_mean"))} Mm³/day</strong>
        &nbsp;|&nbsp;
        vs baseline:
        <span class="{r2_class}">{r2_sign}{r2_delta:.3f} R²</span>
        &nbsp;
        <span class="{mae_class}">{mae_sign}{mae_delta:.3f} MAE</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="winner-box">
      <div class="winner-name">Baseline GBR holds the crown 🏆</div>
      <div style="margin-top:0.5rem;font-size:0.9rem;color:#E0E0E0">
        No challenger improved on the baseline R².
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── 3. Per-fold R² bar chart ──────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Per-fold R² (volume change)</p>',
            unsafe_allow_html=True)

fold_rows = []
for key, entry in models.items():
    by_fold = entry.get("cv_vol_r2_by_fold") or {}
    for fold, val in by_fold.items():
        if val is not None:
            fold_rows.append({
                "Year":  fold,
                "Model": DISPLAY_NAMES.get(key, key),
                "R²":    val,
            })

if fold_rows:
    fold_df = pd.DataFrame(fold_rows)
    pivot = fold_df.pivot(index="Year", columns="Model", values="R²")
    display_order = [DISPLAY_NAMES[k] for k in models if DISPLAY_NAMES[k] in pivot.columns]
    pivot = pivot[display_order]
    st.bar_chart(pivot)

# ── 4. Architecture notes ─────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Architecture Notes</p>', unsafe_allow_html=True)

notes = {
    "Baseline GBR": (
        "The current production model. Stage 1 predicts Jordan River inflow using chained "
        "inflow lags — each day's predicted inflow feeds the next day as lag-1. Stage 2 uses "
        "a direct multi-step design with a fixed anchor state, but Stage 1 chaining remains "
        "a source of cumulative error over the 7-day window."
    ),
    "XGBoost": (
        "Two independent direct models (S1 for inflow, S2 for volume change), each trained "
        "with horizon_h as an explicit feature and a fixed anchor inflow at day 0. Eliminates "
        "Stage 1 chaining entirely. XGBoost's L1/L2 regularisation and column subsampling "
        "typically improve on gradient boosting baselines on tabular data."
    ),
    "LightGBM": (
        "Same two-model direct architecture as XGBoost. LightGBM's leaf-wise tree growth "
        "strategy often yields better performance on smaller datasets with skewed targets — "
        "relevant here because volume change has a heavy positive tail during flood events."
    ),
    "GRU (multi-task)": (
        "A single neural network with a shared 21-day GRU backbone. For each forecast day, "
        "the network receives a 21-day sequence of 14 daily features plus the target horizon "
        "(1-7) as input, and simultaneously predicts both inflow and volume change. The joint "
        "objective allows the network to learn physical co-variance between river flow and lake "
        "response that independent models cannot exploit."
    ),
}

for model_name, text in notes.items():
    if any(DISPLAY_NAMES[k] == model_name for k in models):
        st.markdown(f'<p style="color:#7BA3D4;font-size:0.78rem;margin-top:0.8rem">'
                    f'{model_name}</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:0.82rem;color:#C0C0C0">{text}</p>',
                    unsafe_allow_html=True)
