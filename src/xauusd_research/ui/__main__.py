"""Run the local UI skeleton: python -m xauusd_research.ui --port 8765"""

from __future__ import annotations

import argparse

from .server import create_server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="xauusd-research-ui")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = create_server(port=args.port)
    host, port = server.server_address[:2]
    print(f"serving on http://{host}:{port}  (read-only, localhost only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())