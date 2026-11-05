# Data Cleaning Agent prototype

Install `requirements.txt` and run `streamlit run app.py` from this directory.

## Spreadsheet-style review

1. Enter the study objectives and select a demo CSV or upload a CSV.
2. Click **Profile and propose plan**. The **Data issue summary** appears before the review table, with `column`, `affected_cells_estimate`, and `percentage of missing`. Affected cells are distinct source cells with detected issues; overlapping tool estimates are not added.
3. In **Review the proposed plan**, optionally mark critical and confirmed non-critical variables under Study importance. Other variables remain unconfirmed.
4. Click a **Selected action** cell to open its treatment dropdown. The table shows issue columns, observed reasons, applicable missingness rule, affected-cell estimates, missing percentage, and an exact suggested plan. Invalid column/method combinations block approval. All choices default to keeping data.
5. Download the Excel review form if useful. It includes Summary and Review sheets with per-row dropdowns. Confirm selections in the app: edited-workbook import is not implemented.
6. Click **Apply selected actions** to execute supported choices. Original records remain available; transformations and explicit deletions are audited. Results, CSV and the full audit bundle are downloadable after review.

## Treatment support

Executable after confirmation: existing contract-based normalization; column exclusion; complete-case deletion for selected variables (the UI previews combined row loss); numeric median/mean imputation; unique-mode imputation. Numeric methods require a configured numeric column with finite observed values and are excluded for identifiers. A tied mode cannot be applied. Missing markers follow the editable contract.

MICE, ML prediction, proxy construction, investigation of domain findings and detailed duplicate review are labeled assessment choices. They do not execute a model or silently alter values. Pending assessments are recorded and keep output in completed-with-findings status. The current interface retains duplicate candidates pending a detailed survivor decision; it does not silently use first-row deduplication. Root causes are not inferred from missingness percentages. M1 (<5% non-critical), M2 (<5% critical/unconfirmed), M3 (5–20% inclusive) and M4 (>20%) guide recommendations, not automatic destructive actions.

The OpenAI planner remains optional and uses the configured aggregate-only consent flow. Study-specific modeling, MICE pooling, proxy validity, structural missingness, subgroup sensitivity and clinical interpretation require further assessment. All project/checkpoint state is in memory; export before restart. CSV input is limited to 5 MB, 100 columns and 10,000 rows by the existing loader. This revision changes the main review screen; the alternative study-wizard prototype remains a separate draft PR.

Run `python -m unittest discover -v` for core, demo, review-table, workbook and interface checks.
