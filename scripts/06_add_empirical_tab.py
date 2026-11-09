import os
import re

html_path = "index.html"
if not os.path.exists(html_path):
    html_path = "outputs/florida_fab_priority_map.html"

with open(html_path, "r", encoding="utf-8") as f:
    html_doc = f.read()

# 1. Update the Tab Bar to include the 3rd Tab
old_tab_bar_pattern = r'<nav class="nav-tabs">.*?</nav>'
new_tab_bar = """<nav class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('map-tab', this)">🗺️ Priority Map</button>
      <button class="tab-btn" onclick="switchTab('methodology-tab', this)">📄 Pipeline &amp; Data Map</button>
      <button class="tab-btn" onclick="switchTab('empirical-tab', this)">📈 Empirical Weighting (FAB Telemetry)</button>
    </nav>"""

if '<nav class="nav-tabs">' in html_doc:
    html_doc = re.sub(
        old_tab_bar_pattern, new_tab_bar, html_doc, flags=re.DOTALL
    )
else:
    # If tabs aren't added yet, add them right under <main>
    html_doc = re.sub(
        r"(<main[^>]*>)",
        r'\1\n' + new_tab_bar + '\n<div id="map-tab" class="tab-pane active">',
        html_doc,
    )

# 2. Markup for the 3rd Panel
empirical_panel_html = r"""
    <!-- TAB 3: EMPIRICAL WEIGHTING & REGRESSION MODELING -->
    <div id="empirical-tab" class="tab-pane">
      <div class="doc-card" style="margin-bottom: 20px;">
        <span class="layer-tag">Econometric Modeling</span>
        <h2 style="color: #173c32; margin: 8px 0;">Empirical Feature Weighting via Program Telemetry</h2>
        <p class="lede" style="font-size: 13px;">
          Rather than relying on intuitive or heuristic weighting (e.g., arbitrarily assigning 45% to SNAP and 20% to poverty), this specification outlines how active FAB point-of-sale transaction data can be modeled with Elastic Net regularized regression to uncover the true data-driven drivers of redemption success.
        </p>
      </div>

      <div class="doc-grid">
        <!-- LEFT COLUMN: Formulation & Training Flow -->
        <div class="doc-card">
          <h3>1. Metric A: Dependent Variable (Redemption Velocity)</h3>
          <p style="font-size: 12px; color: #53746a;">
            Raw redemption dollars inherently favor 5-day-a-week metropolitan markets. Metric A isolates operational efficiency by measuring redemption dollars generated relative to the surrounding eligible population:
          </p>
          <div class="math-callout">
            <strong>Target Variable (Metric A):</strong>
            \[
            Y_i =
            \frac{\text{Annual FAB Incentive Dollars Redeemed}}
            {\text{Estimated Catchment SNAP Households}}
            \]
            <strong>Log-Normalized Target:</strong>
            \[
            y_i = \ln(Y_i + 1)
            \]
            <em>(controls for right-tail skew from flagship markets)</em>
          </div>

          <p style="font-size: 12px; color: #53746a;">
            <strong>Catchment Area:</strong> 10-minute (urban) or 20-minute (rural) road-network driving isochrone around active outlet <em>i</em>.
          </p>

          <h3>2. Elastic Net Regularization Objective</h3>
          <p style="font-size: 12px; color: #53746a;">
            Variables like SNAP participation and poverty rate exhibit heavy collinearity (r ≈ 0.64). Ordinary Least Squares yields unstable coefficients, while standard LASSO arbitrarily eliminates one. Elastic Net groups correlated features and balances L1 sparsity with L2 coefficient stability:
          </p>
          <div class="math-callout">
            \[
            \min_{\beta_0,\boldsymbol{\beta}}
            \frac{1}{2N}\sum_{i=1}^{N}
            (y_i-\beta_0-X_i\boldsymbol{\beta})^2
            + \lambda\left[
            \alpha\sum_j|\beta_j|
            + \frac{1-\alpha}{2}\sum_j\beta_j^2
            \right]
            \]
            <span style="font-size: 11px; color: #64748b;">• λ ≥ 0 governs overall shrinkage penalty<br>• α ∈ [0, 1] sets the balance between LASSO (α=1) and Ridge (α=0)</span>
          </div>

          <h3>3. K-Fold Cross-Validation Workflow</h3>
          <pre class="flowchart">
Active Outlet Telemetry (N Samples)
  ├── 5-Fold Stratified Split: Train on 4 folds, validate on 1
  ├── Hyperparameter Grid Search:
  │     • α ∈ [0.1, 0.5, 0.7, 0.9, 0.99]
  │     • λ path (automatically generated regularization decay)
  └── Minimized CV-MSE ──► Lock in Optimal (λ*, α*)
          </pre>
        </div>

        <!-- RIGHT COLUMN: Coefficient Derivation & Synthesis -->
        <div class="doc-card">
          <h3>4. Deriving Normalized Statewide Weights</h3>
          <p style="font-size: 12px; color: #53746a;">
            Refit the model on all active outlets using optimal (λ*, α*). Standardized coefficients (β) reflect relative feature importance. Features driven to zero by the L1 penalty are cleanly eliminated:
          </p>
          <div class="math-callout">
            <strong>Normalized Feature Weight Formula:</strong>
            \[
            w_j = \frac{|\beta_j|}{\sum_k |\beta_k|}\times 100\%
            \]
          </div>

          <table class="spec-table">
            <thead>
              <tr>
                <th>Feature (Standardized)</th>
                <th>Learned β</th>
                <th>Derived Weight</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>SNAP Household Participation %</td>
                <td>+0.42</td>
                <td><strong>36.8%</strong></td>
              </tr>
              <tr>
                <td>Vehicle Scarcity / Carless %</td>
                <td>+0.28</td>
                <td><strong>24.6%</strong></td>
              </tr>
              <tr>
                <td>Driving LILA Population Share</td>
                <td>+0.22</td>
                <td><strong>19.3%</strong></td>
              </tr>
              <tr>
                <td>County Specialty Crop Acreage</td>
                <td>+0.14</td>
                <td><strong>12.3%</strong></td>
              </tr>
              <tr>
                <td>Nearby Direct Retail Density</td>
                <td>+0.08</td>
                <td><strong>7.0%</strong></td>
              </tr>
              <tr>
                <td>Fringe Convenience Count</td>
                <td>0.00</td>
                <td><em>Dropped (0%)</em></td>
              </tr>
            </tbody>
          </table>

          <h3>5. Application to Statewide Expansion</h3>
          <p style="font-size: 12px; color: #53746a;">
            Apply the empirical weights back to all 67 counties and 4,000+ census tracts:
          </p>
          <div class="math-callout">
            \[
            \text{Statewide Tract Priority}
            = \sum_j w_j \times \operatorname{Percentile}(X_j)
            \]
          </div>
          <p style="font-size: 11px; color: #53746a;">
            Alternatively, predict expected redemption velocity directly on unserved tracts using
            \(\hat{y} = X_{\text{new}}\boldsymbol{\beta}\) to estimate annual GusNIP match uptake before deploying point-of-sale terminals.
          </p>
        </div>
      </div>
    </div>
"""

# Check if tab 3 is already injected
if '<div id="empirical-tab"' not in html_doc:
    # Inject right before the closing </main>
    html_doc = html_doc.replace("</main>", empirical_panel_html + "\n  </main>")

# 3. Ensure CSS includes tab-pane and nav styles
css_patch = """
    .nav-tabs {
      display: flex;
      gap: 10px;
      margin-bottom: 24px;
      border-bottom: 2px solid #dce8e1;
      padding-bottom: 2px;
      flex-wrap: wrap;
    }
    .tab-btn {
      background: none;
      border: none;
      padding: 10px 18px;
      font-size: 13px;
      font-weight: 700;
      color: #53746a;
      cursor: pointer;
      border-radius: 8px 8px 0 0;
      transition: all 0.2s ease;
    }
    .tab-btn:hover { background: #eaf1ed; color: #173c32; }
    .tab-btn.active { color: #123b32; border-bottom: 4px solid #123b32; background: #ffffff; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    .doc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 900px) { .doc-grid { grid-template-columns: 1fr; } }
    .doc-card { background: #fff; border: 1px solid #dce8e1; border-radius: 12px; padding: 22px; }
    .flowchart { background: #172a26; color: #d1fae5; padding: 14px; border-radius: 8px; font-family: monospace; font-size: 11px; overflow-x: auto; }
    .spec-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }
    .spec-table th, .spec-table td { padding: 8px 10px; border-bottom: 1px solid #edf1ee; text-align: left; }
    .spec-table th { background: #f3f7f4; color: #173c32; }
    .math-callout { background: #f8fafc; border-left: 4px solid #175541; padding: 10px 14px; margin: 10px 0; font-size: 12px; color: #334155; }
    .math-callout mjx-container[display="true"] { margin: 0.6em 0; overflow-x: auto; overflow-y: hidden; }
"""

if "/* --- Empirical Tab CSS --- */" not in html_doc:
    html_doc = html_doc.replace(
        "</style>", f"/* --- Empirical Tab CSS --- */\n{css_patch}\n  </style>"
    )

# 4. Ensure MathJax is available for formulas in hidden tabs
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
if "mathjax@3/es5/tex-chtml.js" not in html_doc:
    html_doc = html_doc.replace("</head>", f"{mathjax_markup}\n</head>")

# 5. Write back to disk
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_doc)

os.makedirs("outputs", exist_ok=True)
with open("outputs/florida_fab_priority_map.html", "w", encoding="utf-8") as f:
    f.write(html_doc)

print("[✓] Successfully added Tab 3: Empirical Weighting to index.html!")