"""ANALYZE · Feature 4 - Analytics tabs with drill-down tables."""
import plotly.express as px
import streamlit as st

from mednexa import config
from mednexa.core import context
from mednexa.services import analytics, followups, inventory, plans
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Analytics", "Where is it happening, who needs attention, and what has changed?",
               stage="Analyze", feature="Feature 4 · Manager Dashboard & Analytics")
if not context.can(st.session_state, "view_team_analytics"):
    ui.error_state("Analytics are available to managers only.", "Not available for this role")
    st.stop()

d0, d1 = analytics.default_period(ctx.business_date)
c1, c2, c3 = st.columns(3)
period = c1.date_input("Period", (d0, d1), format="DD/MM/YYYY", key="an_period")
if not isinstance(period, tuple) or len(period) != 2:
    st.stop()
reps = [""] + shell.rep_options()
rep = c2.selectbox("Representative", reps, format_func=lambda r: "Whole team" if not r else shell.rep_label(r), key="an_rep")
seg = c3.multiselect("Segment", ["A", "B", "C"], key="an_seg")
f = analytics.Filters(period[0], period[1], rep or None, tuple(seg))

tabs = st.tabs(["Coverage", "Planned vs Actual", "Products", "Samples", "Follow-ups", "Outcomes", "Inventory"])
with tabs[0]:
    comp = analytics.compliance_by_segment(f, ctx.business_date)
    a, b = st.columns([2, 3])
    with a:
        fig = px.bar(comp, x="segment", y="compliance", color="segment", text=comp.compliance.map(lambda x: f"{x:.0%}"),
                     color_discrete_map=dict(config.SEGMENT_COLORS), template="mednexa", height=300,
                     title="Frequency compliance by segment")
        fig.update_layout(showlegend=False, yaxis_tickformat=".0%", yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    with b:
        gaps = analytics.coverage_gaps(f, ctx.business_date)
        ui.section_header("Coverage gaps", "Not visited within 2× the recommended interval, or never")
        if gaps.empty:
            ui.empty_state("No coverage gaps", "Every doctor in scope was visited recently.")
        else:
            st.dataframe(gaps[["doctor_id", "name", "segment", "specialty", "area", "rep_id", "monthly_prescriptions",
                               "status"]], hide_index=True, width="stretch")
with tabs[1]:
    rc = analytics.rep_comparison(f, ctx.business_date)
    fig = px.bar(rc, x="rep_id", y=["Frequency compliance", "A-doctor compliance"], barmode="group",
                 template="mednexa", height=300, title="Actual visits vs recommended frequency (target)")
    fig.update_layout(yaxis_tickformat=".0%", yaxis_title=None, xaxis_title=None, legend_title_text=None)
    st.plotly_chart(fig, width="stretch")
    ui.section_header("Plan execution", "Feature 2 plans")
    items = plans.list_items(rep_id=f.rep_id, as_of=ctx.business_date)
    if items.empty:
        ui.empty_state("No visit plans yet", "Generate plans in the Visit Planner. Plan-based completion is "
                       "measured from September 2026 onwards.")
    else:
        items["state"] = items.apply(lambda r: "MISSED" if r.missed else r.status, axis=1)
        st.dataframe(items.groupby(["rep_id", "state"]).size().unstack(fill_value=0).reset_index(),
                     hide_index=True, width="stretch")
        st.dataframe(items[["planned_date", "rep_id", "doctor_name", "segment", "state", "label", "visit_id"]],
                     hide_index=True, width="stretch")
with tabs[2]:
    vp = analytics.product_activity(f, ctx.business_date)
    if vp.empty:
        ui.empty_state("No product discussions", "No visits in this period.")
    else:
        cnt = vp.groupby("product_name").size().reset_index(name="discussions").sort_values("discussions")
        fig = px.bar(cnt, y="product_name", x="discussions", orientation="h", template="mednexa", height=340,
                     title="Product discussions")
        fig.update_layout(yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, width="stretch")
        fb = vp.groupby(["product_name", "feedback"]).size().unstack(fill_value=0)
        st.caption("Feedback by product (August history is 'Not recorded')")
        st.dataframe(fb, width="stretch")
with tabs[3]:
    sp = analytics.samples_by_product(f, ctx.business_date)
    if sp.empty:
        ui.empty_state("No sample movement", "No sample transactions in this period.")
    else:
        fig = px.bar(sp, x="product_name", y=["SAMPLE_ISSUED", "SAMPLE_RETURNED"], barmode="group",
                     template="mednexa", height=320, title="Samples issued and returned")
        fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title_text=None)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(sp, hide_index=True, width="stretch")
with tabs[4]:
    fu = followups.list_followups(ctx.business_date, rep_id=f.rep_id)
    fu["state"] = fu.apply(lambda r: r.timing if r.status == "Pending" else "COMPLETED", axis=1)
    by = fu.groupby(["rep_id", "state"]).size().unstack(fill_value=0).reset_index()
    st.dataframe(by, hide_index=True, width="stretch")
    over = fu[fu.state == "OVERDUE"].sort_values("days_overdue", ascending=False)
    ui.section_header("Overdue follow-ups", "drill-down")
    st.dataframe(over[["follow_up_id", "rep_id", "doctor_name", "segment", "due_date", "days_overdue"]],
                 hide_index=True, width="stretch")
with tabs[5]:
    oc = analytics.outcomes(f, ctx.business_date)
    if oc.empty:
        ui.empty_state("No visits", "No visits in this period.")
    else:
        fig = px.pie(oc, names="outcome", values="visits", template="mednexa", height=320, hole=.55,
                     title="Visit outcomes")
        st.plotly_chart(fig, width="stretch")
        st.caption("Visits from the August history carry no outcome and are shown as 'Not recorded'.")
with tabs[6]:
    stck = inventory.stock()
    st.dataframe(stck[["product_id", "product_name", "opening_stock", "issued", "returned", "current_stock",
                       "minimum_stock", "status_label"]], hide_index=True, width="stretch")
