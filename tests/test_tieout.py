"""Tie-outs on the REAL outputs. Partition tables must equal fact totals to the cent per agency x
period; subset tables must never exceed their parent total."""
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest

OUT = Path("data/out")
pytestmark = pytest.mark.skipif(not Path("data/spend.duckdb").exists(), reason="real database not built")


@pytest.fixture(scope="module")
def facts():
    con = duckdb.connect("data/spend.duckdb", read_only=True)
    rows = con.execute("SELECT agency, CAST(fy AS VARCHAR), sum(obligation) FROM fact_sup GROUP BY 1, 2").fetchall()
    tot = {(a, p): v for a, p, v in rows}
    for a in {a for a, _ in tot}:
        tot[(a, "FY21-25")] = sum(v for (ag, _), v in tot.items() if ag == a)
    return tot


def cents(x):
    return round(Decimal(str(x)), 2)


def test_concentration_totals(facts):
    c = pd.read_csv(OUT / "concentration.csv")
    for r in c.itertuples():
        assert abs(cents(r.total) - cents(facts[(r.agency, r.period)])) <= Decimal("0.05"), r


def test_pricing_mix_partitions(facts):
    m = pd.read_csv(OUT / "pricing_mix.csv").fillna(0)
    for r in m.itertuples():
        parts = r.fixed + r.cost + r.tm + r.other + r.missing
        assert abs(cents(parts) - cents(r.total)) <= Decimal("0.05"), r
        if r.work_type == "all":
            assert abs(cents(r.total) - cents(facts[(r.agency, r.period)])) <= Decimal("0.05"), r
    by = m[m.work_type != "all"].groupby(["agency", "period"]).total.sum()
    for (a, p), v in by.items():
        assert abs(cents(v) - cents(facts[(a, p)])) <= Decimal("0.05"), (a, p)


def test_competition_partitions(facts):
    c = pd.read_csv(OUT / "competition.csv").fillna(0)
    for r in c.itertuples():
        assert abs(cents(r.competed + r.not_competed + r.follow_on + r.missing) - cents(r.total)) <= Decimal("0.05"), r
        assert abs(cents(r.total) - cents(facts[(r.agency, r.period)])) <= Decimal("0.05"), r


def test_subsets_never_exceed_parent(facts):
    prof = pd.read_csv(OUT / "supplier_profile.csv")
    for a, g in prof.groupby("agency"):
        assert g.amt.sum() <= facts[(a, "FY21-25")]
    mix = pd.read_csv(OUT / "pricing_mix.csv").fillna(0)
    fpd = pd.read_csv(OUT / "fixed_price_development.csv")
    for (a, p), g in fpd.groupby(["agency", "period"]):
        rnd = mix[(mix.agency == a) & (mix.period == p) & (mix.work_type == "R&D")].fixed.iloc[0]
        assert g.fixed_rnd.sum() <= rnd + 0.05, (a, p)
