"""ST3 cleaning, validation and transformation logic, organised as reusable functions.

The steps follow the ST3 workflow (inspect -> clean -> transform) and keep the ST1 pricing
formula and the ST2 service-zone rule exactly as defined in LO1. ST4 calls these functions
once per input file; the adaptations are documented in docs/LO2_Report_ST4_ST5.md (section 4.1).
"""

import pandas as pd

from . import config


def inspect_dataset(df: pd.DataFrame) -> dict:
    """ST3 inspection: shape, missing values per column and exact duplicates."""
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_values": {c: int(v) for c, v in df.isna().sum().items() if v},
        "exact_duplicates": int(df.duplicated().sum()),
    }


def fill_missing_customer(df: pd.DataFrame) -> pd.DataFrame:
    """The customer name is not needed to price a delivery: keep the row, do not invent identity."""
    df = df.copy()
    df["customer"] = df["customer"].fillna("Unknown")
    return df


def standardize_text(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Strip spaces and apply title case so 'batel ' and 'Batel' form one category."""
    df = df.copy()
    for column in columns:
        df[column] = df[column].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    return df


def to_number(series: pd.Series, unit_suffix: str | None = None) -> pd.Series:
    """Convert exported text such as '2,5 kg' to float. Unparseable values become NaN (checked by V2)."""
    text = series.astype("string").str.strip()
    if unit_suffix:
        text = text.str.replace(unit_suffix, "", case=False, regex=False).str.strip()
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def convert_types(df: pd.DataFrame) -> pd.DataFrame:
    """Dates become datetime; distance, weight and minutes become numbers."""
    df = df.copy()
    df["request_date"] = pd.to_datetime(df["request_date"].astype("string").str.strip(),
                                        format="%Y-%m-%d", errors="coerce")
    df["distance_km"] = to_number(df["distance_km"], unit_suffix="km")
    df["package_weight_kg"] = to_number(df["package_weight_kg"], unit_suffix="kg")
    df["delivery_minutes"] = to_number(df["delivery_minutes"], unit_suffix="min")
    return df


def remove_exact_duplicates(df: pd.DataFrame, ignore_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The same delivery exported twice would double count revenue. Returns (kept, removed)."""
    compare = [c for c in df.columns if c not in ignore_columns]
    duplicated = df.duplicated(subset=compare, keep="first")
    return df[~duplicated].copy(), df[duplicated].copy()


def split_business_invalid(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Business rule (ST1 scope assumption made explicit): distance, weight and time must be > 0.

    Python accepts 0 or negative numbers, but they cannot describe a real delivery.
    Returns (valid, excluded) where excluded carries an exclusion_reason column.
    """
    reasons = pd.Series("", index=df.index, dtype="string")
    reasons = reasons.mask(df["distance_km"] <= 0, reasons + "distance_km <= 0; ")
    reasons = reasons.mask(df["package_weight_kg"] <= 0, reasons + "package_weight_kg <= 0; ")
    reasons = reasons.mask(df["delivery_minutes"] <= 0, reasons + "delivery_minutes <= 0; ")
    invalid = reasons != ""
    excluded = df[invalid].copy()
    excluded["exclusion_reason"] = reasons[invalid].str.rstrip("; ")
    return df[~invalid].copy(), excluded


# ---------------------------------------------------------------- ST1 + ST2 business logic
def classify_service_zone(distance_km: float) -> tuple[str, float]:
    """ST2 rule: exactly 5 km is Local, exactly 15 km is Standard, only > 15 km is Extended."""
    if distance_km <= config.LOCAL_MAX_KM:
        zone = "Local"
    elif distance_km <= config.STANDARD_MAX_KM:
        zone = "Standard"
    else:
        zone = "Extended"
    return zone, config.ZONE_FEES_BRL[zone]


def add_quotation_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ST1 formula + ST2 zone fee, stored as separate auditable columns."""
    df = df.copy()
    df["base_fee_brl"] = config.BASE_FEE_BRL
    df["distance_charge_brl"] = (df["distance_km"] * config.DISTANCE_RATE_BRL_PER_KM).round(2)
    df["weight_charge_brl"] = (df["package_weight_kg"] * config.WEIGHT_RATE_BRL_PER_KG).round(2)
    df["cost_before_zone_brl"] = (df["base_fee_brl"] + df["distance_charge_brl"] + df["weight_charge_brl"]).round(2)
    zones = [classify_service_zone(km) for km in df["distance_km"]]
    df["service_zone"] = [zone for zone, _ in zones]
    df["zone_fee_brl"] = [float(fee) for _, fee in zones]
    df["final_delivery_cost_brl"] = (df["cost_before_zone_brl"] + df["zone_fee_brl"]).round(2)
    return df


def add_derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Analytical variable: pace in minutes per km (comparable across short and long routes)."""
    df = df.copy()
    df["minutes_per_km"] = (df["delivery_minutes"] / df["distance_km"]).round(2)
    return df
