import sqlite3

import pytest

from mednexa.core import db
from mednexa.core.errors import DataUnavailableError


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db", must_exist=False)
    c.execute("CREATE TABLE parent (id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE child (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES parent(id))")
    yield c
    c.close()


def test_missing_database_raises_friendly_error(tmp_path):
    with pytest.raises(DataUnavailableError):
        db.connect(tmp_path / "absent.db")


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO child VALUES ('c1', 'nope')")


def test_transaction_commits(conn):
    with db.transaction(conn):
        conn.execute("INSERT INTO parent VALUES ('p1')")
    assert conn.execute("SELECT COUNT(*) FROM parent").fetchone()[0] == 1


def test_transaction_rolls_back_everything(conn):
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction(conn):
            conn.execute("INSERT INTO parent VALUES ('p2')")
            conn.execute("INSERT INTO child VALUES ('c2', 'missing')")   # fails -> whole block undone
    assert conn.execute("SELECT COUNT(*) FROM parent WHERE id='p2'").fetchone()[0] == 0


def test_table_exists_and_rows(conn):
    assert db.table_exists(conn, "parent") and not db.table_exists(conn, "nope")
    conn.execute("INSERT INTO parent VALUES ('p9')")
    assert db.rows_to_dicts(conn.execute("SELECT * FROM parent").fetchall()) == [{"id": "p9"}]
