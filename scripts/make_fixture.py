"""Generate a deterministic synthetic 500-candle fixture (not market data)."""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(20261025)


def main():
    price = 1800.0
    stamp = datetime(2024, 1, 1, 0, 0)
    rows = []
    for _ in range(500):
        open_ = price
        close = open_ + random.uniform(-1.2, 1.2)
        high = max(open_, close) + random.uniform(0.0, 0.8)
        low = min(open_, close) - random.uniform(0.0, 0.8)
        rows.append((stamp, open_, high, low, close))
        price = close
        stamp += timedelta(minutes=1)
    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_500.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL", "VOL", "SPREAD"])
        for stamp, o, h, l, c in rows:
            writer.writerow([stamp.strftime("%Y.%m.%d"), stamp.strftime("%H:%M:%S"),
                             f"{o:.5f}", f"{h:.5f}", f"{l:.5f}", f"{c:.5f}", "10", "0", "20"])
    print("fixture written:", out)


if __name__ == "__main__":
    main()