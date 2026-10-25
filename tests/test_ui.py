import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.ui.server import create_server

ROOT = Path(__file__).resolve().parents[1]


def call(server, method, path):
    host, port = server.server_address[:2]
    conn = HTTPConnection(host, port, timeout=5)
    conn.request(method, path)
    response = conn.getresponse()
    body = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(body)


class UiSkeletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(root=ROOT, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health(self):
        status, payload = call(self.server, "GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["api_version"], "1.0")
        self.assertIn("package_version", payload)
        self.assertTrue(payload["time_utc"].endswith("+00:00"))
        self.assertTrue(payload["checks"]["data_audit_present"])

    def test_quality(self):
        status, payload = call(self.server, "GET", "/quality")
        self.assertEqual(status, 200)
        self.assertEqual(payload["api_version"], "1.0")
        dataset = payload["dataset"]
        self.assertGreater(dataset["rows"], 3_000_000)
        self.assertEqual(len(dataset["sha256"]), 64)
        self.assertIn("integrity", payload)
        self.assertIn("gaps", payload)
        self.assertIn("price_range", payload)

    def test_unknown_route(self):
        status, payload = call(self.server, "GET", "/nope")
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")

    def test_write_methods_rejected(self):
        status, payload = call(self.server, "POST", "/health")
        self.assertEqual(status, 405)
        self.assertEqual(payload["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_quality_without_audit_file(self):
        with TemporaryDirectory() as tmp:
            server = create_server(root=Path(tmp), port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, payload = call(server, "GET", "/quality")
            finally:
                server.shutdown()
                server.server_close()
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "AUDIT_MISSING")


if __name__ == "__main__":
    unittest.main()