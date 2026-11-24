# AIPY – LO2 · Delivery and Logistics Management — Study Themes 4 and 5

Project topic: Delivery and Logistics Management (continuation of LO1: ST1 quotation + ST2 service zones).
Evidence runs committed in this repository: success `outputs/runs/20261123-235408-c5d784`,
rejected batch `outputs/_failed/20261123-235414-d74280`, history `outputs/run_history.csv`.

---

## STUDY THEME 4

### 4.1 Files and batch processing

**Recurring task.** Every week the dispatch system exports one CSV with the delivery requests of that week.
The weekly closing must clean the exports, price each delivery with the ST1 formula and the ST2 zone fee,
and give the operations coordinator one consolidated, validated result.

| Item | Definition |
|---|---|
| Intended user | Dispatch / operations coordinator (weekly closing of quotations) |
| Required inputs | ≥ 2 files `data/raw/deliveries_<start>_to_<end>.csv` with the 8 columns in `data/raw/README.md` |
| Useful outputs | validated CSV, excluded-rows CSV, formatted workbook, short text report, log and run status |

**One execution, two related CSVs.** `python run_pipeline.py` discovers every `deliveries_*.csv`
(`batch.discover_input_files`), processes each one with the same functions (`batch.process_file`) and
concatenates them into one batch (`batch.run_batch`). Run `20261123-235408-c5d784`:

| Source file | Raw rows | Exact duplicates | Business-invalid | Valid |
|---|---|---|---|---|
| deliveries_2026-10-05_to_2026-10-11.csv | 44 | 1 | 2 | 41 |
| deliveries_2026-10-12_to_2026-10-18.csv | 39 | 1 | 2 | 36 |
| **Batch** | **83** | **2** | **4** | **77** |

**ST3 logic reused (`delivery_pipeline/st3_cleaning.py`, `st3_analysis.py`).** The ST3 workflow
(import → inspect → clean → transform → analyze) of the ST3 course project and mini-case is
organised as functions. The original ST3 script was not stored in this repository, so the ST3 steps were
re-implemented here as a module, keeping the ST1 prices and ST2 thresholds unchanged (verified by
tests T1–T6 of LO1, see `tests/test_pipeline.py::St1St2RulesTest`).

| ST3 step | Function | Decision and reason |
|---|---|---|
| Inspect | `inspect_dataset` | shape, missing values, duplicates per file (logged) |
| Missing customer | `fill_missing_customer` | fill `Unknown`: the name is not needed for the price; identity is not invented |
| Inconsistent text | `standardize_text` | strip + title case on `district`, `vehicle` so `  xaxim ` = `Xaxim` |
| Numbers stored as text | `to_number`, `convert_types` | remove `kg`/`km`, comma → dot, `to_numeric`; dates `%Y-%m-%d` |
| Exact duplicate | `remove_exact_duplicates` | same delivery exported twice would double count revenue |
| Business rule | `split_business_invalid` | distance, weight and minutes must be > 0; rows kept in `excluded_records.csv` with the reason |
| Derived variables | `add_quotation_columns`, `add_derived_variables` | ST1 components, ST2 zone + fee, final cost, `minutes_per_km` |

**Adaptations for ST4 (documented).**
1. Functions instead of a linear script so that the same code runs for every file.
2. Files are read with `dtype=str` so that conversion problems are visible (V2) instead of silently guessed by pandas.
3. Duplicate detection ignores the traceability columns `source_file` and `source_row`.
4. Removed rows are not discarded: they are saved with their reason.
5. Title case is applied only to grouping categories. Customer names are only stripped, because title case produced `Café Do Bairro`.

**Paths, originals and source filenames.** All paths are centralised in `config.ProjectPaths`. Raw files are
only read, and their SHA-256 hashes are compared before and after the run (`verify_raw_inputs_unchanged`, logged
as “Raw inputs unchanged”). Every processed row keeps `source_file` and `source_row` (CSV line). Results are
saved as CSV in the run folder (`deliveries_processed.csv`, `excluded_records.csv`).

### 4.2 Spreadsheet automation

`workbook.write_workbook` generates `st4_delivery_batch.xlsx` from the validated batch with no manual steps.

| Sheet | Content |
|---|---|
| Deliveries | detailed records (77 rows, 18 columns, with source file and line) |
| Zone Summary | **business summary**: ST3 `groupby("service_zone")` aggregation, **sorted by revenue (descending)** |
| District Summary | secondary grouping by district, sorted by revenue |
| Excluded Records | the 6 removed rows with reasons |
| Validation Rules | V1–V6 with status |

Zone Summary (run `20261123-235408-c5d784`):

| Zone | Deliveries | Distance (km) | Revenue (BRL) | Avg cost (BRL) | Revenue share |
|---|---|---|---|---|---|
| Extended | 26 | 485.3 | 1,717.01 | 66.04 | 45.6% |
| Standard | 33 | 336.6 | 1,451.84 | 44.00 | 38.5% |
| Local | 18 | 63.9 | 597.81 | 33.21 | 15.9% |

**Presentation.** Readable headers (`Final Delivery Cost (BRL)` instead of `final_delivery_cost_brl`), bold header
with fill, width adjusted to the content, number formats (`R$ #,##0.00`, km `#,##0.0`, kg `#,##0.00`,
percentage `0.0%`, dates `yyyy-mm-dd`), **frozen header (`A2`) and AutoFilter on every sheet**. All
quantities and amounts are written as numbers, not text.

**Verification against the processed data.** After saving, `workbook.verify_workbook` reads the .xlsx back
and compares it with `deliveries_processed.csv`. All 7 checks passed:
- rows: 77 = 77;
- total cost: 3766.66 = 3766.66;
- distance: 885.8 = 885.8;
- summary deliveries: 77 = 77;
- summary revenue = detail revenue;
- the cost column is `float64`.

The result is printed in the report. The run fails if any check differs.

### 4.3 Reports and robustness

**Report** `st4_batch_report.txt` (user: operations coordinator) contains:
- the run ID, the generation time and the status;
- the 2 source files with period, row counts and SHA-256;
- the scope (77 valid deliveries from 2026-10-05 to 2026-10-18, pricing policy, 6 rows not used);
- the rules applied and the indicators;
- the zone summary;
- the finding and the limitation;
- the workbook verification.

**Indicators (ST3 `calculate_indicators`, same validated data as CSV and workbook).**

| Indicator | Value |
|---|---|
| Valid deliveries | 77 |
| Total quoted revenue | R$ 3,766.66 |
| Average delivery cost | R$ 48.92 |
| Largest delivery cost | R$ 96.30 |
| Total distance | 885.8 km |
| Extended share | 33.8% of deliveries, 45.6% of revenue |

**Finding.**
- Evidence: Extended is 33.8% of the deliveries but 45.6% of the revenue. Its average cost is R$ 66.04, against R$ 33.21 in the Local zone.
- Interpretation: long routes bring more revenue per delivery than their volume suggests, so long-route capacity may deserve priority in weekly planning.

**Limitation.**
- Evidence: the batch covers 14 days and 6 raw rows were excluded. The amounts are quoted prices from the team-defined ST1/ST2 policy.
- Interpretation: the figures describe quoted revenue, not profit, and two weeks cannot show seasonality.

**Same data everywhere.** The workbook and the report are computed from `deliveries_processed.csv`, read back
after it is written. The automated test `test_outputs_agree_and_are_published` checks that CSV, workbook, manifest,
report and integrated CSV all show R$ 3,766.66.

**Validation rules before publication (any failure rejects the input and stops the whole batch).**

| Rule | Check | Why it is needed |
|---|---|---|
| V1 Schema | exactly the 8 required columns | files must be compatible to form one batch; a missing column would become NaN silently |
| V2 Types | distance, weight, minutes numeric after cleaning | an unreadable number cannot be priced and must not be guessed |
| V3 Period | valid date inside the period in the file name | prevents a week from being mixed with another or counted twice |
| V4 Key | `delivery_id` filled and unique across the batch | two different records with one ID would double count revenue |
| V5 Quality | ≤ 10% business-invalid rows per file | a larger share means a broken export; publishing would understate totals |
| V6 Consistency | final cost = components; zone = ST2 rule | guarantees the published amounts follow the pricing policy |

**Errors and failure handling.**
- A missing folder or fewer than 2 files raise `InputMissingError`. A rejected file raises `BatchRejectedError` with the rule, the file and the CSV lines.
- Each run writes only to `outputs/_incomplete/<run_id>/`. It is moved to `outputs/runs/<run_id>/` with a single rename **only after every stage and check passes**.
- On failure, the partial files and `ERROR.txt` go to `outputs/_failed/<run_id>/`, the history records `FAILED`, and `LATEST_SUCCESSFUL_RUN.txt` is not touched. Earlier runs are never overwritten, because each run has a unique folder.

Demo (`python run_pipeline.py --input-dir data/demo_invalid_batch`):

```
ERROR | RUN 20261123-235414-d74280 FAILED: BatchRejectedError: [V1] deliveries_2026-10-12_to_2026-10-18.csv:
        incompatible columns - missing ['package_weight_kg'], unexpected []
ERROR | Nothing was published. Latest successful run is unchanged.
```

**Log and status.** `logs/run_<run_id>.log` (copied into the run folder) records:
- the paths and the source files;
- each stage (1 acquisition, 2 validation, 3 ST4 storage, …);
- the counts per file;
- the rules, the checks and the final SUCCESS/FAILED.

One run command: `python run_pipeline.py`. The user identifies the latest run with
`python run_pipeline.py --status`, `outputs/LATEST_SUCCESSFUL_RUN.txt` or `outputs/run_history.csv`.

### 4.4 Documented AI interaction (ST4)

- **Tool:** GitHub Copilot agent (chat/agent mode) in Visual Studio Code 1.141.0. The model version is not displayed by the tool.
- **Date:** 2026-11-23.

**Prompt used** (translated from Portuguese): *“Do this work following all the rubrics [ST4/ST5 statement and
evaluation rubric pasted]. Put the necessary files in my repository so that I can commit them.”* Context
files given to the AI: `st1_delivery_cost.py`, `st2_delivery_zone.py`, the LO1 report and the ST3 course PDFs
(Course Project, Mini-Case, ST3.1–3.3).

**Relevant response.** The AI did four things:
- It noted that the ST3 script was not among the files and proposed re-implementing the ST3 workflow of the mini-case as reusable functions, keeping the LO1 rules.
- It proposed reading the files as text, using row-level ST3 cleaning plus file-level rejection rules, and generating the workbook and the report from the processed CSV.
- It proposed publishing through a staging folder.
- It wrote the code and the tests.

| # | Suggestion considered | Decision | Reason | Test / data check | Observed result |
|---|---|---|---|---|---|
| 1 | Re-implement ST3 as functions with ST1/ST2 constants unchanged | Accepted | one code path for all files; LO1 rules must stay identical | `St1St2RulesTest`: LO1 example (10 km/2 kg = R$ 27.00) and tests T1–T6 | 3/3 tests pass; R$ 13.50 … 46.65 reproduced |
| 2 | Drop every problematic row silently | Rejected | would hide broken exports and change totals without notice | – | – |
| 3 | Row-level exclusions only for business-invalid values, saved with reason, plus V5 limit of 10% | Accepted | keeps usable data and makes every removal traceable | `excluded_records.csv` vs log counts | 4 invalid + 2 duplicates = 6 rows, matching the log |
| 4 | Impute non-numeric distance/weight with the mean | Rejected | invents business data; a quotation cannot be priced on a guess | `test_v2_non_numeric_distance` | batch rejected with V2 and the CSV line |
| 5 | Read CSV with `dtype=str` and convert explicitly | Accepted | values like `4.1 kg` or `10,91` are converted instead of becoming text | processed CSV, line 16 of week 1 (`4.1 kg`) | `package_weight_kg = 4.1`, price computed |
| 6 | Build workbook/report from the processed CSV read back | Accepted | one source of truth for CSV, workbook and report | `verify_workbook` + `test_outputs_agree_and_are_published` | 7/7 PASS; R$ 3,766.66 in all outputs |
| 7 | Title case on all text columns (mini-case pattern) | Partly rejected | `Café do Bairro` became `Café Do Bairro`; customer is not a grouping category | rerun and inspection of `excluded_records.csv` | customer names kept as exported (only stripped) |
| 8 | Staging folder + atomic rename; rejected alternative: overwrite an `outputs/latest` folder | Accepted | failed runs must not look complete or overwrite earlier success | `RejectionTest` (V1–V5, missing file) | `runs/` unchanged, `LATEST` unchanged, history `SUCCESS, FAILED` |
| 9 | First version of the rejection tests | Corrected | AI-generated test corrupted the input *before* the reference run | `python -m unittest` | 5 errors at first, 0 after the fix (22/22 OK) |

**Remaining limitations.**
- The dataset is synthetic (`tools/generate_sample_data.py`).
- V5's 10% threshold is a team choice, not a company rule.
- ST3 was re-implemented because the original script was not available in this repository.

---

## STUDY THEME 5

### 5.1 API integration

**Business question.** *Do rainy days in Curitiba coincide with a slower delivery pace (min/km) or a different
demand?* The local exports contain date, distance and time, but **no weather information**, so they cannot
answer the question alone.

**API selected:** Open-Meteo Historical Weather API (`GET https://archive-api.open-meteo.com/v1/archive`). It is suitable because:
- it is documented (https://open-meteo.com/en/docs/historical-weather-api) and free for educational use, with no key;
- it returns **daily** values (the same level as `request_date`);
- it accepts a `timezone` parameter, so its days match the local calendar days of the deliveries;
- it declares units in `daily_units`.

**Controlled GET** (`api_client.fetch_daily_weather`):
- `requests.get(URL, params=..., timeout=(5, 20))`, followed by `raise_for_status()`;
- separate handling of `Timeout`, `HTTPError` (status code and body) and other `RequestException`s, all converted to `ExternalSourceError`;
- a non-JSON body raises `ExternalDataError`;
- TLS verification is never disabled.

Parameters:

| Parameter | Value | Meaning |
|---|---|---|
| latitude / longitude | -25.4284 / -49.2733 | Curitiba |
| start_date / end_date | 2026-10-05 / 2026-10-18 | derived from the validated batch (min/max `request_date`) |
| daily | precipitation_sum, rain_sum, temperature_2m_max, temperature_2m_min, wind_speed_10m_max | needed variables |
| timezone | America/Sao_Paulo | aligns API days with local delivery days |

**Saved response and documentation.** Each response is saved unmodified as `*_response.json`, with a sidecar
`*_metadata.json` that records the following (earlier files are never overwritten):
- provider and endpoint;
- parameters;
- acquisition date (`acquired_at`) and acquisition method;
- units (time `iso8601`, precipitation `mm`, temperature `°C`, wind `km/h`);
- use conditions: free non-commercial use (< 10,000 calls/day), CC BY 4.0 with attribution, no warranty.

The committed response `data/external/open_meteo/20261123T234610_…` was obtained on 2026-11-23 with the same URL
through the AI tool's web fetch, because the corporate network of the development machine intercepts TLS (a self-signed
certificate in the chain) and Python could not connect. This is recorded in the metadata.

**JSON inspection.**

| JSON element | Type | Use |
|---|---|---|
| root | dict | `latitude`, `longitude`, `timezone`, `elevation` (location actually used: -25.41, -49.24, 920 m) |
| `daily_units` | dict | units checked against `config.WEATHER_EXPECTED_UNITS` |
| `daily` | dict of lists | `time` (list of dates) + one list per variable, same length |

`weather_payload_to_dataframe` maps `time → weather_date`, `precipitation_sum → precipitation_mm`,
`rain_sum → rain_mm`, `temperature_2m_max/min → temperature_max_c/min_c` and
`wind_speed_10m_max → wind_speed_max_kmh`. It also adds `rain_category`, using an if/elif/else rule in the ST2 style:
- below 1 mm: Dry (the WMO "wet day" threshold is 1 mm);
- from 1 mm to below 10 mm: Light rain;
- 10 mm or more: Heavy rain.

**Checks and reaction to unsuitable data** (`validate_weather_payload`). Each check raises `ExternalDataError`, and the run fails without publishing.

| Check | Code reaction |
|---|---|
| `daily` and `daily_units` are dicts; all fields present | missing field → error naming it |
| lists of equal length | error with the lengths |
| units exactly as expected | e.g. `inch` instead of `mm` → error |
| values numeric, no `null` (days not yet available) | error naming the field |
| precipitation ≥ 0; one row per date | error |
| coverage: every delivery date exists in the response | error listing the missing dates |
| network/HTTP failure | `live` mode: run fails. `auto`: falls back to the latest saved response with the same parameters and records the source mode `cache` and the reason |

The tests in `ExternalDataTest` simulate each case: a missing field, a wrong unit, a null value, a coverage gap and the category boundaries.

### 5.2 Data acquisition and integration

**Row meaning.**
- Local (`deliveries_processed.csv`): one row = one validated delivery.
- External (`weather_daily.csv`): one row = one calendar day of weather in Curitiba.

**Join key.** `date_key = YYYY-MM-DD`:
- local side: `request_date`, normalized;
- external side: `weather_date` (`integration.add_date_key`).

Both sides use the local timezone. Method: `merge(how="left", validate="many_to_one", indicator=True)`.
A left join is used so that a delivery without weather can never disappear silently. An inner join was rejected for that reason.

**Checks** (`integrate_deliveries_with_weather`, run `20261123-235408-c5d784`). All passed; if any check fails, the run raises `IntegrationError`.

| Check | Expected | Observed |
|---|---|---|
| Weather key unique (one row per day) | 0 duplicates | 0 |
| Cardinality many-to-one | pandas `validate` | OK |
| Deliveries without weather match | 0 | 0 |
| Row count preserved | 77 | 77 |
| Total revenue preserved (BRL) | 3766.66 | 3766.66 |
| Total distance preserved (km) | 885.8 | 885.8 |
| `delivery_id` still unique | 0 duplicates | 0 |
| Delivery days covered | 14 | 14 |

**Traceability.**
- Every integrated row keeps `source_file` and `source_row` from the local side, and `weather_source` and `weather_response_file` from the external side.
- Raw CSVs and saved API responses remain unchanged in `data/`.
- `run_manifest.json` lists the hashes of the input files and the response file used.

### 5.3 Simple workflow design

One documented command (README, VS Code terminal): `python run_pipeline.py`. `workflow.run_workflow` calls named stage
functions:

| Stage | Function |
|---|---|
| Acquisition | `acquire_local_inputs`, `acquire_external_data` |
| Validation | `validate_local_batch`, `validate_external_data`, `verify_raw_inputs_unchanged` |
| Integration | `integrate_sources` |
| Storage | `store_st4_outputs`, `store_st5_outputs`, `write_manifest`, then `runlog.publish_run` |

**ST4 outputs extended:**
- `deliveries_with_weather.csv` is the integrated CSV;
- `st5_delivery_weather.xlsx` is the updated workbook: all ST4 sheets plus *Deliveries + Weather*, *Rain Summary* (sorted by pace), *Daily Weather*, *Integration Checks* and *External Source*, verified by read-back (7/7 PASS);
- `st5_weather_report.txt` explains the external information.

The report includes:
- the question;
- the provider, endpoint, parameters, acquisition date, units, conditions and coverage;
- the integration method and checks;
- the indicators by rain category;
- the finding and the limitation, with evidence separated from interpretation.

| Rain category | Days | Deliveries | Deliveries/day | Revenue/day (BRL) | Pace (min/km) |
|---|---|---|---|---|---|
| Dry | 3 | 13 | 4.3 | 189.32 | 4.19 |
| Heavy rain | 3 | 19 | 6.3 | 327.38 | 3.88 |
| Light rain | 8 | 45 | 5.6 | 277.07 | 3.75 |

**Finding.**
- Evidence: rainy days (11 days, 64 deliveries) had a pace of 3.79 min/km, against 4.19 on dry days (3 days, 13 deliveries), a difference of −9.7%.
- Interpretation: the evidence does not support a rain buffer on promised times. It does not prove that rain speeds deliveries up, because the route mix could explain the gap, and this was not tested.

**Limitation.** Only 14 days are covered, and the weather value is a daily total for one point. Association is not cause.

**Log, source mode and protection of outputs.**
- The log records the run ID, the weather request, the live failure and the fallback (`WARNING … falling back to cached response`), and the response file used.
- The source mode appears in the ST5 report, the manifest, `LATEST_SUCCESSFUL_RUN.txt` and `run_history.csv`.
- Incomplete results stay in `_incomplete/`, or in `_failed/` after a failure. Earlier successful runs stay in `runs/`, as in ST4.

### 5.4 Documented AI interaction (ST5)

- **Tool:** GitHub Copilot agent in Visual Studio Code 1.141.0 (model version not displayed).
- **Date:** 2026-11-23.
- **Prompt:** the same as in 4.4.

**Relevant response.**
- The AI proposed a weather question for the delivery data and compared candidate APIs.
- It found the TLS interception when it tested the API from Python, and proposed a saved response with source modes.
- It proposed a date-key many-to-one join with reconciliation checks, and wrote the validation code and the tests.

| # | Suggestion considered | Decision | Reason | Test / data check | Observed result |
|---|---|---|---|---|---|
| 1 | Open-Meteo historical weather (daily, documented, keyless, units declared) | Accepted | answers a question the local data cannot; same daily grain as deliveries | coverage check against the 14 delivery dates | 14/14 days covered |
| 2 | BrasilAPI holidays / BCB SGS indicators | Rejected | holidays: only 1 (12 Oct) in the period, too little variation. Monthly macro indicators: wrong grain for daily deliveries | – | – |
| 3 | `verify=False` to bypass the corporate TLS error | Rejected | disables security; not acceptable in production code | live run on the development machine | `SSLError` logged; no insecure connection made |
| 4 | Save the real response + `--source-mode live/cache/auto` | Accepted | reproducible offline run; the source is always identified | run log + `run_history.csv` | `WARNING … falling back`, `source_mode=cache` |
| 5 | Inner join on date | Rejected | unmatched deliveries would disappear silently | `test_unmatched_delivery_is_rejected` | `IntegrationError` raised |
| 6 | Left join with `validate="many_to_one"`, `indicator=True` and reconciliation of counts and totals | Accepted | detects duplicate days, unmatched rows and inflated totals | integration checks + `IntegrationTest` | 77 → 77 rows; R$ 3,766.66 = 3,766.66; duplicate day → error |
| 7 | Validate units, nulls, types and coverage before the DataFrame is used | Accepted | protects against API changes or incomplete recent days | `ExternalDataTest` (5 cases) | each invalid payload rejected |
| 8 | First interpretation: *“other factors (route, vehicle, traffic) explain the pace better than rain”* | Rejected and rewritten | claim not supported by the evidence (not tested) | review of report text vs calculated values | interpretation now limited to what the numbers support |

**Remaining limitations.**
- The committed response was fetched through the AI tool. The code performs the live GET itself on a network without TLS interception.
- With 3 dry days only, the comparison is weak.
- Weather is a single-point daily value, not route-level.

---

## Rubric traceability matrix

| Criterion | Evidence |
|---|---|
| 4.1 | §4.1; `batch.py`, `st3_cleaning.py`; `deliveries_processed.csv` (`source_file`, `source_row`); SHA-256 check in the log |
| 4.2 | §4.2; `workbook.py`; `st4_delivery_batch.xlsx`; read-back checks in the report; `test_workbook_presentation` |
| 4.3 | §4.3; `report.py`, `runlog.py`; `st4_batch_report.txt`; `_failed/20261123-235414-d74280`; `run_history.csv`; `RejectionTest` |
| 4.4 | §4.4 (tool, prompt, response, accepted/rejected, check, observed result, limitation) |
| 5.1 | §5.1; `api_client.py`; `data/external/open_meteo/*_response.json` + `*_metadata.json`; `ExternalDataTest` |
| 5.2 | §5.2; `integration.py`; Integration Checks sheet; `IntegrationTest` |
| 5.3 | §5.3; `workflow.py`, `run_pipeline.py`; `deliveries_with_weather.csv`, `st5_delivery_weather.xlsx`, `st5_weather_report.txt` |
| 5.4 | §5.4 |

How to reproduce: `pip install -r requirements.txt`, then `python run_pipeline.py`, then
`python -m unittest discover -s tests -v` (22 tests, all passing on 2026-11-23).
