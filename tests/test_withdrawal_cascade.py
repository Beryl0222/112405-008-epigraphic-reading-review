import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.errors import ValidationError  # noqa: E402
from case_workbench.models import ACTIVE, PENDING_REVIEW, WITHDRAWN  # noqa: E402
from case_workbench.seed import build_workbench  # noqa: E402


class WithdrawalCascadeTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_withdraw_marks_opinion_and_cascades(self):
        report = self.wb.withdraw_opinion("OP-3", by="U-YI", reason="依据不足")
        self.assertEqual(self.wb.get("OP-3")["status"], WITHDRAWN)
        self.assertIn("ADP-1", report["newly_pending"]["adoptions"])
        for rid in ("REL-LIN", "REL-ID", "REL-KIN", "REL-DATE"):
            self.assertIn(rid, report["newly_pending"]["relations"])
        self.assertIn("CITE-1", report["newly_pending"]["citations"])

    def test_independent_relations_and_citations_unaffected(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        self.assertEqual(self.wb.get("REL-SITE")["status"], ACTIVE)
        self.assertEqual(self.wb.get("CITE-2")["status"], ACTIVE)

    def test_records_are_not_deleted_and_history_grows(self):
        histories_before = {
            rid: len(self.wb.get(rid)["history"])
            for rid in ("OP-3", "ADP-1", "REL-LIN", "CITE-1")
        }
        audit_before = len(self.wb.db["audit"])
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        for rid, before in histories_before.items():
            self.assertGreater(len(self.wb.get(rid)["history"]), before, rid)
        self.assertGreater(len(self.wb.db["audit"]), audit_before)
        # 所有集合一条记录都没少
        self.assertTrue(self.wb.has("OP-3"))
        self.assertTrue(self.wb.has("ADP-1"))

    def test_newly_pending_report_not_duplicated_on_second_call(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="第一次")
        second = self.wb.withdraw_opinion("OP-3", by="U-YI", reason="重复事件")
        self.assertEqual(second["newly_pending"]["relations"], [])
        self.assertEqual(self.wb.get("REL-LIN")["status"], PENDING_REVIEW)

    def test_readopt_and_reconfirm_restores_chain(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        self.wb.adopt_reading("ADP-2", "CAT-1", "G-6", "OP-4", by="U-REN")
        for rid in ("REL-LIN", "REL-ID", "REL-KIN", "REL-DATE"):
            self.wb.reconfirm(rid, by="U-REN", new_adoption_id="ADP-2")
        self.assertEqual(self.wb.get("CITE-1")["status"], ACTIVE)
        # 关系视图中的读法已更新为 OP-4
        rel_lin = self.wb.relation_view(self.wb.get("REL-LIN"))
        self.assertEqual(rel_lin["reading"]["opinion_id"], "OP-4")

    def test_citation_cannot_be_cleared_before_targets(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        with self.assertRaises(ValidationError):
            self.wb.reconfirm("CITE-1", by="U-GUI", note="强行恢复")
        self.assertEqual(self.wb.get("CITE-1")["status"], PENDING_REVIEW)

    def test_scholarly_issue_survives_dependency_reconfirmation(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="x")
        self.wb.adopt_reading("ADP-2", "CAT-1", "G-6", "OP-4", by="U-REN")
        self.wb.reconfirm("REL-EVENT", by="U-GUI", new_adoption_id="ADP-2")
        rel = self.wb.get("REL-EVENT")
        self.assertEqual(rel["status"], PENDING_REVIEW)
        codes = [i["code"] for i in rel["review_issues"] if i["open"]]
        self.assertIn("ep3-unverified", codes)
        self.assertFalse(any(c.startswith("adoption-pending") for c in codes))
        # 显式确认但没有说明 -> 不允许关闭学术问题
        with self.assertRaises(ValidationError):
            self.wb.reconfirm("REL-EVENT", by="U-GUI", acknowledge_scholarly=True)

    def test_superseding_active_adoption_flags_relations(self):
        # 编目在没有撤回的情况下改采另一种有效意见：旧采纳 superseded，
        # 依赖关系必须进入待复核，而不是被静默改写。
        self.wb.add_opinion(
            "OP-5", "G-6", "周", expert_id="U-YI", confidence="high",
            basis=[{"kind": "comparison", "detail": "测试用更强比对"}],
        )
        self.wb.adopt_reading("ADP-NEW", "CAT-1", "G-6", "OP-5", by="U-REN")
        self.assertEqual(self.wb.get("ADP-1")["status"], "superseded")
        self.assertEqual(self.wb.get("REL-LIN")["status"], PENDING_REVIEW)
        codes = [i["code"] for i in self.wb.get("REL-LIN")["review_issues"] if i["open"]]
        self.assertTrue(any(c.startswith("adoption-superseded") for c in codes))


if __name__ == "__main__":
    unittest.main()
