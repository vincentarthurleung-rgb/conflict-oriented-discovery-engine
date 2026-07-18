"""Offline formal/core graph backfill from existing L2 artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl
from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.reporting.whitebox_case import generate_whitebox_case_artifacts


def _json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    if path.suffix == ".json":
        value = _json(path, [])
        return value if isinstance(value, list) else []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _formal_row(item: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "subject_canonical_id": gate["subject_effective_canonical_id"],
        "subject_canonical_name": gate["subject_effective_canonical_name"] or item.get("subject_canonical_name"),
        "object_canonical_id": gate["object_effective_canonical_id"],
        "object_canonical_name": gate["object_effective_canonical_name"] or item.get("object_canonical_name"),
        "relation_raw": item.get("relation_raw"),
        "relation_normalized": item.get("relation_raw") or item.get("relation_family"),
        "formal_relation": gate["formal_relation"],
        "relation_family": gate["relation_family"],
        "measurement_dimension": gate["measurement_dimension"],
        "relation_sign": gate["sign"],
        "formal_core_graph_eligible": True,
        "conflict_eligible": bool(gate["conflict_eligible"]),
        "conflict_reasoning_eligible": True,
        "graph_layer": "core_canonical_graph",
        "canonical_graph_eligible": True,
        "allow_high_confidence_graph_use": True,
        "exclude_from_high_confidence_conflict": False,
        "excluded_from_core_reason": None,
        "core_gate": gate,
    }


def backfill_run(run_dir: str | Path) -> dict[str, Any]:
    run = Path(run_dir)
    artifacts = run / "artifacts"
    observations = _rows(artifacts / "l2_abstract_observations.json")
    retained_ids = {str(row.get("observation_id") or row.get("triple_id") or row.get("claim_id")) for row in _rows(artifacts / "l2_retained_observations.jsonl")}
    graph_ids = {str(row.get("observation_id") or row.get("triple_id") or row.get("claim_id")) for row in _rows(artifacts / "l2_graph_observations.jsonl")}
    audit = []
    formal = []
    for item in observations:
        obs_id = str(item.get("observation_id") or item.get("triple_id") or item.get("claim_id"))
        value = {**item}
        value["graph_observation_eligible"] = bool(value.get("graph_observation_eligible") or obs_id in graph_ids)
        gate = core_graph_eligibility(value)
        audit.append({"observation_id": obs_id, "paper_id": item.get("paper_id"), "retained": obs_id in retained_ids, **gate})
        if obs_id in retained_ids and gate["eligible"]:
            formal.append(_formal_row(value, gate))
    atomic_write_jsonl(artifacts / "core_graph_gate_audit.jsonl", audit)
    atomic_write_jsonl(artifacts / "l2_core_graph_observations.jsonl", formal)
    graph_result = build_merged_evidence_graph_from_run_artifacts(run, include_fulltext=False, include_hypotheses=True)
    generate_whitebox_case_artifacts(run)
    conflicts = _rows(artifacts / "graph_conflict_candidates.jsonl")
    hypothesis = _json(artifacts / "hypothesis_summary.json", {}) or {}
    summary = {
        "schema_version": "formal_graph_backfill_v1",
        "run_dir": str(run),
        "case_id": (_json(artifacts / "case_domain_profile.json", {}) or {}).get("case_id"),
        "l2_retained_observations": len(retained_ids),
        "reviewable_graph_observations": len(_rows(artifacts / "l2_reviewable_graph_observations.jsonl")),
        "graph_observations": len(_rows(artifacts / "l2_graph_observations.jsonl")),
        "formal_core_observations": len(formal),
        "conflict_eligible_observations": sum(bool(row.get("conflict_eligible")) for row in formal),
        "true_conflicts": sum(bool(row.get("is_true_graph_conflict")) for row in conflicts),
        "formal_hypotheses": int(hypothesis.get("formal_hypothesis_count", 0) or 0),
        "core_exclusion_reason_distribution": dict(Counter(row["reason"] for row in audit if row["reason"] != "eligible_and_emitted")),
        "engineering_propagation_failures": {
            "endpoint_decision_join_failure": 0,
            "decision_to_observation_failure": 0,
            "observation_to_graph_failure": int((graph_result.get("contract_report") or {}).get("observation_to_graph_propagation_failures", 0) or 0),
        },
        "atlas_sync_status": "pending",
        "atlas_activation_status": "not_active",
        "atlas_sync_error": None,
        "current_run_calls": {
            "abstract_l1_provider_calls": 0,
            "abstract_retrieval_http_calls": 0,
            "entity_provider_network_calls": 0,
            "l2_entity_llm_cleaner_calls": 0,
        },
    }
    atomic_write_json(artifacts / "formal_graph_backfill_summary.json", summary)
    return summary


def publish_and_sync_run(run_dir: str | Path, *, runs_root: str | Path, output_root: str | Path,
                         dry_run: bool = False, no_database_write: bool = True) -> dict[str, Any]:
    from code_engine.integration.atlas_handoff import ABSTRACT_L2_PROFILE
    from code_engine.integration.atlas_publish import publish_completed_scientific_run
    run = Path(run_dir)
    summary = backfill_run(run)
    if dry_run:
        return {**summary, "handoff_status": "would_publish", "sync_status": "dry_run", "activation_status": "not_active"}
    publication = publish_completed_scientific_run(
        run,
        atlas_config={"runs_root": runs_root, "output_root": output_root, "no_database_write": no_database_write},
        publication_source="backfill_formal_graph",
    )
    result = {
        **summary,
        **publication,
        "handoff_profile": publication.get("handoff_profile") or ABSTRACT_L2_PROFILE,
        "sync_status": publication.get("sync_status") or publication.get("atlas_sync_status"),
        "activation_status": publication.get("atlas_activation_status"),
        "atlas_sync_error": None if publication.get("atlas_sync_status") in {"completed", "no_op"} else publication.get("error"),
        "idempotency_status": "no_op" if publication.get("sync_status") == "no_op" else "created_or_refreshed",
        "review_preservation_status": "preserved_no_database_write_no_review_root_mutation" if no_database_write else "preserved_projection_activation_only",
    }
    manifest_path = run / "artifacts" / "replay_manifest.json"
    replay = _json(manifest_path, {}) or {}
    replay.update({
        "scientific_status": "completed",
        "handoff_status": result.get("handoff_status"),
        "handoff_profile": result.get("handoff_profile"),
        "handoff_manifest": result.get("handoff_manifest"),
        "atlas_sync_status": result.get("atlas_sync_status"),
        "atlas_activation_status": result.get("atlas_activation_status"),
        "projection_id": result["projection_id"],
        "previous_projection_id": result["previous_projection_id"],
        "atlas_sync_error": result.get("atlas_sync_error"),
        "exit_code": 0,
    })
    atomic_write_json(manifest_path, replay)
    atomic_write_json(run / "artifacts" / "abstract_l2_handoff_sync_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--publish-handoff", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--output-root", type=Path, default=Path("system_b_outputs/system_a_sync"))
    parser.add_argument("--database-write", action="store_true")
    args = parser.parse_args(argv)
    summaries = [
        publish_and_sync_run(run, runs_root=args.runs_root, output_root=args.output_root, dry_run=args.dry_run, no_database_write=not args.database_write)
        if args.publish_handoff or args.sync else backfill_run(run)
        for run in args.runs
    ]
    if args.report_json:
        atomic_write_json(args.report_json, {"schema_version": "formal_graph_cross_case_audit_v1", "cases": summaries})
    print(json.dumps({"cases": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
