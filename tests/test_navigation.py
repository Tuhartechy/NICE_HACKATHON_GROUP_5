from pathlib import Path

import pytest

from mednexa import config
from mednexa.ui.navigation import PAGES, nav_spec, reachable_keys

ROOT = Path(__file__).resolve().parent.parent


def test_every_page_file_exists():
    for spec in PAGES.values():
        assert (ROOT / spec.file).is_file(), spec.file


def test_rep_navigation():
    spec = nav_spec(config.ROLE_REP)
    assert list(spec) == ["Act", "Know", "Plan", "Execute"]
    assert reachable_keys(config.ROLE_REP) == {"action_center", "doctors", "doctor_profile", "visit_planner",
                                               "log_visit", "visit_history", "inventory"}
    titles = {e.spec.key: e.title for es in spec.values() for e in es}
    assert titles["visit_planner"] == "My Visit Plan" and titles["inventory"] == "Samples & Stock"


def test_manager_navigation_and_acting_as():
    assert list(nav_spec(config.ROLE_MANAGER)) == ["Analyze", "Act", "Know", "Plan", "Execute"]
    assert "log_visit" not in reachable_keys(config.ROLE_MANAGER)
    assert "log_visit" in reachable_keys(config.ROLE_MANAGER, acting_rep_id="R004")
    assert {"overview", "analytics"} <= reachable_keys(config.ROLE_MANAGER)


def test_reps_cannot_reach_manager_analytics():
    assert not ({"overview", "analytics"} & reachable_keys(config.ROLE_REP))


@pytest.mark.parametrize("role,home", [(config.ROLE_REP, "action_center"), (config.ROLE_MANAGER, "overview")])
def test_exactly_one_home_page(role, home):
    defaults = [e.spec.key for es in nav_spec(role).values() for e in es if e.default]
    assert defaults == [home]


def test_profile_is_hidden_and_urls_unique():
    assert PAGES["doctor_profile"].hidden
    urls = [p.url_path for p in PAGES.values()]
    assert len(urls) == len(set(urls))


def test_unknown_role():
    with pytest.raises(ValueError):
        nav_spec("Guest")
