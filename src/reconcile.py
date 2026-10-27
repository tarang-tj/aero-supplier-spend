"""Reconcile each agency x FY slice against USAspending's own aggregate. The one networked check.

Usage: python -m src.reconcile [--award-types A,B,C,D]   (the override exists to prove the gate goes red)
Writes data/reconcile.csv and exits 1 if any slice is off by more than one cent.
"""
import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

from src import scope
from src.pull import post

TOL = Decimal("0.01")
OUT = Path("data/reconcile.csv")


def api_total(filters):
    """Sum of the awarding-agency aggregate for a filter (one agency row per slice)."""
    d = post("search/spending_by_category/awarding_agency/",
             {"category": "awarding_agency", "limit": 100, "page": 1, "filters": filters})
    return sum(Decimal(str(r["amount"])) for r in d["results"])


def compare(local, api):
    """Return (diff, ok) for one slice."""
    diff = local - api
    return diff, abs(diff) <= TOL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award-types", help="override award types (gate red-test only)")
    a = ap.parse_args()
    con = duckdb.connect("data/spend.duckdb", read_only=True)
    rows, bad = [], 0
    for agency, fy in scope.slices():
        f = scope.filters(agency, fy)
        if a.award_types:
            f["award_type_codes"] = a.award_types.split(",")
        local = con.execute("SELECT coalesce(sum(obligation), 0) FROM fact_txn WHERE agency = ? AND fy = ?",
                            [agency, fy]).fetchone()[0]
        api = api_total(f)
        diff, ok = compare(Decimal(local), api)
        bad += not ok
        rows.append({"slice": f"{agency}-fy{fy}", "local": local, "api": api, "diff": diff, "ok": ok})
        print(f"{agency}-fy{fy}: local {local:,.2f} api {api:,.2f} diff {diff:,.2f} {'OK' if ok else 'FAIL'}")
    if not a.award_types:
        with OUT.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
