"""Automated checks for ST4/ST5. Run from the project folder:

    python -m unittest discover -s tests -v

Every test works on a temporary copy of the inputs, so the real data/ and outputs/ are untouched.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from delivery_pipeline import api_client, st3_analysis, st3_cleaning  # noqa: E402
from delivery_pipeline.config import ProjectPaths  # noqa: E402
from delivery_pipeline.errors import (BatchRejectedError, ExternalDataError, InputMissingError,  # noqa: E402
                                      IntegrationError)
from delivery_pipeline.integration import integrate_deliveries_with_weather  # noqa: E402
from delivery_pipeline.workflow import run_workflow  # noqa: E402

RAW_FILES = sorted((PROJECT / "data" / "raw").glob("deliveries_*.csv"))


class WorkspaceTestCase(unittest.TestCase):
    """Temporary copy of data/raw and the cached API response."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.paths = ProjectPaths(self.tmp / "raw", self.tmp / "outputs", self.tmp / "external", self.tmp / "logs")
        self.paths.input_dir.mkdir()
        for f in RAW_FILES:
            shutil.copy2(f, self.paths.input_dir / f.name)
        shutil.copytree(PROJECT / "data" / "external" / "open_meteo", self.paths.external_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ok(self):
        return run_workflow(self.paths, source_mode="cache")

    def history(self):
        return pd.read_csv(self.paths.output_root / "run_history.csv")

    def rewrite_raw(self, name, transform):
        path = self.paths.input_dir / name
        df = pd.read_csv(path, dtype=str)
        transform(df).to_csv(path, index=False)


class St1St2RulesTest(unittest.TestCase):
    def test_st1_example_from_lo1_report(self):
        df = pd.DataFrame({"distance_km": [10.0], "package_weight_kg": [2.0]})
        row = st3_cleaning.add_quotation_columns(df).iloc[0]
        self.assertEqual(row["cost_before_zone_brl"], 27.00)  # LO1 section 1.3 example

    def test_st2_boundaries_match_lo1_tests(self):
        expected = {1.0: "Local", 5.0: "Local", 5.1: "Standard", 10.0: "Standard", 15.0: "Standard", 15.1: "Extended"}
        for km, zone in expected.items():
            self.assertEqual(st3_cleaning.classify_service_zone(km)[0], zone, km)

    def test_lo1_final_costs(self):
        df = pd.DataFrame({"distance_km": [1.0, 5.0, 5.1, 10.0, 15.0, 15.1], "package_weight_kg": [2.0] * 6})
        costs = st3_cleaning.add_quotation_columns(df)["final_delivery_cost_brl"].tolist()
        self.assertEqual(costs, [13.50, 19.50, 24.65, 32.00, 39.50, 46.65])  # LO1 tests T1-T6


class SuccessfulRunTest(WorkspaceTestCase):
    def test_outputs_agree_and_are_published(self):
        run_dir = self.run_ok()
        self.assertEqual(run_dir.parent.name, "runs")
        processed = pd.read_csv(run_dir / "deliveries_processed.csv")
        integrated = pd.read_csv(run_dir / "deliveries_with_weather.csv")
        detail = pd.read_excel(run_dir / "st4_delivery_batch.xlsx", sheet_name="Deliveries")
        summary = pd.read_excel(run_dir / "st4_delivery_batch.xlsx", sheet_name="Zone Summary")
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))

        revenue = round(processed["final_delivery_cost_brl"].sum(), 2)
        self.assertEqual(len(processed), len(detail))
        self.assertEqual(revenue, round(detail["Final Delivery Cost (BRL)"].sum(), 2))
        self.assertEqual(revenue, round(summary["Revenue (BRL)"].sum(), 2))
        self.assertEqual(revenue, manifest["indicators"]["total_revenue_brl"])
        self.assertEqual(revenue, round(integrated["final_delivery_cost_brl"].sum(), 2))
        self.assertEqual(len(processed), len(integrated))
        self.assertIn(f"R$ {revenue:,.2f}", (run_dir / "st4_batch_report.txt").read_text(encoding="utf-8"))
        self.assertEqual(summary["Revenue (BRL)"].tolist(), sorted(summary["Revenue (BRL)"], reverse=True))
        self.assertEqual(set(processed["source_file"]), {f.name for f in RAW_FILES})
        self.assertEqual(manifest["source_mode"], "cache")

    def test_reuses_st3_indicators(self):
        run_dir = self.run_ok()
        processed = pd.read_csv(run_dir / "deliveries_processed.csv")
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(st3_analysis.calculate_indicators(processed), manifest["indicators"])

    def test_raw_inputs_are_not_modified(self):
        before = {f.name: f.read_bytes() for f in self.paths.input_dir.iterdir()}
        self.run_ok()
        after = {f.name: f.read_bytes() for f in self.paths.input_dir.iterdir()}
        self.assertEqual(before, after)

    def test_workbook_presentation(self):
        from openpyxl import load_workbook
        wb = load_workbook(self.run_ok() / "st4_delivery_batch.xlsx")
        for name in ("Deliveries", "Zone Summary"):
            ws = wb[name]
            self.assertEqual(ws.freeze_panes, "A2")
            self.assertIsNotNone(ws.auto_filter.ref)
            self.assertTrue(ws["A1"].font.bold)
        cost_col = [c.value for c in wb["Deliveries"][1]].index("Final Delivery Cost (BRL)") + 1
        cell = wb["Deliveries"].cell(row=2, column=cost_col)
        self.assertIsInstance(cell.value, float)
        self.assertIn("R$", cell.number_format)


class RejectionTest(WorkspaceTestCase):
    def assert_rejected(self, rule_id, filename, transform):
        first = self.run_ok()  # an earlier success that must survive
        self.rewrite_raw(filename, transform)
        latest_before = (self.paths.output_root / "LATEST_SUCCESSFUL_RUN.txt").read_text()
        with self.assertRaises(BatchRejectedError) as ctx:
            run_workflow(self.paths, source_mode="cache")
        self.assertEqual(ctx.exception.rule_id, rule_id)
        runs = list((self.paths.output_root / "runs").iterdir())
        self.assertEqual(runs, [first])  # nothing new published
        self.assertTrue(first.joinpath("deliveries_processed.csv").exists())
        self.assertEqual(latest_before, (self.paths.output_root / "LATEST_SUCCESSFUL_RUN.txt").read_text())
        self.assertEqual(len(list((self.paths.output_root / "_failed").iterdir())), 1)
        self.assertEqual(self.history()["status"].tolist(), ["SUCCESS", "FAILED"])
        self.assertFalse(any((self.paths.output_root / "_incomplete").iterdir()))

    def test_v1_missing_column(self):
        self.assert_rejected("V1", RAW_FILES[1].name, lambda d: d.drop(columns="package_weight_kg"))

    def test_v2_non_numeric_distance(self):
        def corrupt(d):
            d.loc[3, "distance_km"] = "approx. ten"
            return d
        self.assert_rejected("V2", RAW_FILES[0].name, corrupt)

    def test_v3_date_outside_file_period(self):
        def corrupt(d):
            d.loc[0, "request_date"] = "2026-11-01"
            return d
        self.assert_rejected("V3", RAW_FILES[0].name, corrupt)

    def test_v4_conflicting_delivery_id(self):
        def corrupt(d):
            d.loc[1, "delivery_id"] = d.loc[0, "delivery_id"]
            return d
        self.assert_rejected("V4", RAW_FILES[0].name, corrupt)

    def test_v5_too_many_invalid_rows(self):
        def corrupt(d):
            d.loc[0:9, "package_weight_kg"] = "0"
            return d
        self.assert_rejected("V5", RAW_FILES[1].name, corrupt)

    def test_missing_input_file(self):
        (self.paths.input_dir / RAW_FILES[1].name).unlink()
        with self.assertRaises(InputMissingError):
            run_workflow(self.paths, source_mode="cache")
        self.assertFalse((self.paths.output_root / "runs").exists())
        self.assertEqual(self.history()["status"].tolist(), ["FAILED"])


class ExternalDataTest(unittest.TestCase):
    def setUp(self):
        response = sorted((PROJECT / "data" / "external" / "open_meteo").glob("*_response.json"))[-1]
        self.payload = json.loads(response.read_text(encoding="utf-8"))
        self.dates = self.payload["daily"]["time"]

    def test_valid_payload_passes_and_maps_columns(self):
        api_client.validate_weather_payload(self.payload, self.dates)
        df = api_client.weather_payload_to_dataframe(self.payload, Path("x.json"))
        self.assertEqual(len(df), 14)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["weather_date"]))
        self.assertEqual(df["precipitation_mm"].dtype, float)

    def test_missing_field_is_rejected(self):
        del self.payload["daily"]["rain_sum"]
        with self.assertRaises(ExternalDataError):
            api_client.validate_weather_payload(self.payload, self.dates)

    def test_wrong_unit_is_rejected(self):
        self.payload["daily_units"]["precipitation_sum"] = "inch"
        with self.assertRaises(ExternalDataError):
            api_client.validate_weather_payload(self.payload, self.dates)

    def test_null_value_is_rejected(self):
        self.payload["daily"]["precipitation_sum"][3] = None
        with self.assertRaises(ExternalDataError):
            api_client.validate_weather_payload(self.payload, self.dates)

    def test_coverage_gap_is_rejected(self):
        with self.assertRaises(ExternalDataError):
            api_client.validate_weather_payload(self.payload, self.dates + ["2026-10-19"])

    def test_rain_category_boundaries(self):
        self.assertEqual([api_client.classify_rain(v) for v in (0.0, 0.99, 1.0, 9.99, 10.0)],
                         ["Dry", "Dry", "Light rain", "Light rain", "Heavy rain"])


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.deliveries = pd.DataFrame({
            "delivery_id": ["A", "B", "C"],
            "request_date": pd.to_datetime(["2026-10-05", "2026-10-05", "2026-10-06"]),
            "final_delivery_cost_brl": [10.0, 20.0, 30.0], "distance_km": [1.0, 2.0, 3.0]})
        self.weather = pd.DataFrame({"weather_date": pd.to_datetime(["2026-10-05", "2026-10-06"]),
                                     "precipitation_mm": [0.0, 12.0]})

    def test_counts_and_totals_preserved(self):
        result = integrate_deliveries_with_weather(self.deliveries, self.weather)
        self.assertEqual(len(result.integrated), 3)
        self.assertEqual(result.integrated["final_delivery_cost_brl"].sum(), 60.0)
        self.assertTrue((result.checks["result"] == "PASS").all())

    def test_duplicate_weather_day_is_rejected(self):
        dup = pd.concat([self.weather, self.weather.iloc[[0]]])
        with self.assertRaises(IntegrationError):
            integrate_deliveries_with_weather(self.deliveries, dup)

    def test_unmatched_delivery_is_rejected(self):
        with self.assertRaises(IntegrationError):
            integrate_deliveries_with_weather(self.deliveries, self.weather.iloc[[0]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
