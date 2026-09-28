"""Doctor master data - SQL only (Feature 1)."""
from mednexa.core.db import query_df

BASE = """SELECT d.doctor_id, d.name, d.specialty, d.area, d.territory, d.monthly_prescriptions,
  r.rep_id, r.name AS rep_name, lv.last_visit_date, COALESCE(lv.visit_count,0) AS visit_count
FROM doctors d JOIN reps r ON r.territory = d.territory
LEFT JOIN v_last_visit lv ON lv.doctor_id = d.doctor_id"""


def list_doctors(conn, territory=None):
    if territory:
        return query_df(conn, BASE + " WHERE d.territory = ? ORDER BY d.doctor_id", (territory,))
    return query_df(conn, BASE + " ORDER BY d.doctor_id")


def get(conn, doctor_id):
    df = query_df(conn, BASE + " WHERE d.doctor_id = ?", (doctor_id,))
    return None if df.empty else df.iloc[0].to_dict()


def exists(conn, doctor_id):
    return conn.execute("SELECT 1 FROM doctors WHERE doctor_id=?", (doctor_id,)).fetchone() is not None


def insert(conn, row):
    conn.execute("INSERT INTO doctors VALUES (:doctor_id,:name,:specialty,:area,:territory,"
                 ":monthly_prescriptions,:ts,:ts)", row)


def update(conn, row):
    conn.execute("UPDATE doctors SET name=:name, specialty=:specialty, area=:area, territory=:territory, "
                 "monthly_prescriptions=:monthly_prescriptions, updated_at=:ts WHERE doctor_id=:doctor_id", row)


def distinct_values(conn, column):
    assert column in ("specialty", "area", "territory")
    return [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM doctors ORDER BY 1")]


def areas_by_territory(conn):
    return query_df(conn, "SELECT DISTINCT territory, area FROM doctors ORDER BY territory, area")
