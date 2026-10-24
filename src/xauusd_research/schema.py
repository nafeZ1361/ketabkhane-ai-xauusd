"""Declared CSV schema, row parsing and loading."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS = ("DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE")
OPTIONAL_COLUMNS = ("TICKVOL", "VOL", "SPREAD")
DATE_FORMATS = ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d")
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%H:%M:%S.%f")


class SchemaError(ValueError):
    """Raised when the input CSV does not match the declared schema."""


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tickvol: float = 0.0
    volume: float = 0.0
    spread: float = 0.0


def parse_date(text: str) -> datetime.date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise SchemaError(f"unsupported DATE value: {text!r}")


def parse_time(text: str):
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise SchemaError(f"unsupported TIME value: {text!r}")


def _float(row, column, line_no):
    try:
        return float(row[column])
    except (KeyError, TypeError, ValueError):
        raise SchemaError(f"line {line_no}: column {column} is not numeric")


def parse_row(row, line_no):
    return Candle(
        time=datetime.combine(parse_date(row["DATE"]), parse_time(row["TIME"])),
        open=_float(row, "OPEN", line_no),
        high=_float(row, "HIGH", line_no),
        low=_float(row, "LOW", line_no),
        close=_float(row, "CLOSE", line_no),
        tickvol=_float(row, "TICKVOL", line_no) if row.get("TICKVOL") else 0.0,
        volume=_float(row, "VOL", line_no) if row.get("VOL") else 0.0,
        spread=_float(row, "SPREAD", line_no) if row.get("SPREAD") else 0.0,
    )


def normalise_header(fieldnames):
    if not fieldnames:
        raise SchemaError("CSV has no header row")
    headers = tuple((name or "").strip().upper() for name in fieldnames)
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise SchemaError("missing required columns: " + ", ".join(missing))
    return headers


def load_candles(path):
    path = Path(path)
    if not path.is_file():
        raise SchemaError(f"input file not found: {path}")
    candles = []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        normalise_header(reader.fieldnames)
        for line_no, raw in enumerate(reader, start=2):
            row = {(k or "").strip().upper(): (v or "").strip() for k, v in raw.items()}
            if not any(row.values()):
                continue
            candles.append(parse_row(row, line_no))
    return candles