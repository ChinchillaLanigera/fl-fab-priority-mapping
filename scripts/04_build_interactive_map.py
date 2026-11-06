import json
import os
import urllib.request
import pandas as pd
import plotly.express as px

print("--- Step 1: Loading Processed Strategy Data ---")
strategy_path = "data/processed/fl_county_fab_strategy.csv"

if not os.path.exists(strategy_path):
  raise FileNotFoundError(
      f"Missing {strategy_path}. Run 03_assign_food_banks.py first."
  )

df = pd.read_csv(strategy_path)

# Ensure 5-digit County FIPS string with leading zero (Florida starts with 12)
df["CountyFIPS"] = df["CountyFIPS"].astype(str).str.zfill(5)

# Format metrics for clean hovertool tooltips
df["SNAP_Pct_Label"] = (df["avg_snap_rate"] * 100).round(1).astype(str) + "%"
df["FAB_Score_Label"] = df["fab_priority_score"].round(1).astype(str)

print("--- Step 2: Fetching Florida County Boundaries ---")
geojson_url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
req = urllib.request.Request(geojson_url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(req) as response:
  counties_geojson = json.loads(response.read().decode())

# Filter GeoJSON features to Florida only (FIPS starting with '12')
fl_features = [
    f for f in counties_geojson["features"] if str(f["id"]).startswith("12")
]
fl_geojson = {"type": "FeatureCollection", "features": fl_features}
print(f"Loaded boundary polygons for {len(fl_features)} Florida counties.")

# --- Step 3: Build Interactive Choropleth Map ---
print("--- Step 3: Generating Interactive Choropleth ---")

fig = px.choropleth(
    df,
    geojson=fl_geojson,
    locations="CountyFIPS",
    color="fab_priority_score",
    color_continuous_scale="YlOrRd",
    range_color=(df["fab_priority_score"].min(), df["fab_priority_score"].max()),
    hover_name="County",
    hover_data={
        "CountyFIPS": False,
        "fab_priority_score": False,
        "FAB_Score_Label": True,
        "SNAP_Pct_Label": True,
        "driving_lila_tracts": True,
        "direct_market_count": True,
        "food_bank_partner": True,
        "Strategy_Typology": True,
    },
    labels={
        "FAB_Score_Label": "FAB Priority Score",
        "SNAP_Pct_Label": "Avg SNAP Rate",
        "driving_lila_tracts": "Driving-Distance LILA Tracts",
        "direct_market_count": "SNAP Direct Markets",
        "food_bank_partner": "Feeding FL Partner",
        "Strategy_Typology": "Recommended Action",
        "fab_priority_score": "Priority Score",
    },
)

# Focus map on Florida
fig.update_geos(
    fitbounds="locations",
    visible=False,
    projection_type="mercator",
    showsubunits=True,
    subunitcolor="white",
)

fig.update_layout(
    title={
        "text": (
            "<b>Fresh Access Bucks (FAB) Expansion Priority Index</b><br><sup>"
            " Priority scoring based on rate-based SNAP intensity, driving LILA"
            " barriers, and direct farm retail gaps</sup>"
        ),
        "y": 0.95,
        "x": 0.5,
        "xanchor": "center",
        "yanchor": "top",
    },
    margin={"r": 10, "t": 60, "l": 10, "b": 10},
    coloraxis_colorbar={
        "title": "FAB Need<br>Score",
        "thickness": 15,
        "len": 0.75,
    },
)

# --- Step 4: Export Deliverable ---
os.makedirs("outputs", exist_ok=True)
output_html = "outputs/florida_fab_priority_map.html"
fig.write_html(output_html)

print(f"\n[✓] Interactive map successfully generated at: {output_html}")