"""KNOW · Feature 1 - Doctor Intelligence Hub."""
import math

import plotly.express as px
import streamlit as st

from mednexa import config
from mednexa.core.errors import ServiceError, ValidationError
from mednexa.services import doctors, segmentation
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Doctor Intelligence Hub", "Who are our doctors, and which doctors have higher business potential?",
               stage="Know", feature="Feature 1 · Doctor Intelligence")
shell.show_flash()

df = ui.service_call(doctors.list_doctors, ctx.effective_rep_id, ctx.business_date)
if df is None:
    st.stop()
ov = doctors.overview(df)
ui.kpi_row([
    ui.Kpi("Total doctors", fmt.fmt_int(ov["total"]), foot=shell.scope_label(ctx), tone="primary"),
    ui.Kpi("A · High potential", fmt.fmt_int(ov["A"]), foot="4 visits / month", tone="accent"),
    ui.Kpi("B · Medium potential", fmt.fmt_int(ov["B"]), foot="2 visits / month"),
    ui.Kpi("C · Lower potential", fmt.fmt_int(ov["C"]), foot="1 visit / month"),
    ui.Kpi("Avg monthly Rx", "—" if ov["avg_rx"] is None else f"{ov['avg_rx']:.0f}", foot="prescription potential"),
])

if len(df):
    c1, c2 = st.columns([2, 3])
    with c1:
        seg = df.segment.value_counts().reindex(["A", "B", "C"]).fillna(0).reset_index()
        seg.columns = ["Segment", "Doctors"]
        fig = px.bar(seg, x="Segment", y="Doctors", color="Segment", text="Doctors", title="A/B/C distribution",
                     color_discrete_map=dict(config.SEGMENT_COLORS), template="mednexa", height=280)
        fig.update_layout(showlegend=False, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    with c2:
        sp = df.groupby(["specialty", "segment"]).size().reset_index(name="Doctors")
        fig = px.bar(sp, y="specialty", x="Doctors", color="segment", orientation="h", title="Specialty mix by segment",
                     color_discrete_map=dict(config.SEGMENT_COLORS), template="mednexa", height=280,
                     category_orders={"segment": ["A", "B", "C"]})
        fig.update_layout(yaxis_title=None, xaxis_title=None, legend_title_text="Segment",
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
    st.caption(" · ".join(segmentation.rule_text()))

ui.section_header("Doctor directory", "Select a row to open the profile")
f1, f2, f3, f4, f5 = st.columns([2.2, 1.6, 1.6, 1, 1.6])
search = f1.text_input("Search by name", placeholder="e.g. Mehta", key="doc_search")
spec = f2.multiselect("Specialty", sorted(df.specialty.unique()), key="doc_spec")
area = f3.multiselect("Area", sorted(df.area.unique()), key="doc_area")
segs = f4.multiselect("Segment", ["A", "B", "C"], key="doc_seg")
sort = f5.selectbox("Sort", ["Prescriptions (high→low)", "Prescriptions (low→high)", "Name (A→Z)", "Name (Z→A)"],
                    key="doc_sort")
view = doctors.filter_doctors(df, search, spec, area, segs, sort)

if view.empty:
    ui.empty_state("No matching doctors", "Try clearing a filter or the search text.")
else:
    pages = max(1, math.ceil(len(view) / config.DIRECTORY_PAGE_SIZE))
    pcol, info = st.columns([1, 5])
    page = pcol.number_input("Page", 1, pages, 1, key="doc_page") if pages > 1 else 1
    info.caption(f"{len(view)} doctor(s) · page {page} of {pages}")
    chunk = view.iloc[(page - 1) * config.DIRECTORY_PAGE_SIZE: page * config.DIRECTORY_PAGE_SIZE]
    table = chunk[["doctor_id", "name", "specialty", "area", "monthly_prescriptions", "segment", "potential",
                   "recommended_visits", "rep_id", "last_visit_date"]].rename(columns={
        "doctor_id": "ID", "name": "Doctor", "specialty": "Specialty", "area": "Area",
        "monthly_prescriptions": "Monthly Rx", "segment": "Segment", "potential": "Prescription potential",
        "recommended_visits": "Visits/month", "rep_id": "Rep", "last_visit_date": "Last visit"})
    table["Last visit"] = table["Last visit"].fillna("Never")
    sel = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun",
                       selection_mode="single-row", key="doc_table",
                       column_config={"Monthly Rx": st.column_config.ProgressColumn(
                           "Monthly Rx", min_value=0, max_value=int(df.monthly_prescriptions.max()), format="%d")})
    rows = sel.selection.rows if sel and sel.selection else []
    if rows:
        shell.open_doctor(chunk.iloc[rows[0]]["doctor_id"])

if ctx.is_manager:
    with st.expander("Add doctor (manager)", expanded=False):
        opts = doctors.options()
        with st.form("add_doctor", clear_on_submit=True):
            a1, a2 = st.columns(2)
            name = a1.text_input("Doctor name", placeholder="Dr. First Last")
            specialty = a2.selectbox("Specialty", opts["specialty"])
            territory = a1.selectbox("Territory", opts["territory"])
            abt = opts["areas_by_territory"]
            area_new = a2.selectbox("Area", sorted(abt.area.unique()))
            rx = a1.number_input("Monthly prescriptions", min_value=0, max_value=5000, value=80, step=1)
            st.caption("Segment and recommended visits are derived automatically.")
            if st.form_submit_button("Save doctor", type="primary"):
                try:
                    new_id = doctors.create({"name": name, "specialty": specialty, "area": area_new,
                                             "territory": territory, "monthly_prescriptions": rx}, is_manager=True)
                    seg = segmentation.segment_of(rx)
                    shell.flash(f"{new_id} saved · segment {seg} · {segmentation.visits_per_month(seg)} visits/month")
                    st.rerun()
                except ValidationError as e:
                    st.error(e.user_message + (" " + "; ".join(f"{k}: {v}" for k, v in e.field_errors.items())
                                               if e.field_errors else ""))
                except ServiceError as e:
                    st.error(e.user_message)
