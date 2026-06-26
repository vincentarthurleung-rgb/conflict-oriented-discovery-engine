"""
C.O.D.E. v4.0 Stage 5 Orchestrator: L2 Ontology Alignment + L3 Conflict Discovery.

The legacy CLI entrypoint is preserved, but deterministic work is delegated to
ontology_alignment, conflict_discovery, and context_attribution modules.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Optional

from src.config.loader import DEFAULT_CONFIG_PATH, load_pipeline_config
from src.pipelines.conflict_discovery import build_conflict_graph
from src.pipelines.ontology_alignment import extract_normalized_observations, write_normalization_audit


L1_5_INPUT_DIR = "./data/processed/l1_5_refined"
L2_OUTPUT_DIR = "./data/processed/l2"
L3_OUTPUT_DIR = "./data/processed/l3"
L3_GRAPH_PATH = "./data/processed/l3/integrated_shannon_graph.json"
L3_CONFLICT_EDGES_PATH = "./data/processed/l3/conflict_edges.json"
L3_CONTEXT_ATTRIBUTION_PATH = "./data/processed/l3/context_attribution.json"
L3_REPORT_PATH = "./reports/shannon_reconciliation_report.json"
L3_SUMMARY_MD_PATH = "./reports/l3_conflict_summary.md"
L2_NORMALIZATION_AUDIT_PATH = "./data/processed/l2/entity_normalization_audit.json"


def _write_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_summary_markdown(path: str, report: dict, config_path: str, fallback_events: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# C.O.D.E. L3 Conflict Discovery Summary",
        "",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Config: `{config_path}`",
        f"- Fallback events: {len(fallback_events)}",
        f"- Total pairs evaluated: {report['total_pairs_evaluated']}",
        "",
        "## Conflict Counts",
    ]
    for key, value in report["conflict_attribution_summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Thresholds"])
    for key, value in report["thresholds"].items():
        lines.append(f"- {key}: {value}")
    if fallback_events:
        lines.extend(["", "## Fallback Audit"])
        for event in fallback_events:
            lines.append(f"- {event}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def execute_l2_l3_unified_pipeline(
    config_path: str = DEFAULT_CONFIG_PATH,
    *,
    allow_fallback: bool = False,
    strict_config: bool = True,
) -> None:
    """Load L1.5 data, normalize entities, discover conflicts, and write L3 outputs."""

    print("[C.O.D.E. v4.0 Stage 5] Starting deterministic L2/L3 orchestrator...")
    if not os.path.exists(L1_5_INPUT_DIR):
        raise FileNotFoundError(f"Source L1.5 directory missing: {L1_5_INPUT_DIR}")

    config = load_pipeline_config(
        config_path,
        allow_fallback=allow_fallback,
        strict_config=strict_config,
        required_modules=["ontology_alignment", "conflict_discovery", "context_attribution"],
    )

    observations, normalization_audit = extract_normalized_observations(
        L1_5_INPUT_DIR,
        synonym_map=config.synonym_map,
        forbidden_keywords=config.forbidden_object_keywords,
    )
    print(f"[L2] Normalized observations: {len(observations)}")
    write_normalization_audit(normalization_audit, L2_NORMALIZATION_AUDIT_PATH)

    legacy_graph, conflict_edges, context_attribution, report = build_conflict_graph(
        observations,
        latent_pool=config.latent_pool,
        thresholds=config.thresholds,
    )

    _write_json(L3_GRAPH_PATH, legacy_graph)
    _write_json(L3_CONFLICT_EDGES_PATH, {"conflict_edges": conflict_edges})
    _write_json(L3_CONTEXT_ATTRIBUTION_PATH, {"context_attributions": context_attribution})
    _write_json(
        L3_REPORT_PATH,
        {
            "report_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **report,
            "config_path": config.source_path,
            "fallback_events": config.fallback_events,
            "l2_l3_pipeline_status": "SUCCESS",
        },
    )
    _write_summary_markdown(L3_SUMMARY_MD_PATH, report, config.source_path, config.fallback_events)

    counters = report["conflict_attribution_summary"]
    print("\n[L2/L3 Reconciliation Complete] Deterministic matrix converged.")
    print(f"Uncontested Baseline Edges: {counters['Uncontested']}")
    print(f"Type I (Latent Attribution): {counters['Type I']}")
    print(f"Type II (Spatiotemporal Context): {counters['Type II']}")
    print(f"Type III (Publication Bias Filtered): {counters['Type III']}")
    print(f"Master database saved to: {L3_GRAPH_PATH}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run C.O.D.E. v4.0 L2/L3 deterministic reconciliation.")
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--allow-fallback", action="store_true", help="Allow demo fallback config and write audit.")
    parser.add_argument("--strict-config", action="store_true", default=True, help="Fail if required config is missing.")
    parser.add_argument("--no-strict-config", dest="strict_config", action="store_false")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)
    execute_l2_l3_unified_pipeline(
        config_path=args.config_path,
        allow_fallback=args.allow_fallback,
        strict_config=args.strict_config,
    )


if __name__ == "__main__":
    main()
