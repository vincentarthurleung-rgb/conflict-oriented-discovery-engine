"""Fulltext L1 v2 extraction without canonicalization or formal-science decisions."""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.extraction.deepseek_client import DeepSeekExtractionError, JSONExtractionResult
from code_engine.fulltext.fulltext_l1_extractor import (
    CHUNKER_VERSION, SECTION_WEIGHTS, _jsonl, _shared_cache_enabled_for_run,
    chunk_text, classify_section, select_sections,
)
from code_engine.schemas.fulltext_observation import FulltextL1V2Response, measurement_dimension_values

SCHEMA_VERSION = "fulltext_l1_experimental_observation_schema_v2"
PROMPT_VERSION = "fulltext_experimental_observation_prompt_v3_json_bounded"
PARSER_VERSION = "fulltext_experimental_observation_parser_v3_transport_boundary"
EXTRACTOR_VERSION = "fulltext_l1_extractor_v2"
DEFAULT_MAX_TOKENS = 32_768
MIN_MAX_TOKENS = 1_024
MAX_MAX_TOKENS = 131_072
DUPLICATE_RULE_VERSION = "fulltext_observation_duplicates_v1"
SPLIT_VERSION = "fulltext_block_split_v1"
MAX_SPLIT_DEPTH = 1
OVERSIZED_RAW_RESPONSE_CHARS = 180_000
DEFAULT_SAFE_INPUT_TOKENS = 6_000
DEFAULT_OBSERVATION_LIMIT = 40
MAX_CHILDREN_PER_PARENT = 48
MINIMUM_CHILD_INPUT_TOKENS = 80
TOKEN_ESTIMATOR_VERSION = "conservative_unicode_chars_v1"
PROMPT_RULES = (
    "Use only the supplied full-text block. External biological knowledge is forbidden.",
    "Seeds locate text only; never confirm them merely because they were supplied.",
    "Do not treat experimental group labels, samples, biopsies, or silenced cells as natural-state causal entities.",
    "Keep observed outcome separate from author interpretation and any derived causal interpretation.",
    "Bind every material fact to an exact evidence span; use null/unknown when absent.",
    "Multiple endpoints from one experiment are separate observations sharing experiment_id and evidence_family_id.",
    "Split different experiments or comparisons even when they occur in one sentence or paragraph.",
    "Preserve rescue, re-expression, secondary, and combination interventions as hierarchical fields.",
    "Label background/review statements separately from experiments performed in the current paper.",
    "Never output canonical IDs, final entity acceptance, derived causal sign, final formal relation, strict-core eligibility, conflict, or hypothesis decisions.",
    "Species/model/method context may only bind from this experiment block; Methods context from another experiment must not be imported.",
    "Required nested objects are provenance, experiment, intervention, measurement, observation, author_interpretation, and candidate_relation.",
    "Extract only observations directly supported by this experiment block and never repeat an observation.",
    "Use the shortest original supporting span sufficient for the fields; never copy whole Results or Methods sections.",
    "Do not repeat one span in unnecessary fields. Keep distinct endpoints separate without semantic duplication.",
    "If no qualifying observation exists, return a valid JSON object with an empty experimental_observations array.",
)

_BLOCK_RESPONSE_ERROR_KINDS = {"malformed_json", "schema_parse_failure", "empty_json_content", "output_truncated"}

_MEASUREMENT_ALIASES = {
    "protein_level": "abundance_expression", "protein_expression": "abundance_expression",
    "mrna_expression": "abundance_expression", "mrna_level": "abundance_expression",
    "gene_expression": "abundance_expression", "phosphorylation_level": "phosphorylation",
    "phospho_status": "phosphorylation", "phosphorylated": "phosphorylation",
    "activation_level": "activation_activity", "pathway_activation": "activation_activity",
    "cell_survival": "viability", "proliferative_capacity": "proliferation",
}


def _cause_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = getattr(current, "cause", None) or current.__cause__
    return chain


def _deepseek_block_error_kind(exc: DeepSeekExtractionError) -> str | None:
    """Return only safely recoverable, response-local classifications."""
    explicit = str(getattr(exc, "error_kind", "") or "")
    if explicit in _BLOCK_RESPONSE_ERROR_KINDS:
        return explicit
    if explicit not in {"", "unknown"}:
        return None
    chain = _cause_chain(exc)
    if any(isinstance(item, json.JSONDecodeError) for item in chain):
        return "malformed_json"
    for item in chain:
        error_type = str(getattr(item, "error_type", "") or "")
        if error_type == "json_parse_failed":
            return "malformed_json"
        if error_type in {"response_not_object", "schema_parse_failed", "schema_validation_failed"}:
            return "schema_parse_failure"
    # Compatibility for older serialized/wrapped DeepSeek failures. Keep this
    # deliberately narrow; auth/configuration wording never qualifies.
    message = str(exc)
    if re.search(r"Unterminated string starting at:|Expecting (?:value|property name|',' delimiter)|JSONDecodeError|unexpected (?:end of (?:JSON|input)|EOF)", message, re.IGNORECASE):
        return "malformed_json"
    return None


def _json_position(exc: BaseException) -> dict[str, int | None]:
    for item in _cause_chain(exc):
        if isinstance(item, json.JSONDecodeError):
            return {"json_line": item.lineno, "json_column": item.colno, "json_character_position": item.pos}
    match = re.search(r"line\s+(\d+)\s+column\s+(\d+)\s+\(char\s+(\d+)\)", str(exc), re.IGNORECASE)
    return {"json_line": int(match.group(1)), "json_column": int(match.group(2)), "json_character_position": int(match.group(3))} if match else {"json_line": None, "json_column": None, "json_character_position": None}


def _response_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def _usage_value(usage: dict[str, Any], *keys: str) -> Any:
    return next((usage[key] for key in keys if usage.get(key) is not None), None)


def _cached_tokens(usage: dict[str, Any]) -> Any:
    return _usage_value(usage, "cached_tokens", "prompt_cache_hit_tokens") or (usage.get("prompt_tokens_details") or {}).get("cached_tokens")


def _redact(value: Any) -> str:
    text = _response_text(value)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|token|secret)\s*[:=]\s*[\"']?)[^\s,\"'}]+", r"\1[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    return text


def _hash(value: Any) -> str:
    payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def prompt_hash() -> str:
    return _hash({"version": PROMPT_VERSION, "schema": SCHEMA_VERSION, "rules": PROMPT_RULES,
                  "context_binding_order": "evidence_span>experiment_result_block>figure_or_table>linked_methods>subsection>paper_metadata>abstract_prior"})


def build_prompt(candidate: dict[str, Any], block: dict[str, Any]) -> str:
    """Strict experimental-observation extraction prompt v2 (identity-bearing template)."""
    seed = {
        "case_id": candidate.get("case_id"),
        "subject_seed": candidate.get("subject"),
        "object_seed": candidate.get("object"),
        "abstract_observation_ids": candidate.get("abstract_observation_ids", []),
    }
    rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(PROMPT_RULES, 1))
    dimensions = json.dumps(list(measurement_dimension_values()), ensure_ascii=False)
    example = json.dumps({"schema_version": SCHEMA_VERSION, "experimental_observations": []}, ensure_ascii=False)
    return f"""Extract experimental observations from the supplied full-text block.
Return exactly one JSON object and nothing else. Do not use Markdown code fences or add text before or after the JSON object.
Complete minimal JSON output example: {example}
Allowed measurement_dimension JSON string values: {dimensions}. If none applies, output "unknown".
Never invent a new measurement_dimension label, and do not put an assay name, unit, or measured entity in measurement_dimension.
Rules:
{rules}
TARGET_PRIOR (non-authoritative): {json.dumps(seed, ensure_ascii=False)}
PAPER_METADATA: {json.dumps(block['paper_metadata'], ensure_ascii=False)}
CONTEXT_BINDING_ORDER: evidence_span > experiment_result_block > figure_or_table > linked_methods > subsection > paper_metadata > abstract_prior
FULLTEXT_BLOCK:
{block['text']}"""


def resolve_max_tokens(value: int | str | None = None) -> int:
    """Resolve explicit Fulltext L1 output budget with fail-fast bounds."""
    raw = value if value is not None else os.getenv("FULLTEXT_L1_V2_MAX_TOKENS", DEFAULT_MAX_TOKENS)
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("fulltext_l1_v2 max_tokens must be an integer") from exc
    if not MIN_MAX_TOKENS <= parsed <= MAX_MAX_TOKENS:
        raise ValueError(f"fulltext_l1_v2 max_tokens must be between {MIN_MAX_TOKENS} and {MAX_MAX_TOKENS}")
    return parsed


@dataclass(frozen=True)
class FulltextTokenBudget:
    max_tokens: int = DEFAULT_MAX_TOKENS
    model_context_limit: int = 131_072
    model_maximum_output: int = 384_000
    safe_input_tokens: int = DEFAULT_SAFE_INPUT_TOKENS
    safety_margin: int = 4_096
    observation_limit: int = DEFAULT_OBSERVATION_LIMIT
    max_split_depth: int = MAX_SPLIT_DEPTH
    minimum_child_input_tokens: int = MINIMUM_CHILD_INPUT_TOKENS
    maximum_children_per_parent: int = MAX_CHILDREN_PER_PARENT
    maximum_recovery_calls_per_parent: int = MAX_CHILDREN_PER_PARENT


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer estimate; it is always labelled as an estimate."""
    # CJK characters tend toward one token each; Latin prose is conservatively
    # estimated at one token per three characters.
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    return cjk + (max(0, len(text) - cjk) + 2) // 3


def token_budget_preflight(candidate: dict[str, Any], block: dict[str, Any],
                           budget: FulltextTokenBudget) -> dict[str, Any]:
    prompt = build_prompt(candidate, block)
    text = str(block.get("text") or "")
    setup = "\n".join(re.findall(r"(?m)^PRECEDING_SETUP:.*(?:\n(?!CURRENT_|LINKED_METHODS:).*)*", text))
    methods = "\n".join(re.findall(r"(?m)^LINKED_METHODS:.*(?:\n(?!CURRENT_|PRECEDING_SETUP:).*)*", text))
    block_body = re.sub(r"(?ms)^PRECEDING_SETUP:.*?(?=^CURRENT_|\Z)|^LINKED_METHODS:.*", "", text)
    fixed_prompt = prompt.replace(text, "")
    system_tokens = estimate_tokens(fixed_prompt)
    body_tokens = estimate_tokens(block_body)
    setup_tokens = estimate_tokens(setup)
    methods_tokens = estimate_tokens(methods)
    input_estimate = system_tokens + body_tokens + setup_tokens + methods_tokens
    figure_hints = sorted(set(re.findall(r"(?i)\b(?:fig(?:ure)?|table)\s*[A-Z]?\d+[A-Za-z]?", block_body)))
    estimated_observations = max(1, len(figure_hints), len(re.findall(r"[↑↓]|(?i:\b(?:increased|decreased|reduced|induced|inhibited|promoted|suppressed)\b)", block_body)))
    reasons = []
    if input_estimate > budget.safe_input_tokens:
        reasons.append("safe_input_budget_exceeded")
    if len(figure_hints) > 1:
        reasons.append("multiple_figure_or_experiment_units")
    if estimated_observations > budget.observation_limit:
        reasons.append("estimated_observation_limit_exceeded")
    total = input_estimate + budget.max_tokens + budget.safety_margin
    decision = "split_before_provider_call" if reasons else "execute_as_is"
    if budget.max_tokens > budget.model_maximum_output or total > budget.model_context_limit:
        decision = "reject_invalid_configuration"
        reasons.append("model_budget_exceeded")
    return {
        "block_id": block.get("block_id"), "input_token_estimate": input_estimate,
        "system_prompt_token_estimate": input_estimate, "user_prompt_token_estimate": 0,
        "block_body_token_estimate": body_tokens, "setup_context_token_estimate": setup_tokens,
        "linked_methods_token_estimate": methods_tokens,
        "json_schema_instruction_token_estimate": estimate_tokens(fixed_prompt),
        "requested_output_token_budget": budget.max_tokens, "total_context_budget": total,
        "model_context_limit": budget.model_context_limit,
        "model_maximum_output_limit": budget.model_maximum_output,
        "safety_margin": budget.safety_margin, "preflight_decision": decision,
        "preflight_reasons": reasons, "estimated_observation_count": estimated_observations,
        "figure_experiment_hints": figure_hints, "token_estimator": TOKEN_ESTIMATOR_VERSION,
        "values_are_estimates": True,
    }


def deterministic_child_blocks(parent: dict[str, Any], *, reason: str,
                               budget: FulltextTokenBudget) -> list[dict[str, Any]]:
    """Partition on figure/paragraph/sentence boundaries, never string midpoints."""
    text = str(parent.get("text") or "")
    setup_lines = [x for x in text.splitlines() if x.startswith("PRECEDING_SETUP:")]
    method_lines = [x for x in text.splitlines() if x.startswith("LINKED_METHODS:")]
    body_lines = [x for x in text.splitlines() if not x.startswith(("PRECEDING_SETUP:", "LINKED_METHODS:"))]
    body = "\n".join(body_lines)
    boundary = r"\n\s*\n+|(?=(?i:\b(?:Fig(?:ure)?|Table)\s*[A-Z]?\d+[A-Za-z]?\b|\bexperiment\s*\d+\b|\b(?:human|murine|mice|mouse|rat|patient)\b))"
    units = [x.strip() for x in re.split(boundary, body) if x.strip()]
    if len(units) == 1 and estimate_tokens(units[0]) > budget.safe_input_tokens:
        units = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", units[0]) if x.strip()]
    groups: list[list[str]] = []
    current: list[str] = []
    for unit in units:
        hard_boundary = bool(re.match(r"(?i)^(?:Fig(?:ure)?|Table)\s*[A-Z]?\d+|experiment\s*\d+|human\b|murine\b|mice\b|mouse\b|rat\b|patient\b", unit))
        if hard_boundary and current:
            groups.append(current); current = []
        proposed = " ".join([*current, unit])
        if current and estimate_tokens(proposed) > max(budget.minimum_child_input_tokens, budget.safe_input_tokens // 2):
            groups.append(current); current = []
        current.append(unit)
    if current:
        groups.append(current)
    if len(groups) > budget.maximum_children_per_parent:
        return []
    if len(groups) < 2 and len(units) > 1:
        midpoint = max(1, len(units) // 2)
        groups = [units[:midpoint], units[midpoint:]]
    children = []
    for index, group in enumerate(groups):
        child_text = "\n".join([*setup_lines, " ".join(group), *method_lines])
        child_id = f"{parent['block_id']}__split_{SPLIT_VERSION}_{index:02d}"
        child = deepcopy(parent)
        child.update({
            "block_id": child_id, "parent_block_id": parent["block_id"],
            "child_block_id": child_id, "split_index": index, "split_count": len(groups),
            "split_reason": reason, "split_strategy": "figure_paragraph_sentence_budget",
            "split_strategy_version": SPLIT_VERSION, "split_depth": int(parent.get("split_depth", 0)) + 1,
            "inherited_setup_blocks": setup_lines, "inherited_methods_blocks": method_lines,
            "source_span_ranges": [],
            "species_experiment_boundary_hints": sorted(set(re.findall(r"(?i)\b(?:human|mouse|mice|murine|rat|patient|experiment\s*\d+)\b", " ".join(group)))),
            "text": child_text, "chunk_hash": _hash({"parent": parent["chunk_hash"], "version": SPLIT_VERSION, "index": index, "text": child_text}),
        })
        children.append(child)
    return children


def _alias_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _normalize_measurements(payload: dict[str, Any], audit: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    rows = normalized.get("experimental_observations")
    if not isinstance(rows, list):
        return normalized
    allowed = set(measurement_dimension_values())
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("measurement"), dict):
            continue
        raw = row["measurement"].get("measurement_dimension")
        if raw in allowed:
            continue
        key = _alias_key(raw)
        canonical = _MEASUREMENT_ALIASES.get(key)
        entry = {
            "observation_id": row.get("observation_id"), "observation_index": index,
            "measurement_dimension_raw": raw, "measurement_dimension_normalized": canonical,
            "status": "canonicalized" if canonical else "rejected",
            "mapping_rule": f"measurement_dimension_aliases_v1:{key}" if canonical else None,
            "reason": "whitelisted_alias" if canonical else "measurement_dimension_alias_not_whitelisted",
        }
        audit.append(entry)
        if canonical:
            row["measurement"]["measurement_dimension"] = canonical
    return normalized


def split_transport_metadata(response: Any) -> tuple[Any, dict[str, Any]]:
    """Precisely remove only the two historical transport keys."""
    if isinstance(response, JSONExtractionResult):
        return response.payload, {
            "raw_response": response.raw_response, "warnings": response.warnings,
            "finish_reason": response.finish_reason, "usage": response.usage,
            "attempt_count": response.attempt_count, **response.provider_metadata,
        }
    if not isinstance(response, dict):
        return response, {}
    payload = dict(response)
    warnings = payload.pop("__json_warnings", [])
    raw = payload.pop("__json_raw_response", None)
    return payload, {"warnings": warnings if isinstance(warnings, list) else [str(warnings)], "raw_response": raw}


def parse_response(response: Any, *, normalization_audit: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    response, _ = split_transport_metadata(response)
    if isinstance(response, str):
        response = json.loads(response)
    audit = normalization_audit if normalization_audit is not None else []
    normalized = _normalize_measurements(response, audit) if isinstance(response, dict) else response
    validated = FulltextL1V2Response.model_validate(normalized)
    return [row.model_dump(mode="json") for row in validated.experimental_observations]


def cache_key(*, source_fulltext_hash: str, chunk_hash: str, provider: str, model: str,
              config_hash: str, candidate_prior_hash: str) -> str:
    return _hash({
        "source_fulltext_hash": source_fulltext_hash, "chunk_hash": chunk_hash,
        "prompt_hash": prompt_hash(), "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION, "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION, "relevant_config_hash": config_hash,
        "provider": provider, "model": model, "candidate_prior_hash": candidate_prior_hash,
    })


def build_experiment_blocks(article: dict[str, Any], paper: dict[str, Any], *, max_sections: int,
                            max_chars: int, max_chunks: int) -> list[dict[str, Any]]:
    sections = select_sections(article, max_sections=max_sections)
    all_sections = list(article.get("sections") or [])
    methods = [s for s in all_sections if "method" in str(s.get("section_title") or "").casefold()]
    blocks: list[dict[str, Any]] = []
    for section in sections:
        index = int(section.get("section_index") or 0)
        previous = all_sections[index - 1] if index > 0 else {}
        setup = str(previous.get("text") or "")[-1200:] if "result" in str(section.get("section_title") or "").casefold() else ""
        linked_methods = []
        section_tokens = {x.casefold() for x in str(section.get("text") or "").split() if len(x) > 5}
        for method in methods:
            overlap = section_tokens & {x.casefold() for x in str(method.get("text") or "").split() if len(x) > 5}
            if len(overlap) >= 2:
                linked_methods.append(str(method.get("text") or "")[:1000])
        for chunk_index, chunk in enumerate(chunk_text(str(section.get("text") or ""), max_chars)):
            text = "\n".join(x for x in (f"PRECEDING_SETUP: {setup}" if setup else "", f"CURRENT_{classify_section(str(section.get('section_title') or '')).upper()}: {chunk}", *(f"LINKED_METHODS: {x}" for x in linked_methods[:1])) if x)
            blocks.append({
                "block_id": f"{paper.get('pmcid')}_{index}_{chunk_index}", "section": section,
                "text": text, "chunk_hash": _hash(text),
                "paper_metadata": {k: paper.get(k) for k in ("paper_id", "pmid", "pmcid", "title")},
                "context_sources": ["current_evidence_span", "same_result_block"] + (["preceding_experimental_setup"] if setup else []) + (["linked_methods"] if linked_methods else []),
            })
            if len(blocks) >= max_chunks:
                return blocks
    return blocks


def observation_as_legacy_claim(row: dict[str, Any]) -> dict[str, Any]:
    """Explicit compatibility adapter; it never invents canonical or formal decisions."""
    rel = row.get("candidate_relation") or {}; prov = row.get("provenance") or {}
    obs = row.get("observation") or {}; exp = row.get("experiment") or {}; intervention = row.get("intervention") or {}; measurement = row.get("measurement") or {}
    spans = prov.get("evidence_spans") or []
    return {
        "claim_id": row.get("observation_id"), "observation_id": row.get("observation_id"),
        "source_scope": "full_text", "schema_version": SCHEMA_VERSION,
        "paper_id": prov.get("paper_id"), "pmid": prov.get("pmid"), "pmcid": prov.get("pmcid"),
        "section_title": prov.get("section"), "section_type": classify_section(str(prov.get("section") or "")),
        "subject": rel.get("subject_mention"), "subject_raw": rel.get("subject_mention"), "predicate": rel.get("relation_raw"),
        "object": rel.get("object_mention"), "object_raw": rel.get("object_mention"), "relation_raw": rel.get("relation_raw"),
        "polarity": rel.get("lexical_direction", "unclear"), "direction": rel.get("lexical_direction", "unclear"),
        "relation_family": rel.get("evidence_design_candidate"), "evidence_sentence": " ".join(str(x.get("text") or "") for x in spans),
        "context": {k: exp.get(k) for k in ("species", "model_system", "cell_line", "cell_type", "tissue", "disease_model", "genotype", "localization")},
        "experiment_id": exp.get("experiment_id"), "evidence_family_id": exp.get("evidence_family_id"),
        "intervention_target": intervention.get("intervention_target_mention"), "intervention_type": intervention.get("intervention_type"),
        "intervention_sign": intervention.get("intervention_sign"), "observed_outcome_sign": obs.get("observed_outcome_sign"),
        "observed_result": obs.get("observed_result"), "measurement_dimension": measurement.get("measurement_dimension"),
        "measured_entity": measurement.get("measured_entity_mention") or measurement.get("outcome_mention"),
        "evidence_design": rel.get("evidence_design_candidate"),
        "linked_abstract_observation_ids": [row.get("source_abstract_observation_id")] if row.get("source_abstract_observation_id") else [],
        "extraction_warnings": list(row.get("extraction_warnings") or []) + ["v2_compatibility_adapter_no_formal_decisions"],
        "fulltext_l1_v2_observation": row,
    }


def _plain(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _first(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    return next((mapping[key] for key in keys if mapping.get(key) not in (None, "", [], {})), None)


def migrate_historical_observation(row: dict[str, Any], *, record: dict[str, Any],
                                   source_hash: str, index: int,
                                   audit: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically project an already-paid legacy-shaped row into v2.

    This migration copies source fields and classifies controlled vocabularies;
    it performs no provider call and creates no canonical/formal decisions.
    """
    prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    exp = row.get("experiment") if isinstance(row.get("experiment"), dict) else {}
    intervention = row.get("intervention") if isinstance(row.get("intervention"), dict) else {}
    measurement = row.get("measurement") if isinstance(row.get("measurement"), dict) else {}
    observation = row.get("observation") if isinstance(row.get("observation"), dict) else {"observed_outcome": row.get("observation")}
    interpretation = row.get("author_interpretation") if isinstance(row.get("author_interpretation"), dict) else {"interpretation": row.get("author_interpretation")}
    relation = row.get("candidate_relation") if isinstance(row.get("candidate_relation"), dict) else {}
    evidence = _first(prov, "evidence_span", "evidence_span_text", "source_text", "experiment_result_block", "experiment_result_block_text", "text_source")
    if isinstance(prov.get("evidence_spans"), list) and prov["evidence_spans"]:
        first_span = prov["evidence_spans"][0]
        evidence = first_span.get("text") if isinstance(first_span, dict) else first_span
    evidence = _plain(evidence) or _plain(_first(observation, "observed_outcome", "outcome", "result", "description", "statement", "text", "raw_text")) or _plain(row.get("evidence_span")) or "Historical model response did not isolate a shorter evidence span."
    raw_dimension = _plain(_first(measurement, "measurement_dimension", "type", "measurement_type", "measure_type", "endpoint_type", "readout_type")) or "unknown"
    dimension_key = _alias_key(raw_dimension)
    dimension = _MEASUREMENT_ALIASES.get(dimension_key)
    if not dimension:
        rules = (("phosph", "phosphorylation"), ("activ", "activation_activity"), ("local", "localization"),
                 ("viab", "viability"), ("survival", "viability"), ("prolifer", "proliferation"),
                 ("migrat", "migration"), ("invas", "invasion"), ("apop", "apoptosis"),
                 ("metasta", "metastasis"), ("resistan", "drug_response_resistance"),
                 ("expression", "abundance_expression"), ("abundance", "abundance_expression"),
                 ("mrna", "abundance_expression"), ("protein", "abundance_expression"),
                 ("pathway", "pathway_output"), ("marker", "morphology_marker_panel"))
        dimension = next((canonical for needle, canonical in rules if needle in dimension_key), "unknown")
    exp_type = (_plain(_first(exp, "design_type", "experiment_type", "type", "study_type")) or "").casefold()
    design = next((value for needle, value in (("vitro", "in_vitro"), ("vivo", "in_vivo"), ("patient", "patient_sample"), ("clinical", "patient_sample"), ("comput", "computational"), ("review", "review")) if needle in exp_type), "unknown")
    intervention_text = " ".join(filter(None, [_plain(_first(intervention, "intervention_type", "type")), _plain(_first(intervention, "primary", "primary_intervention", "description", "agent", "target"))])).casefold()
    intervention_type = next((value for needle, value in (("knockout", "knockout"), ("knockdown", "knockdown"), ("silenc", "silencing"), ("inhibit", "inhibition"), ("deplet", "depletion"), ("mutat", "mutation"), ("overexpress", "overexpression"), ("activat", "activation"), ("agon", "agonism"), ("rescue", "rescue"), ("re-expression", "re_expression"), ("drug", "drug_treatment"), ("compound", "drug_treatment"), ("treat", "drug_treatment")) if needle in intervention_text), "observational_no_intervention" if not intervention_text else "unknown")
    observed_text = _plain(_first(observation, "observed_result", "observed_outcome", "outcome", "result", "description", "effect", "statement", "text", "raw_text", "material_fact")) or evidence
    direction_text = (_plain(_first(observation, "direction", "observation_direction", "effect_direction", "change", "observed_change")) or "").casefold()
    sign = -1 if any(x in direction_text for x in ("decreas", "reduc", "down", "inhibit", "suppress")) else 1 if any(x in direction_text for x in ("increas", "up", "promot", "induc", "enhanc")) else None
    lexical = "negative" if sign == -1 else "positive" if sign == 1 else "unclear"
    observation_id = str(row.get("observation_id") or row.get("obs_id") or row.get("id") or f"offline_{record.get('cache_key','unknown')[:16]}_{index:03d}")
    experiment_id = str(row.get("experiment_id") or exp.get("experiment_id") or exp.get("id") or f"exp_{record.get('block_id')}_{index:03d}")
    family_id = str(row.get("evidence_family_id") or exp.get("evidence_family_id") or prov.get("evidence_family_id") or f"family_{record.get('block_id')}_{index:03d}")
    section = _plain(_first(prov, "section", "paper_section", "evidence_section", "source_section"))
    statement_source = " ".join(filter(None, [_plain(_first(prov, "source_type", "statement_type", "observation_type")), exp_type])).casefold()
    role = "review" if "review" in statement_source else "background" if "background" in statement_source else "methods_only" if "method" in statement_source else "current_study_experiment"
    span = {"text": evidence, "span_type": "observation", "section": section}
    migrated = {
        "schema_version": SCHEMA_VERSION, "observation_id": observation_id,
        "provenance": {"paper_id": str(record.get("paper_id") or prov.get("paper_id") or "unknown"),
            "pmid": str(record.get("pmid")) if record.get("pmid") else None,
            "pmcid": str(record.get("pmcid")) if record.get("pmcid") else None,
            "source_document_id": str(record.get("pmcid") or record.get("paper_id") or "unknown"),
            "section": section, "evidence_spans": [span], "fulltext_source_hash": source_hash},
        "experiment": {"experiment_id": experiment_id, "evidence_family_id": family_id,
            "experimental_design": _plain(_first(exp, "experimental_design", "description", "experiment_description", "context")),
            "design_type": design, "model_system": _plain(_first(exp, "model_system", "model", "experimental_system", "model_name")),
            "species": _plain(_first(exp, "species", "organism", "model_organism")),
            "cell_line": _plain(_first(exp, "cell_line", "cell_lines", "cell_line_or_model", "cells")),
            "cell_type": _plain(exp.get("cell_type")), "tissue": _plain(_first(exp, "tissue", "primary_tissue")),
            "genotype": _plain(exp.get("genotype")), "treatment": _plain(_first(exp, "treatment", "condition")),
            "comparison_arm": _plain(_first(exp, "comparison", "comparison_group", "control_group")),
            "context_source": ["historical_raw_response"], "binding_confidence": 0.5},
        "intervention": {"intervention_target_mention": _plain(_first(intervention, "target", "target_entity", "target_gene", "agent", "entity", "primary")),
            "intervention_type": intervention_type, "intervention_sign": -1 if intervention_type in {"knockout", "knockdown", "silencing", "inhibition", "depletion"} else 1 if intervention_type in {"overexpression", "activation", "agonism"} else None,
            "intervention_method": _plain(_first(intervention, "method", "delivery", "description")),
            "secondary_intervention": _plain(_first(intervention, "secondary", "secondary_intervention")),
            "rescue_intervention": _plain(_first(intervention, "rescue", "rescue_intervention"))},
        "measurement": {"outcome_mention": _plain(_first(measurement, "endpoint", "outcome", "readout", "target", "measured_entity", "entity")),
            "measured_entity_mention": _plain(_first(measurement, "measured_entity", "target_entity", "entity_measured", "analyte", "target", "endpoint")),
            "measurement_dimension": dimension, "assay": _plain(_first(measurement, "assay", "assay_type", "technique")),
            "measurement_method": _plain(_first(measurement, "measurement_method", "method", "assay_method")),
            "measurement_span": span},
        "observation": {"observed_result": observed_text, "observed_outcome_sign": sign,
            "effect_size_or_magnitude": _plain(_first(observation, "effect_size", "magnitude", "quantitative_change", "value")),
            "statistical_support": _plain(_first(observation, "statistical_support", "p_value", "significance", "statistics", "statistical_significance")),
            "comparison_relation": _plain(_first(observation, "comparison", "comparator", "compared_to", "group_comparison")),
            "observation_span": span},
        "author_interpretation": {"author_interpretation": _plain(_first(interpretation, "author_interpretation", "interpretation", "interpretation_text", "statement", "text", "claim", "description")),
            "author_conclusion": _plain(_first(interpretation, "author_conclusion", "conclusion", "causal_claim"))},
        "candidate_relation": {"subject_mention": _plain(_first(relation, "subject_mention", "subject", "subject_entity", "subject_seed")),
            "object_mention": _plain(_first(relation, "object_mention", "object", "object_entity", "object_seed")),
            "relation_raw": _plain(_first(relation, "relation_raw", "relation", "relation_type", "predicate", "relation_statement")),
            "lexical_direction": lexical, "evidence_design_candidate": _plain(_first(relation, "evidence_design_candidate", "evidence_type", "type"))},
        "statement_role": role, "extraction_warnings": ["offline_historical_shape_migration_v1"],
    }
    audit.append({"block_id": record.get("block_id"), "observation_id": observation_id,
                  "status": "historical_shape_migrated", "migration_version": "fulltext_l1_v2_historical_raw_v1"})
    return migrated


def merge_child_observations(child_results: list[dict[str, Any]], required_child_ids: list[str]) -> dict[str, Any]:
    """Merge only when every required child parsed or explicitly returned empty."""
    by_id = {str(x.get("child_block_id")): x for x in child_results}
    successful = {"completed", "cache_hit", "recovered_offline_from_raw_response", "completed_empty"}
    missing_or_failed = [child_id for child_id in required_child_ids
                         if child_id not in by_id or by_id[child_id].get("status") not in successful]
    rows: list[dict[str, Any]] = []; seen: set[str] = set()
    if not missing_or_failed:
        for child_id in required_child_ids:
            for row in by_id[child_id].get("observations") or []:
                fingerprint = _hash(row)
                if fingerprint not in seen:
                    seen.add(fingerprint); rows.append(row)
    return {"parent_complete": not missing_or_failed, "observations": rows,
            "required_child_ids": required_child_ids, "failed_or_missing_child_ids": missing_or_failed,
            "dedup_rule_version": DUPLICATE_RULE_VERSION}


def run_fulltext_l1_v2_extraction(*, run_dir: Path, fulltext_candidates_path: Path, parsed_articles_dir: Path,
                                  l1_provider: str, l1_model: str, api_enabled: bool, network_enabled: bool,
                                  client: Any | None = None, dry_run: bool = False, max_papers: int = 20,
                                  max_sections_per_paper: int = 12, max_chunks_per_paper: int = 24,
                                  max_chars_per_chunk: int = 6000, max_total_chunks: int = 200,
                                  read_timeout_seconds: float = 240, max_retries: int = 1,
                                  parent_abstract_run_id: str | None = None,
                                  max_tokens: int | None = None,
                                  observation_limit: int = DEFAULT_OBSERVATION_LIMIT,
                                  safe_input_tokens: int = DEFAULT_SAFE_INPUT_TOKENS,
                                  max_split_depth: int = MAX_SPLIT_DEPTH) -> dict[str, Any]:
    run = Path(run_dir); artifacts = run / "artifacts"; cache = artifacts / "cache/fulltext_l1_v2"; cache.mkdir(parents=True, exist_ok=True)
    shared = Path("data/interim/cache/fulltext_l1_v2"); shared_enabled = _shared_cache_enabled_for_run(run)
    if shared_enabled: shared.mkdir(parents=True, exist_ok=True)
    effective_max_tokens = resolve_max_tokens(max_tokens)
    budget = FulltextTokenBudget(max_tokens=effective_max_tokens, observation_limit=int(observation_limit),
                                 safe_input_tokens=int(safe_input_tokens), max_split_depth=int(max_split_depth))
    config = {"max_sections": max_sections_per_paper, "max_chunks_per_paper": max_chunks_per_paper,
              "max_chars": max_chars_per_chunk, "max_total_chunks": max_total_chunks,
              "max_tokens": effective_max_tokens, "observation_limit": observation_limit,
              "safe_input_tokens": safe_input_tokens, "max_split_depth": max_split_depth,
              "split_version": SPLIT_VERSION, "duplicate_rule_version": DUPLICATE_RULE_VERSION}
    config_hash = _hash(config); observations: list[dict[str, Any]] = []; executions = []; bindings = []
    parser_normalization_audit: list[dict[str, Any]] = []; preflight_records: list[dict[str, Any]] = []
    duplicate_audit: list[dict[str, Any]] = []
    api_calls = actual_llm_calls = cache_hits = parse_errors = retryable_exhausted = 0
    total_blocks = completed_blocks = skipped_blocks = 0
    failed_block_ids: list[str] = []; affected_paper_ids: set[str] = set()
    recovered_block_ids: list[str] = []; newly_failed: list[str] = []; still_failed: list[str] = []
    for paper in _jsonl(Path(fulltext_candidates_path))[:max_papers]:
        article_path = Path(parsed_articles_dir) / str(paper.get("pmcid")) / "article_text.json"
        if not article_path.is_file(): continue
        source_hash = hashlib.sha256(article_path.read_bytes()).hexdigest(); article = json.loads(article_path.read_text(encoding="utf-8"))
        parents = build_experiment_blocks(article, paper, max_sections=max_sections_per_paper, max_chars=max_chars_per_chunk, max_chunks=max_chunks_per_paper)
        blocks: list[dict[str, Any]] = []
        for parent in parents:
            check = token_budget_preflight(paper, parent, budget); preflight_records.append(check)
            if check["preflight_decision"] == "reject_invalid_configuration":
                raise ValueError(f"invalid Fulltext L1 token budget for {parent['block_id']}: {check['preflight_reasons']}")
            if check["preflight_decision"] == "split_before_provider_call":
                children = deterministic_child_blocks(parent, reason=",".join(check["preflight_reasons"]), budget=budget)
                if len(children) < 2:
                    failed_block_ids.append(parent["block_id"]); parse_errors += 1
                    executions.append({"block_id": parent["block_id"], "status": "oversized_block_unresolved",
                                       "api_called": False, "preflight": check})
                    continue
                blocks.extend(children)
            else:
                blocks.append(parent)
        block_index = 0
        while block_index < len(blocks):
            block = blocks[block_index]
            if total_blocks >= max_total_chunks: break
            total_blocks += 1
            block["paper_metadata"]["fulltext_source_hash"] = source_hash
            key = cache_key(source_fulltext_hash=source_hash, chunk_hash=block["chunk_hash"], provider=l1_provider, model=l1_model, config_hash=config_hash, candidate_prior_hash=_hash({k: paper.get(k) for k in ("subject", "object", "abstract_observation_ids")}))
            paths = [cache / f"{key}.json"] + ([shared / f"{key}.json"] if shared_enabled else [])
            prior_failures = sorted(cache.glob(f"{key}.*.raw_error.json")) + sorted(cache.glob(f"{key}.raw_error.json"))
            hit = next((p for p in paths if p.is_file()), None)
            if hit is None:
                # Run-local offline recovery may have been created from an older
                # cache identity. Match only exact block/source/provider/model.
                for recovered in cache.glob("*.json"):
                    if recovered.name.endswith(".raw_error.json"):
                        continue
                    try:
                        candidate_cache = json.loads(recovered.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    bp = candidate_cache.get("block_provenance") or {}
                    if (bp.get("block_id") == block["block_id"] and
                        candidate_cache.get("source_fulltext_hash") == source_hash and
                        candidate_cache.get("provider", l1_provider) == l1_provider and
                        candidate_cache.get("model", l1_model) == l1_model):
                        hit = recovered; break
            raw_rows = []
            transport: dict[str, Any] = {}
            scientific_payload: Any = {}
            block_audit: list[dict[str, Any]] = []
            if hit:
                payload = json.loads(hit.read_text(encoding="utf-8"))
                if payload.get("schema_version") != SCHEMA_VERSION: block_index += 1; continue
                scientific_payload = payload.get("response")
                raw_rows = parse_response(scientific_payload, normalization_audit=block_audit)
                transport = dict(payload.get("transport_metadata") or {})
                cache_hits += 1; completed_blocks += 1; status = "cache_hit"
            elif dry_run or not (api_enabled and network_enabled and client is not None):
                skipped_blocks += 1
                executions.append({"block_id": block["block_id"], "parent_block_id": block.get("parent_block_id"),
                                   "status": "planned" if dry_run else "blocked", "api_called": False,
                                   "cache_key": key, "max_tokens": effective_max_tokens,
                                   "response_format": {"type": "json_object"}})
                block_index += 1; continue
            else:
                response = None
                response_received = False
                try:
                    call = getattr(client, "extract_json_result", client.extract_json)
                    response = call(build_prompt(paper, block), model=l1_model, temperature=0, top_p=1,
                                    timeout=read_timeout_seconds, max_retries=max_retries,
                                    max_tokens=effective_max_tokens)
                    response_received = True
                    scientific_payload, transport = split_transport_metadata(response)
                    api_calls += 1; actual_llm_calls += int(transport.get("attempt_count") or 1)
                    raw_rows = parse_response(scientific_payload, normalization_audit=block_audit)
                    if len(raw_rows) > observation_limit:
                        raise OverflowError(f"observation_overflow:{len(raw_rows)}>{observation_limit}")
                    status = "completed"; completed_blocks += 1
                    payload = {"schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
                               "prompt_hash": prompt_hash(), "parser_version": PARSER_VERSION,
                               "extractor_version": EXTRACTOR_VERSION, "source_fulltext_hash": source_hash,
                               "response": scientific_payload, "transport_metadata": transport,
                               "parser_normalization_audit": block_audit, "config": config,
                               "block_provenance": {k: block.get(k) for k in ("block_id", "parent_block_id", "child_block_id", "split_index", "split_count", "split_reason", "split_strategy", "split_strategy_version")}}
                    paths[0].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    if len(paths) > 1: paths[1].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except DeepSeekExtractionError as exc:
                    api_calls += 1; actual_llm_calls += int(getattr(exc, "attempts", 1) or 1)
                    error_kind = _deepseek_block_error_kind(exc)
                    if error_kind is None:
                        raise
                    response = getattr(exc, "raw_response", None)
                    parse_errors += 1; retryable_exhausted += int(error_kind != "output_truncated")
                    timestamp = datetime.now(timezone.utc).isoformat()
                    stamp = timestamp.replace(":", "").replace("+", "_").replace(".", "_")
                    raw_response_path = cache / f"{key}.{stamp}.raw_response.txt"
                    if response not in (None, ""):
                        raw_response_path.write_text(_redact(response), encoding="utf-8")
                    else:
                        raw_response_path = None
                    raw_text = _response_text(response) if response not in (None, "") else ""
                    cause = (_cause_chain(exc)[1:] or [None])[0]
                    record = {
                        "paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid"),
                        "block_id": block["block_id"], "experiment_block_index": block_index,
                        "input_character_count": len(block["text"]), "prompt_hash": prompt_hash(),
                        "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                        "extractor_version": EXTRACTOR_VERSION, "cache_key": key,
                        "provider": getattr(exc, "provider", None) or l1_provider,
                        "model": getattr(exc, "model", None) or l1_model,
                        "attempt_count": int(getattr(exc, "attempts", 1) or 1),
                        "exception_class": type(exc).__name__, "error_kind": error_kind,
                        "error_message": _redact(str(exc)),
                        "underlying_cause": None if cause is None else {"class": type(cause).__name__, "message": _redact(str(cause))},
                        "raw_response_path": str(raw_response_path) if raw_response_path else None,
                        "raw_response_character_count": len(raw_text),
                        "finish_reason": getattr(exc, "finish_reason", None),
                        "usage": getattr(exc, "usage", {}) or {}, "max_tokens": effective_max_tokens,
                        "configured_max_tokens": effective_max_tokens, "effective_max_tokens": effective_max_tokens,
                        "max_tokens_parameter_source": "argument" if max_tokens is not None else "env" if os.getenv("FULLTEXT_L1_V2_MAX_TOKENS") else "default_constant",
                        "response_format": {"type": "json_object"}, "json_output_enabled": True,
                        "possible_output_truncation": getattr(exc, "finish_reason", None) == "length" or "unterminated string" in str(exc).casefold() or "unexpected eof" in str(exc).casefold(),
                        "output_truncated": error_kind == "output_truncated", "retryable": error_kind != "output_truncated",
                        "failure_timestamp": timestamp, **_json_position(exc),
                    }
                    raw_path = cache / f"{key}.{stamp}.raw_error.json"
                    raw_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    failed_block_ids.append(block["block_id"]); affected_paper_ids.add(str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid")))
                    (still_failed if prior_failures else newly_failed).append(block["block_id"])
                    executions.append({**record, "status": "parse_error", "api_called": True, "raw_error_artifact": str(raw_path), "raw_response_artifact": str(raw_response_path) if raw_response_path else None})
                    if error_kind == "output_truncated" and int(block.get("split_depth", 0)) < max_split_depth:
                        children = deterministic_child_blocks(block, reason="finish_reason_length", budget=budget)
                        if len(children) >= 2:
                            blocks[block_index + 1:block_index + 1] = children
                    block_index += 1; continue
                except (ValidationError, ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                    if not response_received:
                        raise
                    parse_errors += 1
                    timestamp = datetime.now(timezone.utc).isoformat()
                    stamp = timestamp.replace(":", "").replace("+", "_").replace(".", "_")
                    raw_response_path = cache / f"{key}.{stamp}.raw_response.txt"
                    scientific_payload, transport = split_transport_metadata(response)
                    raw_response_path.write_text(_redact(transport.get("raw_response") or scientific_payload), encoding="utf-8")
                    error_kind = "observation_overflow" if isinstance(exc, OverflowError) else "schema_parse_failure" if isinstance(exc, ValidationError) else "malformed_json"
                    record = {
                        "paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid"),
                        "block_id": block["block_id"], "experiment_block_index": block_index,
                        "input_character_count": len(block["text"]), "prompt_hash": prompt_hash(),
                        "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION,
                        "cache_key": key, "provider": l1_provider, "model": l1_model, "attempt_count": 1,
                        "exception_class": type(exc).__name__, "error_kind": error_kind,
                        "error_message": _redact(str(exc)), "underlying_cause": None,
                        "raw_response_path": str(raw_response_path), "raw_response_character_count": len(_response_text(transport.get("raw_response") or scientific_payload)),
                        "raw_response": scientific_payload, "parser_normalization_audit": block_audit,
                        "finish_reason": transport.get("finish_reason"), "usage": transport.get("usage") or {},
                        "max_tokens": effective_max_tokens, "response_format": {"type": "json_object"},
                        "possible_output_truncation": False, "observation_overflow": isinstance(exc, OverflowError),
                        "retryable": True, "failure_timestamp": timestamp, **_json_position(exc),
                    }
                    raw_path = cache / f"{key}.{stamp}.raw_error.json"
                    raw_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    parser_normalization_audit.extend(block_audit)
                    failed_block_ids.append(block["block_id"]); affected_paper_ids.add(str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid")))
                    (still_failed if prior_failures else newly_failed).append(block["block_id"])
                    executions.append({**record, "status": "parse_error", "api_called": True, "raw_error_artifact": str(raw_path), "raw_response_artifact": str(raw_response_path)})
                    if isinstance(exc, OverflowError) and int(block.get("split_depth", 0)) < max_split_depth:
                        children = deterministic_child_blocks(block, reason="observation_overflow", budget=budget)
                        if len(children) >= 2:
                            blocks[block_index + 1:block_index + 1] = children
                    block_index += 1; continue
                if prior_failures:
                    recovered_block_ids.append(block["block_id"])
            parser_normalization_audit.extend(block_audit)
            for row in raw_rows:
                row["parent_abstract_run_id"] = row.get("parent_abstract_run_id") or parent_abstract_run_id
                row["provenance"]["fulltext_source_hash"] = source_hash
                fingerprint = _hash(row)
                if any(item.get("fingerprint") == fingerprint for item in duplicate_audit):
                    duplicate_audit.append({"fingerprint": fingerprint, "block_id": block["block_id"], "status": "exact_duplicate_removed", "rule_version": DUPLICATE_RULE_VERSION})
                    continue
                duplicate_audit.append({"fingerprint": fingerprint, "block_id": block["block_id"], "status": "unique", "rule_version": DUPLICATE_RULE_VERSION})
                observations.append(row)
                bindings.append({"observation_id": row["observation_id"], "experiment_id": row["experiment"]["experiment_id"], "context_source": row["experiment"].get("context_source") or block["context_sources"], "binding_confidence": row["experiment"].get("binding_confidence", 0), "source_block_id": block["block_id"], "cross_experiment_binding": False})
            usage = transport.get("usage") or {}
            executions.append({"block_id": block["block_id"], "parent_block_id": block.get("parent_block_id"),
                "status": status, "api_called": status == "completed", "cache_key": key,
                "observation_count": len(raw_rows), "finish_reason": transport.get("finish_reason"),
                "usage": usage, "input_tokens": _usage_value(usage, "prompt_tokens", "input_tokens"),
                "output_tokens": _usage_value(usage, "completion_tokens", "output_tokens"), "total_tokens": usage.get("total_tokens"),
                "cached_tokens": _cached_tokens(usage),
                "raw_response_character_count": len(str(transport.get("raw_response") or "")),
                "parsed_json_character_count": len(json.dumps(scientific_payload, ensure_ascii=False)),
                "max_tokens": effective_max_tokens, "configured_max_tokens": effective_max_tokens,
                "effective_max_tokens": effective_max_tokens, "response_format": {"type": "json_object"},
                "json_output_enabled": True, "provider": l1_provider, "model": l1_model,
                "attempt_number": transport.get("attempt_count", 0 if status == "cache_hit" else 1),
                "http_status": transport.get("http_status"), "latency_seconds": transport.get("latency_seconds")})
            block_index += 1
    claims = [observation_as_legacy_claim(x) for x in observations]
    def write_jsonl(name: str, rows: list[dict[str, Any]]): (artifacts / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    write_jsonl("fulltext_experiment_observations.jsonl", observations); write_jsonl("fulltext_context_binding_audit.jsonl", bindings); write_jsonl("fulltext_l1_v2_execution_records.jsonl", executions)
    write_jsonl("fulltext_l1_v2_parser_normalization_audit.jsonl", parser_normalization_audit)
    write_jsonl("fulltext_l1_v2_duplicate_audit.jsonl", duplicate_audit)
    write_jsonl("fulltext_l1_v2_preflight.jsonl", preflight_records)
    write_jsonl("l35_fulltext_l1_chunks.jsonl", [{"chunk_id": x.get("block_id"), "cache_key": x.get("cache_key"), "cache_status": "hit" if x.get("status") == "cache_hit" else "miss", "api_call_made": bool(x.get("api_called")), "extraction_status": x.get("status")} for x in executions])
    write_jsonl("l35_fulltext_l1_claims.jsonl", claims)
    fields = {"species": "species", "intervention": "intervention_target_mention", "comparison": "comparison_arm", "measurement": "measurement_dimension"}
    coverage = {"schema_version": "fulltext_l1_schema_coverage_v1", "v1_record_count": 0, "v2_record_count": len(observations), "experiment_count": len({x["experiment"]["experiment_id"] for x in observations}), "observation_count": len(observations), "context_binding_coverage": sum(bool(x.get("context_source")) for x in bindings) / len(bindings) if bindings else 0.0}
    coverage.update({f"{name}_coverage": sum(bool((x["experiment"] if name in {"species", "comparison"} else x[name]).get(field)) and (x["measurement"].get(field) != "unknown" if name == "measurement" else True) for x in observations) / len(observations) if observations else 0.0 for name, field in fields.items()})
    statuses = {str(x.get("status")) for x in executions}
    l1_status = "completed_with_block_failures" if parse_errors else "completed" if observations else "planned" if dry_run else "skipped_provider_unavailable" if statuses and statuses <= {"blocked"} else "completed_no_observations"
    partial = bool(parse_errors)
    summary = {"schema_version": SCHEMA_VERSION, "fulltext_l1_status": l1_status, "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(), "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION, "source_document_count": len({x["provenance"]["source_document_id"] for x in observations}), "experiment_count": coverage["experiment_count"], "observation_count": len(observations), "api_calls_made": api_calls, "cache_hits": cache_hits, "parse_errors": parse_errors, "paid_call_count": actual_llm_calls, "network_call_count": actual_llm_calls, "download_call_count": 0, "config_hash": config_hash,
        "planned_block_count": total_blocks, "attempted_block_count": total_blocks - skipped_blocks,
        "completed_block_count": completed_blocks, "cache_hit_block_count": cache_hits,
        "actual_llm_call_count": actual_llm_calls, "parse_error_block_count": parse_errors,
        "retryable_exhausted_block_count": retryable_exhausted, "fatal_error_count": 0,
        "skipped_block_count": skipped_blocks, "generated_observation_count": len(observations),
        "failed_block_ids": failed_block_ids, "affected_paper_ids": sorted(affected_paper_ids),
        "previously_failed_now_recovered": recovered_block_ids, "still_failed": still_failed,
        "newly_failed": newly_failed, "scientific_input_complete": not partial,
        "partial_block_failures": partial,
        "json_output_enabled_count": sum(bool(x.get("json_output_enabled")) for x in executions),
        "finish_reason_distribution": dict(Counter(str(x.get("finish_reason") or "unknown") for x in executions)),
        "max_tokens_distribution": dict(Counter(str(x.get("max_tokens")) for x in executions if x.get("max_tokens") is not None)),
        "configured_max_tokens": effective_max_tokens, "effective_max_tokens": effective_max_tokens,
        "max_tokens_parameter_source": "argument" if max_tokens is not None else "env" if os.getenv("FULLTEXT_L1_V2_MAX_TOKENS") else "default_constant",
        "token_budget": asdict(budget), "token_estimator": TOKEN_ESTIMATOR_VERSION,
        "consistency_report": {
            "projection_may_continue_for_diagnosis": partial,
            "complete_scientific_run": not partial,
            "publication_allowed": not partial,
            "message": "failed blocks must be resumed/recovered before publication" if partial else "all planned scientific inputs completed",
        }}
    (artifacts / "fulltext_l1_v2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); (artifacts / "fulltext_l1_schema_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"summary": summary, "observations": observations, "claims": claims, "executions": executions,
            "parser_normalization_audit": parser_normalization_audit, "preflight": preflight_records}


def _distribution(observations: list[dict[str, Any]], *, valid_blocks: int,
                  empty_blocks: int, nonempty_blocks: int,
                  paper_block_counts: Counter[str], validation_failures: Counter[str]) -> dict[str, Any]:
    by_paper = Counter(str(x["provenance"].get("pmcid") or x["provenance"].get("paper_id")) for x in observations)
    by_section = Counter(str(x["provenance"].get("section") or "unknown") for x in observations)
    by_context = Counter(source for x in observations for source in (x["experiment"].get("context_source") or ["unknown"]))
    return {
        "schema_version": "fulltext_l1_v2_response_distribution_v1",
        "valid_json_block_count": valid_blocks, "empty_observation_response_count": empty_blocks,
        "nonempty_observation_response_count": nonempty_blocks, "observation_count": len(observations),
        "per_paper_block_count": dict(sorted(paper_block_counts.items())),
        "per_paper_observation_count": dict(sorted(by_paper.items())),
        "section_observation_count": dict(sorted(by_section.items())),
        "context_source_observation_count": dict(sorted(by_context.items())),
        "measurement_dimension_distribution": dict(sorted(Counter(x["measurement"].get("measurement_dimension") or "unknown" for x in observations).items())),
        "experiment_role_distribution": dict(sorted(Counter(x["experiment"].get("design_type") or "unknown" for x in observations).items())),
        "statement_role_distribution": dict(sorted(Counter(x.get("statement_role") or "unknown" for x in observations).items())),
        "schema_validation_failure_reasons": dict(sorted(validation_failures.items())),
    }


def recover_fulltext_l1_v2_offline(run_dir: str | Path, *, max_tokens: int | None = None) -> dict[str, Any]:
    """Reparse paid raw errors in-place with no client/network construction."""
    run = Path(run_dir); artifacts = run / "artifacts"; cache = artifacts / "cache/fulltext_l1_v2"
    if not cache.is_dir():
        raise FileNotFoundError(f"Fulltext L1 v2 cache not found: {cache}")
    effective_max_tokens = resolve_max_tokens(max_tokens)
    budget = FulltextTokenBudget(max_tokens=effective_max_tokens)
    errors = sorted(cache.glob("*.raw_error.json"))
    existing_exec_path = artifacts / "fulltext_l1_v2_execution_records.jsonl"
    existing_exec = [x for x in (_jsonl(existing_exec_path) if existing_exec_path.is_file() else [])
                     if x.get("status") != "recovered_offline_from_raw_response"]
    observations: list[dict[str, Any]] = []; bindings: list[dict[str, Any]] = []
    recovered_exec: list[dict[str, Any]] = []; normalization_audit: list[dict[str, Any]] = []
    recovered_ids: list[str] = []; unresolved_ids: list[str] = []
    paper_blocks: Counter[str] = Counter(); failures: Counter[str] = Counter()
    valid_json = schema_direct = schema_valid = empty = nonempty = raw_present = malformed = schema_invalid = 0
    oversized_records: list[dict[str, Any]] = []
    for error_path in errors:
        record = json.loads(error_path.read_text(encoding="utf-8"))
        block_id = str(record.get("block_id") or error_path.name); paper_key = str(record.get("pmcid") or record.get("paper_id") or "unknown")
        paper_blocks[paper_key] += 1
        raw_path_value = record.get("raw_response_path")
        raw_path = Path(raw_path_value) if raw_path_value else None
        if raw_path and not raw_path.is_absolute() and not raw_path.is_file():
            raw_path = Path.cwd() / raw_path
        if not raw_path or not raw_path.is_file():
            unresolved_ids.append(block_id); failures["raw_response_missing"] += 1; continue
        raw_present += 1; raw_text = raw_path.read_text(encoding="utf-8")
        try:
            raw_value = json.loads(raw_text)
        except json.JSONDecodeError:
            malformed += 1; unresolved_ids.append(block_id); failures["malformed_json"] += 1
            oversized_records.append(record); continue
        valid_json += 1
        payload, legacy_transport = split_transport_metadata(raw_value)
        rows = payload.get("experimental_observations") if isinstance(payload, dict) else None
        if isinstance(rows, list) and rows: nonempty += 1
        elif isinstance(rows, list): empty += 1
        source_hash = "unknown"
        article_path = artifacts / "fulltext/pmc_oa" / str(record.get("pmcid")) / "article_text.json"
        if article_path.is_file(): source_hash = hashlib.sha256(article_path.read_bytes()).hexdigest()
        block_audit: list[dict[str, Any]] = []
        migrated = False
        try:
            parsed = parse_response(payload, normalization_audit=block_audit); schema_direct += 1
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as direct_exc:
            if not isinstance(rows, list):
                schema_invalid += 1; unresolved_ids.append(block_id); failures[type(direct_exc).__name__] += 1; continue
            try:
                migrated_payload = {"schema_version": SCHEMA_VERSION, "experimental_observations": [
                    migrate_historical_observation(row, record=record, source_hash=source_hash, index=index, audit=block_audit)
                    for index, row in enumerate(rows) if isinstance(row, dict)]}
                parsed = parse_response(migrated_payload, normalization_audit=block_audit)
                payload = migrated_payload; migrated = True
            except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                schema_invalid += 1; unresolved_ids.append(block_id); failures[type(exc).__name__] += 1; continue
        schema_valid += 1; recovered_ids.append(block_id); normalization_audit.extend(block_audit)
        clean_rows: list[dict[str, Any]] = []; seen: set[str] = set()
        for row in parsed:
            fingerprint = _hash(row)
            if fingerprint in seen: continue
            seen.add(fingerprint); clean_rows.append(row); observations.append(row)
            bindings.append({"observation_id": row["observation_id"], "experiment_id": row["experiment"]["experiment_id"],
                "context_source": row["experiment"].get("context_source") or ["historical_raw_response"],
                "binding_confidence": row["experiment"].get("binding_confidence", 0), "source_block_id": block_id,
                "cross_experiment_binding": False, "recovered_offline_from_raw_response": True})
        success = {"schema_version": SCHEMA_VERSION, "prompt_version": record.get("prompt_version") or "historical_paid_response",
            "prompt_hash": record.get("prompt_hash"), "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION,
            "source_fulltext_hash": source_hash, "provider": record.get("provider"), "model": record.get("model"),
            "response": {"schema_version": SCHEMA_VERSION, "experimental_observations": clean_rows},
            "transport_metadata": {"raw_response_artifact": str(raw_path), "warnings": legacy_transport.get("warnings") or [],
                "finish_reason": record.get("finish_reason"), "usage": record.get("usage") or {},
                "raw_response_character_count": len(raw_text), "recovered_offline_from_raw_response": True},
            "parser_normalization_audit": block_audit,
            "block_provenance": {"block_id": block_id, "recovered_offline_from_raw_response": True,
                "historical_raw_error_artifact": str(error_path)},
            "config": {"max_tokens": effective_max_tokens, "split_version": SPLIT_VERSION,
                "duplicate_rule_version": DUPLICATE_RULE_VERSION}}
        (cache / f"{record.get('cache_key') or _hash(block_id)}.json").write_text(json.dumps(success, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        recovered_exec.append({"block_id": block_id, "paper_id": record.get("paper_id"), "pmid": record.get("pmid"),
            "pmcid": record.get("pmcid"), "status": "recovered_offline_from_raw_response", "api_called": False,
            "network_called": False, "cache_key": record.get("cache_key"), "observation_count": len(clean_rows),
            "raw_response_character_count": len(raw_text), "finish_reason": record.get("finish_reason"),
            "usage": record.get("usage") or {}, "max_tokens": None,
            "historical_request_max_tokens": None, "historical_request_max_tokens_source": "provider_default_unknown",
            "recovery_cache_identity_max_tokens": effective_max_tokens,
            "response_format": {"type": "json_object"}, "historical_shape_migrated": migrated,
            "historical_raw_error_artifact": str(error_path), "historical_raw_response_artifact": str(raw_path)})
    claims = [observation_as_legacy_claim(x) for x in observations]
    def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    write_jsonl(artifacts / "fulltext_experiment_observations.jsonl", observations)
    write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", claims)
    write_jsonl(artifacts / "fulltext_context_binding_audit.jsonl", bindings)
    write_jsonl(existing_exec_path, [*existing_exec, *recovered_exec])
    write_jsonl(artifacts / "fulltext_l1_v2_parser_normalization_audit.jsonl", normalization_audit)
    distribution = _distribution(observations, valid_blocks=valid_json, empty_blocks=empty, nonempty_blocks=nonempty,
                                 paper_block_counts=paper_blocks, validation_failures=failures)
    (artifacts / "fulltext_l1_v2_response_distribution.json").write_text(json.dumps(distribution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Fulltext L1 v2 Response Distribution", "", f"- Valid JSON blocks: {valid_json}",
          f"- Empty / non-empty blocks: {empty} / {nonempty}", f"- Recovered observations: {len(observations)}", "",
          "## Per-paper observations", ""] + [f"- {key}: {value}" for key, value in distribution["per_paper_observation_count"].items()]
    (artifacts / "fulltext_l1_v2_response_distribution.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    recovery = {"schema_version": "fulltext_l1_v2_offline_recovery_v1", "scanned_error_blocks": len(errors),
        "raw_response_present": raw_present, "valid_json_count": valid_json, "direct_schema_valid_count": schema_direct,
        "schema_valid_count": schema_valid, "schema_invalid_count": schema_invalid,
        "empty_observation_response_count": empty, "nonempty_observation_response_count": nonempty,
        "recovered_observation_count": len(observations), "recovered_legacy_claim_count": len(claims),
        "still_malformed_count": malformed, "still_schema_invalid_count": schema_invalid,
        "api_calls": 0, "network_calls": 0, "provider_clients_constructed": 0,
        "recovered_block_ids": recovered_ids, "unresolved_block_ids": unresolved_ids,
        "historical_shape_migration_count": sum(bool(x.get("historical_shape_migrated")) for x in recovered_exec)}
    (artifacts / "offline_recovery_summary.json").write_text(json.dumps(recovery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_oversized_recovery_plan(run, oversized_records, budget)
    coverage = {"schema_version": "fulltext_l1_schema_coverage_v1", "v1_record_count": 0,
        "v2_record_count": len(observations), "experiment_count": len({x["experiment"]["experiment_id"] for x in observations}),
        "observation_count": len(observations), "context_binding_coverage": sum(bool(x.get("context_source")) for x in bindings) / len(bindings) if bindings else 0.0}
    (artifacts / "fulltext_l1_schema_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old_summary_path = artifacts / "fulltext_l1_v2_summary.json"
    old_summary = json.loads(old_summary_path.read_text(encoding="utf-8")) if old_summary_path.is_file() else {}
    summary = {**old_summary, "fulltext_l1_status": "completed_with_block_failures" if unresolved_ids else "completed",
        "observation_count": len(observations), "generated_observation_count": len(observations),
        "fulltext_l1_claim_count": len(claims),
        "experiment_count": coverage["experiment_count"], "completed_block_count": schema_valid,
        "parse_errors": len(unresolved_ids), "parse_error_block_count": len(unresolved_ids),
        "failed_block_ids": unresolved_ids, "previously_failed_now_recovered": recovered_ids,
        "recovered_offline": recovered_ids, "recovered_by_provider_retry": [], "recovered_by_block_split": [],
        "still_failed": unresolved_ids, "newly_failed": [], "scientific_input_complete": not unresolved_ids,
        "partial_block_failures": bool(unresolved_ids), "offline_recovery_api_calls": 0,
        "offline_recovery_network_calls": 0, "configured_max_tokens": effective_max_tokens,
        "configured_max_tokens_applies_to_future_calls": True,
        "historical_request_max_tokens": None, "historical_request_max_tokens_source": "provider_default_unknown",
        "max_tokens_distribution": {"historical_provider_default_unknown": len(errors)},
        "json_output_enabled_count": len(errors),
        "consistency_report": {"projection_may_continue_for_diagnosis": bool(unresolved_ids),
            "complete_scientific_run": not unresolved_ids, "publication_allowed": not unresolved_ids,
            "message": "oversized block requires confirmed child recovery" if unresolved_ids else "all planned scientific inputs completed"}}
    old_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifacts / "l35_fulltext_l1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (artifacts / "l35_fulltext_retrieval_summary.json", artifacts / "l35_fulltext_conflict_confirmation_summary.json", artifacts / "pipeline_stage_summary.json"):
        if not path.is_file(): continue
        value = json.loads(path.read_text(encoding="utf-8")); target = value.get("fulltext") if isinstance(value.get("fulltext"), dict) else value
        target.update({"fulltext_l1_claim_count": len(claims), "scientific_input_complete": not unresolved_ids,
                       "partial_block_failures": bool(unresolved_ids)})
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (run / "fulltext_bridge_replay_manifest.json", artifacts / "fulltext_bridge_replay_manifest.json"):
        if not path.is_file(): continue
        value = json.loads(path.read_text(encoding="utf-8"))
        stage_summary = value.get("stage_summary") if isinstance(value.get("stage_summary"), dict) else {}
        stage_summary.update({"fulltext_l1_claim_count": len(claims), "scientific_input_complete": not unresolved_ids,
                              "partial_block_failures": bool(unresolved_ids), "fulltext_l1_status": summary["fulltext_l1_status"]})
        value["stage_summary"] = stage_summary
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"summary": recovery, "observations": observations, "claims": claims, "distribution": distribution}


def _write_oversized_recovery_plan(run: Path, records: list[dict[str, Any]], budget: FulltextTokenBudget) -> dict[str, Any]:
    artifacts = run / "artifacts"; candidates = {str(x.get("pmcid")): x for x in _jsonl(artifacts / "l35_fulltext_oa_candidate_papers.jsonl")}
    planned: list[dict[str, Any]] = []
    for record in records:
        paper = candidates.get(str(record.get("pmcid")), {"pmcid": record.get("pmcid"), "paper_id": record.get("paper_id")})
        article_path = artifacts / "fulltext/pmc_oa" / str(record.get("pmcid")) / "article_text.json"
        if not article_path.is_file(): continue
        article = json.loads(article_path.read_text(encoding="utf-8"))
        blocks = build_experiment_blocks(article, paper, max_sections=12, max_chars=6000, max_chunks=24)
        parent = next((x for x in blocks if x.get("block_id") == record.get("block_id")), None)
        if parent is None: continue
        preflight = token_budget_preflight(paper, parent, budget)
        preflight["preflight_decision"] = "split_before_provider_call"
        preflight["preflight_reasons"] = sorted(set([*preflight.get("preflight_reasons", []), "historical_finish_reason_length_oversized"]))
        children = deterministic_child_blocks(parent, reason="historical_finish_reason_length_oversized", budget=budget)
        planned.append({"paper_id": record.get("paper_id"), "pmid": record.get("pmid"), "pmcid": record.get("pmcid"),
            "parent_block_id": record.get("block_id"), "historical_finish_reason": record.get("finish_reason"),
            "historical_raw_response_character_count": record.get("raw_response_character_count"),
            "preflight": preflight, "child_count": len(children), "estimated_provider_calls": len(children),
            "children": [{**{k: child.get(k) for k in ("child_block_id", "split_index", "split_count", "split_reason", "split_strategy", "split_strategy_version", "inherited_setup_blocks", "inherited_methods_blocks", "source_span_ranges", "species_experiment_boundary_hints")},
                "input_token_estimate": token_budget_preflight(paper, child, budget)["input_token_estimate"],
                "input_character_count": len(child["text"]), "chunk_hash": child["chunk_hash"]} for child in children]})
    result = {"schema_version": "fulltext_l1_v2_oversized_recovery_plan_v1", "api_calls": 0, "network_calls": 0,
              "requires_user_confirmation_before_provider_calls": True, "parent_count": len(planned), "plans": planned}
    (artifacts / "oversized_block_recovery_plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Oversized Block Recovery Plan", "", "No provider or network calls were made.", ""]
    for item in planned:
        lines += [f"## {item['parent_block_id']}", "", f"- Child blocks: {item['child_count']}",
                  f"- Estimated provider calls after confirmation: {item['estimated_provider_calls']}",
                  f"- Historical finish reason: {item['historical_finish_reason']}", ""]
        lines += [f"- `{child['child_block_id']}`: estimated {child['input_token_estimate']} input tokens, {child['input_character_count']} characters" for child in item["children"]]
        lines.append("")
    (artifacts / "oversized_block_recovery_plan.md").write_text("\n".join(lines), encoding="utf-8")
    return result
