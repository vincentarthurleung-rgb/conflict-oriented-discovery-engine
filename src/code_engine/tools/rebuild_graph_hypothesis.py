"""Offline rebuilding of graph/hypothesis/report artifacts from an existing run."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
from code_engine.hypothesis.search import run_hypothesis_search_for_run


def rebuild_graph_hypothesis(source_run: str | Path, *, output_suffix: str = "rebuilt_graph_gate",
                             stages: tuple[str, ...] = ("graph", "hypothesis", "report"),
                             external_data_root: str | Path = "data/external",
                             enable_lincs_local_validation: bool = False,
                             lincs_dataset: str = "GSE70138",
                             case_profile: str | Path | None = None) -> Path:
    source = Path(source_run).resolve()
    if not (source / "artifacts").is_dir():
        raise FileNotFoundError(f"source run artifacts missing: {source}")
    output = source.with_name(f"{source.name}_rebuilt_{output_suffix}")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    artifacts = output / "artifacts"

    def load(path: Path, default: dict | list | None = None):
        return json.loads(path.read_text()) if path.exists() else ({} if default is None else default)

    def replace_path_refs(value):
        if isinstance(value, dict):
            return {key: replace_path_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_path_refs(item) for item in value]
        if isinstance(value, str):
            rewritten = value.replace(str(source), str(output))
            if "/runs/" in rewritten and "/artifacts/" in rewritten:
                suffix = rewritten.split("/artifacts/", 1)[1]
                rewritten = str(artifacts / suffix)
            return rewritten
        return value

    # Copied plans must identify artifacts in the rebuilt run, not their source run.
    for name in ("validation_plan.json", "external_validation_execution_summary.json"):
        copied = artifacts / name
        if copied.exists():
            copied.write_text(json.dumps(replace_path_refs(load(copied)), ensure_ascii=False, indent=2), encoding="utf-8")

    source_provenance = load(source / "artifacts/runtime_provenance_report.json")
    source_state = load(source / "run_state.json")
    source_triple_id = str(source_provenance.get("triple_id") or
                           ((source_state.get("summary") or {}).get("triple_metadata") or {}).get("triple_id") or "")
    source_seed = source_provenance.get("seed_triple") or (((source_state.get("summary") or {}).get("triple_metadata") or {}).get("seed_triple") or {})
    mismatch_sources = []
    for name, path, key_path in (
        ("intake.unified_seed_triple", artifacts / "intake.json", ("unified_seed_triple",)),
        ("search_plan.seed_triple", artifacts / "search_plan.json", ("seed_triple",)),
        ("semantic_search_intent.seed_triple", artifacts / "semantic_search_intent.json", ("seed_triple",)),
    ):
        payload = load(path)
        value = payload
        for key in key_path:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        artifact_triple = str(value.get("triple_id") or "") if isinstance(value, dict) else ""
        if artifact_triple and source_triple_id and artifact_triple != source_triple_id:
            mismatch_sources.append(name)

    state_path = output / "run_state.json"
    state = load(state_path)
    if state:
        state["run_id"] = output.name
        state["api_calls_made"] = 0
        state["network_calls_made"] = 0
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance_path = artifacts / "runtime_provenance_report.json"
    provenance = dict(source_provenance)
    plan = load(artifacts / "search_plan.json")
    inherited_filter = dict(plan.get("paper_year_filter") or provenance.get("paper_year_filter") or {})
    if inherited_filter.get("paper_year_from") is not None or inherited_filter.get("paper_year_to") is not None:
        inherited_filter.update(enabled=True, source="inherited_from_source_run_or_frozen_search_plan",
                                hardcoded_cutoff_used=False)
    provenance.update({
        "run_id": output.name, "source_run_id": source.name, "rebuilt_run_id": output.name,
        "run_dir": str(output), "artifacts_dir": str(artifacts),
        "triple_id": source_triple_id or provenance.get("triple_id"), "seed_triple": source_seed,
        "paper_year_filter": inherited_filter,
        "triple_id_consistent_across_artifacts": not bool(mismatch_sources),
    })
    provenance["seed_identity_rebuild_policy"] = {
        "mode": "inherit_from_source_run", "semantic_intake_called": False,
        "llm_search_intent_called": False, "source_triple_id": source_triple_id,
        "rebuilt_triple_id": source_triple_id, "triple_id_changed": False,
        "triple_id_consistent_across_artifacts": not bool(mismatch_sources),
        "legacy_artifact_triple_id_mismatch_detected": bool(mismatch_sources),
        "mismatch_sources": mismatch_sources,
        "reason": "source run contained pre-existing artifact identity mismatch" if mismatch_sources else None,
        "rebuild_introduced_triple_id_mismatch": False,
    }
    provenance["rebuild_from_run"] = {
        "enabled": True, "source_run_dir": str(source), "rebuilt_run_dir": str(output),
        "rebuild_stages": list(stages), "api_calls": 0, "network_calls": 0,
        "source_l1_reused": True, "source_l2_reused": True, "source_acquisition_reused": True,
        "paper_year_filter_inherited": bool(inherited_filter.get("enabled")),
        "rebuild_reason": "graph_conflict_source_gate_update",
    }
    provenance["graph_conflict_source_gate"] = {
        "enabled": True, "requires_true_opposing_polarity": True, "requires_observation_provenance": True,
        "context_specific_run": bool((provenance.get("context_aware_evidence_layering") or {}).get("context_specific_run")),
        "requires_core_context_eligible": True, "requires_strong_context_match": True,
        "requires_core_graph_layer": True, "allows_mechanism_layer_for_conflict": False,
        "allows_review_layer_for_conflict": False, "allows_cross_context_for_conflict": False,
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    def clean_no_conflict_timelines() -> None:
        graph_summary = load(artifacts / "graph_conflict_summary.json") or load(artifacts / "merged_evidence_graph_summary.json")
        if int(graph_summary.get("true_graph_conflict_count", graph_summary.get("graph_conflict_candidate_count", 0))) != 0:
            return
        (artifacts / "conflict_evidence_timelines.jsonl").write_text("", encoding="utf-8")
        timeline_summary = {
            "run_id": output.name, "source_run_id": source.name, "rebuilt_run_id": output.name,
            "timeline_count": 0, "graph_conflict_candidates_used": 0, "timelines_from_graph_conflicts": 0,
            "timeline_rebuild_status": "skipped_due_to_no_true_graph_conflicts",
            "timeline_conflict_attachment_status": "not_applicable_no_true_graph_conflicts",
            "stale_source_timeline_artifacts_ignored": True, "warnings": [], "export_warnings": [],
        }
        (artifacts / "conflict_evidence_timeline_summary.json").write_text(json.dumps(timeline_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        for name in ("graph_conflict_summary.json", "merged_evidence_graph_summary.json"):
            path = artifacts / name
            if path.exists():
                value = load(path); value.update(graph_conflict_candidates_used_by_timeline=0,
                    timeline_rebuild_status="skipped_due_to_no_true_graph_conflicts",
                    timeline_conflict_attachment_status="not_applicable_no_true_graph_conflicts",
                    stale_source_timeline_artifacts_ignored=True)
                value["export_warnings"] = [warning for warning in value.get("export_warnings", []) if warning != "timelines_without_conflict_match"]
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        contract_path = artifacts / "merged_evidence_graph_contract_report.json"
        if contract_path.exists():
            contract = load(contract_path); contract["timelines_without_conflict_match"] = []
            contract["warnings"] = [warning for warning in contract.get("warnings", []) if warning != "timelines_without_conflict_match"]
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    if "graph" in stages:
        build_merged_evidence_graph_from_run_artifacts(output, include_hypotheses=False)
    clean_no_conflict_timelines()
    if "hypothesis" in stages:
        domain = json.loads((artifacts / "domain_profile.json").read_text()) if (artifacts / "domain_profile.json").exists() else {}
        mechanism = json.loads((artifacts / "mechanism_graph.json").read_text()) if (artifacts / "mechanism_graph.json").exists() else {}
        conflict = json.loads((artifacts / "conflict_graph_summary.json").read_text()) if (artifacts / "conflict_graph_summary.json").exists() else {}
        run_hypothesis_search_for_run(conflict, mechanism, domain, output, dry_run=True)
        if "graph" in stages:
            build_merged_evidence_graph_from_run_artifacts(output)

    if set(stages) & {"l4", "l5", "l6", "l7"}:
        from code_engine.reporting.full_abstract_pipeline import generate_full_abstract_pipeline
        generate_full_abstract_pipeline(output)
    else:
        from code_engine.reporting.whitebox_case import generate_whitebox_case_artifacts
        generate_whitebox_case_artifacts(output)
    selection = None
    case_profile_value = None
    if case_profile:
        from code_engine.validation.case_routing import load_case_domain_profile, route_case_validators
        case_profile_value = load_case_domain_profile(case_profile)
        (artifacts / "case_domain_profile.json").write_text(
            case_profile_value.model_dump_json(indent=2), encoding="utf-8")
        selection = route_case_validators(
            case_profile_value, external_data_root=external_data_root,
            lincs_dataset=lincs_dataset,
            manual_cli_validators=["lincs_l1000"] if enable_lincs_local_validation else [],
        )
    elif enable_lincs_local_validation:
        selection = {
            "selection_mode": "manual_cli_override", "selected_validators": ["lincs_l1000"],
            "recommended_but_unavailable": [], "manual_cli_overrides": ["lincs_l1000"],
            "deduplicated": False, "decisions": [],
        }
    if "l7" in stages and selection and "lincs_l1000" in selection["selected_validators"]:
        from code_engine.validation.lincs_local import LincsLocalValidator
        perturbagen = case_profile_value.query.split()[0] if case_profile_value and case_profile_value.query.split() else "metformin"
        lincs_summary = LincsLocalValidator().validate_run(
            output, external_data_root=external_data_root, dataset=lincs_dataset,
            perturbagen=perturbagen,
        )
        selection["executed_validators"] = ["lincs_l1000"] if lincs_summary.get("validation_executed") else []
    elif selection:
        selection["executed_validators"] = []

    if selection:
        selection_report = {"validator_selection": selection}
        (artifacts / "validator_selection_report.json").write_text(
            json.dumps(selection_report, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# Validator Selection Report", "", f"Selection mode: `{selection['selection_mode']}`", "",
                 "## Decisions", ""]
        for item in selection["decisions"]:
            lines.append(f"- `{item['validator_id']}`: **{item['decision']}** — {item['reason']}")
        (artifacts / "validator_selection_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if case_profile_value and selection:
        core = load(artifacts / "core_observation_summary.json")
        conflict = load(artifacts / "conflict_graph_summary.json")
        hypothesis = load(artifacts / "hypothesis_summary.json")
        lincs = load(artifacts / "l7_lincs_validation_summary.json")
        required = [artifacts / "case_domain_profile.json", artifacts / "validator_selection_report.json"]
        executed = list(selection.get("executed_validators", []))
        ready = all(path.exists() for path in required) and bool(executed)
        bundle = {
            "case_id": case_profile_value.case_id, "query": case_profile_value.query,
            "source_run_id": source.name, "final_run_id": output.name,
            "case_domain_profile_path": str(artifacts / "case_domain_profile.json"),
            "executed_validators": executed,
            "recommended_but_unavailable_validators": selection["recommended_but_unavailable"],
            "core_observation_count": int(core.get("core_observation_count", core.get("count", 0)) or 0),
            "true_graph_conflict_count": int(conflict.get("true_graph_conflict_count", 0) or 0),
            "formal_hypothesis_count": int(hypothesis.get("hypothesis_count", 0) or 0),
            "lincs_interpretation": max(lincs.get("interpretation_distribution", {"unavailable": 0}), key=lincs.get("interpretation_distribution", {"unavailable": 0}).get),
            "ready_for_system_b": ready,
            "readiness_warnings": [] if ready else ["required_case_bundle_artifacts_or_executed_validator_missing"],
        }
        (artifacts / "case_bundle_manifest.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    rebuild_metadata = {"enabled": True, "source_run_id": source.name,
                        "rebuilt_run_id": output.name, "rebuild_stages": list(stages)}
    for name in ("graph_conflict_summary.json", "merged_evidence_graph_summary.json", "hypothesis_summary.json"):
        path = artifacts / name
        if path.exists():
            payload = load(path)
            payload.update(run_id=output.name, source_run_id=source.name, rebuilt_run_id=output.name,
                           artifact_rebuild=rebuild_metadata,
                           artifact_run_id_semantics="run_id_is_current_rebuilt_run")
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if state_path.exists():
        state = load(state_path)
        state.setdefault("summary", {})["rebuild_from_run"] = provenance["rebuild_from_run"]
        state["summary"]["runtime_provenance"] = provenance
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        if "report" in stages:
            from code_engine.workflow.reports import render_run_report
            from code_engine.workflow.run_state import load_run_state
            rebuilt_state = load_run_state(output)
            render_run_report(rebuilt_state, output)
            render_run_report(rebuilt_state, output, final=True)
    return output


__all__ = ["rebuild_graph_hypothesis"]
