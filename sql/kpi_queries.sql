-- =====================================================================
-- Supply Chain KPI queries (SQLite) — run against data/supply_chain.db
-- Each query is a named section; src/compute_kpis.py executes them in order
-- and renders the results into reports/kpi_summary.md.
-- =====================================================================

-- Q01: headline delivery KPIs ------------------------------------------------
-- name: headline
SELECT
    COUNT(*)                                              AS total_orders,
    ROUND(100.0 * SUM(on_time) / COUNT(*), 2)             AS on_time_pct,
    ROUND(100.0 * SUM(1 - on_time) / COUNT(*), 2)         AS late_rate_pct,
    ROUND(AVG(CASE WHEN on_time = 0 THEN days_late END), 2) AS avg_days_late,
    ROUND(100.0 * SUM(is_accurate) / COUNT(*), 2)          AS accuracy_pct,
    ROUND(AVG(shipping_cost), 2)                           AS avg_shipping_cost,
    ROUND(100.0 * SUM(pickup_on_time) / COUNT(*), 2)      AS pickup_sla_pct
FROM fact_orders;

-- Q02: carrier scorecard ------------------------------------------------------
-- name: carrier_scorecard
SELECT
    c.carrier_name,
    c.tier,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(CASE WHEN f.on_time = 0 THEN f.days_late END), 2) AS avg_days_late,
    ROUND(AVG(f.shipping_cost), 2)                        AS avg_shipping_cost,
    ROUND(100.0 * SUM(f.pickup_on_time) / COUNT(*), 2)    AS pickup_sla_pct,
    ROUND(AVG(f.pickup_days), 2)                          AS avg_pickup_days
FROM fact_orders f
JOIN dim_carrier c ON c.carrier_id = f.carrier_id
GROUP BY c.carrier_name, c.tier
ORDER BY late_rate_pct DESC;

-- Q03: warehouse throughput and reliability ------------------------------------
-- name: warehouse_scorecard
SELECT
    w.warehouse_name,
    w.city,
    w.province_code,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(100.0 * SUM(f.is_accurate) / COUNT(*), 2)       AS accuracy_pct,
    ROUND(AVG(f.shipping_cost), 2)                        AS avg_shipping_cost
FROM fact_orders f
JOIN dim_warehouse w ON w.warehouse_id = f.warehouse_id
GROUP BY w.warehouse_name, w.city, w.province_code
ORDER BY orders DESC;

-- Q04: provincial delivery performance ------------------------------------------
-- name: province_performance
SELECT
    p.province_code,
    p.province_name,
    p.is_remote,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(CASE WHEN f.on_time = 0 THEN f.days_late END), 2) AS avg_days_late,
    ROUND(AVG(f.shipping_cost), 2)                        AS avg_shipping_cost
FROM fact_orders f
JOIN dim_province p ON p.province_code = f.province_code
GROUP BY p.province_code, p.province_name, p.is_remote
ORDER BY late_rate_pct DESC;

-- Q05: shipping cost and reliability by ship mode --------------------------------
-- name: ship_mode
SELECT
    m.mode_name,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(f.shipping_cost), 2)                        AS avg_shipping_cost,
    ROUND(SUM(f.shipping_cost), 0)                        AS total_shipping_cost
FROM fact_orders f
JOIN dim_ship_mode m ON m.mode_id = f.mode_id
GROUP BY m.mode_name
ORDER BY avg_shipping_cost;

-- Q06: monthly trend --------------------------------------------------------------
-- name: monthly_trend
SELECT
    d.year,
    d.month,
    d.month_name || ' ' || d.year                         AS period,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(100.0 * SUM(f.on_time) / COUNT(*), 2)           AS on_time_pct,
    ROUND(AVG(f.shipping_cost), 2)                        AS avg_shipping_cost
FROM fact_orders f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Q07: winter vs non-winter ----------------------------------------------------------
-- name: winter_effect
SELECT
    CASE WHEN d.is_winter = 1 THEN 'Winter (Dec-Feb)' ELSE 'Rest of year' END AS season,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(CASE WHEN f.on_time = 0 THEN f.days_late END), 2) AS avg_days_late
FROM fact_orders f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.is_winter;

-- Q08: order accuracy breakdown -----------------------------------------------------------
-- name: accuracy_breakdown
SELECT
    accuracy_status,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)     AS pct_of_orders
FROM fact_orders
GROUP BY accuracy_status
ORDER BY orders DESC;

-- Q09: March 2025 disruption vs baseline --------------------------------------------------
-- name: disruption
SELECT
    CASE WHEN d.year = 2025 AND d.month = 3 THEN 'March 2025 (capacity crunch)'
         ELSE 'All other months' END                      AS period,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(CASE WHEN f.on_time = 0 THEN f.days_late END), 2) AS avg_days_late
FROM fact_orders f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY period;

-- Q10: late-rate by product category ----------------------------------------------------
-- name: category_performance
SELECT
    cat.category_name,
    COUNT(*)                                              AS orders,
    ROUND(100.0 * SUM(1 - f.on_time) / COUNT(*), 2)       AS late_rate_pct,
    ROUND(AVG(f.order_value), 2)                          AS avg_order_value
FROM fact_orders f
JOIN dim_category cat ON cat.category_id = f.category_id
GROUP BY cat.category_name
ORDER BY late_rate_pct DESC;
