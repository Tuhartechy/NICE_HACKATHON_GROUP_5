"""
Sequential, human-readable ID allocation (V0321, T00494, D101, FU0100 ...).

IDs continue from the highest existing value in the same table. Always call
next_id() inside the same transaction that inserts the row, so two writers
cannot allocate the same number (transaction() uses BEGIN IMMEDIATE).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class IdFormat:
    table: str
    column: str
    prefix: str
    width: int

    def format(self, n: int) -> str:
        return f"{self.prefix}{n:0{self.width}d}"

    def parse(self, value: str) -> int | None:
        m = re.fullmatch(rf"{re.escape(self.prefix)}(\d+)", value or "")
        return int(m.group(1)) if m else None


# Formats mirror the seed data (V0001, T00001, D001, P001, INV001, R001).
ID_FORMATS: dict[str, IdFormat] = {
    "rep": IdFormat("reps", "rep_id", "R", 3),
    "doctor": IdFormat("doctors", "doctor_id", "D", 3),
    "product": IdFormat("products", "product_id", "P", 3),
    "inventory": IdFormat("inventory", "inventory_id", "INV", 3),
    "visit": IdFormat("visits", "visit_id", "V", 4),
    "transaction": IdFormat("sample_transactions", "transaction_id", "T", 5),
    "follow_up": IdFormat("follow_ups", "follow_up_id", "FU", 4),
    "plan_run": IdFormat("plan_runs", "run_id", "RUN", 4),
    "plan_item": IdFormat("plan_items", "plan_item_id", "PI", 4),
    "plan_event": IdFormat("plan_item_events", "event_id", "PE", 5),
    "action_event": IdFormat("action_events", "event_id", "AE", 5),
}


def next_id(conn: sqlite3.Connection, kind: str, *, reserved: set[str] | None = None) -> str:
    """Return the next free ID for `kind`, e.g. next_id(conn, 'visit') -> 'V0321'.

    `reserved` lets a caller allocate several IDs in one transaction before inserting them.
    """
    fmt = ID_FORMATS[kind]
    rows = conn.execute(
        f"SELECT {fmt.column} FROM {fmt.table} WHERE {fmt.column} LIKE ?", (fmt.prefix + "%",)
    ).fetchall()
    numbers = [n for n in (fmt.parse(r[0]) for r in rows) if n is not None]
    numbers += [n for n in (fmt.parse(x) for x in (reserved or ())) if n is not None]
    return fmt.format(max(numbers, default=0) + 1)
