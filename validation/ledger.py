"""Append-only experiment ledger with a hash chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "a4_ledger.jsonl"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(record: dict, path: Path | None = None) -> dict:
    path = path or PATH
    rows = _load(path)
    prev = rows[-1]["record_hash"] if rows else "0" * 64
    body = dict(record, prev_hash=prev)
    body["record_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(body, ensure_ascii=False) + "\n")
    return body


def count(path: Path | None = None) -> int:
    return len(_load(path or PATH))
