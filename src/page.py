"""Static one-page site: docs/index.html. Every number comes from data/out/memo_numbers.csv.

Usage: python -m src.page
"""
import csv
import html
from pathlib import Path

import pandas as pd

OUT = Path("docs/index.html")
REPO = "https://github.com/tarang-tj/aero-supplier-spend"
CSS = """
:root { --bg:#fcfcfb; --ink:#0b0b0b; --muted:#52514e; --rule:#e6e5e0; --accent:#2a78d6; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 Arial, Helvetica, sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 1.9rem; line-height:1.2; margin: 0 0 8px; }
h2 { font-size: 1.25rem; margin: 40px 0 8px; }
.lede { color: var(--muted); margin: 0 0 20px; }
.stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:12px; margin: 20px 0; }
.stat { border-top: 3px solid var(--accent); padding: 8px 0; }
.stat b { display:block; font-size: 1.6rem; }
.stat span { color: var(--muted); font-size: .9rem; }
img { width:100%; height:auto; border:1px solid var(--rule); background:#fcfcfb; }
table { width:100%; border-collapse: collapse; font-size:.9rem; margin: 12px 0; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--rule); }
td.n, th.n { text-align:right; font-variant-numeric: tabular-nums; }
.wrap { overflow-x:auto; }
a { color: var(--accent); }
.links a { margin-right: 16px; display:inline-block; }
footer { color: var(--muted); font-size:.85rem; margin-top: 48px; }
"""


def numbers():
    rows = csv.DictReader(Path("data/out/memo_numbers.csv").read_text().splitlines())
    return {r["key"]: html.escape(r["printed"]) for r in rows}


def supplier_table(agency):
    p = pd.read_csv("data/out/supplier_profile.csv")
    p = p[p.agency == agency].head(8)
    body = "".join(
        f"<tr><td>{html.escape(r.ultimate_parent)}</td><td class=n>${r.amt / 1e9:,.1f}B</td>"
        f"<td class=n>{r.share:.0%}</td><td class=n>{r.fixed_share:.0%}</td>"
        f"<td class=n>{r.not_competed_share:.0%}</td><td class=n>{r.child_records}</td></tr>"
        for r in p.itertuples())
    return ("<div class=wrap><table><thead><tr><th>Parent company</th><th class=n>FY21-25</th><th class=n>Share</th>"
            "<th class=n>Fixed-price</th><th class=n>Not competed</th><th class=n>Records</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def build():
    n = numbers()
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aerospace supplier spend</title><style>{CSS}</style></head><body><main>
<h1>Who supplies U.S. military and NASA aerospace?</h1>
<p class=lede>Supplier concentration, contract type and competition on {n['rows']} real federal contract
transactions, FY2021 to FY2025, from USAspending.gov. By Tarang Jammalamadaka.</p>
<p class=links><a href="memo.pdf">One-page memo (PDF)</a><a href="aero-supplier-spend.xlsx">Excel spend cube</a>
<a href="{REPO}">Code and method</a></p>
<div class=stats>
<div class=stat><b>{n['total']}</b><span>obligations analyzed, reconciled to USAspending to the cent</span></div>
<div class=stat><b>{n['dod_ultimate_parent_top1_share']}</b><span>Lockheed Martin's share of DoD aerospace, once its {n['dod_top_parent_children']} records are combined</span></div>
<div class=stat><b>{n['dod_rnd_fixed_share']}</b><span>of DoD aerospace R&amp;D on fixed-price contracts, vs {n['dod_product_fixed_share']} of products</span></div>
<div class=stat><b>{n['dod_not_competed_share']}</b><span>of DoD aerospace dollars not competed</span></div>
</div>

<h2>1. Supplier records hide half the concentration</h2>
<p>As reported, DoD's largest aerospace supplier record holds {n['dod_child_top1_share']} of obligations and the top five
hold {n['dod_child_top5_share']} (HHI {n['dod_child_hhi']}). Rolled up to parent companies, Lockheed Martin holds
{n['dod_ultimate_parent_top1_share']}, the top five hold {n['dod_ultimate_parent_top5_share']}, and HHI is
{n['dod_ultimate_parent_hhi']}. For a sense of scale only, the 2023 Merger Guidelines treat a market above 1,800 as highly
concentrated; this is one buyer's spend, not a market. NASA's
supplier base is far flatter: top five {n['nasa_ultimate_parent_top5_share']}, HHI {n['nasa_ultimate_parent_hhi']}.</p>
<img src="charts/rollup-effect.svg" alt="Top five supplier share as reported vs rolled up: DoD {n['dod_child_top5_share']} to {n['dod_ultimate_parent_top5_share']}, NASA {n['nasa_child_top5_share']} to {n['nasa_ultimate_parent_top5_share']}">
<img src="charts/hhi-trend.svg" alt="HHI by fiscal year at record and parent level for DoD and NASA">
<h3>DoD aerospace: top parent companies</h3>{supplier_table('dod')}
<h3>NASA: top parent companies</h3>{supplier_table('nasa')}

<h2>2. Contract type follows the kind of work</h2>
<p>DoD puts {n['dod_all_fixed_share']} of aerospace dollars on fixed-price contracts ({n['dod_ffp_share']} on firm fixed
price alone) but only {n['dod_rnd_fixed_share']} of R&amp;D; {n['dod_rnd_cost_share']} of R&amp;D is cost-reimbursement.
NASA runs the other way: {n['nasa_all_cost_share']} cost-type overall. Time and materials is {n['dod_tm_share']} at DoD
and {n['nasa_tm_share']} at NASA. Fixed price puts cost overruns on the supplier, which is why development work stays
mostly cost-type. One example: in its annual report (10-K) for 2025, Boeing reports $5,013 million of losses in 2024 on its
five major fixed-price development programs.</p>
<img src="charts/pricing-mix.svg" alt="Contract type by work type: DoD R&amp;D {n['dod_rnd_fixed_share']} fixed-price, products {n['dod_product_fixed_share']}; NASA R&amp;D {n['nasa_rnd_fixed_share']} fixed-price">

<h2>3. Most DoD aerospace dollars are not competed</h2>
<p>{n['dod_not_competed_share']} of DoD aerospace obligations were not competed, and {n['dod_only_one_source_share']} of
those cite only one source (FAR 6.302-1). At NASA, {n['nasa_not_competed_share']} was not competed.</p>
<img src="charts/not-competed.svg" alt="Share not competed by year: DoD about {n['dod_not_competed_share']}, NASA about {n['nasa_not_competed_share']}">

<h2>Method</h2>
<p>Every NASA contract transaction and every DoD transaction in NAICS 3364 (aerospace product and parts
manufacturing), FY2021 to FY2025, pulled from the USAspending API with IDV obligations included (they are
{n['nasa_idv_share']} of NASA dollars). Each agency-year sums to USAspending's own aggregate to the cent.
{n['child_records']} supplier records were rolled to parent companies with a {n['crosswalk_rows']}-row crosswalk sourced
to 10-K subsidiary lists, acquisition announcements and NSF's FFRDC list, covering {n['dod_reviewed_share']} of DoD and
{n['nasa_reviewed_share']} of NASA dollars. Each supplier record gets one parent, today's owner, applied to every year. A product-code definition of DoD
aerospace raises the FY2025 top-five record share from {n['dod_fy25_naics_child_top5']} to {n['dod_fy25_psc_child_top5']},
so NAICS 3364 is the conservative boundary. HHI here measures one buyer's spend, not a market.</p>
<footer>Data: USAspending.gov (public domain). Code: <a href="{REPO}">{REPO}</a>.</footer>
</main></body></html>"""
    OUT.write_text(page)
    return OUT


if __name__ == "__main__":
    print(build())
