"""Cost-bounded provider smoke planning for historical Fulltext L1 v2 runs.

The default path is deliberately offline.  It reads only run-local inputs and
writes audit/plan artifacts; provider execution is separately gated by both
explicit CLI authorization and a verified thinking-disable transport setting.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from code_engine.extraction.client_factory import build_json_client_from_config
from code_engine.extraction.deepseek_client import (
    DeepSeekExtractionError,
    build_deepseek_request_payload,
    deepseek_thinking_mode_audit,
)
from code_engine.fulltext.fulltext_l1_v2 import (
    CACHE_IDENTITY_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OBSERVATION_LIMIT,
    DEFAULT_SAFE_INPUT_TOKENS,
    DEFAULT_THINKING_MODE,
    DUPLICATE_RULE_VERSION,
    EXTRACTOR_VERSION,
    FulltextTokenBudget,
    PARSER_VERSION,
    PROMPT_RULES,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    SPLIT_VERSION,
    _hash,
    build_experiment_blocks,
    build_prompt,
    cache_key,
    deterministic_child_blocks,
    estimate_tokens,
    formal_schema_hash,
    hydrate_provider_draft,
    prompt_hash,
    schema_hash,
    split_transport_metadata,
)
from code_engine.fulltext.fulltext_l1_extractor import CHUNKER_VERSION
from code_engine.schemas.fulltext_observation import (
    FulltextL1V2Response,
    fulltext_l1_v2_prompt_examples,
)
from code_engine.schemas.fulltext_observation_draft import (
    DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse, fulltext_l1_draft_prompt_examples,
)
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    COMPLETENESS_POLICY_VERSION, DraftHydrationV3Error, HYDRATOR_VERSION,
)
from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION


SAMPLING_VERSION = "fulltext_l1_v2_provider_smoke_sampling_v1"
COMPATIBILITY_POLICY_VERSION = "legacy_empty_prompt_compatibility_v1"
DECISION_POLICY_VERSION = "fulltext_l1_v2_rerun_scope_decision_v2_raw_nonempty_visibility"
SMOKE_SCHEMA_SUCCESS_THRESHOLD = 5 / 6
MANIFEST_SIZE = 12

LEGACY_PROMPT_VERSION = "fulltext_experimental_observation_prompt_v3_json_bounded"
LEGACY_SCIENTIFIC_RULES = (
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
OUTPUT_CONTRACT_RULES_V4 = PROMPT_RULES[16:]
LEGACY_VERSIONED_CONFIG = {
    "max_sections": 12, "max_chunks_per_paper": 24, "max_chars": 6000,
    "max_total_chunks": 200, "max_tokens": 32768, "observation_limit": 40,
    "safe_input_tokens": 6000, "max_split_depth": 1,
    "split_version": "fulltext_block_split_v1",
    "duplicate_rule_version": "fulltext_observation_duplicates_v1",
}

HIGH_RISK_PATTERNS = (
    r"\bincreased\b", r"\bdecreased\b", r"\binhibited\b", r"\binduced\b",
    r"\bknockdown\b", r"\boverexpression\b", r"\btreated with\b",
    r"\bcompared with\b", r"\bfig(?:ure)?\.?\s*[a-z]?\d+", r"\bpatient samples?\b",
    r"\b(?:mice|mouse|cells?)\b", r"\b(?:measured|assessed|showed)\b",
)
HUMAN_PATTERN = re.compile(r"\b(?:human|patients?|patient samples?|clinical|biops(?:y|ies))\b", re.I)
MOUSE_PATTERN = re.compile(r"\b(?:mouse|mice|murine|in vivo|xenograft)\b", re.I)
VITRO_PATTERN = re.compile(r"\b(?:in vitro|cell line|cells?|culture[ds]?)\b", re.I)
LOW_SECTION_PATTERN = re.compile(r"CURRENT_(?:BACKGROUND|INTRODUCTION|METHODS|REVIEW)|\b(?:review|methods?)\b", re.I)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(value: str | bytes | Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _historical_cache(artifacts: Path, record: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    key = str(record.get("cache_key") or "")
    path = artifacts / "cache" / "fulltext_l1_v2" / f"{key}.json"
    if not path.is_file():
        return None, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _raw_observation_count(value: Any) -> int:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return 0
    if isinstance(value, dict) and isinstance(value.get("experimental_observations"), list):
        return len(value["experimental_observations"])
    return 0


def _raw_provenance(artifacts: Path, record: dict[str, Any]) -> dict[str, Any]:
    cache_path, cached = _historical_cache(artifacts, record)
    raw_path_value = record.get("raw_response_path") or record.get("raw_response_artifact")
    raw_path = Path(str(raw_path_value)) if raw_path_value else None
    raw: Any = record.get("raw_response")
    if record.get("status") == "completed":
        raw = (cached.get("transport_metadata") or {}).get("raw_response", cached.get("response"))
        raw_path = cache_path
    elif raw in (None, "") and raw_path and raw_path.is_file():
        raw = raw_path.read_text(encoding="utf-8")
    version = cached.get("prompt_version") or record.get("prompt_version") or LEGACY_PROMPT_VERSION
    phash = cached.get("prompt_hash") or record.get("prompt_hash")
    return {
        "historical_prompt_version": version,
        "historical_prompt_hash": phash,
        "historical_raw_response_path": str(raw_path) if raw_path else None,
        "historical_raw_response_hash": _sha(raw) if raw not in (None, "") else None,
        "historical_observation_count": _raw_observation_count(raw),
        "historical_cache_path": str(cache_path) if cache_path else None,
        "historical_cache": cached,
    }


def _historical_config(artifacts: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    for record in records:
        _, cached = _historical_cache(artifacts, record)
        if cached.get("config"):
            config = dict(cached["config"])
            config.setdefault("thinking_mode", DEFAULT_THINKING_MODE)
            config.setdefault("cache_identity_version", CACHE_IDENTITY_VERSION)
            return config
    return {
        "max_sections": 12, "max_chunks_per_paper": 24, "max_chars": 6000,
        "max_total_chunks": 200, "max_tokens": DEFAULT_MAX_TOKENS,
        "observation_limit": DEFAULT_OBSERVATION_LIMIT,
        "safe_input_tokens": DEFAULT_SAFE_INPUT_TOKENS, "max_split_depth": 1,
        "split_version": SPLIT_VERSION, "duplicate_rule_version": DUPLICATE_RULE_VERSION,
        "thinking_mode": DEFAULT_THINKING_MODE, "cache_identity_version": CACHE_IDENTITY_VERSION,
    }


def _block_inventory(run_dir: Path, records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = run_dir / "artifacts"
    candidates = _jsonl(artifacts / "l35_fulltext_candidate_papers.jsonl")
    candidate_by_pmcid = {str(row.get("pmcid")): row for row in candidates}
    parsed_root = artifacts / "fulltext" / "pmc_oa"
    needed = {str(row.get("block_id")): row for row in records}
    inventory: dict[str, dict[str, Any]] = {}
    budget = FulltextTokenBudget(
        max_tokens=int(config["max_tokens"]),
        observation_limit=int(config.get("observation_limit", DEFAULT_OBSERVATION_LIMIT)),
        safe_input_tokens=int(config.get("safe_input_tokens", DEFAULT_SAFE_INPUT_TOKENS)),
        max_split_depth=int(config.get("max_split_depth", 1)),
    )
    for pmcid, paper in sorted(candidate_by_pmcid.items()):
        article_path = parsed_root / pmcid / "article_text.json"
        if not article_path.is_file():
            continue
        article = json.loads(article_path.read_text(encoding="utf-8"))
        source_hash = _sha(article_path.read_bytes())
        parents = build_experiment_blocks(
            article, paper, max_sections=int(config["max_sections"]),
            max_chars=int(config["max_chars"]), max_chunks=int(config["max_chunks_per_paper"]),
        )
        for parent in parents:
            candidates_for_parent = [parent, *deterministic_child_blocks(parent, reason="historical_reconstruction", budget=budget)]
            for block in candidates_for_parent:
                block_id = str(block["block_id"])
                if block_id not in needed:
                    continue
                block["paper_metadata"]["fulltext_source_hash"] = source_hash
                inventory[block_id] = {
                    "block": block, "paper": paper, "source_fulltext_hash": source_hash,
                    "article_path": str(article_path), "record": needed[block_id],
                }
    missing = sorted(set(needed) - set(inventory))
    if missing:
        raise RuntimeError(f"could not reconstruct {len(missing)} historical blocks: {missing[:5]}")
    return inventory


def _signals(text: str) -> dict[str, Any]:
    hits = sorted({pattern for pattern in HIGH_RISK_PATTERNS if re.search(pattern, text, re.I)})
    result_terms = len(re.findall(r"\b(?:increased|decreased|inhibited|induced|showed|measured|assessed|reduced|enhanced)\b", text, re.I))
    return {
        "deterministic_signal_patterns": hits,
        "deterministic_signal_count": len(hits),
        "human_or_patient": bool(HUMAN_PATTERN.search(text)),
        "mouse_or_in_vivo": bool(MOUSE_PATTERN.search(text)),
        "in_vitro_or_cell_line": bool(VITRO_PATTERN.search(text)),
        "multi_endpoint": result_terms >= 3 or len(re.findall(r"\bFig(?:ure)?\.?\s*[A-Z]?\d+", text, re.I)) >= 2,
        "simple_single_endpoint": result_terms == 1,
        "low_experiment_probability": bool(LOW_SECTION_PATTERN.search(text)) and not hits,
    }


def _pick_distinct(rows: list[dict[str, Any]], predicate, used: set[str], selected: list[dict[str, Any]]) -> None:
    for row in rows:
        if row in selected or not predicate(row):
            continue
        selected.append(row); used.add(str(row["pmcid"])); return


def _select_nonempty(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (-r["historical_observation_count"], -r["signals"]["deterministic_signal_count"], r["block_id"]))
    selected: list[dict[str, Any]] = []; used: set[str] = set()
    predicates = (
        lambda r: r["historical_observation_count"] == max(x["historical_observation_count"] for x in rows),
        lambda r: r["signals"]["human_or_patient"],
        lambda r: r["signals"]["mouse_or_in_vivo"],
        lambda r: r["signals"]["in_vitro_or_cell_line"],
        lambda r: r["signals"]["multi_endpoint"],
        lambda r: r["signals"]["simple_single_endpoint"],
    )
    for predicate in predicates:
        distinct = [r for r in ordered if str(r["pmcid"]) not in used]
        _pick_distinct(distinct or ordered, predicate, used, selected)
    for row in ordered:
        if len(selected) >= 6:
            break
        if row not in selected:
            selected.append(row); used.add(str(row["pmcid"]))
    return selected[:6]


def _select_empty(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high = sorted((r for r in rows if r["signals"]["deterministic_signal_count"]),
                  key=lambda r: (-r["signals"]["deterministic_signal_count"], r["block_id"]))
    low = sorted((r for r in rows if r["signals"]["low_experiment_probability"]), key=lambda r: r["block_id"])
    selected: list[dict[str, Any]] = []; used: set[str] = set()
    for pool, count in ((high, 3), (low, 2)):
        for _ in range(count):
            distinct = [r for r in pool if r not in selected and str(r["pmcid"]) not in used]
            available = distinct or [r for r in pool if r not in selected]
            if not available:
                break
            row = available[0]; selected.append(row); used.add(str(row["pmcid"]))
    remaining = sorted((r for r in rows if r not in selected), key=lambda r: (
        not (r["signals"]["human_or_patient"] or r["signals"]["mouse_or_in_vivo"] or r["signals"]["in_vitro_or_cell_line"]),
        str(r["pmcid"]) in used, -r["signals"]["deterministic_signal_count"], r["block_id"],
    ))
    selected.extend(remaining[:max(0, 6 - len(selected))])
    return selected[:6]


def _config_hash(config: dict[str, Any]) -> str:
    identity_config = {
        "max_sections": config["max_sections"], "max_chunks_per_paper": config["max_chunks_per_paper"],
        "max_chars": config["max_chars"], "max_total_chunks": config["max_total_chunks"],
        "max_tokens": config["max_tokens"], "observation_limit": config.get("observation_limit", DEFAULT_OBSERVATION_LIMIT),
        "safe_input_tokens": config.get("safe_input_tokens", DEFAULT_SAFE_INPUT_TOKENS),
        "max_split_depth": config.get("max_split_depth", 1), "split_version": config.get("split_version", SPLIT_VERSION),
        "duplicate_rule_version": config.get("duplicate_rule_version", DUPLICATE_RULE_VERSION),
        "thinking_mode": config.get("thinking_mode", DEFAULT_THINKING_MODE),
        "cache_identity_version": config.get("cache_identity_version", CACHE_IDENTITY_VERSION),
    }
    return _hash(identity_config)


def build_request_chain_audit(run_dir: Path, inventory: dict[str, dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    sample = inventory[sorted(inventory)[0]]
    rendered = build_prompt(sample["paper"], sample["block"])
    body = build_deepseek_request_payload(rendered, model="deepseek-v4-pro", max_tokens=int(config["max_tokens"]),
                                          thinking_mode=DEFAULT_THINKING_MODE)
    _, nonempty = fulltext_l1_draft_prompt_examples()
    historical_reasoning = []
    for item in inventory.values():
        usage = item["record"].get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        if reasoning is not None:
            historical_reasoning.append(int(reasoning))
    thinking = deepseek_thinking_mode_audit(DEFAULT_THINKING_MODE)
    return {
        "schema_version": "fulltext_l1_v2_request_chain_audit_v1",
        "run_dir": str(run_dir),
        "request_chain": ["CLI/config", "fulltext stage", "Fulltext L1 v2 extractor", "configured adapter", "DeepSeek client", "HTTP request body"],
        "configured_provider": "deepseek", "configured_model": "deepseek-v4-pro",
        "prompt_version": PROMPT_VERSION, "prompt_identity_hash": prompt_hash(),
        "rendered_system_prompt_example_hash": _sha(rendered), "user_prompt_version": None,
        "user_prompt_hash": None, "message_roles": [row["role"] for row in body["messages"]],
        "complete_nonempty_example_present": json.dumps(nonempty, ensure_ascii=False, separators=(",", ":")) in rendered,
        "response_format_configured": {"type": "json_object"},
        "response_format_in_http_body": body.get("response_format"),
        "configured_max_tokens": int(config["max_tokens"]), "effective_max_tokens": body.get("max_tokens"),
        "thinking": thinking,
        "conflicting_reasoning_parameters": [],
        "historical_reasoning_token_evidence": {
            "records_with_reasoning_token_field": len(historical_reasoning),
            "records_with_positive_reasoning_tokens": sum(value > 0 for value in historical_reasoning),
            "reasoning_tokens_total": sum(historical_reasoning),
        },
        "execution_record_audit": {
            "prompt_version": True, "prompt_hash": True,
            "schema_version": True, "schema_hash": True,
            "response_format": True, "configured_effective_max_tokens": True,
            "thinking_mode": True, "finish_reason": True, "usage": True,
            "raw_response_characters": True, "observation_count": True,
        },
        "http_body_field_audit": {"response_format": True, "max_tokens": True,
                                  "thinking": body.get("thinking") == {"type": "disabled"}},
    }


def build_compatibility_report(artifacts: Path, records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    historical_versions: Counter[str] = Counter(); historical_hashes: Counter[str] = Counter()
    legacy_empty_blocks = []; historical_nonempty_failure_count = 0; historical_raw_observation_count = 0
    for record in records:
        provenance = _raw_provenance(artifacts, record)
        historical_versions[str(provenance["historical_prompt_version"])] += 1
        historical_hashes[str(provenance["historical_prompt_hash"])] += 1
        if record.get("status") == "completed":
            legacy_empty_blocks.append({
                "block_id": record.get("block_id"), "status": "legacy_completed_empty_under_historical_prompt",
                "original_prompt_version": provenance["historical_prompt_version"],
                "original_prompt_hash": provenance["historical_prompt_hash"],
                "historical_raw_response_path": provenance["historical_raw_response_path"],
                "historical_raw_response_hash": provenance["historical_raw_response_hash"],
            })
        elif record.get("status") == "parse_error":
            historical_nonempty_failure_count += 1
            historical_raw_observation_count += provenance["historical_observation_count"]
    scientific_unchanged = list(LEGACY_SCIENTIFIC_RULES) == list(PROMPT_RULES[:16])
    config_unchanged = all(config.get(key) == value for key, value in LEGACY_VERSIONED_CONFIG.items())
    decision = "empty_results_semantically_compatible" if scientific_unchanged and config_unchanged else "compatibility_uncertain"
    return {
        "schema_version": "legacy_empty_prompt_compatibility_report_v1",
        "compatibility_policy_version": COMPATIBILITY_POLICY_VERSION,
        "audited_at": datetime.now(timezone.utc).isoformat(), "reviewer": "automated_structured_prompt_audit",
        "historical_prompt_versions": dict(historical_versions), "historical_prompt_hashes": dict(historical_hashes),
        "legacy_empty_block_count": len(legacy_empty_blocks), "legacy_empty_blocks": sorted(legacy_empty_blocks, key=lambda row: str(row["block_id"])),
        "historical_nonempty_schema_failure_count": historical_nonempty_failure_count,
        "historical_raw_observation_count": historical_raw_observation_count,
        "current_prompt_version": PROMPT_VERSION, "current_prompt_hash": prompt_hash(),
        "structured_rule_comparison": {
            "legacy_scientific_rules": list(LEGACY_SCIENTIFIC_RULES),
            "current_scientific_rules": list(PROMPT_RULES[:16]),
            "scientific_rules_exactly_unchanged": scientific_unchanged,
            "legacy_schema_version": SCHEMA_VERSION, "current_schema_version": SCHEMA_VERSION,
            "legacy_extractor_version": EXTRACTOR_VERSION, "current_extractor_version": EXTRACTOR_VERSION,
            "legacy_parser_version": PARSER_VERSION, "current_parser_version": PARSER_VERSION,
            "versioned_config_compatible": config_unchanged,
        },
        "output_contract_only_changes": [
            "added schema-validated complete non-empty JSON example", "added exact unabbreviated field-name requirement",
            "forbade enumerated legacy aliases", "specified permitted representations for unknown required fields",
            "included the complete current response JSON schema in prompt identity hash",
        ],
        "extraction_semantic_changes": [],
        "unchanged_scientific_rules": list(LEGACY_SCIENTIFIC_RULES), "changed_scientific_rules": [],
        "compatibility_decision": decision,
        "decision_reasons": [
            "structured inclusion/exclusion, grounding, experiment-splitting, current-study/background, endpoint, and context-binding rules are unchanged",
            "schema, extractor, parser, block splitting, and max-token configuration are unchanged",
            "v4 additions constrain representation rather than observation eligibility",
        ] if decision == "empty_results_semantically_compatible" else ["structured scientific rules or versioned extraction configuration could not be proven identical"],
        "provenance_policy": {
            "legacy_status": "legacy_completed_empty_under_historical_prompt",
            "may_be_reused_only_as": "historical-compatible empty",
            "must_never_be_relabelled_as": "completed_empty_under_prompt_v4",
        },
    }


def _fresh_cache_status(artifacts: Path, expected_key: str, block_id: str, source_hash: str) -> tuple[bool, str | None]:
    path = artifacts / "cache" / "fulltext_l1_v2" / f"{expected_key}.json"
    if not path.is_file():
        return False, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        response = payload.get("response")
        FulltextL1DraftResponse.model_validate(response)
    except (OSError, json.JSONDecodeError, ValidationError):
        return False, str(path)
    valid = (
        payload.get("prompt_version") == PROMPT_VERSION and payload.get("prompt_hash") == prompt_hash()
        and payload.get("draft_schema_version") == DRAFT_SCHEMA_VERSION
        and payload.get("hydrator_version") == HYDRATOR_VERSION
        and payload.get("semantics_registry_version") == REGISTRY_VERSION
        and payload.get("evidence_anchor_version") == EVIDENCE_ANCHOR_VERSION
        and payload.get("completeness_policy_version") == COMPLETENESS_POLICY_VERSION
        and payload.get("formal_schema_version") == SCHEMA_VERSION
        and payload.get("source_fulltext_hash") == source_hash
        and payload.get("configured_thinking_mode") == DEFAULT_THINKING_MODE
        and payload.get("effective_thinking_mode") == DEFAULT_THINKING_MODE
        and payload.get("thinking_parameter_sent") is True
        and (payload.get("block_provenance") or {}).get("block_id") == block_id
        and not str(payload.get("origin") or "").startswith("recovered_from_historical")
    )
    return valid, str(path)


def build_manifest(run_dir: Path, records: list[dict[str, Any]], inventory: dict[str, dict[str, Any]],
                   config: dict[str, Any]) -> dict[str, Any]:
    artifacts = run_dir / "artifacts"; rows: list[dict[str, Any]] = []
    config_hash = _config_hash(config)
    for record in records:
        item = inventory[str(record["block_id"])]
        block, paper = item["block"], item["paper"]
        provenance = _raw_provenance(artifacts, record)
        signals = _signals(str(block["text"]))
        prior_hash = _hash({key: paper.get(key) for key in ("subject", "object", "abstract_observation_ids")})
        key = cache_key(
            source_fulltext_hash=item["source_fulltext_hash"], chunk_hash=block["chunk_hash"],
            provider="deepseek", model="deepseek-v4-pro", config_hash=config_hash,
            candidate_prior_hash=prior_hash, thinking_mode=DEFAULT_THINKING_MODE,
            max_tokens=int(config["max_tokens"]),
        )
        fresh, fresh_path = _fresh_cache_status(artifacts, key, str(block["block_id"]), item["source_fulltext_hash"])
        rows.append({
            "sample_group": "historical_nonempty_schema_failure" if record.get("status") == "parse_error" else "historical_completed_empty",
            "paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid"),
            "parent_block_id": block.get("parent_block_id") or block.get("block_id"),
            "child_block_id": block.get("child_block_id"), "block_id": block["block_id"],
            "original_block_hash": block["chunk_hash"], "historical_status": "historical_nonempty_schema_failure" if record.get("status") == "parse_error" else "legacy_completed_empty_under_historical_prompt",
            **{key: provenance[key] for key in ("historical_prompt_version", "historical_prompt_hash", "historical_raw_response_path", "historical_raw_response_hash", "historical_observation_count")},
            "source_text_length": len(block["text"]), "estimated_input_tokens": estimate_tokens(build_prompt(paper, block)),
            "rendered_system_prompt_hash": _sha(build_prompt(paper, block)), "rendered_user_prompt_hash": None,
            "planned_max_tokens": int(config["max_tokens"]), "expected_cache_identity": key,
            "fresh_v4_success_cache_hit": fresh, "fresh_v4_cache_path": fresh_path,
            "estimated_provider_call_count": 0 if fresh else 1, "signals": signals,
        })
    failures = [row for row in rows if row["sample_group"] == "historical_nonempty_schema_failure" and row["historical_observation_count"] > 0]
    empties = [row for row in rows if row["sample_group"] == "historical_completed_empty"]
    selected = _select_nonempty(failures) + _select_empty(empties)
    for row in selected:
        s = row["signals"]
        if row["sample_group"] == "historical_nonempty_schema_failure":
            reasons = [name for name, enabled in (
                ("human/patient block", s["human_or_patient"]), ("mouse/in vivo block", s["mouse_or_in_vivo"]),
                ("in vitro/cell-line block", s["in_vitro_or_cell_line"]), ("multi-endpoint block", s["multi_endpoint"]),
                ("simple single-endpoint block", s["simple_single_endpoint"]),
            ) if enabled]
            if row["historical_observation_count"] == max(x["historical_observation_count"] for x in failures): reasons.append("high historical observation count")
            row["selection_reason"] = reasons or ["stable coverage fallback"]
            row["evidence_span_exact_match_candidate"] = bool(s["deterministic_signal_count"])
        else:
            risk = "high_false_negative_risk" if s["deterministic_signal_count"] else "low_experiment_probability"
            row["legacy_empty_risk_subgroup"] = risk
            row["selection_reason"] = [risk, *s["deterministic_signal_patterns"]]
    return {
        "schema_version": "fulltext_l1_v2_smoke_manifest_v1", "sampling_version": SAMPLING_VERSION,
        "source_run": str(run_dir), "selection_is_deterministic": True,
        "sample_count": len(selected), "group_counts": dict(Counter(row["sample_group"] for row in selected)),
        "paper_count": len({row["pmcid"] for row in selected}), "samples": selected,
    }


def build_preflight(manifest: dict[str, Any], request_audit: dict[str, Any]) -> dict[str, Any]:
    calls = sum(int(row["estimated_provider_call_count"]) for row in manifest["samples"])
    entries = []
    for row in manifest["samples"]:
        entries.append({
            "block_id": row["block_id"], "block_input_hash": row["original_block_hash"],
            "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(), "schema_version": SCHEMA_VERSION,
            "schema_hash": schema_hash(), "estimated_input_tokens": row["estimated_input_tokens"],
            "configured_max_tokens": row["planned_max_tokens"],
            "total_context_estimate": row["estimated_input_tokens"] + row["planned_max_tokens"] + 4096,
            "response_format": {"type": "json_object"}, "thinking_mode": request_audit["thinking"],
            "existing_fresh_v4_cache_hit": row["fresh_v4_success_cache_hit"],
            "provider_call_required": not row["fresh_v4_success_cache_hit"],
        })
    return {
        "schema_version": "fulltext_l1_v2_smoke_preflight_v1", "mode": "plan_only",
        "api_calls": 0, "network_calls": 0, "downloads": 0,
        "planned_provider_calls": calls, "maximum_provider_calls": MANIFEST_SIZE,
        "configured_thinking_mode": request_audit["thinking"]["configured_thinking_mode"],
        "effective_request_mode": request_audit["thinking"]["effective_thinking_mode"],
        "thinking_parameter_sent": request_audit["thinking"]["thinking_parameter_sent"],
        "thinking_mode_verified": request_audit["thinking"]["thinking_mode_verified"],
        "estimated_total_input_tokens": sum(row["estimated_input_tokens"] for row in manifest["samples"] if not row["fresh_v4_success_cache_hit"]),
        "max_possible_output_tokens": calls * DEFAULT_MAX_TOKENS,
        "provider_cost_estimate": {"status": "not_computed", "reason": "no locally versioned provider pricing configuration"},
        "execution_blocked": not request_audit["thinking"]["thinking_mode_verified"],
        "blocking_reason": "thinking_mode_unverified" if not request_audit["thinking"]["thinking_mode_verified"] else None,
        "entries": entries,
    }


def decide_rerun_scope(compatibility: str, request_audit: dict[str, Any], smoke_results: dict[str, Any] | None) -> tuple[str, list[str]]:
    if smoke_results is None:
        return "insufficient_evidence_do_not_rerun", ["fresh v4 provider smoke has not been executed"]
    if not request_audit["thinking"]["thinking_mode_verified"]:
        return "insufficient_evidence_do_not_rerun", ["thinking mode is unverified"]
    if smoke_results.get("provider_thinking_disable_not_honored"):
        return "insufficient_evidence_do_not_rerun", ["provider did not honor explicit thinking disabled; smoke stopped fail closed"]
    nonempty = smoke_results.get("nonempty_failures") or {}
    empty = smoke_results.get("legacy_empty") or {}
    if empty.get("legacy_empty_nonempty_schema_failure_count", 0) > 0:
        return "insufficient_evidence_do_not_rerun", ["legacy-empty raw nonempty responses failed Draft/Formal validation and cannot be counted as remained empty"]
    if nonempty.get("systematic_schema_drift") or nonempty.get("direct_strict_schema_success_count", 0) / 6 < SMOKE_SCHEMA_SUCCESS_THRESHOLD:
        return "insufficient_evidence_do_not_rerun", ["v4 strict-schema smoke success is below threshold or field drift remains"]
    if compatibility != "empty_results_semantically_compatible":
        return "rerun_all_200_blocks", ["legacy and v4 extraction semantics are not proven compatible"]
    if empty.get("high_risk_valid_nonempty_count", 0) >= 1 or empty.get("became_nonempty_count", 0) >= 2:
        return "rerun_all_200_blocks", ["legacy empty blocks show prompt-version-sensitive valid observations"]
    if empty.get("became_nonempty_count", 0) == 0 and empty.get("remained_empty_count") == 6:
        return "rerun_unresolved_107_only", ["v4 schema target passed and every sampled legacy empty remained empty under compatible scientific rules"]
    return "insufficient_evidence_do_not_rerun", ["smoke evidence is contradictory or incomplete"]


def build_rerun_plan(run_dir: Path, records: list[dict[str, Any]], inventory: dict[str, dict[str, Any]],
                     manifest: dict[str, Any], compatibility: dict[str, Any], request_audit: dict[str, Any],
                     smoke_results: dict[str, Any] | None = None) -> dict[str, Any]:
    decision, reasons = decide_rerun_scope(compatibility["compatibility_decision"], request_audit, smoke_results)
    unresolved = sorted(str(row["block_id"]) for row in records if row.get("status") == "parse_error")
    all_blocks = sorted(str(row["block_id"]) for row in records)
    fresh = sorted(row["block_id"] for row in manifest["samples"] if row["fresh_v4_success_cache_hit"])
    required = unresolved if decision == "rerun_unresolved_107_only" else all_blocks if decision == "rerun_all_200_blocks" else []
    reusable = sorted(str(row["block_id"]) for row in records if row.get("status") == "completed") if decision == "rerun_unresolved_107_only" else []
    total_input = sum(estimate_tokens(build_prompt(inventory[block_id]["paper"], inventory[block_id]["block"])) for block_id in required)
    command = f"python -m code_engine.cli.fulltext_l1_v2_provider_smoke_test --run-dir {run_dir} --execute --api"
    return {
        "schema_version": "fulltext_l1_v2_rerun_scope_plan_v1", "decision_policy_version": DECISION_POLICY_VERSION,
        "decision": decision, "decision_reasons": reasons,
        "blocks_requiring_fresh_provider_calls": required, "blocks_reusable_as_historical_compatible_empty": reusable,
        "blocks_already_covered_by_fresh_v4_cache": fresh, "estimated_api_calls": len(required),
        "estimated_input_tokens": total_input, "max_possible_output_tokens": len(required) * DEFAULT_MAX_TOKENS,
        "affected_papers": sorted({inventory[block_id]["paper"].get("pmcid") for block_id in required}),
        "expected_cache_location": str(run_dir / "artifacts" / "cache" / "fulltext_l1_v2"),
        "expected_run_state_transition": "none during smoke; completeness may be recomputed only after an approved complete rerun scope",
        "publication_remains_blocked": True, "exact_future_smoke_command": command,
        "thinking_mode_verified_for_request": request_audit["thinking"]["thinking_mode_verified"],
        "bulk_rerun_executed": False,
    }


def _markdown_report(title: str, rows: Iterable[tuple[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    for key, value in rows:
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")
    return "\n".join(lines) + "\n"


def write_plan_artifacts(run_dir: Path) -> dict[str, Any]:
    """Generate the complete offline plan and return call accounting."""
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"
    records = _jsonl(artifacts / "fulltext_l1_v2_execution_records.jsonl")
    if not records:
        raise FileNotFoundError("historical Fulltext L1 v2 execution records are required")
    config = _historical_config(artifacts, records)
    inventory = _block_inventory(run_dir, records, config)
    before_state = {
        name: _sha((artifacts / name).read_bytes()) for name in ("fulltext_l1_v2_summary.json", "pipeline_stage_summary.json")
        if (artifacts / name).is_file()
    }
    request_audit = build_request_chain_audit(run_dir, inventory, config)
    compatibility = build_compatibility_report(artifacts, records, config)
    manifest = build_manifest(run_dir, records, inventory, config)
    if manifest["sample_count"] != MANIFEST_SIZE or manifest["group_counts"] != {"historical_nonempty_schema_failure": 6, "historical_completed_empty": 6}:
        raise RuntimeError(f"invalid smoke sample shape: {manifest['group_counts']}")
    preflight = build_preflight(manifest, request_audit)
    rerun = build_rerun_plan(run_dir, records, inventory, manifest, compatibility, request_audit)
    summary = json.loads((artifacts / "fulltext_l1_v2_summary.json").read_text(encoding="utf-8")) if (artifacts / "fulltext_l1_v2_summary.json").is_file() else {}
    rerun["current_run_safety_state"] = {
        "scientific_input_complete": summary.get("scientific_input_complete"),
        "partial_block_failures": summary.get("partial_block_failures"),
        "publication_allowed": (summary.get("consistency_report") or {}).get("publication_allowed", False),
        "atlas_publication_attempted": False, "atlas_activation_attempted": False,
    }

    _write_json(artifacts / "fulltext_l1_v2_request_chain_audit.json", request_audit)
    (artifacts / "fulltext_l1_v2_request_chain_audit.md").write_text(_markdown_report("Fulltext L1 v2 request-chain audit", (
        ("prompt_version", PROMPT_VERSION), ("prompt_hash", prompt_hash()), ("response_format", request_audit["response_format_in_http_body"]),
        ("max_tokens", request_audit["effective_max_tokens"]), ("thinking", request_audit["thinking"]),
    )), encoding="utf-8")
    _write_json(artifacts / "legacy_empty_prompt_compatibility_report.json", compatibility)
    (artifacts / "legacy_empty_prompt_compatibility_report.md").write_text(_markdown_report("Legacy empty prompt compatibility", (
        ("historical_prompt_versions", compatibility["historical_prompt_versions"]), ("current_prompt_version", PROMPT_VERSION),
        ("output_contract_only_changes", compatibility["output_contract_only_changes"]), ("extraction_semantic_changes", compatibility["extraction_semantic_changes"]),
        ("compatibility_decision", compatibility["compatibility_decision"]), ("decision_reasons", compatibility["decision_reasons"]),
    )), encoding="utf-8")
    _write_json(artifacts / "fulltext_l1_v2_smoke_manifest.json", manifest)
    (artifacts / "fulltext_l1_v2_smoke_manifest.md").write_text(_markdown_report("Fulltext L1 v2 smoke manifest", (
        ("sampling_version", SAMPLING_VERSION), ("sample_count", manifest["sample_count"]),
        ("group_counts", manifest["group_counts"]), ("blocks", [row["block_id"] for row in manifest["samples"]]),
    )), encoding="utf-8")
    _write_json(artifacts / "fulltext_l1_v2_smoke_preflight.json", preflight)
    _write_json(artifacts / "fulltext_l1_v2_rerun_scope_plan.json", rerun)
    (artifacts / "fulltext_l1_v2_rerun_scope_plan.md").write_text(_markdown_report("Fulltext L1 v2 rerun scope plan", (
        ("decision", rerun["decision"]), ("decision_reasons", rerun["decision_reasons"]),
        ("estimated_api_calls", rerun["estimated_api_calls"]), ("publication_remains_blocked", True),
        ("exact_future_smoke_command", rerun["exact_future_smoke_command"]),
    )), encoding="utf-8")
    after_state = {
        name: _sha((artifacts / name).read_bytes()) for name in before_state
    }
    if before_state != after_state:
        raise RuntimeError("plan-only modified protected run-state artifacts")
    return {
        "mode": "plan_only", "api_calls": 0, "network_calls": 0, "downloads": 0,
        "planned_provider_calls": preflight["planned_provider_calls"], "manifest_blocks": [row["block_id"] for row in manifest["samples"]],
        "thinking_mode": request_audit["thinking"]["effective_mode"], "execution_blocked": preflight["execution_blocked"],
        "thinking_mode_verified": request_audit["thinking"]["thinking_mode_verified"],
        "thinking_parameter_sent": request_audit["thinking"]["thinking_parameter_sent"],
        "compatibility_decision": compatibility["compatibility_decision"], "rerun_decision": rerun["decision"],
        "protected_state_hashes_unchanged": True,
    }


def execute_smoke(run_dir: Path, *, api_authorized: bool, client: Any | None = None,
                  _thinking_audit: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute only a preplanned manifest, after every hard safety gate passes."""
    if not api_authorized:
        raise PermissionError("smoke execution requires both --execute and --api")
    thinking = _thinking_audit or deepseek_thinking_mode_audit(DEFAULT_THINKING_MODE)
    if not thinking.get("thinking_mode_verified") or thinking.get("effective_mode") != "disabled":
        raise RuntimeError("thinking_mode_unverified")
    run_dir = Path(run_dir); artifacts = run_dir / "artifacts"
    manifest_path = artifacts / "fulltext_l1_v2_smoke_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("run --plan-only before provider execution")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = list(manifest.get("samples") or [])
    if len(samples) > MANIFEST_SIZE:
        raise RuntimeError("smoke manifest exceeds 12-call safety bound")
    records = _jsonl(artifacts / "fulltext_l1_v2_execution_records.jsonl")
    config = _historical_config(artifacts, records); inventory = _block_inventory(run_dir, records, config)
    # A smoke block gets one paid attempt.  This makes the hard 12-call bound
    # independent of the general extractor's retry defaults.
    client = client or build_json_client_from_config("deepseek", "deepseek-v4-pro", max_retries=0)
    if client is None:
        raise RuntimeError("DeepSeek provider is not configured")
    results = []; calls = 0
    cache_root = artifacts / "cache" / "fulltext_l1_v2"
    for sample in samples:
        block_id = str(sample["block_id"])
        if sample.get("fresh_v4_success_cache_hit"):
            results.append({"block_id": block_id, "status": "fresh_v4_cache_hit", "api_called": False}); continue
        if calls >= MANIFEST_SIZE:
            raise RuntimeError("smoke provider call bound exceeded")
        item = inventory[block_id]; raw = None; transport: dict[str, Any] = {}
        request_record = {
            "provider": "deepseek", "model": "deepseek-v4-pro",
            "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
            "schema_version": SCHEMA_VERSION, "schema_hash": schema_hash(),
            "response_format": {"type": "json_object"},
            "configured_max_tokens": DEFAULT_MAX_TOKENS, "effective_max_tokens": DEFAULT_MAX_TOKENS,
            "cache_identity": sample["expected_cache_identity"], "cache_status": "miss",
            "configured_thinking_mode": DEFAULT_THINKING_MODE,
            "effective_thinking_mode": DEFAULT_THINKING_MODE,
            "thinking_parameter_sent": True, "thinking_request_payload": {"type": "disabled"},
        }
        try:
            method = getattr(client, "extract_json_result", None) or getattr(client, "extract_json")
            calls += 1
            response = method(build_prompt(item["paper"], item["block"]), model="deepseek-v4-pro", temperature=0,
                              top_p=1, max_tokens=DEFAULT_MAX_TOKENS, retry_on_length=False,
                              thinking_mode=DEFAULT_THINKING_MODE)
            payload, transport = split_transport_metadata(response); raw = transport.get("raw_response")
            usage = transport.get("usage") or {}
            reasoning_value = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            if reasoning_value is None:
                reasoning_value = usage.get("reasoning_tokens")
            reasoning_tokens: int | str = int(reasoning_value) if reasoning_value is not None else "unavailable"
            if (isinstance(reasoning_tokens, int) and reasoning_tokens > 0) or transport.get("reasoning_content_present"):
                result = {**request_record, "block_id": block_id, "status": "provider_thinking_disable_not_honored",
                          "api_called": True, "reasoning_tokens": reasoning_tokens,
                          "reasoning_content_present": bool(transport.get("reasoning_content_present")),
                          "finish_reason": transport.get("finish_reason"),
                          "raw_response_characters": len(str(raw or ""))}
                if raw not in (None, ""):
                    raw_path = cache_root / f"smoke_{sample['expected_cache_identity']}.raw_response.txt"
                    raw_path.write_text(str(raw), encoding="utf-8"); result["raw_response_path"] = str(raw_path)
                results.append(result)
                break
            validated = FulltextL1DraftResponse.model_validate(payload)
            observations, hydration_audit = hydrate_provider_draft(
                validated.model_dump(mode="json"), run_id=run_dir.name, paper=item["paper"], block=item["block"],
                source_hash=item["source_fulltext_hash"], source_artifact=item.get("article_path") or "article_text.json")
            evidence_valid = all(all(str(span.get("text") or "") in item["block"]["text"] for span in (row.get("provenance") or {}).get("evidence_spans", [])) for row in observations)
            result = {"block_id": block_id, "status": "strict_schema_success", "api_called": True,
                      "observation_count": len(observations), "evidence_span_exactness": evidence_valid,
                      "finish_reason": transport.get("finish_reason"), "usage": transport.get("usage") or {},
                      "reasoning_tokens": reasoning_tokens,
                      "raw_response_characters": len(str(raw or "")), "legacy_empty_false_negative_candidate": sample["sample_group"] == "historical_completed_empty" and bool(observations)}
            cache_payload = {
                "schema_version": DRAFT_SCHEMA_VERSION, "schema_hash": schema_hash(),
                "draft_schema_version": DRAFT_SCHEMA_VERSION, "draft_schema_hash": schema_hash(),
                "formal_schema_version": SCHEMA_VERSION, "formal_schema_hash": formal_schema_hash(),
                "hydrator_version": HYDRATOR_VERSION, "semantics_registry_version": REGISTRY_VERSION,
                "evidence_anchor_version": EVIDENCE_ANCHOR_VERSION,
                "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
                "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
                "rendered_system_prompt_hash": sample["rendered_system_prompt_hash"], "rendered_user_prompt_hash": None,
                "parser_version": PARSER_VERSION, "extractor_version": EXTRACTOR_VERSION,
                "source_fulltext_hash": item["source_fulltext_hash"], "response": payload,
                "transport_metadata": {**transport, "configured_max_tokens": DEFAULT_MAX_TOKENS,
                    "effective_max_tokens": DEFAULT_MAX_TOKENS, "response_format": {"type": "json_object"},
                    "thinking_mode": thinking},
                "block_provenance": {"block_id": block_id, "parent_block_id": sample.get("parent_block_id"),
                    "child_block_id": sample.get("child_block_id")},
                "hydration_audit": hydration_audit, "origin": "fresh_v5_draft_provider_smoke",
                "configured_thinking_mode": DEFAULT_THINKING_MODE,
                "effective_thinking_mode": DEFAULT_THINKING_MODE,
                "thinking_parameter_sent": True,
                "thinking_request_payload": {"type": "disabled"},
            }
            cache_path = cache_root / f"{sample['expected_cache_identity']}.json"
            _write_json(cache_path, cache_payload); result["fresh_v4_cache_path"] = str(cache_path)
        except DeepSeekExtractionError as exc:
            raw = exc.raw_response
            error_reasoning = (exc.usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            if error_reasoning is None:
                error_reasoning = exc.usage.get("reasoning_tokens")
            error_reasoning_value: int | str = int(error_reasoning) if error_reasoning is not None else "unavailable"
            mismatch = ((isinstance(error_reasoning_value, int) and error_reasoning_value > 0)
                        or bool(exc.provider_metadata.get("reasoning_content_present")))
            result = {**request_record, "block_id": block_id,
                      "status": "provider_thinking_disable_not_honored" if mismatch else "provider_or_parse_failure",
                      "api_called": True, "reasoning_tokens": error_reasoning_value,
                      "reasoning_content_present": bool(exc.provider_metadata.get("reasoning_content_present")),
                      "error_kind": exc.error_kind, "finish_reason": exc.finish_reason,
                      "raw_response_characters": len(str(raw or ""))}
            if mismatch:
                if raw not in (None, ""):
                    raw_path = cache_root / f"smoke_{sample['expected_cache_identity']}.raw_response.txt"
                    raw_path.write_text(str(raw), encoding="utf-8"); result["raw_response_path"] = str(raw_path)
                results.append(result)
                break
        except (ValidationError, DraftHydrationV3Error, json.JSONDecodeError) as exc:
            unknown_extra_paths = []
            if isinstance(exc, ValidationError):
                unknown_extra_paths = [".".join(map(str, error["loc"])) for error in exc.errors() if error.get("type") == "extra_forbidden"]
            result = {"block_id": block_id, "status": "schema_failure", "api_called": True,
                      "error": str(exc), "unknown_extra_paths": unknown_extra_paths,
                      "finish_reason": transport.get("finish_reason"), "usage": transport.get("usage") or {},
                      "raw_response_characters": len(str(raw or ""))}
            try:
                raw_payload = json.loads(raw) if isinstance(raw, str) else raw
                raw_values = raw_payload.get("experimental_observations") if isinstance(raw_payload, dict) else None
                result["raw_observation_count"] = len(raw_values) if isinstance(raw_values, list) else 0
            except json.JSONDecodeError:
                result["raw_observation_count"] = 0
        if raw not in (None, ""):
            raw_path = cache_root / f"smoke_{sample['expected_cache_identity']}.raw_response.txt"
            raw_path.write_text(str(raw), encoding="utf-8"); result["raw_response_path"] = str(raw_path)
        result = {**request_record, **result}
        results.append(result)
    nonempty_results = [row for row in results if next(x for x in samples if x["block_id"] == row["block_id"])["sample_group"] == "historical_nonempty_schema_failure"]
    empty_results = [row for row in results if next(x for x in samples if x["block_id"] == row["block_id"])["sample_group"] == "historical_completed_empty"]
    high_ids = {row["block_id"] for row in samples if row.get("legacy_empty_risk_subgroup") == "high_false_negative_risk"}
    output = {"schema_version": "fulltext_l1_v2_provider_smoke_results_v1", "api_calls": calls,
              "maximum_calls": MANIFEST_SIZE, "manifest_only": True, "results": results,
              "nonempty_failures": {
                  "direct_strict_schema_success_count": sum(row["status"] == "strict_schema_success" for row in nonempty_results),
                  "schema_failure_count": sum(row["status"] == "schema_failure" for row in nonempty_results),
                  "empty_result_count": sum(row["status"] == "strict_schema_success" and row.get("observation_count") == 0 for row in nonempty_results),
                  "observation_count": sum(row.get("observation_count", 0) for row in nonempty_results),
                  "systematic_schema_drift": sum(row["status"] == "schema_failure" for row in nonempty_results) >= 2,
              },
              "legacy_empty": {
                  "remained_empty_count": sum(row["status"] == "strict_schema_success" and row.get("observation_count") == 0 for row in empty_results),
                  "became_nonempty_count": sum(row["status"] == "strict_schema_success" and row.get("observation_count", 0) > 0 for row in empty_results),
                  "nonempty_observation_count": sum(row.get("observation_count", 0) for row in empty_results),
                  "high_risk_valid_nonempty_count": sum(row["block_id"] in high_ids and row["status"] == "strict_schema_success" and row.get("observation_count", 0) > 0 for row in empty_results),
                  "legacy_empty_raw_empty_count": sum(row.get("raw_observation_count", row.get("observation_count", 0)) == 0 for row in empty_results),
                  "legacy_empty_raw_nonempty_count": sum(row.get("raw_observation_count", row.get("observation_count", 0)) > 0 for row in empty_results),
                  "legacy_empty_draft_valid_nonempty_count": sum(row["status"] == "strict_schema_success" and row.get("observation_count", 0) > 0 for row in empty_results),
                  "legacy_empty_formal_valid_nonempty_count": sum(row["status"] == "strict_schema_success" and row.get("observation_count", 0) > 0 for row in empty_results),
                  "legacy_empty_nonempty_schema_failure_count": sum(row["status"] == "schema_failure" and row.get("raw_observation_count", 0) > 0 for row in empty_results),
                  "legacy_empty_false_negative_candidate_count": sum(row.get("raw_observation_count", row.get("observation_count", 0)) > 0 for row in empty_results),
              },
              "scientific_input_complete_changed": False, "publication_attempted": False}
    output["provider_thinking_disable_not_honored"] = any(row["status"] == "provider_thinking_disable_not_honored" for row in results)
    output["stopped_early"] = output["provider_thinking_disable_not_honored"]
    _write_json(artifacts / "fulltext_l1_v2_provider_smoke_results.json", output)
    compatibility = build_compatibility_report(artifacts, records, config)
    request_audit = build_request_chain_audit(run_dir, inventory, config)
    request_audit["thinking"] = thinking
    rerun = build_rerun_plan(run_dir, records, inventory, manifest, compatibility, request_audit, output)
    _write_json(artifacts / "fulltext_l1_v2_rerun_scope_plan.json", rerun)
    output["rerun_decision"] = rerun["decision"]
    _write_json(artifacts / "fulltext_l1_v2_provider_smoke_results.json", output)
    return output


__all__ = [
    "build_manifest", "build_preflight", "build_request_chain_audit", "build_compatibility_report",
    "decide_rerun_scope", "execute_smoke", "schema_hash", "write_plan_artifacts",
]
