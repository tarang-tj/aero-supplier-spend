"""Four memo charts from data/out CSVs -> docs/charts/*.png and *.svg.

Palette: validated categorical slots 1-4 (dataviz reference palette, light surface).
Values are direct-labeled because slots 3-4 sit below 3:1 contrast on the surface.
"""
import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path("docs/charts")
DATA = Path("data/out")
SURFACE, INK, MUTED = "#fcfcfb", "#0b0b0b", "#52514e"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
AGENCY = {"dod": "DoD aerospace (NAICS 3364)", "nasa": "NASA"}
SOURCE = "Source: USAspending.gov contract transactions incl. IDVs, FY2021-25; analysis by Tarang Jammalamadaka."
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, 0.01, SOURCE, fontsize=7.5, color=MUTED)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def rollup_effect(conc):
    """Top-5 share at child vs ultimate-parent level, five-year total, per agency."""
    d = conc[conc.period == "FY21-25"]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    y = 0
    for agency in ("dod", "nasa"):
        for i, level in enumerate(("child", "ultimate_parent")):
            v = d[(d.agency == agency) & (d.level == level)].top5_share.iloc[0]
            ax.barh(y, v, height=0.7, color=SLOTS[i], edgecolor=SURFACE, linewidth=2)
            ax.text(v + 0.01, y, f"{v:.0%}", va="center", color=INK)
            y += 1
        y += 0.6
    ax.set_yticks([0, 1, 2.6, 3.6])
    ax.set_yticklabels([f"{AGENCY['dod']}\nas reported (UEI)", "rolled up to parent",
                        f"{AGENCY['nasa']}\nas reported (UEI)", "rolled up to parent"])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.set_title("Top-5 supplier share of obligations, FY2021-25", loc="left", color=INK, fontsize=12)
    save(fig, "rollup-effect")


def pricing_mix(mix):
    d = mix[(mix.period == "FY21-25") & (mix.work_type.isin(["R&D", "product", "service"]))]
    fams = [("fixed", "Fixed-price family"), ("cost", "Cost-reimbursement family"),
            ("tm", "Time & Materials / Labor Hour"), ("other", "Other / not reported")]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, agency in zip(axes, ("dod", "nasa"), strict=True):
        rows = d[d.agency == agency].set_index("work_type").reindex(["R&D", "product", "service"])
        left = [0.0] * 3
        for i, (col, label) in enumerate(fams):
            vals = (rows[col].fillna(0) + (rows["missing"].fillna(0) if col == "other" else 0)) / rows.total
            ax.barh(range(3), vals, left=left, color=SLOTS[i], edgecolor=SURFACE, linewidth=2,
                    label=label if agency == "dod" else None)
            for j, v in enumerate(vals):
                if v >= 0.08:
                    ax.text(left[j] + v / 2, j, f"{v:.0%}", ha="center", va="center", color=INK, fontsize=9)
            left = [a + b for a, b in zip(left, vals, strict=True)]
        ax.set_yticks(range(3))
        ax.set_yticklabels(["R&D", "Products", "Services"])
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
        ax.set_title(AGENCY[agency], loc="left", color=INK)
    fig.legend(loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.08), fontsize=8.5)
    fig.suptitle("Contract type by kind of work, share of FY2021-25 obligations", x=0.01, y=1.16,
                 ha="left", color=INK, fontsize=12)
    save(fig, "pricing-mix")


def spread(ys, gap):
    """Nudge end-label positions apart so no two sit closer than `gap` (keeps order)."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in itertools.pairwise(order):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def hhi_trend(conc):
    d = conc[conc.period != "FY21-25"].copy()
    d["fy"] = d.period.astype(int)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    series = [("dod", "child"), ("dod", "ultimate_parent"), ("nasa", "child"), ("nasa", "ultimate_parent")]
    ends, names = [], []
    for i, (agency, level) in enumerate(series):
        s = d[(d.agency == agency) & (d.level == level)].sort_values("fy")
        ax.plot(s.fy, s.hhi, color=SLOTS[i], linewidth=2, marker="o", markersize=5)
        ends.append(s.hhi.iloc[-1])
        names.append(f"{'DoD' if agency == 'dod' else 'NASA'}, {'parent' if level != 'child' else 'as reported'}")
    for y, name in zip(spread(ends, 140), names, strict=True):
        ax.text(d.fy.max() + 0.1, y, name, va="center", color=INK, fontsize=8.5)
    ax.axhline(1800, color=MUTED, linewidth=1, linestyle="--")
    ax.text(d.fy.min(), 1840, "1,800: highly concentrated (2023 Merger Guidelines)", color=MUTED, fontsize=8)
    ax.set_xticks(sorted(d.fy.unique()))
    ax.set_xticklabels([f"FY{y}" for y in sorted(d.fy.unique())])
    ax.set_xlim(right=d.fy.max() + 1.3)
    ax.set_ylabel("HHI of obligation shares")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_title("Supplier concentration (HHI) by fiscal year", loc="left", color=INK, fontsize=12)
    save(fig, "hhi-trend")


def competition(comp):
    d = comp[comp.period != "FY21-25"].copy()
    d["fy"] = d.period.astype(int)
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, agency in enumerate(("dod", "nasa")):
        s = d[d.agency == agency].sort_values("fy")
        share = s.not_competed / s.total
        ax.plot(s.fy, share, color=SLOTS[i], linewidth=2, marker="o", markersize=5)
        ax.text(s.fy.iloc[-1] + 0.1, share.iloc[-1], f"{AGENCY[agency]} {share.iloc[-1]:.0%}",
                va="center", color=INK, fontsize=8.5)
    ax.set_xticks(sorted(d.fy.unique()))
    ax.set_xticklabels([f"FY{y}" for y in sorted(d.fy.unique())])
    ax.set_xlim(right=d.fy.max() + 1.6)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_title("Share of obligations not competed", loc="left", color=INK, fontsize=12)
    save(fig, "not-competed")


def main():
    conc = pd.read_csv(DATA / "concentration.csv")
    rollup_effect(conc)
    pricing_mix(pd.read_csv(DATA / "pricing_mix.csv"))
    hhi_trend(conc)
    competition(pd.read_csv(DATA / "competition.csv"))
    print("charts ->", OUT)


if __name__ == "__main__":
    main()
