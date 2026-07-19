"""Deterministic Atlas projection for abstract-only L2 formal graph handoffs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from code_engine.integration.atlas_handoff import canonical_json, resolve_artifact
from code_engine.system_b.explorer.dossier_projection import dossier_id_for

ADAPTER_VERSION = "abstract_l2_projection_adapter_v1"


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _rows(validated: dict[str, Any], logical_name: str) -> list[dict[str, Any]]:
    spec = validated["manifest"].get("artifacts", {}).get(logical_name)
    if not spec:
        return []
    path = resolve_artifact(Path(validated["run_dir"]), spec["relative_path"])
    if path.suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _entity(row: dict[str, Any], side: str) -> tuple[str | None, str | None, str | None]:
    entity_id = _value(row, f"{side}_canonical_id")
    label = _value(row, f"{side}_canonical_name", f"normalized_{side}", side, f"{side}_raw")
    if not entity_id and label:
        entity_id = "src_" + hashlib.sha1(str(label).casefold().encode()).hexdigest()[:18]
    return (str(entity_id) if entity_id else None, str(label) if label else None, _value(row, f"{side}_entity_type", f"{side}_type"))


def _relation(row: dict[str, Any]) -> str:
    value = _value(row, "formal_relation", "core_projection_relation", "relation_family", "relation_raw", "predicate")
    return str(value or "unknown").strip().casefold().replace(" ", "_")


def _paper(row: dict[str, Any]) -> Any:
    return _value(row, "pmid", "paper_id", "canonical_paper_id", "doi")


class AbstractL2ProjectionAdapter:
    version = ADAPTER_VERSION

    def project(self, validated: dict[str, Any], *, prediction_run_id: str) -> dict[str, Any]:
        manifest = validated["manifest"]
        case_id = manifest["case_id"]
        source_run_id = manifest["source_run_id"]
        artifact_hash = manifest["artifacts"]["l2_core_graph_observations"]["sha256"]
        core_rows = _rows(validated, "l2_core_graph_observations")
        graph_rows = _rows(validated, "l2_graph_observations")
        seen_core = {str(_value(row, "observation_id", "claim_id", "evidence_id", "triple_id") or _canonical_hash(row)) for row in core_rows}
        display_graph_rows = [
            row for row in graph_rows
            if str(_value(row, "observation_id", "claim_id", "evidence_id", "triple_id") or _canonical_hash(row)) not in seen_core
            and row.get("available_for_display", True)
            and row.get("scientific_edge_layer") != "audit_rejected"
        ]
        evidence_rows = core_rows + display_graph_rows
        dossier_evidence = []
        context_rows = []
        claim_candidates = []
        predicted_claim_frame = []
        graph_records = []
        dossier_groups: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(evidence_rows, 1):
            subject_id, subject, subject_type = _entity(row, "subject")
            object_id, obj, object_type = _entity(row, "object")
            relation = _relation(row)
            triple_shape = {"subject_id": subject_id or str(subject or ""), "relation_normalized": relation, "object_id": object_id or str(obj or ""), "direction": row.get("direction")}
            dossier_id = dossier_id_for(triple_shape)
            source_record_hash = _canonical_hash(row)
            claim_id = str(_value(row, "claim_id", "observation_id", "triple_id", "evidence_id", "abstract_l1_claim_id") or source_record_hash[:16])
            provenance = {
                "case_id": case_id,
                "claim_id": claim_id,
                "pmid": row.get("pmid"),
                "pmcid": row.get("pmcid"),
                "paper_title": row.get("title") or row.get("paper_title"),
                "doi": row.get("doi"),
                "source_run_id": source_run_id,
                "source_artifact": "l2_core_graph_observations",
                "source_record_index": index,
                "source_record_hash": source_record_hash,
                "source_artifact_hash": artifact_hash,
            }
            context = row.get("context") if isinstance(row.get("context"), dict) else {}
            evidence = {
                **provenance,
                "dossier_id": dossier_id,
                "triple_id": f"dossier:{dossier_id}",
                "evidence_lane": "abstract_l2_core" if row in core_rows else "abstract_l2_graph",
                "scientific_edge_layer": row.get("scientific_edge_layer") or row.get("retained_layer") or ("strict_causal_core" if row in core_rows else None),
                "evidence_design": row.get("evidence_design") or (row.get("evidence_semantics") or {}).get("evidence_design"),
                "inference_type": row.get("inference_type") or (row.get("evidence_semantics") or {}).get("inference_type"),
                "direction_provenance": row.get("causal_direction_provenance") or row.get("direction_source") or (row.get("evidence_semantics") or {}).get("causal_direction_provenance"),
                "core_exclusion_reasons": row.get("core_exclusion_reasons") or (row.get("core_gate") or {}).get("reasons", []),
                "measurement_dimension": row.get("measurement_dimension") or (row.get("object_endpoint") or {}).get("measurement_dimension") or (row.get("subject_endpoint") or {}).get("measurement_dimension"),
                "measured_entity": row.get("measured_entity") or (row.get("object_endpoint") or {}).get("measured_entity_canonical_name") or (row.get("subject_endpoint") or {}).get("measured_entity_canonical_name"),
                "sample_context": row.get("sample_context") or (row.get("evidence_semantics") or {}).get("sample_context"),
                "intervention_target": row.get("intervention_target") or (row.get("evidence_semantics") or {}).get("intervention_target"),
                "intervention_type": row.get("intervention_type") or (row.get("evidence_semantics") or {}).get("intervention_type"),
                "relation_class": row.get("formal_relation_family") or row.get("relation_family"),
                "seed_distance": None,
                "exploratory_graph_eligible": bool(row.get("graph_observation_eligible", True)),
                "conflict_eligible": bool(row.get("conflict_eligible")),
                "polarity_resolution_status": "resolved" if row.get("direction") in {"positive", "negative", "increase", "decrease"} else "unknown",
                "core_gate_passed": bool(row.get("formal_core_graph_eligible", row in core_rows)),
                "core_gate_failures": (row.get("core_gate") or {}).get("reasons", []),
                "claim_identity_hash": row.get("claim_identity_hash") or source_record_hash,
                "evidence_sentence": row.get("evidence_sentence") or row.get("evidence_text"),
                "subject": subject,
                "relation": relation,
                "object": obj,
                "context": context,
                "source_scope": "abstract",
                "direction": row.get("direction"),
                "evidence_scope": "abstract_only",
                "fulltext_evidence_available": False,
            }
            dossier_evidence.append(evidence)
            group = dossier_groups.setdefault(dossier_id, {
                **triple_shape,
                "triple_id": f"dossier:{dossier_id}",
                "subject_display_label": subject,
                "object_display_label": obj,
                "subject_entity_type": subject_type,
                "object_entity_type": object_type,
                "case_ids": [],
                "evidence_count": 0,
                "fulltext_evidence_count": 0,
                "display_priority_score_v2": 0,
            })
            if case_id not in group["case_ids"]:
                group["case_ids"].append(case_id)
            group["evidence_count"] += 1
            group["display_priority_score_v2"] = group["evidence_count"]
            context_rows.append({**provenance, "dossier_id": dossier_id, "source_scope": "abstract", **context})
            source_key = _canonical_hash([prediction_run_id, case_id, source_record_hash, "claim_review_v1", "1"])
            claim_candidates.append({"source_key": source_key, "schema_id": "claim_review_v1", "schema_version": "1", "prediction_run_id": prediction_run_id, "case_id": case_id, "dossier_id": dossier_id, "claim_id": claim_id, "source_artifact_hash": artifact_hash, "payload": evidence})
            predicted_claim_frame.append({
                "schema_version": "predicted_claim_frame_v1",
                "prediction_claim_key": source_key,
                "claim_id": claim_id,
                "claim_identity_hash": row.get("claim_identity_hash") or source_record_hash,
                "source_record_hash": source_record_hash,
                "source_unit_id": None,
                "paper_id": _paper(row),
                "pmid": row.get("pmid"),
                "pmcid": row.get("pmcid"),
                "doi": row.get("doi"),
                "case_id": case_id,
                "domain_snapshot": {"domain_id": (manifest.get("domain_classification") or {}).get("primary_domain_id"), "taxonomy_version": (manifest.get("domain_classification") or {}).get("taxonomy_version")},
                "source_scope": "abstract",
                "section_type": "abstract",
                "relation_type": relation,
                "confidence_band": "medium",
                "negated": False,
                "artifact_sha256": artifact_hash,
                "projection_id": None,
                "prediction_run_id": prediction_run_id,
            })
            if subject_id and object_id and relation != "unknown":
                graph_records.append({**evidence, "subject_id": subject_id, "subject_entity_type": subject_type, "object_id": object_id, "object_entity_type": object_type, "prediction_run_id": prediction_run_id, "edge_scope": "formal" if row.get("conflict_eligible") is True else "exploratory"})
        exploratory, display = self._display_projection(graph_records, prediction_run_id)
        return {
            "dossier_evidence": sorted(dossier_evidence, key=lambda row: (row["dossier_id"], row["source_record_hash"])),
            "dossier_index": {"items": sorted(dossier_groups.values(), key=lambda row: row["triple_id"]), "dossier_count": len(dossier_groups)},
            "context_rows": sorted(context_rows, key=lambda row: (row["dossier_id"], row["source_record_hash"])),
            "exploratory_triples": exploratory,
            "conflict_predictions": [row for row in graph_records if row.get("conflict_eligible")],
            "claim_review_candidates": sorted({row["source_key"]: row for row in claim_candidates}.values(), key=lambda row: row["source_key"]),
            "conflict_pair_candidates": [],
            "context_candidates": [],
            "predicted_claim_frame": sorted({row["prediction_claim_key"]: row for row in predicted_claim_frame}.values(), key=lambda row: row["prediction_claim_key"]),
            "source_text_unit_frame": [],
            "case_metadata": {"case_id": case_id, "domain_classification": manifest.get("domain_classification") or {}, "capabilities": manifest.get("capabilities") or {}, "handoff_schema_version": manifest.get("schema_version"), "handoff_profile": manifest.get("handoff_profile"), "compatibility": manifest.get("compatibility") or {}, "manifest_hash": validated.get("manifest_hash"), "identity_hash": validated.get("identity_hash") or validated.get("manifest_hash")},
            "display": display,
        }

    def _display_projection(self, rows: list[dict[str, Any]], prediction_run_id: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[(row["subject_id"], row["relation"], row["object_id"])].append(row)
        entities: dict[str, dict[str, Any]] = {}
        triples = []
        evidence_links = []
        contexts = []
        exploratory = []
        for key, evidence in sorted(grouped.items()):
            first = evidence[0]
            triple_id = "sync_tr_" + hashlib.sha1("|".join(key).encode()).hexdigest()[:20]
            for side in ("subject", "object"):
                entity_id = first[f"{side}_id"]
                entities.setdefault(entity_id, {"entity_id": entity_id, "display_label": first[side], "label": first[side], "entity_type": first.get(f"{side}_entity_type") or "unknown", "source_case_ids": sorted({row["case_id"] for row in evidence}), "degree": 0, "evidence_count": len(evidence), "display_priority_score": len(evidence)})
            entities[first["subject_id"]]["degree"] += 1
            entities[first["object_id"]]["degree"] += 1
            triple = {"triple_id": triple_id, "subject_id": first["subject_id"], "subject_display_label": first["subject"], "relation_normalized": first["relation"], "object_id": first["object_id"], "object_display_label": first["object"], "direction": first.get("direction"), "prediction_run_id": prediction_run_id, "evidence_lane": sorted({str(row.get("evidence_lane")) for row in evidence}), "scientific_edge_layers": sorted({str(row.get("scientific_edge_layer")) for row in evidence if row.get("scientific_edge_layer")}), "evidence_designs": sorted({str(row.get("evidence_design")) for row in evidence if row.get("evidence_design")}), "inference_types": sorted({str(row.get("inference_type")) for row in evidence if row.get("inference_type")}), "direction_provenance": sorted({str(row.get("direction_provenance")) for row in evidence if row.get("direction_provenance")}), "core_exclusion_reasons": sorted({reason for row in evidence for reason in (row.get("core_exclusion_reasons") or [])}), "measurement_dimension": first.get("measurement_dimension"), "sample_context": first.get("sample_context"), "intervention_target": first.get("intervention_target"), "intervention_type": first.get("intervention_type"), "edge_scope": "formal" if any(row.get("conflict_eligible") is True for row in evidence) else "exploratory", "exploratory_graph_eligible": True, "conflict_eligible": any(row.get("conflict_eligible") is True for row in evidence), "evidence_count": len(evidence), "fulltext_evidence_count": 0, "related_dossier_ids": sorted({row["dossier_id"] for row in evidence}), "case_ids": sorted({row["case_id"] for row in evidence}), "display_priority_score_v2": len(evidence)}
            triples.append(triple)
            exploratory.append({**triple, "supporting_evidence_count": len(evidence), "case_coverage": len(triple["case_ids"])})
            for row in evidence:
                evidence_links.append({**row, "triple_id": triple_id})
                contexts.append({"triple_id": triple_id, "case_id": row["case_id"], "pmid": row.get("pmid"), "pmcid": row.get("pmcid"), "paper_title": row.get("paper_title"), "evidence_sentence": row.get("evidence_sentence"), **row.get("context", {})})
        case_focused = [{"case_id": case_id, "triple_id": triple["triple_id"]} for triple in triples for case_id in triple["case_ids"]]
        return exploratory, {"display_entities_v2": sorted(entities.values(), key=lambda row: row["entity_id"]), "display_triples_v2": triples, "display_chains_v2": [], "case_focused_triples": case_focused, "case_focused_chains": [], "triple_evidence_links": evidence_links, "triple_contexts": contexts, "validator_annotations": [], "conflict_lens_records": []}


__all__ = ["ADAPTER_VERSION", "AbstractL2ProjectionAdapter"]
