"""
Feature 5 - Action Center. Actions are DERIVED from Feature 3 follow-ups and Feature 2 plan items;
only lifecycle state (snooze/done/dismiss/resolved) and history are stored.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from mednexa import config
from mednexa.core import db
from mednexa.core.dates import parse_date
from mednexa.core.errors import NotFoundError, ValidationError
from mednexa.core.ids import next_id
from mednexa.repositories import actions as repo
from mednexa.services import followups, plans, rules

TYPE_LABELS = {"OVERDUE_FOLLOW_UP": "Overdue follow-up", "DUE_TODAY_FOLLOW_UP": "Follow-up due today",
               "UPCOMING_FOLLOW_UP": "Upcoming follow-up", "MISSED_VISIT": "Missed planned visit",
               "UPCOMING_VISIT_PREPARATION": "Visit preparation"}
CLOSED = ("DONE", "DISMISSED", "RESOLVED")


def _candidates(as_of: date, rep_id: str | None) -> list[dict]:
    out = []
    fu = followups.list_followups(as_of, rep_id=rep_id, status="Pending")
    for r in fu.itertuples():
        t = {"OVERDUE": "OVERDUE_FOLLOW_UP", "DUE_TODAY": "DUE_TODAY_FOLLOW_UP",
             "UPCOMING": "UPCOMING_FOLLOW_UP"}.get(r.timing)
        if not t:
            continue
        late = int(r.days_overdue)
        if t == "OVERDUE_FOLLOW_UP":
            reason = f"Follow-up from the {parse_date(r.visit_date):%d %b} visit is {late} day{'s' if late != 1 else ''} overdue."
            rec = "Visit or contact the doctor and close the follow-up."
        elif t == "DUE_TODAY_FOLLOW_UP":
            reason, rec = "Follow-up is due today.", "Complete the follow-up today."
        else:
            reason = f"Follow-up due {parse_date(r.due_date):%a %d %b}."
            rec = "Plan the follow-up into this week's visits."
        out.append({"action_key": f"FOLLOW_UP:{r.follow_up_id}", "source_type": "FOLLOW_UP",
                    "source_id": r.follow_up_id, "action_type": t, "rep_id": r.rep_id, "doctor_id": r.doctor_id,
                    "doctor_name": r.doctor_name, "specialty": r.specialty, "area": r.area, "segment": r.segment,
                    "due_date": r.due_date, "days_late": late, "reason": reason, "recommended": rec,
                    "priority": rules.action_priority(t, days_late=late, segment=r.segment)})
    items = plans.list_items(rep_id=rep_id, as_of=as_of, statuses=["PLANNED"])
    for r in items.itertuples():
        if rules.is_missed(r.status, r.planned_date, as_of):
            t, late = "MISSED_VISIT", (as_of - parse_date(r.planned_date)).days
            reason = f"Planned for {parse_date(r.planned_date):%a %d %b} and not logged."
            if r.reasons_list:
                reason += f" Planned because: {r.reasons_list[0].lower()}."
            rec = "Log the visit if it happened, otherwise reschedule or skip it."
        elif rules.is_prep_window(r.status, r.planned_date, as_of):
            t, late = "UPCOMING_VISIT_PREPARATION", 0
            reason = f"Visit planned for {parse_date(r.planned_date):%a %d %b}." + (
                f" {'; '.join(r.reasons_list[:2])}." if r.reasons_list else "")
            rec = "Review the doctor profile, last products and open follow-ups before the visit."
        else:
            continue
        out.append({"action_key": f"PLAN_ITEM:{r.plan_item_id}", "source_type": "PLAN_ITEM",
                    "source_id": r.plan_item_id, "action_type": t, "rep_id": r.rep_id, "doctor_id": r.doctor_id,
                    "doctor_name": r.doctor_name, "specialty": r.specialty, "area": r.area, "segment": r.segment,
                    "due_date": r.planned_date, "days_late": late, "reason": reason, "recommended": rec,
                    "priority": rules.action_priority(t, days_late=late, segment=r.segment)})
    return out


def sync(as_of: date, rep_id: str | None = None, actor: str = "SYSTEM") -> list[dict]:
    """Idempotent. Evaluates the whole team (so resolution is always correct), returns rep-scoped rows."""
    cands = _candidates(as_of, None)
    keys = {c["action_key"] for c in cands}
    ts = db.now_iso()
    with db.session() as conn:
        with db.transaction(conn):
            states = repo.all_states(conn)
            for c in cands:
                st = states.get(c["action_key"])
                if st is None:
                    repo.insert(conn, c["action_key"], c["source_type"], c["source_id"], ts)
                    _event(conn, c["action_key"], None, "OPEN", actor, "Generated", ts)
                elif st["status"] == "RESOLVED":
                    repo.set_status(conn, c["action_key"], "OPEN", ts)
                    _event(conn, c["action_key"], "RESOLVED", "OPEN", actor, "Condition active again", ts)
            for key, st in states.items():
                if key not in keys and st["status"] in ("OPEN", "SNOOZED"):
                    repo.set_status(conn, key, "RESOLVED", ts)
                    _event(conn, key, st["status"], "RESOLVED", actor, "Source condition cleared", ts)
            states = repo.all_states(conn)
    for c in cands:
        st = states.get(c["action_key"], {})
        c["status"] = st.get("status", "OPEN")
        c["snoozed_until"] = st.get("snoozed_until")
    return [c for c in cands if rep_id is None or c["rep_id"] == rep_id]


def _event(conn, key, frm, to, actor, note, ts):
    repo.insert_event(conn, {"event_id": next_id(conn, "action_event"), "action_key": key, "from_status": frm,
                             "to_status": to, "actor": actor, "note": note, "at": ts})


def open_actions(as_of: date, rep_id: str | None = None) -> pd.DataFrame:
    cands = sync(as_of, rep_id)
    rows = [c for c in cands if c["status"] == "OPEN"
            or (c["status"] == "SNOOZED" and (not c["snoozed_until"] or parse_date(c["snoozed_until"]) <= as_of))]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["action_key", "priority", "action_type", "doctor_id", "due_date"])
    df["type_label"] = df["action_type"].map(TYPE_LABELS)
    df["rank"] = df["priority"].map(rules.PRIORITY_RANK)
    seg_rank = df["segment"].map({"A": 0, "B": 1, "C": 2})
    df = df.assign(seg_rank=seg_rank).sort_values(["rank", "due_date", "seg_rank", "doctor_id", "action_key"])
    return df.reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {k: 0 for k in ("open", "CRITICAL", "HIGH", "MEDIUM", "LOW", "due_today", "overdue", "upcoming",
                               "missed", "prep")}
    t = df["action_type"]
    return {"open": len(df), **{p: int((df.priority == p).sum()) for p in config.ACTION_PRIORITIES},
            "due_today": int((t == "DUE_TODAY_FOLLOW_UP").sum()), "overdue": int((t == "OVERDUE_FOLLOW_UP").sum()),
            "upcoming": int((t == "UPCOMING_FOLLOW_UP").sum()), "missed": int((t == "MISSED_VISIT").sum()),
            "prep": int((t == "UPCOMING_VISIT_PREPARATION").sum())}


def grouped(df: pd.DataFrame) -> list[dict]:
    """One card per (doctor, action type); follow-ups for the same doctor are grouped."""
    groups = []
    if df.empty:
        return groups
    for (_doc, _t), g in df.groupby(["doctor_id", "action_type"], sort=False):
        first = g.iloc[0].to_dict()
        first["keys"] = list(g["action_key"])
        first["count"] = len(g)
        first["oldest_due"] = g["due_date"].min()
        first["max_late"] = int(g["days_late"].max())
        groups.append(first)
    groups.sort(key=lambda x: (rules.PRIORITY_RANK[x["priority"]], x["oldest_due"], x["doctor_id"]))
    return groups


def _set(key: str, status: str, actor: str, note: str | None, snoozed_until=None):
    ts = db.now_iso()
    with db.session() as conn:
        with db.transaction(conn):
            st = repo.all_states(conn).get(key)
            if not st:
                raise NotFoundError("Action not found.")
            repo.set_status(conn, key, status, ts, snoozed_until)
            _event(conn, key, st["status"], status, actor, note, ts)


def complete_followup_by_contact(key: str, note: str, as_of: date, actor: str) -> None:
    """Completing a follow-up action updates the authoritative Feature 3 follow-up first."""
    if not key.startswith("FOLLOW_UP:"):
        raise ValidationError("Only follow-up actions can be completed by contact.")
    followups.complete(key.split(":", 1)[1], method="CONTACT", note=note, as_of=as_of)
    _set(key, "DONE", actor, f"Completed by contact: {note.strip()}")


def mark_prepared(key: str, actor: str) -> None:
    _set(key, "DONE", actor, "Prepared for visit")


def snooze(key: str, until, actor: str, as_of: date) -> None:
    d = parse_date(until)
    if d <= as_of:
        raise ValidationError("Snooze until a date after the business date.")
    _set(key, "SNOOZED", actor, f"Snoozed until {d:%d %b}", d.isoformat())


def dismiss(key: str, note: str, actor: str) -> None:
    if not (note or "").strip():
        raise ValidationError("Add a reason for dismissing.")
    _set(key, "DISMISSED", actor, note.strip())


def history(limit: int = 100) -> pd.DataFrame:
    with db.session() as conn:
        return repo.events(conn, limit)
