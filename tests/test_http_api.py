import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.server import serve_in_background  # noqa: E402


class HttpQueryApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, cls.thread = serve_in_background(port=0)
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def _get(self, path):
        with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_health(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_report_endpoint(self):
        status, body = self._get("/api/report")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["relations"]), 7)
        self.assertIn("合成样本", body["data_notice"])

    def test_persons_what_if_boat_via_querystring(self):
        qs = urlencode({"what_if": "舟"})
        status, body = self._get(f"/api/persons?{qs}")
        self.assertEqual(status, 200)
        ir1 = next(d for d in body["decisions"] if d["rule_id"] == "IR-1")
        self.assertEqual(ir1["decision"], "split")

    def test_invalid_what_if_rejected(self):
        qs = urlencode({"what_if": "龙"})
        with self.assertRaises(HTTPError) as ctx:
            self._get(f"/api/report?{qs}")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
