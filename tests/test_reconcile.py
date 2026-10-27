"""Reconcile comparison logic (the networked part runs in `make reconcile`, not here)."""
from decimal import Decimal

from src.reconcile import compare


def test_exact_match_passes():
    assert compare(Decimal("1783885760.03"), Decimal("1783885760.03")) == (Decimal("0.00"), True)


def test_idv_gap_fails():
    # Probe 2026-10-26: A-D-only aggregate missed $311,650,641.03 of IDV obligations.
    diff, ok = compare(Decimal("1783885760.03"), Decimal("1472235119.00"))
    assert diff == Decimal("311650641.03") and not ok


def test_one_cent_tolerance():
    assert compare(Decimal("10.01"), Decimal("10.00"))[1]
    assert not compare(Decimal("10.02"), Decimal("10.00"))[1]
