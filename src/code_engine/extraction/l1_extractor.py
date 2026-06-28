"""Offline L1 v2 extraction planning; no API client is invoked here."""

from __future__ import annotations

from typing import Any

from code_engine.domain.prompt_compiler import compile_l1_prompt
from code_engine.domain.prompt_registry import default_prompt_registry
from code_engine.domain.router import default_domain_router
from code_engine.extraction.llm_cache import compute_chunk_hash, load_llm_cache_index
from code_engine.extraction.llm_cache import record_cached_extraction
from code_engine.extraction.policy import (
    DEFAULT_L1_MODEL_FAMILY,
    DEFAULT_L1_MODEL_NAME,
    DEFAULT_L1_POLICY_VERSION,
    DEFAULT_L1_SCHEMA_VERSION,
    get_l1_sampling_config,
)
from code_engine.query.prompt_compatibility import (
    build_l1_prompt_fingerprint,
    compute_l1_cache_key,
)
from code_engine.extraction.converters import l1_claim_to_legacy_tuple
from code_engine.schemas.l1_extraction import L1ExtractedClaim


def build_l1_dry_run_plan(
    chunk_text: str,
    *,
    paper_id: str = "DRY_RUN",
    chunk_id: str = "chunk_0",
    chunk_index: int = 0,
    domain: str | None = None,
    auto_domain: bool = False,
    prompt_profile: str | None = None,
    prompt_version: str = "2.0",
    schema_version: str = DEFAULT_L1_SCHEMA_VERSION,
    model_name: str = DEFAULT_L1_MODEL_NAME,
    model_family: str = DEFAULT_L1_MODEL_FAMILY,
    experimental_temperature_schedule: bool = False,
    cache_path: str = "data/index/llm_cache_index.json",
) -> dict[str, Any]:
    """Compile prompt metadata, fingerprint, and cache decision without API use."""

    router = default_domain_router()
    selected_domain = domain
    if not selected_domain and auto_domain:
        selected_domain = router.route_text(chunk_text).name
    selected_domain = selected_domain or "general_biomedical"
    profile_id = prompt_profile or (
        "neuropharmacology" if selected_domain == "neuropharmacology"
        else "general_biomedical"
    )
    profile = default_prompt_registry().get_profile(profile_id)
    if prompt_profile and not domain and not auto_domain:
        selected_domain = profile.domain_id
    if profile.domain_id != selected_domain:
        raise ValueError(
            f"Prompt profile {profile.profile_id} belongs to {profile.domain_id}, "
            f"not {selected_domain}"
        )
    compiled = compile_l1_prompt(
        profile,
        chunk_text,
        prompt_version=prompt_version,
        output_schema_version=schema_version,
    )
    chunk_hash = compute_chunk_hash(chunk_text)
    fingerprint = build_l1_prompt_fingerprint(
        paper_id=paper_id,
        chunk_id=chunk_id,
        chunk_hash=chunk_hash,
        domain_id=selected_domain,
        prompt_profile_id=profile.profile_id,
        prompt_version=compiled.prompt_version,
        output_schema_version=compiled.output_schema_version,
        extraction_policy_version=DEFAULT_L1_POLICY_VERSION,
        model_name=model_name,
        model_family=model_family,
    )
    cache_key = compute_l1_cache_key(fingerprint)
    cache = load_llm_cache_index(cache_path)
    sampling = get_l1_sampling_config(
        chunk_index,
        experimental_temperature_schedule=experimental_temperature_schedule,
    )
    return {
        "execution_mode": "dry_run_no_api",
        "api_calls_made": 0,
        "paper_id": paper_id,
        "chunk_id": chunk_id,
        "chunk_hash": chunk_hash,
        "domain_id": selected_domain,
        "prompt_profile_id": profile.profile_id,
        "prompt_version": compiled.prompt_version,
        "compiled_prompt_hash": compiled.compiled_prompt_hash,
        "output_schema_version": compiled.output_schema_version,
        "extraction_policy_version": DEFAULT_L1_POLICY_VERSION,
        "model_name": model_name,
        "model_family": model_family,
        "temperature": sampling.temperature,
        "top_p": sampling.top_p,
        "max_retries": sampling.max_retries,
        "experimental_temperature_schedule": sampling.experimental_temperature_schedule,
        "context_slots": list(profile.context_slots),
        "prompt_fingerprint": fingerprint.model_dump(),
        "cache_key": cache_key,
        "cache_compatible": cache_key in cache.get("entries", {}),
        "would_extract": cache_key not in cache.get("entries", {}),
    }


def run_legacy_extraction() -> None:
    """Refuse implicit API execution from the package boundary."""

    raise RuntimeError(
        "Legacy API execution is not connected to L1 v2. Use the dry-run CLI; "
        "an explicit reviewed API adapter is still required."
    )


def execute_l1_extraction(
    chunks: list[dict[str, Any]],
    *,
    repository_root: str = ".",
    execute: bool = False,
    api: bool = False,
    client: Any | None = None,
    domain: str | None = None,
    auto_domain: bool = True,
    prompt_profile: str | None = None,
    prompt_version: str = "2.0",
    schema_version: str = DEFAULT_L1_SCHEMA_VERSION,
    model_name: str = DEFAULT_L1_MODEL_NAME,
    model_family: str = DEFAULT_L1_MODEL_FAMILY,
    experimental_temperature_schedule: bool = False,
) -> dict[str, Any]:
    """Execute chunk extraction only when both execute and api are explicit."""

    from pathlib import Path
    import json

    root = Path(repository_root)
    result = {"chunks_reused": [], "chunks_extracted": [], "extraction_needed": [], "errors": [], "api_calls_made": 0}
    active_client = client
    if execute and api and active_client is None:
        from code_engine.extraction.deepseek_client import DeepSeekClient
        active_client = DeepSeekClient()
    legacy_by_paper: dict[str, list[dict[str, Any]]] = {}
    for index, chunk in enumerate(chunks):
        text = str(chunk.get("content") or chunk.get("text") or "")
        paper_id = str(chunk.get("paper_id") or "UNKNOWN")
        chunk_id = str(chunk.get("chunk_id") or f"chunk_{index}")
        plan = build_l1_dry_run_plan(
            text, paper_id=paper_id, chunk_id=chunk_id, chunk_index=index,
            domain=domain, auto_domain=auto_domain, prompt_profile=prompt_profile,
            prompt_version=prompt_version, schema_version=schema_version,
            model_name=model_name, model_family=model_family,
            experimental_temperature_schedule=experimental_temperature_schedule,
            cache_path=str(root / "data/index/llm_cache_index.json"),
        )
        if plan["cache_compatible"]:
            result["chunks_reused"].append({"paper_id": paper_id, "chunk_id": chunk_id, "cache_key": plan["cache_key"]})
            continue
        if not (execute and api):
            result["extraction_needed"].append({"paper_id": paper_id, "chunk_id": chunk_id, "prompt_fingerprint": plan["prompt_fingerprint"]})
            continue
        try:
            profile = default_prompt_registry().get_profile(plan["prompt_profile_id"])
            compiled = compile_l1_prompt(profile, text, prompt_version=prompt_version, output_schema_version=schema_version)
            response = active_client.extract_json(
                compiled.text, model=model_name, temperature=plan["temperature"],
                top_p=plan["top_p"], timeout=60,
            )
            result["api_calls_made"] += 1
            claims_payload = response.get("claims") or response.get("causal_tuples") or []
            if not isinstance(claims_payload, list):
                raise ValueError("L1 response must contain a claims list")
            chunk_outputs = []
            for claim_index, raw_claim in enumerate(claims_payload):
                sign = raw_claim.get("direct_relation_sign", raw_claim.get("relation_sign", "unknown"))
                if isinstance(sign, int):
                    sign = {1: "positive", -1: "negative", 0: "neutral_or_association"}.get(sign, "unknown")
                context = dict(raw_claim.get("context") or {})
                claim = L1ExtractedClaim(
                    claim_id=str(raw_claim.get("claim_id") or f"{paper_id}_{chunk_id}_{claim_index}"),
                    paper_id=paper_id, chunk_id=chunk_id, chunk_hash=plan["chunk_hash"],
                    domain_id=plan["domain_id"], prompt_profile_id=plan["prompt_profile_id"],
                    prompt_version=prompt_version, output_schema_version=schema_version,
                    extraction_policy_version=plan["extraction_policy_version"],
                    model_name=model_name, model_family=model_family,
                    compiled_prompt_hash=compiled.compiled_prompt_hash,
                    subject_raw=str(raw_claim.get("subject_raw") or raw_claim.get("subject") or ""),
                    subject_type=str(raw_claim.get("subject_type") or "unknown"),
                    relation_raw=str(raw_claim.get("relation_raw") or ""),
                    relation_family=str(raw_claim.get("relation_family") or "unknown"),
                    direct_relation_sign=sign,
                    object_raw=str(raw_claim.get("object_raw") or raw_claim.get("object") or ""),
                    object_type=str(raw_claim.get("object_type") or "unknown"),
                    evidence_sentence=str(raw_claim.get("evidence_sentence") or ""),
                    evidence_quote=str(raw_claim.get("evidence_quote") or raw_claim.get("evidence_sentence") or ""),
                    section=str(raw_claim.get("section") or chunk.get("section") or ""),
                    statement_type=raw_claim.get("statement_type", "unknown"),
                    evidence_type=raw_claim.get("evidence_type", "unknown"),
                    confidence=float(raw_claim.get("confidence", 0.0)),
                    negated=bool(raw_claim.get("negated", False)), speculative=bool(raw_claim.get("speculative", False)),
                    subject_span=str(raw_claim.get("subject_span") or ""), relation_span=str(raw_claim.get("relation_span") or ""), object_span=str(raw_claim.get("object_span") or ""),
                    context_spans=dict(raw_claim.get("context_spans") or {}),
                    **{field: str(raw_claim.get(field) or context.get(field) or "") for field in (
                        "species", "sex", "age", "disease_model", "brain_region", "cell_type", "treatment", "dose", "route", "treatment_duration", "time_after_treatment", "assay_or_readout", "behavioral_assay", "clinical_outcome", "genotype", "oxygen_condition", "localization"
                    )},
                )
                suffix = "" if claim_index == 0 else f"_{claim_index}"
                output = root / f"data/processed/l1_v2/{paper_id}_{chunk_id}_claim{suffix}.json"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(claim.model_dump_json(indent=2), encoding="utf-8")
                chunk_outputs.append(output)
                legacy_by_paper.setdefault(paper_id, []).append(l1_claim_to_legacy_tuple(claim))
                result["chunks_extracted"].append({"paper_id": paper_id, "chunk_id": chunk_id, "claim_id": claim.claim_id, "output_path": str(output.relative_to(root))})
            if chunk_outputs:
                record_cached_extraction(plan["cache_key"], str(chunk_outputs[0]), {"prompt_fingerprint": plan["prompt_fingerprint"]}, path=root / "data/index/llm_cache_index.json")
        except Exception as exc:
            result["errors"].append({"paper_id": paper_id, "chunk_id": chunk_id, "error": str(exc)})
    for paper_id, tuples in legacy_by_paper.items():
        path = root / f"data/processed/l1/{paper_id}_extracted.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"asset_id": paper_id, "chunks_extracted": [{"chunk_index": 0, "raw_samples": [{"causal_tuples": tuples}]}]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
