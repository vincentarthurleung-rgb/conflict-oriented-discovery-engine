import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.annotation_store import AnnotationStore
from tests.test_system_b_knowledge_explorer import write_jsonl


class AtlasReviewWorkspaceV2Tests(unittest.TestCase):
    def test_skip_disposition_does_not_force_unclear_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            queue=[{"review_item_id":"item","case_id":"case","item_type":"fulltext_l1_claim"}]
            write_jsonl(root/"manual_review_queue.jsonl",queue)
            store=AnnotationStore(root,queue)
            saved=store.save("item",{"review_disposition":"skipped","uncertainty_reason":"reviewer_unfamiliar","reviewer_id":"r"})
            self.assertEqual(saved["review_disposition"],"skipped")
            self.assertEqual(saved["uncertainty_reason"],"reviewer_unfamiliar")
            self.assertEqual(saved["final_label"],"")

    def test_review_ui_has_draft_skip_and_progressive_diagnostics(self):
        js=Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
        self.assertIn("我不熟悉该主题，跳过",js)
        self.assertIn("review_disposition",js)
        self.assertIn("reviewer_unfamiliar",js)
        self.assertIn("draft:",js)
        self.assertIn("error-diagnostics",js)


if __name__=="__main__":
    unittest.main()
