import tempfile
import unittest
from pathlib import Path

from code_engine.cli.system_b_evaluation_export_paper import export_paper
from code_engine.system_b.persistence.models import MetricRun
from code_engine.system_b.persistence.services.adjudication_service import submit_adjudication
from code_engine.system_b.persistence.services.evaluation_service import run_evaluation
from code_engine.system_b.persistence.services.gold_service import freeze_gold
from tests.atlas_db_test_utils import migrate, session_for
from tests.test_atlas_adjudication_workflow import prepared_disagreement


class AtlasPaperExportTests(unittest.TestCase):
    def test_paper_export_writes_manifest_tables_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{tmp}/atlas.db"
            migrate(url)
            Session = session_for(url)
            with Session.begin() as session:
                owner, adj, project = prepared_disagreement(session)
                submit_adjudication(session, identity={"user_id": adj.user_id, "username": adj.username, "role": "reviewer", "authenticated": True}, project_id=project["project_id"], review_item_id="item1", payload={"final_label": "VALID"})
                frozen = freeze_gold(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, project_id=project["project_id"], confirm=True)
                run = run_evaluation(session, owner={"user_id": owner.user_id, "username": owner.username, "role": "owner"}, project_id=project["project_id"], gold_version=frozen["gold_version"], predictions={"item1": "VALID"})
            out = export_paper(url, Path(tmp) / "eval", project["project_id"], run["metric_run_id"])
            self.assertTrue((out / "evaluation_manifest.json").exists())
            self.assertTrue((out / "paper_tables" / "table_1_dataset_statistics.csv").exists())
            self.assertTrue((out / "provenance" / "metric_run.json").exists())


if __name__ == "__main__":
    unittest.main()
