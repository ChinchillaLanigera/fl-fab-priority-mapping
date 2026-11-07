import html
import json
import os
import urllib.parse
import urllib.request
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

# Fetch 2020 Florida census-tract centroids from Census TIGERweb
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
tract_col = next(c for c in tracts_df.columns if "censustract" in str(c).lower() or "tract" in str(c).lower())
tracts_df[tract_col] = tracts_df[tract_col].astype(str).str.split(".").str[0].str.zfill(11)
tracts_df = tracts_df.rename(columns={tract_col: "CensusTract20"})

tracts_df = tracts_df.merge(
    tract_centroids,
    on="CensusTract20",
    how="left",
    validate="one_to_one",
)

# --- Step 3: Prepare Point Layers ---
snap_tracts = tracts_df.copy()
lila_tracts = tracts_df[tracts_df["LILA_Flag"] == 1].copy()

# Filter SNAP Retailers for Direct Outlets
retail_df.columns = [
    c.strip().lower().replace(" ", "_") for c in retail_df.columns
]
state_col = next(c for c in retail_df.columns if "state" in c)
if "store_type" not in retail_df.columns:
    raise KeyError("Expected a 'store_type' column in the retailer data.")
type_col = "store_type"
lat_col = next(c for c in retail_df.columns if "lat" in c)
lon_col = next(c for c in retail_df.columns if "lon" in c)
name_col = next(c for c in retail_df.columns if "name" in c)

direct_types = ["farmers and markets", "farmers' market", "direct marketing farmer"]
grocery_types = [
    "supermarket",
    "large grocery store",
    "medium grocery store",
    "super store",
]
fringe_types = ["convenience store", "combination grocery/other"]
direct_retail = retail_df[
    (retail_df[state_col].astype(str).str.upper() == "FL")
    & (retail_df[type_col].astype(str).str.lower().isin(direct_types))
].copy()
direct_retail = direct_retail.dropna(subset=[lat_col, lon_col])
grocery_retail = retail_df[
    (retail_df[state_col].astype(str).str.upper() == "FL")
    & (retail_df[type_col].astype(str).str.strip().str.lower().isin(grocery_types))
].copy()
grocery_retail = grocery_retail.dropna(subset=[lat_col, lon_col])
fringe_retail = retail_df[
    (retail_df[state_col].astype(str).str.upper() == "FL")
    & (retail_df[type_col].astype(str).str.strip().str.lower().isin(fringe_types))
].copy()
fringe_retail = fringe_retail.dropna(subset=[lat_col, lon_col])

# --- Step 4: Assemble Multi-Layer Plotly Figure ---
print("--- Step 4: Assembling Plotly Traces ---")
county_df["need_category"] = county_df["Need_Tier"]
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

county_df["color_value"] = 0.0
for category, (range_start, range_end) in category_color_ranges.items():
    category_mask = county_df["need_category"] == category
    category_scores = county_df.loc[
        category_mask, "fab_expected_impact_score"
    ]
    score_span = category_scores.max() - category_scores.min()
    if score_span:
        score_fraction = (category_scores - category_scores.min()) / score_span
    else:
        score_fraction = pd.Series(0.5, index=category_scores.index)
    county_df.loc[category_mask, "color_value"] = (
        range_start + score_fraction * (range_end - range_start)
    )

county_colorscale = []
for category, (range_start, range_end) in category_color_ranges.items():
    light_color, dark_color = category_colors[category]
    county_colorscale.extend([
        [range_start / 3, light_color],
        [range_end / 3, dark_color],
    ])

fig = go.Figure()

# Trace 0: County Base Choropleth
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
                f"Expected Impact Score: {r['fab_expected_impact_score']:.1f}<br>"
                f"Avg SNAP Rate: {r['avg_snap_rate']*100:.1f}%<br>"
                f"Direct Farm Markets: {r['direct_market_count']} "
                f"({r['direct_per_10k_snap']:.1f}/10k SNAP HH)<br>"
                f"Supermarkets / Grocers: {r['grocery_store_count']}<br>"
                f"Driving LILA Tracts: {r['driving_lila_tracts']}<br>"
                f"Partner: {r['food_bank_partner']}<br>"
                f"Action Profile: {r['Strategy_Typology']}"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="County Priority Index",
        visible=True,
    )
)

# Trace 1: Tract SNAP Participation Points
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
        name="Tract SNAP Usage",
        showlegend=False,
        visible=False,
    )
)

# Trace 2: Driving-Distance LILA Barriers
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
                f"<b>Transit Barrier Tract {r['CensusTract20']}</b><br>"
                f"Low Access: >10 mi rural / >1 mi urban<br>"
                f"SNAP Rate: {r['SNAP_Rate']*100:.1f}%"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="Driving barriers (LILA)",
        showlegend=False,
        visible=False,
    )
)

# Trace 3: Direct-to-Consumer SNAP Outlets
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
        name="SNAP Farm markets",
        showlegend=False,
        visible=False,
    )
)

# Trace 4: SNAP-authorized grocers, excluding convenience/fringe outlets
fig.add_trace(
    go.Scattergeo(
        lon=grocery_retail[lon_col],
        lat=grocery_retail[lat_col],
        mode="markers",
        marker=dict(
            size=9,
            symbol="star",
            color="#1565c0",
            opacity=0.85,
            line=dict(width=1, color="white"),
        ),
        text=grocery_retail.apply(
            lambda r: (
                f"<b>{r[name_col]}</b><br>"
                f"Type: {r[type_col]}<br>"
                f"County: {r.get('county', 'N/A')}<br>"
                f"Address: {r.get('store_street_address', '')}"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="SNAP Grocers",
        showlegend=False,
        visible=False,
    )
)

# Trace 5: SNAP-authorized convenience and fringe retailers
fig.add_trace(
    go.Scattergeo(
        lon=fringe_retail[lon_col],
        lat=fringe_retail[lat_col],
        mode="markers",
        marker=dict(
            size=8,
            symbol="star",
            color="#7b1fa2",
            opacity=0.8,
            line=dict(width=1, color="white"),
        ),
        text=fringe_retail.apply(
            lambda r: (
                f"<b>{r[name_col]}</b><br>"
                f"Type: {r[type_col]}<br>"
                f"County: {r.get('county', 'N/A')}<br>"
                f"Address: {r.get('store_street_address', '')}"
            ),
            axis=1,
        ),
        hoverinfo="text",
        name="SNAP Fringe (Conv. Stores, etc.)",
        showlegend=False,
        visible=False,
    )
)

# Layout Setup
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

# --- Step 5: Render Dashboard HTML ---
map_fragment = fig.to_html(
    full_html=False,
    include_plotlyjs=True,
    div_id="fab-map",
    config={"responsive": True, "displaylogo": False},
)

need_groups = {
    category: county_df[county_df["need_category"] == category].sort_values(
        "fab_expected_impact_score", ascending=False
    )
    for category in ("High Need", "Medium Need", "Low Need")
}

def render_need_table(category, findings):
    group = need_groups[category]
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['County']))}</td>"
        f"<td class=\"score-value\">{row['fab_expected_impact_score']:.1f}</td>"
        f"<td class=\"outlet-value\">{int(row.get('direct_market_count', 0))}</td>"
        f"<td class=\"outlet-value\">{int(row.get('grocery_store_count', 0))}</td>"
        "</tr>"
        for _, row in group.iterrows()
    )
    average_score = group["fab_expected_impact_score"].mean()
    return f"""
        <article class="need-card need-{category.split()[0].lower()}">
          <span class="layer-tag">{len(group)} counties</span>
          <h3>{category}</h3>
          <p class="need-finding">{findings}</p>
          <p class="need-summary">Average impact score <strong>{average_score:.1f}</strong></p>
          <div class="table-wrap">
            <table>
              <thead><tr><th scope="col">County</th><th scope="col">Impact</th><th scope="col">Farm Mkts</th><th scope="col">Grocers</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        </article>"""

high_need = need_groups["High Need"]
high_with_outlets = int(high_need["direct_market_count"].gt(0).sum())
high_without_outlets = int(high_need["direct_market_count"].eq(0).sum())

need_cards = "".join([
    render_need_table(
        "High Need",
        f"{high_with_outlets} high-impact counties have listed farm markets ready for FAB onboarding; {high_without_outlets} have no farm markets and may benefit from grocery pilots, pop-ups, or mobile routes.",
    ),
    render_need_table(
        "Medium Need",
        f"Moderate-impact counties without listed farm markets; monitor for retail partnership and alternative access opportunities.",
    ),
    render_need_table(
        "Low Need",
        f"Moderate-impact counties with a direct-market baseline already present.",
    ),
])

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
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-width: 320px; }}
    .topbar {{
      background: #123b32; color: #fff; padding: 18px clamp(20px, 5vw, 72px);
      display: flex; align-items: center; justify-content: space-between; gap: 20px;
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
      padding: 7px 12px; font-size: 11px; letter-spacing: .06em;
    }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 30px clamp(16px, 4vw, 56px) 48px; }}
    .intro {{ display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 22px; }}
    .eyebrow {{ color: #53746a; font-size: 11px; font-weight: 750; letter-spacing: .14em; text-transform: uppercase; }}
    h1 {{ margin: 7px 0 7px; color: #173c32; font-size: clamp(26px, 3.2vw, 38px); line-height: 1.12; }}
    .lede {{ max-width: 720px; margin: 0; color: #60716b; font-size: 14px; line-height: 1.65; }}
    .score-card {{
      display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.3fr);
      gap: 24px; margin: 0 0 20px; padding: 20px;
      background: #fff; border: 1px solid #e1e9e5; border-radius: 14px;
    }}
    .score-card h2 {{ margin: 0 0 8px; color: #173c32; font-size: 16px; }}
    .score-card p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    .score-details {{ display: grid; gap: 13px; }}
    .weights {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .weight {{
      padding: 10px; border: 1px solid #dce7e1; border-radius: 7px;
      background: #fff; color: #34574b; font-size: 10px; line-height: 1.5;
    }}
    .weight strong {{ display: block; margin-bottom: 3px; color: #175541; font-size: 11px; }}
    .weight p {{ margin: 4px 0 0; font-size: 10px; line-height: 1.5; }}
    .formula {{ font-family: "Segoe UI", Arial, sans-serif; font-weight: 650; }}
    .fine-print {{ color: #6a7b74 !important; font-size: 11px !important; }}
    .panel {{
      overflow: hidden; background: #fff; border: 1px solid #e1e9e5;
      border-radius: 16px; box-shadow: 0 8px 28px rgba(27, 58, 46, .07);
    }}
    .controlbar {{
      min-height: 82px; display: flex; align-items: center; gap: 20px;
      padding: 16px 22px; border-bottom: 1px solid #e8eeeb;
    }}
    .layer-controls {{ flex: 1; min-width: 0; }}
    .control-label {{ display: block; margin-bottom: 8px; color: #183e33; font-size: 13px; font-weight: 750; }}
    .layer-toggles {{ display: flex; flex-wrap: wrap; gap: 8px 14px; }}
    .layer-toggle {{ display: inline-flex; align-items: center; gap: 6px; color: #34574b; font-size: 11px; font-weight: 650; cursor: pointer; }}
    .layer-toggle input {{ accent-color: #175541; }}
    .layer-actions {{ display: flex; gap: 8px; margin-top: 8px; }}
    .layer-actions button {{
      padding: 5px 9px; border: 1px solid #ccd9d3; border-radius: 6px;
      background: #fbfcfb; color: #34574b; font: inherit; font-size: 10px; cursor: pointer;
    }}
    .view-help {{ max-width: 350px; margin: 0; color: #65756f; font-size: 12px; line-height: 1.55; }}
    .map-wrap {{ height: min(67vh, 700px); min-height: 470px; padding: 6px 12px 0; }}
    #fab-map {{ width: 100%; height: 100%; }}
    .layer-guide {{ margin-top: 20px; }}
    .layer-guide h2 {{ margin: 5px 0 13px; color: #173c32; font-size: 18px; }}
    .layer-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .layer-card {{
      min-height: 142px; padding: 18px; background: #eaf1ed;
      border: 1px solid #dce8e1; border-radius: 14px;
    }}
    .layer-card h3 {{ margin: 0 0 8px; color: #173c32; font-size: 14px; }}
    .layer-card p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    .findings {{ margin-top: 30px; }}
    .findings h2 {{ margin: 5px 0 7px; color: #173c32; font-size: 20px; }}
    .findings-intro {{ margin: 0 0 16px; color: #65756f; font-size: 12px; line-height: 1.6; }}
    .need-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start; }}
    .need-card {{ min-width: 0; padding: 18px; background: #eaf1ed; border: 1px solid #dce8e1; border-radius: 14px; }}
    .need-card h3 {{ margin: 0 0 8px; color: #173c32; font-size: 16px; }}
    .need-card .layer-tag {{ margin-bottom: 8px; }}
    .need-finding {{ min-height: 58px; margin: 0; color: #53665e; font-size: 12px; line-height: 1.6; }}
    .need-summary {{ margin: 10px 0; color: #53665e; font-size: 11px; }}
    .need-summary strong {{ color: #175541; font-size: 14px; }}
    .table-wrap {{ max-height: 390px; overflow: auto; border: 1px solid #dce7e1; border-radius: 9px; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    thead {{ position: sticky; top: 0; background: #f3f7f4; }}
    th, td {{ padding: 8px; text-align: left; border-top: 1px solid #edf1ee; }}
    .score-value, .outlet-value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .layer-tag {{ display: inline-block; padding: 4px 8px; border-radius: 999px; background: #fff; color: #53746a; font-size: 9px; font-weight: 750; }}
    .need-high {{ border-top: 3px solid #B2182B; }}
    .need-medium {{ border-top: 3px solid #B8860B; }}
    .need-low {{ border-top: 3px solid #238B45; }}
    .impact-note {{
      margin-top: 14px; padding: 18px; background: #eaf1ed;
      border: 1px solid #dce8e1; border-left: 4px solid #588571; border-radius: 14px;
    }}
    .impact-note h3 {{ margin: 0 0 7px; color: #173c32; font-size: 15px; }}
    .impact-note p {{ margin: 0; color: #53665e; font-size: 12px; line-height: 1.65; }}
    footer {{ padding: 18px 0 0; color: #7a8983; font-size: 10px; }}
    @media (max-width: 700px) {{
      .topbar {{ padding: 15px 18px; }}
      .top-tag {{ display: none; }}
      main {{ padding: 22px 13px 32px; }}
      .intro {{ display: block; }}
      .score-card {{ grid-template-columns: 1fr; gap: 14px; }}
      .controlbar {{ align-items: stretch; flex-direction: column; gap: 9px; padding: 15px; }}
      .layer-grid, .need-grid {{ grid-template-columns: 1fr; }}
      .layer-card {{ min-height: auto; }}
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
      <div class="brand-mark">F</div>
      <div>
        <div class="brand-name">FAB</div>
        <div class="brand-subtitle">Florida community access &amp; opportunity</div>
      </div>
    </div>
    <div class="top-tag">FLORIDA · 67 COUNTIES</div>
  </header>
  <main>
    <section class="intro">
      <div>
        <div class="eyebrow">Program planning dashboard</div>
        <h1>Priority Navigator</h1>
        <p class="lede">Explore where nutrition incentive programs have the greatest opportunity to improve access to fresh, Florida-grown food.</p>
      </div>
    </section>
    <section class="score-card" aria-labelledby="score-title">
      <div>
        <div class="eyebrow">How to read the map</div>
        <h2 id="score-title">What is the FAB Expected Impact Score?</h2>
        <p>The score ranks counties by a combination of SNAP participation, poverty, driving-distance access barriers, and direct-market readiness. Higher scores indicate stronger potential for FAB impact based on these factors.</p>
      </div>
      <div class="score-details">
        <p class="formula">Expected Impact = 45% × SNAP Rate Rank + 20% × Poverty Rank + 15% × Driving-Frictions Rank + 20% × Direct-Market Capacity Rank</p>
        <div class="weights" aria-label="Score components">
          <div class="weight">
            <strong>Pillar 1 · Target Proportion · 45%</strong>
            Average estimated SNAP household participation rate, ranked across counties. This emphasizes communities where SNAP participation is a larger share of the population, not just counties with more people.
          </div>
          <div class="weight">
            <strong>Pillar 1b · Economic Hardship Depth · 20%</strong>
            Average tract poverty rate, ranked across counties. Keeping poverty adds a distinct hardship signal; its lower weight helps limit overlap with SNAP participation.
          </div>
          <div class="weight">
            <strong>Pillar 2 · Geographic Food Access Barrier · 15%</strong>
            Share of county tracts flagged by USDA for low income and long supermarket driving distance, ranked across counties. The share adjusts for county size; the lower weight prevents a binary access flag from dominating.
          </div>
          <div class="weight">
            <strong>Pillar 3 · Point-of-Sale Feasibility · 20%</strong>
            Direct farm-market outlets per 10,000 estimated SNAP households, ranked across counties. Existing market capacity can make FAB easier to use right away; counties without outlets may instead need a grocery pilot, pop-up, or mobile route.
          </div>
        </div>
        <p class="fine-print">All four county measures are converted to percentile ranks before weighting. SNAP participation is an indicator for planning—not an individual eligibility determination. USDA driving-distance thresholds are more than 1 mile in urban areas and more than 10 miles in rural areas. This relative score is not a forecast of redemptions or guaranteed impact.</p>
      </div>
    </section>
    <section class="panel">
      <div class="controlbar">
        <div class="layer-controls">
          <span class="control-label">Map layers</span>
          <div class="layer-toggles" role="group" aria-label="Toggle map layers">
            <label class="layer-toggle"><input type="checkbox" data-trace="1"> Tract SNAP Usage</label>
            <label class="layer-toggle"><input type="checkbox" data-trace="2"> Driving barriers (LILA)</label>
            <label class="layer-toggle"><input type="checkbox" data-trace="3"> SNAP Farm markets</label>
            <label class="layer-toggle"><input type="checkbox" data-trace="4"> SNAP Grocers</label>
            <label class="layer-toggle"><input type="checkbox" data-trace="5"> SNAP Fringe (Conv. Stores, etc.)</label>
          </div>
          <div class="layer-actions">
            <button type="button" id="show-all-layers">Add all</button>
            <button type="button" id="clear-layers">Clear overlays</button>
          </div>
        </div>
        <p class="view-help" id="view-help">County priority is always shown. Check any overlays to add them; uncheck to remove them.</p>
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
          <p>County color shows its need category: green for Low, yellow for Medium, and red for High. Within each category, darker shades indicate a higher expected impact score. Hover over a county for its score, SNAP rate, access barriers, outlets, and strategy.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Census tract view</span>
          <h3>Tract SNAP Usage</h3>
          <p>Each dot represents a Florida census tract. Its color shows the estimated share of households participating in SNAP; darker purple indicates a higher rate. Use the map legend to compare rates.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">USDA access view</span>
          <h3>Driving barriers (LILA)</h3>
          <p>Diamonds mark USDA low-income, low-access tracts, where supermarket driving distance exceeds 1 mile in urban areas or 10 miles in rural areas.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Retail view</span>
          <h3>SNAP Farm markets</h3>
          <p>Green stars show SNAP retailers classified as “Farmers and Markets” in the Florida retailer file. These locations may offer opportunities for FAB outreach.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Grocery view</span>
          <h3>SNAP Grocers</h3>
          <p>Blue stars show SNAP-authorized Supermarket, Large Grocery Store, Medium Grocery Store, and Super Store locations. Convenience, fringe, and other store categories are excluded and counted separately.</p>
        </article>
        <article class="layer-card">
          <span class="layer-tag">Fringe view</span>
          <h3>SNAP Fringe (Conv. Stores, etc.)</h3>
          <p>Purple stars show SNAP-authorized convenience stores and combination grocery/other retailers. These are tracked separately from full-line grocers.</p>
        </article>
      </div>
    </section>
    <section class="findings" aria-labelledby="findings-title">
      <div class="eyebrow">County findings</div>
      <h2 id="findings-title">Need categories at a glance</h2>
      <p class="findings-intro">Need categories use the top 40% of counties by Expected Impact Score plus direct-market availability. Scores are out of 100; market counts come from the available retailer file.</p>
      <div class="need-grid">{need_cards}</div>
    </section>
    <section class="impact-note" aria-labelledby="impact-title">
      <span class="layer-tag">Planning context</span>
      <h3 id="impact-title">Why focus on high-need counties?</h3>
      <p>High-need counties have more concentrated challenges—not necessarily the most people in need overall. FAB may make a bigger difference for households where food budgets and access are both barriers. This score helps guide planning; it does not predict total impact, and a larger county with a lower score may still serve more people.</p>
    </section>
    <footer>Planning reference only · County colors show need category; darker shade means higher score within that group · Map layers use USDA and Census data</footer>
  </main>
  <script>
    const layerInputs = Array.from(
      document.querySelectorAll(".layer-toggle input[data-trace]")
    );
    const updateLayers = () => {{
      layerInputs.forEach((input) => {{
        Plotly.restyle(
          "fab-map",
          {{visible: input.checked}},
          [Number(input.dataset.trace)]
        );
      }});
      const active = layerInputs
        .filter((input) => input.checked)
        .map((input) => input.parentElement.textContent.trim());
      document.getElementById("view-help").textContent = active.length
        ? `County priority plus: ${{active.join(", ")}}.`
        : "County priority is always shown. Check any overlays to add them; uncheck to remove them.";
    }};
    layerInputs.forEach((input) => input.addEventListener("change", updateLayers));
    document.getElementById("show-all-layers").addEventListener("click", () => {{
      layerInputs.forEach((input) => input.checked = true);
      updateLayers();
    }});
    document.getElementById("clear-layers").addEventListener("click", () => {{
      layerInputs.forEach((input) => input.checked = false);
      updateLayers();
    }});
  </script>
</body>
</html>
"""

output_html = "outputs/florida_fab_priority_map.html"
for path in (output_html, "index.html"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_page)

print(f"[OK] Multi-layer dashboard generated at {output_html} and index.html")