import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments
from tests.atlas_db_test_utils import add_review_item, add_user, atlas_fixture, migrate, session_for


class AtlasAssignmentScopeTests(unittest.TestCase):
    def _login(self, client, username):
        page = client.get("/login").get_data(as_text=True)
        token = page.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
        client.post("/login", data={"username": username, "password": "correct horse battery staple", "csrf_token": token})

    def test_review_items_are_filtered_to_current_reviewer_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                a = add_user(session, "reviewer_a")
                b = add_user(session, "reviewer_b")
                adjudicator = add_user(session, "adjudicator")
                add_review_item(session, "item1")
                add_review_item(session, "item2")
                create_project_with_assignments(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, name="prod", namespace="production", annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=a.user_id, secondary_reviewer_user_id=b.user_id, adjudicator_user_id=adjudicator.user_id, item_ids=["item1"])
            root = Path(tmp) / "kg"
            review = Path(tmp) / "review"
            atlas_fixture(root, review)
            app = create_app(root, review, require_auth=True, database_url=url, require_database=True, secret_key="x", testing=True)
            client = app.test_client()
            self._login(client, "reviewer_a")
            items = client.get("/api/review-items").get_json()["items"]
            self.assertEqual([x["review_item_id"] for x in items], ["item1"])


if __name__ == "__main__":
    unittest.main()
