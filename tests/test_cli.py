import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.cli import main, run_pipeline

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "synthetic_500.csv"


class CliTests(unittest.TestCase):
    def test_pipeline_runs_end_to_end(self):
        with TemporaryDirectory() as tmp:
            code, payload = run_pipeline(FIXTURE, tmp, "ma_5_20")
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["cost_label"], "NO_TRADING_COSTS")
            for name in ("trades.csv", "summary.json", "manifest.json"):
                self.assertTrue((Path(tmp) / name).is_file(), name)
            summary = json.loads((Path(tmp) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["rows"], 500)
            self.assertIn("metrics", summary)

    def test_pipeline_is_deterministic(self):
        with TemporaryDirectory() as a, TemporaryDirectory() as b:
            run_pipeline(FIXTURE, a, "ma_10_50")
            run_pipeline(FIXTURE, b, "ma_10_50")
            self.assertEqual((Path(a) / "trades.csv").read_bytes(), (Path(b) / "trades.csv").read_bytes())

    def test_second_strategy_runs(self):
        with TemporaryDirectory() as tmp:
            code, _ = run_pipeline(FIXTURE, tmp, "ma_20_100")
            self.assertEqual(code, 0)

    def test_invalid_data_is_rejected(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.csv"
            bad.write_text("DATE,TIME,OPEN,HIGH,LOW,CLOSE\n2024.01.01,00:00:00,10,9,11,10\n", encoding="utf-8")
            code, payload = run_pipeline(bad, tmp, "ma_5_20")
            self.assertEqual(code, 2)
            self.assertEqual(payload["status"], "INVALID_DATA")

    def test_main_reports_schema_error(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.csv"
            bad.write_text("X,Y\n1,2\n", encoding="utf-8")
            self.assertEqual(main(["run", "--csv", str(bad), "--out", tmp]), 2)

    def test_main_success_exit_code(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(main(["run", "--csv", str(FIXTURE), "--out", tmp]), 0)


if __name__ == "__main__":
    unittest.main()