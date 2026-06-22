"""
Data Quality Audit: Price Variance Anomaly Detection
=====================================================

Business problem
-----------------
Two systems independently record price for the same order line:
  - Unit_Price    -> price set by the pricing/sales system at order time
  - System_Price  -> price recorded by the downstream ERP/inventory system

In real supply-chain operations, these two numbers SHOULD match (or differ
by only a tiny rounding tolerance). When they drift apart, it usually means
one of:
  1. A price update landed in one system but not the other (sync lag)
  2. A manual override / discount was applied inconsistently
  3. Master data error (wrong SKU-to-price mapping)

This script quantifies that drift, flags statistical outliers, and breaks
the anomaly rate down by Plant and Product Group so a supply-chain analyst
can prioritize which process to fix first.

This mirrors a real reconciliation I ran between GSCM and BI inventory
records in a prior role -- this script is a generalized, fully synthetic
recreation of that workflow for portfolio purposes.

Output
------
- Printed summary statistics + anomaly rates by Plant / Product Group
- outputs/price_variance_outliers.csv  -> the flagged order lines
- outputs/price_variance_summary.png   -> distribution + outlier chart
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = "../data/northstar_sos_synthetic.csv"
OUT_DIR = "../outputs"

# ---------------------------------------------------------------------------
# 1. Load + merge check
# ---------------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df):,} order lines from {DATA_PATH}")

required_cols = {"Unit_Price", "System_Price", "Plant", "Product_Group", "Sale_Order_No"}
missing = required_cols - set(df.columns)
if missing:
    raise ValueError(f"Missing expected columns: {missing}")

# ---------------------------------------------------------------------------
# 2. Compute price variance (% difference between the two systems)
# ---------------------------------------------------------------------------
df["Price_Variance_Pct"] = (df["System_Price"] - df["Unit_Price"]) / df["Unit_Price"] * 100

mean_var = df["Price_Variance_Pct"].mean()
std_var = df["Price_Variance_Pct"].std()
print(f"\nOverall price variance: mean={mean_var:.2f}%, std={std_var:.2f}%")

# ---------------------------------------------------------------------------
# 3. Flag statistical outliers (beyond 2 standard deviations)
# ---------------------------------------------------------------------------
THRESHOLD_SD = 2.0
upper = mean_var + THRESHOLD_SD * std_var
lower = mean_var - THRESHOLD_SD * std_var

df["Is_Price_Outlier"] = (df["Price_Variance_Pct"] > upper) | (df["Price_Variance_Pct"] < lower)

n_outliers = df["Is_Price_Outlier"].sum()
pct_outliers = n_outliers / len(df) * 100
print(f"Flagged {n_outliers:,} outlier order lines ({pct_outliers:.2f}% of all orders)")
print(f"Outlier thresholds: < {lower:.2f}% or > {upper:.2f}% variance")

# ---------------------------------------------------------------------------
# 4. Breakdown by Plant -- which plant's data feed is least reliable?
# ---------------------------------------------------------------------------
by_plant = (
    df.groupby("Plant")
    .agg(
        avg_variance_pct=("Price_Variance_Pct", "mean"),
        outlier_rate_pct=("Is_Price_Outlier", lambda s: s.mean() * 100),
        order_count=("Sale_Order_No", "count"),
    )
    .sort_values("outlier_rate_pct", ascending=False)
)
print("\nOutlier rate by Plant (highest first):")
print(by_plant.round(2).to_string())

# ---------------------------------------------------------------------------
# 5. Breakdown by Product Group -- which category needs a pricing review?
# ---------------------------------------------------------------------------
by_group = (
    df.groupby("Product_Group")
    .agg(
        avg_variance_pct=("Price_Variance_Pct", "mean"),
        outlier_rate_pct=("Is_Price_Outlier", lambda s: s.mean() * 100),
        order_count=("Sale_Order_No", "count"),
    )
    .sort_values("outlier_rate_pct", ascending=False)
)
print("\nOutlier rate by Product Group (highest first):")
print(by_group.round(2).to_string())

# ---------------------------------------------------------------------------
# 6. Save flagged rows + chart
# ---------------------------------------------------------------------------
import os
os.makedirs(OUT_DIR, exist_ok=True)

outlier_cols = ["Sale_Order_No", "Order_Date", "Plant", "Product_Group", "Product",
                 "Unit_Price", "System_Price", "Price_Variance_Pct"]
df[df.Is_Price_Outlier][outlier_cols].to_csv(f"{OUT_DIR}/price_variance_outliers.csv", index=False)
print(f"\nSaved {n_outliers:,} flagged rows to {OUT_DIR}/price_variance_outliers.csv")

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

axes[0].hist(df["Price_Variance_Pct"], bins=60, color="#4C72B0", alpha=0.85)
axes[0].axvline(upper, color="crimson", linestyle="--", label=f"+{THRESHOLD_SD}sd")
axes[0].axvline(lower, color="crimson", linestyle="--", label=f"-{THRESHOLD_SD}sd")
axes[0].set_title("Distribution of Price Variance (System vs Unit Price)")
axes[0].set_xlabel("Variance (%)")
axes[0].set_ylabel("Order Count")
axes[0].legend()

by_plant_sorted = by_plant.sort_values("outlier_rate_pct", ascending=True)
axes[1].barh(by_plant_sorted.index, by_plant_sorted["outlier_rate_pct"], color="#DD8452")
axes[1].set_title("Price Outlier Rate by Plant")
axes[1].set_xlabel("Outlier Rate (%)")

plt.tight_layout()
plt.savefig(f"{OUT_DIR}/price_variance_summary.png", dpi=150)
print(f"Saved chart to {OUT_DIR}/price_variance_summary.png")

print("\nDone.")
