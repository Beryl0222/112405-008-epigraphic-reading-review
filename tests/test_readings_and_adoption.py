import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.errors import OpinionUnavailableError, ValidationError  # noqa: E402
from case_workbench.seed import build_workbench  # noqa: E402


class ReadingPreservationTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_raw_ep_records_preserved_verbatim(self):
        for rid in ("EP-1", "EP-2", "EP-3"):
            self.assertTrue(self.wb.has(rid))
        ep1 = self.wb.get("EP-1")
        self.assertIn("舟", ep1["text"])
        self.assertIn("周", ep1["text"])
        self.assertEqual(ep1["kind"], "reading-note")

    def test_glyph_position_and_both_candidates_preserved(self):
        glyph = self.wb.get("G-6")
        self.assertEqual(glyph["line"], 6)
        self.assertIsNotNone(glyph["coordinates"])
        self.assertEqual(glyph["candidates"], ["舟", "周"])
        self.assertIn("右侧残笔", glyph["note"])

    def test_successive_opinions_all_retained(self):
        ids = [o["id"] for o in self.wb.db["opinions"]]
        self.assertEqual(ids, ["OP-1", "OP-2", "OP-3", "OP-4"])
        readings = {o["reading"] for o in self.wb.db["opinions"]}
        self.assertEqual(readings, {"舟", "周"})
        # 每条意见都带可信依据
        for op in self.wb.db["opinions"]:
            self.assertTrue(op["basis"])
            self.assertTrue(op["expert_name"])

    def test_new_candidate_is_appended_not_overwriting(self):
        self.wb.add_candidate_reading("G-6", "冂", note="测试新候选")
        self.assertEqual(self.wb.get("G-6")["candidates"], ["舟", "周", "冂"])

    def test_adoption_snapshots_basis_and_opinion(self):
        adp = self.wb.get("ADP-1")
        self.assertEqual(adp["opinion_id"], "OP-3")
        self.assertEqual(adp["reading"], "周")
        snap = adp["reading_snapshot"]
        self.assertEqual(snap["candidate"], "周")
        self.assertTrue(snap["basis"])
        self.assertEqual(snap["expert_name"], "释读者乙（合成人物）")

    def test_cannot_adopt_withdrawn_opinion(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="测试撤回")
        with self.assertRaises(OpinionUnavailableError):
            self.wb.adopt_reading("ADP-BAD", "CAT-1", "G-6", "OP-3", by="U-REN")

    def test_bare_reading_unknown_candidate_rejected(self):
        with self.assertRaises(ValidationError):
            self.wb.add_relation(
                "REL-BAD", "dated_to", "ART-E12", "DATE-E12",
                glyph_id="G-6", candidate="龙",  # 不在保留候选中
            )

    def test_bare_candidate_without_basis_rejected(self):
        with self.assertRaises(ValidationError):
            self.wb.add_relation(
                "REL-BAD2", "assigned_to_lineage", "ART-E12", "LIN-ZHOU",
                glyph_id="G-6", candidate="舟",
            )

    def test_explicit_candidate_with_basis_allowed_but_flagged(self):
        rel = self.wb.add_relation(
            "REL-DIRECT", "assigned_to_lineage", "ART-E12", "LIN-ZHOU",
            glyph_id="G-6", candidate="舟",
            basis=[{"kind": "context", "detail": "测试者独立辞例判断（合成）"}],
        )
        self.assertTrue(rel["reading"]["hypothesis_only"])
        self.assertIsNone(rel["reading"]["opinion_id"])


if __name__ == "__main__":
    unittest.main()
