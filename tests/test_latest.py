"""FY2026-so-far line: the page shows exactly latest.json, latest.json recomputes from the bulk
files, the patch touches only its block, and a dead API fails loud."""
import json
from datetime import date

import pytest

from src import latest

has_json = pytest.mark.skipif(not latest.OUT.exists(), reason="latest.json not generated")


@has_json
def test_page_shows_latest_json():
    out = json.loads(latest.OUT.read_text())
    page = latest.PAGE.read_text()
    assert latest.block(out) in page
    assert f"${out['agencies']['dod']['total'] / 1e9:,.1f}B" in page


@pytest.mark.skipif(not (latest.DIR / "raw").exists(), reason="no FY2026 bulk files")
def test_latest_json_recomputes_from_the_bulk_files():
    saved = json.loads(latest.OUT.read_text())
    counts = {f"{ag}-fy{latest.FY}": {k: v[k] for k in ("bulk_rows", "api_count")}
              for ag, v in saved["agencies"].items()}
    assert latest.compute(counts) == saved


@has_json
def test_status_flips_to_complete_after_the_publication_delay():
    out = json.loads(latest.OUT.read_text())
    assert "incomplete until Dec 29, 2026" in latest.render(out, today=date(2026, 12, 28))
    assert "and complete;" in latest.render(out, today=date(2026, 12, 29))


@has_json
def test_patch_replaces_only_its_block(tmp_path):
    out = json.loads(latest.OUT.read_text())
    page = tmp_path / "index.html"
    page.write_text(f"<h1>keep</h1>{latest.START}old line{latest.END}<p>tail</p>")
    latest.patch_page(out, page)
    text = page.read_text()
    assert text.startswith("<h1>keep</h1>") and text.endswith("<p>tail</p>") and "old line" not in text
    page.write_text("<h1>no markers</h1>")
    with pytest.raises(ValueError):
        latest.patch_page(out, page)


def test_a_dead_api_fails_loud(monkeypatch, tmp_path):
    from src import scope
    monkeypatch.setattr(scope, "API", scope.API)  # download() repoints it; restore after the test
    monkeypatch.setenv("AERO_API", "http://127.0.0.1:9/api/v2/")
    monkeypatch.setattr(latest, "DIR", tmp_path)
    monkeypatch.setattr("src.pull.fetch_json.__defaults__", (None, 5, 1))
    with pytest.raises(OSError):
        latest.download()
