"""Run-scoped, artifact-grounded hypothesis formation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from code_engine.hypothesis.candidate_builder import build_hypothesis_candidates_from_run_artifacts
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.hypothesis.io import iter_jsonl, write_json
from code_engine.hypothesis.reasoning import build_reasoning_record
from code_engine.hypothesis.scoring import score_hypothesis_candidate
from code_engine.hypothesis.validation_requirements import build_validation_requirements_for_hypothesis


def run_legacy_search() -> None:
    """Explicit opt-in compatibility entry; never called by run-scoped workflow."""
    from src.pipelines.stage6_l4_beam_search import execute_l4_search_pipeline
    execute_l4_search_pipeline()


def _artifact_dir(run_dir: Path) -> Path:
    return run_dir if run_dir.name == "artifacts" else run_dir / "artifacts"


def _json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_observations(artifacts: Path) -> Iterable[dict]:
    for name in ("l2_fulltext_observations.jsonl", "l2_abstract_observations.jsonl"):
        yield from iter_jsonl(artifacts / name)
    for name in ("l2_fulltext_observations.json", "l2_abstract_observations.json", "l2_observations.json"):
        payload = _json(artifacts / name, [])
        if isinstance(payload, list):
            yield from (item for item in payload if isinstance(item, dict))


def run_hypothesis_search_for_run(
    conflict_graph: dict | None,
    mechanism_graph: dict | None,
    domain_profile: dict | None,
    run_dir: Path,
    dry_run: bool = True,
    max_hypotheses: int | None = None,
) -> dict:
    """Build and persist bounded hypotheses using only artifacts under ``run_dir``."""

    artifacts = _artifact_dir(Path(run_dir))
    artifacts.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    mechanism = mechanism_graph or _json(artifacts / "mechanism_graph.json", {})
    legacy = conflict_graph or _json(artifacts / "conflict_graph_summary.json", {})
    paths = {
        "confirmations": artifacts / "fulltext_conflict_confirmation.jsonl",
        "abstract": artifacts / "abstract_conflict_candidates.jsonl",
        "focus": artifacts / "conflict_focus_set.jsonl",
    }
    fulltext_summary = _json(artifacts / "fulltext_conflict_summary.json", {})
    for label, path in paths.items():
        if not path.exists():
            warnings.append(f"missing_optional_hypothesis_input:{label}")
    has_input = any(path.exists() and path.stat().st_size for path in paths.values()) or bool(mechanism.get("edges") or mechanism.get("paths")) or bool(legacy.get("conflict_edges"))
    maximum = 50 if max_hypotheses is None else max(0, int(max_hypotheses))
    source_default = "dry_run_artifact_based" if dry_run else "run_artifact_based"
    candidates_path = artifacts / "hypothesis_candidates.jsonl"
    hyperedges_path = artifacts / "hypothesis_hyperedges.jsonl"
    reasoning_path = artifacts / "hypothesis_reasoning_records.jsonl"
    requirements_path = artifacts / "hypothesis_validation_requirements.jsonl"

    candidate_count = hypothesis_count = 0
    high_confidence = abstract_only = fulltext = mechanism_count = manual = 0
    source_modes: Counter[str] = Counter()
    types: Counter[str] = Counter()
    top: list[dict] = []
    with candidates_path.open("w", encoding="utf-8") as candidate_handle, hyperedges_path.open("w", encoding="utf-8") as edge_handle, reasoning_path.open("w", encoding="utf-8") as reasoning_handle, requirements_path.open("w", encoding="utf-8") as requirement_handle:
        generated = build_hypothesis_candidates_from_run_artifacts(
            mechanism,
            iter_jsonl(paths["confirmations"]), iter_jsonl(paths["abstract"]), iter_jsonl(paths["focus"]),
            iter(legacy.get("conflict_edges", []) or []), _iter_observations(artifacts), maximum,
        )
        for candidate in generated:
            candidate["artifact_source_mode"] = candidate.get("source_mode")
            if dry_run:
                candidate["source_mode"] = source_default
            else:
                candidate.setdefault("source_mode", source_default)
            candidate["formation_mode"] = source_default
            requirements = build_validation_requirements_for_hypothesis(candidate)
            candidate["validation_requirements"] = requirements
            scored = score_hypothesis_candidate(candidate)
            hypothesis_id = "H_" + str(scored["candidate_id"]).removeprefix("HC_")
            scored["hypothesis_id"] = hypothesis_id
            for requirement in requirements:
                requirement["hypothesis_id"] = hypothesis_id
            candidate_handle.write(json.dumps(scored, ensure_ascii=False, sort_keys=True) + "\n")
            candidate_count += 1
            edge = build_hypothesis_hyperedge(scored, seed_query=str((domain_profile or {}).get("seed_query") or ""))
            edge_payload = edge.model_dump(mode="json")
            edge_handle.write(json.dumps(edge_payload, ensure_ascii=False, sort_keys=True) + "\n")
            reasoning_handle.write(build_reasoning_record(edge).model_dump_json() + "\n")
            for requirement in requirements:
                requirement_handle.write(json.dumps(requirement, ensure_ascii=False, sort_keys=True) + "\n")
            hypothesis_count += 1
            high_confidence += int(bool(edge_payload.get("high_confidence", scored.get("high_confidence"))))
            abstract_only += int(edge.source_scope == "abstract")
            fulltext += int(edge.source_scope == "full_text")
            mechanism_count += int(bool(edge.linked_mechanism_edge_ids or edge.linked_mechanism_path_ids) or edge.source_scope == "mechanism")
            manual += int(edge.requires_manual_review)
            source_modes[edge.source_mode] += 1
            types[edge.hypothesis_type] += 1
            top.append({"hypothesis_id": edge.hypothesis_id, "hypothesis_type": edge.hypothesis_type, "hypothesis_text": edge.hypothesis_text, "overall_score": edge.overall_score})

    top.sort(key=lambda item: (-item["overall_score"], item["hypothesis_id"]))
    status = "completed" if hypothesis_count else ("no_input" if not has_input else "insufficient_input")
    reason = None if hypothesis_count else ("no_hypothesis_inputs_in_run" if not has_input else "available_inputs_did_not_form_candidates")
    if reason:
        warnings.append(reason)
    summary = {
        "status": status, "reason": reason, "hypothesis_candidate_count": candidate_count,
        "hypothesis_count": hypothesis_count, "hypothesis_high_confidence_count": high_confidence,
        "hypothesis_abstract_only_count": abstract_only, "hypothesis_fulltext_grounded_count": fulltext,
        "hypothesis_mechanism_grounded_count": mechanism_count,
        "hypothesis_requires_manual_review_count": manual,
        "hypothesis_source_mode_counts": dict(source_modes), "hypothesis_type_counts": dict(types),
        "hypothesis_artifact_count": 5, "top_hypotheses": top[:10],
        "mechanism_graph_used": bool(mechanism), "conflict_graph_available": bool(legacy),
        "domain_id": (domain_profile or {}).get("domain_id"), "max_hypotheses": maximum,
        "fulltext_conflict_summary_available": bool(fulltext_summary),
        "formation_mode": source_default, "run_dir": str(run_dir), "warnings": list(dict.fromkeys(warnings)),
    }
    write_json(artifacts / "hypothesis_summary.json", summary)
    return summary


__all__ = ["run_hypothesis_search_for_run", "run_legacy_search"]
