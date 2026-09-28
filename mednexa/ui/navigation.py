"""
Role-based navigation definition (pure data - no Streamlit calls).

app.py turns this spec into st.Page / st.navigation objects. Keeping it pure lets
tests verify exactly which pages each role can reach.
"""

from __future__ import annotations

from dataclasses import dataclass

from mednexa import config


@dataclass(frozen=True)
class PageSpec:
    key: str
    file: str               # path relative to the project root
    title: str
    icon: str
    url_path: str
    hidden: bool = False


PAGES: dict[str, PageSpec] = {p.key: p for p in (
    PageSpec("action_center", "pages/action_center.py", "Action Center", ":material/bolt:", "action-center"),
    PageSpec("doctors", "pages/doctors.py", "Doctors", ":material/stethoscope:", "doctors"),
    PageSpec("doctor_profile", "pages/doctor_profile.py", "Doctor Profile", ":material/badge:",
             "doctor-profile", hidden=True),
    PageSpec("visit_planner", "pages/visit_planner.py", "Visit Planner", ":material/event_note:", "visit-planner"),
    PageSpec("log_visit", "pages/log_visit.py", "Log Visit", ":material/edit_note:", "log-visit"),
    PageSpec("visit_history", "pages/visit_history.py", "Visit History", ":material/history:", "visit-history"),
    PageSpec("inventory", "pages/inventory.py", "Inventory", ":material/inventory_2:", "inventory"),
    PageSpec("overview", "pages/overview.py", "Overview", ":material/space_dashboard:", "overview"),
    PageSpec("analytics", "pages/analytics.py", "Analytics", ":material/monitoring:", "analytics"),
)}

# Role-specific titles for shared pages
REP_TITLES = {"visit_planner": "My Visit Plan", "inventory": "Samples & Stock"}


@dataclass(frozen=True)
class NavEntry:
    spec: PageSpec
    title: str
    default: bool = False


def nav_spec(role: str, acting_rep_id: str | None = None) -> dict[str, list[NavEntry]]:
    """Ordered sections -> entries for a role. Exactly one entry is the default (home) page."""
    if role == config.ROLE_REP:
        layout = [
            ("Act", [("action_center", True)]),
            ("Know", [("doctors", False), ("doctor_profile", False)]),
            ("Plan", [("visit_planner", False)]),
            ("Execute", [("log_visit", False), ("visit_history", False), ("inventory", False)]),
        ]
        titles = REP_TITLES
    elif role == config.ROLE_MANAGER:
        execute = [("visit_history", False), ("inventory", False)]
        if acting_rep_id:  # managers log visits only while acting as a representative
            execute.insert(0, ("log_visit", False))
        layout = [
            ("Analyze", [("overview", True), ("analytics", False)]),
            ("Act", [("action_center", False)]),
            ("Know", [("doctors", False), ("doctor_profile", False)]),
            ("Plan", [("visit_planner", False)]),
            ("Execute", execute),
        ]
        titles = {}
    else:
        raise ValueError(f"Unknown role '{role}'")

    return {
        section: [NavEntry(PAGES[key], titles.get(key, PAGES[key].title), default) for key, default in entries]
        for section, entries in layout
    }


def reachable_keys(role: str, acting_rep_id: str | None = None) -> set[str]:
    return {e.spec.key for entries in nav_spec(role, acting_rep_id).values() for e in entries}
