import unittest
from pathlib import Path


class AtlasReviewBatchStaticTests(unittest.TestCase):
    def test_review_batch_auto_next_revisit_and_request_guard_exist(self):
        js = Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
        for text in (
            "_reviewBatchItems",
            "slice(0,20)",
            "advanceReviewAfterSave",
            "_reviewRequestSeq",
            "markReviewRevisit",
            "showRevisitItems",
            "openPreviousReview",
            "review_disposition:'revisit'",
            "needs_second_pass",
            "Saving...",
        ):
            self.assertIn(text, js)

    def test_batch_completion_does_not_claim_accuracy(self):
        js = Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
        completion = js.split("review-batch-complete", 1)[1]
        self.assertIn("当前批次已完成", completion)
        self.assertNotIn("accuracy", completion.casefold())
        self.assertNotIn("一致率", completion)


if __name__ == "__main__":
    unittest.main()
