# AI Agent Opportunity Assessment in RWE and HEOR

## 1. Purpose

This project identifies where AI agents could reduce manual work and boost efficiency in the workflow of real-world evidence (RWE) in the healthcare industry. 

It maps the workflow, compares candidate scenario opportunities, and develops a data-cleaning prototype to test whether an agent can help analysts identify issues and apply approved corrections. A first-round validation and ROI estimate provide a basis for deciding whether to run a broader pilot.

## 2. Project workflow

- [Map the RWE workflow](research/1.%20workflow.md) to identify the tasks, handoffs, and outputs across an RWE study.
- [Identify workflow pain points](research/2.%20rwe_painpoints_with_evidence.md) where manual effort, repetition, coordination, errors, or rework may justify AI assistance.
- [Define candidate use cases](research/5.%20candidate_use_cases.md) by linking workflow problems to tasks an agent could support.
- [Rank and select a scenario](#3-from-opportunity-ranking-to-pilot-selection) using weighted criteria and an interactive sensitivity analysis.
- [Build the prototype](#4-data-cleaning-agent) for data cleaning and standardization, the top-ranked opportunity under the default weights.
- [Validate the prototype](#5-first-round-validation) by checking detection, rule assignment, and execution against expected results on synthetic data.
- [Estimate ROI](#6-first-year-roi-estimate) by valuing potential labor savings and accounting for API, maintenance, and development costs.

## 3. From opportunity ranking to pilot selection

### Weighted Scenario Prioritization and Interactive Sensitivity Analysis

https://github.com/user-attachments/assets/98460b94-aa21-406e-b493-112859994c50

Download the dashboard HTML and open it in a browser to adjust the weights and see how the ranking changes. [Interactive sensitivity dashboard](research/scenario_prioritization.html)

**Default weights**

| Metric | Default weight |
|---|---|
| Potential human-effort savings | 35% |
| Potential error reduction | 25% | 
| Reduction in repetitive labor share | 15% | 
| Task frequency | 15% | 
| Reduction in collaboration burden | 10% |

**Score calculation for each scenario**

- **Labor savings.** Divide estimated hours saved by 320 and multiply by 100.
- **Error reduction.** Divide the decrease in error rate, measured in percentage points, by 5 and multiply by 100.
- **Repetition reduction.** Divide the decrease in repetition level by 4 and multiply by 100.
- **Frequency.** Subtract 1 from the baseline task frequency level, divide by 4, and multiply by 100.
- **Collaboration reduction.** Divide the decrease in collaboration level by 4 and multiply by 100.

The dashboard caps the labor and error dimensions at −100 to 100 and sums each dimension score multiplied by its normalized weight.

#### Default ranking from the current inputs

| Rank | Scenario | Potential hours saved per scoped task | Error reduction (percentage points) | Weighted score |
|---|---|---|---|---|
| 1 | W04: Data cleaning and standardization | 218 | 3 | 56.34 |
| 2 | W01: Research question and protocol design | 220 | 2 | 44.06 |
| 3 | W05: Data quality control | 65 | 2 | 40.86 |
| 4 | W09: Literature screening | 15 | 1 | 14.14 |

W04 was selected for the first prototype because it ranks highest under the default inputs. The ranking is a planning estimate that depends on the assumed effort, error rates, and weights. The methodology describes the underlying task scopes and rating scales. [Full prioritization analysis](research/3.%20compare%20significance%20and%20prioritize%20scenario.md)

## 4. Data cleaning agent

The prototype profiles CSV inputs for missing values, outliers, duplicate candidates, and rule violations. It proposes treatments in a review table, lets analysts choose an action for each issue, and applies supported changes after approval. Analysts can compare the original and cleaned data, export the cleaned CSV, and download a management report.

<img width="960" height="567" alt="entire1" src="https://github.com/user-attachments/assets/39eaa40a-9974-4a4a-a6d0-641172103464" />

**Technology stack**

- **GPT-6.1 Sol through the OpenAI Responses API** generates issue explanations and treatment recommendations from study context and aggregate findings.
- **LangGraph** coordinates profiling, planning, human approval, execution, and validation.
- **Skill authoring** codifies cleaning rules, treatment eligibility, and approval requirements in a reusable [data cleaning skill](Data%20Cleaning%20Prototype/SKILL.md).
- **Prompt engineering with edge cases** guides recommendations for cases such as missingness at the 5% threshold, tied modes, and legitimate repeated ZIP codes, with instructions to explain uncertainty and defer methods when evidence is insufficient.
- **Pydantic** validates the structure of model recommendations before the app displays them for review.
- **Python and pandas** support rule-based data checks, approved transformations, and quality summaries.
- **Streamlit** provides the analyst interface, editable review table, and approval controls.
- **openpyxl** generates Excel review workbooks with treatment dropdowns.

[Prototype setup and usage](Data%20Cleaning%20Prototype/README.md)

## 5. First-round validation

We checked all 100 rows in a controlled fixture against issue locations and types specified during fixture construction. The unit of comparison was column or whole-row scope × issue type × source row. A row could trigger multiple checks. Both members of the duplicate group counted as candidates. Repeated ZIP codes were expected and permitted.

| Metric | Result | What was checked |
| --- | --- | --- |
| Detection precision | 47/47 (100%) | 40 missing cells, one IQR outlier, one range violation, one date-order violation, two repeated identifier candidates, and two exact duplicate candidates. The outlier and range violation came from the same value. |
| Detection recall | 47/47 (100%) | All seeded findings were detected, with zero false positives and zero false negatives. Permitted ZIP code repetitions were unflagged. |
| Missingness rule assignment | 4/4 (100%) | 4% missing in a noncritical column → M1, 5% in a critical column → M2, 10% → M3, and 21% → M4. |
| LLM recommendation accuracy | Unmeasured | No live model call was made. The quality of explanations and recommendations and the rate of human overrides remain unmeasured. |
| Calculation and execution accuracy | 5/5 (100%) | The approved median fill produced the independently expected value of 53 in all five cells. The full output and audit matched expectations. |
| Output QC | 5/5 checks passed | Imputed values, full output, audit coverage, pending MICE status, and external CSV parsing with leading zeros preserved. MICE was deferred. |

The controlled fixture returned all 47 expected findings. Three additional synthetic files totaling 1,500 rows matched all six reference counts for missingness and exact duplicate excess, and 41 repository tests passed. This round establishes a baseline for deterministic checks and approved execution. Live model recommendation accuracy and paired manual versus AI-assisted work times remain unmeasured. [Validation report and reproduction steps](research/data_cleaning_validation.md)

## 6. First-year ROI estimate

**ROI = (total benefit − AI cost) ÷ AI cost × 100%**

The illustrative base case assumes 1,000 datasets per year, a loaded analyst rate of $60/hour, and 29 minutes of active labor saved per dataset. First-year AI costs include API usage, maintenance, and development.

| First-year result | Base-case estimate |
| --- | ---: |
| Active labor per dataset, manual → AI-assisted | 70 → 41 minutes |
| Labor capacity value | $29,000 |
| AI cost | $18,500 |
| Net capacity benefit | $10,500 |
| **First-year capacity ROI** | **56.8%** |
| **Total workflow cost reduction versus manual** | **15.0%** |
| Break-even annual volume at base-case savings | 632 datasets |

The ROI estimate values staff time released for other work. Realized cash savings remain unmeasured. [ROI assumptions and sensitivity analysis](research/4.%20roi%20analysis.md)
