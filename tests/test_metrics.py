"""Metric fixtures with hand-computed answers.

Fixture (agency dod, FY2025), five transactions:
  child U1 (parent P_A) $50 fixed product, child U2 (parent P_A) $30 cost R&D,
  child U3 (parent P_B) $15 tm service,  child U4 (parent P_C) $5 fixed R&D (FFRDC), not competed.
Child level shares 50/30/15/5  -> HHI 2500+900+225+25 = 3650, CR4 100%, top1 50%.
Parent level (P_A = U1+U2) 80/15/5 -> HHI 6400+225+25 = 6650, top1 80%.
"""
from decimal import Decimal

import pytest

from src.crosswalk import build_supplier, load_crosswalk
from src.load import build_db, zip_to_parquet
from src.metrics import run
from tests.helpers import txn, write_zip


@pytest.fixture
def frames(tmp_path):
    rows = [
        txn("T1", 50, recipient_uei="U1", recipient_parent_uei="P_A", recipient_parent_name="ALPHA"),
        txn("T2", 30, recipient_uei="U2", recipient_parent_uei="P_A", recipient_parent_name="ALPHA",
            type_of_contract_pricing_code="U", product_or_service_code="AC11"),
        txn("T3", 15, recipient_uei="U3", recipient_parent_uei="P_B", recipient_parent_name="BRAVO",
            type_of_contract_pricing_code="Y", product_or_service_code="R425"),
        txn("T4", 5, recipient_uei="U4", recipient_parent_uei="P_C", recipient_parent_name="CHARLIE",
            product_or_service_code="AC12", extent_competed_code="C",
            federally_funded_research_and_development_corp="t"),
    ]
    write_zip(tmp_path / "dod-fy2025.zip", rows)
    zip_to_parquet(tmp_path / "dod-fy2025.zip", tmp_path)
    con = build_db(str(tmp_path / "*.parquet"), tmp_path / "t.duckdb")
    load_crosswalk(con, tmp_path / "none.csv")
    build_supplier(con)
    return run(con, tmp_path / "out")


def conc(frames, level, variant="all"):
    _, sens = frames
    r = sens[(sens.variant == variant) & (sens.level == level) & (sens.period == "2025")]
    return r.iloc[0]


def test_child_concentration(frames):
    r = conc(frames, "child")
    assert round(r.hhi) == 3650 and r.top1_share == pytest.approx(0.5) and r.cr4 == pytest.approx(1.0)


def test_parent_concentration(frames):
    r = conc(frames, "ultimate_parent")
    assert round(r.hhi) == 6650 and r.top1 == "ALPHA" and r.top1_share == pytest.approx(0.8)


def test_ffrdc_excluded_variant(frames):
    r = conc(frames, "ultimate_parent", "excl_ffrdc")
    assert r.total == Decimal("95.00")


def test_pricing_mix_partitions_total(frames):
    mix = frames[0]["pricing_mix"]
    a = mix[(mix.period == "2025") & (mix.work_type == "all")].iloc[0]
    assert (a.fixed, a.cost, a.tm, a.ffp_only, a.cost_plus_only) == (55, 30, 15, 55, 30)
    rnd = mix[(mix.period == "2025") & (mix.work_type == "R&D")].iloc[0]
    assert (rnd.total, rnd.fixed, rnd.cost) == (35, 5, 30)


def test_competition(frames):
    c = frames[0]["competition"]
    r = c[c.period == "2025"].iloc[0]
    assert (r.total, r.competed, r.not_competed) == (100, 95, 5)


def test_fixed_price_development(frames):
    f = frames[0]["fixed_price_development"]
    r = f[f.period == "2025"].iloc[0]
    assert r.ultimate_parent == "CHARLIE" and r.fixed_rnd == 5
