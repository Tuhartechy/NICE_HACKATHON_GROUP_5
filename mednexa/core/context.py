"""
Session context: role, representative identity, manager "acting as" and business date.

Functions take any MutableMapping (Streamlit's st.session_state in the app, a plain
dict in tests), so this module has no Streamlit dependency. Services never read
session state; pages pass `snapshot(state)` values into service calls explicitly.

Role model (approved):
- Representative: own territory only, read-only doctors, plans/logs own visits.
- Manager: all data, adds/edits doctors, plans for any rep, logs visits only while
  "acting as" a representative, sees Overview/Analytics.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import date

from mednexa import config
from mednexa.core.dates import parse_date
from mednexa.core.errors import PermissionDeniedError, ValidationError

K_ROLE = "mx_role"
K_REP = "mx_rep_id"
K_ACTING = "mx_acting_rep_id"
K_DATE = "mx_business_date"

# capability -> roles allowed (log_visit / plan_own also need a representative in scope)
PERMISSIONS: dict[str, frozenset[str]] = {
    "view_team_analytics": frozenset({config.ROLE_MANAGER}),
    "view_all_territories": frozenset({config.ROLE_MANAGER}),
    "manage_doctors": frozenset({config.ROLE_MANAGER}),
    "plan_any_rep": frozenset({config.ROLE_MANAGER}),
    "plan_own": frozenset({config.ROLE_REP}),
    "log_visit": frozenset({config.ROLE_REP, config.ROLE_MANAGER}),
    "complete_actions": frozenset({config.ROLE_REP, config.ROLE_MANAGER}),
    "change_business_date": frozenset({config.ROLE_REP, config.ROLE_MANAGER}),
}
NEEDS_REP_IN_SCOPE = frozenset({"log_visit", "plan_own"})


@dataclass(frozen=True)
class Context:
    role: str
    rep_id: str | None
    acting_rep_id: str | None
    business_date: date

    @property
    def is_manager(self) -> bool:
        return self.role == config.ROLE_MANAGER

    @property
    def effective_rep_id(self) -> str | None:
        """The representative whose data is in scope (None = whole team)."""
        return self.rep_id if self.role == config.ROLE_REP else self.acting_rep_id

    @property
    def actor(self) -> str:
        """Audit label recorded on writes."""
        if self.role == config.ROLE_REP:
            return f"REP:{self.rep_id}" if self.rep_id else "REP:?"
        return f"MANAGER(as {self.acting_rep_id})" if self.acting_rep_id else "MANAGER"


def init(state: MutableMapping) -> None:
    state.setdefault(K_ROLE, config.DEFAULT_ROLE)
    state.setdefault(K_REP, None)
    state.setdefault(K_ACTING, None)
    state.setdefault(K_DATE, config.DEFAULT_AS_OF)


# ------------------------------------------------------------------ role
def role(state: MutableMapping) -> str:
    return state.get(K_ROLE, config.DEFAULT_ROLE)


def set_role(state: MutableMapping, new_role: str) -> None:
    if new_role not in config.ROLES:
        raise ValidationError(f"Unknown role '{new_role}'.", field_errors={"role": "Invalid role."})
    if new_role != state.get(K_ROLE):
        state[K_ROLE] = new_role
        state[K_ACTING] = None      # switching role clears "acting as"


def is_manager(state: MutableMapping) -> bool:
    return role(state) == config.ROLE_MANAGER


# ------------------------------------------------------------------ representative scope
def _check_rep(rep_id: str | None, valid_rep_ids) -> None:
    if rep_id is not None and valid_rep_ids is not None and rep_id not in set(valid_rep_ids):
        raise ValidationError(f"Unknown representative '{rep_id}'.",
                              field_errors={"rep_id": "Not a known representative."})


def set_rep(state: MutableMapping, rep_id: str | None, valid_rep_ids=None) -> None:
    """Identity of the signed-in representative (Representative role)."""
    _check_rep(rep_id, valid_rep_ids)
    state[K_REP] = rep_id


def set_acting_rep(state: MutableMapping, rep_id: str | None, valid_rep_ids=None) -> None:
    """Manager works on behalf of a representative (None = whole team)."""
    if rep_id is not None and not is_manager(state):
        raise PermissionDeniedError("Only managers can act on behalf of a representative.")
    _check_rep(rep_id, valid_rep_ids)
    state[K_ACTING] = rep_id


def effective_rep_id(state: MutableMapping) -> str | None:
    return snapshot(state).effective_rep_id


# ------------------------------------------------------------------ business date
def business_date(state: MutableMapping) -> date:
    return state.get(K_DATE, config.DEFAULT_AS_OF)


def set_business_date(state: MutableMapping, value) -> date:
    d = parse_date(value, field="business_date")
    if not (config.BUSINESS_DATE_MIN <= d <= config.BUSINESS_DATE_MAX):
        raise ValidationError(
            f"Business date must be between {config.BUSINESS_DATE_MIN:%d %b %Y} "
            f"and {config.BUSINESS_DATE_MAX:%d %b %Y}.",
            field_errors={"business_date": "Out of range."})
    state[K_DATE] = d
    return d


def reset_business_date(state: MutableMapping) -> date:
    state[K_DATE] = config.DEFAULT_AS_OF
    return config.DEFAULT_AS_OF


def is_business_date_overridden(state: MutableMapping) -> bool:
    return business_date(state) != config.DEFAULT_AS_OF


# ------------------------------------------------------------------ permissions
def can(state: MutableMapping, capability: str) -> bool:
    if capability not in PERMISSIONS:
        raise KeyError(f"Unknown capability '{capability}'")
    ctx = snapshot(state)
    if ctx.role not in PERMISSIONS[capability]:
        return False
    if capability in NEEDS_REP_IN_SCOPE:
        return ctx.effective_rep_id is not None
    return True


def require(state: MutableMapping, capability: str) -> None:
    if not can(state, capability):
        raise PermissionDeniedError()


def snapshot(state: MutableMapping) -> Context:
    return Context(
        role=role(state),
        rep_id=state.get(K_REP),
        acting_rep_id=state.get(K_ACTING) if is_manager(state) else None,
        business_date=business_date(state),
    )
