import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_abstract_l1_step


class MissingClientTests(unittest.TestCase):
    def test_execute_api_without_client_is_explicitly_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts=Path(tmp)/"artifacts"; artifacts.mkdir()
            (artifacts/"acquisition_report.json").write_text(json.dumps({"candidate_papers":[{"paper_id":"P","abstract":"Ketamine increased BDNF."}]}))
            (artifacts/"domain_profile.json").write_text("{}")
            result=run_abstract_l1_step(run_dir=Path(tmp),execute=True,api=True,max_papers=None,l1_mode="abstract_screening",repository_root=Path(tmp),l1_task_cache_enabled=False)
            self.assertEqual(result.status,"blocked")
            self.assertEqual(result.skipped_reason,"l1_llm_client_not_configured")


if __name__ == "__main__": unittest.main()
