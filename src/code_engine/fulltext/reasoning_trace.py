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

from code_engine.integration.atlas_handoff import canonical_json, sha256_file

SCHEMA_VERSION = "fulltext_reasoning_trace_v1"
CONSOLIDATION_SCHEMA_VERSION = "fulltext_context_consolidation_v1"
PROMPT_VERSION = "fulltext_reasoning_trace_prompt_v1"
EXTRACTOR_CODE_VERSION = "fulltext_reasoning_trace_extractor_v1"
CONTEXT_RULE_VERSION = "fulltext_context_consolidation_rules_v1"
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
        "claim_id": claim.get("claim_id"),
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
        passage_id = "pass_" + hashlib.sha1(f"{claim.get('claim_id')}|{sent['sentence_id']}".encode()).hexdigest()[:16]
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
            "passage_hash": _hash({"sentence_id": sent["sentence_id"], "text": text}),
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
    summary = reasoning_summary(traces, eligible, api_calls=api_calls, cache_hits=cache_hits, newly=newly, reused=reused)
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


def consolidate_context_for_trace(claim: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    claim_context_raw = claim.get("context") if isinstance(claim.get("context"), dict) else {}
    claim_scoped = {field: _normalize_list(claim_context_raw.get(field)) for field in CLAIM_SCOPED_FIELDS}
    trace_context_raw = trace.get("experimental_context") if isinstance(trace.get("experimental_context"), dict) else {}
    evidence_chain = {field: _normalize_list(trace_context_raw.get(field)) for field in EVIDENCE_CHAIN_FIELDS}
    consolidated: dict[str, list[Any]] = {}
    provenance: dict[str, list[dict[str, Any]]] = {}
    conflicts: list[dict[str, Any]] = []
    sentence_ids = [sid for step in trace.get("reasoning_steps") or [] for sid in step.get("sentence_ids") or []]
    for field in sorted(set(CLAIM_SCOPED_FIELDS) | set(EVIDENCE_CHAIN_FIELDS)):
        values: list[Any] = []
        for source, mapping in (("claim", claim_scoped), ("reasoning_trace", evidence_chain)):
            for value in mapping.get(field, []):
                if value not in values:
                    values.append(value)
                    provenance.setdefault(field, []).append({"value": value, "source": source, "sentence_ids": sentence_ids if source == "reasoning_trace" else []})
        consolidated[field] = values
        if len({str(v).casefold() for v in values}) > 1:
            conflicts.append({"field": field, "values": values, "sources": provenance.get(field, [])})
    missing = [field for field, values in consolidated.items() if not values]
    return {
        "schema_version": CONSOLIDATION_SCHEMA_VERSION,
        "claim_id": claim.get("claim_id"),
        "reasoning_trace_id": trace.get("reasoning_trace_id"),
        "trace_status": trace.get("trace_status"),
        "claim_context": claim_scoped,
        "reasoning_context": evidence_chain,
        "claim_scoped_context": claim_scoped,
        "evidence_chain_context": evidence_chain,
        "consolidated_context": consolidated,
        "field_provenance": provenance,
        "context_conflicts": conflicts,
        "missing_context_fields": missing,
        "strength_profile": trace.get("strength_profile") or {},
        "context_rule_version": CONTEXT_RULE_VERSION,
        "source_record_hash": _hash({"claim": claim_identity_hash(claim), "trace": trace.get("source_record_hash"), "rule": CONTEXT_RULE_VERSION}),
    }


def run_fulltext_context_consolidation_stage(run_dir: str | Path, *, case_id: str | None = None) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    claims = {str(row.get("claim_id")): row for row in _rows(artifacts / "l35_fulltext_l1_claims.jsonl")}
    traces = _rows(artifacts / "fulltext_reasoning_traces.jsonl")
    consolidations = [consolidate_context_for_trace(claims.get(str(trace.get("claim_id")), {}), trace) for trace in traces]
    _write_jsonl(artifacts / "fulltext_context_consolidations.jsonl", consolidations)
    summary = {
        "schema_version": "fulltext_context_consolidation_summary_v1",
        "claim_count": len(claims),
        "trace_count": len(traces),
        "consolidation_count": len(consolidations),
        "claims_with_reasoning_context": sum(any(v for v in row.get("reasoning_context", {}).values()) for row in consolidations),
        "context_conflict_count": sum(len(row.get("context_conflicts") or []) for row in consolidations),
        "context_rule_version": CONTEXT_RULE_VERSION,
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
        "fulltext_context_consolidations.jsonl",
        "fulltext_context_consolidation_summary.json",
    )
    return {name: sha256_file(artifacts / name) for name in names if (artifacts / name).is_file()}
