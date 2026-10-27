-- Supplier concentration of each agency's obligations, at child (UEI) and ultimate-parent level.
-- Shares are of net obligations. HHI = sum of squared percentage shares over suppliers with positive net.
WITH sup AS (
    SELECT agency, period, 'child' AS level, child AS supplier, any_value(child_name) AS label, sum(obligation) AS amt
    FROM base GROUP BY 1, 2, 3, 4
    UNION ALL
    SELECT agency, period, 'ultimate_parent', ultimate_parent, ultimate_parent, sum(obligation)
    FROM base GROUP BY 1, 2, 3, 4
), ranked AS (
    SELECT *, amt / sum(amt) OVER w AS share, sum(amt) OVER w AS total,
           row_number() OVER (PARTITION BY agency, period, level ORDER BY amt DESC) AS rk
    FROM sup WINDOW w AS (PARTITION BY agency, period, level)
)
SELECT agency, period, level, total,
       max(label) FILTER (WHERE rk = 1)            AS top1,
       sum(share) FILTER (WHERE rk = 1)            AS top1_share,
       sum(share) FILTER (WHERE rk <= 4)           AS cr4,
       sum(share) FILTER (WHERE rk <= 5)           AS top5_share,
       sum(power(100 * share, 2)) FILTER (WHERE amt > 0) AS hhi,
       count(*)                                     AS suppliers
FROM ranked GROUP BY 1, 2, 3, 4 ORDER BY 1, 3, 2;
