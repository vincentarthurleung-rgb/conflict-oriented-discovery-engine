#!/usr/bin/env python3
"""Real SEEN-data bridge acceptance; no requests, discovery, or inference."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
sys.dont_write_bytecode = True

from code_engine.construction import handoff_adapter
from code_engine.construction.builder_quality_bridge import (
    normalize_reviewable_builder_claims, project_quality_accepted_builder_claims,
)
from code_engine.evidence_graph.builders import normalize_observation_to_evidence_edge
from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityResolutionRequest
from code_engine.normalization.composite_endpoints import decompose_endpoint
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.providers.local_cache import LocalCacheProvider
from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH
from code_engine.normalization.resolver import ResolverCascade
from scripts.run_code_post_pilot_handoff_to_construction_adapter_offline import CONFIG
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import private_identity_from_jats

OUT = ROOT / "runs/20261013_code_builder_to_conflict_integration_offline"
MARKER = "code_builder_to_conflict_integration_sha256"
BASE = ROOT / "runs/20261013_code_first_full_pipeline_seen_development_offline"
BASE_MARKER = "code_first_full_pipeline_seen_development_sha256"
BASE_SHA = "989fc119c6f1607e4e189dbe3035f8cede6f9f9165f2829b3804abcd986c430b"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load(path):
    return json.loads(path.read_bytes())


def ref(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def put(name, value):
    with (OUT / name).open("xb") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n")
        handle.flush(); os.fsync(handle.fileno())
    (OUT / name).chmod(0o600)


def main():
    started = time.perf_counter()
    assert not OUT.exists(), "NO_OVERWRITE_RESULT"
    denied = []
    def deny(*args, **kwargs):
        denied.append("OFFLINE_DISPATCH_DENIED")
        raise RuntimeError(denied[-1])
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    assert handoff_adapter.root_hash(BASE, BASE_MARKER) == (BASE / BASE_MARKER).read_text().strip() == BASE_SHA
    protected = load(BASE / "provenance_and_execution.json")["protected_roots_before_after"]
    for row in protected:
        assert handoff_adapter.root_hash(ROOT / row["path"], row["marker"]) == row["sha256"]
    adapter_dir = ROOT / "runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline"
    builder_freeze = ROOT / "runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline"
    builder_exec = ROOT / "runs/20261012_code_first_pilot_bound_builder_v4_development_execution"
    quality_freeze = ROOT / "runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline"
    quality_exec = ROOT / "runs/20261013_code_pilot_bound_quality_v2_development_execution"
    source = load(adapter_dir / "source_manifest.json")
    authority = source["opaque_source_token_authority"]
    envelope = handoff_adapter.adapt_verified_handoff(CONFIG, authority)
    assert envelope == source["verified_construction_input"]
    jats_path = Path(envelope["controller_private_provenance"]["normalized_jats_reference"]["artifact_path"])
    identity = authority["binding"]
    private = private_identity_from_jats(jats_path.read_bytes(), identity["pmid"], identity["pmcid"], identity["doi"])
    bm = load(builder_freeze / "builder_request_manifest.json")
    qm = load(quality_freeze / "quality_request_manifest.json")
    be = load(builder_exec / "execution_manifest.json")
    qe = load(quality_exec / "execution_manifest.json")
    cache_path = ROOT / "data/index/entity_cache/accepted_mappings.jsonl"
    registry_path = ROOT / DEFAULT_REGISTRY_PATH
    caches_before = [ref(cache_path), ref(registry_path)]
    registry = load(registry_path)
    assert registry["registry_status"] == "domain_neutral_empty" and registry["entities"] == []
    cache = EntityCache(ROOT / "data/index/entity_cache")
    provider = LocalCacheProvider(cache)
    resolver = ResolverCascade(execute=False, network_enabled=False, api_enabled=False,
        entity_network_lookup=False, entity_llm_proposer=False, entity_llm_cleaner=False, external_clients={})
    probe_rows = load(BASE / "evidence_linked_outputs_private.json")["normalization_component_probes"]
    diagnoses = []
    assert len(probe_rows) == 6
    for row in probe_rows:
        raw = row["decision"]["raw_text"]
        request = EntityResolutionRequest(surface=raw)
        candidates = provider.propose(request)
        lexical = normalize_lexical_surface(raw)
        hits = cache.lookup(lexical.normalized_surface)
        assert candidates == hits == [] and provider.last_status == "cache_miss"
        diagnoses.append({"candidate_id": row["candidate_id"], "field": row["input_field"], "raw_text": raw,
            "lexical_surface": lexical.normalized_surface, "exact_cache_hits": len(hits),
            "enabled_provider_classes": [type(p).__name__ for p in resolver.hub.providers],
            "provider_status": provider.last_status, "previous_expected_type": "NOT_SUPPLIED",
            "default_registry_entity_count": len(registry["entities"]),
            "existing_endpoint_decomposition": decompose_endpoint(raw, "unknown").endpoint_decomposition_status,
            "demonstrated_primary_cause": "NO_LOCAL_CANDIDATES_AND_EXTERNAL_GROUNDERS_DISABLED",
            "contract_mismatch": "Builder role description submitted as a complete entity surface; no verified head or type provided by Builder V4.",
            "incorrect_entity_type": "NOT_DEMONSTRATED_NO_CANDIDATE_REACHED_TYPE_SELECTION",
            "legitimate_ambiguity": "NOT_DEMONSTRATED_ZERO_CANDIDATES",
            "biological_concept_unsupported": "NOT_DEMONSTRATED_EXTERNAL_ONTOLOGIES_NOT_QUERIED",
            "external_ontology_coverage": "NOT_EVALUATED"})
    projection = project_quality_accepted_builder_claims(
        document=envelope["construction_document"], private_source_token=authority["opaque_source_token"],
        source_identity=identity, private_identity=private, builder_request_manifest=bm,
        builder_response_raw=(builder_exec / "provider_response.json").read_bytes(), builder_response_sha256=be["provider_response"]["sha256"],
        quality_request_manifest=qm, quality_response_raw=(quality_exec / "provider_response.json").read_bytes(),
        quality_response_sha256=qe["provider_response"]["sha256"])
    claims = projection["claims"]
    normalized = normalize_reviewable_builder_claims(claims, resolver)
    assert len(claims) == len(normalized) == 3
    # Use the existing graph read/projection boundary on real reviewable claims.
    # RUN-scoped node IDs are display identifiers, never canonical entities.
    edges = [normalize_observation_to_evidence_edge(r, {}, {
        "run_id": OUT.name, "topic_id": None, "query_id": None}) for r in normalized]
    bundles = build_relation_evidence_bundles(edges)
    assert len(edges) == 3 and not bundles
    assert all(e.observation_id is None and e.claim_id and not e.subject_canonical_id and not e.object_canonical_id for e in edges)
    original_candidates = {r["candidate_id"]: r for r in load(BASE / "evidence_linked_outputs_private.json")["candidates"] if r["quality_state"] == "QUALITY_PASS"}
    for record in normalized:
        assert record["builder_candidate"] == original_candidates[record["claim_id"]]["candidate"]
        assert record["candidate_id"] == record["claim_id"]
        assert record["source_bindings"]["construction_document_sha256"] == bm["construction_document_sha256"]
        span = record["evidence_span"]
        assert envelope["construction_document"]["body_text"][span["start_offset"]:span["end_offset"]] == record["evidence_quote"]
        assert not record["canonical_graph_eligible"] and not record["conflict_reasoning_eligible"]
    stages = [
        {"stage": "Builder V4 / Quality V2", "status": "VERIFIED_CACHE_REPLAY", "accepted_claim_count": 3},
        {"stage": "source-bound L1 claim projection", "status": "EXECUTED", "input_count": 3, "output_count": 3, "experimental_observation_count": 0},
        {"stage": "entity and lexical relation normalization", "status": "EXECUTED", "role_text_count": 6, "resolved_roles": 0,
         "registered_lexical_relations": sum(r["lexical_relation_status"] == "registered" for r in normalized), "unresolved_lexical_relations": sum(r["lexical_relation_status"] == "unresolved" for r in normalized)},
        {"stage": "existing core eligibility gate", "status": "EXECUTED", "assessed_claim_count": 3, "eligible_count": sum(r["core_gate_result"]["eligible"] for r in normalized)},
        {"stage": "existing evidence-edge projection and relation-bundle admission", "status": "EXECUTED", "reviewable_evidence_edges": 3, "admitted_relation_bundles": 0},
        {"stage": "scientific cross-paper comparability", "status": "NO_ELIGIBLE_OUTPUT", "reason": "Only one Quality-accepted source; no qualified relation bundles or verified observation/context alignment.", "pair_count": 0},
        {"stage": "conflict detection/classification", "status": "BLOCKED", "reason": "No eligible relation bundle or comparable cross-paper observation pair; reasoning module not called with artificial input.", "conflict_count": 0},
        {"stage": "context attribution", "status": "NO_ELIGIBLE_OUTPUT", "reason": "No validated ConflictCandidate/ContextDifference/Comparability assessment."},
        {"stage": "hypothesis generation", "status": "NO_ELIGIBLE_OUTPUT", "reason": "No admissible conflict or mechanism artifacts; no hypothesis generator invocation."},
    ]
    contracts = [
        ("normalization intake", "src/code_engine/schemas/l1_extraction.py", "L1ExtractedClaim; raw subject/object, relation, evidence and context, model/prompt/source provenance; unknown is permitted."),
        ("entity resolution", "src/code_engine/normalization/candidates.py", "EntityResolutionRequest/Result; grounded candidate/type/species states; no ID fabricated on cache miss."),
        ("relation/core eligibility", "src/code_engine/normalization/core_eligibility.py", "Registered lexical relation is insufficient: accepted endpoints, intervention/measurement semantics, design and provenance gates remain required."),
        ("scientific cross-paper alignment", "src/code_engine/context_attribution/claim_alignment/models.py", "CanonicalPropositionSignature / AlignedClaimGroup; resolved critical dimensions and validated identities, not raw-word equality."),
        ("conflict candidates", "src/code_engine/context_attribution/conflict_candidate/models.py", "ConflictCandidate with two source-bound observation/claim identities, disagreement signal and validated provenance."),
        ("context/comparability", "src/code_engine/context_attribution/conflict_comparability/models.py", "ConflictComparabilityAssessment plus ContextDifference; policy/adjudication must have authority, pending is not comparable."),
        ("graph export and conflict admission", "src/code_engine/evidence_graph/builders.py", "EvidenceEdge and RelationEvidenceBundle; unresolved fallback/display IDs are excluded from scientific bundle reasoning."),
        ("hypothesis formation", "src/code_engine/hypothesis/candidate_builder.py", "Evidence-linked real conflict/confirmation/mechanism artifacts; empty or ineligible inputs do not establish a scientific result."),
        ("verified experiment boundary NOT created by bridge", "src/code_engine/schemas/fulltext_observation.py", "ExperimentalObservationV3 requires experiment, interventions, measurement, observed result, candidate relation and eligibility; Builder/Quality does not supply this authority."),
    ]
    for row in protected:
        assert handoff_adapter.root_hash(ROOT / row["path"], row["marker"]) == row["sha256"]
    assert handoff_adapter.root_hash(BASE, BASE_MARKER) == BASE_SHA
    assert caches_before == [ref(cache_path), ref(registry_path)]
    assert not denied
    OUT.mkdir(mode=0o700)
    put("root_causes.json", {"role_diagnoses": diagnoses, "local_inputs_before_after": caches_before,
        "note": "No candidate is not proof of unsupported biology, wrong type, or ambiguity. Existing local exact coverage is absent; external coverage is untested."})
    put("bridge_results_private.json", {"claims": claims, "normalized_reviewable_claims": normalized,
        "existing_evidence_edges": [e.to_dict() for e in edges], "admitted_relation_bundles": [],
        "review_scoped_node_ids_are_not_canonical": True, "conflicts": [], "hypotheses": []})
    put("contract_bindings.json", {"contracts": [{"stage": name, "file": ref(ROOT / path), "required_boundary": requirement} for name, path, requirement in contracts],
        "bridge": ref(ROOT / "src/code_engine/construction/builder_quality_bridge.py"),
        "runner": ref(Path(__file__)), "tests": ref(ROOT / "tests/test_builder_quality_bridge.py")})
    put("historical_preservation.json", {"previous_development_root": BASE_SHA, "protected_roots_before_after": protected,
        "historical_assets_modified": False, "frozen_builder_quality_contracts_modified": False,
        "local_inputs_unchanged": caches_before, "network_calls": 0, "llm_calls": 0,
        "builder_calls": 0, "quality_calls": 0, "fresh_primary_started": False, "scientific_policy_changed": False})
    summary = {"status": "BRIDGE_IMPLEMENTED_FORMAL_SCIENTIFIC_DOWNSTREAM_BLOCKED", "full_pipeline_pass": False,
        "stage_results": stages, "quality_accepted_source_groups": 1, "quality_accepted_propositions": 3,
        "reviewable_l1_claims": 3, "resolved_entity_roles": 0, "registered_lexical_relations": 2,
        "authoritative_scientific_relations": 0, "verified_experimental_observations_created": 0,
        "comparable_cross_paper_pairs": 0, "conflicts": 0, "hypotheses": 0,
        "provenance_roundtrip_verified": True, "all_upstream_assets_preserved": True,
        "remaining_blockers": ["No exact local cache mappings; default registry empty; external resolution disabled.",
            "Builder role heads/types, measurement and intervention semantics have no verified scientific authority.",
            "REQUIRES remains unregistered under existing relation semantics; no replacement mapping introduced.",
            "Twenty-one other cached Builder propositions still lack separately authorized Quality evaluation.",
            "Cross-paper alignment requires actual comparable source-grounded observations, not a relabeled L1 claim."],
        "ready_for_next_offline_bridge_replay": True, "ready_for_scaled_end_to_end_scientific_execution": False,
        "offline_execution_seconds": round(time.perf_counter() - started, 6), "network_calls": 0, "llm_calls": 0}
    put("summary.json", summary)
    root = handoff_adapter.root_hash(OUT, MARKER)
    with (OUT / MARKER).open("x") as handle:
        handle.write(root + "\n")
    assert handoff_adapter.root_hash(OUT, MARKER) == root
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("integration_root_sha256=" + root)


if __name__ == "__main__":
    main()
