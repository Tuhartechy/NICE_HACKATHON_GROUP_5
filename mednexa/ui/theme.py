"""
MedNexa visual system: CSS injected once per run + a Plotly template.

Direction: midnight surface, deep-teal structure, electric-lime used sparingly
for emphasis (brand mark, active navigation, key figures), warm off-white text,
amber/coral only for warning/critical states. Flat surfaces, 1px borders,
small radii, no gradients or glass effects.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from mednexa import config

T = config.THEME
PLOTLY_TEMPLATE_NAME = "mednexa"
TRANSPARENT = "rgba(0,0,0,0)"


def rgba(hex_colour: str, alpha: float) -> str:
    """'#RRGGBB', alpha -> 'rgba(r,g,b,alpha)' so every tint derives from a config token."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _tone_css(name: str, colour: str) -> str:
    return (f".mx-pill.mx-tone-{name} {{ color: {colour}; border-color: {rgba(colour, .55)}; "
            f"background: {rgba(colour, .08)}; }}\n"
            f".mx-chip.mx-tone-{name} {{ border-color: {rgba(colour, .55)}; }}")


def css() -> str:
    SEG = config.SEGMENT_COLORS
    TONE_CSS = "\n".join(_tone_css(n, T[k]) for n, k in (
        ("critical", "critical"), ("warning", "warning"), ("success", "success"),
        ("accent", "accent"), ("info", "info"), ("primary", "primary_bright")))
    return f"""
<style>
:root {{
  --mx-bg:{T['bg']}; --mx-surface:{T['surface']}; --mx-raised:{T['surface_raised']};
  --mx-border:{T['border']}; --mx-primary:{T['primary']}; --mx-primary-soft:{T['primary_soft']};
  --mx-accent:{T['accent']}; --mx-text:{T['text']}; --mx-muted:{T['muted']};
  --mx-warning:{T['warning']}; --mx-critical:{T['critical']}; --mx-success:{T['success']};
  --mx-info:{T['info']}; --mx-font:{config.FONT_STACK}; --mx-mono:{config.MONO_STACK};
}}
html, body, [data-testid="stApp"] {{ background: var(--mx-bg); color: var(--mx-text);
  font-family: var(--mx-font); }}
[data-testid="stApp"] p, [data-testid="stApp"] li {{ font-family: var(--mx-font); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stHeaderActionElements"], .mx-title a {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ padding-top: 2.2rem; max-width: 1320px; }}
h1, h2, h3, h4 {{ font-family: var(--mx-font); letter-spacing: -0.01em; color: var(--mx-text); }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{ background: {T['sidebar']}; border-right: 1px solid var(--mx-border); }}
[data-testid="stSidebarNav"] {{ padding-top: .25rem; }}
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] span {{
  color: var(--mx-muted) !important; font-size: .68rem !important; font-weight: 700 !important;
  letter-spacing: .16em; text-transform: uppercase; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 4px; border-left: 2px solid transparent; }}
[data-testid="stSidebarNavLink"] span {{ color: var(--mx-text); font-size: .92rem; }}
[data-testid="stSidebarNavLink"]:hover {{ background: var(--mx-surface); }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: var(--mx-primary-soft);
  border-left: 2px solid var(--mx-accent); }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: var(--mx-text); font-weight: 600; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: var(--mx-border); }}

/* ---------- widgets ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 4px; border: 1px solid var(--mx-border); background: var(--mx-surface);
  color: var(--mx-text); font-weight: 600; }}
.stButton > button:hover {{ border-color: var(--mx-primary); color: var(--mx-text); }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--mx-primary); border-color: var(--mx-primary); color: var(--mx-text); }}
.stButton > button[kind="primary"]:hover {{ background: {T['primary_hover']}; border-color: var(--mx-accent); }}
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-testid="stDateInput"] input {{
  border-radius: 4px !important; }}
[data-testid="stExpander"] details {{ border: 1px solid var(--mx-border); border-radius: 6px;
  background: var(--mx-surface); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--mx-border); border-radius: 6px; }}
[data-testid="stTabs"] button[aria-selected="true"] p {{ color: var(--mx-accent); }}

/* ---------- MedNexa components ---------- */
.mx-eyebrow {{ font-size: .7rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
  color: var(--mx-accent); margin-bottom: .35rem; }}
.mx-eyebrow .mx-eyebrow-sep {{ color: var(--mx-muted); margin: 0 .45rem; }}
.mx-eyebrow .mx-eyebrow-feature {{ color: var(--mx-muted); }}
.mx-title {{ font-size: 2rem; font-weight: 700; line-height: 1.15; margin: 0 0 .35rem 0; color: var(--mx-text); }}
.mx-subtitle {{ color: var(--mx-muted); font-size: 1rem; margin: 0 0 1.4rem 0; max-width: 760px; }}
.mx-section {{ display:flex; align-items:baseline; justify-content:space-between;
  border-bottom: 1px solid var(--mx-border); margin: 1.6rem 0 .9rem 0; padding-bottom: .45rem; }}
.mx-section h3 {{ font-size: .8rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
  color: var(--mx-text); margin: 0; }}
.mx-section span {{ color: var(--mx-muted); font-size: .8rem; }}

.mx-contextbar {{ display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; justify-content:flex-end;
  margin: -1.2rem 0 1.2rem 0; }}
.mx-ctx {{ display:inline-flex; gap:.4rem; align-items:center; border:1px solid var(--mx-border);
  background: var(--mx-surface); border-radius: 4px; padding: .22rem .6rem; font-size: .78rem; color: var(--mx-muted); }}
.mx-ctx b {{ color: var(--mx-text); font-weight: 600; }}
.mx-ctx.mx-ctx-override {{ border-color: var(--mx-warning); }}
.mx-ctx.mx-ctx-override b {{ color: var(--mx-warning); }}

.mx-kpi {{ background: var(--mx-surface); border: 1px solid var(--mx-border); border-radius: 6px;
  padding: .9rem 1rem .85rem 1rem; height: 100%; min-height: 112px; box-sizing: border-box; }}
.mx-kpi-label {{ font-size: .7rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: var(--mx-muted); }}
.mx-kpi-value {{ font-size: 1.85rem; font-weight: 700; color: var(--mx-text); margin-top: .25rem;
  font-variant-numeric: tabular-nums; line-height: 1.1; }}
.mx-kpi-foot {{ font-size: .78rem; color: var(--mx-muted); margin-top: .35rem; }}
.mx-kpi.mx-tone-accent {{ border-top: 2px solid var(--mx-accent); }}
.mx-kpi.mx-tone-warning {{ border-top: 2px solid var(--mx-warning); }}
.mx-kpi.mx-tone-critical {{ border-top: 2px solid var(--mx-critical); }}
.mx-kpi.mx-tone-primary {{ border-top: 2px solid var(--mx-primary); }}
.mx-delta-up {{ color: var(--mx-success); }} .mx-delta-down {{ color: var(--mx-critical); }}
.mx-delta-flat {{ color: var(--mx-muted); }}

.mx-badge {{ display:inline-block; min-width: 1.55rem; text-align:center; font-weight: 800; font-size: .74rem;
  border-radius: 3px; padding: .1rem .38rem; letter-spacing: .04em; font-family: var(--mx-mono); }}
.mx-seg-A {{ background: {rgba(SEG['A'], .14)}; color: {SEG['A']}; border:1px solid {rgba(SEG['A'], .45)}; }}
.mx-seg-B {{ background: {rgba(SEG['B'], .14)}; color: {SEG['B']}; border:1px solid {rgba(SEG['B'], .45)}; }}
.mx-seg-C {{ background: {rgba(SEG['C'], .12)}; color: {SEG['C']}; border:1px solid {rgba(SEG['C'], .40)}; }}

.mx-pill {{ display:inline-flex; align-items:center; gap:.3rem; font-size: .68rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; border-radius: 3px; padding: .14rem .5rem;
  border: 1px solid var(--mx-border); color: var(--mx-muted); background: transparent; }}
.mx-chip {{ display:inline-block; font-size: .76rem; color: var(--mx-text); background: var(--mx-raised);
  border: 1px solid var(--mx-border); border-radius: 3px; padding: .12rem .5rem; margin: 0 .3rem .3rem 0; }}
{TONE_CSS}

.mx-card {{ background: var(--mx-surface); border: 1px solid var(--mx-border); border-radius: 6px;
  padding: 1rem 1.1rem; margin-bottom: .75rem; }}
.mx-card.mx-prio-CRITICAL {{ border-left: 3px solid var(--mx-critical); }}
.mx-card.mx-prio-HIGH {{ border-left: 3px solid var(--mx-warning); }}
.mx-card.mx-prio-MEDIUM {{ border-left: 3px solid var(--mx-primary); }}
.mx-card.mx-prio-LOW {{ border-left: 3px solid var(--mx-border); }}
.mx-card-top {{ display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; margin-bottom:.55rem; }}
.mx-card-type {{ font-size: .7rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--mx-muted); }}
.mx-card-title {{ font-size: 1.12rem; font-weight: 700; color: var(--mx-text); margin: 0; }}
.mx-card-meta {{ color: var(--mx-muted); font-size: .85rem; margin: .15rem 0 .6rem 0; }}
.mx-card-grid {{ display:grid; grid-template-columns: max-content 1fr; gap:.25rem .9rem; font-size: .88rem; }}
.mx-card-grid dt {{ color: var(--mx-muted); }} .mx-card-grid dd {{ margin:0; color: var(--mx-text); }}
.mx-card-due {{ margin-left:auto; font-size: .82rem; color: var(--mx-muted); }}
.mx-card-due b {{ color: var(--mx-text); }}

.mx-state {{ border: 1px dashed var(--mx-border); border-radius: 6px; padding: 1.6rem 1.4rem;
  background: {rgba(T['surface'], .5)}; margin-bottom: .75rem; }}
.mx-state h4 {{ margin: 0 0 .35rem 0; font-size: 1.02rem; }}
.mx-state p {{ margin: 0; color: var(--mx-muted); font-size: .92rem; }}
.mx-state.mx-state-error {{ border-style: solid; border-color: {rgba(T['critical'], .55)}; }}
.mx-state.mx-state-error h4 {{ color: var(--mx-critical); }}

.mx-plan {{ background: var(--mx-surface); border: 1px solid var(--mx-border); border-radius: 6px; padding: 1.2rem 1.3rem; }}
.mx-plan-head {{ display:flex; align-items:center; gap:.6rem; margin-bottom:.8rem; }}
.mx-plan-head b {{ font-size: .95rem; }}
.mx-plan ul {{ margin: .2rem 0 0 0; padding-left: 1.1rem; color: var(--mx-text); }}
.mx-plan li {{ margin-bottom: .3rem; font-size: .92rem; }}
.mx-plan .mx-plan-foot {{ margin-top: .9rem; font-size: .8rem; color: var(--mx-muted); }}
.mx-plan code {{ font-family: var(--mx-mono); font-size: .78rem; color: var(--mx-info); background: transparent; }}

.mx-flow {{ display:flex; gap:0; flex-wrap:wrap; margin: .2rem 0 1.4rem 0; }}
.mx-flow-step {{ flex: 1 1 0; min-width: 120px; border: 1px solid var(--mx-border); border-right: none;
  padding: .55rem .75rem; background: var(--mx-surface); }}
.mx-flow-step:last-child {{ border-right: 1px solid var(--mx-border); }}
.mx-flow-step .k {{ font-size: .66rem; font-weight: 800; letter-spacing: .18em; color: var(--mx-muted); }}
.mx-flow-step .n {{ font-size: .86rem; color: var(--mx-text); margin-top: .1rem; }}
.mx-flow-step.mx-current {{ border-top: 2px solid var(--mx-accent); }}
.mx-flow-step.mx-current .k {{ color: var(--mx-accent); }}

.mx-brand {{ padding: .2rem 0 .6rem 0; }}
.mx-muted {{ color: var(--mx-muted); }}
.mx-side-label {{ font-size: .66rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: var(--mx-muted); margin: .4rem 0 .2rem 0; }}
.mx-dbstatus {{ font-size: .78rem; color: var(--mx-muted); display:flex; align-items:center; gap:.4rem; }}
.mx-dot {{ width:.5rem; height:.5rem; border-radius:50%; display:inline-block; }}
.mx-dot.ok {{ background: var(--mx-success); }} .mx-dot.off {{ background: var(--mx-warning); }}
</style>
"""


def plotly_template() -> go.layout.Template:
    return go.layout.Template(layout=dict(
        font=dict(family=config.FONT_STACK, color=T["text"], size=13),
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        colorway=list(config.CHART_COLORWAY),
        margin=dict(l=8, r=8, t=36, b=8),
        xaxis=dict(gridcolor=T["border"], linecolor=T["border"], zerolinecolor=T["border"],
                   tickfont=dict(color=T["muted"])),
        yaxis=dict(gridcolor=T["border"], linecolor=T["border"], zerolinecolor=T["border"],
                   tickfont=dict(color=T["muted"])),
        legend=dict(font=dict(color=T["muted"]), bgcolor=TRANSPARENT),
        hoverlabel=dict(bgcolor=T["surface_raised"], bordercolor=T["border"],
                        font=dict(color=T["text"], family=config.FONT_STACK)),
        title=dict(font=dict(size=14, color=T["text"]), x=0, xanchor="left"),
    ))


def register_plotly_template() -> str:
    pio.templates[PLOTLY_TEMPLATE_NAME] = plotly_template()
    return PLOTLY_TEMPLATE_NAME


def apply_theme() -> None:
    """Inject CSS and register the chart template. Call once per script run (app.py)."""
    import streamlit as st  # local import keeps css()/plotly_template() testable without a session

    st.html(css())
    register_plotly_template()
