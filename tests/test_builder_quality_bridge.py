"""Bridge safety tests; real integration uses frozen Pilot data, never inference."""
import copy
import hashlib
import json
import socket
from pathlib import Path

import pytest

from code_engine.construction.builder_quality_bridge import (
    normalize_reviewable_builder_claims, project_quality_accepted_builder_claims,
)
from code_engine.evidence_graph.builders import normalize_observation_to_evidence_edge
from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.hub import EntityResolutionHub
from code_engine.normalization.providers.local_cache import LocalCacheProvider
from code_engine.normalization.providers.null import NullProvider
from code_engine.normalization.resolver import ResolverCascade
from code_engine.schemas.l1_extraction import L1ExtractedClaim
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import private_identity_from_jats

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("NO_NETWORK_IN_BRIDGE_TEST")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.fixture
def inputs():
    def load(name, file):
        return json.loads((ROOT / "runs" / name / file).read_bytes())
    source = load("20261012_code_minimal_immutable_handoff_to_construction_adapter_offline", "source_manifest.json")
    bm = load("20261012_code_pilot_bound_builder_v4_request_freeze_offline", "builder_request_manifest.json")
    qm = load("20261012_code_pilot_bound_quality_v2_request_freeze_offline", "quality_request_manifest.json")
    br = (ROOT / "runs/20261012_code_first_pilot_bound_builder_v4_development_execution/provider_response.json").read_bytes()
    qr = (ROOT / "runs/20261013_code_pilot_bound_quality_v2_development_execution/provider_response.json").read_bytes()
    envelope = source["verified_construction_input"]
    identity = source["opaque_source_token_authority"]["binding"]
    jats = Path(envelope["controller_private_provenance"]["normalized_jats_reference"]["artifact_path"]).read_bytes()
    return dict(document=envelope["construction_document"], private_source_token=source["opaque_source_token_authority"]["opaque_source_token"],
                source_identity=identity, private_identity=private_identity_from_jats(jats, identity["pmid"], identity["pmcid"], identity["doi"]),
                builder_request_manifest=bm, builder_response_raw=br, builder_response_sha256=hashlib.sha256(br).hexdigest(),
                quality_request_manifest=qm, quality_response_raw=qr, quality_response_sha256=hashlib.sha256(qr).hexdigest())


def test_authentic_claims_keep_identity_context_wording_and_offsets(inputs):
    before = copy.deepcopy(inputs)
    result = project_quality_accepted_builder_claims(**inputs)
    assert len(result["claims"]) == 3 and result["experimental_observations_created"] == 0
    assert inputs == before
    original = json.loads(json.loads(inputs["builder_response_raw"])["choices"][0]["message"]["content"])["candidates"]
    for claim, candidate in zip(result["claims"], original):
        L1ExtractedClaim.model_validate(claim)
        assert claim["neutral_proposition"] == candidate["neutral_proposition"]
        assert claim["builder_candidate"] == candidate
        assert claim["claim_id"] == claim["candidate_id"] == claim["quality_candidate_id"]
        span = claim["evidence_span"]
        assert inputs["document"]["body_text"][span["start_offset"]:span["end_offset"]] == span["exact_text"]
        assert claim["context"]["intrinsic_conditioning"] == candidate["intrinsic_conditioning"]
        assert claim["subject_type"] == claim["object_type"] == "unknown"
        assert claim["statement_type"] == claim["evidence_type"] == "unknown"
        assert claim["direct_relation_sign"] == "unknown"
        assert claim["source_bindings"]["construction_document_sha256"] == inputs["builder_request_manifest"]["construction_document_sha256"]
        assert inputs["private_source_token"] not in json.dumps(claim)


def test_real_normalization_and_graph_admission_do_not_promote_claims(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    normalized = normalize_reviewable_builder_claims(claims)
    assert len(normalized) == 3
    assert sum(r["lexical_relation_status"] == "registered" for r in normalized) == 2
    for r in normalized:
        assert r["observation_id"] is None and r["experimental_observation_verified"] is False
        assert r["subject_canonical_id"] is r["object_canonical_id"] is None
        assert r["core_gate_result"]["eligible"] is False
        assert r["conflict_reasoning_eligible"] is False
        assert r["derived_causal_sign"] is None
        assert r["normalization"]["subject"]["entity_resolution_status"] == "unresolved"
    edges = [normalize_observation_to_evidence_edge(r, {}, {"run_id": "TEST_ONLY", "topic_id": None, "query_id": None}) for r in normalized]
    assert len(edges) == 3 and build_relation_evidence_bundles(edges) == []
    assert all(e.observation_id is None and e.claim_id and not e.subject_canonical_id and not e.export_ready for e in edges)


def test_exact_duplicates_collapse_but_identity_conflicts_fail(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    assert len(normalize_reviewable_builder_claims(claims + copy.deepcopy(claims))) == 3
    changed = copy.deepcopy(claims[0]); changed["neutral_proposition"] += "CHANGED"
    with pytest.raises(ValueError, match="DUPLICATE_CLAIM_ID_CONFLICT"):
        normalize_reviewable_builder_claims(claims + [changed])


@pytest.mark.parametrize("field", ["builder_response_sha256", "quality_response_sha256"])
def test_wrong_response_binding_rejected(inputs, field):
    inputs[field] = "0" * 64
    with pytest.raises(ValueError, match="RESPONSE_HASH_MISMATCH"):
        project_quality_accepted_builder_claims(**inputs)


def test_wrong_document_and_wrong_source_rejected(inputs):
    changed = copy.deepcopy(inputs); changed["document"]["abstract_text"] += "CHANGED"
    with pytest.raises(ValueError, match="DOCUMENT_HASH_MISMATCH"):
        project_quality_accepted_builder_claims(**changed)
    changed = copy.deepcopy(inputs); changed["source_identity"]["pmid"] = "1"
    with pytest.raises(ValueError, match="PRIVATE_SOURCE_IDENTITY_MISMATCH"):
        project_quality_accepted_builder_claims(**changed)


def test_quality_packet_tampering_rejected(inputs):
    inputs["quality_request_manifest"]["quality_payload"]["candidate_packets"][0]["neutral_proposition"] += "CHANGED"
    with pytest.raises(ValueError, match="QUALITY_INPUT_CANDIDATE_OR_EVIDENCE_MISMATCH"):
        project_quality_accepted_builder_claims(**inputs)


def test_duplicate_json_key_rejected_before_any_projection(inputs):
    inputs["quality_response_raw"] = b'{"model":"a","model":"b"}'
    inputs["quality_response_sha256"] = hashlib.sha256(inputs["quality_response_raw"]).hexdigest()
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        project_quality_accepted_builder_claims(**inputs)


def test_nonaccepted_quality_candidate_does_not_enter_normalization(inputs):
    response = json.loads(inputs["quality_response_raw"])
    content = json.loads(response["choices"][0]["message"]["content"])
    item = content["judgments"][0]
    item["criteria"]["SCIENTIFICALLY_COHERENT"] = "UNRESOLVED"
    response["choices"][0]["message"]["content"] = json.dumps(content)
    raw = json.dumps(response).encode(); inputs["quality_response_raw"] = raw
    inputs["quality_response_sha256"] = hashlib.sha256(raw).hexdigest()
    result = project_quality_accepted_builder_claims(**inputs)
    assert len(result["claims"]) == 2
    assert item["candidate_id"] in result["quality_not_accepted_ids"]
    assert item["candidate_id"] not in {c["claim_id"] for c in result["claims"]}


def test_ambiguous_local_candidates_remain_ambiguous_without_authority(inputs, tmp_path):
    # Synthetic cache records are test fixtures only, never real-run evidence.
    claims = project_quality_accepted_builder_claims(**inputs)["claims"][:1]
    from code_engine.normalization.lexical import normalize_lexical_surface
    surface = claims[0]["subject_raw"]
    records = [{"normalized_surface": normalize_lexical_surface(surface).normalized_surface,
                "canonical_id": f"TEST_ONLY:{n}", "canonical_name": f"Fixture {n}", "entity_type": "unknown",
                "semantic_level": "unknown", "source": "test_fixture", "provider_name": "LocalCacheProvider"} for n in (1, 2)]
    (tmp_path / "accepted_mappings.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    resolver = ResolverCascade(hub=EntityResolutionHub([LocalCacheProvider(EntityCache(tmp_path)), NullProvider()]))
    result = normalize_reviewable_builder_claims(claims, resolver)[0]
    assert result["normalization"]["subject"]["candidate_count"] == 2
    assert result["normalization"]["subject"]["entity_resolution_status"] in {"ambiguous", "ambiguous_external_candidate", "manual_review_required"}
    assert not result["subject_canonical_id"] and result["conflict_reasoning_eligible"] is False


def test_online_or_mutating_resolver_rejected(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    resolver = ResolverCascade(execute=True, external_clients={})
    with pytest.raises(ValueError, match="OFFLINE_RESOLVER_REQUIRED"):
        normalize_reviewable_builder_claims(claims, resolver)


def test_schema_does_not_accept_unbound_observation_upgrade(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    claims[0]["experimental_observation_verified"] = True
    with pytest.raises(ValueError, match="REVIEWABLE_CLAIM_REQUIRED"):
        normalize_reviewable_builder_claims(claims)


def test_quality_array_order_does_not_change_candidate_binding(inputs):
    baseline = project_quality_accepted_builder_claims(**inputs)["claims"]
    response = json.loads(inputs["quality_response_raw"])
    content = json.loads(response["choices"][0]["message"]["content"])
    content["judgments"].reverse()
    response["choices"][0]["message"]["content"] = json.dumps(content)
    raw = json.dumps(response).encode(); inputs["quality_response_raw"] = raw
    inputs["quality_response_sha256"] = hashlib.sha256(raw).hexdigest()
    reordered = project_quality_accepted_builder_claims(**inputs)["claims"]
    assert [r["claim_id"] for r in reordered] == [r["claim_id"] for r in baseline]
    assert [r["neutral_proposition"] for r in reordered] == [r["neutral_proposition"] for r in baseline]


def test_duplicate_quality_identity_rejected(inputs):
    response = json.loads(inputs["quality_response_raw"])
    content = json.loads(response["choices"][0]["message"]["content"])
    content["judgments"][1] = copy.deepcopy(content["judgments"][0])
    response["choices"][0]["message"]["content"] = json.dumps(content)
    raw = json.dumps(response).encode(); inputs["quality_response_raw"] = raw
    inputs["quality_response_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="extra or duplicate candidate"):
        project_quality_accepted_builder_claims(**inputs)


def test_requires_stays_unresolved_and_deletion_sign_is_not_inverted(inputs):
    normalized = normalize_reviewable_builder_claims(project_quality_accepted_builder_claims(**inputs)["claims"])
    assert normalized[0]["relation_raw"] == "DECREASES"
    assert normalized[0]["lexical_relation_projection"]["sign"] == -1
    assert "conditional deletion" in normalized[0]["subject_raw"]
    assert normalized[0]["derived_causal_sign"] is None
    assert normalized[1]["relation_raw"] == "REQUIRES"
    assert normalized[1]["lexical_relation_projection"] is None


def test_injected_core_flags_and_ids_cannot_create_formal_authority(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    claims[0].update(subject_canonical_id="TEST_ONLY:injected", canonical_graph_eligible=True,
                     conflict_reasoning_eligible=True, derived_causal_sign=1,
                     evidence_semantics={"retained_layer": "strict_causal_core"})
    result = normalize_reviewable_builder_claims(claims)[0]
    assert result["subject_canonical_id"] is None
    assert result["derived_causal_sign"] is None
    assert not result["canonical_graph_eligible"] and not result["conflict_reasoning_eligible"]
