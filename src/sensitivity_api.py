"""Boundary check for the DoD scope (NAICS 3364) using USAspending aggregates, child level.

Compares top-5 recipient share and total under two aerospace definitions per FY:
  naics: NAICS starting 3364 (the pulled scope)
  psc:   Product/Service Codes in FSC groups 14 (missiles), 15 (aircraft), 16 (aircraft
         components), 18 (space vehicles)
Usage: python -m src.sensitivity_api   -> data/api/*.json, data/out/scope_sensitivity.csv
"""
import csv
import json
from decimal import Decimal
from pathlib import Path

from src import scope
from src.pull import post

API_DIR = Path("data/api")
OUT = Path("data/out/scope_sensitivity.csv")
DEFS = {"naics": {"naics_codes": {"require": ["3364"]}},
        "psc": {"psc_codes": {"require": [["Product", "14"], ["Product", "15"], ["Product", "16"], ["Product", "18"]]}}}


def top5(filters):
    """Top five recipient amounts; the category endpoint returns recipients sorted by amount."""
    d = post("search/spending_by_category/recipient/",
             {"category": "recipient", "limit": 5, "page": 1, "filters": filters})
    return [Decimal(str(r["amount"])) for r in d["results"]]


def main():
    API_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for fy in scope.FYS:
        for name, extra in DEFS.items():
            f = {"agencies": scope.AGENCIES["dod"]["agencies"], "award_type_codes": scope.AWARD_TYPES,
                 "time_period": scope.fy_period(fy), **extra}
            top = top5(f)
            total = post("search/spending_by_category/awarding_agency/",
                         {"category": "awarding_agency", "limit": 10, "page": 1, "filters": f})
            total = sum(Decimal(str(r["amount"])) for r in total["results"])
            rows.append({"fy": fy, "definition": name, "total": total, "top5": sum(top),
                         "top5_share": round(sum(top) / total, 4)})
            (API_DIR / f"dod-{name}-fy{fy}.json").write_text(json.dumps({"filters": f, "row": rows[-1]}, default=str, indent=1))
            print(rows[-1])
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
