"""First screen of docs/index.html: the rollup reveal.

Every DoD supplier record is drawn as a sliver of one bar, width = its share of DoD aerospace
obligations, colored by the parent company it rolls up to. "As reported" orders slivers by record
size, so Lockheed Martin's records sit scattered among everyone else's; "rolled up" slides the same
slivers next to their parent. Widths never change, only positions, so nothing on screen is invented.
Positions for both states are computed here; the page's script only switches between them.
"""
import html
import json

import duckdb

TOP_RECORDS = 160  # largest records drawn individually; smaller ones outside the top five parents form one block
COLORS = ["#d4502b", "#2f6db5", "#3c8c5a", "#8a5cc0", "#c79a2a"]  # top five parents, in order
OTHER = "#cfc6b6"


def records(db="data/spend.duckdb"):
    con = duckdb.connect(db, read_only=True)
    total = float(con.execute("SELECT sum(obligation) FROM fact_sup WHERE agency = 'dod'").fetchone()[0])
    rows = con.execute("""SELECT child, ultimate_parent, sum(obligation) AS amt FROM fact_sup
                          WHERE agency = 'dod' GROUP BY 1, 2 ORDER BY amt DESC""").fetchall()
    parents = con.execute("""SELECT ultimate_parent, sum(obligation) AS amt FROM fact_sup
                             WHERE agency = 'dod' GROUP BY 1 ORDER BY amt DESC LIMIT 5""").fetchall()
    return total, [(c, p, float(a)) for c, p, a in rows], [(p, float(a)) for p, a in parents]


def layout(total, rows, parents):
    """Return slivers with width and left (in percent) for both states, plus the remainder width."""
    rank = {p: i for i, (p, _) in enumerate(parents)}
    # Every record of a top-five parent is drawn (the headline counts them), plus the largest others.
    # A record whose deobligations exceed its obligations nets negative and cannot be drawn: it is
    # netted into its parent's largest record (top five) or into the remainder block (others).
    keep = [(i < TOP_RECORDS or r[1] in rank) and r[2] > 0 for i, r in enumerate(rows)]
    drawn = [list(r) for r, k in zip(rows, keep) if k]
    rest = 0.0
    for r, k in zip(rows, keep):
        if k:
            continue
        if r[2] <= 0 and r[1] in rank:
            next(d for d in drawn if d[1] == r[1])[2] += r[2]  # rows are sorted, so this is the largest
        else:
            rest += r[2]
    rest = 100 * rest / total
    slivers = [{"parent": p, "w": 100 * a / total, "color": COLORS[rank[p]] if p in rank else OTHER} for _, p, a in drawn]
    x = 0.0
    for s in slivers:  # as reported: by record size
        s["l0"], x = x, x + s["w"]
    order = sorted(range(len(slivers)), key=lambda i: (rank.get(slivers[i]["parent"], 99), -slivers[i]["w"]))
    x = 0.0
    for i in order:  # rolled up: grouped by parent, top five first
        slivers[i]["l1"], x = x, x + slivers[i]["w"]
    return slivers, rest


def latest_block():
    """The FY2026-so-far line (src/latest.py), or empty markers until it has run."""
    from src import latest
    if not latest.OUT.exists():
        return latest.START + latest.END
    return latest.block(json.loads(latest.OUT.read_text()))


def build_hero(n, db="data/spend.duckdb"):
    total, rows, parents = records(db)
    slivers, rest = layout(total, rows, parents)
    bar = "".join(
        f'<i style="left:{s["l1"]:.4f}%;width:{s["w"]:.4f}%;background:{s["color"]}" '
        f'data-l0="{s["l0"]:.4f}" data-l1="{s["l1"]:.4f}"></i>' for s in slivers)
    bar += f'<i class=rest style="left:{100 - rest:.4f}%;width:{rest:.4f}%"></i>'
    legend = "".join(f'<span><b style="background:{COLORS[i]}"></b>{html.escape(p)} ${a / 1e9:,.1f}B</span>'
                     for i, (p, a) in enumerate(parents))
    return f"""<section class=hero aria-labelledby=hero-h>
<p class=kicker>DoD aerospace supplier spend, FY2021 to FY2025</p>
<h1 id=hero-h>{n['dod_top_parent_children']} supplier records. One company. {n['dod_ultimate_parent_top1_share']} of DoD aerospace.</h1>
<p class=lede>USAspending lists Lockheed Martin under {n['dod_top_parent_children']} separate supplier records, so its biggest
one looks like {n['dod_child_top1_share']} of the money. Roll every record up to its parent company and five companies hold
{n['dod_ultimate_parent_top5_share']} of {n['dod_total']}.</p>
<div class=reveal data-state=1>
 <div class=readout><span>Top five</span> <strong data-v0="{n['dod_child_top5_share']}" data-v1="{n['dod_ultimate_parent_top5_share']}">{n['dod_ultimate_parent_top5_share']}</strong>
 <em data-v0="as reported, by supplier record" data-v1="rolled up to parent companies">rolled up to parent companies</em></div>
 <div class=bar role=img aria-label="DoD aerospace obligations: the top five hold {n['dod_child_top5_share']} as reported and {n['dod_ultimate_parent_top5_share']} rolled up to parent companies">{bar}</div>
 <div class=legend>{legend}<span><b style="background:{OTHER}"></b>All other suppliers</span></div>
 <div class=toggle role=group aria-label="View"><button type=button data-to=0 aria-pressed=false>As reported</button><button type=button data-to=1 aria-pressed=true>Rolled up</button></div>
</div>
<p class=note>Each sliver is one supplier record in USAspending, width by dollars. Source: USAspending.gov, {n['rows']} DoD and NASA contract transactions, reconciled to USAspending to the cent as of the {n['pull_date']} pull.</p>
{latest_block()}
</section>"""


HERO_CSS = """
.hero { padding: 8px 0 28px; }
.kicker { color:#b6401f; font-weight:600; margin:0; }
.latest { margin: 10px 0 0; padding: 10px 14px; border-left: 3px solid #b6401f; color: var(--muted); font-size: .95rem; max-width: 70ch; }
.latest b { color: var(--ink, inherit); }
.hero h1 { font-size: clamp(2.1rem, 6vw, 4.2rem); line-height:1.03; letter-spacing:-.02em; font-weight:800; margin: 12px 0 18px; max-width: 16ch; }
.reveal { margin: 28px 0 8px; }
.readout { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
.readout span { color: var(--muted); }
.readout strong { font-size: 2.6rem; line-height:1; font-variant-numeric: tabular-nums; }
.readout em { font-style: normal; color: var(--muted); }
.bar { position:relative; height:64px; background:#ebe4d6; border-radius:4px; overflow:hidden; }
.bar i { position:absolute; top:0; bottom:0; box-shadow: inset -1px 0 0 rgba(246,241,231,.85); transition: left 1.6s cubic-bezier(.65,0,.35,1); }
.bar i.rest { background: repeating-linear-gradient(90deg,#d8cfbf 0 2px,#c8bead 2px 3px); box-shadow:none; }
.legend { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.9rem; color:var(--muted); margin-top:12px; }
.legend b { display:inline-block; width:11px; height:11px; border-radius:2px; margin-right:6px; vertical-align:-1px; }
.toggle { margin-top:20px; display:inline-flex; border:2px solid var(--ink); border-radius:999px; overflow:hidden; }
.toggle button { font: inherit; font-weight:600; border:0; background:transparent; color:var(--ink); padding:9px 18px; cursor:pointer; }
.toggle button[aria-pressed=true] { background:var(--ink); color:var(--bg); }
.toggle button:focus-visible { outline:3px solid var(--accent); outline-offset:-3px; }
.note { color:var(--muted); font-size:.85rem; }
@media (prefers-reduced-motion: reduce) { .bar i { transition:none; } }
"""

# Switches the slivers between their two precomputed positions. Starts at "as reported" and rolls
# up once when the bar scrolls into view; without JavaScript the page shows the rolled-up state.
HERO_JS = """
(() => {
  const r = document.querySelector('.reveal'); if (!r) return;
  const set = s => {
    r.dataset.state = s;
    r.querySelectorAll('.bar i[data-l0]').forEach(i => { i.style.left = i.dataset['l' + s] + '%'; });
    r.querySelectorAll('[data-v0]').forEach(e => { e.textContent = e.dataset['v' + s]; });
    r.querySelectorAll('.toggle button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.to === String(s))));
  };
  r.querySelectorAll('.toggle button').forEach(b => b.addEventListener('click', () => set(Number(b.dataset.to))));
  const bars = r.querySelectorAll('.bar i'); bars.forEach(i => { i.style.transition = 'none'; });
  set(0); r.offsetHeight; bars.forEach(i => { i.style.transition = ''; });
  const go = () => setTimeout(() => set(1), 700);
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); go(); } }, { threshold: .6 });
    io.observe(r.querySelector('.bar'));
  } else { go(); }
})();
"""
