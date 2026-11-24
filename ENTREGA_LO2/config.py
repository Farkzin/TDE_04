"""Central configuration: paths, ST1/ST2 business rules, ST4 batch rules and ST5 API settings."""

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProjectPaths:
    input_dir: Path
    output_root: Path
    external_dir: Path
    logs_dir: Path

    @classmethod
    def default(cls) -> "ProjectPaths":
        return cls(
            input_dir=PROJECT_ROOT / "data" / "raw",
            output_root=PROJECT_ROOT / "outputs",
            external_dir=PROJECT_ROOT / "data" / "external" / "open_meteo",
            logs_dir=PROJECT_ROOT / "logs",
        )


# ---------------------------------------------------------------- ST1 pricing policy (unchanged)
BASE_FEE_BRL = 8.00
DISTANCE_RATE_BRL_PER_KM = 1.50
WEIGHT_RATE_BRL_PER_KG = 2.00

# ---------------------------------------------------------------- ST2 service zones (unchanged)
LOCAL_MAX_KM = 5.0
STANDARD_MAX_KM = 15.0
ZONE_FEES_BRL = {"Local": 0.00, "Standard": 5.00, "Extended": 12.00}

# ---------------------------------------------------------------- ST3/ST4 input contract
INPUT_FILE_PATTERN = "deliveries_*.csv"
INPUT_FILENAME_REGEX = r"^deliveries_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv$"
MIN_INPUT_FILES = 2

REQUIRED_COLUMNS = [
    "delivery_id",
    "request_date",
    "customer",
    "district",
    "distance_km",
    "package_weight_kg",
    "vehicle",
    "delivery_minutes",
]
TEXT_COLUMNS_TO_STANDARDIZE = ["district", "vehicle"]  # grouping categories; customer names are only stripped
NUMERIC_COLUMNS = ["distance_km", "package_weight_kg", "delivery_minutes"]

# A file whose business-invalid rows exceed this share is treated as a broken export.
MAX_EXCLUSION_RATE = 0.10

# ---------------------------------------------------------------- ST5 external source
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_LOCATION = {"name": "Curitiba-PR (Brasil)", "latitude": -25.4284, "longitude": -49.2733}
WEATHER_TIMEZONE = "America/Sao_Paulo"
WEATHER_DAILY_FIELDS = [
    "precipitation_sum",
    "rain_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
]
WEATHER_EXPECTED_UNITS = {
    "time": "iso8601",
    "precipitation_sum": "mm",
    "rain_sum": "mm",
    "temperature_2m_max": "°C",
    "temperature_2m_min": "°C",
    "wind_speed_10m_max": "km/h",
}
API_TIMEOUT_SECONDS = (5, 20)  # (connect, read)

# Rain categories (WMO convention: a "wet day" has at least 1 mm of precipitation).
DRY_MAX_MM = 1.0
HEAVY_RAIN_MIN_MM = 10.0

API_PROVIDER = "Open-Meteo (Historical Weather API, ERA5-based reanalysis)"
API_DOCUMENTATION_URL = "https://open-meteo.com/en/docs/historical-weather-api"
API_TERMS = (
    "Free API for non-commercial use (educational use qualifies); < 10,000 calls/day; "
    "data licensed under CC BY 4.0 - attribution: 'Weather data by Open-Meteo.com'. "
    "No warranty of accuracy or availability (https://open-meteo.com/en/terms)."
)
