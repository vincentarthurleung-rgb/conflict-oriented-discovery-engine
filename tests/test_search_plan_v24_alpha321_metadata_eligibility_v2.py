"""Date interval and identity-component tests using offline synthetic metadata."""

import socket
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321c1_authority_resolution_offline as freeze
from scripts import search_plan_v24_alpha321_metadata_eligibility_v2 as v2


@pytest.mark.parametrize("fixture", freeze.date_fixtures(), ids=lambda f: f["fixture_id"])
def test_frozen_date_fixture(fixture):
    raw = fixture["raw_xml"].encode()
    first = v2.resolve_publication_dates(raw, fixture["expected_pmid"])
    second = v2.resolve_publication_dates(raw, fixture["expected_pmid"])
    assert first["state"] == fixture["expected_date_state"]
    assert freeze.canonical(first) == freeze.canonical(second)


@pytest.mark.parametrize("text,start,end", [
    ("2026-09", "2026-09-01", "2026-09-30"),
    ("2026", "2026-01-01", "2026-12-31"),
    ("2024-02", "2024-02-01", "2024-02-29"),
    ("2026 Jan 1-15", "2026-01-01", "2026-01-15"),
    ("2025 Dec-2026 Jan", "2025-12-01", "2026-01-31"),
    ("2026-07-01 to 2026-07-15", "2026-07-01", "2026-07-15"),
])
def test_interval_bounds_do_not_invent_precision(text, start, end):
    actual = v2.normalize_date_text(text)
    assert actual[0].isoformat() == start
    assert actual[1].isoformat() == end


@pytest.mark.parametrize("text", ["2026-02-29", "2026-13", "2026 Mar-Jan", "2026 Jan 31-1",
                                   "2026-10/2026-09", "2026 winter", "2026-07-01/random"])
def test_invalid_date_text_is_not_guessed(text):
    with pytest.raises(ValueError):
        v2.normalize_date_text(text)


def test_reference_and_history_dates_cannot_rescue_missing_direct_date():
    refs = '<ReferenceList><Reference><Article><ArticleDate><Year>2026</Year><Month>07</Month></ArticleDate>' \
           '</Article></Reference></ReferenceList><History><PubMedPubDate><Year>2026</Year><Month>07</Month>' \
           '</PubMedPubDate></History>'
    raw = freeze.synthetic_xml(pubdate="", extra_data=refs)
    assert v2.resolve_publication_dates(raw, "123")["state"] == v2.DATE_MISSING


def test_year_only_does_not_become_clear_by_intersecting_with_exact_date():
    raw = freeze.synthetic_xml(pubdate="<Year>2026</Year>",
        article_dates="<ArticleDate><Year>2026</Year><Month>07</Month><Day>01</Day></ArticleDate>")
    result = v2.resolve_publication_dates(raw, "123")
    assert result["state"] == v2.DATE_CONFLICT
    assert result["representations"][0]["latest_possible_date"] == "2026-12-31"


def test_transitive_components_fail_close_all_without_collapsing_or_winner():
    records = [{"pmid": "1", "doi": "10.fixture/shared"},
               {"pmid": "2", "doi": "10.fixture/shared", "pmcid": "PMC9"},
               {"pmid": "3", "pmcid": "PMC9"}, {"pmid": "4", "doi": "10.fixture/distinct"}]
    result = v2.collision_components(records)
    assert len(result["components"]) == 1
    assert result["components"][0]["member_pmids"] == ["1", "2", "3"]
    assert all(result["source_states"][p] == v2.COLLISION for p in ("1", "2", "3"))
    assert result["source_states"]["4"] == "CLEAR"
    assert result["winner_selection_used"] is result["collapse_used"] is result["replacement_allowed"] is False
    assert freeze.canonical(v2.collision_components(list(reversed(records)))) == freeze.canonical(result)


def test_normalization_is_existing_exact_canonical_identity_not_near_matching():
    graph = v2.collision_components([
        {"pmid": "1", "doi": "https://doi.org/10.Fixture/ABC"},
        {"pmid": "2", "doi": "10.fixture/abc"},
        {"pmid": "3", "doi": "10.fixture/abcd"}])
    assert graph["source_states"]["1"] == graph["source_states"]["2"] == v2.COLLISION
    assert graph["source_states"]["3"] == "CLEAR"


def policies():
    state = freeze.verify_inputs()
    return freeze.obj(state["acceptance_path"]), freeze.obj(state["exclusion_path"])


def response(pmid, **kwargs):
    return {"pmid": pmid, "raw_xml": freeze.synthetic_xml(pmid=pmid, pmcid="PMC" + pmid,
                                                         doi="10.fixture/" + pmid, **kwargs)}


def test_historical_contaminated_member_participates_and_does_not_rescue_neighbor():
    accepted, excluded = policies()
    first = {"pmid": "1", "raw_xml": freeze.synthetic_xml(pmid="1", pmcid="PMC1", doi="10.fixture/shared")}
    second = {"pmid": "2", "raw_xml": freeze.synthetic_xml(pmid="2", pmcid="PMC2", doi="10.fixture/shared")}
    result = v2.evaluate_batch([first, second], accepted, excluded, {"PMC1"}, set())
    assert result["pre_oa_handoff"] == []
    assert result["records"][0]["primary_terminal_reason"] == "HISTORICAL_EXACT_ALIAS_CONTAMINATION"
    assert result["records"][1]["primary_terminal_reason"] == v2.COLLISION
    assert all(r["same_attempt_alias_collision_state"] == v2.COLLISION for r in result["records"])
    assert len(result["records"]) == 2 and result["replacement_used"] is False


def test_current_alias_exposure_does_not_self_exclude():
    accepted, excluded = policies()
    result = v2.evaluate_batch([response("1")], accepted, excluded, set(), set())
    assert result["records"][0]["historical_alias_contamination_state"] == "CLEAR"
    assert result["records"][0]["same_attempt_alias_collision_state"] == "CLEAR"
    assert result["records"][0]["pre_oa_handoff_state"] == "PRE_OA_CLEAR"


def test_sole_updateof_remains_conditionally_deferred():
    accepted, excluded = policies()
    relation = '<CommentsCorrectionsList><CommentsCorrections RefType="UpdateOf"><PMID>99</PMID>' \
               '</CommentsCorrections></CommentsCorrectionsList>'
    result = v2.evaluate_batch([response("1", relationships=relation)], accepted, excluded, set(), set())
    record = result["records"][0]
    assert record["correction_update_state"] == "UNRESOLVED"
    assert record["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE"
    assert record["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF"


def test_metadata_failure_is_isolated_and_sample_units_are_preserved():
    accepted, excluded = policies()
    result = v2.evaluate_batch([{"pmid": "1", "raw_xml": b"invalid"}, response("2")],
                               accepted, excluded, set(), set())
    assert len(result["records"]) == 2
    assert result["records"][0]["primary_terminal_reason"] == "METADATA_TERMINAL_FAILURE"
    assert [r["pmid"] for r in result["pre_oa_handoff"]] == ["2"]
    assert result["replacement_used"] is False


@pytest.mark.parametrize("pubdate", ["<Year>2026</Year>",
    "<Year>2026</Year><Month>10</Month><Day>01</Day>", "<MedlineDate>unknown</MedlineDate>", ""])
def test_date_excluded_or_unresolved_source_cannot_enter_handoff_or_be_replaced(pubdate):
    accepted, excluded = policies()
    result = v2.evaluate_batch([response("1", pubdate=pubdate)], accepted, excluded, set(), set())
    assert result["pre_oa_handoff"] == []
    assert result["records"][0]["primary_terminal_reason"] == "DATE_EXCLUDED_OR_UNRESOLVED"
    assert len(result["records"]) == 1 and result["replacement_used"] is False


def test_same_record_repeated_identifiers_do_not_create_collision():
    accepted, excluded = policies()
    raw = freeze.synthetic_xml().replace(b'</ArticleIdList>', b'<ArticleId IdType="pmc">PMC123</ArticleId></ArticleIdList>')
    result = v2.evaluate_batch([{"pmid": "123", "raw_xml": raw}], accepted, excluded, set(), set())
    assert result["collision_graph"]["components"] == []
    assert result["records"][0]["pre_oa_handoff_state"] == "PRE_OA_CLEAR"


def test_stable_components_and_historical_parser_are_preserved():
    accepted, excluded = policies()
    raw = freeze.synthetic_xml()
    before = freeze.c.historical.parse_metadata(raw, "123")
    after = v2.parse_source(raw, "123", accepted, excluded)
    for key in ("pmid", "pmcid", "doi", "direct_primary_article_ids", "direct_pubmed_ids", "metadata_state",
                "metadata_unresolved_reasons", "publication_types", "correction_relationships"):
        assert after[key] == before[key]
    assert before["date_state"] == "INELIGIBLE" and after["date_state"] == "CLEAR"
    old = freeze.synthetic_xml(pubdate="<Year>2024</Year>")
    assert freeze.c.historical.parse_metadata(old, "123")["date_state"] == "CLEAR"
    assert freeze.c.historical.parse_metadata(raw, "123") == before


def test_offline_overlay_is_ready_but_preserves_failed_C_and_original_requests(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("No network, metadata client construction, or request regeneration is permitted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(freeze.c.historical.PubMedTransport, "__init__", forbidden)
    monkeypatch.setattr(freeze.c, "request_manifest", forbidden)
    original_requests = (freeze.C / "metadata_request_manifest.jsonl").read_bytes()
    with TemporaryDirectory(prefix="alpha321c1_overlay_test_", dir=freeze.RUNS) as temporary:
        monkeypatch.setattr(freeze, "OUT", Path(temporary) / "overlay")
        result = freeze.run()
        assert result["status"] == "completed" and result["metadata_execution_ready"] is True
        assert freeze.root_hash(freeze.OUT, freeze.ROOT_MARKER) == result[freeze.ROOT_MARKER]
        assert all(result[k] == 0 for k in freeze.NO_CALLS)
        assert not (freeze.OUT / "metadata_request_manifest.jsonl").exists()
        assert (freeze.C / "metadata_request_manifest.jsonl").read_bytes() == original_requests
        assert freeze.obj(freeze.C / "validation.json")["status"] == "failed"
        assert freeze.obj(freeze.C / "validation.json")["metadata_parser_authority_resolved"] is False
        handoff = freeze.obj(freeze.OUT / "alpha3_21c1_future_execution_handoff.json")
        assert handoff["network_authorized"] is False
        assert handoff["next_execution_stage"] == "alpha3.21C2"
        assert handoff["logical_request_count"] == 72
        with pytest.raises(freeze.c.b.StageFailure, match="OUTPUT_ALREADY_EXISTS"):
            freeze.run()
