import json
from pathlib import Path

from tools.freeze_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline import (
    ALPHA33, CASES, HARD_TAIL, MAX_FULLTEXTS, PAGE_SIZE, SOFT_TAIL,
    historical_dimensions, query_projection,
)


def frozen_manifest():
    return json.loads((ALPHA33 / "development_retrieval_freeze_manifest.json").read_text())


def test_query_projection_preserves_all_frozen_queries():
    rows = query_projection(frozen_manifest())
    assert len(rows) == 29
    assert len({row["query_id"] for row in rows}) == 29


def test_query_projection_preserves_text_hash_and_relation_provenance():
    source = frozen_manifest()["exact_compiled_query_set"]
    rows = query_projection(frozen_manifest())
    for original, projected in zip(source, rows, strict=True):
        assert projected["exact_query_text"] == original["query_string"]
        assert projected["query_sha256"] == original["query_sha256"]
        assert projected["relation_core_ref"] == original["source_link_sha256"]


def test_query_projection_contains_no_observed_hit_values():
    assert all("raw_hit_count" not in row and "returned_pmid_sequence" not in row
               for row in query_projection(frozen_manifest()))


def test_frozen_case_set_is_exactly_eight_cases():
    assert tuple(sorted({row["case_id"] for row in query_projection(frozen_manifest())})) == CASES


def test_historical_policy_dimensions_are_fully_reconstructed():
    rows = historical_dimensions()
    assert rows
    assert all(row["status"] == "EXACTLY_RECONSTRUCTED" for row in rows)


def test_historical_policy_explicitly_freezes_case_scoped_pmid_identity():
    row = next(row for row in historical_dimensions() if row["dimension"] == "PMID deduplication")
    assert "within case" in row["policy"]
    assert "no cross-case elimination" in row["policy"]


def test_historical_policy_explicitly_freezes_no_replacement():
    row = next(row for row in historical_dimensions() if row["dimension"] == "replacement")
    assert row["policy"].startswith("no replacement")


def test_historical_tail_constants_match_frozen_protocol():
    assert (SOFT_TAIL, HARD_TAIL, PAGE_SIZE) == (120, 180, 30)


def test_historical_fulltext_cap_is_ten():
    assert MAX_FULLTEXTS == 10


def test_no_case_specific_rule_literals_in_policy_reconstruction_function():
    source = Path(__file__).parents[1].joinpath(
        "tools/freeze_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline.py"
    ).read_text()
    function_body = source.split("def historical_dimensions()", 1)[1].split("def main()", 1)[0]
    assert "heldout_v2_10" not in function_body
