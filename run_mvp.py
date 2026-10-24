"""Run the MVP-1 pipeline without installing the package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xauusd_research.cli import main

if __name__ == "__main__":
    raise SystemExit(main())