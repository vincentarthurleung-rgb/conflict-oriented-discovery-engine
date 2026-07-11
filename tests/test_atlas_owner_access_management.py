import tempfile
import unittest

from code_engine.system_b.persistence.models import EvaluationProject, User
from code_engine.system_b.persistence.services.owner_service import (
    correct_empty_pilot_project_namespace,
    owner_change_role,
    owner_create_invite,
    owner_create_user,
    owner_issue_temporary_password,
    owner_set_invite_enabled,
    owner_update_user,
)
from tests.atlas_db_test_utils import add_user, migrate, session_for


class AtlasOwnerAccessManagementTests(unittest.TestCase):
    def test_owner_creates_temp_password_user_and_cannot_create_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                result = owner_create_user(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, username="new_reviewer", display_name="New Reviewer", role="reviewer")
                self.assertIn("temporary_password", result)
                self.assertNotIn(result["temporary_password"], session.get(User, result["user"]["user_id"]).password_hash)
                self.assertTrue(session.get(User, result["user"]["user_id"]).must_change_password)
                with self.assertRaises(ValueError):
                    owner_create_user(session, owner={"user_id": owner.user_id, "role": "owner"}, username="second_owner", display_name="Second", role="owner")

    def test_owner_immutability_disable_and_role_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                reviewer = add_user(session, "rev", "reviewer")
                with self.assertRaises(ValueError):
                    owner_update_user(session, owner={"user_id": owner.user_id, "role": "owner"}, user_id=owner.user_id, enabled=False)
                changed = owner_change_role(session, owner={"user_id": owner.user_id, "role": "owner"}, user_id=reviewer.user_id, role="developer")
                self.assertEqual(changed["role"], "developer")
                self.assertEqual(session.get(User, reviewer.user_id).session_version, 2)

    def test_invite_shows_plain_code_once_and_db_hash_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                result = owner_create_invite(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, label="pilot", role="reviewer", max_uses=1)
                self.assertIn("invite_code", result)
                invite = session.get(__import__("code_engine.system_b.persistence.models", fromlist=["Invite"]).Invite, result["invite"]["invite_id"])
                self.assertNotIn(result["invite_code"], invite.code_hash)
                disabled = owner_set_invite_enabled(session, owner={"user_id": owner.user_id, "role": "owner"}, invite_id=invite.invite_id, enabled=False)
                self.assertEqual(disabled["status"], "disabled")

    def test_empty_pilot_named_production_project_is_corrected_by_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                project = EvaluationProject(name="Eleven-case Pilot Readiness", namespace="production", status="active")
                session.add(project)
                session.flush()
                result = correct_empty_pilot_project_namespace(session, owner={"user_id": owner.user_id, "role": "owner"}, project_id=project.project_id)
                self.assertTrue(result["changed"])
                self.assertEqual(project.namespace, "pilot")


if __name__ == "__main__":
    unittest.main()
