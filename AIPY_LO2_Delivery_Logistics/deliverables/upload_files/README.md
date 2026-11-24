# AIPY – LO2 · Delivery and Logistics Management (ST4 + ST5)

Weekly closing of delivery quotations for a small Curitiba delivery operation, automated end to end:
two weekly CSV exports → ST3 cleaning/validation → processed CSV + Excel workbook + text report (ST4)
→ daily weather from the Open-Meteo API → integrated CSV + updated workbook + report (ST5).

Full documentation (rubric items 4.1–5.4, AI interaction, traceability matrix):
[docs/LO2_Report_ST4_ST5.md](docs/LO2_Report_ST4_ST5.md)

## One command (VS Code terminal)

```powershell
pip install -r requirements.txt          # first time only
python run_pipeline.py                   # full run (ST4 + ST5), weather source mode "auto"
```

| Option | Effect |
|---|---|
| `--source-mode live` | Weather only from the live API (run fails if the API is unreachable) |
| `--source-mode cache` | Weather from the saved response in `data/external/open_meteo` (offline) |
| `--source-mode auto` | Default: live API, falling back to the saved response (fallback is logged) |
| `--st4-only` | Only the ST4 batch, workbook and report |
| `--input-dir data/demo_invalid_batch` | Demonstrates a rejected batch (missing column → nothing published) |
| `--status` | Shows the latest successful run and the recent run history |

The command works from any folder (`python AIPY_LO2_Delivery_Logistics/run_pipeline.py`).
Exit code `0` = SUCCESS, `1` = FAILED.

## Where are the results? How do I know the latest run and its status?

```
outputs/
├── LATEST_SUCCESSFUL_RUN.txt   ← id, folder and source mode of the latest successful run
├── run_history.csv             ← one line per run: SUCCESS / FAILED, mode, files, message
├── runs/<run_id>/              ← completed runs only (never overwritten)
├── _failed/<run_id>/           ← partial files + ERROR.txt of rejected runs (never mixed with runs/)
└── _incomplete/<run_id>/       ← staging area while a run is in progress
logs/run_<run_id>.log           ← steps, source files, outcome (also copied into the run folder)
```

Each successful run folder contains:

| File | Stage |
|---|---|
| `deliveries_processed.csv` | ST4 validated batch (one row = one delivery, with `source_file` and `source_row`) |
| `excluded_records.csv` | ST4 rows removed by ST3 rules, with the reason |
| `st4_delivery_batch.xlsx` | ST4 workbook: Deliveries, Zone Summary, District Summary, Excluded Records, Validation Rules |
| `st4_batch_report.txt` | ST4 user report |
| `weather_daily.csv` | ST5 API data as a DataFrame (one row = one day) |
| `deliveries_with_weather.csv` | ST5 integrated CSV |
| `st5_delivery_weather.xlsx` | ST5 updated workbook (ST4 sheets + weather, rain summary, integration checks, source) |
| `st5_weather_report.txt` | ST5 report explaining the external information |
| `run_manifest.json` | run id, source mode, input file hashes, indicators, checks |

## Tests

```powershell
python -m unittest discover -s tests -v   # 22 tests: ST1/ST2 rules, V1–V5 rejections, workbook, API, join
```

## Submission files

`deliverables/AIPY_LO2_Delivery_Logistics_Report.pdf` (report + appendices with the generated reports and logs)
and `deliverables/AIPY_LO2_Delivery_Logistics_Project.zip` (this folder without caches). Rebuild them with
`python tools/build_deliverables.py` (needs `pip install markdown` and Microsoft Edge).

## Project structure

```
run_pipeline.py              single entry point (CLI)
delivery_pipeline/
  config.py                  paths, ST1 prices, ST2 zones, batch rules, API settings
  st3_cleaning.py            ST3 cleaning/validation/transformation functions (reused)
  st3_analysis.py            ST3 indicators and grouped summaries (reused)
  batch.py                   ST4 file discovery and validation rules V1–V6
  workbook.py                ST4/ST5 formatted Excel + read-back verification
  report.py                  ST4/ST5 text reports
  api_client.py              ST5 GET request, response storage, JSON validation, DataFrame
  integration.py             ST5 join on date key + reconciliation
  runlog.py                  run id, log, staging, publication, history
  workflow.py                named stages: acquisition → validation → integration → storage
data/raw/                    original weekly exports (read-only, never edited)
data/external/open_meteo/    saved API responses + metadata (provider, endpoint, params, date, units, terms)
data/demo_invalid_batch/     input set that must be rejected (demo of failure handling)
tools/generate_sample_data.py how the synthetic raw exports were created (never overwrites raw files)
tests/test_pipeline.py       automated checks
docs/LO2_Report_ST4_ST5.md   documentation for the evaluation
```

Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
