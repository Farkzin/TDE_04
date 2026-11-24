"""ST4/ST5 spreadsheet automation: formatted sheets written with openpyxl and verified by read-back."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .errors import VerificationError

LABELS = {
    "delivery_id": "Delivery ID", "request_date": "Request Date", "customer": "Customer",
    "district": "District", "vehicle": "Vehicle", "distance_km": "Distance (km)",
    "package_weight_kg": "Weight (kg)", "delivery_minutes": "Delivery Time (min)",
    "minutes_per_km": "Pace (min/km)", "service_zone": "Service Zone", "base_fee_brl": "Base Fee (BRL)",
    "distance_charge_brl": "Distance Charge (BRL)", "weight_charge_brl": "Weight Charge (BRL)",
    "cost_before_zone_brl": "Cost Before Zone (BRL)", "zone_fee_brl": "Zone Fee (BRL)",
    "final_delivery_cost_brl": "Final Delivery Cost (BRL)", "source_file": "Source File",
    "source_row": "Source CSV Line", "exclusion_reason": "Exclusion Reason",
    "deliveries": "Deliveries", "total_distance_km": "Total Distance (km)", "total_weight_kg": "Total Weight (kg)",
    "revenue_brl": "Revenue (BRL)", "average_cost_brl": "Average Cost (BRL)", "zone_fees_brl": "Zone Fees (BRL)",
    "average_delivery_minutes": "Avg Delivery Time (min)", "revenue_share": "Revenue Share",
    "average_distance_km": "Avg Distance (km)",
    # ST5
    "weather_date": "Weather Date", "precipitation_mm": "Precipitation (mm)", "rain_mm": "Rain (mm)",
    "temperature_max_c": "Max Temp (°C)", "temperature_min_c": "Min Temp (°C)",
    "wind_speed_max_kmh": "Max Wind (km/h)", "rain_category": "Rain Category",
    "weather_source": "Weather Source", "weather_response_file": "Weather Response File",
    "days": "Days", "deliveries_per_day": "Deliveries per Day", "average_minutes_per_km": "Avg Pace (min/km)",
    "revenue_per_day_brl": "Revenue per Day (BRL)",
    # checks
    "check": "Check", "expected": "Expected (processed CSV)", "observed": "Observed (workbook)", "result": "Result",
    "rule_id": "Rule", "description": "Description", "status": "Status", "item": "Item", "value": "Value",
}

FORMATS = [
    ("_brl", '"R$" #,##0.00'), ("revenue_share", "0.0%"), ("_pct", "0.0"), ("minutes_per_km", "0.00"),
    ("_km", "#,##0.0"), ("_kg", "#,##0.00"), ("_minutes", "#,##0.0"), ("_mm", "0.0"),
    ("_c", "0.0"), ("_kmh", "0.0"), ("deliveries_per_day", "0.0"), ("deliveries", "#,##0"),
    ("days", "#,##0"), ("source_row", "0"),
]
DATE_COLUMNS = {"request_date", "weather_date"}
HEADER_FILL = PatternFill("solid", fgColor="1F5FAD")


def number_format_for(column: str) -> str | None:
    if column in DATE_COLUMNS:
        return "yyyy-mm-dd"
    if column == "delivery_minutes":
        return "0"
    for suffix, fmt in FORMATS:
        if column.endswith(suffix) or column == suffix:
            return fmt
    return None


@dataclass
class SheetSpec:
    name: str
    data: pd.DataFrame


def _write_sheet(wb: Workbook, spec: SheetSpec) -> None:
    ws = wb.create_sheet(spec.name)
    columns = list(spec.data.columns)
    ws.append([LABELS.get(c, c) for c in columns])
    for record in spec.data.itertuples(index=False):
        row = []
        for value in record:
            if isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
            elif pd.api.types.is_scalar(value) and pd.isna(value):
                value = None
            elif hasattr(value, "item"):
                value = value.item()  # numpy scalar -> Python number, keeps cells numeric
            row.append(value)
        ws.append(row)

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for idx, column in enumerate(columns, start=1):
        letter = get_column_letter(idx)
        fmt = number_format_for(column)
        if fmt:
            for cell in ws[letter][1:]:
                cell.number_format = fmt
        values = [LABELS.get(column, column)] + [str(v) for v in spec.data[column].head(500)]
        longest = max(len(v) for v in values)
        ws.column_dimensions[letter].width = min(max(12, longest + 3), 55)


def write_workbook(path: Path, sheets: list[SheetSpec]) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    for spec in sheets:
        _write_sheet(wb, spec)
    wb.save(path)
    return path


def verify_workbook(path: Path, processed: pd.DataFrame, summary: pd.DataFrame,
                    detail_sheet: str, summary_sheet: str) -> pd.DataFrame:
    """Read the saved workbook back and compare it with the processed CSV data."""
    detail = pd.read_excel(path, sheet_name=detail_sheet)
    summ = pd.read_excel(path, sheet_name=summary_sheet)
    cost = LABELS["final_delivery_cost_brl"]
    checks = [
        ("Detail rows", len(processed), len(detail)),
        ("Detail total cost (BRL)", round(processed["final_delivery_cost_brl"].sum(), 2), round(detail[cost].sum(), 2)),
        ("Detail total distance (km)", round(processed["distance_km"].sum(), 1),
         round(detail[LABELS["distance_km"]].sum(), 1)),
        ("Summary deliveries", int(summary["deliveries"].sum()), int(summ[LABELS["deliveries"]].sum())),
        ("Summary revenue (BRL)", round(summary["revenue_brl"].sum(), 2), round(summ[LABELS["revenue_brl"]].sum(), 2)),
        ("Summary revenue = detail revenue", round(processed["final_delivery_cost_brl"].sum(), 2),
         round(summ[LABELS["revenue_brl"]].sum(), 2)),
        ("Cost column is numeric", "float64", str(detail[cost].dtype)),
    ]
    result = pd.DataFrame(checks, columns=["check", "expected", "observed"])
    result["result"] = ["PASS" if str(e) == str(o) else "FAIL" for e, o in zip(result["expected"], result["observed"])]
    if (result["result"] == "FAIL").any():
        raise VerificationError(f"Workbook {path.name} disagrees with processed data:\n{result.to_string(index=False)}")
    return result
