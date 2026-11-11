"""Drift check logic, offline: the classifier and the report against the committed baseline."""
from datetime import date
from decimal import Decimal

from src import drift, scope


def test_classify_names_the_side_that_moved():
    assert drift.classify(Decimal("10.00"), 5, Decimal("10.00"), 5) == "ok"
    assert drift.classify(Decimal("10.00"), 5, Decimal("10.005"), 5) == "ok"  # within a cent
    assert drift.classify(Decimal("10.00"), 5, Decimal("12.00"), 5) == "aggregate +2.00"
    assert drift.classify(Decimal("10.00"), 5, Decimal("10.00"), 7) == "count +2"


def test_closed_years_waits_for_the_fiscal_year_to_end():
    assert drift.closed_years(date(2026, 9, 30)) == []
    assert drift.closed_years(date(2026, 10, 1)) == [2026]


def test_report_is_quiet_when_live_equals_baseline():
    sums, rows = drift.baseline()

    def same(agency, fy):
        return sums[f"{agency}-fy{fy}"], rows[f"{agency}-fy{fy}"]

    text, changes = drift.report(today=date(2026, 9, 1), fetch=same)
    assert changes == 0 and f"0 of {len(scope.slices())} slices moved" in text


def test_report_flags_a_moved_slice_and_a_new_year():
    sums, rows = drift.baseline()

    def moved(agency, fy):
        key = f"{agency}-fy{fy}"
        if key not in sums:
            return Decimal("1e9"), 1
        return sums[key] + (Decimal(5) if key == "dod-fy2021" else 0), rows[key]

    text, changes = drift.report(today=date(2026, 11, 11), fetch=moved)
    assert changes == 1 + len(scope.AGENCIES)
    assert "| dod-fy2021 |" in text and "aggregate +5.00" in text and "FY2026" in text
