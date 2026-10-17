"""Offline AI-assisted review and exploratory discovery, with no formal authority.

There is deliberately no model client, Atlas write or formal promotion function.
Reviews are supplied explicitly by an interactive AI session or separately
budgeted model run. Content hashes establish provenance, never scientific truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code_engine.discovery.lanes import evaluate_claim_comparability
from code_engine.extraction.l1_budget import estimate_tokens
from code_engine.system_b.annotation_schemas.registry import canonical_json

LABEL = "AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED"
NAMESPACE = "seen_development_shadow"
REVIEW_FIELDS = (
    "experimental_scope", "intervention_factor", "comparator_baseline",
    "measurement_endpoint", "observed_result_direction", "evidence_linkage",
    "missing_method_limitations", "mechanistic_overstatement", "source_support",
)
Verdict = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNCERTAIN"]


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ShadowAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    namespace: Literal["seen_development_shadow"] = NAMESPACE
    authority_label: Literal["AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED"] = LABEL
    execution_path: Literal["shadow"] = "shadow"
    scientific_authorization: Literal[False] = False
    human_gold: Literal[False] = False
    strict_core_eligible: Literal[False] = False
    formal_core_graph_eligible: Literal[False] = False

    @model_validator(mode="before")
    @classmethod
    def no_authority_coercion(cls, value: Any) -> Any:
        if isinstance(value, dict):
            for name in ("scientific_authorization", "human_gold", "strict_core_eligible", "formal_core_graph_eligible"):
                if name in value and value[name] is not False:
                    raise ValueError("shadow_authority_must_be_false:" + name)
        return value


class FieldReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    field: str
    verdict: Verdict
    evidence_refs: list[str] = Field(min_length=1)
    reasoning_summary: str = Field(min_length=12)
    uncertainty: str = Field(min_length=5)


class SourceFacet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    value: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    uncertainty: str = Field(min_length=5)


class ShadowClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    measured_entity: SourceFacet
    endpoint: SourceFacet
    measurement_type: SourceFacet
    factor: SourceFacet
    study_design: Literal["interventional", "observational"]
    direction: Literal["positive", "negative", "no_increase", "not_significant", "unknown"]
    direction_evidence_refs: list[str] = Field(min_length=1)
    direction_interpretation: str = Field(min_length=12)
    context: dict[str, SourceFacet]
    canonical_identity_status: Literal["unresolved"] = "unresolved"
    measurement_classification_status: Literal["existing_contract", "unresolved"]


class AIReview(ShadowAuthority):
    schema_version: Literal["ai_scientific_review_shadow_v1"] = "ai_scientific_review_shadow_v1"
    packet_id: str
    input_hashes: dict[str, str]
    V3_observation_id: str | None = None
    Core_revision_id: str | None = None
    reviewer_kind: Literal["interactive_assistant", "budgeted_model_diagnostic"]
    model_family: str = Field(min_length=1)
    exact_model_id: str | None = None
    model_identity_basis: str = Field(min_length=12)
    independence_status: Literal["shared_context_not_independent", "separate_model_diagnostic_only"]
    independence_limitations: str = Field(min_length=12)
    prompt_version: str = Field(min_length=1)
    reviewed_at: str
    fields: list[FieldReview]
    claim: ShadowClaim

    @model_validator(mode="after")
    def complete_review(self) -> "AIReview":
        names = [f.field for f in self.fields]
        if len(names) != len(REVIEW_FIELDS) or set(names) != set(REVIEW_FIELDS):
            raise ValueError("all_nine_review_fields_required_once")
        stamp = datetime.fromisoformat(self.reviewed_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("review_timestamp_timezone_required")
        required = {"packet", "source", "prompt"}
        if not required <= self.input_hashes.keys():
            raise ValueError("review_input_hashes_incomplete")
        for value in self.input_hashes.values():
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid_input_sha256")
        if self.reviewer_kind == "interactive_assistant" and self.independence_status != "shared_context_not_independent":
            raise ValueError("interactive_review_cannot_claim_independent_model_assessment")
        return self


@dataclass(frozen=True)
class BoundPacket:
    packet: dict[str, Any]
    input_hashes: dict[str, str]
    observation_id: str | None
    revision_id: str | None


def load_bound_packet(packet_path: Path, prompt_path: Path, v3_core_path: Path | None = None) -> BoundPacket:
    """Check exact frozen source offsets/hashes; recover no missing facts or links."""
    packet = json.loads(packet_path.read_text())
    source = packet["source"]
    source_path = Path(source.get("article_path") or source.get("article_json_path") or "")
    expected = source.get("article_sha256") or source.get("article_json_sha256")
    if file_hash(source_path) != expected:
        raise ValueError("source_hash_mismatch")
    article = json.loads(source_path.read_text())
    if str(article.get("pmcid")) != str(source["pmcid"]) or str(article.get("pmid")) != str(source["pmid"]):
        raise ValueError("source_identity_mismatch")
    original_paragraphs = None
    original_xml_hash = None
    if source.get("format") == "frozen_jats_paragraph_projection":
        xml_path = Path(source["original_xml_path"])
        original_xml_hash = file_hash(xml_path)
        if original_xml_hash != source["original_xml_sha256"]:
            raise ValueError("original_xml_hash_mismatch")
        xml = ET.parse(xml_path).getroot()
        identities = {x.get("pub-id-type"):x.text for x in xml.findall(".//front/article-meta/article-id")}
        if identities.get("pmcid") != source["pmcid"] or identities.get("pmid") != source["pmid"]:
            raise ValueError("original_xml_identity_mismatch")
        original_paragraphs = xml.findall(".//body//p")
    ids = []
    for span in packet["evidence_spans"]:
        ids.append(span["evidence_span_id"])
        section = article["sections"][span["section_index"]]
        text = section["text"]
        if original_paragraphs is not None:
            original = original_paragraphs[section["source_xml_paragraph_index"]]
            if " ".join("".join(original.itertext()).split()) != text:
                raise ValueError("original_xml_paragraph_projection_mismatch")
        if (text[span["char_start"]:span["char_end"]] != span["text"]
                or hashlib.sha256(span["text"].encode()).hexdigest() != span["text_hash"]
                or hashlib.sha256(text.encode()).hexdigest() != span["source_section_text_sha256"]):
            raise ValueError("source_span_mismatch")
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("source_evidence_ids_invalid")
    hashes = {"packet": file_hash(packet_path), "source": expected, "prompt": file_hash(prompt_path)}
    if original_xml_hash:
        hashes["original_xml"] = original_xml_hash
    obs, rev = packet.get("V3_observation_id"), packet.get("Core_revision_id")
    if v3_core_path is not None:
        record = json.loads(v3_core_path.read_text())
        formal, core = record["ExperimentalObservationV3"], record["ExperimentalCore"]
        if formal["provenance"]["fulltext_source_hash"] != expected or formal["provenance"]["pmcid"] != source["pmcid"]:
            raise ValueError("record_source_mismatch")
        actual_obs, actual_rev = formal["observation_id"], core["revision"]["identity"]
        if (obs is not None and obs != actual_obs) or (rev is not None and rev != actual_rev):
            raise ValueError("record_revision_mismatch")
        obs, rev = actual_obs, actual_rev
        hashes["V3_Core"] = file_hash(v3_core_path)
    return BoundPacket(packet, hashes, obs, rev)


def bind_review(bound: BoundPacket, payload: dict[str, Any]) -> AIReview:
    review = AIReview.model_validate(payload)
    if review.packet_id != bound.packet["packet_id"] or review.input_hashes != bound.input_hashes:
        raise ValueError("review_input_binding_mismatch")
    if review.V3_observation_id != bound.observation_id or review.Core_revision_id != bound.revision_id:
        raise ValueError("review_revision_binding_mismatch")
    refs = {s["evidence_span_id"] for s in bound.packet["evidence_spans"]}
    used = [r for f in review.fields for r in f.evidence_refs]
    used += review.claim.direction_evidence_refs
    for name in ("measured_entity", "endpoint", "measurement_type", "factor"):
        used += getattr(review.claim, name).evidence_refs
    used += [r for f in review.claim.context.values() for r in f.evidence_refs]
    if not set(used) <= refs:
        raise ValueError("review_unknown_evidence_reference")
    return review


def _marked(schema: str, **payload: Any) -> dict[str, Any]:
    return {**ShadowAuthority().model_dump(mode="json"), "schema_version": schema, **payload}


def _review_limits(review: AIReview) -> dict[str, str]:
    return {f.field: f.verdict for f in review.fields if f.verdict != "SUPPORTED"}


def compare_shadow_pair(left: BoundPacket, right: BoundPacket, left_review: AIReview, right_review: AIReview) -> dict[str, Any]:
    """Reuse weak comparison as a diagnostic; never invoke Candidate Qualification."""
    for b,r in ((left,left_review),(right,right_review)):
        bind_review(b,r.model_dump(mode="json"))
    if (left.packet["source"]["pmcid"] == right.packet["source"]["pmcid"]
            or left.packet["source"]["pmid"] == right.packet["source"]["pmid"]):
        raise ValueError("independent_papers_required")
    a,b = left_review.claim,right_review.claim
    def diagnostic(c: ShadowClaim) -> dict[str, Any]:
        # No canonical IDs/names supplied; lexical family matches confer no identity authority.
        return {"subject_raw":c.factor.value,"object_raw":c.measured_entity.value+" "+c.endpoint.value,
            "direction":c.direction if c.direction in {"positive","negative"} else "unknown",
            "relation_raw":"protein level" if c.measurement_type.value=="Western blot" else "expression",
            "context_terms":[x.value for x in c.context.values()]}
    legacy = evaluate_claim_comparability(diagnostic(a),diagnostic(b))
    exact = {name:getattr(a,name).value == getattr(b,name).value for name in ("measured_entity","endpoint","measurement_type","factor")}
    differences=[]
    for name in sorted(a.context.keys() | b.context.keys()):
        x,y=a.context.get(name),b.context.get(name)
        if x is None or y is None or x.value != y.value:
            differences.append({"axis":name,"left":x.model_dump() if x else None,"right":y.model_dump() if y else None,
                "attribution":"candidate_context_modifier_only_NOT_a_causal_explanation"})
    critical=set(REVIEW_FIELDS)-{"missing_method_limitations","mechanistic_overstatement"}
    fields=[f for r in (left_review,right_review) for f in r.fields]
    unsupported=any(f.verdict=="UNSUPPORTED" for f in fields)
    uncertain=any(f.verdict=="UNCERTAIN" and f.field in critical for f in fields)
    critical_supported=all(f.verdict=="SUPPORTED" for f in fields if f.field in critical)
    opposed={a.direction,b.direction}=={"positive","negative"}
    matched=all(exact.values()) and a.study_design==b.study_design
    if unsupported:
        status="NOT_SUPPORTED_BY_REVIEW"
    elif not matched:
        status="NOT_SUFFICIENTLY_COMPARABLE"
    elif uncertain:
        status="UNCERTAIN"
    elif a.direction==b.direction and a.direction in {"positive","negative"}:
        status="DIRECTIONALLY_CONCORDANT_CONTEXT_DIVERGENT" if differences else "DIRECTIONALLY_CONCORDANT"
    elif opposed and critical_supported and legacy["eligible_for_weak_conflict"]:
        status="PROVISIONAL_CONTEXT_SPLIT_CONTRADICTION" if differences else "PROVISIONAL_CONTRADICTION"
    else:
        status="DIRECTION_DIFFERENCE_WITHOUT_ESTABLISHED_OPPOSITION"
    provisional=status in {"PROVISIONAL_CONTEXT_SPLIT_CONTRADICTION","PROVISIONAL_CONTRADICTION"}
    pair=_marked("shadow_evidence_alignment_v1",packet_ids=[left_review.packet_id,right_review.packet_id],
        source_papers=[left.packet["source"]["pmcid"],right.packet["source"]["pmcid"]],
        review_hashes=[content_hash(r.model_dump(mode="json")) for r in (left_review,right_review)],
        alignment_status=status,exact_candidate_labels=exact,identity_authority="NONE_LITERAL_CANDIDATE_LABELS_ONLY",
        canonical_identity_status="unresolved",measurement_classification_status=[a.measurement_classification_status,b.measurement_classification_status],
        observed_directions=[a.direction,b.direction],direction_opposed=opposed,context_differences=differences,
        review_limitations=[_review_limits(left_review),_review_limits(right_review)],legacy_comparison_diagnostic=legacy,
        production_candidate_qualification_invoked=False,formal_conflict=False,provisional_contradiction=provisional,
        derived_causal_sign=None,source_evidence_refs=[a.direction_evidence_refs,b.direction_evidence_refs],
        qualification_limitations="Compatible candidate labels and diagnostic scores are not authorized identity, intervention equivalence, formal comparability or a causal explanation.")
    pair["hypotheses"]=[]
    if provisional and differences:
        modifier=differences[0]
        pair["hypotheses"]=[_marked("shadow_falsifiable_hypothesis_v1",
            statement=f"The observed direction for {a.measured_entity.value} / {a.endpoint.value} under {a.factor.value} may depend on {modifier['axis']}.",
            supporting_evidence_refs=a.direction_evidence_refs,contradicting_evidence_refs=b.direction_evidence_refs,
            candidate_modifier=modifier,observed_direction_predictions=[a.direction,b.direction],derived_causal_sign=None,
            test="Use a prospectively specified, matched assay and comparator across both context strata; vary the proposed context factor while holding measured confounders fixed. Reject this modifier hypothesis if the preregistered directional interaction is absent or not reproducible. This is a proposed test, not a claim that it has been performed.",
            validated_hypothesis=False)]
    return pair


def persist_shadow(root: Path, artifact: dict[str, Any]) -> dict[str, str]:
    """Append by content hash in a dedicated directory; no mutable current pointer."""
    authority=ShadowAuthority.model_validate({k:artifact[k] for k in ShadowAuthority.model_fields})
    if authority.namespace != NAMESPACE:
        raise ValueError("shadow_namespace_required")
    digest=content_hash(artifact)
    data=(canonical_json(artifact)+"\n").encode()
    path=root/"shadow"/(digest+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as handle:handle.write(data)
    except FileExistsError:
        if path.read_bytes()!=data:raise ValueError("immutable_shadow_artifact_collision")
    return {"path":str(path),"canonical_output_sha256":digest,"file_sha256":file_hash(path)}


def run_reviewed_pair(*, packet_paths: list[Path], review_paths: list[Path], prompt_path: Path,
                      output_root: Path, core_paths: list[Path | None] | None = None) -> dict[str, Any]:
    """Runnable ingestion of two supplied real AI reviews; never produce reviews implicitly."""
    if len(packet_paths)!=2 or len(review_paths)!=2 or (core_paths is not None and len(core_paths)!=2):
        raise ValueError("exactly_two_packets_and_reviews_required")
    bound=[load_bound_packet(p,prompt_path,c) for p,c in zip(packet_paths,core_paths or [None,None])]
    reviews=[bind_review(b,json.loads(p.read_text())) for b,p in zip(bound,review_paths)]
    pair=compare_shadow_pair(*bound,*reviews)
    review_receipts=[persist_shadow(output_root,r.model_dump(mode="json")) for r in reviews]
    pair_receipt=persist_shadow(output_root,pair)
    return _marked("shadow_workflow_receipt_v1",review_receipts=review_receipts,pair_receipt=pair_receipt,
        alignment_status=pair["alignment_status"],provisional_contradictions=int(pair["provisional_contradiction"]),
        provisional_hypotheses=len(pair["hypotheses"]),actual_api_calls=0,formal_import_performed=False)


def plan_model_reviews(requests: list[str], *, max_output_tokens: int = 4096,
                       input_usd_per_million: float | None = None, output_usd_per_million: float | None = None) -> dict[str, Any]:
    """Estimate only; incomplete local pricing must never be presented as total cost."""
    if max_output_tokens<=0 or any(r is not None and r<0 for r in (input_usd_per_million,output_usd_per_million)):
        raise ValueError("invalid_budget_parameters")
    tokens=[estimate_tokens(r) for r in requests]
    total_input=sum(tokens);total_output=len(requests)*max_output_tokens
    priced=input_usd_per_million is not None and output_usd_per_million is not None
    return _marked("shadow_model_call_plan_v1",automatic_execution_authorized=False,actual_api_calls=0,
        planned_calls=len(requests),per_call_input_token_estimates=tokens,estimated_total_input_tokens=total_input,
        max_total_output_tokens=total_output,token_estimator="existing_l1_budget_estimate_tokens_len_div_4_NOT_provider_tokenizer",
        model_id=None,input_usd_per_million=input_usd_per_million,output_usd_per_million=output_usd_per_million,
        estimated_total_usd=(total_input*input_usd_per_million+total_output*output_usd_per_million)/1_000_000 if priced else None,
        cost_formula=f"({total_input} * input_rate + {total_output} * output_rate) / 1000000",
        budget_status="ESTIMATE_ONLY_REQUIRES_SEPARATE_APPROVAL" if priced else "UNPRICED_MODEL_AND_BOTH_RATES_REQUIRED",
        pricing_limitations="No network price lookup. Local legacy L1 profiles contain input-only estimates and cannot price review completion tokens.")
