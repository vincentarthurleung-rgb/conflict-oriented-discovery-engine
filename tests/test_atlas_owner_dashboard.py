import tempfile
import unittest

from code_engine.system_b.persistence.database import create_atlas_engine, session_factory, session_scope
from code_engine.system_b.persistence.models import SystemSetting, User
from code_engine.system_b.persistence.services.owner_service import owner_overview, validate_single_owner


class AtlasOwnerDashboardTests(unittest.TestCase):
    def test_single_owner_validation_and_overview_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_atlas_engine(f"sqlite:///{tmp}/atlas.db")
            from code_engine.system_b.persistence.models import Base
            Base.metadata.create_all(engine)
            factory = session_factory(engine)
            with session_scope(factory) as session:
                owner = User(username="owner", display_name="Owner", password_hash="x", role="owner", enabled=True)
                reviewer = User(username="rev", display_name="Reviewer", password_hash="x", role="reviewer", enabled=True)
                session.add_all([owner, reviewer])
                session.flush()
                session.add(SystemSetting(key="owner_user_id", value=owner.user_id))
            with session_scope(factory) as session:
                self.assertTrue(validate_single_owner(session)["ok"])
                overview = owner_overview(session)
                self.assertEqual(overview["formal_user_count"], 2)
                self.assertEqual(overview["active_reviewer_count"], 1)


if __name__ == "__main__":
    unittest.main()
