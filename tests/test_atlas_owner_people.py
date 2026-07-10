import tempfile
import unittest

from code_engine.system_b.persistence.services.owner_service import owner_people
from tests.atlas_db_test_utils import add_user, migrate, session_for


class AtlasOwnerPeopleTests(unittest.TestCase):
    def test_owner_people_lists_roles_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                add_user(session, "owner", "owner")
                add_user(session, "reviewer")
                result = owner_people(session)
                self.assertEqual(result["total"], 2)
                self.assertIn("assigned", result["items"][0])


if __name__ == "__main__":
    unittest.main()
