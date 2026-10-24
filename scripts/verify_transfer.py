#!/usr/bin/env python3
"""Verify that legacy/source matches docs/TRANSFER_RECORD.md byte-for-byte."""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "TRANSFER_RECORD.md"
ARCHIVE = ROOT / "legacy" / "source"
ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*([0-9a-f]{64})\s*\|$", re.M)


def main() -> int:
    if not RECORD.is_file():
        print("FAIL: missing", RECORD)
        return 1
    rows = ROW.findall(RECORD.read_text(encoding="utf-8"))
    if not rows:
        print("FAIL: no hash rows found in", RECORD)
        return 1

    failures = 0
    for rel, size, expected in rows:
        path = ARCHIVE / rel
        if not path.is_file():
            print("MISSING", rel)
            failures += 1
            continue
        data = path.read_bytes()
        if len(data) != int(size):
            print("SIZE  %s: %d != %s" % (rel, len(data), size))
            failures += 1
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            print("HASH  %s: %s != %s" % (rel, digest, expected))
            failures += 1

    print("%d files checked, %d failure(s)" % (len(rows), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())