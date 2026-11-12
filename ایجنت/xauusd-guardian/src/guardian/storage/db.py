"""SQLite access and hash-verified, reversible migrations.

One connection per caller; no global connection object (no hidden global state).

Forward migrations live in ``migrations/``. Their reverses live in
``migrations/rollback/`` and are executed only by :func:`revert_migration`.

Safety model, in layers:

1. ``apply_migrations`` refuses to record a migration whose declared objects already
   exist (adoption would make the ledger claim something it did not do).
2. Every apply records the objects it *actually created*, observed from
   ``sqlite_master`` before and after, in ``schema_objects``. Provenance is measured,
   not parsed.
3. A reverse may only drop objects recorded as created by that migration, targets
   ``main`` explicitly, and runs inside one transaction.
4. After the reverse, every schema is re-inspected: an object that existed before and
   was not created by this migration must still exist, and every created object must be
   gone. Otherwise the whole reverse rolls back.
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

#: SQLite accepts four identifier spellings, optionally schema-qualified.
_IDENT = r'(?:"[^"]+"|\[[^\]]+\]|`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)'
_SCHEMA_PREFIX = r"(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?"

_CREATE_RE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(?P<kind>TABLE|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>" + _SCHEMA_PREFIX + _IDENT + r")",
    re.IGNORECASE,
)
_DROP_RE = re.compile(
    r"^DROP\s+(?P<kind>TABLE|INDEX)\s+(?:IF\s+EXISTS\s+)?(?P<name>" + _SCHEMA_PREFIX + _IDENT + r")$",
    re.IGNORECASE,
)
_TABLE_CONSTRAINT_KEYWORDS = frozenset({"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"})
_OBJECT_TYPES = ("table", "index", "trigger", "view")


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    version: int
    filename: str
    sha256: str
    applied_at: str


@dataclass(frozen=True, slots=True)
class ReversalPlan:
    """Everything :func:`revert_migration` is about to do, checked beforehand."""

    version: int
    forward_filename: str
    forward_sha256: str
    down_filename: str
    down_sha256: str
    drops: tuple[tuple[str, str], ...]
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
    """Reverse scripts, matched by the strict ``NNNN_name.down.sql`` pattern."""
    directory = Path(rollback_dir)
    if not directory.is_dir():
        return []
    pattern = re.compile(DOWN_MIGRATION_PATTERN)
    return sorted(p for p in directory.iterdir() if p.is_file() and pattern.match(p.name))


# --------------------------------------------------------------------------- #
# SQL-text helpers
# --------------------------------------------------------------------------- #


def _strip_comments(statement: str) -> str:
    """Drop ``--`` comments so a keyword check cannot be hidden behind one."""
    return "\n".join(line.split("--", 1)[0] for line in statement.splitlines()).strip()


def _split_sql_statements(sql: str, source: str) -> list[str]:
    """Split a script using SQLite's own completeness test.

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


def _bare_identifier(raw: str) -> str:
    """Normalise ``[schema.]name`` / ``"name"`` / ``[name]`` / ```name``` to a lower bare name."""
    value = raw.strip()
    if not value.startswith('"') and not value.startswith("[") and not value.startswith("`"):
        if "." in value:
            value = value.split(".", 1)[1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    elif len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        value = value[1:-1]
    return value.lower()


def _created_objects(forward_sql: str) -> dict[str, str]:
    """Map bare object name -> ``table``/``index`` for every CREATE in a migration.

    Comments are stripped first, so a ``--`` comment that happens to mention
    ``CREATE TABLE bars`` cannot widen the reverse whitelist. Names are normalised:
    SQLite treats quoted, bracketed, backticked and schema-qualified spellings as the
    same identifier, and compares them case-insensitively.
    """
    objects: dict[str, str] = {}
    for match in _CREATE_RE.finditer(_strip_comments(forward_sql)):
        objects[_bare_identifier(match.group("name"))] = match.group("kind").lower()
    return objects


def _object_inventory(conn: sqlite3.Connection, schema: str = "main") -> set[tuple[str, str]]:
    """``(type, lower name)`` for every object in one schema, minus SQLite internals."""
    try:
        rows = conn.execute(f"SELECT type, name FROM {schema}.sqlite_master").fetchall()
    except sqlite3.DatabaseError:
        return set()
    return {
        (row["type"].lower(), row["name"].lower())
        for row in rows
        if row["type"].lower() in _OBJECT_TYPES and not row["name"].lower().startswith("sqlite_")
    }


def _schema_list(conn: sqlite3.Connection) -> list[str]:
    names = ["main", "temp"]
    for row in conn.execute("PRAGMA database_list"):
        name = row["name"]
        if name not in names:
            names.append(name)
    return names


def _all_inventories(conn: sqlite3.Connection) -> dict[str, set[tuple[str, str]]]:
    return {schema: _object_inventory(conn, schema) for schema in _schema_list(conn)}


def _existing_objects(conn: sqlite3.Connection, names: tuple[str, ...]) -> list[str]:
    """Names from ``names`` that already exist in ``main``, sorted.

    Case-insensitive and quote-insensitive, because SQLite is.
    """
    if not names:
        return []
    wanted = {name.lower() for name in names}
    present = {name for _, name in _object_inventory(conn, "main")}
    return sorted(present & wanted)


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #


def _ensure_bookkeeping(conn: sqlite3.Connection) -> None:
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_objects (
            version INTEGER NOT NULL,
            kind    TEXT NOT NULL,
            name    TEXT NOT NULL,
            PRIMARY KEY (version, kind, name)
        )
        """
    )
    conn.commit()


def apply_migrations(conn: sqlite3.Connection, migrations_dir: str | Path) -> list[int]:
    """Apply pending migrations in filename order. Returns applied versions.

    Each migration runs in one transaction together with its ledger row and its
    measured object provenance: either the schema changed and the ledger says which
    objects it created, or nothing happened. A migration whose declared objects
    already exist is refused — it would create nothing and lie about it.
    """
    _ensure_bookkeeping(conn)

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

        declared = _created_objects(sql)
        adopted = _existing_objects(conn, tuple(declared))
        if adopted:
            raise MigrationError(
                f"migration {path.name} would adopt existing object(s) {adopted} instead of "
                f"creating them; refusing to record a migration that creates nothing. If these "
                f"objects came from an interrupted apply, resolve the database manually, then re-run."
            )

        statements = _split_sql_statements(sql, path.name)
        before = _object_inventory(conn, "main")
        if conn.in_transaction:
            conn.commit()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for statement in statements:
                conn.execute(statement)
            created = _object_inventory(conn, "main") - before
            missing = sorted(set(declared) - {name for _, name in created})
            if missing:
                raise MigrationError(
                    f"migration {path.name} did not create declared object(s) {missing}; "
                    f"refusing to record it"
                )
            conn.execute(
                "INSERT INTO schema_migrations (version, filename, sha256, applied_at) VALUES (?, ?, ?, ?)",
                (version, path.name, digest, datetime.now(timezone.utc).isoformat()),
            )
            conn.executemany(
                "INSERT INTO schema_objects (version, kind, name) VALUES (?, ?, ?)",
                [(version, kind, name) for kind, name in sorted(created)],
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


def migration_provenance(conn: sqlite3.Connection, version: int) -> tuple[tuple[str, str], ...]:
    """Objects recorded as created by one migration, as ``(kind, name)`` pairs."""
    rows = conn.execute(
        "SELECT kind, name FROM schema_objects WHERE version = ? ORDER BY kind, name", (version,)
    ).fetchall()
    return tuple((row["kind"], row["name"]) for row in rows)


# --------------------------------------------------------------------------- #
# Reversal
# --------------------------------------------------------------------------- #


def _declared_shape(forward_sql: str, table: str) -> tuple[tuple[str, str], ...]:
    """``(column, declared type)`` pairs for ``CREATE TABLE <table> (...)``, in order."""
    match = re.search(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?"
        + r'(?:"' + re.escape(table) + r'"|\[?' + re.escape(table) + r'\]?)' + r"\s*\(",
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
        parts = _strip_comments(item).split()
        if not parts:
            continue
        if parts[0].upper() in _TABLE_CONSTRAINT_KEYWORDS:
            continue
        declared_type = parts[1].upper() if len(parts) > 1 else ""
        columns.append((_bare_identifier(parts[0]), declared_type))
    return tuple(columns)


def _check_declared_shapes(
    conn: sqlite3.Connection,
    forward_sql: str,
    forward_name: str,
    tables: tuple[str, ...],
) -> None:
    """Refuse to drop a table whose live columns or declared types drifted.

    Catches manual DDL between apply and revert. Adoption cannot reach this check:
    ``apply_migrations`` refuses to record a migration whose objects already exist, and
    the reverse only targets objects the migration is recorded as having created.
    A table missing from ``main`` is left to fail at DROP time, inside the transaction.
    """
    present = {name for kind, name in _object_inventory(conn, "main") if kind == "table"}
    for table in tables:
        if table.lower() not in present:
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
            for row in conn.execute(f'PRAGMA main.table_info("{table}")')
        )
        if declared != actual:
            raise MigrationError(
                f"table {table!r} does not match {forward_name} "
                f"(declared {list(declared)}, actual {list(actual)}); refusing to drop a drifted table"
            )


def _checked_down_statements(
    down_sql: str,
    down_name: str,
    owned: dict[str, str],
    forward_name: str,
) -> list[tuple[str, str]]:
    """Validate the reverse and return canonical ``(kind, bare name)`` drops.

    The whitelist is deliberately narrow: ``DROP TABLE`` or ``DROP INDEX`` of an object
    the paired forward migration is recorded as having created, targeting ``main`` or no
    schema at all. ``DELETE``, ``UPDATE``, ``ALTER``, ``ATTACH``, another schema, a
    duplicated drop, or a drop of any object the migration did not create is rejected
    before a single statement runs.
    """
    statements = _split_sql_statements(down_sql, down_name)
    if not statements:
        raise MigrationError(f"{down_name} contains no statements")

    drops: list[tuple[str, str]] = []
    seen: set[str] = set()
    for statement in statements:
        text = " ".join(_strip_comments(statement).split()).rstrip(";").strip()
        match = _DROP_RE.match(text)
        if match is None:
            raise MigrationError(
                f"{down_name} contains a statement that is not a plain DROP TABLE/INDEX: {text!r}"
            )
        raw_name = match.group("name").strip()
        if "." in raw_name and not raw_name.startswith('"'):
            schema = raw_name.split(".", 1)[0].strip().strip('"[]`').lower()
            if schema != "main":
                raise MigrationError(
                    f"{down_name} targets schema {schema!r}; a reverse may only touch main"
                )
        kind = match.group("kind").lower()
        name = _bare_identifier(raw_name)
        if name not in owned:
            raise MigrationError(
                f"{down_name} would drop {name!r}, which {forward_name} did not create"
            )
        if owned[name] != kind:
            raise MigrationError(
                f"{down_name} would drop {name!r} as a {kind}, but {forward_name} created it as a {owned[name]}"
            )
        if name in seen:
            raise MigrationError(f"{down_name} drops {name!r} more than once")
        seen.add(name)
        drops.append((kind, name))
    return drops


def _verify_reversal(
    plan: ReversalPlan,
    before: dict[str, set[tuple[str, str]]],
    after: dict[str, set[tuple[str, str]]],
) -> None:
    """Post-condition across every schema.

    Two ways to fail: an owned object survived, or a foreign object vanished.
    """
    owned = {("table", name) for name in plan.tables} | {("index", name) for name in plan.indexes}
    for schema, objects in before.items():
        lost = objects - owned - after.get(schema, set())
        if lost:
            raise MigrationError(
                f"reversal of {plan.version} removed objects it did not own in {schema}: {sorted(lost)}"
            )
    remaining = sorted(
        f"{schema}:{name}" for schema, objects in after.items() for kind, name in objects & owned
    )
    if remaining:
        raise MigrationError(f"reversal of {plan.version} left objects behind: {remaining}")


def reversal_plan(
    conn: sqlite3.Connection,
    migrations_dir: str | Path,
    version: int,
    *,
    rollback_dir: str | Path | None = None,
) -> ReversalPlan:
    """Resolve and validate the reverse of one applied migration, without acting."""
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

    provenance = migration_provenance(conn, version)
    if not provenance:
        raise MigrationError(
            f"no object provenance recorded for migration {version}; this database was applied "
            f"before provenance tracking existed, so a safe reverse cannot be derived. "
            f"Audit or rebuild the database instead of reverting."
        )
    owned = {name: kind for kind, name in provenance}
    if not owned:
        raise MigrationError(f"migration {version} is recorded as having created no objects")

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

    drops = _checked_down_statements(down_sql, down.name, owned, recorded.filename)
    tables = tuple(sorted(name for name, kind in owned.items() if kind == "table"))
    indexes = tuple(sorted(name for name, kind in owned.items() if kind == "index"))
    _check_declared_shapes(conn, forward_sql, recorded.filename, tables)

    return ReversalPlan(
        version=version,
        forward_filename=recorded.filename,
        forward_sha256=current,
        down_filename=down.name,
        down_sha256=_sha256(down_sql),
        drops=tuple(drops),
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
    """Reverse exactly one applied migration and drop its bookkeeping rows.

    Every DROP is qualified with ``main``, so an unqualified statement can never reach a
    ``TEMP`` or attached schema. The drops, the post-condition and both bookkeeping
    deletes run in one explicit ``BEGIN IMMEDIATE ... COMMIT``.
    """
    plan = reversal_plan(conn, migrations_dir, version, rollback_dir=rollback_dir)
    before = _all_inventories(conn)

    if conn.in_transaction:
        conn.commit()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for kind, name in plan.drops:
            quoted = name.replace('"', '""')
            conn.execute(f'DROP {kind.upper()} main."{quoted}"')
        _verify_reversal(plan, before, _all_inventories(conn))
        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (plan.version,))
        conn.execute("DELETE FROM schema_objects WHERE version = ?", (plan.version,))
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    return plan.version
