"""Visit plans - SQL only (Feature 2)."""
from mednexa.core.db import query_df

ITEMS = """SELECT pi.plan_item_id, pi.rep_id, pi.doctor_id, d.name AS doctor_name, d.specialty, d.area,
  d.monthly_prescriptions, pi.planned_date, pi.original_date, pi.status, pi.is_manual, pi.score,
  pi.score_breakdown, pi.reasons, pi.run_id, pi.visit_id, pi.status_note,
  (SELECT GROUP_CONCAT(follow_up_id) FROM plan_item_follow_ups x WHERE x.plan_item_id = pi.plan_item_id)
     AS follow_up_ids
FROM plan_items pi JOIN doctors d USING(doctor_id) WHERE 1=1"""


def list_items(conn, rep_id=None, date_from=None, date_to=None, statuses=None, doctor_id=None):
    sql, params = ITEMS, []
    for cond, val in (("pi.rep_id=?", rep_id), ("pi.planned_date>=?", date_from),
                      ("pi.planned_date<=?", date_to), ("pi.doctor_id=?", doctor_id)):
        if val:
            sql += f" AND {cond}"
            params.append(str(val))
    if statuses:
        sql += f" AND pi.status IN ({','.join('?' * len(statuses))})"
        params += list(statuses)
    return query_df(conn, sql + " ORDER BY pi.planned_date, d.area, pi.score DESC", params)


def get(conn, plan_item_id):
    df = query_df(conn, ITEMS + " AND pi.plan_item_id=?", (plan_item_id,))
    return None if df.empty else df.iloc[0].to_dict()


def delete_items(conn, ids):
    for i in ids:
        conn.execute("DELETE FROM plan_item_follow_ups WHERE plan_item_id=?", (i,))
        conn.execute("DELETE FROM plan_item_events WHERE plan_item_id=?", (i,))
        conn.execute("DELETE FROM plan_items WHERE plan_item_id=?", (i,))


def insert_run(conn, row):
    conn.execute("INSERT INTO plan_runs VALUES (:run_id,:rep_id,:start_date,:num_days,:as_of,:ts)", row)


def insert_item(conn, row):
    conn.execute("""INSERT INTO plan_items (plan_item_id,rep_id,doctor_id,planned_date,original_date,status,
        is_manual,score,score_breakdown,reasons,run_id,visit_id,status_note,created_at,updated_at)
        VALUES (:plan_item_id,:rep_id,:doctor_id,:planned_date,:planned_date,'PLANNED',:is_manual,:score,
        :score_breakdown,:reasons,:run_id,NULL,NULL,:ts,:ts)""", row)


def link_followups(conn, plan_item_id, follow_up_ids):
    conn.executemany("INSERT OR IGNORE INTO plan_item_follow_ups VALUES (?,?)",
                     [(plan_item_id, f) for f in follow_up_ids])


def set_status(conn, plan_item_id, status, note, ts, visit_id=None):
    conn.execute("UPDATE plan_items SET status=?, status_note=?, updated_at=?, visit_id=COALESCE(?, visit_id) "
                 "WHERE plan_item_id=?", (status, note, ts, visit_id, plan_item_id))


def set_date(conn, plan_item_id, new_date, ts):
    conn.execute("UPDATE plan_items SET planned_date=?, is_manual=1, updated_at=? WHERE plan_item_id=?",
                 (new_date, ts, plan_item_id))


def insert_event(conn, row):
    conn.execute("INSERT INTO plan_item_events VALUES (:event_id,:plan_item_id,:from_status,:to_status,"
                 ":from_date,:to_date,:actor,:note,:at)", row)
