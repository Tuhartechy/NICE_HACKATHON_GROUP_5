"""Follow-ups - SQL only (Feature 3)."""
from mednexa.core.db import query_df

BASE = """SELECT f.follow_up_id, f.visit_id, f.due_date, f.notes, f.status, f.completed_on, f.completion_method,
  f.completed_visit_id, f.completion_note, v.visit_date, v.rep_id, v.doctor_id, d.name AS doctor_name,
  d.specialty, d.area, d.monthly_prescriptions
FROM follow_ups f JOIN visits v USING(visit_id) JOIN doctors d ON d.doctor_id = v.doctor_id WHERE 1=1"""


def list_followups(conn, rep_id=None, status=None, doctor_id=None):
    sql, params = BASE, []
    for cond, val in (("v.rep_id=?", rep_id), ("f.status=?", status), ("v.doctor_id=?", doctor_id)):
        if val:
            sql += f" AND {cond}"
            params.append(val)
    return query_df(conn, sql + " ORDER BY f.due_date, f.follow_up_id", params)


def get(conn, follow_up_id):
    df = query_df(conn, BASE + " AND f.follow_up_id=?", (follow_up_id,))
    return None if df.empty else df.iloc[0].to_dict()


def complete(conn, follow_up_id, completed_on, method, visit_id, note):
    cur = conn.execute("""UPDATE follow_ups SET status='Completed', completed_on=?, completion_method=?,
        completed_visit_id=?, completion_note=? WHERE follow_up_id=? AND status='Pending'""",
                       (completed_on, method, visit_id, note, follow_up_id))
    return cur.rowcount == 1


def insert(conn, row):
    conn.execute("INSERT INTO follow_ups (follow_up_id,visit_id,due_date,notes,status) "
                 "VALUES (:follow_up_id,:visit_id,:due_date,:notes,'Pending')", row)
