"""Single source of truth for what gets pulled from USAspending.

Scope: every NASA contract transaction, plus DoD contract transactions in
aerospace product and parts manufacturing (NAICS 3364), FY2021-FY2025.

DoD procurement data is published with a 90-day delay (FPDS: DoD data "is
subject to a 90-day delay", https://www.fpds.gov/fpdsng_cms/index.php/en/).
FY2025 closed 2025-09-30, so it is complete; FY2026 is excluded.
"""

API = "https://api.usaspending.gov/api/v2/"

FYS = [2021, 2022, 2023, 2024, 2025]

AGENCIES = {
    "nasa": {
        "agencies": [{"type": "awarding", "tier": "toptier",
                      "name": "National Aeronautics and Space Administration"}],
    },
    "dod": {
        "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
        "naics_codes": {"require": ["3364"]},
    },
}

# Contracts (A-D) plus every IDV type. IDVs carry real obligations (e.g. NASA's
# launch services IDIQ); leaving them out under-counts supplier spend.
AWARD_TYPES = ["A", "B", "C", "D", "IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B",
               "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]

COLUMNS = [
    "contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid",
    "modification_number", "parent_award_id_piid", "action_date", "action_date_fiscal_year",
    "federal_action_obligation", "awarding_agency_name", "awarding_sub_agency_name",
    "awarding_office_name", "recipient_uei", "recipient_name", "recipient_parent_uei",
    "recipient_parent_name", "type_of_contract_pricing_code", "type_of_contract_pricing",
    "extent_competed_code", "other_than_full_and_open_competition_code",
    "number_of_offers_received", "naics_code", "product_or_service_code",
    "product_or_service_code_description", "award_type_code", "idv_type_code",
    "research_code", "cost_or_pricing_data_code",
    "federally_funded_research_and_development_corp",
    "contracting_officers_determination_of_business_size_code", "major_program",
    "transaction_description", "usaspending_permalink",
]


def fy_period(fy):
    """Federal fiscal year FY runs Oct 1 of FY-1 through Sep 30 of FY."""
    return [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}]


def filters(agency, fy):
    """Search/download filter object for one agency x fiscal-year slice."""
    return {**AGENCIES[agency], "award_type_codes": AWARD_TYPES, "time_period": fy_period(fy)}


def slices():
    return [(a, fy) for a in AGENCIES for fy in FYS]
