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
        "warnings": [],
    }
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
