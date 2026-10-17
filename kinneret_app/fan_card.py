"""The long-range fan card: the next 12 months as a range, with the red-line odds.

Draws Models/longrange_fan.json (written monthly by Automation/fan_today.py). The path
can be overridden with KINNERET_FAN_FILE (tests). A missing file shows a note, not an error.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_utils import PROJECT_ROOT
from theme import PALETTE, style_plotly

FAN_FILE = PROJECT_ROOT / "Models" / "longrange_fan.json"


def load_fan():
    p = Path(os.environ.get("KINNERET_FAN_FILE", FAN_FILE))
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


MONTH = 365.25 / 12


def _point(fan, days, tol=3):
    """The horizon the model forecast within `tol` days of `days`, or None. Never a line
    between horizons: the lake's spring peak sits between them."""
    near = [h for h in fan["horizons"] if abs(h["H"] - days) <= tol]
    return min(near, key=lambda h: abs(h["H"] - days)) if near else None


def _at(fan, key, days):
    h = _point(fan, days)
    return None if h is None else float(h[key])


def _months(fan):
    """The month-by-month points (about every 30 days, 1 to 12 months), if the file has them."""
    out = [_point(fan, k * MONTH) for k in range(1, 13)]
    return [h for h in out if h is not None] if all(out) else []


def _band(fig, x, lo, hi, alpha, name):
    fig.add_trace(go.Scatter(x=list(x) + list(x[::-1]), y=list(hi) + list(lo[::-1]), fill="toself", mode="lines",
                             fillcolor=f"rgba(43,217,196,{alpha})", line=dict(width=0),
                             hoverinfo="skip", name=name))


def render(history: pd.Series = None):
    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="kn-label">The next 12 months · range and red-line odds</div>',
                unsafe_allow_html=True)
    fan = load_fan()
    if fan is None:
        st.markdown("The long-range forecast is not available yet.")
        return
    t0 = pd.Timestamp(fan["start"])
    red, upper = fan["lines"]["red"], fan["lines"]["upper"]
    p12 = _at(fan, "p_red", 365)

    if _point(fan, 182) is not None:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("In 6 months, most likely", f"{_at(fan, 'median', 182):.2f} m",
                      help=f"80% range {_at(fan, 'lo_80', 182):.2f} to {_at(fan, 'hi_80', 182):.2f} m")
        with c2:
            st.metric(f"Below {red:.0f} m in 6 months", f"{_at(fan, 'p_red', 182):.0%}")
    else:
        c1, c3 = st.columns(2)
        with c1:
            st.metric("In 12 months, most likely", f"{_at(fan, 'median', 365):.2f} m",
                      help=f"80% range {_at(fan, 'lo_80', 365):.2f} to {_at(fan, 'hi_80', 365):.2f} m")
    with c3:
        st.metric(f"Below {red:.0f} m in 12 months", f"{p12:.0%}")

    hs = [{"H": 0, "median": fan["level0"], **{f"{s}_{k}": fan["level0"] for k in (50, 80, 90)
                                                for s in ("lo", "hi")}}] + fan["horizons"]
    x = [t0 + pd.Timedelta(days=h["H"]) for h in hs]
    col = lambda k: np.array([h[k] for h in hs])
    fig = go.Figure()
    _band(fig, x, col("lo_90"), col("hi_90"), 0.10, "90% range")
    _band(fig, x, col("lo_80"), col("hi_80"), 0.18, "80% range")
    _band(fig, x, col("lo_50"), col("hi_50"), 0.30, "50% range")
    if history is not None:
        h = history[history.index <= t0]
        fig.add_trace(go.Scatter(x=h.index, y=h.values, mode="lines", name="observed level",
                                 line=dict(color=PALETTE["bone_dim"], width=2)))
    fig.add_trace(go.Scatter(x=x, y=col("median"), mode="lines+markers", name="most likely",
                             line=dict(color=PALETTE["aqua_bright"], width=2.6)))
    for s, colr in zip(fan["scenarios"], (PALETTE["leaf"], PALETTE["gold"])):
        fig.add_trace(go.Scatter(x=[t0] + [t0 + pd.Timedelta(days=p["H"]) for p in s["path"]],
                                 y=[fan["level0"]] + [p["level"] for p in s["path"]], mode="lines",
                                 line=dict(color=colr, width=1.4, dash="dot"),
                                 name=f"winter like {s['winter']} ({s['kind']})"))
    fig.add_hline(y=red, line_dash="dot", line_color=PALETTE["ember"],
                  annotation_text=f"lower red line {red:.1f} m", annotation_position="bottom left",
                  annotation_font_color=PALETTE["ember"])
    fig.add_hline(y=upper, line_dash="dot", line_color=PALETTE["leaf"], opacity=0.5,
                  annotation_text=f"upper red line {upper:.1f} m", annotation_position="top left",
                  annotation_font_color=PALETTE["leaf"])
    fig.update_layout(yaxis_title="level (m MSL)", legend=dict(orientation="h", y=-0.12, x=0))
    style_plotly(fig, height=480)
    fig.update_layout(margin=dict(b=90))
    st.plotly_chart(fig, width="stretch")

    months = _months(fan)
    if months:
        st.dataframe(pd.DataFrame({
            "month": [pd.Timestamp(h["date"]).strftime("%b %Y") for h in months],
            "most likely (m)": [round(h["median"], 2) for h in months],
            "80% range (m)": [f"{h['lo_80']:.2f} to {h['hi_80']:.2f}" for h in months],
            f"chance below {red:.0f} m": [f"{h['p_red']:.0%}" for h in months]}),
            hide_index=True, width="stretch")

    s = fan.get("seasonal") or {}
    lean = ""
    if s.get("season_ratio") is not None:
        r = s["season_ratio"]
        word = ("wetter" if r > 1.15 else "slightly wetter" if r > 1.03 else
                "drier" if r < 0.85 else "slightly drier" if r < 0.97 else "about normal")
        lean = (f" The {s['source']} seasonal forecast ({pd.Timestamp(s['init']):%B %Y}) leans {word}: "
                f"season rain {r:.2f}× normal, {s['rank']} of {s['of']} since 1993.")
    st.markdown(
        f"Made from **{t0.day} {t0:%b %Y}** (level {fan['level0']:.2f} m). Each past winter's weather is run "
        f"through the model, weighted by how well it matches the seasonal forecast, plus the "
        f"model's own past errors.{lean} Chance still below {red:.0f} m in 12 months: **{p12:.0%}**.")
    st.caption(f"{fan['model']} · made {fan['made_on']} · refreshed monthly after the seasonal "
               f"forecast (5th) · tested 2011-2025: the 80% range held the outcome 78-82% of the time "
               f"up to 8 months ahead, 73% at 12 months.")
