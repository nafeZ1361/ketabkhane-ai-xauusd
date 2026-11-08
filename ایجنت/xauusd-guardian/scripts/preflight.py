"""Read-only environment gate.

Attaches to the already-running terminal, verifies the approved identity,
resolves the gold symbol, and writes an evidence manifest. It never sends an
order and never reads balance, equity, margin or profit.

Exit codes: 0 = PASS (symbol VERIFIED), 1 = FAIL (connection/environment), 2 = BLOCKED.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.application.symbol_service import build_resolver_service  # noqa: E402
from guardian.audit.evidence import sha256_text  # noqa: E402
from guardian.config.settings import APPROVED_TERMINAL_PATH, ConfigError, load_settings  # noqa: E402
from guardian.contracts.schemas import ResolutionStatus  # noqa: E402
from guardian.domain.symbols import IDENTITY_POLICY  # noqa: E402
from guardian.observability.logging_setup import scrub_mapping  # noqa: E402
from guardian.reporting.ranking import format_ranked  # noqa: E402

RESULTS: list[dict[str, str]] = []

STATUS_LABEL = {
    ResolutionStatus.VERIFIED: ("PASS", 0),
    ResolutionStatus.CONNECTION_FAILED: ("FAIL", 1),
}


def record(name: str, status: str, value: str, note: str = "") -> None:
    RESULTS.append({"check": name, "status": status, "value": value, "note": note})
    line = f"{status:<8} {name} = {value}"
    if note:
        line += f"  ({note})"
    print(line, flush=True)


def main() -> int:
    print("XAUUSD Guardian — preflight (read-only)")
    print("=" * 60)

    version = ".".join(str(p) for p in sys.version_info[:3])
    if sys.version_info[:2] == (3, 11):
        record("python", "PASS", version, sys.executable)
    else:
        record("python", "FAIL", version, f"expected 3.11.x, got {sys.executable}")

    try:
        settings = load_settings(ROOT / "configs" / "config.toml")
        record(
            "config",
            "PASS",
            f"schema={settings.schema_version} mode={settings.execution.mode.value}",
            f"policy={settings.execution.symbol_policy}",
        )
    except ConfigError as exc:
        record("config", "FAIL", "invalid", str(exc))
        return 1

    terminal = Path(settings.execution.terminal_path)
    if not terminal.is_file():
        record("terminal_exe", "FAIL", str(terminal), "approved executable missing")
        return 1
    record("terminal_exe", "PASS", str(terminal), f"{terminal.stat().st_size} bytes")
    if APPROVED_TERMINAL_PATH.lower() not in str(terminal).lower():
        record("terminal_approval", "BLOCKED", str(terminal), "path differs from the approved baseline")
        return 2

    from guardian.adapters.mt5_readonly import (  # noqa: E402
        Mt5ReadOnlyAdapter,
        package_version,
    )

    try:
        record("metatrader5", "PASS", package_version())
    except Exception as exc:  # pragma: no cover - environment dependent
        record("metatrader5", "FAIL", "not importable", repr(exc))
        return 1

    adapter = Mt5ReadOnlyAdapter(
        settings.execution.terminal_path,
        require_path_match=settings.execution.require_terminal_path_match,
    )
    service = build_resolver_service(settings, adapter)
    outcome = service.resolve()
    resolution = outcome.resolution

    if outcome.fingerprint:
        record(
            "terminal_attach",
            "PASS",
            str(outcome.fingerprint.get("terminal_path")),
            f"build={outcome.fingerprint.get('build')}",
        )
    else:
        record("terminal_attach", "FAIL", "error", resolution.reason)

    if outcome.identity:
        identity = scrub_mapping(dict(outcome.identity))
        record("account_identity", "PASS", json.dumps(identity, sort_keys=True))

    verdict = 0
    if outcome.account_gate_failed:
        record("account_mode", "BLOCKED", "not DEMO-ready", resolution.reason)
        record("symbol_resolution", "NOT CHECKED", "n/a", "account gate failed first")
        record("spread_points", "NOT CHECKED", "n/a", "account gate failed")
        verdict = 2
    else:
        if outcome.identity and outcome.identity.get("trade_mode") == "DEMO":
            record("account_mode", "PASS", "DEMO", outcome.identity.get("server", ""))

        label, code = STATUS_LABEL.get(resolution.status, ("BLOCKED", 2))
        if resolution.ok and resolution.policy != IDENTITY_POLICY:
            label, code = "BLOCKED", 2
            detail = f"policy {resolution.policy!r} is not gate-eligible"
        else:
            detail = resolution.reason
        if resolution.ranked:
            detail = f"{detail} | top={format_ranked(resolution.ranked)}"
        if resolution.mismatches:
            detail = f"{detail} | {list(resolution.mismatches)}"
        record("symbol_resolution", label, resolution.status.value, detail)

        if resolution.ok and outcome.spread_points:
            record("spread_points", "PASS", str(list(outcome.spread_points)))
        elif resolution.ok:
            record("spread_points", "NOT CHECKED", "n/a", "no samples requested")
        else:
            record("spread_points", "NOT CHECKED", "n/a", "symbol not verified")
        verdict = code

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = {
        "schema_version": 1,
        "kind": "preflight",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "settings_source": str(ROOT / "configs" / "config.toml"),
        "policy": resolution.policy,
        "symbol": {
            "status": resolution.status.value,
            "name": resolution.symbol_name,
            "reason": resolution.reason,
            "mismatches": [list(m) for m in resolution.mismatches],
            "observed": {k: v for k, v in resolution.observed},
            "ranked": format_ranked(resolution.ranked) if resolution.ranked else "",
        },
        "checks": RESULTS,
        "exit_code": verdict,
    }
    evidence["checks_sha256"] = sha256_text(json.dumps(RESULTS, sort_keys=True))

    evidence_dir = ROOT / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    path = evidence_dir / f"preflight-{stamp}.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    print("=" * 60)
    print(f"evidence: {path}")
    print(f"verdict: {'PASS' if verdict == 0 else 'BLOCKED' if verdict == 2 else 'FAIL'}")
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
