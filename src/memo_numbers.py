"""Every number the memo, page and README may print, with its exact printed form.

Usage: python -m src.memo_numbers   -> data/out/memo_numbers.csv (key, value, printed, source)
The memo number audit (tests/test_memo_numbers.py) accepts only `printed` strings from this file.
"""
import csv
from pathlib import Path

import duckdb
import pandas as pd

OUT = Path("data/out")
P5 = "FY21-25"


def pct(x, nd=0):
    return f"{100 * x:.{nd}f}%"


def bn(x):
    return f"${x / 1e9:,.1f}B"


def build(con, out=OUT):
    conc = pd.read_csv(out / "concentration.csv")
    mix = pd.read_csv(out / "pricing_mix.csv")
    comp = pd.read_csv(out / "competition.csv")
    prof = pd.read_csv(out / "supplier_profile.csv")
    var = pd.read_csv(out / "concentration_variants.csv")
    scope_s = pd.read_csv(out / "scope_sensitivity.csv")
    rows = []

    def add(key, value, printed, source):
        rows.append({"key": key, "value": value, "printed": printed, "source": source})

    n, total = con.execute("SELECT count(*), sum(obligation) FROM fact_sup").fetchone()
    add("rows", n, f"{n:,}", "fact_sup")
    add("total", float(total), bn(float(total)), "fact_sup")
    for ag in ("dod", "nasa"):
        c = conc[(conc.agency == ag) & (conc.period == P5)].set_index("level")
        add(f"{ag}_total", c.loc["child", "total"], bn(c.loc["child", "total"]), "concentration.csv")
        for lvl in ("child", "ultimate_parent"):
            r = c.loc[lvl]
            add(f"{ag}_{lvl}_top1_share", r.top1_share, pct(r.top1_share), "concentration.csv")
            add(f"{ag}_{lvl}_top5_share", r.top5_share, pct(r.top5_share), "concentration.csv")
            add(f"{ag}_{lvl}_hhi", r.hhi, f"{r.hhi:,.0f}", "concentration.csv")
            add(f"{ag}_{lvl}_top1", r.top1, r.top1, "concentration.csv")
        fy25 = conc[(conc.agency == ag) & (conc.period == "2025")].set_index("level")
        for lvl in ("child", "ultimate_parent"):
            add(f"{ag}_fy25_{lvl}_top1_share", fy25.loc[lvl, "top1_share"], pct(fy25.loc[lvl, "top1_share"], 1),
                "concentration.csv")
        m = mix[(mix.agency == ag) & (mix.period == P5)].set_index("work_type")
        for wt in ("all", "R&D", "product", "service"):
            r = m.loc[wt]
            k = wt.replace("&", "n").lower()
            add(f"{ag}_{k}_fixed_share", r.fixed / r.total, pct(r.fixed / r.total), "pricing_mix.csv")
            add(f"{ag}_{k}_cost_share", r.cost / r.total, pct(r.cost / r.total), "pricing_mix.csv")
            add(f"{ag}_{k}_total", r.total, bn(r.total), "pricing_mix.csv")
        a = m.loc["all"]
        add(f"{ag}_ffp_share", a.ffp_only / a.total, pct(a.ffp_only / a.total), "pricing_mix.csv")
        add(f"{ag}_cost_plus_share", a.cost_plus_only / a.total, pct(a.cost_plus_only / a.total), "pricing_mix.csv")
        add(f"{ag}_tm_share", (a.tm or 0) / a.total, pct((a.tm or 0) / a.total, 1), "pricing_mix.csv")
        cp = comp[(comp.agency == ag) & (comp.period == P5)].iloc[0]
        add(f"{ag}_not_competed_share", cp.not_competed / cp.total, pct(cp.not_competed / cp.total), "competition.csv")
        add(f"{ag}_single_offer_share", cp.single_offer / cp.total, pct(cp.single_offer / cp.total), "competition.csv")
        p = prof[prof.agency == ag].iloc[0]
        add(f"{ag}_top_parent_not_competed", p.not_competed_share, pct(p.not_competed_share), "supplier_profile.csv")
        add(f"{ag}_top_parent_children", p.child_records, f"{p.child_records}", "supplier_profile.csv")
        for v in ("excl_ffrdc", "excl_idv"):
            r = var[(var.variant == v) & (var.agency == ag) & (var.period == P5) & (var.level == "ultimate_parent")].iloc[0]
            add(f"{ag}_{v}_top5_share", r.top5_share, pct(r.top5_share), "concentration_variants.csv")
        idv_all = var[(var.variant == "all") & (var.agency == ag) & (var.period == P5) & (var.level == "child")].iloc[0].total
        idv_ex = var[(var.variant == "excl_idv") & (var.agency == ag) & (var.period == P5) & (var.level == "child")].iloc[0].total
        add(f"{ag}_idv_share", 1 - idv_ex / idv_all, pct(1 - idv_ex / idv_all, 1), "concentration_variants.csv")
    reasons = pd.read_csv(out / "competition_reasons.csv")
    fpd = pd.read_csv(out / "fixed_price_development.csv")
    for ag in ("dod", "nasa"):
        one = reasons[(reasons.agency == ag) & (reasons.reason == "ONE")].share_of_not_competed.sum()
        add(f"{ag}_only_one_source_share", one, pct(one), "competition_reasons.csv")
        cov = con.execute("SELECT sum(obligation) FILTER (WHERE reviewed) / sum(obligation) FROM fact_sup WHERE agency = ?",
                          [ag]).fetchone()[0]
        add(f"{ag}_reviewed_share", float(cov), pct(float(cov)), "fact_sup.reviewed")
        rnd_fixed = mix[(mix.agency == ag) & (mix.period == P5) & (mix.work_type == "R&D")].fixed.iloc[0]
        add(f"{ag}_rnd_fixed_total", rnd_fixed, bn(rnd_fixed), "pricing_mix.csv")
        for parent in fpd[(fpd.agency == ag) & (fpd.period == P5)].head(3).itertuples():
            k = parent.ultimate_parent.lower().replace(" ", "_")
            add(f"{ag}_fixed_rnd_{k}", parent.fixed_rnd, bn(parent.fixed_rnd), "fixed_price_development.csv")
            add(f"{ag}_fixed_rnd_{k}_share", parent.share_of_fixed_rnd, pct(parent.share_of_fixed_rnd),
                "fixed_price_development.csv")
    n_parents = con.execute("SELECT count(DISTINCT ultimate_parent) FROM fact_sup").fetchone()[0]
    n_children = con.execute("SELECT count(DISTINCT child) FROM fact_sup").fetchone()[0]
    add("child_records", n_children, f"{n_children:,}", "fact_sup")
    add("parent_companies", n_parents, f"{n_parents:,}", "fact_sup")
    add("crosswalk_rows", len(pd.read_csv("data/crosswalk.csv")), f"{len(pd.read_csv('data/crosswalk.csv'))}", "crosswalk.csv")
    s25 = scope_s[scope_s.fy == 2025].set_index("definition")
    for d in ("naics", "psc"):
        add(f"dod_fy25_{d}_child_top5", s25.loc[d, "top5_share"], pct(s25.loc[d, "top5_share"]), "scope_sensitivity.csv")
    pd.DataFrame(rows).to_csv(out / "memo_numbers.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    return pd.DataFrame(rows)


def main():
    df = build(duckdb.connect("data/spend.duckdb", read_only=True))
    print(df[["key", "printed"]].to_string(index=False))


if __name__ == "__main__":
    main()
