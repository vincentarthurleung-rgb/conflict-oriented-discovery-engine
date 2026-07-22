"""Replay only the fulltext candidate bridge, OA retrieval, and fulltext L1 path."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from code_engine.fulltext.candidate_bridge import SOURCE_FILES


INPUT_FILES = (*SOURCE_FILES, "fulltext_escalation_plan.json")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _count_jsonl(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _resolve_source_artifacts(source_run: Path) -> Path:
    source = source_run.resolve()
    artifacts = source / "artifacts"
    if artifacts.is_dir():
        return artifacts
    if source.is_dir() and any((source / name).is_file() for name in INPUT_FILES):
        return source
    raise FileNotFoundError(f"source run has no artifacts directory with fulltext candidates: {source_run}")


def _resolve_output_run(case_id: str, *, output_run: Path | None, output_root: Path | None,
                        output_suffix: str | None, overwrite: bool) -> Path:
    if output_run is not None:
        target = output_run
    else:
        root = output_root or Path("runs")
        suffix = output_suffix or "fulltext_bridge_only"
        target = root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{case_id}_{suffix}"
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"output run exists: {target}")
        shutil.rmtree(target)
    return target


def _copy_candidate_inputs(source_artifacts: Path, target_artifacts: Path) -> list[str]:
    copied: list[str] = []
    target_artifacts.mkdir(parents=True, exist_ok=True)
    for name in INPUT_FILES:
        source = source_artifacts / name
        if source.is_file():
            shutil.copy2(source, target_artifacts / name)
            copied.append(name)
    if not copied:
        raise FileNotFoundError(
            "no fulltext candidate inputs found; expected one of: " + ", ".join(INPUT_FILES)
        )
    return copied


def replay_fulltext_bridge_from_run(
    *,
    case_id: str,
    source_run: str | Path,
    output_run: str | Path | None = None,
    output_root: str | Path | None = None,
    output_suffix: str | None = None,
    network: bool = False,
    api: bool = False,
    open_access_required: bool = True,
    overwrite: bool = False,
    max_papers: int = 20,
    max_sections_per_paper: int = 12,
    max_chunks_per_paper: int = 24,
    max_chars_per_chunk: int = 6000,
    max_total_chunks: int = 200,
    l1_read_timeout_seconds: float = 240,
    l1_max_retries: int = 1,
    fulltext_l1_max_tokens: int | None = None,
) -> dict:
    source_artifacts = _resolve_source_artifacts(Path(source_run))
    target = _resolve_output_run(
        case_id,
        output_run=Path(output_run) if output_run is not None else None,
        output_root=Path(output_root) if output_root is not None else None,
        output_suffix=output_suffix,
        overwrite=overwrite,
    )
    artifacts = target / "artifacts"
    copied = _copy_candidate_inputs(source_artifacts, artifacts)

    from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
    from code_engine.fulltext.stage import run_l35_pmc_oa_stage

    provider = os.getenv("L1_PROVIDER", "")
    model = os.getenv("MODEL_NAME", "")
    client = (
        build_l1_client_from_env_or_config(
            provider,
            model,
            read_timeout_seconds=l1_read_timeout_seconds,
            max_retries=l1_max_retries,
        )
        if api
        else None
    )
    summary = run_l35_pmc_oa_stage(
        target,
        enabled=True,
        network_enabled=network,
        api_enabled=api,
        max_papers=max_papers,
        l1_client=client,
        l1_provider=provider,
        l1_model=model,
        max_sections_per_paper=max_sections_per_paper,
        max_chunks_per_paper=max_chunks_per_paper,
        max_chars_per_chunk=max_chars_per_chunk,
        max_total_chunks=max_total_chunks,
        l1_read_timeout_seconds=l1_read_timeout_seconds,
        l1_max_retries=l1_max_retries,
        fulltext_l1_max_tokens=fulltext_l1_max_tokens,
    )

    availability_path = artifacts / "fulltext_availability_summary.json"
    availability = _read_json(availability_path)
    if availability and availability.get("open_access_required") != bool(open_access_required):
        availability["open_access_required"] = bool(open_access_required)
        availability_path.write_text(json.dumps(availability, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": "fulltext_bridge_replay_v1",
        "case_id": case_id,
        "source_run": str(Path(source_run).resolve()),
        "source_artifacts": str(source_artifacts),
        "new_run": str(target.resolve()),
        "copied_candidate_inputs": copied,
        "replayed_stages": ["fulltext_candidate_bridge", "pmcid_integrity", "pmc_oa_diagnostics", "pmc_oa_retrieval", "fulltext_l1"],
        "skipped_stages": ["l1_acquisition", "l2_entity_normalization", "abstract_conflict_screening", "discovery_lanes", "l7_validation"],
        "network_used": bool(network),
        "api_used": bool(api),
        "open_access_required": bool(open_access_required),
        "llm_used": bool(api),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": availability.get("candidate_count", 0),
        "candidate_with_pmcid_count": availability.get("candidate_with_pmcid_count", 0),
        "pmcid_conflict_count": availability.get("pmcid_conflict_count", 0),
        "retrieval_attempt_count": availability.get("retrieval_attempt_count", 0),
        "retrieval_record_count": _count_jsonl(artifacts / "l35_fulltext_retrieval_results.jsonl"),
        "skip_reason_counts": availability.get("skip_reason_counts", {}),
        "stage_summary": summary,
    }
    (target / "fulltext_bridge_replay_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (artifacts / "fulltext_bridge_replay_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = "\n".join([
        "# Fulltext Bridge-Only Replay",
        "",
        f"- Case ID: `{case_id}`",
        f"- Source run: `{Path(source_run).resolve()}`",
        f"- New run: `{target.resolve()}`",
        f"- Candidate count: {manifest['candidate_count']}",
        f"- Candidate with PMCID count: {manifest['candidate_with_pmcid_count']}",
        f"- PMCID conflict count: {manifest['pmcid_conflict_count']}",
        f"- Retrieval attempt count: {manifest['retrieval_attempt_count']}",
        f"- Skip reasons: `{json.dumps(manifest['skip_reason_counts'], sort_keys=True)}`",
        "- L2/entity replay performed: false",
        "",
    ])
    (target / "fulltext_bridge_replay_report.md").write_text(report, encoding="utf-8")
    (artifacts / "fulltext_bridge_replay_report.md").write_text(report, encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run only fulltext candidate bridge, PMC OA retrieval, and fulltext L1 from an existing run.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--source-run", required=True, type=Path)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output-run", type=Path)
    output.add_argument("--output-root", type=Path)
    parser.add_argument("--output-suffix")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--open-access-required", action="store_true", default=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fulltext-max-papers", type=int, default=20)
    parser.add_argument("--fulltext-max-sections-per-paper", type=int, default=12)
    parser.add_argument("--fulltext-max-chunks-per-paper", type=int, default=24)
    parser.add_argument("--fulltext-max-chars-per-chunk", type=int, default=6000)
    parser.add_argument("--fulltext-max-total-chunks", type=int, default=200)
    parser.add_argument("--fulltext-l1-read-timeout-seconds", type=float, default=240)
    parser.add_argument("--fulltext-l1-max-retries", type=int, default=1)
    parser.add_argument("--fulltext-l1-max-tokens", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = replay_fulltext_bridge_from_run(
        case_id=args.case_id,
        source_run=args.source_run,
        output_run=args.output_run,
        output_root=args.output_root,
        output_suffix=args.output_suffix,
        network=args.network,
        api=args.api,
        open_access_required=args.open_access_required,
        overwrite=args.overwrite,
        max_papers=args.fulltext_max_papers,
        max_sections_per_paper=args.fulltext_max_sections_per_paper,
        max_chunks_per_paper=args.fulltext_max_chunks_per_paper,
        max_chars_per_chunk=args.fulltext_max_chars_per_chunk,
        max_total_chunks=args.fulltext_max_total_chunks,
        l1_read_timeout_seconds=args.fulltext_l1_read_timeout_seconds,
        l1_max_retries=args.fulltext_l1_max_retries,
        fulltext_l1_max_tokens=args.fulltext_l1_max_tokens,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
