import os
import re

html_path = "index.html"
if not os.path.exists(html_path):
    html_path = "outputs/florida_fab_priority_map.html"

with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# --- 1. CSS for Navigation Tabs and Panel Layout ---
panel_css = """
    /* --- Tab Navigation Styling --- */
    .nav-tabs {
      display: flex;
      gap: 10px;
      margin-bottom: 24px;
      border-bottom: 2px solid #dce8e1;
      padding-bottom: 2px;
    }
    .tab-btn {
      background: none;
      border: none;
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 700;
      color: #53746a;
      cursor: pointer;
      border-radius: 8px 8px 0 0;
      transition: all 0.2s ease;
    }
    .tab-btn:hover {
      background: #eaf1ed;
      color: #173c32;
    }
    .tab-btn.active {
      color: #123b32;
      border-bottom: 4px solid #123b32;
      background: #ffffff;
    }
    .tab-pane {
      display: none;
    }
    .tab-pane.active {
      display: block;
    }

    /* --- One-Pager Panel Cards & Flowchart --- */
    .doc-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 900px) {
      .doc-grid { grid-template-columns: 1fr; }
    }
    .doc-card {
      background: #ffffff;
      border: 1px solid #dce8e1;
      border-radius: 14px;
      padding: 24px;
      box-shadow: 0 4px 18px rgba(27, 58, 46, 0.04);
    }
    .doc-card h3 {
      margin-top: 0;
      color: #173c32;
      font-size: 18px;
      border-bottom: 2px solid #f0f4f2;
      padding-bottom: 8px;
    }
    .flowchart {
      background: #172a26;
      color: #d1fae5;
      padding: 18px;
      border-radius: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      line-height: 1.45;
      overflow-x: auto;
      margin: 16px 0;
    }
    .spec-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      margin-top: 12px;
    }
    .spec-table th, .spec-table td {
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid #edf1ee;
    }
    .spec-table th {
      background: #f3f7f4;
      color: #173c32;
      font-weight: 700;
    }
    .badge-src {
      display: inline-block;
      padding: 3px 7px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      background: #e8f1e8;
      color: #175541;
    }
    .math-callout {
      background: #f8fafc;
      border-left: 4px solid #175541;
      padding: 12px 16px;
      margin: 12px 0;
      font-size: 12px;
      color: #334155;
    }
        .math-callout mjx-container[display="true"] {
          margin: 0.6em 0;
          overflow-x: auto;
          overflow-y: hidden;
        }
    """

# --- 2. HTML Markup for the One-Pager Panel ---
methodology_html = """
    <!-- TAB BUTTONS -->
    <nav class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('map-tab', this)">🗺️ Priority Map</button>
      <button class="tab-btn" onclick="switchTab('methodology-tab', this)">📄 Data Architecture & Methodology</button>
    </nav>

    <!-- WRAP EXISTING MAP AND CARDS INSIDE TAB-PANE -->
    <div id="map-tab" class="tab-pane active">
"""

panel_content = r"""
    </div><!-- END MAP TAB -->

    <!-- METHODOLOGY ONE-PAGER PANEL -->
    <div id="methodology-tab" class="tab-pane">
      <div class="doc-card" style="margin-bottom: 20px;">
        <span class="layer-tag">Technical Architecture</span>
        <h2 style="color: #173c32; margin: 8px 0;">FAB: Data Pipeline & Empirical Integration</h2>
        <p class="lede" style="font-size: 13px;">
          This pipeline replaces subjective heuristic weighting with an empirical, multi-tier data pipeline that matches community need, driving-distance retail friction, local grower capacity, and point-of-sale operational readiness across all 67 Florida counties.
        </p>
      </div>

      <div class="doc-grid">
        <!-- LEFT: Pipeline Flow & Data Map -->
        <div class="doc-card">
          <h3>1. End-to-End Integration Flow</h3>
          <p style="font-size: 12px; color: #53746a;">
            Data flows from four authoritative public data sources through normalization, spatial catchment aggregation, and regularization:
          </p>
          <pre class="flowchart">
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│   USDA ERS (FARA)    │    │    USDA NASS (Ag)    │    │    USDA AMS (Dir)    │    │    USDA FNS (SNAP)   │
│ Tract Demographics & │    │ Specialty Crop Acres │    │ Total Physical Farm  │    │ Audited EBT Retailer │
│ Driving LILA Access  │    │ & Direct Farm Sales  │    │ Markets & Farm Stands│    │ Types & Coordinates  │
└──────────┬───────────┘    └──────────┬───────────┘    └──────────┬───────────┘    └──────────┬───────────┘
           │                           │                           │                           │
           ▼                           ▼                           ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       PIPELINE PROCESSING STEPS                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 1: DEMAND & TRANSIT BARRIERS (scripts/01_build_fab_index.py)                                       │
│ • Standardize 11-digit GEOID; calculate SNAP household proportion: TractSNAP / (POP2020 / 2.5)          │
│ • Map driving-distance barriers (DD_SRAM_LILATracts_1And10: 10 mi rural / 1 mi urban)                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 2: SUPPLY, INFRASTRUCTURE & GAP SYNTHESIS (scripts/02_map_retail_gaps.py)                          │
│ • Standardize county names (ST. LUCIE, MIAMI-DADE, DESOTO)                                               │
│ • Reconcile USDA AMS physical farm markets against USDA FNS EBT-authorized outlets                       │
│ • Compute normalized density: Direct Markets per 10k SNAP Households                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 3: EMPIRICAL SCORING & ACTION MATRIX                                                                │
│ • Elastic Net / LASSO regularized regression weights on active redemption velocity                       │
│ • Quadrant Classification: High Need Turn-Key vs. High Need Retail Desert vs. Baseline Coverage          │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 4: GOVERNANCE & TERRITORIAL DEPLOYMENT (scripts/03_assign_food_banks.py)                           │
│ • Map all 67 counties to the 9 Feeding Florida regional food bank networks                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
          </pre>

          <h3>2. Master Data Sources</h3>
          <table class="spec-table">
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Resolution</th>
                <th>Key Features</th>
                <th>Operational Role</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><span class="badge-src">USDA ERS FARA</span></td>
                <td>Census Tract</td>
                <td><code>POP2020</code>, <code>TractSNAP</code>, <code>PovertyRate</code>, <code>DD_SRAM</code></td>
                <td>Identifies SNAP concentration and physical road transit friction to supermarkets.</td>
              </tr>
              <tr>
                <td><span class="badge-src">USDA NASS</span></td>
                <td>County FIPS</td>
                <td><code>specialty_crop_acres</code>, <code>direct_farm_sales_usd</code></td>
                <td>Ensures local Florida produce supply capacity is available for incentive matching.</td>
              </tr>
              <tr>
                <td><span class="badge-src">USDA AMS</span></td>
                <td>Point (Lat/Lon)</td>
                <td><code>listing_type</code>, <code>market_name</code>, operating schedules</td>
                <td>Measures total physical direct-market infrastructure regardless of payment types.</td>
              </tr>
              <tr>
                <td><span class="badge-src">USDA FNS</span></td>
                <td>Point (Lat/Lon)</td>
                <td><code>Store_Type</code> (Farmers' Market, Direct Farmer, Grocer)</td>
                <td>Flags audited POS EBT card acceptance and highlights immediate onboarding targets.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- RIGHT: Mathematical & Methodological Specifications -->
        <div class="doc-card">
          <h3>3. Mathematical Scoring Formulation</h3>
          <p style="font-size: 12px; color: #53746a;">
            The model normalizes raw counts into population-adjusted percentiles (\(P \in [0, 100]\)):
          </p>

          <div class="math-callout">
            <strong>Target Demand Score (Tract Level):</strong>
            \[
            \text{FAB Need} =
            0.50\,P_{\text{SNAP}} +
            0.25\,P_{\text{Poverty}} +
            0.25\,(\text{LILA}_{\text{Driving}} \times 100)
            \]
          </div>

          <div class="math-callout">
            <strong>Normalized Market Density:</strong>
            \[
            \text{Markets per 10{,}000 SNAP HH} =
            \frac{\text{Direct Markets}}{\text{Estimated SNAP Households}}
            \times 10{,}000
            \]
          </div>

          <div class="math-callout">
            <strong>Empirical Elastic Net Loss Objective:</strong>
            \[
            \min_{\beta_0,\boldsymbol{\beta}}
            \frac{1}{2N}\sum_{i=1}^{N}
            (y_i-\beta_0-X_i\boldsymbol{\beta})^2
            + \lambda\left[
            \alpha\sum_j|\beta_j|
            + \frac{1-\alpha}{2}\sum_j\beta_j^2
            \right]
            \]
            <span style="font-size: 10px; color: #64748b;">Tuned via 5-Fold Cross-Validation on active outlet redemption velocity.</span>
          </div>

          <h3>4. Feeding Florida Regional Territories</h3>
          <p style="font-size: 12px; color: #53746a;">
            Every priority tier connects to the designated regional food bank partner to direct operational actions (mobile routes, technical onboarding, EBT terminal deployment):
          </p>
          <ul style="font-size: 11px; color: #1e293b; padding-left: 18px; line-height: 1.6;">
            <li><strong>Second Harvest of the Big Bend:</strong> 11 High-Need rural panhandle counties.</li>
            <li><strong>Feeding Tampa Bay:</strong> Agricultural heartland (Hardee, Highlands, Citrus).</li>
            <li><strong>All Faiths Food Bank:</strong> DeSoto County (Acute Rural Retail Void).</li>
            <li><strong>Treasure Coast Food Bank:</strong> Okeechobee County (Transit & Retail Desert).</li>
            <li><strong>Feeding South Florida:</strong> Metro transit-dense corridors.</li>
          </ul>
        </div>
      </div>
    </div><!-- END METHODOLOGY TAB -->
"""

# --- 3. JavaScript Tab Switcher ---
tab_js = """
  <script>
    function switchTab(tabId, btn) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      btn.classList.add('active');
      // Trigger a resize event so Plotly adjusts map sizing when returning to the map tab
      if (tabId === 'map-tab') {
        window.dispatchEvent(new Event('resize'));
      }
    }
  </script>
"""

# --- 4. Apply Injections to index.html ---
# Load MathJax when the base map has not already included it.
mathjax_markup = """
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [['\\\\(', '\\\\)']],
        displayMath: [['\\\\[', '\\\\]']]
      },
      chtml: { scale: 1.05 }
    };
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
"""
if "mathjax@3/es5/tex-chtml.js" not in content:
    content = content.replace("</head>", f"{mathjax_markup}\n</head>")

# Add CSS before </head>
if "/* --- Tab Navigation Styling --- */" not in content:
    content = content.replace("</style>", f"{panel_css}\n  </style>")

# Add nav tabs and opening tag right after <main>
if '<nav class="nav-tabs">' not in content:
    content = re.sub(r"(<main[^>]*>)", r"\1\n" + methodology_html, content)

    # Insert closing tag and methodology panel right before </main>
    content = content.replace("</main>", f"{panel_content}\n  </main>")

# Add JS before </body>
if "function switchTab" not in content:
    content = content.replace("</body>", f"{tab_js}\n</body>")

# Write out the updated file
with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

os.makedirs("outputs", exist_ok=True)
with open("outputs/florida_fab_priority_map.html", "w", encoding="utf-8") as f:
    f.write(content)

print("[✓] Successfully injected Methodology & Architecture tab into index.html!")