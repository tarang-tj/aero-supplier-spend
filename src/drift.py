"""Monthly drift check: has USAspending moved since the pull this analysis is built on?

Usage: python -m src.drift [--out report.md]
Compares, per agency x fiscal year, the committed baseline (data/reconcile.csv sums and
data/manifest.csv row counts, both from the bulk download) with USAspending's live search side
(spending_by_category aggregate and download/count). Also reports a newly closed fiscal year.

It never edits data or the page. It prints a markdown report and exits 0 when nothing moved,
3 when something did (the workflow then opens or updates one issue), and raises on API errors
so a broken check is red, not silent.

Known since 2026-11-11: for DoD FY2021 the live aggregate is $2.58B above a fresh bulk download
that is identical to the baseline, so "index drift" here does not by itself mean the data changed.
"""
import argparse
import csv
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from src import scope
from src.pull import post

TOL = Decimal("0.01")
BN = Decimal("1e9")


def baseline():
    sums = {r["slice"]: Decimal(r["local"]) for r in csv.DictReader(Path("data/reconcile.csv").read_text().splitlines())}
    rows = {r["slice"]: int(r["prime_rows"]) for r in csv.DictReader(Path("data/manifest.csv").read_text().splitlines())
            if r["status"] == "ok"}
    return sums, rows


def live(agency, fy):
    f = scope.filters(agency, fy)
    d = post("search/spending_by_category/awarding_agency/",
             {"category": "awarding_agency", "limit": 100, "page": 1, "filters": f})
    total = sum(Decimal(str(r["amount"])) for r in d["results"])
    count = int(post("download/count/", {"filters": f})["calculated_transaction_count"])
    return total, count


def closed_years(today):
    """Fiscal years after the baseline that have ended (FY N ends Sep 30 of year N)."""
    last = max(scope.FYS)
    return [fy for fy in range(last + 1, today.year + 1) if date(fy, 9, 30) < today]


def classify(base_sum, base_rows, live_sum, live_rows):
    """One slice: 'ok', or a short reason naming which side moved."""
    moved = []
    if abs(live_sum - base_sum) > TOL:
        moved.append(f"aggregate {live_sum - base_sum:+,.2f}")
    if live_rows != base_rows:
        moved.append(f"count {live_rows - base_rows:+,}")
    return "ok" if not moved else "; ".join(moved)


def report(today=None, fetch=live):
    today = today or date.today()
    sums, rows = baseline()
    lines, moved = [], 0
    for agency, fy in scope.slices():
        key = f"{agency}-fy{fy}"
        s, c = fetch(agency, fy)
        verdict = classify(sums[key], rows[key], s, c)
        moved += verdict != "ok"
        lines.append(f"| {key} | ${sums[key] / BN:,.3f}B | ${s / BN:,.3f}B | {verdict} |")
    new = []
    for fy in closed_years(today):
        for agency in scope.AGENCIES:
            s, c = fetch(agency, fy)
            new.append(f"- {agency} FY{fy}: ${s / BN:,.2f}B, {c:,} transactions (not in the analysis yet)")
    head = [f"# USAspending drift check, {today.isoformat()}", "",
            f"{moved} of {len(lines)} slices moved since the baseline pull.", "",
            "| slice | baseline (bulk) | live aggregate | verdict |", "|---|---|---|---|"]
    tail = ["", "## Newly closed fiscal years", *(new or ["- none"]), "",
            "A moved aggregate or count is USAspending's search side. Before republishing, re-pull the slice",
            "and diff it by transaction key: on 2026-11-11 the bulk file was unchanged while the aggregate rose."]
    return "\n".join(head + lines + tail), moved + len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    text, changes = report()
    print(text)
    if a.out:
        a.out.write_text(text + "\n")
    return 3 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
