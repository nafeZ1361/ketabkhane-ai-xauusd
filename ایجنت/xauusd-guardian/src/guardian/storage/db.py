"""SQLite access and hash-verified migrations.

One connection per caller; no global connection object (no hidden global state).
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MIGRATION_PATTERN = r"^[0-9]{4}_[a-z0-9_]+\.sql$"


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    version: int
    filename: str
    sha256: str
    applied_at: str


class MigrationError(RuntimeError):
    """Raised when migration history is inconsistent or tampered with."""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover_migrations(migrations_dir: str | Path) -> list[Path]:
    import re

    directory = Path(migrations_dir)
    if not directory.is_dir():
        return []
    pattern = re.compile(MIGRATION_PATTERN)
    return sorted(p for p in directory.iterdir() if p.is_file() and pattern.match(p.name))


def apply_migrations(conn: sqlite3.Connection, migrations_dir: str | Path) -> list[int]:
    """Apply pending migrations in filename order. Returns applied versions."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            filename   TEXT NOT NULL,
            sha256     TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    history = {
        row["version"]: row
        for row in conn.execute("SELECT version, filename, sha256, applied_at FROM schema_migrations")
    }

    applied: list[int] = []
    for path in discover_migrations(migrations_dir):
        version = int(path.name.split("_", 1)[0])
        sql = path.read_text(encoding="utf-8")
        digest = _sha256(sql)

        if version in history:
            if history[version]["sha256"] != digest:
                raise MigrationError(
                    f"migration {path.name} changed after being applied "
                    f"(recorded {history[version]['sha256']}, now {digest})"
                )
            continue

        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, filename, sha256, applied_at) VALUES (?, ?, ?, ?)",
            (version, path.name, digest, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        applied.append(version)

    return applied


def migration_history(conn: sqlite3.Connection) -> list[AppliedMigration]:
    rows: Iterable[sqlite3.Row] = conn.execute(
        "SELECT version, filename, sha256, applied_at FROM schema_migrations ORDER BY version"
    )
    return [
        AppliedMigration(
            version=row["version"],
            filename=row["filename"],
            sha256=row["sha256"],
            applied_at=row["applied_at"],
        )
        for row in rows
    ]
