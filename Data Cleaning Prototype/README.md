# Study-led Data Cleaning Agent prototype

Run `pip install -r requirements.txt`, then `streamlit run app.py` from this directory.

The main interface follows SKILL.md: each new project requires study objectives; read the three existing synthetic 500-row patient, medication and procedure CSVs together or upload multiple CSVs; review missingness by variable importance and M1–M4 thresholds; select duplicate survivors/deletions with all candidate columns visible; review IQR outlier candidates and choose retention, explicit deletion, missing assignment or P95 / P5–P95 capping; validate and download CSVs, JSON reports and candidate details. Files remain separate. No source file is overwritten.

Only empty fields count as missing by default. Users explicitly configure other markers. All editing decisions require confirmation; keeping candidates is the default. Row provenance and before/after edits are exported. Numeric capping uses Decimal linear quantiles fixed at the review stage. The lower tail is never moved to P95.

## Limits

This revision uses an explicit local workflow; the prior optional LangGraph/OpenAI planner in agent.py remains available for existing integrations but is not used by the main interface. No dataset is sent to an external model by the new interface.

MICE, machine-learning imputation and proxy construction are assessment recommendations, not implemented transformations. Selecting further assessment retains data and marks output provisional. Simple median/mode filling is available only by explicit user choice and requires a documented rationale; it does not preserve inferential uncertainty. Missingness mechanisms, subgroup diagnostics, structural missingness and clinical causes need study-specific assessment. The built-in outlier detector uses full-file IQR, not subgroup models. CSV-only input is supported; no automatic joining or cross-table validation is performed. Project state is in memory and is cleared by New project or server restart.

PASS means configured technical and contract checks passed; it is not proof of study validity. Retained candidates and limitations are included in the report. Contract findings or deferred methods make output provisional. CSV nulls become empty fields; the audit report preserves the source values involved in changes.

Run `python -m unittest discover -v` for workflow, interface, legacy core and demo fixture checks.
