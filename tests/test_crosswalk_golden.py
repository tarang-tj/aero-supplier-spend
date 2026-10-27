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


def _build(tmp_path, rows, xw_rows):
    write_zip(tmp_path / "dod-fy2025.zip", rows)
    zip_to_parquet(tmp_path / "dod-fy2025.zip", tmp_path)
    con = build_db(str(tmp_path / "*.parquet"), tmp_path / "t.duckdb")
    xw = tmp_path / "xw.csv"
    xw.write_text("key_type,key,name_raw,ultimate_parent,basis,ffrdc,source_url,reviewed_on\n" + "".join(xw_rows))
    load_crosswalk(con, xw)
    build_supplier(con)
    return con


def test_one_parent_per_uei_when_reported_parent_changes(tmp_path):
    """C1 reports parent PA (reviewed) in 2023 and PZ (unreviewed) in 2025: all of C1 goes to Acme."""
    con = _build(tmp_path, [
        txn("T1", 60, recipient_uei="C1", recipient_parent_uei="PA", action_date="2023-01-10"),
        txn("T2", 40, recipient_uei="C1", recipient_parent_uei="PZ", recipient_parent_name="ZED HOLDINGS",
            action_date="2025-01-10")], ["parent_uei,PA,A,Acme,own_parent,,,\n"])
    assert dict(con.execute("SELECT ultimate_parent, sum(obligation) FROM fact_sup GROUP BY 1").fetchall()) == {"Acme": 100}


def test_recipient_row_beats_parent_row_and_sets_ffrdc(tmp_path):
    con = _build(tmp_path, [txn("T1", 10, recipient_uei="C1", recipient_parent_uei="PA")],
                 ["parent_uei,PA,A,Acme,own_parent,,,\n", "recipient_uei,C1,C,Lab (FFRDC),acquisition,yes,,\n"])
    assert con.execute("SELECT ultimate_parent, is_ffrdc FROM fact_sup").fetchone() == ("Lab (FFRDC)", True)


def test_conflicting_rows_rejected(tmp_path):
    with pytest.raises(ValueError, match="conflicting"):
        _build(tmp_path, [txn("T1", 10)], ["parent_uei,P1,A,Acme,own_parent,,,\n", "parent_uei,P1,A,Other,own_parent,,,\n"])


def test_unreviewed_spelling_variants_group(tmp_path):
    con = _build(tmp_path, [
        txn("T1", 10, recipient_uei="C1", recipient_parent_uei="Q1", recipient_parent_name="AEROVIRONMENT, INC"),
        txn("T2", 5, recipient_uei="C2", recipient_parent_uei="Q2", recipient_parent_name="AEROVIRONMENT, INC.")], [])
    assert con.execute("SELECT count(DISTINCT ultimate_parent) FROM fact_sup").fetchone()[0] == 1


@pytest.mark.skipif(not DB.exists(), reason="real database not built")
def test_real_reviewed_ueis_have_one_parent():
    con = duckdb.connect(str(DB), read_only=True)
    split = con.execute("""SELECT recipient_uei FROM dim_supplier WHERE recipient_uei IS NOT NULL
                           GROUP BY 1 HAVING count(DISTINCT ultimate_parent) > 1""").fetchall()
    assert split == []
