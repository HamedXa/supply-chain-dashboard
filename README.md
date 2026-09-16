# Supply Chain Analytics Dashboard — Canadian Operations Monitoring

> **Synthetic data.** Every order in this project was generated with a fixed
> random seed (`seed = 42`) by `src/generate_data.py`. No real company,
> carrier, or customer is represented — carrier names are fictional. The
> dataset exists to demonstrate end-to-end analytics craft: data modelling,
> KPI engineering, and executive dashboarding.

An end-to-end analytics project monitoring a fictional Canadian e-commerce
supply chain: **75,000 orders** across 24 months (Jan 2024 – Dec 2025), four
warehouses, five carriers, and ten provinces. It answers the questions an
operations leadership team actually asks: *Where are deliveries failing? Which
carriers are worth their cost? What is the winter plan?*

**Headline results:** 92.0% on-time delivery · 8.0% late (avg 4.0 days late) ·
97.2% order accuracy · $15.25 average shipping cost per order.

## Business problem

The logistics team lacked a single view of delivery performance. Carrier
choices were made on price alone, winter slowdowns arrived as a surprise every
year, and nobody could quantify what the March 2025 capacity crunch actually
cost in service terms. This project builds that view: a reproducible KPI
pipeline plus an executive dashboard.

**Stakeholders:** VP Operations, Logistics/Transportation Manager, Carrier
Relations, Finance (freight spend).

## KPI definitions

| KPI | Definition |
|---|---|
| On-time delivery % | Orders delivered on/before the promised date ÷ all orders |
| Late rate % | 1 − on-time % |
| Avg days late | Mean `days_late` across late orders only |
| Order accuracy % | Orders with no substitution, damage, or missing item ÷ all orders |
| Shipping cost per order | Mean `shipping_cost` (CAD) |
| Pickup SLA compliance % | Orders picked up by the carrier within 2 days of order date ÷ all orders |
| Warehouse throughput | Order count fulfilled per warehouse |

## Key findings (all computed — see `reports/kpi_summary.md`)

1. **BudgetHaul is the network's weak link.** The budget carrier's late rate
   is **13.98%** — 2.4× the best carrier (CanParcel, 5.89%). Its pickup SLA
   compliance is just **15.66%** against a network average of 79.00%, taking
   3.25 days on average to collect an order. Slow pickup cascades into late
   delivery.
2. **Winter nearly doubles the late rate: 11.72% (Dec–Feb) vs 6.71%** the rest
   of the year. December is both the highest-volume and worst-performing month
   (12.02% late in Dec 2024).
3. **The March 2025 capacity crunch was the worst month in the dataset:**
   17.44% late and 5.59 average days late, vs a 7.62% / 3.86-day baseline —
   a backlog event, not a weather event.
4. **Remote Atlantic provinces pay more and wait longer.** NL (16.24%),
   PE (16.25%), and NB (15.29%) run at roughly 2× the network late rate while
   averaging ~$22.70 in shipping cost per order vs ~$13.40–13.81 in BC/ON/QC.
5. **The speed/cost trade-off is quantified:** Express costs **$25.48/order
   (2.37× Standard's $10.75)** but delivers a **4.93% late rate vs 9.46%** —
   roughly half the failures.
6. **Order accuracy is 97.15%**, with damage (1.51%) the largest failure mode,
   followed by substitutions (0.95%) and missing items (0.40%).
7. **Warehouse spread is narrow but real:** Vancouver is the most reliable
   (6.86% late); Montreal the least (8.89%), while Toronto carries the highest
   throughput (27,887 orders).

## Recommendations

1. **Renegotiate or reduce BudgetHaul volume.** Enforce the 2-day pickup SLA
   with financial penalties, or shift volume to CanParcel/NorthStar. Pickup
   compliance of 15.66% is the single clearest operational lever in the data.
2. **Adopt a winter playbook:** build buffer into promised delivery dates and
   pre-book linehaul capacity for Dec–Feb, when the late rate nearly doubles.
3. **Review the Atlantic service promise:** NL/PE/NB suffer 2× the late rate
   at ~1.7× the shipping cost — adjust SLAs, add regional sort capacity, or
   set expectations explicitly.
4. **Build a disruption contingency plan** from the March 2025 post-mortem:
   backup carrier capacity and proactive customer communication before the
   backlog compounds (delays stretched to 5.59 days).
5. **Codify ship-mode guidance:** Express for time-sensitive/high-value
   orders (half the late rate); Standard for cost-sensitive volume.
6. **Audit packaging and handling:** 1.51% of orders arrive damaged — start
   with winter months and BudgetHaul lanes.

## Tech stack

| Layer | Tools |
|---|---|
| Data generation | Python (NumPy, pandas), fixed seed 42 |
| Warehouse | SQLite — star schema (1 fact, 6 dimensions) |
| KPI layer | SQL (`sql/kpi_queries.sql`), Python (`src/compute_kpis.py`) |
| Dashboard | Plotly — self-contained HTML, no server required |
| Reproducibility | `run_all.py` runs the full pipeline with one command |

## Project structure

```
supply-chain-dashboard/
├── README.md
├── requirements.txt
├── run_all.py                  # one-command pipeline: data → db → KPIs → dashboard
├── src/
│   ├── generate_data.py        # synthetic order generator (seed 42)
│   ├── build_database.py       # CSV → SQLite star schema
│   ├── compute_kpis.py         # runs SQL KPIs → reports/kpi_summary.md
│   └── build_dashboard.py      # renders the Plotly HTML dashboard
├── sql/
│   └── kpi_queries.sql         # 10 named KPI queries
├── data/
│   ├── supply_chain_orders.csv # generated (75,000 rows)
│   └── supply_chain.db         # generated (star schema)
├── reports/
│   └── kpi_summary.md          # generated — every number in this README
├── docs/
│   ├── assumptions.md          # every data-generating assumption, documented
│   └── powerbi_rebuild.md      # star-schema map + DAX measures for Power BI
└── dashboard/
    ├── supply_chain_dashboard.html  # generated — open in any browser
    └── screenshots/                 # PNG exports for this README
```

## How to reproduce

```bash
pip install -r requirements.txt
python run_all.py
```

This regenerates the data, rebuilds the database, recomputes every KPI, and
re-renders the dashboard. Output is deterministic: same seed, same numbers.
Then open `dashboard/supply_chain_dashboard.html` in any browser — no server
needed.

To rebuild the dashboard in Power BI Desktop instead, follow
`docs/powerbi_rebuild.md` (schema map + DAX measures included).

## Data

`data/supply_chain_orders.csv` — 75,000 synthetic orders, 17 columns:
`order_id, order_date, warehouse, carrier, dest_province, ship_mode, category,
order_value, pickup_date, pickup_days, pickup_on_time, promised_delivery_date,
actual_delivery_date, on_time, days_late, accuracy_status, shipping_cost`.

Full column semantics and every modelling assumption: `docs/assumptions.md`.

## Author

Hamed Sharafeldin — Data Analyst ([LinkedIn](https://www.linkedin.com/in/hamed-sharafeldin-821273203/) · [GitHub](https://github.com/HamedXa))
