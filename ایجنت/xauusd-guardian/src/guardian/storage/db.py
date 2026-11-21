"""SQLite access and hash-verified, reversible migrations.

One connection per caller; no global connection object (no hidden global state).

Forward migrations live in ``migrations/``. Their reverses live in
``migrations/rollback/`` and are **never executed here**: :func:`emit_reverse_sql`
validates a reverse and returns the SQL a human must review and run.

Safety model, in layers:

1. ``apply_migrations`` refuses to record a migration whose declared objects already
   exist (adoption would make the ledger claim something it did not do).
2. Every apply records the objects it *actually created*, observed from
   ``sqlite_master`` before and after, in ``schema_objects``. Provenance is measured,
   not parsed.
3. This module performs no destructive DDL. :func:`revert_migration` exists only to
   refuse; the reverse of a migration is a script, not an action.
4. The emitted script may only drop objects recorded as created by that migration, targets
   ``main`` explicitly, and is wrapped in one ``BEGIN IMMEDIATE ... COMMIT`` together with
   the ledger deletes.
5. The script must account for every object the migration created: a down script that
   leaves an owned object behind is refused before a script is produced. An index counts
   as covered when its table is dropped or when it no longer exists.
6. An apply also records an identity token per object (``sqlite_master`` rowid, root
   page, normalised-DDL digest, ``schema_version``). A script is emitted only while the
   first three match, so drift is caught. The token proves *drift*, not *ownership*: a
   dropped object can be re-created with the same rowid, root page and DDL, and every
   signal lives in the same database the operator controls. That is precisely why the
   destructive step is not automated, and why a human runs the script.
7. Scope is ``CREATE TABLE`` and ``CREATE INDEX`` only. A migration containing any other
   ``CREATE`` (view, trigger, TEMP object) or an identifier spelling this parser cannot
   attribute is refused before it runs; it is never recorded and never left
   apply-only.
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
_SCHEMA_PREFIX = r'(?:(?:"[^"]+"|\[[^\]]+\]|`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?'

_CREATE_RE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(?P<kind>TABLE|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?!IF\b)(?P<name>" + _SCHEMA_PREFIX + _IDENT + r")",
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
    """Everything :func:`emit_reverse_sql` has validated before writing a script."""

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
    # synchronous is left at SQLite's default (FULL): the migration ledger and published
    # signals are durability contracts. A NORMAL opt-in is a behaviour change and needs a
    # recorded decision (D-020); it must not be reintroduced silently.
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
    """Drop ``/* ... */`` and ``--`` comments so a keyword check cannot hide behind one."""
    without_blocks = re.sub(r"/\*.*?\*/", " ", statement, flags=re.DOTALL)
    return "\n".join(line.split("--", 1)[0] for line in without_blocks.splitlines()).strip()


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
    # Split off a schema prefix before unquoting, so main.signals, "main".signals
    # and `main`.`signals` all resolve to the bare object name.
    prefix = re.match(r'(?:"[^"]*"|\[[^\]]*\]|`[^`]*`|[A-Za-z_][A-Za-z0-9_]*)\s*\.', value)
    if prefix:
        value = value[prefix.end():].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'`":
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


def _object_identity(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[int, int, str, int]]:
    """Physical identity of every table/index in ``main``, as SQLite can expose it.

    ``(schema rowid, root page, sha256 of the normalised DDL, schema_version)``.
    SQLite has no stable object id: a dropped-and-recreated object can reuse both its
    ``sqlite_master.rowid`` and its root page (measured), so the token is a set of
    independent signals rather than a single key. Ownership is decided by the first
    three; ``schema_version`` is recorded for diagnostics only, because it is global
    and changes on any DDL anywhere, including ``CREATE TEMP TABLE``.
    """
    version = conn.execute("PRAGMA main.schema_version").fetchone()[0]
    found: dict[tuple[str, str], tuple[int, int, str, int]] = {}
    rows = conn.execute(
        "SELECT rowid, type, name, rootpage, sql FROM main.sqlite_master"
    ).fetchall()
    for row in rows:
        kind = row["type"].lower()
        name = row["name"].lower()
        if kind not in {"table", "index"} or name.startswith("sqlite_"):
            continue
        found[(kind, name)] = (
            row["rowid"],
            row["rootpage"],
            _sha256(" ".join((row["sql"] or "").split())),
            version,
        )
    return found


def _recorded_identity(
    conn: sqlite3.Connection, version: int
) -> dict[tuple[str, str], tuple[int, int, str, int]]:
    rows = conn.execute(
        "SELECT kind, name, schema_rowid, rootpage, sql_sha256, schema_version "
        "FROM schema_object_identity WHERE version = ?", (version,)
    ).fetchall()
    return {
        (row["kind"], row["name"]): (
            row["schema_rowid"], row["rootpage"], row["sql_sha256"], row["schema_version"],
        )
        for row in rows
    }


def _check_object_identity(
    conn: sqlite3.Connection,
    version: int,
    owned: dict[str, str],
    forward_name: str,
) -> None:
    """Refuse to drop an object that is not provably the one the migration created.

    A name and a column shape are not ownership: an operator can drop the owned table
    and re-create an identical-shaped one, and SQLite cannot tell the difference by
    name, root page or DDL alone. The apply step therefore records a token, and a script is
    emitted only while every signal still matches. That proves the object has not *drifted*;
    it does not prove ownership, which is why this module drops nothing and a human runs the
    script.
    """
    recorded = _recorded_identity(conn, version)
    if not recorded:
        raise MigrationError(
            f"no object identity recorded for migration {version}; this database was applied "
            f"before identity tracking existed, so ownership of its objects cannot be proven. "
            f"Audit or rebuild the database instead of reverting."
        )

    current = _object_identity(conn)
    for name in sorted(owned):
        kind = owned[name]
        want = recorded.get((kind, name))
        if want is None:
            raise MigrationError(
                f"{forward_name} is recorded as having created {name!r} but no identity token "
                f"was stored for it; refusing to drop an unverifiable object"
            )
        got = current.get((kind, name))
        if got is None:
            # Missing object: leave it to the DROP, inside the transaction (R1).
            continue
        if got[:3] != want[:3]:
            raise MigrationError(
                f"{name!r} is not the {kind} that {forward_name} created: its schema rowid, "
                f"root page or definition changed after the migration was applied. "
                f"Refusing to drop a replacement object."
            )


def _unattributed_create(forward_sql: str, source: str) -> str | None:
    """Return the first ``CREATE`` statement this parser cannot attribute, if any.

    Only ``CREATE TABLE`` and ``CREATE INDEX`` are in scope for S7. A ``CREATE VIEW``,
    ``CREATE TRIGGER``, ``CREATE TEMP`` object, or an identifier spelling the parser
    does not recognise (a single-quoted identifier, for example) must fail closed and
    name the statement. Otherwise it would produce an empty declared set, make the
    adoption and ``missing`` guards vacuous, and be recorded as if it had done work.
    """
    for statement in _split_sql_statements(_strip_comments(forward_sql), source):
        body = statement.strip()
        if not re.match(r"(?is)^CREATE\b", body):
            continue
        if _CREATE_RE.match(body):
            continue
        return " ".join(body.split())[:120]
    return None


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_object_identity (
            version        INTEGER NOT NULL,
            kind           TEXT NOT NULL,
            name           TEXT NOT NULL,
            schema_rowid   INTEGER NOT NULL,
            rootpage       INTEGER NOT NULL,
            sql_sha256     TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
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
        unattributed = _unattributed_create(sql, path.name)
        if unattributed is not None:
            raise MigrationError(
                f"migration {path.name} contains a CREATE this project does not support: "
                f"{unattributed!r}. S7 scope is CREATE TABLE and CREATE INDEX only; views, "
                f"triggers, TEMP objects and identifier spellings the parser cannot attribute "
                f"are refused rather than recorded."
            )
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
            if not created:
                raise MigrationError(
                    f"migration {path.name} created no objects in main; refusing to record a "
                    f"migration that changed nothing. Data-only and TEMP-only migrations are "
                    f"not supported: a migration must create what it declares."
                )
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
            identity = _object_identity(conn)
            conn.executemany(
                "INSERT INTO schema_object_identity (version, kind, name, schema_rowid, "
                "rootpage, sql_sha256, schema_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (version, kind, name) + identity[(kind, name)]
                    for kind, name in sorted(created)
                ],
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
    cleaned = _strip_comments(forward_sql)
    name = re.escape(table)
    declared_name = r'(?:"' + name + r'"|\[?' + name + r'\]?|`' + name + r'`)'
    match = re.search(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + _SCHEMA_PREFIX + declared_name + r"\s*\(",
        cleaned,
        re.IGNORECASE,
    )
    if match is None:
        return ()

    body: list[str] = []
    depth = 1
    for char in cleaned[match.end():]:
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
        schema_prefix = re.match(
            r'(?:"[^"]+"|\[[^\]]+\]|`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)\s*\.', raw_name
        )
        if schema_prefix:
            schema = _bare_identifier(schema_prefix.group(0).rstrip(". "))
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


def _check_foreign_key_dependents(
    conn: sqlite3.Connection,
    tables: tuple[str, ...],
    forward_name: str,
) -> None:
    """Refuse a reverse whose DROP would cascade into rows this migration never created.

    With ``PRAGMA foreign_keys = ON`` a ``DROP TABLE`` performs an implicit
    ``DELETE FROM`` first, so every ``ON DELETE CASCADE`` / ``SET NULL`` / ``SET DEFAULT``
    child loses its rows. Nothing re-checks row loss once a human runs the script, so a
    reverse that could cascade is refused before the script is produced.
    """
    owned = {table.lower() for table in tables}
    if not owned:
        return

    offenders: list[str] = []
    rows = conn.execute(
        "SELECT name FROM main.sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for row in rows:
        child = row["name"]
        if child.lower() in owned:
            continue
        quoted = child.replace('"', '""')
        try:
            keys = conn.execute(f'PRAGMA main.foreign_key_list("{quoted}")').fetchall()
        except sqlite3.DatabaseError:
            continue
        for key in keys:
            parent = (key["table"] or "").lower()
            action = (key["on_delete"] or "NO ACTION").upper()
            if parent in owned and action in {"CASCADE", "SET NULL", "SET DEFAULT"}:
                offenders.append(f"{child} -> {parent} ON DELETE {action}")

    if offenders:
        raise MigrationError(
            f"reverting {forward_name} would drop a table that {sorted(offenders)} "
            f"references with ON DELETE CASCADE/SET NULL/SET DEFAULT; rows this migration did not "
            f"create would be deleted. Drop or detach those tables first."
        )


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
    _check_foreign_key_dependents(conn, tables, recorded.filename)
    _check_declared_shapes(conn, forward_sql, recorded.filename, tables)
    _check_object_identity(conn, version, owned, recorded.filename)

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


def emit_reverse_sql(
    conn: sqlite3.Connection,
    migrations_dir: str | Path,
    version: int,
    *,
    rollback_dir: str | Path | None = None,
) -> str:
    """Validate a reverse and return the SQL a human must review and run.

    This module performs **no destructive DDL**. :func:`reversal_plan` still applies every
    precondition (provenance, identity token, declared shape, foreign-key dependents, down
    script whitelist), so a script is emitted only for a state the library is willing to
    describe. Whether to run it is a human decision, taken outside this program.

    Every DROP is qualified with ``main``, and the bookkeeping deletes are part of the
    same transaction, so the script is self-contained and all-or-nothing.
    """
    plan = reversal_plan(conn, migrations_dir, version, rollback_dir=rollback_dir)

    dropped = {name for _kind, name in plan.drops}
    dropped_tables = {name for kind, name in plan.drops if kind == "table"}
    # An index disappears with its table, so it need not be named in the down script.
    live_index_tables = {
        row["name"].lower(): (row["tbl_name"] or "").lower()
        for row in conn.execute(
            "SELECT name, tbl_name FROM main.sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    owned = set(plan.tables) | set(plan.indexes)
    missing = []
    for name in sorted(owned - set(dropped)):
        if name in plan.indexes:
            table_of_index = live_index_tables.get(name)
            # an index already gone, or one that vanishes with a dropped table,
            # cannot be "left behind"
            if table_of_index is None or table_of_index in dropped_tables:
                continue
        missing.append(name)
    if missing:
        raise MigrationError(
            f"{plan.down_filename} leaves objects behind: {missing}; a reverse script must "
            f"drop every object the migration created, or it is not a reverse."
        )

    lines = [
        f"-- XAUUSD Guardian reverse of {plan.forward_filename} (version {plan.version}).",
        f"-- forward sha256: {plan.forward_sha256}",
        f"-- down    sha256: {plan.down_sha256}",
        "-- REVIEW EVERY STATEMENT. This program will not run them.",
        "BEGIN IMMEDIATE;",
    ]
    for kind, name in plan.drops:
        quoted = name.replace('"', '""')
        lines.append(f'DROP {kind.upper()} main."{quoted}";')
    for table in ("schema_migrations", "schema_objects", "schema_object_identity"):
        lines.append(f"DELETE FROM main.{table} WHERE version = {plan.version};")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def revert_migration(*args: object, **kwargs: object) -> int:
    """Removed: this project no longer reverses migrations automatically.

    The automated path executed destructive DDL after validating ownership from inside the
    same database, and no in-database evidence can prove ownership (a dropped object can be
    re-created with the same schema rowid, root page and DDL). Keeping that path meant a
    reverse could delete a table the migration did not create.

    Use :func:`emit_reverse_sql`, review the script, and run it yourself.
    """
    raise MigrationError(
        "automated reversal has been removed: this tool does not execute destructive DDL. "
        "Call emit_reverse_sql(conn, migrations_dir, version) and review the script before "
        "running it yourself."
    )
