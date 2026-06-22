# Northstar SCM Analytics

**A synthetic supply-chain dataset + Python/SQL-style data pipeline + Tableau dashboard suite, built to demonstrate end-to-end supply-chain data analysis: data generation, cleaning, anomaly detection, and visualization.**

> 🔗 Live Tableau dashboards: 
**[Sankey Dashboard]
> https://public.tableau.com/app/profile/blaire.kim8868/viz/LeadTimeAnalysis_17821502520500/LeadTimeAnalysis**
**[Lead Time Analysis]
> https://public.tableau.com/app/profile/blaire.kim8868/viz/SCMPlantManagement/SankeyDashboard**

---

## Why this project exists

As a supply chain business analyst transitioning into a more technical analytics role, where real operational data from my day job is confidential, I built a **fully synthetic but realistically-structured** appliance distribution dataset — a fictional retailer ("Northstar Home Improvement") sourcing fictional appliances ("Atlas Appliances") through a Plant → Distribution Center → Store network — to reproduce the kinds of analyses I do at work, end to end, in a way I can show publicly.

This repo covers the **data engineering side**: generating, enriching, and auditing the dataset. The companion Tableau workbook covers the **visualization side** (Sankey routing diagrams, OTIF/lead-time dashboards).

---

## The business problem → data → insight narrative

### 1. Business problem
Supply chain teams often pull the same fact (e.g., price, inventory on-hand) from two different systems — e.g., a planning/ERP system (GSCM) and a BI/reporting layer — and those numbers don't always agree. When they drift apart silently, it erodes trust in the data and can mask real operational issues (stale master data, missed price updates, sync failures).

A second, related problem: leadership wants to know whether **logistics routing is improving over time** and whether **delivery promises are being kept (OTIF)** — but raw transactional data alone doesn't answer that; it has to be modeled, joined, and aggregated correctly first.

### 2. Data
Since I can't use my employer's data, I generated a synthetic dataset (`src/01_generate_synthetic_orders.py`) that mirrors the **shape** of a real special-order appliance supply chain:
- 90,000 order lines, **Plant → DC → Store** hierarchy (8 plants, 8 DCs, 51 stores, 17 states)
- 2 years of order history with realistic seasonality, month-to-month demand "lumpiness," and promotional spikes
- An intentional **routing-efficiency trend baked in**: early shipments are routed somewhat randomly across plants/DCs; later shipments increasingly converge on each DC's "primary" (nearest) plant — simulating a logistics network that gets more efficient over time
- A second pricing field (`System_Price`) that mostly tracks `Unit_Price` within normal rounding noise, **except for a deliberately injected ~2% of order lines with a much larger gap** — simulating real-world price sync failures / stale master data

Then `src/02_add_delivery_performance.py` enriches every order with **Promised_Date**, **Actual_Delivery_Date**, and a **derived** OTIF flag (not random — actually computed from whether the delivery beat the promise), with realistic drivers baked in: plant-to-DC distance, promo-week strain, and year-over-year operational improvement.

### 3. Insight
Running `src/04_detect_price_anomalies.py` on the dataset surfaces:
- **1,807 order lines (2.0%)** with statistically anomalous price variance between the two systems (beyond ±2 standard deviations)
- The anomaly rate is **not evenly distributed** — it ranges from **1.6% (Plant P105) to 2.3% (Plant P108)** — pointing to which plant's data feed most needs a sync/process fix, rather than treating "data quality" as one undifferentiated problem
- This is the same diagnostic pattern I'd use to reconcile inventory/pricing discrepancies between planning and BI systems in a live SCM environment

See `outputs/price_variance_summary.png` and `outputs/price_variance_outliers.csv` for the full output.

---

## Repo structure

```
northstar-scm-analytics/
├── src/
│   ├── 01_generate_synthetic_orders.py     # builds the 90k-row base dataset
│   ├── 02_add_delivery_performance.py      # adds Promised/Actual dates, derives OTIF
│   ├── 03_prepare_sankey_data.py           # reshapes data for the Tableau Sankey chart
│   └── 04_detect_price_anomalies.py        # data quality audit / anomaly detection
├── data/
│   └── northstar_sos_synthetic.csv         # generated dataset (gitignored if too large; see Setup)
├── outputs/
│   ├── price_variance_outliers.csv         # flagged anomalous order lines
│   └── price_variance_summary.png          # distribution + by-plant chart
└── requirements.txt
```

## Setup & how to run

```bash
pip install -r requirements.txt
cd src
python 01_generate_synthetic_orders.py      # creates data/northstar_sos_synthetic.csv
python 02_add_delivery_performance.py       # adds OTIF / lead time fields
python 03_prepare_sankey_data.py            # creates the Sankey-ready 3,000-row extract
python 04_detect_price_anomalies.py         # runs the anomaly detection audit
```

Each script prints diagnostics so you can verify the intended patterns (seasonality, routing convergence, OTIF improvement, anomaly rates) are present before loading the data into Tableau or any other BI tool.

## Tech used
- **Python / pandas / numpy** — data generation, joins, feature engineering, LOD-style aggregation logic
- **matplotlib** — anomaly visualization
- **Tableau** — Sankey routing diagram (Plant → DC → Store), OTIF & lead-time dashboard with KPI cards, MTD/PMTD comparisons, and box-plot variance analysis (see live link above)

## Notes
- All company names, plants, DCs, and stores are fictional. This dataset does not contain or derive from any real employer data.
- Random seed is fixed (`seed=42`/`seed=7`) so the pipeline is fully reproducible.
