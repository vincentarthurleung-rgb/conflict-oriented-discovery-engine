"""Replay downstream stages from existing fulltext L1 claims."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_engine.fulltext.reentry import reenter_fulltext_l1_claims

FULLTEXT_REUSED_ARTIFACTS = (
    "fulltext_experiment_observations.jsonl",
    "fulltext_context_binding_audit.jsonl",
    "fulltext_l1_v2_execution_records.jsonl",
    "fulltext_l1_v2_summary.json",
    "fulltext_l1_schema_coverage.json",
    "l35_fulltext_l1_claims.jsonl",
    "l35_fulltext_l1_execution_records.jsonl",
    "l35_fulltext_discovery_selected_chunks.jsonl",
    "l35_fulltext_retrieval_results.jsonl",
    "l35_fulltext_candidate_papers.jsonl",
    "l35_fulltext_oa_candidate_papers.jsonl",
    "l35_fulltext_l1_chunks.jsonl",
    "l35_fulltext_l1_summary.json",
    "l35_fulltext_conflict_confirmation_summary.json",
    "l35_fulltext_conflict_confirmations.jsonl",
    "l35_fulltext_discovery_execution_records.jsonl",
    "fulltext_candidate_bridge_audit.jsonl",
    "pmcid_integrity_audit.jsonl",
    "fulltext_claim_passage_index.jsonl",
    "fulltext_reasoning_traces.jsonl",
    "fulltext_reasoning_trace_summary.json",
    "fulltext_reasoning_trace_warnings.jsonl",
    "experimental_evidence_chains.jsonl",
    "claim_evidence_links.jsonl",
    "experimental_evidence_chain_summary.json",
    "fulltext_context_consolidations.jsonl",
    "fulltext_context_consolidation_summary.json",
)


def _count_jsonl(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _copy_artifacts(source_artifacts: Path, target_artifacts: Path) -> list[str]:
    copied = []
    for name in FULLTEXT_REUSED_ARTIFACTS:
        src = source_artifacts / name
        if src.is_file():
            shutil.copy2(src, target_artifacts / name)
            copied.append(name)
    return copied


def run_replay(
    *,
    case_id: str,
    base_run: Path,
    fulltext_run: Path,
    output_root: Path,
    output_suffix: str,
    network: bool = False,
    api: bool = False,
    entity_network_lookup: bool = False,
    entity_llm_cleaner: bool = False,
    overwrite: bool = False,
    publish_atlas: bool = False,
    output_run: Path | None = None,
) -> dict[str, Any]:
    source = base_run.resolve()
    fulltext = fulltext_run.resolve()
    target = Path(output_run) if output_run is not None else output_root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{case_id}_{output_suffix}"
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"output run exists: {target}")
        shutil.rmtree(target)
    shutil.copytree(source, target)
    artifacts = target / "artifacts"
    fulltext_artifacts = fulltext / "artifacts"
    copied = _copy_artifacts(fulltext_artifacts, artifacts)
    claims_path = artifacts / "l35_fulltext_l1_claims.jsonl"
    source_count = _count_jsonl(claims_path)

    summary = reenter_fulltext_l1_claims(
        target,
        source_fulltext_run=fulltext,
        execute=True,
        network=network,
        api=api,
        entity_network_lookup=entity_network_lookup,
        entity_llm_cleaner=entity_llm_cleaner,
    )
    if summary.get("fulltext_l1_api_calls") != 0:
        raise RuntimeError("fulltext re-entry must not invoke fulltext L1 API calls")
    from code_engine.fulltext.evidence_projection import project_fulltext_run
    projection = project_fulltext_run(target, output_root=target.parent)
    manifest = {
        "schema_version": "fulltext_reentry_replay_manifest_v1",
        "case_id": case_id,
        "base_run": str(source),
        "fulltext_run": str(fulltext),
        "new_run": str(target.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reused_fulltext_artifacts": copied,
        "skipped_stages": ["abstract_acquisition", "abstract_l1", "pmcid_repair", "pmc_retrieval", "xml_parsing", "fulltext_l1"],
        "rerun_stages": ["fulltext_claim_level_evidence_lane_classification", "fulltext_l2_reentry", "comparability_context_screening", "fulltext_discovery_reentry", "l4_context_mining", "l5_context_attribution", "l6_mechanism_graph"],
        "network_used": bool(network),
        "api_used": bool(api),
        "entity_network_lookup_enabled": bool(entity_network_lookup),
        "entity_llm_cleaner_enabled": bool(entity_llm_cleaner),
        "fulltext_l1_reused": True,
        "fulltext_l1_api_calls": 0,
        "source_fulltext_claim_count": source_count,
        "evidence_projection_auto_triggered": True,
        "projection_run": projection.get("output_run"),
        "atlas_activated": False,
        **summary,
    }
    (target / "fulltext_reentry_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifacts / "fulltext_reentry_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pipeline = _json(artifacts / "pipeline_stage_summary.json", {})
    pipeline.update({"status": pipeline.get("status", "completed"), "fulltext_reentry": summary})
    (artifacts / "pipeline_stage_summary.json").write_text(json.dumps(pipeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if publish_atlas:
        from code_engine.integration.atlas_handoff import publish_atlas_handoff
        handoff = publish_atlas_handoff(
            target,
            runs_root=output_root,
            lineage={"base_run": source, "fulltext_l1_run": fulltext, "reentry_run": target},
        )
        manifest["atlas_handoff"] = {key: handoff[key] for key in ("status", "manifest_path", "manifest_hash")}
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay downstream evidence stages from existing fulltext L1 claims.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--base-run", type=Path, required=True)
    parser.add_argument("--fulltext-run", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument("--output-run", type=Path)
    parser.add_argument("--output-suffix", required=True)
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--entity-network-lookup", action="store_true")
    parser.add_argument("--entity-llm-cleaner", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--publish-atlas-handoff", action="store_true", help="Explicitly publish a validated handoff; default is no publication or activation.")
    args = parser.parse_args(argv)
    result = run_replay(
        case_id=args.case_id,
        base_run=args.base_run,
        fulltext_run=args.fulltext_run,
        output_root=args.output_root,
        output_suffix=args.output_suffix,
        network=args.network,
        api=args.api,
        entity_network_lookup=args.entity_network_lookup,
        entity_llm_cleaner=args.entity_llm_cleaner,
        overwrite=args.overwrite,
        publish_atlas=args.publish_atlas_handoff,
        output_run=args.output_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
