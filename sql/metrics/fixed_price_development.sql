-- R&D work (PSC starting 'A') obligated on fixed-price-family contracts, by ultimate parent.
SELECT agency, period, ultimate_parent, sum(obligation) AS fixed_rnd,
       sum(obligation) / sum(sum(obligation)) OVER (PARTITION BY agency, period) AS share_of_fixed_rnd
FROM base WHERE work_type = 'R&D' AND pricing_family = 'fixed'
GROUP BY 1, 2, 3
QUALIFY row_number() OVER (PARTITION BY agency, period ORDER BY sum(obligation) DESC) <= 10
ORDER BY 1, 2, 4 DESC;
