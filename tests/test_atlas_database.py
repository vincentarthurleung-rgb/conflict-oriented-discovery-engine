import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.system_b.persistence.database import create_atlas_engine, sqlite_health
from code_engine.system_b.persistence.models import User
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasDatabaseTests(unittest.TestCase):
    def test_migration_and_sqlite_pragmas(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            health = sqlite_health(create_atlas_engine(url))
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["foreign_keys"], 1)
            self.assertEqual(health["journal_mode"], "wal")
            self.assertEqual(health["busy_timeout"], 10000)
            self.assertEqual(health["schema_version"], "0009_system_a_v2_metadata")

    def test_user_model_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            engine = create_atlas_engine(url)
            Session = sessionmaker(bind=engine, future=True)
            with Session.begin() as session:
                session.add(User(username="reviewer", display_name="Reviewer", password_hash="x", role="reviewer"))
            with Session() as session:
                user = session.execute(select(User).where(User.username == "reviewer")).scalar_one()
                self.assertEqual(user.role, "reviewer")


if __name__ == "__main__":
    unittest.main()
