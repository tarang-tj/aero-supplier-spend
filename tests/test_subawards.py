"""Boeing subaward analysis on a fixture: date window, dedupe, and name rollup to parents."""
import json

import duckdb

from src.subawards import analyze


def test_window_dedupe_and_rollup(tmp_path):
    db = tmp_path / "s.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""CREATE TABLE dim_supplier AS SELECT * FROM (VALUES
        ('U1', 'ROCKWELL COLLINS, INC.', 'RTX', true), ('U2', 'RAYTHEON COMPANY', 'RTX', true))
        t(recipient_uei, recipient_name, ultimate_parent, reviewed)""")
    con.close()
    rows = [
        {"award_key": "A1", "subaward_number": "1", "action_date": "2022-01-01", "amount": 60, "recipient_name": "ROCKWELL COLLINS INC"},
        {"award_key": "A1", "subaward_number": "1", "action_date": "2022-01-01", "amount": 60, "recipient_name": "ROCKWELL COLLINS INC"},
        {"award_key": "A1", "subaward_number": "2", "action_date": "2023-01-01", "amount": 30, "recipient_name": "RAYTHEON COMPANY"},
        {"award_key": "A2", "subaward_number": "3", "action_date": "2024-01-01", "amount": 10, "recipient_name": "ACME"},
        {"award_key": "A2", "subaward_number": "4", "action_date": "2019-01-01", "amount": 999, "recipient_name": "OLD"},
    ]
    cache = tmp_path / "c.jsonl"
    cache.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "out"
    out.mkdir()
    s = analyze(duckdb.connect(), cache, out, str(db))
    assert s["reports"] == 3 and s["total"] == 100
    assert s["child_top1_share"] == 0.6 and s["parent_top1"] == "RTX" and s["parent_top1_share"] == 0.9
