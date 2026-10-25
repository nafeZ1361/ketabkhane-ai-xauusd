"""Compute and store the SHA-256 of validation/gates.yaml (config_hash)."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    config = ROOT / "validation" / "gates.yaml"
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    (ROOT / "validation" / "gates.sha256").write_text(digest + "\n", encoding="utf-8")
    print("config_hash", digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())