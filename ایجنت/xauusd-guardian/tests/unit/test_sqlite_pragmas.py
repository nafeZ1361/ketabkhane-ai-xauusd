"""Connection pragmas: WAL plus NORMAL synchronous (Stage 3b)."""

from guardian.storage.db import connect


def test_wal_and_normal_synchronous(tmp_path):
    conn = connect(tmp_path / "pragmas.sqlite3")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # 1 == NORMAL
