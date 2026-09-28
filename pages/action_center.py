"""ACT · Feature 5 - MedNexa Action Center."""
from datetime import timedelta

import streamlit as st

from mednexa import config
from mednexa.core.dates import next_working_day
from mednexa.core.errors import ServiceError
from mednexa.services import actions, plans
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Action Center", "Your field priorities for today." if not ctx.is_manager
               else "Team priorities: what each representative should do next.",
               stage="Act", feature="Feature 5 · Rep Action & Follow-up Management")
shell.show_flash()

rep_id = ctx.effective_rep_id
if ctx.role == config.ROLE_REP and rep_id is None:
    shell.require_rep()
df = ui.service_call(actions.open_actions, ctx.business_date, rep_id)
if df is None:
    st.stop()
s = actions.summary(df)
ui.kpi_row([
    ui.Kpi("Critical", fmt.fmt_int(s["CRITICAL"]), tone="critical", foot=f"≥{config.OVERDUE_CRITICAL_DAYS}d overdue / missed A"),
    ui.Kpi("High", fmt.fmt_int(s["HIGH"]), tone="warning"),
    ui.Kpi("Due today", fmt.fmt_int(s["due_today"]), tone="warning" if s["due_today"] else "neutral",
           foot=fmt.fmt_date(ctx.business_date)),
    ui.Kpi("Overdue follow-ups", fmt.fmt_int(s["overdue"]), tone="critical" if s["overdue"] else "neutral"),
    ui.Kpi("Upcoming", fmt.fmt_int(s["upcoming"] + s["prep"]), foot=f"{s['upcoming']} follow-ups · {s['prep']} visits"),
    ui.Kpi("Missed visits", fmt.fmt_int(s["missed"]), tone="critical" if s["missed"] else "neutral"),
])

f1, f2, f3 = st.columns([2, 3, 2])
prio = f1.multiselect("Priority", list(config.ACTION_PRIORITIES), key="ac_prio")
types = f2.multiselect("Action type", list(actions.TYPE_LABELS), format_func=actions.TYPE_LABELS.get, key="ac_type")
search = f3.text_input("Doctor", placeholder="Search doctor", key="ac_doc")
view = df
if prio:
    view = view[view.priority.isin(prio)]
if types:
    view = view[view.action_type.isin(types)]
if search:
    view = view[view.doctor_name.str.contains(search, case=False, regex=False)]

groups = actions.grouped(view)
if not groups:
    ui.empty_state("Nothing needs your attention", "No open actions match these filters for the business date.")
for i, g in enumerate(groups):
    count = g["count"]
    title = g["type_label"] + (f" ×{count}" if count > 1 else "")
    reason = g["reason"] if count == 1 else f"{count} pending follow-ups; oldest {g['max_late']} days overdue." \
        if g["action_type"] == "OVERDUE_FOLLOW_UP" else f"{count} items. {g['reason']}"
    ui.action_card(ui.ActionCardView(
        g["priority"], title, g["doctor_name"], f"{g['specialty']} · {g['area']} · {g['doctor_id']}", reason,
        g["recommended"], fmt.fmt_date(g["oldest_due"]),
        rep_label=shell.rep_label(g["rep_id"]) if ctx.is_manager else None, segment=g["segment"]))
    k = f"{i}_{g['keys'][0]}"
    cols = st.columns([1.1, 1.1, 1.3, 1, 3])
    if cols[0].button("View doctor", key=f"vd_{k}"):
        shell.open_doctor(g["doctor_id"])
    can_log = ctx.effective_rep_id == g["rep_id"]
    if g["action_type"] == "UPCOMING_VISIT_PREPARATION":
        if cols[1].button("Mark prepared", key=f"mp_{k}", type="primary"):
            for key in g["keys"]:
                actions.mark_prepared(key, ctx.actor)
            shell.flash(f"Preparation for {g['doctor_name']} marked done.")
            st.rerun()
        continue
    if cols[1].button("Log visit", key=f"lv_{k}", type="primary", disabled=not can_log,
                      help=None if can_log else "Act as this representative to log a visit"):
        shell.open_log_visit(g["doctor_id"], g["source_id"] if g["source_type"] == "PLAN_ITEM" else None)
    if g["source_type"] == "FOLLOW_UP":
        with cols[2].popover("Complete by contact"):
            note = st.text_input("What was done? (required)", key=f"note_{k}")
            if st.button("Complete follow-up", key=f"cc_{k}", type="primary"):
                try:
                    for key in g["keys"]:
                        actions.complete_followup_by_contact(key, note, ctx.business_date, ctx.actor)
                    shell.flash(f"{count} follow-up(s) for {g['doctor_name']} completed by contact.")
                    st.rerun()
                except ServiceError as e:
                    st.error(e.user_message)
        with cols[3].popover("Snooze"):
            until = st.date_input("Until", ctx.business_date + timedelta(days=2), min_value=ctx.business_date +
                                  timedelta(days=1), key=f"sz_{k}", format="DD/MM/YYYY")
            if st.button("Snooze", key=f"szb_{k}"):
                for key in g["keys"]:
                    actions.snooze(key, until, ctx.actor, ctx.business_date)
                st.rerun()
    else:  # missed visit -> Feature 2 reschedule/skip
        with cols[2].popover("Reschedule"):
            nd = st.date_input("New date", next_working_day(ctx.business_date), min_value=ctx.business_date,
                               key=f"rsd_{k}", format="DD/MM/YYYY")
            if st.button("Move visit", key=f"rsb_{k}", type="primary"):
                try:
                    plans.move(g["source_id"], nd, ctx.actor, ctx.business_date)
                    shell.flash(f"Visit to {g['doctor_name']} rescheduled to {fmt.fmt_date(nd)}.")
                    st.rerun()
                except ServiceError as e:
                    st.error(e.user_message)
        with cols[3].popover("Skip"):
            rsn = st.text_input("Reason", key=f"skr_{k}")
            if st.button("Skip visit", key=f"skb_{k}"):
                try:
                    plans.skip(g["source_id"], rsn, ctx.actor)
                    st.rerun()
                except ServiceError as e:
                    st.error(e.user_message)

with st.expander("Action history"):
    h = actions.history(60)
    if h.empty:
        st.caption("No action history yet.")
    else:
        st.dataframe(h[["at", "action_key", "from_status", "to_status", "actor", "note"]], hide_index=True,
                     width="stretch")
