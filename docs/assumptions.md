# Data-generating assumptions

> **All data in this project is synthetic.** Every order below was produced by
> `src/generate_data.py` with a fixed random seed (`42`), so the dataset is
> fully reproducible. No real company, carrier, or customer is represented —
> carrier names are fictional. This document records every modelling choice so
> the analysis can be interpreted (and challenged) honestly.

## Scope

- **75,000 orders** over **2024-01-01 → 2025-12-31** (24 months).
- Grain: one row per order. No line-item detail; each order is treated as a
  single shipment.
- Currency: Canadian dollars (CAD).

## Order volume & timing

- Monthly order counts follow a fixed holiday seasonality curve
  (multipliers: Jan 0.90, Feb 0.90, Mar 1.00, Apr 1.00, May 1.05, Jun 1.00,
  Jul 1.00, Aug 1.00, Sep 1.05, Oct 1.10, Nov 1.35, Dec 1.50), normalised to
  exactly 75,000 orders. December is the peak month; January/February the trough.
- Within a month, order dates are uniformly distributed across days.

## Geography

- **Warehouses (4):** Toronto ON, Vancouver BC, Calgary AB, Montreal QC.
- **Destination provinces (10):** ON, QC, BC, AB, MB, SK, NS, NB, NL, PE with
  population-skewed weights (ON 32% … PE 2%).
- **Fulfilment logic:** each order ships from the nearest warehouse with fixed
  probabilities (e.g. ON → Toronto 85% / Montreal 15%; Atlantic provinces →
  Montreal 70% / Toronto 30%).
- **Distance factor** is a regional heuristic, not real kilometres:
  same province = 1.00, same region = 1.25, cross-region = 1.60, plus +0.15 for
  any Atlantic destination. It scales shipping cost and adds delay risk.

## Carriers (fictional names)

| Carrier | Tier | Share | Extra late-risk | Mean pickup days |
|---|---|---|---|---|
| CanParcel | Premium | 28% | +0.0 pp | 0.8 |
| NorthStar Logistics | Premium | 24% | +1.0 pp | 1.0 |
| Maple Freight | Standard | 20% | +2.5 pp | 1.2 |
| Prairie Express | Standard | 16% | +3.5 pp | 1.3 |
| BudgetHaul | Budget | 12% | +7.5 pp | 2.8 |

- Pickup time = tier mean + Exponential(0.9) − 0.45 days, floored at 0.
  BudgetHaul is **systematically slower on pickup** by design.
- **Pickup SLA = 2 days** (carrier must collect within 2 days of order date).

## Ship modes

| Mode | Share | Promised days | Base cost | Late-risk multiplier |
|---|---|---|---|---|
| Standard | 62% | 6 | $8.50 | 1.15× |
| Express | 23% | 3 | $21.25 (~2.5× Standard) | 0.60× |
| Priority | 15% | 2 | $15.00 | 0.80× |

Express gets priority handling (lower delay risk) at ~2.5× the base cost of
Standard — the classic speed/cost trade-off under test.

## Product categories & order value

- Mix: Electronics 28%, Apparel 24%, Home & Kitchen 20%, Grocery 15%,
  Health & Personal Care 13%.
- Order value = category median ($45–$120) × Lognormal(0, 0.55), clipped to
  $5–$2,500. Value influences shipping cost slightly (+1% of value).

## Late-delivery model (the baked-in, discoverable patterns)

Late probability per order (additive, clipped to [0.5%, 60%]):

- Base: **3.0%**
- **Winter (Dec–Feb): +6.0 pp** — winter storms slow the network.
- **Remote provinces (NL, PE, NB): +5.0 pp** — distance effect.
- **Cross-country leg (distance factor ≥ 1.60): +3.0 pp.**
- **March 2025: +12.0 pp** — a simulated carrier capacity crunch
  (backlog event) that spikes late rates for one month.
- **Carrier tier effect:** +0 to +7.5 pp (see carrier table).
- **Missed pickup SLA: +1.5 pp** — slow pickup cascades downstream.
- All multiplied by the ship-mode factor (Express 0.60×, Priority 0.80×,
  Standard 1.15×).

Days late (when late) = 1 + Exponential(2.5), plus **+1.5 for BudgetHaul**
and **+2.0 in March 2025**, capped at 30 days, rounded to whole days.

Delivery dates: `actual = promised + days_late` when late; on-time orders
arrive on or up to 2 days before the promised date.

## Order accuracy

- Accurate: ~97.5% baseline.
- Damaged: 1.2% base, +0.8 pp for BudgetHaul, +0.5 pp in winter.
- Substitution: 1.0%. Missing item: 0.4%.

## Shipping cost

`cost = mode_base × distance_factor × U(0.85, 1.15) + 1% of order value`,
rounded to cents.

## Known limitations

1. Synthetic — patterns above are *designed in*, so the analysis
   demonstrates method, not discovery of real-world truth.
2. Carrier names are fictional; any resemblance to real firms is coincidental.
3. Distance is a coarse regional heuristic, not road/rail kilometres.
4. One disruption event only (March 2025); real networks face many.
5. No returns, cancellations, or multi-shipment orders are modelled.
6. Costs are illustrative and exclude fuel surcharges, dimensional weight,
   and accessorial fees.
