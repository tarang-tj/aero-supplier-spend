"""Golden mapping test on the REAL crosswalk: named UEIs from the data must roll up to the
parent company their primary source says owns them (tests/golden_suppliers.csv)."""
import csv
from pathlib import Path

import duckdb
import pytest

from src.crosswalk import build_supplier, load_crosswalk
from src.load import build_db, zip_to_parquet
from tests.helpers import txn, write_zip

DB = Path("data/spend.duckdb")
GOLDEN = list(csv.DictReader(Path("tests/golden_suppliers.csv").read_text().splitlines()))


def mapped(con, uei):
    rows = con.execute("SELECT DISTINCT ultimate_parent FROM dim_supplier WHERE recipient_uei = ?", [uei]).fetchall()
    return {r[0] for r in rows}


@pytest.mark.skipif(not DB.exists(), reason="real database not built")
@pytest.mark.parametrize("row", GOLDEN, ids=[g["recipient_uei"] for g in GOLDEN])
def test_real_crosswalk_golden(row):
    con = duckdb.connect(str(DB), read_only=True)
    assert mapped(con, row["recipient_uei"]) == {row["expected_parent"]}


def test_rollup_keeps_totals_and_merges(tmp_path):
    """Two child UEIs under two parent UEIs collapse to one parent; total dollars unchanged."""
    write_zip(tmp_path / "dod-fy2025.zip", [
        txn("T1", 70, recipient_uei="C1", recipient_parent_uei="PA"),
        txn("T2", 20, recipient_uei="C2", recipient_parent_uei="PB"),
        txn("T3", 10, recipient_uei="C3", recipient_parent_uei="PC", recipient_parent_name="OTHER")])
    zip_to_parquet(tmp_path / "dod-fy2025.zip", tmp_path)
    con = build_db(str(tmp_path / "*.parquet"), tmp_path / "t.duckdb")
    xw = tmp_path / "xw.csv"
    xw.write_text("key_type,key,name_raw,ultimate_parent,basis,ffrdc,source_url,reviewed_on\n"
                  "parent_uei,PA,A,Acme,own_parent,,,\nparent_uei,PB,B,Acme,subsidiary,,,\n")
    load_crosswalk(con, xw)
    build_supplier(con)
    got = dict(con.execute("SELECT ultimate_parent, sum(obligation) FROM fact_sup GROUP BY 1").fetchall())
    assert got == {"Acme": 90, "OTHER": 10}
