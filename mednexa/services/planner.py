"""
Feature 2 - PURE planning logic (no database, no Streamlit).

build_plan() is deterministic: same inputs -> same plan. Tie-break: score desc,
earliest pending follow-up due date, higher prescriptions, lower doctor_id.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from mednexa import config
from mednexa.core.dates import working_days_between, working_days_from


@dataclass(frozen=True)
class DoctorInput:
    doctor_id: str
    name: str
    area: str
    monthly_prescriptions: int
    segment: str
    visits_per_month: int
    last_visit: date | None
    pending_followups: tuple = ()           # ((follow_up_id, due_date), ...)


@dataclass
class PlannedVisit:
    doctor_id: str
    planned_date: date
    area: str
    score: float
    breakdown: dict
    reasons: list
    follow_up_ids: list = field(default_factory=list)
    mandatory: bool = False


def score_doctor(d: DoctorInput, as_of: date, window_end: date) -> tuple[float, dict, list]:
    w, u = config.PLAN_WEIGHTS, config.URGENCY
    reasons = []
    urgency = 0.0
    if d.pending_followups:
        due = min(x[1] for x in d.pending_followups)
        n = len(d.pending_followups)
        late = (as_of - due).days
        if late > 0:
            urgency = u["overdue_base"] + (1 - u["overdue_base"]) * min(late, config.OVERDUE_URGENCY_CAP_DAYS) \
                / config.OVERDUE_URGENCY_CAP_DAYS
            reasons.append(f"Follow-up {late} day{'s' if late != 1 else ''} overdue")
        elif late == 0:
            urgency = u["due_today"]
            reasons.append("Follow-up due today")
        elif due <= window_end:
            urgency = u["in_window"]
            reasons.append(f"Follow-up due {due:%d %b}")
        else:
            urgency = u["later"]
            reasons.append(f"Follow-up due {due:%d %b}")
        if n > 1:
            reasons.append(f"{n} pending follow-ups merged")
    never = d.last_visit is None
    if never:
        recency = 1.0
        reasons.append("Never visited")
    else:
        gap = (as_of - d.last_visit).days
        recency = min(gap, config.RECENCY_CAP_DAYS) / config.RECENCY_CAP_DAYS
        if gap >= 14:
            reasons.append(f"{gap} days since last visit")
    potential = min(d.monthly_prescriptions, config.RX_SCORE_CAP) / config.RX_SCORE_CAP
    if d.segment == "A":
        reasons.append(f"High potential ({d.monthly_prescriptions} Rx/month)")
    parts = {"urgency": urgency, "recency": recency, "potential": potential, "never": 1.0 if never else 0.0}
    breakdown = {k: round(100 * w[k] * v, 1) for k, v in parts.items()}
    total = round(sum(100 * w[k] * v for k, v in parts.items()), 1)
    return total, breakdown, reasons


def priority_label(score: float, reasons: list) -> str:
    if any("overdue" in r or r == "Never visited" for r in reasons) or score >= config.PLAN_LABEL_HIGH:
        return "HIGH"
    return "MEDIUM" if score >= config.PLAN_LABEL_MEDIUM else "LOW"


def build_plan(doctors: list[DoctorInput], start: date, num_days: int, as_of: date,
               occupied: dict | None = None, exclude: set | None = None) -> list[PlannedVisit]:
    """occupied: {date: n protected visits already on that day}; exclude: doctor_ids already planned."""
    days = working_days_from(start, num_days)
    if not days:
        return []
    cap = {d: config.PLAN_DAILY_CAPACITY - (occupied or {}).get(d, 0) for d in days}
    exclude = set(exclude or ())
    scored = {}
    for doc in doctors:
        if doc.doctor_id in exclude:
            continue
        s, b, r = score_doctor(doc, as_of, days[-1])
        scored[doc.doctor_id] = (doc, s, b, r)

    def tiebreak(item):
        doc, s, _b, _r = item
        due = min((x[1] for x in doc.pending_followups), default=date.max)
        return (-s, due, -doc.monthly_prescriptions, doc.doctor_id)

    plan: list[PlannedVisit] = []
    placed: set[str] = set()

    def place(doc, s, b, r, from_idx, mandatory, extra_reason=None):
        for i in range(from_idx, len(days)):
            if cap[days[i]] > 0:
                cap[days[i]] -= 1
                reasons = list(r) + ([extra_reason] if extra_reason and i > from_idx else [])
                plan.append(PlannedVisit(doc.doctor_id, days[i], doc.area, s, b, reasons,
                                         [x[0] for x in doc.pending_followups], mandatory))
                placed.add(doc.doctor_id)
                return True
        return False

    # 1) mandatory follow-up visits: overdue/due-today -> Day 1, due in window -> due date
    mandatory = []
    for doc, s, b, r in scored.values():
        if not doc.pending_followups:
            continue
        due = min(x[1] for x in doc.pending_followups)
        if due <= days[0] or due < as_of:
            idx = 0
        elif due <= days[-1]:
            idx = next(i for i, d in enumerate(days) if d >= due)
        else:
            continue
        mandatory.append((idx, (doc, s, b, r)))
    for idx, item in sorted(mandatory, key=lambda x: (x[0], tiebreak(x[1]))):
        place(*item, from_idx=idx, mandatory=True, extra_reason="Capacity overflow from earlier day")

    # 2) fill remaining capacity by score among eligible doctors
    for i, day in enumerate(days):
        if cap[day] <= 0:
            continue
        pool = []
        for doc, s, b, r in scored.values():
            if doc.doctor_id in placed:
                continue
            if doc.last_visit is not None:
                gap_needed = math.floor(config.REVISIT_WORKING_DAYS_BASE / doc.visits_per_month)
                if working_days_between(doc.last_visit, day) < gap_needed:
                    continue
            pool.append((doc, s, b, r))
        for item in sorted(pool, key=tiebreak)[:cap[day]]:
            place(*item, from_idx=i, mandatory=False)

    return sorted(plan, key=lambda p: (p.planned_date, p.area, -p.score, p.doctor_id))
