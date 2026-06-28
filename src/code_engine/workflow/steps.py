"""Thin workflow adapters around existing scientific modules."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from code_engine.domain.router import default_domain_router
from code_engine.query.intake import parse_research_intake
from code_engine.query.search_planner import LiteratureSearchPlan, build_literature_search_plan


@dataclass
class StepResult:
    status: str = "completed"
    summary: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    api_calls_made: int = 0
    network_calls_made: int = 0
    skipped_reason: str | None = None


def _write(run_dir: Path, name: str, payload: Any) -> str:
    path = run_dir / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read(run_dir: Path, name: str, default: Any = None) -> Any:
    path = run_dir / "artifacts" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def run_intake_step(*, query: str, run_dir: Path, execute: bool, api: bool, **_: Any) -> StepResult:
    # No client is injected here: the workflow must never construct an implicit API client.
    intake = parse_research_intake(query, use_api=False)
    profile = default_domain_router().resolve(intake.research_intent.domain_id) or default_domain_router().route_text(query)
    intake_path = _write(run_dir, "intake.json", intake)
    profile_path = _write(run_dir, "domain_profile.json", profile.to_dict())
    summary = {
        "domain_id": profile.domain_id, "subdomain_id": profile.subdomain_id,
        "domain_profile_id": profile.profile_id, "prompt_profile_id": profile.prompt_profile_id,
        "entity_registry_profile": profile.entity_registry_profile,
        "validator_profile_id": profile.validator_profile_id,
        "seed_triple_count": len(intake.seed_triples),
    }
    warnings = list(intake.ambiguities)
    if execute and api:
        warnings.append("api_enabled_but_no_intake_client_configured_deterministic_parser_used")
    return StepResult(summary=summary, artifacts={"intake": intake_path, "domain_profile": profile_path}, counts={"seed_triple_count": len(intake.seed_triples)}, warnings=warnings)


def run_search_step(*, run_dir: Path, execute: bool, api: bool, max_papers: int | None, **_: Any) -> StepResult:
    intake_data = _read(run_dir, "intake.json")
    profile_data = _read(run_dir, "domain_profile.json")
    if not intake_data or not profile_data:
        return StepResult(status="blocked", warnings=["intake_artifacts_missing"], skipped_reason="intake_artifacts_missing")
    from code_engine.domain.models import DomainProfile
    from code_engine.query.intake import ResearchIntakeResult
    intake = ResearchIntakeResult.model_validate(intake_data)
    profile_data = dict(profile_data)
    for key in ("aliases", "preferred_validators", "fallback_validators", "required_context_slots", "optional_context_slots", "key_entity_types", "key_relation_types", "key_evidence_types", "warnings"):
        if key in profile_data:
            profile_data[key] = tuple(profile_data[key])
    profile = DomainProfile(**profile_data)
    plan = build_literature_search_plan(intake.research_intent, seed_triples=intake.seed_triples, domain_profile=profile, use_llm=False)
    if max_papers is not None:
        plan.max_total_results = max_papers
        for query in plan.pubmed_queries + plan.pmc_queries:
            query.max_results = min(query.max_results, max_papers)
    path = _write(run_dir, "search_plan.json", plan)
    count = len(plan.pubmed_queries) + len(plan.pmc_queries)
    warnings = list(plan.warnings)
    if execute and api:
        warnings.append("api_enabled_but_search_query_generation_remains_deterministic")
    return StepResult(summary={"query_count": count, "domain_id": plan.domain_id, "search_profile_id": plan.search_profile_id, "prompt_profile_id": plan.prompt_profile_id, "validator_profile_id": plan.validator_profile_id}, artifacts={"search_plan": path}, counts={"search_query_count": count}, warnings=warnings)


def run_acquisition_step(*, run_dir: Path, repository_root: Path, execute: bool, network: bool, max_papers: int | None, **_: Any) -> StepResult:
    plan_data = _read(run_dir, "search_plan.json")
    if not plan_data:
        return StepResult(status="blocked", warnings=["search_plan_missing"], skipped_reason="search_plan_missing")
    plan = LiteratureSearchPlan.model_validate(plan_data)
    acquisition_plan = {"intent_id": plan.intent_id, "queries": [item.model_dump() for item in plan.pmc_queries + plan.pubmed_queries], "max_papers": max_papers or plan.max_total_results, "execute": execute, "network": network}
    plan_path = _write(run_dir, "acquisition_plan.json", acquisition_plan)
    if execute and network:
        from code_engine.acquisition.literature_search import execute_acquisition_plan
        report = execute_acquisition_plan(plan, repository_root=repository_root, execute=True, network=True, max_papers=max_papers or plan.max_total_results)
    else:
        report = {"intent_id": plan.intent_id, "execution_mode": "plan_only", "candidate_papers": list(plan.candidate_papers), "reused_papers": [], "downloaded_papers": [], "skipped_duplicates": [], "network_calls_made": 0, "warnings": ["network_disabled_acquisition_plan_only"]}
    report_path = _write(run_dir, "acquisition_report.json", report)
    summary = {key: len(report.get(key, [])) for key in ("candidate_papers", "reused_papers", "downloaded_papers", "skipped_duplicates")}
    calls = int(report.get("network_calls_made", 0))
    return StepResult(status="completed" if execute and network else "planned", summary=summary, artifacts={"acquisition_plan": plan_path, "acquisition_report": report_path}, counts=summary, warnings=report.get("warnings", []), network_calls_made=calls)


def run_payload_step(*, run_dir: Path, execute: bool, **_: Any) -> StepResult:
    acquisition = _read(run_dir, "acquisition_report.json", {})
    downloaded = acquisition.get("downloaded_papers", [])
    report = {"payload_count": 0, "chunk_count": 0, "inputs": downloaded, "mode": "execute" if execute else "dry_run"}
    warnings = []
    status = "planned"
    reason = None
    if not downloaded:
        status, reason = "blocked", "no_raw_data_in_run"
        warnings.append("payload_build_blocked_no_raw_data_in_run")
    elif execute:
        from code_engine.preprocessing.payload_builder import build_payloads_for_downloads
        repository_root = Path(_["repository_root"])
        chunks = build_payloads_for_downloads(downloaded, repository_root)
        report.update({"payload_count": len({item["paper_id"] for item in chunks}), "chunk_count": len(chunks), "chunks": chunks})
        status = "completed"
    else:
        status = "planned"
        reason = "execute_required_for_payload_build"
        warnings.append("payload_inputs_available_execution_disabled")
    path = _write(run_dir, "payload_report.json", report)
    return StepResult(status=status, summary=report, artifacts={"payload_report": path}, counts={"payload_count": report["payload_count"], "chunk_count": report["chunk_count"]}, warnings=warnings, skipped_reason=reason)


def run_l1_step(*, run_dir: Path, execute: bool, api: bool, **kwargs: Any) -> StepResult:
    profile = _read(run_dir, "domain_profile.json", {})
    payload = _read(run_dir, "payload_report.json", {})
    chunks = list(payload.get("chunks", []))
    plan = {"prompt_profile_id": profile.get("prompt_profile_id"), "domain_id": profile.get("domain_id"), "reused_chunks": 0, "chunks_need_l1": len(chunks), "execute": execute, "api": api}
    plan_path = _write(run_dir, "l1_plan.json", plan)
    result = {"chunks_reused": [], "chunks_extracted": [], "extraction_needed": [], "errors": [], "api_calls_made": 0}
    if chunks:
        from code_engine.domain.models import DomainProfile
        from code_engine.extraction.l1_extractor import execute_l1_extraction
        profile_payload = dict(profile)
        for key in ("aliases", "preferred_validators", "fallback_validators", "required_context_slots", "optional_context_slots", "key_entity_types", "key_relation_types", "key_evidence_types", "warnings"):
            if key in profile_payload:
                profile_payload[key] = tuple(profile_payload[key])
        result = execute_l1_extraction(chunks, repository_root=str(kwargs["repository_root"]), execute=execute, api=api, domain_profile=DomainProfile(**profile_payload))
    summary = {**plan, "reused_chunks": len(result["chunks_reused"]), "chunks_need_l1": len(result["extraction_needed"]), "extracted_claim_count": len(result["chunks_extracted"]), "api_calls_made": int(result["api_calls_made"]), "outputs": result["chunks_extracted"], "errors": result["errors"]}
    summary_path = _write(run_dir, "l1_summary.json", summary)
    reason = "no_weighted_payloads" if not chunks else ("api_disabled_l1_plan_only" if not api else None)
    status = "blocked" if not chunks else ("completed" if execute and api and not result["errors"] else "planned")
    return StepResult(status=status, summary=summary, artifacts={"l1_plan": plan_path, "l1_summary": summary_path}, counts={"reused_chunks": summary["reused_chunks"], "chunks_need_l1": summary["chunks_need_l1"], "extracted_claim_count": summary["extracted_claim_count"]}, warnings=([reason] if reason else []) + [str(item) for item in result["errors"]], api_calls_made=summary["api_calls_made"], skipped_reason=reason)


def _blocked_summary_step(filename: str, artifact_key: str, reason: str, summary: dict[str, Any], counts: dict[str, int] | None = None) -> Callable[..., StepResult]:
    def run(*, run_dir: Path, **_: Any) -> StepResult:
        path = _write(run_dir, filename, summary)
        return StepResult(status="blocked", summary=summary, artifacts={artifact_key: path}, counts=counts or {}, warnings=[reason], skipped_reason=reason)
    return run


def run_l1_5_step(*, run_dir: Path, execute: bool, repository_root: Path, **_: Any) -> StepResult:
    l1 = _read(run_dir, "l1_summary.json", {})
    outputs = [repository_root / item["output_path"] for item in l1.get("outputs", []) if item.get("output_path")]
    refined = []
    if execute and outputs:
        from code_engine.extraction.l1_refiner import refine_l1_file
        target_dir = run_dir / "artifacts" / "l1_5_data"
        for index, source in enumerate(outputs):
            target = target_dir / f"{source.stem}_{index}_refined.json"
            result = refine_l1_file(source, target)
            refined.append({"input": str(source), "output": str(target), "refined_claim_count": len(result.get("refined_claims", []))})
    summary = {"refined_claim_count": sum(item["refined_claim_count"] for item in refined), "outputs": refined}
    path = _write(run_dir, "l1_5_summary.json", summary)
    reason = None if refined else "no_l1_claims_in_run"
    return StepResult(status="completed" if refined else "blocked", summary=summary, artifacts={"l1_5_summary": path}, counts={"refined_claim_count": summary["refined_claim_count"]}, warnings=[reason] if reason else [], skipped_reason=reason)


def run_l2_step(*, run_dir: Path, execute: bool, **_: Any) -> StepResult:
    refined_dir = run_dir / "artifacts" / "l1_5_data"
    observations, audit = [], []
    if execute and refined_dir.exists():
        from code_engine.graph.ontology_alignment import extract_normalized_observations
        from code_engine.normalization.resolver import ResolverCascade
        profile = _read(run_dir, "domain_profile.json", {})
        resolver = ResolverCascade(domain_id=profile.get("domain_id", "general_biomedical"), entity_registry_profile=profile.get("entity_registry_profile", "general_biomedical_registry"), resolver_policy_id=profile.get("resolver_policy_id", "conservative_resolver_v2"))
        observations, audit = extract_normalized_observations(str(refined_dir), None, [], resolver=resolver)
    statuses: dict[str, int] = {}
    for item in audit:
        status = str(item.get("normalization_status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
    summary = {"resolved_count": statuses.get("resolved", 0), "ambiguous_count": statuses.get("ambiguous", 0), "unresolved_fallback_count": statuses.get("unresolved_fallback", 0), "excluded_low_confidence_count": sum(not item.get("allow_high_confidence_graph_use", False) for item in audit), "normalization_records": audit}
    path = _write(run_dir, "l2_normalization_audit.json", summary)
    observations_path = _write(run_dir, "l2_observations.json", observations)
    reason = None if observations else "no_l1_5_claims_in_run"
    return StepResult(status="completed" if observations else "blocked", summary=summary, artifacts={"l2_normalization_audit": path, "l2_observations": observations_path}, counts={key: value for key, value in summary.items() if key.endswith("_count")}, warnings=[reason] if reason else [], skipped_reason=reason)


def run_conflict_step(*, run_dir: Path, execute: bool, **_: Any) -> StepResult:
    observations = _read(run_dir, "l2_observations.json", [])
    edges, graph, attributions, audit = [], [], [], {}
    if execute and observations:
        from code_engine.graph.conflict_discovery import build_conflict_graph
        graph, edges, attributions, audit = build_conflict_graph(observations, latent_pool=[])
    types = {"Type I": 0, "Type II": 0, "Type III": 0, "Uncontested": 0}
    for edge in graph:
        key = edge.get("conflict_attribution_type", "Uncontested")
        types[key] = types.get(key, 0) + 1
    summary = {"conflict_edge_count": len(edges), "uncontested_count": types["Uncontested"], "type_i_count": types["Type I"], "type_ii_count": types["Type II"], "type_iii_count": types["Type III"], "skipped_low_confidence_observation_count": int(audit.get("skipped_low_confidence_observation_count", 0)), "conflict_edges": edges, "context_attributions": attributions}
    path = _write(run_dir, "conflict_graph_summary.json", summary)
    reason = None if observations else "no_normalized_observations_in_run"
    return StepResult(status="completed" if observations else "blocked", summary=summary, artifacts={"conflict_graph_summary": path}, counts={key: value for key, value in summary.items() if key.endswith("_count")}, warnings=[reason] if reason else [], skipped_reason=reason)
run_hypothesis_step = _blocked_summary_step("hypothesis_summary.json", "hypothesis_summary", "no_conflict_graph_in_run", {"hypothesis_count": 0}, {"hypothesis_count": 0})


def run_validation_step(*, run_dir: Path, execute: bool, **_: Any) -> StepResult:
    from code_engine.domain.models import DomainProfile
    from code_engine.validation.router import DomainAdaptiveValidationRouter
    profile_data = _read(run_dir, "domain_profile.json", {})
    for key in ("aliases", "preferred_validators", "fallback_validators", "required_context_slots", "optional_context_slots", "key_entity_types", "key_relation_types", "key_evidence_types", "warnings"):
        if key in profile_data:
            profile_data[key] = tuple(profile_data[key])
    profile = DomainProfile(**profile_data)
    hypothesis_data = _read(run_dir, "hypothesis_summary.json", {})
    hypotheses = hypothesis_data.get("hypotheses", [])
    placeholder = {"hypothesis_id": "PLANNED", "seed_pair": "", "relation_type": profile.key_relation_types[0] if profile.key_relation_types else "unknown"}
    plans = [DomainAdaptiveValidationRouter().create_plan(item, profile) for item in (hypotheses or [placeholder])]
    plan_payload = {"domain_id": profile.domain_id, "validator_profile_id": profile.validator_profile_id, "plans": [item.model_dump() for item in plans], "planning_only": not bool(execute and hypotheses)}
    plan_path = _write(run_dir, "validation_plan.json", plan_payload)
    selected = list(dict.fromkeys(name for plan in plans for name in plan.selected_validators))
    results = []
    coverage = []
    if execute and hypotheses:
        from code_engine.validation.registry import ValidatorRegistry
        from code_engine.validation.result_aggregator import ValidationResultAggregator
        registry = ValidatorRegistry().register_defaults()
        for plan in plans:
            plan_results = [registry.validate(name, question) for question in plan.questions for name in plan.selected_validators]
            results.extend(plan_results)
            coverage.append(ValidationResultAggregator().aggregate(plan_results).model_dump())
    coverage_summary = {"overall_status": "no_coverage", "reason": "no_candidate_hypotheses" if not hypotheses else "validation_execution_not_requested"}
    if coverage:
        coverage_summary = {"reports": coverage, "overall_status": coverage[0]["overall_status"] if len(coverage) == 1 else "multiple_hypotheses"}
    summary = {"validation_question_count": sum(len(plan.questions) for plan in plans), "selected_validators": selected, "validation_result_count": len(results), "validation_results": [item.model_dump() for item in results], "coverage_summary": coverage_summary}
    summary_path = _write(run_dir, "validation_summary.json", summary)
    return StepResult(status="completed" if execute and hypotheses else "planned", summary=summary, artifacts={"validation_plan": plan_path, "validation_summary": summary_path}, counts={"validation_question_count": summary["validation_question_count"], "validation_result_count": len(results)}, warnings=["validation_plan_generated_without_candidate_hypotheses"] if not hypotheses else [])


STEP_RUNNERS = {
    "intake": run_intake_step, "search": run_search_step, "acquisition": run_acquisition_step,
    "payload": run_payload_step, "l1": run_l1_step, "l1_5": run_l1_5_step, "l2": run_l2_step,
    "conflict": run_conflict_step, "hypothesis": run_hypothesis_step, "validation": run_validation_step,
}
