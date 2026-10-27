"""Loader and derived-column tests on hand-built fixtures (no network)."""
from decimal import Decimal

import pytest

from src.load import build_db, check_codes, zip_to_parquet
from src.pull import check_rows, count_prime_rows
from tests.helpers import txn, write_zip


@pytest.fixture
def db(tmp_path):
    rows = [
        txn("T1", 100, type_of_contract_pricing_code="J", product_or_service_code="1510"),
        txn("T2", 50, type_of_contract_pricing_code="U", product_or_service_code="AC12"),
        txn("T3", 25, type_of_contract_pricing_code="Y", product_or_service_code="R425"),
        txn("T4", -10, type_of_contract_pricing_code="L", award_type_code="", idv_type_code="B"),
    ]
    z = write_zip(tmp_path / "dod-fy2025.zip", rows, subaward_rows=7)
    zip_to_parquet(z, tmp_path)
    return build_db(str(tmp_path / "*.parquet"), tmp_path / "t.duckdb")


def test_prime_rows_ignore_subawards(tmp_path):
    z = write_zip(tmp_path / "x.zip", [txn("A", 1), txn("B", 2)], subaward_rows=5)
    assert count_prime_rows(z) == 2


def test_check_rows_goes_red_on_mismatch():
    check_rows(10, 10)
    with pytest.raises(ValueError):
        check_rows(10, 11)


def test_derived_columns(db):
    got = dict(db.execute("SELECT txn_key, pricing_family || '/' || work_type FROM fact_txn").fetchall())
    assert got == {"T1": "fixed/product", "T2": "cost/R&D", "T3": "tm/service", "T4": "fixed/product"}


def test_idv_rows_kept_and_typed(db):
    assert db.execute("SELECT award_type FROM fact_txn WHERE txn_key='T4'").fetchone()[0] == "IDV_B"


def test_net_total_includes_deobligations(db):
    assert db.execute("SELECT sum(obligation) FROM fact_txn").fetchone()[0] == Decimal("165.00")
    assert db.execute("SELECT agency, fy FROM fact_txn LIMIT 1").fetchone() == ("dod", 2025)


def test_duplicate_keys_fail(tmp_path):
    write_zip(tmp_path / "nasa-fy2025.zip", [txn("D1", 1)])
    write_zip(tmp_path / "dod-fy2025.zip", [txn("D1", 1)])
    for z in tmp_path.glob("*.zip"):
        zip_to_parquet(z, tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        build_db(str(tmp_path / "*.parquet"), tmp_path / "t.duckdb")


def test_code_map_flags_unknown(db):
    assert check_codes(db) == (set(), set())
    db.execute("UPDATE fact_txn SET pricing_code='Q' WHERE txn_key='T1'")
    assert check_codes(db)[0] == {"Q"}
