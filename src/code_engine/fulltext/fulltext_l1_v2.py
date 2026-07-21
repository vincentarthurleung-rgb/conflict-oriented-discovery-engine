"""Fulltext L1 v2 extraction without canonicalization or formal-science decisions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.fulltext.fulltext_l1_extractor import (
    CHUNKER_VERSION, SECTION_WEIGHTS, _jsonl, _shared_cache_enabled_for_run,
    chunk_text, classify_section, select_sections,
)
from code_engine.schemas.fulltext_observation import FulltextL1V2Response

SCHEMA_VERSION = "fulltext_l1_experimental_observation_schema_v2"
PROMPT_VERSION = "fulltext_experimental_observation_prompt_v2"
PARSER_VERSION = "fulltext_experimental_observation_parser_v2"
EXTRACTOR_VERSION = "fulltext_l1_extractor_v2"
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
)


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
    return f"""Extract experimental observations from the supplied full-text block and return strict JSON only.
Schema: {{"schema_version":"{SCHEMA_VERSION}","experimental_observations":[...]}}.
Rules:
{rules}
TARGET_PRIOR (non-authoritative): {json.dumps(seed, ensure_ascii=False)}
PAPER_METADATA: {json.dumps(block['paper_metadata'], ensure_ascii=False)}
CONTEXT_BINDING_ORDER: evidence_span > experiment_result_block > figure_or_table > linked_methods > subsection > paper_metadata > abstract_prior
FULLTEXT_BLOCK:
{block['text']}"""


def parse_response(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, str):
        response = json.loads(response)
    validated = FulltextL1V2Response.model_validate(response)
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


def run_fulltext_l1_v2_extraction(*, run_dir: Path, fulltext_candidates_path: Path, parsed_articles_dir: Path,
                                  l1_provider: str, l1_model: str, api_enabled: bool, network_enabled: bool,
                                  client: Any | None = None, dry_run: bool = False, max_papers: int = 20,
                                  max_sections_per_paper: int = 12, max_chunks_per_paper: int = 24,
                                  max_chars_per_chunk: int = 6000, max_total_chunks: int = 200,
                                  read_timeout_seconds: float = 240, max_retries: int = 1,
                                  parent_abstract_run_id: str | None = None) -> dict[str, Any]:
    run = Path(run_dir); artifacts = run / "artifacts"; cache = artifacts / "cache/fulltext_l1_v2"; cache.mkdir(parents=True, exist_ok=True)
    shared = Path("data/interim/cache/fulltext_l1_v2"); shared_enabled = _shared_cache_enabled_for_run(run)
    if shared_enabled: shared.mkdir(parents=True, exist_ok=True)
    config = {"max_sections": max_sections_per_paper, "max_chunks_per_paper": max_chunks_per_paper, "max_chars": max_chars_per_chunk, "max_total_chunks": max_total_chunks}
    config_hash = _hash(config); observations: list[dict[str, Any]] = []; executions = []; bindings = []
    api_calls = cache_hits = parse_errors = 0; total_blocks = 0
    for paper in _jsonl(Path(fulltext_candidates_path))[:max_papers]:
        article_path = Path(parsed_articles_dir) / str(paper.get("pmcid")) / "article_text.json"
        if not article_path.is_file(): continue
        source_hash = hashlib.sha256(article_path.read_bytes()).hexdigest(); article = json.loads(article_path.read_text(encoding="utf-8"))
        blocks = build_experiment_blocks(article, paper, max_sections=max_sections_per_paper, max_chars=max_chars_per_chunk, max_chunks=max_chunks_per_paper)
        for block in blocks:
            if total_blocks >= max_total_chunks: break
            total_blocks += 1
            block["paper_metadata"]["fulltext_source_hash"] = source_hash
            key = cache_key(source_fulltext_hash=source_hash, chunk_hash=block["chunk_hash"], provider=l1_provider, model=l1_model, config_hash=config_hash, candidate_prior_hash=_hash({k: paper.get(k) for k in ("subject", "object", "abstract_observation_ids")}))
            paths = [cache / f"{key}.json"] + ([shared / f"{key}.json"] if shared_enabled else [])
            hit = next((p for p in paths if p.is_file()), None); raw_rows = []
            if hit:
                payload = json.loads(hit.read_text(encoding="utf-8"))
                if payload.get("schema_version") != SCHEMA_VERSION: continue
                raw_rows = parse_response(payload.get("response")); cache_hits += 1; status = "cache_hit"
            elif dry_run or not (api_enabled and network_enabled and client is not None):
                executions.append({"block_id": block["block_id"], "status": "planned" if dry_run else "blocked", "api_called": False, "cache_key": key}); continue
            else:
                response = None
                try:
                    response = client.extract_json(build_prompt(paper, block), model=l1_model, temperature=0, top_p=1, timeout=read_timeout_seconds, max_retries=max_retries)
                    api_calls += 1; raw_rows = parse_response(response); status = "completed"
                    payload = {"schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(), "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION, "source_fulltext_hash": source_hash, "response": response}
                    paths[0].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    if len(paths) > 1: paths[1].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    parse_errors += 1; raw_path = cache / f"{key}.raw_error.json"
                    raw_path.write_text(json.dumps({"raw_response": response, "error": str(exc), "retryable": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    executions.append({"block_id": block["block_id"], "status": "parse_error", "api_called": True, "cache_key": key, "raw_response_artifact": str(raw_path)}); continue
            for row in raw_rows:
                row["parent_abstract_run_id"] = row.get("parent_abstract_run_id") or parent_abstract_run_id
                row["provenance"]["fulltext_source_hash"] = source_hash
                observations.append(row)
                bindings.append({"observation_id": row["observation_id"], "experiment_id": row["experiment"]["experiment_id"], "context_source": row["experiment"].get("context_source") or block["context_sources"], "binding_confidence": row["experiment"].get("binding_confidence", 0), "source_block_id": block["block_id"], "cross_experiment_binding": False})
            executions.append({"block_id": block["block_id"], "status": status, "api_called": status == "completed", "cache_key": key, "observation_count": len(raw_rows)})
    claims = [observation_as_legacy_claim(x) for x in observations]
    def write_jsonl(name: str, rows: list[dict[str, Any]]): (artifacts / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    write_jsonl("fulltext_experiment_observations.jsonl", observations); write_jsonl("fulltext_context_binding_audit.jsonl", bindings); write_jsonl("fulltext_l1_v2_execution_records.jsonl", executions)
    write_jsonl("l35_fulltext_l1_chunks.jsonl", [{"chunk_id": x.get("block_id"), "cache_key": x.get("cache_key"), "cache_status": "hit" if x.get("status") == "cache_hit" else "miss", "api_call_made": bool(x.get("api_called")), "extraction_status": x.get("status")} for x in executions])
    write_jsonl("l35_fulltext_l1_claims.jsonl", claims)
    fields = {"species": "species", "intervention": "intervention_target_mention", "comparison": "comparison_arm", "measurement": "measurement_dimension"}
    coverage = {"schema_version": "fulltext_l1_schema_coverage_v1", "v1_record_count": 0, "v2_record_count": len(observations), "experiment_count": len({x["experiment"]["experiment_id"] for x in observations}), "observation_count": len(observations), "context_binding_coverage": sum(bool(x.get("context_source")) for x in bindings) / len(bindings) if bindings else 0.0}
    coverage.update({f"{name}_coverage": sum(bool((x["experiment"] if name in {"species", "comparison"} else x[name]).get(field)) and (x["measurement"].get(field) != "unknown" if name == "measurement" else True) for x in observations) / len(observations) if observations else 0.0 for name, field in fields.items()})
    statuses = {str(x.get("status")) for x in executions}
    l1_status = "completed" if observations else "planned" if dry_run else "skipped_provider_unavailable" if statuses and statuses <= {"blocked"} else "failed" if parse_errors and statuses <= {"parse_error"} else "completed_no_observations"
    summary = {"schema_version": SCHEMA_VERSION, "fulltext_l1_status": l1_status, "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(), "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION, "source_document_count": len({x["provenance"]["source_document_id"] for x in observations}), "experiment_count": coverage["experiment_count"], "observation_count": len(observations), "api_calls_made": api_calls, "cache_hits": cache_hits, "parse_errors": parse_errors, "paid_call_count": api_calls, "network_call_count": api_calls, "download_call_count": 0, "config_hash": config_hash}
    (artifacts / "fulltext_l1_v2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); (artifacts / "fulltext_l1_schema_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"summary": summary, "observations": observations, "claims": claims, "executions": executions}
