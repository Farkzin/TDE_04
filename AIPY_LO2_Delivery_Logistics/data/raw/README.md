# data/raw – original weekly exports (never edited)

Files: `deliveries_<period start>_to_<period end>.csv` – one file per week exported by the dispatch system.
The two files have the same column structure. **One row = one delivery request** priced with the
ST1/ST2 quotation policy.

| Column | Type after cleaning | Business meaning |
|---|---|---|
| `delivery_id` | text (key) | Unique delivery reference (`DLV-0000`) |
| `request_date` | date | Day the delivery was requested and dispatched (local time, Curitiba) |
| `customer` | text | Business customer; may be empty in the export (filled with `Unknown`) |
| `district` | category | Destination district in Curitiba |
| `distance_km` | float (km) | Route distance from the depot – drives the ST1 distance charge and the ST2 zone |
| `package_weight_kg` | float (kg) | Package weight – drives the ST1 weight charge |
| `vehicle` | category | Motorcycle (≤ 5 kg), Car (≤ 15 kg) or Van |
| `delivery_minutes` | integer (min) | Time from dispatch to delivery |

Known export problems (handled by the ST3 cleaning functions, see docs section 4.1): missing customer,
one exact duplicate row per file, extra spaces / wrong capitalisation in `district` and `vehicle`,
units typed inside numbers (`4.1 kg`, `3.9 km`), comma decimals (`10,91`) and a few zero/negative values.

Origin: synthetic educational dataset created once by `tools/generate_sample_data.py` (fixed seed).
Delivery times depend only on distance and vehicle; weather was not used to create them.
