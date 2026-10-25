"""Declared CSV/TSV schema, row parsing and loading."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from .timezones import ServerTimeError, to_utc

REQUIRED_COLUMNS = ("DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE")
OPTIONAL_COLUMNS = ("TICKVOL", "VOL", "SPREAD")
DATE_FORMATS = ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d")
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%H:%M:%S.%f")


class SchemaError(ValueError):
    """Raised when the input file does not match the declared schema."""


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


def parse_date(text: str):
    text = text.strip()
    if len(text) == 10 and text[7] == text[4] and text[4] in ".-/":
        try:
            return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
        except ValueError:
            pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise SchemaError(f"unsupported DATE value: {text!r}")


def parse_time(text: str):
    text = text.strip()
    if len(text) == 8 and text[2] == ":" and text[5] == ":":
        try:
            return time(int(text[0:2]), int(text[3:5]), int(text[6:8]))
        except ValueError:
            pass
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise SchemaError(f"unsupported TIME value: {text!r}")


def _num(value, column, line_no):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SchemaError(f"line {line_no}: column {column} is not numeric")


def normalise_header(fieldnames):
    if not fieldnames:
        raise SchemaError("file has no header row")
    headers = tuple((name or "").strip().strip("<>").upper() for name in fieldnames)
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise SchemaError("missing required columns: " + ", ".join(missing))
    return headers


def detect_delimiter(sample: str) -> str:
    return "\t" if sample.count("\t") > sample.count(",") else ","


def _build_candle(raw, positions, optional, line_no, tz_policy, allow_ambiguous):
    date_text = raw[positions["DATE"]]
    time_text = raw[positions["TIME"]]
    naive = datetime.combine(parse_date(date_text), parse_time(time_text))
    try:
        stamp = to_utc(naive, tz_policy, allow_ambiguous)
    except ServerTimeError as exc:
        raise SchemaError(f"line {line_no}: {exc}")
    return Candle(
        time=stamp,
        open=_num(raw[positions["OPEN"]], "OPEN", line_no),
        high=_num(raw[positions["HIGH"]], "HIGH", line_no),
        low=_num(raw[positions["LOW"]], "LOW", line_no),
        close=_num(raw[positions["CLOSE"]], "CLOSE", line_no),
        tickvol=_num(raw[optional["TICKVOL"]], "TICKVOL", line_no) if "TICKVOL" in optional else 0.0,
        volume=_num(raw[optional["VOL"]], "VOL", line_no) if "VOL" in optional else 0.0,
        spread=_num(raw[optional["SPREAD"]], "SPREAD", line_no) if "SPREAD" in optional else 0.0,
    )


def iter_candles(path, tz_policy="eu-dst", allow_ambiguous=False):
    """Yield candles one by one, converting server wall-clock time to UTC."""
    path = Path(path)
    if not path.is_file():
        raise SchemaError(f"input file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        sample = fh.readline()
        delimiter = detect_delimiter(sample)
        fh.seek(0)
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader, None)
        headers = normalise_header(header)
        positions = {name: headers.index(name) for name in REQUIRED_COLUMNS}
        optional = {name: headers.index(name) for name in OPTIONAL_COLUMNS if name in headers}
        for line_no, raw in enumerate(reader, start=2):
            if not raw or len(raw) < len(headers):
                continue
            yield _build_candle(raw, positions, optional, line_no, tz_policy, allow_ambiguous)


def load_candles(path, tz_policy="eu-dst", allow_ambiguous=False):
    """Load all candles into a list (small files only)."""
    return list(iter_candles(path, tz_policy, allow_ambiguous))