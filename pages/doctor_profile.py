"""KNOW · Feature 1 - Doctor Profile with activity snapshot from Features 2 and 3."""
import streamlit as st

from mednexa import config
from mednexa.core.errors import ServiceError, ValidationError
from mednexa.services import doctors, segmentation
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
all_docs = doctors.list_doctors(ctx.effective_rep_id, ctx.business_date)
if all_docs.empty:
    ui.empty_state("No doctors in scope", "Change the representative in the sidebar.")
    st.stop()
ids = list(all_docs.sort_values("name").doctor_id)
current = st.session_state.get(shell.K_SELECTED_DOCTOR)
choice = st.selectbox("Doctor", ids, index=ids.index(current) if current in ids else 0,
                      format_func=lambda i: f"{all_docs.set_index('doctor_id').loc[i, 'name']} · {i}")
st.session_state[shell.K_SELECTED_DOCTOR] = choice
d = ui.service_call(doctors.get, choice)
if d is None:
    st.stop()
shell.show_flash()
ui.page_header(d["name"], f"{d['specialty']} · {d['area']} · {d['territory']} · {d['rep_id']} {d['rep_name']}",
               stage="Know", feature="Doctor Profile")
st.markdown(ui.segment_badge_html(d["segment"]) + " " + ui.status_pill_html(d["potential"], "accent"
            if d["segment"] == "A" else "info"), unsafe_allow_html=True)

snap = doctors.profile_snapshot(choice, ctx.business_date)
ui.kpi_row([
    ui.Kpi("Monthly prescriptions", fmt.fmt_int(d["monthly_prescriptions"]), tone="accent"),
    ui.Kpi("Recommended visits", f"{d['recommended_visits']} / month"),
    ui.Kpi("Visits logged", fmt.fmt_int(snap["visit_count"]),
           foot=f"last {fmt.fmt_date(snap['last_visit'])}" if snap["last_visit"] else "never visited",
           tone="critical" if not snap["visit_count"] else "neutral"),
    ui.Kpi("Pending follow-ups", fmt.fmt_int(len(snap["pending_followups"])),
           tone="warning" if len(snap["pending_followups"]) else "neutral"),
    ui.Kpi("Upcoming planned", fmt.fmt_int(len(snap["planned"])), foot=f"{snap['missed']} missed"),
])

c1, c2 = st.columns([3, 2])
with c1:
    ui.section_header("Why this doctor matters")
    for line in doctors.why_it_matters(d, doctors.list_doctors(None)):
        st.markdown(f"- {line}")
    if not snap["visit_count"]:
        st.markdown("- **Never visited.** There is no field activity yet, so this doctor is a coverage gap.")
    ui.section_header("Recent visits", "Feature 3")
    if snap["visits"].empty:
        ui.empty_state("No visits yet", "Visits logged for this doctor will appear here.")
    else:
        v = snap["visits"].head(8)[["visit_date", "rep_id", "products", "samples_issued", "outcome", "follow_up_status"]]
        st.dataframe(v.rename(columns={"visit_date": "Date", "rep_id": "Rep", "products": "Products",
                                       "samples_issued": "Samples", "outcome": "Outcome",
                                       "follow_up_status": "Follow-up"}), hide_index=True, width="stretch")
with c2:
    ui.section_header("Open follow-ups", "Feature 3")
    fu = snap["pending_followups"]
    if fu.empty:
        st.caption("No pending follow-ups.")
    for r in fu.itertuples():
        tone = {"OVERDUE": "critical", "DUE_TODAY": "warning", "UPCOMING": "info"}.get(r.timing, "neutral")
        st.markdown(ui.status_pill_html(r.timing.replace("_", " "), tone) +
                    f" &nbsp;{r.follow_up_id} · due {fmt.fmt_date(r.due_date)}"
                    + (f" · {r.days_overdue} days overdue" if r.days_overdue else ""), unsafe_allow_html=True)
    ui.section_header("Planned visits", "Feature 2")
    if snap["planned"].empty:
        st.caption("No open planned visits.")
    for r in snap["planned"].itertuples():
        st.markdown(f"**{fmt.fmt_date(r.planned_date, with_weekday=True)}** · {r.label}"
                    + (" · MISSED" if r.missed else ""))
        st.markdown(ui.chips_html(r.reasons_list), unsafe_allow_html=True)
    if ctx.effective_rep_id and st.button("Log a visit for this doctor", type="primary"):
        shell.open_log_visit(choice)

if ctx.is_manager:
    with st.expander("Edit doctor (manager)"):
        opts = doctors.options()
        with st.form("edit_doctor"):
            e1, e2 = st.columns(2)
            name = e1.text_input("Name", d["name"])
            spec = e2.selectbox("Specialty", opts["specialty"], index=opts["specialty"].index(d["specialty"]))
            terr = e1.selectbox("Territory", opts["territory"], index=opts["territory"].index(d["territory"]))
            areas = sorted(opts["areas_by_territory"].area.unique())
            area = e2.selectbox("Area", areas, index=areas.index(d["area"]))
            rx = e1.number_input("Monthly prescriptions", 0, 5000, int(d["monthly_prescriptions"]))
            new_seg = segmentation.segment_of(rx)
            if st.form_submit_button("Save changes", type="primary"):
                try:
                    doctors.update(choice, {"name": name, "specialty": spec, "area": area, "territory": terr,
                                            "monthly_prescriptions": rx}, is_manager=True)
                    shell.flash(f"Saved. Segment is now {new_seg} "
                                f"({segmentation.visits_per_month(new_seg)} visits/month).")
                    st.rerun()
                except ValidationError as e:
                    st.error("; ".join(f"{k}: {v}" for k, v in e.field_errors.items()) or e.user_message)
                except ServiceError as e:
                    st.error(e.user_message)
