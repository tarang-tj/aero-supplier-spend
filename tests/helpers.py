"""Fixture builders: tiny zips shaped exactly like USAspending downloads."""
import csv
import io
import zipfile

from src import scope


def txn(key, obligation, **kw):
    """One prime transaction row with every scope column present."""
    row = {c: "" for c in scope.COLUMNS}
    row.update({
        "contract_transaction_unique_key": key, "contract_award_unique_key": f"AW_{key}",
        "action_date": "2025-01-15", "action_date_fiscal_year": "2025",
        "federal_action_obligation": str(obligation), "recipient_uei": "UEI1", "recipient_name": "ACME",
        "recipient_parent_uei": "P1", "recipient_parent_name": "ACME PARENT",
        "type_of_contract_pricing_code": "J", "extent_competed_code": "A",
        "product_or_service_code": "1510", "award_type_code": "D",
        "federally_funded_research_and_development_corp": "f",
    })
    row.update(kw)
    return row


def write_zip(path, rows, subaward_rows=0):
    """Write a download-shaped zip: prime CSV plus a subaward CSV that must be ignored."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=scope.COLUMNS)
    w.writeheader()
    w.writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Contracts_PrimeTransactions_2026-01-01_1.csv", buf.getvalue())
        z.writestr("Contracts_Subawards_2026-01-01_1.csv", "a,b\n" + "x,y\n" * subaward_rows)
    return path
