import tempfile
import unittest

from code_engine.system_b.persistence.services.auth_service import change_password, complete_password_reset, issue_password_reset, load_identity
from tests.atlas_db_test_utils import add_user, migrate, session_for


class AtlasPasswordAndSessionSecurityTests(unittest.TestCase):
    def test_password_change_increments_session_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                user = add_user(session, "reviewer")
                old_version = user.session_version
                change_password(session, user_id=user.user_id, current_password="correct horse battery staple", new_password="new correct horse battery staple", confirm_password="new correct horse battery staple")
                self.assertEqual(user.session_version, old_version + 1)
                self.assertIsNone(load_identity(session, user.user_id, old_version))

    def test_reset_token_hash_only_and_one_time_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                user = add_user(session, "reviewer")
                issued = issue_password_reset(session, target_user=user, owner={"user_id": owner.user_id, "role": "owner"})
                self.assertIn("token", issued)
                self.assertNotIn(issued["token"], session.query(__import__("code_engine.system_b.persistence.models", fromlist=["PasswordResetToken"]).PasswordResetToken).one().token_hash)
                complete_password_reset(session, token=issued["token"], new_password="another correct horse staple", confirm_password="another correct horse staple")
                with self.assertRaises(Exception):
                    complete_password_reset(session, token=issued["token"], new_password="yet another correct horse", confirm_password="yet another correct horse")


if __name__ == "__main__":
    unittest.main()
