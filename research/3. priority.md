# Pain Point Definitions

Hypothesis 1. Manual processing burden: Completing a task requires extensive manual operations, reading, or expert judgment, resulting in substantial human time investment.        

Hypothesis 2. Repetitive work: The same or similar information processing and operations are performed repeatedly.

Hypothesis 3. Coordination and waiting: Tasks depend on clarification, handoffs, confirmation, or approval across individuals or teams, creating additional communication effort and waiting time that extend delivery timelines.

Hypothesis 4. Errors and rework: Errors, omissions, or inconsistencies in data, logic, code, or outputs require additional checks, potentially including tracing back through the processes and results of multiple upstream steps.

Hypothesis 5. Difficulty adapting and reusing existing work: In new projects, existing logic, code, or deliverables cannot be readily adapted or reused, requiring substantial modification, adaptation, and revalidation.

## Current Workflow — Planning Estimates

Every value marked **E** is a planning assumption requiring validation, not an industry benchmark. **R** denotes a published reference value whose applicability still needs validation.

| Scenario | Human effort (person-hours/task) | Role types | Unit processing time (minutes/unit) | Error rate (%) | Task frequency (1–5) | Repetitive labor share (1–5) |
|---|---|---|---|---|---|---|
| W01: Research question and protocol design | 80–160 (E) | 3 (E) | 4,800–9,600/protocol (E) | 5 (E) | 2 (E) | 3 (E) |
| W09: Literature screening and evidence extraction | 50–80 (E) | 2 (E) | 16.4/article; extraction only, median (R, S1) | 3 (E) | 2 (E) | 5 (E) |
| W04: Data cleaning and standardization | 80–120 (E) | 3 (E) | 48–72/source field (E) | 5 (E) | 3 (E) | 4 (E) |
| W05: Data quality control | 8–16 (E) | 2 (E) | 24–48/exception (E) | 5 (E) | 4 (E) | 4 (E) |
| W07: Endpoint derivation | 20–40 (E) | 3 (E) | 12–24/patient (E) | 8 (E) | 3 (E) | 4 (E) |

## With AI, the Time Spent — Planning Estimates

| Scenario | Human effort (person-hours/task) | Role types | Unit processing time (minutes/unit) | Error rate (%) | Task frequency (1–5) | Repetitive labor share (1–5) |
|---|---|---|---|---|---|---|
| W01: Research question and protocol design | 50–100 (E) | 3 (E) | 3,000–6,000/protocol (E) | 4 (E) | 2 (E) | 2 (E) |
| W09: Literature screening and evidence extraction | 35–60 (E) | 2 (E) | 13.8/article; review and correction of AI extraction only, median (R, S1) | 3 (E) | 2 (E) | 3 (E) |
| W04: Data cleaning and standardization | 45–80 (E) | 3 (E) | 27–48/source field (E) | 4 (E) | 3 (E) | 3 (E) |
| W05: Data quality control | 5–10 (E) | 2 (E) | 15–30/exception (E) | 5 (E) | 4 (E) | 3 (E) |
| W07: Endpoint derivation | 12–25 (E) | 3 (E) | 7.2–15/patient (E) | 6 (E) | 3 (E) | 3 (E) |

## Task Scope and Measurement Assumptions

- **W01:** One moderately complex retrospective study protocol.
- **W09:** Screen 1,000 titles/abstracts and extract approximately 21 fields from 75 articles. The batch effort estimates cover screening, extraction and review; the published per-article times cover only the first reviewer's extraction work.
- **W04:** Clean and standardize one batch containing approximately 100 source fields.
- **W05:** Investigate, resolve and review 20 data quality exceptions.
- **W07:** Derive one prespecified endpoint for 100 patients.
- Human effort means the sum of all participants' active labor. AI-assisted estimates include input preparation, operation, correction and human review; they exclude one-time development and deployment.
- Role counts describe distinct role types, not headcount. Counts are provisional: W01 scientist, epidemiologist and programmer; W09 evidence reviewer and adjudicator; W04 data engineer, analyst and clinical terminology expert; W05 analyst and QA reviewer; W07 epidemiologist, programmer and clinical reviewer.
- Unit times for W01, W04, W05 and W07 are arithmetic conversions of the batch effort estimates, not independent measurements. Equal allocation per field, exception or patient is a simplifying assumption.
- Error rate is provisionally the proportion of checked items with a confirmed defect. The AI column represents residual errors after human review, including human- and AI-originated errors. Define and hold the inspected item and review standard constant before comparison.
- Previously entered calendar durations (W01: 2–3 months; W09: 8.3 days versus 3 days; W04: 2–4 weeks versus 1–2 weeks) are retained here for reference only. Their sources and labor/calendar-time interpretation remain unverified; they were not directly converted into person-hours.
- Task frequency assumes the same team and incoming task demand before and after AI adoption.

## Project-Defined Rating Scales

These are project scoring conventions, not published industry standards. The assigned scores above are hypotheses requiring validation.

| Level | Task frequency, per team | Repetitive operation person-hours / total person-hours |
|---|---|---|
| 1 | Less than 1 task/month | Below 20% |
| 2 | 1–3 tasks/month | 20% to below 40% |
| 3 | 4–9 tasks/month | 40% to below 60% |
| 4 | 10–19 tasks/month | 60% to below 80% |
| 5 | At least 20 tasks/month | 80%–100% |

## Needs Validation / Industry Expert Interview

- **W01 — RWE scientists and epidemiologists:** Confirm protocol complexity, role allocation, preparation/drafting/discussion/review hours, incoming task volume, repetitive work and protocol defect definitions.
- **W09 — Evidence synthesis researchers:** Confirm the screening and extraction batch, independent review requirements, adjudication time, error denominators, task volume and transferability of S1.
- **W04 — Data engineers and clinical informatics experts:** Fix source complexity, field count, coding systems and data quality; measure mapping, cleaning, exception handling and review effort.
- **W05 — Data analysts and QA reviewers:** Confirm exception severity, investigation/resolution scope, false positives, verification effort and task frequency.
- **W07 — Epidemiologists, programmers and clinicians:** Specify endpoint type (e.g., OS or rwPFS), data sources, observation windows and reference standard; measure implementation and clinical review time.
- Validate estimated error rates, role counts, frequency and repetitive labor scores with task records or structured interviews. Validate AI time savings and residual quality in a matched pilot; expert opinion alone does not establish realized gains.

## Source

**S1:** Gates et al. (2021), [Creating efficiencies in the extraction of data from randomized trials: a prospective evaluation of a machine learning and text mining tool](https://doi.org/10.1186/s12874-021-01354-2), Results, “Time Savings.” Across 75 randomized trials, median manual extraction time was 16.4 minutes/article versus 13.8 minutes/article to review and amend automated extractions. First-reviewer totals were 21.6 versus 17.9 hours. These measurements do not establish the full-batch estimates above and do not include the second reviewer's verification in that comparison.
