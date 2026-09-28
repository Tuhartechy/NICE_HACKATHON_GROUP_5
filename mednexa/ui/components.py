"""
Reusable MedNexa UI components shared by every feature page.

Each component has a pure `*_html()` builder (escaped, unit-testable) and, where
useful, a render helper that writes it with Streamlit. Components only present
values they are given; they never query data or apply business rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Callable, Iterable, Sequence

import streamlit as st

from mednexa import config

TONES = ("neutral", "primary", "accent", "success", "info", "warning", "critical")


def _e(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def _tone(tone: str | None) -> str:
    return tone if tone in TONES else "neutral"


def _md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------------------- headers
def page_header_html(title: str, subtitle: str | None = None, *, stage: str | None = None,
                     feature: str | None = None) -> str:
    eyebrow = ""
    if stage or feature:
        parts = []
        if stage:
            parts.append(_e(stage))
        if feature:
            sep = '<span class="mx-eyebrow-sep">/</span>' if stage else ""
            parts.append(f'{sep}<span class="mx-eyebrow-feature">{_e(feature)}</span>')
        eyebrow = f'<div class="mx-eyebrow">{"".join(parts)}</div>'
    sub = f'<p class="mx-subtitle">{_e(subtitle)}</p>' if subtitle else ""
    return f'{eyebrow}<h1 class="mx-title">{_e(title)}</h1>{sub}'


def page_header(title: str, subtitle: str | None = None, *, stage: str | None = None,
                feature: str | None = None) -> None:
    _md(page_header_html(title, subtitle, stage=stage, feature=feature))


def section_header_html(title: str, note: str | None = None) -> str:
    n = f"<span>{_e(note)}</span>" if note else ""
    return f'<div class="mx-section"><h3>{_e(title)}</h3>{n}</div>'


def section_header(title: str, note: str | None = None) -> None:
    _md(section_header_html(title, note))


# ----------------------------------------------------------------- KPI tiles
@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    foot: str | None = None
    tone: str = "neutral"
    delta: str | None = None
    delta_direction: str | None = None    # "up" | "down" | "flat"


def kpi_tile_html(k: Kpi) -> str:
    foot_parts = []
    if k.delta:
        cls = {"up": "mx-delta-up", "down": "mx-delta-down"}.get(k.delta_direction or "", "mx-delta-flat")
        foot_parts.append(f'<span class="{cls}">{_e(k.delta)}</span>')
    if k.foot:
        foot_parts.append(_e(k.foot))
    foot = f'<div class="mx-kpi-foot">{" · ".join(foot_parts)}</div>' if foot_parts else ""
    return (f'<div class="mx-kpi mx-tone-{_tone(k.tone)}">'
            f'<div class="mx-kpi-label">{_e(k.label)}</div>'
            f'<div class="mx-kpi-value">{_e(k.value)}</div>{foot}</div>')


def kpi_row(kpis: Sequence[Kpi]) -> None:
    if not kpis:
        return
    cols = st.columns(len(kpis))
    for col, k in zip(cols, kpis):
        with col:
            _md(kpi_tile_html(k))


# ----------------------------------------------------------------- badges, pills, chips
def segment_badge_html(segment: str | None) -> str:
    seg = (segment or "").upper()
    if seg not in {s for s, *_ in config.SEGMENT_RULES}:
        return '<span class="mx-badge mx-seg-C">?</span>'
    return f'<span class="mx-badge mx-seg-{seg}" title="Segment {seg}">{seg}</span>'


def status_pill_html(text: str, tone: str = "neutral") -> str:
    return f'<span class="mx-pill mx-tone-{_tone(tone)}">{_e(text)}</span>'


def reason_chip_html(text: str, tone: str = "neutral") -> str:
    return f'<span class="mx-chip mx-tone-{_tone(tone)}">{_e(text)}</span>'


def chips_html(items: Iterable[tuple[str, str] | str]) -> str:
    out = []
    for it in items:
        text, tone = (it, "neutral") if isinstance(it, str) else it
        out.append(reason_chip_html(text, tone))
    return "".join(out)


PRIORITY_TONES = {"CRITICAL": "critical", "HIGH": "warning", "MEDIUM": "primary", "LOW": "neutral"}


# ----------------------------------------------------------------- cards
@dataclass(frozen=True)
class ActionCardView:
    """Presentation model for an Action Center card (values are computed by services)."""
    priority: str
    action_type_label: str
    doctor_name: str
    doctor_meta: str
    reason: str
    recommended: str
    due_label: str
    rep_label: str | None = None
    segment: str | None = None
    extra_chips: tuple = field(default_factory=tuple)


def action_card_html(a: ActionCardView) -> str:
    prio = a.priority if a.priority in PRIORITY_TONES else "LOW"
    seg = segment_badge_html(a.segment) if a.segment else ""
    rep = f"<dt>Representative</dt><dd>{_e(a.rep_label)}</dd>" if a.rep_label else ""
    chips = f'<div style="margin-top:.6rem">{chips_html(a.extra_chips)}</div>' if a.extra_chips else ""
    return (
        f'<div class="mx-card mx-prio-{prio}">'
        f'<div class="mx-card-top">{status_pill_html(prio, PRIORITY_TONES[prio])}'
        f'<span class="mx-card-type">{_e(a.action_type_label)}</span>'
        f'<span class="mx-card-due">Due <b>{_e(a.due_label)}</b></span></div>'
        f'<p class="mx-card-title">{_e(a.doctor_name)} {seg}</p>'
        f'<div class="mx-card-meta">{_e(a.doctor_meta)}</div>'
        f'<dl class="mx-card-grid"><dt>Why</dt><dd>{_e(a.reason)}</dd>'
        f'<dt>Next step</dt><dd>{_e(a.recommended)}</dd>{rep}</dl>{chips}</div>'
    )


def action_card(a: ActionCardView) -> None:
    _md(action_card_html(a))


@dataclass(frozen=True)
class DoctorCardView:
    name: str
    specialty: str
    area: str
    segment: str | None
    potential_label: str
    monthly_prescriptions: str
    note: str | None = None


def doctor_card_html(d: DoctorCardView) -> str:
    note = f'<div class="mx-card-meta" style="margin-top:.5rem">{_e(d.note)}</div>' if d.note else ""
    return (
        f'<div class="mx-card"><p class="mx-card-title">{_e(d.name)} {segment_badge_html(d.segment)}</p>'
        f'<div class="mx-card-meta">{_e(d.specialty)} · {_e(d.area)}</div>'
        f'<dl class="mx-card-grid"><dt>Potential</dt><dd>{_e(d.potential_label)}</dd>'
        f'<dt>Monthly Rx</dt><dd>{_e(d.monthly_prescriptions)}</dd></dl>{note}</div>'
    )


# ----------------------------------------------------------------- states
def empty_state_html(title: str, message: str) -> str:
    return f'<div class="mx-state"><h4>{_e(title)}</h4><p>{_e(message)}</p></div>'


def empty_state(title: str, message: str) -> None:
    _md(empty_state_html(title, message))


def error_state_html(message: str, title: str = "We couldn't load this view") -> str:
    return f'<div class="mx-state mx-state-error"><h4>{_e(title)}</h4><p>{_e(message)}</p></div>'


def error_state(message: str, title: str = "We couldn't load this view") -> None:
    _md(error_state_html(message, title))


def service_call(fn: Callable, *args, fallback=None, error_title: str = "We couldn't load this view", **kwargs):
    """Run a service call; show a friendly error state instead of a traceback on ServiceError."""
    from mednexa.core.errors import ServiceError

    try:
        return fn(*args, **kwargs)
    except ServiceError as exc:
        error_state(exc.user_message, error_title)
        return fallback


# ----------------------------------------------------------------- product flow + milestone placeholders
FLOW = (("KNOW", "Doctor Intelligence"), ("PLAN", "Visit Planner"), ("EXECUTE", "Visit & Sample Logging"),
        ("ANALYZE", "Manager Dashboard"), ("ACT", "Action Center"))


def flow_strip_html(current: str | None = None) -> str:
    steps = []
    for key, name in FLOW:
        cls = "mx-flow-step mx-current" if key == current else "mx-flow-step"
        steps.append(f'<div class="{cls}"><div class="k">{key}</div><div class="n">{_e(name)}</div></div>')
    return f'<div class="mx-flow">{"".join(steps)}</div>'


def flow_strip(current: str | None = None) -> None:
    _md(flow_strip_html(current))


def milestone_panel_html(milestone: int, heading: str, items: Sequence[str],
                         services: Sequence[str] = ()) -> str:
    lis = "".join(f"<li>{_e(i)}</li>" for i in items)
    svc = ""
    if services:
        svc = ('<div class="mx-plan-foot">Backed by '
               + ", ".join(f"<code>{_e(s)}</code>" for s in services) + "</div>")
    return (f'<div class="mx-plan"><div class="mx-plan-head">'
            f'{status_pill_html(f"Milestone {milestone}", "accent")}<b>{_e(heading)}</b></div>'
            f"<ul>{lis}</ul>{svc}</div>")


def milestone_panel(milestone: int, heading: str, items: Sequence[str], services: Sequence[str] = ()) -> None:
    _md(milestone_panel_html(milestone, heading, items, services))


# ----------------------------------------------------------------- filters
@dataclass(frozen=True)
class FilterSpec:
    key: str
    label: str
    options: Sequence
    default: object = None
    kind: str = "select"          # "select" | "multiselect"
    format_func: Callable | None = None


def filter_bar(specs: Sequence[FilterSpec], *, key_prefix: str) -> dict:
    """Render a row of filters and return {spec.key: value}. Filtering itself happens in services."""
    if not specs:
        return {}
    values = {}
    cols = st.columns(len(specs))
    for col, s in zip(cols, specs):
        with col:
            kwargs = {"format_func": s.format_func} if s.format_func else {}
            wkey = f"{key_prefix}_{s.key}"
            if s.kind == "multiselect":
                values[s.key] = st.multiselect(s.label, list(s.options), default=s.default or [],
                                               key=wkey, **kwargs)
            else:
                opts = list(s.options)
                idx = opts.index(s.default) if s.default in opts else 0
                values[s.key] = st.selectbox(s.label, opts, index=idx, key=wkey, **kwargs)
    return values
