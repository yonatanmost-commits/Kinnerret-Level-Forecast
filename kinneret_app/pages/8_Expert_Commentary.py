"""
8_Expert_Commentary.py  —  Expert Commentary

Dr. Wade Storm, hydraulic & meteorological modeling specialist, narrates the
full data story of the Kinneret level-forecast model: the wins (Signal Harvest,
0.694 -> 0.771) and the honest dead-ends (Architecture J). One live chart tracks
the R2 progression; its final point reads from docs/olympics_results.json so the
story stays true as the model is retrained.
"""
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_utils import PROJECT_ROOT
    from theme import inject_theme, style_plotly, PALETTE
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    PALETTE = {"aqua": "#2BD9C4", "ember": "#FF6B35", "gold": "#F2B441",
               "leaf": "#86E05A", "bone": "#F4EBDD"}
    def inject_theme():
        return None
    def style_plotly(fig, **kwargs):
        return fig

RESULTS_FILE = PROJECT_ROOT / "docs" / "olympics_results.json"
FALLBACK_R2 = 0.771  # last-known champion S2 R2 (radiation backfill, 2026-06-01)


def load_champion_r2() -> float:
    """Current champion S2 R2 from the live olympics file; fallback if absent."""
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        v = d["models"][d["winner"]]["cv_vol_r2_mean"]
        return float(v) if v is not None else FALLBACK_R2
    except Exception:
        return FALLBACK_R2


st.set_page_config(page_title="Expert Commentary", page_icon="🌊", layout="wide")
inject_theme()

champion_r2 = load_champion_r2()

# ── Title + byline ─────────────────────────────────────────────────────────────
st.markdown("<h1>🌊 Expert Commentary</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="kn-subtitle" style="margin-top:0.6rem;">'
    'The data story, told by the modeller who lived it'
    '</p>', unsafe_allow_html=True)
st.markdown(
    '<div class="expert-byline">'
    '<strong>Dr. Wade Storm</strong> &mdash; Hydraulic &amp; Meteorological '
    'Modeling Specialist<br>'
    'Commissioned review of the Lake Kinneret level-forecast model &middot; '
    '1 June 2026'
    '</div>', unsafe_allow_html=True)

# ── Essay movements ─────────────────────────────────────────────────────────────
def movement(label: str, body_html: str) -> None:
    st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
    st.markdown(f'<p class="kn-label">{label}</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="expert-essay">{body_html}</div>',
                unsafe_allow_html=True)


movement("What I was asked to do", """
<p>They handed me a model that already worked, and asked why it had stopped
getting better. Two stages of gradient boosting: the first reads the weather and
predicts how much water the Jordan pours into the lake; the second turns that
inflow, plus the lake's own recent behaviour, into tomorrow's change in volume,
which becomes a level. Honest engineering. But it had plateaued at a
cross-validated R&sup2; of <strong>0.694</strong> on the held-out years, and
nobody could say why. So I did what you always do when a model goes quiet: I
stopped looking at the model and started looking at the residuals.</p>
""")

movement("First, the data lied", """
<p>Before I could trust a single residual, I had to trust the data &mdash; and
it turned out 2023 was poisoned. The meteorological feed wrote a bare
<code>-</code> where a reading was missing; somewhere downstream that became a
sentinel, the daily aggregation took the <em>first</em> value instead of summing,
pandas quietly turned whole rainfall columns to NaN, and a path mismatch meant
the cleaned file wasn't even the one being read. Four small bugs in a chain, each
defensible alone, together fabricating a drought that never happened. You cannot
diagnose a model standing on poisoned ground. We fixed the data first &mdash; at
the source, in the pipeline, never with a patch in the feature code &mdash; and
only then did the residuals start telling the truth.</p>
""")

movement("Reading the residuals", """
<p>The first thing the clean residuals confessed was that the target was
violently lopsided: a skew of <strong>4.82</strong> and a kurtosis of
<strong>49</strong>. A handful of January flood days &mdash; 116 of them, just
<strong>2.4%</strong> of all days &mdash; carried <strong>58%</strong> of the
entire variance. The model was spending almost all of its effort wrestling a few
giants and leaving the ordinary days underserved. The second confession was an
absence: <code>outflow</code> &mdash; the water pumped south out of the lake,
measured every day, correlated <strong>0.606</strong> with the very thing we
predict &mdash; was sitting untouched in the feature table. The strongest unused
signal in the building, and nobody had opened the box.</p>
""")

movement("The Signal Harvest", """
<p>So we harvested. Six changes, each aimed at one confession. We put a
signed-log transform on the target so a thirty-million-cubic-metre flood stopped
shouting down every quiet day. We anchored yesterday's known outflow into the
second stage. We let the model see two and three days of the lake's own momentum,
not just one. We gave it sharper seasonal bumps and the <em>intensity</em> of
rain, not merely its total. And we slowed the learner down &mdash; gentler steps,
more of them. The plateau broke: cross-validated R&sup2; climbed from
<strong>0.694 to 0.758</strong>. Not magic &mdash; just signal that was there all
along, finally let in.</p>
""")

movement("When a sensor dies", """
<p>On 25 April 2026 the radiation sensor at the lake simply stopped, and with it
went the evaporation input the model leans on through the dry months. We
backfilled it from Open-Meteo's reanalysis so the live forecast would never again
run blind. Let me be precise about what that did and didn't buy us: the champion
now scores <strong>{champion:.3f}</strong>, up from 0.758, but that backfill is
2026 data &mdash; it lives <em>outside</em> the 2021&ndash;2024 cross-validation
folds. The headline number rose partly because the live inputs are now gap-free,
and partly because gradient boosting wobbles a little run to run. I will not sell
you a sensor repair as a modelling triumph.</p>
""".format(champion=champion_r2))

movement("The honest failure: Architecture J", """
<p>Now the dead-end, because you deserve it. The weak years fail in
<em>opposite</em> directions: 2023, a drought, the model over-predicts the
floods; 2021, after a wet autumn, it under-predicts them. That is the fingerprint
of a model blind to how wet the ground already is &mdash; the catchment's
memory. So I added it the obvious way: rolling 30- and 45-day rainfall totals,
&ldquo;Architecture J.&rdquo; It barely moved: <strong>+0.005</strong>, against
the +0.02 I'd have called a win. An honest negative result. The reason, in
hindsight, is physical: a flat sum of recent rain cannot encode
<em>saturation</em>. Forty millimetres on bone-dry ground and forty on a sodden
hillside produce wildly different runoff, and a sum treats them the same.</p>
""")

movement("What's still unsolved", """
<p>The fix Architecture J reached for is real; the instrument was wrong. What the
model needs is not a sum but a <strong>state</strong> &mdash; a soil-moisture
bucket that fills with rain, drains with evaporation, and saturates. Track
precipitation minus evapotranspiration as a decaying store and you give the model
the one thing it still lacks: a sense of how much more the ground can hold before
it sheds water into the lake. That is the next chapter, and I think it is where
the next real gain lives. Until then, the honest scoreboard reads
<strong>{champion:.3f}</strong> &mdash; hard-won, and not yet finished.</p>
""".format(champion=champion_r2))

# ── Signature visual: R2 progression timeline ──────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">The climb, milestone by milestone</p>',
            unsafe_allow_html=True)

milestones = [
    ("Baseline", 0.694),
    ("Signal Harvest", 0.758),
    ("Architecture J", 0.763),
    ("Radiation backfill", champion_r2),
]
labels = [m[0] for m in milestones]
values = [m[1] for m in milestones]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=labels, y=values, mode="lines+markers+text",
    text=[f"{v:.3f}" for v in values], textposition="top center",
    textfont=dict(color=PALETTE["bone"], size=12),
    line=dict(color=PALETTE["aqua"], width=3),
    marker=dict(size=11, color=PALETTE.get("aqua_bright", PALETTE["aqua"]),
                line=dict(color=PALETTE["ember"], width=1.5)),
    hovertemplate="%{x}<br>S2 R&sup2; = %{y:.3f}<extra></extra>",
))
fig.update_yaxes(title_text="cross-validated S2 R²", range=[0.66, 0.80])
style_plotly(fig, height=340, legend=False)
st.plotly_chart(fig, width="stretch")
st.markdown(
    '<p style="color:var(--bone-faint);font-family:Space Mono,monospace;'
    'font-size:0.7rem;margin-top:-0.4rem">'
    'Baseline through Architecture J are historical milestones; the final point '
    'reads live from docs/olympics_results.json.</p>',
    unsafe_allow_html=True)

# ── Signature ───────────────────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown(
    '<div class="expert-sig">Dr. Wade Storm</div>'
    '<div class="expert-sig-title">Hydraulic &amp; Meteorological Modeling '
    'Specialist</div>', unsafe_allow_html=True)
