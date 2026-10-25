import json
import shutil
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.ui.server import create_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_500.csv"


def call(server, method, path, body=None):
    host, port = server.server_address[:2]
    conn = HTTPConnection(host, port, timeout=10)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    conn.request(method, path, body=payload, headers=headers)
    response = conn.getresponse()
    raw = response.read().decode("utf-8")
    conn.close()
    try:
        return response.status, json.loads(raw)
    except json.JSONDecodeError:
        return response.status, raw


class _TempRoot:
    def __init__(self):
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "data").mkdir()
        (root / "config").mkdir()
        shutil.copyfile(FIXTURE, root / "data" / "sample.csv")
        shutil.copyfile(ROOT / "config" / "scenario_s1.json", root / "config" / "scenario_s1.json")
        self.root = root

    def close(self):
        self.tmp.cleanup()


class RunApiTests(unittest.TestCase):
    def setUp(self):
        self.env = _TempRoot()
        self.server = create_server(root=self.env.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env.close()

    def test_page_renders_form(self):
        status, html = call(self.server, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("<select id=\"ds\">", html)
        self.assertIn("/runs", html)

    def test_datasets_listing(self):
        status, payload = call(self.server, "GET", "/datasets")
        self.assertEqual(status, 200)
        self.assertEqual(payload["datasets"][0]["name"], "sample.csv")

    def test_run_lifecycle(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "sample.csv", "strategy": "ma_5_20",
                                "profile": "config/scenario_s1.json"})
        self.assertEqual(status, 202)
        run_id = payload["run_id"]
        self.assertEqual(payload["status"], "QUEUED")

        deadline = time.time() + 30
        state = None
        while time.time() < deadline:
            code, body = call(self.server, "GET", f"/runs/{run_id}")
            self.assertEqual(code, 200)
            state = body["run"]
            if state["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.2)
        self.assertEqual(state["status"], "COMPLETED", state)
        self.assertIn("metrics", state["result"])
        self.assertGreater(state["result"]["metrics"]["trades"], 0)
        self.assertEqual(state["result"]["cost_label"], "PROVISIONAL_COST_SCENARIO")

    def test_path_traversal_is_rejected(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "../secret.csv", "strategy": "ma_5_20", "profile": "none"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_DATASET")

    def test_absolute_path_is_rejected(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "C:\\Windows\\win.ini", "strategy": "ma_5_20", "profile": "none"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_DATASET")

    def test_unknown_strategy(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "sample.csv", "strategy": "nope", "profile": "none"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_STRATEGY")

    def test_unknown_profile(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "sample.csv", "strategy": "ma_5_20", "profile": "config/../x.json"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_PROFILE")

    def test_missing_dataset(self):
        status, payload = call(self.server, "POST", "/runs",
                               {"dataset": "absent.csv", "strategy": "ma_5_20", "profile": "none"})
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "DATASET_NOT_FOUND")

    def test_unknown_run(self):
        status, payload = call(self.server, "GET", "/runs/deadbeef")
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "RUN_NOT_FOUND")

    def test_invalid_json_body(self):
        host, port = self.server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/runs", body=b"not-json", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        response.read()
        conn.close()
        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()