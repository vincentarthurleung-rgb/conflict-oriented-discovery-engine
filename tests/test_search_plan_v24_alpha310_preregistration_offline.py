import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
A39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"


def load(name):
    return json.loads((RUN / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def test_query_execution_manifest_matches_frozen_alpha39_bytes_and_all_contributions():
    source = [json.loads(line) for line in (A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl").read_text().splitlines()]
    manifest = load("search_constraint_allocation_v1_development_execution_manifest.json")
    queries = manifest["exact_queries"]
    assert len(source) == len(queries) == 55
    assert sum(len(row["contributions"]) for row in queries) == 63
    assert Counter(row["case_id"] for row in queries) == dict(zip((f"heldout_v2_{n}" for n in range(101, 109)), (7, 5, 3, 5, 9, 12, 6, 8)))
    for order, (original, frozen) in enumerate(zip(source, queries), start=1):
        assert frozen["execution_order"] == order
        assert frozen["execution_status"] == "NOT_EXECUTED_PREREGISTRATION"
        assert (frozen["case_id"], frozen["query_id"], frozen["exact_query_text"]) == (original["case_id"], original["query_id"], original["query"])
        assert frozen["query_sha256"] == hashlib.sha256(original["query"].encode()).hexdigest()
        assert len(frozen["contributions"]) == len(original["contributions"])
        for contribution in frozen["contributions"]:
            assert contribution["minimum_relational_retrieval_evidence_certificate"]["all_paths_certified"]
            assert contribution["search_relation_evidence"]["scientific_proof"] is False
            assert contribution["query_ast"]["ast_sha256"] == contribution["query_ast_sha256"]
            assert contribution["serialized_query"] == original["query"]
            assert contribution["query_sha256"] == frozen["query_sha256"]
            assert contribution["query_family_id"].startswith("scafamv3:")


def test_policy_and_observation_boundary():
    summary = load("summary.json")
    manifest = load("search_constraint_allocation_v1_development_execution_manifest.json")
    matrix = load("downstream_policy_reuse_matrix.json")
    assert summary["downstream_policy_compatible"] is True
    assert summary["material_downstream_policy_changes"] == 0
    assert all(row["alpha3_10_compatibility"] == "REUSED_IDENTICALLY" for row in matrix["rows"])
    assert len(matrix["rows"]) >= 21
    assert (manifest["soft_tail"], manifest["hard_tail"], manifest["adaptive_tail_enabled"]) == (120, 180, False)
    assert manifest["max_fulltexts_per_case"] == 10
    assert manifest["observed_retrieval_values"] is None
    assert load("technical_continuation_policy.json")["successful_query_reruns"] == 0
    assert load("runtime_adaptation_prohibition.json")["runtime_adaptation_allowed"] is False
    assert summary["network_calls"] == summary["retrieval_calls"] == summary["hit_counts_seen"] == summary["candidate_records_seen"] == 0


def test_frozen_hashes_and_exact_output_set():
    validation = load("validation.json")
    assert validation["valid"] is True
    assert {p.name for p in RUN.iterdir()} == set(validation["required_output_names"])
    manifest_path = RUN / "search_constraint_allocation_v1_development_execution_manifest.json"
    assert sha(manifest_path) == (RUN / "search_constraint_allocation_v1_development_execution_manifest_sha256").read_text().strip()
    components = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_10_sha256"]
    assert hashlib.sha256(canonical(components)).hexdigest() == (RUN / "search_plan_v24_dev_alpha3_10_sha256").read_text().strip()
    assert sha(ROOT / "scripts/search_plan_v24_alpha310_preregister_offline.py") == validation["runner_sha256"]
