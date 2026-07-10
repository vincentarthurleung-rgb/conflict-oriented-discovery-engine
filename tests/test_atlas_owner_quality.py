import tempfile
import unittest

from code_engine.system_b.persistence.services.owner_service import owner_quality_alerts
from tests.atlas_db_test_utils import migrate, session_for


class AtlasOwnerQualityTests(unittest.TestCase):
    def test_quality_alerts_are_not_misconduct_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                result = owner_quality_alerts(session)
                self.assertIn("do not automatically imply misconduct", result["note"])


if __name__ == "__main__":
    unittest.main()
