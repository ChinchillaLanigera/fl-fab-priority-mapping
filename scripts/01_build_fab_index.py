import os
import numpy as np
import pandas as pd

print("--- Step 1: Loading USDA Food Access Research Atlas ---")
fara_path = "data/raw/FoodAccessResearchAtlasData.xlsx"

if not os.path.exists(fara_path):
  raise FileNotFoundError(
      f"Missing {fara_path}. Please place the USDA Excel file in data/raw/."
  )

# Inspect available sheets to ensure we load the data table, not the 'Read Me' tab
xl = pd.ExcelFile(fara_path)
print(f"Sheets found in workbook: {xl.sheet_names}")

# Target the data sheet
target_sheet = next(
    (s for s in xl.sheet_names if "generaltractcharacteristic data" in s.lower()),
    None,
)

# Default fallback if no match found
if not target_sheet:
  target_sheet = xl.sheet_names[-1]

print(f"Loading data from sheet: '{target_sheet}' (this may take ~10-20s)...")
df_fara = pd.read_excel(fara_path, sheet_name=target_sheet, header=1)

# Print first few column names to verify
print(f"Loaded {len(df_fara)} total records with {len(df_fara.columns)} columns.")

# Locate Census Tract column
tract_candidates = [
    c
    for c in df_fara.columns
    if "censustract" in str(c).lower() or "tract" in str(c).lower()
]
if not tract_candidates:
  print("Available columns:", list(df_fara.columns[:10]))
  raise KeyError("Could not find a Census Tract column in the loaded sheet.")

tract_col = tract_candidates[0]
print(f"Using tract identifier column: '{tract_col}'")

# Preserve county names for retailer-data matching in the next step.
county_name_col = next(
    (c for c in ["County", "County20", "County24"] if c in df_fara.columns),
    None,
)
if county_name_col and county_name_col != "County":
  df_fara["County"] = df_fara[county_name_col]

# Ensure CensusTract is string with leading zeros (Florida starts with 12)
df_fara[tract_col] = df_fara[tract_col].astype(str).str.split(".").str[0]
df_fara[tract_col] = df_fara[tract_col].str.zfill(11)

# Filter for Florida
if "State" in df_fara.columns:
  fl_tracts = df_fara[
      (df_fara["State"] == "Florida") | (df_fara["State"] == "FL")
  ].copy()
else:
  fl_tracts = df_fara[df_fara[tract_col].str.startswith("12")].copy()

fl_tracts["CountyFIPS"] = fl_tracts[tract_col].str[:5]
print(
    f"Extracted {len(fl_tracts)} Florida census tracts across"
    f" {fl_tracts['CountyFIPS'].nunique()} counties."
)

# --- Step 2: Extract Key Metrics ---
print("--- Step 2: Normalizing Intensity Metrics ---")


# Helper to find column flexibly
def find_col(patterns, df):
  for p in patterns:
    for c in df.columns:
      if p.lower() in str(c).lower():
        return c
  return None


pop_col = find_col(["Pop2010", "Pop2020", "population"], fl_tracts)
poverty_col = find_col(["PovertyRate", "poverty"], fl_tracts)
snap_col = find_col(["TractSNAP", "SNAP"], fl_tracts)

dd_sheet = next(
    (s for s in xl.sheet_names if "driving distance data" in s.lower()),
    None,
)
if not dd_sheet:
  raise ValueError("Could not find the Driving Distance Data sheet.")

df_dd = pd.read_excel(
    fara_path,
    sheet_name=dd_sheet,
    header=1,
    usecols=["CensusTract20", "DD_SRAM_LILATracts_1And10"],
)
df_dd["CensusTract20"] = (
    df_dd["CensusTract20"].astype(str).str.split(".").str[0].str.zfill(11)
)
df_dd = df_dd.rename(columns={"CensusTract20": tract_col})
fl_tracts = fl_tracts.merge(df_dd, on=tract_col, how="left", validate="one_to_one")
lila_col = "DD_SRAM_LILATracts_1And10"

print(
    f"Columns identified -> Pop: '{pop_col}', Poverty: '{poverty_col}', LILA:"
    f" '{lila_col}', SNAP: '{snap_col}'"
)

cols = [tract_col, "CountyFIPS", pop_col, poverty_col, lila_col, snap_col]
if "County" in fl_tracts.columns:
  cols.append("County")

df_fl = fl_tracts[cols].copy()

# Household proxy: population / 2.5
df_fl["Estimated_Households"] = (df_fl[pop_col] / 2.5).clip(lower=1)
df_fl["SNAP_Rate"] = (
    df_fl[snap_col] / df_fl["Estimated_Households"]
).clip(upper=1.0).fillna(0)

# Percentile ranks (0 to 100)
df_fl["P_SNAP"] = df_fl["SNAP_Rate"].rank(pct=True) * 100
df_fl["P_Poverty"] = df_fl[poverty_col].rank(pct=True) * 100
df_fl["LILA_Flag"] = df_fl[lila_col].fillna(0).astype(int)

# Composite Index Starter
# --- UPDATED CODE: Focus on Target Demand Proportion ---
# 50% Target Proportion: Rewards tracts where 25-45%+ of households are on SNAP
# 25% Economic Depth: Poverty rate
# 25% Physical Friction: Driving-distance supermarket access barrier (1 & 10 miles)
df_fl["FAB_Need_Score"] = (
    0.50 * df_fl["P_SNAP"]
    + 0.25 * df_fl["P_Poverty"]
    + 0.25 * (df_fl["LILA_Flag"] * 100)
)

# --- Step 3: Roll Up to County Summary ---
print("--- Step 3: Rolling Up to County Summary ---")
group_cols = ["CountyFIPS"]
if "County" in df_fl.columns:
  group_cols.append("County")

county_summary = (
    df_fl.groupby(group_cols)
    .agg(
        total_pop=(pop_col, "sum"),
        total_lila_tracts=("LILA_Flag", "sum"),
        total_tracts=(tract_col, "count"),
        high_snap_tracts=("SNAP_Rate", lambda x: (x >= 0.30).sum()),
        avg_poverty_rate=(poverty_col, "mean"),
        avg_snap_rate=("SNAP_Rate", "mean"),
        county_fab_score=("FAB_Need_Score", "mean"),
    )
    .reset_index()
    .sort_values(by="county_fab_score", ascending=False)
)

# Export processed files
os.makedirs("data/processed", exist_ok=True)
df_fl.to_csv("data/processed/fl_tracts_scored.csv", index=False)
county_summary.to_csv("data/processed/fl_county_summary.csv", index=False)

print("\nFiles saved successfully to data/processed/:")
print(" - fl_tracts_scored.csv")
print(" - fl_county_summary.csv")

print("\nTop 10 Priority Counties by Relative Need (Non-population weighted):")
display_cols = (
    ["County", "avg_snap_rate", "total_lila_tracts", "county_fab_score"]
    if "County" in county_summary.columns
    else ["CountyFIPS", "avg_snap_rate", "total_lila_tracts", "county_fab_score"]
)
print(county_summary[display_cols].head(10).to_string(index=False))