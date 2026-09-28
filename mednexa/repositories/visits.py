"""Visits, visit products and sample transactions - SQL only (Feature 3)."""
from mednexa.core.db import query_df


def history(conn, rep_id=None, doctor_id=None, date_from=None, date_to=None):
    sql = """SELECT v.visit_id, v.visit_date, v.rep_id, v.doctor_id, d.name AS doctor_name, d.specialty, d.area,
      d.monthly_prescriptions, v.outcome, v.notes, v.source, COALESCE(pt.products_discussed,'') AS products,
      s.issued AS samples_issued, s.returned AS samples_returned, f.follow_up_required, f.follow_up_date,
      f.follow_up_status
    FROM visits v JOIN doctors d USING(doctor_id)
    LEFT JOIN v_visit_products_text pt USING(visit_id)
    LEFT JOIN v_visit_samples s USING(visit_id)
    LEFT JOIN v_visit_followup f USING(visit_id) WHERE 1=1"""
    params = []
    for cond, val in (("v.rep_id = ?", rep_id), ("v.doctor_id = ?", doctor_id),
                      ("v.visit_date >= ?", date_from), ("v.visit_date <= ?", date_to)):
        if val:
            sql += f" AND {cond}"
            params.append(str(val))
    return query_df(conn, sql + " ORDER BY v.visit_date DESC, v.visit_id DESC", params)


def visit_products(conn, rep_id=None):
    sql = """SELECT vp.visit_id, vp.product_id, p.product_name, vp.feedback, v.visit_date, v.rep_id, v.doctor_id
             FROM visit_products vp JOIN products p USING(product_id) JOIN visits v USING(visit_id)"""
    return query_df(conn, sql + (" WHERE v.rep_id = ?" if rep_id else ""), (rep_id,) if rep_id else ())


def transactions(conn):
    return query_df(conn, """SELECT t.*, v.rep_id, v.doctor_id, p.product_name FROM sample_transactions t
        JOIN visits v USING(visit_id) JOIN products p USING(product_id)""")


def doctor_holdings(conn, doctor_id):
    rows = conn.execute("""SELECT t.product_id,
        SUM(CASE WHEN t.transaction_type='SAMPLE_ISSUED' THEN t.quantity ELSE -t.quantity END)
        FROM sample_transactions t JOIN visits v USING(visit_id) WHERE v.doctor_id=? GROUP BY t.product_id""",
                        (doctor_id,)).fetchall()
    return {r[0]: r[1] for r in rows}


def insert_visit(conn, row):
    conn.execute("INSERT INTO visits (visit_id,rep_id,doctor_id,visit_date,outcome,notes,source,created_at) "
                 "VALUES (:visit_id,:rep_id,:doctor_id,:visit_date,:outcome,:notes,'APP',:ts)", row)


def insert_visit_product(conn, visit_id, product_id, feedback):
    conn.execute("INSERT INTO visit_products VALUES (?,?,?)", (visit_id, product_id, feedback))


def insert_transaction(conn, row):
    conn.execute("INSERT INTO sample_transactions VALUES (:transaction_id,:visit_id,:product_id,:quantity,"
                 ":transaction_type,:transaction_date)", row)
