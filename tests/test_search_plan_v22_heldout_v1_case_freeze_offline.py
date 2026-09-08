"""Focused invariants for the offline held-out v1 case and query freeze."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"
REQUIRED = {
    "heldout_case_registry.jsonl", "heldout_scientific_targets.jsonl",
    "heldout_retrieval_targets.jsonl", "heldout_search_lexical_entries.jsonl",
    "heldout_query_families.jsonl", "heldout_query_variants.jsonl",
    "heldout_frozen_queries.jsonl", "unseen_proposition_audit.jsonl",
    "calibration_collision_audit.json", "heldout_budget_binding.json",
    "heldout_fulltext_acquisition_protocol.json",
    "heldout_evaluation_metrics_preregistration.json",
    "heldout_evaluation_heuristics_preregistration.json",
    "domain_ambiguity_balance.json", "freeze_manifest.json",
    "scientific_state_safety_audit.json", "production_leakage_audit.json",
    "validation.json", "manifest.json", "summary.json",
}


def jl(name):
    return [json.loads(x) for x in (RUN / name).read_text(encoding="utf-8").splitlines() if x]


def j(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class HeldoutV1CaseFreezeTests(unittest.TestCase):
    def test_exact_case_set_and_balance(self):
        rows = jl("heldout_case_registry.jsonl")
        self.assertEqual([x["case_id"] for x in rows], [f"heldout_v1_{i:03d}" for i in range(1, 9)])
        self.assertEqual([x["case_order"] for x in rows], list(range(1, 9)))
        self.assertEqual(Counter(x["ambiguity_tier"] for x in rows), {"LOW": 2, "MEDIUM": 2, "HIGH": 4})
        self.assertEqual(sum(x["oncology_case"] for x in rows), 2)
        self.assertEqual(sum(not x["oncology_case"] for x in rows), 6)
        self.assertTrue(all(x["case_state"] == "FROZEN_PRE_RETRIEVAL" for x in rows))
        self.assertTrue(all(not x["replacement_allowed"] for x in rows))

    def test_scientific_and_retrieval_authority_are_separate(self):
        scientific = jl("heldout_scientific_targets.jsonl")
        retrieval = jl("heldout_retrieval_targets.jsonl")
        lexical = jl("heldout_search_lexical_entries.jsonl")
        self.assertEqual(len(scientific), 8)
        self.assertEqual(len(retrieval), 8)
        self.assertEqual({x["artifact_schema_version"] for x in scientific}, {"ScientificPropositionTargetV1"})
        self.assertEqual({x["artifact_schema_version"] for x in retrieval}, {"RetrievalTargetV2"})
        self.assertTrue(all(x["primary_evidence_required"] for x in scientific))
        self.assertTrue(all(not x["retrieval_membership_grants_compatibility"] for x in scientific))
        self.assertTrue(all(not x["search_membership_implies_proposition_compatibility"] for x in retrieval))
        self.assertTrue(all(x["search_use_allowed"] for x in lexical))
        self.assertTrue(all(not x["scientific_equivalence_authorized"] for x in lexical))
        self.assertTrue(all(not x["search_membership_grants_proposition_compatibility"] for x in lexical))
        targets = {x["case_id"]: x for x in scientific}
        self.assertEqual((targets["heldout_v1_001"]["subject"], targets["heldout_v1_001"]["object"]), ("IL-6", "STAT3"))
        self.assertEqual(targets["heldout_v1_005"]["therapy"], "osimertinib")
        self.assertEqual(targets["heldout_v1_006"]["relation_family"], "increases_sensitivity_to")
        self.assertIn("GLUT4 abundance/translocation", targets["heldout_v1_008"]["scientific_boundaries"][0])

    def test_unseen_audit_is_fail_closed_and_clear(self):
        rows = jl("unseen_proposition_audit.jsonl")
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertFalse(row["exact_proposition_signature_previously_used"])
            self.assertFalse(row["calibration_case_collision"])
            self.assertFalse(row["prior_retrieval_calibration_collision"])
            self.assertFalse(row["prior_adjudication_collision"])
            self.assertEqual(row["exact_collision_refs"], [])
            self.assertTrue(row["entity_or_topic_overlap_is_not_case_collision"])
            self.assertTrue(row["offline_repository_inspection_only"])
        audit = j("calibration_collision_audit.json")
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["calibration_case_overlap"], 0)
        self.assertEqual(audit["exact_prior_proposition_collision"], 0)
        self.assertEqual(audit["prior_retrieval_calibration_collision"], 0)
        self.assertEqual(audit["prior_adjudication_collision"], 0)
        self.assertGreater(audit["audit_source_count"], 0)

    def test_exact_compiler_is_reused_and_queries_are_frozen(self):
        families = jl("heldout_query_families.jsonl")
        variants = jl("heldout_query_variants.jsonl")
        queries = jl("heldout_frozen_queries.jsonl")
        self.assertEqual((len(families), len(variants), len(queries)), (48, 48, 48))
        self.assertEqual([x["query_order"] for x in queries], list(range(1, 49)))
        self.assertEqual([x["query_order"] for x in variants], list(range(1, 49)))
        self.assertEqual({x["compiler_source_sha256"] for x in families}, {sha(COMPILER)})
        for case_id in {x["case_id"] for x in families}:
            case_families = [x for x in families if x["case_id"] == case_id]
            self.assertEqual([x["family_code"] for x in case_families], list("ABCDEF"))
            case_queries = [x["query_text"] for x in queries if x["case_id"] == case_id]
            self.assertEqual(len(case_queries), len(set(case_queries)))
        forbidden = ("contradiction", "conflict", "opposite", "unexpected", "resistance reversal")
        self.assertTrue(all(not any(term in x["query_text"].casefold() for term in forbidden) for x in queries))
        self.assertTrue(all(x["sort"] == "relevance" and x["frozen"] for x in queries))
        self.assertTrue(all(not x["network_execution_authorized"] for x in queries))
        for variant in variants:
            self.assertFalse(variant["direction_steering_terms_added"])
            self.assertTrue(all(not ann["authorizes_proposition_identity"] for ann in variant["lexical_provenance"]))
            self.assertTrue(all(not ann["scientific_equivalence_authorized"] for ann in variant["lexical_provenance"]))

    def test_budget_acquisition_metrics_and_heuristics(self):
        budget = j("heldout_budget_binding.json")
        self.assertEqual((budget["metadata_soft_checkpoint"], budget["metadata_hard_safety_ceiling"]), (120, 180))
        self.assertEqual(budget["adaptive_early_stop_state"], "deferred")
        self.assertTrue(budget["same_maximum_for_all_ambiguity_levels"])
        self.assertFalse(budget["retrieval_beyond_180_allowed"])
        acquisition = j("heldout_fulltext_acquisition_protocol.json")
        self.assertEqual(acquisition["max_fulltext_selection_per_case"], 10)
        self.assertFalse(acquisition["reviewer_label_influence_allowed"])
        self.assertFalse(acquisition["replacement_based_on_expected_relevance_allowed"])
        metrics = j("heldout_evaluation_metrics_preregistration.json")
        self.assertEqual(len(metrics["metrics"]), 12)
        self.assertFalse(metrics["true_literature_precision_or_recall_claimed"])
        heuristics = j("heldout_evaluation_heuristics_preregistration.json")
        self.assertEqual(heuristics["tier_a_acquisition_acceptability_target"]["value"], 0.80)
        self.assertEqual(heuristics["overall_acquisition_acceptability_target"]["value"], 0.65)
        self.assertEqual(heuristics["review_only_or_wrong_evidence_mode_contamination_target"]["value"], 0.15)
        self.assertEqual(heuristics["tier_b_utility_proxy_target"]["value"], 0.30)

    def test_protocol_hash_manifest_and_offline_safety(self):
        freeze = j("freeze_manifest.json")
        self.assertEqual(freeze["component_count"], 10)
        pairs = [(x["path"], sha(RUN / x["path"])) for x in freeze["components"]]
        self.assertEqual(freeze["heldout_v1_protocol_sha256"], object_sha(pairs))
        safety = j("scientific_state_safety_audit.json")
        for key in ("network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"):
            self.assertEqual(safety[key], 0)
        self.assertFalse(safety["retrieval_performed"])
        self.assertFalse(safety["relevance_labels_created_or_predicted"])
        self.assertFalse(safety["historical_assets_modified"])
        self.assertFalse(j("production_leakage_audit.json")["heldout_validation_started"])
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 20)
        self.assertEqual({x["path"] for x in manifest["files"]} | {"manifest.json"}, REQUIRED)
        self.assertTrue(all(sha(RUN / x["path"]) == x["sha256"] for x in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
