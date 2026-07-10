import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.system_b.explorer.auth import hash_password, write_user_store
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import SystemSetting, User
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasOwnerPermissionTests(unittest.TestCase):
    def _login(self, client, username):
        page = client.get("/login").get_data(as_text=True)
        token = page.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
        return client.post("/login", data={"username": username, "password": "correct horse battery staple", "csrf_token": token})

    def test_owner_api_forbidden_to_developer_and_allowed_to_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kg"
            root.mkdir()
            KnowledgeExplorerTests().fixture(root)
            users_file = Path(tmp) / "users.json"
            password_hash = hash_password("correct horse battery staple")
            write_user_store(users_file, {
                "owner": {"username": "owner", "password_hash": password_hash, "display_name": "Owner", "role": "owner", "enabled": True},
                "dev": {"username": "dev", "password_hash": password_hash, "display_name": "Dev", "role": "developer", "enabled": True},
            }, [])
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            factory = session_factory(create_atlas_engine(url))
            with session_scope(factory) as session:
                owner = User(username="owner", display_name="Owner", password_hash=password_hash, role="owner", enabled=True)
                dev = User(username="dev", display_name="Dev", password_hash=password_hash, role="developer", enabled=True)
                session.add_all([owner, dev])
                session.flush()
                session.add(SystemSetting(key="owner_user_id", value=owner.user_id))
            app = create_app(root, None, require_auth=True, users_file=users_file, secret_key="x", database_url=url, require_database=True, testing=True)
            dev_client = app.test_client()
            self._login(dev_client, "dev")
            self.assertEqual(dev_client.get("/api/owner/overview").status_code, 403)
            owner_client = app.test_client()
            self._login(owner_client, "owner")
            response = owner_client.get("/api/owner/overview")
            self.assertEqual(response.status_code, 200)
            self.assertIn("formal_user_count", response.get_json())


if __name__ == "__main__":
    unittest.main()
