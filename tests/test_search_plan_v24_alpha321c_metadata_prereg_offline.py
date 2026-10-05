"""Offline source-ID request freeze and inherited-authority failure checks."""

import socket
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321c_metadata_prereg_offline as m


def article_xml(year, month="01", pmid="123", extra=""):
    return f'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>{pmid}</PMID>
        <Article><Journal><JournalIssue><PubDate><Year>{year}</Year><Month>{month}</Month>
        <Day>01</Day></PubDate></JournalIssue></Journal>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
        </Article></MedlineCitation><PubmedData><ArticleIdList>
        <ArticleId IdType="pubmed">{pmid}</ArticleId><ArticleId IdType="pmc">PMC123</ArticleId>
        <ArticleId IdType="doi">10.1/direct</ArticleId></ArticleIdList>{extra}
        </PubmedData></PubmedArticle></PubmedArticleSet>'''.encode()


def test_exact_72_request_universe_has_frozen_sample_order_and_provenance():
    state = m.verify_inputs()
    requests = m.request_manifest(state["sample"])
    assert len(requests) == len({r["logical_request_id"] for r in requests}) == 72
    assert [r["sampled_pmids"][0] for r in requests] == [s["pmid"] for s in state["sample"]]
    for ordinal, (request, source) in enumerate(zip(requests, state["sample"]), 1):
        assert request["execution_ordinal"] == ordinal
        assert request["parameters"] == {"db": "pubmed", "retmode": "xml", "id": source["pmid"]}
        assert request["source_selection_provenance"] == source
        assert m.sha(m.canonical(request["request_payload"])) == request["request_payload_sha256"]


def test_inherited_date_parser_is_not_primary_2026_compatible():
    parsed = m.historical.parse_metadata(article_xml("2026", "07"), "123")
    assert parsed["date_state"] == "INELIGIBLE"
    assert m.authority_audit()["complete_metadata_eligibility_parser_authority_resolved"] is False


def test_inherited_date_parser_has_no_partial_year_boundary_semantics():
    january = m.historical.parse_metadata(article_xml("2024", "01"), "123")
    november = m.historical.parse_metadata(article_xml("2024", "11"), "123")
    assert january["date_state"] == november["date_state"] == "CLEAR"
    assert january["publication_year"] == november["publication_year"] == 2024
    assert "publication_date" not in january


def test_reference_ids_do_not_bind_sampled_source_identity():
    refs = '<ReferenceList><Reference><ArticleIdList><ArticleId IdType="pmc">PMC999</ArticleId>' \
           '<ArticleId IdType="doi">10.1/reference</ArticleId></ArticleIdList></Reference></ReferenceList>'
    parsed = m.historical.parse_metadata(article_xml("2024", extra=refs), "123")
    assert parsed["pmcid"] == "PMC123"
    assert parsed["doi"] == "10.1/direct"
    assert parsed["reference_article_ids_scanned"] is False


@pytest.mark.parametrize("kind,value", [("pmcid", "PMC123"), ("doi", "10.1/shared")])
def test_existing_collision_detector_has_no_sample_lifecycle_disposition(kind, value):
    collisions = m.source_identity.identifier_collision_rows([
        {"pmid": "123", kind: value}, {"pmid": "456", kind: value}])
    assert len(collisions) == 1
    assert collisions[0]["status"] == "identifier_conflict"
    assert collisions[0]["resolution_status"] == "fail_closed"
    assert not {"retained_pmid", "excluded_pmids", "pre_oa_handoff_state"} & collisions[0].keys()
    audit = m.authority_audit()
    assert audit["same_attempt_collision_detection_resolved"] is True
    assert audit["same_attempt_collision_disposition_authority_resolved"] is False


def test_registry_alias_normalization_reproduces_frozen_counts():
    state = m.verify_inputs()
    assert len(state["canonical_aliases"]["pmcid"]["canonical_values"]) == 146
    assert len(state["canonical_aliases"]["doi"]["canonical_values"]) == 180
    assert state["transport"]["maximum_attempts_per_request"] == 4
    assert state["transport"]["timeout_seconds"] == 60
    assert state["transport"]["backoff_seconds"] == [2, 4, 8]


def test_blocked_offline_preregistration_freezes_requests_without_authorizing_C1(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Metadata network/client execution is prohibited during preregistration")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(m.historical.PubMedTransport, "__init__", forbidden)
    with TemporaryDirectory(prefix="alpha321c_prereg_test_", dir=m.RUNS) as temporary:
        monkeypatch.setattr(m, "OUT", Path(temporary) / "prereg")
        result = m.run()
        assert result["status"] == "failed"
        assert result["alpha3_21c_classification"] == m.CLASS_BLOCKED
        assert result["planned_metadata_logical_requests"] == 72
        assert result["metadata_request_authority_resolved"] is True
        assert result["metadata_parser_authority_resolved"] is False
        assert result["publication_date_policy_frozen"] is False
        assert result["same_attempt_source_identity_collision_policy_resolved"] is False
        assert m.root_hash(m.OUT, m.ROOT_MARKER) == result[m.ROOT_MARKER]
        for stem, suffix in (("metadata_request_manifest", ".jsonl"),
                             ("metadata_response_validity_contract", ".json"),
                             ("metadata_pre_oa_handoff_contract", ".json")):
            assert m.digest(m.OUT / (stem + suffix)) == result[stem + "_sha256"]
        handoff = m.obj(m.OUT / "alpha3_21c1_execution_handoff.json")
        assert handoff["execution_ready"] is handoff["authorization_ready"] is False
        assert handoff["network_authorized"] is False
        assert handoff["maximum_potential_transport_attempts_if_authorized"] == 288
        assert all(result[key] == 0 for key in m.NO_CALLS)
        assert len(m.rows(m.OUT / "metadata_request_manifest.jsonl")) == 72
        with pytest.raises(m.b.StageFailure, match="OUTPUT_ALREADY_EXISTS"):
            m.run()
