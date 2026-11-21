"""Connection pragmas: WAL plus SQLite's default FULL synchronous (D-020).

F-1: the tree briefly carried ``PRAGMA synchronous = NORMAL`` with no decision record.
It was reverted on 2026-11-20. With WAL, NORMAL keeps the file consistent but can lose
the last committed transaction on power/OS failure, which contradicts the ledger and
published-signal contracts. Do not reintroduce it without a recorded decision.
"""

from guardian.storage.db import connect


def test_wal_and_default_synchronous(tmp_path):
    conn = connect(tmp_path / "pragmas.sqlite3")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # 2 == FULL (SQLite default)


def test_synchronous_contract_holds_for_every_new_connection(tmp_path):
    """F-1 regression: no connection may downgrade durability."""
    for name in ("a.sqlite3", "b.sqlite3", "c.sqlite3"):
        conn = connect(tmp_path / name)
        try:
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2, name
        finally:
            conn.close()
