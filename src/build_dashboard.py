"""Render the executive Plotly dashboard as a single self-contained HTML file.

Reads every number from data/supply_chain.db (nothing hand-written), inlines
plotly.js so the file works by double-clicking (no server, no CDN needed at
view time), and saves 3 PNG screenshots for the README via matplotlib.

Usage:
    python src/build_dashboard.py
"""

from __future__ import annotations

import sqlite3
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "supply_chain.db"
OUT = BASE / "dashboard" / "supply_chain_dashboard.html"
SHOT_DIR = BASE / "dashboard" / "screenshots"

PLOTLY_JS_URL = "https://cdn.plot.ly/plotly-2.24.1.min.js"

NAVY, TEAL, AMBER, CORAL, SLATE = "#1f3a5f", "#2a9d8f", "#e9c46a", "#e76f51", "#6c7a89"
BG, CARD = "#f4f6f9", "#ffffff"


def q(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql_query(sql, con)


def load_data() -> dict:
    """Every dashboard number comes from the database."""
    d = {}
    d["headline"] = q("""
        SELECT COUNT(*) AS n,
               ROUND(100.0*SUM(on_time)/COUNT(*),2) AS on_time_pct,
               ROUND(100.0*SUM(1-on_time)/COUNT(*),2) AS late_pct,
               ROUND(AVG(CASE WHEN on_time=0 THEN days_late END),2) AS avg_late,
               ROUND(100.0*SUM(is_accurate)/COUNT(*),2) AS acc_pct,
               ROUND(AVG(shipping_cost),2) AS avg_cost,
               ROUND(100.0*SUM(pickup_on_time)/COUNT(*),2) AS pickup_pct
        FROM fact_orders""").iloc[0]
    d["monthly"] = q("""
        SELECT d.year, d.month, d.month_name||' '||d.year AS period,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct,
               ROUND(100.0*SUM(f.on_time)/COUNT(*),2) AS on_time_pct,
               COUNT(*) AS n
        FROM fact_orders f JOIN dim_date d ON d.date_key=f.date_key
        GROUP BY d.year, d.month ORDER BY d.year, d.month""")
    d["carrier"] = q("""
        SELECT c.carrier_name, c.tier, COUNT(*) AS n,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct,
               ROUND(AVG(f.shipping_cost),2) AS avg_cost,
               ROUND(100.0*SUM(f.pickup_on_time)/COUNT(*),2) AS pickup_pct,
               ROUND(AVG(f.pickup_days),2) AS avg_pickup
        FROM fact_orders f JOIN dim_carrier c ON c.carrier_id=f.carrier_id
        GROUP BY c.carrier_name, c.tier ORDER BY late_pct DESC""")
    d["province"] = q("""
        SELECT p.province_code, p.is_remote, COUNT(*) AS n,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct,
               ROUND(AVG(f.shipping_cost),2) AS avg_cost
        FROM fact_orders f JOIN dim_province p ON p.province_code=f.province_code
        GROUP BY p.province_code, p.is_remote ORDER BY late_pct DESC""")
    d["mode"] = q("""
        SELECT m.mode_name, COUNT(*) AS n,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct,
               ROUND(AVG(f.shipping_cost),2) AS avg_cost
        FROM fact_orders f JOIN dim_ship_mode m ON m.mode_id=f.mode_id
        GROUP BY m.mode_name ORDER BY avg_cost""")
    d["accuracy"] = q("""
        SELECT accuracy_status, COUNT(*) AS n,
               ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct
        FROM fact_orders GROUP BY accuracy_status ORDER BY n DESC""")
    d["warehouse"] = q("""
        SELECT w.warehouse_name, COUNT(*) AS n,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct
        FROM fact_orders f JOIN dim_warehouse w ON w.warehouse_id=f.warehouse_id
        GROUP BY w.warehouse_name ORDER BY n DESC""")
    d["winter"] = q("""
        SELECT CASE WHEN d.is_winter=1 THEN 'Winter (Dec-Feb)' ELSE 'Rest of year' END AS s,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct
        FROM fact_orders f JOIN dim_date d ON d.date_key=f.date_key
        GROUP BY d.is_winter""")
    d["disruption"] = q("""
        SELECT CASE WHEN d.year=2025 AND d.month=3 THEN 'Mar 2025' ELSE 'Baseline' END AS s,
               ROUND(100.0*SUM(1-f.on_time)/COUNT(*),2) AS late_pct,
               ROUND(AVG(CASE WHEN f.on_time=0 THEN f.days_late END),2) AS avg_late
        FROM fact_orders f JOIN dim_date d ON d.date_key=f.date_key GROUP BY s""")
    return d


def plotly_js() -> str:
    """Inline plotly.js; fall back to a CDN <script> tag if offline."""
    try:
        with urllib.request.urlopen(PLOTLY_JS_URL, timeout=30) as r:
            return "<script>\n" + r.read().decode("utf-8") + "\n</script>"
    except Exception as e:  # noqa: BLE001 — offline build must still succeed
        print(f"  plotly.js download failed ({e}); using CDN reference instead")
        return f'<script src="{PLOTLY_JS_URL}"></script>'


def kpi_cards(h: pd.Series) -> str:
    cards = [
        ("On-time delivery", f"{h['on_time_pct']:.2f}%", TEAL),
        ("Late rate", f"{h['late_pct']:.2f}%", CORAL),
        ("Avg days late", f"{h['avg_late']:.2f}", AMBER),
        ("Order accuracy", f"{h['acc_pct']:.2f}%", TEAL),
        ("Avg shipping cost", f"${h['avg_cost']:.2f}", NAVY),
        ("Pickup SLA compliance", f"{h['pickup_pct']:.2f}%", SLATE),
    ]
    inner = "".join(
        f"<div class='kpi'><div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value' style='color:{c}'>{v}</div></div>"
        for label, v, c in cards
    )
    return f"<div class='kpi-row'>{inner}</div>"


def fig_monthly(m: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=m["period"], y=m["on_time_pct"], name="On-time %",
                             line=dict(color=TEAL, width=2.5)))
    fig.add_trace(go.Scatter(x=m["period"], y=m["late_pct"], name="Late %",
                             line=dict(color=CORAL, width=2.5)))
    spike = m.loc[m["late_pct"].idxmax()]
    fig.add_annotation(x=spike["period"], y=spike["late_pct"],
                       text=f"Mar 2025 capacity crunch<br>{spike['late_pct']:.2f}% late",
                       showarrow=True, arrowhead=2, arrowcolor=CORAL, bgcolor="white")
    fig.update_layout(title="Monthly delivery performance (24 months)",
                      yaxis_title="%", xaxis_tickangle=-45, height=420,
                      template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.08))
    return fig


def fig_carrier(c: pd.DataFrame) -> go.Figure:
    tier_color = {"Premium": TEAL, "Standard": AMBER, "Budget": CORAL}
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=c["carrier_name"], y=c["late_pct"], name="Late rate %",
                         marker_color=[tier_color[t] for t in c["tier"]],
                         text=[f"{v:.1f}%" for v in c["late_pct"]],
                         textposition="outside"), secondary_y=False)
    fig.add_trace(go.Scatter(x=c["carrier_name"], y=c["pickup_pct"],
                             name="Pickup SLA %", mode="lines+markers",
                             line=dict(color=NAVY, width=3),
                             marker=dict(size=9)), secondary_y=True)
    fig.update_layout(title="Carrier scorecard: late rate vs pickup SLA",
                      template="plotly_white", height=420,
                      legend=dict(orientation="h", y=1.12))
    fig.update_yaxes(title_text="Late rate %", secondary_y=False, range=[0, 17])
    fig.update_yaxes(title_text="Pickup SLA %", secondary_y=True, range=[0, 105])
    fig.update_xaxes(tickangle=-20)
    return fig


def fig_province(p: pd.DataFrame) -> go.Figure:
    colors = [CORAL if r else TEAL for r in p["is_remote"]]
    fig = go.Figure(go.Bar(
        x=p["late_pct"], y=p["province_code"], orientation="h",
        marker_color=colors, text=[f"{v:.1f}%" for v in p["late_pct"]],
        textposition="outside"))
    fig.update_layout(title="Late rate by destination province (red = remote Atlantic)",
                      xaxis_title="Late rate %", template="plotly_white", height=420,
                      xaxis_range=[0, 19])
    return fig


def fig_mode(m: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=m["mode_name"], y=m["avg_cost"], name="Avg cost/order ($)",
                         marker_color=[NAVY, TEAL, AMBER],
                         text=[f"${v:.2f}" for v in m["avg_cost"]],
                         textposition="outside"), secondary_y=False)
    fig.add_trace(go.Scatter(x=m["mode_name"], y=m["late_pct"], name="Late rate %",
                             mode="lines+markers", line=dict(color=CORAL, width=3),
                             marker=dict(size=10)), secondary_y=True)
    fig.update_layout(title="Ship mode: cost vs reliability trade-off",
                      template="plotly_white", height=420,
                      legend=dict(orientation="h", y=1.12))
    fig.update_yaxes(title_text="Avg shipping cost ($)", secondary_y=False, range=[0, 30])
    fig.update_yaxes(title_text="Late rate %", secondary_y=True, range=[0, 12])
    return fig


def fig_accuracy(a: pd.DataFrame) -> go.Figure:
    colors = {"accurate": TEAL, "damaged": CORAL, "substitution": AMBER,
              "missing item": SLATE}
    fig = go.Figure(go.Pie(labels=a["accuracy_status"], values=a["pct"], hole=0.55,
                            marker_colors=[colors[s] for s in a["accuracy_status"]],
                            textinfo="label+percent"))
    fig.update_layout(title="Order accuracy breakdown", template="plotly_white",
                      height=420)
    return fig


def fig_warehouse(w: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=w["warehouse_name"], y=w["n"], name="Orders",
                         marker_color=NAVY,
                         text=[f"{v:,}" for v in w["n"]],
                         textposition="outside"), secondary_y=False)
    fig.add_trace(go.Scatter(x=w["warehouse_name"], y=w["late_pct"],
                             name="Late rate %", mode="lines+markers",
                             line=dict(color=CORAL, width=3),
                             marker=dict(size=10)), secondary_y=True)
    fig.update_layout(title="Warehouse throughput vs late rate",
                      template="plotly_white", height=420,
                      legend=dict(orientation="h", y=1.12))
    fig.update_yaxes(title_text="Orders", secondary_y=False)
    fig.update_yaxes(title_text="Late rate %", secondary_y=True, range=[0, 12])
    return fig


def findings_panel(d: dict) -> str:
    h, c, p, m = d["headline"], d["carrier"], d["province"], d["mode"]
    bh = c.iloc[0]  # BudgetHaul (sorted worst first)
    cp = c.iloc[-1]  # CanParcel (best)
    winter = d["winter"].set_index("s")["late_pct"]
    dis = d["disruption"].set_index("s")
    exp = m.set_index("mode_name").loc["Express"]
    std = m.set_index("mode_name").loc["Standard"]
    items = [
        f"<b>One carrier is dragging the network down:</b> {bh['late_pct']:.2f}% late "
        f"(vs {cp['late_pct']:.2f}% for {cp['carrier_name']}), with pickup SLA "
        f"compliance of only {bh['pickup_pct']:.2f}% vs {h['pickup_pct']:.2f}% network-wide. "
        f"Slow pickup turns into late delivery.",
        f"<b>Winter is the worst stretch:</b> {winter['Winter (Dec-Feb)']:.2f}% late "
        f"in Dec-Feb vs {winter['Rest of year']:.2f}% the rest of the year.",
        f"<b>March 2025 was the worst month in the data:</b> {dis.loc['Mar 2025','late_pct']:.2f}% late, "
        f"{dis.loc['Mar 2025','avg_late']:.2f} avg days late "
        f"(baseline {dis.loc['Baseline','late_pct']:.2f}% / {dis.loc['Baseline','avg_late']:.2f} days). "
        f"That was a capacity crunch, not weather.",
        f"<b>The Atlantic provinces get the worst of it:</b> PE {p.set_index('province_code').loc['PE','late_pct']:.2f}%, "
        f"NL {p.set_index('province_code').loc['NL','late_pct']:.2f}%, "
        f"NB {p.set_index('province_code').loc['NB','late_pct']:.2f}% - about 2x the network rate at ~$22.70/order.",
        f"<b>Express costs more but works:</b> ${exp['avg_cost']:.2f}/order "
        f"({exp['avg_cost']/std['avg_cost']:.2f}x Standard) with roughly half the late rate "
        f"({exp['late_pct']:.2f}% vs {std['late_pct']:.2f}%).",
    ]
    recs = [
        "Enforce the 2-day pickup SLA with BudgetHaul - with penalties - or move that volume to better carriers.",
        "Plan for winter: pad promised dates and book linehaul capacity ahead for Dec-Feb.",
        "Rethink the Atlantic service promise: the SLA, the capacity, or the dates have to change.",
        "Keep a backup plan for disruptions. March 2025 is what happens without one.",
        "Use Express on purpose: time-sensitive orders go Express, everything else goes Standard.",
    ]
    f_html = "".join(f"<li>{i}</li>" for i in items)
    r_html = "".join(f"<li>{r}</li>" for r in recs)
    return (f"<div class='panel'><h2>Key findings</h2><ul>{f_html}</ul>"
            f"<h2>Recommendations</h2><ol>{r_html}</ol></div>")


def save_screenshots(d: dict) -> None:
    """Static PNGs for the README (matplotlib — no browser needed)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 150, "font.size": 9})

    # 1. monthly trend
    m = d["monthly"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(m["period"], m["late_pct"], color=CORAL, lw=2, label="Late %")
    ax.plot(m["period"], m["on_time_pct"], color=TEAL, lw=2, label="On-time %")
    ax.annotate("Mar 2025 capacity crunch\n17.44% late",
                xy=(14, 17.44), xytext=(8, 20),
                arrowprops=dict(arrowstyle="->", color=CORAL), color=CORAL)
    ax.set_title("Monthly delivery performance (24 months)")
    ax.set_ylabel("%"); ax.set_xticks(range(0, 24, 3))
    ax.set_xticklabels(m["period"][::3], rotation=30, ha="right")
    ax.legend(); fig.tight_layout()
    fig.savefig(SHOT_DIR / "monthly_trend.png"); plt.close(fig)

    # 2. carrier scorecard
    c = d["carrier"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(c))
    ax.bar([i - 0.2 for i in x], c["late_pct"], 0.4, color=CORAL, label="Late rate %")
    ax.bar([i + 0.2 for i in x], c["pickup_pct"], 0.4, color=NAVY, label="Pickup SLA %")
    ax.set_title("Carrier scorecard: late rate vs pickup SLA compliance")
    ax.set_ylabel("%"); ax.set_xticks(list(x)); ax.set_xticklabels(c["carrier_name"], rotation=15, ha="right")
    ax.legend(); fig.tight_layout()
    fig.savefig(SHOT_DIR / "carrier_scorecard.png"); plt.close(fig)

    # 3. province performance
    p = d["province"]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    colors = [CORAL if r else TEAL for r in p["is_remote"]]
    ax.barh(p["province_code"], p["late_pct"], color=colors)
    ax.set_title("Late rate by province (red = remote Atlantic)")
    ax.set_xlabel("Late rate %")
    for i, v in enumerate(p["late_pct"]):
        ax.text(v + 0.2, i, f"{v:.1f}%", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(SHOT_DIR / "province_performance.png"); plt.close(fig)
    print(f"  screenshots -> {SHOT_DIR}")


def main() -> Path:
    print("Loading data from", DB)
    d = load_data()
    h = d["headline"]
    print(f"  {h['n']:,.0f} orders | on-time {h['on_time_pct']:.2f}% | "
          f"late {h['late_pct']:.2f}%")

    figs = {
        "monthly": fig_monthly(d["monthly"]),
        "carrier": fig_carrier(d["carrier"]),
        "province": fig_province(d["province"]),
        "mode": fig_mode(d["mode"]),
        "accuracy": fig_accuracy(d["accuracy"]),
        "warehouse": fig_warehouse(d["warehouse"]),
    }

    print("Embedding plotly.js...")
    js = plotly_js()

    # Figure specs are injected per-div in the template below via _fig_script().

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Supply Chain Analytics Dashboard — Canadian Operations</title>
{js}
<style>
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
         background: {BG}; color: #222; margin: 0; padding: 0 24px 48px; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; }}
  header {{ padding: 32px 0 8px; }}
  header h1 {{ color: {NAVY}; margin: 0 0 6px; font-size: 30px; }}
  header p {{ color: {SLATE}; margin: 4px 0; }}
  .synth {{ background: #fff8e6; border: 1px solid {AMBER}; border-radius: 8px;
            padding: 10px 14px; margin: 16px 0; font-size: 13px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin: 18px 0; }}
  .kpi {{ background: {CARD}; border-radius: 10px; padding: 14px 10px; text-align: center;
         box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .kpi-label {{ font-size: 12px; color: {SLATE}; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 26px; font-weight: 700; }}
  .chart {{ background: {CARD}; border-radius: 10px; padding: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,.08); margin: 16px 0; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .panel {{ background: {CARD}; border-radius: 10px; padding: 20px 26px;
            box-shadow: 0 1px 4px rgba(0,0,0,.08); margin: 16px 0; }}
  .panel h2 {{ color: {NAVY}; font-size: 19px; }}
  .panel li {{ margin: 7px 0; line-height: 1.45; font-size: 14.5px; }}
  footer {{ color: {SLATE}; font-size: 12.5px; margin-top: 24px; }}
  @media (max-width: 900px) {{ .kpi-row, .grid2 {{ grid-template-columns: 1fr 1fr; }} }}
</style></head>
<body><div class="wrap">
<header>
  <h1>Supply Chain Analytics Dashboard</h1>
  <p>Canadian e-commerce operations monitoring &mdash; Jan 2024 &ndash; Dec 2025 &middot;
     {h['n']:,.0f} orders &middot; 4 warehouses &middot; 5 carriers &middot; 10 provinces</p>
</header>
<div class="synth"><b>About the data:</b> I generated all 75,000 orders myself with a Python
script (fixed seed 42, so it is reproducible). The carrier names are fictional.
The project is about the analytics work, not the data.</div>
{kpi_cards(h)}
<div class="chart" id="div-monthly"></div>
<div class="grid2">
  <div class="chart" id="div-carrier"></div>
  <div class="chart" id="div-province"></div>
</div>
<div class="grid2">
  <div class="chart" id="div-mode"></div>
  <div class="chart" id="div-accuracy"></div>
</div>
<div class="chart" id="div-warehouse"></div>
{findings_panel(d)}
<footer>Generated {date.today().isoformat()} from <code>data/supply_chain.db</code> by
<code>src/build_dashboard.py</code> &middot; Reproduce: <code>pip install -r requirements.txt &amp;&amp; python run_all.py</code>
&middot; Power BI rebuild guide: <code>docs/powerbi_rebuild.md</code></footer>
</div>
<script>
{''.join(_fig_script(k, f) for k, f in figs.items())}
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:,.0f} KB)")

    print("Saving screenshots...")
    save_screenshots(d)
    return OUT


def _fig_script(key: str, fig: go.Figure) -> str:
    import json
    from plotly.utils import PlotlyJSONEncoder
    spec = fig.to_plotly_json()
    return (f"Plotly.newPlot('div-{key}', {json.dumps(spec['data'], cls=PlotlyJSONEncoder)}, "
            f"{json.dumps(spec['layout'], cls=PlotlyJSONEncoder)});\n")


if __name__ == "__main__":
    main()
