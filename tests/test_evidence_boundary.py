import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.errors import ValidationError  # noqa: E402
from case_workbench.models import EVENT_UNVERIFIED  # noqa: E402
from case_workbench.seed import build_workbench  # noqa: E402


class EvidenceBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_new_photo_appends_visible_evidence_only(self):
        before_evidence = len(self.wb.db["evidence"])
        before_event = self.wb.get("EV-SAC")["occurrence_status"]
        self.wb.add_photo(
            "EVD-TEST-PH", "测试照片", glyph_id="G-6",
            observed_traits=["新残笔"],
        )
        self.assertEqual(len(self.wb.db["evidence"]), before_evidence + 1)
        self.assertEqual(
            self.wb.get("EV-SAC")["occurrence_status"], before_event
        )
        # 字形历史留下证据增加记录
        self.assertTrue(
            any(h["action"] == "evidence_added" for h in self.wb.get("G-6")["history"])
        )
        # 审计明确记录“照片不等于事件证实”
        self.assertTrue(
            any(e["action"] == "photo_evidence_only" for e in self.wb.db["audit"])
        )

    def test_even_strong_zhou_opinion_does_not_verify_event(self):
        self.wb.add_opinion(
            "OP-STRONG", "G-6", "周", expert_id="U-YI", confidence="high",
            basis=[{"kind": "photo", "detail": "假设性强证据（测试）"}],
        )
        self.assertEqual(self.wb.get("EV-SAC")["occurrence_status"], EVENT_UNVERIFIED)

    def test_photo_cannot_corroborate_event(self):
        with self.assertRaises(ValidationError):
            self.wb.corroborate_event("EV-SAC", "EVD-PH1", by="U-GUI")
        self.assertEqual(self.wb.get("EV-SAC")["occurrence_status"], EVENT_UNVERIFIED)
        self.assertNotIn("EVD-PH1", self.wb.get("EV-SAC")["evidence_ids"])

    def test_rubbing_also_cannot_corroborate_event(self):
        with self.assertRaises(ValidationError):
            self.wb.corroborate_event("EV-SAC", "EVD-RB1", by="U-GUI")

    def test_independent_archaeological_evidence_can_corroborate(self):
        self.wb.add_evidence(
            "EVD-ARCH", "archaeological-context", "祭祀坑共存（合成）",
        )
        # add_evidence 应按 kind 自动标记 independent
        self.assertTrue(self.wb.get("EVD-ARCH")["independent"])
        self.wb.corroborate_event("EV-SAC", "EVD-ARCH", by="U-REN")
        self.assertEqual(self.wb.get("EV-SAC")["occurrence_status"], "corroborated")
        self.assertIn("EVD-ARCH", self.wb.get("EV-SAC")["evidence_ids"])

    def test_photo_does_not_change_catalog_adoption_automatically(self):
        self.wb.add_photo("EVD-PHX", "又一张照片", glyph_id="G-6")
        active = [a for a in self.wb.db["adoptions"] if a["status"] == "active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], "ADP-1")


if __name__ == "__main__":
    unittest.main()
