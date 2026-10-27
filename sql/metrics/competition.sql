-- Competition by agency x period. Not competed = B, C, G, NDO; E (follow-on to a competed action)
-- is its own column; competed = A, D, F, CDO (USAspending data dictionary, ExtentCompeted).
SELECT agency, period, sum(obligation) AS total,
       sum(obligation) FILTER (WHERE competed_code IN ('A', 'D', 'F', 'CDO'))      AS competed,
       sum(obligation) FILTER (WHERE competed_code IN ('B', 'C', 'G', 'NDO'))      AS not_competed,
       sum(obligation) FILTER (WHERE competed_code = 'E')                          AS follow_on,
       sum(obligation) FILTER (WHERE competed_code IS NULL
                               OR competed_code NOT IN ('A','B','C','D','E','F','G','CDO','NDO')) AS missing,
       sum(obligation) FILTER (WHERE offers = 1)                                   AS single_offer
FROM base GROUP BY 1, 2 ORDER BY 1, 2;
