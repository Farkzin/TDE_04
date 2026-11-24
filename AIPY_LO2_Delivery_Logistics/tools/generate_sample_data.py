"""Generate the two weekly raw exports used by the project (run once; never overwrites raw files).

The records are a synthetic educational dataset for a small Curitiba delivery operation.
Export problems are inserted on purpose (missing customer, duplicate row, inconsistent text,
units inside numeric fields, comma decimals, zero/negative values) so that the ST3 cleaning
logic has real work to do. Delivery times depend on distance and vehicle only - weather is
NOT used to generate them, so any rain association found in ST5 is not built in.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
SEED = 20261005

DISTRICTS_KM = {
    "Centro": 2.0, "Batel": 3.0, "Rebouças": 3.5, "Água Verde": 4.5, "Bigorrilho": 5.0, "Juvevê": 4.8,
    "Cabral": 6.0, "Portão": 7.0, "Boa Vista": 9.0, "Cajuru": 10.0, "Xaxim": 11.0, "Boqueirão": 12.0,
    "Bairro Alto": 13.0, "Santa Felicidade": 14.0, "Pinheirinho": 15.5, "Cidade Industrial": 16.0,
    "Sítio Cercado": 18.0, "Campo Comprido": 17.0, "Umbará": 21.0, "Tatuquara": 23.0,
}
CUSTOMERS = [
    "Padaria Bom Dia", "Farmácia Vida", "Loja Tech Sul", "Mercado Central", "Ateliê Flor", "Livraria Leitura",
    "Pet Shop Amigo", "Ótica Visão", "Café do Bairro", "Studio Fit", "Clínica Sorriso", "Doce Sabor Confeitaria",
]
FIELDS = ["delivery_id", "request_date", "customer", "district", "distance_km", "package_weight_kg",
          "vehicle", "delivery_minutes"]


def vehicle_for(weight_kg: float) -> str:
    if weight_kg <= 5:
        return "Motorcycle"
    elif weight_kg <= 15:
        return "Car"
    return "Van"


def make_week(rng: random.Random, start: date, first_id: int) -> list[dict]:
    rows, next_id = [], first_id
    for offset in range(7):
        day = start + timedelta(days=offset)
        for _ in range(rng.randint(3, 4) if day.weekday() == 6 else rng.randint(5, 7)):
            district = rng.choice(list(DISTRICTS_KM))
            km = round(DISTRICTS_KM[district] * rng.uniform(0.85, 1.15), 1)
            weight = round(rng.choice([rng.uniform(0.3, 5), rng.uniform(0.3, 5), rng.uniform(5, 15),
                                       rng.uniform(15, 25)]), 2)
            vehicle = vehicle_for(weight)
            minutes = round(10 + km * 2.6 * rng.uniform(0.85, 1.25) + (8 if vehicle == "Van" else 0))
            rows.append({"delivery_id": f"DLV-{next_id:04d}", "request_date": day.isoformat(),
                         "customer": rng.choice(CUSTOMERS), "district": district, "distance_km": f"{km}",
                         "package_weight_kg": f"{weight}", "vehicle": vehicle, "delivery_minutes": f"{minutes}"})
            next_id += 1
    return rows


def add_export_problems(rows: list[dict], rng: random.Random, week: int) -> list[dict]:
    picks = rng.sample(range(len(rows)), 12)
    rows[picks[0]]["customer"] = ""
    rows[picks[1]]["customer"] = ""
    rows[picks[2]]["district"] = "  " + rows[picks[2]]["district"].lower() + " "
    rows[picks[3]]["district"] = rows[picks[3]]["district"].upper()
    rows[picks[4]]["vehicle"] = rows[picks[4]]["vehicle"].lower()
    rows[picks[5]]["vehicle"] = " " + rows[picks[5]]["vehicle"] + "  "
    rows[picks[6]]["package_weight_kg"] += " kg"
    rows[picks[7]]["package_weight_kg"] = rows[picks[7]]["package_weight_kg"].replace(".", ",")
    rows[picks[8]]["distance_km"] = rows[picks[8]]["distance_km"] + " km"
    if week == 1:
        rows[picks[9]]["distance_km"] = "0"
        rows[picks[10]]["package_weight_kg"] = "-1.5"
    else:
        rows[picks[9]]["delivery_minutes"] = "0"
        rows[picks[10]]["distance_km"] = "-3.2"
    rows.insert(picks[11] + 1, dict(rows[picks[11]]))  # exact duplicate exported twice
    return rows


def main() -> None:
    rng = random.Random(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    next_id = 1001
    for week, start in enumerate([date(2026, 10, 5), date(2026, 10, 12)], start=1):
        end = start + timedelta(days=6)
        path = RAW_DIR / f"deliveries_{start}_to_{end}.csv"
        rows = make_week(rng, start, next_id)
        next_id += len(rows)
        rows = add_export_problems(rows, rng, week)
        if path.exists():
            print(f"skip (raw files are never overwritten): {path.name}")
            continue
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"written {path.name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
