"""V2 source-execution preflight and fail-closed validation, without network."""

import json

from scripts import search_plan_v24_alpha318a_v2_execute_ncbi_source_acquisition as run


def test_all_frozen_v2_roots_and_references_before_network():
    manifest = run.verify_before_network()
    assert len(manifest["queries"]) == 6
    assert manifest["query_file"]["sha256"] == run.QUERY_SHA
    assert manifest["pubmed_esearch_response_validity_v2_sha256"] == run.VALIDITY_SHA
    assert manifest["active_source_frame_policy_v2"]["page_size"] == 50
    assert manifest["active_source_frame_policy_v2"]["frame_cap_per_stratum"] == 200
    assert all(q["query_utf8"].count('"pubmed pmc"[sb]') == 1 for q in manifest["queries"])


def test_original_error_response_cannot_be_a_v2_zero_frame():
    original = run.ROOT / "runs/20260928_search_plan_v24_dev_alpha3_18a_ncbi_only_source_acquisition"
    rows = [json.loads(line) for line in (original / "source_query_execution_results.jsonl").read_text().splitlines()]
    raw = (original / rows[0]["attempts"][-1]["raw_path"]).read_bytes()
    verdict = run.validity.validate_response(200, raw, 0, 50)
    assert verdict["state"] == "QUERY_SEMANTIC_ERROR"
    assert verdict["count"] is None
    assert verdict["idlist"] is None


def test_warnings_fail_even_if_hits_are_present():
    raw = b'{"esearchresult":{"count":"10","retstart":"0","retmax":"1","idlist":["123"],"warninglist":{"phrasesignored":["term"]}}}'
    verdict = run.validity.validate_response(200, raw, 0, 50)
    assert verdict["state"] == "QUERY_WARNING_UNRESOLVED"
