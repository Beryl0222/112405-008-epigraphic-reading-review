import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from case_workbench.cli import main as cli_main  # noqa: E402
from case_workbench.scenario import evaluate  # noqa: E402
from case_workbench.seed import build_workbench  # noqa: E402
from case_workbench.workbench import Workbench  # noqa: E402


class PersistenceTest(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        wb = build_workbench()
        wb.withdraw_opinion("OP-3", by="U-YI", reason="往返测试")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "wb.json"
            wb.save(path)
            self.assertTrue(path.exists())
            loaded = Workbench.load(path)
            self.assertEqual(loaded.get("OP-3")["status"], "withdrawn")
            self.assertEqual(loaded.get("REL-LIN")["status"], "pending_review")
            report = loaded.research_report({"G-6": "舟"})
            self.assertTrue(report["identity"]["decisions"])
            # 文件必须是 UTF-8 JSON 且保留中文
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(any("舟" in o["reading"] for o in payload["opinions"]))

    def test_from_dict_deepcopy_is_independent(self):
        data = build_workbench().to_dict()
        wb = Workbench.from_dict(data)
        wb.withdraw_opinion("OP-3", by="x")
        self.assertNotEqual(data["opinions"][2]["status"], "withdrawn")


class ScenarioVerificationTest(unittest.TestCase):
    def test_all_end_to_end_checks_pass(self):
        checks = evaluate()
        failed = [(name, detail) for name, ok, detail in checks if not ok]
        self.assertEqual(failed, [])


class CliTest(unittest.TestCase):
    def test_cli_verify_exit_zero(self):
        self.assertEqual(cli_main(["verify"]), 0)

    def test_cli_init_and_query_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "wb.json"
            self.assertEqual(cli_main(["--db", str(db), "init"]), 0)
            self.assertTrue(db.exists())
            # 重复 init 不带 force 应返回 1
            self.assertEqual(cli_main(["--db", str(db), "init"]), 1)

    def test_module_invocation_demo_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "case_workbench", "verify"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("通过", proc.stdout)


if __name__ == "__main__":
    unittest.main()
