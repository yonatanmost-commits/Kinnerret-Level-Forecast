import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date
from app_utils import (
    load_gold, PROJECT_ROOT,
    LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX,
)
from theme import inject_theme, style_plotly, PALETTE

st.set_page_config(
    page_title="Days to Red Line · Kinneret",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()

st.title("⏳ Days to the Red Line")
st.markdown(
    '<div style="font-family:\'Space Mono\',monospace;font-size:0.72rem;'
    'letter-spacing:0.18em;color:var(--ember);text-transform:uppercase;'
    'margin-top:-0.8rem;margin-bottom:1.5rem;">'
    'When does the lake cross the lower red line · summer recession is near-deterministic'
    '</div>',
    unsafe_allow_html=True,
)

RED = LEVEL_LEGAL_MIN          # -213.00 m, lower management line
CLIM_FROM_YEAR = 2005          # recent-decades climatology (reflects current pumping/climate)
OBS_WINDOW = 21                # days of recent trajectory used to gauge this year's anomaly
SCALE_CLAMP = (0.45, 1.6)      # keep the anomaly multiplier physically sane
HORIZON = 400                  # max days to project forward


# ── Deep level history (1966+) for the seasonal recession shape ────────────────
@st.cache_data
def load_level_history() -> pd.Series:
    path = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").set_index("date")
    daily = df["kinneret_level"].resample("D").mean().interpolate("linear")
    return daily


@st.cache_data
def seasonal_recession_rate() -> pd.Series:
    """Mean daily level change by day-of-year (m/day), recent decades, smoothed.
    Negative = falling. Indexed 1..366."""
    daily = load_level_history()
    d = daily.diff()
    d = d[d.index.year >= CLIM_FROM_YEAR]
    doy = d.groupby(d.index.dayofyear).mean()
    doy = doy.reindex(range(1, 367)).interpolate()
    # wrap-aware smoothing so 31 Dec → 1 Jan is continuous
    ext = pd.concat([doy, doy, doy]).rolling(15, center=True, min_periods=1).mean()
    return ext.iloc[366:732].set_axis(range(1, 367))


def project(start_level, start_date, rate_by_doy, scale):
    """Step the level forward day-by-day; return (crossing_date, days, path_df)."""
    rows = [(start_date, start_level)]
    lvl, dt = start_level, start_date
    crossing = None
    for _ in range(HORIZON):
        dt = dt + pd.Timedelta(days=1)
        lvl += rate_by_doy[dt.dayofyear] * scale
        rows.append((dt, lvl))
        if crossing is None and lvl <= RED:
            crossing = dt
            # keep drawing ~20 days past the crossing for context, then stop
            if (dt - start_date).days > 0 and len(rows) > 0:
                pass
        if crossing is not None and (dt - crossing).days >= 25:
            break
    path = pd.DataFrame(rows, columns=["date", "level"])
    days = (crossing - start_date).days if crossing is not None else None
    return crossing, days, path


# ── Anchor on the current reading (consistent with the rest of the app) ────────
gold = load_gold()
valid = gold.dropna(subset=["level_m"])
last = valid.iloc[-1]
anchor_level = float(last["level_m"])
anchor_date = pd.Timestamp(last["date"])
gap = anchor_level - RED

rate_by_doy = seasonal_recession_rate()

# This year's recent observed rate vs the climatological rate over the same window
hist = load_level_history()
win_end = min(anchor_date, hist.index[-1])
win_start = win_end - pd.Timedelta(days=OBS_WINDOW)
obs_rate = (hist.loc[win_end] - hist.loc[win_start]) / OBS_WINDOW
clim_win = np.mean([rate_by_doy[d.dayofyear]
                    for d in pd.date_range(win_start, win_end)])
# scale only meaningful while both are falling; clamp for sanity
if clim_win < -1e-4:
    scale = float(np.clip(obs_rate / clim_win, *SCALE_CLAMP))
else:
    scale = 1.0

# Three scenarios: central (this-year-scaled), fast (full climatology),
# slow (this year's gentleness persists a touch further)
cross_c, days_c, path_c = project(anchor_level, anchor_date, rate_by_doy, scale)
cross_f, days_f, path_f = project(anchor_level, anchor_date, rate_by_doy, 1.0)
slow_scale = min(scale, 1.0) * 0.82
cross_s, days_s, path_s = project(anchor_level, anchor_date, rate_by_doy, slow_scale)


def fmt(dt, days):
    if dt is None:
        return "—", "no crossing within a year"
    today = pd.Timestamp(date.today())
    from_now = (dt - today).days
    return dt.strftime("%d %b %Y"), f"{from_now:+d} days from today"


cdate, cfrom = fmt(cross_c, days_c)

# ── Already below? ─────────────────────────────────────────────────────────────
if gap <= 0:
    st.markdown(
        f'<div class="state-banner" style="border-left-color:var(--ember);">'
        f'<b style="color:var(--ember)">Already below the red line.</b> &nbsp; '
        f'Current level {anchor_level:+.3f} m is {abs(gap):.2f} m under the '
        f'{RED:.1f} m line.</div>',
        unsafe_allow_html=True,
    )

# ── Hero readout ────────────────────────────────────────────────────────────────
band_lo = cross_f.strftime("%d %b") if cross_f is not None else "—"
band_hi = cross_s.strftime("%d %b") if cross_s is not None else "—"

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,rgba(255,107,53,0.10),
         rgba(30,26,19,0.6));border:1px solid var(--hairline);
         border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;">
      <div style="font-family:'Space Mono',monospace;font-size:0.66rem;
           letter-spacing:0.22em;color:var(--bone-dim);text-transform:uppercase;">
        Projected crossing of the lower red line ({RED:.1f} m)</div>
      <div style="font-family:'Space Mono',monospace;font-size:2.4rem;
           font-weight:700;color:var(--ember-bright);line-height:1.15;
           margin-top:0.2rem;">{cdate}</div>
      <div style="font-family:'Space Mono',monospace;font-size:0.9rem;
           color:var(--bone);">{cfrom}</div>
      <div style="font-family:'Space Mono',monospace;font-size:0.72rem;
           color:var(--bone-dim);margin-top:0.5rem;">
        honest band &nbsp;<b style="color:var(--bone)">{band_lo} → {band_hi}</b>
        &nbsp;·&nbsp; faster if recession steepens to climatology, later if this
        year stays gentle</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Metric strip ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Current level", f"{anchor_level:+.3f} m",
              help=f"Last reading {anchor_date.date():%d %b %Y}")
with c2:
    st.metric("Gap to red line", f"{gap:+.3f} m")
with c3:
    st.metric("Recession now", f"{obs_rate*1000:.1f} mm/day",
              help=f"Observed over the last {OBS_WINDOW} days")
with c4:
    st.metric("Anomaly vs normal", f"{scale:.2f}×",
              help="This year's recession relative to the recent-decades "
                   "seasonal rate. <1 = gentler (started fuller); >1 = steeper.")

# ── Chart: recent history + projected descent with band ────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="kn-label">The descent to the red line</div>',
            unsafe_allow_html=True)

hist_tail = hist[hist.index >= anchor_date - pd.Timedelta(days=120)]

fig = go.Figure()

# Uncertainty band between fast (climatology) and slow (gentle) paths
m = min(len(path_f), len(path_s))
band_x = list(path_f["date"][:m]) + list(path_s["date"][:m][::-1])
band_y = list(path_f["level"][:m]) + list(path_s["level"][:m][::-1])
fig.add_trace(go.Scatter(
    x=band_x, y=band_y, fill="toself",
    fillcolor="rgba(255,107,53,0.12)", line=dict(width=0),
    hoverinfo="skip", showlegend=True, name="uncertainty band",
))

# Recent actual level
fig.add_trace(go.Scatter(
    x=hist_tail.index, y=hist_tail.values, mode="lines",
    line=dict(color=PALETTE["aqua"], width=2.4), name="observed level",
))

# Central projection
fig.add_trace(go.Scatter(
    x=path_c["date"], y=path_c["level"], mode="lines",
    line=dict(color=PALETTE["ember"], width=2.4, dash="dash"),
    name="projected (central)",
))

# Red line + crossing marker
fig.add_hline(y=RED, line_dash="dot", line_color=PALETTE["ember"],
              annotation_text=f"lower red line {RED:.1f} m",
              annotation_position="bottom left",
              annotation_font_color=PALETTE["ember"])
fig.add_hline(y=LEVEL_LEGAL_MAX, line_dash="dot",
              line_color=PALETTE["leaf"], opacity=0.4)

if cross_c is not None:
    fig.add_trace(go.Scatter(
        x=[cross_c], y=[RED], mode="markers+text",
        marker=dict(color=PALETTE["ember_bright"], size=11,
                    line=dict(color=PALETTE["bone"], width=1)),
        text=[f"  {cross_c:%d %b}"], textposition="top right",
        textfont=dict(color=PALETTE["bone"], size=11),
        name="crossing", showlegend=False,
    ))

fig.update_layout(
    yaxis_title="level (m MSL)",
    xaxis_title=None,
    legend=dict(orientation="h", y=1.08, x=0),
)
style_plotly(fig, height=420)
st.plotly_chart(fig, width="stretch")

# ── Method & the human wildcard ────────────────────────────────────────────────
with st.expander("How this is calculated — and the one thing it can't see"):
    st.markdown(
        f"""
**Why this forecast has skill (unlike a long-range one).**
In summer, rainfall over the basin is ≈ 0, so the lake level is governed by
evaporation and pumping — both slow and seasonal. The level becomes a
near-deterministic descent rather than a chaotic one.

**The method (anomaly-scaled seasonal recession):**
1. From the deep level record ({CLIM_FROM_YEAR}+), the **mean daily level change
   for each day of the year** is computed — the climatological recession shape.
   It deepens to its worst in **July–August** (≈ −10 mm/day) and eases through
   autumn.
2. This year's recession over the last **{OBS_WINDOW} days**
   ({obs_rate*1000:.1f} mm/day) is compared to that climatology to get an
   **anomaly multiplier** ({scale:.2f}×). Below 1 means the lake started fuller
   and is falling more gently than average.
3. That multiplier is carried **forward through the seasonal ramp** — so the
   forecast respects both this year's gentleness *and* the coming July–August
   evaporation peak. The crossing is where the projected level first touches
   **{RED:.1f} m**.

**Scenarios shown:** central = {scale:.2f}× · fast edge = full climatology
(1.0×) · slow edge = {slow_scale:.2f}×.

**The one thing the math can't see — pumping.** Evaporation is reliable;
extraction is *policy*. If Mekorot dials pumping up or down this summer, the
crossing slides accordingly. This is a forecast of the physics, not of a
decision someone makes in an office.
"""
    )

st.caption(
    f"Anchored on {anchor_date.date():%d %b %Y} · climatology {CLIM_FROM_YEAR}+ · "
    f"recomputes automatically as the level updates."
)
