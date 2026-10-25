"""Local HTTP server: read-only state plus a minimal run launcher (stdlib only).

Security model:
- binds to 127.0.0.1 only
- datasets are restricted to the data/ directory (no traversal)
- profiles are restricted to known config/*.json files
- one process-local queue, no database, no shell execution
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import __version__
from ..cli import run_pipeline
from ..strategies import STRATEGY_BY_NAME

API_VERSION = "1.0"
DEFAULT_ROOT = Path(__file__).resolve().parents[3]
AUDIT_REL = Path("docs") / "evidence" / "data_audit.json"
DATA_SUFFIXES = (".csv", ".tsv", ".txt")
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._\-]+$")
MAX_BODY_BYTES = 8192

RUNS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value):
    if not value:
        return None
    return str(value).replace(" ", "T")


def list_datasets(root: Path) -> list[dict]:
    data_dir = Path(root) / "data"
    if not data_dir.is_dir():
        return []
    items = []
    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in DATA_SUFFIXES:
            items.append({"name": path.name, "bytes": path.stat().st_size})
    return items


def list_profiles(root: Path) -> list[dict]:
    config_dir = Path(root) / "config"
    items = [{"id": "none", "label": "بدون هزینه (NO_TRADING_COSTS)"}]
    if config_dir.is_dir():
        for path in sorted(config_dir.glob("*.json")):
            items.append({"id": f"config/{path.name}", "label": path.stem})
    return items


def resolve_dataset(root: Path, name: str) -> Path:
    if not name or not SAFE_TOKEN.match(name):
        raise ApiError(400, "BAD_DATASET", "dataset name must be a plain file name")
    data_dir = (Path(root) / "data").resolve()
    path = (data_dir / name).resolve()
    if path.parent != data_dir:
        raise ApiError(400, "BAD_DATASET", "dataset must live directly inside data/")
    if not path.is_file():
        raise ApiError(404, "DATASET_NOT_FOUND", f"dataset not found: {name}")
    return path


def resolve_profile(root: Path, profile: str):
    if profile in (None, "", "none"):
        return None
    if not profile.startswith("config/") or not SAFE_TOKEN.match(profile.split("/", 1)[1]):
        raise ApiError(400, "BAD_PROFILE", "profile must be a config/*.json name")
    config_dir = (Path(root) / "config").resolve()
    path = (config_dir / profile.split("/", 1)[1]).resolve()
    if path.parent != config_dir or path.suffix != ".json" or not path.is_file():
        raise ApiError(400, "BAD_PROFILE", f"unknown profile: {profile}")
    return str(path)


def build_quality_payload(root: Path) -> dict:
    audit_path = Path(root) / AUDIT_REL
    if not audit_path.is_file():
        raise ApiError(503, "AUDIT_MISSING", "docs/evidence/data_audit.json not found")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    return {
        "api_version": API_VERSION,
        "source": {"path": str(AUDIT_REL).replace("\\", "/"), "sha256": sha256_file(audit_path)},
        "dataset": {
            "path": audit.get("file"), "sha256": audit.get("sha256"), "bytes": audit.get("bytes"),
            "rows": audit.get("rows"), "columns": audit.get("header"),
            "time_reference": "SERVER_TIME_NAIVE",
            "first_time": _iso(audit.get("first_time")), "last_time": _iso(audit.get("last_time")),
            "per_year": audit.get("per_year", {}),
        },
        "integrity": {key: audit.get(key) for key in (
            "column_mismatch", "numeric_errors", "ohlc_errors", "non_positive_price",
            "duplicate_time", "out_of_order", "negative_spread")},
        "zeros": {"tickvol": audit.get("zero_tickvol"), "volume": audit.get("zero_volume"),
                  "spread": audit.get("zero_spread")},
        "gaps": {"bar_interval_seconds": audit.get("bar_interval_mode"),
                 "greater_than_60s": audit.get("gaps_gt_60s"),
                 "greater_than_12h": audit.get("gaps_gt_12h"),
                 "largest": audit.get("largest_gaps", [])},
        "price_range": {"min_low": audit.get("min_low"), "max_high": audit.get("max_high")},
    }


def health_payload(root: Path) -> dict:
    return {
        "api_version": API_VERSION,
        "status": "ok",
        "service": "xauusd-research-ui",
        "package_version": __version__,
        "time_utc": utc_now(),
        "checks": {"data_audit_present": (Path(root) / AUDIT_REL).is_file(), "root": str(Path(root))},
    }


def _execute_run(root: Path, run_id: str, dataset: Path, strategy: str, profile, trend_window):
    with RUNS_LOCK:
        RUNS[run_id]["status"] = "RUNNING"
        RUNS[run_id]["started_at"] = utc_now()
    out_dir = Path(root) / "artifacts" / "ui_runs" / run_id
    try:
        code, payload = run_pipeline(dataset, out_dir, strategy, "eu-dst", "stream", profile, trend_window)
        with RUNS_LOCK:
            if code == 0:
                RUNS[run_id]["status"] = "COMPLETED"
                RUNS[run_id]["result"] = {
                    "metrics": payload["metrics"], "cost_label": payload["cost_label"],
                    "strategy": payload["strategy"], "elapsed_seconds": payload["elapsed_seconds"],
                    "broker_profile": payload["broker_profile"],
                    "artifacts": {"trades_csv": f"artifacts/ui_runs/{run_id}/trades.csv",
                                  "summary_json": f"artifacts/ui_runs/{run_id}/summary.json",
                                  "manifest_json": f"artifacts/ui_runs/{run_id}/manifest.json"},
                }
            else:
                RUNS[run_id]["status"] = "FAILED"
                RUNS[run_id]["error"] = {"code": "INVALID_DATA", "message": str(payload.get("issues"))}
    except Exception as exc:  # keep the server alive, report the failure
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "FAILED"
            RUNS[run_id]["error"] = {"code": type(exc).__name__, "message": str(exc)}
    finally:
        with RUNS_LOCK:
            RUNS[run_id]["finished_at"] = utc_now()


def start_run(root: Path, body: dict) -> dict:
    dataset_name = str(body.get("dataset") or "")
    strategy = str(body.get("strategy") or "")
    profile_name = body.get("profile", "none")
    trend = body.get("trend_window")
    if strategy not in STRATEGY_BY_NAME:
        raise ApiError(400, "BAD_STRATEGY", f"unknown strategy: {strategy}")
    if trend is not None:
        try:
            trend = int(trend)
        except (TypeError, ValueError):
            raise ApiError(400, "BAD_TREND", "trend_window must be an integer")
        if trend < 2 or trend > 100000:
            raise ApiError(400, "BAD_TREND", "trend_window out of range")
    dataset = resolve_dataset(root, dataset_name)
    profile = resolve_profile(root, profile_name)

    run_id = uuid.uuid4().hex[:12]
    state = {
        "run_id": run_id, "status": "QUEUED", "created_at": utc_now(),
        "started_at": None, "finished_at": None,
        "params": {"dataset": dataset.name, "strategy": strategy,
                   "profile": profile_name or "none", "trend_window": trend},
        "result": None, "error": None,
    }
    with RUNS_LOCK:
        RUNS[run_id] = state
    threading.Thread(target=_execute_run, args=(root, run_id, dataset, strategy, profile, trend),
                     daemon=True).start()
    return state


HTML_PAGE = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>XAUUSD Research UI</title>
<style>
body{font-family:system-ui,Segoe UI,Tahoma,sans-serif;margin:2rem;background:#0f1115;color:#e6e6e6}
select,button{font-size:1rem;padding:.4rem;margin:.3rem 0}
fieldset{max-width:34rem;border:1px solid #333;border-radius:8px;padding:1rem}
pre{background:#141821;padding:1rem;border-radius:8px;overflow:auto;max-height:26rem}
label{display:block;margin-top:.6rem}
</style></head><body>
<h2>اجرای آزمایش</h2>
<fieldset>
<label>فایل داده (data/)<select id="ds">__DATASETS__</select></label>
<label>استراتژی<select id="st">__STRATEGIES__</select></label>
<label>پروفایل هزینه<select id="pr">__PROFILES__</select></label>
<label>فیلتر روند (اختیاری)<input id="tw" type="number" min="2" max="100000" placeholder="500"></label>
<button id="go">اجرا</button>
</fieldset>
<h3>وضعیت</h3><pre id="out">—</pre>
<script>
const $=(id)=>document.getElementById(id);
async function poll(id){
  const r=await fetch('/runs/'+id); const j=await r.json();
  $('out').textContent=JSON.stringify(j,null,2);
  if(j.status==='QUEUED'||j.status==='RUNNING'){setTimeout(()=>poll(id),2000);}
}
$('go').addEventListener('click',async()=>{
  const tw=$('tw').value.trim();
  const body={dataset:$('ds').value,strategy:$('st').value,profile:$('pr').value};
  if(tw){body.trend_window=Number(tw);}
  $('out').textContent='در حال ارسال...';
  const r=await fetch('/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  $('out').textContent=JSON.stringify(j,null,2);
  if(r.ok){poll(j.run_id);}
});
</script></body></html>"""


def render_page(root: Path) -> str:
    datasets = "".join(f'<option value="{d["name"]}">{d["name"]}</option>' for d in list_datasets(root))
    strategies = "".join(f'<option value="{name}">{name}</option>' for name in sorted(STRATEGY_BY_NAME))
    profiles = "".join(f'<option value="{p["id"]}">{p["label"]}</option>' for p in list_profiles(root))
    return (HTML_PAGE.replace("__DATASETS__", datasets)
                     .replace("__STRATEGIES__", strategies)
                     .replace("__PROFILES__", profiles))


def _error(status: int, code: str, message: str) -> dict:
    return {"api_version": API_VERSION, "error": {"status": status, "code": code, "message": message}}


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "xauusd-research-ui/" + __version__
        sys_version = ""

        def log_message(self, fmt, *args):
            return

        def _send(self, status: int, payload, content_type="application/json; charset=utf-8"):
            body = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            try:
                if path == "/":
                    self._send(200, render_page(root), "text/html; charset=utf-8")
                elif path == "/health":
                    self._send(200, health_payload(root))
                elif path == "/quality":
                    self._send(200, build_quality_payload(root))
                elif path == "/datasets":
                    self._send(200, {"api_version": API_VERSION, "datasets": list_datasets(root)})
                elif path.startswith("/runs/"):
                    run_id = path.split("/", 2)[2]
                    with RUNS_LOCK:
                        state = RUNS.get(run_id)
                    if state is None:
                        raise ApiError(404, "RUN_NOT_FOUND", f"unknown run: {run_id}")
                    self._send(200, {"api_version": API_VERSION, "run": state})
                else:
                    self._send(404, _error(404, "NOT_FOUND", f"no route for GET {path}"))
            except ApiError as exc:
                self._send(exc.status, _error(exc.status, exc.code, exc.message))

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path != "/runs":
                known = path in ("/", "/health", "/quality", "/datasets") or path.startswith("/runs/")
                if known:
                    self._send(405, _error(405, "METHOD_NOT_ALLOWED", "only GET and POST /runs are supported"))
                else:
                    self._send(404, _error(404, "NOT_FOUND", f"no route for POST {path}"))
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ApiError(400, "BAD_BODY", "body must be a small JSON object")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ApiError(400, "BAD_BODY", "body must be a JSON object")
                state = start_run(root, body)
                self._send(202, {"api_version": API_VERSION, "run_id": state["run_id"],
                                 "status": "QUEUED", "status_url": f"/runs/{state['run_id']}"})
            except ApiError as exc:
                self._send(exc.status, _error(exc.status, exc.code, exc.message))
            except (ValueError, json.JSONDecodeError):
                self._send(400, _error(400, "BAD_BODY", "invalid JSON"))

        def _rejected(self):
            self._send(405, _error(405, "METHOD_NOT_ALLOWED", "only GET and POST /runs are supported"))

        do_PUT = do_DELETE = do_PATCH = _rejected

    return Handler


def create_server(root=None, host="127.0.0.1", port=0) -> ThreadingHTTPServer:
    root = Path(root) if root is not None else DEFAULT_ROOT
    return ThreadingHTTPServer((host, port), make_handler(root))