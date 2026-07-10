import json
import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.system_b.explorer.explorer_server import create_app
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests, write_jsonl


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasAnnotationTransactionTests(unittest.TestCase):
    def test_database_annotation_ignores_frontend_reviewer_and_checks_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kg"
            root.mkdir()
            KnowledgeExplorerTests().fixture(root)
            review = Path(tmp) / "review"
            review.mkdir()
            item = {
                "review_item_id": "item1",
                "case_id": "case",
                "item_type": "fulltext_l1_claim",
                "subject": "A",
                "relation": "promotes",
                "object": "B",
                "evidence_sentence": "A promotes B.",
            }
            write_jsonl(review / "manual_review_queue.jsonl", [item])
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            app = create_app(root, review, database_url=url, require_database=True, testing=True)
            client = app.test_client()
            token = client.get("/api/session").get_json()["csrf_token"]
            payload = {"final_label": "VALID", "reviewer_id": "attacker", "client_submission_id": "once"}
            first = client.post("/api/annotation/item1", json=payload, headers={"X-CSRF-Token": token})
            self.assertEqual(first.status_code, 200)
            body = first.get_json()
            self.assertEqual(body["reviewer_user_id"], "local-dev-user")
            self.assertEqual(body["reviewer_username_snapshot"], "local_dev")
            duplicate = client.post("/api/annotation/item1", json={**payload, "final_label": "INVALID"}, headers={"X-CSRF-Token": token})
            self.assertEqual(duplicate.status_code, 200)
            self.assertEqual(duplicate.get_json()["final_label"], "VALID")
            stale = client.post("/api/annotation/item1", json={"final_label": "INVALID", "expected_revision": 0}, headers={"X-CSRF-Token": token})
            self.assertEqual(stale.status_code, 409)


if __name__ == "__main__":
    unittest.main()
