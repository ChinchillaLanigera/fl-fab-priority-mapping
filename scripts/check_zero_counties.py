import pandas as pd

retailer_path = "data/raw/snap_retailers_fl.csv"
df = pd.read_csv(retailer_path, low_memory=False)
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

# Filter to Florida
state_col = next(c for c in df.columns if "state" in c)
df_fl = df[df[state_col].astype(str).str.upper() == "FL"].copy()

county_col = next(c for c in df.columns if "county" in c)
type_col = next(c for c in df.columns if "type" in c or "store" in c)
name_col = next(c for c in df.columns if "name" in c)

# Normalize county names
df_fl["county_norm"] = (
    df_fl[county_col]
    .astype(str)
    .str.upper()
    .str.replace(" COUNTY", "")
    .str.replace("SAINT ", "ST. ")
    .str.replace("ST ", "ST. ")
    .str.strip()
)

target_counties = [
    "BAKER",
    "HAMILTON",
    "LAFAYETTE",
    "LIBERTY",
    "MIAMI-DADE",
    "DADE",
    "ST. JOHNS",
    "ST. LUCIE",
    "WAKULLA",
]
sub = df_fl[df_fl["county_norm"].isin(target_counties)]

print(f"Total SNAP records across these counties: {len(sub)}")
print("\nBreakdown of Store Types found:")
print(sub[type_col].value_counts())

print("\nRecords coded as Farmers' Market or Direct Marketing Farmer:")
direct_mkt = sub[
    sub[type_col].astype(str).str.lower().str.contains("farmer|market")
]
print(direct_mkt[["county_norm", name_col, type_col]].to_string(index=False))