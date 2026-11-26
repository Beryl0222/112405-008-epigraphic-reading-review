import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_workbench.seed import build_workbench  # noqa: E402


class ArtifactSiteAndDuplicateTest(unittest.TestCase):
    def setUp(self):
        self.wb = build_workbench()

    def test_old_and_new_registration_numbers_resolve_same_artifact(self):
        self.assertEqual(self.wb.resolve_artifact_id("E-12"), "ART-E12")
        self.assertEqual(self.wb.resolve_artifact_id("E12"), "ART-E12")
        art = self.wb.find_artifact("E-12")
        self.assertEqual(art["id"], "ART-E12")
        self.assertIn("E12", art["aliases"])

    def test_mistaken_new_artifact_preserved_and_pointing_back(self):
        art999 = self.wb.get("ART-E999")
        self.assertEqual(art999["status"], "merged_duplicate")
        self.assertEqual(art999["duplicate_of"], "ART-E12")
        # 误建编号现在也能解析回 canonical
        self.assertEqual(self.wb.resolve_artifact_id("ART-E999"), "ART-E12")
        self.assertEqual(self.wb.resolve_artifact_id("E999"), "ART-E12")

    def test_later_rubbing_repointed_with_history(self):
        rb2 = self.wb.get("RB-2")
        self.assertEqual(rb2["artifact_id"], "ART-E12")
        actions = [h["action"] for h in rb2["history"]]
        self.assertIn("artifact_repointed", actions)

    def test_hasty_site_relation_flagged_pending_after_merge(self):
        rel = self.wb.get("REL-E999-SITE")
        self.assertEqual(rel["from_id"], "ART-E12")
        self.assertEqual(rel["status"], "pending_review")
        self.assertTrue(
            any(i["code"].startswith("artifact-merge") for i in rel["review_issues"])
        )

    def test_confirmed_site_relation_has_excavation_basis(self):
        rel = self.wb.get("REL-SITE")
        self.assertEqual(rel["to_id"], "SITE-HD")
        self.assertEqual(rel["status"], "active")
        self.assertTrue(rel["basis"])
        self.assertIn("SRC-EXC-1", rel["source_record_ids"])

    def test_merge_is_non_destructive_for_relations(self):
        wb2 = build_workbench()
        wb2.add_artifact("A1", "器1")
        wb2.add_artifact("A2", "器2误建")
        wb2.add_site("S1", "地点")
        wb2.add_relation("R1", "unearthed_at", "A2", "S1")
        count_before_merge = len(wb2.db["relations"])
        result = wb2.merge_artifacts("A2", "A1", reason="同一器")
        # 合并只改指、不删除关系
        self.assertEqual(len(wb2.db["relations"]), count_before_merge)
        self.assertIn("R1", result["repointed"]["relations"])
        self.assertEqual(wb2.get("R1")["from_id"], "A1")
        self.assertTrue(wb2.has("A2"))


if __name__ == "__main__":
    unittest.main()
