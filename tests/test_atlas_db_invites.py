import tempfile
import threading
import unittest

from sqlalchemy.exc import IntegrityError

from code_engine.system_b.persistence.models import User
from code_engine.system_b.persistence.services.auth_service import create_invite, create_owner, register_with_invite
from tests.atlas_db_test_utils import migrate, session_for


class AtlasDbInviteTests(unittest.TestCase):
    def test_concurrent_last_invite_use_allows_one_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            code = "invite-code-with-enough-entropy"
            with Session.begin() as session:
                create_invite(session, code=code, label="one", max_uses=1)
            barrier = threading.Barrier(2)
            results = []

            def worker(username):
                session = Session()
                try:
                    barrier.wait()
                    register_with_invite(session, username=username, display_name=username, password="correct horse battery staple", confirm_password="correct horse battery staple", invite_code=code)
                    session.commit()
                    results.append("ok")
                except Exception:
                    session.rollback()
                    results.append("failed")
                finally:
                    session.close()

            threads = [threading.Thread(target=worker, args=(f"user{i}",)) for i in range(2)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            self.assertEqual(results.count("ok"), 1)
            with Session() as session:
                self.assertEqual(session.query(User).filter(User.username.like("user%")).count(), 1)

    def test_only_one_enabled_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                create_owner(session, username="vincent", display_name="Vincent", password="correct horse battery staple")
            with Session.begin() as session:
                with self.assertRaises(ValueError):
                    create_owner(session, username="other", display_name="Other", password="correct horse battery staple")


if __name__ == "__main__":
    unittest.main()
