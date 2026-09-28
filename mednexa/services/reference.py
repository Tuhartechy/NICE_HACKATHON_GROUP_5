"""
Shared reference data used by the app shell (representatives, database status).

Contains no feature business logic. Feature services (F1-F5) own their own entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from mednexa.core import db
from mednexa.core.errors import DataUnavailableError
from mednexa.repositories import reps as reps_repo


@dataclass(frozen=True)
class DatabaseStatus:
    available: bool
    path: str
    message: str


def database_status() -> DatabaseStatus:
    path = str(db.db_path())
    if not db.database_exists():
        return DatabaseStatus(False, path, "Database not initialised")
    try:
        with db.session() as conn:
            if not db.table_exists(conn, "reps"):
                return DatabaseStatus(False, path, "Database schema missing")
    except Exception:  # corrupted/locked file - shown as unavailable, never as a stack trace
        return DatabaseStatus(False, path, "Database could not be opened")
    return DatabaseStatus(True, path, "Connected")


def list_reps() -> list[dict]:
    """All representatives as dicts {rep_id, name, territory}.

    Raises DataUnavailableError until the database has been seeded.
    """
    if not database_status().available:
        raise DataUnavailableError()
    with db.session() as conn:
        return reps_repo.list_reps(conn)
