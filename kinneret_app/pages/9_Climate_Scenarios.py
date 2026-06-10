"""
9_Climate_Scenarios.py  —  Climate Scenarios

CORDEX RCP4.5 / RCP8.5 ensemble projections for the Kinneret basin.
12 regional climate models drive a daily water-balance model held at modern
inflow and pumping climatology, isolating the temperature-driven signal.

Three tabs:
  ☀️  Evaporative Demand   — lake ET₀, HIGH confidence (deterministic physics)
  💧  Water Balance & Level — projected level, MEDIUM confidence (DTR->rain AUC 0.811)
  📋  Hindcast Check        — model skill vs 2006-2024 observed record

Data source: Gold Data/cordex_hindcast.parquet (2006-2024 hindcast water balance)
             Gold Data/cordex_waterbalance.parquet (2006-2100 forward projection, if present)
Config:      docs/cordex_config.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Path bootstrap ────────────────────────────────────────────────────────────
try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_utils import PROJECT_ROOT
    from theme import inject_theme, style_plotly, PALETTE
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    PALETTE = {
        "aqua": "#2BD9C4", "ember": "#FF6B35", "gold": "#F2B441",
        "leaf": "#86E05A", "bone": "#F4EBDD", "ink": "#0C0B09",
        "bone_dim": "#B7A992", "bone_faint": "#6F6353",
    }
    def inject_theme():
        return None
    def style_plotly(fig, **kwargs):
        return fig

# ── File paths ────────────────────────────────────────────────────────────────
WB_FILE       = PROJECT_ROOT / "Gold Data" / "cordex_waterbalance.parquet"
HINDCAST_FILE = PROJECT_ROOT / "Gold Data" / "cordex_hindcast.parquet"
CONFIG_FILE   = PROJECT_ROOT / "docs" / "cordex_config.json"
LEVEL_FILE    = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"

# ── Constants ─────────────────────────────────────────────────────────────────
LOWER_RED_LINE = -215.5   # management lower red line (m ASL)
FULL_LEVEL     = -208.8   # full lake level (m ASL)
MODEL_OPACITY  = 0.15


# ── Data loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_config() -> dict:
    """Load CORDEX config JSON; return empty dict if missing."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def load_waterbalance() -> pd.DataFrame | None:
    """Load forward-projection water balance (2006-2100).

    Tries cordex_waterbalance.parquet first; falls back to cordex_hindcast.parquet
    so the page still works during development before the full projection is generated.
    Returns None if neither file exists.
    """
    if WB_FILE.exists():
        try:
            df = pd.read_parquet(WB_FILE)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values(["date", "model", "scenario"]).reset_index(drop=True)
        except Exception:
            pass
    if HINDCAST_FILE.exists():
        try:
            df = pd.read_parquet(HINDCAST_FILE)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values(["date", "model", "scenario"]).reset_index(drop=True)
        except Exception:
            pass
    return None


@st.cache_data(ttl=3600)
def load_hindcast() -> pd.DataFrame | None:
    """Load hindcast water balance (2006-2024); returns None if missing."""
    if not HINDCAST_FILE.exists():
        return None
    try:
        df = pd.read_parquet(HINDCAST_FILE)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values(["date", "model", "scenario"]).reset_index(drop=True)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def load_observed_level() -> pd.DataFrame | None:
    """Load kinneret_level.csv; returns None if missing."""
    if not LEVEL_FILE.exists():
        return None
    try:
        df = pd.read_csv(LEVEL_FILE, parse_dates=["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None


# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Climate Scenarios", page_icon="🌡", layout="wide")
inject_theme()

# ── Load data ─────────────────────────────────────────────────────────────────
cfg = load_config()
wb  = load_waterbalance()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("<h1>🌡 Climate Scenarios</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="kn-subtitle" style="margin-top:0.6rem;">'
    "What does warming do to the Kinneret?"
    "</p>",
    unsafe_allow_html=True,
)

# ── Assumption callout — always visible, above tabs ───────────────────────────
st.info(
    "**Held assumptions:** Inflow volume and pumping are held at modern-period "
    "climatology. This projection shows the effect of temperature — not of policy "
    "or land-use change."
)

# ── Hindcast gate ─────────────────────────────────────────────────────────────
hindcast_rmse = float(cfg.get("hindcast_rmse_m", 0.0))
if hindcast_rmse > 2.0:
    st.warning(
        f"⚠️ Hindcast RMSE = {hindcast_rmse:.2f} m — the water balance cannot "
        "closely track the 2006–2024 observed record. Forward projections are "
        "exploratory only."
    )

# ── Guard: need water-balance data for all tabs ───────────────────────────────
if wb is None:
    st.warning(
        "Water balance data not found. Expected one of:\n"
        f"- `{WB_FILE}`\n"
        f"- `{HINDCAST_FILE}`\n\n"
        "Run the CORDEX calibration and hindcast scripts to generate these files, "
        "then reload this page."
    )
    st.stop()

required = {"date", "model", "scenario", "level_m", "lake_ET_Mm3"}
missing = required - set(wb.columns)
if missing:
    st.error(f"Water balance data is missing columns: {missing}")
    st.stop()

# ── Helper: compute annual aggregates ────────────────────────────────────────

def _annual_et(df: pd.DataFrame) -> pd.DataFrame:
    """Annual sum of lake_ET_Mm3 per year × model × scenario."""
    out = df.copy()
    out["year"] = out["date"].dt.year
    return (
        out.groupby(["year", "model", "scenario"])["lake_ET_Mm3"]
        .sum()
        .reset_index()
    )


def _annual_level(df: pd.DataFrame) -> pd.DataFrame:
    """Annual mean of level_m per year × model × scenario."""
    out = df.copy()
    out["year"] = out["date"].dt.year
    return (
        out.groupby(["year", "model", "scenario"])["level_m"]
        .mean()
        .reset_index()
    )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB to rgba(r,g,b,a) — Plotly does not support 8-char hex."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _ribbon_traces(
    annual: pd.DataFrame,
    value_col: str,
    scenario: str,
    color: str,
    label: str,
    show_legend_ribbon: bool = True,
    show_legend_median: bool = True,
) -> list[go.BaseTraceType]:
    """Return Plotly traces for one scenario: ribbon + thin model lines + median."""
    traces: list[go.BaseTraceType] = []
    sub = annual[annual["scenario"] == scenario].copy()
    if sub.empty:
        return traces

    pivot = sub.pivot(index="year", columns="model", values=value_col).sort_index()
    years = pivot.index.tolist()
    models = pivot.columns.tolist()

    p10 = pivot.quantile(0.10, axis=1).values
    p50 = pivot.quantile(0.50, axis=1).values
    p90 = pivot.quantile(0.90, axis=1).values

    fill_color = _hex_to_rgba(color, 0.15)

    # Upper ribbon boundary (p90) — no legend entry
    traces.append(go.Scatter(
        x=years, y=p90,
        mode="lines", line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
        name=f"_p90_{scenario}",
    ))
    # Lower ribbon boundary (p10) — filled to previous trace
    traces.append(go.Scatter(
        x=years, y=p10,
        mode="lines", line=dict(width=0),
        fill="tonexty",
        fillcolor=fill_color,
        showlegend=show_legend_ribbon,
        legendgroup=scenario,
        name=f"{label} 10–90th pct",
        hoverinfo="skip",
    ))

    # Thin individual model lines
    for model in models:
        traces.append(go.Scatter(
            x=years,
            y=pivot[model].values,
            mode="lines",
            line=dict(color=color, width=0.8),
            opacity=MODEL_OPACITY,
            showlegend=False,
            hovertemplate=f"{model}<br>%{{y:.1f}}<extra>{label}</extra>",
            name=f"_model_{scenario}_{model}",
        ))

    # Median line
    traces.append(go.Scatter(
        x=years, y=p50,
        mode="lines",
        line=dict(color=color, width=2.5),
        showlegend=show_legend_median,
        legendgroup=scenario,
        name=f"{label} median",
        hovertemplate=f"{label} median<br>Year: %{{x}}<br>%{{y:.1f}}<extra></extra>",
    ))
    return traces


def _summary_table(annual: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Median + 10th–90th pct for defined periods per scenario."""
    periods = [
        ("2010–2030", 2010, 2030),
        ("2030–2050", 2030, 2050),
        ("2050–2080", 2050, 2080),
        ("2080–2100", 2080, 2100),
    ]
    rows = []
    for scenario in ["rcp45", "rcp85"]:
        sub = annual[annual["scenario"] == scenario]
        for label, y0, y1 in periods:
            vals = sub[(sub["year"] >= y0) & (sub["year"] <= y1)][value_col]
            if vals.empty:
                rows.append({
                    "Scenario": scenario.upper(),
                    "Period": label,
                    "P10": None, "Median": None, "P90": None,
                })
            else:
                rows.append({
                    "Scenario": scenario.upper(),
                    "Period": label,
                    "P10": round(float(np.percentile(vals, 10)), 1),
                    "Median": round(float(np.median(vals)), 1),
                    "P90": round(float(np.percentile(vals, 90)), 1),
                })
    return pd.DataFrame(rows)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(
    ["☀️ Evaporative Demand", "💧 Water Balance", "📋 Hindcast Check"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Evaporative Demand (HIGH confidence)
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(
        "**Confidence: HIGH** — Hargreaves ET₀ is deterministic physics from "
        "tmin/tmax alone.",
        unsafe_allow_html=False,
    )
    st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)

    annual_et = _annual_et(wb)

    # Reference line: 2006-2024 mean of annual ET₀
    hc_et = annual_et[annual_et["year"] <= 2024]
    ref_et = float(hc_et["lake_ET_Mm3"].mean()) if not hc_et.empty else None

    fig_et = go.Figure()

    for scenario, color, label in [
        ("rcp45", PALETTE["aqua"],  "RCP4.5"),
        ("rcp85", PALETTE["ember"], "RCP8.5"),
    ]:
        for tr in _ribbon_traces(annual_et, "lake_ET_Mm3", scenario, color, label):
            fig_et.add_trace(tr)

    if ref_et is not None:
        min_year = int(annual_et["year"].min())
        max_year = int(annual_et["year"].max())
        fig_et.add_trace(go.Scatter(
            x=[min_year, max_year],
            y=[ref_et, ref_et],
            mode="lines",
            line=dict(color=PALETTE["gold"], width=1.5, dash="dash"),
            showlegend=True,
            name=f"2006–2024 mean ({ref_et:.0f} Mm³/yr)",
            hovertemplate=f"Reference: {ref_et:.1f} Mm³/yr<extra></extra>",
        ))

    fig_et.update_yaxes(title_text="Lake ET₀ (Mm³ / year)")
    fig_et.update_xaxes(title_text="Year")
    style_plotly(fig_et, height=420)
    st.plotly_chart(fig_et, use_container_width=True)

    # Summary table
    st.markdown('<p class="kn-label">Period summary — Lake ET₀ (Mm³/year)</p>',
                unsafe_allow_html=True)
    tbl_et = _summary_table(annual_et, "lake_ET_Mm3")
    st.table(tbl_et)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Water Balance & Level (MEDIUM confidence)
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(
        "**Confidence: MEDIUM** — rain propensity is inferred from temperature "
        "(DTR signal, AUC 0.811). Bands show model uncertainty, not measurement "
        "precision.",
        unsafe_allow_html=False,
    )
    st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)

    annual_lv = _annual_level(wb)

    # Chart A — annual mean level ribbon
    fig_lv = go.Figure()

    for scenario, color, label in [
        ("rcp45", PALETTE["aqua"],  "RCP4.5"),
        ("rcp85", PALETTE["ember"], "RCP8.5"),
    ]:
        for tr in _ribbon_traces(annual_lv, "level_m", scenario, color, label):
            fig_lv.add_trace(tr)

    # Horizontal reference lines
    min_year = int(annual_lv["year"].min())
    max_year = int(annual_lv["year"].max())
    fig_lv.add_trace(go.Scatter(
        x=[min_year, max_year],
        y=[LOWER_RED_LINE, LOWER_RED_LINE],
        mode="lines",
        line=dict(color=PALETTE["ember"], width=1.5, dash="dot"),
        showlegend=True,
        name=f"Lower red line ({LOWER_RED_LINE} m)",
        hovertemplate=f"Lower red line: {LOWER_RED_LINE} m ASL<extra></extra>",
    ))
    fig_lv.add_trace(go.Scatter(
        x=[min_year, max_year],
        y=[FULL_LEVEL, FULL_LEVEL],
        mode="lines",
        line=dict(color=PALETTE["aqua"], width=1.5, dash="dot"),
        showlegend=True,
        name=f"Full level ({FULL_LEVEL} m)",
        hovertemplate=f"Full level: {FULL_LEVEL} m ASL<extra></extra>",
    ))

    fig_lv.update_yaxes(title_text="Level (m ASL)")
    fig_lv.update_xaxes(title_text="Year")
    style_plotly(fig_lv, height=400)
    st.plotly_chart(fig_lv, use_container_width=True)

    # Chart B — box plots at key horizons
    st.markdown('<p class="kn-label">Level distribution at key horizons</p>',
                unsafe_allow_html=True)

    horizons = [
        ("2030", 2025, 2035),
        ("2050", 2045, 2055),
        ("2100", 2090, 2100),
    ]

    fig_box = go.Figure()
    for scenario, color, label in [
        ("rcp45", PALETTE["aqua"],  "RCP4.5"),
        ("rcp85", PALETTE["ember"], "RCP8.5"),
    ]:
        sub = annual_lv[annual_lv["scenario"] == scenario]
        for h_label, y0, y1 in horizons:
            vals = sub[(sub["year"] >= y0) & (sub["year"] <= y1)]["level_m"].values
            if len(vals) == 0:
                continue
            fig_box.add_trace(go.Box(
                q1=[float(np.percentile(vals, 25))],
                median=[float(np.median(vals))],
                q3=[float(np.percentile(vals, 75))],
                lowerfence=[float(np.percentile(vals, 10))],
                upperfence=[float(np.percentile(vals, 90))],
                name=f"{h_label}<br>{label}",
                marker_color=color,
                boxmean=True,
                showlegend=False,
            ))

    fig_box.update_yaxes(title_text="Annual mean level (m ASL)")
    style_plotly(fig_box, height=360)
    st.plotly_chart(fig_box, use_container_width=True)

    st.markdown(
        '<p style="color:var(--bone-faint);font-family:Space Mono,monospace;'
        'font-size:0.75rem;margin-top:-0.3rem">'
        "Box spans 25th–75th percentile across 12 models; whiskers = 10th–90th. "
        "No single number is a forecast — the spread IS the message."
        "</p>",
        unsafe_allow_html=True,
    )

    # Summary table
    st.markdown('<p class="kn-label">Period summary — Annual mean level (m ASL)</p>',
                unsafe_allow_html=True)
    tbl_lv = _summary_table(annual_lv, "level_m")
    st.table(tbl_lv)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Hindcast Check
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    hc = load_hindcast()
    obs = load_observed_level()

    # Metrics row
    rmse = float(cfg.get("hindcast_rmse_m", 0.0))
    corr = float(cfg.get("hindcast_corr", 0.0))
    n_days = int(cfg.get("hindcast_n_days", 0))

    if rmse > 2.0:
        rmse_delta = f"⚠️ {rmse:.2f} m — exploratory"
    else:
        rmse_delta = f"✓ within tolerance ({rmse:.2f} m)"

    col1, col2, col3 = st.columns(3)
    col1.metric("Hindcast RMSE", f"{rmse:.2f} m", delta=rmse_delta)
    col2.metric("Correlation (r)", f"{corr:.3f}")
    col3.metric("Overlap days", f"{n_days:,}")

    st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)

    if hc is None:
        st.warning(
            f"Hindcast data not found at `{HINDCAST_FILE}`. "
            "Run the hindcast script to generate it."
        )
    else:
        # Build hindcast chart
        hc_annual = _annual_level(hc)

        fig_hc = go.Figure()

        # Ensemble ribbon + median (combine both scenarios for hindcast context)
        # Use rcp45 as "historical forcing" representative
        for scenario, color, label in [
            ("rcp45", PALETTE["aqua"],  "Ensemble (RCP4.5)"),
            ("rcp85", PALETTE["ember"], "Ensemble (RCP8.5)"),
        ]:
            sub = hc_annual[hc_annual["scenario"] == scenario]
            if sub.empty:
                continue
            pivot = sub.pivot(index="year", columns="model", values="level_m").sort_index()
            years = pivot.index.tolist()
            p10 = pivot.quantile(0.10, axis=1).values
            p50 = pivot.quantile(0.50, axis=1).values
            p90 = pivot.quantile(0.90, axis=1).values
            fill_color = _hex_to_rgba(color, 0.15)

            fig_hc.add_trace(go.Scatter(
                x=years, y=p90,
                mode="lines", line=dict(width=0),
                showlegend=False, hoverinfo="skip",
                name=f"_p90_{scenario}",
            ))
            fig_hc.add_trace(go.Scatter(
                x=years, y=p10,
                mode="lines", line=dict(width=0),
                fill="tonexty", fillcolor=fill_color,
                showlegend=True, legendgroup=scenario,
                name=f"{label} 10–90th pct",
                hoverinfo="skip",
            ))
            fig_hc.add_trace(go.Scatter(
                x=years, y=p50,
                mode="lines", line=dict(color=color, width=2.5),
                showlegend=True, legendgroup=scenario,
                name=f"{label} median",
                hovertemplate=f"{label} median<br>Year: %{{x}}<br>%{{y:.2f}} m ASL<extra></extra>",
            ))

        # Observed level — annual mean
        if obs is not None:
            obs["year"] = obs["date"].dt.year
            obs_annual = obs.groupby("year")["kinneret_level"].mean().reset_index()
            # Clip to hindcast period
            obs_annual = obs_annual[
                (obs_annual["year"] >= hc["date"].dt.year.min()) &
                (obs_annual["year"] <= hc["date"].dt.year.max())
            ]
            fig_hc.add_trace(go.Scatter(
                x=obs_annual["year"].tolist(),
                y=obs_annual["kinneret_level"].tolist(),
                mode="lines+markers",
                line=dict(color=PALETTE["bone"], width=2),
                marker=dict(size=5, color=PALETTE["bone"]),
                showlegend=True,
                name="Observed (annual mean)",
                hovertemplate="Observed<br>Year: %{x}<br>%{y:.2f} m ASL<extra></extra>",
            ))

        fig_hc.update_yaxes(title_text="Annual mean level (m ASL)")
        fig_hc.update_xaxes(title_text="Year")
        style_plotly(fig_hc, height=400)
        st.plotly_chart(fig_hc, use_container_width=True)

    st.markdown(
        '<p style="color:var(--bone-faint);font-family:Space Mono,monospace;'
        'font-size:0.75rem;margin-top:-0.3rem">'
        "The hindcast runs the water-balance model over 2006–2024 using observed "
        "CORDEX temperatures as forcing. Comparing ensemble median against the "
        "observed Kinneret record quantifies how well the model tracks real "
        "variability before we trust it forward in time."
        "</p>",
        unsafe_allow_html=True,
    )
