"""Load downloaded zips into Parquet, then build fact_txn in DuckDB.

Usage: python -I -m src.load   (reads data/raw/*.zip, writes data/parquet/, data/spend.duckdb)
CSV text is read as strings and typed in SQL so nothing is coerced silently.
"""
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from src import scope

RAW = Path("data/raw")
PARQ = Path("data/parquet")
DB = Path("data/spend.duckdb")
DERIVE = Path("sql/derive.sql")
# Code lists from the USAspending data dictionary (TypeOfContractPricing, ExtentCompeted).
KNOWN_PRICING = set("ABJKLMRSTUVYZ123")
KNOWN_COMPETED = {"A", "B", "C", "D", "E", "F", "G", "CDO", "NDO"}


def zip_to_parquet(zpath, out_dir=PARQ):
    """Prime transaction CSVs in one zip -> one Parquet file with a slice column."""
    out_dir.mkdir(parents=True, exist_ok=True)
    slice_name = zpath.stem
    opts = pacsv.ConvertOptions(column_types={c: pa.string() for c in scope.COLUMNS})
    tables = []
    with zipfile.ZipFile(zpath) as z:
        for name in sorted(z.namelist()):
            if name.startswith("Contracts_PrimeTransactions"):
                with z.open(name) as fh:
                    tables.append(pacsv.read_csv(fh, convert_options=opts))
    t = pa.concat_tables(tables).select(scope.COLUMNS)
    t = t.append_column("slice", pa.array([slice_name] * t.num_rows, pa.string()))
    out = out_dir / f"{slice_name}.parquet"
    pq.write_table(t, out)
    return out, t.num_rows


def build_db(parquet_glob, db_path=DB):
    con = duckdb.connect(str(db_path))
    con.execute(f"CREATE OR REPLACE VIEW raw_txn AS SELECT * FROM read_parquet('{parquet_glob}')")
    con.execute(DERIVE.read_text())
    dupes = con.execute("SELECT count(*) - count(DISTINCT txn_key) FROM fact_txn").fetchone()[0]
    if dupes:
        raise ValueError(f"{dupes} duplicate transaction keys across slices")
    return con


def check_codes(con):
    """Codes present in the data but missing from the dictionary lists: (pricing, competed)."""
    pricing = {r[0] for r in con.execute("SELECT DISTINCT pricing_code FROM fact_txn WHERE pricing_code IS NOT NULL").fetchall()}
    competed = {r[0] for r in con.execute("SELECT DISTINCT competed_code FROM fact_txn WHERE competed_code IS NOT NULL").fetchall()}
    return pricing - KNOWN_PRICING, competed - KNOWN_COMPETED


def main():
    for z in sorted(RAW.glob("*.zip")):
        out, n = zip_to_parquet(z)
        print(f"{z.name}: {n} rows -> {out}")
    con = build_db(str(PARQ / "*.parquet"))
    print(con.execute("SELECT agency, fy, count(*), sum(obligation) FROM fact_txn GROUP BY 1, 2 ORDER BY 1, 2").fetchall())
    unknown = check_codes(con)
    if any(unknown):
        raise ValueError(f"codes outside the data dictionary: pricing {unknown[0]}, competed {unknown[1]}")


if __name__ == "__main__":
    main()
