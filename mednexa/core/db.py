"""
SQLite access for MedNexa.

- One database file (config.DB_PATH) is the authoritative mutable store.
- Foreign keys are enforced on every connection.
- `transaction()` gives all-or-nothing writes (used by e.g. visit logging).
Only repositories import this module; pages never do.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from mednexa import config
from mednexa.core.errors import DataUnavailableError


def db_path() -> Path:
    return Path(config.DB_PATH)


def database_exists(path: Path | None = None) -> bool:
    p = Path(path) if path else db_path()
    return p.exists() and p.stat().st_size > 0


def connect(path: Path | str | None = None, *, must_exist: bool = True) -> sqlite3.Connection:
    """Open a connection with MedNexa defaults.

    isolation_level=None puts sqlite3 in autocommit mode so that transaction()
    controls BEGIN/COMMIT/ROLLBACK explicitly.
    """
    target = str(path) if path is not None else str(db_path())
    if must_exist and target != ":memory:" and not database_exists(Path(target)):
        raise DataUnavailableError()
    conn = sqlite3.connect(target, isolation_level=None, detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block atomically: commit on success, roll back on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


@contextmanager
def session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection for the duration of a block and always close it."""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)
    ).fetchone()
    return row is not None


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def query_df(conn: sqlite3.Connection, sql: str, params=()) -> "pd.DataFrame":
    import pandas as pd
    return pd.read_sql_query(sql, conn, params=params)


def now_iso() -> str:
    """Audit timestamp (technical metadata only - never used for business logic)."""
    from datetime import datetime
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")
