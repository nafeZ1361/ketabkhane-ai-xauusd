"""Attempt 3: slower MAs and a trend-regime filter, evaluated in one pass."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xauusd_research.schema import iter_candles  # noqa: E402
from xauusd_research.strategies import StrategySpec  # noqa: E402
from xauusd_research.stream import StreamingBacktester  # noqa: E402

CSV = ROOT / "data" / "XAUUSD_M1_201610030100_202610092354.csv"
OUT = ROOT / "artifacts" / "sweep_attempt3"
SPREADS = (20, 30, 42)
POINT_COST = 0.01

CANDIDATES = [
    ("ma_50_200", StrategySpec("ma_50_200", 50, 200), None),
    ("ma_100_400", StrategySpec("ma_100_400", 100, 400), None),
    ("ma_50_200_t500", StrategySpec("ma_50_200", 50, 200), 500),
    ("ma_100_400_t500", StrategySpec("ma_100_400", 100, 400), 500),
    ("ma_20_100_t500", StrategySpec("ma_20_100", 20, 100), 500),
]


def key(name, trend):
    return name if trend is None else f"{name}_t{trend}"


def main() -> int:
    engines = {}
    for name, spec, trend in CANDIDATES:
        engines[key(name, trend)] = StreamingBacktester(spec, None, trend)

    rows = 0
    for candle in iter_candles(CSV):
        rows += 1
        for engine in engines.values():
            engine.feed(candle)

    results = []
    for name, spec, trend in CANDIDATES:
        label = key(name, trend)
        result = engines[label].finish()
        n = len(result.trades)
        gross = round(sum(t.pnl for t in result.trades), 2)
        row = {"candidate": label, "trades": n, "gross_usd": gross}
        for spread in SPREADS:
            row[f"net_s{spread}"] = round(gross - n * spread * POINT_COST, 2)
        row["break_even_spread"] = round(gross / (n * POINT_COST), 3) if n else None
        results.append(row)
        print(label, "trades", n, "gross", gross, "net20", row["net_s20"],
              "net30", row["net_s30"], "be", row["break_even_spread"])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sweep.json").write_text(json.dumps({"rows": rows, "results": results}, indent=2), encoding="utf-8")
    print("rows", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())