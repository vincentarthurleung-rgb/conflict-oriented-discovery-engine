"""Offline tests for alpha3.21A's frozen PubMed request universe."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321a_source_acquisition_prereg_offline as a


@pytest.mark.parametrize("count,expected", [
    (0, [0]), (1, [0]), (50, [0]), (51, [0, 50]),
    (100, [0, 50]), (101, [0, 50, 100]),
    (150, [0, 50, 100]), (151, [0, 50, 100, 150]),
    (200, [0, 50, 100, 150]),
])
def test_conditional_page_predicate(count: int, expected: list[int]) -> None:
    assert [offset for offset in a.PAGE_OFFSETS if a.page_required(offset, count)] == expected


def test_potential_request_universe_matches_frozen_master(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(a, "OUT", tmp_path / "not_created")
    state = a.preflight()
    pages = a.potential_requests(state["queries"])
    assert len(pages) == 24
    assert len({row["logical_request_id"] for row in pages}) == 24
    assert len([row for row in pages if row["retstart"] == 0]) == 6
    assert all(row["request_payload"]["term"] == state["queries"][
        row["stratum_ordinal"] - 1]["query_utf8"] for row in pages)


def test_temp_freeze_copies_queries_and_does_not_execute(monkeypatch) -> None:
    with TemporaryDirectory(prefix="alpha321a_test_", dir=a.RUNS) as temporary:
        output = Path(temporary) / "prereg"
        monkeypatch.setattr(a, "OUT", output)
        result = a.run()
        assert (output / "alpha3_21_source_query_set.jsonl").read_bytes() == (
            a.MASTER / "alpha3_21_source_query_set.jsonl").read_bytes()
        assert a.root_hash(output, a.ROOT_MARKER) == result[a.ROOT_MARKER]
        first = a.rows(output / "alpha3_21_first_page_request_manifest.jsonl")
        potential = a.rows(output / "alpha3_21_potential_page_request_manifest.jsonl")
        assert len(first) == 6 and len(potential) == 24
        assert all(row["retstart"] == 0 for row in first)
        assert all(row["execution_predicate"] == "UNCONDITIONAL_FIRST_PAGE"
                   for row in first)
        validation = json.loads((output / "validation.json").read_text())
        assert validation["network_calls"] == validation["pubmed_calls"] == 0
        assert validation["deduplication_performed"] is False
        assert validation["current_attempt_exposure_registry_created"] is False
        assert a.root_hash(a.MASTER,
            "search_plan_v24_primary_alpha3_21_master_prereg_sha256") == a.MASTER_ROOT
