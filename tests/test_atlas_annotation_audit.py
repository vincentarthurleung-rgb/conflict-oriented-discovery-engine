import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import AnnotationEvent
from code_engine.system_b.persistence.services.review_service import ensure_local_developer, import_review_items, save_annotation
from tests.test_system_b_knowledge_explorer import write_jsonl


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasAnnotationAuditTests(unittest.TestCase):
    def test_annotation_events_are_append_only_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "review"
            review.mkdir()
            write_jsonl(review / "manual_review_queue.jsonl", [{"review_item_id": "item", "case_id": "case", "item_type": "fulltext_l1_claim"}])
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            factory = session_factory(create_atlas_engine(url))
            with session_scope(factory) as session:
                user = ensure_local_developer(session)
                import_review_items(session, review)
                identity = {"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "role": user.role, "authenticated": False}
                first = save_annotation(session, review_item_id="item", payload={"final_label": "VALID"}, identity=identity, namespace="test")
                second = save_annotation(session, review_item_id="item", payload={"final_label": "PARTIAL", "expected_revision": first["revision"]}, identity=identity, namespace="test")
                self.assertEqual(second["revision"], 2)
            with session_scope(factory) as session:
                events = session.execute(select(AnnotationEvent).order_by(AnnotationEvent.occurred_at)).scalars().all()
                self.assertEqual(len(events), 2)
                self.assertEqual(events[0].new_revision, 1)
                self.assertEqual(events[1].previous_revision, 1)
                self.assertIn("PARTIAL", events[1].full_snapshot_json)


if __name__ == "__main__":
    unittest.main()
