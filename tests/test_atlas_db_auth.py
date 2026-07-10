import tempfile
import unittest

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.models import User
from tests.atlas_db_test_utils import atlas_fixture, migrate, session_for


class AtlasDbAuthTests(unittest.TestCase):
    def _login(self, client, username, password="correct horse battery staple"):
        page = client.get("/login").get_data(as_text=True)
        token = page.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
        return client.post("/login", data={"username": username, "password": password, "csrf_token": token})

    def test_db_login_disabled_role_change_and_json_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                user = User(username="reviewer", display_name="DB Reviewer", password_hash=hash_password("correct horse battery staple"), role="reviewer", enabled=True)
                disabled = User(username="disabled", display_name="Disabled", password_hash=hash_password("correct horse battery staple"), role="reviewer", enabled=False)
                session.add_all([user, disabled])
            root = __import__("pathlib").Path(tmp) / "kg"
            review = __import__("pathlib").Path(tmp) / "review"
            atlas_fixture(root, review)
            app = create_app(root, review, require_auth=True, database_url=url, require_database=True, secret_key="x", testing=True)
            client = app.test_client()
            self.assertEqual(self._login(client, "reviewer").status_code, 302)
            self.assertEqual(client.get("/api/session").get_json()["role"], "reviewer")
            with Session.begin() as session:
                session.query(User).filter_by(username="reviewer").one().role = "developer"
            self.assertEqual(client.get("/api/session").get_json()["role"], "developer")
            bad = self._login(app.test_client(), "disabled")
            self.assertIn("用户名或密码错误", bad.get_data(as_text=True))

    def test_require_database_does_not_fallback_to_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = __import__("pathlib").Path(tmp) / "kg"
            review = __import__("pathlib").Path(tmp) / "review"
            atlas_fixture(root, review)
            with self.assertRaises(RuntimeError):
                create_app(root, review, require_auth=True, database_url=f"sqlite:///{tmp}/missing.db", require_database=True, users_file=__file__, secret_key="x")


if __name__ == "__main__":
    unittest.main()
