"""Offline tests for prospective PMC OA, source-type and JATS contracts."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.search_plan_v24_alpha318a1_source_contracts import (
    LOCAL_PUBLICATION_TYPES, build_construction_document, construction_oa_state,
    license_class_from_url, oa_subset_esearch_term, resolve_candidate_span,
    source_type_state,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
UP = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
TOKEN = "src_" + "a" * 64
JATS = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta><title-group><article-title>Secret Article Title</article-title></title-group>
<abstract><p>Context about A and B.</p></abstract>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">
<license-p>Creative Commons Attribution license.</license-p></license></permissions></article-meta></front>
<body><sec><title>1. Materials and Methods</title><p>We perturbed A
<xref ref-type="bibr" rid="r1">[1]</xref> and measured B.</p></sec>
<sec><title>2. Results</title><p>A increased B.</p>
<sec><title>Additional observations</title><p>B remained elevated.</p></sec></sec></body>
<back><ref-list><ref><mixed-citation>Private cited work PMID 12345678</mixed-citation></ref></ref-list></back>
</article>'''


def _load(name: str):
    return json.loads((RUN / name).read_text())


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def test_oa_subset_route_and_license_three_state() -> None:
    assert oa_subset_esearch_term("PMC12345") == "12345[UID] AND open access[filter]"
    with pytest.raises(ValueError):
        oa_subset_esearch_term("12345")
    assert license_class_from_url("https://creativecommons.org/licenses/by/4.0/") == "CC_BY"
    assert license_class_from_url("https://creativecommons.org/licenses/by-nc/4.0/") == "EXPLICIT_NONWHITELIST_CC"
    assert construction_oa_state("PMC12345", True, JATS)["state"] == "CONSTRUCTION_OA_ELIGIBLE"
    assert construction_oa_state("PMC12345", False, None)["state"] == "CONSTRUCTION_OA_INELIGIBLE"
    assert construction_oa_state("PMC12345", None, JATS)["state"] == "CONSTRUCTION_OA_UNRESOLVED"
    assert construction_oa_state(None, True, JATS)["state"] == "CONSTRUCTION_OA_UNRESOLVED"


def test_source_type_is_mechanical_and_conservative() -> None:
    good = source_type_state(["Journal Article"], JATS)
    assert good["state"] == "SOURCE_TYPE_ELIGIBLE"
    assert good["methods_paths"] == [[1]]
    assert good["results_paths"] == [[2]]
    assert source_type_state(["Review", "Journal Article"], JATS)["state"] == "SOURCE_TYPE_INELIGIBLE"
    assert source_type_state(["Journal Article", "Unseen Type"], JATS)["state"] == "SOURCE_TYPE_UNRESOLVED"
    assert source_type_state(["Journal Article"], None)["state"] == "SOURCE_TYPE_UNRESOLVED"
    assert set(_load("pubmed_publication_type_authority.json")["observed_exact_strings"]) == LOCAL_PUBLICATION_TYPES


def test_canonical_document_excludes_front_back_and_maps_body_span() -> None:
    document = build_construction_document(JATS, TOKEN)
    assert document["schema_version"] == "ConstructionEvidenceDocumentV1"
    assert "Secret Article Title" not in json.dumps(document)
    assert "Private cited work" not in json.dumps(document)
    assert "[1]" not in document["body_text"]
    assert "We perturbed A and measured B." in document["body_text"]
    assert len(document["paragraphs"]) == 3
    start = document["body_text"].index("A increased B.")
    anchor = resolve_candidate_span(document, "body", start, start + len("A increased B."), "A increased B.")
    assert anchor.startswith("spanv1_")
    assert anchor == build_construction_document(JATS, TOKEN)["paragraphs"][1]["span_id"]
    with pytest.raises(ValueError):
        resolve_candidate_span(document, "abstract", start, start + 1, "A")


def test_frozen_contract_hashes_and_query_immutability() -> None:
    query_audit = _load("source_query_immutability_audit.json")
    assert query_audit["query_changes"] == 0
    assert query_audit["source_query_file_sha256"] == _sha((UP / "exact_source_queries.jsonl").read_bytes())
    summary = _load("summary.json")
    assert summary["status"] == "completed"
    for marker in ("construction_oa_eligibility_v1_sha256", "source_type_mechanical_eligibility_v1_sha256",
                   "construction_evidence_document_v1_sha256", "evidence_span_anchor_v1_sha256"):
        assert summary[marker] == (RUN / marker).read_text().strip()
    names = sorted(p.name for p in RUN.iterdir() if p.is_file() and p.name != "search_plan_v24_dev_alpha3_18a1_sha256")
    pairs = [[name, _sha((RUN / name).read_bytes())] for name in names]
    root = _sha(json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())
    assert root == (RUN / "search_plan_v24_dev_alpha3_18a1_sha256").read_text().strip()
    safety = _load("scientific_state_safety_audit.json")
    assert all(safety[key] == 0 for key in ("network_calls", "retrieval_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls"))
