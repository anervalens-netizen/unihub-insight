BEGIN;

CREATE OR REPLACE VIEW insight.monthly_review_item_month
WITH (security_barrier = true)
AS
SELECT
    sale.import_month,
    sale.site_code,
    sale.agent,
    sale.item_code,
    MAX(sale.item_name) AS item_name,
    MAX(NULLIF(BTRIM(sale.brand), '')) AS brand,
    MAX(NULLIF(BTRIM(sale.category), '')) AS category,
    SUM(sale.total_value) AS net_sales,
    SUM(sale.quantity) AS net_quantity,
    SUM(sale.total_value) FILTER (WHERE NOT sale.is_return) AS gross_sales,
    SUM(ABS(sale.total_value)) FILTER (WHERE sale.is_return) AS return_value,
    SUM(GREATEST(sale.quantity, 0)) FILTER (WHERE NOT sale.is_return) AS positive_quantity,
    SUM(ABS(LEAST(sale.quantity, 0))) FILTER (WHERE sale.is_return) AS return_quantity
FROM public.sales_transactions sale
WHERE NOT sale.is_cartela
GROUP BY
    sale.import_month,
    sale.site_code,
    sale.agent,
    sale.item_code;

COMMENT ON VIEW insight.monthly_review_item_month IS
    'Governed monthly return-value and product-attribute supplement. Core KPIs remain sourced from reporting_* tables.';

GRANT SELECT ON insight.monthly_review_item_month TO unihub_insight_reader;

COMMIT;
