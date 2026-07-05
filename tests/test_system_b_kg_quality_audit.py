import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.clean_kg import _score_triple, build_clean_kg, canonicalize_entity
from code_engine.system_b.kg_quality_audit import audit_clean_kg


class KGQualityAuditTests(unittest.TestCase):
    def test_safe_normalization_type_quality_and_display_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / "bundle"; bundle.mkdir()
            (bundle / "case_bundle_manifest.json").write_text(json.dumps({"case_id": "case"}))
            rows = [
                {"subject": "α-mangostin", "predicate": "increases", "object": "apoptosis", "source_scope": "full_text", "section_title": "Results"},
                {"subject": "alpha-mangostin (2)", "predicate": "promotes", "object": "apoptosis", "source_scope": "full_text", "section_title": "Results"},
                {"subject": "effect", "predicate": "affects", "object": "level"},
            ]
            (bundle / "l2_reviewable_graph_observations.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            out = root / "kg"; build_clean_kg([root], out, max_chain_depth=1)
            entities = [json.loads(x) for x in (out / "clean_entities.jsonl").read_text().splitlines()]
            mangostin = next(x for x in entities if "mangostin" in x["canonical_label"])
            self.assertEqual(mangostin["canonical_label"], "alpha-mangostin")
            self.assertEqual(set(mangostin["aliases"]), {"α-mangostin", "alpha-mangostin (2)"})
            self.assertEqual(mangostin["entity_type"], "compound")
            display = (out / "clean_triples_display.jsonl").read_text()
            self.assertIn("α-mangostin", display); self.assertNotIn('"subject_label": "effect"', display)
            chains = [json.loads(x) for x in (out / "chain_index.jsonl").read_text().splitlines()]
            self.assertTrue(all(x["depth"] <= 1 for x in chains)); self.assertTrue(all("chain_quality_score" in x for x in chains))

    def test_quality_rewards_evidence_and_penalizes_generic(self):
        base = {"triple_id": "x", "subject_id": "a", "subject_label": "effect", "subject_type": "unknown_biomedical_entity", "relation_normalized": "regulates", "object_id": "b", "object_label": "level", "object_type": "unknown_biomedical_entity", "case_ids": ["c"], "evidence_count": 1, "fulltext_evidence_count": 0, "results_section_evidence_count": 0, "review_priority_score_max": None, "seed_neighborhood_score_max": None}
        generic = _score_triple(dict(base)); strong = _score_triple({**base, "subject_label": "TP53", "subject_type": "gene", "object_label": "apoptosis", "object_type": "biological_process", "evidence_count": 5, "fulltext_evidence_count": 3, "results_section_evidence_count": 2})
        self.assertGreater(generic["noise_risk_score"], strong["noise_risk_score"]); self.assertGreater(strong["display_priority_score"], generic["display_priority_score"])

    def test_audit_detects_contamination_candidates_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kg"; root.mkdir(parents=True)
            entities = [{"entity_id": "a", "label": "Reactome", "canonical_label": "reactome", "entity_type": "unknown_biomedical_entity", "aliases": ["Reactome"], "degree": 2, "evidence_count": 3}, {"entity_id": "b", "label": "α-mangostin", "canonical_label": "alpha-mangostin", "entity_type": "compound", "aliases": ["α-mangostin", "alpha-mangostin (2)"], "degree": 1, "evidence_count": 2}]
            (root / "clean_entities.jsonl").write_text("".join(json.dumps(x) + "\n" for x in entities))
            out = Path(tmp) / "audit"; report = audit_clean_kg(root, out)
            self.assertEqual(report["validator_artifact_terms_found_in_main_graph"], 1)
            self.assertTrue(any(x["reason"] == "parenthetical_suffix" for x in report["possible_duplicate_entities"]))
            self.assertTrue((out / "unknown_entity_review_queue.csv").is_file()); self.assertTrue(report["warnings"])

    def test_canonical_variants(self):
        self.assertEqual(canonicalize_entity(" α-mangostin (2). "), "alpha-mangostin")


if __name__ == "__main__": unittest.main()
