import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.clean_kg import build_clean_kg, normalize_relation


class CleanKGTests(unittest.TestCase):
    def test_clean_projection_aggregation_provenance_chain_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / "nested" / "case"; bundle.mkdir(parents=True)
            (bundle / "case_bundle_manifest.json").write_text(json.dumps({"case_id": "case"}))
            rows = [
                {"subject": "A", "subject_type": "protein", "predicate": "increases", "object": "B", "object_type": "pathway", "evidence_sentence": "first", "context": {"tissue": "liver"}},
                {"subject": "A", "subject_type": "protein", "predicate": "increases", "object": "B", "object_type": "pathway", "evidence_sentence": "second"},
                {"subject": "B", "subject_type": "pathway", "predicate": "promotes", "object": "C", "object_type": "disease", "evidence_sentence": "third"},
                {"subject": "LINCS", "predicate": "validates", "object": "A", "evidence_sentence": "validator"},
                {"subject": "paper", "predicate": "contains", "object": "claim", "evidence_sentence": "metadata"},
            ]
            (bundle / "l2_reviewable_graph_observations.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            (bundle / "l7_reactome_summary.json").write_text(json.dumps({"status": "available", "pathways": 2}))
            pair = {"observation_a": rows[0], "observation_b": {"subject": "A", "predicate": "inhibits", "object": "B"}, "rejection_reason": "contexts differ"}
            (bundle / "non_comparable_direction_pairs.jsonl").write_text(json.dumps(pair) + "\n")
            out = root / "out"; summary = build_clean_kg([root], out, max_chain_depth=2)
            entities = [json.loads(x) for x in (out / "clean_entities.jsonl").read_text().splitlines()]
            triples = [json.loads(x) for x in (out / "clean_triples.jsonl").read_text().splitlines()]
            links = [json.loads(x) for x in (out / "triple_evidence_links.jsonl").read_text().splitlines()]
            chains = [json.loads(x) for x in (out / "chain_index.jsonl").read_text().splitlines()]
            self.assertEqual({x["label"] for x in entities}, {"A", "B", "C"})
            self.assertNotIn("first", {x["label"] for x in entities})
            ab = next(x for x in triples if x["subject_label"] == "A")
            self.assertEqual(ab["relation"], "increases"); self.assertEqual(ab["relation_normalized"], "promotes"); self.assertEqual(ab["evidence_count"], 2)
            self.assertEqual(len([x for x in links if x["triple_id"] == ab["triple_id"]]), 2)
            self.assertTrue(any(x["entity_path"] == ["A", "B", "C"] and x["depth"] == 2 for x in chains))
            self.assertFalse(any(x["depth"] > 2 for x in chains))
            self.assertEqual(summary["validator_annotations_total"], 1); self.assertGreater(summary["validator_nodes_blocked_count"], 0)
            conflicts = [json.loads(x) for x in (out / "conflict_lens_records.jsonl").read_text().splitlines()]
            self.assertEqual(conflicts[0]["record_type"], "non_comparable_direction_pair"); self.assertTrue(conflicts[0]["linked_triple_ids"])
            for name in ("clean_entities.csv", "clean_triples.csv", "entity_index.json", "relation_index.json"):
                self.assertTrue((out / name).is_file())
            self.assertIn("l35_fulltext_discovery_observations.jsonl", summary["missing_files"]["case"])

    def test_relation_normalization_is_conservative(self):
        self.assertEqual(normalize_relation("upregulates"), "promotes")
        self.assertEqual(normalize_relation("binds_to"), "binds to")


if __name__ == "__main__": unittest.main()
