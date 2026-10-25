"""Detect double-encoded (mojibake) text in repository documents."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"[\u00c3\u00d9]{2,}")
SKIP = {".git", "artifacts", "data", "legacy", "__pycache__", ".venv"}


def main() -> int:
    bad_files = 0
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = PATTERN.findall(text)
        if hits:
            bad_files += 1
            print(f"MOJIBAKE {path.relative_to(ROOT)} hits={len(hits)}")
    print("files with mojibake:", bad_files)
    return 1 if bad_files else 0


if __name__ == "__main__":
    raise SystemExit(main())