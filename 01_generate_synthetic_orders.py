"""
Synthetic appliance supply-chain dataset generator (v3).

True three-tier physical route:  PLANT -> DC -> CUSTOMER (STORE)
- Each store belongs to a fixed regional DC (DC -> Store leg is stable).
- The PLANT -> DC leg starts TANGLED (DCs replenished by random plants) and
  converges over time to CLEAN STREAMS (each DC served by its nearest plant),
  i.e. logistics routing becomes efficient. Filter the Sankey by time to watch it.

All entities fictional. Retailer: Northstar Home Improvement / Mfr: Atlas Appliances
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
START, END = "2024-06-01", "2026-06-19"
start_ts, end_ts = pd.Timestamp(START), pd.Timestamp(END)

# 1. Plants ------------------------------------------------------------
PLANTS = {
    "P101": ("Atlas Plant - Newark",    "NJ"), "P102": ("Atlas Plant - Dallas",   "TX"),
    "P103": ("Atlas Plant - Atlanta",   "GA"), "P104": ("Atlas Plant - Columbus", "OH"),
    "P105": ("Atlas Plant - Phoenix",   "AZ"), "P106": ("Atlas Plant - Charlotte","NC"),
    "P107": ("Atlas Plant - Fresno",    "CA"), "P108": ("Atlas Plant - Richmond", "VA"),
}
PLANT_CODES = list(PLANTS.keys())
PLANT_WEIGHTS = np.array([0.16, 0.15, 0.14, 0.13, 0.10, 0.12, 0.11, 0.09])
PLANT_WEIGHTS = PLANT_WEIGHTS / PLANT_WEIGHTS.sum()

# 2. DCs (1:1 with a nearest "primary" plant) --------------------------
DCS = {
    "D01": ("Northstar DC - Edison, NJ",   "NJ", "P101"),
    "D02": ("Northstar DC - Dallas, TX",   "TX", "P102"),
    "D03": ("Northstar DC - Atlanta, GA",  "GA", "P103"),
    "D04": ("Northstar DC - Columbus, OH", "OH", "P104"),
    "D05": ("Northstar DC - Phoenix, AZ",  "AZ", "P105"),
    "D06": ("Northstar DC - Charlotte, NC","NC", "P106"),
    "D07": ("Northstar DC - Ontario, CA",  "CA", "P107"),
    "D08": ("Northstar DC - Richmond, VA", "VA", "P108"),
}
DC_PRIMARY = {dc: v[2] for dc, v in DCS.items()}

# 3. States -> their regional DC ---------------------------------------
STATES = {
    "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "FL": "Florida", "GA": "Georgia",
    "IL": "Illinois", "NC": "North Carolina", "OH": "Ohio", "PA": "Pennsylvania",
    "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas", "VA": "Virginia",
    "WA": "Washington",
}
STATE_CODES = list(STATES.keys())
STATE_WEIGHTS = rng.dirichlet(np.ones(len(STATE_CODES)) * 2.0)
STATE_TO_DC = {
    "CT": "D01", "PA": "D01", "AR": "D02", "CO": "D02", "TX": "D02",
    "AL": "D03", "FL": "D03", "GA": "D03", "TN": "D03", "IL": "D04", "OH": "D04",
    "AZ": "D05", "NC": "D06", "SC": "D06", "CA": "D07", "WA": "D07", "VA": "D08",
}

# 4. Stores per state (each store belongs to its state's DC) -----------
def make_stores():
    stores, sid = {}, 3000
    for st in STATE_CODES:
        lst = []
        for _ in range(rng.integers(2, 5)):
            sid += rng.integers(3, 19)
            kind = rng.choice(["STORE", "ADC"], p=[0.8, 0.2])
            lst.append((f"NS-{kind}-{sid}", f"Northstar {kind} #{sid}"))
        stores[st] = lst
    return stores
STORES = make_stores()

# 5. Products ----------------------------------------------------------
PRODUCTS = {
    "REF":     (["FDR", "SBS", "1DOOR", "TMF", "BMF", "WINE CELLAR"], (800, 3200), 0.425),
    "COOKING": (["RANGE/COOKER", "MWO", "COOKTOP", "OVEN", "OTHERS"], (250, 2000), 0.254),
    "LAUNDRY": (["WASHER", "DRYER"],                                  (450, 1600), 0.160),
    "DW":      (["DW"],                                               (350, 1200), 0.161),
}
GROUP_CODES = list(PRODUCTS.keys())
GROUP_WEIGHTS = np.array([PRODUCTS[g][2] for g in GROUP_CODES]); GROUP_WEIGHTS /= GROUP_WEIGHTS.sum()
PLANT_OTIF = {p: rng.uniform(0.80, 0.95) for p in PLANT_CODES}

# 6. Weekly demand: growth + seasonality + lumpy months + promo spikes -
weeks = pd.date_range(START, END, freq="W-MON"); n_weeks = len(weeks)
fw = np.clip(np.asarray((weeks - start_ts) / (end_ts - start_ts), dtype=float), 0, 1)
months = pd.PeriodIndex(weeks, freq="M")
month_factor = {m: rng.lognormal(0.0, 0.38) for m in months.unique()}
mfac = np.array([month_factor[m] for m in months])
growth = 1.0 + 0.18 * fw
season = 1.0 + 0.30 * np.sin(2 * np.pi * (weeks.dayofyear.values / 365.0) - 0.6)
promo = np.ones(n_weeks)
spike = rng.choice(n_weeks, size=int(n_weeks * 0.07), replace=False)
promo[spike] *= rng.uniform(1.7, 2.6, spike.size)
week_weight = growth * season * mfac * promo; week_weight /= week_weight.sum()

# 7. Generate ----------------------------------------------------------
N = 90_000
wk_idx = rng.choice(n_weeks, size=N, p=week_weight)
order_date = pd.to_datetime(weeks[wk_idx]) + pd.to_timedelta(rng.integers(0, 7, N), unit="D")
order_date = order_date.where(order_date <= end_ts, end_ts)
create_date = order_date - pd.to_timedelta(rng.integers(0, 5, N), unit="D")
ship_state = rng.choice(STATE_CODES, size=N, p=STATE_WEIGHTS)
group = rng.choice(GROUP_CODES, size=N, p=GROUP_WEIGHTS)

dc_code = np.array([STATE_TO_DC[s] for s in ship_state])
frac = np.clip((order_date - start_ts) / (end_ts - start_ts), 0, 1).astype(float)
efficiency = np.clip(0.12 + 0.82 * frac, 0, 0.95)          # plant->DC routing efficiency
use_primary = rng.random(N) < efficiency
primary_plant = np.array([DC_PRIMARY[d] for d in dc_code])
random_plant = rng.choice(PLANT_CODES, size=N, p=PLANT_WEIGHTS)
plant = np.where(use_primary, primary_plant, random_plant)

rows = []
for i in range(N):
    g = group[i]; prods, (lo, hi), _ = PRODUCTS[g]
    product = rng.choice(prods); model = f"{g[:2]}{rng.integers(100,999)}{rng.choice(list('ABCDXY'))}"
    st = ship_state[i]; store_code, store_name = STORES[st][rng.integers(0, len(STORES[st]))]
    dc = dc_code[i]
    qty = int(rng.choice([1,1,1,2,2,3,4,6,10], p=[.34,.20,.12,.12,.08,.06,.04,.02,.02]))
    unit_price = round(float(rng.uniform(lo, hi)), 2)
    order_amt = round(unit_price * qty, 2)
    # Most rows: small, normal rounding/timing noise between the two systems.
    # ~2% of rows: a genuine sync failure / stale master-data price (much larger gap).
    if rng.random() < 0.02:
        system_price = round(unit_price * rng.uniform(1.12, 1.35) * rng.choice([1, -1, 1, 1]), 2)
        system_price = abs(system_price)
    else:
        system_price = round(unit_price * rng.uniform(0.96, 1.05), 2)
    p_otif = PLANT_OTIF[plant[i]] * (0.92 if promo[wk_idx[i]] > 1.3 else 1.0)
    otif = "Yes" if rng.random() < p_otif else "No"
    rows.append((
        f"SO{8000000+i}", "ZSO", order_date[i], create_date[i],
        "Northstar Home Improvement", f"100{rng.integers(100,999)}", "Northstar Home Improvement Corp",
        store_code, store_name, store_name, STATES[st], st,
        plant[i], PLANTS[plant[i]][0], PLANTS[plant[i]][1],
        dc, DCS[dc][0], DCS[dc][1],
        g, product, model, qty, unit_price, order_amt, system_price, otif,
    ))

cols = ["Sale_Order_No","Sales_Doc_Type","Order_Date","Order_Create_Date","Customer",
        "SoldTo_No","SoldTo_Name","ShipTo_Code","ShipTo_Name","Store_Name",
        "ShipToState","ShipToStateShort","Plant","Plant_Name","Plant_State",
        "DC_Code","DC_Name","DC_State",
        "Product_Group","Product","Model","Order_Qty","Unit_Price","Order_Amt","System_Price","OTIF"]
df = pd.DataFrame(rows, columns=cols)
df["Year"] = df["Order_Date"].dt.year
df["Week"] = df["Order_Date"].dt.isocalendar().week.astype(int)
df["YearWeek"] = df["Year"].astype(str) + "W" + df["Week"].astype(str).str.zfill(2)
df["YearMonth"] = df["Order_Date"].dt.strftime("%Y-%m")
df = df.sort_values("Order_Date").reset_index(drop=True)
df.to_csv("../data/northstar_sos_synthetic.csv", index=False)

# Diagnostics
print("Rows:", len(df), "| Range:", df.Order_Date.min().date(), "->", df.Order_Date.max().date())
print("Tiers present -> PLANT:", df.Plant.nunique(), "| DC:", df.DC_Code.nunique(), "| STORE:", df.ShipTo_Code.nunique())
print("\nRoute sample (Plant -> DC -> Store):")
print(df[["Plant_Name","DC_Name","Store_Name","ShipToStateShort"]].head(6).to_string(index=False))
def conc(sub):  # avg dominant-plant share per DC -> 1.0 = clean streams
    return sub.groupby("DC_Code").apply(lambda x: x.Plant.value_counts(normalize=True).iloc[0]).mean()
print("\nPLANT->DC convergence (avg dominant-plant share per DC):")
print("  Early (Jun-Sep 2024): %.0f%% (tangled)" % (conc(df[df.Order_Date < '2024-10-01'])*100))
print("  Late  (Mar-Jun 2026): %.0f%% (clean streams)" % (conc(df[df.Order_Date >= '2026-03-01'])*100))
