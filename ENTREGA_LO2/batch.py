"""ST4 batch processing: discover the weekly exports, apply ST3 cleaning per file, and enforce
the publication rules V1-V6. Any rejected file stops the whole batch (BatchRejectedError)."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config, st3_cleaning
from .errors import BatchRejectedError, InputMissingError

SOURCE_COLUMNS = ["source_file", "source_row"]

VALIDATION_RULES = {
    "V1": "Schema: every file has exactly the required columns (compatible structure for one batch).",
    "V2": "Types: distance, weight and minutes are present and numeric after ST3 text cleaning.",
    "V3": "Period: every request_date is a valid date inside the period stated in the file name.",
    "V4": "Key: delivery_id is filled and unique across the whole batch after exact duplicates are removed.",
    "V5": f"Quality: business-invalid rows (<= 0 values) are at most {config.MAX_EXCLUSION_RATE:.0%} of a file.",
    "V6": "Consistency: final cost = base + distance + weight + zone fee and zones match the ST2 thresholds.",
}


@dataclass
class FileReport:
    source_file: str
    sha256: str
    period_start: str
    period_end: str
    raw_rows: int
    missing_customer_filled: int
    exact_duplicates_removed: int
    business_invalid_excluded: int
    valid_rows: int


@dataclass
class BatchResult:
    valid: pd.DataFrame
    excluded: pd.DataFrame
    files: list[FileReport]
    rules_passed: list[str] = field(default_factory=list)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_input_files(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        raise InputMissingError(f"Input folder not found: {input_dir}")
    files = sorted(input_dir.glob(config.INPUT_FILE_PATTERN))
    if len(files) < config.MIN_INPUT_FILES:
        raise InputMissingError(
            f"Expected at least {config.MIN_INPUT_FILES} files matching '{config.INPUT_FILE_PATTERN}' "
            f"in {input_dir}, found {len(files)}: {[f.name for f in files]}")
    return files


def parse_period(path: Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    match = re.match(config.INPUT_FILENAME_REGEX, path.name)
    if not match:
        raise BatchRejectedError("V3", path.name, "file name must follow deliveries_YYYY-MM-DD_to_YYYY-MM-DD.csv")
    start, end = pd.Timestamp(match.group(1)), pd.Timestamp(match.group(2))
    if end < start:
        raise BatchRejectedError("V3", path.name, "period end is before period start")
    return start, end


def load_raw_file(path: Path) -> pd.DataFrame:
    """Read as text (ST3 converts types explicitly) and record where every row came from."""
    try:
        raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise BatchRejectedError("V1", path.name, f"file cannot be read as a UTF-8 CSV ({exc})") from exc
    if raw.empty:
        raise BatchRejectedError("V1", path.name, "file has a header but no records")
    raw["source_file"] = path.name
    raw["source_row"] = range(2, len(raw) + 2)  # line number in the CSV (line 1 = header)
    return raw


def validate_schema(raw: pd.DataFrame, path: Path) -> None:
    columns = [c for c in raw.columns if c not in SOURCE_COLUMNS]
    missing = [c for c in config.REQUIRED_COLUMNS if c not in columns]
    unexpected = [c for c in columns if c not in config.REQUIRED_COLUMNS]
    if missing or unexpected:
        raise BatchRejectedError("V1", path.name, f"incompatible columns - missing {missing}, unexpected {unexpected}")


def validate_numeric_fields(converted: pd.DataFrame, path: Path) -> None:
    problems = []
    for column in config.NUMERIC_COLUMNS:
        bad_rows = converted.loc[converted[column].isna(), "source_row"].tolist()
        if bad_rows:
            problems.append(f"{column} empty or not numeric at CSV lines {bad_rows}")
    if problems:
        raise BatchRejectedError("V2", path.name, "; ".join(problems))


def validate_period(converted: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, path: Path) -> None:
    invalid = converted["request_date"].isna()
    outside = ~invalid & ~converted["request_date"].between(start, end)
    if invalid.any() or outside.any():
        raise BatchRejectedError(
            "V3", path.name,
            f"invalid dates at lines {converted.loc[invalid, 'source_row'].tolist()}, "
            f"dates outside {start.date()}..{end.date()} at lines {converted.loc[outside, 'source_row'].tolist()}")


def validate_exclusion_rate(excluded: int, rows: int, path: Path) -> None:
    rate = excluded / rows
    if rate > config.MAX_EXCLUSION_RATE:
        raise BatchRejectedError(
            "V5", path.name,
            f"{excluded} of {rows} rows ({rate:.1%}) violate the > 0 business rule; "
            f"limit is {config.MAX_EXCLUSION_RATE:.0%} - the export looks broken")


def validate_unique_ids(batch: pd.DataFrame) -> None:
    empty = batch["delivery_id"].isna() | (batch["delivery_id"].astype("string").str.strip() == "")
    if empty.any():
        rows = batch.loc[empty, ["source_file", "source_row"]].to_dict("records")
        raise BatchRejectedError("V4", "batch", f"delivery_id is empty at {rows}")
    dup = batch["delivery_id"].duplicated(keep=False)
    if dup.any():
        rows = batch.loc[dup, ["delivery_id", "source_file", "source_row"]].to_dict("records")
        raise BatchRejectedError("V4", "batch", f"conflicting records share the same delivery_id: {rows}")


def validate_calculations(batch: pd.DataFrame) -> None:
    recomputed = (batch["base_fee_brl"] + batch["distance_charge_brl"]
                  + batch["weight_charge_brl"] + batch["zone_fee_brl"]).round(2)
    wrong_total = (recomputed - batch["final_delivery_cost_brl"]).abs() > 0.005
    expected_zone = [st3_cleaning.classify_service_zone(km)[0] for km in batch["distance_km"]]
    wrong_zone = batch["service_zone"] != pd.Series(expected_zone, index=batch.index)
    if wrong_total.any() or wrong_zone.any():
        raise BatchRejectedError("V6", "batch", f"{int(wrong_total.sum())} cost and {int(wrong_zone.sum())} zone mismatches")


def process_file(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, FileReport]:
    """ST3 pipeline for one file + file-level rules V1, V2, V3 and V5."""
    start, end = parse_period(path)
    raw = load_raw_file(path)
    validate_schema(raw, path)

    missing_customer = int(raw["customer"].isna().sum())
    df = st3_cleaning.fill_missing_customer(raw)
    df["customer"] = df["customer"].astype("string").str.strip()
    df = st3_cleaning.standardize_text(df, config.TEXT_COLUMNS_TO_STANDARDIZE)
    df["delivery_id"] = df["delivery_id"].astype("string").str.strip().str.upper()
    df = st3_cleaning.convert_types(df)
    validate_numeric_fields(df, path)
    validate_period(df, start, end, path)

    df, duplicates = st3_cleaning.remove_exact_duplicates(df, ignore_columns=SOURCE_COLUMNS)
    df, excluded = st3_cleaning.split_business_invalid(df)
    validate_exclusion_rate(len(excluded), len(raw), path)

    df = st3_cleaning.add_quotation_columns(df)
    df = st3_cleaning.add_derived_variables(df)
    report = FileReport(
        source_file=path.name, sha256=file_sha256(path),
        period_start=str(start.date()), period_end=str(end.date()),
        raw_rows=len(raw), missing_customer_filled=missing_customer,
        exact_duplicates_removed=len(duplicates), business_invalid_excluded=len(excluded),
        valid_rows=len(df))
    duplicates = duplicates.assign(exclusion_reason="exact duplicate of an earlier row")
    return df, pd.concat([excluded, duplicates]), report


def run_batch(files: list[Path], logger) -> BatchResult:
    valid_parts, excluded_parts, reports = [], [], []
    for path in files:
        logger.info("Processing %s", path.name)
        valid, excluded, report = process_file(path)
        logger.info("  %s: raw=%d, duplicates removed=%d, excluded=%d, valid=%d", path.name, report.raw_rows,
                    report.exact_duplicates_removed, report.business_invalid_excluded, report.valid_rows)
        valid_parts.append(valid)
        excluded_parts.append(excluded)
        reports.append(report)

    batch = pd.concat(valid_parts, ignore_index=True)
    validate_unique_ids(batch)
    validate_calculations(batch)
    batch = batch.sort_values(["request_date", "delivery_id"], ignore_index=True)
    excluded = pd.concat(excluded_parts, ignore_index=True)
    logger.info("Rules V1-V6 passed for %d files (%d valid rows)", len(files), len(batch))
    return BatchResult(valid=batch, excluded=excluded, files=reports, rules_passed=list(VALIDATION_RULES))


PROCESSED_COLUMN_ORDER = [
    "delivery_id", "request_date", "customer", "district", "vehicle",
    "distance_km", "package_weight_kg", "delivery_minutes", "minutes_per_km",
    "service_zone", "base_fee_brl", "distance_charge_brl", "weight_charge_brl",
    "cost_before_zone_brl", "zone_fee_brl", "final_delivery_cost_brl",
    "source_file", "source_row",
]
