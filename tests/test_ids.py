import pytest

from mednexa.core import db
from mednexa.core.ids import ID_FORMATS, next_id


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "ids.db", must_exist=False)
    c.execute("CREATE TABLE visits (visit_id TEXT PRIMARY KEY)")
    c.execute("CREATE TABLE doctors (doctor_id TEXT PRIMARY KEY)")
    yield c
    c.close()


def test_first_id_when_empty(conn):
    assert next_id(conn, "visit") == "V0001"


def test_continues_from_seed_maximum(conn):
    conn.executemany("INSERT INTO visits VALUES (?)", [("V0001",), ("V0320",), ("V0007",)])
    assert next_id(conn, "visit") == "V0321"


def test_ignores_foreign_formats_and_respects_width(conn):
    conn.executemany("INSERT INTO doctors VALUES (?)", [("D100",), ("DX99",)])
    assert next_id(conn, "doctor") == "D101"


def test_reserved_ids_within_one_transaction(conn):
    conn.execute("INSERT INTO visits VALUES ('V0320')")
    first = next_id(conn, "visit")
    assert next_id(conn, "visit", reserved={first}) == "V0322"


def test_formats_match_seed_conventions():
    assert ID_FORMATS["transaction"].format(494) == "T00494"
    assert ID_FORMATS["follow_up"].format(100) == "FU0100"
    assert ID_FORMATS["inventory"].format(1) == "INV001"
