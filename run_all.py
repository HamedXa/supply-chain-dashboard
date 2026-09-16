"""Run the full supply-chain analytics pipeline with one command.

Steps:
    1. src/generate_data.py   -> data/supply_chain_orders.csv (seed 42)
    2. src/build_database.py  -> data/supply_chain.db (star schema)
    3. src/compute_kpis.py    -> reports/kpi_summary.md
    4. src/build_dashboard.py -> dashboard/supply_chain_dashboard.html

Usage:
    python run_all.py
"""

from __future__ import annotations

import runpy
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"


def main() -> None:
    for script in ["generate_data.py", "build_database.py",
                   "compute_kpis.py", "build_dashboard.py"]:
        print(f"\n{'=' * 60}\n>>> {script}\n{'=' * 60}")
        runpy.run_path(str(SRC / script), run_name="__main__")
    print("\nPipeline complete. Open dashboard/supply_chain_dashboard.html")


if __name__ == "__main__":
    main()
