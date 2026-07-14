"""Deterministic projection of fulltext re-entry v5 evidence into Atlas views."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from code_engine.integration.atlas_handoff import LANE_FILES, canonical_json, resolve_artifact
from code_engine.system_b.explorer.dossier_projection import dossier_id_for

ADAPTER_VERSION = "fulltext_reentry_v5_adapter_v1"
CONTEXT_ALIASES = {
    "species": ("species",),
    "cell_type": ("cell_type", "cell_line"),
    "tissue": ("tissue",),
    "disease_subtype": ("disease_subtype", "disease_or_cancer_type", "cancer_type", "disease"),
    "treatment": ("treatment", "intervention"),
    "dose": ("dose",),
    "duration": ("duration", "treatment_duration", "time"),
    "genotype": ("genotype",),
    "localization": ("localization",),
    "assay_method": ("assay_method", "assay_or_readout", "assay"),
    "outcome_definition": ("outcome_definition", "outcome"),
    "measured_endpoint": ("measured_endpoint", "outcome_definition", "outcome"),
    "intervention_type": ("intervention_type", "treatment", "intervention"),
    "intervention_target": ("intervention_target",),
    "control_group": ("control_group",),
    "model_system": ("model_system",),
    "validation_design": ("validation_design",),
    "reasoning_trace_status": ("reasoning_trace_status", "trace_status"),
    "disease_stage": ("disease_stage", "stage"),
}
FORBIDDEN_GRAPH_RELATIONS = {"expression_state", "association", "comparison", "no_effect"}


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _value(row: dict, *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _entity(row: dict, side: str) -> tuple[str | None, str | None, str | None]:
    label = _value(row, f"{side}_canonical_name", f"normalized_{side}", side, f"{side}_raw")
    source_id = _value(row, f"{side}_canonical_id")
    if not label:
        return None, None, None
    entity_id = str(source_id) if source_id else "src_" + hashlib.sha1(str(label).casefold().encode()).hexdigest()[:18]
    return entity_id, str(label), _value(row, f"{side}_entity_type", f"{side}_type")


def _relation(row: dict) -> str | None:
    value = _value(row, "predicate", "relation", "relation_raw")
    return str(value).strip().casefold().replace(" ", "_") if value else None


def _paper_title(row: dict) -> Any:
    return _value(row, "paper_title", "title")


def _context(row: dict) -> dict[str, Any]:
    raw = row.get("context") if isinstance(row.get("context"), dict) else {}
    slots = row.get("context_slots") if isinstance(row.get("context_slots"), dict) else {}
    merged = {**slots, **raw}
    result = {}
    for target, aliases in CONTEXT_ALIASES.items():
        value = _value(merged, *aliases)
        result[target] = value if value not in (None, "") else None
    return result


def _optional_jsonl(validated: dict[str, Any], logical_name: str) -> list[dict[str, Any]]:
    manifest = validated["manifest"]
    spec = manifest.get("artifacts", {}).get(logical_name)
    if not spec:
        return []
    path = resolve_artifact(Path(validated["run_dir"]), spec["relative_path"])
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _first_context_value(values: Any) -> Any:
    if isinstance(values, list):
        if not values:
            return None
        first = values[0]
        return first.get("value") if isinstance(first, dict) and "value" in first else first
    if isinstance(values, dict) and "value" in values:
        return values.get("value")
    return values


def _reasoning_context_for(claim_id: Any, consolidations: dict[str, dict[str, Any]], traces: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cons = consolidations.get(str(claim_id)) or {}
    trace = traces.get(str(claim_id)) or {}
    consolidated = cons.get("consolidated_context") if isinstance(cons.get("consolidated_context"), dict) else {}
    row = {key: _first_context_value(value) for key, value in consolidated.items()}
    row["reasoning_trace_status"] = trace.get("trace_status") or cons.get("trace_status")
    row["reasoning_trace_id"] = trace.get("reasoning_trace_id") or cons.get("reasoning_trace_id")
    row["reasoning_strength_profile"] = trace.get("strength_profile") or cons.get("strength_profile") or {}
    row["field_provenance"] = cons.get("field_provenance") or {}
    row["linked_chain_ids"] = cons.get("linked_chain_ids") or []
    return {key: value for key, value in row.items() if value not in (None, "", [], {})}


def _provenance(row: dict, *, case_id: str, source_run_id: str, logical_name: str, artifact_hash: str, index: int) -> dict:
    return {
        "case_id": case_id,
        "claim_id": row.get("claim_id"),
        "pmid": row.get("pmid"),
        "pmcid": row.get("pmcid"),
        "paper_title": _paper_title(row),
        "doi": row.get("doi"),
        "section_type": row.get("section_type"),
        "section_title": row.get("section_title"),
        "chunk_id": row.get("chunk_id"),
        "source_run_id": source_run_id,
        "source_artifact": logical_name,
        "source_record_index": index,
        "source_record_hash": _canonical_hash(row),
        "source_artifact_hash": artifact_hash,
    }


def _graph_eligible(row: dict) -> bool:
    lane = row.get("evidence_lane")
    allowed_lane = lane in {"core_seed_relation", "seed_neighborhood_mechanism"} or row.get("exploratory_graph_eligible") is True
    relation_class = str(row.get("relation_class") or "").casefold()
    if not allowed_lane or relation_class in FORBIDDEN_GRAPH_RELATIONS:
        return False
    if row.get("polarity_resolution_status") == "mismatch" or row.get("subject_is_composite") is True or row.get("object_is_composite") is True:
        return False
    subject_id, subject, _ = _entity(row, "subject")
    object_id, obj, _ = _entity(row, "object")
    return bool(subject_id and subject and object_id and obj and _relation(row))


class FulltextReentryV5Adapter:
    version = ADAPTER_VERSION

    def project(self, validated: dict[str, Any], *, prediction_run_id: str) -> dict[str, Any]:
        manifest = validated["manifest"]
        run = Path(validated["run_dir"])
        case_id = manifest["case_id"]
        source_run_id = manifest["source_run_id"]
        reasoning_traces = {str(row.get("claim_id")): row for row in _optional_jsonl(validated, "fulltext_reasoning_traces")}
        consolidations = {str(row.get("claim_id")): row for row in _optional_jsonl(validated, "fulltext_context_consolidations")}
        chains = {str(row.get("chain_id")): row for row in _optional_jsonl(validated, "experimental_evidence_chains")}
        links_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for link in _optional_jsonl(validated, "claim_evidence_links"):
            links_by_claim[str(link.get("claim_id"))].append(link)
        records = []
        for lane, relative in LANE_FILES.items():
            spec = manifest["artifacts"][f"lane_{lane}"]
            path = resolve_artifact(run, relative)
            with path.open(encoding="utf-8") as handle:
                for index, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("evidence_lane") != lane:
                        raise ValueError(f"lane mismatch in {relative}:{index}")
                    records.append((row, f"lane_{lane}", spec["sha256"], index))

        dossier_evidence = []
        dossier_groups: dict[str, dict[str, Any]] = {}
        context_rows = []
        graph_records = []
        conflict_predictions = []
        claim_candidates = []
        context_candidates = []
        for row, logical_name, artifact_hash, index in records:
            subject_id, subject, subject_type = _entity(row, "subject")
            object_id, obj, object_type = _entity(row, "object")
            relation = _relation(row)
            triple_shape = {"subject_id": subject_id or str(row.get("subject") or ""), "relation_normalized": relation or "", "object_id": object_id or str(row.get("object") or ""), "direction": row.get("direction")}
            dossier_id = dossier_id_for(triple_shape)
            provenance = _provenance(row, case_id=case_id, source_run_id=source_run_id, logical_name=logical_name, artifact_hash=artifact_hash, index=index)
            reasoning_context = _reasoning_context_for(row.get("claim_id"), consolidations, reasoning_traces)
            linked_links = links_by_claim.get(str(row.get("claim_id")), [])
            linked_chains = []
            for link in linked_links:
                chain = chains.get(str(link.get("chain_id")))
                if chain:
                    linked_chains.append({"link": link, "chain": chain})
            combined_context = {**_context(row), **reasoning_context}
            evidence = {
                **provenance,
                "dossier_id": dossier_id,
                "triple_id": f"dossier:{dossier_id}",
                "evidence_lane": row.get("evidence_lane"),
                "relation_class": row.get("relation_class"),
                "seed_distance": row.get("seed_distance"),
                "exploratory_graph_eligible": row.get("exploratory_graph_eligible"),
                "exploratory_retention_reason": row.get("exploratory_retention_reason"),
                "conflict_eligible": row.get("conflict_eligible"),
                "polarity_resolution_status": row.get("polarity_resolution_status"),
                "evidence_origin": row.get("evidence_origin"),
                "abstract_duplicate_status": row.get("abstract_duplicate_status"),
                "independent_fulltext_body_evidence": row.get("independent_fulltext_body_evidence"),
                "abstract_section_reextraction": row.get("abstract_section_reextraction"),
                "core_gate_passed": row.get("core_gate_passed"),
                "core_gate_failures": row.get("core_gate_failures"),
                "claim_identity_hash": row.get("claim_identity_hash"),
                "duplicate_match_basis": row.get("duplicate_match_basis"),
                "dedup_action": row.get("dedup_action"),
                "evidence_sentence": row.get("evidence_sentence"),
                "subject": subject,
                "relation": relation,
                "object": obj,
                "context": combined_context,
                "reasoning_trace": reasoning_traces.get(str(row.get("claim_id"))),
                "evidence_chains": linked_chains,
                "evidence_chain_status": "available" if linked_chains else "unavailable",
                "evidence_chain_missing_message": None if linked_chains else "Experimental evidence chain not available for this historical run.",
                "source_scope": row.get("source_scope"),
                "direction": row.get("direction"),
            }
            dossier_evidence.append(evidence)
            group = dossier_groups.setdefault(dossier_id, {
                **triple_shape,
                "triple_id": f"dossier:{dossier_id}",
                "subject_display_label": subject or row.get("subject"),
                "object_display_label": obj or row.get("object"),
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
            group["fulltext_evidence_count"] += 1
            group["display_priority_score_v2"] = group["evidence_count"]
            context = {**provenance, "dossier_id": dossier_id, "evidence_lane": row.get("evidence_lane"), **combined_context}
            context_rows.append(context)
            source_key_material = [prediction_run_id, case_id, artifact_hash, row.get("claim_id") or provenance["source_record_hash"]]
            claim_key = _canonical_hash(source_key_material + ["claim_review_v1", "1"])
            claim_candidates.append({"source_key": claim_key, "schema_id": "claim_review_v1", "schema_version": "1", "prediction_run_id": prediction_run_id, "case_id": case_id, "dossier_id": dossier_id, "claim_id": row.get("claim_id"), "source_artifact_hash": artifact_hash, "payload": evidence})
            context_key = _canonical_hash(source_key_material + ["context_attribution_v1", "1"])
            context_candidates.append({"source_key": context_key, "schema_id": "context_attribution_v1", "schema_version": "1", "prediction_run_id": prediction_run_id, "case_id": case_id, "dossier_id": dossier_id, "claim_id": row.get("claim_id"), "source_artifact_hash": artifact_hash, "payload": context})
            if _graph_eligible(row):
                graph_evidence = {key: value for key, value in evidence.items() if key != "reasoning_trace"}
                graph_records.append({**graph_evidence, "subject_id": subject_id, "subject_entity_type": subject_type, "object_id": object_id, "object_entity_type": object_type, "prediction_run_id": prediction_run_id, "edge_scope": "formal" if row.get("conflict_eligible") is True else "exploratory"})
            if row.get("conflict_eligible") is True:
                conflict_evidence = {key: value for key, value in evidence.items() if key != "reasoning_trace"}
                conflict_predictions.append({**conflict_evidence, "prediction_run_id": prediction_run_id, "edge_scope": "formal"})

        exploratory, display = self._display_projection(graph_records, prediction_run_id)
        dossier_index = {"items": sorted(dossier_groups.values(), key=lambda row: row["triple_id"]), "dossier_count": len(dossier_groups)}
        return {
            "dossier_evidence": sorted(dossier_evidence, key=lambda row: (row["dossier_id"], row["source_record_hash"])),
            "dossier_index": dossier_index,
            "context_rows": sorted(context_rows, key=lambda row: (row["dossier_id"], row["source_record_hash"])),
            "exploratory_triples": exploratory,
            "conflict_predictions": sorted(conflict_predictions, key=lambda row: row["source_record_hash"]),
            "claim_review_candidates": sorted({row["source_key"]: row for row in claim_candidates}.values(), key=lambda row: row["source_key"]),
            "conflict_pair_candidates": [],
            "context_candidates": sorted({row["source_key"]: row for row in context_candidates}.values(), key=lambda row: row["source_key"]),
            "display": display,
        }

    def _display_projection(self, rows: list[dict], prediction_run_id: str) -> tuple[list[dict], dict[str, list[dict]]]:
        grouped: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[(row["subject_id"], row["relation"], row["object_id"])].append(row)
        entities = {}
        triples = []
        evidence_links = []
        contexts = []
        exploratory = []
        for key, evidence in sorted(grouped.items()):
            first = evidence[0]
            raw = "|".join(key)
            triple_id = "sync_tr_" + hashlib.sha1(raw.encode()).hexdigest()[:20]
            for side in ("subject", "object"):
                entity_id = first[f"{side}_id"]
                entities[entity_id] = {"entity_id": entity_id, "display_label": first[side], "label": first[side], "entity_type": first.get(f"{side}_entity_type") or "unknown", "source_case_ids": sorted({row["case_id"] for row in evidence}), "degree": 0, "evidence_count": len(evidence), "display_priority_score": len(evidence)}
            entities[first["subject_id"]]["degree"] += 1
            entities[first["object_id"]]["degree"] += 1
            dossier_ids = sorted({row["dossier_id"] for row in evidence})
            triple = {"triple_id": triple_id, "subject_id": first["subject_id"], "subject_display_label": first["subject"], "relation_normalized": first["relation"], "object_id": first["object_id"], "object_display_label": first["object"], "direction": first.get("direction"), "prediction_run_id": prediction_run_id, "evidence_lane": sorted({str(row.get("evidence_lane")) for row in evidence}), "edge_scope": "formal" if any(row.get("conflict_eligible") for row in evidence) else "exploratory", "exploratory_graph_eligible": any(row.get("exploratory_graph_eligible") for row in evidence), "conflict_eligible": any(row.get("conflict_eligible") for row in evidence), "evidence_count": len(evidence), "fulltext_evidence_count": len(evidence), "related_dossier_ids": dossier_ids, "case_ids": sorted({row["case_id"] for row in evidence}), "display_priority_score_v2": len(evidence)}
            triples.append(triple)
            exploratory.append({**triple, "supporting_evidence_count": len(evidence), "case_coverage": len(triple["case_ids"])})
            for row in evidence:
                evidence_links.append({**row, "triple_id": triple_id})
                contexts.append({"triple_id": triple_id, "case_id": row["case_id"], "pmid": row.get("pmid"), "pmcid": row.get("pmcid"), "paper_title": row.get("paper_title"), "evidence_sentence": row.get("evidence_sentence"), **row.get("context", {}), **_reasoning_context_for(row.get("claim_id"), {}, {str(row.get("claim_id")): row.get("reasoning_trace") or {}}), "evidence_chains": row.get("evidence_chains") or []})
        case_focused = [{"case_id": case_id, "triple_id": triple["triple_id"]} for triple in triples for case_id in triple["case_ids"]]
        return exploratory, {"display_entities_v2": sorted(entities.values(), key=lambda row: row["entity_id"]), "display_triples_v2": triples, "display_chains_v2": [], "case_focused_triples": case_focused, "case_focused_chains": [], "triple_evidence_links": evidence_links, "triple_contexts": contexts, "validator_annotations": [], "conflict_lens_records": []}
