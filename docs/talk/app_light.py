"""
app_light.py - the dashboard's front page (kinneret_app/app.py) as a slide: light theme, big type.

The live app is dark (theme.py, "WATERLINE"). For the talk, its landing page is shown in the same
colours as the lake animation (make_lake_animation.py): light page, sand basin, teal water,
Segoe UI. And it is cut down to what the back row of a hall can read: the title, the red-line
chip, the lake picture and the two big numbers (level, volume) - all enlarged. Everything small
(kicker, subtitle, alert banners, days-since card, charts, navigation) is left out.

Nothing in kinneret_app/ changes - this runs the real app.py with:
  * theme.PALETTE / app_utils.COLOURS recoloured in place
  * a second <style> after inject_theme() that redefines the CSS variables, flattens the
    background, swaps the fonts and scales the type up
  * build_lake_svg's dark basin and light label recoloured (as in make_images.make_title),
    its labels enlarged
  * the small elements dropped by wrapping the Streamlit calls app.py makes

FULL mode (KN_TALK_FULL=1, slide 4's scroll, originator 20 Oct): the whole front page, nothing
dropped, in the same light colours at the app's own type sizes, charts included (Plotly recoloured).

Run (the screenshot script starts it for you):
  streamlit run docs/talk/app_light.py --theme.base light
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parents[2] / "kinneret_app" / "app.py"
sys.path.insert(0, str(APP.parent))

import app_utils  # noqa: E402
import theme  # noqa: E402

# the animation's colours (make_lake_animation.py)
SURFACE, INK, INK_2, FAINT = "#FBFAF7", "#1D1D1B", "#5F5D57", "#8A877F"
EMPTY_BASIN, TEAL, TEAL_DEEP = "#E6E1D6", "#1BA898", "#0B6E6B"
RED, GREEN = "#C2410C", "#4E9A2E"           # red line (the deck's one red) / spill line, as the live app

theme.PALETTE.update({
    "ink": SURFACE, "ink_2": "#F3F1EB", "ink_3": "#FFFFFF",
    "hairline": "rgba(29,29,27,0.10)",
    "aqua": TEAL, "aqua_bright": TEAL_DEEP, "aqua_deep": TEAL_DEEP,
    "ember": RED, "ember_bright": RED, "leaf": GREEN,
    "bone": INK, "bone_dim": INK_2, "bone_faint": FAINT,
})
app_utils.COLOURS.update({
    "predicted": TEAL, "actual": RED, "winter": TEAL, "summer": RED, "rising": GREEN,
    "falling": RED, "stable": FAINT, "legal_min": RED, "legal_max": GREEN,
})

# ─── the lake picture: light basin, dark label, bigger type ─────────────────

_build_lake_svg = app_utils.build_lake_svg


def build_lake_svg_light(level: float) -> str:
    return (_build_lake_svg(level)
            .replace("#1E1A13", EMPTY_BASIN)
            .replace('fill="#F4EBDD"', f'fill="{INK}"')
            .replace('font-family="monospace"', 'font-family="Segoe UI"')
            .replace('font-size="6.5"', 'font-size="11"')
            .replace('font-size="8.0"', 'font-size="13"')
            .replace("#86E05A", GREEN).replace("#FF6B35", RED))


app_utils.build_lake_svg = build_lake_svg_light

FULL = os.environ.get("KN_TALK_FULL") == "1"

# ─── Plotly: the dark template's text and grid, in the light colours ────────

_style_plotly = theme.style_plotly


def style_plotly_light(fig, **kw):
    _style_plotly(fig, **kw)
    grid = "rgba(29,29,27,0.08)"
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Segoe UI", color=INK_2, size=14))
    if fig.layout.legend is not None:
        fig.update_layout(legend=dict(font=dict(family="Segoe UI", size=13, color=INK_2)))
    for ax in (fig.update_xaxes, fig.update_yaxes):
        ax(gridcolor=grid, zerolinecolor=grid, linecolor=grid,
           tickfont=dict(family="Segoe UI", size=13, color=INK_2), title_font=dict(color=INK_2))
    return fig


theme.style_plotly = style_plotly_light

# ─── keep only what reads from the back row ─────────────────────────────────

_markdown = st.markdown


def markdown_big_only(body: str, *args, **kwargs):
    if body.lstrip().startswith("<style"):
        return _markdown(body, *args, **kwargs)        # the theme's own stylesheet
    if "kn-divider" in body or "kn-label" in body or "kn-nav-hint" in body:
        return None                                    # section labels, dividers
    body = re.sub(r'<div style="font-family:var\(--mono\);font-size:0\.72rem;.*?</div>', "",
                  body, count=1, flags=re.S)           # "Sea of Galilee / Lake Kinneret"
    body = re.sub(r'<div class="kn-subtitle".*?</div>', "", body, count=1, flags=re.S)
    body = body.replace("Flood<br>&amp;", "Flood &amp;")  # the title on one row
    return _markdown(body, *args, **kwargs)


_metric = st.metric


def metric_big_only(label: str, *args, **kwargs):
    if label.lower().startswith("days since"):
        return None
    return _metric(label, *args, **kwargs)


def nothing(*args, **kwargs):
    return None


def page_card(page: str, label: str = "", **kwargs):
    """st.page_link needs the real multipage app; here the same link drawn as a still card."""
    return _markdown(f'<div style="background:#FFFFFF;border:1px solid rgba(29,29,27,0.10);border-radius:8px;'
                     f'padding:0.7rem 1rem;margin-bottom:0.5rem;color:{INK};">{label}</div>',
                     unsafe_allow_html=True)


if FULL:
    st.page_link = page_card
else:
    st.markdown = markdown_big_only
    st.metric = metric_big_only
    for name in ("error", "success", "info", "plotly_chart", "subheader", "page_link"):
        setattr(st, name, nothing)

# ─── light theme, big type ──────────────────────────────────────────────────

LIGHT_CSS = f"""
<style>
:root {{
  --ink: {SURFACE}; --ink-2: #F3F1EB; --ink-3: #FFFFFF;
  --hairline: rgba(29,29,27,0.10);
  --aqua: {TEAL}; --aqua-bright: {TEAL_DEEP}; --aqua-deep: {TEAL_DEEP};
  --ember: {RED}; --ember-bright: {RED}; --leaf: {GREEN};
  --bone: {INK}; --bone-dim: {INK_2}; --bone-faint: {FAINT};
  --display: 'Segoe UI', sans-serif;
  --mono: 'Segoe UI', sans-serif;
}}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--ink) !important; }}
.stApp::before, .stApp::after {{ display: none !important; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], header {{ display: none !important; }}
.block-container {{ max-width: 1440px !important; padding-top: 0.6rem !important; }}

body h1 {{ font-size: 4.6rem !important; font-weight: 600 !important; line-height: 1.0 !important;
          text-transform: none !important; letter-spacing: -0.015em !important; }}
body h1::after {{ background: var(--aqua) !important; height: 6px !important;
                 width: 140px !important; margin-top: 1rem !important; }}
body h1, body h1 * {{ color: var(--bone) !important; }}
/* the red-line chip */
.block-container span[style*="999px"] {{
  font-size: 1.9rem !important; font-weight: 600 !important; letter-spacing: 0 !important;
  padding: 0.5rem 1.4rem !important; margin-top: 1.6rem !important; }}

[data-testid="stMetric"] {{ background: #FFFFFF !important; padding: 1.6rem 2rem !important;
  border-left-width: 6px !important; margin-bottom: 0.9rem !important; }}
[data-testid="stMetricLabel"] > div, [data-testid="stMetricLabel"] p {{
  font-size: 1.5rem !important; font-weight: 600 !important; letter-spacing: 0.06em !important;
  color: var(--bone-dim) !important; }}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  font-size: 4.2rem !important; font-weight: 600 !important; color: var(--bone) !important;
  line-height: 1.15 !important; }}
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {{
  font-size: 1.6rem !important; font-weight: 600 !important; }}
</style>
"""

_inject = theme.inject_theme


# FULL: only the colours and fonts; the app keeps its own sizes
FULL_CSS = LIGHT_CSS[:LIGHT_CSS.index("body h1")] + f"""
body h1, body h1 * {{ color: var(--bone) !important; font-weight: 600 !important; }}
body h1::after {{ background: var(--aqua) !important; }}
[data-testid="stMetric"] {{ background: #FFFFFF !important; }}
h2, h3, h2 *, h3 * {{ font-family: 'Segoe UI', sans-serif !important; font-weight: 600 !important;
                      color: var(--bone) !important; }}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{ color: var(--bone) !important; }}
</style>
"""


def inject_light() -> None:
    _inject()
    _markdown(FULL_CSS if FULL else LIGHT_CSS, unsafe_allow_html=True)


theme.inject_theme = inject_light

exec(compile(APP.read_text(encoding="utf-8"), str(APP), "exec"),
     {"__file__": str(APP), "__name__": "__main__"})
