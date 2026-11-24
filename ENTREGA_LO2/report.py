"""ST4/ST5 short text reports for the operations coordinator. Every number comes from the same
validated DataFrames used for the CSVs and workbooks; evidence and interpretation are separated."""

from datetime import datetime

import pandas as pd

from . import config
from .batch import VALIDATION_RULES

LINE = "=" * 78


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}"


def _table(df: pd.DataFrame) -> str:
    return df.to_string(index=False)


def build_st4_report(run_id: str, batch, indicators: dict, zone_summary: pd.DataFrame,
                     workbook_checks: pd.DataFrame) -> str:
    valid = batch.valid
    start, end = valid["request_date"].min().date(), valid["request_date"].max().date()
    lines = [
        LINE, "DELIVERY BATCH REPORT (ST4) - Delivery and Logistics Management", LINE,
        f"Run ID ............ {run_id}",
        f"Generated at ...... {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Status ............ SUCCESS - rules {', '.join(batch.rules_passed)} passed before publication",
        "Source mode ....... local CSV exports from data/raw (no external data in ST4)",
        "Intended user ..... dispatch / operations coordinator (weekly closing of delivery quotations)",
        "",
        f"SOURCE FILES ({len(batch.files)})",
    ]
    for f in batch.files:
        lines.append(f"  - {f.source_file}  period {f.period_start}..{f.period_end}  raw={f.raw_rows}  "
                     f"duplicates removed={f.exact_duplicates_removed}  excluded={f.business_invalid_excluded}  "
                     f"valid={f.valid_rows}  sha256={f.sha256[:12]}...")
    lines += [
        "",
        "SCOPE",
        f"  {len(valid)} valid deliveries requested from {start} to {end}. Prices use the ST1 formula "
        f"(R$ {config.BASE_FEE_BRL:.2f} + R$ {config.DISTANCE_RATE_BRL_PER_KM:.2f}/km + "
        f"R$ {config.WEIGHT_RATE_BRL_PER_KG:.2f}/kg) plus the ST2 zone fee.",
        f"  {len(batch.excluded)} raw rows were not used: "
        f"{sum(f.exact_duplicates_removed for f in batch.files)} exact duplicates and "
        f"{sum(f.business_invalid_excluded for f in batch.files)} business-invalid rows "
        "(see excluded_records.csv for the reason of each one).",
        "",
        "VALIDATION RULES APPLIED",
        *[f"  {rid} PASS - {text}" for rid, text in VALIDATION_RULES.items()],
        "",
        "INDICATORS (calculated evidence)",
        f"  1. Valid deliveries ............... {indicators['valid_deliveries']}",
        f"  2. Total quoted revenue ........... {_brl(indicators['total_revenue_brl'])}",
        f"  3. Average delivery cost .......... {_brl(indicators['average_delivery_cost_brl'])}",
        f"  4. Largest delivery cost .......... {_brl(indicators['largest_delivery_cost_brl'])}",
        f"  5. Total distance ................. {indicators['total_distance_km']:,.1f} km",
        f"  6. Extended zone share ............ {indicators['extended_share_of_deliveries_pct']:.1f}% of deliveries, "
        f"{indicators['extended_share_of_revenue_pct']:.1f}% of revenue",
        "",
        "SUMMARY BY SERVICE ZONE (sorted by revenue, largest first)",
        _table(zone_summary[["service_zone", "deliveries", "total_distance_km", "revenue_brl", "average_cost_brl",
                             "revenue_share"]].assign(revenue_share=lambda d: (d["revenue_share"] * 100).round(1))
               .rename(columns={"revenue_share": "revenue_share_pct"})),
        "",
    ]

    top = zone_summary.iloc[0]
    by_zone = zone_summary.set_index("service_zone")
    cheapest = zone_summary.sort_values("average_cost_brl").iloc[0]
    share_del, share_rev = indicators["extended_share_of_deliveries_pct"], indicators["extended_share_of_revenue_pct"]
    lines += [
        "FINDING",
        f"  Evidence: the {top['service_zone']} zone generated {_brl(top['revenue_brl'])} "
        f"({top['revenue_share'] * 100:.1f}% of revenue) from {int(top['deliveries'])} deliveries. "
        f"Extended deliveries are {share_del:.1f}% of the volume but {share_rev:.1f}% of revenue; "
        f"their average cost is {_brl(by_zone.loc['Extended', 'average_cost_brl']) if 'Extended' in by_zone.index else 'n/a'} "
        f"versus {_brl(cheapest['average_cost_brl'])} in the {cheapest['service_zone']} zone.",
    ]
    if share_rev > share_del:
        lines.append("  Interpretation: long routes bring more revenue per delivery than their volume suggests, so "
                     "losing a few Extended customers would affect revenue more than losing the same number of "
                     "Local ones. Long-route capacity may deserve priority when the weekly schedule is planned.")
    else:
        lines.append("  Interpretation: revenue follows volume rather than distance, so the operation depends mainly "
                     "on the number of short and medium deliveries.")
    lines += [
        "",
        "LIMITATION",
        f"  Evidence: the batch covers {(end - start).days + 1} days and {len(batch.excluded)} raw rows were excluded; "
        "amounts are quoted prices from the team-defined ST1/ST2 policy.",
        "  Interpretation: the figures describe quoted revenue, not profit (fuel, driver and vehicle costs are not in "
        "the data), and two weeks are not enough to show seasonality.",
        "",
        "WORKBOOK VERIFICATION (read back from the saved .xlsx)",
        _table(workbook_checks),
        "",
        "OUTPUT FILES: deliveries_processed.csv, excluded_records.csv, st4_delivery_batch.xlsx, st4_batch_report.txt",
        LINE,
    ]
    return "\n".join(lines) + "\n"


def build_st5_report(run_id: str, acquisition, weather: pd.DataFrame, integration, rain_summary: pd.DataFrame,
                     workbook_checks: pd.DataFrame) -> str:
    meta = acquisition.metadata
    integrated = integration.integrated
    summary = rain_summary.set_index("rain_category")
    lines = [
        LINE, "DELIVERIES x WEATHER REPORT (ST5) - Delivery and Logistics Management", LINE,
        f"Run ID ............ {run_id}",
        f"Generated at ...... {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Source mode ....... {acquisition.source_mode.upper()} ({acquisition.note})",
        "",
        "BUSINESS QUESTION",
        "  Do rainy days in Curitiba coincide with a slower delivery pace (min/km) or with a different demand?",
        "  The local CSVs contain dates, distances and times but no weather, so they cannot answer it alone.",
        "",
        "EXTERNAL INFORMATION",
        f"  Provider ......... {meta['provider']}",
        f"  Endpoint ......... GET {meta['endpoint']}",
        f"  Parameters ....... {meta['parameters']}",
        f"  Acquired at ...... {meta['acquired_at']} ({meta['acquisition_method']})",
        f"  Response file .... data/external/open_meteo/{acquisition.response_file.name}",
        f"  Units ............ {meta['units']}",
        f"  Use conditions ... {meta['use_conditions']}",
        f"  Coverage ......... {weather['weather_date'].min().date()} to {weather['weather_date'].max().date()} "
        f"({len(weather)} days, one row per day). Rain category: < {config.DRY_MAX_MM:g} mm Dry, "
        f"{config.DRY_MAX_MM:g} to < {config.HEAVY_RAIN_MIN_MM:g} mm Light rain, >= {config.HEAVY_RAIN_MIN_MM:g} mm Heavy rain.",
        "",
        "INTEGRATION",
        "  One delivery row (local) is joined to one day row (weather) on date_key = request_date as YYYY-MM-DD.",
        "  Relationship many-to-one, left join, validated by pandas (validate='many_to_one').",
        _table(integration.checks),
        "",
        "INDICATORS BY RAIN CATEGORY (calculated evidence, sorted by pace - slowest first)",
        _table(rain_summary[["rain_category", "days", "deliveries", "deliveries_per_day", "revenue_per_day_brl",
                             "average_minutes_per_km", "precipitation_mm"]]),
        "",
    ]
    dry = summary.loc["Dry"] if "Dry" in summary.index else None
    wet = integrated[integrated["rain_category"] != "Dry"]
    wet_pace = wet["delivery_minutes"].sum() / wet["distance_km"].sum() if len(wet) else float("nan")
    dry_rows = integrated[integrated["rain_category"] == "Dry"]
    dry_pace = dry_rows["delivery_minutes"].sum() / dry_rows["distance_km"].sum() if len(dry_rows) else float("nan")
    diff_pct = 100 * (wet_pace - dry_pace) / dry_pace if dry is not None else float("nan")
    wet_days = integrated.loc[integrated["rain_category"] != "Dry", "date_key"].nunique()
    lines += [
        "FINDING",
        f"  Evidence: on rainy days (Light + Heavy, {wet_days} days, {len(wet)} deliveries) the pace was "
        f"{wet_pace:.2f} min/km against {dry_pace:.2f} min/km on dry days "
        f"({0 if dry is None else int(dry['days'])} days, {len(dry_rows)} deliveries): a difference of {diff_pct:+.1f}%.",
    ]
    if abs(diff_pct) < 5:
        lines.append("  Interpretation: in this period rain did not change the delivery pace in a meaningful way "
                     "(< 5%), so the current delivery-time promise does not need a rain buffer based on this evidence.")
    elif diff_pct > 0:
        lines.append(f"  Interpretation: deliveries were slower on rainy days; adding a buffer of about "
                     f"{diff_pct:.0f}% to promised times on rainy days could reduce late arrivals.")
    else:
        lines.append("  Interpretation: the evidence does not support adding a rain buffer to promised delivery times. "
                     "The faster pace on rainy days should not be read as 'rain speeds deliveries up': with few dry "
                     "days, a different route mix (long routes have a lower min/km) could explain the gap - this was "
                     "not tested.")
    lines += [
        "",
        "LIMITATION",
        f"  Evidence: only {integrated['date_key'].nunique()} days and {wet_days} rainy days; the weather value is a "
        "daily total for one coordinate in Curitiba.",
        "  Interpretation: rain may have fallen outside delivery hours or in other districts, and a two-week sample "
        "cannot separate the effect of rain from the effect of the weekday or route mix (association, not cause).",
        "",
        "WORKBOOK VERIFICATION (st5_delivery_weather.xlsx read back)",
        _table(workbook_checks),
        "",
        "OUTPUT FILES: weather_daily.csv, deliveries_with_weather.csv, st5_delivery_weather.xlsx, st5_weather_report.txt",
        "Weather data by Open-Meteo.com (CC BY 4.0).",
        LINE,
    ]
    return "\n".join(lines) + "\n"
