"""Gate evaluation against the pre-registered `validation/gates.yaml`.

Parses the locked gate configuration (minimal YAML subset — no third-party
dependency), reads the experiment ledger, and produces the fixed JSON output
contract required by Charter v2.0 section 14:

    { verdict, gates, metrics, config_hash, data_version_hash, seed }

``verdict`` is one of PASS | FAIL | INSUFFICIENT_EVIDENCE and the distinction
between FAIL and INSUFFICIENT_EVIDENCE is enforced here:
- a numeric gate breaching its threshold          -> contributes FAIL
- a gate whose activation condition is unmet      -> contributes INSUFFICIENT
  (never silently treated as pass or fail)
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from validation.metrics import cscv_pbo, deflated_sharpe_ratio

ROOT = Path(__file__).resolve().parents[1]
GATES_PATH = ROOT / "validation" / "gates.yaml"

VERDICTS = ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE")


def load_gates(path=None) -> dict:
    """Parse the flat two-level YAML structure used by gates.yaml."""
    path = Path(path) if path else GATES_PATH
    text = path.read_text(encoding="utf-8")
    gates: dict = {}
    current = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        value = value.strip().strip('"')
        if indent == 0:
            if value == "":
                gates[key] = {}
                current = key
            else:
                gates[key] = _coerce(value)
                current = None
        else:
            if current is None:
                raise ValueError(f"malformed gates.yaml near: {raw!r}")
            gates[current][key] = _coerce(value)
    return gates


def _coerce(value: str):
    if value in ("null", "~", ""):
        return None
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def config_hash(path=None) -> str:
    path = Path(path) if path else GATES_PATH
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_dsr(records: list[dict], metrics_by_seq: dict[int, dict]) -> float | None:
    """Deflated Sharpe Ratio of the best trial over all ledger trials.

    Uses per-trade Sharpe ratios recorded by the A3 runners (same units across
    trials) and the extreme-value benchmark derived from their spread — no
    external constant is invented (see validation.metrics.deflated_sharpe_ratio).
    Returns ``None`` when fewer than 2 usable Sharpes exist.
    """
    sharpes = []
    for r in records:
        s = metrics_by_seq.get(r["seq"], {}).get("sharpe")
        if s is not None:
            sharpes.append(float(s))
    if len(sharpes) < 2:
        return None
    best_idx = max(range(len(sharpes)), key=lambda i: sharpes[i])
    dsr = deflated_sharpe_ratio(sharpes, candidate_index=best_idx)
    return None if dsr is None else round(dsr, 6)


def compute_pbo(records: list[dict], metrics_by_seq: dict[int, dict],
                groups: int = 8):
    """CSCV-PBO estimated at STRATEGY level over the full pre-registered grid.

    Each ledger cell (strategy) contributes one row; its per-trade PnL is cut
    into ``groups`` contiguous time slices and scored by profit factor per
    slice — this is exactly the CSCV input shape (Bailey et al. 2016). The
    runner recomputes each cell deterministically from the same CSV with the
    same engine semantics as scripts/a3_grid.py / a3_breakout.py.

    Returns ``None`` when fewer than 2 usable strategies exist or the trade
    sample cannot fill ``groups`` slices (gate stays INSUFFICIENT — never
    fabricates an estimate).
    """
    import os
    csv_path = os.environ.get("A3_CSV_PATH")
    if not csv_path or not Path(csv_path).is_file():
        return None
    profile_path = os.environ.get("A3_PROFILE_PATH")

    from xauusd_research.backtest import Backtester  # noqa: E402
    from xauusd_research.costs import BrokerProfile  # noqa: E402
    from xauusd_research.schema import iter_candles  # noqa: E402

    profile = BrokerProfile.load(profile_path) if profile_path else None
    candles = list(iter_candles(Path(csv_path)))

    score_rows: list[list[float]] = []
    for r in records:
        params = r.get("params") or {}
        window_a = params.get("window_a") or params.get("entry_window")
        window_b = params.get("window_b") or params.get("exit_window")
        if not window_a or not window_b:
            continue
        bt = Backtester(f"{r['strategy']}-pbo", int(window_a), int(window_b),
                        trend_window=params.get("trend_window"),
                        profile=profile)
        for candle in candles:
            bt.feed(candle)
        result = bt.finish()
        pnls = [t.pnl for t in result.trades]
        if len(pnls) < 2 * groups:
            continue  # too few trades to support the CSCV partition
        per = len(pnls) // groups
        trimmed = pnls[:per * groups]
        row = []
        for g in range(groups):
            chunk = trimmed[g * per:(g + 1) * per]
            wins = sum(p for p in chunk if p > 0)
            losses = -sum(p for p in chunk if p < 0)
            row.append(wins / losses if losses > 0 else (float("inf") if wins > 0 else 0.0))
        score_rows.append(row)

    if len(score_rows) < 2:
        return None
    result = cscv_pbo(score_rows, groups=groups)
    if isinstance(result, dict):
        result["scope"] = "strategy_level_over_preregistered_grid"
    return result


def evaluate(ledger_records: list[dict], metrics_by_seq: dict[int, dict],
             families: set[str], gates: dict | None = None,
             data_version_hash: str | None = None, seed: int | None = None) -> dict:
    """Apply the locked decision rules to ledger evidence.

    ``metrics_by_seq`` maps ledger ``seq`` to computed metric block containing
    at least ``sharpe``, ``pf_lower_ci`` (bootstrap lower bound) when available.
    """
    gates = gates or load_gates()
    n = len(ledger_records)
    out_gates: dict = {}
    reasons_fail: list[str] = []
    reasons_insufficient: list[str] = []

    # Compute DSR/PBO directly from ledger evidence when stored metrics are
    # absent (runners record per-cell metrics only; the deflation/CSCV math is
    # a gate-level concern). Computed values are reported, never fabricated:
    # None keeps the gate INSUFFICIENT.
    dsr_computed = compute_dsr(ledger_records, metrics_by_seq)
    pbo_computed = compute_pbo(ledger_records, metrics_by_seq)

    dsr_cfg = gates.get("dsr", {})
    dsr_threshold = dsr_cfg.get("activation_threshold", 10)
    if n >= dsr_threshold and dsr_cfg.get("status", "").startswith("INACTIVE"):
        reasons_insufficient.append(
            "dsr status in gates.yaml is INACTIVE but N>=threshold; DEC + rehash pending")
    if n < dsr_threshold:
        out_gates["dsr"] = {"status": "INACTIVE_N_TOO_SMALL", "n": n,
                            "threshold": dsr_threshold}
        reasons_insufficient.append(f"DSR: N={n} < {dsr_threshold}")
    else:
        values = [m.get("dsr") for m in metrics_by_seq.values() if m.get("dsr") is not None]
        min_allowed = dsr_cfg.get("min_allowed", 0.95)
        best = max(values) if values else dsr_computed
        if best is None:
            reasons_insufficient.append("DSR: no deflated Sharpe computable from ledger")
            out_gates["dsr"] = {"status": "MISSING_METRIC", "n": n}
        else:
            ok = best >= min_allowed
            out_gates["dsr"] = {"status": "ACTIVE", "best": best,
                                "min_allowed": min_allowed, "pass": ok,
                                "source": "stored_metrics" if values else "gate_computed"}
            if not ok:
                reasons_fail.append(f"DSR best {best:.4f} < {min_allowed}")

    pbo_cfg = gates.get("pbo", {})
    pbo_threshold = pbo_cfg.get("activation_threshold", 2)
    if len(families) < pbo_threshold:
        out_gates["pbo"] = {"status": "INACTIVE_M_LESS_THAN_2", "families": sorted(families),
                            "threshold": pbo_threshold}
        reasons_insufficient.append(f"PBO: M={len(families)} < {pbo_threshold}")
    else:
        pbo_values = [m.get("pbo") for m in metrics_by_seq.values() if m.get("pbo") is not None]
        max_allowed = pbo_cfg.get("max_allowed", 0.20)
        computed = pbo_computed.get("pbo") if isinstance(pbo_computed, dict) else None
        worst = max(pbo_values) if pbo_values else computed
        if worst is None:
            reasons_insufficient.append("PBO: no CSCV estimate computable from ledger")
            out_gates["pbo"] = {"status": "MISSING_METRIC", "families": sorted(families)}
        else:
            ok = worst <= max_allowed
            out_gates["pbo"] = {"status": "ACTIVE", "worst": worst,
                                "max_allowed": max_allowed, "pass": ok,
                                "source": "stored_metrics" if pbo_values else "gate_computed_cscv_family_level"}
            if not ok:
                reasons_fail.append(f"PBO worst {worst:.4f} > {max_allowed}")

    oos_cfg = gates.get("oos", {})
    if oos_cfg.get("status") == "DEFERRED_NO_VALID_OOS" or not oos_cfg.get("pristine_range"):
        out_gates["oos"] = {"status": "DEFERRED_NO_VALID_OOS"}
        reasons_insufficient.append("OOS: no pristine range registered")
    else:
        out_gates["oos"] = {"status": str(oos_cfg.get("status"))}

    boot_cfg = gates.get("bootstrap", {})
    ci_values = [m.get("pf_lower_ci") for m in metrics_by_seq.values()
                 if m.get("pf_lower_ci") is not None]
    if not ci_values:
        out_gates["bootstrap"] = {"status": "MISSING_METRIC",
                                  "decision_rule": boot_cfg.get("decision_rule")}
        reasons_insufficient.append("bootstrap: no PF lower CI supplied")
    else:
        rule = boot_cfg.get("decision_rule", "lower_ci_bound")
        best_lb = max(ci_values)
        ok = best_lb > 1.0
        out_gates["bootstrap"] = {"status": "ACTIVE", "rule": rule,
                                  "best_pf_lower_ci": best_lb, "pass": ok}
        if not ok:
            reasons_fail.append(f"bootstrap: best PF lower CI {best_lb:.4f} <= 1.0")

    if reasons_fail:
        verdict = "FAIL"
    elif reasons_insufficient:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "gates": out_gates,
        "metrics": metrics_by_seq,
        "config_hash": config_hash(),
        "data_version_hash": data_version_hash,
        "seed": seed,
        "fail_reasons": reasons_fail,
        "insufficient_reasons": reasons_insufficient,
        "ledger_records": n,
    }


def render(report: dict, out_path) -> None:
    Path(out_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")


def metrics_by_seq_from_ledger(records):
    """Extract the per-seq metric blocks stored by the A3 grid runners."""
    return {r["seq"]: dict(r.get("metrics", {})) for r in records}


def families_from_ledger(records):
    return {r.get("family") for r in records if r.get("family")}


def build_report_from_ledger(ledger, data_version_hash=None, seed=None):
    """Full contract report from an experiment ledger (Charter v2.0 s.14)."""
    records = ledger.records()
    return evaluate(records, metrics_by_seq_from_ledger(records),
                    families_from_ledger(records),
                    data_version_hash=data_version_hash, seed=seed)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate gates against a ledger")
    parser.add_argument("--ledger", required=True, help="path to experiments.jsonl")
    parser.add_argument("--out", default=None, help="write JSON report here")
    args = parser.parse_args()

    from validation.ledger import Ledger

    report = build_report_from_ledger(Ledger(args.ledger))
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        render(report, args.out)
    print(text)
