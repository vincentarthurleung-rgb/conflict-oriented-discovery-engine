"""Runtime isolation provenance for one workflow run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable


LEGACY_PREFIXES = ("src.pipelines.",)


def imported_legacy_modules() -> list[str]:
    return sorted(name for name in sys.modules if name.startswith(LEGACY_PREFIXES))


def _nonempty_json(path: Path) -> bool:
    if not path.exists() or not path.stat().st_size:
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return bool(value)
    except (OSError, json.JSONDecodeError):
        return True


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _reasoning_year_violation(artifacts: Path, config: dict[str, Any]) -> bool:
    from code_engine.temporal.paper_year_filter import paper_year_filter_from_dict, publication_year
    year_filter = paper_year_filter_from_dict(config)
    if not year_filter.enabled:
        return False
    names = (
        "abstract_l1_claims.jsonl", "l2_abstract_observations.json", "relation_evidence_bundles.jsonl",
        "graph_conflict_candidates.jsonl", "hypothesis_hyperedges.jsonl",
        "conflict_evidence_timelines.jsonl", "fulltext_l1_claims.jsonl",
    )
    for name in names:
        path = artifacts / name
        if not path.exists():
            continue
        try:
            if path.suffix == ".jsonl":
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                value = json.loads(path.read_text(encoding="utf-8")); records = value if isinstance(value, list) else [value]
        except (OSError, json.JSONDecodeError):
            continue
        for record in records:
            year = publication_year(record)
            if year is not None and not year_filter.includes(year):
                return True
    return False


def build_runtime_provenance(
    run_dir: Path, *, repository_root: Path, resume_explicit: bool,
    entity_registry_path: str | Path | None, automatic_pilot_registry: bool,
    l1_mode: str, l1_task_cache_enabled: bool, update_global_corpus: bool,
    paper_registry_enabled: bool, coverage_precheck: bool,
    allow_coverage_short_circuit: bool, merge_knowledge_store: bool,
    update_global_knowledge_store: bool, execute: bool,
    legacy_modules_before: Iterable[str] = (),
    pilot_profile: str | None = None, pilot_terms: Iterable[str] = (),
    domain_specific_defaults_used: Iterable[str] = (),
    batch_id: str | None = None, triple_id: str | None = None,
    query_hash: str | None = None, seed_triple: dict[str, Any] | None = None,
    paper_artifact_cache_enabled: bool = True,
    paper_artifact_cache_index: str | Path | None = None,
    paper_artifact_cache_hits: int = 0, paper_artifact_cache_misses: int = 0,
    cache_hit_records: Iterable[dict[str, Any]] = (), cache_miss_records: Iterable[dict[str, Any]] = (),
    l1_timeout_config: dict[str, Any] | None = None,
    paper_year_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import code_engine
    from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH

    root = Path(repository_root).resolve()
    actual = Path(code_engine.__file__).resolve()
    expected = (root / "src/code_engine/__init__.py").resolve()
    shadowing = actual != expected
    selected_registry = Path(entity_registry_path).resolve() if entity_registry_path else (root / DEFAULT_REGISTRY_PATH).resolve()
    config_files = [str(selected_registry)]
    legacy_config = False
    before = set(legacy_modules_before)
    legacy_imported = sorted(set(imported_legacy_modules()) - before)
    artifacts = Path(run_dir).resolve() / "artifacts"
    run_state = _json(Path(run_dir).resolve() / "run_state.json", {})
    intake = _json(artifacts / "intake.json", {})
    search_plan = _json(artifacts / "search_plan.json", {})
    acquisition = _json(artifacts / "acquisition_report.json", {})
    fulltext_acquisition = _json(artifacts / "fulltext_acquisition_summary.json", {})
    abstract_cache = _json(artifacts / "abstract_l1_cache_report.json", {})
    fulltext_cache = _json(artifacts / "fulltext_l1_cache_report.json", {})
    abstract_l1 = _json(artifacts / "abstract_l1_summary.json", {})
    fulltext_l1 = _json(artifacts / "fulltext_l1_summary.json", {})
    acquisition_year = _json(artifacts / "acquisition_report.json", {})
    search_intent = _json(artifacts / "semantic_search_intent.json", {})
    query_guard = _json(artifacts / "search_query_guard_report.json", {})
    l2_summary = _json(artifacts / "l2_abstract_summary.json", {})
    intake_triple = (intake.get("unified_seed_triple") or {}).get("triple_id")
    search_triple = (search_plan.get("seed_triple") or {}).get("triple_id")
    identity_values = [value for value in (triple_id, intake_triple, search_triple) if value]
    legacy_artifacts = []
    if l1_mode == "legacy":
        legacy_artifacts.extend(name for name in ("l2_observations.json", "conflict_graph_summary.json") if (artifacts / name).exists())
    elif _nonempty_json(artifacts / "l2_observations.json"):
        legacy_artifacts.append("l2_observations.json")
    global_read = bool(coverage_precheck or merge_knowledge_store)
    provenance = {
        "code_engine_import_path": str(actual), "expected_code_engine_path": str(expected),
        "python_executable": sys.executable, "sys_path_head": list(sys.path[:10]),
        "config_files_used": config_files, "entity_registry_path": str(selected_registry),
        "run_dir": str(Path(run_dir).resolve()), "artifacts_dir": str(artifacts),
        "global_store_read": global_read, "global_store_write": bool(update_global_knowledge_store),
        "global_store_read_reason": "post_reasoning_merge_plan" if merge_knowledge_store else ("explicit_coverage_precheck" if coverage_precheck else None),
        "global_evidence_injected_before_reasoning": bool(coverage_precheck and allow_coverage_short_circuit),
        "paper_registry_read": bool(paper_registry_enabled), "paper_registry_write": bool(update_global_corpus),
        "l1_cache_read": bool(l1_task_cache_enabled), "l1_cache_write": bool(l1_task_cache_enabled and update_global_corpus),
        "entity_cache_read": bool(not selected_registry), "entity_cache_write": bool(execute and not selected_registry),
        "legacy_modules_imported": legacy_imported, "legacy_artifacts_read": sorted(set(legacy_artifacts)),
        "legacy_config_used": legacy_config, "historical_runs_read": False,
        "resume_explicit": bool(resume_explicit), "current_run_only": True,
        "import_shadowing_risk": shadowing,
        "pilot_profile": pilot_profile,
        "pilot_terms_used": list(dict.fromkeys(str(item) for item in pilot_terms)),
        "domain_specific_defaults_used": list(dict.fromkeys(str(item) for item in domain_specific_defaults_used)),
        "ketamine_specific_defaults_used": bool(automatic_pilot_registry),
        "batch_id": batch_id, "triple_id": triple_id, "query_hash": query_hash,
        "seed_triple": seed_triple or {},
        "paper_artifact_cache_enabled": bool(paper_artifact_cache_enabled),
        "paper_artifact_cache_index": str(paper_artifact_cache_index) if paper_artifact_cache_index else None,
        "paper_artifact_cache_hits": int(paper_artifact_cache_hits),
        "paper_artifact_cache_misses": int(paper_artifact_cache_misses),
        "cross_batch_paper_artifacts_reused": bool(paper_artifact_cache_hits),
        "reasoning_artifacts_reused_from_other_batch": False,
        "cache_hit_records": list(cache_hit_records), "cache_miss_records": list(cache_miss_records),
        "semantic_seed_triple_source": "intake",
        "semantic_seed_count": max(len(intake.get("seed_triples") or []), int(bool(intake.get("unified_seed_triple")))),
        "seed_triple_confidence": (intake.get("unified_seed_triple") or {}).get("confidence"),
        "seed_triple_human_review_required": bool((intake.get("unified_seed_triple") or {}).get("human_review_required")),
        "abstract_retrieval_source_order": list((search_plan.get("abstract_retrieval") or {}).get("source_order") or ["pubmed"]),
        "abstract_open_access_required": bool((search_plan.get("abstract_retrieval") or {}).get("open_access_required", False)),
        "abstract_fulltext_required": bool((search_plan.get("abstract_retrieval") or {}).get("fulltext_required", False)),
        "fulltext_escalation_after_conflict_screening": True,
        "fulltext_escalation_enabled": bool(run_state.get("fulltext_escalation_enabled")),
        "fulltext_open_access_required": True,
        "fulltext_candidates_from_conflicts_only": True,
        "initial_fulltext_download_count": int(acquisition.get("initial_fulltext_download_count", 0)),
        "fulltext_download_count": int(fulltext_acquisition.get("fulltext_download_count", 0)),
        "fulltext_downloaded_only_selected_candidates": bool(fulltext_acquisition.get("downloaded_only_selected_candidates", True)),
        "evidence_graph_core_before_fulltext_escalation": True,
        "triple_id_consistent_across_artifacts": len(set(identity_values)) <= 1,
        "paper_cache_consumed_by_l1": bool(abstract_cache.get("paper_cache_consumed_by_l1") or fulltext_cache.get("paper_cache_consumed_by_l1")),
        "paper_cache_consumed_by_acquisition": bool(acquisition.get("paper_cache_consumed_by_acquisition")),
        "l1_task_cache_hits": int(abstract_cache.get("hit_count", 0)) + int(fulltext_cache.get("hit_count", 0)),
        "l1_task_cache_misses": int(abstract_cache.get("miss_count", 0)) + int(fulltext_cache.get("miss_count", 0)),
        "l1_task_cache_fingerprint_complete": True,
        "static_journal_weight_used": False,
        "belief_weight_used_for_reasoning": False,
        "impact_factor_used_for_reasoning": False,
        "paper_quality_metadata_used_for_display_only": True,
        "l1_timeout_config": dict(l1_timeout_config or {}),
        "abstract_l1_timeout_count": int(abstract_l1.get("timeout_count", 0)),
        "fulltext_l1_timeout_count": int(fulltext_l1.get("timeout_count", 0)),
        "workflow_continued_after_l1_timeout": bool(
            (int(abstract_l1.get("timeout_count", 0)) and abstract_l1.get("workflow_continued_after_l1_errors")) or
            (int(fulltext_l1.get("timeout_count", 0)) and fulltext_l1.get("workflow_continued_after_l1_errors"))
        ),
        "paper_year_filter": dict(paper_year_filter or {}),
        "papers_excluded_by_year_filter": int(acquisition_year.get("papers_excluded_by_year_filter", 0)),
        "papers_missing_year_excluded": int(acquisition_year.get("papers_missing_year_excluded", 0)),
        "temporal_filter_violation_detected": bool(
            abstract_l1.get("temporal_filter_violation_detected") or fulltext_l1.get("temporal_filter_violation_detected") or
            _reasoning_year_violation(artifacts, dict(paper_year_filter or {}))
        ),
        "semantic_search_intent": {
            "enabled": True, "mode": search_intent.get("mode"),
            "confidence": search_intent.get("confidence", 0.0),
            "confidence_source": search_intent.get("confidence_source", "failed_zero"),
            "planner_prompt_profile_id": search_intent.get("planner_prompt_profile_id"),
            "planner_prompt_version": search_intent.get("planner_prompt_version"),
            "planner_prompt_hash": search_intent.get("planner_prompt_hash"),
            "planner_prompt_chars": search_intent.get("planner_prompt_chars", 0),
            "llm_search_intent_used": bool(search_intent.get("llm_search_intent_used")),
            "search_intent_schema_valid": bool(search_intent.get("search_intent_schema_valid")),
            "normalization_applied": bool(search_intent.get("normalization_applied")),
            "normalization_repair_count": int(search_intent.get("normalization_repair_count", 0)),
            "search_intent_schema_valid_after_normalization": bool(search_intent.get("search_intent_schema_valid_after_normalization")),
            "deterministic_search_fallback_used": bool(search_intent.get("deterministic_search_fallback_used")),
            "allow_deterministic_search_fallback": bool(search_intent.get("allow_deterministic_search_fallback")),
            "real_api_run_with_uncertain_search_intent": bool(search_intent.get("real_api_run_with_uncertain_search_intent")),
            "planner_error": search_intent.get("planner_error"),
            "planner_error_type": search_intent.get("planner_error_type"),
            "blocked_reason": search_intent.get("blocked_reason"),
        },
        "query_guard": query_guard,
        "context_aware_evidence_layering": {
            "enabled": True,
            "context_specific_run": bool(((search_intent.get("seed_triple") or intake.get("unified_seed_triple") or {}).get("context") or {}).get("terms") or ((search_intent.get("seed_triple") or intake.get("unified_seed_triple") or {}).get("context") or {}).get("context_terms")),
            "context_terms": list(((search_intent.get("seed_triple") or intake.get("unified_seed_triple") or {}).get("context") or {}).get("terms") or ((search_intent.get("seed_triple") or intake.get("unified_seed_triple") or {}).get("context") or {}).get("context_terms") or []),
            "context_guard_enabled": bool(query_guard.get("context_guard_enabled")),
            "context_mismatch_core_block_enabled": True,
            "query_context_alone_sufficient_for_core": False,
            "strong_context_required_for_context_specific_core": True,
            "strong_context_sources": ["evidence_sentence", "abstract", "title", "metadata", "l1_context_slots"],
            "weak_context_sources": ["retrieval_query", "user_query", "semantic_intent"],
            "cross_context_mechanism_retention_enabled": True,
        },
        "seed_predicate_anchoring": {
            "enabled": True, "core_requires_seed_predicate_anchor": True,
            "predicate_direction_consistency_required": True,
        },
        "search_plan_provenance_consistent": all(
            query.get("search_intent_mode") == search_intent.get("mode")
            and bool(query.get("passed_query_guard"))
            and query.get("paper_year_filter_enabled") == bool((search_plan.get("paper_year_filter") or {}).get("enabled"))
            and query.get("temporal_role") == (search_plan.get("paper_year_filter") or {}).get("temporal_role")
            for query in search_plan.get("pubmed_queries", [])
        ) if search_plan.get("pubmed_queries") else True,
        "l2_layered_retention": {
            "enabled": True,
            "binary_high_confidence_gate_used_as_only_retention_gate": False,
            "runtime_entity_hints_used": bool(l2_summary.get("runtime_entity_hints_used")),
            "run_entity_registry_enabled": True,
            "external_entity_resolution_enabled": False,
            "core_graph_remains_strict": True,
        },
        "l2_summary_semantics": {
            "layered_retention_enabled": True,
            "excluded_low_confidence_count_uses_legacy_semantics": False,
            "non_core_observation_count_available": "non_core_observation_count" in l2_summary,
            "excluded_from_retention_count_available": "excluded_from_retention_count" in l2_summary,
        },
        "l2_counts": {key: int(l2_summary.get(key, 0)) for key in (
            "core_canonical_observation_count", "cross_context_mechanism_observation_count", "mechanism_observation_count",
            "context_observation_count", "review_observation_count", "excluded_observation_count",
        )},
        "prompt_profile_id": abstract_l1.get("prompt_profile_id") or fulltext_l1.get("prompt_profile_id"),
        "prompt_profile_version": abstract_l1.get("prompt_profile_version") or fulltext_l1.get("prompt_profile_version"),
        "abstract_l1_prompt_uses_compiled_profile": bool(abstract_l1.get("abstract_l1_prompt_uses_compiled_profile")),
        "fulltext_l1_prompt_uses_compiled_profile": bool(fulltext_l1.get("fulltext_l1_prompt_uses_compiled_profile")),
        "hardcoded_abstract_l1_prompt_used": bool(abstract_l1.get("hardcoded_abstract_l1_prompt_used", False)),
        "l1_prompt_calls": list(abstract_l1.get("prompt_calls") or []) + list(fulltext_l1.get("prompt_calls") or []),
        "warnings": [],
    }
    for warning in [*abstract_l1.get("warnings", []), *fulltext_l1.get("warnings", [])]:
        if str(warning).startswith(("l1_response_", "legacy_causal_tuples_")):
            provenance["warnings"].append(str(warning))
    if shadowing:
        provenance["warnings"].append("top_level_code_engine_package_shadows_src_package")
    if legacy_artifacts:
        provenance["warnings"].append("legacy_artifact_fallback_read_explicitly_reported")
    if automatic_pilot_registry:
        provenance["warnings"].append("automatic_query_selected_pilot_is_forbidden")
    if provenance["entity_cache_read"]:
        provenance["warnings"].append("entity_cache_read_with_provenance")
    if provenance["l1_cache_read"]:
        provenance["warnings"].append("l1_cache_read_exact_task_signature_only")
    return provenance


def contamination_check(provenance: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if provenance.get("import_shadowing_risk"): blockers.append("code_engine_import_shadowing")
    if provenance.get("legacy_modules_imported"): blockers.append("legacy_pipeline_used")
    if provenance.get("historical_runs_read") and not provenance.get("resume_explicit"): blockers.append("historical_runs_read_without_explicit_resume")
    if provenance.get("global_evidence_injected_before_reasoning"): blockers.append("global_evidence_injected_before_reasoning")
    if provenance.get("ketamine_specific_defaults_used"): blockers.append("ketamine_specific_defaults_used")
    if any(provenance.get(key) for key in (
        "static_journal_weight_used", "belief_weight_used_for_reasoning",
        "impact_factor_used_for_reasoning",
    )):
        blockers.append("static_belief_weight_used_in_core_reasoning")
    if provenance.get("temporal_filter_violation_detected"):
        blockers.append("temporal_filter_violation_detected")
    warnings = list(provenance.get("warnings", []))
    return {
        "status": "blocked" if blockers else ("warning" if warnings else "pass"),
        "import_shadowing_risk": bool(provenance.get("import_shadowing_risk")),
        "legacy_pipeline_used": bool(provenance.get("legacy_modules_imported")),
        "legacy_config_used": bool(provenance.get("legacy_config_used")),
        "historical_runs_read": bool(provenance.get("historical_runs_read")),
        "global_evidence_injected_before_reasoning": bool(provenance.get("global_evidence_injected_before_reasoning")),
        "unsafe_artifact_fallback": False, "blocking_reasons": blockers, "warnings": warnings,
    }


def write_runtime_provenance(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


__all__ = ["build_runtime_provenance", "contamination_check", "imported_legacy_modules", "write_runtime_provenance"]
