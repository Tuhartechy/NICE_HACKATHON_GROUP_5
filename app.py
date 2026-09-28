"""
MEDNEXA - Pharma Field Intelligence Platform
Single Streamlit entry point: page config, theme, session context, sidebar and
role-based navigation. Feature pages live in pages/ and only call services.

Run:  streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from mednexa import config
from mednexa.core import context
from mednexa.ui import shell
from mednexa.ui.navigation import nav_spec
from mednexa.ui.theme import apply_theme

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title=f"{config.APP_NAME.title()} · {config.APP_SUBTITLE}",
    page_icon=str(ROOT / "assets" / "mednexa_mark.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
st.logo(str(ROOT / "assets" / "mednexa_logo.svg"), size="large",
        icon_image=str(ROOT / "assets" / "mednexa_mark.svg"))

context.init(st.session_state)
shell.load_shell_data()

ctx = context.snapshot(st.session_state)
sections = {
    section: [
        st.Page(str(ROOT / e.spec.file), title=e.title, icon=e.spec.icon, url_path=e.spec.url_path,
                default=e.default, visibility="hidden" if e.spec.hidden else "visible")
        for e in entries
    ]
    for section, entries in nav_spec(ctx.role, ctx.acting_rep_id).items()
}
page = st.navigation(sections, position="sidebar")

shell.render_sidebar_controls()
with st.sidebar:
    st.caption(config.APP_SUBTITLE)

shell.render_context_bar()
page.run()
