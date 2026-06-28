"""Run-scoped planning adapter and explicit legacy compatibility boundary."""

from pathlib import Path


def run_legacy_search() -> None:
    from src.pipelines.stage6_l4_beam_search import execute_l4_search_pipeline

    execute_l4_search_pipeline()


def run_hypothesis_search_for_run(
    conflict_graph: dict | None,
    mechanism_graph: dict | None,
    domain_profile: dict | None,
    run_dir: Path,
    dry_run: bool = True,
    max_hypotheses: int | None = None,
) -> dict:
    """Describe safe run inputs without invoking the global-path Stage6 implementation."""

    mechanism_edges = list((mechanism_graph or {}).get("edges", []))
    paths = list((mechanism_graph or {}).get("paths", []))
    conflicted = [item for item in mechanism_edges if item.get("has_conflict")]
    has_conflicts = bool((conflict_graph or {}).get("conflict_edges") or (conflict_graph or {}).get("conflict_edge_count"))
    mechanism_used = bool(mechanism_graph)
    reason = "legacy_stage6_run_scoped_callable_missing"
    return {
        "status": "planned" if dry_run else "blocked",
        "reason": reason,
        "hypothesis_count": 0,
        "mechanism_graph_used": mechanism_used,
        "conflict_graph_available": has_conflicts,
        "conflicted_mechanism_edge_count": len(conflicted),
        "candidate_mechanism_path_count": len(paths),
        "domain_id": (domain_profile or {}).get("domain_id"),
        "max_hypotheses": max_hypotheses,
        "run_dir": str(run_dir),
        "warnings": [reason, "global_path_driven_stage6_not_invoked"],
    }
