"""Streamlit AppTest smoke tests: every page renders for each role without exceptions."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mednexa import config
from mednexa.core import context
from mednexa.ui.navigation import PAGES, reachable_keys

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


def _app(role=config.ROLE_MANAGER, acting=None, business_date=None):
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state[context.K_ROLE] = role
    at.session_state[context.K_ACTING] = acting
    at.session_state[context.K_REP] = None
    at.session_state[context.K_DATE] = business_date or config.DEFAULT_AS_OF
    return at


def _text(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_manager_home_without_database_is_friendly():
    at = _app().run()
    assert not at.exception
    assert "Data not available" in _text(at) and "Tue 01 Sep 2026" in _text(at)


def test_rep_home_without_database_is_friendly():
    at = _app(config.ROLE_REP).run()
    assert not at.exception and "Data not available" in _text(at)


@pytest.mark.parametrize("role,acting", [(config.ROLE_MANAGER, None), (config.ROLE_MANAGER, "R004"),
                                         (config.ROLE_REP, None)])
def test_every_reachable_page_renders(role, acting):
    for key in sorted(reachable_keys(role, acting)):
        at = _app(role, acting).run()
        at.switch_page(PAGES[key].file).run()
        assert not at.exception, (role, key, [e.value for e in at.exception])
        assert "mx-title" in _text(at) or "Data not available" in _text(at), (role, key)


def test_business_date_override_is_visible():
    at = _app(business_date=config.DEFAULT_AS_OF.replace(day=3)).run()
    assert "Thu 03 Sep 2026" in _text(at) and "(override)" in _text(at)
    assert any("Reset to" in b.label for b in at.sidebar.button)


def test_database_status_shown_when_not_seeded():
    at = _app().run()
    side = " ".join(m.value for m in at.sidebar.markdown)
    assert "Database not initialised" in side


def test_role_switch_via_sidebar():
    at = _app().run()
    at.sidebar.radio(key="w_role").set_value(config.ROLE_REP).run()
    assert not at.exception and at.session_state[context.K_ROLE] == config.ROLE_REP


def test_every_manager_page_renders_with_seeded_data(tmp_path, monkeypatch):
    from mednexa.db import seed
    path = tmp_path / "mx.db"
    seed.build(path, validate=False)
    monkeypatch.setattr(config, "DB_PATH", path)
    for key in sorted(reachable_keys(config.ROLE_MANAGER)):
        at = _app().run()
        at.switch_page(PAGES[key].file).run()
        assert not at.exception, (key, [e.value for e in at.exception])
        assert "Data not available" not in _text(at), key
