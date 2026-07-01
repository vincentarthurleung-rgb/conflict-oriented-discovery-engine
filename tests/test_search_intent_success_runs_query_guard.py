import tempfile,unittest,json
from pathlib import Path
from code_engine.workflow.steps import run_search_step
from tests.search_intent_helpers import FakePlanner,prepare

class GuardAfterParserTests(unittest.TestCase):
    def test_valid_parser_does_not_bypass_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);prepare(run);run_search_step(run_dir=run,execute=True,api=True,network=True,max_papers=5,semantic_llm_client=FakePlanner(),query="metformin AMPK cancer")
            report=json.loads((run/"artifacts/search_query_guard_report.json").read_text());self.assertEqual(report["allowed_l1_acquisition_queries"],1);self.assertEqual(report["context_only_queries_removed"],1)

if __name__=="__main__":unittest.main()
