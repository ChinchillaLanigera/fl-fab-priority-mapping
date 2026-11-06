import os
import pandas as pd

county_summary_path = "data/processed/fl_county_summary.csv"
retailer_path = "data/raw/snap_retailers_fl.csv"

# 1. Load files
county_df = pd.read_csv(county_summary_path)
df_retail = pd.read_csv(retailer_path, low_memory=False)
df_retail.columns = [
    c.strip().lower().replace(" ", "_") for c in df_retail.columns
]

# Filter retailer file to FL
state_col = next(c for c in df_retail.columns if "state" in c)
df_fl = df_retail[df_retail[state_col].astype(str).str.upper() == "FL"].copy()

county_col_retail = next(c for c in df_fl.columns if "county" in c)
county_col_summary = "County" if "County" in county_df.columns else "CountyFIPS"


# 2. Extract raw unique county values
def clean_basic(s):
  return str(s).upper().replace(" COUNTY", "").strip()


retail_counties_raw = set(df_fl[county_col_retail].dropna().unique())
summary_counties_raw = set(county_df[county_col_summary].dropna().unique())

retail_counties_clean = {clean_basic(c) for c in retail_counties_raw}
summary_counties_clean = {clean_basic(c) for c in summary_counties_raw}

# 3. Find Mismatches
in_summary_not_retail = sorted(
    list(summary_counties_clean - retail_counties_clean)
)
in_retail_not_summary = sorted(
    list(retail_counties_clean - summary_counties_clean)
)

print("=======================================================")
print("             COUNTY NAME MISMATCH AUDIT                ")
print("=======================================================\n")

print(
    f"Total distinct counties in Summary file: {len(summary_counties_clean)}"
)
print(f"Total distinct counties in Retailer file: {len(retail_counties_clean)}")

if in_summary_not_retail:
  print(
      f"\n[!] Counties in Summary but NOT found in Retailer file"
      f" ({len(in_summary_not_retail)}):"
  )
  for c in in_summary_not_retail:
    print(f"   - {c}")
else:
  print(
    "\n[✓] All 67 Florida counties from the summary file exist in the"
    " retailer file."
)

if in_retail_not_summary:
  print(
      f"\n[?] Unmatched names in Retailer file ({len(in_retail_not_summary)}):"
  )
  for c in in_retail_not_summary:
    print(f"   - {c}")

# 4. Check the specific counties showing 0 direct markets
check_counties = [
    "DESOTO",
    "PUTNAM",
    "OKEECHOBEE",
    "LIBERTY",
    "GADSDEN",
    "HENDRY",
    "HAMILTON",
    "CALHOUN",
    "TAYLOR",
    "BRADFORD",
    "DIXIE",
]
print("\n-------------------------------------------------------")
print("Raw SNAP Retailer counts for our top 'Zero Direct Market' counties:")
print("(Total SNAP retailers of ANY type vs. Direct-Market Produce retailers)")
print("-------------------------------------------------------")

type_col = next(c for c in df_fl.columns if "type" in c or "store" in c)
name_col = next(c for c in df_fl.columns if "name" in c)

df_fl["clean_county"] = df_fl[county_col_retail].apply(clean_basic)

results = []
for cty in check_counties:
  # Check for potential fuzzy matches (e.g. DE SOTO vs DESOTO)
  matching_rows = df_fl[
      df_fl["clean_county"].str.replace(" ", "") == cty.replace(" ", "")
  ]
  actual_name_in_retail = (
      matching_rows["clean_county"].iloc[0] if len(matching_rows) > 0 else "NONE"
  )
  total_any_snap = len(matching_rows)

  # Check direct market matches
  direct_mkt_rows = matching_rows[
      matching_rows[type_col]
      .astype(str)
      .str.lower()
      .isin(["farmers' market", "direct marketing farmer"])
      | matching_rows[name_col]
      .astype(str)
      .str.lower()
      .str.contains("farmers market|farm stand|produce")
  ]

  results.append({
      "County": cty,
      "Name_in_Retail_File": actual_name_in_retail,
      "Total_SNAP_Stores": total_any_snap,
      "Direct_Produce_Matches": len(direct_mkt_rows),
  })

print(pd.DataFrame(results).to_string(index=False))