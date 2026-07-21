"""Claim-centered full-text reasoning traces and experimental context consolidation.

This module keeps extracted claims immutable. Reasoning traces are evidence-process
artifacts keyed by claim identity and source passages; they never become L2 claims,
formal conflict edges, or KG nodes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from code_engine.fulltext.experimental_parameters import (
    PARAMETER_CLASSIFIER_VERSION,
    ClassifiedParameter,
    extract_parameters,
    first_parameter,
)
from code_engine.integration.atlas_handoff import canonical_json, sha256_file
from code_engine.normalization.resolver import ResolverCascade
from code_engine.schemas.evidence_chain import (
    AuthorInterpretation,
    CausalDesign,
    ClaimEvidenceLink,
    Comparator,
    ConsolidatedContextValue,
    EvidenceAnchor,
    ExperimentalEvidenceChain,
    ExperimentalSystem,
    Intervention,
    Measurement,
    ObservedResult,
    UnlinkedClaimReason,
    validate_claim_evidence_references,
)

SCHEMA_VERSION = "fulltext_reasoning_trace_v2"
CONSOLIDATION_SCHEMA_VERSION = "fulltext_context_consolidation_v2"
EVIDENCE_CHAIN_SCHEMA_VERSION = "experimental_evidence_chain_v2"
CLAIM_EVIDENCE_LINK_SCHEMA_VERSION = "claim_evidence_link_v2"
PROMPT_VERSION = "fulltext_reasoning_trace_prompt_v1"
EXTRACTOR_CODE_VERSION = "fulltext_reasoning_trace_extractor_v2"
CONTEXT_RULE_VERSION = "fulltext_context_consolidation_rules_v2"
EVIDENCE_CHAIN_EXTRACTOR_VERSION = "experimental_evidence_chain_from_trace_v2"
DIRECT_EVIDENCE_CHAIN_EXTRACTOR_VERSION = "direct_fulltext_evidence_chain_extractor_v2"
CLAIM_EVIDENCE_LINKER_VERSION = "claim_evidence_linker_v2"
RETRIEVAL_CONFIG_VERSION = "claim_centered_passage_retrieval_v1"

TRACE_STATUSES = {
    "complete",
    "partial",
    "not_found",
    "unsupported_by_retrieved_passages",
    "unavailable_abstract_only",
    "extraction_failed",
}
STEP_ROLES = {
    "background_premise",
    "hypothesis",
    "experimental_intervention",
    "comparison_or_control",
    "measurement",
    "observation",
    "functional_result",
    "loss_of_function",
    "gain_of_function",
    "blocking_experiment",
    "rescue_experiment",
    "dose_response",
    "temporal_order",
    "mediation_evidence",
    "statistical_support",
    "in_vivo_validation",
    "author_interpretation",
    "alternative_explanation",
    "limitation",
    "final_conclusion",
}
CONTEXT_FIELDS = (
    "species",
    "model_system",
    "cell_type",
    "tissue",
    "disease_subtype",
    "intervention_type",
    "intervention_target",
    "control_group",
    "dose",
    "duration",
    "assay_method",
    "measured_endpoint",
    "genotype",
    "localization",
    "validation_design",
)
CLAIM_SCOPED_FIELDS = ("species", "disease_subtype", "cell_type", "tissue", "genotype", "localization")
EVIDENCE_CHAIN_FIELDS = (
    "model_system",
    "intervention_type",
    "intervention_target",
    "control_group",
    "dose",
    "duration",
    "assay_method",
    "measured_endpoint",
    "validation_design",
)
EXPERIMENT_TERMS = (
    "knockdown",
    "knockout",
    "silencing",
    "silenced",
    "inhibition",
    "inhibitor",
    "blockade",
    "overexpression",
    "activation",
    "treatment",
    "treated",
    "rescued",
    "rescue",
    "restored",
    "reversed",
    "abolished",
    "dependent on",
    "mediated by",
    "resulted in",
    "led to",
    "suggesting that",
    "collectively",
    "therefore",
    "control",
    "assay",
)
INTERVENTION_PATTERNS = (
    r"(?:treated|treatment|exposure|exposed|stimulated|incubated)\s+(?:with|to|by)?\s*([A-Za-z0-9α-ωΑ-Ωβγκ\-_/+. ]{2,60})",
    r"([A-Za-z0-9α-ωΑ-Ωβγκ\-_/+. ]{2,60})\s+(?:treatment|exposure|stimulation|knockdown|knockout|overexpression|silencing|inhibition)",
)
DOSE_PATTERN = r"(\d+(?:\.\d+)?\s*(?:mg/kg|mg / kg|µg/kg|ug/kg|mg))"
TIME_PATTERN = r"(\d+(?:\.\d+)?\s*(?:h|hr|hrs|hours|day|days|min|minutes))"
CELL_LINE_PATTERN = r"\b([A-Z][A-Za-z0-9-]{1,12}(?:-[A-Z0-9]+){0,3})\s+cells\b"
FIGURE_PATTERN = r"\b(?:Fig\.?|Figure)\s*([0-9]+[A-Za-z]?)\b"
TABLE_PATTERN = r"\bTable\s*([0-9]+[A-Za-z]?)\b"
SECTION_PRIORITY = {
    "results": 0,
    "methods": 1,
    "figure_caption": 2,
    "table_caption": 3,
    "discussion": 4,
    "abstract": 5,
    "conclusion": 6,
    "introduction": 7,
    "other": 8,
}


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", str(text or "")):
        sent = re.sub(r"\s+", " ", match.group(0)).strip()
        if sent:
            spans.append((match.start(), match.end(), sent))
    return spans


def classify_section(title: Any) -> str:
    value = str(title or "").casefold()
    if "result" in value:
        return "results"
    if "method" in value or "material" in value:
        return "methods"
    if "figure" in value or value.startswith("fig"):
        return "figure_caption"
    if "table" in value:
        return "table_caption"
    if "discussion" in value:
        return "discussion"
    if "abstract" in value:
        return "abstract"
    if "conclusion" in value:
        return "conclusion"
    if "introduction" in value or "background" in value:
        return "introduction"
    return "other"


def claim_identity_hash(claim: dict[str, Any]) -> str:
    material = {
        "paper_id": claim.get("paper_id"),
        "pmid": claim.get("pmid"),
        "pmcid": claim.get("pmcid"),
        "subject": claim.get("subject"),
        "relation": claim.get("predicate") or claim.get("relation") or claim.get("relation_family"),
        "object": claim.get("object"),
        "sign": claim.get("polarity") or claim.get("direction") or claim.get("sign"),
        "negated": claim.get("negated"),
        "evidence_sentence": claim.get("evidence_sentence"),
    }
    return _hash(material)


def _sentence_index(article: dict[str, Any], paper: dict[str, Any]) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    prefix = str(paper.get("pmcid") or paper.get("pmid") or paper.get("paper_id") or "paper")
    for section_index, section in enumerate(article.get("sections", [])):
        text = str(section.get("text") or "")
        section_type = section.get("section_type") or classify_section(section.get("section_title"))
        for sentence_index, (start, end, sent) in enumerate(_split_sentences(text)):
            sid = f"sent_{hashlib.sha1(f'{prefix}|{section_index}|{sentence_index}|{sent}'.encode()).hexdigest()[:16]}"
            sentences.append({
                "sentence_id": sid,
                "paper_id": paper.get("paper_id"),
                "pmid": paper.get("pmid"),
                "pmcid": paper.get("pmcid"),
                "section_index": section_index,
                "section_title": section.get("section_title"),
                "section_type": section_type,
                "start": start,
                "end": end,
                "text": sent,
            })
    return sentences


def _terms_for_claim(claim: dict[str, Any]) -> list[str]:
    terms = [claim.get("subject"), claim.get("object"), claim.get("predicate"), claim.get("relation_family"), claim.get("evidence_sentence")]
    terms.extend(claim.get("context_terms") or [])
    aliases = claim.get("entity_aliases") if isinstance(claim.get("entity_aliases"), dict) else {}
    for value in aliases.values():
        terms.extend(value if isinstance(value, list) else [value])
    return [str(x) for x in terms if str(x or "").strip()]


def retrieve_claim_centered_passages(
    claim: dict[str, Any],
    article: dict[str, Any],
    paper: dict[str, Any],
    *,
    max_passages: int = 8,
    max_chars: int = 12000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sentences = _sentence_index(article, paper)
    terms = [_norm(x) for x in _terms_for_claim(claim)]
    subject = _norm(claim.get("subject"))
    obj = _norm(claim.get("object"))
    evidence = _norm(claim.get("evidence_sentence"))
    scored: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for sent in sentences:
        text_norm = _norm(sent["text"])
        has_subject = bool(subject and subject in text_norm)
        has_object = bool(obj and obj in text_norm)
        has_evidence = bool(evidence and (text_norm in evidence or evidence in text_norm))
        term_hits = sum(1 for term in terms if term and term in text_norm)
        experiment_hits = sum(1 for term in EXPERIMENT_TERMS if _norm(term) in text_norm)
        if not (has_subject or has_object or has_evidence or term_hits or experiment_hits):
            continue
        priority = SECTION_PRIORITY.get(str(sent.get("section_type") or "other"), 8)
        score = 100 * int(has_evidence) + 40 * int(has_subject and has_object) + 10 * experiment_hits + 5 * term_hits - priority
        scored.append(((-score, priority, sent["start"]), sent))
    scored.sort(key=lambda item: item[0])
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for _, sent in scored:
        if sent["sentence_id"] in seen:
            continue
        text = sent["text"]
        if total + len(text) > max_chars and chosen:
            break
        seen.add(sent["sentence_id"])
        claim_hash = claim_identity_hash(claim)
        passage_content_hash = _hash({"paper": paper.get("pmcid") or paper.get("pmid") or paper.get("paper_id"), "text": text})
        passage_id = "pass_" + hashlib.sha1(f"{claim_hash}|{passage_content_hash}".encode()).hexdigest()[:16]
        chosen.append({
            "passage_id": passage_id,
            "claim_id": claim.get("claim_id"),
            "paper_id": paper.get("paper_id"),
            "pmid": paper.get("pmid"),
            "pmcid": paper.get("pmcid"),
            "section_title": sent.get("section_title"),
            "section_type": sent.get("section_type"),
            "sentence_ids": [sent["sentence_id"]],
            "source_spans": [{"sentence_id": sent["sentence_id"], "start": sent["start"], "end": sent["end"]}],
            "text": text,
            "passage_hash": passage_content_hash,
        })
        total += len(text)
        if len(chosen) >= max_passages:
            break
    return chosen, sentences


def build_reasoning_prompt(claim: dict[str, Any], passages: list[dict[str, Any]]) -> str:
    payload = {
        "target_claim": {
            "claim_id": claim.get("claim_id"),
            "subject": claim.get("subject"),
            "relation": claim.get("predicate") or claim.get("relation_family"),
            "object": claim.get("object"),
            "sign": claim.get("polarity") or claim.get("direction") or claim.get("sign"),
            "evidence_sentence": claim.get("evidence_sentence"),
        },
        "allowed_step_roles": sorted(STEP_ROLES),
        "allowed_trace_statuses": sorted(TRACE_STATUSES),
        "passages": [{"passage_id": p["passage_id"], "section_type": p.get("section_type"), "section_title": p.get("section_title"), "sentence_ids": p.get("sentence_ids"), "text": p.get("text")} for p in passages],
    }
    return (
        "You extract a claim-centered reasoning trace from provided full-text passages only.\n"
        "Do not modify the target claim. Do not create new causal claims. Do not infer unreported links.\n"
        "Every reasoning step must cite sentence_ids from the passages and use an allowed role.\n"
        "Separate intervention, observation, functional result, rescue/blocking, and author interpretation.\n"
        "Return strict JSON only with trace_status, reasoning_steps, author_conclusion, experimental_context, alternative_explanations, limitations, missing_links.\n"
        f"PAYLOAD: {json.dumps(payload, ensure_ascii=False)}"
    )


def _cache_key(claim: dict[str, Any], paper: dict[str, Any], passages: list[dict[str, Any]], *, provider: str, model: str) -> str:
    material = {
        "paper_identity": {"paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid")},
        "claim_identity_hash": claim_identity_hash(claim),
        "retrieved_passage_hashes": [p["passage_hash"] for p in passages],
        "reasoning_prompt_hash": _hash({"prompt_version": PROMPT_VERSION}),
        "provider": provider,
        "model": model,
        "output_schema_version": SCHEMA_VERSION,
        "extractor_code_version": EXTRACTOR_CODE_VERSION,
        "retrieval_configuration_hash": _hash({"version": RETRIEVAL_CONFIG_VERSION, "terms": EXPERIMENT_TERMS}),
    }
    return _hash(material)


def _empty_context() -> dict[str, list[Any]]:
    return {field: [] for field in CONTEXT_FIELDS}


def _normalize_list(value: Any) -> list[Any]:
    if value in (None, "", {}):
        return []
    if isinstance(value, list):
        return [x for x in value if x not in (None, "", {}, [])]
    return [value]


def _span_text_valid(step: dict[str, Any], sentence_by_id: dict[str, dict[str, Any]]) -> bool:
    reported = str(step.get("reported_text") or "").strip()
    ids = [str(x) for x in step.get("sentence_ids") or []]
    if not reported or not ids:
        return False
    source_text = " ".join(str(sentence_by_id.get(sid, {}).get("text") or "") for sid in ids)
    return bool(source_text and (_norm(reported) in _norm(source_text) or _norm(source_text) in _norm(reported)))


def _validate_extracted_trace(raw: dict[str, Any], *, claim: dict[str, Any], paper: dict[str, Any], passages: list[dict[str, Any]], sentences: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    sentence_ids = {sid for p in passages for sid in p.get("sentence_ids", [])}
    sentence_by_id = {s["sentence_id"]: s for s in sentences if s["sentence_id"] in sentence_ids}
    status = str(raw.get("trace_status") or "partial")
    if status not in TRACE_STATUSES:
        warnings.append(f"invalid_trace_status:{status}")
        status = "partial"
    steps = []
    for index, step in enumerate(raw.get("reasoning_steps") or [], 1):
        role = str(step.get("role") or "")
        ids = [str(x) for x in step.get("sentence_ids") or []]
        if role not in STEP_ROLES:
            warnings.append(f"step_{index}_invalid_role")
            continue
        if any(sid not in sentence_by_id for sid in ids):
            warnings.append(f"step_{index}_missing_sentence_provenance")
            continue
        if str(step.get("provenance_type") or "reported") not in {"reported", "reconstructed_from_reported_steps"}:
            warnings.append(f"step_{index}_invalid_provenance_type")
            continue
        if not _span_text_valid(step, sentence_by_id):
            warnings.append(f"step_{index}_reported_text_not_anchored")
            continue
        first = sentence_by_id[ids[0]]
        steps.append({
            "step_id": step.get("step_id") or f"step_{len(steps)+1:03d}",
            "role": role,
            "reported_text": step.get("reported_text"),
            "section_type": step.get("section_type") or first.get("section_type"),
            "section_title": step.get("section_title") or first.get("section_title"),
            "sentence_ids": ids,
            "source_spans": step.get("source_spans") or [{"sentence_id": sid, "start": sentence_by_id[sid]["start"], "end": sentence_by_id[sid]["end"]} for sid in ids],
            "relation_to_claim": step.get("relation_to_claim") or "",
            "provenance_type": step.get("provenance_type") or "reported",
            "confidence": step.get("confidence"),
        })
    context = _empty_context()
    raw_context = raw.get("experimental_context") if isinstance(raw.get("experimental_context"), dict) else {}
    for field in CONTEXT_FIELDS:
        context[field] = _normalize_list(raw_context.get(field))
    trace = {
        "schema_version": SCHEMA_VERSION,
        "reasoning_trace_id": "rt_" + _hash({"claim": claim_identity_hash(claim), "passages": [p["passage_hash"] for p in passages]})[:20],
        "claim_id": claim.get("claim_id"),
        "case_id": claim.get("case_id") or paper.get("case_id"),
        "paper_id": paper.get("paper_id") or claim.get("paper_id"),
        "pmid": paper.get("pmid") or claim.get("pmid"),
        "pmcid": paper.get("pmcid") or claim.get("pmcid"),
        "trace_status": status,
        "source_scope": "fulltext",
        "claim_identity_hash": claim_identity_hash(claim),
        "reasoning_steps": steps,
        "author_conclusion": raw.get("author_conclusion") if isinstance(raw.get("author_conclusion"), dict) else {},
        "experimental_context": context,
        "strength_profile": strength_profile(steps),
        "strength_level": strength_level(strength_profile(steps)),
        "alternative_explanations": raw.get("alternative_explanations") or [],
        "limitations": raw.get("limitations") or [],
        "missing_links": raw.get("missing_links") or [],
        "retrieved_passage_ids": [p["passage_id"] for p in passages],
        "source_record_hash": _hash(raw),
    }
    if status == "complete" and not steps:
        trace["trace_status"] = "partial"
        warnings.append("complete_status_without_steps_downgraded")
    return trace, warnings


def strength_profile(steps: list[dict[str, Any]]) -> dict[str, bool]:
    roles = {str(step.get("role")) for step in steps}
    text = " ".join(str(step.get("reported_text") or "").casefold() for step in steps)
    return {
        "has_intervention": bool(roles & {"experimental_intervention", "loss_of_function", "gain_of_function", "blocking_experiment", "rescue_experiment"}),
        "has_control": "comparison_or_control" in roles or "control" in text,
        "has_loss_of_function": "loss_of_function" in roles,
        "has_gain_of_function": "gain_of_function" in roles,
        "has_blocking_experiment": "blocking_experiment" in roles,
        "has_rescue_experiment": "rescue_experiment" in roles,
        "has_temporal_order": "temporal_order" in roles,
        "has_dose_response": "dose_response" in roles,
        "has_orthogonal_validation": len(roles & {"measurement", "functional_result", "in_vivo_validation", "rescue_experiment", "blocking_experiment"}) >= 2,
        "has_in_vivo_validation": "in_vivo_validation" in roles or "in vivo" in text or "mouse" in text or "mice" in text,
        "has_alternative_explanation_test": "alternative_explanation" in roles,
    }


def strength_level(profile: dict[str, bool]) -> str:
    if profile.get("has_blocking_experiment") or profile.get("has_rescue_experiment"):
        return "blocking_or_rescue_supported"
    if profile.get("has_loss_of_function") or profile.get("has_gain_of_function"):
        return "loss_or_gain_of_function"
    if profile.get("has_intervention"):
        return "intervention_supported"
    if profile.get("has_control") or profile.get("has_orthogonal_validation"):
        return "observational"
    return "author_conclusion_only"


def _first_text_for_roles(trace: dict[str, Any], roles: set[str]) -> str | None:
    for step in trace.get("reasoning_steps") or []:
        if step.get("role") in roles and step.get("reported_text"):
            return str(step.get("reported_text"))
    return None


def _anchors_for_trace(trace: dict[str, Any]) -> list[EvidenceAnchor]:
    anchors: list[EvidenceAnchor] = []
    seen: set[str] = set()
    for step in trace.get("reasoning_steps") or []:
        for sid in step.get("sentence_ids") or []:
            key = str(sid)
            if key in seen:
                continue
            seen.add(key)
            anchors.append(EvidenceAnchor(
                anchor_id="anc_" + _hash({"trace": trace.get("reasoning_trace_id"), "sentence_id": key})[:16],
                section=step.get("section_title") or step.get("section_type"),
                sentence_id=key,
                sentence_text=step.get("reported_text"),
            ))
    return anchors


def _direction_from_text(text: str | None) -> str:
    norm = _norm(text or "")
    if any(x in norm for x in ("increase", "increased", "higher", "upregulated", "enhanced", "activated")):
        return "increase"
    if any(x in norm for x in ("decrease", "decreased", "lower", "reduced", "suppressed", "inhibited", "abolished")):
        return "decrease"
    if any(x in norm for x in ("no change", "no difference", "not significant")):
        return "no_change"
    return "unknown"


def _figure(text: str | None) -> str | None:
    match = re.search(FIGURE_PATTERN, str(text or ""), flags=re.I)
    return f"Figure {match.group(1)}" if match else None


def _table(text: str | None) -> str | None:
    match = re.search(TABLE_PATTERN, str(text or ""), flags=re.I)
    return f"Table {match.group(1)}" if match else None


def _extract_first(pattern: str, text: str | None) -> str | None:
    match = re.search(pattern, str(text or ""), flags=re.I)
    return re.sub(r"\s+", " ", match.group(1)).strip(" .;,") if match else None


def _clean_agent(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\b(?:for|at|in|on|and|or|the|a|an|cells?|cell lines?)\b.*$", "", value, flags=re.I).strip(" .;,")
    return text[:80] or None


def _direct_context_from_sentence(claim: dict[str, Any], sentence: dict[str, Any], nearby: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join([sentence.get("text") or "", *(row.get("text") or "" for row in nearby)])
    claim_context = claim.get("context") if isinstance(claim.get("context"), dict) else {}
    cell_line = claim_context.get("cell_line") or claim_context.get("cell_type") or _extract_first(CELL_LINE_PATTERN, text)
    species = claim_context.get("species") or claim_context.get("organism")
    if not species and re.search(r"\bmice|mouse|murine\b", text, flags=re.I):
        species = "mouse"
    elif not species and re.search(r"\brat|rats\b", text, flags=re.I):
        species = "rat"
    elif not species and re.search(r"\bhuman\b", text, flags=re.I):
        species = "human"
    return {
        "species": species,
        "cell_line": cell_line if cell_line and re.search(r"\d|[A-Z]{2,}", str(cell_line)) else None,
        "cell_type": claim_context.get("cell_type") if claim_context.get("cell_type") != cell_line else None,
        "disease_model": claim_context.get("disease") or claim_context.get("disease_model") or claim_context.get("model_system"),
        "tissue": claim_context.get("tissue"),
        "genotype": claim_context.get("genotype"),
        "localization": claim_context.get("localization"),
    }


def _nearby_experimental_sentences(sentences: list[dict[str, Any]], target: dict[str, Any], window: int = 2) -> list[dict[str, Any]]:
    section_index = target.get("section_index")
    same_section = [row for row in sentences if row.get("section_index") == section_index]
    try:
        position = next(i for i, row in enumerate(same_section) if row.get("sentence_id") == target.get("sentence_id"))
    except StopIteration:
        return []
    candidates = same_section[max(0, position - window): position] + same_section[position + 1: position + 1 + window]
    return [row for row in candidates if any(_norm(term) in _norm(row.get("text")) for term in EXPERIMENT_TERMS) or str(row.get("section_type")) == "methods"]


def _methods_context_sentences(sentences: list[dict[str, Any]], claim: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    terms = [_norm(claim.get("subject")), _norm(claim.get("object"))]
    rows: list[tuple[int, dict[str, Any]]] = []
    for row in sentences:
        if str(row.get("section_type")) != "methods":
            continue
        text = _norm(row.get("text"))
        score = sum(2 for term in terms if term and term in text)
        score += 2 if re.search(DOSE_PATTERN, str(row.get("text") or ""), flags=re.I) else 0
        score += sum(1 for term in ("assay", "measured", "western blot", "qpcr", "transwell", "migration", "invasion") if term in text)
        if score:
            rows.append((score, row))
    return [row for _, row in sorted(rows, key=lambda item: -item[0])[:limit]]


def _claim_sentence_match(claim: dict[str, Any], sentences: list[dict[str, Any]]) -> dict[str, Any] | None:
    evidence = _norm(claim.get("evidence_sentence"))
    if not evidence:
        return None
    def usable(row: dict[str, Any]) -> bool:
        text = str(row.get("text") or "").strip()
        if len(text) < 25:
            return False
        if _norm(text) in {"results", "methods", "discussion", "conclusion", "abstract"}:
            return False
        return str(row.get("section_type") or "").casefold() not in {"abstract", "introduction", "conclusion"}
    body = [row for row in sentences if usable(row)]
    for row in body:
        text_norm = _norm(row.get("text"))
        if text_norm and (text_norm in evidence or evidence in text_norm):
            return row
    subject = _norm(claim.get("subject"))
    obj = _norm(claim.get("object"))
    relation = _norm(claim.get("predicate") or claim.get("relation_family"))
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in body:
        text_norm = _norm(row.get("text"))
        score = 0
        score += 3 if subject and subject in text_norm else 0
        score += 3 if obj and obj in text_norm else 0
        score += 2 if relation and relation in text_norm else 0
        score += sum(1 for term in EXPERIMENT_TERMS if _norm(term) in text_norm)
        if score >= 4:
            scored.append((score, row))
    return sorted(scored, key=lambda item: (-item[0], SECTION_PRIORITY.get(str(item[1].get("section_type")), 8)))[0][1] if scored else None


def _direct_causal_design(sentence_text: str, nearby_text: str) -> CausalDesign:
    text = _norm(f"{sentence_text} {nearby_text}")
    if any(term in text for term in ("rescue", "rescued", "restored", "reversed")):
        return CausalDesign(evidence_type="rescue", causal_strength="rescue_support", classification_basis=["direct fulltext rescue terminology in anchored experiment"])
    if any(term in text for term in ("knockdown", "silencing", "silenced", "depletion")):
        return CausalDesign(evidence_type="knockdown", causal_strength="necessity_support", classification_basis=["direct fulltext knockdown/silencing design"])
    if any(term in text for term in ("knockout", "deficiency", "deletion")):
        return CausalDesign(evidence_type="knockout", causal_strength="necessity_support", classification_basis=["direct fulltext knockout/deficiency design"])
    if any(term in text for term in ("inhibitor", "inhibition", "blockade", "blocked", "abolished")):
        return CausalDesign(evidence_type="pharmacological_blockade", causal_strength="necessity_support", classification_basis=["direct fulltext blockade/inhibition design"])
    if any(term in text for term in ("overexpression", "overexpressed", "forced expression")):
        return CausalDesign(evidence_type="overexpression", causal_strength="sufficiency_support", classification_basis=["direct fulltext overexpression design"])
    if any(term in text for term in ("dose", "concentration")) or re.search(DOSE_PATTERN, f"{sentence_text} {nearby_text}", flags=re.I):
        return CausalDesign(evidence_type="dose_response", causal_strength="mechanistic_support", classification_basis=["direct fulltext dose/concentration context"])
    if any(term in text for term in ("treated", "treatment", "exposure", "stimulated", "transfected")):
        return CausalDesign(evidence_type="intervention", causal_strength="intervention_support", classification_basis=["direct fulltext intervention followed by measurement/result"])
    if any(term in text for term in ("correlat", "associated", "association")):
        return CausalDesign(evidence_type="association", causal_strength="association", classification_basis=["direct fulltext association wording"])
    return CausalDesign(evidence_type="other", causal_strength="unclear", classification_basis=["direct fulltext anchor lacks clear experimental design"])


def _direct_chain_for_claim(claim: dict[str, Any], paper: dict[str, Any], sentence: dict[str, Any], nearby: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_text = str(sentence.get("text") or claim.get("evidence_sentence") or "")
    nearby_text = " ".join(str(row.get("text") or "") for row in nearby)
    parameter_context = evidence_text + " " + nearby_text
    context = _direct_context_from_sentence(claim, sentence, nearby)
    agent = _clean_agent(_extract_first(INTERVENTION_PATTERNS[0], evidence_text + " " + nearby_text) or _extract_first(INTERVENTION_PATTERNS[1], evidence_text + " " + nearby_text) or claim.get("subject"))
    parameters = extract_parameters(parameter_context, context=parameter_context, source_anchor_ids=[str(sentence.get("sentence_id") or "")])
    dose = first_parameter(parameters, "dose")
    concentration = first_parameter(parameters, "concentration")
    duration = first_parameter(parameters, "duration") or (claim.get("context") or {}).get("exposure_time")
    timepoint = first_parameter(parameters, "timepoint")
    measurement_parameters = [
        item for item in parameters
        if item.parameter_type in {"wavelength", "assay_readout", "statistical_value", "temperature", "centrifugation_speed", "rotation_speed", "frequency", "timepoint"}
    ]
    comparator = "control" if re.search(r"\bcontrol|vehicle|untreated|wild[- ]type\b", evidence_text + " " + nearby_text, flags=re.I) else None
    assay = None
    for term in ("western blot", "qRT-PCR", "qPCR", "MTT", "CCK-8", "transwell", "wound healing", "immunofluorescence", "flow cytometry", "ELISA", "migration assay", "invasion assay"):
        if term.casefold() in (evidence_text + " " + nearby_text).casefold():
            assay = term
            break
    endpoint = str(claim.get("object") or "")
    anchor = EvidenceAnchor(
        anchor_id="anc_" + _hash({"claim": claim.get("claim_id"), "sentence": sentence.get("sentence_id")})[:16],
        section=sentence.get("section_title") or sentence.get("section_type"),
        sentence_id=sentence.get("sentence_id"),
        sentence_text=evidence_text,
        figure=_figure(evidence_text),
        table=_table(evidence_text) or (_table(sentence.get("section_title")) if sentence.get("section_type") == "table_caption" else None),
    )
    chain = ExperimentalEvidenceChain(
        chain_id="chain_" + _hash({"origin": "direct_fulltext", "claim": claim.get("claim_id"), "sentence": sentence.get("sentence_id")})[:20],
        paper_id=str(paper.get("paper_id") or claim.get("paper_id") or ""),
        source_document_id=str(paper.get("pmcid") or claim.get("pmcid") or paper.get("pmid") or claim.get("pmid") or ""),
        experimental_system=ExperimentalSystem(**{key: value for key, value in context.items() if key in ExperimentalSystem.model_fields}),
        interventions=[Intervention(
            agent_raw=agent or "",
            dose=dose,
            concentration=concentration,
            duration=duration,
            timing=timepoint,
            parameters=[item.to_dict() for item in parameters if item.parameter_type in {"dose", "concentration", "duration", "timepoint", "mass", "volume", "unknown_parameter"}],
        )] if agent or dose or concentration or duration or timepoint else [],
        comparators=[Comparator(comparator_type="other", description=comparator)] if comparator else [],
        measurements=[Measurement(assay=assay, endpoint=endpoint or None, measurement_time=timepoint or duration, parameters=[item.to_dict() for item in measurement_parameters])],
        observed_results=[ObservedResult(endpoint=endpoint, direction=_direction_from_text(evidence_text), effect_description=evidence_text)],
        author_interpretation=AuthorInterpretation(text=evidence_text if re.search(r"\bsuggest|indicat|demonstrat|therefore|consequently|conclusion\b", evidence_text, flags=re.I) else None, certainty="suggested" if re.search(r"\bsuggest|indicat|consequently\b", evidence_text, flags=re.I) else "not_stated"),
        causal_design=_direct_causal_design(evidence_text, nearby_text),
        evidence_anchors=[anchor],
        extraction_confidence=0.82 if str(sentence.get("section_type")) in {"results", "methods", "figure_caption", "table_caption"} else 0.65,
        validation_status="valid",
        extraction_origin="direct_fulltext",
        claim_id=claim.get("claim_id"),
        source_section_type=sentence.get("section_type"),
        extraction_version=DIRECT_EVIDENCE_CHAIN_EXTRACTOR_VERSION,
    )
    return chain.model_dump(mode="json")


def extract_direct_fulltext_evidence_chains(claims: list[dict[str, Any]], candidates: list[dict[str, Any]], artifacts: Path) -> list[dict[str, Any]]:
    paper_by_key: dict[str, dict[str, Any]] = {}
    for paper in candidates:
        for key in (paper.get("paper_id"), paper.get("pmid"), paper.get("pmcid")):
            if key:
                paper_by_key[str(key)] = paper
    chains: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claims:
        if "full" not in str(claim.get("source_scope") or "").casefold():
            continue
        if str(claim.get("section_type") or "").casefold() == "abstract":
            continue
        key = str(claim.get("paper_id") or claim.get("pmid") or claim.get("pmcid") or "")
        paper = paper_by_key.get(key) or {k: claim.get(k) for k in ("paper_id", "pmid", "pmcid", "case_id")}
        article_path = artifacts / "fulltext/pmc_oa" / str(paper.get("pmcid") or claim.get("pmcid")) / "article_text.json"
        if not article_path.is_file():
            continue
        article = _json(article_path, {})
        sentences = _sentence_index(article, paper)
        sentence = _claim_sentence_match(claim, sentences)
        if not sentence:
            continue
        nearby = _nearby_experimental_sentences(sentences, sentence)
        for row in _methods_context_sentences(sentences, claim):
            if row.get("sentence_id") not in {item.get("sentence_id") for item in nearby}:
                nearby.append(row)
        chain = _direct_chain_for_claim(claim, paper, sentence, nearby)
        if chain["chain_id"] not in seen:
            chains.append(chain)
            seen.add(chain["chain_id"])
    return chains


def evidence_chains_from_v2_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert grounded L1 v2 observations to chain inputs without causal completion."""
    chains: list[dict[str, Any]] = []
    for row in observations:
        prov = row.get("provenance") or {}; exp = row.get("experiment") or {}
        intervention = row.get("intervention") or {}; measurement = row.get("measurement") or {}
        observation = row.get("observation") or {}; interpretation = row.get("author_interpretation") or {}
        spans = prov.get("evidence_spans") or []
        anchors = [EvidenceAnchor(
            anchor_id=f"{row.get('observation_id')}_{index}", section=span.get("section") or prov.get("section"),
            paragraph_id=span.get("paragraph_id") or prov.get("paragraph_id"), sentence_id=span.get("sentence_id"),
            sentence_text=span.get("text"), figure=(prov.get("figure_ids") or [None])[0],
            table=(prov.get("table_ids") or [None])[0], supplement=prov.get("supplementary_reference"),
        ) for index, span in enumerate(spans)]
        itype = str(intervention.get("intervention_type") or "unknown")
        causal_strength = (
            "rescue_support" if itype in {"rescue", "re_expression"}
            else "necessity_support" if intervention.get("intervention_sign") == -1
            else "sufficiency_support" if intervention.get("intervention_sign") == 1
            else "association"
        )
        chain = ExperimentalEvidenceChain(
            chain_id="chain_" + _hash({"observation": row.get("observation_id"), "experiment": exp.get("experiment_id")})[:20],
            paper_id=str(prov.get("paper_id") or prov.get("pmid") or prov.get("pmcid") or ""),
            source_document_id=str(prov.get("source_document_id") or ""),
            experimental_system=ExperimentalSystem(
                species=exp.get("species"), disease_model=exp.get("disease_model") or exp.get("model_system"),
                tissue=exp.get("tissue"), cell_type=exp.get("cell_type"), cell_line=exp.get("cell_line"),
                genotype=exp.get("genotype"), localization=exp.get("localization"),
            ),
            interventions=[Intervention(
                agent_raw=intervention.get("intervention_target_mention") or "", dose=exp.get("dose"),
                duration=exp.get("duration_time"), combination=", ".join(intervention.get("combination_intervention") or []) or None,
            )] if itype != "observational_no_intervention" else [],
            comparators=[Comparator(comparator_type="other", description=exp.get("comparison_arm") or exp.get("control_arm") or "")] if exp.get("comparison_arm") or exp.get("control_arm") else [],
            measurements=[Measurement(assay=measurement.get("assay") or measurement.get("measurement_method"), endpoint=measurement.get("measured_entity_mention") or measurement.get("outcome_mention"))],
            observed_results=[ObservedResult(
                endpoint=measurement.get("outcome_mention") or measurement.get("measured_entity_mention") or "",
                direction={1: "increase", -1: "decrease", 0: "no_change"}.get(observation.get("observed_outcome_sign"), "unknown"),
                effect_description=observation.get("observed_result") or "", effect_size=observation.get("effect_size_or_magnitude"),
                statistical_support=observation.get("statistical_support"),
            )],
            author_interpretation=AuthorInterpretation(text=interpretation.get("author_interpretation") or interpretation.get("author_conclusion"), certainty="asserted" if interpretation.get("author_conclusion") else "not_stated"),
            causal_design=CausalDesign(evidence_type="rescue" if itype in {"rescue", "re_expression"} else "intervention" if intervention.get("intervention_sign") in {-1, 1} else "association", causal_strength=causal_strength, classification_basis=["Fulltext L1 v2 structured intervention; causal sign remains downstream"]),
            evidence_anchors=anchors, extraction_confidence=float(exp.get("binding_confidence") or 0),
            validation_status="valid" if anchors and row.get("statement_role") == "current_study_experiment" else "partial" if anchors else "invalid",
            extraction_origin="fulltext_l1_v2", observation_id=row.get("observation_id"), claim_id=row.get("observation_id"),
            experiment_id=exp.get("experiment_id"), evidence_family_id=exp.get("evidence_family_id"),
            intervention_type=itype, intervention_sign=intervention.get("intervention_sign"),
            observed_outcome_sign=observation.get("observed_outcome_sign"), measurement_dimension=measurement.get("measurement_dimension"),
            context_source=exp.get("context_source") or [], binding_confidence=exp.get("binding_confidence"),
            extraction_version="fulltext_l1_v2_to_evidence_chain_v1",
        )
        chains.append(chain.model_dump(mode="json"))
    return chains


def _normalization_payload(decision: Any) -> dict[str, Any]:
    return {
        "raw_text": decision.raw_text,
        "mention_text": decision.raw_text,
        "canonical_id": decision.canonical_id or None,
        "canonical_name": decision.canonical_name or decision.normalized_surface,
        "entity_type": decision.entity_type,
        "resolution_status": decision.normalization_status,
        "resolution_method": decision.resolver,
        "confidence": decision.confidence,
    }


NON_ENTITY_RE = re.compile(
    r"(\d+\s*(?:mg|µg|ug|ng|nm|mM|µM|uM|nM|h|hr|min|day|°C|rpm|×g|x\s*g)|"
    r"\b(?:figure|fig\.?|table|p\s*[<=>]|OD\d+|absorbance|measured at|after \d+|for \d+)\b)",
    re.I,
)
ENTITY_STOPWORDS = {
    "control", "vehicle", "untreated", "treated", "treatment", "cells", "cell",
    "expression", "migration", "invasion", "viability", "proliferation", "apoptosis",
    "role", "effect", "effects", "after", "of", "the", "and", "or",
}


def _candidate_entity_type(text: str, role: str) -> str | None:
    norm = text.strip()
    low = norm.casefold()
    if not norm or len(norm) < 2:
        return None
    if NON_ENTITY_RE.search(norm):
        return None
    if len(norm.split()) > 6:
        return None
    if low in ENTITY_STOPWORDS:
        return None
    if role in {"cell_line"} or re.fullmatch(r"[A-Z][A-Za-z0-9-]{1,12}(?:-[A-Z0-9]+){0,3}", norm):
        return "cell_line"
    if role in {"cell_type", "tissue", "disease_model"}:
        return role
    if re.search(r"\b(pathway|signaling|phosphorylation|emt)\b", low):
        return "pathway"
    if re.search(r"\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)?\b", norm) or re.search(r"[α-ωΑ-Ωβγκ]", norm):
        return "gene_or_protein"
    if role == "intervention_agent":
        return "compound_or_biomolecule"
    if role in {"assay_endpoint", "observed_endpoint"} and len(norm.split()) <= 3:
        return "molecular_endpoint"
    return None


def _mention_candidates(value: Any, *, role: str) -> list[dict[str, str]]:
    text = str(value or "").strip(" .;,")
    if not text:
        return []
    text = re.sub(r"\b(?:after|for)\s+\d+(?:\.\d+)?\s*(?:h|hr|hours|min|days?)\b", " ", text, flags=re.I)
    text = re.sub(r"\bmeasured\s+at\s+\d+(?:\.\d+)?\s*nm\b", " ", text, flags=re.I)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:mg/kg|µg/kg|ug/kg|mg|µg|ug|ng/mL|mg/mL|µM|uM|nM|mM|nm)\b", " ", text, flags=re.I)
    text = re.sub(r"^(?:of|in|with|by|after|the)\s+", "", text.strip(), flags=re.I)
    parts = re.split(r"\s+(?:and|or|with|plus|versus|vs\.?)\s+|[,;/]", text)
    candidates = []
    for part in parts:
        clean = re.sub(r"\s+", " ", part).strip(" .;:()[]")
        etype = _candidate_entity_type(clean, role)
        if etype:
            candidates.append({"raw_text": str(value), "mention_text": clean, "inferred_type": etype})
    return candidates


def _resolve_chain_value(resolver: ResolverCascade, value: Any, *, role: str, chain: dict[str, Any]) -> dict[str, Any] | None:
    candidates = _mention_candidates(value, role=role)
    if not candidates:
        return None
    text = candidates[0]["mention_text"]
    decision = resolver.resolve_entity(text, {
        "mention_role": role,
        "expected_entity_type": candidates[0]["inferred_type"],
        "paper_id": chain.get("paper_id"),
        "claim_id": chain.get("claim_id"),
        "context_text": " ".join(str((a or {}).get("sentence_text") or "") for a in chain.get("evidence_anchors") or []),
    })
    return {**_normalization_payload(decision), **candidates[0]}


def normalize_evidence_chain_entities(
    chains: list[dict[str, Any]],
    *,
    run_dir: str | Path,
    network_enabled: bool = False,
    api_enabled: bool = False,
    entity_network_lookup: bool = False,
    entity_llm_cleaner: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    run = Path(run_dir)
    profile = _json(run / "artifacts/domain_profile.json", {}) or _json(run / "artifacts/case_domain_profile.json", {})
    resolver = ResolverCascade(
        domain_id=profile.get("domain_id", "general_biomedical"),
        entity_registry_profile=profile.get("entity_registry_profile", "general_entity_resolution_hub"),
        resolver_policy_id=profile.get("resolver_policy_id", "conservative_resolver_v2"),
        run_dir=run,
        execute=True,
        network_enabled=network_enabled,
        api_enabled=api_enabled,
        entity_network_lookup=entity_network_lookup,
        entity_llm_cleaner=entity_llm_cleaner,
    )
    counts = {
        "raw_candidate_span_count": 0,
        "non_entity_filtered_count": 0,
        "eligible_entity_mention_count": 0,
        "entity_resolved_count": 0,
        "entity_ambiguous_count": 0,
        "entity_unresolved_count": 0,
    }
    unresolved_frequency: dict[tuple[str, str], dict[str, Any]] = {}
    for chain in chains:
        normalized_entities: list[dict[str, Any]] = []
        for intervention in chain.get("interventions") or []:
            if not isinstance(intervention, dict):
                continue
            raw_candidates = 1 if intervention.get("agent_raw") else 0
            mention_candidates = _mention_candidates(intervention.get("agent_raw"), role="intervention_agent")
            counts["raw_candidate_span_count"] += raw_candidates
            counts["non_entity_filtered_count"] += max(0, raw_candidates - len(mention_candidates))
            payload = _resolve_chain_value(resolver, intervention.get("agent_raw"), role="intervention_agent", chain=chain)
            if payload:
                intervention["canonical_id"] = payload.get("canonical_id")
                intervention["canonical_name"] = payload.get("canonical_name")
                intervention["entity_type"] = payload.get("entity_type")
                intervention["resolution_status"] = payload.get("resolution_status")
                intervention["resolution_method"] = payload.get("resolution_method")
                intervention["resolution_confidence"] = payload.get("confidence")
                normalized_entities.append({**payload, "role": "intervention_agent"})
        system = chain.get("experimental_system") if isinstance(chain.get("experimental_system"), dict) else {}
        for key, role in (("disease_model", "disease_model"), ("cell_type", "cell_type"), ("cell_line", "cell_line"), ("tissue", "tissue")):
            raw_candidates = 1 if system.get(key) else 0
            mention_candidates = _mention_candidates(system.get(key), role=role)
            counts["raw_candidate_span_count"] += raw_candidates
            counts["non_entity_filtered_count"] += max(0, raw_candidates - len(mention_candidates))
            payload = _resolve_chain_value(resolver, system.get(key), role=role, chain=chain)
            if payload:
                normalized_entities.append({**payload, "role": role})
        for measurement in chain.get("measurements") or []:
            if isinstance(measurement, dict):
                raw_candidates = 1 if measurement.get("endpoint") else 0
                mention_candidates = _mention_candidates(measurement.get("endpoint"), role="assay_endpoint")
                counts["raw_candidate_span_count"] += raw_candidates
                counts["non_entity_filtered_count"] += max(0, raw_candidates - len(mention_candidates))
                payload = _resolve_chain_value(resolver, measurement.get("endpoint"), role="assay_endpoint", chain=chain)
                if payload:
                    measurement["endpoint_normalization"] = payload
                    normalized_entities.append({**payload, "role": "assay_endpoint"})
        for result in chain.get("observed_results") or []:
            if isinstance(result, dict):
                raw_candidates = 1 if result.get("endpoint") else 0
                mention_candidates = _mention_candidates(result.get("endpoint"), role="observed_endpoint")
                counts["raw_candidate_span_count"] += raw_candidates
                counts["non_entity_filtered_count"] += max(0, raw_candidates - len(mention_candidates))
                payload = _resolve_chain_value(resolver, result.get("endpoint"), role="observed_endpoint", chain=chain)
                if payload:
                    result["endpoint_normalization"] = payload
                    normalized_entities.append({**payload, "role": "observed_endpoint"})
        for item in normalized_entities:
            counts["eligible_entity_mention_count"] += 1
            if item.get("resolution_status") == "resolved":
                counts["entity_resolved_count"] += 1
            elif item.get("resolution_status") == "ambiguous":
                counts["entity_ambiguous_count"] += 1
            else:
                counts["entity_unresolved_count"] += 1
                key = (str(item.get("mention_text") or item.get("raw_text")), str(item.get("inferred_type") or item.get("entity_type") or "unknown"))
                bucket = unresolved_frequency.setdefault(key, {"raw_text": key[0], "inferred_type": key[1], "frequency": 0, "example_chain_ids": []})
                bucket["frequency"] += 1
                if chain.get("chain_id") not in bucket["example_chain_ids"] and len(bucket["example_chain_ids"]) < 5:
                    bucket["example_chain_ids"].append(chain.get("chain_id"))
        chain["normalized_entities"] = normalized_entities
        chain["entity_normalization"] = {
            "resolver": "ResolverCascade",
            "network_enabled": bool(network_enabled and entity_network_lookup),
            "llm_cleaner_enabled": bool(entity_llm_cleaner),
            "entity_count": len(normalized_entities),
        }
    eligible = counts["eligible_entity_mention_count"]
    counts["resolution_rate"] = round(counts["entity_resolved_count"] / eligible, 6) if eligible else 0.0
    counts["top_unresolved_entities"] = sorted(unresolved_frequency.values(), key=lambda row: (-row["frequency"], row["raw_text"]))[:25]  # type: ignore[assignment]
    return chains, counts


def _causal_design(trace: dict[str, Any]) -> CausalDesign:
    roles = {str(step.get("role")) for step in trace.get("reasoning_steps") or []}
    basis: list[str] = []
    if "rescue_experiment" in roles:
        basis.append("rescue_experiment step reported")
        return CausalDesign(evidence_type="rescue", causal_strength="rescue_support", classification_basis=basis)
    if roles & {"blocking_experiment", "loss_of_function"}:
        basis.append("blocking/loss-of-function step reported")
        evidence_type = "pharmacological_blockade" if "blocking_experiment" in roles else "knockdown"
        return CausalDesign(evidence_type=evidence_type, causal_strength="necessity_support", classification_basis=basis)
    if "gain_of_function" in roles:
        basis.append("gain-of-function step reported")
        return CausalDesign(evidence_type="overexpression", causal_strength="sufficiency_support", classification_basis=basis)
    if "dose_response" in roles:
        basis.append("dose-response step reported")
        return CausalDesign(evidence_type="dose_response", causal_strength="mechanistic_support", classification_basis=basis)
    if "experimental_intervention" in roles:
        basis.append("intervention step precedes reported observation")
        return CausalDesign(evidence_type="intervention", causal_strength="intervention_support", classification_basis=basis)
    if roles & {"observation", "functional_result", "measurement"}:
        basis.append("measurement/observation without perturbation design")
        return CausalDesign(evidence_type="association", causal_strength="association", classification_basis=basis)
    return CausalDesign(evidence_type="other", causal_strength="unclear", classification_basis=["insufficient structured experimental design"])


def _context_first(context: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        values = _normalize_list(context.get(key))
        if values:
            return str(values[0])
    return None


def evidence_chains_from_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for trace in traces:
        if trace.get("source_scope") != "fulltext" or not trace.get("reasoning_steps"):
            continue
        context = trace.get("experimental_context") if isinstance(trace.get("experimental_context"), dict) else {}
        intervention_text = _first_text_for_roles(trace, {"experimental_intervention", "loss_of_function", "gain_of_function", "blocking_experiment", "rescue_experiment", "dose_response"})
        measurement_text = _first_text_for_roles(trace, {"measurement", "statistical_support"})
        result_text = _first_text_for_roles(trace, {"observation", "functional_result", "in_vivo_validation"})
        control_text = _first_text_for_roles(trace, {"comparison_or_control"})
        author_text = _first_text_for_roles(trace, {"author_interpretation", "final_conclusion"})
        anchors = _anchors_for_trace(trace)
        confidence = 0.85 if anchors and trace.get("trace_status") == "complete" else 0.65 if anchors else 0.3
        status = "valid" if anchors and trace.get("trace_status") == "complete" else "partial" if anchors else "invalid"
        chain = ExperimentalEvidenceChain(
            chain_id="chain_" + _hash({"trace": trace.get("reasoning_trace_id"), "claim": trace.get("claim_id")})[:20],
            paper_id=str(trace.get("paper_id") or trace.get("pmid") or trace.get("pmcid") or ""),
            source_document_id=str(trace.get("pmcid") or trace.get("pmid") or trace.get("paper_id") or ""),
            experimental_system=ExperimentalSystem(
                species=_context_first(context, "species"),
                disease_model=_context_first(context, "model_system", "disease_subtype"),
                tissue=_context_first(context, "tissue"),
                cell_type=_context_first(context, "cell_type"),
                genotype=_context_first(context, "genotype"),
                localization=_context_first(context, "localization"),
            ),
            interventions=[Intervention(
                agent_raw=_context_first(context, "intervention_target", "intervention_type") or intervention_text or "",
                dose=_context_first(context, "dose"),
                duration=_context_first(context, "duration"),
            )] if (intervention_text or _context_first(context, "intervention_target", "intervention_type", "dose", "duration")) else [],
            comparators=[Comparator(comparator_type="other", description=control_text or "")] if control_text else [],
            measurements=[Measurement(assay=_context_first(context, "assay_method"), endpoint=_context_first(context, "measured_endpoint") or measurement_text)],
            observed_results=[ObservedResult(endpoint=_context_first(context, "measured_endpoint") or "", direction=_direction_from_text(result_text), effect_description=result_text or "")] if result_text else [],
            author_interpretation=AuthorInterpretation(text=author_text, certainty="asserted" if author_text else "not_stated"),
            causal_design=_causal_design(trace),
            evidence_anchors=anchors,
            extraction_confidence=confidence,
            validation_status=status,
            legacy_reasoning_trace_id=trace.get("reasoning_trace_id"),
            claim_id=trace.get("claim_id"),
            strength_profile=trace.get("strength_profile") or {},
            extraction_origin="reasoning_trace_assisted" if trace.get("source_scope") == "fulltext" else "legacy_trace_migration",
            extraction_version=EVIDENCE_CHAIN_EXTRACTOR_VERSION,
        )
        chains.append(chain.model_dump(mode="json"))
    return chains


LINK_THRESHOLDS = {
    "minimum_link": 0.34,
    "high": 0.72,
    "medium": 0.52,
    "weak": 0.34,
}


def _tokens(value: Any) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9α-ωΑ-Ωβγκ]+", str(value or "").casefold()) if len(x) > 1}


def _chain_text(chain: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("chain_id", "paper_id", "claim_id"):
        parts.append(str(chain.get(key) or ""))
    for item in chain.get("interventions") or []:
        if isinstance(item, dict):
            parts.extend(str(item.get(k) or "") for k in ("agent_raw", "canonical_name", "dose", "concentration", "duration", "timing"))
    for item in chain.get("measurements") or []:
        if isinstance(item, dict):
            parts.extend(str(item.get(k) or "") for k in ("assay", "endpoint", "measurement_time"))
    for item in chain.get("observed_results") or []:
        if isinstance(item, dict):
            parts.extend(str(item.get(k) or "") for k in ("endpoint", "direction", "effect_description"))
    parts.append(str((chain.get("author_interpretation") or {}).get("text") or ""))
    parts.extend(str((a or {}).get("sentence_id") or "") + " " + str((a or {}).get("sentence_text") or "") for a in chain.get("evidence_anchors") or [])
    return " ".join(parts)


def _overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


def score_claim_chain_link(claim: dict[str, Any], chain: dict[str, Any]) -> dict[str, Any]:
    claim_text = " ".join(str(claim.get(k) or "") for k in ("subject", "object", "predicate", "relation", "relation_family", "evidence_sentence"))
    chain_text = _chain_text(chain)
    claim_tokens = _tokens(claim_text)
    chain_tokens = _tokens(chain_text)
    subject_object = _tokens(claim.get("subject")) | _tokens(claim.get("object"))
    interventions = set()
    endpoints = set()
    for item in chain.get("interventions") or []:
        if isinstance(item, dict):
            interventions |= _tokens(item.get("agent_raw")) | _tokens(item.get("canonical_name"))
    for item in (chain.get("measurements") or []) + (chain.get("observed_results") or []):
        if isinstance(item, dict):
            endpoints |= _tokens(item.get("endpoint"))
    anchor_text = " ".join(str((a or {}).get("sentence_text") or "") for a in chain.get("evidence_anchors") or [])
    evidence_tokens = _tokens(claim.get("evidence_sentence"))
    chain_direction = next((str((r or {}).get("direction") or "") for r in chain.get("observed_results") or [] if isinstance(r, dict) and (r or {}).get("direction")), "")
    claim_direction = str(claim.get("direction") or claim.get("polarity") or claim.get("sign") or "")
    components = {
        "entity_match_score": max(_overlap_score(subject_object, chain_tokens), _overlap_score(claim_tokens, chain_tokens) * 0.6),
        "direction_match_score": 0.7 if chain_direction and claim_direction and chain_direction in claim_direction.casefold() else 0.35 if chain_direction and chain_direction != "unknown" else 0.0,
        "intervention_match_score": _overlap_score(_tokens(claim.get("subject")) | _tokens(claim.get("object")), interventions),
        "endpoint_match_score": _overlap_score(_tokens(claim.get("object")) | evidence_tokens, endpoints),
        "anchor_overlap_score": 1.0 if str(claim.get("claim_id")) and str(claim.get("claim_id")) == str(chain.get("claim_id")) else _overlap_score(evidence_tokens, _tokens(anchor_text)),
        "interpretation_match_score": _overlap_score(claim_tokens, _tokens((chain.get("author_interpretation") or {}).get("text"))),
        "context_compatibility_score": 1.0 if str(claim.get("paper_id") or claim.get("pmid") or claim.get("pmcid")) in {str(chain.get("paper_id")), str(chain.get("source_document_id"))} else 0.0,
    }
    score = round(
        components["entity_match_score"] * 0.18
        + components["direction_match_score"] * 0.12
        + components["intervention_match_score"] * 0.16
        + components["endpoint_match_score"] * 0.16
        + components["anchor_overlap_score"] * 0.22
        + components["interpretation_match_score"] * 0.08
        + components["context_compatibility_score"] * 0.08,
        4,
    )
    if str(claim.get("claim_id") or "") and str(claim.get("claim_id")) == str(chain.get("claim_id") or ""):
        score = max(score, 0.55 if chain.get("validation_status") == "partial" else 0.72)
        components["anchor_overlap_score"] = max(components["anchor_overlap_score"], 1.0)
    basis = [name for name, value in components.items() if value > 0]
    return {"score": score, "components": components, "basis": basis}


def _link_relation(score: float, components: dict[str, float], claim: dict[str, Any], chain: dict[str, Any]) -> str:
    chain_direction = next((str((r or {}).get("direction") or "") for r in chain.get("observed_results") or [] if isinstance(r, dict) and (r or {}).get("direction")), "")
    claim_text = str(claim.get("evidence_sentence") or claim.get("object") or "").casefold()
    if score < LINK_THRESHOLDS["minimum_link"]:
        return "unclear"
    if chain_direction in {"increase", "decrease"} and any(term in claim_text for term in ("opposite", "reduced" if chain_direction == "increase" else "increased")):
        return "weakens"
    if components.get("context_compatibility_score", 0) >= 0.5 and components.get("entity_match_score", 0) >= 0.3 and components.get("endpoint_match_score", 0) < 0.2:
        return "contextualizes"
    if score < LINK_THRESHOLDS["medium"]:
        return "unclear"
    if components.get("context_compatibility_score", 0) >= 0.5 and components.get("anchor_overlap_score", 0) >= 0.5 and (components.get("entity_match_score", 0) >= 0.2 or components.get("endpoint_match_score", 0) >= 0.2):
        return "supports" if score >= LINK_THRESHOLDS["high"] else "qualifies"
    return "qualifies"


def unlinked_reason_for_claim(claim: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(str(claim.get(k) or "") for k in ("section_type", "evidence_sentence", "predicate", "relation", "relation_family")).casefold()
    highest = max((row["score"] for row in candidates), default=None)
    if any(x in text for x in ("introduction", "background")):
        primary = "background_claim"
    elif any(x in text for x in ("review", "previous", "reported", "prior work")):
        primary = "review_or_prior_work_claim"
    elif any(x in text for x in ("suggest", "indicat", "may", "could")) and not candidates:
        primary = "interpretive_claim"
    elif not claim.get("evidence_sentence"):
        primary = "no_experimental_anchor"
    elif not candidates:
        primary = "fulltext_experiment_not_reconstructed"
    elif highest is not None and highest < LINK_THRESHOLDS["minimum_link"]:
        primary = "insufficient_matching_evidence"
    else:
        primary = "no_compatible_chain"
    return UnlinkedClaimReason(
        claim_id=str(claim.get("claim_id") or ""),
        primary_reason=primary,  # type: ignore[arg-type]
        reason_details=[f"linker={CLAIM_EVIDENCE_LINKER_VERSION}"],
        candidate_chain_count=len(candidates),
        highest_candidate_score=highest,
    ).model_dump(mode="json")


def link_claims_to_evidence_chains(claims: list[dict[str, Any]], chains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_ids = {str(row.get("claim_id")) for row in claims if row.get("claim_id")}
    chain_ids = {str(row.get("chain_id")) for row in chains if row.get("chain_id")}
    links: list[ClaimEvidenceLink] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        if claim_id not in claim_ids:
            continue
        scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        for chain in chains:
            if str(chain.get("paper_id") or "") and str(claim.get("paper_id") or claim.get("pmid") or claim.get("pmcid") or "") not in {str(chain.get("paper_id")), str(chain.get("source_document_id"))}:
                if str(claim.get("claim_id")) != str(chain.get("claim_id")):
                    continue
            score = score_claim_chain_link(claim, chain)
            scored.append((score["score"], chain, score))
        for score_value, chain, score in sorted(scored, key=lambda item: -item[0])[:4]:
            if score_value < LINK_THRESHOLDS["minimum_link"]:
                continue
            relation = _link_relation(score_value, score["components"], claim, chain)
            if relation == "unclear" and score_value < LINK_THRESHOLDS["medium"]:
                continue
            links.append(ClaimEvidenceLink(
                link_id="link_" + _hash({"claim_id": claim_id, "chain_id": chain.get("chain_id"), "score": score_value})[:20],
                claim_id=claim_id,
                chain_id=str(chain.get("chain_id")),
                paper_id=str(chain.get("paper_id") or ""),
                relation=relation,
                link_method="structured_matching" if str(claim.get("claim_id")) != str(chain.get("claim_id")) else "shared_result_anchor",
                link_confidence=max(0.5, min(0.95, score_value)),
                link_basis=score["basis"],
                score_components=score["components"],
                evidence_anchor_ids=[str(anchor.get("anchor_id") or anchor.get("sentence_id")) for anchor in chain.get("evidence_anchors") or []],
            ))
    validate_claim_evidence_references(links, claim_ids=claim_ids, chain_ids=chain_ids)
    return [link.model_dump(mode="json") for link in links]


def evidence_chain_summary(
    claims: list[dict[str, Any]],
    chains: list[dict[str, Any]],
    links: list[dict[str, Any]],
    entity_counts: dict[str, Any] | None = None,
    unlinked_reasons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    linked_claims = {row.get("claim_id") for row in links}
    strengths = [((row.get("causal_design") or {}).get("causal_strength") or "unclear") for row in chains]
    statuses = [row.get("validation_status") for row in chains]
    origins = [row.get("extraction_origin") for row in chains]
    entity_rows = [entity for chain in chains for entity in chain.get("normalized_entities") or []]
    entity_counts = entity_counts or {}
    eligible = int(entity_counts.get("eligible_entity_mention_count") or len(entity_rows))
    resolved = int(entity_counts.get("entity_resolved_count") or sum(entity.get("resolution_status") == "resolved" for entity in entity_rows))
    unlinked_reasons = unlinked_reasons or []
    return {
        "schema_version": "experimental_evidence_chain_summary_v1",
        "claim_count": len(claims),
        "evidence_chain_count": len(chains),
        "claim_evidence_link_count": len(links),
        "linked_claim_count": len(linked_claims),
        "unlinked_claim_count": max(0, len(claims) - len(linked_claims)),
        "association_chain_count": sum(x == "association" for x in strengths),
        "necessity_support_count": sum(x == "necessity_support" for x in strengths),
        "sufficiency_support_count": sum(x == "sufficiency_support" for x in strengths),
        "rescue_support_count": sum(x == "rescue_support" for x in strengths),
        "invalid_chain_count": sum(x == "invalid" for x in statuses),
        "partial_chain_count": sum(x == "partial" for x in statuses),
        "direct_fulltext_chain_count": sum(x == "direct_fulltext" for x in origins),
        "reasoning_trace_assisted_chain_count": sum(x == "reasoning_trace_assisted" for x in origins),
        "legacy_trace_migration_chain_count": sum(x == "legacy_trace_migration" for x in origins),
        "raw_candidate_span_count": int(entity_counts.get("raw_candidate_span_count") or 0),
        "non_entity_filtered_count": int(entity_counts.get("non_entity_filtered_count") or 0),
        "eligible_entity_mention_count": eligible,
        "entity_resolved_count": resolved,
        "entity_ambiguous_count": int(entity_counts.get("entity_ambiguous_count") or sum(entity.get("resolution_status") == "ambiguous" for entity in entity_rows)),
        "entity_unresolved_count": int(entity_counts.get("entity_unresolved_count") or sum(entity.get("resolution_status") not in {"resolved", "ambiguous"} for entity in entity_rows)),
        "resolution_rate": round(resolved / eligible, 6) if eligible else 0.0,
        "top_unresolved_entities": entity_counts.get("top_unresolved_entities") or [],
        "unlinked_claim_reasons": unlinked_reasons,
        "extractor_version": EVIDENCE_CHAIN_EXTRACTOR_VERSION,
        "direct_extractor_version": DIRECT_EVIDENCE_CHAIN_EXTRACTOR_VERSION,
        "linker_version": CLAIM_EVIDENCE_LINKER_VERSION,
        "evidence_chain_status": "completed" if chains else "unavailable_fulltext_required",
        "claim_evidence_link_status": "completed" if links else "failed" if chains else "unavailable",
    }


def unavailable_abstract_trace(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "reasoning_trace_id": "rt_" + claim_identity_hash(claim)[:20],
        "claim_id": claim.get("claim_id"),
        "case_id": claim.get("case_id"),
        "paper_id": claim.get("paper_id"),
        "pmid": claim.get("pmid"),
        "pmcid": claim.get("pmcid"),
        "trace_status": "unavailable_abstract_only",
        "source_scope": "abstract",
        "claim_identity_hash": claim_identity_hash(claim),
        "reasoning_steps": [],
        "author_conclusion": {},
        "experimental_context": _empty_context(),
        "strength_profile": strength_profile([]),
        "strength_level": "author_conclusion_only",
        "alternative_explanations": [],
        "limitations": [],
        "missing_links": [],
        "retrieved_passage_ids": [],
        "source_record_hash": claim_identity_hash(claim),
    }


def _not_found_trace(claim: dict[str, Any], paper: dict[str, Any], status: str, passages: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "reasoning_trace_id": "rt_" + _hash({"claim": claim_identity_hash(claim), "status": status})[:20],
        "claim_id": claim.get("claim_id"),
        "case_id": claim.get("case_id") or paper.get("case_id"),
        "paper_id": paper.get("paper_id") or claim.get("paper_id"),
        "pmid": paper.get("pmid") or claim.get("pmid"),
        "pmcid": paper.get("pmcid") or claim.get("pmcid"),
        "trace_status": status,
        "source_scope": "fulltext",
        "claim_identity_hash": claim_identity_hash(claim),
        "reasoning_steps": [],
        "author_conclusion": {},
        "experimental_context": _empty_context(),
        "strength_profile": strength_profile([]),
        "strength_level": "author_conclusion_only",
        "alternative_explanations": [],
        "limitations": [],
        "missing_links": [{"reason": error}] if error else [],
        "retrieved_passage_ids": [p["passage_id"] for p in passages],
        "source_record_hash": _hash({"claim": claim_identity_hash(claim), "status": status, "error": error}),
    }


def _trace_from_v2_observation(row: dict[str, Any]) -> dict[str, Any]:
    prov = row.get("provenance") or {}; exp = row.get("experiment") or {}; intervention = row.get("intervention") or {}
    measurement = row.get("measurement") or {}; observation = row.get("observation") or {}; interpretation = row.get("author_interpretation") or {}
    steps = []
    for role, value in (
        ("experimental_intervention", intervention.get("intervention_span")),
        ("comparison_or_control", {"text": exp.get("comparison_arm") or exp.get("control_arm")}),
        ("measurement", measurement.get("measurement_span")),
        ("observation", observation.get("observation_span")),
        ("author_interpretation", interpretation.get("interpretation_span")),
    ):
        if isinstance(value, dict) and value.get("text"):
            steps.append({"step_id": f"{row.get('observation_id')}_{role}", "role": role, "text": value.get("text"), "sentence_id": value.get("sentence_id"), "source": "fulltext_l1_v2_grounded_span"})
    context = {key: [value] for key, value in {
        "species": exp.get("species"), "model_system": exp.get("model_system"), "cell_type": exp.get("cell_type"),
        "tissue": exp.get("tissue"), "intervention_type": intervention.get("intervention_type"),
        "intervention_target": intervention.get("intervention_target_mention"), "control_group": exp.get("control_arm"),
        "dose": exp.get("dose"), "duration": exp.get("duration_time"), "assay_method": measurement.get("assay"),
        "measured_endpoint": measurement.get("measured_entity_mention") or measurement.get("outcome_mention"),
        "genotype": exp.get("genotype"), "localization": exp.get("localization"),
    }.items() if value}
    status = "complete" if steps and row.get("statement_role") == "current_study_experiment" else "partial"
    return {
        "schema_version": SCHEMA_VERSION, "reasoning_trace_id": "rt_" + _hash({"v2_observation": row.get("observation_id")})[:20],
        "claim_id": row.get("observation_id"), "paper_id": prov.get("paper_id"), "pmid": prov.get("pmid"), "pmcid": prov.get("pmcid"),
        "trace_status": status, "source_scope": "fulltext", "claim_identity_hash": _hash(row.get("observation_id")),
        "reasoning_steps": steps, "author_conclusion": interpretation, "experimental_context": context,
        "strength_profile": strength_profile(steps), "strength_level": "structured_experimental_observation",
        "alternative_explanations": [], "limitations": interpretation.get("limitation_statements") or [], "missing_links": [],
        "retrieved_passage_ids": [], "source_record_hash": _hash(row), "extraction_origin": "fulltext_l1_v2_deterministic",
        "api_call_made": False,
    }


def run_fulltext_reasoning_trace_stage(
    run_dir: str | Path,
    *,
    case_id: str | None = None,
    api_enabled: bool = False,
    network_enabled: bool = False,
    provider: str | None = None,
    model: str | None = None,
    client: Any | None = None,
    extractor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    claims = _rows(artifacts / "l35_fulltext_l1_claims.jsonl")
    v2_observations = _rows(artifacts / "fulltext_experiment_observations.jsonl")
    v2_by_id = {str(x.get("observation_id")): x for x in v2_observations}
    candidates = _rows(artifacts / "l35_fulltext_oa_candidate_papers.jsonl") + _rows(artifacts / "l35_fulltext_candidate_papers.jsonl")
    paper_by_key: dict[str, dict[str, Any]] = {}
    for paper in candidates:
        for key in (paper.get("paper_id"), paper.get("pmid"), paper.get("pmcid")):
            if key:
                paper_by_key[str(key)] = paper
    provider = provider if provider is not None else os.getenv("L1_PROVIDER", "")
    model = model if model is not None else os.getenv("MODEL_NAME", "")
    cache_dir = artifacts / "cache/fulltext_reasoning_trace"
    shared_cache_dir = Path("data/interim/cache/fulltext_reasoning_trace")
    cache_dir.mkdir(parents=True, exist_ok=True)
    shared_cache_dir.mkdir(parents=True, exist_ok=True)
    passages_out: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    api_calls = cache_hits = newly = reused = eligible = 0
    blocked = not (api_enabled and network_enabled and (client is not None or extractor is not None))
    for claim in claims:
        v2_row = v2_by_id.get(str(claim.get("observation_id") or claim.get("claim_id")))
        if v2_row:
            traces.append(_trace_from_v2_observation(v2_row)); eligible += 1
            continue
        if "full" not in str(claim.get("source_scope") or "").casefold():
            traces.append(unavailable_abstract_trace(claim))
            continue
        eligible += 1
        key = str(claim.get("paper_id") or claim.get("pmid") or claim.get("pmcid") or "")
        paper = paper_by_key.get(key) or {k: claim.get(k) for k in ("paper_id", "pmid", "pmcid", "case_id")}
        article_path = artifacts / "fulltext/pmc_oa" / str(paper.get("pmcid") or claim.get("pmcid")) / "article_text.json"
        if not article_path.is_file():
            traces.append(_not_found_trace(claim, paper, "not_found", [], "article_text_missing"))
            continue
        article = _json(article_path, {})
        passages, sentences = retrieve_claim_centered_passages(claim, article, paper)
        passages_out.extend(passages)
        if not passages:
            traces.append(_not_found_trace(claim, paper, "not_found", [], "no_claim_centered_passages"))
            continue
        cache_key = _cache_key(claim, paper, passages, provider=provider or "", model=model or "")
        cache_path = cache_dir / f"{cache_key}.json"
        shared_cache_path = shared_cache_dir / f"{cache_key}.json"
        hit_path = next((path for path in (cache_path, shared_cache_path) if path.is_file()), None)
        if hit_path and not force:
            cached = _json(hit_path, {})
            trace = cached.get("trace") if isinstance(cached.get("trace"), dict) else cached
            trace["cache_status"] = "hit"
            trace["cache_source"] = cached.get("cache_source") or {"run_dir": str(run), "cache_key": cache_key, "cache_path": str(hit_path)}
            traces.append(trace)
            cache_hits += 1
            reused += 1
            continue
        if dry_run or blocked:
            traces.append(_not_found_trace(claim, paper, "unsupported_by_retrieved_passages", passages, "reasoning_extractor_not_executed"))
            continue
        try:
            prompt = build_reasoning_prompt(claim, passages)
            raw = extractor(prompt, {"claim": claim, "paper": paper, "passages": passages}) if extractor else client.extract_json(prompt, model=model, temperature=0, top_p=1)
            api_calls += 1
            trace, trace_warnings = _validate_extracted_trace(raw or {}, claim=claim, paper=paper, passages=passages, sentences=sentences)
            trace["cache_status"] = "miss"
            for warning in trace_warnings:
                warnings.append({"claim_id": claim.get("claim_id"), "warning": warning})
            cache_payload = {"trace": trace, "cache_source": {"run_dir": str(run), "cache_key": cache_key}}
            _write_json(cache_path, cache_payload)
            _write_json(shared_cache_path, cache_payload)
            traces.append(trace)
            newly += 1
        except Exception as exc:
            traces.append(_not_found_trace(claim, paper, "extraction_failed", passages, str(exc)[:500]))
            warnings.append({"claim_id": claim.get("claim_id"), "warning": "extraction_failed", "error": str(exc)[:500]})
    _write_jsonl(artifacts / "fulltext_claim_passage_index.jsonl", passages_out)
    _write_jsonl(artifacts / "fulltext_reasoning_traces.jsonl", traces)
    _write_jsonl(artifacts / "fulltext_reasoning_trace_warnings.jsonl", warnings)
    v2_chains = evidence_chains_from_v2_observations(v2_observations)
    direct_chains = extract_direct_fulltext_evidence_chains(claims, candidates, artifacts)
    trace_chains = evidence_chains_from_traces(traces)
    direct_claim_ids = {str(row.get("claim_id")) for row in direct_chains}
    v2_claim_ids = {str(row.get("claim_id")) for row in v2_chains}
    chains = [*v2_chains, *[row for row in direct_chains if str(row.get("claim_id")) not in v2_claim_ids], *[row for row in trace_chains if str(row.get("claim_id")) not in direct_claim_ids | v2_claim_ids]]
    chains, entity_counts = normalize_evidence_chain_entities(
        chains,
        run_dir=run,
        network_enabled=False,
        api_enabled=False,
        entity_network_lookup=False,
        entity_llm_cleaner=False,
    )
    links = link_claims_to_evidence_chains(claims, chains)
    linked_claim_ids = {str(link.get("claim_id")) for link in links}
    candidate_scores_by_claim = {
        str(claim.get("claim_id")): [score_claim_chain_link(claim, chain) for chain in chains]
        for claim in claims
    }
    unlinked_reasons = [
        unlinked_reason_for_claim(claim, candidate_scores_by_claim.get(str(claim.get("claim_id")), []))
        for claim in claims
        if str(claim.get("claim_id")) not in linked_claim_ids
    ]
    _write_jsonl(artifacts / "experimental_evidence_chains.jsonl", chains)
    _write_jsonl(artifacts / "claim_evidence_links.jsonl", links)
    _write_jsonl(artifacts / "unlinked_claim_reasons.jsonl", unlinked_reasons)
    _write_json(artifacts / "experimental_evidence_chain_summary.json", evidence_chain_summary(claims, chains, links, entity_counts, unlinked_reasons))
    summary = reasoning_summary(traces, eligible, api_calls=api_calls, cache_hits=cache_hits, newly=newly, reused=reused)
    chain_summary = evidence_chain_summary(claims, chains, links, entity_counts, unlinked_reasons)
    summary.update({
        "evidence_chain_count": chain_summary["evidence_chain_count"],
        "claim_evidence_link_count": chain_summary["claim_evidence_link_count"],
        "linked_claim_count": chain_summary["linked_claim_count"],
        "unlinked_claim_count": chain_summary["unlinked_claim_count"],
        "evidence_chain_status": chain_summary["evidence_chain_status"],
        "claim_evidence_link_status": chain_summary["claim_evidence_link_status"],
        "direct_fulltext_chain_count": chain_summary["direct_fulltext_chain_count"],
        "reasoning_trace_assisted_chain_count": chain_summary["reasoning_trace_assisted_chain_count"],
        **entity_counts,
    })
    _write_json(artifacts / "fulltext_reasoning_trace_summary.json", summary)
    return summary


def reasoning_summary(traces: list[dict[str, Any]], eligible: int, *, api_calls: int = 0, cache_hits: int = 0, newly: int = 0, reused: int = 0) -> dict[str, Any]:
    counts = {status: sum(row.get("trace_status") == status for row in traces) for status in TRACE_STATUSES}
    eligible_accounted = sum(counts[x] for x in ("complete", "partial", "not_found", "unsupported_by_retrieved_passages", "extraction_failed"))
    return {
        "schema_version": "fulltext_reasoning_trace_summary_v1",
        "eligible_fulltext_claim_count": eligible,
        "reasoning_complete_count": counts["complete"],
        "reasoning_partial_count": counts["partial"],
        "reasoning_not_found_count": counts["not_found"],
        "reasoning_unsupported_count": counts["unsupported_by_retrieved_passages"],
        "extraction_failed_count": counts["extraction_failed"],
        "abstract_only_unavailable_count": counts["unavailable_abstract_only"],
        "total_reasoning_step_count": sum(len(row.get("reasoning_steps") or []) for row in traces),
        "claims_with_intervention": sum(bool((row.get("strength_profile") or {}).get("has_intervention")) for row in traces),
        "claims_with_control": sum(bool((row.get("strength_profile") or {}).get("has_control")) for row in traces),
        "claims_with_rescue": sum(bool((row.get("strength_profile") or {}).get("has_rescue_experiment")) for row in traces),
        "claims_with_blocking": sum(bool((row.get("strength_profile") or {}).get("has_blocking_experiment")) for row in traces),
        "claims_with_in_vivo_validation": sum(bool((row.get("strength_profile") or {}).get("has_in_vivo_validation")) for row in traces),
        "fully_reused_claim_count": reused,
        "partially_reused_claim_count": 0,
        "newly_processed_claim_count": newly,
        "api_call_count": api_calls,
        "cache_hit_count": cache_hits,
        "status_accounting_valid": eligible_accounted == eligible,
    }


def _context_values_from_chain(chain: dict[str, Any]) -> dict[str, list[Any]]:
    if chain.get("__link_relation") in {"weakens", "unclear"}:
        return {field: [] for field in EVIDENCE_CHAIN_FIELDS}
    system = chain.get("experimental_system") if isinstance(chain.get("experimental_system"), dict) else {}
    values = {
        "species": _normalize_list(system.get("species")),
        "model_system": _normalize_list(system.get("disease_model")),
        "cell_type": _normalize_list(system.get("cell_type") or system.get("cell_line")),
        "tissue": _normalize_list(system.get("tissue") or system.get("organ")),
        "genotype": _normalize_list(system.get("genotype")),
        "localization": _normalize_list(system.get("localization")),
        "intervention_type": [],
        "intervention_target": [],
        "control_group": [],
        "dose": [],
        "duration": [],
        "assay_method": [],
        "measured_endpoint": [],
        "validation_design": _normalize_list((chain.get("causal_design") or {}).get("causal_strength")),
    }
    for item in chain.get("interventions") or []:
        if isinstance(item, dict):
            values["intervention_target"].extend(_normalize_list(item.get("agent_raw")))
            values["dose"].extend(_normalize_list(item.get("dose")))
            values.setdefault("concentration", [])
            values["duration"].extend(_normalize_list(item.get("duration") or item.get("timing")))
    for item in chain.get("comparators") or []:
        if isinstance(item, dict):
            values["control_group"].extend(_normalize_list(item.get("description") or item.get("comparator_type")))
    for item in chain.get("measurements") or []:
        if isinstance(item, dict):
            values["assay_method"].extend(_normalize_list(item.get("assay")))
            values["measured_endpoint"].extend(_normalize_list(item.get("endpoint")))
    for item in chain.get("observed_results") or []:
        if isinstance(item, dict):
            values["measured_endpoint"].extend(_normalize_list(item.get("endpoint")))
    return {key: [x for x in vals if x not in (None, "", [], {})] for key, vals in values.items()}


def _agreement(values: list[ConsolidatedContextValue]) -> str:
    unique = {str(item.value).casefold() for item in values}
    source_types = {item.source_type for item in values}
    if len(unique) <= 1 and len(source_types) <= 1:
        return "single_source"
    if len(unique) <= 1:
        return "consistent"
    return "mixed"


def consolidate_context_for_claim(claim: dict[str, Any], linked_chains: list[dict[str, Any]], trace: dict[str, Any] | None = None) -> dict[str, Any]:
    claim_context_raw = claim.get("context") if isinstance(claim.get("context"), dict) else {}
    claim_scoped = {field: _normalize_list(claim_context_raw.get(field)) for field in CLAIM_SCOPED_FIELDS}
    evidence_chain: dict[str, list[Any]] = {field: [] for field in EVIDENCE_CHAIN_FIELDS}
    evidence_chain_sources: dict[str, list[dict[str, Any]]] = {}
    for chain in linked_chains:
        chain_values = _context_values_from_chain(chain)
        for field, values in chain_values.items():
            if field not in evidence_chain:
                evidence_chain[field] = []
            for value in values:
                if value not in evidence_chain[field]:
                    evidence_chain[field].append(value)
                relation = chain.get("__link_relation") or "supports"
                evidence_chain_sources.setdefault(field, []).append({
                    "value": value,
                    "source_type": "contextual_only" if relation == "contextualizes" else "evidence_chain_context",
                    "source_ids": [chain.get("chain_id")],
                    "source_link_ids": [chain.get("__link_id")] if chain.get("__link_id") else [],
                    "confidence": chain.get("extraction_confidence", 0.5),
                })
    consolidated: dict[str, list[dict[str, Any]]] = {}
    provenance: dict[str, list[dict[str, Any]]] = {}
    conflicts: list[dict[str, Any]] = []
    sentence_ids = [sid for step in (trace or {}).get("reasoning_steps") or [] for sid in step.get("sentence_ids") or []]
    for field in sorted(set(CLAIM_SCOPED_FIELDS) | set(EVIDENCE_CHAIN_FIELDS)):
        values: list[ConsolidatedContextValue] = []
        for source, mapping in (("explicit_claim_context", claim_scoped), ("evidence_chain_context", evidence_chain)):
            for value in mapping.get(field, []):
                source_rows = [item for item in evidence_chain_sources.get(field, []) if item.get("value") == value]
                source_ids = [str(claim.get("claim_id"))] if source == "explicit_claim_context" else [str(item.get("source_ids", [""])[0]) for item in source_rows]
                source_type = source if source == "explicit_claim_context" else ("evidence_chain_context")
                entry = ConsolidatedContextValue(value=value, source_type=source_type, source_ids=[x for x in source_ids if x], confidence=0.95 if source == "explicit_claim_context" else 0.75)
                if entry not in values:
                    values.append(entry)
                    provenance.setdefault(field, []).append({
                        "value": value,
                        "source_type": source_rows[0].get("source_type") if source_rows else source,
                        "source_ids": entry.source_ids,
                        "source_link_ids": [x for row in source_rows for x in row.get("source_link_ids", [])],
                        "sentence_ids": sentence_ids if source == "evidence_chain_context" else [],
                    })
        agreement = _agreement(values)
        for entry in values:
            entry.agreement_status = agreement  # type: ignore[misc]
        consolidated[field] = [entry.model_dump(mode="json") for entry in values]
        if agreement == "mixed":
            conflicts.append({"field": field, "values": [entry.value for entry in values], "sources": provenance.get(field, []), "agreement_status": agreement})
    missing = [field for field, values in consolidated.items() if not values]
    return {
        "schema_version": CONSOLIDATION_SCHEMA_VERSION,
        "claim_id": claim.get("claim_id"),
        "reasoning_trace_id": (trace or {}).get("reasoning_trace_id"),
        "trace_status": (trace or {}).get("trace_status"),
        "claim_context": claim_scoped,
        "explicit_claim_context": claim_scoped,
        "reasoning_context": evidence_chain,
        "claim_scoped_context": claim_scoped,
        "evidence_chain_context": evidence_chain,
        "consolidated_context": consolidated,
        "field_provenance": provenance,
        "context_conflicts": conflicts,
        "missing_context_fields": missing,
        "linked_chain_ids": [chain.get("chain_id") for chain in linked_chains],
        "source_chain_ids": [chain.get("chain_id") for chain in linked_chains],
        "source_link_ids": [chain.get("__link_id") for chain in linked_chains if chain.get("__link_id")],
        "strength_profile": (trace or {}).get("strength_profile") or {},
        "context_rule_version": CONTEXT_RULE_VERSION,
        "source_record_hash": _hash({"claim": claim_identity_hash(claim), "chains": [chain.get("chain_id") for chain in linked_chains], "rule": CONTEXT_RULE_VERSION}),
    }


def consolidate_context_for_trace(claim: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    row = consolidate_context_for_claim(claim, [], trace)
    trace_context_raw = trace.get("experimental_context") if isinstance(trace.get("experimental_context"), dict) else {}
    trace_context = {field: _normalize_list(trace_context_raw.get(field)) for field in EVIDENCE_CHAIN_FIELDS}
    for field, values in trace_context.items():
        if values and not row["evidence_chain_context"].get(field):
            row["evidence_chain_context"][field] = values
            row["reasoning_context"][field] = values
            row.setdefault("field_provenance", {})[field] = [
                {
                    "value": value,
                    "source": "reasoning_trace",
                    "source_type": "evidence_chain_context",
                    "source_ids": [str(trace.get("reasoning_trace_id") or "")],
                    "sentence_ids": [sid for step in trace.get("reasoning_steps") or [] for sid in step.get("sentence_ids") or []],
                }
                for value in values
            ]
            row["consolidated_context"][field] = [
                ConsolidatedContextValue(
                    value=value,
                    source_type="evidence_chain_context",
                    source_ids=[str(trace.get("reasoning_trace_id") or "")],
                    confidence=0.7,
                    agreement_status="single_source",
                ).model_dump(mode="json")
                for value in values
            ]
    row["source_record_hash"] = _hash({"claim": claim_identity_hash(claim), "trace": trace.get("source_record_hash"), "rule": CONTEXT_RULE_VERSION})
    return row


def run_fulltext_context_consolidation_stage(run_dir: str | Path, *, case_id: str | None = None) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    claim_rows = _rows(artifacts / "l35_fulltext_l1_claims.jsonl")
    claims = {str(row.get("claim_id")): row for row in claim_rows}
    traces = _rows(artifacts / "fulltext_reasoning_traces.jsonl")
    chains = {str(row.get("chain_id")): row for row in _rows(artifacts / "experimental_evidence_chains.jsonl")}
    links = _rows(artifacts / "claim_evidence_links.jsonl")
    if not chains and traces:
        derived_chains = evidence_chains_from_traces(traces)
        derived_links = link_claims_to_evidence_chains(claim_rows, derived_chains)
        derived_linked = {str(link.get("claim_id")) for link in derived_links}
        derived_unlinked = [
            unlinked_reason_for_claim(claim, [score_claim_chain_link(claim, chain) for chain in derived_chains])
            for claim in claim_rows
            if str(claim.get("claim_id")) not in derived_linked
        ]
        _write_jsonl(artifacts / "experimental_evidence_chains.jsonl", derived_chains)
        _write_jsonl(artifacts / "claim_evidence_links.jsonl", derived_links)
        _write_jsonl(artifacts / "unlinked_claim_reasons.jsonl", derived_unlinked)
        _write_json(artifacts / "experimental_evidence_chain_summary.json", evidence_chain_summary(claim_rows, derived_chains, derived_links, {}, derived_unlinked))
        chains = {str(row.get("chain_id")): row for row in derived_chains}
        links = derived_links
    trace_by_claim = {str(row.get("claim_id")): row for row in traces}
    links_by_claim: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        if link.get("relation") in {"supports", "qualifies", "contextualizes"}:
            links_by_claim.setdefault(str(link.get("claim_id")), []).append(link)
    consolidations = [
        consolidate_context_for_claim(
            claim,
            [
                {**chains[str(link.get("chain_id"))], "__link_relation": link.get("relation"), "__link_id": link.get("link_id")}
                for link in links_by_claim.get(str(claim.get("claim_id")), [])
                if str(link.get("chain_id")) in chains
            ],
            trace_by_claim.get(str(claim.get("claim_id"))),
        )
        for claim in claim_rows
    ]
    _write_jsonl(artifacts / "fulltext_context_consolidations.jsonl", consolidations)
    summary = {
        "schema_version": "fulltext_context_consolidation_summary_v1",
        "claim_count": len(claims),
        "trace_count": len(traces),
        "evidence_chain_count": len(chains),
        "claim_evidence_link_count": len(links),
        "consolidation_count": len(consolidations),
        "claims_with_reasoning_context": sum(any(v for v in row.get("evidence_chain_context", {}).values()) for row in consolidations),
        "context_enriched_claim_count": sum(any(v for v in row.get("evidence_chain_context", {}).values()) for row in consolidations),
        "context_conflict_count": sum(len(row.get("context_conflicts") or []) for row in consolidations),
        "context_rule_version": CONTEXT_RULE_VERSION,
        "claim_extraction_status": "reused",
        "evidence_chain_status": "completed" if chains else "unavailable",
        "claim_evidence_link_status": "completed" if links else "unavailable",
        "context_consolidation_status": "completed",
        "api_call_count": 0,
    }
    _write_json(artifacts / "fulltext_context_consolidation_summary.json", summary)
    return summary


def optional_reasoning_artifact_hashes(run_dir: str | Path) -> dict[str, str]:
    artifacts = Path(run_dir) / "artifacts"
    names = (
        "fulltext_claim_passage_index.jsonl",
        "fulltext_reasoning_traces.jsonl",
        "fulltext_reasoning_trace_summary.json",
        "experimental_evidence_chains.jsonl",
        "claim_evidence_links.jsonl",
        "unlinked_claim_reasons.jsonl",
        "experimental_evidence_chain_summary.json",
        "fulltext_context_consolidations.jsonl",
        "fulltext_context_consolidation_summary.json",
    )
    return {name: sha256_file(artifacts / name) for name in names if (artifacts / name).is_file()}
