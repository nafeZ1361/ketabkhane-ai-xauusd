"""Monte Carlo risk report — CLI (D-026).

    python scripts/montecarlo.py --input trades.json --out artifacts/mc \
        --sims 2000 --seed 7 --mode block --block-size 5 \
        --risk 0.01 --ruin 0.5 --cost-multipliers 1,1.5,2,3

Input JSON: either ``{"strategies": {"ma_100_400": [0.5, -1.0, ...]}}`` or a bare
list of R multiples for a single strategy.

Writes ``report.json`` and ``report.md`` into ``--out``. The JSON contains the
input digest, seed, parameters, assumptions, results and its own content digest,
so a run can be reproduced byte-for-byte. No MT5, no account, no orders.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.domain.risk.montecarlo import (  # noqa: E402
    MonteCarloError,
    MonteCarloSpec,
    canonical_digest,
    compare_strategies,
)

ASSUMPTIONS = [
    "trades are re-used, not predicted: the engine samples the observed R multiples only",
    "resampling assumes the observed sample is representative; a regime the sample never saw is invisible",
    "IID mode destroys serial dependence; moving-block mode preserves runs of block_size trades",
    "dynamic sizing risks a fixed fraction of CURRENT equity, so results compound",
    "cost_r is subtracted from every trade as a multiple of the risked amount",
    "ruin is equity <= initial_equity * (1 - ruin_fraction); a path stops there",
    "no slippage model beyond cost_r; no liquidity limits; no guarantee of future behaviour",
]


def _decimal_list(values: object, name: str) -> list[Decimal]:
    if not isinstance(values, list) or not values:
        raise MonteCarloError(f"{name} must be a non-empty list of numbers")
    out: list[Decimal] = []
    for raw in values:
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise MonteCarloError(f"{name} contains a non-numeric value: {raw!r}")
        try:
            out.append(Decimal(str(raw)))
        except InvalidOperation as exc:
            raise MonteCarloError(f"{name} contains an invalid number: {raw!r}") from exc
    return out


def _load(path: Path) -> tuple[dict[str, list[Decimal]], str]:
    raw = path.read_bytes()
    digest = __import__("hashlib").sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if isinstance(payload, dict) and "strategies" in payload:
        strategies = {
            str(name): _decimal_list(values, f"strategies[{name}]")
            for name, values in payload["strategies"].items()
        }
    elif isinstance(payload, dict) and "r_multiples" in payload:
        strategies = {"strategy": _decimal_list(payload["r_multiples"], "r_multiples")}
    elif isinstance(payload, list):
        strategies = {"strategy": _decimal_list(payload, "trades")}
    else:
        raise MonteCarloError("input must be a list, or {strategies|r_multiples: ...}")
    return strategies, digest


def _revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10
        ).stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - git absent
        return "unknown"


def _markdown(report: dict) -> str:
    lines = ["# Monte Carlo risk report", ""]
    lines.append(f"- generated_utc: `{report['generated_utc']}`")
    lines.append(f"- software_revision: `{report['software_revision']}`")
    lines.append(f"- input: `{report['input']['path']}` (sha256 `{report['input']['sha256']}`)")
    lines.append(f"- seed: `{report['parameters']['seed']}` · mode: `{report['parameters']['mode']}` "
                 f"· simulations: `{report['parameters']['simulations']}`")
    lines.append("")
    for multiplier, block in report["results"].items():
        lines.append(f"## Cost multiplier ×{multiplier}")
        lines.append("")
        lines.append("| strategy | ruin freq | mean maxDD | p95 maxDD | p99 maxDD | median final equity |")
        lines.append("|---|---|---|---|---|---|")
        for name, summary in block.items():
            lines.append(
                f"| {name} | {summary['ruin_frequency']} | {summary['mean_max_drawdown']} | "
                f"{summary['p95_max_drawdown']} | {summary['p99_max_drawdown']} | "
                f"{summary['median_final_equity']} |"
            )
        lines.append("")
    lines.append("## Assumptions and limits")
    lines.append("")
    for item in report["assumptions"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"content_sha256: `{report['content_sha256']}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monte Carlo risk report (D-026)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--mode", choices=("iid", "block"), default="block")
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--equity", default="10000")
    parser.add_argument("--risk", default="0.01")
    parser.add_argument("--ruin", default="0.5")
    parser.add_argument("--cost-r", default="0.02")
    parser.add_argument("--cost-multipliers", default="1,1.5,2,3")
    args = parser.parse_args(argv)

    source = Path(args.input)
    strategies, data_digest = _load(source)

    results: dict[str, dict] = {}
    for raw in args.cost_multipliers.split(","):
        multiplier = Decimal(raw.strip())
        spec = MonteCarloSpec(
            simulations=args.sims,
            seed=args.seed,
            mode=args.mode,
            block_size=args.block_size,
            initial_equity=Decimal(args.equity),
            risk_fraction=Decimal(args.risk),
            ruin_fraction=Decimal(args.ruin),
            cost_r=Decimal(args.cost_r),
            cost_multiplier=multiplier,
        )
        summaries = compare_strategies(strategies, spec)
        results[format(multiplier, "f")] = {k: v.as_dict() for k, v in summaries.items()}

    report = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "software_revision": _revision(),
        "input": {"path": str(source), "sha256": data_digest},
        "parameters": {
            "simulations": args.sims,
            "seed": args.seed,
            "mode": args.mode,
            "block_size": args.block_size,
            "equity": args.equity,
            "risk": args.risk,
            "ruin": args.ruin,
            "cost_r": args.cost_r,
            "cost_multipliers": args.cost_multipliers,
        },
        "assumptions": ASSUMPTIONS,
        "results": results,
    }
    report["content_sha256"] = canonical_digest({k: v for k, v in report.items() if k != "generated_utc"})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"content_sha256": report["content_sha256"],
                      "report": str(out / "report.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MonteCarloError as exc:
        print(f"montecarlo: {exc}", file=sys.stderr)
        raise SystemExit(2)
