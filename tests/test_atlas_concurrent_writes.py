import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope, sqlite_health
from code_engine.system_b.persistence.services.review_service import StaleAnnotationRevision, ensure_local_developer, import_review_items, save_annotation
from tests.test_system_b_knowledge_explorer import write_jsonl


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasConcurrentWritesTests(unittest.TestCase):
    def test_busy_timeout_configured_and_stale_update_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "review"
            review.mkdir()
            write_jsonl(review / "manual_review_queue.jsonl", [{"review_item_id": "item", "case_id": "case", "item_type": "fulltext_l1_claim"}])
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            engine = create_atlas_engine(url)
            self.assertEqual(sqlite_health(engine)["busy_timeout"], 10000)
            factory = session_factory(engine)
            with session_scope(factory) as session:
                user = ensure_local_developer(session)
                import_review_items(session, review)
                identity = {"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "role": user.role, "authenticated": False}
                first = save_annotation(session, review_item_id="item", payload={"final_label": "VALID"}, identity=identity, namespace="test")
                with self.assertRaises(StaleAnnotationRevision):
                    save_annotation(session, review_item_id="item", payload={"final_label": "INVALID", "expected_revision": first["revision"] - 1}, identity=identity, namespace="test")


if __name__ == "__main__":
    unittest.main()
