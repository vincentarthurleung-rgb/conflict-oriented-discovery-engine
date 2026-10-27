"""Source-bound proposal adapter. Exact references validate structure, not science.

This is a development sidecar: it never materializes a relation, updates native
Core, or changes the existing materializer's authority requirements.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field

from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
from code_engine.schemas.fulltext_observation import FormalEvidenceSpanV3
from .assembly import assemble_v3
from .comparison_semantics import classify_comparison
from .comparator_linkage import recover_comparator
from .linkage_completeness import assess_linkage_v2
from .models import StrictCoreAsset, ExperimentalObservationLinkage
from .repair_v1 import SourceGroundedLinkageCandidateV1, materialize_linkage

VERSION = "source_grounded_linkage_proposal_adapter_v1"
PROMPT_VERSION = "source_grounded_linkage_candidate_prompt_v1"


class LinkProposal(StrictCoreAsset):
    relation_type: Literal[
        "factor_applies_to_measurement", "measurement_produces_result",
        "result_compared_against_factor", "result_uses_baseline",
        "observation_belongs_to_experiment_scope",
    ]
    source_ref: str
    target_ref: str
    evidence_refs: list[str] = Field(min_length=1)
    source_basis: Literal[
        "explicit_group_endpoint_statement", "explicit_measurement_result_statement",
        "explicit_comparison_statement", "explicit_scope_statement",
    ]
    support_explanation: str = Field(min_length=1)
    unresolved_information: list[str] = Field(default_factory=list)


class LinkProposalResponse(StrictCoreAsset):
    schema_version: Literal["source_grounded_linkage_proposals_v1"]
    observation_identity: str
    core_revision_identity: str
    proposals: list[LinkProposal]
    unresolved_information: list[str] = Field(default_factory=list)


def candidate_input(assembled, *, source_artifact, source_blocks, additional_evidence=()):
    """Existing V3 components plus optional controller-supplied exact source anchors.

    Supplemental anchors remain sidecar evidence, never silently appended to V3.
    They can identify related Results/captions/Methods in the same source. Their
    scientific applicability is still a proposal, not inferred from co-location.
    """
    env = assembled["envelope"]
    # Recheck source bytes as well as native schema/references, including when a
    # caller supplies an assembly loaded from disk.
    assemble_v3(env["ExperimentalObservationV3"], source_artifact=source_artifact,
                source_blocks=source_blocks)
    prepare_experimental_handoff(env, Path(source_artifact))
    formal, core = env["ExperimentalObservationV3"], env["ExperimentalCore"]
    spans = deepcopy(formal["provenance"]["evidence_spans"])
    by_id = {s["evidence_span_id"]: s for s in spans}
    for raw in additional_evidence:
        s = FormalEvidenceSpanV3.model_validate(raw).model_dump(mode="json")
        if s["source_document_id"] != formal["provenance"]["source_document_id"]:
            raise ValueError("supplemental_anchor_cross_source")
        block = source_blocks.get(s["block_id"])
        if (block is None or not 0 <= s["char_start"] < s["char_end"] <= len(block) or
                block[s["char_start"]:s["char_end"]] != s["text"] or
                hashlib.sha256(s["text"].encode()).hexdigest() != s["text_hash"]):
            raise ValueError("supplemental_anchor_source_coordinate_mismatch")
        if s["evidence_span_id"] in by_id and by_id[s["evidence_span_id"]] != s:
            raise ValueError("supplemental_anchor_identity_collision")
        by_id[s["evidence_span_id"]] = s
    spans = list(by_id.values())
    return {
        "observation_identity": formal["observation_id"],
        "core_revision_identity": core["revision"]["identity"],
        "experiment_scope_identity": formal["experiment"]["experiment_id"],
        "experiment": deepcopy(formal["experiment"]),
        "source_identity": {k: formal["provenance"][k] for k in ("pmid", "pmcid", "fulltext_source_hash")},
        "source_artifact": str(Path(source_artifact).resolve()),
        "source_artifact_sha256": file_hash(Path(source_artifact)),
        "source_blocks_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sorted(source_blocks.items())},
        "components": {k: deepcopy(core[k]) for k in ("factors", "measurements", "results")},
        "evidence_spans": deepcopy(spans),
        "scientific_authorization": False,
    }


def render_candidate_prompt(packet):
    # Separately versioned; frozen V3 prompts and schemas are not changed.
    rules = (
        "Propose experimental linkage candidates only, using exact supplied component "
        "identities and evidence_span_id references. Return zero proposals when unsupported. "
        "Same paragraph, shared scope, endpoint cardinality and name similarity do not "
        "establish linkage. Results, captions and Methods may jointly support a link only "
        "when their explicit group, endpoint or figure references support the relationship. "
        "Explain that explicit support and preserve uncertainty; never infer mediation, "
        "causal signs, canonical identity, missing methods or experimental manipulation "
        "from biomarker strata. Do not assert scientific approval or materialization authority. "
        "Use the supplied observation and Core revision identities. Output JSON matching "
        "this response schema."
    )
    import json
    return PROMPT_VERSION + "\n" + rules + "\nSCHEMA:\n" + json.dumps(
        LinkProposalResponse.model_json_schema(), sort_keys=True
    ) + "\nSOURCE_BOUND_INPUT:\n" + json.dumps(packet, ensure_ascii=False, sort_keys=True)


def produce_candidates(assembled, response, *, source_artifact, source_blocks, proposal_origin, additional_evidence=()):
    packet = candidate_input(assembled, source_artifact=source_artifact, source_blocks=source_blocks, additional_evidence=additional_evidence)
    response = LinkProposalResponse.model_validate(response)
    if (response.observation_identity != packet["observation_identity"] or
            response.core_revision_identity != packet["core_revision_identity"]):
        raise ValueError("linkage_proposal_revision_binding_mismatch")
    core = assembled["envelope"]["ExperimentalCore"]
    ids = {k: {x["identity"] for x in core[k]} for k in ("factors", "measurements", "results")}
    endpoints = {
        "factor_applies_to_measurement": (ids["factors"], ids["measurements"]),
        "measurement_produces_result": (ids["measurements"], ids["results"]),
        "result_compared_against_factor": (ids["results"], ids["factors"]),
        "result_uses_baseline": (ids["results"], ids["factors"]),
        "observation_belongs_to_experiment_scope": (
            {packet["core_revision_identity"], packet["observation_identity"]},
            {packet["experiment_scope_identity"]}),
    }
    bases = {
        "factor_applies_to_measurement": "explicit_group_endpoint_statement",
        "measurement_produces_result": "explicit_measurement_result_statement",
        "result_compared_against_factor": "explicit_comparison_statement",
        "result_uses_baseline": "explicit_comparison_statement",
        "observation_belongs_to_experiment_scope": "explicit_scope_statement",
    }
    evidence = {s["evidence_span_id"]: s for s in packet["evidence_spans"]}
    provenance = {"producer": VERSION, "producer_version": "1",
                  "source_artifact_refs": [packet["source_artifact"]],
                  "deterministic_rule_refs": ["exact_endpoint_and_source_anchor_integrity_only"],
                  "limitations": ["Source semantics are a proposal, not independent verification", proposal_origin],
                  "offline": True}
    links, candidates, decisions, seen = [], [], [], set()
    for p in response.proposals:
        left, right = endpoints[p.relation_type]
        if p.source_ref not in left or p.target_ref not in right:
            raise ValueError("linkage_proposal_endpoint_type_or_scope_mismatch")
        if not set(p.evidence_refs) <= evidence.keys():
            raise ValueError("linkage_proposal_unknown_evidence_anchor")
        if p.source_basis != bases[p.relation_type]:
            raise ValueError("linkage_proposal_explicit_basis_mismatch")
        key = (p.relation_type, p.source_ref, p.target_ref)
        if key in seen:
            raise ValueError("duplicate_linkage_proposal")
        seen.add(key)
        payload = dict(observation_revision_identity=packet["core_revision_identity"],
                       relation_type=p.relation_type, source_ref=p.source_ref, target_ref=p.target_ref,
                       evidence_anchor_ids=p.evidence_refs, derivation_method=VERSION + ":" + proposal_origin,
                       validation_status="candidate_structural_integrity_only",
                       authority_status="candidate_only", provenance=provenance)
        ident = "candidate_link_" + content_hash([packet, p.model_dump(mode="json")])
        links.append(ExperimentalObservationLinkage(**payload, linkage_id=ident, identity=ident).model_dump(mode="json"))
        if p.relation_type in {"factor_applies_to_measurement", "result_compared_against_factor"}:
            candidate = SourceGroundedLinkageCandidateV1(
                observation_identity=packet["observation_identity"], relation_type=p.relation_type,
                source_ref=p.source_ref, target_ref=p.target_ref,
                source_identity=packet["source_identity"]["fulltext_source_hash"],
                evidence_refs=p.evidence_refs, explicit_source_semantics=True,
                # No deterministic semantic grounding claimed by this adapter.
                deterministic_grounding_version="", candidate_completeness_status="complete",
                structural_integrity_passed=True, authority_state="candidate",
                identity=ident, provenance=provenance)
            candidates.append(candidate.model_dump(mode="json"))
            decisions.append(materialize_linkage(candidate).model_dump(mode="json"))
    return {
        "schema_version": VERSION, "input_sha256": content_hash(packet),
        "input": packet, "proposal_origin": proposal_origin,
        "response": response.model_dump(mode="json"),
        "native_candidate_linkages": links, "source_grounded_candidates": candidates,
        "materialization_decisions": decisions,
        "structural_validation_passed": True,
        "source_semantics_independently_verified": False,
        "authority_label": "AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED",
        "scientific_authorization": False, "strict_core_eligible": False, "human_gold": False,
    }


def candidate_v2_diagnostic(assembled, sidecar):
    """Run existing V2 on a hypothetical candidate graph; return metrics, never Core.

    This diagnostic cannot be passed to formal handoff or admission. The original
    V3/Core remains byte-for-byte unchanged and materialization stays rejected.
    """
    core = deepcopy(assembled["envelope"]["ExperimentalCore"])
    if sidecar["input"]["core_revision_identity"] != core["revision"]["identity"]:
        raise ValueError("candidate_preview_revision_mismatch")
    for link in sidecar["native_candidate_linkages"]:
        for r in core["results"]:
            if r["identity"] == link["source_ref"]:
                if link["relation_type"] == "result_compared_against_factor":
                    r["comparison_factor_refs"].append(link["target_ref"])
                elif link["relation_type"] == "result_uses_baseline":
                    r["baseline_ref"] = link["target_ref"]
    formal = assembled["envelope"]["ExperimentalObservationV3"]
    semantics = [classify_comparison(r, core["revision"], formal) for r in core["results"]]
    recoveries = [recover_comparator(r, core["factors"], s, [])[1] for r, s in zip(core["results"], semantics)]
    metrics = assess_linkage_v2(core["revision"], core["factors"], core["measurements"], core["results"],
                               core["linkages"] + sidecar["native_candidate_linkages"], semantics, recoveries)
    return {"lane": "hypothetical_candidate_graph_diagnostic_only", "linkage_v2": metrics,
            "original_linkage_v2": assembled["audit"]["linkage"],
            "formal_core_modified": False, "scientific_authorization": False,
            "strict_core_eligible": False, "materialized_links": 0}
