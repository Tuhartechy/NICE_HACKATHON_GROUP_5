from datetime import date

import pytest

from mednexa.core import dates
from mednexa.core.errors import ValidationError


def test_parse_date_variants():
    assert dates.parse_date("2026-09-01") == date(2026, 9, 1)
    assert dates.parse_date(date(2026, 9, 1)) == date(2026, 9, 1)
    with pytest.raises(ValidationError):
        dates.parse_date("01/09/2026")
    with pytest.raises(ValidationError):
        dates.parse_date(None)


@pytest.mark.parametrize("d,expected", [
    (date(2026, 8, 31), True),    # Monday
    (date(2026, 9, 5), True),     # Saturday
    (date(2026, 9, 6), False),    # Sunday
    (date(2026, 8, 15), False),   # holiday (Saturday)
])
def test_is_working_day(d, expected):
    assert dates.is_working_day(d) is expected


def test_next_working_day_skips_sunday():
    assert dates.next_working_day(date(2026, 9, 6)) == date(2026, 9, 7)
    assert dates.next_working_day(date(2026, 9, 5)) == date(2026, 9, 5)
    assert dates.next_working_day(date(2026, 9, 5), include_self=False) == date(2026, 9, 7)


def test_add_working_days_across_sunday_and_month_end():
    assert dates.add_working_days(date(2026, 9, 5), 1) == date(2026, 9, 7)
    assert dates.add_working_days(date(2026, 8, 29), 1) == date(2026, 8, 31)
    assert dates.add_working_days(date(2026, 8, 31), 1) == date(2026, 9, 1)
    assert dates.add_working_days(date(2026, 9, 6), 0) == date(2026, 9, 7)


def test_working_days_from_default_planning_window():
    days = dates.working_days_from(date(2026, 9, 1), 6)
    assert days == [date(2026, 9, d) for d in (1, 2, 3, 4, 5, 7)]
    assert all(d.weekday() != 6 for d in days)


def test_working_days_between():
    assert dates.working_days_between(date(2026, 9, 1), date(2026, 9, 1)) == 0
    assert dates.working_days_between(date(2026, 9, 5), date(2026, 9, 7)) == 1   # Sunday skipped
    assert dates.working_days_between(date(2026, 8, 14), date(2026, 8, 17)) == 1  # holiday + Sunday


def test_helpers():
    assert dates.days_between(date(2026, 8, 29), date(2026, 9, 1)) == 3
    assert dates.week_start(date(2026, 9, 3)) == date(2026, 8, 31)
    assert dates.month_bounds(date(2026, 8, 20)) == (date(2026, 8, 1), date(2026, 8, 31))
    assert dates.month_bounds(date(2026, 12, 5)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert dates.clamp_business_date(date(2020, 1, 1)) == date(2026, 8, 1)
