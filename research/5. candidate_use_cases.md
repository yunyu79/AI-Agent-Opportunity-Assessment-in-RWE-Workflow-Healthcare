# Candidate AI Agent Use Cases

**Status:** Six hypotheses derived from the 12-task workflow map. **Not ranked** for PMF, feasibility or ROI. Sources refer to workflow and quality requirements; they are not direct evidence of commercial demand.

| ID | Use case | Mapped tasks | Target user | Proposed task boundary | Output | Success metrics | Unvalidated risk |
|---|---|---|---|---|---|---|---|
| UC01 | RWD Data QC Investigation Agent | W04; W05 | RWE data analyst; data engineer | Run existing QC checks; interpret failed rules; propose root-cause investigations; assemble review-ready issue reports | Traceable exception report with severity, suspected causes, and reviewer disposition | Triage precision; root-cause suggestion acceptance; net review hours; missed critical exceptions | QC tools already exist; Agent must add value beyond automated rule execution |
| UC02 | Data Dictionary and Mapping Assistant | W02; W03; W04 | Data engineer; RWE analyst | Propose source-to-target field mappings and highlight semantic or datatype conflicts for human review | Mapping specification; conflicts; pending approvals | Top-1 mapping accuracy; acceptance rate; mapping time; critical mapping error rate | Semantic suggestions require domain validation and governance |
| UC03 | Cohort Definition and Code Validation Agent | W06; W07 | Epidemiologist; RWE programmer | Translate protocol conditions into structured cohort logic; draft SQL; run rule-based and attrition checks | Auditable cohort specification; code draft; test and attrition reports | Criteria coverage; SQL test pass rate; cohort count agreement; review time | Clinical definitions and temporal logic demand expert signoff |
| UC04 | Statistical Results QA Agent | W08; W09 | Biostatistician; statistical programmer | Reconcile SAP requirements with code, logs, numerical outputs and tables; flag missing or inconsistent analyses | Issue register; coverage matrix; discrepancy report | Known-error recall; false-positive rate; manual QA time; output consistency | Computations remain deterministic; Agent assists reconciliation |
| UC05 | HEOR Literature Evidence Extraction Agent | W10 | HEOR researcher; evidence synthesis analyst | Extract study/population/exposure/outcome/HRU/cost fields from eligible papers with traceable provenance | Structured evidence table; quotations/locations; unresolved discrepancies | Field accuracy; critical-field recall; citation accuracy; net minutes per article | Manual adjudication may erode theoretical time savings |
| UC06 | HEOR Model and Report Consistency Agent | W11; W12 | Health economist; HEOR scientist | Cross-check model inputs, assumptions, cited sources, output tables and report statements | Parameter lineage table; inconsistency register; review checklist | Issue recall; citation traceability; review time; false positives | Does not replace scientific or economic model validation |

## Validation approach

1. Collect task-level baseline time, frequency and actual error/rework evidence.
2. Benchmark comparable existing tools and quantify incremental value beyond deterministic software.
3. Design a small, auditable test set per use case and record human review effort.
4. Identify economic buyers and validate willingness to pay in interviews before claiming PMF.

Machine-readable version: [candidate_use_cases.csv](candidate_use_cases.csv). Workflow details and foundational sources: [workflow.md](workflow.md).
