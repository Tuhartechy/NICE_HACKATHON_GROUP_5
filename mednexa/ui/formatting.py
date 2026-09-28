"""Display formatting only - no business rules."""

from __future__ import annotations

from datetime import date

from mednexa import config
from mednexa.core.dates import parse_date

DASH = "—"


def fmt_date(value, *, with_weekday: bool = False) -> str:
    if value is None or value == "":
        return DASH
    d = parse_date(value)
    return d.strftime("%a, %d %b %Y") if with_weekday else d.strftime("%d %b %Y")


def fmt_short_date(value) -> str:
    if value is None or value == "":
        return DASH
    return parse_date(value).strftime("%d %b")


def fmt_int(value) -> str:
    if value is None:
        return DASH
    return f"{int(value):,}"


def fmt_pct(ratio, *, digits: int = 0) -> str:
    """0.724 -> '72%'. None (not computable) -> '—', never a fake 0%."""
    if ratio is None:
        return DASH
    return f"{ratio * 100:.{digits}f}%"


def fmt_signed(value, *, digits: int = 0) -> str:
    if value is None:
        return DASH
    if digits == 0:
        return f"{int(round(value)):+,d}"
    return f"{value:+,.{digits}f}"


def or_not_recorded(value) -> str:
    """Historical records without outcome/feedback show 'Not recorded'."""
    if value is None or (isinstance(value, float) and value != value) or str(value).strip() == "":
        return config.NOT_RECORDED
    return str(value)


def days_label(n: int) -> str:
    return f"{n} day" if abs(n) == 1 else f"{n} days"


def business_date_label(d: date) -> str:
    return d.strftime("%a %d %b %Y")
