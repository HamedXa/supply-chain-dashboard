# Supply Chain Analytics Dashboard

> **About the data:** I generated all 75,000 orders myself with a Python script (fixed seed, so it's reproducible). The carriers are fictional. Nothing here is real company data. The project is about the analytics work.

I wanted a portfolio project that feels like real operations analytics: raw orders go in, a KPI pipeline does the math, and a dashboard comes out that a logistics manager could actually read. So I built one around a fictional Canadian e-commerce supply chain. 75,000 orders, two years (Jan 2024 - Dec 2025), four warehouses, five carriers, ten provinces.

**Bottom line:** 92.0% on-time · 8.0% late (about 4 days late on average) · 97.2% order accuracy · $15.25 shipping cost per order.

## What I measured
| KPI | How I defined it |
|---|---|
| On-time delivery % | Orders delivered on or before the promised date |
| Late rate | Everything not on time |
| Avg days late | Average delay, late orders only |
| Order accuracy % | Orders with no substitution, damage, or missing item |
| Shipping cost per order | Average shipping cost (CAD) |
| Pickup SLA compliance | % of orders picked up within 2 days |
| Warehouse throughput | Orders fulfilled per warehouse |

## What the data showed
1. **One carrier is dragging the network down.** BudgetHaul (fictional) was late 13.98% of the time, 2.4x the best carrier, and only picked up on time 15.66% of the time vs 79.00% network-wide. Slow pickup turns into late delivery.
2. **Winter is brutal.** Dec-Feb ran 11.72% late vs 6.71% the rest of the year. December is the highest-volume month and the worst-performing one.
3. **March 2025 was the worst month in the dataset.** 17.44% late, 5.59 days late on average. That was a capacity crunch, not weather.
4. **The Atlantic provinces get the worst of it.** NL (16.24%), PE (16.25%), NB (15.29%) run about 2x the network late rate while costing ~$22.70 per order to ship, vs ~$13-14 in BC/ON/QC.
5. **Express is worth it when it matters.** $25.48 per order (2.37x Standard's $10.75) but a 4.93% late rate vs 9.46%. Roughly half the failures.
6. **Accuracy is solid at 97.15%.** Damage (1.51%) is the biggest issue, then substitutions (0.95%), then missing items (0.40%).
7. **Warehouses are close, but Vancouver leads** (6.86% late) and Montreal trails (8.89%). Toronto handles the most volume (27,887 orders).

Every number above comes from `reports/kpi_summary.md`, which the pipeline generates.

## What I'd do about it
1. **Fix the BudgetHaul problem.** Enforce the 2-day pickup SLA with penalties, or move volume to better carriers. 15.66% pickup compliance is the clearest lever in the data.
2. **Plan for winter.** Pad promised dates and lock in linehaul capacity for Dec-Feb instead of getting surprised every year.
3. **Be honest about Atlantic service levels.** 2x the late rate at 1.7x the cost means the SLA, the capacity, or the promise needs to change.
4. **Keep a backup plan for disruptions.** March 2025 is what happens without one.
5. **Use Express on purpose.** Time-sensitive orders go Express, everything else goes Standard.
6. **Look into the damage rate.** 1.51% of orders arriving damaged is a packaging and handling conversation.

## How it's built
| Layer | Tools |
|---|---|
| Data | Python (NumPy, pandas), generated with seed 42 |
| Storage | SQLite, star schema |
| KPIs | SQL (`sql/kpi_queries.sql`) + Python |
| Dashboard | Plotly. One self-contained HTML file, opens in any browser. |

## Project structure
```
supply-chain-dashboard/
├── README.md
├── requirements.txt
├── .gitignore
├── run_all.py
├── src/
│   ├── __init__.py
│   ├── generate_data.py
│   ├── build_database.py
│   ├── compute_kpis.py
│   └── build_dashboard.py
├── sql/
│   └── kpi_queries.sql
├── dashboard/
│   ├── supply_chain_dashboard.html
│   └── screenshots/
├── reports/
│   └── kpi_summary.md
├── docs/
│   ├── assumptions.md
│   └── powerbi_rebuild.md
└── data/
    ├── supply_chain_orders.csv
    └── supply_chain.db
```

## Run it yourself
```bash
pip install -r requirements.txt
python run_all.py
```
That regenerates the data, rebuilds the database, recomputes every KPI, and re-renders the dashboard. Same seed, same numbers, every time. Then open `dashboard/supply_chain_dashboard.html`. No server needed.

There's also `docs/powerbi_rebuild.md` with the star schema and DAX measures if you'd rather rebuild the dashboard in Power BI Desktop.

## Data
`data/supply_chain_orders.csv` holds the 75,000 synthetic orders. Column meanings and every assumption behind the data are in `docs/assumptions.md`.

## Author
Hamed Sharafeldin — [LinkedIn](https://www.linkedin.com/in/hamed-sharafeldin-821273203/) · [GitHub](https://github.com/HamedXa)
