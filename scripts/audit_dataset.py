"""Read-only audit of a market-data CSV (streaming, no modification)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

REQUIRED = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"]
OPTIONAL = ["TICKVOL", "VOL", "SPREAD"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    path = Path(args.csv)
    if not path.is_file():
        print("ERROR: file not found", path)
        return 2

    stats = {
        "file": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": 0,
        "header": [],
        "column_mismatch": 0,
        "numeric_errors": 0,
        "ohlc_errors": 0,
        "non_positive_price": 0,
        "duplicate_time": 0,
        "out_of_order": 0,
        "zero_volume": 0,
        "zero_tickvol": 0,
        "zero_spread": 0,
        "negative_spread": 0,
        "first_time": None,
        "last_time": None,
        "min_low": None,
        "max_high": None,
        "per_year": {},
        "gaps_gt_60s": 0,
        "gaps_gt_12h": 0,
        "largest_gaps": [],
    }
    largest = []
    prev = None
    expected_cols = None
    deltas = {}

    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        first = fh.readline()
        delimiter = "\t" if first.count("\t") > first.count(",") else ","
        stats["delimiter"] = "TAB" if delimiter == "\t" else "COMMA"
        fh.seek(0)
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader, None)
        if header is None:
            print("ERROR: empty file")
            return 2
        header = [h.strip().strip("<>").upper() for h in header]
        stats["header"] = header
        expected_cols = len(header)
        idx = {name: header.index(name) for name in REQUIRED if name in header}
        if len(idx) != len(REQUIRED):
            print("ERROR: missing columns", [c for c in REQUIRED if c not in header])
            return 2
        opt = {name: header.index(name) for name in OPTIONAL if name in header}

        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            stats["rows"] += 1
            if len(row) != expected_cols:
                stats["column_mismatch"] += 1
                continue
            try:
                d = row[idx["DATE"]]
                t = row[idx["TIME"]]
                stamp = datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]),
                                 int(t[0:2]), int(t[3:5]), int(t[6:8]))
                o = float(row[idx["OPEN"]]); h = float(row[idx["HIGH"]])
                l = float(row[idx["LOW"]]); c = float(row[idx["CLOSE"]])
            except (ValueError, IndexError):
                stats["numeric_errors"] += 1
                continue

            if stats["first_time"] is None:
                stats["first_time"] = stamp.isoformat(sep=" ")
            stats["last_time"] = stamp.isoformat(sep=" ")
            stats["per_year"][str(stamp.year)] = stats["per_year"].get(str(stamp.year), 0) + 1

            if min(o, h, l, c) <= 0:
                stats["non_positive_price"] += 1
            if h < max(o, c) or l > min(o, c) or h < l:
                stats["ohlc_errors"] += 1
            stats["min_low"] = l if stats["min_low"] is None else min(stats["min_low"], l)
            stats["max_high"] = h if stats["max_high"] is None else max(stats["max_high"], h)

            if "TICKVOL" in opt and float(row[opt["TICKVOL"]] or 0) == 0:
                stats["zero_tickvol"] += 1
            if "VOL" in opt and float(row[opt["VOL"]] or 0) == 0:
                stats["zero_volume"] += 1
            if "SPREAD" in opt:
                spread = float(row[opt["SPREAD"]] or 0)
                if spread == 0:
                    stats["zero_spread"] += 1
                if spread < 0:
                    stats["negative_spread"] += 1

            if prev is not None:
                delta = (stamp - prev).total_seconds()
                if delta == 0:
                    stats["duplicate_time"] += 1
                elif delta < 0:
                    stats["out_of_order"] += 1
                else:
                    deltas[int(delta)] = deltas.get(int(delta), 0) + 1
                    if delta > 60:
                        stats["gaps_gt_60s"] += 1
                    if delta > 43200:
                        stats["gaps_gt_12h"] += 1
                    if len(largest) < 10 or delta > largest[0][0]:
                        largest.append((delta, prev.isoformat(sep=" "), stamp.isoformat(sep=" ")))
                        largest.sort(reverse=True)
                        del largest[10:]
            prev = stamp

    stats["largest_gaps"] = [
        {"seconds": int(s), "from": a, "to": b} for s, a, b in sorted(largest, reverse=True)
    ]
    stats["bar_interval_mode"] = max(deltas, key=deltas.get) if deltas else None

    md = [
        "# گزارش ممیزی دیتاست (خواندن فقط)",
        "",
        f"- فایل: `{stats['file']}`",
        f"- حجم: {stats['bytes']:,} بایت",
        f"- SHA-256: `{stats['sha256']}`",
        f"- تعداد ردیف داده: {stats['rows']:,}",
        f"- بازه: {stats['first_time']} تا {stats['last_time']}",
        f"- ستون‌ها: {', '.join(stats['header'])}",
        "",
        "## یکپارچگی",
        "",
        "| بررسی | تعداد |",
        "|---|---|",
        f"| ستون ناهماهنگ | {stats['column_mismatch']} |",
        f"| مقدار عددی نامعتبر | {stats['numeric_errors']} |",
        f"| OHLC ناسازگار | {stats['ohlc_errors']} |",
        f"| قیمت ≤ ۰ | {stats['non_positive_price']} |",
        f"| زمان تکراری | {stats['duplicate_time']} |",
        f"| ترتیب معیوب | {stats['out_of_order']} |",
        f"| SPREAD منفی | {stats['negative_spread']} |",
        "",
        "## مقادیر صفر",
        "",
        "| ستون | تعداد صفر |",
        "|---|---|",
        f"| TICKVOL | {stats['zero_tickvol']:,} |",
        f"| VOL | {stats['zero_volume']:,} |",
        f"| SPREAD | {stats['zero_spread']:,} |",
        "",
        "## شکاف‌های زمانی",
        "",
        f"- فاصلهٔ غالب بین کندل‌ها: {stats['bar_interval_mode']} ثانیه",
        f"- شکاف > ۶۰ ثانیه: {stats['gaps_gt_60s']:,}",
        f"- شکاف > ۱۲ ساعت: {stats['gaps_gt_12h']:,}",
        "",
        "| مدت (ثانیه) | از | تا |",
        "|---|---|---|",
    ]
    for gap in stats["largest_gaps"]:
        md.append(f"| {gap['seconds']:,} | {gap['from']} | {gap['to']} |")
    md += ["", "## توزیع سالانه", "", "| سال | ردیف |", "|---|---|"]
    for year in sorted(stats["per_year"]):
        md.append(f"| {year} | {stats['per_year'][year]:,} |")
    md += ["", "## محدودهٔ قیمت", "",
           f"- کمترین Low: {stats['min_low']}", f"- بیشترین High: {stats['max_high']}", "",
           "## محدودیت‌ها", "",
           "- این گزارش فقط کیفیت ساختاری فایل را می‌سنجد؛ منشأ، مجوز انتشار و منطقهٔ زمانی مبدأ را تأیید نمی‌کند.",
           "- فایل تغییر داده نشد (فقط خوانده شد)."]

    Path(args.md).write_text("\n".join(md) + "\n", encoding="utf-8")
    Path(args.json).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print("rows", stats["rows"], "dups", stats["duplicate_time"], "ooo", stats["out_of_order"])
    print("gaps>60s", stats["gaps_gt_60s"], "gaps>12h", stats["gaps_gt_12h"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())