# First-round validation of the data cleaning agent

Version evaluated: [fb9db275](https://github.com/yunyu79/AI-Agent-Opportunity-Assessment-in-RWE-Workflow-Healthcare/commit/fb9db275aa43595c54c99971fb848f2b909b1bfb). This round used synthetic data to check issue detection, rule assignment, and execution of approved actions. Human time is estimated because historical time logs and independent manual QC records were unavailable.

## Measured results

We checked all 100 rows in a controlled fixture against issue locations and types specified during fixture construction. The unit of comparison was column or whole-row scope × issue type × source row. A row could trigger multiple checks. Both members of the duplicate group counted as candidates. Repeated ZIP codes were expected and permitted.

| Metric | Result | What was checked |
| --- | --- | --- |
| Detection precision | 47/47 (100%) | 40 missing cells, one IQR outlier, one range violation, one date-order violation, two repeated identifier candidates, and two exact duplicate candidates. The outlier and range violation came from the same value. |
| Detection recall | 47/47 (100%) | All seeded findings were detected, with zero false positives and zero false negatives. Permitted ZIP code repetitions were unflagged. |
| Missingness rule assignment | 4/4 (100%) | 4% missing in a noncritical column → M1, 5% in a critical column → M2, 10% → M3, and 21% → M4. |
| LLM recommendation accuracy | Unmeasured | No live model call was made. The quality of explanations and recommendations and the rate of human overrides remain unmeasured. |
| Calculation and execution accuracy | 5/5 (100%) | The approved median fill produced the independently expected value of 53 in all five cells. The full output and audit matched expectations. |
| Output QC | 5/5 checks passed | Imputed values, full output, audit coverage, pending MICE status, and external CSV parsing with leading zeros preserved. MICE was deferred. |

We also checked three repository examples with 500 rows each. File hashes matched the manifest, and all six aggregate checks passed. `patient.csv` had 150 missing `race` values and two excess exact duplicates. `medication.csv` had 125 missing `paid_amount` values and zero excess duplicates. `procedure.csv` had 125 missing `description` values and one excess duplicate. The examples have aggregate reference counts only, so they support aggregate validation rather than issue-level accuracy estimates. The repository's 41 existing tests also passed.

**Export limitation.** External CSV readers parse the cleaned output correctly. The agent's upload entry point rejects the reserved `__source_row__` column included in the export, so direct re-upload into the agent failed.

## Timing and planning estimates

Across seven local runs on the 100-row controlled fixture, the median times were 0.007 seconds to detect issues and prepare the review table, 0.016 seconds to execute approved actions, and 0.002 seconds to calculate statistics and serialize the CSV. These timings cover local code execution. Browser interaction, online model latency, waiting, and human review were outside the timing scope.

The estimates below assume one analyst, an approximately 500-row table, known rules, and the same independent QC scope in both workflows. Units are active person-minutes per dataset. Each activity is counted once. Low, base, and high are planning scenarios rather than confidence intervals.

| Activity | Manual low / base / high | AI-assisted low / base / high | Base-case breakdown |
| --- | ---: | ---: | --- |
| Processing | 25 / 40 / 65 | 10 / 18 / 35 | Manual: 15 inspection, 20 cleaning and export, 5 rework. AI: 5 setup, 8 review and selection, 5 export and rework. |
| Communication | 5 / 10 / 20 | 5 / 8 / 20 | Two clarification rounds in each workflow, at five minutes per manual round and four per AI-assisted round. |
| QC | 12 / 20 / 35 | 10 / 15 / 30 | Manual: 15 checks, 5 retest. AI: 10 output and audit checks, 5 retest. |
| **Total** | **42 / 70 / 120** | **25 / 41 / 85** | **29 minutes of estimated savings in the base case.** |

Response wait times and online model latency remain unmeasured. A paired manual comparison should capture active minutes for each participant and total elapsed time from intake to delivery. Have the manual analyst work independently and apply identical QC criteria to both outputs. The synthetic results establish a functional baseline. A realized ROI estimate needs timed work and independent QC.

## Reproduction

Install dependencies from `Data Cleaning Prototype/requirements.txt`. From the repository root, run `python research/validate_cleaning_agent.py`. The script reports counts and timings without an API key. [Raw validation results](data_cleaning_validation_results.json).
