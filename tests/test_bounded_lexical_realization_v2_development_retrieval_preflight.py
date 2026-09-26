from collections import Counter

from tools.run_bounded_lexical_realization_v2_development_retrieval import (
    CASE_COUNTS, EXPECTED_MANIFEST, EXPECTED_QUERY_SET, RUN, preflight,
)


def test_preflight_binds_exactly_frozen_query_and_policy_inputs():
    verification, manifest, adapted, targets, gates = preflight()
    assert verification["verified_before_first_network_request"]
    assert verification["execution_manifest_sha256"] == EXPECTED_MANIFEST
    assert verification["query_set_sha256"] == EXPECTED_QUERY_SET
    assert verification["downstream_policy_changes"] == 0
    assert len(adapted) == 55
    assert sum(len(q["contributions"]) for q in adapted) == 63
    assert Counter(q["case_id"] for q in adapted) == Counter(CASE_COUNTS)
    assert len({q["query_id"] for q in adapted}) == 55
    assert len(targets) == len(gates) == 8
    assert manifest["execution_status"] == "NOT_EXECUTED_PREREGISTRATION"
    assert manifest["observed_retrieval_values"] is None


def test_preflight_creates_no_execution_directory():
    before = RUN.exists()
    preflight()
    assert RUN.exists() == before
