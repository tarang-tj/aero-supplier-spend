-- base: fact_sup with a period column (each FY plus the five-year total). {where} filters variants.
CREATE OR REPLACE TEMP VIEW base AS
SELECT *, CAST(fy AS VARCHAR) AS period FROM fact_sup WHERE {where}
UNION ALL
SELECT *, 'FY21-25' AS period FROM fact_sup WHERE {where};
