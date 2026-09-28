"""
Deterministic calendar helpers.

Working days are Monday-Saturday excluding configured holidays.
Nothing here reads the machine clock; callers always pass the business date.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from mednexa import config
from mednexa.core.errors import ValidationError


def parse_date(value, *, field: str = "date") -> date:
    """Accept a date, datetime or ISO 'YYYY-MM-DD' string."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValidationError(f"'{value}' is not a valid date.", field_errors={field: "Use YYYY-MM-DD."})


def to_iso(value) -> str:
    return parse_date(value).isoformat()


def is_working_day(d: date, holidays: Iterable[date] | None = None) -> bool:
    hol = config.HOLIDAYS if holidays is None else frozenset(holidays)
    return d.weekday() in config.WORKING_WEEKDAYS and d not in hol


def next_working_day(d: date, *, include_self: bool = True) -> date:
    cur = d if include_self else d + timedelta(days=1)
    while not is_working_day(cur):
        cur += timedelta(days=1)
    return cur


def add_working_days(d: date, n: int) -> date:
    """Move n working days forward (n >= 0). add_working_days(d, 0) == next_working_day(d)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    cur = next_working_day(d)
    for _ in range(n):
        cur = next_working_day(cur, include_self=False)
    return cur


def working_days_from(start: date, count: int) -> list[date]:
    """The first `count` working days on or after `start`."""
    if count < 0:
        raise ValueError("count must be >= 0")
    out: list[date] = []
    cur = start
    while len(out) < count:
        if is_working_day(cur):
            out.append(cur)
        cur += timedelta(days=1)
    return out


def working_days_between(start: date, end: date) -> int:
    """Working days in the half-open interval (start, end]. 0 if end <= start."""
    if end <= start:
        return 0
    days, cur = 0, start + timedelta(days=1)
    while cur <= end:
        if is_working_day(cur):
            days += 1
        cur += timedelta(days=1)
    return days


def days_between(start: date, end: date) -> int:
    """Calendar days from start to end (negative if end is earlier)."""
    return (end - start).days


def week_start(d: date) -> date:
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def month_bounds(d: date) -> tuple[date, date]:
    first = d.replace(day=1)
    nxt = (first.replace(year=first.year + 1, month=1) if first.month == 12
           else first.replace(month=first.month + 1))
    return first, nxt - timedelta(days=1)


def clamp_business_date(d: date) -> date:
    return min(max(d, config.BUSINESS_DATE_MIN), config.BUSINESS_DATE_MAX)
