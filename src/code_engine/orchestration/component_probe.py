"""Prepare hash-bound component requests; this module has no sending capability."""
from decimal import Decimal
import json
from pathlib import Path

from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.extraction_assets.experimental_core.linkage_candidates import (
    candidate_input, render_candidate_prompt,
)

VERSION = "bounded_linkage_component_probe_plan_v1"
CHAT_FRAMING_TOKEN_RESERVE = 1024


def request_proposal(body, *, source_identity, source_files, pricing, maximum_attempts=2):
    """Reserve all attempts, peak cache-miss price, full output including reasoning.

    UTF-8 request bytes plus explicit chat-framing reserve is a conservative
    engineering token ceiling, not a provider tokenizer measurement. Actual usage
    must be captured and checked by the existing budget controller at execution.
    """
    if maximum_attempts != 2 or body["model"] != pricing["model"]:
        raise ValueError("component_probe_model_or_retry_contract_mismatch")
    tokens = len(canonical_json(body).encode()) + CHAT_FRAMING_TOKEN_RESERVE
    output = body["max_tokens"]
    if output <= 0 or output > pricing["max_output_tokens"] or tokens + output > pricing["context_tokens"]:
        raise ValueError("component_probe_context_or_output_limit")
    cost = (Decimal(tokens) * Decimal(pricing["input_usd_per_million"]) +
            Decimal(output) * Decimal(pricing["output_usd_per_million"])) / Decimal(1000000)
    return {
        "schema_version": VERSION, "provider_body_sha256": content_hash(body),
        "model": body["model"], "source_identity": source_identity,
        "source_files": [{"path": str(Path(p).resolve()), "sha256": file_hash(Path(p))} for p in source_files],
        "input_token_ceiling": tokens, "output_token_ceiling": output,
        "input_ceiling_method": "canonical UTF-8 request bytes + 1024 chat framing tokens; not measured tokenizer count",
        "maximum_attempts": maximum_attempts, "per_attempt_reservation_usd": str(cost),
        "full_retry_reservation_usd": str(cost * maximum_attempts),
        "pricing_sha256": content_hash(pricing), "cache_or_off_peak_discount_assumed": False,
        "execution_authorized": False, "actual_API_calls": 0,
    }


def conditional_linkage_request(assembled, *, source_artifact, source_blocks,
                                actual_v3_response_file, validated_v3_file, model="deepseek-flash",
                                input_token_ceiling=40000, max_output_tokens=8192, question_domain=None,
                                hydration_context=None, additional_evidence=()):
    """Bind after actual V3 hydration, before any separately authorized dispatch.

    Caller must retain the provider response and validated formal output. The
    returned proposal remains unauthorized and cannot send itself. No future
    observation identity or future response-file hash is guessed in a plan.
    """
    response_path = Path(actual_v3_response_file)
    if not response_path.is_file():
        raise ValueError("actual_V3_response_artifact_required")
    validated_path = Path(validated_v3_file)
    text = validated_path.read_text()
    try:
        payload = json.loads(text)
    except ValueError:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    formal = assembled["envelope"]["ExperimentalObservationV3"]
    def contains_exact_formal(value):
        if isinstance(value, dict):
            return value == formal or any(contains_exact_formal(x) for x in value.values())
        return isinstance(value, list) and any(contains_exact_formal(x) for x in value)
    if not contains_exact_formal(payload):
        raise ValueError("validated_V3_artifact_observation_binding_mismatch")
    # A file merely named "response" is not evidence that it produced the V3.
    # Re-run the existing parser/hydrator against the exact retained context.
    from dataclasses import asdict
    import hashlib
    from code_engine.fulltext.fulltext_l1_v2 import parse_draft_response
    from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import hydrate_draft_response_v3
    if hydration_context is None:
        raise ValueError("actual_V3_hydration_context_required")
    ctx = hydration_context
    if (source_blocks.get(ctx.block_id) != ctx.block_text or
            hashlib.sha256(ctx.block_text.encode()).hexdigest() != ctx.source_block_hash or
            file_hash(Path(ctx.source_artifact)) != ctx.fulltext_source_hash):
        raise ValueError("actual_V3_source_context_binding_mismatch")
    raw = json.loads(response_path.read_text())
    if "choices" in raw:
        choice = raw["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("actual_V3_response_not_complete")
        raw = json.loads(choice["message"]["content"])
    hydrated = hydrate_draft_response_v3(parse_draft_response(raw), ctx)
    if hydrated.rejected or formal not in hydrated.formal_response["experimental_observations"]:
        raise ValueError("actual_V3_response_observation_binding_mismatch")
    packet = candidate_input(assembled, source_artifact=source_artifact, source_blocks=source_blocks,
                             additional_evidence=additional_evidence)
    result_refs = set(formal["observation"]["evidence_span_ids"])
    if (not any(f["evidence_anchor_ids"] for f in packet["components"]["factors"]) or not packet["evidence_spans"] or
            not formal["measurement"]["evidence_span_ids"] or
            not any(s["evidence_span_id"] in result_refs and s["source_role"] == "current" for s in packet["evidence_spans"]) or
            formal["statement_role"] != "current_study_experiment"):
        raise ValueError("actual_V3_components_and_evidence_required")
    from code_engine.domain.extraction_routing import prepare_linkage_prompt
    prompt,routing = prepare_linkage_prompt(packet,render_candidate_prompt(packet),question_domain=question_domain)
    body = {"model": model, "messages": [{"role": "system", "content": prompt}],
            "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"},
            "max_tokens": max_output_tokens}
    ceiling = len(canonical_json(body).encode()) + CHAT_FRAMING_TOKEN_RESERVE
    if ceiling > input_token_ceiling:
        raise ValueError("conditional_linkage_request_exceeds_reserved_input_ceiling")
    return {"body": body, "body_sha256": content_hash(body), "routing":routing,
            "cache_identity":content_hash({'body':body,'routing':routing}),"input_token_ceiling": ceiling,
            "actual_v3_response_file": str(response_path.resolve()),
            "actual_v3_response_sha256": file_hash(response_path), "input_sha256": content_hash(packet),
            "hydration_context_sha256": content_hash(asdict(ctx)),
            "verification": "source-bound parser/hydrator replay; no independent scientific or provider-origin attestation",
            "validated_v3_file": str(validated_path.resolve()), "validated_v3_sha256": file_hash(validated_path),
            "execution_authorized": False, "binding_status": "prepared_candidate_request_not_authorized"}


def prepare_v3_component_request(article,block,*,question_domain=None,model="deepseek-flash",max_output_tokens=32768):
    """Current routed preparation path for a future component probe. Never sends."""
    from code_engine.domain.extraction_routing import prepare_v3_prompt,routed_v3_preflight
    from code_engine.fulltext.fulltext_l1_v2 import FulltextTokenBudget
    audit=routed_v3_preflight(article,block,question_domain=question_domain,budget=FulltextTokenBudget(max_tokens=max_output_tokens))
    if audit['preflight_decision']!='execute_as_is':
        raise ValueError('routed_component_input_requires_source_replanning')
    prompt,route=prepare_v3_prompt(article,block,question_domain=question_domain)
    body={'model':model,'messages':[{'role':'system','content':prompt}],'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'max_tokens':max_output_tokens}
    return {'body':body,'body_sha256':content_hash(body),'routing':route,'preflight':audit,
            'cache_identity':content_hash({'body':body,'routing':route}),'execution_authorized':False}
