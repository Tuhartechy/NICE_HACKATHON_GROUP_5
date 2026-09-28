"""Feature 2 - plan persistence: generate/regenerate, list, move, skip, cancel, add."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from mednexa import config
from mednexa.core import db
from mednexa.core.dates import is_working_day, parse_date, working_days_from
from mednexa.core.errors import ConflictError, NotFoundError, ValidationError
from mednexa.core.ids import next_id
from mednexa.repositories import doctors as doctors_repo
from mednexa.repositories import followups as fu_repo
from mednexa.repositories import plans as repo
from mednexa.repositories import reps as reps_repo
from mednexa.services import planner, rules, segmentation

PROTECTED = ("COMPLETED", "SKIPPED", "CANCELLED")


def list_reps() -> list[dict]:
    with db.session() as conn:
        return reps_repo.list_reps(conn)


def _inputs(conn, rep: dict) -> list[planner.DoctorInput]:
    docs = doctors_repo.list_doctors(conn, rep["territory"])
    fus = fu_repo.list_followups(conn, status="Pending")
    pending: dict[str, list] = {}
    for r in fus.itertuples():
        pending.setdefault(r.doctor_id, []).append((r.follow_up_id, parse_date(r.due_date)))
    out = []
    for r in docs.itertuples():
        seg = segmentation.segment_of(r.monthly_prescriptions)
        out.append(planner.DoctorInput(
            r.doctor_id, r.name, r.area, int(r.monthly_prescriptions), seg, segmentation.visits_per_month(seg),
            parse_date(r.last_visit_date) if isinstance(r.last_visit_date, str) else None,
            tuple(sorted(pending.get(r.doctor_id, []), key=lambda x: (x[1], x[0])))))
    return out


def rep_summary(rep_id: str, as_of: date) -> dict:
    with db.session() as conn:
        rep = reps_repo.get(conn, rep_id)
        if not rep:
            raise NotFoundError(f"Representative {rep_id} not found.")
        inputs = _inputs(conn, rep)
    week_end = as_of.toordinal() + 6
    fu = [x for d in inputs for x in d.pending_followups]
    return {"rep": rep, "doctors": len(inputs),
            "overdue": sum(1 for _, due in fu if due < as_of),
            "due_this_week": sum(1 for _, due in fu if as_of <= due and due.toordinal() <= week_end),
            "never_visited": sum(1 for d in inputs if d.last_visit is None)}


def generate(rep_id: str, start: date, num_days: int, as_of: date, actor: str) -> str:
    if num_days < 1 or num_days > 26:
        raise ValidationError(field_errors={"num_days": "Choose 1–26 working days."})
    days = working_days_from(start, num_days)
    ts = db.now_iso()
    with db.session() as conn:
        with db.transaction(conn):
            rep = reps_repo.get(conn, rep_id)
            if not rep:
                raise NotFoundError(f"Representative {rep_id} not found.")
            existing = repo.list_items(conn, rep_id=rep_id, date_from=days[0], date_to=days[-1])
            # replace only engine-made PLANNED items on/after the business date; everything else is protected
            replace = existing[(existing.status == "PLANNED") & (existing.is_manual == 0)
                               & (existing.planned_date >= as_of.isoformat())]
            repo.delete_items(conn, list(replace.plan_item_id))
            keep = existing[~existing.plan_item_id.isin(replace.plan_item_id)]
            keep = keep[keep.status != "CANCELLED"]
            occupied = keep.groupby(keep.planned_date.map(parse_date)).size().to_dict()
            # doctors with an open PLANNED item anywhere are not planned twice
            open_items = repo.list_items(conn, rep_id=rep_id, statuses=["PLANNED"])
            exclude = set(keep.doctor_id) | set(open_items.doctor_id)
            result = planner.build_plan(_inputs(conn, rep), days[0], num_days, as_of, occupied, exclude)
            run_id = next_id(conn, "plan_run")
            repo.insert_run(conn, {"run_id": run_id, "rep_id": rep_id, "start_date": days[0].isoformat(),
                                   "num_days": num_days, "as_of": as_of.isoformat(), "ts": ts})
            reserved: set[str] = set()
            for p in result:
                pid = next_id(conn, "plan_item", reserved=reserved)
                reserved.add(pid)
                repo.insert_item(conn, {"plan_item_id": pid, "rep_id": rep_id, "doctor_id": p.doctor_id,
                                        "planned_date": p.planned_date.isoformat(), "is_manual": 0,
                                        "score": p.score, "score_breakdown": json.dumps(p.breakdown),
                                        "reasons": json.dumps(p.reasons), "run_id": run_id, "ts": ts})
                repo.link_followups(conn, pid, p.follow_up_ids)
    return run_id


def list_items(rep_id=None, as_of: date | None = None, date_from=None, date_to=None, doctor_id=None,
               statuses=None) -> pd.DataFrame:
    with db.session() as conn:
        df = repo.list_items(conn, rep_id, date_from, date_to, statuses, doctor_id)
    as_of = as_of or config.DEFAULT_AS_OF
    df["segment"] = df["monthly_prescriptions"].map(segmentation.segment_of) if len(df) else []
    df["reasons_list"] = df["reasons"].map(lambda s: json.loads(s) if s else []) if len(df) else []
    df["breakdown"] = df["score_breakdown"].map(lambda s: json.loads(s) if s else {}) if len(df) else []
    df["label"] = [planner.priority_label(s or 0, r) for s, r in zip(df["score"], df["reasons_list"])] if len(df) else []
    df["missed"] = [rules.is_missed(s, d, as_of) for s, d in zip(df["status"], df["planned_date"])] if len(df) else []
    return df


def _change(item_id: str, actor: str, fn):
    ts = db.now_iso()
    with db.session() as conn:
        with db.transaction(conn):
            item = repo.get(conn, item_id)
            if not item:
                raise NotFoundError("Planned visit not found.")
            if item["status"] != "PLANNED":
                raise ConflictError("Only open planned visits can be changed.")
            ev = fn(conn, item, ts)
            repo.insert_event(conn, {"event_id": next_id(conn, "plan_event"), "plan_item_id": item_id,
                                     "actor": actor, "at": ts, **ev})


def move(item_id: str, new_date, actor: str, as_of: date) -> None:
    d = parse_date(new_date)
    if not is_working_day(d):
        raise ValidationError("Choose a working day (Monday–Saturday).")
    if d < as_of:
        raise ValidationError("A visit cannot be moved into the past.")

    def fn(conn, item, ts):
        same_day = repo.list_items(conn, rep_id=item["rep_id"], date_from=d, date_to=d, statuses=["PLANNED", "COMPLETED"])
        if len(same_day[same_day.plan_item_id != item_id]) >= config.PLAN_DAILY_CAPACITY:
            raise ConflictError(f"{d:%d %b} already has {config.PLAN_DAILY_CAPACITY} visits.")
        repo.set_date(conn, item_id, d.isoformat(), ts)
        return {"from_status": "PLANNED", "to_status": "PLANNED", "from_date": item["planned_date"],
                "to_date": d.isoformat(), "note": "Moved"}
    _change(item_id, actor, fn)


def skip(item_id: str, reason: str, actor: str) -> None:
    if not (reason or "").strip():
        raise ValidationError("Give a reason for skipping.", field_errors={"reason": "Required."})

    def fn(conn, item, ts):
        repo.set_status(conn, item_id, "SKIPPED", reason.strip(), ts)
        return {"from_status": "PLANNED", "to_status": "SKIPPED", "from_date": item["planned_date"],
                "to_date": item["planned_date"], "note": reason.strip()}
    _change(item_id, actor, fn)


def cancel(item_id: str, reason: str, actor: str) -> None:
    def fn(conn, item, ts):
        repo.set_status(conn, item_id, "CANCELLED", (reason or "Removed").strip(), ts)
        return {"from_status": "PLANNED", "to_status": "CANCELLED", "from_date": item["planned_date"],
                "to_date": item["planned_date"], "note": (reason or "Removed").strip()}
    _change(item_id, actor, fn)


def add_item(rep_id: str, doctor_id: str, planned_date, actor: str, as_of: date) -> str:
    d = parse_date(planned_date)
    if not is_working_day(d) or d < as_of:
        raise ValidationError("Choose a working day on or after the business date.")
    ts = db.now_iso()
    with db.session() as conn:
        with db.transaction(conn):
            rep, doc = reps_repo.get(conn, rep_id), doctors_repo.get(conn, doctor_id)
            if not rep or not doc or doc["territory"] != rep["territory"]:
                raise ValidationError("Doctor is outside this representative's territory.")
            pid = next_id(conn, "plan_item")
            repo.insert_item(conn, {"plan_item_id": pid, "rep_id": rep_id, "doctor_id": doctor_id,
                                    "planned_date": d.isoformat(), "is_manual": 1, "score": None,
                                    "score_breakdown": None, "reasons": json.dumps(["Added manually"]),
                                    "run_id": None, "ts": ts})
            pending = fu_repo.list_followups(conn, status="Pending", doctor_id=doctor_id)
            repo.link_followups(conn, pid, list(pending.follow_up_id))
            repo.insert_event(conn, {"event_id": next_id(conn, "plan_event"), "plan_item_id": pid,
                                     "from_status": None, "to_status": "PLANNED", "from_date": None,
                                     "to_date": d.isoformat(), "actor": actor, "note": "Added", "at": ts})
    return pid
