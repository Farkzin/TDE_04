"""ST5 integration: join validated deliveries (one row = one delivery) with daily weather
(one row = one day in Curitiba) on a normalised calendar-date key, with full reconciliation."""

from dataclasses import dataclass

import pandas as pd

from .errors import IntegrationError

RAIN_ORDER = ["Dry", "Light rain", "Heavy rain"]


@dataclass
class IntegrationResult:
    integrated: pd.DataFrame
    checks: pd.DataFrame


def add_date_key(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Normalise both sources to the same text key YYYY-MM-DD (local calendar day, America/Sao_Paulo)."""
    df = df.copy()
    df["date_key"] = pd.to_datetime(df[date_column]).dt.normalize().dt.strftime("%Y-%m-%d")
    return df


def integrate_deliveries_with_weather(deliveries: pd.DataFrame, weather: pd.DataFrame) -> IntegrationResult:
    left = add_date_key(deliveries, "request_date")
    right = add_date_key(weather, "weather_date")

    checks = []

    def record(name, expected, observed):
        ok = expected == observed
        checks.append({"check": name, "expected": expected, "observed": observed, "result": "PASS" if ok else "FAIL"})
        return ok

    if not record("Weather key unique (one row per day)", 0, int(right["date_key"].duplicated().sum())):
        raise IntegrationError("Weather data has more than one row for the same day")
    try:
        merged = left.merge(right, on="date_key", how="left", validate="many_to_one", indicator=True)
    except pd.errors.MergeError as exc:
        raise IntegrationError(f"Relationship is not many-to-one: {exc}") from exc

    unmatched = merged.loc[merged["_merge"] != "both", "delivery_id"].tolist()
    record("Deliveries without weather match", 0, len(unmatched))
    record("Row count preserved (deliveries in = rows out)", len(deliveries), len(merged))
    record("Total revenue preserved (BRL)", round(float(deliveries["final_delivery_cost_brl"].sum()), 2),
           round(float(merged["final_delivery_cost_brl"].sum()), 2))
    record("Total distance preserved (km)", round(float(deliveries["distance_km"].sum()), 1),
           round(float(merged["distance_km"].sum()), 1))
    record("delivery_id still unique", 0, int(merged["delivery_id"].duplicated().sum()))
    days_with_deliveries = left["date_key"].nunique()
    record("Delivery days covered by weather", days_with_deliveries,
           int(left["date_key"].isin(right["date_key"]).groupby(left["date_key"]).any().sum()))

    checks_df = pd.DataFrame(checks, dtype=object)
    if (checks_df["result"] == "FAIL").any():
        raise IntegrationError(f"Integration checks failed (unmatched: {unmatched}):\n{checks_df.to_string(index=False)}")
    return IntegrationResult(integrated=merged.drop(columns="_merge"), checks=checks_df)


def summarize_by_rain(integrated: pd.DataFrame) -> pd.DataFrame:
    """Compare operational pace and demand on dry vs rainy days (sorted by pace, slowest first)."""
    summary = (
        integrated.groupby("rain_category")
        .agg(
            days=("date_key", "nunique"),
            deliveries=("delivery_id", "count"),
            revenue_brl=("final_delivery_cost_brl", "sum"),
            total_distance_km=("distance_km", "sum"),
            total_minutes=("delivery_minutes", "sum"),
            average_cost_brl=("final_delivery_cost_brl", "mean"),
            precipitation_mm=("precipitation_mm", "mean"),
        )
        .reindex([c for c in RAIN_ORDER if c in set(integrated["rain_category"])])
        .reset_index()
    )
    summary["average_minutes_per_km"] = (summary["total_minutes"] / summary["total_distance_km"]).round(2)
    summary["deliveries_per_day"] = (summary["deliveries"] / summary["days"]).round(1)
    summary["revenue_per_day_brl"] = (summary["revenue_brl"] / summary["days"]).round(2)
    summary = summary.drop(columns="total_minutes").sort_values("average_minutes_per_km", ascending=False,
                                                               ignore_index=True)
    return summary.round({"revenue_brl": 2, "total_distance_km": 1, "average_cost_brl": 2, "precipitation_mm": 1})


def summarize_by_day(integrated: pd.DataFrame) -> pd.DataFrame:
    daily = (
        integrated.groupby(["weather_date", "rain_category", "precipitation_mm"])
        .agg(deliveries=("delivery_id", "count"), revenue_brl=("final_delivery_cost_brl", "sum"),
             total_distance_km=("distance_km", "sum"), total_minutes=("delivery_minutes", "sum"))
        .reset_index()
    )
    daily["average_minutes_per_km"] = (daily["total_minutes"] / daily["total_distance_km"]).round(2)
    return daily.drop(columns="total_minutes").round({"revenue_brl": 2, "total_distance_km": 1})
