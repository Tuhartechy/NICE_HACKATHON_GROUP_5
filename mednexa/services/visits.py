"""Feature 3 - visit logging (single atomic transaction) and visit history."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from mednexa import config
from mednexa.core import db
from mednexa.core.dates import is_working_day, parse_date
from mednexa.core.errors import ConflictError, NotFoundError, ValidationError
from mednexa.core.ids import next_id
from mednexa.repositories import doctors as doctors_repo
from mednexa.repositories import followups as fu_repo
from mednexa.repositories import plans as plans_repo
from mednexa.repositories import products as prod_repo
from mednexa.repositories import reps as reps_repo
from mednexa.repositories import visits as repo
from mednexa.services import followups as fu_service


def history(rep_id=None, doctor_id=None, date_from=None, date_to=None) -> pd.DataFrame:
    with db.session() as conn:
        df = repo.history(conn, rep_id, doctor_id, date_from, date_to)
    df["outcome"] = df["outcome"].fillna(config.NOT_RECORDED)
    return df


def doctor_holdings(doctor_id: str) -> dict:
    with db.session() as conn:
        return repo.doctor_holdings(conn, doctor_id)


def log_visit(payload: dict, *, as_of: date, actor: str) -> str:
    """Create a visit with products, feedback, samples, follow-up changes and plan link - all or nothing.

    payload keys: rep_id, doctor_id, visit_date, outcome, notes, products [{product_id, feedback}],
    issued {product_id: qty}, returned {product_id: qty}, close_follow_up_ids [..],
    new_follow_up {due_date, notes} | None, plan_item_id | None
    """
    errors = {}
    rep_id, doctor_id = payload.get("rep_id"), payload.get("doctor_id")
    if not rep_id:
        errors["rep_id"] = "Select a representative."
    if not doctor_id:
        errors["doctor_id"] = "Select a doctor."
    try:
        vdate = parse_date(payload.get("visit_date"), field="visit_date")
        if vdate > as_of:
            errors["visit_date"] = "Visit date cannot be after the business date."
        elif not is_working_day(vdate):
            errors["visit_date"] = "Visits cannot be logged on Sundays or holidays."
    except ValidationError:
        errors["visit_date"] = "Enter a valid date."
        vdate = None
    outcome = payload.get("outcome")
    if outcome not in config.OUTCOMES:
        errors["outcome"] = "Select the visit outcome."
    products = payload.get("products") or []
    pids = [p["product_id"] for p in products]
    if not pids and outcome != "Doctor unavailable":
        errors["products"] = "Select at least one product discussed."
    if len(pids) != len(set(pids)):
        errors["products"] = "A product can only be added once per visit."
    for p in products:
        if p.get("feedback") not in (None, "", *config.FEEDBACK):
            errors["products"] = "Invalid product feedback."
    issued = {k: int(v) for k, v in (payload.get("issued") or {}).items() if v}
    returned = {k: int(v) for k, v in (payload.get("returned") or {}).items() if v}
    if any(q <= 0 for q in [*issued.values(), *returned.values()]):
        errors["samples"] = "Sample quantities must be positive whole numbers."
    if set(issued) - set(pids):
        errors["samples"] = "Samples can only be issued for products discussed in this visit."
    nf = payload.get("new_follow_up")
    if nf:
        try:
            due = parse_date(nf.get("due_date"), field="follow_up_date")
            if vdate and due <= vdate:
                errors["follow_up_date"] = "Follow-up date must be after the visit date."
        except ValidationError:
            errors["follow_up_date"] = "Enter a valid follow-up date."
    if errors:
        raise ValidationError(field_errors=errors)

    with db.session() as conn:
        with db.transaction(conn):
            rep = reps_repo.get(conn, rep_id)
            doc = doctors_repo.get(conn, doctor_id)
            if not rep or not doc:
                raise NotFoundError("Unknown representative or doctor.")
            if doc["territory"] != rep["territory"]:
                raise ValidationError("This doctor is outside the representative's territory.",
                                      field_errors={"doctor_id": "Outside territory."})
            ts = db.now_iso()
            visit_id = next_id(conn, "visit")
            repo.insert_visit(conn, {"visit_id": visit_id, "rep_id": rep_id, "doctor_id": doctor_id,
                                     "visit_date": vdate.isoformat(), "outcome": outcome,
                                     "notes": (payload.get("notes") or "").strip() or None, "ts": ts})
            for p in products:
                repo.insert_visit_product(conn, visit_id, p["product_id"], p.get("feedback") or None)

            holdings = repo.doctor_holdings(conn, doctor_id)
            reserved: set[str] = set()
            for kind, items in (("SAMPLE_RETURNED", returned), ("SAMPLE_ISSUED", issued)):
                for pid, qty in items.items():
                    if prod_repo.stock_of(conn, pid) is None:
                        raise NotFoundError(f"Product {pid} has no inventory record.")
                    if kind == "SAMPLE_RETURNED" and qty > holdings.get(pid, 0):
                        raise ConflictError(f"The doctor holds only {holdings.get(pid, 0)} unit(s) of {pid}; "
                                            f"cannot return {qty}.")
                    if not prod_repo.adjust_stock(conn, pid, qty if kind == "SAMPLE_RETURNED" else -qty):
                        raise ConflictError(f"Insufficient stock for {pid}: only "
                                            f"{prod_repo.stock_of(conn, pid)} unit(s) available.")
                    tid = next_id(conn, "transaction", reserved=reserved)
                    reserved.add(tid)
                    repo.insert_transaction(conn, {"transaction_id": tid, "visit_id": visit_id, "product_id": pid,
                                                   "quantity": qty, "transaction_type": kind,
                                                   "transaction_date": vdate.isoformat()})

            for fid in payload.get("close_follow_up_ids") or []:
                f = fu_repo.get(conn, fid)
                if not f or f["doctor_id"] != doctor_id:
                    raise ValidationError(f"Follow-up {fid} does not belong to this doctor.")
                if f["due_date"] and parse_date(f["visit_date"]) > vdate:
                    raise ValidationError(f"Follow-up {fid} was created after this visit date.")
                fu_repo.complete(conn, fid, vdate.isoformat(), "VISIT", visit_id, None)

            if nf:
                fu_repo.insert(conn, {"follow_up_id": next_id(conn, "follow_up"), "visit_id": visit_id,
                                      "due_date": parse_date(nf["due_date"]).isoformat(),
                                      "notes": (nf.get("notes") or "").strip() or None})

            pid_item = payload.get("plan_item_id")
            if pid_item:
                item = plans_repo.get(conn, pid_item)
                if not item or item["doctor_id"] != doctor_id or item["rep_id"] != rep_id:
                    raise ValidationError("The selected planned visit does not match this doctor.")
                if item["status"] != "PLANNED":
                    raise ConflictError("This planned visit is no longer open.")
                plans_repo.set_status(conn, pid_item, "COMPLETED", f"Logged as {visit_id}", ts, visit_id)
                plans_repo.insert_event(conn, {"event_id": next_id(conn, "plan_event"), "plan_item_id": pid_item,
                                               "from_status": "PLANNED", "to_status": "COMPLETED",
                                               "from_date": item["planned_date"], "to_date": item["planned_date"],
                                               "actor": actor, "note": visit_id, "at": ts})
    return visit_id
