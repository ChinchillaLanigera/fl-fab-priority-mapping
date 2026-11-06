# Florida Fresh Access Bucks (FAB) Expansion Priority Index

An open-source geospatial analytics and prioritization pipeline designed to guide the geographic expansion of the **Fresh Access Bucks (FAB)** nutrition incentive program across Florida. Administered statewide by **Feeding Florida** (Florida's network of 9 Feeding America member food banks) and supported by USDA GusNIP funding, FAB provides a dollar-for-dollar match for SNAP participants purchasing Florida-grown fruits and vegetables at direct-to-consumer outlets (farmers markets, farm stands, mobile markets, and CSAs).

This repository models community need, transit friction, and retail infrastructure across all 67 Florida counties and census tracts to identify high-priority zones for market onboarding and mobile produce interventions.

---

## Analytical Methodology & Principles

Traditional food access analyses often rely on raw population counts, which disproportionately flag dense metropolitan centers (e.g., Miami-Dade, Broward, Orange) while obscuring severe food insecurity in rural agricultural corridors. This model addresses those limitations through three core methodological design choices:

1. **Rate-Based Intensity Over Raw Counts:** Need metrics are normalized by population denominators (e.g., household SNAP participation rates rather than raw counts of SNAP recipients). This establishes geographic equity, allowing high-intensity rural communities (where 15–25% of households rely on SNAP) to compete fairly against large metro areas.
2. **Driving-Distance Friction (SRAM/LRAM):** Access barriers are evaluated through the USDA Economic Research Service (ERS) Food Access Research Atlas driving-distance metrics (`DD_SRAM_LILATracts_1And10`) rather than walking-distance measures alone. In rural and peri-urban Florida, physical road-transit distance to full-service supermarkets is the defining barrier to fresh produce.
3. **Official Administrative Store Classifications:** Rather than relying on fragile name-based keyword matching (which misclassifies commercial supermarket chains like *Publix Super Market* or *Walmart Neighborhood Market* as direct farm markets), the pipeline filters the USDA FNS SNAP Retailer Database strictly by official, audited store types:
   * `Farmers' Market`
   * `Direct Marketing Farmer` (farm stands, CSAs, mobile farm trucks, on-farm markets)

---

### Scoring Formula

Each Florida census tract is evaluated using a composite **FAB Need Score** ($0\text{–}100$) based on percentile-ranked socioeconomic indicators and transit barriers:

$$\text{FAB Need Score} = 0.50 \cdot P_{\text{SNAP}} + 0.30 \cdot P_{\text{Poverty}} + 0.20 \cdot (\text{LILA}_{\text{Driving}} \times 100)$$

* $P_{\text{SNAP}}$: Percentile rank of tract household SNAP participation rate ($0\text{–}100$).
* $P_{\text{Poverty}}$: Percentile rank of tract poverty rate ($0\text{–}100$).
* $\text{LILA}_{\text{Driving}}$: Binary indicator ($1$ or $0$) from the USDA Food Access Research Atlas denoting Low Income and Low Access based on driving distances (10-mile threshold in rural areas, 1-mile in urban areas).

County-level scores aggregate tract scores weighted by need and transit friction, integrated with direct-market capacity to classify counties into actionable programmatic typologies.

---

## Strategic Action Typologies

Counties in the upper 40th percentile of priority scores are categorized into two primary intervention tiers:

* **Tier 1: Mobile Produce Route Needed (High Need, Zero Direct Retail):** High SNAP intensity combined with zero USDA-authorized direct-market produce outlets. In these areas, conventional farmers market matches are impossible without external supply interventions; they require mobile produce trucks, pop-up markets, or community grocery pilots (e.g., the *Florida Fresh Dollars* model). Top examples include **DeSoto, Putnam, Hardee, Okeechobee, Liberty, and Gadsden counties**.
* **Tier 1: Onboard / Expand Existing SNAP Outlets:** High SNAP intensity with at least one active SNAP-authorized direct agricultural market. These locations offer immediate turn-key opportunities to activate FAB's dollar-for-dollar produce match. Examples include **Highlands, Citrus, and Jefferson counties**.
* **Tier 2: Baseline Coverage / Monitor:** Moderate relative need or existing baseline coverage.

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
   * Applies administrative filtering on `Store_Type` (`Farmers' Market`, `Direct Marketing Farmer`) while excluding commercial chain grocers.
   * Assigns strategic action typologies and exports `fl_county_fab_strategy.csv`.

3. **`scripts/03_assign_food_banks.py`**:
   * Maps all 67 Florida counties to their official Feeding Florida regional food bank territory crosswalk.
   * Aggregates regional performance benchmarks and appends partner assignments to `fl_county_fab_strategy.csv`.

4. **`scripts/04_build_interactive_map.py`**:
   * Fetches county boundary GeoJSON geometries and pairs them with priority metrics.
   * Renders a standalone, interactive Plotly choropleth map with customized hovertool diagnostics.
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