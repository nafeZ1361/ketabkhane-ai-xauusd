"""Fail when the repository tracks data/archives or oversized files."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
FORBIDDEN = {".csv", ".tsv", ".rar", ".zip", ".7z"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    violations = []
    for rel in tracked_files():
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in FORBIDDEN:
            violations.append(f"forbidden type: {rel}")
        elif path.stat().st_size > MAX_BYTES:
            violations.append(f"too large ({path.stat().st_size} bytes): {rel}")
    for item in violations:
        print("VIOLATION", item)
    print("tracked files:", len(tracked_files()), "violations:", len(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
