"""PLAN · Feature 2 - Visit Planner."""
from datetime import timedelta

import streamlit as st

from mednexa import config
from mednexa.core.dates import add_working_days, parse_date
from mednexa.core.errors import ServiceError
from mednexa.services import plans
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Visit Planner" if ctx.is_manager else "My Visit Plan", "When should each doctor be visited?",
               stage="Plan", feature="Feature 2 · Visit Planner")
shell.show_flash()

if ctx.is_manager:
    reps = shell.rep_options()
    default = ctx.acting_rep_id if ctx.acting_rep_id in reps else reps[0]
    rep_id = st.selectbox("Representative", reps, index=reps.index(default), format_func=shell.rep_label,
                          key="plan_rep")
else:
    rep_id = shell.require_rep()

summ = ui.service_call(plans.rep_summary, rep_id, ctx.business_date)
if summ is None:
    st.stop()
ui.kpi_row([
    ui.Kpi("Doctors in territory", fmt.fmt_int(summ["doctors"]), foot=summ["rep"]["territory"], tone="primary"),
    ui.Kpi("Overdue follow-ups", fmt.fmt_int(summ["overdue"]), tone="critical" if summ["overdue"] else "neutral",
           foot="go on Day 1"),
    ui.Kpi("Follow-ups due this week", fmt.fmt_int(summ["due_this_week"]), tone="warning" if summ["due_this_week"] else "neutral"),
    ui.Kpi("Never visited", fmt.fmt_int(summ["never_visited"]), tone="accent" if summ["never_visited"] else "neutral"),
])

g1, g2, g3 = st.columns([1.4, 1, 1.4])
start = g1.date_input("Start date", ctx.business_date, min_value=ctx.business_date, format="DD/MM/YYYY", key="plan_start")
days = g2.number_input("Working days", 1, 26, config.PLAN_DEFAULT_DAYS, key="plan_days")
g3.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
if g3.button("Generate plan", type="primary", width="stretch"):
    try:
        run = plans.generate(rep_id, start, int(days), ctx.business_date, ctx.actor)
        shell.flash(f"Plan generated ({run}). Completed, skipped and manually moved visits were kept.")
        st.rerun()
    except ServiceError as e:
        st.error(e.user_message)
st.caption(f"Up to {config.PLAN_DAILY_CAPACITY} visits/day, Mon–Sat, own territory only. Score = follow-up urgency "
           f"40% · days since last visit 25% · prescriptions 25% · never visited 10%.")

window_end = add_working_days(start, int(days) - 1)
lookback = ctx.business_date - timedelta(days=14)
items = plans.list_items(rep_id=rep_id, as_of=ctx.business_date, date_from=min(lookback, start).isoformat(),
                         date_to=window_end.isoformat())
if items.empty:
    ui.empty_state("No plan yet", "Choose a start date and generate a plan.")
    st.stop()

TONE = {"HIGH": "critical", "MEDIUM": "warning", "LOW": "neutral"}
STATUS_TONE = {"COMPLETED": "success", "SKIPPED": "neutral", "CANCELLED": "neutral", "PLANNED": "info"}
show_closed = st.toggle("Show completed, skipped and removed visits", value=True)
if not show_closed:
    items = items[items.status == "PLANNED"]

for day, day_items in items.groupby("planned_date", sort=True):
    dd = parse_date(day)
    open_n = int((day_items.status == "PLANNED").sum())
    ui.section_header(fmt.fmt_date(dd, with_weekday=True).upper(),
                      f"{len(day_items)} visit(s) · {open_n} open" + (" · in the past" if dd < ctx.business_date else ""))
    for area, a_items in sorted(day_items.groupby("area"), key=lambda x: (-len(x[1]), x[0])):
        st.markdown(f"<div class='mx-side-label' style='color:var(--mx-accent)'>{area}</div>", unsafe_allow_html=True)
        for r in a_items.sort_values("score", ascending=False, na_position="last").itertuples():
            c1, c2 = st.columns([5, 2])
            status_html = ui.status_pill_html("MISSED", "critical") if r.missed else ui.status_pill_html(
                r.status, STATUS_TONE[r.status])
            score = "" if r.score != r.score or r.score is None else f" · score {r.score:.0f}"
            moved = f" · moved from {fmt.fmt_short_date(r.original_date)}" if r.original_date != r.planned_date else ""
            c1.markdown(
                f"{ui.status_pill_html(r.label + ' priority', TONE[r.label])} {status_html} "
                f"<b>{r.doctor_name}</b> {ui.segment_badge_html(r.segment)} "
                f"<span class='mx-muted'>{r.specialty} · {r.doctor_id}{score}{moved}</span><br>"
                f"{ui.chips_html([(x, 'critical' if 'overdue' in x else 'accent' if x == 'Never visited' else 'neutral') for x in r.reasons_list])}",
                unsafe_allow_html=True)
            if r.status != "PLANNED":
                c2.caption(r.status_note or "")
                continue
            b1, b2 = c2.columns(2)
            if b1.button("Log visit", key=f"log_{r.plan_item_id}", type="primary", width="stretch"):
                shell.open_log_visit(r.doctor_id, r.plan_item_id)
            with b2.popover("More", width="stretch"):
                nd = st.date_input("Move to", max(dd, ctx.business_date), min_value=ctx.business_date,
                                   key=f"mv_{r.plan_item_id}", format="DD/MM/YYYY")
                if st.button("Move", key=f"mvb_{r.plan_item_id}"):
                    try:
                        plans.move(r.plan_item_id, nd, ctx.actor, ctx.business_date)
                        shell.flash(f"{r.doctor_name} moved to {fmt.fmt_date(nd)}.")
                        st.rerun()
                    except ServiceError as e:
                        st.error(e.user_message)
                reason = st.text_input("Reason (skip/remove)", key=f"rs_{r.plan_item_id}")
                s1, s2 = st.columns(2)
                if s1.button("Skip", key=f"sk_{r.plan_item_id}"):
                    try:
                        plans.skip(r.plan_item_id, reason, ctx.actor)
                        st.rerun()
                    except ServiceError as e:
                        st.error(e.user_message)
                if s2.button("Remove", key=f"rm_{r.plan_item_id}"):
                    try:
                        plans.cancel(r.plan_item_id, reason, ctx.actor)
                        st.rerun()
                    except ServiceError as e:
                        st.error(e.user_message)
