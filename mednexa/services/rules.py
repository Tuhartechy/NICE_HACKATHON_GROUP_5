"""
Shared business-rule layer. Features 2, 3, 4 and 5 import these definitions;
none of them re-implements the same rule.
"""
from __future__ import annotations

from datetime import date

from mednexa import config
from mednexa.core.dates import add_working_days, parse_date
from mednexa.services import segmentation

# ---------------- follow-up timing (owner F3)
OVERDUE, DUE_TODAY, UPCOMING, LATER = "OVERDUE", "DUE_TODAY", "UPCOMING", "LATER"


def follow_up_timing(due, as_of: date) -> str:
    d = parse_date(due)
    if d < as_of:
        return OVERDUE
    if d == as_of:
        return DUE_TODAY
    if (d - as_of).days <= config.UPCOMING_WINDOW_DAYS:
        return UPCOMING
    return LATER


def days_overdue(due, as_of: date) -> int:
    return max((as_of - parse_date(due)).days, 0)


# ---------------- stock status (owner F3)
def stock_status(current: int, minimum: int) -> str:
    if current <= config.STOCK_CRITICAL_RATIO * minimum:
        return "CRITICAL"
    if current < minimum:
        return "LOW"
    if current <= config.STOCK_WATCH_RATIO * minimum:
        return "WATCH"
    return "HEALTHY"


def stock_label(current: int, minimum: int) -> str:
    s = stock_status(current, minimum)
    return "Out of stock" if current == 0 else s.title()


# ---------------- plan items (owner F2)
def is_missed(status: str, planned_date, as_of: date) -> bool:
    return status == "PLANNED" and parse_date(planned_date) < as_of


def is_prep_window(status: str, planned_date, as_of: date) -> bool:
    d = parse_date(planned_date)
    return status == "PLANNED" and as_of <= d <= add_working_days(as_of, config.PREP_WINDOW_WORKING_DAYS)


# ---------------- doctor recency (owner F4 definitions, F1 frequency)
def days_since(last_visit, as_of: date):
    if last_visit is None or last_visit != last_visit or last_visit == "":
        return None
    return (as_of - parse_date(last_visit)).days


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def not_recently_visited(days, segment: str) -> bool:
    if _missing(days):
        return True
    return days > config.NOT_RECENT_MULTIPLIER * (30 / segmentation.visits_per_month(segment))


def is_active(days) -> bool:
    return not _missing(days) and days <= config.ACTIVE_DOCTOR_DAYS


# ---------------- action priority (owner F5)
def action_priority(action_type: str, *, days_late: int = 0, segment: str | None = None) -> str:
    if action_type == "OVERDUE_FOLLOW_UP":
        return "CRITICAL" if days_late >= config.OVERDUE_CRITICAL_DAYS else "HIGH"
    if action_type == "DUE_TODAY_FOLLOW_UP":
        return "HIGH"
    if action_type == "MISSED_VISIT":
        return "CRITICAL" if segment == "A" else "HIGH"
    if action_type == "UPCOMING_FOLLOW_UP":
        return "MEDIUM"
    if action_type == "UPCOMING_VISIT_PREPARATION":
        return "MEDIUM" if segment == "A" else "LOW"
    return "LOW"


PRIORITY_RANK = {p: i for i, p in enumerate(config.ACTION_PRIORITIES)}
