"""Boeing as buyer: first-tier subcontracts Boeing reported under its 100 largest DoD prime awards in
scope (85% of its FY2021-25 DoD aerospace obligations), via the per-award /api/v2/subawards/ endpoint.

Usage: python -m src.subawards   -> data/raw/boeing_subawards.jsonl (cache), data/out/boeing_subawards*.csv
Caveats: self-reported by the prime under FFATA; first tier only; reporting threshold $30,000 before
2025-10-01 and $40,000 after (FAC 2025-06); duplicates removed on (award, number, date, amount).
"""
import json
from pathlib import Path

import duckdb

from src.crosswalk import NORMALIZE
from src.pull import post

KEYS = Path("data/api/boeing_top100_award_keys.json")
RTX_EX21 = "https://www.sec.gov/Archives/edgar/data/101829/000010182926000006/exhibit212025-12x3110xk.htm"
# Subcontractor names absent from the prime data but listed in a parent's Exhibit 21.
EXTRA = {"B/E AEROSPACE": ("RTX", RTX_EX21)}
CACHE = Path("data/raw/boeing_subawards.jsonl")
OUT = Path("data/out")


def fetch_award(key):
    rows, page = [], 1
    while True:
        d = post("subawards/", {"award_id": key, "limit": 100, "page": page, "sort": "subaward_number", "order": "desc"})
        rows += [{**r, "award_key": key} for r in d.get("results", [])]
        if not d["page_metadata"]["hasNext"]:
            return rows
        page += 1


def pull():
    done = set()
    if CACHE.exists():
        done = {json.loads(line)["award_key"] for line in CACHE.read_text().splitlines()}
    for key in json.loads(KEYS.read_text()):
        if key in done:
            continue
        rows = fetch_award(key) or [{"award_key": key, "empty": True}]
        with CACHE.open("a") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in rows)


def name_map(con, db="data/spend.duckdb"):
    """Normalized supplier name -> reviewed ultimate parent, from the prime-contract crosswalk.
    Names that map to more than one parent are dropped as ambiguous."""
    con.execute(f"ATTACH '{db}' AS spend (READ_ONLY)")
    con.execute(f"""CREATE OR REPLACE TABLE name_map AS
        SELECT {NORMALIZE.format(col="recipient_name")} AS supplier, any_value(ultimate_parent) AS parent
        FROM spend.dim_supplier WHERE reviewed AND recipient_name IS NOT NULL
        GROUP BY 1 HAVING count(DISTINCT ultimate_parent) = 1""")
    for name, (parent, _) in EXTRA.items():
        con.execute("INSERT INTO name_map SELECT ?, ? WHERE ? NOT IN (SELECT supplier FROM name_map)", [name, parent, name])


def level_summary(con, col):
    df = con.execute(f"""SELECT {col} AS supplier, count(*) AS reports, sum(amount) AS amt,
                                sum(amount) / sum(sum(amount)) OVER () AS share
                         FROM sub GROUP BY 1 ORDER BY amt DESC""").df()
    return df, {"top1": df.supplier.iloc[0], "top1_share": float(df.share.iloc[0]),
                "top5_share": float(df.share.head(5).sum()), "hhi": float(((df.share * 100) ** 2).sum()),
                "suppliers": len(df)}


def analyze(con, cache=CACHE, out=OUT, db="data/spend.duckdb"):
    con.execute(f"CREATE OR REPLACE TABLE sub_raw AS SELECT * FROM read_json_auto('{cache}')")
    name_map(con, db)
    con.execute(f"""CREATE OR REPLACE TABLE sub AS
        WITH d AS (SELECT DISTINCT award_key, subaward_number, CAST(action_date AS DATE) AS action_date,
                          CAST(amount AS DECIMAL(18, 2)) AS amount, {NORMALIZE.format(col="recipient_name")} AS supplier
                   FROM sub_raw WHERE recipient_name IS NOT NULL
                     AND CAST(action_date AS DATE) BETWEEN DATE '2020-10-01' AND DATE '2025-09-30')
        SELECT d.*, coalesce(m.parent, d.supplier) AS parent FROM d LEFT JOIN name_map m USING (supplier)""")
    child, cs = level_summary(con, "supplier")
    parent, ps = level_summary(con, "parent")
    parent.head(25).to_csv(out / "boeing_subawards.csv", index=False)
    s = {"awards": con.execute("SELECT count(DISTINCT award_key) FROM sub").fetchone()[0],
         "reports": con.execute("SELECT count(*) FROM sub").fetchone()[0], "total": float(child.amt.sum()),
         **{f"child_{k}": v for k, v in cs.items()}, **{f"parent_{k}": v for k, v in ps.items()}}
    with (out / "boeing_subawards_summary.csv").open("w") as fh:
        fh.write("metric,value\n" + "".join(f"{k},{v}\n" for k, v in s.items()))
    return s


def main():
    pull()
    print(analyze(duckdb.connect()))


if __name__ == "__main__":
    main()
