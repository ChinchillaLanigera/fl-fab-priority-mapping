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

# --- UPDATED STEP 2: Categorize Direct Markets, Grocers, and Convenience ---
if not os.path.exists(retailer_path):
    print(f"[!] Warning: '{retailer_path}' not found.")
    county_df["direct_market_count"] = 0
    county_df["grocery_store_count"] = 0
    county_df["convenience_store_count"] = 0
    county_df["total_snap_retailers"] = 0
else:
    print(f"Loading '{retailer_path}'...")
    df_retail = pd.read_csv(retailer_path, low_memory=False)
    df_retail.columns = [
        c.strip().lower().replace(" ", "_") for c in df_retail.columns
    ]

    state_col = next(c for c in df_retail.columns if "state" in c)
    df_fl = df_retail[df_retail[state_col].astype(str).str.upper() == "FL"].copy()

    county_col = next(c for c in df_fl.columns if "county" in c)
    type_col = next(c for c in df_fl.columns if c in ["store_type", "type"])

    df_fl["store_type_clean"] = df_fl[type_col].astype(str).str.strip().str.lower()

# Categories
    direct_types = ["farmers and markets", "farmers' market", "direct marketing farmer"]
    grocery_types = [
        "supermarket",
        "large grocery store",
        "medium grocery store",
        "super store",
    ]
    fringe_types = ["convenience store", "combination grocery/other"]

    df_fl["is_direct"] = df_fl["store_type_clean"].isin(direct_types)
    df_fl["is_grocery"] = df_fl["store_type_clean"].isin(grocery_types)
    df_fl["is_fringe"] = df_fl["store_type_clean"].isin(fringe_types)

    print(
        "Identified SNAP Outlets -> "
        f"Direct Markets: {df_fl['is_direct'].sum()}, "
        f"Grocers: {df_fl['is_grocery'].sum()}, "
        f"Convenience/Fringe: {df_fl['is_fringe'].sum()}"
    )

    # Aggregate counts by canonical county
    df_fl["county_canonical"] = df_fl[county_col].apply(canonical_county)
    county_key = "County" if "County" in county_df.columns else "CountyFIPS"
    county_df["county_canonical"] = county_df[county_key].apply(canonical_county)

    retail_summary = (
        df_fl.groupby("county_canonical")
        .agg(
            direct_market_count=("is_direct", "sum"),
            grocery_store_count=("is_grocery", "sum"),
            convenience_store_count=("is_fringe", "sum"),
            total_snap_retailers=("is_direct", "count"),
        )
        .reset_index()
    )

    county_df = pd.merge(county_df, retail_summary, on="county_canonical", how="left")
    for col in [
        "direct_market_count",
        "grocery_store_count",
        "convenience_store_count",
        "total_snap_retailers",
    ]:
        county_df[col] = county_df[col].fillna(0).astype(int)
    county_df.drop(columns=["county_canonical"], inplace=True)

# --- UPDATED STEP 3: Compute Likelihood of Impact & Strategy ---
print("\n--- Step 3: Normalizing Access and Scoring Expected Impact ---")
county_df["est_snap_households"] = (
    (county_df["total_pop"] / 2.5) * county_df["avg_snap_rate"]
).clip(lower=1)

# Market Capacity: outlets per 10k estimated SNAP households
county_df["direct_per_10k_snap"] = (
    county_df["direct_market_count"] / county_df["est_snap_households"]
) * 10000

county_df["grocery_per_10k_snap"] = (
    county_df["grocery_store_count"] / county_df["est_snap_households"]
) * 10000

if "total_tracts" not in county_df.columns:
    raise KeyError("County summary must include 'total_tracts' for impact scoring.")

county_df["P_SNAP_Prop"] = county_df["avg_snap_rate"].rank(pct=True) * 100
county_df["P_Poverty_Rank"] = (
    county_df["avg_poverty_rate"].rank(pct=True) * 100
)
county_df["P_LILA_Tracts"] = (
    county_df["driving_lila_tracts"] / county_df["total_tracts"]
).rank(pct=True) * 100
county_df["P_Market_Ready"] = (
    county_df["direct_per_10k_snap"].rank(pct=True) * 100
)

county_df["fab_expected_impact_score"] = (
    0.45 * county_df["P_SNAP_Prop"]
    + 0.20 * county_df["P_Poverty_Rank"]
    + 0.15 * county_df["P_LILA_Tracts"]
    + 0.20 * county_df["P_Market_Ready"]
)

impact_threshold = county_df["fab_expected_impact_score"].quantile(0.60)

def classify_impact_strategy(row):
    is_high_priority = row["fab_expected_impact_score"] >= impact_threshold
    has_direct = row["direct_market_count"] > 0
    has_grocery = row["grocery_store_count"] > 0

    if is_high_priority:
        need_tier = "High Need"
        if has_direct:
            typology = (
                "High Impact Potential: Active Markets Ready for FAB Onboarding"
            )
        elif has_grocery:
            typology = (
                "High Need Produce Gap: Supermarkets Present, Zero Farm Outlets"
                " (Grocery Pilot / Pop-Up Target)"
            )
        else:
            typology = (
                "High Need Food Desert: Zero Farm Outlets, Grocery Scarcity"
                " (Mobile Route Priority)"
            )
    else:
        if has_direct:
            need_tier = "Low Need"
            typology = "Moderate Need: Direct-Market Baseline Present"
        else:
            need_tier = "Medium Need"
            typology = "Moderate Need: Retail Deficit / Monitor"

    if not has_direct:
        readiness = "Retail Deficit (0 Direct Markets)"
    elif row["direct_per_10k_snap"] < 1.0:
        readiness = (
            f"Severe Capacity Deficit "
            f"({row['direct_per_10k_snap']:.1f}/10k SNAP HH)"
        )
    else:
        readiness = (
            f"Direct-Market Active ({row['direct_market_count']} outlet(s))"
        )

    return pd.Series(
        [need_tier, readiness, typology],
        index=["Need_Tier", "Retail_Readiness", "Strategy_Typology"],
    )

county_df[["Need_Tier", "Retail_Readiness", "Strategy_Typology"]] = (
    county_df.apply(classify_impact_strategy, axis=1)
)

output_path = "data/processed/fl_county_fab_strategy.csv"
county_df.to_csv(output_path, index=False)
print(f"Saved verified county action plan to: {output_path}")

display_cols = [
    "County" if "County" in county_df.columns else "CountyFIPS",
    "avg_snap_rate",
    "driving_lila_tracts",
    "fab_priority_score",
    "fab_expected_impact_score",
    "direct_market_count",
    "grocery_store_count",
    "Retail_Readiness",
    "Strategy_Typology",
]
available_cols = [c for c in display_cols if c in county_df.columns]
print("\n--- Top Priority Counties Summary ---")
print(
    county_df.sort_values(
        by="fab_expected_impact_score", ascending=False
    )[available_cols]
    .head(15)
    .to_string(index=False)
)