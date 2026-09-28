"""Products & inventory - SQL only (Feature 3)."""
from mednexa.core.db import query_df


def list_products(conn):
    return query_df(conn, "SELECT product_id, product_name FROM products ORDER BY product_id")


def inventory(conn):
    return query_df(conn, """SELECT i.inventory_id, i.product_id, p.product_name, i.opening_stock,
        i.current_stock, i.minimum_stock FROM inventory i JOIN products p USING(product_id) ORDER BY i.product_id""")


def stock_of(conn, product_id):
    r = conn.execute("SELECT current_stock FROM inventory WHERE product_id=?", (product_id,)).fetchone()
    return None if r is None else r[0]


def adjust_stock(conn, product_id, delta):
    """delta<0 issues, delta>0 returns. Returns False if it would go negative."""
    cur = conn.execute("UPDATE inventory SET current_stock = current_stock + ? "
                       "WHERE product_id = ? AND current_stock + ? >= 0", (delta, product_id, delta))
    return cur.rowcount == 1
