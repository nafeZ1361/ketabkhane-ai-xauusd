import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.schema import SchemaError, load_candles, normalise_header

HEADER = "DATE,TIME,OPEN,HIGH,LOW,CLOSE\n"


class SchemaTests(unittest.TestCase):
    def _write(self, tmp, body, header=HEADER):
        path = Path(tmp) / "data.csv"
        path.write_text(header + body, encoding="utf-8")
        return path

    def test_loads_valid_rows(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,00:00:00,10,11,9,10.5\n2024.01.01,00:01:00,10.5,11.5,10,11\n")
            candles = load_candles(path)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].open, 10.0)
        self.assertEqual(candles[1].close, 11.0)
        self.assertEqual(candles[0].tickvol, 0.0)

    def test_optional_columns_are_parsed(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,00:00:00,10,11,9,10.5,7,0,20\n",
                                "DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL,VOL,SPREAD\n")
            candle = load_candles(path)[0]
        self.assertEqual((candle.tickvol, candle.volume, candle.spread), (7.0, 0.0, 20.0))

    def test_header_is_case_insensitive(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,00:00:00,10,11,9,10.5\n", "date,time,open,high,low,close\n")
            self.assertEqual(len(load_candles(path)), 1)

    def test_blank_lines_are_skipped(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "\n2024.01.01,00:00:00,10,11,9,10.5\n\n")
            self.assertEqual(len(load_candles(path)), 1)

    def test_missing_column_raises(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,00:00:00,10,11,9\n", "DATE,TIME,OPEN,HIGH,LOW\n")
            with self.assertRaises(SchemaError):
                load_candles(path)

    def test_non_numeric_raises(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,00:00:00,abc,11,9,10.5\n")
            with self.assertRaises(SchemaError):
                load_candles(path)

    def test_bad_date_raises(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024/13/45,00:00:00,10,11,9,10.5\n")
            with self.assertRaises(SchemaError):
                load_candles(path)

    def test_bad_time_raises(self):
        with TemporaryDirectory() as tmp:
            path = self._write(tmp, "2024.01.01,99:99:99,10,11,9,10.5\n")
            with self.assertRaises(SchemaError):
                load_candles(path)

    def test_missing_file_raises(self):
        with self.assertRaises(SchemaError):
            load_candles(Path("does-not-exist.csv"))

    def test_missing_header_raises(self):
        with self.assertRaises(SchemaError):
            normalise_header(None)


if __name__ == "__main__":
    unittest.main()