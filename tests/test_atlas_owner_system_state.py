import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.auth import hash_password
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import Assignment, EvaluationProject, SystemSetting, User
from code_engine.system_b.persistence.services.owner_service import owner_pilot_preview, owner_system_state
from tests.atlas_db_test_utils import add_review_item, migrate
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


class AtlasOwnerSystemStateTests(unittest.TestCase):
    def _fixture(self, tmp):
        root = Path(tmp) / "kg"
        root.mkdir()
        KnowledgeExplorerTests().fixture(root)
        url = f"sqlite:///{tmp}/atlas.db"
        migrate(url)
        factory = session_factory(create_atlas_engine(url))
        password = hash_password("correct horse battery staple")
        with session_scope(factory) as session:
            owner = User(username="owner", display_name="Owner", password_hash=password, role="owner", enabled=True)
            primary = User(username="primary", display_name="Primary", password_hash=password, role="reviewer", enabled=True)
            secondary = User(username="secondary", display_name="Secondary", password_hash=password, role="reviewer", enabled=True)
            adjudicator = User(username="adjudicator", display_name="Adjudicator", password_hash=password, role="developer", enabled=True)
            disabled = User(username="disabled", display_name="Disabled", password_hash=password, role="reviewer", enabled=False)
            session.add_all([owner, primary, secondary, adjudicator, disabled])
            session.flush()
            session.add(SystemSetting(key="owner_user_id", value=owner.user_id))
            item1 = add_review_item(session, "pilot-item-1", case_id="case-a", namespace="pilot", item_type="conflict_pair")
            item2 = add_review_item(session, "pilot-item-2", case_id="case-b", namespace="pilot", item_type="fulltext_l1_claim")
            project = EvaluationProject(name="Pilot", namespace="pilot", status="active", created_by_user_id=owner.user_id)
            session.add(project)
            session.flush()
            for role, reviewer, item in (("primary", primary, item1), ("secondary", secondary, item1), ("adjudicator", adjudicator, item1), ("primary", primary, item2)):
                session.add(Assignment(project_id=project.project_id, review_item_id=item.review_item_id, reviewer_user_id=reviewer.user_id, assignment_role=role, status="assigned", assigned_by_user_id=owner.user_id))
            ids = {"owner": owner.user_id, "primary": primary.user_id, "secondary": secondary.user_id, "adjudicator": adjudicator.user_id, "disabled": disabled.user_id}
        return root, url, factory, ids

    def _login(self, client, username):
        page = client.get("/login").get_data(as_text=True)
        token = page.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
        return client.post("/login", data={"username": username, "password": "correct horse battery staple", "csrf_token": token})

    def test_system_state_counts_items_cases_and_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            _root, _url, factory, _ids = self._fixture(tmp)
            with session_scope(factory) as session:
                state = owner_system_state(session, database_path="tmp/atlas.db", schema_head="head")
            self.assertEqual(state["database_path"], "tmp/atlas.db")
            self.assertEqual(state["schema_head"], "head")
            self.assertEqual(state["review_items_by_namespace"][0]["review_items"], 2)
            self.assertEqual(state["review_items_by_namespace"][0]["unique_cases"], 2)
            self.assertEqual(sum(row["assignments"] for row in state["assignment_counts"]), 4)

    def test_pilot_preview_blocks_invalid_reviewer_and_missing_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            _root, _url, factory, ids = self._fixture(tmp)
            with session_scope(factory) as session:
                preview = owner_pilot_preview(
                    session,
                    primary_reviewer_user_id=ids["primary"],
                    secondary_reviewer_user_id=ids["primary"],
                    adjudicator_user_id=ids["disabled"],
                )
            codes = {row["code"] for row in preview["errors"]}
            self.assertIn("primary_secondary_must_differ", codes)
            self.assertIn("user_not_available", codes)
            self.assertTrue(preview["blocked"])
            self.assertEqual(preview["unique_review_items"], 2)
            self.assertEqual(preview["unique_cases"], 2)

    def test_owner_system_state_api_is_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, url, _factory, _ids = self._fixture(tmp)
            app = create_app(root, None, require_auth=True, secret_key="x", database_url=url, require_database=True, testing=True)
            reviewer_client = app.test_client()
            self._login(reviewer_client, "primary")
            self.assertEqual(reviewer_client.get("/api/owner/system-state").status_code, 403)
            owner_client = app.test_client()
            self._login(owner_client, "owner")
            response = owner_client.get("/api/owner/system-state")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("assignment_counts", data)
            self.assertEqual(data["owner"]["username"], "owner")


if __name__ == "__main__":
    unittest.main()
