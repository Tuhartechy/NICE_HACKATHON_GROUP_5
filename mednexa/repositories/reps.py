"""Representative reference data - SQL only."""
from __future__ import annotations


def list_reps(conn) -> list[dict]:
    rows = conn.execute("SELECT rep_id, name, territory FROM reps ORDER BY rep_id").fetchall()
    return [dict(r) for r in rows]


def get(conn, rep_id):
    r = conn.execute("SELECT rep_id, name, territory FROM reps WHERE rep_id=?", (rep_id,)).fetchone()
    return dict(r) if r else None
