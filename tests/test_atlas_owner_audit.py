import tempfile
import unittest

from code_engine.system_b.persistence.services.audit_service import write_audit_event
from code_engine.system_b.persistence.services.owner_service import owner_audit_events
from tests.atlas_db_test_utils import add_user, migrate, session_for


class AtlasOwnerAuditTests(unittest.TestCase):
    def test_owner_audit_filters_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner = add_user(session, "owner", "owner")
                write_audit_event(session, action="gold_frozen", object_type="gold_version", actor={"user_id": owner.user_id, "username": owner.username})
                result = owner_audit_events(session, action="gold_frozen")
                self.assertEqual(result["total"], 1)


if __name__ == "__main__":
    unittest.main()
