import re
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.database import session_scope
from code_engine.system_b.persistence.models import Assignment, EvaluationProject
from tests.atlas_db_test_utils import add_review_item, add_user, atlas_fixture, migrate, session_for


class AtlasReviewAssignmentScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.display = base / "display"
        self.review = base / "legacy-review"
        atlas_fixture(self.display, self.review, item_id="legacy-unassigned")
        self.url = f"sqlite:///{base / 'atlas.db'}"
        migrate(self.url)
        Session = session_for(self.url)
        with Session.begin() as db:
            reviewer = add_user(db, "reviewer-a")
            other = add_user(db, "reviewer-b")
            owner = add_user(db, "owner", role="owner")
            first = add_review_item(db, "assigned-a", case_id="case-a", namespace="pilot")
            second = add_review_item(db, "assigned-b", case_id="case-b", namespace="pilot", item_type="conflict_pair")
            project = EvaluationProject(name="Scoped Pilot", namespace="pilot", status="active", created_by_user_id=owner.user_id)
            db.add(project)
            db.flush()
            db.add_all([
                Assignment(project_id=project.project_id, review_item_id=first.review_item_id, reviewer_user_id=reviewer.user_id, assignment_role="primary", status="assigned", assigned_by_user_id=owner.user_id),
                Assignment(project_id=project.project_id, review_item_id=second.review_item_id, reviewer_user_id=reviewer.user_id, assignment_role="primary", status="assigned", assigned_by_user_id=owner.user_id),
                Assignment(project_id=project.project_id, review_item_id=first.review_item_id, reviewer_user_id=other.user_id, assignment_role="secondary", status="assigned", assigned_by_user_id=owner.user_id),
            ])
        self.Session = Session
        self.app = create_app(
            self.display,
            self.review,
            require_auth=True,
            secret_key="scope-test",
            database_url=self.url,
            require_database=True,
            testing=True,
        )
        self.client = self.app.test_client()
        self.login("reviewer-a")

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, username):
        page = self.client.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        response = self.client.post("/login", data={"csrf_token": token, "username": username, "password": "correct horse battery staple"})
        self.assertEqual(response.status_code, 302)

    def test_workspace_and_filters_only_include_current_assignments(self):
        workspace = self.client.get("/api/review-workspace").get_json()
        self.assertEqual(workspace["total_items"], 2)
        self.assertEqual([row["case_id"] for row in workspace["cases"]], ["case-a", "case-b"])

        case_items = self.client.get("/api/review-items?case_id=case-a&item_type=fulltext_l1_claim").get_json()
        self.assertEqual(case_items["total"], 1)
        self.assertEqual(case_items["items"][0]["review_item_id"], "assigned-a")
        self.assertNotIn("legacy-unassigned", str(workspace) + str(case_items))

    def test_metrics_are_read_only_and_legacy_writes_exports_are_blocked(self):
        with self.Session() as db:
            before_projects = db.scalar(select(func.count()).select_from(EvaluationProject))
        metrics = self.client.get("/api/review-metrics")
        self.assertEqual(metrics.status_code, 200)
        self.assertEqual(metrics.get_json()["unreviewed_count"], 2)
        with self.Session() as db:
            after_projects = db.scalar(select(func.count()).select_from(EvaluationProject))
        self.assertEqual(after_projects, before_projects)

        with self.client.session_transaction() as session:
            csrf = session["csrf_token"]
        for path, method in (("/api/review-metrics/recompute", "post"), ("/api/review-export.csv", "get"), ("/api/review-export.jsonl", "get")):
            response = getattr(self.client, method)(path, headers={"X-CSRF-Token": csrf})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"], "legacy_review_artifact_access_disabled")


if __name__ == "__main__":
    unittest.main()
