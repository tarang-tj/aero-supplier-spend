"""Supplier master data: roll each recipient UEI up to an ultimate parent company.

data/crosswalk.csv rows map a key (a parent UEI or a recipient UEI) to an ultimate parent.
Lookup order per transaction: recipient UEI row, then parent UEI row, then the parent name
USAspending reports, then the recipient name. Unreviewed suppliers keep their own name.
Usage: python -m src.crosswalk   (adds dim_supplier and fact_sup to data/spend.duckdb)
"""
import csv
from pathlib import Path

import duckdb

XWALK = Path("data/crosswalk.csv")
# Grouping key for unreviewed names: upper case, no punctuation, no corporate suffix.
NORMALIZE = ("trim(regexp_replace(regexp_replace(upper({col}), '[.,]', '', 'g'), "
             "' (INC|INCORPORATED|LLC|L ?L ?C|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|L ?P|PLC)$', '', 'g'))")
FIELDS = ["key_type", "key", "name_raw", "ultimate_parent", "basis", "ffrdc", "source_url", "reviewed_on"]


def load_crosswalk(con, path=XWALK):
    rows = list(csv.DictReader(path.read_text().splitlines())) if path.exists() else []
    con.execute("CREATE OR REPLACE TABLE crosswalk (key_type VARCHAR, key VARCHAR, ultimate_parent VARCHAR, basis VARCHAR, ffrdc BOOLEAN)")
    for r in rows:
        if r["key_type"] not in ("parent_uei", "recipient_uei"):
            raise ValueError(f"bad key_type {r['key_type']!r} for {r['key']}")
        con.execute("INSERT INTO crosswalk VALUES (?, ?, ?, ?, ?)",
                    [r["key_type"], r["key"], r["ultimate_parent"], r["basis"], r.get("ffrdc") == "yes"])
    dupes = con.execute("""SELECT key_type, key FROM crosswalk GROUP BY 1, 2
                           HAVING count(DISTINCT ultimate_parent) > 1 OR count(DISTINCT ffrdc) > 1""").fetchall()
    if dupes:
        raise ValueError(f"conflicting crosswalk rows: {dupes}")
    return len(rows)


def build_supplier(con):
    """dim_supplier: one ultimate parent per recipient UEI, applied to every year.

    Each (recipient UEI, reported parent UEI) pair is looked up in the crosswalk (recipient row,
    then parent row). A UEI then takes the parent of its most recent reviewed pair; with no
    reviewed pair, the most recent reported parent name, normalized so spelling variants
    ("ACME, INC" vs "ACME INC.") group together. fact_sup adds the result to every transaction.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE dim_supplier AS
        WITH pairs AS (
            SELECT recipient_uei, parent_uei, any_value(recipient_name) AS recipient_name,
                   any_value(parent_name) AS parent_name, max(action_date) AS last_date
            FROM fact_txn GROUP BY 1, 2),
        looked AS (
            SELECT p.*, coalesce(r.ultimate_parent, pu.ultimate_parent) AS mapped,
                   coalesce(r.ffrdc, pu.ffrdc, false) AS ffrdc,
                   {NORMALIZE.format(col="coalesce(p.parent_name, p.recipient_name, 'UNKNOWN')")} AS fallback
            FROM pairs p
            LEFT JOIN (SELECT DISTINCT key, ultimate_parent, ffrdc FROM crosswalk WHERE key_type = 'recipient_uei') r
                   ON r.key = p.recipient_uei
            LEFT JOIN (SELECT DISTINCT key, ultimate_parent, ffrdc FROM crosswalk WHERE key_type = 'parent_uei') pu
                   ON pu.key = p.parent_uei),
        pick AS (
            SELECT recipient_uei, coalesce(mapped, fallback) AS ultimate_parent, mapped IS NOT NULL AS reviewed, ffrdc
            FROM looked WHERE recipient_uei IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY recipient_uei
                                       ORDER BY (mapped IS NOT NULL) DESC, last_date DESC, parent_uei) = 1)
        SELECT l.recipient_uei, l.parent_uei, l.recipient_name, l.parent_name,
               coalesce(k.ultimate_parent, l.mapped, l.fallback) AS ultimate_parent,
               coalesce(k.reviewed, l.mapped IS NOT NULL) AS reviewed,
               coalesce(k.ffrdc, l.ffrdc) AS ffrdc
        FROM looked l LEFT JOIN pick k ON k.recipient_uei = l.recipient_uei
    """)
    con.execute("""
        CREATE OR REPLACE TABLE fact_sup AS
        -- The per-row FFRDC flag is unreliable (JPL rows arrive flagged false), so the
        -- crosswalk's NSF-sourced flag is OR-ed in.
        SELECT f.* REPLACE (f.is_ffrdc OR d.ffrdc AS is_ffrdc), coalesce(f.recipient_uei, f.recipient_name) AS child,
               coalesce(f.recipient_name, f.recipient_uei) AS child_name, d.ultimate_parent, d.reviewed
        FROM fact_txn f
        JOIN dim_supplier d ON d.recipient_uei IS NOT DISTINCT FROM f.recipient_uei
                           AND d.parent_uei IS NOT DISTINCT FROM f.parent_uei
    """)
    before, after = con.execute("SELECT (SELECT sum(obligation) FROM fact_txn), (SELECT sum(obligation) FROM fact_sup)").fetchone()
    if before != after:
        raise ValueError(f"rollup changed total dollars: {before} -> {after}")


def main():
    con = duckdb.connect("data/spend.duckdb")
    n = load_crosswalk(con)
    build_supplier(con)
    print(f"{n} crosswalk rows; reviewed share by agency:")
    print(con.execute("""SELECT agency, round(100 * sum(obligation) FILTER (WHERE reviewed) / sum(obligation), 1)
                         FROM fact_sup GROUP BY 1 ORDER BY 1""").fetchall())


if __name__ == "__main__":
    main()
