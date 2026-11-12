"""SQLite access and hash-verified migrations.

One connection per caller; no global connection object (no hidden global state).

Forward migrations live in ``migrations/``. Their reverses live in
``migrations/rollback/`` and are executed only by :func:`revert_migration`;
the dotted ``*.down.sql`` name can never match the forward discovery pattern,
so a reverse is never applied as the next forward step.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MIGRATION_PATTERN = r"^[0-9]{4}_[a-z0-9_]+\.sql$"
DOWN_MIGRATION_PATTERN = r"^(?P<version>[0-9]{4})_[a-z0-9_]+\.down\.sql$"

_CREATE_RE = re.compile(
    r"CREATE\s+(?P<kind>TABLE|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_DROP_RE = re.compile(
    r"^DROP\s+(?P<kind>TABLE|INDEX)\s+(?:IF\s+EXISTS\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)$",
    re.IGNORECASE,
)
_TABLE_CONSTRAINT_KEYWORDS = frozenset({"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"})


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    version: int
    filename: str
    sha256: str
    applied_at: str


@dataclass(frozen=True, slots=True)
class ReversalPlan:
    """Everything :func:`revert_migration` is about to do, checked beforehand.

    Exposed so an operator or an inspector can read the exact objects and the
    exact reverse script (with its digest) before anything is dropped.
    """

    version: int
    forward_filename: str
    forward_sha256: str
    down_filename: str
    down_sha256: str
    statements: tuple[str, ...]
    tables: tuple[str, ...]
    indexes: tuple[str, ...]


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


def discover_down_migrations(rollback_dir: str | Path) -> list[Path]:
    """Reverse scripts, matched by the strict ``NNNN_name.down.sql`` pattern.

    Deliberately narrower than :func:`discover_migrations`: a forward file that
    is copied into ``rollback/`` is not a candidate, and neither is a reverse
    with a malformed name. Being strict here means "no down file" is a loud
    refusal instead of an accidental execution of the wrong script.
    """
    directory = Path(rollback_dir)
    if not directory.is_dir():
        return []
    pattern = re.compile(DOWN_MIGRATION_PATTERN)
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

        adopted = _existing_objects(conn, tuple(_created_objects(sql)))
        if adopted:
            raise MigrationError(
                f"migration {path.name} would adopt existing object(s) {adopted} instead of "
                f"creating them; refusing to record a migration that creates nothing. If these "
                f"objects came from an interrupted apply, resolve the database manually, then re-run."
            )

        statements = _split_sql_statements(sql, path.name)
        if conn.in_transaction:
            conn.commit()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, filename, sha256, applied_at) VALUES (?, ?, ?, ?)",
                (version, path.name, digest, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
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


# --------------------------------------------------------------------------- #
# Reversal
# --------------------------------------------------------------------------- #


def _strip_comments(statement: str) -> str:
    """Drop ``--`` comments so a keyword check cannot be hidden behind one."""
    return "\n".join(line.split("--", 1)[0] for line in statement.splitlines()).strip()


def _split_sql_statements(sql: str, source: str) -> list[str]:
    """Split a script into statements using SQLite's own completeness test.

    ``sqlite3.complete_statement`` respects quotes, ``BEGIN ... END`` bodies and
    parentheses, so a naive ``str.split(";")`` cannot be fooled into treating
    one statement as two.
    """
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        if not buffer and not line.strip():
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            if _strip_comments(buffer):
                statements.append(buffer.strip())
            buffer = ""
    if buffer.strip() and _strip_comments(buffer):
        raise MigrationError(f"{source} ends with an incomplete statement: {buffer.strip()!r}")
    return statements


def _created_objects(forward_sql: str) -> dict[str, str]:
    """Map object name -> ``table``/``index`` for every CREATE in a migration.

    Comments are stripped first, so a ``--`` comment that happens to mention
    ``CREATE TABLE bars`` cannot widen the reverse whitelist. Names are
    lower-cased because SQLite compares identifiers case-insensitively: a table
    created as ``SIGNALS`` is the same object as ``signals``.
    """
    return {
        match.group("name").lower(): match.group("kind").lower()
        for match in _CREATE_RE.finditer(_strip_comments(forward_sql))
    }


def _existing_objects(conn: sqlite3.Connection, names: tuple[str, ...]) -> list[str]:
    """Names from ``names`` that already exist in ``sqlite_master``, sorted.

    Case-insensitive, for the same reason as :func:`_created_objects`.
    """
    if not names:
        return []
    lowered = tuple(name.lower() for name in names)
    placeholders = ",".join("?" for _ in lowered)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE lower(name) IN ({placeholders})", lowered
    ).fetchall()
    return sorted(row["name"] for row in rows)


def _declared_shape(forward_sql: str, table: str) -> tuple[tuple[str, str], ...]:
    """``(column, declared type)`` pairs for ``CREATE TABLE <table> (...)``, in order."""
    match = re.search(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + re.escape(table) + r"\s*\(",
        forward_sql,
        re.IGNORECASE,
    )
    if match is None:
        return ()

    body: list[str] = []
    depth = 1
    for char in forward_sql[match.end():]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        body.append(char)

    items: list[str] = []
    current: list[str] = []
    depth = 0
    for char in "".join(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    items.append("".join(current))

    columns: list[tuple[str, str]] = []
    for item in items:
        tokens = _strip_comments(item).split()
        if not tokens:
            continue
        if tokens[0].upper() in _TABLE_CONSTRAINT_KEYWORDS:
            continue
        declared_type = tokens[1].upper() if len(tokens) > 1 else ""
        columns.append((tokens[0].strip('"`[]').lower(), declared_type))
    return tuple(columns)


def _checked_down_statements(
    down_sql: str,
    down_name: str,
    owned: dict[str, str],
    forward_name: str,
) -> list[str]:
    """Refuse a reverse that could touch anything its forward did not create.

    The whitelist is intentionally narrow: ``DROP TABLE`` or ``DROP INDEX`` of an
    object created by the paired forward migration. ``DELETE``, ``UPDATE``,
    ``ALTER``, ``ATTACH`` or a drop of any pre-existing object is rejected before
    a single statement runs, so a mistaken down file cannot remove pre-migration
    data even inside the transaction.
    """
    statements = _split_sql_statements(down_sql, down_name)
    if not statements:
        raise MigrationError(f"{down_name} contains no statements")

    for statement in statements:
        text = " ".join(_strip_comments(statement).split()).rstrip(";").strip()
        match = _DROP_RE.match(text)
        if match is None:
            raise MigrationError(
                f"{down_name} contains a statement that is not a plain DROP TABLE/INDEX: {text!r}"
            )
        kind = match.group("kind").lower()
        name = match.group("name")
        if name.lower() not in owned:
            raise MigrationError(
                f"{down_name} would drop {name!r}, which {forward_name} did not create"
            )
        if owned[name.lower()] != kind:
            raise MigrationError(
                f"{down_name} would drop {name!r} as a {kind}, but {forward_name} created it as a {owned[name.lower()]}"
            )
    return statements


def _check_declared_shapes(
    conn: sqlite3.Connection,
    forward_sql: str,
    forward_name: str,
    tables: tuple[str, ...],
) -> None:
    """Refuse to drop a table whose live columns or declared types drifted.

    Catches manual DDL between apply and revert: an added column, a changed
    type, a replaced table. Adoption of a pre-existing table cannot reach this
    check: :func:`apply_migrations` refuses to record a migration whose objects
    already exist, so a table named by an applied migration was created by it.
    """
    for table in tables:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND lower(name) = ?", (table.lower(),)
        ).fetchone()
        if present is None:
            # A missing table fails loudly at DROP time, inside the transaction.
            continue
        declared = _declared_shape(forward_sql, table)
        if not declared:
            raise MigrationError(
                f"{forward_name} declares no columns for {table!r}; refusing to drop an unverifiable table"
            )
        actual = tuple(
            (
                row["name"].lower(),
                row["type"].upper().split()[0] if row["type"].strip() else "",
            )
            for row in conn.execute(f'PRAGMA table_info("{table}")')
        )
        if declared != actual:
            raise MigrationError(
                f"table {table!r} does not match {forward_name} "
                f"(declared {list(declared)}, actual {list(actual)}); refusing to drop a drifted table"
            )


def _verify_reversal(conn: sqlite3.Connection, plan: ReversalPlan) -> None:
    """Post-condition: no object the forward created may still exist."""
    names = plan.tables + plan.indexes
    if not names:
        return
    lowered = tuple(name.lower() for name in names)
    placeholders = ",".join("?" for _ in lowered)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE lower(name) IN ({placeholders})", lowered
    ).fetchall()
    if rows:
        remaining = sorted(row["name"] for row in rows)
        raise MigrationError(
            f"reversal of {plan.version} left objects behind: {remaining}"
        )


def reversal_plan(
    conn: sqlite3.Connection,
    migrations_dir: str | Path,
    version: int,
    *,
    rollback_dir: str | Path | None = None,
) -> ReversalPlan:
    """Resolve and validate the reverse of one applied migration, without acting.

    Refuses, rather than guesses, when the ledger and the files disagree: an
    unapplied version, a later version still applied, a forward file that
    changed after being applied, no down file or more than one, a down file that
    touches an object the forward did not create, or a live table whose shape
    drifted from the declared one.
    """
    migrations_dir = Path(migrations_dir)
    down_dir = Path(rollback_dir) if rollback_dir is not None else migrations_dir / "rollback"

    history = {entry.version: entry for entry in migration_history(conn)}
    if version not in history:
        raise MigrationError(f"migration {version} is not applied")
    later = sorted(applied for applied in history if applied > version)
    if later:
        raise MigrationError(f"cannot revert {version} while later migrations are applied: {later}")

    recorded = history[version]
    forward = migrations_dir / recorded.filename
    if not forward.is_file():
        raise MigrationError(f"forward migration is missing: {recorded.filename}")
    forward_sql = forward.read_text(encoding="utf-8")
    current = _sha256(forward_sql)
    if current != recorded.sha256:
        raise MigrationError(
            f"migration {recorded.filename} changed after being applied "
            f"(recorded {recorded.sha256}, now {current})"
        )

    candidates = [
        path
        for path in discover_down_migrations(down_dir)
        if int(path.name.split("_", 1)[0]) == version
    ]
    if len(candidates) != 1:
        raise MigrationError(
            f"expected exactly one down migration for version {version} in {down_dir}, "
            f"found {len(candidates)}"
        )
    down = candidates[0]
    down_sql = down.read_text(encoding="utf-8")

    owned = _created_objects(forward_sql)
    if not owned:
        raise MigrationError(f"{recorded.filename} creates no objects; no reverse can be derived")
    statements = _checked_down_statements(down_sql, down.name, owned, recorded.filename)

    tables = tuple(sorted(name for name, kind in owned.items() if kind == "table"))
    indexes = tuple(sorted(name for name, kind in owned.items() if kind == "index"))
    _check_declared_shapes(conn, forward_sql, recorded.filename, tables)

    return ReversalPlan(
        version=version,
        forward_filename=recorded.filename,
        forward_sha256=current,
        down_filename=down.name,
        down_sha256=_sha256(down_sql),
        statements=tuple(statements),
        tables=tables,
        indexes=indexes,
    )


def revert_migration(
    conn: sqlite3.Connection,
    migrations_dir: str | Path,
    version: int,
    *,
    rollback_dir: str | Path | None = None,
) -> int:
    """Reverse exactly one applied migration and drop its bookkeeping row.

    The reverse script, the post-condition and the ``schema_migrations`` delete
    run in one explicit ``BEGIN IMMEDIATE ... COMMIT``: either the schema is
    fully reversed and the ledger says so, or nothing happened. A half-dropped
    schema left recorded as applied would be hash-skipped by
    :func:`apply_migrations` for ever.
    """
    plan = reversal_plan(conn, migrations_dir, version, rollback_dir=rollback_dir)

    if conn.in_transaction:
        conn.commit()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for statement in plan.statements:
            conn.execute(statement)
        _verify_reversal(conn, plan)
        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (plan.version,))
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    return plan.version
