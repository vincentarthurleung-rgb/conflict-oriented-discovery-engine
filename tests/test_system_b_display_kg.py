import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.display_kg import display_label, prepare_display_kg


class DisplayKGTests(unittest.TestCase):
    def fixture(self):
        entities = []
        for eid, label, etype in (("a", "α-compound (2)", "compound"), ("b", "ferroptosis", "biological_process"), ("c", "cancer", "disease"), ("d", "KPF", "unknown_biomedical_entity")):
            entities.append({"entity_id": eid, "label": label, "canonical_label": label.casefold(), "aliases": [label], "entity_type": etype, "degree": 10, "in_degree": 5, "out_degree": 5, "evidence_count": 10, "fulltext_evidence_count": 3, "results_section_evidence_count": 1, "source_case_ids": ["case_a", "case_b"]})
        def triple(tid, s, o, count, cases):
            labels = {x["entity_id"]: x for x in entities}
            return {"triple_id": tid, "subject_id": s, "subject_label": labels[s]["label"], "subject_type": labels[s]["entity_type"], "relation_normalized": "promotes", "direction": "positive", "object_id": o, "object_label": labels[o]["label"], "object_type": labels[o]["entity_type"], "evidence_count": count, "fulltext_evidence_count": 2, "results_section_evidence_count": 1, "case_ids": cases, "conflict_status": "none", "display_priority_score": .9}
        triples = [triple("t_specific", "a", "b", 2, ["case_a"]), triple("t_global", "c", "b", 20, ["case_b"]), triple("t_unknown", "d", "b", 3, ["case_a"])]
        chains = [{"chain_id": "ch", "entity_path": ["α-compound (2)", "ferroptosis"], "relation_path": ["promotes"], "triple_ids": ["t_specific"], "chain_quality_score": .8, "display_recommended": True, "depth": 1, "case_ids": ["case_a"], "evidence_count_sum": 2, "fulltext_evidence_count_sum": 2, "results_section_evidence_count_sum": 1, "conflict_statuses": [], "start_entity_id": "a", "start_label": "α-compound (2)", "end_entity_id": "b", "end_label": "ferroptosis", "chain_noise_risk_score": 0, "chain_flags": []}]
        links = [{"case_id": "case_a", "triple_id": "t_specific", "source_scope": "fulltext", "section_title": "Results", "seed_neighborhood_score": .9, "review_priority_score": .8}, {"case_id": "case_b", "triple_id": "t_global", "source_scope": "fulltext", "section_title": "Results", "seed_neighborhood_score": .1, "review_priority_score": .1}]
        return entities, triples, chains, links

    def test_display_labels_generic_ranking_case_focus_limits_and_outputs(self):
        self.assertEqual(display_label("α-compound (2)")[0], "alpha-compound")
        self.assertEqual(display_label("ER stress (endoplasmic reticulum stress)")[0], "ER stress (endoplasmic reticulum stress)")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); e, t, c, links = self.fixture()
            summary = prepare_display_kg(root, e, t, c, links, [{"case_id": "case_a"}], [], max_entities=3, max_triples=2, max_chains=1, max_triples_per_case=1, max_chains_per_case=1)
            display_entities = [json.loads(x) for x in (root / "display_entities_v2.jsonl").read_text().splitlines()]
            normalized = next(x for x in display_entities if x["entity_id"] == "a")
            self.assertEqual(normalized["display_label"], "alpha-compound"); self.assertIn("α-compound (2)", normalized["aliases"])
            self.assertFalse(any(x["label"] == "cancer" for x in display_entities))
            self.assertLessEqual(summary["display_entities_v2_count"], 3); self.assertLessEqual(summary["display_triples_v2_count"], 2); self.assertLessEqual(summary["display_chains_v2_count"], 1)
            focused = [json.loads(x) for x in (root / "case_focused_triples.jsonl").read_text().splitlines()]
            self.assertEqual(next(x for x in focused if x["case_id"] == "case_a")["triple_id"], "t_specific")
            triples = [json.loads(x) for x in (root / "display_triples_v2.jsonl").read_text().splitlines()]
            self.assertTrue(all(isinstance(x["ui_badges"], list) for x in triples)); self.assertNotIn("validator", {x["subject_display_label"].casefold() for x in triples})
            for name in ("top_unknown_display_entities.csv", "generic_entity_downranking_report.csv", "display_label_normalization_report.csv", "kg_display_quality_summary.json"):
                self.assertTrue((root / name).is_file())

    def test_specific_processes_are_not_generic(self):
        e, t, c, links = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            prepare_display_kg(Path(tmp), e, t, c, links, [], [])
            rows = [json.loads(x) for x in (Path(tmp) / "display_entities_v2.jsonl").read_text().splitlines()]
            self.assertEqual(next(x for x in rows if x["label"] == "ferroptosis")["genericity_score"], 0)

if __name__ == "__main__": unittest.main()
