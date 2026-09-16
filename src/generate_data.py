"""Generate synthetic Canadian supply chain order data.

Produces data/supply_chain_orders.csv with ~75,000 orders across 2024-01-01 to
2025-12-31. All data is SYNTHETIC, generated with a fixed seed (42) so output
is fully reproducible. See docs/assumptions.md for every modelling assumption.

Usage:
    python src/generate_data.py [--n 75000] [--seed 42]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ORDERS = 75_000
START = date(2024, 1, 1)
END = date(2025, 12, 31)

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------
WAREHOUSES = {
    "Toronto": {"city": "Toronto", "province": "ON", "region": "Central"},
    "Vancouver": {"city": "Vancouver", "province": "BC", "region": "West"},
    "Calgary": {"city": "Calgary", "province": "AB", "region": "West"},
    "Montreal": {"city": "Montreal", "province": "QC", "region": "Central"},
}

PROVINCES = {
    "ON": {"name": "Ontario", "region": "Central", "remote": False, "weight": 0.32},
    "QC": {"name": "Quebec", "region": "Central", "remote": False, "weight": 0.20},
    "BC": {"name": "British Columbia", "region": "West", "remote": False, "weight": 0.13},
    "AB": {"name": "Alberta", "region": "West", "remote": False, "weight": 0.12},
    "MB": {"name": "Manitoba", "region": "West", "remote": False, "weight": 0.06},
    "SK": {"name": "Saskatchewan", "region": "West", "remote": False, "weight": 0.05},
    "NS": {"name": "Nova Scotia", "region": "Atlantic", "remote": False, "weight": 0.04},
    "NB": {"name": "New Brunswick", "region": "Atlantic", "remote": True, "weight": 0.03},
    "NL": {"name": "Newfoundland and Labrador", "region": "Atlantic", "remote": True, "weight": 0.03},
    "PE": {"name": "Prince Edward Island", "region": "Atlantic", "remote": True, "weight": 0.02},
}

# Carrier mix mirrors a tiered market: two premium, two mid-tier, one budget
# carrier (BudgetHaul) that is systematically slower on pickup.
CARRIERS = {
    "CanParcel": {"tier": "Premium", "weight": 0.28, "late_add": 0.000, "pickup_mean": 0.8},
    "NorthStar Logistics": {"tier": "Premium", "weight": 0.24, "late_add": 0.010, "pickup_mean": 1.0},
    "Maple Freight": {"tier": "Standard", "weight": 0.20, "late_add": 0.025, "pickup_mean": 1.2},
    "Prairie Express": {"tier": "Standard", "weight": 0.16, "late_add": 0.035, "pickup_mean": 1.3},
    "BudgetHaul": {"tier": "Budget", "weight": 0.12, "late_add": 0.075, "pickup_mean": 2.8},
}

SHIP_MODES = {
    "Standard": {"weight": 0.62, "promised_days": 6, "base_cost": 8.50, "late_mult": 1.15},
    "Express": {"weight": 0.23, "promised_days": 3, "base_cost": 21.25, "late_mult": 0.60},
    "Priority": {"weight": 0.15, "promised_days": 2, "base_cost": 15.00, "late_mult": 0.80},
}

CATEGORIES = {
    "Electronics": {"weight": 0.28, "median_value": 120.0},
    "Apparel": {"weight": 0.24, "median_value": 65.0},
    "Home & Kitchen": {"weight": 0.20, "median_value": 80.0},
    "Grocery": {"weight": 0.15, "median_value": 45.0},
    "Health & Personal Care": {"weight": 0.13, "median_value": 50.0},
}

# Monthly volume seasonality (holiday peak in Nov/Dec)
MONTH_MULT = {1: 0.90, 2: 0.90, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.00,
              7: 1.00, 8: 1.00, 9: 1.05, 10: 1.10, 11: 1.35, 12: 1.50}

WINTER_MONTHS = {12, 1, 2}
PICKUP_SLA_DAYS = 2  # carrier must pick up within 2 days of order date

# Nearest-warehouse fulfilment probabilities: {dest_province: [(warehouse, p), ...]}
WAREHOUSE_MIX = {
    "ON": [("Toronto", 0.85), ("Montreal", 0.15)],
    "QC": [("Montreal", 0.85), ("Toronto", 0.15)],
    "BC": [("Vancouver", 1.00)],
    "AB": [("Calgary", 0.80), ("Vancouver", 0.20)],
    "MB": [("Calgary", 0.70), ("Toronto", 0.30)],
    "SK": [("Calgary", 0.70), ("Toronto", 0.30)],
    "NS": [("Montreal", 0.70), ("Toronto", 0.30)],
    "NB": [("Montreal", 0.70), ("Toronto", 0.30)],
    "PE": [("Montreal", 0.70), ("Toronto", 0.30)],
    "NL": [("Montreal", 0.70), ("Toronto", 0.30)],
}


def _choose(rng: np.random.Generator, options: dict, key: str = "weight") -> np.ndarray:
    names = np.array(list(options))
    probs = np.array([options[n][key] for n in names], dtype=float)
    return rng.choice(names, p=probs / probs.sum())


def distance_factor(warehouse: str, dest_prov: str) -> float:
    """Relative transit difficulty: 1.0 = same province, up to ~1.75 cross-country."""
    wh = WAREHOUSES[warehouse]
    dp = PROVINCES[dest_prov]
    if wh["province"] == dest_prov:
        f = 1.00
    elif wh["region"] == dp["region"]:
        f = 1.25
    else:
        f = 1.60
    if dp["region"] == "Atlantic":
        f += 0.15  # Atlantic Canada adds a leg for every warehouse
    return f


def main(n_orders: int = N_ORDERS, seed: int = SEED) -> Path:
    rng = np.random.default_rng(seed)
    out = Path(__file__).resolve().parent.parent / "data" / "supply_chain_orders.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    # --- order dates: monthly counts with holiday seasonality ----------------
    months = pd.period_range(START, END, freq="M")
    weights = np.array([MONTH_MULT[m.month] for m in months], dtype=float)
    counts = np.floor(n_orders * weights / weights.sum()).astype(int)
    counts[-1] += n_orders - counts.sum()  # fix rounding so total == n_orders

    order_dates: list[date] = []
    for period, c in zip(months, counts):
        month_start = period.start_time.date()
        month_end = period.end_time.date()
        span = (month_end - month_start).days + 1
        order_dates.extend(
            month_start + timedelta(days=int(d))
            for d in rng.integers(0, span, size=c)
        )
    rng.shuffle(order_dates)
    order_dates = order_dates[:n_orders]

    # --- dimensions ----------------------------------------------------------
    provinces = _choose(rng, PROVINCES)
    provinces = rng.choice(
        list(PROVINCES), size=n_orders,
        p=np.array([PROVINCES[p]["weight"] for p in PROVINCES]),
    )
    warehouses = np.array([
        rng.choice([w for w, _ in WAREHOUSE_MIX[pv]],
                   p=[pr for _, pr in WAREHOUSE_MIX[pv]])
        for pv in provinces
    ])
    carriers = _choose(rng, CARRIERS)
    carriers = rng.choice(
        list(CARRIERS), size=n_orders,
        p=np.array([CARRIERS[c]["weight"] for c in CARRIERS]),
    )
    modes = rng.choice(
        list(SHIP_MODES), size=n_orders,
        p=np.array([SHIP_MODES[m]["weight"] for m in SHIP_MODES]),
    )
    categories = rng.choice(
        list(CATEGORIES), size=n_orders,
        p=np.array([CATEGORIES[c]["weight"] for c in CATEGORIES]),
    )

    # --- order value (lognormal around category median) ----------------------
    medians = np.array([CATEGORIES[c]["median_value"] for c in categories])
    order_value = np.round(medians * rng.lognormal(0, 0.55, n_orders), 2)
    order_value = np.clip(order_value, 5.0, 2500.0)

    # --- pickup performance (BudgetHaul systematically slower) ----------------
    pickup_mean = np.array([CARRIERS[c]["pickup_mean"] for c in carriers])
    pickup_days = np.maximum(
        0, np.round(pickup_mean + rng.exponential(0.9, n_orders) - 0.45)
    ).astype(int)
    pickup_on_time = pickup_days <= PICKUP_SLA_DAYS

    # --- late-delivery probability: baked-in, discoverable patterns -----------
    is_winter = np.array([d.month in WINTER_MONTHS for d in order_dates])
    is_remote = np.array([PROVINCES[p]["remote"] for p in provinces])
    is_march_2025 = np.array([(d.year, d.month) == (2025, 3) for d in order_dates])
    dist = np.array([distance_factor(w, p) for w, p in zip(warehouses, provinces)])
    carrier_add = np.array([CARRIERS[c]["late_add"] for c in carriers])
    mode_mult = np.array([SHIP_MODES[m]["late_mult"] for m in modes])

    p_late = (
        0.030
        + 0.060 * is_winter          # winter storms slow the network
        + 0.050 * is_remote          # distance to NL / PE / NB
        + 0.030 * (dist >= 1.60)     # cross-country legs
        + 0.120 * is_march_2025      # March 2025 carrier capacity crunch
        + carrier_add                # carrier tier effect (BudgetHaul worst)
        + 0.015 * (~pickup_on_time)  # missed pickup SLA compounds downstream
    ) * mode_mult                    # Express/Priority get priority handling
    p_late = np.clip(p_late, 0.005, 0.60)

    is_late = rng.random(n_orders) < p_late

    # --- days late ------------------------------------------------------------
    days_late = np.zeros(n_orders, dtype=int)
    late_idx = np.where(is_late)[0]
    base_late = 1 + rng.exponential(2.5, late_idx.size)
    # BudgetHaul late orders drag longer (slow pickup cascades)
    base_late += (carriers[late_idx] == "BudgetHaul").astype(float) * 1.5
    # March 2025 crunch: backlog means longer delays
    base_late += is_march_2025[late_idx].astype(float) * 2.0
    days_late[late_idx] = np.minimum(np.round(base_late), 30).astype(int)

    # --- promised vs actual delivery ------------------------------------------
    promised_days = np.array([SHIP_MODES[m]["promised_days"] for m in modes])
    promised = np.array([
        d + timedelta(days=int(pd_)) for d, pd_ in zip(order_dates, promised_days)
    ])
    early = rng.integers(0, 3, n_orders)  # on-time orders often arrive early
    actual = np.array([
        (p + timedelta(days=int(dl))) if late else (p - timedelta(days=int(e)))
        for p, dl, late, e in zip(promised, days_late, is_late, early)
    ])

    # --- order accuracy --------------------------------------------------------
    # Base 97.5% accurate; BudgetHaul damages more; winter damages more.
    p_damaged = 0.012 + 0.008 * (carriers == "BudgetHaul") + 0.005 * is_winter
    p_substitution = 0.010
    p_missing = 0.004
    roll = rng.random(n_orders)
    accuracy = np.where(
        roll < p_damaged, "damaged",
        np.where(roll < p_damaged + p_substitution, "substitution",
                 np.where(roll < p_damaged + p_substitution + p_missing,
                          "missing item", "accurate")),
    )

    # --- shipping cost: Express ~2.5x Standard; distance and value add ---------
    mode_base = np.array([SHIP_MODES[m]["base_cost"] for m in modes])
    shipping_cost = np.round(
        mode_base * dist * (0.85 + 0.30 * rng.random(n_orders))
        + order_value * 0.01,
        2,
    )

    df = pd.DataFrame({
        "order_id": [f"ORD-{i:06d}" for i in range(1, n_orders + 1)],
        "order_date": [d.isoformat() for d in order_dates],
        "warehouse": warehouses,
        "carrier": carriers,
        "dest_province": provinces,
        "ship_mode": modes,
        "category": categories,
        "order_value": np.round(order_value, 2),
        "pickup_date": [(d + timedelta(days=int(p))).isoformat()
                        for d, p in zip(order_dates, pickup_days)],
        "pickup_days": pickup_days,
        "pickup_on_time": pickup_on_time,
        "promised_delivery_date": [p_.isoformat() for p_ in promised],
        "actual_delivery_date": [a.isoformat() for a in actual],
        "on_time": ~is_late,
        "days_late": days_late,
        "accuracy_status": accuracy,
        "shipping_cost": shipping_cost,
    })
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} synthetic orders -> {out}")
    print(f"  On-time rate: {(~is_late).mean():.2%} | "
          f"Accuracy: {(accuracy == 'accurate').mean():.2%} | "
          f"Avg shipping cost: ${shipping_cost.mean():.2f}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_ORDERS)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    main(n_orders=args.n, seed=args.seed)
