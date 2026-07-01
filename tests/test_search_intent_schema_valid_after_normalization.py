import tempfile
import unittest
from pathlib import Path

from code_engine.search.semantic_search_intent import plan_semantic_search_intent


RAW = {"seed_triple": {"subject": {"name": "metformin", "aliases": "Glucophage"},
       "relation": {"name": "activates", "family": "activates", "directional": "subject>object"},
       "object": {"name": "AMPK"}, "context": {"context_terms": ["cancer"]}},
       "query_groups": {"direct_relation": [{"query": '"metformin" AND "AMPK" AND activates',
       "purpose": "Find direct statements", "allowed_for_l1_acquisition": "yes"}]}}


class FakePlanner:
    def extract_json(self, prompt): return RAW


class SchemaAfterNormalizationTests(unittest.TestCase):
    def test_real_failure_shape_validates_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = plan_semantic_search_intent("metformin AMPK cancer", domain_id="general_biomedical",
                                                seed_triple={}, llm_client=FakePlanner(), run_dir=tmp)
            self.assertTrue(value.search_intent_schema_valid_after_normalization)
            self.assertTrue(value.normalization_applied)
            self.assertTrue((Path(tmp) / "artifacts/search_intent_normalization_report.json").exists())


if __name__ == "__main__": unittest.main()
