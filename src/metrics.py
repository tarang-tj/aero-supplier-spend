"""Run sql/metrics/*.sql against fact_sup and write data/out/*.csv.

Usage: python -m src.metrics   (needs src.load and src.crosswalk to have run)
Each table is computed by SQL; Python only picks the filter variant and writes CSV.
"""
from pathlib import Path

import duckdb

SQL = Path("sql/metrics")
OUT = Path("data/out")
TABLES = ["concentration", "pricing_mix", "competition", "competition_reasons",
          "supplier_profile", "fixed_price_development"]
# Sensitivity variants recompute concentration on a filtered base.
VARIANTS = {"all": "TRUE", "excl_ffrdc": "NOT is_ffrdc", "excl_idv": "award_type NOT LIKE 'IDV%'"}


def set_base(con, where="TRUE"):
    con.execute((SQL / "base.sql").read_text().format(where=where))


def table(con, name):
    return con.execute((SQL / f"{name}.sql").read_text()).df()


def run(con, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    set_base(con)
    frames = {n: table(con, n) for n in TABLES}
    for n, df in frames.items():
        df.to_csv(out / f"{n}.csv", index=False)
    rows = []
    for variant, where in VARIANTS.items():
        set_base(con, where)
        c = table(con, "concentration")
        c.insert(0, "variant", variant)
        rows.append(c)
    import pandas as pd  # local import keeps module import cheap for tests
    sens = pd.concat(rows, ignore_index=True)
    sens.to_csv(out / "concentration_variants.csv", index=False)
    set_base(con)
    return frames, sens


def main():
    con = duckdb.connect("data/spend.duckdb")
    frames, _ = run(con)
    for n, df in frames.items():
        print(f"{n}: {len(df)} rows")


if __name__ == "__main__":
    main()
