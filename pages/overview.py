"""ANALYZE · Feature 4 - Manager Overview."""
import plotly.express as px
import streamlit as st

from mednexa.core import context
from mednexa.services import analytics
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Overview", "What is happening across the field team?",
               stage="Analyze", feature="Feature 4 · Manager Dashboard & Analytics")
if not context.can(st.session_state, "view_team_analytics"):
    ui.error_state("The Overview is available to managers only.", "Not available for this role")
    st.stop()

d0, d1 = analytics.default_period(ctx.business_date)
c1, c2, c3 = st.columns([2, 2, 2])
period = c1.date_input("Period", (d0, d1), format="DD/MM/YYYY", key="ov_period")
if not isinstance(period, tuple) or len(period) != 2:
    st.info("Select a start and end date.")
    st.stop()
reps = [""] + shell.rep_options()
rep = c2.selectbox("Representative", reps, format_func=lambda r: "Whole team" if not r else shell.rep_label(r), key="ov_rep")
seg = c3.multiselect("Segment", ["A", "B", "C"], key="ov_seg")
f = analytics.Filters(period[0], period[1], rep or None, tuple(seg))

k = analytics.kpis(f, ctx.business_date)
ui.kpi_row([
    ui.Kpi("Doctors", fmt.fmt_int(k["doctors"]), foot=f"A {k['A']} · B {k['B']} · C {k['C']}", tone="primary"),
    ui.Kpi("Visits completed", fmt.fmt_int(k["visits"]), foot=f"{k['doctors_visited']} doctors · coverage {fmt.fmt_pct(k['coverage'])}"),
    ui.Kpi("Planned visits", fmt.fmt_int(k["planned"]), foot=(f"{ctx.business_date:%b} plan · completion "
           f"{fmt.fmt_pct(k['plan_completion'])}") if k["planned"] else f"no {ctx.business_date:%b} plans yet"),
    ui.Kpi("Follow-ups pending", fmt.fmt_int(k["pending_fu"]), foot=f"{k['overdue_fu']} overdue",
           tone="critical" if k["overdue_fu"] else "neutral"),
    ui.Kpi("Samples issued", fmt.fmt_int(k["samples_issued"])),
    ui.Kpi("Inventory alerts", fmt.fmt_int(k["stock_alerts"]), foot=f"{k['stock_critical']} critical",
           tone="critical" if k["stock_critical"] else "neutral"),
])

wc = analytics.week_comparison(f, ctx.business_date)
ui.section_header("Week on week", f"{fmt.fmt_date(wc['this'][0])} – {fmt.fmt_date(wc['this'][1])} vs previous week")
labels = {"visits": "Visits", "doctors": "Doctors visited", "samples": "Samples issued", "fu_completed": "Follow-ups closed"}
tiles = []
for key, label in labels.items():
    diff, pct = wc["delta"][key]
    delta = fmt.fmt_signed(diff) + ("" if pct is None else f" ({pct * 100:+.0f}%)")
    tiles.append(ui.Kpi(label, fmt.fmt_int(wc["this_vals"][key]), delta=delta,
                        delta_direction="up" if diff > 0 else "down" if diff < 0 else "flat",
                        foot=f"prev {wc['prev_vals'][key]}" if pct is not None else "no prior data"))
ui.kpi_row(tiles)

left, right = st.columns([3, 2])
with left:
    ui.section_header("Exceptions", "Shared rules · also drive the Action Center")
    ex = analytics.exceptions(ctx.business_date, f.rep_id)
    if not ex:
        ui.empty_state("No exceptions", "Nothing needs management attention.")
    for e in ex:
        st.markdown(f"{ui.status_pill_html(e['severity'], e['severity'])} <b>{e['title']}</b><br>"
                    f"<span class='mx-muted'>{e['detail']}</span>", unsafe_allow_html=True)
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
with right:
    ui.section_header("Visits per week")
    tr = analytics.visits_trend(f, ctx.business_date)
    if tr.empty:
        ui.empty_state("No visits in period", "Change the period filter.")
    else:
        fig = px.bar(tr, x="week", y="visits", color="rep_id", template="mednexa", height=300)
        fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title_text=None, bargap=.25)
        st.plotly_chart(fig, width="stretch")

ui.section_header("Representative comparison", "Neutral view · no ranking")
rc = analytics.rep_comparison(f, ctx.business_date)
st.dataframe(rc.drop(columns=["rep_id"]), hide_index=True, width="stretch", column_config={
    c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="percent")
    for c in ("Coverage", "Frequency compliance", "A-doctor compliance", "Follow-up closure")})
st.caption("Frequency compliance = visits against Feature 1's recommended frequency (A 4 · B 2 · C 1 per month), "
           "each doctor capped at its target. It is a target, not a plan. Plan completion uses Feature 2 plans.")
