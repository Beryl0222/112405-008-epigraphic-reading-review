import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.seed import build_workbench  # noqa: E402


class ResearchQueryTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_every_reading_dependent_relation_view_has_reading_and_basis(self):
        report = self.wb.research_report()
        dependent = {"REL-LIN", "REL-ID", "REL-KIN", "REL-DATE", "REL-EVENT"}
        for rv in report["relations"]:
            if rv["id"] in dependent:
                self.assertIsNotNone(rv["reading"], rv["id"])
                self.assertEqual(rv["reading"]["candidate"], "周")
                self.assertTrue(rv["reading"]["basis"], rv["id"])
                self.assertTrue(rv["reading"]["opinion_id"])

    def test_site_relation_explicitly_independent_of_reading(self):
        rv = next(r for r in self.wb.research_report()["relations"] if r["id"] == "REL-SITE")
        self.assertIsNone(rv["reading"])
        self.assertTrue(rv["basis"])

    def test_view_shows_withdrawal_warning_live_status(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="测试撤回")
        rv = next(r for r in self.wb.research_report()["relations"] if r["id"] == "REL-LIN")
        self.assertEqual(rv["status"], "pending_review")
        self.assertEqual(rv["reading"]["opinion_current_status"], "withdrawn")
        self.assertTrue(rv["open_issues"])

    def test_view_lists_citations_and_their_status(self):
        rv = next(r for r in self.wb.research_report()["relations"] if r["id"] == "REL-DATE")
        cite_ids = {c["id"] for c in rv["citations"]}
        self.assertIn("CITE-1", cite_ids)
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        rv = next(r for r in self.wb.research_report()["relations"] if r["id"] == "REL-DATE")
        c1 = next(c for c in rv["citations"] if c["id"] == "CITE-1")
        self.assertEqual(c1["status"], "pending_review")

    def test_report_carries_synthetic_notice_and_events(self):
        report = self.wb.research_report()
        self.assertIn("合成样本", report["data_notice"])
        self.assertTrue(report["events"])
        ev = report["events"][0]
        self.assertEqual(ev["occurrence_status"], "unverified")
        self.assertIn("照片", ev["interpretation_boundary"])

    def test_pending_index_after_withdrawal(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        pending = {(p["type"], p["id"]) for p in self.wb.research_report()["pending_review"]}
        self.assertIn(("adoption", "ADP-1"), pending)
        self.assertIn(("citation", "CITE-1"), pending)
        self.assertIn(("relation", "REL-LIN"), pending)
        # 本来就待核的 EP-3 关系仍在
        self.assertIn(("relation", "REL-EVENT"), pending)

    def test_citation_view_shows_target_current_reading_and_original_statement(self):
        report = self.wb.research_report()
        c1 = next(c for c in report["citations"] if c["id"] == "CITE-1")
        self.assertTrue(c1["statement"])  # 原引表述保留，不被改写
        date_target = next(t for t in c1["targets"] if t["id"] == "REL-DATE")
        self.assertEqual(date_target["reading"]["candidate"], "周")
        self.assertEqual(date_target["status"], "active")
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        report = self.wb.research_report()
        c1 = next(c for c in report["citations"] if c["id"] == "CITE-1")
        self.assertEqual(c1["status"], "pending_review")
        statuses = {t["id"]: t["status"] for t in c1["targets"]}
        self.assertEqual(statuses["REL-DATE"], "pending_review")


if __name__ == "__main__":
    unittest.main()
