"""EXECUTE · Feature 3 - Log Visit: one atomic save for visit, products, feedback, samples, follow-ups, plan link."""
from datetime import timedelta

import streamlit as st

from mednexa import config
from mednexa.core.dates import parse_date
from mednexa.core.errors import ServiceError, ValidationError
from mednexa.services import doctors, followups, inventory, plans, visits
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Log Visit", "Record what actually happened at a doctor visit.",
               stage="Execute", feature="Feature 3 · Visit & Sample Logging")
shell.show_flash()
rep_id = shell.require_rep("Visits are logged for one representative. Managers: choose 'Acting as' in the sidebar.")
st.markdown(f"<span class='mx-ctx'>Logging as <b>{shell.rep_label(rep_id)}</b></span>", unsafe_allow_html=True)

prefill = st.session_state.get(shell.K_LOG_PREFILL) or {}
docs = doctors.list_doctors(rep_id, ctx.business_date).sort_values("name")
ids = list(docs.doctor_id)
names = docs.set_index("doctor_id")
pre_doc = prefill.get("doctor_id")
doctor_id = st.selectbox("Doctor", ids, index=ids.index(pre_doc) if pre_doc in ids else 0,
                         format_func=lambda i: f"{names.loc[i, 'name']} · {names.loc[i, 'specialty']} · "
                                               f"{names.loc[i, 'area']} · {names.loc[i, 'segment']}", key="lv_doctor")

open_items = plans.list_items(rep_id=rep_id, as_of=ctx.business_date, doctor_id=doctor_id, statuses=["PLANNED"])
item_opts = [None] + list(open_items.plan_item_id)
pre_item = prefill.get("plan_item_id") if prefill.get("doctor_id") == doctor_id else None
plan_item_id = st.selectbox("Planned visit being completed", item_opts,
                            index=item_opts.index(pre_item) if pre_item in item_opts else (1 if len(item_opts) > 1 else 0),
                            format_func=lambda x: "Unplanned visit" if x is None else
                            f"{x} · planned {fmt.fmt_date(open_items.set_index('plan_item_id').loc[x, 'planned_date'])}",
                            key=f"lv_item_{doctor_id}")

c1, c2 = st.columns(2)
visit_date = c1.date_input("Visit date", ctx.business_date, min_value=ctx.business_date - timedelta(days=60),
                           max_value=ctx.business_date, format="DD/MM/YYYY", key="lv_date")
outcome = c2.selectbox("Visit outcome", config.OUTCOMES, index=None, placeholder="Select outcome", key="lv_outcome")

prods = inventory.stock()
pmap = prods.set_index("product_id")
ui.section_header("Products discussed & samples", "Stock is checked when you save")
chosen = st.multiselect("Products discussed", list(prods.product_id),
                        format_func=lambda p: f"{pmap.loc[p, 'product_name']} (stock {pmap.loc[p, 'current_stock']}"
                                              f" · {pmap.loc[p, 'status_label']})", key=f"lv_products_{doctor_id}")
products, issued = [], {}
for pid in chosen:
    a, b, c = st.columns([2, 2, 2])
    a.markdown(f"**{pmap.loc[pid, 'product_name']}**<br><span class='mx-muted'>stock {pmap.loc[pid, 'current_stock']} · "
               f"min {pmap.loc[pid, 'minimum_stock']}</span>", unsafe_allow_html=True)
    fb = b.selectbox("Feedback (optional)", ["—", *config.FEEDBACK], key=f"fb_{doctor_id}_{pid}")
    q = c.number_input("Samples issued", 0, 500, 0, key=f"q_{doctor_id}_{pid}")
    products.append({"product_id": pid, "feedback": None if fb == "—" else fb})
    if q:
        issued[pid] = int(q)

holdings = {k: v for k, v in visits.doctor_holdings(doctor_id).items() if v > 0}
returned = {}
with st.expander(f"Samples returned by the doctor ({sum(holdings.values())} unit(s) held)"):
    if not holdings:
        st.caption("This doctor holds no samples from earlier visits.")
    for pid, held in holdings.items():
        r = st.number_input(f"{pmap.loc[pid, 'product_name']} (holds {held})", 0, int(held), 0, key=f"ret_{doctor_id}_{pid}")
        if r:
            returned[pid] = int(r)

ui.section_header("Follow-ups")
pend = followups.list_followups(ctx.business_date, doctor_id=doctor_id, status="Pending")
close_ids = []
if pend.empty:
    st.caption("No pending follow-ups for this doctor.")
for r in pend.itertuples():
    label = f"Close {r.follow_up_id} (due {fmt.fmt_date(r.due_date)}" + (f", {r.days_overdue} days overdue)" if r.days_overdue else ")")
    if st.checkbox(label, value=parse_date(r.visit_date) <= visit_date, key=f"close_{r.follow_up_id}"):
        close_ids.append(r.follow_up_id)
need_fu = st.checkbox("Follow-up required after this visit", key=f"lv_needfu_{doctor_id}")
new_fu = None
if need_fu:
    f1, f2 = st.columns([1, 3])
    due = f1.date_input("Follow-up date", visit_date + timedelta(days=7), min_value=visit_date + timedelta(days=1),
                        format="DD/MM/YYYY", key="lv_fu_date")
    note = f2.text_input("Follow-up details", key="lv_fu_note")
    new_fu = {"due_date": due, "notes": note}
notes = st.text_area("Visit notes (optional)", key=f"lv_notes_{doctor_id}", height=80)

if st.button("Save visit", type="primary"):
    try:
        vid = visits.log_visit({"rep_id": rep_id, "doctor_id": doctor_id, "visit_date": visit_date, "outcome": outcome,
                                "notes": notes, "products": products, "issued": issued, "returned": returned,
                                "close_follow_up_ids": close_ids, "new_follow_up": new_fu,
                                "plan_item_id": plan_item_id}, as_of=ctx.business_date, actor=ctx.actor)
        st.session_state.pop(shell.K_LOG_PREFILL, None)
        parts = [f"Visit {vid} saved for {names.loc[doctor_id, 'name']}"]
        if issued:
            parts.append(f"{sum(issued.values())} sample(s) issued")
        if close_ids:
            parts.append(f"{len(close_ids)} follow-up(s) closed")
        if plan_item_id:
            parts.append(f"planned visit {plan_item_id} completed")
        if new_fu:
            parts.append(f"follow-up due {fmt.fmt_date(new_fu['due_date'])}")
        shell.flash(" · ".join(parts) + ".")
        st.rerun()
    except ValidationError as e:
        st.error("Please fix: " + "; ".join(e.field_errors.values()) if e.field_errors else e.user_message)
    except ServiceError as e:
        st.error(e.user_message)
