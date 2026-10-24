import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.schema import SchemaError, detect_delimiter, load_candles

HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"


class TsvTests(unittest.TestCase):
    def _write(self, tmp, body):
        path = Path(tmp) / "data.csv"
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def test_detects_tab(self):
        self.assertEqual(detect_delimiter(HEADER), "\t")
        self.assertEqual(detect_delimiter("DATE,TIME\n"), ",")

    def test_loads_mt5_style_export(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.07.01\t12:00:00\t10\t11\t9\t10.5\t5\t0\t20\n")
            candle = load_candles(path)[0]
        self.assertEqual(candle.time, datetime(2024, 7, 1, 9, 0, tzinfo=timezone.utc))
        self.assertEqual((candle.tickvol, candle.volume, candle.spread), (5.0, 0.0, 20.0))

    def test_ambiguous_timestamp_is_a_schema_error(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.10.27\t03:30:00\t10\t11\t9\t10.5\t5\t0\t20\n")
            with self.assertRaises(SchemaError):
                load_candles(path)

    def test_policy_can_be_overridden(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.10.27\t03:30:00\t10\t11\t9\t10.5\t5\t0\t20\n")
            candle = load_candles(path, tz_policy="utc")[0]
        self.assertEqual(candle.time, datetime(2024, 10, 27, 3, 30, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()