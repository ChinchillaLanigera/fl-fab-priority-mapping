import html
import json
import os
import re
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd
import plotly.graph_objects as go

print("--- Step 1: Loading Data Layers ---")
strategy_path = "data/processed/fl_county_fab_strategy.csv"
tracts_path = "data/processed/fl_tracts_scored.csv"
retailer_path = "data/raw/snap_retailers_fl.csv"

county_df = pd.read_csv(strategy_path)
tracts_df = pd.read_csv(tracts_path)
retail_df = pd.read_csv(retailer_path, low_memory=False)

# Ensure 5-digit FIPS for county matching
county_df["CountyFIPS"] = county_df["CountyFIPS"].astype(str).str.zfill(5)

# --- Step 2: Fetch County Boundaries GeoJSON ---
print("--- Step 2: Fetching Boundary Polygons ---")
geojson_url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
req = urllib.request.Request(geojson_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as response:
  counties_geojson = json.loads(response.read().decode())

fl_features = [
    f for f in counties_geojson["features"] if str(f["id"]).startswith("12")
]
fl_geojson = {"type": "FeatureCollection", "features": fl_features}

# Fetch 2020 Florida census-tract internal points from Census TIGERweb.
print("--- Step 2a: Fetching Census Tract Centroids ---")
tract_service_url = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Tracts_Blocks/MapServer/10/query"
)
tract_features = []
page_size = 2000
offset = 0
while True:
  params = urllib.parse.urlencode(
      {
          "where": "STATE='12'",
          "outFields": "GEOID,CENTLAT,CENTLON",
          "returnGeometry": "false",
          "f": "json",
          "resultRecordCount": page_size,
          "resultOffset": offset,
          "orderByFields": "GEOID",
      }
  )
  req = urllib.request.Request(
      f"{tract_service_url}?{params}",
      headers={"User-Agent": "Mozilla/5.0"},
  )
  with urllib.request.urlopen(req) as response:
    page = json.loads(response.read().decode())
  if "error" in page:
    raise RuntimeError(f"Census TIGERweb query failed: {page['error']}")
  features = page.get("features", [])
  if not features:
    break
  tract_features.extend(feature["attributes"] for feature in features)
  offset += len(features)
  if not page.get("exceededTransferLimit", False):
    break

tract_centroids = pd.DataFrame(tract_features).rename(
    columns={
        "GEOID": "CensusTract20",
        "CENTLAT": "Latitude",
        "CENTLON": "Longitude",
    }
)
tract_centroids["CensusTract20"] = (
    tract_centroids["CensusTract20"].astype(str).str.zfill(11)
)
tract_centroids["Latitude"] = pd.to_numeric(
    tract_centroids["Latitude"], errors="raise"
)
tract_centroids["Longitude"] = pd.to_numeric(
    tract_centroids["Longitude"], errors="raise"
)
tracts_df["CensusTract20"] = tracts_df["CensusTract20"].astype(str).str.zfill(11)
tracts_df = tracts_df.merge(
    tract_centroids,
    on="CensusTract20",
    how="left",
    validate="one_to_one",
)
if tracts_df[["Latitude", "Longitude"]].isna().any().any():
  missing_tracts = int(tracts_df["Latitude"].isna().sum())
  raise ValueError(
      f"Census TIGERweb returned no centroid for {missing_tracts} Florida tracts."
  )

# --- Step 3: Prepare Layer Data ---
# Layer 1: All Florida census tracts, colored by estimated household SNAP rate
snap_tracts = tracts_df.copy()

# Layer 2: Driving-Distance LILA Tracts
lila_tracts = tracts_df[tracts_df["LILA_Flag"] == 1].copy()

# Layer 3: Direct-to-Consumer SNAP Outlets
retail_df.columns = [
    c.strip().lower().replace(" ", "_") for c in retail_df.columns
]
state_col = next(c for c in retail_df.columns if "state" in c)
type_col = next(c for c in retail_df.columns if c == "store_type")
lat_col = next(c for c in retail_df.columns if "lat" in c)
lon_col = next(c for c in retail_df.columns if "lon" in c)
name_col = next(c for c in retail_df.columns if "name" in c)

direct_types = ["farmers and markets"]
direct_retail = retail_df[
    (retail_df[state_col].astype(str).str.upper() == "FL")
    & (retail_df[type_col].astype(str).str.lower().isin(direct_types))
].copy()
direct_retail = direct_retail.dropna(subset=[lat_col, lon_col])

# --- Step 4: Assemble Multi-Layer Plotly Figure ---
print("--- Step 4: Assembling Layers ---")
county_df["need_category"] = county_df["Strategy_Typology"].str.split(
    ":", n=1
).str[0]
category_color_ranges = {
    "Low Need": (0.0, 1.0),
    "Medium Need": (1.001, 2.0),
    "High Need": (2.001, 3.0),
}
category_colors = {
    "Low Need": ("#A1D99B", "#238B45"),
    "Medium Need": ("#FEE391", "#B8860B"),
    "High Need": ("#FC9272", "#B2182B"),
}
if not county_df["need_category"].isin(category_color_ranges).all():
  unexpected_categories = sorted(
      county_df.loc[
          ~county_df["need_category"].isin(category_color_ranges),
          "need_category",
      ].unique()
  )
  raise ValueError(f"Unrecognized need categories: {unexpected_categories}")

county_df["color_value"] = 0.0
for category, (range_start, range_end) in category_color_ranges.items():
  category_mask = county_df["need_category"] == category
  category_scores = county_df.loc[category_mask, "fab_priority_score"]
  score_span = category_scores.max() - category_scores.min()
  if score_span:
    score_fraction = (
        category_scores - category_scores.min()
    ) / score_span
  else:
    score_fraction = pd.Series(0.5, index=category_scores.index)
  county_df.loc[category_mask, "color_value"] = (
      range_start + score_fraction * (range_end - range_start)
  )

county_colorscale = []
for category, (range_start, range_end) in category_color_ranges.items():
  light_color, dark_color = category_colors[category]
  county_colorscale.extend(
      [
          [range_start / 3, light_color],
          [range_end / 3, dark_color],
      ]
  )

fig = go.Figure()

# Base Layer (Trace 0): County Choropleth
fig.add_trace(
    go.Choropleth(
        geojson=fl_geojson,
        locations=county_df["CountyFIPS"],
        z=county_df["color_value"],
        zmin=0,
        zmax=3,
        colorscale=county_colorscale,
        showscale=False,
        text=county_df.apply(
            lambda r: (
                f"<b>{r['County']}</b><br>"
                f"Priority Score: {r['fab_priority_score']:.1f}<br>"
                f"Avg SNAP Rate: {r['avg_snap_rate']*100:.1f}%<br>"
                f"Driving LILA Tracts: {r['driving_lila_tracts']}<br>"
                f"Direct Outlets: {r['direct_market_count']}<br>"
                f"Partner: {r['food_bank_partner']}<br>"
                f"Strategy: {r['Strategy_Typology']}"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="County Priority Index",
        visible=True,
    )
)

# Layer 2 (Trace 1): SNAP Tract Intensity Points
fig.add_trace(
    go.Scattergeo(
        lon=snap_tracts["Longitude"],
        lat=snap_tracts["Latitude"],
        mode="markers",
        marker=dict(
            size=5,
            color=snap_tracts["SNAP_Rate"] * 100,
            colorscale="Purples",
            cmin=0,
            cmax=100,
            opacity=0.7,
            showscale=False,
        ),
        text=snap_tracts.apply(
            lambda r: (
                f"<b>Tract {r['CensusTract20']}</b><br>"
                f"SNAP Rate: {r['SNAP_Rate']*100:.1f}%<br>"
                f"Poverty Rate: {r.get('PovertyRate', 'N/A')}%"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="Tract SNAP Participation Rate",
        showlegend=False,
        visible=False,
    )
)

# Layer 3 (Trace 2): Driving-Distance LILA Barriers
fig.add_trace(
    go.Scattergeo(
        lon=lila_tracts["Longitude"],
        lat=lila_tracts["Latitude"],
        mode="markers",
        marker=dict(
            size=7,
            symbol="diamond",
            color="#004d40",
            opacity=0.85,
            line=dict(width=1, color="white"),
        ),
        text=lila_tracts.apply(
            lambda r: (
                f"<b>Transit Desert Tract {r['CensusTract20']}</b><br>"
                f"Low Access: >10 mi rural / >1 mi urban<br>"
                f"SNAP Rate: {r['SNAP_Rate']*100:.1f}%"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="Driving Access Barriers (USDA LILA)",
        showlegend=False,
        visible=False,
    )
)

# Layer 4 (Trace 3): SNAP Direct-to-Consumer Retailers
fig.add_trace(
    go.Scattergeo(
        lon=direct_retail[lon_col],
        lat=direct_retail[lat_col],
        mode="markers",
        marker=dict(
            size=9,
            symbol="star",
            color="#2e7d32",
            line=dict(width=1, color="black"),
        ),
        text=direct_retail.apply(
            lambda r: (
                f"<b>{r[name_col]}</b><br>"
                f"Type: {r[type_col]}<br>"
                f"Address: {r.get('address', '')}"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="Direct-Market SNAP Outlets",
        showlegend=False,
        visible=False,
    )
)

# --- Step 5: Configure Layer Control Dropdown ---
fig.update_layout(
    geo=dict(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        showsubunits=True,
        subunitcolor="white",
        bgcolor="#f8fafc",
        domain=dict(x=[0.02, 0.98], y=[0.08, 0.98]),
    ),
    margin={"r": 10, "t": 10, "l": 10, "b": 38},
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#263238"),
    showlegend=False,
)

# --- Step 6: Render the map inside a responsive dashboard page ---
map_fragment = fig.to_html(
    full_html=False,
    include_plotlyjs=True,
    div_id="fab-map",
    config={"responsive": True, "displaylogo": False},
)

need_groups = {
    category: county_df[county_df["need_category"] == category].sort_values(
        "fab_priority_score", ascending=False
    )
    for category in ("High Need", "Medium Need", "Low Need")
}
high_need = need_groups["High Need"]
medium_need = need_groups["Medium Need"]
low_need = need_groups["Low Need"]
high_with_outlets = int(high_need["direct_market_count"].gt(0).sum())
high_without_outlets = int(high_need["direct_market_count"].eq(0).sum())


def render_need_table(category, findings):
  group = need_groups[category]
  rows = "".join(
      "<tr>"
      f"<td>{html.escape(str(row['County']))}</td>"
      f"<td class=\"score-value\">{row['fab_priority_score']:.1f}</td>"
      f"<td class=\"outlet-value\">{int(row['direct_market_count'])}</td>"
      "</tr>"
      for _, row in group.iterrows()
  )
  average_score = group["fab_priority_score"].mean()
  return f"""
        <article class="need-card need-{category.split()[0].lower()}">
          <span class="layer-tag">{len(group)} counties</span>
          <h3>{category}</h3>
          <p class="need-finding">{findings}</p>
          <p class="need-summary">Average score <strong>{average_score:.1f}</strong></p>
          <div class="table-wrap">
            <table>
              <thead><tr><th scope="col">County</th><th scope="col">Score</th><th scope="col">Markets</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        </article>"""


need_cards = "".join(
    [
        render_need_table(
            "High Need",
            (
                f"{high_with_outlets} counties have listed markets to onboard or"
                f" expand; {high_without_outlets} have none listed and may need"
                " alternative retail options."
            ),
        ),
        render_need_table(
            "Medium Need",
            f"All {len(medium_need)} counties have no listed Farmers and Markets"
            " SNAP outlets; scores are below the High Need cutoff.",
        ),
        render_need_table(
            "Low Need",
            f"All {len(low_need)} counties have at least one listed market"
            f" ({int(low_need['direct_market_count'].sum())} total); scores are"
            " lower relative to other counties.",
        ),
    ]
)

html_page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#123b32">
  <title>Florida FAB | Priority Navigator</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      color: #172a26;
      background: #f3f6f5;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-width: 320px; }}
    .topbar {{
      background: #123b32;
      color: #fff;
      padding: 18px clamp(20px, 5vw, 72px);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      border-bottom: 4px solid #d5a843;
    }}
    .brand {{ display: flex; align-items: center; gap: 13px; }}
    .brand-mark {{
      width: 40px; height: 40px; border-radius: 12px;
      display: grid; place-items: center; background: #e8f1e8;
      color: #175541; font-size: 19px; font-weight: 800;
    }}
    .brand-name {{ font-size: 12px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }}
    .brand-subtitle {{ margin-top: 4px; color: #c4d6ce; font-size: 12px; }}
    .top-tag {{
      border: 1px solid #54766d; color: #e0ebe5; border-radius: 999px;
      padding: 7px 12px; font-size: 11px; letter-spacing: .06em; white-space: nowrap;
    }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 30px clamp(16px, 4vw, 56px) 48px; }}
    .intro {{ display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 22px; }}
    .eyebrow {{ color: #53746a; font-size: 11px; font-weight: 750; letter-spacing: .14em; text-transform: uppercase; }}
    h1 {{ margin: 7px 0 7px; color: #173c32; font-size: clamp(26px, 3.2vw, 38px); line-height: 1.12; letter-spacing: -.035em; }}
    .lede {{ max-width: 720px; margin: 0; color: #60716b; font-size: 14px; line-height: 1.65; }}
    .county-count {{ flex: none; color: #466158; font-size: 12px; font-weight: 650; }}
    .panel {{
      overflow: hidden; background: #fff; border: 1px solid #e1e9e5;
      border-radius: 16px; box-shadow: 0 8px 28px rgba(27, 58, 46, .07);
    }}
    .controlbar {{
      min-height: 82px; display: flex; align-items: center; gap: 20px;
      padding: 16px 22px; border-bottom: 1px solid #e8eeeb;
    }}
    .control-label {{ color: #183e33; font-size: 13px; font-weight: 750; white-space: nowrap; }}
    .select-wrap {{ position: relative; flex: 0 0 min(260px, 36vw); }}
    select {{
      appearance: none; width: 100%; padding: 11px 38px 11px 13px;
      border: 1px solid #ccd9d3; border-radius: 9px; background: #fbfcfb;
      color: #183e33; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer;
    }}
    .select-wrap:after {{ content: "⌄"; position: absolute; right: 14px; top: 7px; color: #53746a; pointer-events: none; }}
    .view-help {{ max-width: 620px; margin: 0; color: #65756f; font-size: 12px; line-height: 1.55; }}
    .map-legend {{
      width: 100%; min-height: 34px; display: flex; align-items: center;
      flex-wrap: wrap; gap: 14px; padding: 10px 0 0;
      border-top: 1px solid #e8eeeb;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 7px; color: #52675e; font-size: 10px; }}
    .legend-item[hidden] {{ display: none; }}
    .legend-category {{ display: flex; align-items: center; gap: 5px; }}
    .legend-category-ramp {{ width: 42px; height: 9px; border-radius: 999px; }}
    .legend-low-ramp {{ background: linear-gradient(90deg, #A1D99B, #238B45); }}
    .legend-medium-ramp {{ background: linear-gradient(90deg, #FEE391, #B8860B); }}
    .legend-high-ramp {{ background: linear-gradient(90deg, #FC9272, #B2182B); }}
    .legend-category-name {{ font-weight: 700; }}
    .legend-direction {{ color: #65756f; }}
    .legend-ramp {{ width: 92px; height: 9px; border-radius: 999px; }}
    .legend-snap-ramp {{ background: linear-gradient(90deg, #f7f4f9, #9e9ac8, #4a1486); }}
    .legend-symbol {{ display: inline-block; flex: none; }}
    .legend-diamond {{ width: 9px; height: 9px; background: #004d40; transform: rotate(45deg); }}
    .legend-star {{ color: #2e7d32; font-size: 16px; line-height: 10px; }}
    .legend-low, .legend-high {{ color: #40584e; font-variant-numeric: tabular-nums; }}
    .map-wrap {{ height: min(67vh, 700px); min-height: 470px; padding: 6px 12px 0; }}
    #fab-map {{ width: 100%; height: 100%; }}
    .score-card {{
      margin: 20px 0; padding: 22px 24px; display: grid;
      grid-template-columns: minmax(210px, .75fr) 2fr; gap: 28px;
      background: #eaf1ed; border: 1px solid #dce8e1; border-radius: 14px;
    }}
    .score-card h2 {{ margin: 0 0 8px; color: #173c32; font-size: 16px; }}
    .score-card p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    .score-details {{ display: grid; gap: 13px; }}
    .layer-guide {{ margin-top: 20px; }}
    .layer-guide h2 {{ margin: 5px 0 13px; color: #173c32; font-size: 18px; }}
    .layer-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .layer-card {{
      min-height: 142px; padding: 18px; background: #eaf1ed;
      border: 1px solid #dce8e1; border-radius: 14px;
    }}
    .layer-card h3 {{ margin: 0 0 8px; color: #173c32; font-size: 14px; }}
    .layer-card p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    .layer-tag {{
      display: inline-block; margin-bottom: 10px; padding: 4px 8px;
      border-radius: 999px; background: #fff; color: #53746a;
      font-size: 9px; font-weight: 750; letter-spacing: .1em; text-transform: uppercase;
    }}
    .findings {{ margin-top: 30px; }}
    .findings h2 {{ margin: 5px 0 7px; color: #173c32; font-size: 20px; }}
    .findings-intro {{ margin: 0 0 16px; color: #65756f; font-size: 12px; line-height: 1.6; }}
    .need-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start; }}
    .need-card {{
      min-width: 0; padding: 18px; background: #eaf1ed;
      border: 1px solid #dce8e1; border-radius: 14px;
    }}
    .need-card h3 {{ margin: 0 0 8px; color: #173c32; font-size: 16px; }}
    .need-card .layer-tag {{ margin-bottom: 8px; }}
    .need-finding {{ min-height: 58px; margin: 0; color: #53665e; font-size: 12px; line-height: 1.6; }}
    .need-summary {{ margin: 10px 0; color: #53665e; font-size: 11px; }}
    .need-summary strong {{ color: #175541; font-size: 14px; }}
    .table-wrap {{ max-height: 390px; overflow: auto; border: 1px solid #dce7e1; border-radius: 9px; background: #fff; }}
    .need-card table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: left; }}
    .need-card thead {{ position: sticky; top: 0; z-index: 1; background: #f3f7f4; }}
    .need-card th {{ padding: 9px 8px; color: #49645a; font-size: 10px; font-weight: 750; }}
    .need-card td {{ padding: 8px; color: #344a41; border-top: 1px solid #edf1ee; }}
    .need-card tbody tr:nth-child(even) {{ background: #fafcfb; }}
    .score-value, .outlet-value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .need-high {{ border-top: 3px solid #B2182B; }}
    .need-medium {{ border-top: 3px solid #B8860B; }}
    .need-low {{ border-top: 3px solid #238B45; }}
    .impact-note {{
      margin-top: 14px; padding: 18px; background: #eaf1ed;
      border: 1px solid #dce8e1; border-left: 4px solid #588571;
      border-radius: 14px;
    }}
    .impact-note h3 {{ margin: 0 0 7px; color: #173c32; font-size: 15px; }}
    .impact-note p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    .weights {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .weight {{
      padding: 7px 10px; border-radius: 7px; background: #fff;
      color: #34574b; font-size: 11px; font-weight: 700;
      border: 1px solid #dce7e1;
    }}
    .weight strong {{ color: #175541; }}
    .fine-print {{ color: #6a7b74 !important; font-size: 11px !important; }}
    footer {{ padding: 18px 0 0; color: #7a8983; font-size: 10px; }}
    @media (max-width: 700px) {{
      .topbar {{ padding: 15px 18px; }}
      .top-tag {{ display: none; }}
      main {{ padding: 22px 13px 32px; }}
      .intro {{ display: block; }}
      .county-count {{ margin-top: 12px; }}
      .controlbar {{ align-items: stretch; flex-direction: column; gap: 9px; padding: 15px; }}
      .select-wrap {{ flex-basis: auto; width: 100%; }}
      .map-legend {{ gap: 10px 14px; }}
      .map-wrap {{ height: 58vh; min-height: 390px; padding: 0; }}
      .score-card {{ grid-template-columns: 1fr; gap: 14px; padding: 18px; }}
      .layer-grid {{ grid-template-columns: 1fr; }}
      .layer-card {{ min-height: auto; }}
      .need-grid {{ grid-template-columns: 1fr; }}
      .need-finding {{ min-height: auto; }}
    }}
    @media (min-width: 520px) and (max-width: 900px) {{
      .layer-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .need-grid {{ grid-template-columns: 1fr; }}
      .table-wrap {{ max-height: 360px; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">F</div>
      <div>
        <div class="brand-name">FAB</div>
        <div class="brand-subtitle">Florida community access &amp; opportunity</div>
      </div>
    </div>
    <div class="top-tag">FLORIDA · 67 COUNTIES</div>
  </header>
  <main>
    <section class="intro" aria-labelledby="page-title">
      <div>
        <div class="eyebrow">Program planning dashboard</div>
        <h1 id="page-title">Priority Navigator</h1>
        <p class="lede">Explore where nutrition incentive programs may have the greatest opportunity to improve access to fresh, Florida-grown food.</p>
      </div>
      <div class="county-count">County scores, tract patterns &amp; authorized outlets</div>
    </section>
    <section class="score-card" aria-labelledby="score-title">
      <div>
        <div class="eyebrow">How to read the map</div>
        <h2 id="score-title">What is the FAB Priority Score?</h2>
        <p>A county’s score is the average of the need scores for its census tracts. Higher scores indicate greater relative need compared with other Florida counties; the county average is not weighted by population.</p>
      </div>
      <div class="score-details">
        <p>Each tract score combines three signals into a 0–100 measure: how its estimated household SNAP participation and poverty compare with other tracts, plus whether USDA identifies it as both low-income and far from a supermarket by driving distance.</p>
        <div class="weights" aria-label="Score components">
          <span class="weight"><strong>40%</strong> Relative SNAP participation</span>
          <span class="weight"><strong>30%</strong> Relative poverty</span>
          <span class="weight"><strong>30%</strong> USDA driving-distance access flag</span>
        </div>
        <p class="fine-print">SNAP participation is estimated using tract population divided by 2.5 households per person. USDA’s low-income/low-access flag uses a 1-mile threshold for urban areas and 10 miles for rural areas. Retail outlet counts inform the strategy classification, not the score itself.</p>
      </div>
    </section>
    <section class="panel" aria-label="Interactive Florida map">
      <div class="controlbar">
        <label class="control-label" for="map-view">Map view</label>
        <div class="select-wrap">
          <select id="map-view" aria-describedby="view-help">
            <option value="county">County priority</option>
            <option value="snap">Tract SNAP participation</option>
            <option value="lila">Driving-access barriers</option>
            <option value="retail">SNAP-authorized farm outlets</option>
            <option value="all">All layers</option>
          </select>
        </div>
        <p class="view-help" id="view-help">Compare counties by relative need. Select a county to see its score, SNAP participation, access barriers, and program strategy.</p>
        <div class="map-legend" id="map-legend" aria-label="Map legend" aria-live="polite">
          <div class="legend-item" data-legend="county">
            <span>FAB Priority Score:</span>
            <span class="legend-category"><span class="legend-category-name">Low</span><span class="legend-category-ramp legend-low-ramp" aria-hidden="true"></span></span>
            <span class="legend-category"><span class="legend-category-name">Medium</span><span class="legend-category-ramp legend-medium-ramp" aria-hidden="true"></span></span>
            <span class="legend-category"><span class="legend-category-name">High</span><span class="legend-category-ramp legend-high-ramp" aria-hidden="true"></span></span>
            <span class="legend-direction">lighter to darker = lower to higher score within each group</span>
          </div>
          <div class="legend-item" data-legend="snap" hidden>
            <span>Tract SNAP rate</span>
            <span class="legend-low">0%</span>
            <span class="legend-ramp legend-snap-ramp" aria-hidden="true"></span>
            <span class="legend-high">100%</span>
          </div>
          <div class="legend-item" data-legend="lila" hidden>
            <span class="legend-symbol legend-diamond" aria-hidden="true"></span>
            <span>USDA low-income, low-access tract</span>
          </div>
          <div class="legend-item" data-legend="retail" hidden>
            <span class="legend-symbol legend-star" aria-hidden="true">★</span>
            <span>SNAP Farmers and Markets outlet</span>
          </div>
        </div>
      </div>
      <div class="map-wrap">{map_fragment}</div>
    </section>
    <section class="layer-guide" aria-labelledby="layer-guide-title">
      <div class="eyebrow">Map guide</div>
      <h2 id="layer-guide-title">Explore the layers</h2>
      <div class="layer-grid">
        <article class="layer-card">
          <span class="layer-tag">County view</span>
          <h3>FAB Priority</h3>
          <p>County color shows its need category: green for Low, yellow for Medium, and red for High. Within each category, darker shades indicate higher scores. Hover over a county for its exact score, SNAP rate, access barriers, outlets, and strategy.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Census tract view</span>
          <h3>Tract SNAP participation</h3>
          <p>Each dot represents a Florida census tract. Its color shows the estimated share of households participating in SNAP; darker purple indicates a higher rate. Use the map legend to compare rates.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">USDA access view</span>
          <h3>Driving-access barriers</h3>
          <p>Diamonds mark USDA low-income, low-access tracts, where supermarket driving distance exceeds 1 mile in urban areas or 10 miles in rural areas.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Retail view</span>
          <h3>SNAP farm outlets</h3>
          <p>Stars show SNAP retailers classified as “Farmers and Markets” in the Florida retailer file. These locations may offer opportunities for FAB outreach.</p>
        </article>
      </div>
    </section>
    <section class="findings" aria-labelledby="findings-title">
      <div class="eyebrow">County findings</div>
      <h2 id="findings-title">Need categories at a glance</h2>
      <p class="findings-intro">Categories reflect relative FAB Priority Scores and listed SNAP-authorized Farmers and Markets. Scores are out of 100; market counts come from the available retailer file.</p>
      <div class="need-grid">{need_cards}
      </div>
    </section>
    <section class="impact-note" aria-labelledby="impact-title">
      <span class="layer-tag">Planning context</span>
      <h3 id="impact-title">Why focus on high-need counties?</h3>
      <p>High-need counties have more concentrated challenges—not necessarily the most people in need overall. FAB may make a bigger difference for households where food budgets and access are both barriers. This score helps guide planning; it does not predict total impact, and a larger county with a lower score may still serve more people.</p>
    </section>
    <footer>Planning reference only · County colors show need category; darker shade means higher score within that group · Map layers use USDA and Census data</footer>
  </main>
  <script>
    const viewHelp = {{
      county: "Compare counties by relative need. Select a county to see its score, SNAP participation, access barriers, and program strategy.",
      snap: "Each dot represents a Florida census tract. Darker purple indicates a higher estimated household SNAP participation rate; use the map legend to compare rates.",
      lila: "Diamonds mark USDA-designated low-income, low-access tracts based on driving distance to supermarkets.",
      retail: "Stars show Florida SNAP-authorized farmers’ markets and direct-marketing farmers included in this dataset.",
      all: "View county priority scores together with tract SNAP participation rates, driving-access barriers, and SNAP-authorized farm outlets."
    }};
    const visibility = {{
      county: [true, false, false, false],
      snap: [true, true, false, false],
      lila: [true, false, true, false],
      retail: [true, false, false, true],
      all: [true, true, true, true]
    }};
    const viewSelect = document.getElementById("map-view");
    viewSelect.addEventListener("change", () => {{
      const selected = viewSelect.value;
      document.getElementById("view-help").textContent = viewHelp[selected];
      document.querySelectorAll(".legend-item").forEach((item) => {{
        item.hidden = selected !== "all" && item.dataset.legend !== selected;
      }});
      visibility[selected].forEach((visible, traceIndex) => {{
        Plotly.restyle("fab-map", {{visible}}, [traceIndex]);
      }});
    }});
  </script>
</body>
</html>
"""

output_html = "outputs/florida_fab_priority_map.html"
for path in (output_html, "index.html"):
  with open(path, "w", encoding="utf-8") as output_file:
    output_file.write(html_page)
print(f"[OK] Multi-layer map generated at {output_html} and index.html")