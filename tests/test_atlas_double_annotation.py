import tempfile
import unittest

from code_engine.system_b.annotation_schemas import schema_for_item_type
from code_engine.system_b.persistence.models import Annotation, UserOnboardingAcknowledgement
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments, my_review_items
from code_engine.system_b.persistence.services.review_service import save_annotation
from tests.atlas_db_test_utils import add_review_item, add_user, migrate, session_for


class AtlasDoubleAnnotationTests(unittest.TestCase):
    def test_two_reviewers_write_independent_annotations(self):
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
                a_item = my_review_items(session, user_id=a.user_id)[0]
                b_item = my_review_items(session, user_id=b.user_id)[0]
                save_annotation(session, review_item_id="item1", payload={"assignment_id": a_item["assignment_id"], "final_label": "VALID"}, identity={"user_id": a.user_id, "username": a.username, "display_name": a.display_name, "role": a.role, "authenticated": True}, namespace="production")
                save_annotation(session, review_item_id="item1", payload={"assignment_id": b_item["assignment_id"], "final_label": "PARTIAL"}, identity={"user_id": b.user_id, "username": b.username, "display_name": b.display_name, "role": b.role, "authenticated": True}, namespace="production")
                self.assertEqual(session.query(Annotation).filter_by(project_id=project["project_id"]).count(), 2)

    def test_pilot_annotation_resolves_assignment_from_project_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                reviewer = add_user(session, "reviewer_a")
                other = add_user(session, "reviewer_b")
                adj = add_user(session, "adjudicator")
                add_review_item(session, "item1", namespace="pilot")
                project = create_project_with_assignments(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, name="pilot", namespace="pilot", annotation_schema_version="atlas_schema_registry_v1", primary_reviewer_user_id=reviewer.user_id, secondary_reviewer_user_id=other.user_id, adjudicator_user_id=adj.user_id, item_ids=["item1"])
                schema = schema_for_item_type("fulltext_l1_claim")
                session.add(UserOnboardingAcknowledgement(user_id=reviewer.user_id, project_id=project["project_id"], schema_id=schema.schema_id, instructions_version=schema.instructions_version, instructions_hash=schema.instructions_hash))
                session.flush()
                result = save_annotation(
                    session,
                    review_item_id="item1",
                    payload={"project_id": project["project_id"], "review_disposition": "submitted", "structured_fields": {"final_label": "VALID"}},
                    identity={"user_id": reviewer.user_id, "username": reviewer.username, "display_name": reviewer.display_name, "role": reviewer.role, "authenticated": True},
                    namespace="pilot",
                )
                self.assertEqual(result["project_id"], project["project_id"])
                self.assertEqual(session.query(Annotation).filter_by(project_id=project["project_id"]).count(), 1)


if __name__ == "__main__":
    unittest.main()
