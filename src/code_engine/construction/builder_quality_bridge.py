"""Lossless, offline Builder/Quality-to-reviewable-L1 integration.

Builder propositions are claims, not ExperimentalObservationV3 records.
This bridge supplies existing normalization interfaces without granting
experimental, canonical identity, comparability, or causal authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict
from typing import Any

from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts.search_plan_v24_alpha317a_safety_audits import leakage_failed
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha320a_v4_localizer import SUCCESS, localize_exact_body_quote

from code_engine.construction.handoff_adapter import validate_construction_document
from code_engine.extraction.polarity import normalize_directional_relation
from code_engine.normalization.composite_endpoints import decompose_endpoint, endpoint_with_resolution
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.formal_relations import normalize_formal_relation
from code_engine.normalization.intervention_semantics import EvidenceSemantics
from code_engine.normalization.resolver import ResolverCascade
from code_engine.schemas.l1_extraction import L1ExtractedClaim

BRIDGE_VERSION = "builder_quality_reviewable_l1_bridge_v1"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: require(False, "NONFINITE_JSON"))
    require(type(value) is dict, "JSON_OBJECT_REQUIRED")
    return value


def project_quality_accepted_builder_claims(
    *, document: dict, private_source_token: str, source_identity: dict,
    private_identity: dict, builder_request_manifest: dict,
    builder_response_raw: bytes, builder_response_sha256: str,
    quality_request_manifest: dict, quality_response_raw: bytes,
    quality_response_sha256: str,
) -> dict[str, Any]:
    """Caller verifies immutable source admission/roots; this checks every join.

    No file or network access. Public bibliographic identity stays controller
    side. Only exact, source-bound QUALITY_PASS candidates become L1 claims.
    """
    validate_construction_document(document, private_source_token)
    require(source_identity.get("pmid") and source_identity.get("pmcid"), "SOURCE_IDENTITY_REQUIRED")
    require(all(private_identity.get(k) == source_identity.get(k)
                for k in ("pmid", "pmcid")), "PRIVATE_SOURCE_IDENTITY_MISMATCH")
    if source_identity.get("doi") is not None:
        require(private_identity.get("doi") == source_identity["doi"], "SOURCE_DOI_MISMATCH")
    document_sha = sha(canonical(document))
    bm, qm = builder_request_manifest, quality_request_manifest
    require(document_sha == bm["construction_document_sha256"] == qm["construction_document_sha256"], "DOCUMENT_HASH_MISMATCH")
    require(sha(canonical(bm["request"])) == bm["request_sha256"] == qm["builder_request_sha256"], "BUILDER_REQUEST_HASH_MISMATCH")
    require(sha(canonical(qm["request"])) == qm["request_sha256"], "QUALITY_REQUEST_HASH_MISMATCH")
    require(sha(builder_response_raw) == builder_response_sha256 == qm["builder_response_sha256"], "BUILDER_RESPONSE_HASH_MISMATCH")
    require(sha(quality_response_raw) == quality_response_sha256, "QUALITY_RESPONSE_HASH_MISMATCH")
    require(bm["scientific_source_input_sha256"] == sha(canonical({
        "abstract_text": document["abstract_text"], "body_text": document["body_text"]})), "BUILDER_SOURCE_INPUT_MISMATCH")
    require(bm["opaque_source_token_sha256"] == sha(private_source_token.encode()) == qm["private_source_token_sha256"], "SOURCE_TOKEN_HASH_MISMATCH")
    br, qr = _strict_json(builder_response_raw), _strict_json(quality_response_raw)
    for response, manifest in ((br, bm), (qr, qm)):
        require(response["model"] == manifest["request"]["model"], "PROVIDER_MODEL_MISMATCH")
        require(len(response["choices"]) == 1 and response["choices"][0]["finish_reason"] == "stop", "INCOMPLETE_PROVIDER_RESPONSE")
    schema = bm["expected_response_schema"]
    expected_user = ("Source token: " + private_source_token + "\nAbstract: " + document["abstract_text"]
                     + "\nBody: " + document["body_text"] + "\nOutput schema: " + canonical(schema).decode() + "\n")
    require(bm["request"]["messages"][1]["content"] == expected_user, "BUILDER_VISIBLE_INPUT_MISMATCH")
    parsed = _strict_json(br["choices"][0]["message"]["content"].encode())
    prechecks.validate_builder_response(canonical(parsed), private_source_token, schema)
    by_id: dict[str, dict] = {}
    survivors = []
    for position, candidate in enumerate(parsed["candidates"]):
        cid = candidate_id(private_source_token, candidate)
        if cid in by_id:
            require(by_id[cid]["candidate"] == candidate, "CANDIDATE_ID_COLLISION")
            by_id[cid]["original_array_positions"].append(position)
            continue
        location = localize_exact_body_quote(candidate["construction_evidence_span"]["exact_text"], document["body_text"], document["paragraphs"])
        record = {"candidate": candidate, "location": location, "original_array_positions": [position]}
        by_id[cid] = record
        if location["development_v4_localization_state"] != SUCCESS:
            continue
        start, end = location["body_document_start_offset"], location["body_document_end_offset"]
        sentence = prechecks.evidence_sentence(document["body_text"], start, end)
        if leakage_failed(candidate["neutral_proposition"], private_identity["title_1"], sentence):
            continue
        enriched = copy.deepcopy(candidate)
        enriched["construction_evidence_span"] = {"source_field": "body", "start_offset": start, "end_offset": end,
                                                   "exact_text": candidate["construction_evidence_span"]["exact_text"]}
        survivors.append({"candidate_id": cid, "candidate_payload_sha256": sha(canonical(candidate)), "candidate": enriched,
                          "original_array_positions": record["original_array_positions"]})
    survivors.sort(key=lambda r: (r["candidate_payload_sha256"], r["candidate_id"]))
    expected_payload = prechecks.build_quality_payload(private_source_token, survivors, document, private_identity)
    require(expected_payload == qm["quality_payload"], "QUALITY_INPUT_CANDIDATE_OR_EVIDENCE_MISMATCH")
    packets = expected_payload["candidate_packets"]
    # The exact model-visible packet list must actually occur in the frozen request.
    require(canonical(packets).decode() in qm["request"]["messages"][1]["content"], "QUALITY_VISIBLE_INPUT_MISMATCH")
    quality_parsed = _strict_json(qr["choices"][0]["message"]["content"].encode())
    judgments = quality.validate_response(quality_parsed, expected_payload["source_group_id"], {p["candidate_id"] for p in packets},
        {p["candidate_id"]: p["evidence"]["exact_evidence_span"] + "\n" + p["evidence"]["bounded_local_context"] for p in packets}, qm["expected_response_schema"])
    eligible = {j["candidate_id"] for j in judgments if quality.quality_result(j["criteria"])["overall_quality_state"] == "QUALITY_ELIGIBLE"}
    claims = []
    for cid, record in by_id.items():
        if cid not in eligible:
            continue
        candidate, location = record["candidate"], record["location"]
        start, end = location["body_document_start_offset"], location["body_document_end_offset"]
        paragraph = next(p for p in document["paragraphs"] if p["span_id"] == location["anchor_id"])
        context = {k: candidate[k] for k in ("species", "biological_unit", "intrinsic_conditioning", "intrinsic_therapy_context", "intrinsic_disease_or_genotype_context")}
        relation = normalize_directional_relation(candidate["relation_direction"])
        # Unknown types, statement role, design, and direct sign remain unknown.
        claim = L1ExtractedClaim(
            claim_id=cid, paper_id=source_identity["pmid"], chunk_id=location["anchor_id"], chunk_hash=sha(paragraph["text"].encode()),
            domain_id="general_biomedical", prompt_profile_id=bm["builder_v4_version"], prompt_version=bm["selected_abstraction_variant"],
            output_schema_version="BuilderOutputSchemaV4", extraction_policy_version=BRIDGE_VERSION, model_name=br["model"],
            model_family=bm["provider"], compiled_prompt_hash=bm["prompt_sha256"],
            subject_raw=candidate["actor_or_intervention"], object_raw=candidate["response_or_endpoint"],
            relation_raw=candidate["relation_direction"], relation_family=relation.relation_family, direction=relation.direction,
            polarity_type=relation.polarity_type, context=context, species=candidate["species"] or "",
            evidence_sentence=document["body_text"][start:end], evidence_quote=document["body_text"][start:end],
            section=" / ".join(paragraph["section_headings"]),
            record_kind="builder_quality_reviewable_claim", candidate_id=cid, neutral_proposition=candidate["neutral_proposition"],
            builder_candidate=copy.deepcopy(candidate), original_array_positions=record["original_array_positions"],
            evidence_span={"source_field": "body", "start_offset": start, "end_offset": end, "coordinate_end_semantics": "exclusive", "offset_unit": "Unicode code point", "exact_text": document["body_text"][start:end], "anchor_id": location["anchor_id"]},
            source_scope="full_text", evidence_tier="fulltext_evidence", source_identity=copy.deepcopy(source_identity),
            quality_candidate_id=cid, quality_source_group_id=expected_payload["source_group_id"],
            quality_criterion_states=next(j["criteria"] for j in judgments if j["candidate_id"] == cid),
            context_authority="builder_reported_not_independently_experiment_validated",
            experimental_observation_verified=False,
            unavailable_experimental_fields=["validated_endpoint_types", "comparator", "dose", "route", "validated_measurement", "observation_result", "validated_intervention_semantics"],
            source_bindings={"construction_document_sha256": document_sha, "body_utf8_sha256": sha(document["body_text"].encode()),
                             "builder_request_sha256": bm["request_sha256"], "builder_response_sha256": builder_response_sha256,
                             "quality_request_sha256": qm["request_sha256"], "quality_response_sha256": quality_response_sha256,
                             "source_token_sha256": sha(private_source_token.encode())},
        )
        claims.append(claim.model_dump(mode="json"))
    return {"claims": claims, "quality_accepted_count": len(eligible), "quality_not_accepted_ids": sorted(set(by_id) - eligible),
            "exact_duplicate_candidates_removed": sum(len(r["original_array_positions"]) - 1 for r in by_id.values()),
            "experimental_observations_created": 0}


def normalize_reviewable_builder_claims(claims: list[dict], resolver: ResolverCascade | None = None) -> list[dict]:
    """Consume actual L1 fields while retaining all unresolved/ambiguous states.

    No local-ID salvage, new registry, inferred head extraction, or causal
    inversion. This output is for review/evidence export, not L2 observations.
    """
    resolver = resolver or ResolverCascade(execute=False, network_enabled=False, api_enabled=False,
        entity_network_lookup=False, entity_llm_proposer=False, entity_llm_cleaner=False, external_clients={})
    require(not any(getattr(resolver, name) for name in ("execute", "network_enabled", "api_enabled", "entity_network_lookup", "entity_llm_proposer", "entity_llm_cleaner_enabled")), "OFFLINE_RESOLVER_REQUIRED")
    require(resolver.hub.entity_cache is None and resolver.hub.audit_writer is None, "READ_ONLY_RESOLVER_REQUIRED")
    seen: dict[str, bytes] = {}
    result = []
    for raw in claims:
        claim = L1ExtractedClaim.model_validate(raw).model_dump(mode="json")
        require(claim.get("record_kind") == "builder_quality_reviewable_claim" and claim.get("experimental_observation_verified") is False, "REVIEWABLE_CLAIM_REQUIRED")
        cid = claim["claim_id"]
        if cid in seen:
            require(seen[cid] == canonical(claim), "DUPLICATE_CLAIM_ID_CONFLICT")
            continue
        seen[cid] = canonical(claim)
        value = copy.deepcopy(claim)
        decisions = {}
        for role in ("subject", "object"):
            decomposition = decompose_endpoint(claim[f"{role}_raw"], claim[f"{role}_type"])
            # No verified type is supplied by Builder V4; do not guess one.
            decision = resolver.resolve_entity(claim[f"{role}_raw"], {"paper_id": claim["paper_id"], "claim_id": cid,
                "species": claim["species"], "mention_role": role, "expected_entity_type": claim[f"{role}_type"], "context_text": claim["evidence_quote"]})
            decisions[role] = decision.model_dump(mode="json")
            # Resolver diagnostics can retain the top candidate's ID even when
            # ambiguous. Never publish that suggestion as canonical authority.
            resolved = decision.normalization_status == "resolved"
            value[f"{role}_canonical_id"] = (decision.canonical_id or None) if resolved else None
            value[f"{role}_canonical_name"] = (decision.canonical_name or None) if resolved else None
            value[f"{role}_normalization_status"] = decision.normalization_status
            value[f"{role}_entity_type"] = decision.entity_type
            value[f"{role}_resolution_decision_id"] = cid + ":" + role
            endpoint = decomposition.to_endpoint_fields()
            if decomposition.endpoint_decomposition_status == "decomposed":
                # A mapping for the complete surface is not a mapping for its
                # measured molecular head. Keep that separate lookup unresolved.
                endpoint.update(measured_entity_resolution_status="unresolved_fallback",
                                core_projection_reason="measured_head_resolution_not_available")
            else:
                endpoint = endpoint_with_resolution(endpoint, decision, cid + ":" + role)
            value[f"{role}_endpoint"] = endpoint
        value["normalization"] = decisions
        # Lexical registration is separate from scientific relationship authority.
        relation = normalize_formal_relation({"relation_raw": claim["relation_raw"].casefold(), "direction": claim["direction"]})
        value["lexical_relation_projection"] = asdict(relation) if relation else None
        value["lexical_relation_status"] = "registered" if relation else "unresolved"
        value["evidence_semantics"] = EvidenceSemantics().to_dict()
        value["core_gate_result"] = core_graph_eligibility(value)
        value.update(canonical_graph_eligible=False, allow_high_confidence_graph_use=False,
                     conflict_reasoning_eligible=False, formal_hypothesis_eligible=False,
                     graph_layer="reviewable_claim", scientific_edge_layer="causal_reviewable",
                     derived_causal_sign=None, observation_id=None,
                     core_exclusion_reasons=list(dict.fromkeys(value["core_gate_result"]["reasons"] + ["builder_claim_not_verified_experimental_observation"])))
        result.append(value)
    return result
