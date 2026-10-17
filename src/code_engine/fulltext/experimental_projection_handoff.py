"""Data-only V3/Core handoff; structural validation grants no graph authority."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.experimental_core.comparison_semantics import classify_comparison
from code_engine.extraction_assets.experimental_core.comparator_linkage import recover_comparator
from code_engine.extraction_assets.experimental_core.integrity import evaluate_integrity
from code_engine.extraction_assets.experimental_core.linkage import reference_audit
from code_engine.extraction_assets.experimental_core.linkage_completeness import assess_linkage_v2
from code_engine.extraction_assets.experimental_core.models import (
    ExperimentalFactorRecord, ExperimentalObservationLinkage, MeasurementRecord,
    ObservedResultRecord, StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.experimental_core.projection import build_projection
from code_engine.extraction_assets.experimental_core.readiness_v2 import evaluate_readiness_v2
from code_engine.schemas.fulltext_observation import ExperimentalObservationV3
from code_engine.normalization.experimental_admission import is_shadow_artifact

from .reentry import _fulltext_record_from_claim


def prepare_experimental_handoff(record: dict[str, Any], source: Path) -> dict[str, Any]:
    """Accept a native V3, its existing claim wrapper, or a V3/Core envelope.

    Retain exact payloads and use existing component/linkage gates. Never infer
    factors, links, entity identities, measurement categories or causal signs.
    """
    if is_shadow_artifact(record):
        raise ValueError("shadow_artifact_forbidden_in_formal_projection")
    formal = record.get("ExperimentalObservationV3") or record.get("formal_v3_native_payload")
    nested = record.get("fulltext_l1_v2_observation")
    if formal is None and isinstance(nested, dict) and nested.get("schema_version") == "fulltext_l1_experimental_observation_schema_v3":
        formal = nested
    if formal is None and record.get("schema_version") == "fulltext_l1_experimental_observation_schema_v3":
        formal = record.get("fulltext_l1_v2_observation") or record
    if formal is None:
        if record.get("adapter_mode") == "formal_v3_native" or any(k in record for k in ("ExperimentalCore", "experimental_core")):
            raise ValueError("native_experimental_payload_missing")
        return record
    ExperimentalObservationV3.model_validate(formal)
    claim = deepcopy(record)
    # Only recomputation from actual components can populate this diagnostic.
    # A caller-supplied audit is not an alternative admission path.
    claim.pop("experimental_core_handoff_audit", None)
    claim.update(schema_version=formal["schema_version"], fulltext_l1_v2_observation=deepcopy(formal))
    if any(claim.get(key) not in (None, formal["observation_id"]) for key in ("claim_id", "observation_id")):
        raise ValueError("experimental_projection_observation_identity_mismatch")
    row = _fulltext_record_from_claim(claim, source)
    core = record.get("ExperimentalCore") or record.get("experimental_core")
    if core is not None:
        row["experimental_core"] = deepcopy(core)
        row["experimental_core_handoff_audit"] = _validate_core(core, formal)
    return row


def _validate_core(core: dict[str, Any], formal: dict[str, Any]) -> dict[str, Any]:
    revision = core["revision"]
    StructuredExperimentalObservationRevision.model_validate(revision)
    if (revision["source_observation_identity"] != formal["observation_id"]
            or revision.get("source_fulltext_v3_identity") != formal["observation_id"]
            or revision.get("experiment_scope_identity") != formal["experiment"]["experiment_id"]):
        raise ValueError("experimental_core_source_binding_mismatch")
    groups = (
        ("factors", ExperimentalFactorRecord, "factor_id", "experimental_factor_ids"),
        ("measurements", MeasurementRecord, "measurement_id", "measurement_ids"),
        ("results", ObservedResultRecord, "observed_result_id", "observed_result_ids"),
        ("linkages", ExperimentalObservationLinkage, "linkage_id", "linkage_record_ids"),
    )
    all_ids = []
    evidence_ids = {s["evidence_span_id"] for s in formal["provenance"]["evidence_spans"]}
    evidence_ids.update(s["anchor_id"] for s in formal["provenance"]["evidence_spans"] if s.get("anchor_id"))
    for name, model, key, refs in groups:
        ids = [item[key] for item in core[name]]
        if sorted(ids) != sorted(revision[refs]) or len(ids) != len(set(ids)):
            raise ValueError("experimental_core_component_reference_mismatch:" + name)
        for item in core[name]:
            model.model_validate(item)
            if item["observation_revision_identity"] != revision["identity"]:
                raise ValueError("experimental_core_cross_observation_reference")
            if not set(item["evidence_anchor_ids"]) <= evidence_ids:
                raise ValueError("experimental_core_evidence_reference_mismatch")
            all_ids.append(item["identity"])
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("experimental_core_duplicate_identity")
    factors, measurements, results, links = (core[k] for k in ("factors", "measurements", "results", "linkages"))
    fids, mids, rids = ({r[key] for r in rows} for rows, key in (
        (factors, "factor_id"), (measurements, "measurement_id"), (results, "observed_result_id")))
    for result in results:
        if not set(result["comparison_factor_refs"]) <= fids or result.get("baseline_ref") not in fids | {None}:
            raise ValueError("experimental_core_comparator_reference_mismatch")
    endpoints = {
        "factor_applies_to_measurement": (fids, mids), "measurement_produces_result": (mids, rids),
        "result_compared_against_factor": (rids, fids), "result_uses_baseline": (rids, fids),
        "factor_precedes_factor": (fids, fids), "factor_cooccurs_with_factor": (fids, fids),
    }
    for link in links:
        if link["relation_type"] == "observation_belongs_to_experiment_scope":
            valid = link["source_ref"] in {revision["identity"], formal["observation_id"]} and link["target_ref"] == revision["experiment_scope_identity"]
        else:
            left, right = endpoints[link["relation_type"]]
            valid = link["source_ref"] in left and link["target_ref"] in right
        if not valid:
            raise ValueError("experimental_core_link_endpoint_mismatch")
    # The V1 audit only accepts component endpoints; scope links are checked above.
    audit = reference_audit(revision["identity"], factors, measurements, results,
                            [l for l in links if l["relation_type"] != "observation_belongs_to_experiment_scope"])
    if not audit["valid"]:
        raise ValueError("experimental_core_invalid_references")
    integrity, issues, _ = evaluate_integrity(observation_type=revision["observation_type"], factors=factors,
        measurements=measurements, results=results, links=links, reference_audit=audit)
    semantics = [classify_comparison(result, revision, formal) for result in results]
    # Empty evidence texts: consume existing comparator references, recover none.
    recoveries = [recover_comparator(result, factors, semantic, [])[1]
                  for result, semantic in zip(results, semantics)]
    linkage = assess_linkage_v2(revision, factors, measurements, results, links, semantics, recoveries)
    readiness = evaluate_readiness_v2(revision, linkage,
        [{"method_present_after": bool(m.get("method_raw") or m.get("method_extracted") or m.get("method_canonical"))} for m in measurements],
        context_available=bool(formal["experiment"]))
    return {"reference_audit": audit, "structural_integrity": integrity, "issues": issues,
            "linkage": linkage, "readiness": readiness,
            "projection": build_projection(revision, readiness_ref=readiness["identity"]),
            "scientific_authority_granted": False}


def structured_experiment_chain(row: dict[str, Any]) -> dict[str, Any]:
    """Assemble a reasoning input from preserved records, not text proximity."""
    formal = row["formal_v3_native_payload"]
    experiment, measurement, result = (formal[k] for k in ("experiment", "measurement", "observation"))
    core = row.get("experimental_core") or {}
    return {
        "chain_id": experiment["experiment_id"], "paper_id": formal["provenance"]["paper_id"],
        "causal_design": deepcopy(experiment), "interventions": deepcopy(formal["interventions"]),
        "comparators": [{"role": key, "description": experiment[key]} for key in ("comparison_arm_raw", "control_arm_raw") if experiment.get(key)],
        "measurements": deepcopy(core.get("measurements", [measurement])),
        "observed_results": deepcopy(core.get("results", [result])),
        "evidence_anchors": deepcopy(formal["provenance"]["evidence_spans"]),
        "experimental_factors": deepcopy(core.get("factors", [])),
        "experimental_linkages": deepcopy(core.get("linkages", [])),
        "experimental_core_projection": deepcopy((row.get("experimental_core_handoff_audit") or {}).get("projection")),
    }
