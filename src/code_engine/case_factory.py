"""Natural-language to reproducible, run_case-compatible case packages."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.search.search_plan_replay import load_frozen_search_plan
from code_engine.validation.readiness import check_case_readiness
from code_engine.workflow.steps import run_intake_step, run_search_step

CONFLICT_NEEDS = ["post_cutoff_literature", "pathway_membership", "gene_set_enrichment", "full_text_conflict_confirmation"]
CONFLICT_EXPECTED = ["pubmed_post_cutoff", "reactome", "enrichr"]
CONFLICT_OPTIONAL = ["chembl", "opentargets", "pmc_oa"]
VALIDATOR_BY_NEED = {
    "post_cutoff_literature": "pubmed_post_cutoff", "pathway_membership": "reactome",
    "gene_set_enrichment": "enrichr", "drug_target_annotation": "chembl",
    "target_disease_association": "opentargets", "drug_perturbation_transcriptomic": "lincs_l1000",
    "full_text_conflict_confirmation": "pmc_oa",
}
BOUNDARIES = [
    "Search plan targets conflict-enriched literature but does not prove conflict.",
    "Abstract-only conflict requires full-text confirmation.",
    "PubMed hit count is not support or refutation.",
    "Reactome and Enrichr are plausibility metadata, not causal proof.",
]


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unique(*values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for group in values for item in group if str(item).strip()))


def build_case_profile(*, case_id: str, query: str, case_type: str, semantic_intake: dict[str, Any],
                       domain_profile: dict[str, Any]) -> dict[str, Any]:
    intent = semantic_intake.get("research_intent") or {}
    routing = semantic_intake.get("domain_routing") or intent.get("domain_routing") or {}
    seeds = list(semantic_intake.get("seed_triples") or [])
    seed_types = [str(value) for seed in seeds for value in (seed.get("subject_type"), seed.get("object_type")) if value]
    genes = [str(seed.get(side) or "") for seed in seeds for side in ("subject", "object")
             if str(seed.get(f"{side}_type") or "").casefold() == "gene"]
    conflict = case_type == "conflict_enriched"
    needs = list(CONFLICT_NEEDS if conflict else [])
    if not conflict:
        domain_need = {"drug_target_binding": "drug_target_annotation", "pathway_biology": "pathway_membership",
                       "clinical_outcome": "post_cutoff_literature"}.get(str(routing.get("domain_id") or ""))
        if domain_need: needs.append(domain_need)
    expected = list(CONFLICT_EXPECTED if conflict else [VALIDATOR_BY_NEED[x] for x in needs if x in VALIDATOR_BY_NEED])
    optional = list(CONFLICT_OPTIONAL if conflict else domain_profile.get("fallback_validators") or [])
    fulltext = {"enabled": conflict, "source": "pmc_oa", "selection_policy": "conflict_related_only",
                "max_papers": 20, "include_near_conflicts": True, "require_oa": True, "skip_non_oa": True}
    alternatives = [str(item.get("domain_id") or "") if isinstance(item, dict) else str(item)
                    for item in routing.get("alternative_domains") or []]
    return {
        "schema_version": "case_domain_profile_v1", "case_id": case_id, "case_version": "v1",
        "query": query, "case_type": case_type, "case_role": "conflict_discovery" if conflict else "discovery",
        "domain_tags": _unique([str(routing.get("domain_id") or domain_profile.get("domain_id") or "general_biomedical")], alternatives),
        "disease_areas": _unique(list(intent.get("disease_or_condition") or [])),
        "mechanism_areas": _unique(list(intent.get("mechanism_entities") or []), list(intent.get("outcome_entities") or [])),
        "genes": _unique(genes), "entity_types": _unique(list(domain_profile.get("key_entity_types") or []), seed_types),
        "intervention_types": ["intervention"] if intent.get("intervention_entities") else [],
        "validation_needs": needs, "expected_validators": expected, "optional_validators": optional,
        "excluded_validators": [], "validator_policy": {"require_production_validators": False},
        "fulltext_policy": fulltext,
        "scientific_notes": {"intended_conflict": query if conflict else "No conflict is asserted by package generation.",
                             "do_not_overclaim": list(BOUNDARIES)}, "profile_version": "1.0",
    }


def _report_md(manifest: dict[str, Any]) -> str:
    warnings = manifest.get("warnings") or []
    return (f"# Case Factory Report: {manifest['case_id']}\n\n"
            f"- Status: `{manifest['status']}`\n- Semantic mode: `{manifest['semantic_mode']}`\n"
            f"- Frozen search plan: `{str(manifest['frozen_search_plan']).lower()}`\n"
            f"- Readiness: `{manifest['readiness_status']}`\n- Warnings: {len(warnings)}\n\n"
            "Generated artifacts are planning artifacts, not scientific evidence.\n")


def generate_case_package(*, case_id: str, query: str, case_type: str = "conflict_enriched",
                          year_from: int | None = None, year_to: int | None = None,
                          output_root: str | Path = "configs/generated_cases", api: bool = False,
                          network: bool = False, freeze_search_plan: bool = True, run_readiness: bool = False,
                          copy_to_configs: bool = False, overwrite_generated: bool = False,
                          overwrite_configs: bool = False, repository_root: str | Path = ".",
                          llm_client: Any | None = None) -> dict[str, Any]:
    root = Path(repository_root)
    output = root / Path(output_root) / case_id
    if output.exists() and any(output.iterdir()) and not overwrite_generated:
        raise FileExistsError(f"generated case already exists: {output}; pass --overwrite-generated")
    active_client = llm_client
    if api and active_client is None:
        try:
            from code_engine.encoder.scientific_encoder import create_default_scientific_encoder_client
            active_client = create_default_scientific_encoder_client()
        except Exception:
            active_client = None
    with tempfile.TemporaryDirectory(prefix=f"case_factory_{case_id}_") as temp:
        work = Path(temp); (work / "artifacts").mkdir()
        intake_result = run_intake_step(query=query, run_dir=work, execute=api, api=api,
                                        allow_uncertain_intake=True, semantic_llm_client=active_client)
        year_filter = {"paper_year_from": year_from, "paper_year_to": year_to,
                       "temporal_role": "discovery", "source": "case_factory"}
        frozen = work / "artifacts" / "search_plan.frozen.json"
        search_result = run_search_step(run_dir=work, execute=api, api=api, network=network, max_papers=60,
                                        query=query, paper_year_filter=year_filter, semantic_llm_client=active_client,
                                        allow_deterministic_search_fallback=True, save_search_plan=frozen,
                                        freeze_search_plan_requested=freeze_search_plan)
        if search_result.status == "blocked" or not frozen.is_file():
            raise RuntimeError(f"search plan generation failed: {search_result.warnings}")
        load_frozen_search_plan(frozen, fail_if_drift=True)
        intake = json.loads((work / "artifacts/intake.json").read_text(encoding="utf-8"))
        semantic = intake.get("semantic_intake") or {}
        domain = json.loads((work / "artifacts/domain_profile.json").read_text(encoding="utf-8"))
        profile = build_case_profile(case_id=case_id, query=query, case_type=case_type,
                                     semantic_intake=semantic, domain_profile=domain)
        if output.exists() and overwrite_generated: shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)
        _write(output / "case_profile.json", profile)
        shutil.copy2(frozen, output / "search_plan.frozen.json")
        _write(output / "semantic_intake.json", semantic)
        for name in ("semantic_search_intent.json", "search_query_guard_report.json"):
            shutil.copy2(work / "artifacts" / name, output / name)
    readiness = None
    if run_readiness:
        readiness = check_case_readiness(output / "case_profile.json", output / "search_plan.frozen.json",
                                         root / "data/external", network_allowed=network)
        _write(output / "readiness_report.json", readiness)
    search_warnings = [item for item in search_result.warnings
                       if not (item == "api_enabled_but_search_query_generation_remains_deterministic"
                               and search_result.summary.get("llm_search_intent_used"))]
    warnings = _unique(intake_result.warnings, search_warnings, (readiness or {}).get("blocking_reasons", []),
                       (readiness or {}).get("warnings", []))
    readiness_status = "NOT_RUN" if readiness is None else ("READY" if readiness.get("ready") else "WARNINGS")
    status = "CASE_FACTORY_GENERATED_WITH_READINESS_WARNINGS" if readiness is not None and not readiness.get("ready") else "CASE_FACTORY_GENERATED"
    generated = [p.name for p in sorted(output.iterdir()) if p.is_file()]
    manifest = {"schema_version": "case_factory_manifest_v1", "case_id": case_id, "case_type": case_type,
                "query": query, "year_from": year_from, "year_to": year_to,
                "semantic_mode": intake_result.summary.get("semantic_mode", "deterministic_degraded"),
                "llm_used": bool(intake_result.api_calls_made or search_result.api_calls_made), "network_used": bool(network),
                "generated_files": generated + ["case_factory_manifest.json", "case_factory_report.md"],
                "case_profile_path": str(output / "case_profile.json"), "search_plan_path": str(output / "search_plan.frozen.json"),
                "frozen_search_plan": True, "readiness_run": bool(run_readiness), "readiness_status": readiness_status,
                "warnings": warnings, "created_at": datetime.now(timezone.utc).isoformat(), "status": status}
    _write(output / "case_factory_manifest.json", manifest)
    (output / "case_factory_report.md").write_text(_report_md(manifest), encoding="utf-8")
    if copy_to_configs:
        destinations = [(output / "case_profile.json", root / f"configs/case_profiles/{case_id}.case_profile.json"),
                        (output / "search_plan.frozen.json", root / f"configs/search_plans/{case_id}_{year_from}_{year_to}.llm_v1.frozen.json")]
        for source, destination in destinations:
            if destination.exists() and not overwrite_configs:
                raise FileExistsError(f"config already exists: {destination}; pass --overwrite-configs")
            destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, destination)
    return manifest


__all__ = ["build_case_profile", "generate_case_package"]
