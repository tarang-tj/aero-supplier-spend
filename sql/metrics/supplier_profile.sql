-- Top 15 ultimate parents per agency over FY21-25 with their contract terms.
WITH p AS (
    SELECT agency, ultimate_parent, sum(obligation) AS amt,
           sum(obligation) FILTER (WHERE pricing_family = 'fixed') / sum(obligation)  AS fixed_share,
           sum(obligation) FILTER (WHERE pricing_family = 'cost') / sum(obligation)   AS cost_share,
           sum(obligation) FILTER (WHERE work_type = 'R&D') / sum(obligation)         AS rnd_share,
           sum(obligation) FILTER (WHERE competed_code IN ('B','C','G','NDO')) / sum(obligation) AS not_competed_share,
           count(DISTINCT child) AS child_records, bool_or(is_ffrdc) AS ffrdc
    FROM base WHERE period = 'FY21-25' GROUP BY 1, 2
)
SELECT *, amt / sum(amt) OVER (PARTITION BY agency) AS share
FROM p QUALIFY row_number() OVER (PARTITION BY agency ORDER BY amt DESC) <= 15
ORDER BY agency, amt DESC;
