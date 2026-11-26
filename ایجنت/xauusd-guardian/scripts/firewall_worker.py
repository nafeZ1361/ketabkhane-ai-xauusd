"""Minimal bootstrap for the fixed-purpose F4 Windows worker."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if sys.platform != "win32":
        return 2
    if len(sys.argv) != 5 or sys.argv[1] != "--key-handle" or sys.argv[3] != "--session-id":
        return 2
    try:
        key_handle = int(sys.argv[2], 10)
    except ValueError:
        return 2
    session_id = sys.argv[4]
    if key_handle <= 0 or len(session_id) != 64:
        return 2
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "src"))
    from guardian.firewall.worker import worker_main

    return worker_main(key_handle, session_id)


if __name__ == "__main__":
    raise SystemExit(main())
