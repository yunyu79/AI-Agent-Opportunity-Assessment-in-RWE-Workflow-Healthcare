# Data Cleaning Agent prototype

Install `requirements.txt` and run `streamlit run app.py` from this directory.

## Spreadsheet-style review

1. Enter the study objectives and select a demo CSV or upload a CSV.
2. Click **Profile and propose plan**. The **Data issue summary** appears before the review table, with `column`, `affected_cells_estimate`, and `percentage of missing`. Affected cells are distinct source cells with detected issues; overlapping tool estimates are not added.
3. In **Review the proposed plan**, optionally mark critical and confirmed non-critical variables under Study importance. Other variables remain unconfirmed.
4. Click a **Selected action** cell to open its treatment dropdown. The table shows issue columns, observed reasons, applicable missingness rule, affected-cell estimates, missing percentage, and an exact suggested plan. Invalid column/method combinations block approval. Each Action defaults to its mapped suggested plan; explicit user edits take precedence. Preselection does not execute changes.
5. Download the Excel review form if useful. It includes Summary and Review sheets with per-row dropdowns. Confirm selections in the app: edited-workbook import is not implemented.
6. Click **Approve and apply selected actions** to execute supported choices. Original records remain available; transformations and explicit deletions are audited. Results, CSV and the full audit bundle are downloadable after review.

## Treatment support

Executable after confirmation: existing contract-based normalization; column exclusion; complete-case deletion for selected variables (the UI previews combined row loss); numeric median/mean imputation; unique-mode imputation. Numeric methods require a configured numeric column with finite observed values and are excluded for identifiers. Tied modes use a balanced, reproducible assignment after approval. Missing markers follow the editable contract.

MICE, ML prediction, proxy construction, investigation of domain findings and detailed duplicate review are labeled assessment choices. They do not execute a model or silently alter values. Pending assessments are recorded and keep output in completed-with-findings status. The current interface retains duplicate candidates pending a detailed survivor decision; it does not silently use first-row deduplication. Root causes are not inferred from missingness percentages. M1 (<5% non-critical), M2 (<5% critical/unconfirmed), M3 (5–20% inclusive) and M4 (>20%) guide recommendations, not automatic destructive actions.

The OpenAI planner remains optional and uses the configured aggregate-only consent flow. Study-specific modeling, MICE pooling, proxy validity, structural missingness, subgroup sensitivity and clinical interpretation require further assessment. Projects are saved locally in `.local_projects/` (override with `CLEANING_PROJECT_DIR`). Bookmark the project URL to reopen the same settings, uploaded data, pending choices and graph progress after refresh/reconnect/server restart. No approved tools or API calls are replayed on restore. **Close project** removes its saved snapshot and clears the UI; source files and exported downloads are preserved. This is a local single-user prototype; the project URL is an identifier, not an authentication system. The storage directory must be persistent on hosted deployments. CSV input is limited to 5 MB, 100 columns and 10,000 rows by the existing loader. This revision changes the main review screen; the alternative study-wizard prototype remains a separate draft PR.

Run `python -m unittest discover -v` for core, demo, review-table, workbook and interface checks.

Missing-value guidance now requires examining causes and documenting MCAR, MAR or MNAR as a hypothesis or uncertain, then presenting a reasoned plan and reasonable alternatives before user approval. No row changes precede that approval.

## Sol spreadsheet review
The default is `gpt-6.1-sol`; saved Sol/4.1-mini defaults are upgraded. The main review is one editable spreadsheet grid with Column name, Data issue, Reasons, Suggested plan and Action. It stays tabular on narrow screens and supports horizontal scrolling. Click Action cells for dropdowns; inapplicable choices block approval.

After the review-context consent checkbox is enabled, the LLM assessment runs automatically once per changed review context. Successful explanations are saved. Failed requests show the missing-key, API status or connection error; Retry LLM assessment explicitly retries without automatic repeated charges. An OPENAI_API_KEY and Sol model access are required. Tests mock API responses; live account access must be verified on the deployment. Generating explanations and editing dropdowns never alter data; Approve and apply selected actions remains required. Excel download contains the same explanations and recommendations.

## Separate diagnostic findings
Review now shows one row per variable/issue type: missingness, formatting, finite-number parsing, date parsing, allowed ranges, dictionary categories, required columns, 1.5×IQR statistical outliers, repeated identifier candidates, exact duplicate groups, and configured date order. `end_date > start_date` is strict; existing configured event pairs allow equality. Missing markers are excluded from parse failures; IDs are excluded from statistical outliers. IQR requires at least four finite observations and nonzero IQR. Checks use the configured contract and do not claim all possible domain rules. Expand Issue details to view affected source records. New non-missing findings currently support retain or investigate-source assessment; automatic corrective edits require dedicated approved tools. Sol receives aggregate descriptions, not record values.

## Imputation recommendations and duplicate policy
The recommendation call reads SKILL.md directly. M2 uses ≤5% for critical/unconfirmed variables and prefers suitable ordinary imputation; at exactly 5% it takes precedence over M3. M3 considers ordinary imputation, MICE, ML and proxy. Aggregate numeric summaries support mean versus median selection. Structurally missing fields, identifiers and all-missing columns need explicit exceptions. Suggested treatment is independent of the unapproved Action default. Skill changes invalidate cached recommendations.

ZIP/postal codes may repeat by default. In Contract JSON, optionally add `allowed_duplicate_columns: ["zip_code"]` and `duplicate_unique_columns: ["record_id"]` (using valid JSON syntax and actual column names). An explicit unique-column list replaces identifier-based duplicate candidates; an empty list disables those candidates. Columns cannot occur in both lists. An explicit uniqueness rule can override the postal-code default. Exact full-row duplicate checks remain separate.

Action dropdown defaults mirror the Suggested plan. Ambiguous removal defaults to an assessment: select row deletion or column exclusion explicitly before applying. Inapplicable or unavailable model recommendations also remain clearly labeled assessments. Existing explicit selections made with this version survive reruns and project restoration.

## Refresh and submit
Use **↻ Rerun** at the top to refresh the running application without clearing the project or reapplying transformations. The visible interface marker is “Review interface v2”. A full-width **Approve and apply selected actions** button appears directly below the review table, with an explanation if it is disabled. The redundant available-options section and reviewer-note input were removed. Completed reviews show their submitted state. Rerun requires the Streamlit server to remain running; it cannot launch a stopped server or download GitHub updates.

## Approved results and management report
The original/cleaned comparison keeps the cleaned side empty until an approved apply step succeeds. Selection alone does not produce cleaned output. A tied mode means multiple categories share the largest count; approved mode imputation balances assignments across them using seed 42. After submission, Download management report provides a printable HTML document with objectives, issue columns, executed methods, before/after counts, reconciliation and unresolved findings. Open the HTML in a browser to print or save as PDF. Proposed or assessment-only methods are never described as executed.

Balanced tied-mode imputation gives each tied category an equal share, with remainders differing by at most one. Seed 42 randomizes which category receives the remainder and assignment to missing source rows. Existing observations remain intact; audit and management report record allocations. This simple imputation does not model individual attributes or preserve inferential uncertainty. MICE remains an assessment-only alternative.

## Quality summary and cleaned downloads
The review includes full-file per-column missingness, IQR outliers, range violations, distinct/repeated values, finite numeric counts and min/median/max. Overall metrics distinguish exact duplicate groups, all member rows and excess rows; repeated ZIP/category values are descriptive, not automatically invalid. Download quality statistics CSV for the table. Download cleaned dataset (CSV) is directly beneath the approved cleaned-data panel and contains only successfully approved changes; a pending further review is labeled. Management reports include before/after duplicate and outlier counts.
