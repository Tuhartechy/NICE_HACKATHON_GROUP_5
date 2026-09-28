"""
Application shell: sidebar workspace controls, context bar and page context helpers.

The shell owns *presentation* of the session context. The rules for roles,
permissions and the business date live in mednexa.core.context.
"""

from __future__ import annotations

import streamlit as st

from mednexa import config
from mednexa.core import context
from mednexa.core.errors import ServiceError
from mednexa.services import reference
from mednexa.ui import formatting as fmt
from mednexa.ui.components import _e

_REPS_KEY = "_mx_reps"          # refreshed every run from the database (never persisted elsewhere)
_DB_KEY = "_mx_db_status"


# ----------------------------------------------------------------- data for the shell
def load_shell_data() -> None:
    status = reference.database_status()
    st.session_state[_DB_KEY] = status
    reps: list[dict] = []
    if status.available:
        try:
            reps = reference.list_reps()
        except ServiceError:
            reps = []
    st.session_state[_REPS_KEY] = reps


def reps() -> list[dict]:
    return st.session_state.get(_REPS_KEY, [])


def rep_by_id(rep_id: str | None) -> dict | None:
    return next((r for r in reps() if r["rep_id"] == rep_id), None)


def rep_label(rep_id: str | None) -> str:
    r = rep_by_id(rep_id)
    return f"{r['rep_id']} · {r['name']} · {r['territory']}" if r else (rep_id or "—")


def current_context() -> context.Context:
    return context.snapshot(st.session_state)


def scope_label(ctx: context.Context | None = None) -> str:
    ctx = ctx or current_context()
    rid = ctx.effective_rep_id
    if rid:
        r = rep_by_id(rid)
        return f"{r['name']} · {r['territory']}" if r else rid
    return "Whole team" if ctx.is_manager else "No representative selected"


# ----------------------------------------------------------------- sidebar controls
def _on_role_change() -> None:
    context.set_role(st.session_state, st.session_state["w_role"])


def _on_rep_change() -> None:
    context.set_rep(st.session_state, st.session_state["w_rep"], [r["rep_id"] for r in reps()])


def _on_acting_change() -> None:
    value = st.session_state["w_acting"]
    context.set_acting_rep(st.session_state, value or None, [r["rep_id"] for r in reps()])


def _on_date_change() -> None:
    try:
        context.set_business_date(st.session_state, st.session_state["w_date"])
    except ServiceError as exc:
        st.session_state["_mx_date_error"] = exc.user_message


def _on_date_reset() -> None:
    d = context.reset_business_date(st.session_state)
    st.session_state["w_date"] = d


def render_sidebar_controls() -> None:
    state = st.session_state
    rep_ids = [r["rep_id"] for r in reps()]

    with st.sidebar:
        st.markdown('<div class="mx-side-label">Workspace</div>', unsafe_allow_html=True)
        st.radio("Role", config.ROLES, index=config.ROLES.index(context.role(state)), key="w_role",
                 horizontal=True, on_change=_on_role_change)

        if context.role(state) == config.ROLE_REP:
            if rep_ids:
                if state.get(context.K_REP) not in rep_ids:
                    context.set_rep(state, rep_ids[0], rep_ids)
                st.selectbox("Signed in as", rep_ids, index=rep_ids.index(state[context.K_REP]),
                             key="w_rep", format_func=rep_label, on_change=_on_rep_change)
            else:
                st.caption("Representative profiles become available after the database is seeded.")
        else:
            options = [""] + rep_ids
            current = state.get(context.K_ACTING) or ""
            st.selectbox("Acting as", options, index=options.index(current) if current in options else 0,
                         key="w_acting", on_change=_on_acting_change, disabled=not rep_ids,
                         format_func=lambda v: "Whole team" if v == "" else rep_label(v),
                         help="Managers log visits only while acting on behalf of a representative.")

        st.date_input("Business date", value=context.business_date(state), key="w_date",
                      min_value=config.BUSINESS_DATE_MIN, max_value=config.BUSINESS_DATE_MAX,
                      format="DD/MM/YYYY", on_change=_on_date_change,
                      help="All due, overdue, upcoming and planning logic uses this date, "
                           "never the computer clock.")
        if context.is_business_date_overridden(state):
            st.button(f"Reset to {config.DEFAULT_AS_OF:%d %b %Y}", on_click=_on_date_reset,
                      width="stretch")
        if state.get("_mx_date_error"):
            st.warning(state.pop("_mx_date_error"))

        status = state.get(_DB_KEY)
        if status is not None:
            dot = "ok" if status.available else "off"
            st.markdown(f'<div class="mx-dbstatus"><span class="mx-dot {dot}"></span>'
                        f'Data: {_e(status.message)}</div>', unsafe_allow_html=True)
            if not status.available:
                st.caption("Run `python -m mednexa.db.seed` and reload.")


# ----------------------------------------------------------------- context bar
def context_bar_html(ctx: context.Context, scope: str) -> str:
    override = ctx.business_date != config.DEFAULT_AS_OF
    date_cls = "mx-ctx mx-ctx-override" if override else "mx-ctx"
    date_note = " (override)" if override else ""
    return (
        '<div class="mx-contextbar">'
        f'<span class="{date_cls}">Business date <b>{_e(fmt.business_date_label(ctx.business_date))}</b>'
        f'{_e(date_note)}</span>'
        f'<span class="mx-ctx">Role <b>{_e(ctx.role)}</b></span>'
        f'<span class="mx-ctx">Scope <b>{_e(scope)}</b></span>'
        "</div>"
    )


def render_context_bar() -> None:
    ctx = current_context()
    st.markdown(context_bar_html(ctx, scope_label(ctx)), unsafe_allow_html=True)


# ----------------------------------------------------------------- page helpers
K_SELECTED_DOCTOR = "mx_selected_doctor"
K_LOG_PREFILL = "mx_log_prefill"
K_FLASH = "mx_flash"


def require_data() -> None:
    """Stop the page with a friendly state when the database is not ready."""
    status = st.session_state.get(_DB_KEY)
    if status is None or not status.available:
        from mednexa.ui import components as ui
        ui.error_state("The MedNexa database has not been created yet. Run `python -m mednexa.db.seed` "
                       "in the project folder, then reload this page.", "Data not available")
        st.stop()


def require_rep(message: str = "Select a representative in the sidebar to continue.") -> str:
    ctx = current_context()
    if ctx.effective_rep_id is None:
        from mednexa.ui import components as ui
        ui.empty_state("Choose a representative", message)
        st.stop()
    return ctx.effective_rep_id


def open_doctor(doctor_id: str) -> None:
    st.session_state[K_SELECTED_DOCTOR] = doctor_id
    st.switch_page("pages/doctor_profile.py")


def open_log_visit(doctor_id: str, plan_item_id: str | None = None) -> None:
    st.session_state[K_LOG_PREFILL] = {"doctor_id": doctor_id, "plan_item_id": plan_item_id}
    st.switch_page("pages/log_visit.py")


def flash(message: str, kind: str = "success") -> None:
    st.session_state[K_FLASH] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop(K_FLASH, None)
    if item:
        kind, msg = item
        {"success": st.success, "warning": st.warning, "error": st.error}.get(kind, st.info)(msg)


def rep_options() -> list[str]:
    return [r["rep_id"] for r in reps()]
