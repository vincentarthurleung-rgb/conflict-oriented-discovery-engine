"""Offline D binding tests: synthetic licenses/BODY/identity, no primary JATS."""

import socket
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321d_prereg_offline as s


@pytest.mark.parametrize("fixture", s.license_fixtures(), ids=lambda f: f["fixture_id"])
def test_exact_hardened_license_fixture(fixture):
    try:
        state = s.d19.license_v2.extract_license_v2(fixture["raw_xml"].encode())["state"]
    except s.d19.ET.ParseError:
        state = "INVALID_XML"
    assert state == fixture["expected_state"]


def test_historical_identity_gap_is_proved_without_changing_parser():
    results = s.identity_gap_probe()
    assert {r["fixture_id"] for r in results} == {"contradictory_direct_pmid", "contradictory_direct_doi"}
    assert all(r["historical_canonicalizer_accepts"] for r in results)
    assert all(r["historical_canonicalizer_checks_this_identifier"] is False for r in results)


@pytest.mark.parametrize("raw", [
    b'<article><front><article-meta><article-id pub-id-type="pmc">456</article-id></article-meta></front><back><ref-list><article-id pub-id-type="pmc">123</article-id></ref-list></back></article>',
    b'<article><front><article-meta><article-id pub-id-type="pmc">123</article-id><article-id pub-id-type="pmcid">456</article-id></article-meta></front></article>',
    b'<article/>', b'<root><article/><article/></root>', b'malformed XML',
])
def test_existing_PMCID_and_structure_guards_are_not_weakened(raw):
    with pytest.raises((ValueError, s.d19.ET.ParseError)):
        s.d19.frozen_rules.canonical_jats(raw, "PMC123")


def test_missing_optional_JATS_pmid_doi_not_newly_rejected():
    raw = b'<article><front><article-meta><article-id pub-id-type="pmc">123</article-id></article-meta></front></article>'
    assert s.d19.frozen_rules.canonical_jats(raw, "PMC123").startswith(b"<article>")


@pytest.mark.parametrize("type_state,expected", [("SOURCE_TYPE_ELIGIBLE", "CLEAR"),
    ("SOURCE_TYPE_INELIGIBLE", "INELIGIBLE"), ("SOURCE_TYPE_UNRESOLVED", "UNRESOLVED")])
def test_UpdateOf_uses_exact_historical_mechanical_rule(type_state, expected):
    result = s.d19_1.correction.classify(["Journal Article"], [{"ref_type": "UpdateOf", "linked_pmid": "999", "ref_source": None}],
        independent_primary_state=type_state)
    assert result["state"] == "CORRECTION_REFERENCE_" + expected


def test_frozen_request_universe_is_49_mandatory_and_49_conditional():
    state = s.preflight()
    requests = s.requests_for(state["sources"])
    assert len(requests) == len({r["logical_request_id"] for r in requests}) == 98
    assert [r["pmid"] for r in requests[:49]] == [r["pmid"] for r in requests[49:]] == [r["pmid"] for r in state["sources"]]
    assert all(r["request_class"] == "PMC_OA_SUBSET" for r in requests[:49])
    assert all(r["request_class"] == "PMC_JATS" and "OA_SUBSET_ELIGIBLE" in r["activation_condition"] for r in requests[49:])
    assert all(r["network_authorized"] is False for r in requests)
    assert s.canonical(requests) == s.canonical(s.requests_for(state["sources"]))
    for request in requests:
        assert request["request_payload_sha256"] == s.sha(s.canonical(request["request_payload"]))
        assert request["request_payload"]["parameters"]["db"] == "pmc"


def test_body_projection_has_no_abstract_document_token_or_anchors():
    xml = b'<article><front><article-meta><abstract><p>SECRET ABSTRACT</p></abstract></article-meta></front><body><sec><title>Methods</title><p>A <italic>B</italic> C<xref ref-type="bibr">CITATION</xref> D</p><sec><title>Results</title><p>Nested</p></sec><fig><caption><p>Figure</p></caption></fig><table-wrap><caption>Table</caption></table-wrap></sec><sec><title>References</title><p>SECRET REFERENCE</p></sec><sec sec-type="supplementary-material"><p>SECRET SUPPLEMENT</p></sec></body><back><p>SECRET BACK</p></back></article>'
    result = s.body_only.canonical_body(xml)
    assert result["body_text"] == "A B C D\n\nNested\n\nFigure\n\nTable"
    assert set(result) == {"body_text", "paragraphs", "normalization"}
    assert [p["section_path"] for p in result["paragraphs"]] == [[1], [1, 1], [1], [1]]
    assert [p["ordinal"] for p in result["paragraphs"]] == [1, 1, 2, 3]
    for paragraph in result["paragraphs"]:
        assert result["body_text"][paragraph["start_offset"]:paragraph["end_offset"]] == paragraph["text"]
        assert "span_id" not in paragraph
    assert "SECRET" not in result["body_text"]


def test_body_normalization_unicode_offsets_and_historical_60000_limit():
    xml = '<article><body><p>Ａ\u00a0 β\tγ</p><p>' + 'x' * 60000 + '</p></body></article>'
    result = s.body_only.canonical_body(xml.encode())
    assert result["body_text"].startswith("A β γ\n\n")
    assert len(result["body_text"]) == 60000
    assert result["paragraphs"][-1]["end_offset"] == 60000


@pytest.mark.parametrize("xml", [b'<article/>', b'<article><body/></article>', b'<root><body><p>x</p></body></root>'])
def test_missing_or_empty_BODY_blocks_without_repair(xml):
    with pytest.raises(ValueError):
        s.body_only.canonical_body(xml)


def test_offline_freeze_retains_identity_blocker_and_all_historical_roots(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("NETWORK_OR_CLIENT_CONSTRUCTION_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", prohibited)
    monkeypatch.setattr(socket, "create_connection", prohibited)
    monkeypatch.setattr(s.d19.PMCTransport, "__init__", prohibited)
    upstream = [(s.C2, s.c2.ROOT_MARKER), (s.MASTER, "search_plan_v24_primary_alpha3_21_master_prereg_sha256"),
        (s.d19.OUT, s.d19.ROOT_MARKER), (s.d19_1.OUT, s.d19_1.ROOT_MARKER)]
    before = [s.root_hash(p, marker) for p, marker in upstream]
    with TemporaryDirectory(prefix="alpha321d_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = s.run()
        assert result["status"] == "failed"
        assert result["alpha3_21d_classification"] == s.CLASS_BLOCKED
        assert result["pmc_client_mechanics_resolved"] is True
        assert result["pmc_acquisition_authority_resolved"] is False
        assert result["execution_ready"] is False
        assert result["updateof_structural_resolution_authority_resolved"] is True
        assert result["pre_oa_input_source_count"] == 49
        assert result["pre_oa_deferred_source_count"] == 3
        assert all(result[k] == 0 for k in s.NO_CALLS)
        assert s.obj(s.OUT / "alpha3_21d1_execution_handoff.json")["network_authorized"] is False
        assert s.obj(s.OUT / "pmc_primary_source_identity_binding_contract.json")["direct_JATS_DOI_comparison_authority"] is None
        assert len(s.rows(s.OUT / "alpha3_21d_network_request_manifest.jsonl")) == 98
        assert s.root_hash(s.OUT, s.ROOT_MARKER) == result[s.ROOT_MARKER]
        assert not any("ConstructionEvidenceDocument" in p.name for p in s.OUT.iterdir())
        with pytest.raises(Exception, match="NO_OVERWRITE"):
            s.run()
    assert [s.root_hash(p, marker) for p, marker in upstream] == before


def test_integrity_mismatch_stops_before_creating_requests(monkeypatch):
    monkeypatch.setattr(s, "C2_SHA", "0" * 64)
    with pytest.raises(Exception, match="C2_ROOT_MISMATCH"):
        s.preflight()
