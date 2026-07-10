import tempfile
import unittest
from unittest.mock import patch

from code_engine.system_b.persistence.models import Annotation
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments, my_review_items
from code_engine.system_b.persistence.services.review_service import save_annotation
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for


class AtlasTransactionAtomicityTests(unittest.TestCase):
    def test_annotation_and_audit_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                reviewer = add_user(session, "reviewer")
                other = add_user(session, "other")
                adj = add_user(session, "adjudicator")
                add_review_item(session, "item1")
                create_project_with_assignments(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, name="prod", namespace="production", annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=reviewer.user_id, secondary_reviewer_user_id=other.user_id, adjudicator_user_id=adj.user_id, item_ids=["item1"])
                assignment = my_review_items(session, user_id=reviewer.user_id)[0]
            session = Session()
            try:
                with patch("code_engine.system_b.persistence.services.review_service.write_audit_event", side_effect=RuntimeError("audit failed")):
                    with self.assertRaises(RuntimeError):
                        save_annotation(session, review_item_id="item1", payload={"assignment_id": assignment["assignment_id"], "final_label": "VALID"}, identity={"user_id": reviewer.user_id, "username": reviewer.username, "display_name": reviewer.display_name, "role": reviewer.role, "authenticated": True}, namespace="production")
                    session.rollback()
                self.assertEqual(session.query(Annotation).count(), 0)
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
