"""Write a hash-chained approval record under approvals/.

A hash proves the record was not edited afterwards. It does NOT prove human
identity — never describe these records as cryptographic signatures.

Usage:
    python scripts/record_approval.py --id A-01 ^
        --action "create project workspace" --scope "xauusd-guardian/**" ^
        --phase 1 --approver "icFixer.ir (human, AutoClaw chat)" --expires none
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.audit.evidence import sha256_text  # noqa: E402

APPROVALS = ROOT / "approvals"


def _previous_hash() -> str:
    existing = sorted(APPROVALS.glob("A-*.json"))
    if not existing:
        return "GENESIS"
    last = json.loads(existing[-1].read_text(encoding="utf-8"))
    return last["record_sha256"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--expires", default="none")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    APPROVALS.mkdir(exist_ok=True)
    target = APPROVALS / f"{args.id}.json"
    if target.exists():
        print(f"refusing to overwrite existing approval: {target}")
        return 1

    body = {
        "approval_id": args.id,
        "action": args.action,
        "scope": args.scope,
        "phase": args.phase,
        "granted_utc": datetime.now(timezone.utc).isoformat(),
        "approver": args.approver,
        "expires": args.expires,
        "note": args.note,
        "prev_sha256": _previous_hash(),
    }
    body["record_sha256"] = sha256_text(json.dumps(body, sort_keys=True))
    target.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {target}")
    print(f"record_sha256={body['record_sha256']}")
    print(f"prev_sha256={body['prev_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
