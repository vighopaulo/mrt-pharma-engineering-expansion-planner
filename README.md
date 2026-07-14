# MRT Pharma Digital Twin V2

Supports Expansion and Greenfield planning, independent Conventional/MRT optimization, weighted decision scoring, diagnostics, charts, and exports.

Run: `streamlit run app.py`

Tests: `pytest -q`


## Hospital-selected decision priorities

Before the financial inputs, the hospital ranks its three most important outcomes. The application assigns 30% to Priority 1, 20% to Priority 2, and 15% to Priority 3. The remaining 35% is distributed across all other metrics according to a fixed balanced baseline. The selected priorities and generated weights are shown in the results and exported workbook.
