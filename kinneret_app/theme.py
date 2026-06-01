"""
theme.py — Central design system for the Kinneret dashboard.

Concept: "WATERLINE — between flood and drought."
A bold environmental identity built on the tension between vivid turquoise
*water* and hot ember *desert*, grounded on warm basalt-black. Expressive
Bricolage Grotesque display type sits over Space Mono instrument labels.

Every page calls `inject_theme()` once near the top (after st.set_page_config)
to get the full chrome: fonts, atmospheric background, metric cards, alerts,
tabs, tables, buttons, sidebar, dividers and motion.

Charts call `style_plotly(fig)` for a matching transparent, warm-dark template.

Exports:
  PALETTE        : dict of named colours (hex / rgba strings)
  inject_theme() : inject the global CSS (idempotent per rerun)
  style_plotly() : apply the shared Plotly layout to a figure
  COLOURS bridge : see app_utils.COLOURS (chart trace colours)
"""
from __future__ import annotations

import streamlit as st

# ── Palette ──────────────────────────────────────────────────────────────────
# Warm basalt ground · turquoise water · ember/sand drought.
PALETTE = {
    # ground
    "ink":        "#0C0B09",   # warm near-black base
    "ink_2":      "#15120D",   # panel base
    "ink_3":      "#1E1A13",   # raised panel
    "hairline":   "rgba(244,235,221,0.10)",

    # water
    "aqua":       "#2BD9C4",   # primary — vivid turquoise
    "aqua_bright":"#67F2DE",
    "aqua_deep":  "#0B6E6B",

    # desert / drought / alert
    "ember":      "#FF6B35",   # burnt orange — falling / red line
    "ember_bright":"#FF8A4C",
    "gold":       "#F2B441",   # sand — warnings
    "leaf":       "#86E05A",   # healthy / rising

    # text (warm, not cold grey)
    "bone":       "#F4EBDD",   # primary text
    "bone_dim":   "#B7A992",   # muted label
    "bone_faint": "#6F6353",   # faint chrome
}

# ── Plotly shared layout ─────────────────────────────────────────────────────
PLOTLY_FONT = "Space Mono, ui-monospace, monospace"
_GRID = "rgba(244,235,221,0.06)"


def style_plotly(fig, *, height: int | None = None, legend: bool = True):
    """Apply the WATERLINE design system to a Plotly figure (transparent,
    warm-dark, Space Mono). Returns the same figure for chaining."""
    fig.update_layout(
        font=dict(family=PLOTLY_FONT, color=PALETTE["bone_dim"], size=11),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=14, b=30),
        hoverlabel=dict(
            font=dict(family=PLOTLY_FONT, size=11, color=PALETTE["bone"]),
            bgcolor=PALETTE["ink_3"],
            bordercolor=PALETTE["aqua_deep"],
        ),
        colorway=[PALETTE["aqua"], PALETTE["ember"], PALETTE["gold"],
                  PALETTE["leaf"], PALETTE["aqua_bright"]],
    )
    if height is not None:
        fig.update_layout(height=height)
    if legend:
        fig.update_layout(legend=dict(
            font=dict(family=PLOTLY_FONT, size=10, color=PALETTE["bone_dim"]),
            bgcolor="rgba(0,0,0,0)",
        ))
    fig.update_xaxes(gridcolor=_GRID, zerolinecolor=_GRID,
                     tickfont=dict(family=PLOTLY_FONT, size=10,
                                   color=PALETTE["bone_faint"]),
                     linecolor=PALETTE["hairline"])
    fig.update_yaxes(gridcolor=_GRID, zerolinecolor=_GRID,
                     tickfont=dict(family=PLOTLY_FONT, size=10,
                                   color=PALETTE["bone_faint"]),
                     linecolor=PALETTE["hairline"])
    return fig


# ── Global CSS ───────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

:root {
  --ink: #0C0B09;        --ink-2: #15120D;       --ink-3: #1E1A13;
  --hairline: rgba(244,235,221,0.10);
  --aqua: #2BD9C4;       --aqua-bright: #67F2DE;  --aqua-deep: #0B6E6B;
  --ember: #FF6B35;      --ember-bright: #FF8A4C;
  --gold: #F2B441;       --leaf: #86E05A;
  --bone: #F4EBDD;       --bone-dim: #B7A992;     --bone-faint: #6F6353;
  --display: 'Bricolage Grotesque', sans-serif;
  --mono: 'Space Mono', ui-monospace, monospace;
}

/* ── Atmosphere ─────────────────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(120% 90% at 8% -10%, rgba(43,217,196,0.16), transparent 45%),
    radial-gradient(130% 100% at 108% 115%, rgba(255,107,53,0.16), transparent 50%),
    repeating-linear-gradient(180deg, transparent 0 78px,
        rgba(244,235,221,0.018) 78px 79px),
    var(--ink);
  background-attachment: fixed;
  color: var(--bone);
}
/* drifting climate glow + film grain */
.stApp::before {
  content: ""; position: fixed; inset: -20%; z-index: 0; pointer-events: none;
  background:
    radial-gradient(40% 38% at 22% 18%, rgba(43,217,196,0.10), transparent 60%),
    radial-gradient(46% 42% at 80% 86%, rgba(255,107,53,0.10), transparent 60%);
  animation: knDrift 26s ease-in-out infinite alternate;
}
.stApp::after {
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.05; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
@keyframes knDrift {
  0%   { transform: translate(0,0) scale(1); }
  100% { transform: translate(2.5%,-2%) scale(1.06); }
}
[data-testid="stHeader"] { background: transparent; }
.block-container { position: relative; z-index: 1;
  padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1240px;
  animation: knEnter 0.6s cubic-bezier(.2,.75,.25,1) both; }
@keyframes knEnter { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

/* ── Typography ─────────────────────────────────────────────────────────── */
html, body, .stApp, [class*="css"] {
  font-family: var(--display);
  color: var(--bone);
}
body h1, body h2, body h3, body h4 {
  font-family: var(--display) !important;
  font-weight: 800 !important;
  letter-spacing: -0.02em !important;
  color: var(--bone) !important;
}
body h1 {
  font-size: 2.55rem !important; line-height: 1.02 !important;
  text-transform: uppercase;
}
/* gradient water-edge underline under the page title */
body h1::after {
  content: ""; display: block; height: 4px; width: 92px; margin-top: 0.55rem;
  background: linear-gradient(90deg, var(--aqua), var(--ember));
  border-radius: 2px;
}
body h2 { font-size: 1.5rem !important; }
body h3 { font-size: 1.16rem !important; color: var(--aqua-bright) !important; }
p, li, span, label, .stMarkdown { color: var(--bone-dim); }
a { color: var(--aqua) !important; text-decoration: none; }
a:hover { color: var(--aqua-bright) !important; }
code, kbd { font-family: var(--mono) !important;
  background: rgba(43,217,196,0.08) !important; color: var(--aqua-bright) !important;
  border: 1px solid var(--hairline); border-radius: 4px; padding: 0.05rem 0.34rem; }

/* ── Shared chrome classes (used across pages) ──────────────────────────── */
.kn-subtitle, .kn-label, .kn-nav-hint {
  font-family: var(--mono) !important;
}
.kn-subtitle {
  font-size: 0.72rem; letter-spacing: 0.26em; color: var(--aqua);
  text-transform: uppercase; margin: -0.4rem 0 1.8rem;
}
.kn-label {
  font-size: 0.72rem !important; letter-spacing: 0.2em !important;
  color: var(--bone-faint) !important; text-transform: uppercase;
  margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.55rem;
}
.kn-label::before {
  content: ""; width: 18px; height: 2px; background: var(--aqua);
  display: inline-block; flex-shrink: 0;
}
.kn-nav-hint {
  font-size: 0.7rem; color: var(--bone-faint); letter-spacing: 0.1em;
  margin-bottom: 0.9rem;
}
.kn-divider, hr.kn-divider {
  height: 1px; border: none;
  background: linear-gradient(90deg, transparent, rgba(43,217,196,0.4),
      rgba(255,107,53,0.25), transparent);
  margin: 1.7rem 0;
}

/* ── Metric cards ───────────────────────────────────────────────────────── */
[data-testid="stMetric"],
[data-testid="metric-container"] {
  background: linear-gradient(160deg, var(--ink-3), var(--ink-2));
  border: 1px solid var(--hairline);
  border-left: 3px solid var(--aqua);
  border-radius: 10px;
  padding: 0.9rem 1.15rem 0.7rem;
  margin-bottom: 0.55rem;
  transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
}
[data-testid="stMetric"]:hover,
[data-testid="metric-container"]:hover {
  transform: translateY(-2px);
  border-left-color: var(--ember);
  box-shadow: 0 10px 30px -16px rgba(255,107,53,0.5);
}
[data-testid="stMetricLabel"] > div, [data-testid="stMetricLabel"] p {
  font-family: var(--mono) !important; font-size: 0.66rem !important;
  letter-spacing: 0.16em; text-transform: uppercase; color: var(--bone-faint) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important; font-size: 1.62rem !important;
  font-weight: 700 !important; color: var(--bone) !important;
}
[data-testid="stMetricDelta"] { font-family: var(--mono) !important;
  font-size: 0.8rem !important; }
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Alerts — refine type + accent, keep Streamlit's semantic tint ──────── */
[data-testid="stAlert"], .stAlert {
  border-radius: 9px !important;
  border-left: 3px solid currentColor !important;
  font-family: var(--mono) !important;
}
[data-testid="stAlert"] p { font-family: var(--mono) !important;
  font-size: 0.82rem !important; }

/* ── Tabs ───────────────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] { gap: 0.4rem; border-bottom: 1px solid var(--hairline); }
[data-baseweb="tab"] {
  font-family: var(--mono) !important; font-size: 0.78rem !important;
  letter-spacing: 0.05em; text-transform: uppercase; color: var(--bone-faint) !important;
}
[data-baseweb="tab"][aria-selected="true"] { color: var(--aqua) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { background: var(--aqua) !important; }

/* ── Tables / dataframes ────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border: 1px solid var(--hairline); border-radius: 10px; }
[data-testid="stTable"] table, .stMarkdown table {
  font-family: var(--mono) !important; font-size: 0.82rem;
}
[data-testid="stTable"] th, .stMarkdown th {
  color: var(--aqua) !important; border-bottom: 1px solid var(--hairline) !important;
  text-transform: uppercase; letter-spacing: 0.04em;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.stButton > button, [data-testid="baseButton-secondary"], button[kind] {
  font-family: var(--mono) !important; text-transform: uppercase;
  letter-spacing: 0.1em; font-size: 0.76rem !important; font-weight: 700 !important;
  border-radius: 8px !important;
  background: linear-gradient(160deg, var(--ink-3), var(--ink-2)) !important;
  color: var(--aqua) !important; border: 1px solid rgba(43,217,196,0.4) !important;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.stButton > button:hover, button[kind]:hover {
  transform: translateY(-2px); border-color: var(--ember) !important;
  color: var(--ember-bright) !important;
  box-shadow: 0 10px 26px -14px rgba(255,107,53,0.6) !important;
}

/* ── page_link nav cards ────────────────────────────────────────────────── */
[data-testid="stPageLink"] a, a[data-testid="stPageLink-NavLink"] {
  font-family: var(--mono) !important; font-size: 0.84rem !important;
  border: 1px solid var(--hairline); border-radius: 9px;
  padding: 0.6rem 0.85rem !important; margin-bottom: 0.5rem;
  background: linear-gradient(160deg, var(--ink-3), var(--ink-2));
  transition: transform .16s ease, border-color .16s ease, padding-left .16s ease;
  display: block;
}
[data-testid="stPageLink"] a:hover {
  transform: translateY(-2px); border-color: rgba(43,217,196,0.5);
  padding-left: 1.1rem !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--ink-2), var(--ink));
  border-right: 1px solid var(--hairline);
}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
[data-baseweb="input"], [data-baseweb="select"], .stDateInput input, .stTextInput input {
  font-family: var(--mono) !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 11px; height: 11px; }
::-webkit-scrollbar-track { background: var(--ink); }
::-webkit-scrollbar-thumb { background: var(--aqua-deep); border-radius: 6px;
  border: 2px solid var(--ink); }
::-webkit-scrollbar-thumb:hover { background: var(--aqua); }

/* ── Page-specific blocks (folded in from individual pages) ─────────────── */
.etl-flow { display: flex; align-items: center; gap: 0.8rem;
  padding: 1rem 0 1.2rem; flex-wrap: wrap; }
.etl-box {
  background: linear-gradient(160deg, var(--ink-3), var(--ink-2));
  border: 1px solid var(--hairline); border-left: 3px solid var(--aqua);
  border-radius: 9px; padding: 0.7rem 1rem; font-family: var(--mono);
  font-size: 0.8rem; text-align: center; flex: 1; min-width: 120px;
  color: var(--bone); }
.etl-arrow { font-size: 1.4rem; color: var(--ember); flex-shrink: 0; }

.arch-box, .anchor-box, .state-banner {
  background: linear-gradient(160deg, var(--ink-3), var(--ink-2));
  border: 1px solid var(--hairline); border-left: 3px solid var(--aqua);
  border-radius: 10px; padding: 1rem 1.15rem; font-family: var(--mono);
  font-size: 0.82rem; color: var(--bone-dim); height: 100%; }
.arch-box h4 { font-family: var(--display) !important; font-size: 0.98rem;
  color: var(--aqua-bright) !important; margin-bottom: 0.5rem; }
.anchor-box, .state-banner { height: auto; margin-bottom: 0.85rem; }

.winner-box {
  background: linear-gradient(135deg, rgba(43,217,196,0.10), rgba(242,180,65,0.08));
  border: 1px solid rgba(242,180,65,0.45); border-left: 3px solid var(--gold);
  border-radius: 11px; padding: 1.1rem 1.4rem; margin: 0.8rem 0; }
.winner-name { font-family: var(--display); font-size: 1.5rem; font-weight: 800;
  color: var(--gold); letter-spacing: -0.02em; }
.delta-pos { color: var(--leaf); font-weight: 700; }
.delta-neg { color: var(--ember); font-weight: 700; }

/* ── Expert Commentary byline + signature ───────────────────────────────── */
.expert-byline {
  font-family: var(--mono); font-size: 0.82rem; color: var(--bone-dim);
  border-left: 3px solid var(--aqua); padding: 0.6rem 0 0.6rem 0.95rem;
  margin: 0.2rem 0 1.4rem; line-height: 1.5;
}
.expert-byline strong { color: var(--aqua-bright); font-weight: 700; }
.expert-sig {
  font-family: var(--display); font-size: 1.15rem; font-weight: 800;
  color: var(--aqua-bright); letter-spacing: -0.01em; margin-top: 0.4rem;
}
.expert-sig + .expert-sig-title {
  font-family: var(--mono); font-size: 0.72rem; color: var(--bone-faint);
  letter-spacing: 0.14em; text-transform: uppercase;
}
.expert-essay p { color: var(--bone-dim); font-size: 0.95rem; line-height: 1.65;
  font-family: var(--display); }
.expert-essay strong { color: var(--bone); }
</style>
"""


def inject_theme() -> None:
    """Inject the WATERLINE design system. Call once per page, after
    st.set_page_config(), before rendering content."""
    st.markdown(_CSS, unsafe_allow_html=True)
