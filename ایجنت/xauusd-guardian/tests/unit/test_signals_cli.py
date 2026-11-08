"""S5: CLI contract — exit codes, machine-readable output, database isolation."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from guardian.contracts.market import FeedRun, MarketBar, Timeframe
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

SYMBOL = "XAUUSD."
TF = Timeframe.M5
START = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
NOW_TEXT = (START + timedelta(minutes=600)).isoformat()
FULL = [100.0 + i for i in range(60)] + [160.0 - 3.0 * (i - 60) for i in range(60, 120)]


def make_bars(count: int = 120):
    return [
        MarketBar(
            symbol=SYMBOL,
            timeframe=TF,
            time_utc=START + timedelta(minutes=5 * i),
            open=FULL[i], high=FULL[i] + 1, low=FULL[i] - 1, close=FULL[i], tick_volume=1,
        )
        for i in range(count)
    ]


@pytest.fixture()
def db_path(tmp_path, project_root):
    path = tmp_path / "cli.sqlite3"
    conn = connect(path)
    apply_migrations(conn, project_root / "migrations")
    store = MarketStore(conn, quota_bytes=50_000_000)
    store.record_run_start(
        FeedRun(run_id="run-1", symbol=SYMBOL, kind="bars", timeframe=TF, started_utc=START, status="OK")
    )
    store.upsert_bars("run-1", make_bars())
    conn.close()
    return path


def run_cli(project_root, *args):
    return subprocess.run(
        [sys.executable, str(project_root / "scripts" / "signals.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=180,
    )


def test_cli_success_is_machine_readable(db_path, project_root):
    result = run_cli(project_root, "--db", str(db_path), "--now", NOW_TEXT)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "OK"
    assert payload["symbol"] == SYMBOL
    assert payload["timeframe"] == "M5"
    assert payload["strategy_id"] == "ema_cross_v1"
    assert payload["bars_seen"] == 120
    assert payload["signals"] >= 1
    assert payload["created"] is True
    assert len(payload["bars_digest"]) == 64


def test_cli_repeat_run_is_idempotent(db_path, project_root):
    first = run_cli(project_root, "--db", str(db_path), "--now", NOW_TEXT)
    second = run_cli(project_root, "--db", str(db_path), "--now", NOW_TEXT)

    assert (first.returncode, second.returncode) == (0, 0)
    one, two = json.loads(first.stdout), json.loads(second.stdout)
    assert one["run_id"] == two["run_id"]
    assert two["written"] == 0
    assert two["created"] is False
    assert two["identical"] == one["signals"]


def test_cli_empty_database_exits_1(tmp_path, project_root):
    path = tmp_path / "empty.sqlite3"
    conn = connect(path)
    apply_migrations(conn, project_root / "migrations")
    conn.close()

    result = run_cli(project_root, "--db", str(path), "--now", NOW_TEXT)

    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "FAILED"


@pytest.mark.parametrize(
    "bad_now",
    [
        "2026-11-05T18:00:00",        # naive
        "not-a-timestamp",
        "2026-11-05T18:00:00+25:00",  # offset out of range
    ],
)
def test_cli_invalid_now_exits_2(db_path, project_root, bad_now):
    result = run_cli(project_root, "--db", str(db_path), "--now", bad_now)
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout.strip() == ""


def test_cli_never_touches_the_default_database(db_path, project_root):
    default_db = project_root / "data" / "guardian.sqlite3"
    existed = default_db.exists()
    result = run_cli(project_root, "--db", str(db_path), "--now", NOW_TEXT)
    assert result.returncode == 0
    assert default_db.exists() is existed
