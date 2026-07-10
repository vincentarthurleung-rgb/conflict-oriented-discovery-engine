import tempfile
import unittest

from code_engine.system_b.persistence.services.agreement_service import compare_annotations
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments, my_review_items
from code_engine.system_b.persistence.services.review_service import save_annotation
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for


class AtlasDisagreementDetectionTests(unittest.TestCase):
    def test_disagreement_summary_is_deterministic(self):
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
                project = create_project_with_assignments(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, name="prod", namespace="production", annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=a.user_id, secondary_reviewer_user_id=b.user_id, adjudicator_user_id=adj.user_id, item_ids=["item1"])
                ai, bi = my_review_items(session, user_id=a.user_id)[0], my_review_items(session, user_id=b.user_id)[0]
                save_annotation(session, review_item_id="item1", payload={"assignment_id": ai["assignment_id"], "final_label": "VALID", "direction_correct": True}, identity={"user_id": a.user_id, "username": a.username, "display_name": a.display_name, "role": a.role, "authenticated": True}, namespace="production")
                save_annotation(session, review_item_id="item1", payload={"assignment_id": bi["assignment_id"], "final_label": "PARTIAL", "direction_correct": False}, identity={"user_id": b.user_id, "username": b.username, "display_name": b.display_name, "role": b.role, "authenticated": True}, namespace="production")
                result = compare_annotations(session, project_id=project["project_id"], review_item_id="item1")
                self.assertEqual(result["status"], "needs_adjudication")
                self.assertEqual(result["field_differences"]["final_label"], ["VALID", "PARTIAL"])


if __name__ == "__main__":
    unittest.main()
