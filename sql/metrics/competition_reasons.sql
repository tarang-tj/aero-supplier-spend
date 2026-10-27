-- Why spend was not competed (other_than_full_and_open_competition_code), five-year totals.
SELECT agency, coalesce(sole_source_reason, 'none recorded') AS reason, sum(obligation) AS amt,
       sum(obligation) / sum(sum(obligation)) OVER (PARTITION BY agency) AS share_of_not_competed
FROM base WHERE period = 'FY21-25' AND competed_code IN ('B', 'C', 'G', 'NDO')
GROUP BY 1, 2 ORDER BY 1, 3 DESC;
