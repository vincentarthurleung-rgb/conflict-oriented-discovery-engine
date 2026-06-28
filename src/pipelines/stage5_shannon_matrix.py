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
from code_engine.normalization.registry import LocalBiomedicalRegistry
from code_engine.normalization.resolver import ResolverCascade


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
        f"- Low-confidence observations skipped: {report.get('skipped_low_confidence_observation_count', 0)}",
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
    resolver_cascade: bool = True,
    legacy_synonym_only: bool = False,
    include_low_confidence: bool = False,
    entity_registry_path: str | None = None,
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

    if legacy_synonym_only:
        resolver_cascade = False
    resolver_mode = "legacy_synonym_only" if legacy_synonym_only else "resolver_cascade"
    resolver = None
    active_registry_path = "not_used_in_legacy_synonym_only_mode"
    if resolver_cascade:
        if entity_registry_path:
            registry = LocalBiomedicalRegistry(entity_registry_path, allow_fallback=allow_fallback)
            resolver = ResolverCascade(registry)
            active_registry_path = str(registry.path)
        else:
            resolver = ResolverCascade()
            active_registry_path = "EntityResolutionHub"
    elif not legacy_synonym_only:
        raise ValueError("Resolver cascade may only be disabled with --legacy-synonym-only")

    print(f"[L2] Resolver mode: {resolver_mode}")
    print(f"[L2] Entity registry: {active_registry_path}")

    observations, normalization_audit = extract_normalized_observations(
        L1_5_INPUT_DIR,
        synonym_map=config.synonym_map,
        forbidden_keywords=config.forbidden_object_keywords,
        resolver=resolver,
        resolver_cascade=resolver_cascade,
        legacy_synonym_only=legacy_synonym_only,
        registry_path=entity_registry_path,
    )
    resolved_observations = sum(
        obs.get("subject_normalization_status") == "resolved"
        and obs.get("object_normalization_status") == "resolved"
        for obs in observations
    )
    ambiguous_observations = sum(
        "ambiguous" in {
            obs.get("subject_normalization_status"),
            obs.get("object_normalization_status"),
        }
        for obs in observations
    )
    unresolved_observations = sum(
        "unresolved_fallback" in {
            obs.get("subject_normalization_status"),
            obs.get("object_normalization_status"),
        }
        for obs in observations
    )
    excluded_observations = sum(
        bool(obs.get("exclude_from_high_confidence_conflict")) for obs in observations
    )
    print(f"[L2] Total observations: {len(observations)}")
    print(f"[L2] Resolved observations: {resolved_observations}")
    print(f"[L2] Ambiguous observations: {ambiguous_observations}")
    print(f"[L2] Unresolved fallback observations: {unresolved_observations}")
    print(
        "[L2] Excluded low-confidence observations: "
        f"{0 if include_low_confidence else excluded_observations}"
    )
    write_normalization_audit(normalization_audit, L2_NORMALIZATION_AUDIT_PATH)

    legacy_graph, conflict_edges, context_attribution, report = build_conflict_graph(
        observations,
        latent_pool=config.latent_pool,
        thresholds=config.thresholds,
        include_low_confidence=include_low_confidence,
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
            "resolver_mode": resolver_mode,
            "entity_registry_path": active_registry_path,
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
    resolver_group = parser.add_mutually_exclusive_group()
    resolver_group.add_argument(
        "--resolver-cascade",
        dest="resolver_cascade",
        action="store_true",
        default=True,
        help="Use the type/relation-aware resolver cascade (default).",
    )
    resolver_group.add_argument(
        "--legacy-synonym-only",
        action="store_true",
        help="Explicitly use the legacy synonym-map/uppercase normalizer.",
    )
    parser.add_argument(
        "--include-low-confidence",
        action="store_true",
        help="Include unresolved/ambiguous observations in conflict statistics.",
    )
    parser.add_argument("--entity-registry-path", default=None, help="Explicit curated anchor fixture/path; no registry is loaded by default.")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)
    execute_l2_l3_unified_pipeline(
        config_path=args.config_path,
        allow_fallback=args.allow_fallback,
        strict_config=args.strict_config,
        resolver_cascade=args.resolver_cascade and not args.legacy_synonym_only,
        legacy_synonym_only=args.legacy_synonym_only,
        include_low_confidence=args.include_low_confidence,
        entity_registry_path=args.entity_registry_path,
    )


if __name__ == "__main__":
    main()
