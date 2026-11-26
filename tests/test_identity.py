import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.workbench import Workbench  # noqa: E402
from case_workbench.seed import build_workbench  # noqa: E402


class IdentityResolutionTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_current_catalog_adoption_merges(self):
        # 种子中 CAT-1 采纳 OP-3“周”
        result = self.wb.resolve_persons()
        ir1 = next(d for d in result["decisions"] if d["rule_id"] == "IR-1")
        self.assertEqual(ir1["decision"], "merged")
        self.assertFalse(result["pending"])

    def test_what_if_zhou_merges(self):
        result = self.wb.resolve_persons({"G-6": "周"})
        ir1 = next(d for d in result["decisions"] if d["rule_id"] == "IR-1")
        self.assertEqual(ir1["decision"], "merged")
        self.assertTrue(ir1["reading"]["hypothetical"])

    def test_what_if_boat_splits(self):
        result = self.wb.resolve_persons({"G-6": "舟"})
        ir1 = next(d for d in result["decisions"] if d["rule_id"] == "IR-1")
        self.assertEqual(ir1["decision"], "split")
        # MN-1 与 P-ZB 不在同一簇；MN-2 仍无条件与 P-ZB 同簇
        together = any(
            {"MN-1", "P-ZB"} <= {m["id"] for m in cluster["members"]}
            for cluster in result["clusters"]
        )
        self.assertFalse(together)
        mn2_zb = any(
            {"MN-2", "P-ZB"} <= {m["id"] for m in cluster["members"]}
            for cluster in result["clusters"]
        )
        self.assertTrue(mn2_zb)

    def test_hypothetical_does_not_mutate_catalog(self):
        self.wb.resolve_persons({"G-6": "舟"})
        self.assertEqual(self.wb.get("ADP-1")["reading"], "周")
        states = self.wb.reading_states()
        self.assertEqual(states["G-6"]["candidate"], "周")

    def test_no_adoption_means_pending_not_forced_split(self):
        wb = Workbench()
        wb.add_person("E1", "专家甲")
        wb.add_glyph("G", "某位置", candidates=["舟", "周"])
        wb.add_opinion("O1", "G", "舟", expert_id="E1")
        wb.add_person_entity("P1", "周伯")
        wb.add_mention("M1", "名讳", glyph_id="G")
        wb.add_identity_rule("R1", "M1", "P1", glyph_id="G", if_reading="周")
        result = wb.resolve_persons()
        self.assertEqual(result["decisions"][0]["decision"], "pending")
        self.assertEqual(result["pending"][0]["rule_id"], "R1")

    def test_withdrawn_adoption_makes_identity_pending(self):
        self.wb.withdraw_opinion("OP-3", by="U-YI", reason="测试")
        result = self.wb.resolve_persons()
        ir1 = next(d for d in result["decisions"] if d["rule_id"] == "IR-1")
        self.assertEqual(ir1["decision"], "pending")


if __name__ == "__main__":
    unittest.main()
