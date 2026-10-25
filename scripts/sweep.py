"""Evaluate several MA-crossover specs in a single streaming pass (attempt 2)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xauusd_research.schema import iter_candles  # noqa: E402
from xauusd_research.strategies import StrategySpec  # noqa: E402
from xauusd_research.stream import StreamingBacktester  # noqa: E402

CSV = ROOT / "data" / "XAUUSD_M1_201610030100_202610092354.csv"
OUT = ROOT / "artifacts" / "sweep_attempt2"
SPREADS = (20, 30, 42)
POINT_COST = 0.01  # spread_points * point_size(0.01) * contract(100) * lots(0.01)

SPECS = [
    StrategySpec("ma_5_20", 5, 20),
    StrategySpec("ma_10_50", 10, 50),
    StrategySpec("ma_20_100", 20, 100),
    StrategySpec("ma_50_200", 50, 200),
]


def main() -> int:
    engines = {spec.name: StreamingBacktester(spec) for spec in SPECS}
    rows = 0
    for candle in iter_candles(CSV):
        rows += 1
        for engine in engines.values():
            engine.feed(candle)

    results = []
    for spec in SPECS:
        result = engines[spec.name].finish()
        n = len(result.trades)
        gross = round(sum(t.pnl for t in result.trades), 2)
        row = {"strategy": spec.name, "fast": spec.fast, "slow": spec.slow,
               "trades": n, "gross_usd": gross}
        for spread in SPREADS:
            row[f"net_s{spread}"] = round(gross - n * spread * POINT_COST, 2)
        row["break_even_spread"] = round(gross / (n * POINT_COST), 3) if n else None
        results.append(row)
        print(spec.name, "trades", n, "gross", gross,
              "net20", row["net_s20"], "be_spread", row["break_even_spread"])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sweep.json").write_text(json.dumps({"rows": rows, "results": results}, indent=2), encoding="utf-8")
    print("rows", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())