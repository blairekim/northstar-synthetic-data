import pandas as pd, numpy as np

df = pd.read_csv("../data/northstar_sos_synthetic.csv",
                 parse_dates=["Order_Date", "Order_Create_Date"])

# 1) reduce to 1000 base rows, keep diversity & time spread
base = df.sample(n=1000, random_state=7).sort_values("Order_Date").reset_index(drop=True)
base["Order_Date"] = base["Order_Date"].dt.date
base["Order_Create_Date"] = base["Order_Create_Date"].dt.date

# diversity / convergence check on the 1000-row base
def conc(sub):
    return sub.groupby("DC_Code").apply(lambda x: x.Plant.value_counts(normalize=True).iloc[0]).mean()
e = base[pd.to_datetime(base.Order_Date) < "2024-10-01"]
l = base[pd.to_datetime(base.Order_Date) >= "2026-03-01"]
print("Base 1000 rows — diversity:")
print("  Plants:%d  DCs:%d  Stores:%d  States:%d  ProductGroups:%d  OTIF:%s"
      % (base.Plant.nunique(), base.DC_Code.nunique(), base.ShipTo_Code.nunique(),
         base.ShipToStateShort.nunique(), base.Product_Group.nunique(),
         sorted(base.OTIF.unique())))
print("  Plant->DC convergence  early:%.0f%%  late:%.0f%%" % (conc(e)*100, conc(l)*100))
print("  Unique Sale_Order_No (link key):", base.Sale_Order_No.nunique())

# 2) triplicate with Vizside = Plant / DC / Store (1000 each), identical content
blocks = []
for side in ["Plant", "DC", "Store"]:
    b = base.copy()
    b.insert(0, "Vizside", side)
    blocks.append(b)
out = pd.concat(blocks, ignore_index=True)

out.to_csv("../data/northstar_sos_sankey_3000.csv", index=False)
print("\nFinal:", out.shape, "| Vizside counts:", out.Vizside.value_counts().to_dict())
print("Each Sale_Order_No appears", out.groupby("Sale_Order_No").size().unique(), "times (once per Vizside)")
