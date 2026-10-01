import json

from scripts.run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility import oa_subset_state


def response(count, ids, retmax):
    return json.dumps({"esearchresult": {"count": str(count), "retstart": "0",
        "retmax": str(retmax), "idlist": ids, "querytranslation": "frozen query"}}).encode()


def attempts():
    return [{"http_status": 200}]


def test_exact_numeric_uid_is_oa_positive():
    state, verdict = oa_subset_state(response(1, ["123"], 1), attempts(), "PMC123")
    assert state == "OA_SUBSET_ELIGIBLE"
    assert verdict["query_semantic_success"]


def test_valid_zero_is_oa_negative():
    state, verdict = oa_subset_state(response(0, [], 0), attempts(), "PMC123")
    assert state == "OA_SUBSET_INELIGIBLE"
    assert verdict["query_semantic_success"]


def test_other_uid_is_unresolved_not_oa_proof():
    state, _ = oa_subset_state(response(1, ["456"], 1), attempts(), "PMC123")
    assert state == "OA_SUBSET_UNRESOLVED"


def test_error_only_envelope_is_unresolved():
    raw = json.dumps({"esearchresult": {"ERROR": "backend failed"}}).encode()
    state, verdict = oa_subset_state(raw, attempts(), "PMC123")
    assert state == "OA_SUBSET_UNRESOLVED"
    assert not verdict["query_semantic_success"]
