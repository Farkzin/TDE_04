"""ST5 acquisition: controlled GET to the Open-Meteo Historical Weather API, response storage,
JSON validation and conversion to a DataFrame."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from . import config
from .errors import ExternalDataError, ExternalSourceError

COLUMN_MAP = {
    "time": "weather_date",
    "precipitation_sum": "precipitation_mm",
    "rain_sum": "rain_mm",
    "temperature_2m_max": "temperature_max_c",
    "temperature_2m_min": "temperature_min_c",
    "wind_speed_10m_max": "wind_speed_max_kmh",
}


@dataclass
class Acquisition:
    payload: dict
    metadata: dict
    response_file: Path
    source_mode: str  # "live" or "cache"
    note: str


def build_weather_params(start: str, end: str) -> dict:
    return {
        "latitude": config.WEATHER_LOCATION["latitude"],
        "longitude": config.WEATHER_LOCATION["longitude"],
        "start_date": start,
        "end_date": end,
        "daily": ",".join(config.WEATHER_DAILY_FIELDS),
        "timezone": config.WEATHER_TIMEZONE,
    }


def fetch_daily_weather(params: dict) -> dict:
    """GET with timeout and explicit HTTP error handling. Never disables TLS verification."""
    try:
        response = requests.get(config.OPEN_METEO_ARCHIVE_URL, params=params, timeout=config.API_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ExternalSourceError(f"Open-Meteo did not answer within {config.API_TIMEOUT_SECONDS}s") from exc
    except requests.HTTPError as exc:
        detail = exc.response.text[:200] if exc.response is not None else ""
        raise ExternalSourceError(f"Open-Meteo returned HTTP {exc.response.status_code}: {detail}") from exc
    except requests.RequestException as exc:
        raise ExternalSourceError(f"Open-Meteo request failed: {type(exc).__name__}: {str(exc)[:200]}") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalDataError("Open-Meteo answered with a body that is not JSON") from exc


def _response_stem(params: dict, acquired_at: datetime) -> str:
    return f"{acquired_at:%Y%m%dT%H%M%S}_archive_curitiba_{params['start_date']}_{params['end_date']}"


def build_metadata(params: dict, acquired_at: datetime, method: str, payload: dict) -> dict:
    return {
        "provider": config.API_PROVIDER,
        "endpoint": config.OPEN_METEO_ARCHIVE_URL,
        "documentation": config.API_DOCUMENTATION_URL,
        "http_method": "GET",
        "parameters": params,
        "location": config.WEATHER_LOCATION["name"],
        "acquired_at": acquired_at.isoformat(timespec="seconds"),
        "acquisition_method": method,
        "units": payload.get("daily_units", {}),
        "use_conditions": config.API_TERMS,
    }


def save_response(payload: dict, params: dict, external_dir: Path, method: str) -> tuple[Path, dict]:
    """Store the raw JSON exactly as received plus a metadata sidecar. Earlier files are never overwritten."""
    external_dir.mkdir(parents=True, exist_ok=True)
    acquired_at = datetime.now().astimezone()
    stem = _response_stem(params, acquired_at)
    response_file = external_dir / f"{stem}_response.json"
    metadata = build_metadata(params, acquired_at, method, payload)
    response_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (external_dir / f"{stem}_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")
    return response_file, metadata


def load_cached_response(params: dict, external_dir: Path) -> tuple[dict, dict, Path]:
    """Most recent saved response whose request parameters match exactly."""
    for metadata_file in sorted(external_dir.glob("*_metadata.json"), reverse=True):
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if metadata.get("parameters") == params:
            response_file = metadata_file.with_name(metadata_file.name.replace("_metadata.json", "_response.json"))
            return json.loads(response_file.read_text(encoding="utf-8")), metadata, response_file
    raise ExternalSourceError(f"No cached Open-Meteo response in {external_dir} matches parameters {params}")


def acquire_weather(start: str, end: str, mode: str, external_dir: Path, logger) -> Acquisition:
    """mode: live (API only), cache (saved response only), auto (live, falling back to cache)."""
    params = build_weather_params(start, end)
    logger.info("Weather request: GET %s params=%s", config.OPEN_METEO_ARCHIVE_URL, params)
    if mode in ("live", "auto"):
        try:
            payload = fetch_daily_weather(params)
            response_file, metadata = save_response(payload, params, external_dir, "live GET from run_pipeline.py")
            logger.info("Live response saved to %s", response_file.name)
            return Acquisition(payload, metadata, response_file, "live", "live API response")
        except ExternalSourceError as exc:
            if mode == "live":
                raise
            logger.warning("Live request failed (%s); falling back to cached response", exc)
            fallback_note = f"cache fallback after live failure: {exc}"
    else:
        fallback_note = "cache requested by --source-mode cache"
    payload, metadata, response_file = load_cached_response(params, external_dir)
    logger.info("Using cached response %s (acquired %s)", response_file.name, metadata["acquired_at"])
    return Acquisition(payload, metadata, response_file, "cache", fallback_note)


def validate_weather_payload(payload: dict, required_dates: list[str]) -> None:
    """Structure, units, types, value ranges and date coverage. Raises ExternalDataError."""
    if not isinstance(payload, dict):
        raise ExternalDataError("Response root must be a JSON object")
    if payload.get("error"):
        raise ExternalDataError(f"API reported an error: {payload.get('reason')}")
    daily, units = payload.get("daily"), payload.get("daily_units")
    if not isinstance(daily, dict) or not isinstance(units, dict):
        raise ExternalDataError("Response must contain the dictionaries 'daily' and 'daily_units'")

    missing = [f for f in COLUMN_MAP if f not in daily]
    if missing:
        raise ExternalDataError(f"Missing daily fields: {missing}")
    lengths = {f: len(daily[f]) if isinstance(daily[f], list) else None for f in COLUMN_MAP}
    if None in lengths.values() or len(set(lengths.values())) != 1:
        raise ExternalDataError(f"Daily fields must be lists of equal length, got {lengths}")

    wrong_units = {f: units.get(f) for f, unit in config.WEATHER_EXPECTED_UNITS.items() if units.get(f) != unit}
    if wrong_units:
        raise ExternalDataError(f"Unexpected units {wrong_units}; expected {config.WEATHER_EXPECTED_UNITS}")

    for field in COLUMN_MAP:
        if field == "time":
            continue
        values = daily[field]
        if any(v is None for v in values):
            raise ExternalDataError(f"Field '{field}' has null values (data not yet available for some days)")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            raise ExternalDataError(f"Field '{field}' must contain only numbers")
    if any(v < 0 for v in daily["precipitation_sum"] + daily["rain_sum"]):
        raise ExternalDataError("Precipitation cannot be negative")

    dates = daily["time"]
    if len(set(dates)) != len(dates):
        raise ExternalDataError("Duplicate dates in the response: one row per day is required")
    not_covered = sorted(set(required_dates) - set(dates))
    if not_covered:
        raise ExternalDataError(f"Weather data does not cover delivery dates {not_covered}")


def classify_rain(precipitation_mm: float) -> str:
    """ST2-style rule: < 1 mm Dry; 1 to < 10 mm Light rain; >= 10 mm Heavy rain."""
    if precipitation_mm < config.DRY_MAX_MM:
        return "Dry"
    elif precipitation_mm < config.HEAVY_RAIN_MIN_MM:
        return "Light rain"
    else:
        return "Heavy rain"


def weather_payload_to_dataframe(payload: dict, response_file: Path) -> pd.DataFrame:
    """One row = one calendar day of weather in Curitiba."""
    weather = pd.DataFrame(payload["daily"])[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    weather["weather_date"] = pd.to_datetime(weather["weather_date"], format="%Y-%m-%d", errors="raise")
    numeric = [c for c in weather.columns if c != "weather_date"]
    weather[numeric] = weather[numeric].astype(float)
    weather["rain_category"] = weather["precipitation_mm"].apply(classify_rain)
    weather["weather_source"] = "Open-Meteo Historical Weather API"
    weather["weather_response_file"] = response_file.name
    return weather
