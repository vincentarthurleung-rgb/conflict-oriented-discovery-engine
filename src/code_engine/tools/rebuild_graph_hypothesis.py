"""Offline rebuilding of graph/hypothesis/report artifacts from an existing run."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
from code_engine.hypothesis.search import run_hypothesis_search_for_run


def rebuild_graph_hypothesis(source_run: str | Path, *, output_suffix: str = "rebuilt_graph_gate",
                             stages: tuple[str, ...] = ("graph", "hypothesis", "report")) -> Path:
    source = Path(source_run).resolve()
    if not (source / "artifacts").is_dir():
        raise FileNotFoundError(f"source run artifacts missing: {source}")
    output = source.with_name(f"{source.name}_rebuilt_{output_suffix}")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    artifacts = output / "artifacts"

    if "graph" in stages:
        build_merged_evidence_graph_from_run_artifacts(output, include_hypotheses=False)
    if "hypothesis" in stages:
        domain = json.loads((artifacts / "domain_profile.json").read_text()) if (artifacts / "domain_profile.json").exists() else {}
        mechanism = json.loads((artifacts / "mechanism_graph.json").read_text()) if (artifacts / "mechanism_graph.json").exists() else {}
        conflict = json.loads((artifacts / "conflict_graph_summary.json").read_text()) if (artifacts / "conflict_graph_summary.json").exists() else {}
        run_hypothesis_search_for_run(conflict, mechanism, domain, output, dry_run=True)
        if "graph" in stages:
            build_merged_evidence_graph_from_run_artifacts(output)

    provenance_path = artifacts / "runtime_provenance_report.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    provenance["graph_conflict_source_gate"] = {
        "enabled": True, "requires_true_opposing_polarity": True, "requires_observation_provenance": True,
        "context_specific_run": bool((provenance.get("context_aware_evidence_layering") or {}).get("context_specific_run")),
        "requires_core_context_eligible": True, "requires_strong_context_match": True,
        "requires_core_graph_layer": True, "allows_mechanism_layer_for_conflict": False,
        "allows_review_layer_for_conflict": False, "allows_cross_context_for_conflict": False,
    }
    provenance["rebuild_from_run"] = {
        "enabled": True, "source_run_dir": str(Path(source_run)), "rebuild_stages": list(stages),
        "api_calls": 0, "network_calls": 0, "source_l1_reused": True, "source_l2_reused": True,
        "rebuild_reason": "graph_conflict_source_gate_update",
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    state_path = output / "run_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        state["run_id"] = output.name
        state["api_calls_made"] = 0
        state["network_calls_made"] = 0
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
