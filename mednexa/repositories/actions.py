"""Action state and history - SQL only (Feature 5)."""
from mednexa.core.db import query_df


def all_states(conn):
    return {r["action_key"]: dict(r) for r in conn.execute("SELECT * FROM actions")}


def insert(conn, key, source_type, source_id, ts):
    conn.execute("INSERT INTO actions VALUES (?,?,?,'OPEN',NULL,?,NULL)", (key, source_type, source_id, ts))


def set_status(conn, key, status, ts, snoozed_until=None):
    closed = ts if status in ("DONE", "DISMISSED", "RESOLVED") else None
    conn.execute("UPDATE actions SET status=?, snoozed_until=?, closed_at=? WHERE action_key=?",
                 (status, snoozed_until, closed, key))


def insert_event(conn, row):
    conn.execute("INSERT INTO action_events VALUES (:event_id,:action_key,:from_status,:to_status,:actor,:note,:at)",
                 row)


def events(conn, limit=100):
    return query_df(conn, "SELECT * FROM action_events ORDER BY at DESC, event_id DESC LIMIT ?", (limit,))
