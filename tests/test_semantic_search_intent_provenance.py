import json,tempfile,unittest
from pathlib import Path
from code_engine.workflow.runtime_provenance import build_runtime_provenance
from tests.search_intent_helpers import PAYLOAD

class SearchIntentProvenanceTests(unittest.TestCase):
    def test_provenance_reads_intent_and_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); a=run/"artifacts"; a.mkdir(); payload={**PAYLOAD,"confidence_source":"llm_response_confidence","llm_search_intent_used":True,"deterministic_search_fallback_used":False}
            (a/"semantic_search_intent.json").write_text(json.dumps(payload)); (a/"search_query_guard_report.json").write_text(json.dumps({"off_seed_queries_removed":2}))
            value=build_runtime_provenance(run,repository_root=Path.cwd(),resume_explicit=False,entity_registry_path=None,automatic_pilot_registry=False,l1_mode="abstract_screening",l1_task_cache_enabled=False,update_global_corpus=False,paper_registry_enabled=True,coverage_precheck=False,allow_coverage_short_circuit=False,merge_knowledge_store=False,update_global_knowledge_store=False,execute=False)
        self.assertTrue(value["semantic_search_intent"]["llm_search_intent_used"]); self.assertEqual(value["query_guard"]["off_seed_queries_removed"],2)
        self.assertEqual(value["semantic_search_intent"]["confidence"], .82); self.assertEqual(value["semantic_search_intent"]["confidence_source"], "llm_response_confidence")

if __name__ == "__main__": unittest.main()
