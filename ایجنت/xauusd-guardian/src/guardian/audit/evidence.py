"""Evidence helpers: hashes and run manifests.

A hash proves integrity, never human identity.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_run_manifest(
    directory: str | Path,
    *,
    name: str,
    payload: Mapping[str, Any],
) -> Path:
    """Write an immutable run manifest and return its path."""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record.setdefault("created_utc", utc_iso())
    record["manifest_sha256"] = sha256_text(json.dumps(record, sort_keys=True, default=str))

    path = target_dir / name
    if path.exists():
        raise FileExistsError(f"manifest already exists, refusing to overwrite: {path}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return path
