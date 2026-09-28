"""EXECUTE · Feature 3 - Visit History."""
import streamlit as st

from mednexa import config
from mednexa.services import visits
from mednexa.ui import components as ui, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Visit History", "What actually happened in the field.",
               stage="Execute", feature="Feature 3 · Visit & Sample Logging")
df = ui.service_call(visits.history, rep_id=ctx.effective_rep_id)
if df is None:
    st.stop()
c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
q = c1.text_input("Doctor", placeholder="Search doctor", key="vh_q")
rng = c2.date_input("Dates", (), format="DD/MM/YYYY", key="vh_dates")
oc = c3.multiselect("Outcome", [*config.OUTCOMES, config.NOT_RECORDED], key="vh_oc")
fs = c4.multiselect("Follow-up", ["Pending", "Completed", "Not Required"], key="vh_fs")
if q:
    df = df[df.doctor_name.str.contains(q, case=False, regex=False)]
if isinstance(rng, tuple) and len(rng) == 2:
    df = df[(df.visit_date >= rng[0].isoformat()) & (df.visit_date <= rng[1].isoformat())]
if oc:
    df = df[df.outcome.isin(oc)]
if fs:
    df = df[df.follow_up_status.isin(fs)]
st.caption(f"{len(df)} visit(s) · {shell.scope_label(ctx)}")
if df.empty:
    ui.empty_state("No visits match", "Adjust the filters.")
else:
    st.dataframe(df[["visit_id", "visit_date", "rep_id", "doctor_name", "specialty", "products", "samples_issued",
                     "samples_returned", "outcome", "follow_up_status", "follow_up_date", "source"]].rename(columns={
        "visit_id": "Visit", "visit_date": "Date", "rep_id": "Rep", "doctor_name": "Doctor", "specialty": "Specialty",
        "products": "Products", "samples_issued": "Issued", "samples_returned": "Returned", "outcome": "Outcome",
        "follow_up_status": "Follow-up", "follow_up_date": "Follow-up date", "source": "Source"}),
        hide_index=True, width="stretch", height=560)
