# Florida FAB Expansion Priority Index

An open-source geospatial analytics and prioritization pipeline designed to guide the geographic expansion of the **FAB** nutrition incentive program across Florida. Administered statewide by **Feeding Florida** (Florida's network of 9 Feeding America member food banks) and supported by USDA GusNIP funding, FAB provides a dollar-for-dollar match for SNAP participants purchasing Florida-grown fruits and vegetables at direct-to-consumer outlets (farmers markets, farm stands, mobile markets, and CSAs).

This repository models community need, transit friction, and retail infrastructure across all 67 Florida counties and census tracts to identify high-priority zones for market onboarding and mobile produce interventions.

---

## Analytical Methodology & Principles

Traditional food access analyses often rely on raw population counts, which disproportionately flag dense metropolitan centers (e.g., Miami-Dade, Broward, Orange) while obscuring severe food insecurity in rural agricultural corridors. This model addresses those limitations through three core methodological design choices:

1. **Rate-Based Intensity Over Raw Counts:** Need metrics are normalized by population denominators (e.g., household SNAP participation rates rather than raw counts of SNAP recipients). This establishes geographic equity, allowing high-intensity rural communities (where 15–25% of households rely on SNAP) to compete fairly against large metro areas.
2. **Driving-Distance Friction (SRAM/LRAM):** Access barriers are evaluated through the USDA Economic Research Service (ERS) Food Access Research Atlas driving-distance metrics (`DD_SRAM_LILATracts_1And10`) rather than walking-distance measures alone. In rural and peri-urban Florida, physical road-transit distance to full-service supermarkets is the defining barrier to fresh produce.
3. **Official Administrative Store Classifications:** Rather than relying on fragile name-based keyword matching (which misclassifies commercial supermarket chains like *Publix Super Market* or *Walmart Neighborhood Market* as direct farm markets), the pipeline filters the USDA FNS SNAP Retailer Database by the `Farmers and Markets` store category present in the Florida retailer extract.

---

### Scoring Formula

Each Florida census tract receives a composite **FAB Need Score** ($0\text{–}100$):

$$\text{FAB Need Score} = 0.50 \cdot P_{\text{SNAP}} + 0.25 \cdot P_{\text{Poverty}} + 0.25 \cdot (\text{LILA}_{\text{Driving}} \times 100)$$

* $P_{\text{SNAP}}$: Percentile rank of the tract's estimated household SNAP participation rate ($0\text{–}100$). Estimated households are calculated as population divided by 2.5.
* $P_{\text{Poverty}}$: Percentile rank of tract poverty rate ($0\text{–}100$).
* $\text{LILA}_{\text{Driving}}$: Binary indicator ($1$ or $0$) from the USDA Food Access Research Atlas denoting Low Income and Low Access based on driving distances (10-mile threshold in rural areas, 1-mile in urban areas).

The county **FAB Priority Score** is the unweighted average of its tract FAB Need Scores. The county **FAB Expected Impact Score** is a separate, county-level planning measure. Each input is percentile-ranked across Florida counties, then weighted:

$$\begin{aligned}
\text{FAB Expected Impact Score} =\;&
0.45 \cdot P_{\text{SNAP Rate}}
&&\text{(Pillar 1: Target Proportion)}\\
&+ 0.20 \cdot P_{\text{Poverty}}
&&\text{(Pillar 1b: Economic Hardship Depth)}\\
&+ 0.15 \cdot P_{\text{Driving Friction}}
&&\text{(Pillar 2: Geographic Food Access Barrier)}\\
&+ 0.20 \cdot P_{\text{Direct Market Capacity}}
&&\text{(Pillar 3: Point-of-Sale Feasibility)}
\end{aligned}$$

* **Target Proportion (45%):** The county's average estimated household SNAP participation rate, ranked against other counties. This gives greater weight to places where SNAP participation is a larger share of the community, rather than simply favoring counties with more residents. SNAP participation is a planning indicator; it is not an individual eligibility determination.
* **Economic Hardship Depth (20%):** The county's average tract poverty rate, percentile-ranked. Poverty remains in the score as a distinct hardship signal, but at a lower weight than SNAP participation to limit overlap between related measures.
* **Geographic Food Access Barrier (15%):** The share of county census tracts flagged as low-income and low-access under USDA's driving-distance measure, percentile-ranked. The thresholds are more than 1 mile to a supermarket in urban areas and more than 10 miles in rural areas. Using the tract share accounts for county size; the lower weight keeps this binary geographic flag from outweighing demand and retail readiness.
* **Point-of-Sale Feasibility (20%):** SNAP-authorized direct-market outlets per 10,000 estimated SNAP households, percentile-ranked. This rewards counties with more existing direct-market capacity where FAB can be used, while market availability also informs the action profile for counties without a listed market.

The score is a relative ranking aid, not a forecast of redemptions or proof that a particular county will produce greater impact. Its market-capacity component intentionally values existing point-of-sale readiness; a high-need county with no direct market may therefore have lower feasibility on this component, while the strategy label can identify a grocery gap or mobile-route opportunity. The highest 40% of expected-impact scores are classified as **High Need**. Below that cutoff, counties with a listed direct market are **Low Need** and counties without one are **Medium Need**.

## County Need Categories

* **High Impact Potential: Active Markets Ready for FAB Onboarding:** High-priority counties with at least one listed direct-market outlet.
* **High Need Produce Gap: Supermarkets Present, Zero Farm Outlets:** High-priority counties with grocers but no listed direct-market outlets.
* **High Need Food Desert: Zero Farm Outlets, Grocery Scarcity:** High-priority counties with neither listed direct-market outlets nor grocers.
* **Moderate Need: Direct-Market Baseline Present:** Counties below the high-priority cutoff with a listed direct-market outlet.
* **Moderate Need: Retail Deficit / Monitor:** Counties below the high-priority cutoff with no listed direct-market outlet.

These are planning categories based on relative county need and the available retailer data, not a measure of program eligibility or a guarantee of adequate food access.

All 67 counties are mapped directly to their regional **Feeding Florida 9-member food bank territory** (e.g., Feeding Tampa Bay, Feeding South Florida, Second Harvest of the Big Bend, All Faiths Food Bank) to align priority rankings directly with local operational footprints.

---

## Pipeline Architecture & Scripts

The analytical pipeline is executed sequentially via Python scripts in the `scripts/` directory:

```text
├── data/
│   ├── raw/                      # Bulky raw source data (git-ignored)
│   │   ├── FoodAccessResearchAtlasData.xlsx
│   │   └── snap_retailers_fl.csv
│   └── processed/                # Lightweight pipeline deliverables
│       ├── fl_tracts_scored.csv
│       ├── fl_county_summary.csv
│       ├── fl_county_fab_strategy.csv
│       └── fl_acute_priority_tracts.csv
├── scripts/
│   ├── 01_build_fab_index.py
│   ├── 02_map_retail_gaps.py
│   ├── 03_assign_food_banks.py
│   └── 04_build_interactive_map.py
├── outputs/
│   ├── florida_fab_priority_map.html
│   └── fab_county_strategy_brief.md
├── index.html                    # Root map served via GitHub Pages
├── .gitignore
└── README.md
```

### Script Workflow

1. **`scripts/01_build_fab_index.py`**:
   * Ingests the USDA ERS Food Access Research Atlas driving-distance sheet (`DD_SRAM_LILATracts_1And10`).
   * Normalizes rates, computes tract percentiles, calculates the composite `FAB_Need_Score`, and rolls tract data up to county baselines.
   * Exports `fl_tracts_scored.csv` and `fl_county_summary.csv`.

2. **`scripts/02_map_retail_gaps.py`**:
   * Ingests the USDA FNS SNAP Retailer dataset.
   * Enforces canonical county string normalization to eliminate punctuation, spacing, and name mismatches (e.g., `MIAMI-DADE` vs. `MIAMI DADE`, `ST. JOHNS` vs. `ST JOHNS`).
   * Counts direct markets, full-line grocers, convenience/fringe retailers, and total SNAP retailers by county.
   * Computes direct-market capacity per 10,000 estimated SNAP households, percentile-ranks the four impact components, assigns need tiers and action profiles, and exports `fl_county_fab_strategy.csv`.

3. **`scripts/03_assign_food_banks.py`**:
   * Maps all 67 Florida counties to their official Feeding Florida regional food bank territory crosswalk.
   * Aggregates regional performance benchmarks and appends partner assignments to `fl_county_fab_strategy.csv`.

4. **`scripts/04_build_interactive_map.py`**:
   * Fetches county boundary GeoJSON geometries and pairs them with priority metrics.
   * Renders an interactive Plotly map with county impact scores, tract-level context, and independently toggleable farm-market, grocer, and fringe layers.
   * Exports `outputs/florida_fab_priority_map.html` and root `index.html` for GitHub Pages hosting.

---

## Data Sources

| Source | Description | Format |
| :--- | :--- | :--- |
| **USDA Economic Research Service (ERS)** | Food Access Research Atlas (FARA) — Driving Distance (SRAM) Sheet | `.xlsx` |
| **USDA Food and Nutrition Service (FNS)** | SNAP Retailer Locator Database (State of Florida extract) | `.csv` |
| **US Census Bureau / Plotly Open Data** | County FIPS Boundary Geometries | `.json` |

---

## Local Setup & Reproduction

### Prerequisites
* Python 3.9+
* VS Code (or preferred IDE)

### 1. Clone & Set Up Virtual Environment
```powershell
git clone https://github.com/ChinchillaLanigera/fl-fab-priority-mapping.git
cd fl-fab-priority-mapping

python -m venv .venv
.venv\Scripts\activate   # On Linux/macOS: source .venv/bin/activate
pip install pandas numpy openpyxl plotly scikit-learn
```

### 2. Add Raw Data
Download raw datasets and place them in `data/raw/`:
* `data/raw/FoodAccessResearchAtlasData.xlsx` (USDA ERS)
* `data/raw/snap_retailers_fl.csv` (USDA FNS)

*(Note: Raw data files are excluded from git via `.gitignore` to prevent exceeding repository file-size limits).*

### 3. Run Pipeline
```powershell
python scripts/01_build_fab_index.py
python scripts/02_map_retail_gaps.py
python scripts/03_assign_food_banks.py
python scripts/04_build_interactive_map.py
```

### 4. View Interactive Map Locally
```powershell
Start-Process outputs/florida_fab_priority_map.html
```

---

## Live Interactive Map

The complete county priority index and territorial food bank map can be accessed directly in the browser via GitHub Pages:  
👉 **`https://ChinchillaLanigera.github.io/fl-fab-priority-mapping/`**