import json
import tempfile
import unittest
from pathlib import Path

from code_engine.batch.triple_runner import run_triple_batch


class BatchResumeInvalidationTests(unittest.TestCase):
    def test_changed_config_reruns_triple(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            triples = [{"query_text": "metformin AMPK cancer"}]
            base = {"until": "report", "l1_mode": "abstract_screening", "merge_knowledge_store": False}
            run_triple_batch(triples, root / "batch", batch_id="b", workflow_kwargs=base)
            result = run_triple_batch(
                triples, root / "batch", batch_id="b", resume=True,
                workflow_kwargs={**base, "min_abstract_evidence_count": 7},
            )
            self.assertEqual(result["resumed_triple_count"], 0)


if __name__ == "__main__":
    unittest.main()
