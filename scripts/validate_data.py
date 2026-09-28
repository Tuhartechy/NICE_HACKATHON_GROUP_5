"""
validate_data.py - Data-quality checks for the synthetic pharma field-force dataset.

Usage:  python validate_data.py
Uses the Python standard library only. Exit code 0 = all checks passed, 1 = at least one FAIL.
"""

import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# MedNexa copy: only this path line differs from the original dataset project.
# Seed CSVs live in <project>/data/seed; MEDNEXA_SEED_DIR overrides it.
DATA_DIR = Path(os.environ.get("MEDNEXA_SEED_DIR", Path(__file__).resolve().parent.parent / "data" / "seed"))
AS_OF = date(2026, 8, 31)            # dataset "today"
MONTH = (2026, 8)                    # all visits must fall in this month
A_MIN, B_MIN = 150, 70               # segmentation thresholds
PLANNED = {"A": 4, "B": 2, "C": 1}

SCHEMA = {
    "reps.csv": ["rep_id", "name", "territory"],
    "doctors.csv": ["doctor_id", "name", "specialty", "area", "territory", "monthly_prescriptions"],
    "visits.csv": ["visit_id", "rep_id", "doctor_id", "date", "products_discussed",
                   "samples_given", "follow_up_required", "follow_up_date", "follow_up_status"],
}
EXPECTED_ROWS = {"reps.csv": (5, 5), "doctors.csv": (100, 100), "visits.csv": (300, 500)}
REQUIRED_NON_NULL = {
    "reps.csv": ["rep_id", "name", "territory"],
    "doctors.csv": ["doctor_id", "name", "specialty", "area", "territory", "monthly_prescriptions"],
    "visits.csv": ["visit_id", "rep_id", "doctor_id", "date", "products_discussed",
                   "samples_given", "follow_up_required", "follow_up_status"],
}

results = []  # (status, check, detail)


def record(ok, check, detail="", warn=False):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    results.append((status, check, detail))


def show(bad, limit=5):
    bad = list(bad)
    return "" if not bad else f"{len(bad)} issue(s), e.g. {bad[:limit]}"


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def parse_int(s):
    try:
        f = float(s)
        return int(f) if f == int(f) else None
    except (ValueError, TypeError):
        return None


def segment(rx):
    return "A" if rx >= A_MIN else ("B" if rx >= B_MIN else "C")


# ------------------------------------------------------------------ 1. files & columns
tables = {}
for fname, cols in SCHEMA.items():
    path = DATA_DIR / fname
    if not path.exists():
        record(False, f"{fname}: file exists", f"missing at {path}")
        continue
    record(True, f"{fname}: file exists")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in reader]
    missing = [c for c in cols if c not in header]
    record(not missing, f"{fname}: required columns", f"missing {missing}" if missing else "")
    tables[fname] = rows

if len(tables) < 3 or any(r[0] == "FAIL" for r in results):
    for s, c, d in results:
        print(f"[{s}] {c} {('- ' + d) if d else ''}")
    print("\nOVERALL: FAIL (cannot continue without all files/columns)")
    sys.exit(1)

reps, doctors, visits = tables["reps.csv"], tables["doctors.csv"], tables["visits.csv"]

# ------------------------------------------------------------------ 2. row counts
for fname, (lo, hi) in EXPECTED_ROWS.items():
    n = len(tables[fname])
    record(lo <= n <= hi, f"{fname}: row count", f"{n} rows (expected {lo}-{hi})")

# ------------------------------------------------------------------ 3. duplicates
for fname, key in [("reps.csv", "rep_id"), ("doctors.csv", "doctor_id"), ("visits.csv", "visit_id")]:
    dup = [k for k, c in Counter(r[key] for r in tables[fname]).items() if c > 1]
    record(not dup, f"{fname}: unique {key}", show(dup))
dup_names = [k for k, c in Counter(r["name"] for r in doctors).items() if c > 1]
record(not dup_names, "doctors.csv: unique doctor names", show(dup_names))
dup_dd = [k for k, c in Counter((r["doctor_id"], r["date"]) for r in visits).items() if c > 1]
record(not dup_dd, "visits.csv: max one visit per doctor per day", show(dup_dd))

# ------------------------------------------------------------------ 4. missing values
for fname, cols in REQUIRED_NON_NULL.items():
    bad = [(i + 2, c) for i, r in enumerate(tables[fname]) for c in cols if r.get(c, "") == ""]
    record(not bad, f"{fname}: no missing required values", show(bad))

# ------------------------------------------------------------------ 5. foreign keys & territory
rep_ids = {r["rep_id"] for r in reps}
doc_by_id = {r["doctor_id"]: r for r in doctors}
rep_terr = {r["rep_id"]: r["territory"] for r in reps}

bad = [v["visit_id"] for v in visits if v["rep_id"] not in rep_ids]
record(not bad, "visits.rep_id -> reps.rep_id", show(bad))
bad = [v["visit_id"] for v in visits if v["doctor_id"] not in doc_by_id]
record(not bad, "visits.doctor_id -> doctors.doctor_id", show(bad))
bad = [d["doctor_id"] for d in doctors if d["territory"] not in set(rep_terr.values())]
record(not bad, "doctors.territory matches a rep territory", show(bad))
record(len(set(rep_terr.values())) == len(reps), "one unique territory per rep")
bad = [v["visit_id"] for v in visits
       if v["doctor_id"] in doc_by_id and doc_by_id[v["doctor_id"]]["territory"] != rep_terr.get(v["rep_id"])]
record(not bad, "visits: rep visits only doctors in own territory", show(bad))
per_terr = Counter(d["territory"] for d in doctors)
bad = [t for t in rep_terr.values() if per_terr.get(t, 0) < 5]
record(not bad, "every rep has multiple doctors (>=5)", str(dict(per_terr)) if not bad else show(bad))
orphan_reps = rep_ids - {v["rep_id"] for v in visits}
record(not orphan_reps, "every rep has visit activity", show(orphan_reps))

# ------------------------------------------------------------------ 6. dates
bad_fmt, out_month, future = [], [], []
for v in visits:
    d = parse_date(v["date"])
    if d is None:
        bad_fmt.append(v["visit_id"])
        continue
    if (d.year, d.month) != MONTH:
        out_month.append(v["visit_id"])
    if d > AS_OF:
        future.append(v["visit_id"])
record(not bad_fmt, "visits.date valid ISO date (YYYY-MM-DD)", show(bad_fmt))
record(not out_month, f"visits.date within {MONTH[0]}-{MONTH[1]:02d}", show(out_month))
record(not future, f"no visit after as-of date {AS_OF}", show(future))
sundays = [v["visit_id"] for v in visits if parse_date(v["date"]) and parse_date(v["date"]).weekday() == 6]
record(not sundays, "no visits on Sundays", show(sundays), warn=True)

# ------------------------------------------------------------------ 7. follow-up logic
bad = []
for v in visits:
    req, st, fd_s = v["follow_up_required"], v["follow_up_status"], v["follow_up_date"]
    vid = v["visit_id"]
    if req not in ("Yes", "No"):
        bad.append((vid, f"follow_up_required={req!r}"))
        continue
    if st not in ("Pending", "Completed", "Not Required"):
        bad.append((vid, f"status={st!r}"))
        continue
    if req == "No":
        if fd_s != "":
            bad.append((vid, "No but follow_up_date set"))
        if st != "Not Required":
            bad.append((vid, f"No but status={st}"))
    else:
        if st == "Not Required":
            bad.append((vid, "Yes but status=Not Required"))
        fd, d = parse_date(fd_s), parse_date(v["date"])
        if fd is None:
            bad.append((vid, f"invalid follow_up_date {fd_s!r}"))
        elif d and fd <= d:
            bad.append((vid, "follow_up_date not after visit date"))
        if st == "Completed" and fd and fd > AS_OF:
            bad.append((vid, "Completed but due after as-of date"))
record(not bad, "follow-up field combinations valid", show(bad))

# completed follow-ups should be evidenced by a later visit to the same doctor
visit_days = defaultdict(list)
for v in visits:
    visit_days[v["doctor_id"]].append(parse_date(v["date"]))
unevidenced = [v["visit_id"] for v in visits if v["follow_up_status"] == "Completed"
               and not any(parse_date(v["date"]) < x <= parse_date(v["follow_up_date"])
                           for x in visit_days[v["doctor_id"]])]
record(not unevidenced, "completed follow-ups have a matching later visit", show(unevidenced), warn=True)

# ------------------------------------------------------------------ 8. numeric values
bad = [(v["visit_id"], v["samples_given"]) for v in visits
       if parse_int(v["samples_given"]) is None or not 0 <= parse_int(v["samples_given"]) <= 50]
record(not bad, "samples_given integer in 0-50", show(bad))
bad = [(d["doctor_id"], d["monthly_prescriptions"]) for d in doctors
       if parse_int(d["monthly_prescriptions"]) is None or not 0 < parse_int(d["monthly_prescriptions"]) <= 1000]
record(not bad, "monthly_prescriptions integer in 1-1000", show(bad))

# ------------------------------------------------------------------ 9. business-scenario coverage
for d in doctors:
    d["_seg"] = segment(parse_int(d["monthly_prescriptions"]) or 0)
seg_counts = Counter(d["_seg"] for d in doctors)
record(all(seg_counts[s] >= 10 for s in "ABC"), "A/B/C segments all well represented", str(dict(sorted(seg_counts.items()))))

actual = Counter(v["doctor_id"] for v in visits)
missed_A = [d["doctor_id"] for d in doctors if d["_seg"] == "A" and actual[d["doctor_id"]] < PLANNED["A"]]
record(len(missed_A) >= 5, "scenario: A doctors with missed planned visits", f"{len(missed_A)} doctors")

status = Counter(v["follow_up_status"] for v in visits)
overdue = [v for v in visits if v["follow_up_status"] == "Pending" and parse_date(v["follow_up_date"]) <= AS_OF]
upcoming = [v for v in visits if v["follow_up_status"] == "Pending" and parse_date(v["follow_up_date"]) > AS_OF]
record(status["Completed"] >= 10, "scenario: completed follow-ups", str(status["Completed"]))
record(len(overdue) >= 10, "scenario: overdue follow-ups (pending, due <= as-of)", str(len(overdue)))
record(len(upcoming) >= 10, "scenario: upcoming follow-ups (pending, due > as-of)", str(len(upcoming)))
fu_share = sum(v["follow_up_required"] == "Yes" for v in visits) / len(visits)
record(0.2 <= fu_share <= 0.6, "scenario: follow-up not required on every visit", f"{fu_share:.0%} require follow-up")

# rep performance spread (plan compliance = sum(min(actual, planned)) / sum(planned))
comp = {}
for r in reps:
    my = [d for d in doctors if d["territory"] == r["territory"]]
    planned = sum(PLANNED[d["_seg"]] for d in my)
    done = sum(min(actual[d["doctor_id"]], PLANNED[d["_seg"]]) for d in my)
    comp[r["rep_id"]] = done / planned
spread = max(comp.values()) - min(comp.values())
record(spread >= 0.2, "scenario: reps performing well vs falling behind",
       ", ".join(f"{k}={v:.0%}" for k, v in comp.items()))
avg_samples = defaultdict(list)
for v in visits:
    avg_samples[v["rep_id"]].append(int(v["samples_given"]))
avg = {k: sum(x) / len(x) for k, x in avg_samples.items()}
record(max(avg.values()) >= 2 * min(avg.values()), "scenario: varied sample usage across reps",
       ", ".join(f"{k}={v:.1f}/visit" for k, v in sorted(avg.items())))
products = Counter(p for v in visits for p in v["products_discussed"].split(";"))
record(len(products) >= 5, "scenario: multiple products discussed", f"{len(products)} products")

# ------------------------------------------------------------------ report
width = max(len(c) for _, c, _ in results)
print("=" * 80)
print(" DATA VALIDATION REPORT - Pharma Field-Force Synthetic Dataset")
print(f" data dir: {DATA_DIR}   as-of: {AS_OF}")
print("=" * 80)
for s, c, d in results:
    print(f"[{s}] {c.ljust(width)}  {d}")
counts = Counter(s for s, _, _ in results)
print("-" * 80)
print(f"PASS: {counts['PASS']}   WARN: {counts['WARN']}   FAIL: {counts['FAIL']}")
overall = "FAIL" if counts["FAIL"] else "PASS"
print(f"OVERALL: {overall}")
sys.exit(1 if overall == "FAIL" else 0)
