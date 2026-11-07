import os
import re
import pandas as pd

print("--- Step 1: Loading Processed County Scores ---")
county_summary_path = "data/processed/fl_county_summary.csv"
retailer_path = "data/raw/snap_retailers_fl.csv"

if not os.path.exists(county_summary_path):
  raise FileNotFoundError(
      f"Run 01_build_fab_index.py first. Missing {county_summary_path}"
  )

county_df = pd.read_csv(county_summary_path)
county_df = county_df.rename(
    columns={
        "county_fab_score": "fab_priority_score",
        "total_lila_tracts": "driving_lila_tracts",
    }
)


# Canonical normalizer for county name matching
def canonical_county(val):
  if pd.isna(val):
    return ""
  s = str(val).upper().strip()
  s = re.sub(r"\bCOUNTY\b", "", s)
  s = s.replace(".", "").replace("-", " ")
  s = re.sub(r"\bSAINT\b", "ST", s)
  s = re.sub(r"\s+", " ", s).strip()
  if s == "DADE":
    s = "MIAMI DADE"
  if s == "DE SOTO":
    s = "DESOTO"
  return s


# --- Step 2: Load and Filter SNAP Retailer Data via USDA Categories ---
if not os.path.exists(retailer_path):
  print(f"[!] Warning: '{retailer_path}' not found.")
  county_df["direct_market_count"] = 0
else:
  print(f"Loading '{retailer_path}'...")
  df_retail = pd.read_csv(retailer_path, low_memory=False)
  df_retail.columns = [
      c.strip().lower().replace(" ", "_") for c in df_retail.columns
  ]

  # State filter
  state_col = next(c for c in df_retail.columns if "state" in c)
  df_fl = df_retail[df_retail[state_col].astype(str).str.upper() == "FL"].copy()

  county_col = next(c for c in df_fl.columns if "county" in c)
  type_col = next(c for c in df_fl.columns if c == "store_type")

  # Count the category used in this retailer extract for farm markets.
  usda_direct_types = ["farmers and markets"]

  df_fl["store_type_clean"] = df_fl[type_col].astype(str).str.strip().str.lower()
  df_direct = df_fl[df_fl["store_type_clean"].isin(usda_direct_types)].copy()

  print(
      f"Identified {len(df_direct)} official USDA Direct-Market SNAP outlets in"
      " Florida."
  )
  print(f"Breakdown by category:\n{df_direct['store_type_clean'].value_counts()}")

  # Aggregate direct markets by canonical county
  df_direct["county_canonical"] = df_direct[county_col].apply(canonical_county)
  county_key = "County" if "County" in county_df.columns else "CountyFIPS"
  county_df["county_canonical"] = county_df[county_key].apply(canonical_county)

  market_counts = (
      df_direct.groupby("county_canonical")
      .size()
      .reset_index(name="direct_market_count")
  )

  # Merge
  county_df = pd.merge(
      county_df, market_counts, on="county_canonical", how="left"
  )
  county_df["direct_market_count"] = (
      county_df["direct_market_count"].fillna(0).astype(int)
  )
  county_df.drop(columns=["county_canonical"], inplace=True)

# --- Step 3: Classify Action Strategy ---
print("\n--- Step 3: Assigning Action Typologies ---")
score_threshold = county_df["fab_priority_score"].quantile(0.60)


def classify_strategy(row):
  if row["fab_priority_score"] >= score_threshold:
    if row["direct_market_count"] > 0:
      return "High Need: Onboard / Expand Existing SNAP Markets"
    else:
      return "High Need: Mobile Produce Route Needed (Zero Direct Markets)"
  else:
    if row["direct_market_count"] == 0:
      return "Medium Need: Retail Scarcity / Monitor"
    else:
      return "Low Need: Baseline Coverage Adequate"


county_df["Strategy_Typology"] = county_df.apply(classify_strategy, axis=1)

output_path = "data/processed/fl_county_fab_strategy.csv"
county_df.to_csv(output_path, index=False)
print(f"Saved verified county action plan to: {output_path}")

# Display top counties
display_cols = [
    "County" if "County" in county_df.columns else "CountyFIPS",
    "avg_snap_rate",
    "driving_lila_tracts",
    "fab_priority_score",
    "direct_market_count",
    "Strategy_Typology",
]
available_cols = [c for c in display_cols if c in county_df.columns]

print("\n--- Top Priority Counties (Based on Official USDA Classifications) ---")
print(
    county_df.sort_values(by="fab_priority_score", ascending=False)[
        available_cols
    ]
    .head(15)
    .to_string(index=False)
)