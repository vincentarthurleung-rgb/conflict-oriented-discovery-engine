import json
import tempfile
import unittest
from pathlib import Path
from code_engine.corpus.coverage_precheck import run_global_coverage_precheck


class CoveragePrecheckTests(unittest.TestCase):
    def test_empty_partial_high_and_validation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp); self.assertEqual(run_global_coverage_precheck("sirolimus mtor", None, corpus).recommended_action, "insufficient_global_store")
            store = corpus / "knowledge_store"; store.mkdir()
            for name, count in (("papers", 2), ("claims", 3), ("conflicts", 1), ("mechanism_edges", 1), ("hypotheses", 1), ("validation_results", 1)):
                (store / f"{name}.jsonl").write_text("".join(json.dumps({"id": i, "text": "sirolimus mtor"}) + "\n" for i in range(count)))
            high = run_global_coverage_precheck("sirolimus mtor", None, corpus, .7)
            self.assertEqual(high.recommended_action, "use_existing_knowledge")
            (store / "validation_results.jsonl").write_text("")
            validation = run_global_coverage_precheck("sirolimus mtor", None, corpus, .7)
            self.assertEqual(validation.recommended_action, "run_validation_only")


if __name__ == "__main__": unittest.main()
