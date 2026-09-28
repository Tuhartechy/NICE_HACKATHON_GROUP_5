"""EXECUTE · Feature 3 - Samples & Stock / Inventory."""
import plotly.graph_objects as go
import streamlit as st

from mednexa import config
from mednexa.services import inventory
from mednexa.ui import components as ui, formatting as fmt, shell

shell.require_data()
ctx = shell.current_context()
ui.page_header("Inventory" if ctx.is_manager else "Samples & Stock",
               "Sample stock levels and movement for every product.",
               stage="Execute", feature="Feature 3 · Visit & Sample Logging")
st_df = inventory.stock()
cnt = st_df.status.value_counts()
ui.kpi_row([ui.Kpi("Critical", fmt.fmt_int(cnt.get("CRITICAL", 0)), tone="critical", foot="≤25% of minimum"),
            ui.Kpi("Low", fmt.fmt_int(cnt.get("LOW", 0)), tone="warning", foot="below minimum"),
            ui.Kpi("Watch", fmt.fmt_int(cnt.get("WATCH", 0)), foot="≤1.5× minimum"),
            ui.Kpi("Healthy", fmt.fmt_int(cnt.get("HEALTHY", 0)), tone="primary"),
            ui.Kpi("Samples issued", fmt.fmt_int(st_df.issued.sum()), foot=f"{st_df.returned.sum()} returned")])
T = config.THEME
colour = {"CRITICAL": T["critical"], "LOW": T["warning"], "WATCH": T["info"], "HEALTHY": T["primary_bright"]}
fig = go.Figure()
fig.add_bar(x=st_df.product_name, y=st_df.current_stock, marker_color=[colour[s] for s in st_df.status],
            name="Current stock", text=st_df.status_label, textposition="outside")
fig.add_scatter(x=st_df.product_name, y=st_df.minimum_stock, mode="markers", name="Minimum",
                marker=dict(symbol="line-ew", size=26, line=dict(width=3, color=T["text"])))
fig.update_layout(template="mednexa", height=360, title="Current stock vs minimum", legend_orientation="h")
st.plotly_chart(fig, width="stretch")
if not st_df.ledger_ok.all():
    st.warning("Stock ledger mismatch detected for: " + ", ".join(st_df[~st_df.ledger_ok].product_id))
st.dataframe(st_df[["product_id", "product_name", "opening_stock", "issued", "returned", "current_stock",
                    "minimum_stock", "status_label"]].rename(columns={"status_label": "Status"}),
             hide_index=True, width="stretch")
