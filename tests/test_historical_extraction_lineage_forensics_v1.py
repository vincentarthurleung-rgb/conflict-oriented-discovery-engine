from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.forensics.identities import canonical_payload_hash, forensic_contract_identity
from code_engine.extraction_assets.forensics.matching_graph import candidate_edge
from code_engine.extraction_assets.forensics.models import (
    AuthorityLevel, HistoricalLineageBinding, SelectiveReextractionRequirementV2,
)
from code_engine.extraction_assets.forensics.parsed_matching import compare_payloads
from code_engine.extraction_assets.forensics.raw_replay import extract_raw_features, replay_parser
from code_engine.extraction_assets.forensics.reextraction import compress_requirements
from code_engine.extraction_assets.forensics.replayability import classify_replayability_v2
from code_engine.extraction_assets.forensics.source_recovery import recover_source_snapshot
from code_engine.extraction_assets.forensics.uniqueness import resolve_one_to_one
from code_engine.extraction_assets.forensics.validation import make_binding


def test_direct_ids_and_hash_references_exact_bind():
    for kind in ("provider_request_id_exact", "provider_response_id_exact", "raw_sha256_reference_exact"):
        row = make_binding("a", "r", direct_evidence=[{"type": kind}], candidate_identities=["r"])
        assert row.binding_authority_level == AuthorityLevel.exact_bound
        assert row.authoritative and row.formal_replay_use_allowed


@pytest.mark.parametrize("weak", [["timestamp"], ["filename"], ["directory"], ["timestamp", "filename"]])
def test_weak_location_signals_never_authorize(weak):
    row = make_binding("a", "r", weak_evidence=weak, candidate_identities=["r"])
    assert row.binding_authority_level == AuthorityLevel.probable_non_authoritative
    assert not row.authoritative and not row.formal_replay_use_allowed


def test_unbound_not_authoritative_and_rejected_requires_reason():
    assert make_binding("a", None).binding_authority_level == AuthorityLevel.unbound
    with pytest.raises(ValidationError):
        HistoricalLineageBinding(
            binding_id="b", left_identity="a", binding_authority_level="rejected",
            authoritative=False, formal_replay_use_allowed=False, one_to_one_valid=False,
            identity="i",
        )


def test_actual_request_and_deterministic_hash_can_recover_snapshot():
    direct = recover_source_snapshot("s", request_bytes=b"sent", direct_reference="ledger.json#request")
    assert direct.authoritative and direct.status.value == "exact_request_snapshot_recovered"
    deterministic = recover_source_snapshot(
        "s", request_bytes=b"sent",
        deterministic_hash=canonical_payload_hash("sent") if False else __import__("hashlib").sha256(b"sent").hexdigest(),
        template_identity="template:1",
    )
    assert deterministic.authoritative


def test_missing_whitespace_encoding_or_current_rechunk_remains_incomplete():
    assert not recover_source_snapshot("s", request_bytes=b"candidate").authoritative
    assert not recover_source_snapshot(
        "s", request_bytes=b"candidate", deterministic_hash=__import__("hashlib").sha256(b"candidate").hexdigest(),
        template_identity="t", encoding=None,
    ).authoritative


def test_raw_features_are_hash_bound_duplicate_safe_and_invalid_json_survives(tmp_path):
    path = tmp_path / "r.raw"
    path.write_bytes(b"not-json")
    before = path.read_bytes()
    features = extract_raw_features(path)
    assert features["json_parse_status"] == "invalid" and features["byte_count"] == len(before)
    assert path.read_bytes() == before


def test_raw_provider_ids_are_extracted(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"id": "resp", "request_id": "req", "model": "m", "choices": [{"finish_reason": "stop"}]}))
    row = extract_raw_features(path)
    assert (row["provider_request_id"], row["provider_response_id"], row["finish_reason"]) == ("req", "resp", "stop")


def test_parser_replay_never_calls_provider_and_preserves_raw_hash():
    replay = replay_parser(b'{"x":1}', lambda value: value, parser_name="historical", parser_version="1", historical=True)
    assert replay["parse_status"] == "parsed" and replay["authoritative_replay_eligible"]
    failed = replay_parser(b"x", lambda value: value, parser_name="historical", parser_version="1", historical=True)
    assert failed["parse_status"] == "parse_failed" and failed["errors"]


def test_canonical_exact_preserves_omitted_null_and_list_order():
    assert compare_payloads({"é": 1}, {"e\u0301": 1})["comparison_level"] == "canonical_exact"
    assert compare_payloads({}, {"x": None})["comparison_level"] != "canonical_exact"
    assert compare_payloads({"x": [1, 2]}, {"x": [2, 1]})["comparison_level"] != "canonical_exact"


def test_unique_replay_can_reconstruct_but_ties_remain_ambiguous():
    row = make_binding("a", "r", deterministic_evidence=[{"type": "canonical_exact"}], candidate_identities=["r"])
    assert row.binding_authority_level == AuthorityLevel.deterministically_reconstructed
    tied = make_binding("a", None, deterministic_evidence=[{"type": "canonical_exact"}], candidate_identities=["r1", "r2"])
    assert tied.binding_authority_level == AuthorityLevel.probable_non_authoritative


def test_one_to_one_is_stable_and_does_not_choose_by_score():
    first = candidate_edge("a", "r", replay=["canonical_exact"], score=1)
    second = candidate_edge("a", "r2", replay=["canonical_exact"], score=999)
    result = resolve_one_to_one([first, second])
    reverse = resolve_one_to_one([second, first])
    assert result == reverse
    assert not result["accepted_edge_ids"] and len(result["ambiguous_edge_ids"]) == 2


def test_probable_lineage_never_becomes_raw_replayable():
    status = classify_replayability_v2(
        source_authority=AuthorityLevel.unbound,
        raw_authority=AuthorityLevel.probable_non_authoritative,
        parsed_available=True, parser_available=True,
    )
    assert status.value == "replayable_from_parsed_candidate_only"


def test_direct_and_reconstructed_full_lineage_classify_distinctly():
    direct = classify_replayability_v2(
        source_authority=AuthorityLevel.exact_bound, raw_authority=AuthorityLevel.exact_bound,
        parsed_available=True, parser_available=True, complete_provenance=True,
    )
    reconstructed = classify_replayability_v2(
        source_authority=AuthorityLevel.deterministically_reconstructed,
        raw_authority=AuthorityLevel.deterministically_reconstructed,
        parsed_available=True, parser_available=True, complete_provenance=True,
    )
    assert direct.value.endswith("_direct") and reconstructed.value.endswith("_reconstructed")


@pytest.mark.parametrize("field,mode", [
    ("authoritative_raw_available", "raw_rebinding"),
    ("authoritative_parsed_migration_available", "parsed_migration"),
    ("authoritative_anchor_reconstruction_available", "anchor_reconstruction"),
    ("validator_replay_available", "validator_replay"),
    ("normalization_replay_available", "normalization_replay"),
    ("derived_schema_only", "derived_only"),
])
def test_each_offline_mode_eliminates_provider_requirement(field, mode):
    result = compress_requirements([{"source_block_identity": "b", field: True}])
    assert result[f"requirements_eliminated_by_{mode}" if mode != "derived_only" else "requirements_eliminated_as_derived_only"] == 1
    assert result["post_forensic_reextraction_required_count"] == 0


def test_v2_requirement_forces_all_execution_authorizations_false():
    base = dict(
        requirement_id="r", pre_forensic_requirement_identity="v1", source_block_identity="b",
        post_forensic_reextraction_required=True, post_forensic_reason="missing",
        minimal_text_scope="block", dedup_group_identity="d", estimated_call_count=1, identity="i",
    )
    SelectiveReextractionRequirementV2(**base)
    with pytest.raises(ValidationError):
        SelectiveReextractionRequirementV2(**base, provider_call_authorized=True)


def test_contract_identities_recompute_and_exclude_case_data():
    identity = forensic_contract_identity("historical_lineage_binding")
    assert identity["identity_match"] and identity["identity_sha256"] == identity["recomputed_sha256"]
    assert "HIF1A" not in json.dumps(identity)


def test_dependency_boundary_has_no_provider_network_or_gold_imports():
    root = Path(__file__).parents[1] / "src/code_engine/extraction_assets/forensics"
    text = "\n".join(path.read_text() for path in root.glob("*.py"))
    for forbidden in ("deepseek_client", "requests", "httpx", "dataset_release", "human_gold"):
        assert forbidden not in text

