from collections import Counter

from tools.run_search_constraint_allocation_v1_development_retrieval import (
    CASE_COUNTS, EXPECTED_MANIFEST, EXPECTED_QUERIES, preflight, project_queries,
)


def test_preflight_is_offline_and_binds_frozen_queries_and_targets():
    verification, queries, targets, gates = preflight()
    assert verification["verified_before_first_network_request"]
    assert verification["execution_manifest_sha256"] == EXPECTED_MANIFEST
    assert verification["query_set_sha256"] == EXPECTED_QUERIES
    assert len(queries) == 55
    assert sum(len(q["contributions"]) for q in queries) == 63
    assert Counter(q["case_id"] for q in queries) == Counter(CASE_COUNTS)
    assert len(targets) == len(gates) == 8
    assert all(q["execution_status"] == "NOT_EXECUTED_PREREGISTRATION" for q in queries)


def test_transport_projection_changes_no_frozen_query_bytes():
    _, queries, _, _ = preflight()
    projected = project_queries(queries)
    assert [(q["query_id"], q["exact_query_text"], q["query_sha256"]) for q in projected] == [
        (q["query_id"], q["exact_query_text"], q["query_sha256"]) for q in queries]
    assert all(q["contributing_intent_types"] and q["relation_core_ids"] and q["surface_plan_ids"] and q["pubmed_ast_hashes"] for q in projected)
