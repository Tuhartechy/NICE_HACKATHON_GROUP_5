"""Feature 3 - authoritative follow-up service. The ONLY way a follow-up is completed."""
from __future__ import annotations

from datetime import date

import pandas as pd

from mednexa import config
from mednexa.core import db
from mednexa.core.dates import parse_date
from mednexa.core.errors import ConflictError, NotFoundError, ValidationError
from mednexa.repositories import followups as repo
from mednexa.services import rules, segmentation


def list_followups(as_of: date, rep_id=None, status=None, doctor_id=None) -> pd.DataFrame:
    with db.session() as conn:
        df = repo.list_followups(conn, rep_id=rep_id, status=status, doctor_id=doctor_id)
    if len(df):
        df["segment"] = df["monthly_prescriptions"].map(segmentation.segment_of)
        df["timing"] = [rules.follow_up_timing(d, as_of) if s == "Pending" else "DONE"
                        for d, s in zip(df["due_date"], df["status"])]
        df["days_overdue"] = [rules.days_overdue(d, as_of) if s == "Pending" else 0
                              for d, s in zip(df["due_date"], df["status"])]
    else:
        df["segment"], df["timing"], df["days_overdue"] = [], [], []
    return df


def complete(follow_up_id: str, *, method: str, as_of: date, note: str | None = None,
             visit_id: str | None = None, conn=None) -> None:
    """Complete a pending follow-up by VISIT (needs visit_id) or CONTACT (needs a note)."""
    if method not in config.COMPLETION_METHODS:
        raise ValidationError(field_errors={"method": "Invalid completion method."})
    if method == "CONTACT" and not (note or "").strip():
        raise ValidationError("Add a short note describing the contact.", field_errors={"note": "Required."})
    if method == "VISIT" and not visit_id:
        raise ValidationError("A visit is required to complete by visit.")

    def _do(c):
        f = repo.get(c, follow_up_id)
        if f is None:
            raise NotFoundError(f"Follow-up {follow_up_id} not found.")
        if f["status"] != "Pending":
            raise ConflictError("This follow-up is already completed.")
        when = as_of.isoformat()
        if parse_date(when) < parse_date(f["visit_date"]):
            raise ValidationError("Completion date cannot be before the originating visit.")
        repo.complete(c, follow_up_id, when, method, visit_id, (note or "").strip() or None)

    if conn is not None:
        _do(conn)
    else:
        with db.session() as c:
            with db.transaction(c):
                _do(c)
