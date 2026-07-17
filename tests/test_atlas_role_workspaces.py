from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from code_engine.system_b.authorization import GLOBAL_ROLES, landing_path, navigation_for, role_capabilities
from code_engine.system_b.explorer.explorer_server import create_app
from code_engine.system_b.persistence.models import Assignment, SystemSetting, User
from code_engine.system_b.persistence.services.assignment_service import create_project_with_assignments, my_review_items
from code_engine.system_b.persistence.services.review_service import save_annotation
from tests.atlas_db_test_utils import add_review_item, add_user, atlas_fixture, migrate, session_for


PASSWORD = "correct horse battery staple"


class AtlasRoleWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.display = base / "display"; self.review = base / "review"
        atlas_fixture(self.display, self.review)
        self.url = f"sqlite:///{base / 'atlas.db'}"; migrate(self.url); self.Session = session_for(self.url)
        with self.Session.begin() as db:
            users = {role: add_user(db, role, role=role) for role in ("owner", "admin", "developer", "researcher", "adjudicator")}
            users["reviewer"] = add_user(db, "reviewer", role="reviewer")
            users["reviewer_b"] = add_user(db, "reviewer-b", role="reviewer")
            users["unassigned"] = add_user(db, "unassigned", role="reviewer")
            db.add(SystemSetting(key="owner_user_id", value=users["owner"].user_id))
            item = add_review_item(db, "scoped-item", case_id="case-a", namespace="production")
            other = add_review_item(db, "other-item", case_id="case-b", namespace="production")
            project = create_project_with_assignments(
                db, owner={"user_id": users["owner"].user_id, "role": "owner"}, name="Role Scope", namespace="production",
                annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=users["reviewer"].user_id,
                secondary_reviewer_user_id=users["reviewer_b"].user_id, adjudicator_user_id=users["adjudicator"].user_id,
                item_ids=[item.review_item_id],
            )
            second_project = create_project_with_assignments(
                db, owner={"user_id": users["owner"].user_id, "role": "owner"}, name="Other Scope", namespace="production",
                annotation_schema_version="atlas_annotation_v1", primary_reviewer_user_id=users["reviewer_b"].user_id,
                secondary_reviewer_user_id=users["unassigned"].user_id, adjudicator_user_id=users["adjudicator"].user_id,
                item_ids=[other.review_item_id],
            )
            self.ids = {name: user.user_id for name, user in users.items()}
            self.project_id = project["project_id"]; self.other_project_id = second_project["project_id"]
        self.app = create_app(self.display, self.review, require_auth=True, secret_key="role-test", database_url=self.url, require_database=True, testing=True)

    def tearDown(self): self.tmp.cleanup()

    def login(self, username: str, *, next_path: str | None = None):
        client = self.app.test_client(); path = "/login" + ("?next=" + next_path if next_path else "")
        page = client.get(path); token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        response = client.post(path, data={"csrf_token": token, "username": username, "password": PASSWORD})
        return client, response

    @staticmethod
    def csrf(client):
        with client.session_transaction() as session: return session["csrf_token"]

    def test_registry_landing_navigation_and_capabilities(self):
        self.assertIn("researcher", GLOBAL_ROLES); self.assertIn("adjudicator", GLOBAL_ROLES)
        expected = {"owner": "/owner", "admin": "/admin", "developer": "/console", "reviewer": "/review", "adjudicator": "/adjudication", "researcher": "/discover"}
        for role, path in expected.items():
            self.assertEqual(landing_path(role), path)
            ids = {row["id"] for row in navigation_for(role)}
            self.assertIn(path.strip("/") if role not in {"researcher"} else "discover", ids)
        self.assertFalse(role_capabilities("developer")["manage_users"])
        self.assertFalse(role_capabilities("admin")["freeze_production_gold"])
        self.assertTrue(role_capabilities("owner")["freeze_production_gold"])
        self.assertIn("adjudication", {row["id"] for row in navigation_for("reviewer", {"adjudication_assigned": 1})})

    def test_authoritative_login_redirect_root_and_safe_next(self):
        expected = {"owner": "/owner", "admin": "/admin", "developer": "/console", "reviewer": "/review", "adjudicator": "/adjudication", "researcher": "/discover"}
        for username, path in expected.items():
            client, response = self.login(username)
            self.assertEqual(response.headers["Location"], path)
            self.assertEqual(client.get("/", follow_redirects=False).headers["Location"], path)
        _, blocked = self.login("researcher", next_path="/owner")
        self.assertEqual(blocked.headers["Location"], "/discover")
        _, external = self.login("researcher", next_path="//evil.example/x")
        self.assertEqual(external.headers["Location"], "/discover")
        _, permitted = self.login("reviewer", next_path="/discover")
        self.assertEqual(permitted.headers["Location"], "/discover")

    def test_session_payload_and_page_matrix(self):
        expected = {
            "researcher": {"ok": ["/discover", "/domains", "/cases", "/graph", "/library"], "denied": ["/review", "/adjudication", "/console", "/admin", "/owner"]},
            "reviewer": {"ok": ["/review", "/progress", "/discover"], "denied": ["/adjudication", "/console", "/admin", "/owner"]},
            "adjudicator": {"ok": ["/adjudication", "/discover"], "denied": ["/review", "/console", "/admin", "/owner"]},
            "developer": {"ok": ["/console", "/discover"], "denied": ["/review", "/adjudication", "/admin", "/owner"]},
            "admin": {"ok": ["/admin", "/discover"], "denied": ["/review", "/adjudication", "/console", "/owner", "/evaluation"]},
            "owner": {"ok": ["/owner", "/evaluation", "/discover"], "denied": ["/review", "/adjudication", "/console", "/admin"]},
        }
        for role, matrix in expected.items():
            client, _ = self.login(role)
            session = client.get("/api/session").get_json()
            self.assertEqual(session["landing_path"], landing_path(role)); self.assertIn("capabilities", session); self.assertIn("task_summary", session); self.assertIn("navigation", session)
            self.assertNotIn("session_version", session["user"]); self.assertNotIn("password_hash", str(session)); self.assertNotIn("token_hash", str(session))
            for path in matrix["ok"]: self.assertEqual(client.get(path).status_code, 200, (role, path))
            for path in matrix["denied"]: self.assertEqual(client.get(path).status_code, 403, (role, path))

    def test_api_role_boundaries_and_no_technical_or_governance_inheritance(self):
        researcher, _ = self.login("researcher")
        self.assertEqual(researcher.get("/api/entities").status_code, 403)
        self.assertEqual(researcher.get("/api/review-items").status_code, 403)
        developer, _ = self.login("developer")
        self.assertEqual(developer.get("/api/console/overview").status_code, 200)
        self.assertEqual(developer.get("/api/review-items").status_code, 403)
        self.assertEqual(developer.get("/api/adjudication/queue").status_code, 403)
        self.assertEqual(developer.get("/api/owner/users").status_code, 403)
        admin, _ = self.login("admin")
        self.assertEqual(admin.get("/api/admin/overview").status_code, 200)
        self.assertEqual(admin.get("/api/db/health").status_code, 403)
        self.assertEqual(admin.get("/api/owner/gold/readiness").status_code, 403)
        owner, _ = self.login("owner")
        self.assertEqual(owner.get("/api/owner/overview").status_code, 200)
        self.assertEqual(owner.get("/api/db/health").status_code, 403)

    def test_reviewer_object_scope_and_blind_payload_isolation(self):
        reviewer, _ = self.login("reviewer")
        items = reviewer.get("/api/review-items").get_json()["items"]
        self.assertEqual([row["review_item_id"] for row in items], ["scoped-item"])
        self.assertEqual(reviewer.get("/api/review-item/other-item").status_code, 404)
        self.assertNotIn("reviewer-b", str(items)); self.assertNotIn("annotations", str(items))
        self.assertEqual(reviewer.get("/api/review-export.jsonl").status_code, 403)

    def test_adjudicator_requires_assignment_double_submission_and_disagreement(self):
        adjudicator, _ = self.login("adjudicator")
        self.assertEqual(adjudicator.get("/api/adjudication/queue").get_json()["items"], [])
        self.assertEqual(adjudicator.get(f"/api/adjudication/scoped-item?project_id={self.project_id}").status_code, 404)
        with self.Session.begin() as db:
            a = db.get(User, self.ids["reviewer"]); item = my_review_items(db, user_id=a.user_id, project_id=self.project_id)[0]
            save_annotation(db, review_item_id="scoped-item", payload={"assignment_id": item["assignment_id"], "final_label": "VALID"}, identity={"user_id": a.user_id, "username": a.username, "display_name": a.display_name, "role": a.role, "authenticated": True}, namespace="production")
        early = adjudicator.get(f"/api/adjudication/scoped-item?project_id={self.project_id}")
        self.assertEqual(early.status_code, 404); self.assertNotIn("VALID", early.get_data(as_text=True))
        with self.Session.begin() as db:
            b = db.get(User, self.ids["reviewer_b"]); item = my_review_items(db, user_id=b.user_id, project_id=self.project_id)[0]
            save_annotation(db, review_item_id="scoped-item", payload={"assignment_id": item["assignment_id"], "final_label": "PARTIAL"}, identity={"user_id": b.user_id, "username": b.username, "display_name": b.display_name, "role": b.role, "authenticated": True}, namespace="production")
        queue = adjudicator.get("/api/adjudication/queue").get_json()["items"]
        self.assertEqual([row["review_item_id"] for row in queue], ["scoped-item"])
        detail = adjudicator.get(f"/api/adjudication/scoped-item?project_id={self.project_id}").get_json()
        self.assertEqual({row["reviewer_label"] for row in detail["annotations"]}, {"Reviewer A", "Reviewer B"})
        self.assertNotIn("reviewer-b", str(detail)); self.assertNotIn("reviewer_username", str(detail))

    def test_admin_cannot_modify_owner_or_promote_to_owner(self):
        admin, _ = self.login("admin"); headers = {"X-CSRF-Token": self.csrf(admin)}
        target = self.ids["reviewer"]
        denied = admin.post(f"/api/admin/user/{target}/change-role", json={"role": "owner"}, headers=headers)
        self.assertEqual(denied.status_code, 403)
        owner_target = admin.post(f"/api/admin/user/{self.ids['owner']}/disable", json={}, headers=headers)
        self.assertEqual(owner_target.status_code, 403)
        created = admin.post("/api/admin/users", json={"username": "new-reader", "display_name": "New Reader", "role": "researcher"}, headers=headers)
        self.assertEqual(created.status_code, 201)

    def test_role_change_invalidates_old_session_and_new_landing(self):
        reviewer, _ = self.login("reviewer"); owner, _ = self.login("owner")
        changed = owner.post(f"/api/owner/user/{self.ids['reviewer']}/change-role", json={"role": "researcher"}, headers={"X-CSRF-Token": self.csrf(owner)})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(reviewer.get("/api/session").status_code, 401)
        relogin, response = self.login("reviewer")
        self.assertEqual(response.headers["Location"], "/discover")
        self.assertNotIn("review", relogin.get("/api/session").get_json()["navigation_capabilities"])


if __name__ == "__main__": unittest.main()
