"""Offline checks for the prospective PMC-subset query and ESearch validity V2."""

import json

import pytest

from scripts import search_plan_v24_alpha318a4_esearch_response_validity as validity
from scripts import search_plan_v24_alpha318a4_freeze_query_runtime_amendment_offline as freeze


@pytest.mark.parametrize("row", [json.loads(line) for line in
    (freeze.OUT / "esearch_synthetic_cases.jsonl").read_text().splitlines()],
    ids=lambda row: row["case_id"])
def test_frozen_synthetic_case(row):
    actual = validity.validate_response(row["http_status"], row["raw_utf8"].encode(), 0, 50)
    assert actual["state"] == row["expected_state"]


def test_errorlist_is_checked_before_missing_count():
    raw = b'{"esearchresult":{"errorlist":{"phrasesnotfound":["pmc"]}}}'
    assert validity.validate_response(200, raw, 0, 50)["state"] == "QUERY_SEMANTIC_ERROR"


def test_unknown_warning_fails_closed_even_with_positive_count():
    raw = b'{"esearchresult":{"count":"1","retstart":"0","retmax":"1","idlist":["123"],"warninglist":{"future":["altered"]}}}'
    assert validity.validate_response(200, raw, 0, 50)["state"] == "QUERY_WARNING_UNRESOLVED"


def test_query_delta_is_exact_and_prior_roots_are_preserved():
    original = freeze.verify()
    changed, delta = freeze.amended_queries(original)
    assert len(changed) == len(delta) == 6
    for old, new, mapping in zip(original, changed, delta):
        assert old["query_utf8"].replace(freeze.INVALID, freeze.REPLACEMENT) == new["query_utf8"]
        assert new["query_utf8"].replace(freeze.REPLACEMENT, freeze.INVALID) == old["query_utf8"]
        assert mapping["changed_scientific_terms"] == 0
        assert mapping["changed_date_constraints"] == 0


def test_frozen_manifest_and_root_are_self_consistent():
    marker = (freeze.OUT / freeze.ROOT_MARKER).read_text().strip()
    assert freeze.prior.all_file_root(freeze.OUT, freeze.ROOT_MARKER) == marker
    manifest_path = freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2.json"
    manifest = json.loads(manifest_path.read_text())
    assert freeze.prior.sha(manifest_path.read_bytes()) == (
        freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2_sha256").read_text().strip()
    assert manifest["material_runtime_policy_unresolved_count"] == 0
    assert manifest["active_source_frame_policy_v2"]["query_bytes_source"] == "source_query_set_v2.jsonl"
    assert manifest["queries"][0]["query_utf8"].count(freeze.REPLACEMENT) == 1
    assert manifest["actual_builder_scientific_call_count_before_valid_rerun"] == "UNKNOWN"
