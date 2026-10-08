"""Prospective identity fixtures and a network-free D.1 authority freeze."""

import socket
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321d1_identity_authority_offline as s
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as v2


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("NETWORK_OR_TRANSPORT_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", prohibited)
    monkeypatch.setattr(socket, "create_connection", prohibited)
    monkeypatch.setattr(s.d.d19.PMCTransport, "__init__", prohibited)


@pytest.mark.parametrize("fixture", s.identity_fixtures(), ids=lambda f: f["fixture_id"])
def test_synthetic_fixture(fixture):
    result = s.fixture_results([fixture])[0]["result"]
    assert result["identity_state"] == fixture["expected_identity_state"]
    if fixture["expected_identity_state"] is None:
        assert result["jats_validity_state"] == "JATS_FAILED_NO_REPLACEMENT"
        assert result["direct_identifiers"] is None
        assert result["structural_parser_failure_is_identifier_mismatch"] is False


def result_for(name):
    fixture = next(f for f in s.identity_fixtures() if f["fixture_id"] == name)
    return v2.validate_jats_primary_identity_v2(fixture["raw_xml"].encode(), **fixture["expected_identity"])


def test_all_required_matrix_cases_and_more_are_present():
    names = {f["fixture_id"] for f in s.identity_fixtures()}
    assert {"correct_all", "missing_pmid", "missing_doi", "missing_both_secondary", "wrong_pmcid",
        "wrong_pmid", "wrong_doi", "wrong_both_secondary", "duplicate_equal_pmid", "conflicting_pmid",
        "duplicate_equal_doi", "conflicting_doi", "missing_pmcid", "pmcid_only_reference_list",
        "pmid_only_reference_list", "doi_only_reference_list"} <= names
    assert len(names) == len(s.identity_fixtures()) == 34


@pytest.mark.parametrize("kind", ["pmid", "doi", "pmcid"])
def test_equal_canonical_duplicates_preserve_occurrence_count(kind):
    result = result_for("duplicate_equal_" + kind)
    summary = result["direct_identifiers"]["identifier_summaries"][kind]
    assert summary["assertion_count"] == 2
    assert summary["distinct_canonical_count"] == 1
    assert summary["multiplicity_state"] == "DIRECT_IDENTIFIER_REDUNDANT_SAME_VALUE"
    assert result["source_identity_allows_progression"] is True


@pytest.mark.parametrize("kind", ["pmid", "doi", "pmcid"])
def test_distinct_canonical_values_have_no_winner_or_majority(kind):
    result = result_for("conflicting_" + kind)
    summary = result["direct_identifiers"]["identifier_summaries"][kind]
    assert summary["distinct_canonical_count"] == 2
    assert summary["effective_value"] is None
    assert result["identity_state"] == v2.CONFLICT
    assert result["source_identity_allows_progression"] is False
    assert result["conflicting_assertions_authoritative_for_exposure"] is False
    assert result["majority_vote_used"] is False


def test_multiple_mismatches_all_retained_reporting_precedence_only():
    result = result_for("wrong_both_secondary")
    assert result["identity_failures"] == ["JATS_DIRECT_PMID_MISMATCH", "JATS_DIRECT_DOI_MISMATCH"]
    assert result["per_identifier_states"]["pmcid"] == "JATS_PRIMARY_PMCID_MATCH"
    raw = s.synthetic_xml([("pmc", "456"), ("pmid", "999"), ("doi", "10.fixture/other")]).encode()
    result = v2.validate_jats_primary_identity_v2(raw, **s.EXPECTED)
    assert result["identity_failures"] == ["JATS_PRIMARY_PMCID_MISMATCH", "JATS_DIRECT_PMID_MISMATCH", "JATS_DIRECT_DOI_MISMATCH"]


def test_new_doi_not_expected_requires_bound_pmcid_for_authoritative_exposure():
    assert result_for("doi_new_assertion")["authoritative_new_doi_assertion"] == "10.fixture/expected"
    assert result_for("doi_new_cannot_rescue_pmcid")["authoritative_new_doi_assertion"] is None
    assert result_for("missing_both_secondary")["missing_secondary_assertions_are_identity_evidence"] is False


def test_direct_chain_never_searches_reference_related_supplement_or_updateof_ids():
    result = result_for("related_supplement_updateof_ids_ignored")
    assert len(result["direct_identifiers"]["assertions"]) == 3
    assert result["direct_identifiers"]["reference_or_related_identifiers_scanned"] is False
    assert result_for("nested_article_id_not_direct")["identity_state"] == "JATS_PRIMARY_PMCID_MISSING"


def test_multiple_direct_metadata_chains_do_not_pick_first_match():
    raw = b'<article><front><article-meta><article-id pub-id-type="pmc">123</article-id></article-meta><article-meta><article-id pub-id-type="pmcid">456</article-id></article-meta></front></article>'
    result = v2.validate_jats_primary_identity_v2(raw, **s.EXPECTED)
    assert result["identity_state"] == v2.CONFLICT
    assert [r["article_meta_ordinal"] for r in result["direct_identifiers"]["assertions"]] == [1, 2]


def test_no_license_body_or_updateof_rescue_or_content_dependency():
    bad = s.synthetic_xml([("pmc", "123"), ("pmid", "999")])
    adorned = bad.replace("<body/>", '<body><p>ANY SCIENTIFIC CONTENT</p></body>').replace("</article-meta>",
        '<permissions><license href="https://creativecommons.org/licenses/by/4.0/"/></permissions><related-article related-article-type="UpdateOf"/></article-meta>')
    left = v2.validate_jats_primary_identity_v2(bad.encode(), **s.EXPECTED)
    right = v2.validate_jats_primary_identity_v2(adorned.encode(), **s.EXPECTED)
    assert left == right
    assert right["source_identity_allows_progression"] is False
    assert right["scientific_content_used"] is False


def test_no_new_identifier_type_alias_or_numeric_fuzzy_equivalence():
    assert v2.TYPE_MAP == {"pmc": "pmcid", "pmcid": "pmcid", "pmid": "pmid", "doi": "doi"}
    assert result_for("no_numeric_closeness")["identity_state"] == "JATS_DIRECT_PMID_MISMATCH"
    raw = s.synthetic_xml([("pmc", "0123")]).encode()
    assert v2.validate_jats_primary_identity_v2(raw, **s.EXPECTED)["identity_state"] == "JATS_PRIMARY_PMCID_MISMATCH"
    assert v2.normalize_identifier is s.d.c2.v2.normalize_identifier


@pytest.mark.parametrize("override", [{"expected_pmid": None}, {"expected_pmid": ""}, {"expected_pmid": "abc"},
    {"expected_pmid": 123}, {"expected_pmcid": None}, {"expected_pmcid": "PMCunknown"},
    {"expected_doi": "doi:"}, {"expected_doi": ""}])
def test_unresolved_immutable_expected_identity_aborts_without_response_repair(override):
    with pytest.raises(ValueError, match="CONTROLLER_EXPECTED_PRIMARY_IDENTITY_INVALID"):
        v2.validate_jats_primary_identity_v2(s.synthetic_xml([("pmc", "123")]).encode(), **{**s.EXPECTED, **override})


def test_legacy_gap_probes_accept_unchanged_while_new_validator_rejects():
    before = s.d.implementation(s.d.d19.frozen_rules.canonical_jats, "test")
    for probe in s.d.identity_gap_probe():
        assert probe["historical_canonicalizer_accepts"] is True
        assert v2.validate_jats_primary_identity_v2(probe["synthetic_xml"].encode(), **s.EXPECTED)["source_identity_allows_progression"] is False
    assert before == s.d.implementation(s.d.d19.frozen_rules.canonical_jats, "test")


def test_complete_offline_freeze_preserves_original_roots_inputs_requests_and_blindness(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("REQUEST_REGENERATION_OR_DOWNSTREAM_PROCESSING_FORBIDDEN")
    monkeypatch.setattr(s.d, "requests_for", prohibited)
    monkeypatch.setattr(s.d, "run", prohibited)
    monkeypatch.setattr(s.d.body_only, "canonical_body", prohibited)
    monkeypatch.setattr(s.d.d19.source_policy, "build_construction_document", prohibited)
    original_open = Path.open

    def no_xml_read(path, *args, **kwargs):
        historical_hash_inputs = (s.d.d19.OUT, s.d.d19_1.OUT, s.d.C2)
        if path.suffix.lower() in (".xml", ".jats") and not any(path.is_relative_to(p) for p in historical_hash_inputs):
            raise AssertionError("FRESH_PRIMARY_XML_OBSERVATION_FORBIDDEN")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", no_xml_read)
    upstream = [(s.d.OUT, s.d.ROOT_MARKER), (s.d.C2, s.d.c2.ROOT_MARKER), (s.d.MASTER, s.MASTER_MARKER),
        (s.d.d19.OUT, s.d.d19.ROOT_MARKER), (s.d.d19_1.OUT, s.d.d19_1.ROOT_MARKER)]
    before = [s.root_hash(p, marker) for p, marker in upstream]
    frozen_bytes = [s.INPUT.read_bytes(), s.REQUESTS.read_bytes()]
    with TemporaryDirectory(prefix="alpha321d1_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = s.run()
        assert result["status"] == "completed"
        assert result["alpha3_21d1_classification"] == s.CLASS_OK
        assert result["pmc_end_to_end_execution_authority_resolved"] is True
        assert result["pre_oa_input_source_count"] == 49
        assert result["pre_oa_clear_source_count"] == 46
        assert result["pre_oa_deferred_source_count"] == 3
        assert all(result[k] == 0 for k in s.NO_CALLS)
        assert s.obj(s.OUT / "alpha3_21d2_execution_handoff.json")["network_authorized"] is False
        assert all((s.OUT / name).is_file() for name in s.REQUIRED)
        assert s.root_hash(s.OUT, s.ROOT_MARKER) == result[s.ROOT_MARKER]
        assert not any(p.suffix in (".jsonl", ".xml") for p in s.OUT.iterdir())
        assert not any(p.is_symlink() for p in s.OUT.rglob("*"))
        assert s.digest(s.OUT / "jats_primary_source_identity_contract_v2.json") == result["jats_primary_source_identity_contract_v2_sha256"]
        assert s.digest(s.OUT / "alpha321_pmc_jats_execution_authority_v2.json") == result["alpha321_pmc_jats_execution_authority_v2_sha256"]
        with pytest.raises(Exception, match="NO_OVERWRITE"):
            s.run()
    assert [s.root_hash(p, marker) for p, marker in upstream] == before
    assert [s.INPUT.read_bytes(), s.REQUESTS.read_bytes()] == frozen_bytes


def test_wrong_root_fails_closed_before_any_output_or_fixture_processing(monkeypatch):
    monkeypatch.setattr(s, "D_SHA", "0" * 64)
    with TemporaryDirectory(prefix="alpha321d1_bad_root_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        with pytest.raises(Exception, match="D_ROOT_MISMATCH"):
            s.run()
        assert not s.OUT.exists()
