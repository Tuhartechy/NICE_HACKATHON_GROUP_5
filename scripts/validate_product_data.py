"""
validate_product_data.py - checks products, visit_products, inventory and sample_transactions
against each other and against the shared reps / doctors / visits datasets.

Usage:  python validate_product_data.py
Standard library only. Exit code 0 = PASS, 1 = at least one FAIL.
"""

import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# MedNexa copy: only this path line differs from the original dataset project.
# Seed CSVs live in <project>/data/seed; MEDNEXA_SEED_DIR overrides it.
DATA = Path(os.environ.get("MEDNEXA_SEED_DIR", Path(__file__).resolve().parent.parent / "data" / "seed"))
REPLENISHMENT_SUPPORTED = False          # no replenishment in the Aug-2026 dataset
CONSISTENCY_TOLERANCE = 0                 # units allowed between stock ledger and transactions
VALID_TXN_TYPES = {"SAMPLE_ISSUED", "SAMPLE_RETURNED"}

SCHEMA = {
    "reps.csv": ["rep_id", "name", "territory"],
    "doctors.csv": ["doctor_id", "name", "specialty", "area", "territory", "monthly_prescriptions"],
    "visits.csv": ["visit_id", "rep_id", "doctor_id", "date", "products_discussed", "samples_given",
                   "follow_up_required", "follow_up_date", "follow_up_status"],
    "products.csv": ["product_id", "product_name"],
    "visit_products.csv": ["visit_id", "product_id"],
    "inventory.csv": ["inventory_id", "product_id", "opening_stock", "current_stock", "minimum_stock"],
    "sample_transactions.csv": ["transaction_id", "visit_id", "product_id", "quantity",
                                "transaction_type", "transaction_date"],
}

results = []


def record(ok, section, check, detail="", warn=False):
    results.append(("PASS" if ok else ("WARN" if warn else "FAIL"), section, check, detail))


def show(items, limit=5):
    items = list(items)
    return "" if not items else f"{len(items)} issue(s), e.g. {items[:limit]}"


def to_int(s):
    try:
        f = float(s)
        return int(f) if f == int(f) else None
    except (TypeError, ValueError):
        return None


def to_date(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def stock_status(cur, mn):
    """same thresholds the app should use for inventory alerts"""
    if cur <= 0.25 * mn:
        return "CRITICAL"
    if cur < mn:
        return "BELOW_MIN"
    if cur <= 1.5 * mn:
        return "NEAR_MIN"
    return "HEALTHY"


# ------------------------------------------------------------------ load
T = {}
for fname, cols in SCHEMA.items():
    sec = fname.replace(".csv", "").upper()
    path = DATA / fname
    if not path.exists():
        record(False, sec, "file exists", str(path))
        continue
    record(True, sec, "file exists")
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        header = rd.fieldnames or []
        rows = [{k: (v or "").strip() for k, v in r.items()} for r in rd]
    missing = [c for c in cols if c not in header]
    record(not missing, sec, "required columns", f"missing {missing}" if missing else "")
    if not missing:
        T[fname] = rows

if len(T) < len(SCHEMA):
    for r in results:
        print(f"[{r[0]}] {r[1]}: {r[2]} {r[3]}")
    print("\nOVERALL: FAIL (missing files or columns)")
    sys.exit(1)

reps, doctors, visits = T["reps.csv"], T["doctors.csv"], T["visits.csv"]
products, vp, inv, txn = (T["products.csv"], T["visit_products.csv"],
                          T["inventory.csv"], T["sample_transactions.csv"])
visit_by_id = {v["visit_id"]: v for v in visits}
product_ids = {p["product_id"] for p in products}
name_to_pid = {p["product_name"]: p["product_id"] for p in products}


def not_null(rows, cols, sec, label="no missing required values"):
    bad = [(i + 2, c) for i, r in enumerate(rows) for c in cols if r.get(c, "") == ""]
    record(not bad, sec, label, show(bad))


def unique(rows, key, sec):
    keys = [tuple(r[k] for k in key) if isinstance(key, tuple) else r[key] for r in rows]
    dup = [k for k, c in Counter(keys).items() if c > 1]
    record(not dup, sec, f"unique {key if isinstance(key, str) else '(' + ', '.join(key) + ')'}", show(dup))


# ------------------------------------------------------------------ PRODUCTS
S = "PRODUCTS"
unique(products, "product_id", S)
unique(products, "product_name", S)
not_null(products, SCHEMA["products.csv"], S)
record(10 <= len(products) <= 15, S, "row count 10-15", f"{len(products)} rows")

# ------------------------------------------------------------------ VISIT_PRODUCTS
S = "VISIT_PRODUCTS"
not_null(vp, SCHEMA["visit_products.csv"], S, "no null foreign keys")
unique(vp, ("visit_id", "product_id"), S)
record(not (b := [r["visit_id"] for r in vp if r["visit_id"] not in visit_by_id]), S,
       "every visit_id exists in visits.csv", show(b))
record(not (b := [r["product_id"] for r in vp if r["product_id"] not in product_ids]), S,
       "every product_id exists in products.csv", show(b))
per_visit = Counter(r["visit_id"] for r in vp)
record(not (b := [k for k, c in per_visit.items() if not 1 <= c <= 3]), S,
       "1-3 products per visit", show(b))
record(not (b := [v for v in visit_by_id if v not in per_visit]), S,
       "every visit has at least one product discussed", show(b), warn=True)
# agreement with the denormalised visits.products_discussed text column
vp_sets = defaultdict(set)
for r in vp:
    vp_sets[r["visit_id"]].add(r["product_id"])
mismatch = [vid for vid, v in visit_by_id.items()
            if {name_to_pid.get(n.strip(), "?" + n.strip()) for n in v["products_discussed"].split(";") if n.strip()}
            != vp_sets.get(vid, set())]
record(not mismatch, S, "matches visits.products_discussed", show(mismatch))

# ------------------------------------------------------------------ INVENTORY
S = "INVENTORY"
not_null(inv, SCHEMA["inventory.csv"], S)
unique(inv, "inventory_id", S)
record(not (b := [r["product_id"] for r in inv if r["product_id"] not in product_ids]), S,
       "every product_id exists in products.csv", show(b))
dup = [k for k, c in Counter(r["product_id"] for r in inv).items() if c > 1]
record(not dup, S, "no duplicate product inventory records", show(dup))
record(not (b := product_ids - {r["product_id"] for r in inv}), S,
       "every product has an inventory record", show(b))
for col in ("opening_stock", "current_stock", "minimum_stock"):
    bad = [(r["inventory_id"], r[col]) for r in inv if to_int(r[col]) is None or to_int(r[col]) < 0]
    record(not bad, S, f"{col} is an integer >= 0", show(bad))
bad = [r["inventory_id"] for r in inv if (to_int(r["opening_stock"]) or 0) <= 0 or (to_int(r["minimum_stock"]) or 0) <= 0]
record(not bad, S, "opening_stock and minimum_stock > 0", show(bad))
if not REPLENISHMENT_SUPPORTED:
    bad = [r["inventory_id"] for r in inv
           if (to_int(r["current_stock"]) or 0) > (to_int(r["opening_stock"]) or 0)]
    record(not bad, S, "current_stock <= opening_stock (no replenishment)", show(bad))

# ------------------------------------------------------------------ SAMPLE_TRANSACTIONS
S = "SAMPLE_TRANSACTIONS"
not_null(txn, SCHEMA["sample_transactions.csv"], S)
unique(txn, "transaction_id", S)
record(not (b := [t["transaction_id"] for t in txn if t["visit_id"] not in visit_by_id]), S,
       "every visit_id exists in visits.csv", show(b))
record(not (b := [t["transaction_id"] for t in txn if t["product_id"] not in product_ids]), S,
       "every product_id exists in products.csv", show(b))
record(not (b := [(t["transaction_id"], t["quantity"]) for t in txn
                  if to_int(t["quantity"]) is None or to_int(t["quantity"]) <= 0]), S,
       "quantity is a positive integer", show(b))
record(not (b := [(t["transaction_id"], t["transaction_type"]) for t in txn
                  if t["transaction_type"] not in VALID_TXN_TYPES]), S,
       f"transaction_type in {sorted(VALID_TXN_TYPES)}", show(b))
record(not (b := [t["transaction_id"] for t in txn if to_date(t["transaction_date"]) is None]), S,
       "transaction_date is a valid ISO date", show(b))
dup_pair = [k for k, c in Counter((t["visit_id"], t["product_id"], t["transaction_type"]) for t in txn).items() if c > 1]
record(not dup_pair, S, "one row per (visit, product, type)", show(dup_pair))

# ------------------------------------------------------------------ CROSS-TABLE
S = "CROSS-TABLE"
bad = [t["transaction_id"] for t in txn if t["visit_id"] in visit_by_id
       and t["transaction_date"] != visit_by_id[t["visit_id"]]["date"]]
record(not bad, S, "transaction_date = related visit date", show(bad))

bad = [t["transaction_id"] for t in txn if t["transaction_type"] == "SAMPLE_ISSUED"
       and t["product_id"] not in vp_sets.get(t["visit_id"], set())]
record(not bad, S, "issued samples only for products discussed in that visit", show(bad))

issued_per_visit = defaultdict(int)
for t in txn:
    if t["transaction_type"] == "SAMPLE_ISSUED":
        issued_per_visit[t["visit_id"]] += to_int(t["quantity"]) or 0
bad = [(vid, int(v["samples_given"]), issued_per_visit[vid]) for vid, v in visit_by_id.items()
       if to_int(v["samples_given"]) != issued_per_visit[vid]]
record(not bad, S, "SAMPLE_ISSUED per visit = visits.samples_given", show(bad))

# a doctor can only return what they previously received (running balance never negative)
balance, bad = defaultdict(int), []
ordered = sorted(txn, key=lambda t: (t["transaction_date"], t["transaction_id"]))
for t in ordered:
    if t["visit_id"] not in visit_by_id:
        continue
    key = (visit_by_id[t["visit_id"]]["doctor_id"], t["product_id"])
    q = to_int(t["quantity"]) or 0
    if t["transaction_type"] == "SAMPLE_RETURNED":
        if q > balance[key]:
            bad.append((t["transaction_id"], key, q, balance[key]))
        balance[key] -= q
    else:
        balance[key] += q
record(not bad, S, "returns never exceed samples previously held by that doctor", show(bad))

# the rep who logged a return is the doctor's territory rep (visits already enforce this)
orphans = (len([r for r in vp if r["visit_id"] not in visit_by_id or r["product_id"] not in product_ids])
           + len([t for t in txn if t["visit_id"] not in visit_by_id or t["product_id"] not in product_ids])
           + len([i for i in inv if i["product_id"] not in product_ids]))
record(orphans == 0, S, "no orphan records in any product table", f"{orphans} orphans" if orphans else "")

issued, returned = defaultdict(int), defaultdict(int)
for t in txn:
    (issued if t["transaction_type"] == "SAMPLE_ISSUED" else returned)[t["product_id"]] += to_int(t["quantity"]) or 0
bad = []
for r in inv:
    exp = to_int(r["opening_stock"]) - issued[r["product_id"]] + returned[r["product_id"]]
    if abs(exp - to_int(r["current_stock"])) > CONSISTENCY_TOLERANCE:
        bad.append((r["product_id"], f"expected {exp}", f"found {r['current_stock']}"))
record(not bad, S, "current_stock = opening - issued + returned", show(bad))

# ------------------------------------------------------------------ DEMO SCENARIOS
S = "SCENARIOS"
status = {r["product_id"]: stock_status(to_int(r["current_stock"]), to_int(r["minimum_stock"])) for r in inv}
sc = Counter(status.values())
for st in ("HEALTHY", "NEAR_MIN", "BELOW_MIN", "CRITICAL"):
    record(sc[st] >= 1, S, f"inventory status {st} present", f"{sc[st]} product(s)")
disc = Counter(r["product_id"] for r in vp)
record(max(disc.values()) >= 4 * min(disc.values()), S, "varied product popularity",
       f"most {max(disc.values())} / least {min(disc.values())} discussions")
record(sum(t["transaction_type"] == "SAMPLE_RETURNED" for t in txn) >= 5, S, "some SAMPLE_RETURNED rows",
       str(sum(t["transaction_type"] == "SAMPLE_RETURNED" for t in txn)))

# ------------------------------------------------------------------ report
print("=" * 88)
print(" PRODUCT / INVENTORY / SAMPLE DATA VALIDATION REPORT")
print("=" * 88)
print(f" rows: products={len(products)}  visit_products={len(vp)}  inventory={len(inv)}  "
      f"sample_transactions={len(txn)}  (visits={len(visits)})")
print("-" * 88)
w = max(len(c) for _, _, c, _ in results)
cur = None
for st, sec, chk, det in results:
    if sec != cur:
        print(f"\n{sec}")
        cur = sec
    print(f"  [{st}] {chk.ljust(w)}  {det}")
print("\nInventory status (current vs minimum):")
for r in inv:
    print(f"  {r['product_id']}  opening={r['opening_stock']:>4}  issued={issued[r['product_id']]:>4}  "
          f"returned={returned[r['product_id']]:>3}  current={r['current_stock']:>4}  "
          f"min={r['minimum_stock']:>4}  -> {status[r['product_id']]}")
c = Counter(s for s, *_ in results)
print("-" * 88)
print(f"PASS: {c['PASS']}   WARN: {c['WARN']}   FAIL: {c['FAIL']}")
overall = "FAIL" if c["FAIL"] else "PASS"
print(f"OVERALL: {overall}")
sys.exit(1 if overall == "FAIL" else 0)
