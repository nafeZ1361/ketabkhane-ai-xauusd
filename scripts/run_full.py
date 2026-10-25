"""Run the full dataset in streaming mode and report wall time and peak RSS."""

import ctypes
import ctypes.wintypes as wt
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xauusd_research.cli import run_pipeline  # noqa: E402

CSV = ROOT / "data" / "XAUUSD_M1_201610030100_202610092354.csv"
OUT = ROOT / "artifacts" / "full_run"


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def peak_mb():
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                             ctypes.byref(counters), counters.cb)
    return round(counters.PeakWorkingSetSize / 1024 / 1024, 1)


def main() -> int:
    started = time.perf_counter()
    code, payload = run_pipeline(CSV, OUT, "ma_5_20", "eu-dst", "stream")
    elapsed = time.perf_counter() - started
    print("exit", code, "status", payload.get("status"))
    if code == 0:
        m = payload["metrics"]
        print("mode", payload["mode"], "trades", m["trades"], "net_pnl", m["net_pnl"],
              "win_rate", m["win_rate"], "max_dd", m["max_drawdown"])
    print("elapsed_seconds", round(elapsed, 1))
    print("peak_rss_mb", peak_mb())
    return code


if __name__ == "__main__":
    raise SystemExit(main())