import json
import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from code_engine.cli.atlas_db_import_legacy import main as import_main
from code_engine.system_b.explorer.auth import hash_password, write_user_store
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory
from code_engine.system_b.persistence.models import ReviewItem, User
from tests.test_system_b_knowledge_explorer import write_jsonl


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasLegacyImportTests(unittest.TestCase):
    def test_dry_run_does_not_persist_and_real_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            users_file = Path(tmp) / "users.json"
            write_user_store(users_file, {"rev": {"username": "rev", "display_name": "Rev", "password_hash": hash_password("correct horse battery staple"), "role": "reviewer", "enabled": True}}, [])
            review = Path(tmp) / "review"
            review.mkdir()
            write_jsonl(review / "manual_review_queue.jsonl", [{"review_item_id": "item", "case_id": "case", "item_type": "fulltext_l1_claim"}])
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            import_main(["--database-url", url, "--users-file", str(users_file), "--review-root", str(review), "--dry-run"])
            factory = session_factory(create_atlas_engine(url))
            with factory() as session:
                self.assertEqual(session.execute(select(User)).scalars().all(), [])
            import_main(["--database-url", url, "--users-file", str(users_file), "--review-root", str(review), "--no-backup"])
            import_main(["--database-url", url, "--users-file", str(users_file), "--review-root", str(review), "--no-backup"])
            with factory() as session:
                self.assertEqual(len(session.execute(select(User)).scalars().all()), 1)
                self.assertEqual(len(session.execute(select(ReviewItem)).scalars().all()), 1)


if __name__ == "__main__":
    unittest.main()
