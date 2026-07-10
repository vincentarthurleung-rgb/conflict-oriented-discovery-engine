import tempfile
import unittest

from code_engine.system_b.persistence.models import Assignment
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for


class AtlasOwnerAssignmentsTests(unittest.TestCase):
    def test_owner_creates_primary_secondary_and_adjudicator_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                a = add_user(session, "reviewer_a")
                b = add_user(session, "reviewer_b")
                adj = add_user(session, "adjudicator")
                add_review_item(session, "item1")
                result = create_project_with_assignments(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, name="prod", namespace="production", annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=a.user_id, secondary_reviewer_user_id=b.user_id, adjudicator_user_id=adj.user_id, item_ids=["item1"])
                self.assertEqual(result["assignment_count"], 3)
                self.assertEqual(session.query(Assignment).filter_by(project_id=result["project_id"]).count(), 3)


if __name__ == "__main__":
    unittest.main()
