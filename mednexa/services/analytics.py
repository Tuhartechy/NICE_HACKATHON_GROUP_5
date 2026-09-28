"""Feature 4 - management analytics. Read-only; every rule comes from rules.py / segmentation.py."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from mednexa import config
from mednexa.core import db
from mednexa.core.dates import month_bounds, parse_date, week_start
from mednexa.repositories import visits as visits_repo
from mednexa.services import doctors, followups, inventory, plans, rules, segmentation


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    rep_id: str | None = None
    segment: tuple = ()
    area: tuple = ()


def default_period(as_of: date) -> tuple[date, date]:
    """History month before the business date (Aug 2026 by default)."""
    """History month start through the business date (so visits logged 'today' are included)."""
    return month_bounds(as_of - timedelta(days=1))[0], as_of


def _scope(f: Filters, as_of: date):
    docs = doctors.list_doctors(f.rep_id, as_of)
    if f.segment:
        docs = docs[docs.segment.isin(f.segment)]
    if f.area:
        docs = docs[docs.area.isin(f.area)]
    ids = set(docs.doctor_id)
    vis = visits_repo_history(f)
    vis = vis[vis.doctor_id.isin(ids)]
    return docs, vis, ids


def visits_repo_history(f: Filters) -> pd.DataFrame:
    with db.session() as conn:
        v = visits_repo.history(conn, rep_id=f.rep_id, date_from=f.start.isoformat(), date_to=f.end.isoformat())
    v["outcome"] = v["outcome"].fillna(config.NOT_RECORDED)
    return v


def pct_change(cur, prev):
    """None when the previous value is zero/unavailable - never a fabricated percentage."""
    if prev in (None, 0) or cur is None:
        return None
    return (cur - prev) / prev


def kpis(f: Filters, as_of: date) -> dict:
    docs, vis, ids = _scope(f, as_of)
    fu = followups.list_followups(as_of, rep_id=f.rep_id)
    fu = fu[fu.doctor_id.isin(ids)]
    pend = fu[fu.status == "Pending"]
    p0, p1 = month_bounds(as_of)          # plan KPIs always use the business-date month (plans start Sep 2026)
    items = plans.list_items(rep_id=f.rep_id, as_of=as_of, date_from=p0.isoformat(), date_to=p1.isoformat())
    items = items[items.doctor_id.isin(ids) & (items.status != "CANCELLED")] if len(items) else items
    # due = planned before the business date, or already closed (completed/skipped) on any date
    due_items = items[(items.planned_date < as_of.isoformat()) | items.status.isin(["COMPLETED", "SKIPPED"])] \
        if len(items) else items
    completion = (float((due_items.status == "COMPLETED").sum()) / len(due_items)) if len(due_items) else None
    stock = inventory.stock()
    seg = docs.segment.value_counts()
    return {
        "doctors": len(docs), "A": int(seg.get("A", 0)), "B": int(seg.get("B", 0)), "C": int(seg.get("C", 0)),
        "reps": len(plans.list_reps()) if f.rep_id is None else 1,
        "visits": len(vis), "doctors_visited": vis.doctor_id.nunique(),
        "coverage": (vis.doctor_id.nunique() / len(docs)) if len(docs) else None,
        "planned": len(items), "plan_completion": completion,
        "pending_fu": len(pend), "overdue_fu": int((pend.timing == "OVERDUE").sum()),
        "samples_issued": int(vis.samples_issued.sum()) if len(vis) else 0,
        "stock_alerts": int(stock.status.isin(["CRITICAL", "LOW"]).sum()),
        "stock_critical": int((stock.status == "CRITICAL").sum()),
    }


def week_comparison(f: Filters, as_of: date) -> dict:
    """Last full Mon–Sun week before the business date vs the week before it."""
    this_start = week_start(as_of) - timedelta(days=7)
    prev_start = this_start - timedelta(days=7)
    out = {"this": (this_start, this_start + timedelta(days=6)), "prev": (prev_start, prev_start + timedelta(days=6))}
    for key, (s, e) in list(out.items()):
        ff = Filters(s, e, f.rep_id, f.segment, f.area)
        _d, v, ids = _scope(ff, as_of)
        fu = followups.list_followups(as_of, rep_id=f.rep_id)
        done = fu[(fu.status == "Completed") & fu.completed_on.between(s.isoformat(), e.isoformat())
                  & fu.doctor_id.isin(ids)]
        out[key + "_vals"] = {"visits": len(v), "doctors": v.doctor_id.nunique(),
                              "samples": int(v.samples_issued.sum()) if len(v) else 0, "fu_completed": len(done)}
    out["delta"] = {k: (out["this_vals"][k] - out["prev_vals"][k], pct_change(out["this_vals"][k], out["prev_vals"][k]))
                    for k in out["this_vals"]}
    return out


def rep_comparison(f: Filters, as_of: date) -> pd.DataFrame:
    rows = []
    m_start, m_end = f.start, f.end
    for rep in plans.list_reps():
        ff = Filters(m_start, m_end, rep["rep_id"], f.segment, f.area)
        docs, vis, ids = _scope(ff, as_of)
        actual = vis.groupby("doctor_id").size()
        docs = docs.assign(actual=docs.doctor_id.map(actual).fillna(0).astype(int))
        rec = docs.recommended_visits.sum()
        comp = docs[["actual", "recommended_visits"]].min(axis=1).sum() / rec if rec else None
        a = docs[docs.segment == "A"]
        a_comp = (a[["actual", "recommended_visits"]].min(axis=1).sum() / a.recommended_visits.sum()) if len(a) else None
        fu = followups.list_followups(as_of, rep_id=rep["rep_id"])
        fu = fu[fu.doctor_id.isin(ids)]
        closed = int((fu.status == "Completed").sum())
        due = closed + int(((fu.status == "Pending") & (fu.timing == "OVERDUE")).sum())
        rows.append({"rep_id": rep["rep_id"], "Representative": rep["name"], "Territory": rep["territory"],
                     "Doctors": len(docs), "Visits": len(vis), "Doctors visited": vis.doctor_id.nunique(),
                     "Coverage": vis.doctor_id.nunique() / len(docs) if len(docs) else None,
                     "Frequency compliance": comp, "A-doctor compliance": a_comp,
                     "Samples issued": int(vis.samples_issued.sum()) if len(vis) else 0,
                     "Pending follow-ups": int((fu.status == "Pending").sum()),
                     "Overdue follow-ups": int(((fu.status == "Pending") & (fu.timing == "OVERDUE")).sum()),
                     "Follow-up closure": closed / due if due else None})
    return pd.DataFrame(rows)


def compliance_by_segment(f: Filters, as_of: date) -> pd.DataFrame:
    docs, vis, _ = _scope(f, as_of)
    actual = vis.groupby("doctor_id").size()
    docs = docs.assign(actual=docs.doctor_id.map(actual).fillna(0).astype(int))
    docs["capped"] = docs[["actual", "recommended_visits"]].min(axis=1)
    g = docs.groupby("segment").agg(doctors=("doctor_id", "count"), recommended=("recommended_visits", "sum"),
                                    actual=("actual", "sum"), fulfilled=("capped", "sum")).reset_index()
    g["compliance"] = g.fulfilled / g.recommended
    return g


def coverage_gaps(f: Filters, as_of: date) -> pd.DataFrame:
    docs, _v, _ = _scope(f, as_of)
    docs = docs.copy()
    docs["not_recent"] = [rules.not_recently_visited(d, s) for d, s in zip(docs.days_since_visit, docs.segment)]
    gaps = docs[docs.not_recent].copy()
    gaps["status"] = gaps.days_since_visit.map(lambda d: "Never visited" if d is None or d != d else f"{int(d)} days")
    return gaps.sort_values(["segment", "monthly_prescriptions"], ascending=[True, False])


def visits_trend(f: Filters, as_of: date) -> pd.DataFrame:
    _d, vis, _ = _scope(f, as_of)
    if vis.empty:
        return pd.DataFrame(columns=["week", "rep_id", "visits"])
    vis = vis.assign(week=vis.visit_date.map(lambda d: week_start(parse_date(d))))
    return vis.groupby(["week", "rep_id"]).size().reset_index(name="visits")


def product_activity(f: Filters, as_of: date) -> pd.DataFrame:
    _d, vis, _ = _scope(f, as_of)
    with db.session() as conn:
        vp = visits_repo.visit_products(conn)
    vp = vp[vp.visit_id.isin(set(vis.visit_id))]
    vp["feedback"] = vp["feedback"].fillna(config.NOT_RECORDED)
    return vp


def samples_by_product(f: Filters, as_of: date) -> pd.DataFrame:
    _d, vis, _ = _scope(f, as_of)
    tx = inventory.transactions()
    tx = tx[tx.visit_id.isin(set(vis.visit_id))]
    if tx.empty:
        return pd.DataFrame(columns=["product_name", "SAMPLE_ISSUED", "SAMPLE_RETURNED", "net"])
    p = tx.pivot_table(index="product_name", columns="transaction_type", values="quantity", aggfunc="sum",
                       fill_value=0).reset_index()
    for c in config.TRANSACTION_TYPES:
        if c not in p:
            p[c] = 0
    p["net"] = p.SAMPLE_ISSUED - p.SAMPLE_RETURNED
    return p.sort_values("SAMPLE_ISSUED", ascending=False)


def outcomes(f: Filters, as_of: date) -> pd.DataFrame:
    _d, vis, _ = _scope(f, as_of)
    return vis.groupby("outcome").size().reset_index(name="visits")


def exceptions(as_of: date, rep_id: str | None = None) -> list[dict]:
    """Shared exception conditions (same rules the Action Center converts into actions)."""
    out = []
    fu = followups.list_followups(as_of, rep_id=rep_id, status="Pending")
    over = fu[fu.timing == "OVERDUE"]
    crit = over[over.days_overdue >= config.OVERDUE_CRITICAL_DAYS]
    if len(over):
        out.append({"severity": "critical" if len(crit) else "warning", "title": f"{len(over)} overdue follow-ups",
                    "detail": f"{len(crit)} are {config.OVERDUE_CRITICAL_DAYS}+ days overdue · "
                              + ", ".join(f"{r}: {n}" for r, n in over.rep_id.value_counts().sort_index().items())})
    docs = doctors.list_doctors(rep_id, as_of)
    never_a = docs[(docs.segment == "A") & docs.last_visit_date.isna()]
    if len(never_a):
        out.append({"severity": "critical", "title": f"{len(never_a)} high-potential doctors never visited",
                    "detail": ", ".join(f"{r.name} ({r.rep_id})" for r in never_a.itertuples())})
    items = plans.list_items(rep_id=rep_id, as_of=as_of, statuses=["PLANNED"])
    missed = items[items.missed] if len(items) else items
    if len(missed):
        out.append({"severity": "warning", "title": f"{len(missed)} missed planned visits",
                    "detail": ", ".join(f"{r.doctor_name} ({r.planned_date})" for r in missed.head(6).itertuples())})
    stock = inventory.stock()
    for status, sev in (("CRITICAL", "critical"), ("LOW", "warning")):
        s = stock[stock.status == status]
        if len(s):
            out.append({"severity": sev, "title": f"{len(s)} product(s) {status.lower()} on stock",
                        "detail": ", ".join(f"{r.product_name}: {r.current_stock} (min {r.minimum_stock})"
                                            for r in s.itertuples())})
    return out
