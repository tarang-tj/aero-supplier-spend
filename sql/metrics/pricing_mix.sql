-- Contract pricing mix by agency x period x work type. Family columns partition the total;
-- ffp_only (J) and cost_plus_only (R, U, V) are the posting's named types, subsets of their families.
SELECT agency, period, coalesce(work_type, 'all') AS work_type,
       sum(obligation)                                                      AS total,
       sum(obligation) FILTER (WHERE pricing_family = 'fixed')             AS fixed,
       sum(obligation) FILTER (WHERE pricing_family = 'cost')              AS cost,
       sum(obligation) FILTER (WHERE pricing_family = 'tm')                AS tm,
       sum(obligation) FILTER (WHERE pricing_family = 'other')             AS other,
       sum(obligation) FILTER (WHERE pricing_family = 'missing')           AS missing,
       sum(obligation) FILTER (WHERE pricing_code = 'J')                   AS ffp_only,
       sum(obligation) FILTER (WHERE pricing_code IN ('R', 'U', 'V'))      AS cost_plus_only
FROM base GROUP BY GROUPING SETS ((agency, period, work_type), (agency, period))
ORDER BY 1, 2, 3;
