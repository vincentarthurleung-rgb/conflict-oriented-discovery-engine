"""Offline direction, precedence, provenance, and freeze checks for alpha3.18A.3."""

import json

import pytest

from scripts import search_plan_v24_alpha318a3_correction_reference as rule
from scripts import search_plan_v24_alpha318a3_finalize_source_prereg_offline as freeze


@pytest.mark.parametrize("case", freeze.cases(), ids=lambda row: row["case_id"])
def test_synthetic_case(case):
    result = rule.classify(case["publication_types"], case["relationships"],
                           case["independent_primary_state"])
    assert result["state"] == case["expected_state"]
    assert result["state"] in rule.STATES


def test_direction_not_collapsed_and_all_reasons_preserved():
    result = rule.classify(["Journal Article", "Retracted Publication"], [
        {"ref_type": "RetractionIn", "linked_pmid": None, "ref_source": "Private citation"},
        {"ref_type": "ErratumIn", "linked_pmid": "123", "ref_source": None},
    ])
    assert result["state"] == "CORRECTION_REFERENCE_INELIGIBLE"
    assert len(result["ineligible_reasons"]) == 2
    assert result["unresolved_reasons"] == ["REF_TYPE:ErratumIn"]
    assert rule.classify(["Journal Article"], [
        {"ref_type": "RetractionOf", "linked_pmid": "123", "ref_source": None}
    ])["state"] == "CORRECTION_REFERENCE_INELIGIBLE"


def test_pubmed_xml_extraction_keeps_linked_identity_private():
    raw = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation>
    <Article><PublicationTypeList><PublicationType>Journal Article</PublicationType>
    </PublicationTypeList></Article><CommentsCorrectionsList>
    <CommentsCorrections RefType="RetractionIn"><RefSource>Private journal citation</RefSource>
    </CommentsCorrections></CommentsCorrectionsList></MedlineCitation></PubmedArticle></PubmedArticleSet>'''
    extracted = rule.parse_pubmed_relationships(raw)
    assert extracted["publication_types"] == ["Journal Article"]
    assert extracted["relationships"] == [{"ref_type": "RetractionIn", "linked_pmid": None,
                                          "ref_source": "Private journal citation"}]
    assert rule.classify(**extracted)["state"] == "CORRECTION_REFERENCE_INELIGIBLE"


def test_frozen_roots_and_manifest_bindings():
    freeze.verify()
    root = freeze.prior.all_file_root(freeze.OUT, "search_plan_v24_dev_alpha3_18a3_prereg_sha256")
    assert root == (freeze.OUT / "search_plan_v24_dev_alpha3_18a3_prereg_sha256").read_text().strip()
    manifest_file = freeze.OUT / "alpha3_18a3_source_acquisition_execution_manifest.json"
    manifest = json.loads(manifest_file.read_text())
    assert freeze.prior.sha(manifest_file.read_bytes()) == (
        freeze.OUT / "alpha3_18a3_source_acquisition_execution_manifest_sha256").read_text().strip()
    assert manifest["material_runtime_policy_unresolved_count"] == 0
    assert manifest["network_calls_in_this_preregistration"] == 0
    assert manifest["builder_visibility"]["prospective_amendment"]["path"].endswith(
        "builder_request_visibility_amendment.json")
    assert len(manifest["queries"]) == 6
