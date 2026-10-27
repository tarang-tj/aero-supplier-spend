"""Stretch: Boeing as buyer. First-tier subcontracts that Boeing reported under its DoD prime
contracts, FY2021-25 (FFATA subaward reporting, shown in USAspending as subawards).

Usage: python -m src.subawards   -> data/raw/boeing-subawards.zip, data/out/boeing_subawards.csv
Caveats: self-reported by the prime; first tier only; reporting threshold $30,000 before
2025-10-01 and $40,000 after (FAC 2025-06); USAspending documents duplicate subaward records.
"""
import io
import time
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.csv as pacsv

from src import scope
from src.pull import fetch_json, post

ZIP = Path("data/raw/boeing-subawards.zip")
OUT = Path("data/out/boeing_subawards.csv")
FILTERS = {"agencies": scope.AGENCIES["dod"]["agencies"], "award_type_codes": ["A", "B", "C", "D"],
           "time_period": [{"start_date": "2020-10-01", "end_date": "2025-09-30"}],
           "recipient_search_text": ["THE BOEING COMPANY"]}


def pull():
    if ZIP.exists():
        return
    job = post("download/transactions/", {"filters": FILTERS, "spending_level": "subawards", "file_format": "csv"})
    while (st := fetch_json(job["status_url"])).get("status") not in ("finished", "failed"):
        time.sleep(10)
    if st["status"] != "finished":
        raise RuntimeError(f"subaward download failed: {st.get('message')}")
    urllib.request.urlretrieve(job["file_url"], ZIP)


def load():
    with zipfile.ZipFile(ZIP) as z:
        name = next(n for n in z.namelist() if "Subaward" in n)
        raw = pacsv.read_csv(io.BytesIO(z.read(name)))
    t = raw.cast(pa.schema([pa.field(c, pa.string()) for c in raw.column_names]))
    con = duckdb.connect()
    con.register("raw", t)
    # Deduplicate identical reports (same prime award, subawardee, number, amount, date).
    con.execute("""CREATE TABLE sub AS SELECT DISTINCT prime_award_unique_key, prime_awardee_name,
                   subawardee_uei, subawardee_name, subawardee_parent_name, subaward_number,
                   TRY_CAST(subaward_amount AS DECIMAL(18, 2)) AS amount, subaward_action_date
                   FROM raw WHERE prime_awardee_name ILIKE '%BOEING%'""")
    return con


def summarize(con):
    con.execute("""CREATE TABLE s AS SELECT coalesce(NULLIF(subawardee_parent_name, ''), subawardee_name) AS supplier,
                   count(*) AS reports, sum(amount) AS amt FROM sub GROUP BY 1""")
    total = con.execute("SELECT sum(amt) FROM s").fetchone()[0]
    df = con.execute("""SELECT supplier, reports, amt, amt / sum(amt) OVER () AS share
                        FROM s ORDER BY amt DESC""").df()
    df.head(25).to_csv(OUT, index=False)
    hhi = float(((df.share * 100) ** 2).sum())
    n, rows = con.execute("SELECT count(DISTINCT supplier), (SELECT count(*) FROM sub) FROM s").fetchone()
    return {"rows": rows, "suppliers": n, "total": total, "top5_share": float(df.share.head(5).sum()), "hhi": hhi}


def main():
    pull()
    print(summarize(load()))


if __name__ == "__main__":
    main()
