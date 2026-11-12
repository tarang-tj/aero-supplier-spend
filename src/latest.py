"""FY2026 as reported so far: the latest fiscal year, outside the frozen FY2021-25 study.

Usage: python -I -m src.latest [--offline] [--out report.md]

The study (every number in memo.md and the hero) stays on FY2021-FY2025. This module pulls the
current bulk download of FY2026 for the same two slices (DoD NAICS 3364, all NASA), loads it with
the study's own loader and crosswalk, computes concentration with the study's own SQL, and writes
data/out/latest.json. DoD publishes contract data with a 90-day delay, so FY2026 is incomplete
until about 2026-12-29: the page says so, and the monthly workflow re-pulls until then.

The bulk file and USAspending's download/count endpoint disagree since 2026-11 (see src/drift.py),
so the bulk file is used, as the study's method does, and both row counts are recorded.

Exit 0: latest.json unchanged. Exit 3: it changed (the workflow rebuilds the page and commits).
Any API error raises.
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from src import crosswalk, load, metrics, pull, scope

FY = 2026
COMPLETE = date(FY, 9, 30) + timedelta(days=90)  # DoD's 90-day publication delay (see src/scope.py)
DIR = Path("data/latest")
OUT = Path("data/out/latest.json")
CONC = Path("data/out/concentration.csv")


def download():
    """Fetch both slices into data/latest/raw; return {slice: {bulk_rows, api_count}}."""
    if os.environ.get("AERO_API"):  # the workflow's failure drill points this at a dead address
        scope.API = os.environ["AERO_API"]
    raw = DIR / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rows = {}
    for agency in scope.AGENCIES:
        r = pull.pull_slice(agency, FY, raw=raw, strict=False)
        rows[r["slice"]] = {"bulk_rows": r["prime_rows"], "api_count": r["api_count"]}
    return rows


def compute(counts):
    """Concentration of FY2026 obligations per agency, by the study's SQL and crosswalk."""
    for z in sorted((DIR / "raw").glob(f"*-fy{FY}.zip")):
        load.zip_to_parquet(z, DIR / "parquet")
    db = DIR / "latest.duckdb"
    db.unlink(missing_ok=True)
    con = load.build_db(str(DIR / "parquet" / "*.parquet"), db)
    crosswalk.load_crosswalk(con)
    crosswalk.build_supplier(con)
    metrics.set_base(con)
    conc = metrics.table(con, "concentration")
    out = {"fy": FY, "complete_after": COMPLETE.isoformat(), "agencies": {}}
    for ag in scope.AGENCIES:
        c = conc[(conc.agency == ag) & (conc.period == str(FY))].set_index("level")
        reviewed = con.execute("""SELECT sum(obligation) FILTER (WHERE reviewed) / sum(obligation)
                                  FROM fact_sup WHERE agency = ? AND fy = ?""", [ag, FY]).fetchone()[0]
        slice_counts = counts.get(f"{ag}-fy{FY}", {})
        out["agencies"][ag] = {
            "total": round(float(c.loc["child", "total"]), 2),
            "child_top5_share": round(float(c.loc["child", "top5_share"]), 4),
            "parent_top5_share": round(float(c.loc["ultimate_parent", "top5_share"]), 4),
            "parent_top1": c.loc["ultimate_parent", "top1"],
            "parent_top1_share": round(float(c.loc["ultimate_parent", "top1_share"]), 4),
            "reviewed_share": round(float(reviewed), 4),
            **slice_counts,
        }
    return out


def fy2025(agency):
    """The same measures for FY2025 alone, from the frozen study, for a like-for-like comparison."""
    import pandas as pd
    c = pd.read_csv(CONC)
    c = c[(c.agency == agency) & (c.period.astype(str) == "2025")].set_index("level")
    return {"total": float(c.loc["child", "total"]),
            "parent_top5_share": float(c.loc["ultimate_parent", "top5_share"]),
            "parent_top1_share": float(c.loc["ultimate_parent", "top1_share"])}


def report(out):
    d, base = out["agencies"]["dod"], fy2025("dod")
    lines = [f"# FY{FY} as reported so far ({'complete' if date.today() >= COMPLETE else 'incomplete until ' + out['complete_after']})", ""]
    for ag, a in out["agencies"].items():
        lines.append(f"- {ag}: ${a['total'] / 1e9:,.2f}B in {a['bulk_rows']:,} bulk rows (download/count says "
                     f"{a['api_count']:,}); top five parents {a['parent_top5_share']:.1%}; top parent "
                     f"{a['parent_top1']} {a['parent_top1_share']:.1%}; crosswalk-reviewed dollars {a['reviewed_share']:.1%}")
    lines.append(f"- DoD FY2025 for comparison: ${base['total'] / 1e9:,.2f}B, top five parents {base['parent_top5_share']:.1%}")
    if d["reviewed_share"] < 0.8:
        lines.append("WARNING: under 80% of DoD FY2026 dollars map through the reviewed crosswalk; extend data/crosswalk.csv.")
    return "\n".join(lines)


START, END = "<!-- latest:start -->", "<!-- latest:end -->"
PAGE = Path("docs/index.html")


def render(out, today=None):
    """One line under the hero. Plain numbers from latest.json, so the monthly job can patch it in."""
    d, base = out["agencies"]["dod"], fy2025("dod")
    status = ("complete" if (today or date.today()) >= date.fromisoformat(out["complete_after"])
              else f"incomplete until {date.fromisoformat(out['complete_after']):%b %-d, %Y}, because DoD reports with a 90-day delay")
    return (f'<p class=latest><b>FY{out["fy"]} so far:</b> DoD ${d["total"] / 1e9:,.1f}B, top five parent companies '
            f'{d["parent_top5_share"]:.1%} (FY2025 alone: {base["parent_top5_share"]:.1%}), {d["parent_top1"]} '
            f'{d["parent_top1_share"]:.1%}. Outside the FY2021 to FY2025 study and {status}; re-pulled monthly from the '
            f'bulk download ({d["bulk_rows"]:,} rows; USAspending\'s own count says {d["api_count"]:,}).</p>')


def block(out):
    return f"{START}{render(out)}{END}"


def patch_page(out, page=PAGE):
    text = page.read_text()
    if START not in text or END not in text:
        raise ValueError(f"{page} has no latest markers")
    i, j = text.index(START), text.index(END) + len(END)
    page.write_text(text[:i] + block(out) + text[j:])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="recompute from data/latest/raw, no download")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    before = OUT.read_text() if OUT.exists() else ""
    prev = json.loads(before) if before else {}
    counts = ({f"{ag}-fy{FY}": {k: v[k] for k in ("bulk_rows", "api_count")} for ag, v in prev.get("agencies", {}).items()}
              if a.offline else download())
    out = compute(counts)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    patch_page(out)
    text = report(out)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 3 if OUT.read_text() != before else 0


if __name__ == "__main__":
    sys.exit(main())
