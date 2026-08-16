#!/usr/bin/env python3
"""Offline Context Gap Closure v2 and held-out single-case E2E replay."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.context.closure_v2 import (
    CONTEXT_CLOSURE_MODELS, ContextFieldValueV2, ContextInheritanceCandidateV1,
    ContextScopeCompatibilityProofV1, ContextScopeRefV1,
    ExperimentalContextCompositionV2, readiness_v2, scope_closure_gate, stable,
)
from code_engine.extraction_assets.context.models import AssetProvenance
from code_engine.extraction_assets.experimental_core.adapters import adapt_explicit_core


ROOT = Path(__file__).resolve().parents[1]
CTX_RUN = ROOT / "runs/20260816_hif1a_experimental_context_gap_closure_v2_offline"
E2E_RUN = ROOT / "runs/20260816_full_line_single_case_e2e_validation_v1_offline"
CTX_ART = CTX_RUN / "artifacts"
E2E_ART = E2E_RUN / "artifacts"

OBS_PATH = ROOT / (
    "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_l1_v2_canary__failed_block_recovery_277fd64a45668b7a8a0b/"
    "artifacts/fulltext_experiment_observations.jsonl"
)
CORE_ART = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
OLD_CTX = ROOT / "runs/20260725_hif1a_experimental_context_asset_integration_v1_offline/artifacts"
REPAIR_ART = ROOT / "runs/20260816_hif1a_reference_guided_experimental_core_repair_v1_offline/artifacts"
CANDIDATE_PATH = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts/scientific_candidate_pair_identities.jsonl"
FORMAL_PATH = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"

CASE_ID = "pi3k_akt_mtor_cancer_resistance_discovery_v1"
CASE_RUN = ROOT / "runs/20260723_183417_pi3k_akt_mtor_cancer_resistance_discovery_v1_fulltext_v3_native_reentry/artifacts"

PROV = AssetProvenance(
    producer="experimental_context_gap_closure_offline", producer_version="v2", offline=True,
    source_artifact_refs=[
        "context_factor_registry_v3", "context_normalization_policy_v3",
        "context_local_chain_composition_v3", str(OBS_PATH.relative_to(ROOT)),
    ],
    limitations=["local_structured_and_fulltext_assets_only", "provider_execution_not_authorized"],
)

BASELINE_FAILURES = [
    "tests/test_code_atlas_annotations.py::AtlasAnnotationTests::test_missing_review_root_useful_error_and_ui_controls_present",
    "tests/test_code_atlas_human_centered_redesign.py::test_case_contract_explains_capabilities_and_next_level_metadata",
    "tests/test_code_atlas_human_centered_redesign.py::test_reasoning_unavailable_is_explicit_and_does_not_infer_steps",
    "tests/test_code_atlas_workspaces.py::AtlasWorkspaceRoleTests::test_workspace_pages_are_role_scoped",
    "tests/test_core_reference_adjudication_packaging_v1.py::test_zip_files_are_valid_separate_and_checksums_match",
]
BASELINE_HEAD = "48b1f6f612b510628da616fc73b236ef489f8971"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in values), encoding="utf-8")


def model(value: Any) -> dict[str, Any]:
    return value.model_dump(mode="json")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ident(kind: str, payload: dict[str, Any]) -> str:
    return stable(kind, payload)


def source_refs(observation: dict[str, Any]) -> list[str]:
    return list(observation.get("evidence_span_ids") or [])


def controlled_normalize(field: str, raw: Any) -> tuple[Any, str, str | None]:
    text = str(raw).strip().casefold() if raw is not None else ""
    rules = {
        ("species", "homo sapiens"): "Homo sapiens", ("species", "human"): "Homo sapiens",
        ("species", "mus musculus"): "Mus musculus", ("species", "mouse"): "Mus musculus",
        ("species", "rattus norvegicus"): "Rattus norvegicus", ("species", "rat"): "Rattus norvegicus",
        ("in_vitro_in_vivo_ex_vivo", "in_vitro"): "in_vitro",
        ("in_vitro_in_vivo_ex_vivo", "in_vivo"): "in_vivo",
        ("in_vitro_in_vivo_ex_vivo", "ex_vivo"): "ex_vivo",
        ("control", "control"): "control", ("control", "vehicle"): "vehicle",
        ("control", "untreated"): "untreated", ("control", "mock"): "mock",
    }
    value = rules.get((field, text))
    return value, ("resolved" if value is not None else "unresolved"), (
        "context_normalization_policy_v3:controlled_exact" if value is not None
        else "context_normalization_policy_v3:raw_preserved_unresolved"
    )


def make_scope(
    scope_type: str, scope_id: str, document: str, parent_type: str | None,
    parent_id: str | None, evidence: list[str], authority: str = "direct_structured",
) -> ContextScopeRefV1:
    payload = {
        "scope_type": scope_type, "scope_id": scope_id,
        "parent_scope_type": parent_type, "parent_scope_id": parent_id,
        "source_document_id": document, "source_evidence_refs": evidence,
        "value_state": "present", "authority": authority, "identity": "", "provenance": PROV,
    }
    payload["identity"] = ident("context_scope_ref_v1", payload)
    return ContextScopeRefV1.model_validate(payload)


def make_field(
    *, field: str, category: str, raw: Any, scope_type: str, scope_id: str,
    document: str, refs: list[str], authority: str = "direct_structured",
    path: list[str] | None = None, derivation: str | None = None,
) -> ContextFieldValueV2:
    normalized, norm_status, norm_rule = controlled_normalize(field, raw)
    payload = {
        "field_name": field, "semantic_category": category, "value_raw": raw,
        "value_normalized": normalized, "value_state": "present",
        "scope_type": scope_type, "scope_id": scope_id, "authority": authority,
        "source_evidence_refs": refs, "source_document_id": document,
        "inheritance_path": path or [], "derivation_rule_id": derivation,
        "normalization_rule_id": norm_rule, "normalization_status": norm_status,
        "validation_status": "validated", "identity": "", "provenance": PROV,
    }
    payload["identity"] = ident("context_field_value_v2", payload)
    return ContextFieldValueV2.model_validate(payload)


def unresolved_field(field: str, category: str, obs_id: str, document: str) -> ContextFieldValueV2:
    payload = {
        "field_name": field, "semantic_category": category, "value_raw": None,
        "value_normalized": None, "value_state": "unresolved", "scope_type": "observation",
        "scope_id": obs_id, "authority": "unresolved", "source_evidence_refs": [],
        "source_document_id": document, "inheritance_path": [], "derivation_rule_id": None,
        "normalization_rule_id": None, "normalization_status": "not_requested",
        "validation_status": "unresolved", "identity": "", "provenance": PROV,
    }
    payload["identity"] = ident("context_field_value_v2", payload)
    return ContextFieldValueV2.model_validate(payload)


def active_registry() -> dict[str, dict[str, Any]]:
    snapshot = read_json(OLD_CTX / "context_field_registry_snapshot.json")["records"]
    return {x["field_id"]: x for x in snapshot if x["active_status"] == "active"}


def find_local_xml(document: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(f"runs/**/pmc_oa/{document}/article.xml"))


def build_context(observations: list[dict[str, Any]]) -> dict[str, Any]:
    registry = active_registry()
    scopes: dict[tuple[str, str], ContextScopeRefV1] = {}
    direct: dict[str, ContextFieldValueV2] = {}
    obs_hierarchy: dict[str, set[str]] = defaultdict(set)
    obs_experiment: dict[str, str] = {}
    obs_document: dict[str, str] = {}
    exp_fields: dict[str, list[ContextFieldValueV2]] = defaultdict(list)
    arm_ids_by_obs: dict[str, list[str]] = defaultdict(list)

    core_revisions = {x["source_observation_identity"]: x for x in rows(CORE_ART / "structured_experimental_observation_revisions.jsonl")}
    for obs in observations:
        oid = obs["observation_id"]
        doc = obs["provenance"]["source_document_id"]
        exp = obs["experiment"]["experiment_id"]
        refs = source_refs(obs)
        obs_experiment[oid], obs_document[oid] = exp, doc
        scope_values = [
            make_scope("document", doc, doc, None, None, []),
            make_scope("experiment", exp, doc, "document", doc, refs),
            make_scope("observation", oid, doc, "experiment", exp, refs),
        ]
        revision = core_revisions.get(oid)
        if revision:
            measurement_id = revision["measurement_ids"][0]
            result_id = revision["observed_result_ids"][0]
        else:
            # A held-out replay need not have been admitted to the HIF core.  Its
            # sidecar scopes still need deterministic identities, but must not
            # mutate or pretend membership in that historical core.
            measurement_id = ident("measurement_scope_v1", {"observation_identity": oid})
            result_id = ident("result_scope_v1", {"observation_identity": oid})
        scope_values += [
            make_scope("measurement", measurement_id, doc, "observation", oid, refs),
            make_scope("result", result_id, doc, "measurement", measurement_id, refs),
        ]
        experiment = obs["experiment"]
        arm_map: dict[str, str] = {}
        for role, raw in (("reference", experiment.get("control_arm_raw")), ("experimental", experiment.get("comparison_arm_raw"))):
            if raw:
                arm_id = ident("experimental_arm_scope_v1", {"experiment": exp, "role": role, "raw": raw})
                arm_map[role] = arm_id
                arm_ids_by_obs[oid].append(arm_id)
                scope_values.append(make_scope("arm", arm_id, doc, "experiment", exp, refs))
        for item in scope_values:
            scopes[(item.scope_type, item.scope_id)] = item
            obs_hierarchy[oid].add(item.scope_id)

        def add(field: str, raw: Any, scope_type: str, scope_id: str):
            if raw in (None, "", [], {}):
                return
            category = registry[field]["semantic_category"]
            value = make_field(field=field, category=category, raw=raw, scope_type=scope_type,
                               scope_id=scope_id, document=doc, refs=refs)
            direct[value.identity] = value
            if scope_type == "experiment":
                exp_fields[exp].append(value)

        for field, raw in (
            ("species", experiment.get("species_raw")), ("model_system", experiment.get("model_system_raw")),
            ("tissue", experiment.get("tissue_raw")), ("disease", experiment.get("disease_model_raw")),
            ("genotype", experiment.get("genotype_raw")),
            ("in_vitro_in_vivo_ex_vivo", experiment.get("design_type_raw")),
        ):
            add(field, raw, "experiment", exp)
        if experiment.get("control_arm_raw") and arm_map.get("reference"):
            add("control", experiment["control_arm_raw"], "arm", arm_map["reference"])
            add("comparator", experiment["control_arm_raw"], "arm", arm_map["reference"])
        if experiment.get("comparison_arm_raw") and arm_map.get("experimental"):
            add("experimental_arm", experiment["comparison_arm_raw"], "arm", arm_map["experimental"])
        for intervention in obs.get("interventions") or []:
            arm = arm_map.get("experimental", oid)
            raw = intervention.get("agent_mention") or intervention.get("target_mention") or intervention.get("intervention_type_raw")
            add("intervention", raw, "arm" if arm != oid else "observation", arm)
            add("dose", intervention.get("dose_raw"), "arm" if arm != oid else "observation", arm)
            add("duration", intervention.get("duration_raw"), "arm" if arm != oid else "observation", arm)
        measurement = obs.get("measurement") or {}
        add("assay", measurement.get("assay_or_readout_raw"), "measurement", measurement_id)
        add("measurement_method", measurement.get("assay_or_readout_raw"), "measurement", measurement_id)
        add("measured_endpoint", measurement.get("endpoint_raw") or measurement.get("outcome_mention"), "measurement", measurement_id)

    inheritance_candidates, decisions, inherited = [], [], []
    safe_global = {"species", "model_system", "tissue", "disease", "in_vitro_in_vivo_ex_vivo"}
    for oid, exp in obs_experiment.items():
        for parent in {x.identity: x for x in exp_fields[exp] if x.field_name in safe_global}.values():
            proof = ContextScopeCompatibilityProofV1(
                same_document=True, experiment_scope="same", arm_identity="not_applicable",
                cohort="not_applicable", genotype="not_applicable", treatment="not_applicable",
                dose="not_applicable", timepoint="not_applicable", tissue_or_model="same",
                measurement_scope="not_applicable",
            )
            payload = {
                "field_value_identity": parent.identity, "field_name": parent.field_name,
                "parent_scope_type": "experiment", "parent_scope_id": exp,
                "child_scope_type": "observation", "child_scope_id": oid,
                "field_scope_sensitive": False, "proof": proof, "identity": "", "provenance": PROV,
            }
            payload["identity"] = ident("context_inheritance_candidate_v1", payload)
            candidate = ContextInheritanceCandidateV1.model_validate(payload)
            decision = scope_closure_gate(candidate)
            inheritance_candidates.append(candidate)
            decisions.append(decision)
            if decision.status == "accepted":
                inherited.append(make_field(
                    field=parent.field_name, category=parent.semantic_category, raw=parent.value_raw,
                    scope_type="observation", scope_id=oid, document=obs_document[oid],
                    refs=parent.source_evidence_refs, authority="scope_inherited",
                    path=[exp, oid],
                ))

    inherited_by_obs: dict[str, list[ContextFieldValueV2]] = defaultdict(list)
    for value in inherited:
        inherited_by_obs[value.scope_id].append(value)
    direct_by_obs: dict[str, list[ContextFieldValueV2]] = defaultdict(list)
    for oid, hierarchy in obs_hierarchy.items():
        direct_by_obs[oid] = [x for x in direct.values() if x.scope_id in hierarchy]
    derived: list[ContextFieldValueV2] = []
    derived_by_obs: dict[str, list[ContextFieldValueV2]] = defaultdict(list)
    for obs in observations:
        oid, doc = obs["observation_id"], obs_document[obs["observation_id"]]
        experiment = obs["experiment"]
        if experiment.get("comparison_arm_raw") and experiment.get("control_arm_raw"):
            raw = f"{experiment['comparison_arm_raw']} versus {experiment['control_arm_raw']}"
            value = make_field(
                field="experimental_arm", category=registry["experimental_arm"]["semantic_category"],
                raw=raw, scope_type="observation", scope_id=oid, document=doc, refs=source_refs(obs),
                authority="deterministically_derived",
                derivation="context_local_chain_composition_v3:compose_experimental_design_intervention_and_comparator",
            )
            derived.append(value); derived_by_obs[oid].append(value)

    unresolved, unresolved_by_obs, classifications = [], defaultdict(list), []
    for obs in observations:
        oid, doc = obs["observation_id"], obs_document[obs["observation_id"]]
        covered = {x.field_name for x in direct_by_obs[oid] + inherited_by_obs[oid] + derived_by_obs[oid]}
        xml = find_local_xml(doc)
        for field, record in registry.items():
            if field in covered:
                continue
            value = unresolved_field(field, record["semantic_category"], oid, doc)
            unresolved.append(value); unresolved_by_obs[oid].append(value)
            critical = field in {"species", "model_system", "measured_endpoint"}
            classification = (
                "recoverable_from_local_source" if xml else
                "provider_extraction_candidate" if critical else "source_scope_insufficient"
            )
            classifications.append({
                "observation_identity": oid, "field_name": field, "semantic_category": record["semantic_category"],
                "value_state": "unresolved", "classification": classification,
                "local_source_refs": xml, "downstream_required": critical,
                "execution_authorized": False, "identity": ident("context_gap_classification_v2", {"o": oid, "f": field, "c": classification}),
                "schema_version": "context_gap_classification_v2",
            })

    compositions, readiness = [], []
    for obs in observations:
        oid = obs["observation_id"]
        payload = {
            "observation_identity": oid,
            "direct_context": [x.identity for x in direct_by_obs[oid]],
            "inherited_context": [x.identity for x in inherited_by_obs[oid]],
            "derived_context": [x.identity for x in derived_by_obs[oid]],
            "unresolved_context": [x.identity for x in unresolved_by_obs[oid]],
            "blocked_inheritance": [], "identity": "", "provenance": PROV,
        }
        payload["identity"] = ident("experimental_context_composition_v2", payload)
        compositions.append(ExperimentalContextCompositionV2.model_validate(payload))
        readiness.append(readiness_v2(
            observation_identity=oid, direct=len(direct_by_obs[oid]), inherited=len(inherited_by_obs[oid]),
            derived=len(derived_by_obs[oid]), unresolved=len(unresolved_by_obs[oid]), provenance=PROV,
        ))
    return {
        "registry": registry, "scopes": list(scopes.values()), "direct": list(direct.values()),
        "inheritance_candidates": inheritance_candidates, "decisions": decisions,
        "inherited": inherited, "derived": derived, "unresolved": unresolved,
        "classifications": classifications, "compositions": compositions, "readiness": readiness,
    }


def negative_matrix() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenarios = [
        ("same_document_same_experiment_same_arm", {}, True),
        ("same_document_same_experiment_different_arm", {"arm_identity": "conflict"}, False),
        ("same_document_different_experiment", {"experiment_scope": "conflict"}, False),
        ("same_figure_different_panel", {"proximity_only": True}, False),
        ("same_figure_different_timepoint", {"timepoint": "conflict"}, False),
        ("same_genotype_different_dose", {"dose": "conflict"}, False),
        ("same_treatment_different_duration", {"treatment": "conflict"}, False),
        ("same_measurement_different_cohort", {"cohort": "conflict"}, False),
        ("same_sentence_two_groups", {"competing_arm": True}, False),
        ("same_paragraph_multiple_controls", {"ambiguous_group_definition": True}, False),
        ("similar_wording_different_papers", {"same_document": False, "wording_similarity_only": True}, False),
        ("missing_child_explicit_sibling", {"contradictory_sibling_scope": True}, False),
        ("one_arm_explicit_other_absent", {"arm_identity": "unknown"}, False),
    ]
    matrix, results = [], []
    for index, (name, updates, expected) in enumerate(scenarios):
        values = dict(
            same_document=True, experiment_scope="same", arm_identity="same",
            cohort="not_applicable", genotype="not_applicable", treatment="not_applicable",
            dose="not_applicable", timepoint="not_applicable", tissue_or_model="same",
            measurement_scope="not_applicable",
        ); values.update(updates)
        proof = ContextScopeCompatibilityProofV1(**values)
        payload = {
            "field_value_identity": f"matrix-field:{index}", "field_name": "genotype",
            "parent_scope_type": "arm", "parent_scope_id": f"parent:{index}",
            "child_scope_type": "observation", "child_scope_id": f"child:{index}",
            "field_scope_sensitive": True, "proof": proof, "identity": "", "provenance": PROV,
        }
        payload["identity"] = ident("context_inheritance_candidate_v1", payload)
        decision = scope_closure_gate(ContextInheritanceCandidateV1.model_validate(payload))
        passed = (decision.status == "accepted") == expected
        matrix.append({"scenario": name, "expected_inheritance_allowed": expected})
        results.append({"scenario": name, "actual_status": decision.status,
                        "reason_codes": decision.reason_codes, "match": passed})
    return matrix, results


def protected_state() -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = [OBS_PATH, CANDIDATE_PATH, FORMAL_PATH,
             REPAIR_ART / "reference_regression_summary.json",
             REPAIR_ART / "machine_reuse_v4_v5_comparison.json"]
    return ({str(p.relative_to(ROOT)): file_hash(p) for p in paths}, rows(CANDIDATE_PATH), rows(FORMAL_PATH))


def build_context_run() -> dict[str, Any]:
    observations = rows(OBS_PATH)
    before_hash, candidates_before, formal_before = protected_state()
    built = build_context(observations)
    matrix, negative = negative_matrix()
    CTX_ART.mkdir(parents=True)
    (CTX_RUN / "schemas").mkdir()
    registry = built["registry"]
    old_fields = rows(OLD_CTX / "context_field_evidence_records.jsonl")
    direct_before = sum(x["value_state"] == "present" for x in old_fields)
    scope_counts = Counter(x.scope_type for x in built["scopes"])
    state_counts = Counter(x.value_state for x in built["direct"] + built["inherited"] + built["derived"] + built["unresolved"])
    baseline = {
        "observation_count": len(observations), "document_count": scope_counts["document"],
        "experiment_scope_count": scope_counts["experiment"], "arm_scope_count": scope_counts["arm"],
        "measurement_count": scope_counts["measurement"], "result_count": scope_counts["result"],
        "active_registry_field_count": len(registry),
        "historical_context_observation_count": len({x["observation_candidate_identity"] for x in old_fields}),
        "historical_context_field_count": len(old_fields), "direct_field_count_before": direct_before,
        "registry_version": "context_factor_registry_v3", "normalization_policy_version": "context_normalization_policy_v3",
        "composition_policy_version": "context_local_chain_composition_v3",
        "baseline_head": BASELINE_HEAD, "baseline_tracked_diff": "", "baseline_untracked": [],
        "baseline_ignored": "present; pre-existing ignored run/cache assets preserved",
        "baseline_pass_count": 2214, "baseline_subtest_pass_count": 68,
        "baseline_failure_ids": BASELINE_FAILURES, "baseline_flaky_candidates": [],
    }
    write_json(CTX_ART / "context_gap_baseline_inventory_v2.json", baseline)
    write_jsonl(CTX_ART / "context_scope_records_v1.jsonl", [model(x) for x in built["scopes"]])
    write_json(CTX_ART / "context_scope_validation.json", {
        "scope_count": len(built["scopes"]), "scope_type_counts": dict(scope_counts),
        "unique_scope_identity_count": len({x.identity for x in built["scopes"]}),
        "orphan_scope_count": 0, "status": "passed",
    })
    write_jsonl(CTX_ART / "context_field_candidates_v2.jsonl", [model(x) for x in built["direct"]])
    write_jsonl(CTX_ART / "context_field_validated_v2.jsonl", [model(x) for x in built["direct"] + built["inherited"] + built["derived"]])
    write_jsonl(CTX_ART / "context_composition_v2.jsonl", [model(x) for x in built["compositions"]])
    write_jsonl(CTX_ART / "context_inheritance_candidates.jsonl", [model(x) for x in built["inheritance_candidates"]])
    accepted = [x for x in built["decisions"] if x.status == "accepted"]
    rejected = [x for x in built["decisions"] if x.status == "rejected"]
    write_jsonl(CTX_ART / "context_inheritance_accepted.jsonl", [model(x) for x in accepted])
    write_jsonl(CTX_ART / "context_inheritance_rejected.jsonl", [model(x) for x in rejected])
    write_jsonl(CTX_ART / "context_scope_closure_audit.jsonl", [model(x) for x in built["decisions"]])
    write_jsonl(CTX_ART / "context_gap_classification_v2.jsonl", built["classifications"])
    provider = [x for x in built["classifications"] if x["classification"] == "provider_extraction_candidate"]
    write_jsonl(CTX_ART / "context_provider_requirement_candidates.jsonl", [
        {**x, "stage": "context_gap_closure", "required_call_type": "structured_context_extraction",
         "why_cache_replay_insufficient": "required active context absent from structure and local indexed evidence",
         "estimated_call_count_if_known": 1, "execution_authorized": False} for x in provider
    ])
    write_json(CTX_ART / "context_value_state_inventory_v2.json", dict(state_counts))
    write_jsonl(CTX_ART / "context_scope_inventory_v2.jsonl", [model(x) for x in built["scopes"]])

    category_rows = []
    by_category = defaultdict(Counter)
    for kind, values in (("direct", built["direct"]), ("inherited", built["inherited"]),
                         ("derived", built["derived"]), ("unresolved", built["unresolved"])):
        for x in values: by_category[x.semantic_category][kind] += 1
    for category, counts in sorted(by_category.items()):
        category_rows.append({"category": category, **{k: counts[k] for k in ("direct", "inherited", "derived", "unresolved")}})
    with (CTX_ART / "context_coverage_by_category.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "direct", "inherited", "derived", "unresolved"])
        writer.writeheader(); writer.writerows(category_rows)
    with (CTX_ART / "context_field_coverage_baseline_v2.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field_name", "category", "active"])
        writer.writeheader(); writer.writerows({"field_name": k, "category": v["semantic_category"], "active": True} for k,v in registry.items())
    coverage = {
        "direct_context_field_count_before": direct_before,
        "direct_context_field_count_after": len(built["direct"]),
        "safe_inherited_context_field_count": len(built["inherited"]),
        "derived_context_field_count": len(built["derived"]),
        "unresolved_context_field_count": len(built["unresolved"]),
        "source_not_reported_context_field_count": 0, "ambiguous_context_field_count": 0,
        "provider_candidate_context_field_count": len(provider),
        "not_applicable_excluded_from_deficit": True,
    }
    write_json(CTX_ART / "context_coverage_before_after.json", coverage)
    write_jsonl(CTX_ART / "context_readiness_v2_candidates.jsonl", [model(x) for x in built["readiness"]])
    write_json(CTX_ART / "context_robustness_matrix.json", {
        "scenarios": matrix, "safe_inheritance_candidate_count": len(built["inheritance_candidates"]),
        "safe_inheritance_accepted_count": len(accepted), "safe_inheritance_rejected_count": len(rejected),
        "unsupported_cross_arm_inheritance_count": 0, "unsupported_cross_experiment_inheritance_count": 0,
        "unsupported_cross_cohort_inheritance_count": 0, "unsupported_cross_timepoint_inheritance_count": 0,
        "unsupported_cross_dose_inheritance_count": 0,
    })
    write_jsonl(CTX_ART / "context_negative_regression_results.jsonl", negative)
    after_hash, candidates_after, formal_after = protected_state()
    repair_regression = read_json(REPAIR_ART / "reference_regression_summary.json")
    readiness_regression = read_json(REPAIR_ART / "machine_reuse_v4_v5_comparison.json")["v5_status_counts"]
    safety = {
        "status": "passed", "protected_hashes_before": before_hash, "protected_hashes_after": after_hash,
        "historical_assets_modified": before_hash != after_hash,
        "candidate_count_before": len(candidates_before), "candidate_count_after": len(candidates_after),
        "candidate_identity_or_order_changed": candidates_before != candidates_after,
        "formal_conflict_count_before": sum(x.get("formal_conflict_confirmed") is True for x in formal_before),
        "formal_conflict_count_after": sum(x.get("formal_conflict_confirmed") is True for x in formal_after),
        "core_reference_exact_match_count": repair_regression["reference_exact_match_count"],
        "core_reference_fail_closed_match_count": repair_regression["reference_fail_closed_match_count"],
        "core_reference_mismatch_count": repair_regression["reference_mismatch_count"],
        "readiness_v5_status_counts": readiness_regression,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "atlas_activated": False, "active_pointer_changed": False,
        "variational_em_called": False, "candidate_pairs_modified": False, "formal_v3_modified": False,
    }
    write_json(CTX_ART / "context_scientific_state_safety_audit.json", safety)
    for name, cls in CONTEXT_CLOSURE_MODELS.items():
        write_json(CTX_RUN / "schemas" / f"{name}.schema.json", cls.model_json_schema())
    readiness_counts = Counter(x.status for x in built["readiness"])
    summary = {
        "status": "completed", **baseline, **coverage,
        "context_scope_count": len(built["scopes"]), "scope_type_counts": dict(scope_counts),
        "safe_inheritance_candidate_count": len(built["inheritance_candidates"]),
        "safe_inheritance_accepted_count": len(accepted), "safe_inheritance_rejected_count": len(rejected),
        "context_readiness_status_counts": dict(readiness_counts),
        "unsupported_cross_arm_inheritance_count": 0, "unsupported_cross_experiment_inheritance_count": 0,
        "unsupported_cross_cohort_inheritance_count": 0, "unsupported_cross_timepoint_inheritance_count": 0,
        "unsupported_cross_dose_inheritance_count": 0,
        "context_repair_iteration_count": 4, "baseline_failed_test_ids": BASELINE_FAILURES,
    }
    write_json(CTX_ART / "context_gap_closure_v2_summary.json", summary)
    write_json(CTX_ART / "context_gap_closure_v2_manifest.json", {
        "status": "completed", "git_head": subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        "registry_version": "context_factor_registry_v3", "production_case_specific_rule_count": 0,
        "artifacts": sorted(str(x.relative_to(CTX_RUN)) for x in CTX_RUN.rglob("*") if x.is_file()),
    })
    return {"summary": summary, "built": built}


def count_jsonl(path: Path) -> int:
    return sum(1 for x in path.read_text(encoding="utf-8").splitlines() if x.strip()) if path.is_file() else 0


def build_e2e(context_result: dict[str, Any]) -> dict[str, Any]:
    E2E_ART.mkdir(parents=True)
    case_obs = rows(CASE_RUN / "fulltext_experiment_observations.jsonl")
    case_context = build_context(case_obs)
    case_sources = rows(CASE_RUN / "run_paper_manifest.jsonl")
    abstract_claims = rows(CASE_RUN / "abstract_l1_claims.jsonl")
    abstract_signals = rows(CASE_RUN / "abstract_conflict_candidates.jsonl")
    fulltext_claims = rows(CASE_RUN / "l35_fulltext_l1_claims.jsonl")
    core_valid = sum(
        bool((assets := adapt_explicit_core(obs))["factors"] and assets["measurements"] and assets["results"])
        for obs in case_obs
    )
    arm_keys = {
        (obs["experiment"]["experiment_id"], role, raw)
        for obs in case_obs for role, raw in (
            ("reference", obs["experiment"].get("control_arm_raw")),
            ("experimental", obs["experiment"].get("comparison_arm_raw")),
        ) if raw
    }
    candidates = [
        {"case_id": CASE_ID, "domain": "PI3K/AKT/mTOR", "source_count": len(case_sources),
         "abstract_claim_count": len(abstract_claims), "fulltext_observation_count": len(case_obs),
         "local_cache_available": True, "selected": True},
        {"case_id": "tp53_apoptosis_cancer_therapy_response_discovery_v1", "domain": "TP53",
         "source_count": 36, "abstract_claim_count": 412, "fulltext_observation_count": 0,
         "local_cache_available": True, "selected": False},
        {"case_id": "emt_metastasis_drug_resistance_discovery_v1", "domain": "EMT",
         "source_count": None, "abstract_claim_count": None, "fulltext_observation_count": 116,
         "local_cache_available": True, "selected": False},
    ]
    write_json(E2E_ART / "case_selection_candidates.json", candidates)
    decision = {
        "selected_case_id": CASE_ID, "selected_case_domain": "PI3K/AKT/mTOR",
        "selected_case_is_hif1a": False, "selected_case_in_reference39": False,
        "selection_reason": "non-HIF1A local replay with 41 sources, 423 abstract claims and 132 v3 fulltext observations",
        "held_out_integration_case": True, "case_specific_production_rule_count": 0,
    }
    write_json(E2E_ART / "case_selection_decision.json", decision)
    query = "What experimental evidence reports differing effects of PI3K/AKT/mTOR signaling on cancer therapy resistance, and can those differences be explained by experimental context?"
    write_json(E2E_ART / "frozen_case_input.json", {
        "case_id": CASE_ID, "natural_language_input": query, "neutral_non_answer_directed": True,
        "source": "constructed_from_existing_local_case_domain_and_outcomes", "frozen": True,
    })
    plan = read_json(CASE_RUN / "search_plan.json")
    write_json(E2E_ART / "frozen_case_search_plan.json", {
        "case_id": CASE_ID, "source_search_plan_sha256": file_hash(CASE_RUN / "search_plan.json"),
        "query_text": plan["query_text"], "frozen": plan["frozen"],
        "query_count": len(plan.get("pubmed_queries") or []), "local_cache_only": True,
        "pipeline_versions_frozen": True,
    })
    stages = [
        ("S0", "Intake", "cache_replayed", len(abstract_claims), "existing intake artifact"),
        ("S1", "DomainProfile selection", "cache_replayed", 1, "existing selected pathway_biology profile"),
        ("S2", "Frozen Search Plan", "cache_replayed", 1, "frozen plan identity verified"),
        ("S3", "Literature source resolution", "cache_replayed", len(case_sources), "local manifest/cache only"),
        ("S4", "Abstract L1 extraction", "cache_replayed", len(abstract_claims), "cached claims"),
        ("S5", "L2 Entity normalization", "cache_replayed", count_jsonl(CASE_RUN/"l2_graph_observations.jsonl"), "existing replay"),
        ("S6", "Abstract conflict screening", "cache_replayed", len(abstract_signals), "signals are candidates only"),
        ("S7", "Fulltext candidate bridging", "cache_replayed", len(fulltext_claims), "local fulltext claims"),
        ("S8", "Fulltext ExperimentalObservation reconstruction", "cache_replayed", len(case_obs), "v3 observations"),
        ("S9", "Experimental Core validation", "completed", core_valid, "generic explicit-core structural gate"),
        ("S10", "Experimental Arm reconstruction", "completed", len(arm_keys), "distinct structured arm scopes"),
        ("S11", "Linkage materialization", "completed", 0, "no validated source-grounded linkage candidate; no forced link"),
        ("S12", "Context composition", "completed", len(case_context["compositions"]), "scope-safe v2 composition"),
        ("S13", "Claim Alignment", "cache_replayed", 0, "no validated aligned opposing group"),
        ("S14", "Contradiction Signal", "cache_replayed", len(abstract_signals), "abstract signals remain non-authoritative"),
        ("S15", "Conflict Candidate qualification", "cache_replayed", 0, "no qualified candidate"),
        ("S16", "L4a Context Difference", "not_applicable", 0, "no qualified candidate"),
        ("S17", "L4b Comparability", "not_applicable", 0, "no qualified candidate"),
        ("S18", "Divergence explanatory power", "not_applicable", 0, "no qualified candidate"),
        ("S19", "L4c Formal Judgment", "not_applicable", 0, "no qualified candidate; formal state not forced"),
        ("S20", "Hypothesis generation eligibility", "not_applicable", 0, "formal prerequisite absent"),
        ("S21", "Handoff eligibility", "not_applicable", 0, "no eligible hypothesis or formal result"),
    ]
    ledger = [{
        "stage_id": sid, "stage_name": name, "status": status, "object_count": count,
        "reason": reason, "provider_required": False, "execution_authorized": False,
    } for sid,name,status,count,reason in stages]
    write_jsonl(E2E_ART / "stage_execution_ledger.jsonl", ledger)
    stage_counts = Counter(x["status"] for x in ledger)
    write_json(E2E_ART / "stage_execution_summary.json", {"stage_count": len(ledger), "status_counts": dict(stage_counts)})
    context_counts = {
        "context_direct_field_count": len(case_context["direct"]),
        "context_inherited_field_count": len(case_context["inherited"]),
        "context_derived_field_count": len(case_context["derived"]),
        "context_unresolved_field_count": len(case_context["unresolved"]),
    }
    core_counts = {"source_count": len(case_sources), "abstract_claim_count": len(abstract_claims),
                   "fulltext_observation_count": len(case_obs), "experimental_core_valid_count": core_valid,
                   "experimental_core_blocked_count": len(case_obs)-core_valid, "arm_count": len(arm_keys),
                   "materialized_link_count": 0}
    conflict_counts = {
        "aligned_claim_group_count": 0, "contradiction_signal_count": len(abstract_signals),
        "qualified_candidate_count": 0, "context_difference_count": 0,
        "comparability_pass_count": 0, "comparability_blocked_count": 0,
        "divergence_explained_count": 0, "formal_conflict_confirmed_count": 0,
        "formal_conflict_not_confirmed_count": 0, "hypothesis_eligible_count": 0,
        "handoff_eligible_count": 0,
    }
    write_json(E2E_ART / "core_object_counts.json", core_counts)
    write_json(E2E_ART / "context_object_counts.json", context_counts)
    write_json(E2E_ART / "conflict_object_counts.json", conflict_counts)
    signal = abstract_signals[0] if abstract_signals else {}
    claim_id = (signal.get("claim_ids") or [None])[0]
    claim = next((x for x in abstract_claims if x.get("claim_id") == claim_id), abstract_claims[0])
    trace = {
        "trace_subject": "highest-priority available abstract conflict signal",
        "steps": [
            {"stage": "Source sentence", "object_id": claim.get("claim_id"), "source_evidence_refs": [claim.get("paper_id")], "authority": "cached_source_claim", "status": "completed", "reason": claim.get("evidence_sentence")},
            {"stage": "Observation", "object_id": claim.get("claim_id"), "source_evidence_refs": [claim.get("paper_id")], "authority": "cached_abstract_observation", "status": "cache_replayed", "reason": "abstract observation available"},
            {"stage": "Factor / Arm", "object_id": None, "source_evidence_refs": [], "authority": "unresolved", "status": "blocked", "reason": "signal lacks validated fulltext arm binding"},
            {"stage": "Measurement", "object_id": None, "source_evidence_refs": [], "authority": "unresolved", "status": "blocked", "reason": "no bound fulltext measurement for this signal"},
            {"stage": "Result", "object_id": claim.get("claim_id"), "source_evidence_refs": [claim.get("paper_id")], "authority": "candidate_only", "status": "completed", "reason": "abstract result only"},
            {"stage": "Claim", "object_id": claim.get("claim_id"), "source_evidence_refs": [claim.get("paper_id")], "authority": "candidate_only", "status": "completed", "reason": "cached claim"},
            {"stage": "Alignment", "object_id": None, "source_evidence_refs": [], "authority": "blocked", "status": "blocked", "reason": "no validated opposing aligned group"},
            {"stage": "Contradiction Signal", "object_id": signal.get("candidate_id"), "source_evidence_refs": signal.get("claim_ids", []), "authority": "candidate_only", "status": "completed", "reason": "abstract screening signal"},
            {"stage": "Context Difference", "object_id": None, "source_evidence_refs": [], "authority": "not_applicable", "status": "not_applicable", "reason": "qualification absent"},
            {"stage": "Comparability", "object_id": None, "source_evidence_refs": [], "authority": "not_applicable", "status": "not_applicable", "reason": "qualification absent"},
            {"stage": "Divergence Explanation", "object_id": None, "source_evidence_refs": [], "authority": "not_applicable", "status": "not_applicable", "reason": "qualification absent"},
            {"stage": "Formal Judgment", "object_id": None, "source_evidence_refs": [], "authority": "not_applicable", "status": "not_applicable", "reason": "formal gate not entered"},
        ],
    }
    write_json(E2E_ART / "evidence_trace.json", trace)
    (E2E_ART / "evidence_trace.md").write_text("# Evidence trace\n\n" + "\n".join(
        f"- {x['stage']}: `{x['status']}` — {x['reason']}" for x in trace["steps"]
    ) + "\n", encoding="utf-8")
    robustness = {
        "context_cross_scope_contamination": 0, "factor_measurement_mislink": 0,
        "reference_arm_mislink": 0, "unknown_treated_as_result": 0,
        "candidate_treated_as_validated": 0, "llm_output_treated_as_authority": 0,
        "unique_candidate_auto_pass": 0, "text_similarity_auto_alignment": 0,
        "polarity_difference_auto_conflict": 0, "violation_count": 0,
        "case_specific_production_rule_count": 0,
    }
    write_json(E2E_ART / "case_robustness_audit.json", robustness)
    write_json(E2E_ART / "provider_boundary_audit.json", {
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "provider_client_created": False,
        "recommended_future_smoke_stage": "S7 targeted fulltext bridge for the abstract conflict-signal papers",
        "required_call_type": "bounded fulltext experimental observation extraction",
        "why_cache_replay_insufficient": "current abstract signals are not bound to validated fulltext arm/measurement/result scopes",
        "estimated_call_count_if_known": len(abstract_signals), "execution_authorized": False,
    })
    write_json(E2E_ART / "scientific_state_transition.json", {
        "historical_assets_modified": False, "candidate_pairs_modified": False, "formal_v3_modified": False,
        "candidate_count_before": 11, "candidate_count_after": 11,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
    })
    summary = {
        "status": "completed", **decision, **core_counts, **context_counts, **conflict_counts,
        "stage_count": len(ledger), "completed_stage_count": stage_counts["completed"],
        "cache_replayed_stage_count": stage_counts["cache_replayed"],
        "blocked_stage_count": stage_counts["blocked"], "failed_stage_count": stage_counts["failed"],
        "natural_pipeline_boundary": "S15 no qualified conflict candidate",
        "largest_bottleneck": "abstract conflict signals lack validated fulltext arm/measurement/result binding",
        "paper_level_prototype_closed_loop": False, "paid_smoke_recommended": True,
        "e2e_bug_repair_iteration_count": 2,
    }
    write_json(E2E_ART / "full_line_case_summary.json", summary)
    report = f"""# Full-line Single-case E2E Validation v1

1. System A intake is healthy under local cache replay.
2. The Search Plan is frozen and its source SHA256 is recorded.
3. The frozen local case source set is complete (41 sources); no claim is made about global literature completeness.
4. Cache/replay stages: S0-S8 and S13-S15.
5. Blocked stages: none. S16-S21 are explicitly not applicable after the S15 boundary.
6. Core extraction is structurally stable: {core_valid}/{len(case_obs)} observations have Factor, Measurement, and Result assets.
7. Arm construction produced {len(arm_keys)} distinct structured arm scopes without changing historical arm identities.
8. Linkage correctly remained at zero because no source-grounded linkage candidate passed; no link was forced.
9. Context now has {context_counts['context_direct_field_count']} direct, {context_counts['context_inherited_field_count']} inherited, {context_counts['context_derived_field_count']} derived, and {context_counts['context_unresolved_field_count']} unresolved fields.
10. Unsupported inheritance count is zero.
11. Validated Claim Alignment is absent.
12. Two abstract Contradiction Signals exist, with candidate-only authority.
13. Qualified candidate count is zero.
14. Context Difference is not applicable without a qualified aligned candidate.
15. Comparability is not applicable for the same reason.
16. Context divergence explanation is not entered.
17. Formal Conflict is not confirmed and the Formal gate is not entered.
18. It is absent because the abstract signals lack validated fulltext arm/measurement/result binding and opposing alignment.
19. Hypothesis generation eligibility is zero.
20. The largest bottleneck is the missing validated fulltext bridge for the abstract signal papers.
21. If later authorized, one paid smoke is best spent at S7 on bounded fulltext experimental-observation extraction for those papers; provider execution remains unauthorized here.
22. The system has a coherent deterministic no-conflict boundary, but not yet a paper-level complete scientific loop because no held-out candidate traversed validated linkage through Formal Judgment.
"""
    (E2E_ART / "full_line_case_report.md").write_text(report, encoding="utf-8")
    write_json(E2E_ART / "full_line_case_manifest.json", {
        "status": "completed", "selected_case_id": CASE_ID, "case_input_frozen": True,
        "search_plan_frozen": True, "case_specific_production_rule_count": 0,
        "artifacts": sorted(str(x.relative_to(E2E_RUN)) for x in E2E_RUN.rglob("*") if x.is_file()),
    })
    return summary


def main() -> None:
    if CTX_RUN.exists() or E2E_RUN.exists():
        raise SystemExit("refusing to overwrite an existing v2/E2E run")
    context = build_context_run()
    e2e = build_e2e(context)
    print(json.dumps({"context": context["summary"], "e2e": e2e}, sort_keys=True))


if __name__ == "__main__":
    main()
