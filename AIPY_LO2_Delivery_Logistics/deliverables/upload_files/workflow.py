"""Workflow orchestration. Stages are named functions: acquisition, validation, integration and storage.
Everything is written to a staging folder and published only after all checks pass."""

import json
from pathlib import Path

import pandas as pd

from . import api_client, batch as batch_mod, integration, report, runlog, st3_analysis, workbook
from .config import ProjectPaths
from .errors import PipelineError, VerificationError

CSV_OPTIONS = {"index": False, "encoding": "utf-8-sig", "date_format": "%Y-%m-%d"}


# ---------------------------------------------------------------- acquisition
def acquire_local_inputs(paths: ProjectPaths, ctx: runlog.RunContext) -> tuple[list[Path], dict]:
    files = batch_mod.discover_input_files(paths.input_dir)
    ctx.input_files = [f.name for f in files]
    hashes = {f.name: batch_mod.file_sha256(f) for f in files}
    ctx.logger.info("Stage 1 - acquisition: %d input files in %s: %s", len(files), paths.input_dir, ctx.input_files)
    return files, hashes


def acquire_external_data(valid: pd.DataFrame, source_mode: str, paths: ProjectPaths,
                          ctx: runlog.RunContext) -> api_client.Acquisition:
    start = valid["request_date"].min().strftime("%Y-%m-%d")
    end = valid["request_date"].max().strftime("%Y-%m-%d")
    ctx.logger.info("Stage 4 - external acquisition (%s mode) for %s..%s", source_mode, start, end)
    acquisition = api_client.acquire_weather(start, end, source_mode, paths.external_dir, ctx.logger)
    ctx.source_mode = acquisition.source_mode
    return acquisition


# ---------------------------------------------------------------- validation
def validate_local_batch(files: list[Path], ctx: runlog.RunContext) -> batch_mod.BatchResult:
    ctx.logger.info("Stage 2 - validation: ST3 cleaning + rules %s", ", ".join(batch_mod.VALIDATION_RULES))
    result = batch_mod.run_batch(files, ctx.logger)
    ctx.valid_deliveries = len(result.valid)
    return result


def validate_external_data(acquisition: api_client.Acquisition, valid: pd.DataFrame,
                           ctx: runlog.RunContext) -> pd.DataFrame:
    required = sorted(valid["request_date"].dt.strftime("%Y-%m-%d").unique())
    api_client.validate_weather_payload(acquisition.payload, required)
    weather = api_client.weather_payload_to_dataframe(acquisition.payload, acquisition.response_file)
    ctx.logger.info("Stage 5 - external validation passed: %d days, units %s", len(weather),
                    acquisition.payload["daily_units"])
    return weather


def verify_raw_inputs_unchanged(files: list[Path], hashes_before: dict, ctx: runlog.RunContext) -> None:
    changed = [f.name for f in files if batch_mod.file_sha256(f) != hashes_before[f.name]]
    if changed:
        raise VerificationError(f"Raw input files changed during the run: {changed}")
    ctx.logger.info("Raw inputs unchanged (SHA-256 verified)")


# ---------------------------------------------------------------- integration
def integrate_sources(valid: pd.DataFrame, weather: pd.DataFrame,
                      ctx: runlog.RunContext) -> integration.IntegrationResult:
    result = integration.integrate_deliveries_with_weather(valid, weather)
    ctx.logger.info("Stage 6 - integration: %d rows, all %d checks PASS", len(result.integrated), len(result.checks))
    return result


# ---------------------------------------------------------------- storage
def _rules_table(batch: batch_mod.BatchResult) -> pd.DataFrame:
    return pd.DataFrame([{"rule_id": k, "description": v, "status": "PASS"}
                         for k, v in batch_mod.VALIDATION_RULES.items()])


def _st4_sheets(batch: batch_mod.BatchResult, zone_summary, district_summary) -> list[workbook.SheetSpec]:
    excluded_cols = [c for c in ["delivery_id", "request_date", "customer", "district", "distance_km",
                                 "package_weight_kg", "delivery_minutes", "exclusion_reason", "source_file",
                                 "source_row"] if c in batch.excluded.columns]
    return [
        workbook.SheetSpec("Deliveries", batch.valid[batch_mod.PROCESSED_COLUMN_ORDER]),
        workbook.SheetSpec("Zone Summary", zone_summary),
        workbook.SheetSpec("District Summary", district_summary),
        workbook.SheetSpec("Excluded Records", batch.excluded[excluded_cols]),
        workbook.SheetSpec("Validation Rules", _rules_table(batch)),
    ]


def store_st4_outputs(batch: batch_mod.BatchResult, ctx: runlog.RunContext) -> dict:
    out = ctx.staging_dir
    processed = batch.valid[batch_mod.PROCESSED_COLUMN_ORDER]
    processed.to_csv(out / "deliveries_processed.csv", **CSV_OPTIONS)
    batch.excluded.to_csv(out / "excluded_records.csv", **CSV_OPTIONS)

    # The workbook and the report are built from the processed CSV read back, so all three agree.
    reloaded = pd.read_csv(out / "deliveries_processed.csv", encoding="utf-8-sig", parse_dates=["request_date"])
    indicators = st3_analysis.calculate_indicators(reloaded)
    zone_summary = st3_analysis.summarize_by_zone(reloaded)
    district_summary = st3_analysis.summarize_by_district(reloaded)

    xlsx = workbook.write_workbook(out / "st4_delivery_batch.xlsx", _st4_sheets(batch, zone_summary, district_summary))
    checks = workbook.verify_workbook(xlsx, reloaded, zone_summary, "Deliveries", "Zone Summary")
    text = report.build_st4_report(ctx.run_id, batch, indicators, zone_summary, checks)
    (out / "st4_batch_report.txt").write_text(text, encoding="utf-8")
    ctx.logger.info("Stage 3 - storage (ST4): processed CSV, workbook (%d checks PASS) and report written", len(checks))
    return {"indicators": indicators, "zone_summary": zone_summary, "district_summary": district_summary,
            "workbook_checks": checks}


def store_st5_outputs(batch, st4: dict, acquisition, weather, integrated: integration.IntegrationResult,
                      ctx: runlog.RunContext) -> dict:
    out = ctx.staging_dir
    weather.to_csv(out / "weather_daily.csv", **CSV_OPTIONS)
    integrated_cols = batch_mod.PROCESSED_COLUMN_ORDER + [
        "date_key", "precipitation_mm", "rain_mm", "temperature_max_c", "temperature_min_c", "wind_speed_max_kmh",
        "rain_category", "weather_source", "weather_response_file"]
    integrated.integrated[integrated_cols].to_csv(out / "deliveries_with_weather.csv", **CSV_OPTIONS)

    reloaded = pd.read_csv(out / "deliveries_with_weather.csv", encoding="utf-8-sig", parse_dates=["request_date"])
    rain_summary = integration.summarize_by_rain(reloaded)
    daily_summary = integration.summarize_by_day(
        reloaded.assign(weather_date=pd.to_datetime(reloaded["date_key"])))

    sheets = _st4_sheets(batch, st4["zone_summary"], st4["district_summary"]) + [
        workbook.SheetSpec("Deliveries + Weather", reloaded[integrated_cols]),
        workbook.SheetSpec("Rain Summary", rain_summary),
        workbook.SheetSpec("Daily Weather", daily_summary),
        workbook.SheetSpec("Integration Checks", integrated.checks),
        workbook.SheetSpec("External Source", pd.DataFrame(
            [{"item": k, "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)}
             for k, v in {**acquisition.metadata, "source_mode": acquisition.source_mode,
                          "note": acquisition.note, "response_file": acquisition.response_file.name}.items()])),
    ]
    xlsx = workbook.write_workbook(out / "st5_delivery_weather.xlsx", sheets)
    checks = workbook.verify_workbook(xlsx, reloaded, rain_summary, "Deliveries + Weather", "Rain Summary")
    text = report.build_st5_report(ctx.run_id, acquisition, weather, integrated, rain_summary, checks)
    (out / "st5_weather_report.txt").write_text(text, encoding="utf-8")
    ctx.logger.info("Stage 7 - storage (ST5): integrated CSV, updated workbook (%d checks PASS) and report written",
                    len(checks))
    return {"rain_summary": rain_summary, "workbook_checks": checks}


def write_manifest(ctx, batch, st4, acquisition=None, integrated=None) -> None:
    manifest = {
        "run_id": ctx.run_id,
        "status": "SUCCESS",
        "started_at": ctx.started_at.isoformat(timespec="seconds"),
        "source_mode": ctx.source_mode,
        "input_files": [vars(f) for f in batch.files],
        "validation_rules": batch_mod.VALIDATION_RULES,
        "indicators": st4["indicators"],
        "excluded_rows": int(len(batch.excluded)),
        "outputs": sorted(p.name for p in ctx.staging_dir.iterdir()),
    }
    if acquisition is not None:
        manifest["external_source"] = {**acquisition.metadata, "response_file": acquisition.response_file.name,
                                       "note": acquisition.note}
        manifest["integration_checks"] = integrated.checks.astype(str).to_dict("records")
    (ctx.staging_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")


# ---------------------------------------------------------------- orchestration
def run_workflow(paths: ProjectPaths, source_mode: str = "auto", st4_only: bool = False) -> Path:
    ctx = runlog.start_run(paths.output_root, paths.logs_dir)
    ctx.logger.info("Paths: input=%s output=%s external=%s", paths.input_dir, paths.output_root, paths.external_dir)
    try:
        files, hashes = acquire_local_inputs(paths, ctx)
        batch = validate_local_batch(files, ctx)
        if st4_only:
            ctx.source_mode = "local-only"
        st4 = store_st4_outputs(batch, ctx)
        acquisition = integrated = None
        if not st4_only:
            acquisition = acquire_external_data(batch.valid, source_mode, paths, ctx)
            weather = validate_external_data(acquisition, batch.valid, ctx)
            integrated = integrate_sources(batch.valid, weather, ctx)
            store_st5_outputs(batch, st4, acquisition, weather, integrated, ctx)
        verify_raw_inputs_unchanged(files, hashes, ctx)
        write_manifest(ctx, batch, st4, acquisition, integrated)
        return runlog.publish_run(ctx)
    except PipelineError as error:
        runlog.fail_run(ctx, error)
        raise
    except Exception as error:  # unexpected bug: still never publish partial results
        runlog.fail_run(ctx, error)
        raise
