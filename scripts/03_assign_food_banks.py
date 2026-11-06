import os
import pandas as pd

strategy_path = "data/processed/fl_county_fab_strategy.csv"
if not os.path.exists(strategy_path):
  raise FileNotFoundError(f"Missing {strategy_path}")

df = pd.read_csv(strategy_path)


# Feeding Florida 9-Member Food Bank Regional Territory Crosswalk
def map_food_bank(county_name):
  c = (
      str(county_name)
      .upper()
      .replace(" COUNTY", "")
      .replace(".", "")
      .replace("-", " ")
      .strip()
  )

  # 1. Feeding South Florida (4 counties)
  if c in ["BROWARD", "MIAMI DADE", "MONROE", "PALM BEACH"]:
    return "Feeding South Florida"

  # 2. Feeding Tampa Bay (10 counties)
  elif c in [
      "CITRUS",
      "HARDEE",
      "HERNANDO",
      "HIGHLANDS",
      "HILLSBOROUGH",
      "MANATEE",
      "PASCO",
      "PINELLAS",
      "POLK",
      "SUMTER",
  ]:
    return "Feeding Tampa Bay"

  # 3. Second Harvest of Central Florida (6 counties)
  elif c in ["BREVARD", "LAKE", "ORANGE", "OSCEOLA", "SEMINOLE", "VOLUSIA"]:
    return "Second Harvest of Central Florida"

  # 4. Feeding Northeast Florida (8 counties)
  elif c in [
      "BAKER",
      "BRADFORD",
      "CLAY",
      "DUVAL",
      "FLAGLER",
      "NASSAU",
      "PUTNAM",
      "ST JOHNS",
  ]:
    return "Feeding Northeast Florida"

  # 5. Harry Chapin Food Bank of Southwest Florida (5 counties)
  elif c in ["CHARLOTTE", "COLLIER", "GLADES", "HENDRY", "LEE"]:
    return "Harry Chapin Food Bank"

  # 6. Treasure Coast Food Bank (4 counties)
  elif c in ["INDIAN RIVER", "MARTIN", "OKEECHOBEE", "ST LUCIE"]:
    return "Treasure Coast Food Bank"

  # 7. America's Second Harvest of the Big Bend (11 counties)
  elif c in [
      "CALHOUN",
      "FRANKLIN",
      "GADSDEN",
      "GULF",
      "JACKSON",
      "JEFFERSON",
      "LEON",
      "LIBERTY",
      "MADISON",
      "TAYLOR",
      "WAKULLA",
  ]:
    return "Second Harvest of the Big Bend"

  # 8. Feeding the Gulf Coast - FL Panhandle (7 counties)
  elif c in [
      "BAY",
      "ESCAMBIA",
      "HOLMES",
      "OKALOOSA",
      "SANTA ROSA",
      "WALTON",
      "WASHINGTON",
  ]:
    return "Feeding the Gulf Coast"

  # 9. Bread of the Mighty Food Bank (12 counties)
  elif c in [
      "ALACHUA",
      "COLUMBIA",
      "DIXIE",
      "GILCHRIST",
      "HAMILTON",
      "LAFAYETTE",
      "LEVY",
      "MARION",
      "SUWANNEE",
      "UNION",
  ]:
    return "Bread of the Mighty"

  # Fallback for All Faiths Food Bank (Sarasota/DeSoto)
  elif c in ["DESOTO", "SARASOTA"]:
    return "All Faiths Food Bank"

  return "Unassigned"


county_col = "County" if "County" in df.columns else "CountyFIPS"
df["food_bank_partner"] = df[county_col].apply(map_food_bank)

# Aggregated Regional Roll-Up
regional_summary = (
    df.groupby("food_bank_partner")
    .agg(
        county_count=(county_col, "count"),
        total_driving_lila_tracts=("driving_lila_tracts", "sum"),
        avg_priority_score=("fab_priority_score", "mean"),
        total_direct_markets=("direct_market_count", "sum"),
    )
    .reset_index()
    .sort_values(by="avg_priority_score", ascending=False)
)

print("=====================================================================")
print("      FEEDING FLORIDA NETWORK REGIONAL FAB EXPANSION PRIORITIES      ")
print("=====================================================================\n")
print(regional_summary.to_string(index=False))

# Save enhanced table
output_path = "data/processed/fl_county_fab_strategy.csv"
df.to_csv(output_path, index=False)
print(f"\nRegional food bank mappings saved back to: {output_path}")

print(
    "\nTop 10 High-Need Counties by Regional Network Partner:"
    f" ({county_col}):"
)
print(
    df.sort_values(by="fab_priority_score", ascending=False)[
        [
            county_col,
            "food_bank_partner",
            "fab_priority_score",
            "Strategy_Typology",
        ]
    ]
    .head(10)
    .to_string(index=False)
)