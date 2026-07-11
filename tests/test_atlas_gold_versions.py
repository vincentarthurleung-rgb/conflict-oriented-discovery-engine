import tempfile
import unittest

from code_engine.system_b.persistence.models import GoldRecord
from code_engine.system_b.persistence.services.adjudication_service import submit_adjudication
from code_engine.system_b.persistence.services.gold_service import freeze_gold, gold_readiness
from tests.atlas_db_test_utils import migrate, session_for
from tests.test_atlas_adjudication_workflow import prepared_disagreement


class AtlasGoldVersionTests(unittest.TestCase):
    def test_owner_freezes_new_gold_version_after_adjudication(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner, adj, project = prepared_disagreement(session)
                submit_adjudication(session, identity={"user_id": adj.user_id, "username": adj.username, "role": "reviewer", "authenticated": True}, project_id=project["project_id"], review_item_id="item1", payload={"final_label": "VALID"})
                ready = gold_readiness(session, project_id=project["project_id"])
                self.assertTrue(ready["ready"])
                result = freeze_gold(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, project_id=project["project_id"], confirm=True)
                self.assertEqual(result["gold_dataset_version"], 1)
                self.assertEqual(result["gold_version"], 1)
                self.assertEqual(session.query(GoldRecord).filter_by(project_id=project["project_id"], status="frozen").count(), 1)


if __name__ == "__main__":
    unittest.main()
