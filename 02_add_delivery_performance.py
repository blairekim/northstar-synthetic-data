"""
Adds delivery-performance fields to the base dataset for the
OTIF / Lead Time dashboard:

  Promised_Date          -> date quoted to the customer at order time
  Actual_Delivery_Date   -> date it actually arrived
  Lead_Time_Days         -> Actual_Delivery_Date - Order_Date
  OTIF                   -> "Yes" if Actual <= Promised, else "No"  (derived, not random)

Patterns intentionally baked in (so the dashboard has real insights to find):
  1. Plant distance effect   -> farther plants (Fresno/Phoenix) ship slower
  2. Promo-week strain       -> high-volume weeks add delay + hurt OTIF
  3. Year-over-year learning -> routing/ops improve 2024 -> 2026 (lead time
     shortens, OTIF rises), consistent with the Sankey "tangled -> clean" story
  4. Product-group effect    -> large appliances (REF) take longer than
     small ones (COOKING/DW)
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

df = pd.read_csv("../data/northstar_sos_synthetic.csv", parse_dates=["Order_Date"])
n = len(df)

# ---- baseline promised lead time (days quoted at order time) ----------
# Give a realistic buffer so baseline (no stress) OTIF lands ~90%+
PRODUCT_BASE_DAYS = {"REF": 12, "COOKING": 8, "LAUNDRY": 9, "DW": 7}
promised_base = df["Product_Group"].map(PRODUCT_BASE_DAYS).to_numpy()
promised_days = promised_base + rng.integers(-1, 3, n)          # small quoting variance
promised_days = np.clip(promised_days, 4, None)
df["Promised_Date"] = df["Order_Date"] + pd.to_timedelta(promised_days, unit="D")

# ---- plant distance factor (extra transit days, mild) ------------------
PLANT_DISTANCE_DAYS = {  # rough "how far from a typical DC" proxy
    "P101": 0.2, "P102": 0.5, "P103": 0.2, "P104": 0.2,
    "P105": 1.2, "P106": 0.2, "P107": 1.6, "P108": 0.2,
}
distance_extra = df["Plant"].map(PLANT_DISTANCE_DAYS).to_numpy()

# ---- promo-week strain (capped so it dents OTIF without crashing it) ---
week_qty = df.groupby("YearWeek")["Order_Qty"].sum()
qty_z = (week_qty - week_qty.mean()) / week_qty.std()
promo_extra_by_week = (qty_z.clip(lower=0, upper=1.3) * 0.9).to_dict()   # capped impact
promo_extra = df["YearWeek"].map(promo_extra_by_week).to_numpy()

# ---- year-over-year ops improvement (later = faster & more reliable) ---
# Strong enough to dominate the (uneven) promo-week confound across years
year_relief = {2024: 0.0, 2025: 1.3, 2026: 2.2}
improvement_relief = df["Order_Date"].dt.year.map(year_relief).to_numpy()

# ---- systematic buffer: on average actual beats the promise slightly ---
# (so a "normal" order with no distance/promo penalty is comfortably on-time)
BASE_OFFSET_DAYS = -1.6

# ---- actual transit variability -----------------------------------------
noise = rng.normal(0, 1.0, n)
actual_extra_days = BASE_OFFSET_DAYS + distance_extra + promo_extra - improvement_relief + noise
actual_days = promised_days + actual_extra_days
actual_days = np.clip(actual_days, 1, None)
actual_days_int = np.round(actual_days).astype(int)

df["Actual_Delivery_Date"] = df["Order_Date"] + pd.to_timedelta(actual_days_int, unit="D")
df["Lead_Time_Days"] = (df["Actual_Delivery_Date"] - df["Order_Date"]).dt.days
df["Promised_Lead_Time_Days"] = promised_days
df["OTIF"] = np.where(df["Actual_Delivery_Date"] <= df["Promised_Date"], "Yes", "No")

df.to_csv("../data/northstar_synthetic.csv", index=False)

# ---- diagnostics ---------------------------------------------------------
print("Rows:", len(df))
print("\nOverall OTIF rate: %.1f%%" % (df.OTIF.eq("Yes").mean() * 100))
print("Overall avg lead time: %.1f days (promised avg %.1f days)" %
      (df.Lead_Time_Days.mean(), df.Promised_Lead_Time_Days.mean()))

print("\nOTIF % by Plant (distance effect should show P105/P107 lower):")
print((df.groupby("Plant").OTIF.apply(lambda s: (s == "Yes").mean() * 100)).round(1).to_string())

print("\nAvg lead time by Product Group (REF should be longest):")
print(df.groupby("Product_Group").Lead_Time_Days.mean().round(1).to_string())

print("\nOTIF % by Year (should improve 2024 -> 2026):")
print((df.groupby("Year").OTIF.apply(lambda s: (s == "Yes").mean() * 100)).round(1).to_string())

print("\nOTIF % in top-10 busiest weeks vs rest (promo strain check):")
busy_weeks = week_qty.sort_values(ascending=False).head(10).index
busy_otif = df[df.YearWeek.isin(busy_weeks)].OTIF.eq("Yes").mean() * 100
rest_otif = df[~df.YearWeek.isin(busy_weeks)].OTIF.eq("Yes").mean() * 100
print("  Busy weeks: %.1f%%  |  Other weeks: %.1f%%" % (busy_otif, rest_otif))
