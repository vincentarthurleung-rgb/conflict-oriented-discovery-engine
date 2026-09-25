import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
ALPHA36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"


def load(name):
    return json.loads((RUN / name).read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_query_set_is_bound_without_text_changes():
    check = load("alpha3_6_query_set_verification.json")
    assert check["new_query_set_verified"] is True
    assert check["query_count"] == 25
    assert check["query_text_changes"] == 0
    assert check["per_case_counts"] == {
        "heldout_v2_101": 3, "heldout_v2_102": 2, "heldout_v2_103": 1,
        "heldout_v2_104": 2, "heldout_v2_105": 4, "heldout_v2_106": 6,
        "heldout_v2_107": 3, "heldout_v2_108": 4,
    }
    assert all(row["verified"] for row in check["query_verifications"])


def test_manifest_preserves_all_deduplicated_provenance():
    manifest = load("retrieval_surface_v2_development_execution_manifest.json")
    assert len(manifest["exact_queries"]) == 25
    assert len(manifest["source_relation_contributions"]) == 29
    assert len({row["relation_core_sha256"]
                for row in manifest["source_relation_contributions"]}) == 29
    query_ids = {row["query_id"] for row in manifest["exact_queries"]}
    assert all(row["executed_query_id"] in query_ids
               for row in manifest["source_relation_contributions"])


def test_downstream_policy_is_compatible_and_unchanged():
    audit = load("downstream_policy_compatibility_audit.json")
    matrix = load("downstream_policy_reuse_matrix.json")
    assert audit["downstream_policy_compatible"] is True
    assert audit["material_downstream_policy_changes"] == 0
    assert matrix["status_counts"]["INCOMPATIBLE"] == 0
    assert all(row["compatibility"] == "REUSED_IDENTICALLY" for row in matrix["rows"])


def test_tail_acquisition_and_adaptation_are_frozen():
    summary = load("summary.json")
    assert summary["soft_tail"] == 120
    assert summary["hard_tail"] == 180
    assert summary["adaptive_tail_enabled"] is False
    assert summary["max_fulltexts_per_case"] == 10
    assert summary["runtime_adaptation_allowed"] is False
    barrier = load("selection_freeze_barrier_policy.json")
    assert barrier["freeze_and_hash_before_first_pmc_fetch"] is True
    assert barrier["case_count"] == 8


def test_manifest_hash_is_new_and_correct():
    body = (RUN / "retrieval_surface_v2_development_execution_manifest.json").read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    recorded = (RUN / "retrieval_surface_v2_development_execution_manifest_sha256").read_text().strip()
    assert actual == recorded
    assert actual != "559b09754580bb06f05c51cc58f513e5364d2a5e2d541a8a074351a8b09f9320"


def test_alpha37_root_and_all_components_verify():
    validation = load("validation.json")
    assert validation["status"] == "PASS"
    for name, expected in validation["aggregate_components"]:
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == expected
    actual = hashlib.sha256(canonical(validation["aggregate_components"])).hexdigest()
    assert actual == validation["search_plan_v24_dev_alpha3_7_sha256"]
    assert actual == (RUN / "search_plan_v24_dev_alpha3_7_sha256").read_text().strip()


def test_query_set_remains_byte_identical_to_alpha36():
    query_path = ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"
    assert hashlib.sha256(query_path.read_bytes()).hexdigest() == (
        "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947")
    manifest = load("retrieval_surface_v2_development_execution_manifest.json")
    source = [json.loads(line) for line in query_path.read_text().splitlines() if line]
    assert [row["exact_query_text"] for row in manifest["exact_queries"]] == [
        row["serialized_query"] for row in source]


def test_safety_audit_is_offline_and_blinded():
    safety = load("scientific_state_safety_audit.json")
    for key in ["provider_calls", "llm_calls", "network_calls", "retrieval_calls",
                "known_pmid_checks", "hit_counts_seen", "candidate_records_seen"]:
        assert safety[key] == 0
    assert safety["historical_assets_modified"] is False
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    assert load("known_paper_blindness_policy.json")["known_pmid_recovery_check_before_acquisition_freeze"] is False
    assert load("historical_label_blinding_policy.json")["historical_label_blinding_frozen"] is True
