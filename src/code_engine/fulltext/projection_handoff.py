"""Offline, non-activating Formal v3 projection handoff and Atlas staging."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl, iter_jsonl
from code_engine.fulltext.reentry import _fulltext_record_from_claim

PROFILE = "fulltext_evidence_projection"
SCHEMA = "fulltext_projection_handoff_v1"


class ProjectionHandoffError(ValueError):
    pass


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ProjectionHandoffError(f"missing projection/reentry artifact: {path}")
    return list(iter_jsonl(path))


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProjectionHandoffError(f"missing projection/reentry artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProjectionHandoffError(f"artifact must be a JSON object: {path}")
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _record_id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or row.get("claim_id") or row.get("triple_id") or "")


def stage_projection_handoff(
    *, fulltext_run: str | Path, reentry_run: str | Path, projection_run: str | Path,
    base_abstract_run: str | Path | None = None, output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Create immutable handoff/staging files; never sync or activate Atlas."""
    fulltext = Path(fulltext_run).resolve()
    reentry = Path(reentry_run).resolve()
    projection = Path(projection_run).resolve()
    base = Path(base_abstract_run).resolve() if base_abstract_run else None
    pa, ra, fa = projection / "artifacts", reentry / "artifacts", fulltext / "artifacts"

    projection_manifest = _json(projection / "projection_manifest.json")
    projected = _rows(pa / "fulltext_projected_observations.jsonl")
    edges = _rows(pa / "canonical_edge_evidence_families.jsonl")
    readjudication = _json(pa / "fulltext_l2_readjudication_summary.json")
    core_summary = _json(pa / "fulltext_core_projection_summary.json")
    if projection_manifest.get("status") != "completed" or projection_manifest.get("api_used") is not False or projection_manifest.get("network_used") is not False:
        raise ProjectionHandoffError("projection is not a completed offline artifact")
    if readjudication.get("schema_version") != "fulltext_l2_readjudication_summary_v1" or core_summary.get("schema_version") != "fulltext_core_projection_summary_v1":
        raise ProjectionHandoffError("incompatible projection schema")
    if any(int(v or 0) for v in (core_summary.get("safety_violations") or {}).values()):
        raise ProjectionHandoffError("projection safety integrity check failed")
    core = [dict(row, edge_layer="formal_projection") for row in projected if row.get("formal_core_graph_eligible") is True]
    reviewable_projection = [row for row in projected if row.get("formal_core_graph_eligible") is not True]
    if len(core) != int(core_summary.get("formal_core_observation_count", -1)) or len(edges) != int(core_summary.get("canonical_edge_count", -1)):
        raise ProjectionHandoffError("projection declared counts do not match artifacts")
    if any(not row.get("subject_canonical_id") or not row.get("object_canonical_id") for row in core):
        raise ProjectionHandoffError("formal core contains unresolved canonical endpoints")

    seed = _rows(ra / "fulltext_seed_neighborhood_observations.jsonl")
    reviewable = _rows(ra / "fulltext_reviewable_relations.jsonl")
    off_seed = _rows(ra / "fulltext_off_seed_relations.jsonl")
    context_graph_path = ra / "fulltext_context_graph_observations.jsonl"
    context_graph = list(iter_jsonl(context_graph_path)) if context_graph_path.is_file() else [
        dict(row, edge_layer="context_reentry") for row in [*seed, *reviewable, *off_seed]
        if row.get("exploratory_graph_eligible") is True
    ]
    abstract_prior = _rows(base / "artifacts/l2_graph_observations.jsonl") if base else []
    l1 = _json(fa / "fulltext_l1_v2_summary.json")
    source_claims = _rows(fa / "l35_fulltext_l1_claims.jsonl")
    adapted_claims = [_fulltext_record_from_claim(row, fulltext) for row in source_claims]
    adapted_by_id = {_record_id(row): row for row in adapted_claims}
    enriched_core = []
    for row in core:
        source_record = adapted_by_id.get(_record_id(row), {})
        enriched_core.append({
            **row,
            "source_block_id": row.get("source_block_id") or source_record.get("source_block_id"),
            "evidence_anchor_ids": row.get("evidence_anchor_ids") or source_record.get("evidence_anchor_ids") or [],
            "authoritative_evidence_spans": row.get("authoritative_evidence_spans") or source_record.get("authoritative_evidence_spans") or [],
            "interventions": row.get("interventions") or source_record.get("interventions") or [],
            "formal_v3_source_trace": {
                "observation_id": _record_id(source_record), "experiment_id": source_record.get("experiment_id"),
                "evidence_family_id": source_record.get("evidence_family_id"), "source_document_id": source_record.get("source_document_id"),
                "source_block_id": source_record.get("source_block_id"), "evidence_anchor_ids": source_record.get("evidence_anchor_ids") or [],
            },
        })
    core = enriched_core
    reentry_summary = _json(ra / "fulltext_reentry_summary.json")
    scientific_complete = l1.get("scientific_input_complete") is True and not l1.get("partial_block_failures")
    publication_allowed = bool(scientific_complete and (l1.get("consistency_report") or {}).get("publication_allowed") is True)

    identity = {
        "schema": SCHEMA, "fulltext": str(fulltext), "reentry": str(reentry),
        "projection": str(projection), "base": str(base) if base else None,
        "projection_identity": projection_manifest.get("content_identity"),
        "core_ids": [_record_id(x) for x in core], "edge_ids": [x.get("canonical_edge_id") for x in edges],
    }
    root = Path(output_root).resolve() if output_root else projection.parent
    output = root / f"{reentry.name}__fulltext_projection_handoff_{_digest(identity)[:20]}"
    out = output / "artifacts"
    previously_completed = (out / "fulltext_projection_handoff_manifest.json").is_file()
    out.mkdir(parents=True, exist_ok=True)

    context_relations = [
        *[dict(x, handoff_layer="seed_neighborhood_relation") for x in seed],
        *[dict(x, handoff_layer="reviewable_context_relation") for x in reviewable],
        *[dict(x, handoff_layer="off_seed_relation") for x in off_seed],
    ]
    seen: set[str] = set()
    mechanism_overlay = []
    for row in [*context_graph, *core]:
        key = f"{row.get('edge_layer')}:{_record_id(row)}"
        if key not in seen:
            seen.add(key)
            mechanism_overlay.append(row)

    cops8 = any(
        edge.get("subject_canonical_id") == "EntrezGene:10920"
        and edge.get("object_canonical_id") == "GO:0001837"
        and edge.get("polarity") == "positive" for edge in edges
    )
    calls = {"api_calls": 0, "network_calls": 0, "downloads": 0, "fulltext_l1_calls": 0, "entity_llm_calls": 0}
    summary = {
        "schema_version": SCHEMA, "handoff_profile": PROFILE,
        "formal_core_observation_count": len(core), "canonical_edge_count": len(edges),
        "context_relation_count": len(context_relations), "reviewable_relation_count": len(reviewable) + len(reviewable_projection),
        "off_seed_relation_count": len(off_seed), "abstract_prior_count": len(abstract_prior),
        "projection_source_recorded": True, "reentry_source_recorded": True,
        "scientific_input_complete": scientific_complete, "partial_block_failures": bool(l1.get("partial_block_failures")),
        "publication_allowed": publication_allowed, **calls,
        "projection_input_count": len(projected),
        "formal_projected_observation_count": len(projected),
        "strict_core_count": len(core), "reviewable_projection_count": len(reviewable_projection),
        "evidence_family_count": sum(len(x.get("evidence_family_ids") or []) for x in edges),
        "species_conflict_count": int(readjudication.get("species_conflicts_blocked", 0)),
        "derived_sign_correction_count": int(readjudication.get("derived_sign_corrections", 0)),
        "safety_violation_count": sum(int(v or 0) for v in (core_summary.get("safety_violations") or {}).values()),
    }
    formal_native = [x for x in adapted_claims if x.get("adapter_mode") == "formal_v3_native"]
    formal_reentry_summary = {
        "schema_version": "fulltext_formal_v3_reentry_summary_v1",
        "input_fulltext_claim_count": len(source_claims),
        "formal_v3_native_adapter_count": len(formal_native),
        "legacy_adapter_count": sum(x.get("adapter_mode") == "legacy_compatibility" for x in adapted_claims),
        "interventions_preserved_count": sum(bool(x.get("interventions")) for x in formal_native),
        "multi_intervention_preserved_count": sum(len(x.get("interventions") or []) > 1 for x in formal_native),
        "measurement_dimension_preserved_count": sum(bool(x.get("measurement_dimension")) for x in formal_native),
        "evidence_design_preserved_count": sum(bool(x.get("evidence_design")) for x in formal_native),
        "anchor_provenance_preserved_count": sum(bool(x.get("evidence_anchor_ids")) and bool(x.get("authoritative_evidence_spans")) for x in formal_native),
        "normalized_claim_count": int(reentry_summary.get("normalized_fulltext_claim_count", 0)),
        "canonical_verified_count": int(reentry_summary.get("canonical_verified_claim_count", 0)),
        "exploratory_graph_eligible_count": int(reentry_summary.get("exploratory_graph_eligible_count", 0)),
        "reviewable_count": len(reviewable), "context_relation_count": len(context_relations),
        "off_seed_count": len(off_seed), "mechanism_graph_fulltext_observation_count": len(context_graph),
        **calls,
    }
    manifest = {
        "schema_version": SCHEMA, "status": "staged_incomplete" if not scientific_complete else "staged",
        "handoff_profile": PROFILE, "formal_core_source_run": str(projection),
        "formal_core_source_profile": PROFILE, "context_lane_source_run": str(reentry),
        "projection_run": str(projection), "reentry_run": str(reentry),
        "base_abstract_run": str(base) if base else None, "fulltext_l1_run": str(fulltext),
        "authority": {"formal_fulltext_strict_core": "evidence_projection", "fulltext_context_lanes": "reentry", "abstract": "prior_only"},
        "scientific_input_complete": scientific_complete, "publication_allowed": publication_allowed,
        "fallback_used": False, "content_identity": _digest(identity),
    }
    staging = {
        "schema_version": "atlas_fulltext_projection_staging_v1", "status": "generated",
        "handoff_profile": PROFILE, "source_run": str(reentry), "projection_run": str(projection),
        "atlas_staging_generated": True, "staging_core_observation_count": len(core),
        "staging_canonical_edge_count": len(edges), "staging_contains_cops8_emt": cops8,
        "context_layer_count": len(context_relations), "reviewable_projection_count": len(reviewable_projection),
        "scientific_input_complete": scientific_complete, "publication_allowed": publication_allowed,
        "atlas_activated": False, "active_projection_unchanged": True, **calls,
    }

    atomic_write_jsonl(out / "fulltext_projection_handoff_core_observations.jsonl", core)
    atomic_write_jsonl(out / "fulltext_projection_handoff_canonical_edges.jsonl", edges)
    atomic_write_jsonl(out / "fulltext_projection_handoff_context_relations.jsonl", context_relations)
    atomic_write_jsonl(out / "fulltext_projection_handoff_reviewable_observations.jsonl", reviewable_projection)
    atomic_write_jsonl(out / "fulltext_projection_handoff_abstract_prior.jsonl", abstract_prior)
    atomic_write_jsonl(out / "fulltext_projection_mechanism_graph_overlay.jsonl", mechanism_overlay)
    atomic_write_json(out / "fulltext_formal_v3_reentry_summary.json", formal_reentry_summary)
    atomic_write_jsonl(out / "fulltext_formal_v3_reentry_audit.jsonl", ({
        "claim_id": x.get("claim_id"), "observation_id": x.get("observation_id"),
        "adapter_mode": x.get("adapter_mode"), "experiment_id": x.get("experiment_id"),
        "source_document_id": x.get("source_document_id"), "source_block_id": x.get("source_block_id"),
        "evidence_anchor_ids": x.get("evidence_anchor_ids"),
        "intervention_count": len(x.get("interventions") or []),
        "combination_mode": x.get("combination_mode"), "measurement_dimension": x.get("measurement_dimension"),
        "evidence_design": x.get("evidence_design"), "normalization_status": x.get("normalization_status"),
        "review_reasons": x.get("review_reasons"),
    } for x in adapted_claims))
    atomic_write_json(out / "fulltext_projection_handoff_manifest.json", manifest)
    atomic_write_json(out / "fulltext_projection_handoff_summary.json", summary)
    atomic_write_json(out / "atlas_fulltext_projection_staging_manifest.json", {**manifest, **staging})
    atomic_write_json(out / "atlas_fulltext_projection_staging_summary.json", staging)
    report = [
        "# Fulltext projection end-to-end report", "", f"- Profile: `{PROFILE}`",
        f"- Formal projected core: {len(core)}", f"- Canonical edges: {len(edges)}",
        f"- COPS8/CSN8 → EMT staged: {str(cops8).lower()}",
        f"- Context relations: {len(context_relations)}", f"- Mechanism overlay records: {len(mechanism_overlay)}",
        f"- Scientific input complete: {str(scientific_complete).lower()}",
        f"- Publication allowed: {str(publication_allowed).lower()}",
        "- Atlas staging generated: true", "- Atlas activated: false", "- Active projection unchanged: true",
        "- API/network/download/fulltext-L1/entity-LLM calls: 0/0/0/0/0", "",
        "The two unresolved source blocks remain publication-blocking. No source run or Atlas active pointer was modified.",
    ]
    (out / "fulltext_projection_end_to_end_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {**summary, **staging, "output_run": str(output), "reused_completed_handoff": previously_completed}


__all__ = ["PROFILE", "ProjectionHandoffError", "stage_projection_handoff"]
