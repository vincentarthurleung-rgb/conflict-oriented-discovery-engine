import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.cli.fulltext_bridge_replay import main, replay_fulltext_bridge_from_run


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class FulltextBridgeReplayCliTests(unittest.TestCase):
    def test_cli_reads_candidate_file_and_writes_bridge_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            output = root / "bridge"
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(
                json.dumps({"paper_id": "p1", "pmid": "111", "selection_score": 0.9, "anchor_strength": "strong"}) + "\n",
                encoding="utf-8",
            )

            rc = main([
                "--case-id", "case_v1",
                "--source-run", str(source),
                "--output-run", str(output),
                "--overwrite",
            ])

            self.assertEqual(rc, 0)
            audit = rows(output / "artifacts" / "fulltext_candidate_bridge_audit.jsonl")
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0]["skip_reason"], "missing_pmcid")

    def test_cli_does_not_call_l2_or_entity_normalization(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(
                json.dumps({"paper_id": "p1", "pmid": "111", "selection_score": 0.9, "anchor_strength": "strong"}) + "\n",
                encoding="utf-8",
            )
            with patch("code_engine.workflow.steps.run_l2_abstract_step", side_effect=AssertionError("L2 should not run"), create=True), \
                 patch("code_engine.normalization.llm_entity_cleaner.clean_entities_with_llm", side_effect=AssertionError("entity cleaner should not run"), create=True):
                result = replay_fulltext_bridge_from_run(
                    case_id="case_v1",
                    source_run=source,
                    output_run=root / "out",
                    overwrite=True,
                )
            self.assertIn("l2_entity_normalization", result["skipped_stages"])

    def test_wnt_like_l35_only_candidates_produce_candidate_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "l35_fulltext_discovery_candidate_papers.jsonl").write_text(
                json.dumps({"paper_id": "wnt-like", "pmid": "222", "selection_score": 0.9, "anchor_strength": "strong"}) + "\n",
                encoding="utf-8",
            )
            result = replay_fulltext_bridge_from_run(
                case_id="wnt_beta_catenin_cancer_stemness_immunity_discovery_v1",
                source_run=source,
                output_run=root / "out",
                overwrite=True,
            )
            availability = json.loads((root / "out" / "artifacts" / "fulltext_availability_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(result["candidate_count"], 1)
            self.assertGreater(availability["candidate_count"], 0)

    def test_summary_candidate_count_matches_canonical_list_and_skip_counts_populate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"; artifacts = source / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(
                "\n".join([
                    json.dumps({"paper_id": "p1", "pmid": "111", "selection_score": 0.9, "anchor_strength": "strong"}),
                    json.dumps({"paper_id": "p2", "pmid": "222", "selection_score": 0.8, "anchor_strength": "strong"}),
                ]) + "\n",
                encoding="utf-8",
            )
            replay_fulltext_bridge_from_run(
                case_id="case_v1",
                source_run=source,
                output_run=root / "out",
                overwrite=True,
            )
            out_artifacts = root / "out" / "artifacts"
            canonical = rows(out_artifacts / "l35_fulltext_candidate_papers.jsonl")
            availability = json.loads((out_artifacts / "fulltext_availability_summary.json").read_text(encoding="utf-8"))
            retrieval_records = rows(out_artifacts / "l35_fulltext_retrieval_results.jsonl")
            self.assertEqual(availability["candidate_count"], len(canonical))
            self.assertEqual(retrieval_records, [])
            self.assertEqual(availability["skip_reason_counts"]["missing_pmcid"], 2)


if __name__ == "__main__":
    unittest.main()
