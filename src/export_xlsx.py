"""Excel spend cube for procurement readers: flat Supplier Cube (PivotTable-ready) plus summaries.

Usage: python -m src.export_xlsx   -> docs/aero-supplier-spend.xlsx
Every sheet ends with a =SUM() totals row so the workbook recalculates in Excel.
"""
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

OUT = Path("docs/aero-supplier-spend.xlsx")
FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
HEAD_FILL = PatternFill("solid", fgColor="DDE3EA")
MONEY, PCT = '$#,##0;($#,##0);"-"', "0.0%"
CUBE_SQL = """
SELECT ultimate_parent AS "Ultimate parent", agency AS "Agency", CAST(fy AS VARCHAR) AS "Fiscal year",
       CASE pricing_family WHEN 'fixed' THEN 'Fixed-price family' WHEN 'cost' THEN 'Cost-reimbursement family'
            WHEN 'tm' THEN 'Time & Materials / Labor Hour' WHEN 'other' THEN 'Other' ELSE 'Not reported' END AS "Pricing family",
       work_type AS "Work type", count(*) AS "Transactions", sum(obligation) AS "Obligations ($)"
FROM fact_sup GROUP BY ALL ORDER BY 1, 2, 3, 4, 5
"""


def write_sheet(wb, title, df, money_cols=(), pct_cols=(), sum_cols=()):
    """Write a dataframe as a formatted table; add a SUM row for sum_cols. Returns the sheet."""
    ws = wb.create_sheet(title)
    ws.append(list(df.columns))
    for c in ws[1]:
        c.font, c.fill = BOLD, HEAD_FILL
    for row in df.itertuples(index=False):
        ws.append([None if pd.isna(v) else (float(v) if hasattr(v, "is_finite") else v) for v in row])
    last = ws.max_row
    if sum_cols:
        ws.cell(last + 1, 1, "Total").font = BOLD
        for name in sum_cols:
            col = get_column_letter(list(df.columns).index(name) + 1)
            ws[f"{col}{last + 1}"] = f"=SUM({col}2:{col}{last})"
            ws[f"{col}{last + 1}"].font = BOLD
    for i, name in enumerate(df.columns, 1):
        col = get_column_letter(i)
        fmt = MONEY if name in money_cols else PCT if name in pct_cols else None
        for cell in ws[col][1:]:
            if not cell.font.bold:
                cell.font = FONT
            if fmt:
                cell.number_format = fmt
        ws.column_dimensions[col].width = max(12, min(42, len(str(name)) + 4))
    ws.freeze_panes = "A2"
    return ws


def readme(wb, totals):
    ws = wb.active
    ws.title = "README"
    lines = [
        "Aerospace supplier spend: DoD (NAICS 3364) and NASA contract obligations, FY2021-FY2025",
        f"Source: USAspending.gov prime contract transactions (incl. IDV obligations), pulled {date.today().isoformat()}.",
        "Each agency x fiscal-year slice reconciles to USAspending's own aggregate within $0.01 (data/reconcile.csv).",
        "Obligations are net of deobligations. Fiscal year = federal FY (Oct-Sep).",
        "Ultimate parent: recipient UEI rolled to its parent company; top suppliers reviewed by hand (Crosswalk sheet).",
        "Pricing families per FAR 16 and the USAspending data dictionary: fixed-price A,B,J,K,L,M; cost R,S,T,U,V; T&M/LH Y,Z.",
        "Work type from Product/Service Code: A* = R&D, digit = product, other letter = service.",
        "Supplier Cube is flat: insert a PivotTable on it to slice by supplier, agency, year, pricing family, work type.",
        "Totals rows use =SUM formulas; Excel computes them on open.",
        "", "Agency totals FY2021-25 ($):",
    ] + [f"  {a}: {v:,.2f}" for a, v in totals]
    for i, t in enumerate(lines, 1):
        ws.cell(i, 1, t).font = BOLD if i == 1 else FONT
    ws.column_dimensions["A"].width = 120


def build(con, out=OUT, data_out=Path("data/out"), xwalk=Path("data/crosswalk.csv")):
    wb = Workbook()
    readme(wb, con.execute("SELECT agency, sum(obligation) FROM fact_sup GROUP BY 1 ORDER BY 1").fetchall())
    write_sheet(wb, "Supplier Cube", con.execute(CUBE_SQL).df(), money_cols={"Obligations ($)"},
                sum_cols={"Obligations ($)", "Transactions"})
    conc = pd.read_csv(data_out / "concentration.csv")
    write_sheet(wb, "Concentration", conc, money_cols={"total"}, pct_cols={"top1_share", "cr4", "top5_share"})
    mix = pd.read_csv(data_out / "pricing_mix.csv")
    write_sheet(wb, "Pricing Mix", mix, money_cols=set(mix.columns[3:]))
    comp = pd.read_csv(data_out / "competition.csv")
    write_sheet(wb, "Competition", comp, money_cols=set(comp.columns[2:]))
    prof = pd.read_csv(data_out / "supplier_profile.csv")
    write_sheet(wb, "Top Suppliers", prof, money_cols={"amt"},
                pct_cols={c for c in prof.columns if c.endswith("share")})
    if xwalk.exists():
        write_sheet(wb, "Crosswalk", pd.read_csv(xwalk))
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main():
    print(build(duckdb.connect("data/spend.duckdb", read_only=True)))


if __name__ == "__main__":
    main()
