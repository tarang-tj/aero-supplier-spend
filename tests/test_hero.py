"""The rollup reveal draws real records: check what the animation claims on the REAL data."""
import csv
from pathlib import Path

import pytest

from src.hero import layout, records

DB = Path("data/spend.duckdb")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="spend.duckdb not built")


@pytest.fixture(scope="module")
def drawn():
    total, rows, parents = records(str(DB))
    slivers, rest = layout(total, rows, parents)
    return slivers, rest, parents


def published(key):
    rows = csv.DictReader(Path("data/out/memo_numbers.csv").read_text().splitlines())
    return float(next(r["value"] for r in rows if r["key"] == key))


def test_bar_covers_all_dod_dollars(drawn):
    slivers, rest, _ = drawn
    assert abs(sum(s["w"] for s in slivers) + rest - 100) < 1e-6


def test_both_states_tile_the_bar_without_gaps(drawn):
    slivers, rest, _ = drawn
    for key in ("l0", "l1"):
        x = 0.0
        for s in sorted(slivers, key=lambda s: s[key]):
            assert abs(s[key] - x) < 1e-6
            x += s["w"]
        assert abs(x + rest - 100) < 1e-6


def test_as_reported_is_ordered_by_record_size(drawn):
    widths = [s["w"] for s in sorted(drawn[0], key=lambda s: s["l0"])]
    assert widths == sorted(widths, reverse=True)


def test_rolled_up_top_parent_is_one_block_matching_the_published_share(drawn):
    slivers, _, parents = drawn
    top = parents[0][0]
    mine = sorted((s for s in slivers if s["parent"] == top), key=lambda s: s["l1"])
    assert mine[0]["l1"] == 0
    assert abs(mine[-1]["l1"] + mine[-1]["w"] - sum(s["w"] for s in mine)) < 1e-6  # contiguous
    # every record of the top parent is drawn (net-negative ones are netted in), so its block matches
    # what the page publishes; no more slivers than the records the headline counts
    assert 0 < len(mine) <= int(published("dod_top_parent_children"))
    assert abs(sum(s["w"] for s in mine) - 100 * published("dod_ultimate_parent_top1_share")) < 1e-6
