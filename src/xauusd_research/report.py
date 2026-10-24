"""Output writers and hashing helpers."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_trades(result, path):
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["entry_time", "exit_time", "entry_price", "exit_price", "pnl", "bars", "reason"])
        for trade in result.trades:
            writer.writerow([trade.entry_time.isoformat(), trade.exit_time.isoformat(),
                             trade.entry_price, trade.exit_price, trade.pnl, trade.bars, trade.reason])
    return path


def write_summary(result, report, path, input_path):
    payload = {
        "strategy": result.spec.name,
        "fast": result.spec.fast,
        "slow": result.spec.slow,
        "cost_label": result.label,
        "rows": report.rows,
        "gaps": report.gaps,
        "issues": [{"code": i.code, "message": i.message, "row": i.row} for i in report.issues],
        "metrics": result.metrics,
        "input_sha256": sha256_file(input_path),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return Path(path)


def write_manifest(inputs, outputs, path):
    payload = {
        "inputs": [{"path": str(p), "sha256": sha256_file(p)} for p in inputs],
        "outputs": [{"path": str(p), "sha256": sha256_file(p)} for p in outputs],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return Path(path)