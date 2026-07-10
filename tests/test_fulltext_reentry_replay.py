import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
from code_engine.fulltext.reentry import reenter_fulltext_l1_claims


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeClient:
    def extract_json(self, prompt, **kwargs):
        return {"claims": [{"subject": "A", "predicate": "promotes", "object": "B", "polarity": "positive", "evidence_sentence": "A promotes B."}]}


class FulltextReentryReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        self.artifacts = self.run / "artifacts"
        self.artifacts.mkdir(parents=True)
        seed = {"subject": {"name": "A"}, "object": {"name": "B"}, "context": {"context_terms": ["B"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        write_json(self.artifacts / "search_plan_replay.json", {"enabled": True})
        write_json(self.artifacts / "intake.json", {"research_intent": {"primary_entities": ["A"], "mechanism_entities": ["B"]}})
        write_json(self.artifacts / "domain_profile.json", {})
        write_json(self.artifacts / "pipeline_stage_summary.json", {})
        write_json(self.artifacts / "hypothesis_summary.json", {"formal_hypothesis_count": 0})
        write_json(self.artifacts / "l35_fulltext_l1_summary.json", {"fulltext_l1_status": "completed_with_claims", "selected_chunk_count": 1})
        write_json(self.artifacts / "l35_fulltext_conflict_confirmation_summary.json", {"fulltext_confirmed_conflict_count": 0})
        write_rows(self.artifacts / "l35_fulltext_l1_chunks.jsonl", [])
        write_rows(self.artifacts / "l35_fulltext_discovery_execution_records.jsonl", [])
        write_rows(self.artifacts / "fulltext_discovery_escalation_candidates.jsonl", [])
        write_rows(self.artifacts / "l35_fulltext_candidate_papers.jsonl", [])
        write_rows(self.artifacts / "l35_fulltext_retrieval_results.jsonl", [])
        self.claim = {"claim_id": "F1", "paper_id": "P1", "pmid": "1", "pmcid": "PMC1", "subject": "A", "predicate": "promotes", "object": "B", "polarity": "positive", "section_title": "Results", "chunk_id": "C1", "evidence_sentence": "A promotes B."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [self.claim])
        abstract = {"observation_id": "A1", "claim_id": "A1", "paper_id": "P0", "subject_raw": "A", "object_raw": "B", "evidence_sentence": "A promotes B.", "retained": True, "graph_observation_eligible": True, "source_scope": "abstract"}
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [abstract])
        write_rows(self.artifacts / "l2_graph_observations.jsonl", [abstract])

    def tearDown(self):
        self.tmp.cleanup()

    def accepted_observation(self, claim_id="F1", direction="positive"):
        return {
            "observation_id": claim_id, "claim_id": claim_id, "paper_id": "P1", "pmid": "1", "pmcid": "PMC1",
            "subject_raw": "A", "object_raw": "B", "relation_raw": "promotes", "direction": direction,
            "evidence_sentence": "A promotes B.", "retained": True, "graph_observation_eligible": True,
            "canonical_graph_eligible": True, "allow_high_confidence_graph_use": True,
            "conflict_reasoning_eligible": True, "exclude_from_high_confidence_conflict": False,
            "excluded_from_core_reason": None, "predicate_direction_consistent": True,
            "predicate_anchor_status": "seed_predicate_found", "subject_normalization_status": "resolved",
            "object_normalization_status": "resolved", "subject_requires_manual_review": False,
            "object_requires_manual_review": False, "source_scope": "full_text", "evidence_source": "fulltext",
        }

    def test_existing_fulltext_claims_are_reused_without_l1_api_calls(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertTrue(summary["fulltext_l1_reused"])
        self.assertEqual(summary["fulltext_l1_api_calls"], 0)
        self.assertEqual(summary["source_fulltext_claim_count"], 1)

    def test_fulltext_claims_enter_l2_normalization(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]) as normalizer:
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertEqual(normalizer.call_count, 1)
        self.assertEqual(normalizer.call_args.args[0][0]["claim_id"], "F1")
        self.assertEqual(normalizer.call_args.args[0][0]["evidence_source"], "fulltext")

    def test_accepted_fulltext_claim_enters_merged_evidence_graph(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        rows = [json.loads(line) for line in (self.artifacts / "merged_l2_graph_observations.jsonl").read_text().splitlines()]
        self.assertEqual(summary["reentered_observation_count"], 1)
        self.assertIn(("fulltext", "F1"), {(row.get("evidence_source"), row.get("observation_id")) for row in rows})

    def test_rejected_claim_has_explicit_reason(self):
        rejected = {**self.accepted_observation(), "retained": False, "graph_observation_eligible": False, "excluded_from_retention_reason": "low_confidence_entity_resolution"}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[rejected]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(summary["rejected_fulltext_claim_count"], 1)
        self.assertEqual(audit[0]["rejection_reason"], "low_confidence_entity_resolution")

    def test_abstract_and_fulltext_provenance_remain_distinguishable(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        rows = [json.loads(line) for line in (self.artifacts / "l2_graph_observations.jsonl").read_text().splitlines()]
        self.assertEqual(sorted({row.get("evidence_source") for row in rows}), ["abstract", "fulltext"])

    def test_duplicate_abstract_fulltext_evidence_has_explicit_counts(self):
        fulltext = {**self.accepted_observation(), "evidence_sentence": "A promotes B."}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[fulltext]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertEqual(summary["abstract_observation_count"], 1)
        self.assertEqual(summary["fulltext_observation_count"], 1)
        self.assertEqual(summary["merged_graph_observation_count"], 2)

    def test_non_comparable_evidence_does_not_become_conflict(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertEqual(summary["confirmed_conflict_count"], 0)

    def test_fulltext_conflict_confirmation_remains_conservative(self):
        write_json(self.artifacts / "l35_fulltext_conflict_confirmation_summary.json", {"fulltext_confirmed_conflict_count": 0})
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertEqual(summary["hypothesis_count"], 0)

    def test_expression_state_claim_is_not_reentered_as_causal_graph_edge(self):
        claim = {**self.claim, "claim_id": "E1", "subject": "KIF3B", "predicate": "up-regulated", "object": "breast cancer", "polarity": "positive", "evidence_sentence": "KIF3B is up-regulated in breast cancer."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("E1"), "subject_raw": "KIF3B", "relation_raw": "up-regulated", "object_raw": "breast cancer", "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        graph_rows = [json.loads(line) for line in (self.artifacts / "l2_fulltext_graph_observations.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(summary["reentered_observation_count"], 0)
        self.assertEqual(summary["evidence_lane_counts"], {"reviewable_context_relation": 1})
        self.assertEqual(graph_rows, [])
        self.assertEqual(audit[0]["relation_class"], "expression_state")
        self.assertFalse(audit[0]["structural_graph_eligible"])
        self.assertEqual(audit[0]["evidence_lane"], "reviewable_context_relation")
        self.assertFalse(audit[0]["conflict_eligible"])

    def test_one_hop_seed_mechanism_enters_seed_neighborhood_lane_not_core_graph(self):
        seed = {"subject": {"name": "cancer stemness"}, "object": {"name": "Wnt beta catenin signaling"}, "context": {"context_terms": ["Wnt/β-catenin signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        claim = {**self.claim, "claim_id": "W1", "subject": "NUSAP1", "predicate": "promotes activation of", "object": "Wnt/β-catenin signaling", "polarity": "positive", "evidence_sentence": "NUSAP1 promotes activation of Wnt/β-catenin signaling."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("W1"), "subject_raw": "NUSAP1", "relation_raw": "promotes activation of", "object_raw": "Wnt/β-catenin signaling", "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        neighborhood = [json.loads(line) for line in (self.artifacts / "l2_fulltext_seed_neighborhood_observations.jsonl").read_text().splitlines() if line.strip()]
        graph_rows = [json.loads(line) for line in (self.artifacts / "l2_fulltext_graph_observations.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(summary["reentered_observation_count"], 0)
        self.assertEqual(summary["seed_neighborhood_mechanism_count"], 1)
        self.assertEqual(summary["rejected_fulltext_claim_count"], 0)
        self.assertEqual(graph_rows, [])
        self.assertEqual(neighborhood[0]["claim_id"], "W1")
        self.assertIn(audit[0]["seed_distance"], {"direct", "one_hop"})
        self.assertEqual(audit[0]["evidence_lane"], "seed_neighborhood_mechanism")
        self.assertFalse(audit[0]["conflict_eligible"])

    def test_audit_records_include_required_evidence_lane_model_fields(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        required = {
            "relation_class", "structural_graph_eligible", "seed_distance", "evidence_lane", "conflict_eligible",
            "raw_claim_sign", "relation_polarity", "subject_perturbation_polarity", "effective_entity_polarity",
            "polarity_resolution_status", "lane_reason",
        }
        self.assertTrue(required.issubset(audit[0]))

    def test_bare_subject_is_not_perturbation_inverted_by_sentence_context(self):
        claim = {**self.claim, "claim_id": "P1", "subject": "NUSAP1", "predicate": "promotes activation of", "object": "B", "polarity": "positive", "evidence_sentence": "NUSAP1 knockdown reduced B, showing NUSAP1 promotes activation of B."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("P1"), "subject_raw": "NUSAP1", "relation_raw": "promotes activation of", "object_raw": "B", "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["subject_perturbation_polarity"], "neutral")
        self.assertEqual(audit[0]["effective_entity_polarity"], "positive")

    def test_relation_sign_mismatch_routes_to_reviewable(self):
        claim = {**self.claim, "claim_id": "M1", "subject": "CD151", "predicate": "suppresses", "object": "luminal cell-associated tumorigenesis", "polarity": "positive", "evidence_sentence": "CD151 suppresses luminal cell-associated tumorigenesis."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("M1"), "subject_raw": "CD151", "relation_raw": "suppresses", "object_raw": "luminal cell-associated tumorigenesis", "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["polarity_resolution_status"], "mismatch")
        self.assertEqual(audit[0]["evidence_lane"], "reviewable_context_relation")
        self.assertFalse(audit[0]["conflict_eligible"])

    def test_microbial_upstream_seed_mechanism_enters_seed_neighborhood(self):
        seed = {"subject": {"name": "cancer stemness"}, "object": {"name": "Wnt beta catenin signaling"}, "context": {"context_terms": ["Wnt/β-catenin signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        claim = {**self.claim, "claim_id": "FN1", "subject": "F. nucleatum", "predicate": "induced", "object": "activation of Wnt/β-catenin signaling pathway", "polarity": "positive", "evidence_sentence": "F. nucleatum induced activation of Wnt/β-catenin signaling pathway."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("FN1"), "subject_raw": "F. nucleatum", "relation_raw": "induced", "object_raw": claim["object"], "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(summary["seed_neighborhood_mechanism_count"], 1)
        self.assertEqual(audit[0]["evidence_lane"], "seed_neighborhood_mechanism")

    def test_off_seed_claim_in_seed_relevant_paper_stays_off_seed(self):
        seed = {"subject": {"name": "cancer stemness"}, "object": {"name": "Wnt beta catenin signaling"}, "context": {"context_terms": ["Wnt/β-catenin signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        claim = {**self.claim, "claim_id": "OS1", "subject": "NUSAP1", "predicate": "promotes", "object": "NSCLC cell proliferation", "polarity": "positive", "evidence_sentence": "NUSAP1 promotes NSCLC cell proliferation. Wnt is discussed elsewhere."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("OS1"), "subject_raw": "NUSAP1", "relation_raw": "promotes", "object_raw": "NSCLC cell proliferation", "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["seed_distance"], "none")
        self.assertEqual(audit[0]["evidence_lane"], "off_seed_relation")

    def test_negative_perturbation_inverts_base_entity_polarity(self):
        seed = {"subject": {"name": "KIF3B"}, "object": {"name": "Wnt beta catenin signaling"}, "context": {"context_terms": ["Wnt/β-catenin signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        claim = {**self.claim, "claim_id": "INV1", "subject": "KIF3B silencing", "predicate": "decreased", "object": "Wnt/β-catenin signaling", "polarity": "negative", "evidence_sentence": "KIF3B silencing decreased Wnt/β-catenin signaling."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("INV1"), "subject_raw": claim["subject"], "relation_raw": "decreased", "object_raw": claim["object"], "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["subject_perturbation_polarity"], "negative")
        self.assertEqual(audit[0]["relation_polarity"], "negative")
        self.assertEqual(audit[0]["effective_entity_polarity"], "positive")
        self.assertTrue(audit[0]["base_entity_polarity_derived"])
        self.assertEqual(summary["perturbation_inversion_count"], 1)

    def test_inhibitor_subject_resolves_before_mismatch_check(self):
        claim = {**self.claim, "claim_id": "INH1", "subject": "5-c-8HQ (JMJD2D inhibitor)", "predicate": "reduces", "object": "LCSC self-renewal", "polarity": "positive", "evidence_sentence": "5-c-8HQ (JMJD2D inhibitor) reduces LCSC self-renewal."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("INH1"), "subject_raw": claim["subject"], "relation_raw": "reduces", "object_raw": claim["object"], "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["subject_perturbation_polarity"], "negative")
        self.assertEqual(audit[0]["polarity_resolution_status"], "resolved")
        self.assertNotEqual(audit[0]["polarity_resolution_status"], "mismatch")

    def test_composite_pathway_list_routes_to_reviewable(self):
        claim = {**self.claim, "claim_id": "C1", "subject": "WNT, Notch, Hedgehog and AMPK pathways", "predicate": "associated with", "object": "immune silent phenotype", "polarity": "positive", "evidence_sentence": "WNT, Notch, Hedgehog and AMPK pathways are associated with immune silent phenotype."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("C1"), "subject_raw": claim["subject"], "relation_raw": "associated with", "object_raw": claim["object"], "evidence_sentence": claim["evidence_sentence"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["relation_class"], "association")
        self.assertTrue(audit[0]["subject_is_composite"])
        self.assertEqual(audit[0]["composite_entity_status"], "composite")
        self.assertEqual(audit[0]["evidence_lane"], "reviewable_context_relation")
        self.assertFalse(audit[0]["conflict_eligible"])

    def test_actual_wnt_abstract_duplicate_core_candidate_is_hard_vetoed(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "24c6d7688b83c730", "pmid": "34621119", "subject_raw": "Canonical Wnt signaling pathway", "relation_raw": "promotes", "object_raw": "cancer cell proliferation", "direction": "positive", "evidence_sentence": "Canonical Wnt signaling pathway plays a crucial role in cancer cell proliferation.", "retained": True, "graph_observation_eligible": True, "source_scope": "abstract"}])
        write_rows(self.artifacts / "l2_graph_observations.jsonl", [])
        seed = {"subject": {"name": "Canonical Wnt signaling pathway"}, "object": {"name": "cancer cell proliferation"}, "context": {"context_terms": ["Wnt signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        claim = {**self.claim, "claim_id": "ft_501a95357d76_0", "pmid": "34621119", "pmcid": "PMC8457021", "subject": "Canonical Wnt signaling pathway", "predicate": "promotes", "object": "cancer cell proliferation", "polarity": "positive", "section_type": "abstract", "section_title": "abstract", "linked_abstract_observation_ids": ["24c6d7688b83c730"], "evidence_sentence": "Canonical Wnt signaling pathway plays a crucial role in cancer cell proliferation."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("ft_501a95357d76_0"), "pmid": "34621119", "pmcid": "PMC8457021", "subject_raw": claim["subject"], "object_raw": claim["object"], "relation_raw": "promotes", "evidence_sentence": claim["evidence_sentence"], "canonical_graph_eligible": False, "allow_high_confidence_graph_use": False, "allow_high_confidence_graph_use_legacy": False, "conflict_reasoning_eligible": False, "exclude_from_high_confidence_conflict": True, "excluded_from_core_reason": "not_strict_canonical_seed_relation", "normalization_quality": "low_confidence", "subject_normalization_status": "unresolved_fallback", "object_normalization_status": "unresolved_fallback", "subject_requires_manual_review": True, "object_requires_manual_review": True, "predicate_anchor_status": "no_seed_predicate_found", "predicate_direction_consistent": False, "linked_abstract_observation_ids": ["24c6d7688b83c730"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        core_rows = [line for line in (self.artifacts / "fulltext_core_seed_observations.jsonl").read_text().splitlines() if line.strip()]
        retained = [json.loads(line) for line in (self.artifacts / "l2_retained_observations.jsonl").read_text().splitlines()]
        self.assertFalse(audit[0]["core_gate_passed"])
        self.assertFalse(audit[0]["conflict_eligible"])
        self.assertEqual(audit[0]["evidence_lane"], "reviewable_context_relation")
        self.assertEqual(audit[0]["evidence_origin"], "abstract_section")
        self.assertEqual(audit[0]["abstract_duplicate_status"], "exact_evidence_duplicate")
        self.assertEqual(audit[0]["duplicate_match_basis"], ["same_pmid", "same_evidence_hash", "same_subject", "same_relation_family", "same_object", "same_polarity"])
        self.assertEqual(audit[0]["matched_abstract_observation_id"], "24c6d7688b83c730")
        self.assertEqual(audit[0]["dedup_action"], "merge_provenance_into_abstract")
        self.assertEqual(core_rows, [])
        self.assertEqual(summary["core_seed_relation_count"], 0)
        self.assertEqual(summary["conflict_eligible_count"], 0)
        expected_failures = {"canonical_graph_ineligible", "high_confidence_graph_use_disallowed", "conflict_reasoning_ineligible", "excluded_from_high_confidence_conflict", "excluded_from_core_reason_present", "predicate_direction_inconsistent", "predicate_anchor_not_accepted", "unresolved_subject", "unresolved_object", "subject_requires_manual_review", "object_requires_manual_review", "exact_evidence_duplicate"}
        self.assertTrue(expected_failures.issubset(set(audit[0]["core_gate_failures"])))
        linked = next(row for row in retained if row.get("observation_id") == "24c6d7688b83c730")
        self.assertEqual(linked["merged_fulltext_provenance"][0]["claim_id"], "ft_501a95357d76_0")

    def test_linked_abstract_id_alone_is_possible_not_confirmed_duplicate(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS1", "pmid": "9", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "direction": "positive", "evidence_sentence": "A promotes B.", "retained": True, "source_scope": "abstract"}])
        claims = [
            {**self.claim, "claim_id": "L1", "pmid": "9", "subject": "NUSAP1", "predicate": "promotes", "object": "NSCLC proliferation", "linked_abstract_observation_ids": ["ABS1"], "section_type": "abstract", "section_title": "abstract", "evidence_sentence": "NUSAP1 promotes NSCLC proliferation."},
            {**self.claim, "claim_id": "L2", "pmid": "9", "subject": "MEF2D", "predicate": "enhances", "object": "NUSAP1 expression", "linked_abstract_observation_ids": ["ABS1"], "section_type": "abstract", "section_title": "abstract", "evidence_sentence": "MEF2D enhances NUSAP1 expression."},
            {**self.claim, "claim_id": "L3", "pmid": "9", "subject": "F. nucleatum", "predicate": "induced", "object": "Wnt signaling", "linked_abstract_observation_ids": ["ABS1"], "section_type": "abstract", "section_title": "abstract", "evidence_sentence": "F. nucleatum induced Wnt signaling."},
        ]
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", claims)
        observations = [{**self.accepted_observation(row["claim_id"]), "pmid": "9", "subject_raw": row["subject"], "relation_raw": row["predicate"], "object_raw": row["object"], "evidence_sentence": row["evidence_sentence"], "linked_abstract_observation_ids": ["ABS1"]} for row in claims]
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=observations):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual({row["abstract_duplicate_status"] for row in audit}, {"possible_linked_duplicate"})
        self.assertEqual({row["dedup_action"] for row in audit}, {"preserve_without_automatic_merge"})
        self.assertEqual(summary["possible_linked_duplicate_count"], 3)
        self.assertEqual(summary["abstract_provenance_merge_count"], 0)

    def test_deterministic_claim_duplicate_requires_matching_identity(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS2", "pmid": "2", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "direction": "positive", "evidence_sentence": "Different wording.", "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "DUP1", "pmid": "2", "subject": "A", "predicate": "promotes", "object": "B", "polarity": "positive", "section_type": "abstract", "evidence_sentence": "A causally promotes B in another sentence."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation("DUP1") | {"pmid": "2"}]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["abstract_duplicate_status"], "deterministic_claim_duplicate")
        self.assertEqual(audit[0]["matched_abstract_observation_id"], "ABS2")
        self.assertEqual(summary["deterministic_claim_duplicate_count"], 1)
        self.assertEqual(summary["abstract_provenance_merge_count"], 1)

    def test_different_claim_identity_does_not_merge_even_with_link(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS3", "pmid": "3", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "direction": "positive", "evidence_sentence": "A promotes B.", "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "DIFF1", "pmid": "3", "subject": "X", "predicate": "suppresses", "object": "Y", "polarity": "negative", "linked_abstract_observation_ids": ["ABS3"], "section_type": "abstract", "evidence_sentence": "X suppresses Y."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("DIFF1"), "pmid": "3", "subject_raw": "X", "relation_raw": "suppresses", "object_raw": "Y", "direction": "negative", "linked_abstract_observation_ids": ["ABS3"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["abstract_duplicate_status"], "possible_linked_duplicate")
        self.assertEqual(audit[0]["dedup_action"], "preserve_without_automatic_merge")
        self.assertEqual(summary["abstract_provenance_merge_count"], 0)

    def test_section_origin_actions_and_audit_provenance_are_explicit(self):
        claim = {**self.claim, "claim_id": "ABSNEW", "pmid": "4", "section_type": "abstract", "section_title": "abstract", "evidence_sentence": "A promotes B with new abstract wording."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation("ABSNEW") | {"pmid": "4", "evidence_sentence": claim["evidence_sentence"]}]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        for field in ("subject_raw", "relation_raw", "object_raw", "evidence_sentence", "section_type", "section_title", "section_provenance", "linked_abstract_observation_ids", "evidence_origin", "duplicate_match_basis", "matched_abstract_observation_id"):
            self.assertIn(field, audit[0])
        self.assertEqual(audit[0]["evidence_origin"], "abstract_section")
        self.assertEqual(audit[0]["abstract_duplicate_status"], "not_duplicate")
        self.assertEqual(audit[0]["dedup_action"], "keep_as_abstract_section_reextraction")
        self.assertEqual(summary["abstract_section_reextraction_count"], 1)

    def test_body_claim_with_coarse_link_is_body_evidence_and_missing_section_is_unknown(self):
        body = {**self.claim, "claim_id": "BODY1", "section_type": "Results", "section_title": "Results", "linked_abstract_observation_ids": ["ABS1"]}
        unknown = {k: v for k, v in {**self.claim, "claim_id": "UNK1"}.items() if k not in {"section_type", "section_title"}}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [body, unknown])
        observations = [self.accepted_observation("BODY1") | {"linked_abstract_observation_ids": ["ABS1"]}, self.accepted_observation("UNK1")]
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=observations):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = {row["claim_id"]: row for row in [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]}
        self.assertEqual(audit["BODY1"]["evidence_origin"], "body_section")
        self.assertEqual(audit["BODY1"]["abstract_duplicate_status"], "possible_linked_duplicate")
        self.assertEqual(audit["BODY1"]["dedup_action"], "preserve_without_automatic_merge")
        self.assertEqual(audit["UNK1"]["evidence_origin"], "unknown_section")
        self.assertEqual(summary["body_section_claim_count"], 1)
        self.assertEqual(summary["unknown_section_claim_count"], 1)

    def test_possible_linked_duplicate_preserves_mechanism_lane_and_body_independence(self):
        seed = {"subject": {"name": "cancer stemness"}, "object": {"name": "Wnt beta catenin signaling"}, "context": {"context_terms": ["Wnt/β-catenin signaling"]}}
        write_json(self.artifacts / "semantic_search_intent.json", {"seed_triple": seed})
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS1", "pmid": "5", "subject_raw": "Different", "relation_raw": "associated with", "object_raw": "Thing", "evidence_sentence": "Different evidence.", "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "PLM1", "pmid": "5", "subject": "NUSAP1", "predicate": "promotes activation of", "object": "Wnt/β-catenin signaling", "section_type": "Results", "section_title": "Results", "linked_abstract_observation_ids": ["ABS1"], "evidence_sentence": "NUSAP1 promotes activation of Wnt/β-catenin signaling."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("PLM1"), "pmid": "5", "subject_raw": claim["subject"], "relation_raw": claim["predicate"], "object_raw": claim["object"], "linked_abstract_observation_ids": ["ABS1"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["abstract_duplicate_status"], "possible_linked_duplicate")
        self.assertEqual(audit[0]["evidence_lane"], "seed_neighborhood_mechanism")
        self.assertTrue(audit[0]["exploratory_graph_eligible"])
        self.assertTrue(audit[0]["independent_fulltext_body_evidence"])
        self.assertFalse(audit[0]["conflict_eligible"])
        self.assertEqual(summary["independent_fulltext_body_evidence_count"], 1)

    def test_possible_linked_duplicate_preserves_off_seed_lane(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS1", "pmid": "6", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "evidence_sentence": "A promotes B.", "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "PLO1", "pmid": "6", "subject": "NUSAP1", "predicate": "promotes", "object": "NSCLC cell proliferation", "section_type": "Results", "linked_abstract_observation_ids": ["ABS1"], "evidence_sentence": "NUSAP1 promotes NSCLC cell proliferation."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("PLO1"), "pmid": "6", "subject_raw": "NUSAP1", "relation_raw": "promotes", "object_raw": "NSCLC cell proliferation", "linked_abstract_observation_ids": ["ABS1"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["abstract_duplicate_status"], "possible_linked_duplicate")
        self.assertEqual(audit[0]["evidence_lane"], "off_seed_relation")
        self.assertTrue(audit[0]["independent_fulltext_body_evidence"])

    def test_abstract_possible_linked_duplicate_is_reextraction_not_body_evidence(self):
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS1", "pmid": "7", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "evidence_sentence": "A promotes B.", "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "PLA1", "pmid": "7", "subject": "NUSAP1", "predicate": "promotes", "object": "NSCLC cell proliferation", "section_type": "abstract", "section_title": "abstract", "linked_abstract_observation_ids": ["ABS1"], "evidence_sentence": "NUSAP1 promotes NSCLC cell proliferation."}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("PLA1"), "pmid": "7", "subject_raw": "NUSAP1", "relation_raw": "promotes", "object_raw": "NSCLC cell proliferation", "linked_abstract_observation_ids": ["ABS1"]}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["dedup_action"], "preserve_without_automatic_merge")
        self.assertTrue(audit[0]["abstract_section_reextraction"])
        self.assertFalse(audit[0]["independent_fulltext_body_evidence"])
        self.assertEqual(summary["abstract_section_reextraction_count"], 1)

    def test_same_sentence_different_triples_are_not_exact_duplicates(self):
        sentence = "A promotes B and X suppresses Y."
        write_rows(self.artifacts / "l2_retained_observations.jsonl", [{"observation_id": "ABS1", "pmid": "8", "subject_raw": "A", "relation_raw": "promotes", "object_raw": "B", "direction": "positive", "evidence_sentence": sentence, "retained": True, "source_scope": "abstract"}])
        claim = {**self.claim, "claim_id": "SS1", "pmid": "8", "subject": "X", "predicate": "suppresses", "object": "Y", "polarity": "negative", "section_type": "abstract", "evidence_sentence": sentence}
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
        normalized = {**self.accepted_observation("SS1", direction="negative"), "pmid": "8", "subject_raw": "X", "relation_raw": "suppresses", "object_raw": "Y", "evidence_sentence": sentence}
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["abstract_duplicate_status"], "same_sentence_possible_duplicate")
        self.assertEqual(audit[0]["dedup_action"], "preserve_without_automatic_merge")
        self.assertEqual(summary["same_sentence_possible_duplicate_count"], 1)
        self.assertEqual(summary["exact_claim_duplicate_count"], 0)

    def test_hard_vetoes_prevent_direct_seed_core_eligibility(self):
        cases = [
            ("canonical_graph_eligible", False, "canonical_graph_ineligible"),
            ("allow_high_confidence_graph_use", False, "high_confidence_graph_use_disallowed"),
            ("conflict_reasoning_eligible", False, "conflict_reasoning_ineligible"),
            ("excluded_from_core_reason", "not_strict_canonical_seed_relation", "excluded_from_core_reason_present"),
            ("predicate_direction_consistent", False, "predicate_direction_inconsistent"),
            ("subject_normalization_status", "unresolved_fallback", "unresolved_subject"),
            ("subject_requires_manual_review", True, "subject_requires_manual_review"),
        ]
        for field, value, failure in cases:
            with self.subTest(field=field):
                self.tearDown()
                self.setUp()
                normalized = {**self.accepted_observation(), field: value}
                with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[normalized]):
                    summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
                audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
                self.assertFalse(audit[0]["core_gate_passed"])
                self.assertFalse(audit[0]["conflict_eligible"])
                self.assertIn(failure, audit[0]["core_gate_failures"])
                self.assertEqual(summary["conflict_eligible_count"], 0)

    def test_canonical_anchored_direct_seed_relation_can_still_enter_core(self):
        with patch("code_engine.fulltext.reentry._normalize_progressive_records", return_value=[self.accepted_observation()]):
            summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        audit = [json.loads(line) for line in (self.artifacts / "fulltext_reentry_audit.jsonl").read_text().splitlines()]
        self.assertTrue(audit[0]["core_gate_passed"])
        self.assertTrue(audit[0]["conflict_eligible"])
        self.assertEqual(audit[0]["evidence_lane"], "core_seed_relation")
        self.assertEqual(summary["core_seed_relation_count"], 1)

    def test_empty_fulltext_claim_file_writes_no_input_summary(self):
        write_rows(self.artifacts / "l35_fulltext_l1_claims.jsonl", [])
        summary = reenter_fulltext_l1_claims(self.run, source_fulltext_run=Path("fulltext"))
        self.assertEqual(summary["status"], "no_input")
        self.assertEqual(summary["input_fulltext_claim_count"], 0)

    def test_execution_records_include_observability_fields(self):
        run = Path(self.tmp.name) / "l1_run"
        artifacts = run / "artifacts"
        parsed = artifacts / "fulltext/pmc_oa/PMC1"
        parsed.mkdir(parents=True)
        write_rows(artifacts / "l35_fulltext_oa_candidate_papers.jsonl", [{"paper_id": "P1", "pmid": "1", "pmcid": "PMC1"}])
        write_json(parsed / "article_text.json", {"sections": [{"section_title": "Results", "text": "A promotes B."}]})
        run_fulltext_l1_extraction(run_dir=run, fulltext_candidates_path=artifacts / "l35_fulltext_oa_candidate_papers.jsonl", parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fake", l1_model="m", api_enabled=True, network_enabled=True, client=FakeClient())
        record = json.loads((artifacts / "l35_fulltext_l1_execution_records.jsonl").read_text().splitlines()[0])
        self.assertEqual(record["api_called"], True)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["claim_count"], 1)


if __name__ == "__main__":
    unittest.main()
