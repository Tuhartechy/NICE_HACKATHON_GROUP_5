"""
Seed the MedNexa SQLite database from the read-only CSVs in data/seed.

Gates: both dataset validators must pass; after loading, row counts, the
products/samples views and the stock ledger must match the CSVs exactly.

Usage:  python -m mednexa.db.seed          (creates the database if missing)
        python -m mednexa.db.seed --reset  (rebuilds it from scratch)
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from mednexa import config
from mednexa.core import db

SCHEMA = Path(__file__).with_name("schema.sql")
EXPECTED = {"reps": 5, "doctors": 100, "visits": 320, "products": 12, "visit_products": 552,
            "inventory": 12, "sample_transactions": 493, "follow_ups": 99}


def _read(name: str) -> list[dict]:
    with open(Path(config.SEED_DIR) / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_validators() -> None:
    root = config.PROJECT_ROOT / "scripts"
    for script in ("validate_data.py", "validate_product_data.py"):
        res = subprocess.run([sys.executable, str(root / script)], capture_output=True, text=True,
                             env={**__import__("os").environ, "MEDNEXA_SEED_DIR": str(config.SEED_DIR)})
        if res.returncode != 0:
            raise SystemExit(f"Seed blocked: {script} failed.\n{res.stdout[-1500:]}")


def build(path: Path, *, validate: bool = True) -> dict:
    if validate:
        run_validators()
    ts = db.now_iso()
    conn = db.connect(path, must_exist=False)
    try:
        conn.executescript(SCHEMA.read_text())
        with db.transaction(conn):
            conn.executemany("INSERT INTO reps VALUES (:rep_id,:name,:territory)", _read("reps.csv"))
            conn.executemany(
                "INSERT INTO doctors VALUES (:doctor_id,:name,:specialty,:area,:territory,"
                ":monthly_prescriptions,?,?)".replace("?,?", f"'{ts}','{ts}'"), _read("doctors.csv"))
            conn.executemany("INSERT INTO products VALUES (:product_id,:product_name)", _read("products.csv"))
            conn.executemany("INSERT INTO inventory VALUES (:inventory_id,:product_id,:opening_stock,"
                             ":current_stock,:minimum_stock)", _read("inventory.csv"))
            visits = _read("visits.csv")
            conn.executemany(
                "INSERT INTO visits (visit_id,rep_id,doctor_id,visit_date,outcome,notes,source,created_at) "
                "VALUES (:visit_id,:rep_id,:doctor_id,:date,NULL,NULL,'SEED',:ts)",
                [{**v, "ts": ts} for v in visits])
            conn.executemany("INSERT INTO visit_products (visit_id,product_id,feedback) "
                             "VALUES (:visit_id,:product_id,NULL)", _read("visit_products.csv"))
            conn.executemany("INSERT INTO sample_transactions VALUES (:transaction_id,:visit_id,:product_id,"
                             ":quantity,:transaction_type,:transaction_date)", _read("sample_transactions.csv"))
            # follow-ups: one row per visit with follow_up_required = Yes
            by_doctor: dict[str, list[tuple[str, str]]] = {}
            for v in visits:
                by_doctor.setdefault(v["doctor_id"], []).append((v["date"], v["visit_id"]))
            n = 0
            for v in sorted(visits, key=lambda x: x["visit_id"]):
                if v["follow_up_required"] != "Yes":
                    continue
                n += 1
                row = {"id": f"FU{n:04d}", "visit_id": v["visit_id"], "due": v["follow_up_date"],
                       "status": v["follow_up_status"], "on": None, "method": None, "cv": None}
                if v["follow_up_status"] == "Completed":
                    later = sorted(x for x in by_doctor[v["doctor_id"]] if v["date"] < x[0] <= v["follow_up_date"])
                    if not later:
                        raise SystemExit(f"Seed blocked: completed follow-up on {v['visit_id']} has no later visit")
                    row.update(on=later[0][0], method="VISIT", cv=later[0][1])
                conn.execute("INSERT INTO follow_ups (follow_up_id,visit_id,due_date,notes,status,completed_on,"
                             "completion_method,completed_visit_id,completion_note) "
                             "VALUES (:id,:visit_id,:due,NULL,:status,:on,:method,:cv,NULL)", row)
        checks = verify(conn, visits)
    finally:
        conn.close()
    return checks


def verify(conn, visits: list[dict]) -> dict:
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in EXPECTED}
    bad = {t: (counts[t], e) for t, e in EXPECTED.items() if counts[t] != e}
    if bad:
        raise SystemExit(f"Seed blocked: row counts differ {bad}")
    text = dict(conn.execute("SELECT visit_id, products_discussed FROM v_visit_products_text").fetchall())
    samples = dict(conn.execute("SELECT visit_id, issued FROM v_visit_samples").fetchall())
    for v in visits:
        if text.get(v["visit_id"]) != v["products_discussed"]:
            raise SystemExit(f"Seed blocked: products mismatch for {v['visit_id']}")
        if samples.get(v["visit_id"]) != int(v["samples_given"]):
            raise SystemExit(f"Seed blocked: samples mismatch for {v['visit_id']}")
    ledger = conn.execute("""
        SELECT i.product_id, i.opening_stock, i.current_stock,
          COALESCE(SUM(CASE WHEN t.transaction_type='SAMPLE_ISSUED' THEN t.quantity ELSE -t.quantity END),0) AS net
        FROM inventory i LEFT JOIN sample_transactions t USING(product_id) GROUP BY i.product_id""").fetchall()
    for pid, opening, current, net in ledger:
        if opening - net != current:
            raise SystemExit(f"Seed blocked: stock ledger mismatch for {pid}")
    fu = dict(conn.execute("SELECT status, COUNT(*) FROM follow_ups GROUP BY status").fetchall())
    return {**counts, "follow_ups_pending": fu.get("Pending", 0), "follow_ups_completed": fu.get("Completed", 0)}


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    path = Path(config.DB_PATH)
    if path.exists():
        if "--reset" not in argv:
            print(f"Database already exists: {path}\nUse --reset to rebuild it from the seed CSVs.")
            return 0
        path.unlink()
    tmp = path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    try:
        checks = build(tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)
    print(f"MedNexa database created: {path}")
    for k, v in checks.items():
        print(f"  {k:<22} {v}")
    print("All seed checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
