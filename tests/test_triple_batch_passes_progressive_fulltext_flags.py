import json
import tempfile
import unittest
from pathlib import Path

from code_engine.batch.triple_runner import run_triple_batch
from code_engine.cli.triple_batch import build_parser


class TripleBatchProgressiveFlagsTests(unittest.TestCase):
    def test_default_cli_is_safe(self):
        parser = build_parser()
        args = parser.parse_args(["--triples", "x.jsonl", "--batch-dir", "out"])
        self.assertFalse(args.execute)
        self.assertFalse(args.api)
        self.assertFalse(args.network)
        self.assertEqual(args.l1_mode, "abstract_screening")

    def test_progressive_flags_reach_each_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_triple_batch(
                [{"query_text": "metformin AMPK cancer"}], root / "batch",
                paper_artifact_cache_index=root / "cache.jsonl",
                workflow_kwargs={"until": "fulltext_conflict_confirmation", "l1_mode": "progressive_fulltext",
                                 "enable_fulltext_escalation": True, "allow_uncertain_intake": True,
                                 "merge_knowledge_store": False},
            )
            row = json.loads(Path(result["processed_triples_index"]).read_text().splitlines()[0])
            run = Path(row["run_dir"])
            state = json.loads((run / "run_state.json").read_text())
            self.assertEqual(state["l1_mode"], "progressive_fulltext")
            self.assertTrue(state["fulltext_escalation_enabled"])
            self.assertTrue((run / "artifacts/fulltext_availability_records.jsonl").exists())
            self.assertTrue((run / "artifacts/fulltext_acquisition_records.jsonl").exists())


if __name__ == "__main__": unittest.main()
