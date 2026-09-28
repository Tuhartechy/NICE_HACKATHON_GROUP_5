"""Feature 3 - inventory status and sample movement."""
from __future__ import annotations

import pandas as pd

from mednexa.core import db
from mednexa.repositories import products as prod_repo
from mednexa.repositories import visits as visits_repo
from mednexa.services import rules


def products() -> pd.DataFrame:
    with db.session() as conn:
        return prod_repo.list_products(conn)


def stock() -> pd.DataFrame:
    with db.session() as conn:
        inv = prod_repo.inventory(conn)
        tx = visits_repo.transactions(conn)
    issued = tx[tx.transaction_type == "SAMPLE_ISSUED"].groupby("product_id")["quantity"].sum()
    returned = tx[tx.transaction_type == "SAMPLE_RETURNED"].groupby("product_id")["quantity"].sum()
    inv["issued"] = inv["product_id"].map(issued).fillna(0).astype(int)
    inv["returned"] = inv["product_id"].map(returned).fillna(0).astype(int)
    inv["status"] = [rules.stock_status(c, m) for c, m in zip(inv.current_stock, inv.minimum_stock)]
    inv["status_label"] = [rules.stock_label(c, m) for c, m in zip(inv.current_stock, inv.minimum_stock)]
    inv["ledger_ok"] = inv.opening_stock - inv.issued + inv.returned == inv.current_stock
    return inv


def transactions() -> pd.DataFrame:
    with db.session() as conn:
        return visits_repo.transactions(conn)
