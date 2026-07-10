import tempfile
import unittest

from code_engine.system_b.persistence.services.adjudication_service import submit_adjudication
from code_engine.system_b.persistence.services.evaluation_service import evaluation_readiness, run_evaluation
from code_engine.system_b.persistence.services.gold_service import freeze_gold
from tests.atlas_db_test_utils import migrate, session_for
from tests.test_atlas_adjudication_workflow import prepared_disagreement


class AtlasEvaluationReadinessTests(unittest.TestCase):
    def test_readiness_and_metric_run_use_frozen_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner, adj, project = prepared_disagreement(session)
                self.assertEqual(evaluation_readiness(session, project_id=project["project_id"])["primary_endpoints"]["conflict_macro_f1"]["status"], "needs_annotation")
                submit_adjudication(session, identity={"user_id": adj.user_id, "username": adj.username, "role": "reviewer", "authenticated": True}, project_id=project["project_id"], review_item_id="item1", payload={"final_label": "VALID"})
                frozen = freeze_gold(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, project_id=project["project_id"], confirm=True)
                ready = evaluation_readiness(session, project_id=project["project_id"], gold_version=frozen["gold_version"])
                self.assertEqual(ready["primary_endpoints"]["conflict_macro_f1"]["status"], "ready")
                run = run_evaluation(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, project_id=project["project_id"], gold_version=frozen["gold_version"])
                self.assertEqual(run["status"], "ready")


if __name__ == "__main__":
    unittest.main()
