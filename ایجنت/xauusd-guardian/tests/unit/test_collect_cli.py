"""CLI window resolution and the inserted-zero guard (Phase A1/A2)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import collect  # noqa: E402

from guardian.application.market_data_service import CollectionOutcome  # noqa: E402
from guardian.contracts.market import FeedRun  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 11, 5, 10, 31, 53, tzinfo=timezone.utc)
END = datetime(2026, 11, 5, 10, 41, 53, tzinfo=timezone.utc)


def test_parse_utc_accepts_zulu_and_offsets():
    assert collect.parse_utc("2026-11-05T10:31:53Z") == START
    assert collect.parse_utc("2026-11-05T14:01:53+03:30") == START


@pytest.mark.parametrize("value", ["2026-11-05T10:31:53", "not-a-time", ""])
def test_parse_utc_rejects_naive_and_garbage(value):
    with pytest.raises(argparse.ArgumentTypeError):
        collect.parse_utc(value)


def test_explicit_window_is_used_exactly():
    assert collect.resolve_tick_window(start=START, end=END, minutes=0, now=NOW) == (START, END)


def test_explicit_end_is_never_replaced_by_now():
    start, end = collect.resolve_tick_window(start=START, end=END, minutes=0, now=NOW)
    assert end == END and end != NOW


def test_relative_window_is_unchanged_and_defaults_to_thirty_minutes():
    assert collect.resolve_tick_window(start=None, end=None, minutes=10, now=NOW) == (
        NOW - timedelta(minutes=10),
        NOW,
    )
    assert collect.resolve_tick_window(start=None, end=None, minutes=0, now=NOW)[0] == NOW - timedelta(minutes=30)


def test_negative_minutes_is_refused():
    with pytest.raises(ValueError, match="negative"):
        collect.resolve_tick_window(start=None, end=None, minutes=-5, now=NOW)


def test_one_sided_window_is_refused():
    with pytest.raises(ValueError, match="together"):
        collect.resolve_tick_window(start=START, end=None, minutes=0, now=NOW)
    with pytest.raises(ValueError, match="together"):
        collect.resolve_tick_window(start=None, end=END, minutes=0, now=NOW)


def test_conflicting_arguments_are_refused():
    with pytest.raises(ValueError, match="cannot be combined"):
        collect.resolve_tick_window(start=START, end=END, minutes=5, now=NOW)


@pytest.mark.parametrize(("start", "end"), [(END, START), (START, START)])
def test_reversed_and_empty_windows_are_refused(start, end):
    with pytest.raises(ValueError):
        collect.resolve_tick_window(start=start, end=end, minutes=0, now=NOW)


def outcome(status: str, *runs: FeedRun) -> CollectionOutcome:
    return CollectionOutcome(status, tuple(runs), ())


def ticks_run(inserted: int, status: str = "OK") -> FeedRun:
    return FeedRun(run_id="r", symbol="XAUUSD.", kind="ticks", started_utc=START, status=status, inserted=inserted)


def test_zero_insert_is_a_failure_not_a_success():
    status, reasons = collect.effective_status(outcome("OK", ticks_run(0)))
    assert status == "FAILED"
    assert "inserted_zero:no_new_rows" in reasons


def test_degraded_zero_insert_is_also_a_failure():
    status, _ = collect.effective_status(outcome("DEGRADED", ticks_run(0, status="DEGRADED")))
    assert status == "FAILED"


def test_a_real_tick_insert_keeps_its_status():
    status, reasons = collect.effective_status(outcome("OK", ticks_run(7840)))
    assert status == "OK" and reasons == []


def test_zero_insert_for_bars_is_not_a_failure():
    bar_run = FeedRun(run_id="b", symbol="XAUUSD.", kind="bars", started_utc=START, status="OK", inserted=0)
    status, _ = collect.effective_status(outcome("OK", bar_run))
    assert status == "OK"


def test_blocked_outcome_is_never_upgraded_or_downgraded():
    status, reasons = collect.effective_status(outcome("BLOCKED", ticks_run(0)))
    assert status == "BLOCKED" and reasons == []
