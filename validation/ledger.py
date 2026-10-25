"""Append-only experiment ledger with hash chaining (Charter v2.0, section 14).

Every trial run is recorded as one JSONL line. Each line carries:
- ``seq``          : strictly increasing sequence number
- ``prev_hash``    : SHA-256 hex of the previous record's canonical JSON
                     (genesis record uses 64 zeros)
- ``record_hash``  : SHA-256 hex of this record's canonical JSON
                     (computed over every field except ``record_hash`` itself)

Integrity rules (enforced by :func:`verify`):
1. Records are appended in order; ``seq`` increases by exactly 1.
2. ``prev_hash`` of record n equals ``record_hash`` of record n-1.
3. No rewrite or deletion: removing or editing any line breaks the chain and
   is reported as an integrity failure (acceptance test AT-STAT-05).

This module deliberately has no third-party dependencies so it can be audited
and reproduced anywhere.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS_HASH = "0" * 64


def canonical_json(record: dict) -> str:
    """Deterministic serialization: sorted keys, compact separators, ASCII."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_hash(record: dict) -> str:
    """SHA-256 of the canonical JSON of ``record`` without ``record_hash``."""
    payload = {k: v for k, v in record.items() if k != "record_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class LedgerError(RuntimeError):
    """Raised on any integrity violation of the experiment ledger."""


class Ledger:
    """Hash-chained append-only experiment ledger stored as JSONL."""

    def __init__(self, path):
        self.path = Path(path)

    # ------------------------------------------------------------------ write
    def _read_lines(self) -> list[str]:
        if not self.path.is_file():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return [line for line in handle.read().splitlines() if line.strip()]

    def last_record(self) -> dict | None:
        lines = self._read_lines()
        if not lines:
            return None
        return json.loads(lines[-1])

    def count(self) -> int:
        return len(self._read_lines())

    def append(self, fields: dict) -> dict:
        """Append one immutable record; returns the stored record."""
        if "record_hash" in fields or "prev_hash" in fields or "seq" in fields:
            raise LedgerError("seq, prev_hash and record_hash are managed by the ledger")
        previous = self.last_record()
        seq = 1 if previous is None else previous["seq"] + 1
        prev_hash = GENESIS_HASH if previous is None else previous["record_hash"]
        record = dict(fields)
        record["seq"] = seq
        record["prev_hash"] = prev_hash
        record["record_hash"] = record_hash(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    # ------------------------------------------------------------------ read
    def records(self) -> list[dict]:
        return [json.loads(line) for line in self._read_lines()]

    def verify(self) -> dict:
        """Validate the full hash chain. Returns a report; raises nothing."""
        records = self.records()
        issues: list[str] = []
        expected_prev = GENESIS_HASH
        for position, record in enumerate(records):
            declared = record.get("record_hash")
            recomputed = record_hash(record)
            if declared != recomputed:
                issues.append(
                    f"seq {record.get('seq')} at line {position + 1}: "
                    f"record_hash mismatch (content edited?)")
            if record.get("prev_hash") != expected_prev:
                issues.append(
                    f"seq {record.get('seq')} at line {position + 1}: "
                    f"prev_hash does not match preceding record (deleted or reordered?)")
            expected_prev = recomputed
        if records:
            seqs = [r.get("seq") for r in records]
            if seqs != list(range(1, len(seqs) + 1)):
                issues.append("sequence numbers are not 1..N")
        return {
            "records": len(records),
            "intact": not issues,
            "issues": issues,
            "head_hash": expected_prev,
        }
