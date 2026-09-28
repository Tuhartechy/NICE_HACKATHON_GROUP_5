from datetime import date

import pytest

from mednexa import config
from mednexa.core import context
from mednexa.core.errors import PermissionDeniedError, ValidationError

REPS = ["R001", "R002", "R003", "R004", "R005"]


@pytest.fixture()
def state():
    s = {}
    context.init(s)
    return s


def test_defaults(state):
    ctx = context.snapshot(state)
    assert ctx.role == config.ROLE_MANAGER and ctx.business_date == date(2026, 9, 1)
    assert ctx.effective_rep_id is None and ctx.actor == "MANAGER"


def test_business_date_override_and_reset(state):
    context.set_business_date(state, "2026-09-03")
    assert context.business_date(state) == date(2026, 9, 3) and context.is_business_date_overridden(state)
    context.reset_business_date(state)
    assert context.business_date(state) == config.DEFAULT_AS_OF


def test_business_date_out_of_range_rejected(state):
    with pytest.raises(ValidationError):
        context.set_business_date(state, "2025-01-01")


def test_rep_role_scope(state):
    context.set_role(state, config.ROLE_REP)
    context.set_rep(state, "R004", REPS)
    ctx = context.snapshot(state)
    assert ctx.effective_rep_id == "R004" and ctx.actor == "REP:R004"
    with pytest.raises(ValidationError):
        context.set_rep(state, "R999", REPS)


def test_manager_acting_as_and_role_switch_clears_it(state):
    context.set_acting_rep(state, "R002", REPS)
    assert context.snapshot(state).effective_rep_id == "R002"
    context.set_role(state, config.ROLE_REP)
    context.set_role(state, config.ROLE_MANAGER)
    assert context.snapshot(state).acting_rep_id is None


def test_only_managers_can_act_as(state):
    context.set_role(state, config.ROLE_REP)
    with pytest.raises(PermissionDeniedError):
        context.set_acting_rep(state, "R001", REPS)


def test_unknown_role_rejected(state):
    with pytest.raises(ValidationError):
        context.set_role(state, "Admin")


def test_permission_matrix(state):
    # manager, whole team
    assert context.can(state, "view_team_analytics") and context.can(state, "manage_doctors")
    assert context.can(state, "plan_any_rep") and not context.can(state, "log_visit")
    context.set_acting_rep(state, "R003", REPS)
    assert context.can(state, "log_visit")
    # representative
    context.set_role(state, config.ROLE_REP)
    assert not context.can(state, "view_team_analytics") and not context.can(state, "manage_doctors")
    assert not context.can(state, "log_visit")            # no rep identity yet
    context.set_rep(state, "R003", REPS)
    assert context.can(state, "log_visit") and context.can(state, "plan_own")
    with pytest.raises(PermissionDeniedError):
        context.require(state, "manage_doctors")
    with pytest.raises(KeyError):
        context.can(state, "launch_rockets")
