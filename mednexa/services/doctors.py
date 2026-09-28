"""Feature 1 - Doctor Intelligence Hub services."""
from __future__ import annotations

from datetime import date

import pandas as pd

from mednexa.core import db
from mednexa.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from mednexa.core.ids import next_id
from mednexa.repositories import doctors as repo
from mednexa.repositories import reps as reps_repo
from mednexa.services import rules, segmentation


def territory_of(rep_id: str | None) -> str | None:
    if not rep_id:
        return None
    with db.session() as conn:
        r = reps_repo.get(conn, rep_id)
    if not r:
        raise NotFoundError(f"Representative {rep_id} not found.")
    return r["territory"]


def list_doctors(rep_id: str | None = None, as_of: date | None = None) -> pd.DataFrame:
    """All doctors in scope with derived segment, potential, recommended visits and recency."""
    with db.session() as conn:
        df = repo.list_doctors(conn, territory_of(rep_id))
    df = segmentation.add_columns(df)
    if as_of is not None and len(df):
        df["days_since_visit"] = df["last_visit_date"].map(lambda d: rules.days_since(d, as_of))
    return df


def filter_doctors(df: pd.DataFrame, search: str = "", specialty=None, area=None, segment=None,
                   sort: str = "Prescriptions (high→low)") -> pd.DataFrame:
    out = df
    if search:
        out = out[out["name"].str.contains(search.strip(), case=False, regex=False)]
    if specialty:
        out = out[out["specialty"].isin(specialty)]
    if area:
        out = out[out["area"].isin(area)]
    if segment:
        out = out[out["segment"].isin(segment)]
    key = {"Prescriptions (high→low)": ("monthly_prescriptions", False),
           "Prescriptions (low→high)": ("monthly_prescriptions", True),
           "Name (A→Z)": ("name", True), "Name (Z→A)": ("name", False)}.get(sort, ("monthly_prescriptions", False))
    return out.sort_values([key[0], "doctor_id"], ascending=[key[1], True])


def overview(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "A": 0, "B": 0, "C": 0, "avg_rx": None}
    counts = df["segment"].value_counts()
    return {"total": len(df), "A": int(counts.get("A", 0)), "B": int(counts.get("B", 0)),
            "C": int(counts.get("C", 0)), "avg_rx": float(df["monthly_prescriptions"].mean())}


def get(doctor_id: str) -> dict:
    with db.session() as conn:
        d = repo.get(conn, doctor_id)
    if not d:
        raise NotFoundError(f"Doctor {doctor_id} not found.")
    seg = segmentation.segment_of(d["monthly_prescriptions"])
    return {**d, "segment": seg, "potential": segmentation.label(seg),
            "recommended_visits": segmentation.visits_per_month(seg)}


def options() -> dict:
    with db.session() as conn:
        return {"specialty": repo.distinct_values(conn, "specialty"), "area": repo.distinct_values(conn, "area"),
                "territory": repo.distinct_values(conn, "territory"),
                "areas_by_territory": repo.areas_by_territory(conn)}


def why_it_matters(d: dict, all_df: pd.DataFrame | None = None) -> list[str]:
    rx, seg = int(d["monthly_prescriptions"]), d["segment"]
    lines = [f"Writes about {rx} prescriptions a month, which places {d['name']} in segment {seg} "
             f"({segmentation.label(seg).lower()})."]
    if all_df is not None and len(all_df):
        rank = int((all_df["monthly_prescriptions"] > rx).sum()) + 1
        terr = all_df[all_df["territory"] == d["territory"]]
        trank = int((terr["monthly_prescriptions"] > rx).sum()) + 1
        lines.append(f"Ranks #{rank} of {len(all_df)} doctors overall and #{trank} of {len(terr)} in {d['territory']}.")
    lines.append(f"Recommended coverage: {segmentation.visits_per_month(seg)} visit(s) per month.")
    return lines


def _validate(data: dict) -> dict:
    errors = {}
    name = (data.get("name") or "").strip()
    if len(name) < 3:
        errors["name"] = "Enter the doctor's full name."
    for f in ("specialty", "area", "territory"):
        if not (data.get(f) or "").strip():
            errors[f] = "Required."
    try:
        rx = int(data.get("monthly_prescriptions"))
        if rx < 0 or rx > 5000:
            errors["monthly_prescriptions"] = "Must be between 0 and 5000."
    except (TypeError, ValueError):
        errors["monthly_prescriptions"] = "Must be a whole number."
        rx = None
    if errors:
        raise ValidationError(field_errors=errors)
    return {"name": name if name.lower().startswith("dr") else f"Dr. {name}",
            "specialty": data["specialty"].strip(), "area": data["area"].strip(),
            "territory": data["territory"].strip(), "monthly_prescriptions": rx}


def create(data: dict, *, is_manager: bool) -> str:
    if not is_manager:
        raise PermissionDeniedError("Only managers can add doctors.")
    row = _validate(data)
    with db.session() as conn:
        with db.transaction(conn):
            if conn.execute("SELECT 1 FROM reps WHERE territory=?", (row["territory"],)).fetchone() is None:
                raise ValidationError(field_errors={"territory": "Unknown territory."})
            if conn.execute("SELECT 1 FROM doctors WHERE lower(name)=lower(?) AND area=?",
                            (row["name"], row["area"])).fetchone():
                raise ValidationError("A doctor with this name already exists in this area.",
                                      field_errors={"name": "Duplicate."})
            row["doctor_id"] = next_id(conn, "doctor")
            row["ts"] = db.now_iso()
            repo.insert(conn, row)
    return row["doctor_id"]


def update(doctor_id: str, data: dict, *, is_manager: bool) -> None:
    if not is_manager:
        raise PermissionDeniedError("Only managers can edit doctors.")
    row = _validate(data)
    with db.session() as conn:
        with db.transaction(conn):
            if not repo.exists(conn, doctor_id):
                raise NotFoundError(f"Doctor {doctor_id} not found.")
            repo.update(conn, {**row, "doctor_id": doctor_id, "ts": db.now_iso()})


def profile_snapshot(doctor_id: str, as_of: date) -> dict:
    """Activity read from Features 2 and 3 (never stored in Feature 1)."""
    from mednexa.services import followups, plans, visits

    hist = visits.history(doctor_id=doctor_id)
    fu = followups.list_followups(as_of, doctor_id=doctor_id, status="Pending")
    pl = plans.list_items(doctor_id=doctor_id, as_of=as_of)
    return {
        "visits": hist,
        "visit_count": len(hist),
        "last_visit": hist["visit_date"].iloc[0] if len(hist) else None,
        "samples": int(hist["samples_issued"].sum()) if len(hist) else 0,
        "pending_followups": fu,
        "planned": pl[pl["status"] == "PLANNED"] if len(pl) else pl,
        "missed": int(pl["missed"].sum()) if len(pl) else 0,
        "completed_plans": int((pl["status"] == "COMPLETED").sum()) if len(pl) else 0,
    }
