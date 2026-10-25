"""Local HTTP server exposing read-only project state (stdlib only).

Security model:
- binds to 127.0.0.1 only
- read-only: no upload, no command execution, no writes
- returns JSON only
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import __version__

API_VERSION = "1.0"
DEFAULT_ROOT = Path(__file__).resolve().parents[3]
AUDIT_REL = Path("docs") / "evidence" / "data_audit.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value):
    """Audit file stores naive server time; expose it as explicit UTC-naive marker."""
    if not value:
        return None
    return str(value).replace(" ", "T")


def build_quality_payload(root: Path) -> dict:
    audit_path = Path(root) / AUDIT_REL
    if not audit_path.is_file():
        raise FileNotFoundError(str(audit_path))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    return {
        "api_version": API_VERSION,
        "source": {"path": str(AUDIT_REL).replace("\\", "/"), "sha256": sha256_file(audit_path)},
        "dataset": {
            "path": audit.get("file"),
            "sha256": audit.get("sha256"),
            "bytes": audit.get("bytes"),
            "rows": audit.get("rows"),
            "columns": audit.get("header"),
            "time_reference": "SERVER_TIME_NAIVE",
            "first_time": _iso(audit.get("first_time")),
            "last_time": _iso(audit.get("last_time")),
            "per_year": audit.get("per_year", {}),
        },
        "integrity": {
            "column_mismatch": audit.get("column_mismatch"),
            "numeric_errors": audit.get("numeric_errors"),
            "ohlc_errors": audit.get("ohlc_errors"),
            "non_positive_price": audit.get("non_positive_price"),
            "duplicate_time": audit.get("duplicate_time"),
            "out_of_order": audit.get("out_of_order"),
            "negative_spread": audit.get("negative_spread"),
        },
        "zeros": {
            "tickvol": audit.get("zero_tickvol"),
            "volume": audit.get("zero_volume"),
            "spread": audit.get("zero_spread"),
        },
        "gaps": {
            "bar_interval_seconds": audit.get("bar_interval_mode"),
            "greater_than_60s": audit.get("gaps_gt_60s"),
            "greater_than_12h": audit.get("gaps_gt_12h"),
            "largest": audit.get("largest_gaps", []),
        },
        "price_range": {"min_low": audit.get("min_low"), "max_high": audit.get("max_high")},
    }


def health_payload(root: Path) -> dict:
    audit_path = Path(root) / AUDIT_REL
    return {
        "api_version": API_VERSION,
        "status": "ok",
        "service": "xauusd-research-ui",
        "package_version": __version__,
        "time_utc": utc_now(),
        "checks": {
            "data_audit_present": audit_path.is_file(),
            "root": str(Path(root)),
        },
    }


def _error(status: int, code: str, message: str) -> dict:
    return {"api_version": API_VERSION, "error": {"status": status, "code": code, "message": message}}


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "xauusd-research-ui/" + __version__
        sys_version = ""

        def log_message(self, fmt, *args):  # keep the console quiet during tests
            return

        def _send(self, status: int, payload: dict):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path == "/health":
                self._send(200, health_payload(root))
            elif path == "/quality":
                try:
                    self._send(200, build_quality_payload(root))
                except FileNotFoundError:
                    self._send(503, _error(503, "AUDIT_MISSING", "docs/evidence/data_audit.json not found"))
            else:
                self._send(404, _error(404, "NOT_FOUND", f"no route for GET {path}"))

        def do_POST(self):
            self._send(405, _error(405, "METHOD_NOT_ALLOWED", "this API is read-only"))

        do_PUT = do_DELETE = do_PATCH = do_POST

    return Handler


def create_server(root=None, host="127.0.0.1", port=0) -> ThreadingHTTPServer:
    root = Path(root) if root is not None else DEFAULT_ROOT
    server = ThreadingHTTPServer((host, port), make_handler(root))
    return server