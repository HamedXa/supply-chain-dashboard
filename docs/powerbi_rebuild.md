# Rebuilding this dashboard in Power BI Desktop

This guide maps the project's SQLite star schema to a Power BI model and gives
the core DAX measures, so the dashboard can be rebuilt natively in Power BI
(the skill this project is designed to demonstrate for BI Analyst roles).

## 1. Get the data in

1. **Get Data → CSV** → `data/supply_chain_orders.csv`
   (or **Get Data → ODBC/SQLite** → `data/supply_chain.db`, table `fact_orders`
   plus the six `dim_*` tables).
2. In Power Query, split the flat file into the star schema below
   (or import the `dim_*` tables directly from SQLite — they are already clean).

## 2. Model (star schema)

```
dim_date ──────┐
dim_warehouse ─┤
dim_carrier ───┼──► fact_orders
dim_province ──┤
dim_ship_mode ─┤
dim_category ──┘
```

| Power BI table | Source | Key | Relationships |
|---|---|---|---|
| `fact_orders` | CSV / `fact_orders` | `order_id` | — |
| `dim_date` | `dim_date` | `date_key` (YYYY-MM-DD) | 1 → many to `fact_orders[date_key]` |
| `dim_warehouse` | `dim_warehouse` | `warehouse_id` | 1 → many to `fact_orders[warehouse_id]` |
| `dim_carrier` | `dim_carrier` | `carrier_id` | 1 → many to `fact_orders[carrier_id]` |
| `dim_province` | `dim_province` | `province_code` | 1 → many to `fact_orders[province_code]` |
| `dim_ship_mode` | `dim_ship_mode` | `mode_id` | 1 → many to `fact_orders[mode_id]` |
| `dim_category` | `dim_category` | `category_name` | 1 → many to `fact_orders[category_id]`* |

\*If you import from CSV, join on the text column `category`; the SQLite
build already resolves it to `category_id`.

- Mark `dim_date[date_key]` as the date table (Table tools → Mark as Date Table).
- `on_time`, `pickup_on_time`, `is_accurate`, `is_winter`, `is_remote` are
  stored as 1/0 integers — set their data type to Whole Number and, for
  measures, aggregate with `SUM`.

## 3. Core DAX measures

```dax
Total Orders =
COUNTROWS ( fact_orders )

On-Time % =
DIVIDE ( SUM ( fact_orders[on_time] ), [Total Orders] )

Late Rate % =
1 - [On-Time %]

Avg Days Late =
AVERAGEX (
    FILTER ( fact_orders, fact_orders[on_time] = 0 ),
    fact_orders[days_late]
)

Order Accuracy % =
DIVIDE ( SUM ( fact_orders[is_accurate] ), [Total Orders] )

Avg Shipping Cost per Order =
AVERAGE ( fact_orders[shipping_cost] )

Total Shipping Cost =
SUM ( fact_orders[shipping_cost] )

Pickup SLA Compliance % =
DIVIDE ( SUM ( fact_orders[pickup_on_time] ), [Total Orders] )

Avg Pickup Days =
AVERAGE ( fact_orders[pickup_days] )

-- Winter uplift story (Dec–Feb vs rest of year)
Winter Late Rate % =
CALCULATE (
    [Late Rate %],
    dim_date[is_winter] = 1
)

-- March 2025 disruption callout
Mar 2025 Late Rate % =
CALCULATE (
    [Late Rate %],
    dim_date[year] = 2025,
    dim_date[month] = 3
)

-- Carrier ranking: late rate, sorted worst → best
Carrier Late Rank =
RANKX ( ALL ( dim_carrier[carrier_name] ), [Late Rate %], , DESC )
```

## 4. Suggested report pages (mirrors `dashboard/supply_chain_dashboard.html`)

1. **Executive overview** — KPI cards (`On-Time %`, `Late Rate %`,
   `Avg Days Late`, `Order Accuracy %`, `Avg Shipping Cost per Order`,
   `Pickup SLA Compliance %`); line chart of `Late Rate %` by month
   (use `dim_date[period]`); donut of accuracy status.
2. **Carrier scorecard** — clustered bar: `Late Rate %` by carrier with
   `Pickup SLA Compliance %` as a line on a secondary axis; table with
   `Avg Pickup Days` and `Avg Shipping Cost per Order`.
3. **Network & geography** — bar chart of `Late Rate %` by province
   (conditional formatting on `is_remote`); bar chart by warehouse;
   `Avg Shipping Cost per Order` by ship mode.
4. **Findings** — text box with the key findings from
   `reports/kpi_summary.md`; Q&A visual or bookmarks for the
   March-2025 and winter stories.

## 5. Refresh

The dataset is static and synthetic. To regenerate with different parameters,
run `python src/generate_data.py --n 75000 --seed 42` and refresh the
Power BI dataset (same schema, new rows).
