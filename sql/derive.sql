-- fact_txn: one row per contract transaction, typed, with derived analysis columns.
-- Pricing families follow the USAspending data dictionary (TypeOfContractPricing) and FAR 16.101(b).
-- Work type comes from the first character of the Product or Service Code:
--   'A' = research and development, digit = product, any other letter = service.
CREATE OR REPLACE TABLE fact_txn AS
SELECT
    contract_transaction_unique_key                         AS txn_key,
    contract_award_unique_key                               AS award_key,
    split_part(slice, '-', 1)                               AS agency,
    CAST(action_date_fiscal_year AS INTEGER)                AS fy,
    CAST(action_date AS DATE)                               AS action_date,
    CAST(NULLIF(federal_action_obligation, '') AS DECIMAL(18, 2)) AS obligation,
    NULLIF(trim(recipient_uei), '')                         AS recipient_uei,
    NULLIF(trim(recipient_name), '')                        AS recipient_name,
    NULLIF(recipient_parent_uei, '')                        AS parent_uei,
    NULLIF(recipient_parent_name, '')                       AS parent_name,
    NULLIF(type_of_contract_pricing_code, '')               AS pricing_code,
    CASE
        WHEN type_of_contract_pricing_code IN ('A', 'B', 'J', 'K', 'L', 'M') THEN 'fixed'
        WHEN type_of_contract_pricing_code IN ('R', 'S', 'T', 'U', 'V') THEN 'cost'
        WHEN type_of_contract_pricing_code IN ('Y', 'Z') THEN 'tm'
        WHEN type_of_contract_pricing_code IN ('1', '2', '3') THEN 'other'
        ELSE 'missing'
    END                                                     AS pricing_family,
    NULLIF(extent_competed_code, '')                        AS competed_code,
    TRY_CAST(number_of_offers_received AS INTEGER)          AS offers,
    NULLIF(other_than_full_and_open_competition_code, '')   AS sole_source_reason,
    naics_code,
    product_or_service_code                                 AS psc,
    product_or_service_code_description                     AS psc_desc,
    CASE
        WHEN product_or_service_code IS NULL OR product_or_service_code = '' THEN 'unknown'
        WHEN left(product_or_service_code, 1) = 'A' THEN 'R&D'
        WHEN regexp_matches(left(product_or_service_code, 1), '[0-9]') THEN 'product'
        ELSE 'service'
    END                                                     AS work_type,
    coalesce(NULLIF(award_type_code, ''), 'IDV_' || idv_type_code) AS award_type,
    upper(coalesce(federally_funded_research_and_development_corp, '')) IN ('T', 'TRUE', 'Y', 'YES')
                                                            AS is_ffrdc,
    contracting_officers_determination_of_business_size_code AS business_size,
    major_program,
    transaction_description,
    usaspending_permalink
FROM raw_txn;
