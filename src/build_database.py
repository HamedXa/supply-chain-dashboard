"""Build a clean star-schema SQLite database from the generated CSV.

Schema:
    dim_date        - one row per calendar date (2024-01-01 .. 2025-12-31)
    dim_warehouse   - 4 Canadian warehouses
    dim_carrier     - 5 carriers with service tier
    dim_province    - 10 destination provinces (region, remote flag)
    dim_ship_mode   - Standard / Express / Priority (promised days, base cost)
    dim_category    - 5 product categories
    fact_orders     - one row per order, foreign keys into the dimensions

Usage:
    python src/build_database.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
CSV = BASE / "data" / "supply_chain_orders.csv"
DB = BASE / "data" / "supply_chain.db"

WAREHOUSES = [
    ("Toronto", "Toronto", "ON", "Central"),
    ("Vancouver", "Vancouver", "BC", "West"),
    ("Calgary", "Calgary", "AB", "West"),
    ("Montreal", "Montreal", "QC", "Central"),
]
CARRIERS = [
    ("CanParcel", "Premium"),
    ("NorthStar Logistics", "Premium"),
    ("Maple Freight", "Standard"),
    ("Prairie Express", "Standard"),
    ("BudgetHaul", "Budget"),
]
PROVINCES = [
    ("ON", "Ontario", "Central", 0), ("QC", "Quebec", "Central", 0),
    ("BC", "British Columbia", "West", 0), ("AB", "Alberta", "West", 0),
    ("MB", "Manitoba", "West", 0), ("SK", "Saskatchewan", "West", 0),
    ("NS", "Nova Scotia", "Atlantic", 0), ("NB", "New Brunswick", "Atlantic", 1),
    ("NL", "Newfoundland and Labrador", "Atlantic", 1),
    ("PE", "Prince Edward Island", "Atlantic", 1),
]
SHIP_MODES = [
    ("Standard", 6, 8.50), ("Express", 3, 21.25), ("Priority", 2, 15.00),
]
CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Grocery",
              "Health & Personal Care"]


def main() -> Path:
    df = pd.read_csv(CSV)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE dim_date (
            date_key        TEXT PRIMARY KEY,   -- YYYY-MM-DD
            year            INTEGER NOT NULL,
            quarter         INTEGER NOT NULL,
            month           INTEGER NOT NULL,
            month_name      TEXT NOT NULL,
            is_winter       INTEGER NOT NULL    -- 1 for Dec/Jan/Feb
        );
        CREATE TABLE dim_warehouse (
            warehouse_id    INTEGER PRIMARY KEY,
            warehouse_name  TEXT UNIQUE NOT NULL,
            city            TEXT NOT NULL,
            province_code   TEXT NOT NULL,
            region          TEXT NOT NULL
        );
        CREATE TABLE dim_carrier (
            carrier_id      INTEGER PRIMARY KEY,
            carrier_name    TEXT UNIQUE NOT NULL,
            tier            TEXT NOT NULL
        );
        CREATE TABLE dim_province (
            province_code   TEXT PRIMARY KEY,
            province_name   TEXT NOT NULL,
            region          TEXT NOT NULL,
            is_remote       INTEGER NOT NULL
        );
        CREATE TABLE dim_ship_mode (
            mode_id         INTEGER PRIMARY KEY,
            mode_name       TEXT UNIQUE NOT NULL,
            promised_days   INTEGER NOT NULL,
            base_cost       REAL NOT NULL
        );
        CREATE TABLE dim_category (
            category_id     INTEGER PRIMARY KEY,
            category_name   TEXT UNIQUE NOT NULL
        );
        CREATE TABLE fact_orders (
            order_id               TEXT PRIMARY KEY,
            date_key               TEXT NOT NULL REFERENCES dim_date(date_key),
            warehouse_id           INTEGER NOT NULL REFERENCES dim_warehouse(warehouse_id),
            carrier_id             INTEGER NOT NULL REFERENCES dim_carrier(carrier_id),
            province_code          TEXT NOT NULL REFERENCES dim_province(province_code),
            mode_id                INTEGER NOT NULL REFERENCES dim_ship_mode(mode_id),
            category_id            INTEGER NOT NULL REFERENCES dim_category(category_id),
            order_value            REAL NOT NULL,
            pickup_date            TEXT NOT NULL,
            pickup_days            INTEGER NOT NULL,
            pickup_on_time         INTEGER NOT NULL,   -- 1 = picked up within SLA
            promised_delivery_date TEXT NOT NULL,
            actual_delivery_date   TEXT NOT NULL,
            on_time                INTEGER NOT NULL,   -- 1 = delivered on/before promise
            days_late              INTEGER NOT NULL,
            accuracy_status        TEXT NOT NULL,
            is_accurate            INTEGER NOT NULL,
            shipping_cost          REAL NOT NULL
        );
        CREATE INDEX idx_fact_date ON fact_orders(date_key);
        CREATE INDEX idx_fact_carrier ON fact_orders(carrier_id);
        CREATE INDEX idx_fact_warehouse ON fact_orders(warehouse_id);
        CREATE INDEX idx_fact_province ON fact_orders(province_code);
    """)

    # --- dimensions ------------------------------------------------------
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    cur.executemany(
        "INSERT INTO dim_date VALUES (?,?,?,?,?,?)",
        [(d.strftime("%Y-%m-%d"), d.year, (d.month - 1) // 3 + 1, d.month,
          month_names[d.month - 1], int(d.month in (12, 1, 2))) for d in dates],
    )
    cur.executemany(
        "INSERT INTO dim_warehouse (warehouse_name, city, province_code, region)"
        " VALUES (?,?,?,?)", WAREHOUSES)
    cur.executemany(
        "INSERT INTO dim_carrier (carrier_name, tier) VALUES (?,?)", CARRIERS)
    cur.executemany(
        "INSERT INTO dim_province VALUES (?,?,?,?)", PROVINCES)
    cur.executemany(
        "INSERT INTO dim_ship_mode (mode_name, promised_days, base_cost)"
        " VALUES (?,?,?)", SHIP_MODES)
    cur.executemany(
        "INSERT INTO dim_category (category_name) VALUES (?)",
        [(c,) for c in CATEGORIES])

    # --- facts -------------------------------------------------------------
    w_id = {r[0]: i + 1 for i, r in enumerate(
        cur.execute("SELECT warehouse_name FROM dim_warehouse ORDER BY warehouse_id"))}
    c_id = {r[0]: i + 1 for i, r in enumerate(
        cur.execute("SELECT carrier_name FROM dim_carrier ORDER BY carrier_id"))}
    m_id = {r[0]: i + 1 for i, r in enumerate(
        cur.execute("SELECT mode_name FROM dim_ship_mode ORDER BY mode_id"))}
    cat_id = {r[0]: i + 1 for i, r in enumerate(
        cur.execute("SELECT category_name FROM dim_category ORDER BY category_id"))}

    rows = [(
        r.order_id, r.order_date,
        w_id[r.warehouse], c_id[r.carrier], r.dest_province,
        m_id[r.ship_mode], cat_id[r.category],
        float(r.order_value), r.pickup_date, int(r.pickup_days),
        int(bool(r.pickup_on_time)), r.promised_delivery_date,
        r.actual_delivery_date, int(bool(r.on_time)), int(r.days_late),
        r.accuracy_status, int(r.accuracy_status == "accurate"),
        float(r.shipping_cost),
    ) for r in df.itertuples()]
    cur.executemany(
        """INSERT INTO fact_orders VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    con.commit()

    n = cur.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    con.close()
    print(f"Built {DB} with {n:,} fact rows + 6 dimensions")
    return DB


if __name__ == "__main__":
    main()
