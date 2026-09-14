#!/usr/bin/env python3
"""Freeze 1,072 pre-acquisition profiles, then run alpha4 shadow analyses."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re

from code_engine.search.biological_unit_compatibility_v1_1 import (
    BiologicalUnitRegistryV1_1,
    decide_biological_unit_compatibility_v1_1,
)
from code_engine.search.composite_preacquisition_profile_v1 import (
    B_SUBTIERS,
    EVIDENCE_CLASSES,
    decide_composite_preacquisition_profile_v1,
)
from code_engine.search.endpoint_semantics_v1 import decide_endpoint_semantics_v1
from code_engine.search.functional_relation_evidence_v1_1 import (
    decide_functional_relation_evidence_v1_1,
)
from code_engine.search.historical_manifest_verifier import verify_frozen_manifest

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    from . import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1
    from . import run_search_plan_v23_alpha3_endpoint_semantics_shadow_offline as alpha3
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1
    import run_search_plan_v23_alpha3_endpoint_semantics_shadow_offline as alpha3


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260915_search_plan_v23_alpha4_composite_tierb_shadow_offline"
RETRIEVAL = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
CASE_FREEZE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
ERROR_RUN = alpha1.ERROR_RUN

METADATA = RETRIEVAL / "metadata_inventory.jsonl"
GATES = RETRIEVAL / "v22_gate_outputs.jsonl"
FULLTEXT_SELECTION = RETRIEVAL / "fulltext_selection_inventory.jsonl"
CASE_EXECUTION = RETRIEVAL / "heldout_case_execution_inventory.jsonl"
TARGETS = CASE_FREEZE / "heldout_scientific_targets.jsonl"
LABELS = ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl"

COMPOSITE_POLICY = ROOT / "configs/search_plans/composite_preacquisition_policy_v1.json"
TIER_B_POLICY = ROOT / "configs/search_plans/tier_b_acquisition_policy_v1.json"
IMPLEMENTATION = ROOT / "src/code_engine/search/composite_preacquisition_profile_v1.py"
PRODUCTION_FILES = [IMPLEMENTATION, COMPOSITE_POLICY, TIER_B_POLICY]

SEARCH_PLAN_VERSION = "v2.3-alpha4"
PROFILE_VERSION = "v1"
STRUCTURAL_STATUS = "frozen_candidate_universe_offline_shadow_analysis"
RETROSPECTIVE_STATUS = "seen_heldout_v1_retrospective_development_only"
EXPECTED_PROTOCOL_ROOT = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
EXPECTED_P0_ROOT = "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c"
EXPECTED_P1_ROOT = "fc5b98266996235995595ad6c097dc433ef0345d6023cda4e5deaa55a32e12b3"
EXPECTED_P2_ROOT = "cd576081b9b9add0d29a5982ec10fa3545dccd0eeb64e34949cefc6ff43e755d"
EXPECTED_P2_DECISIONS = "35e486b16e1454a28e7e52b1e0ac7cac0c7d520dc92247eb51761f763a1550c6"
EXPECTED_SOURCE = {
    "metadata_inventory.jsonl": (1072, "21c8a21402836c7182a33e35c741bb6263ce41caa8a2f0a5de42f915e446304e"),
    "v22_gate_outputs.jsonl": (1072, "85b01abbf6bb09473612281a2385e7b15d1e0212cd1df6dae8e0a775dc85d954"),
    "fulltext_selection_inventory.jsonl": (914, "89182a7296f3582f5746ac345854b747d3e5bed1b137eab02620018a04026d77"),
    "heldout_case_execution_inventory.jsonl": (8, "eb480dfbc22074f345a18058bd38978f2ed8f8195b12d69cb24ef18e7281d687"),
}
EXPECTED_TARGETS_SHA = "685c50f922ab0973393853ff571129df9a4bd55aa4272fbcfc7ab09c6cd67f8f"
EXPECTED_COUNTS = {"TIER_A": 142, "TIER_B": 772, "REJECT": 125, "ABSTAIN": 33}
CASES = tuple(f"heldout_v1_{index:03d}" for index in range(1, 9))
ZERO_CALLS = {
    "network_calls": 0,
    "provider_calls": 0,
    "llm_calls": 0,
    "downloads": 0,
    "new_fulltext_acquisitions": 0,
    "new_scientific_adjudication_calls": 0,
}
PHASE1_FILES = {
    "p2_endpoint_semantics_final_development_status.json",
    "composite_policy_snapshot.json",
    "tier_b_policy_snapshot.json",
    "candidate_universe_identity_manifest.json",
    "candidate_universe_validation.json",
    "v23_alpha4_candidate_composite_profiles.jsonl",
    "v23_alpha4_candidate_composite_profiles_sha256",
}
REQUIRED = PHASE1_FILES | {
    "candidate_universe_structural_analysis.json",
    "per_case_candidate_supply_analysis.json",
    "policy_a_shadow_analysis.json",
    "policy_b_shadow_analysis.json",
    "policy_c_shadow_analysis.json",
    "replacement_simulation_boundary.json",
    "acquired70_composite_profiles.json",
    "acquired70_retrospective_safety_analysis.json",
    "cross_module_overlap_analysis.json",
    "heldout_specific_rule_audit.json",
    "implementation_manifest.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}


def load_json(path: Path):
    return json.loads(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def json_bytes(value):
    return alpha1.frozen.pretty_json(value)


def require(condition, message):
    alpha1.frozen.require(condition, message)


def sha(path: Path):
    return alpha1.frozen.sha256(path)


def digest(value: bytes):
    return alpha1.frozen.digest(value)


def tagged_structural(payload):
    return {"development_status": STRUCTURAL_STATUS, **payload}


def tagged_retrospective(payload):
    return {"development_status": RETROSPECTIVE_STATUS, **payload}


def verify_declared_production_files(run: Path):
    manifest = load_json(run / "implementation_manifest.json")
    verified = []
    for entry in manifest.get("production_files", []):
        path = ROOT / entry["path"]
        require(path.is_file() and not path.is_symlink(), f"missing protected production file: {path}")
        actual = sha(path)
        require(actual == entry["sha256"], f"protected production file changed: {path}")
        verified.append({"path": entry["path"], "sha256": actual})
    require(verified, f"no production files declared by {run}")
    return verified


def verify_retrieval_sources():
    manifest = load_json(RETRIEVAL / "manifest.json")
    declared = {row["path"]: row for row in manifest["files"]}
    verified = []
    for name, (expected_count, expected_sha) in EXPECTED_SOURCE.items():
        entry = declared.get(name)
        require(entry is not None, f"retrieval manifest missing {name}")
        actual = sha(RETRIEVAL / name)
        require(entry["record_count"] == expected_count, f"retrieval record count changed: {name}")
        require(actual == entry["sha256"] == expected_sha, f"retrieval artifact changed: {name}")
        verified.append({"path": str((RETRIEVAL / name).relative_to(ROOT)),
                         "record_count": expected_count, "sha256": actual})
    require(manifest["heldout_v1_protocol_sha256"] == EXPECTED_PROTOCOL_ROOT,
            "retrieval protocol root changed")
    return {
        "manifest_path": str((RETRIEVAL / "manifest.json").relative_to(ROOT)),
        "manifest_sha256": sha(RETRIEVAL / "manifest.json"),
        "heldout_v1_protocol_sha256": EXPECTED_PROTOCOL_ROOT,
        "verified_candidate_universe_sources": verified,
    }


def verify_case_freeze():
    manifest = load_json(CASE_FREEZE / "freeze_manifest.json")
    pairs = []
    for entry in manifest["components"]:
        actual = sha(CASE_FREEZE / entry["path"])
        require(actual == entry["sha256"], f"case-freeze component changed: {entry['path']}")
        pairs.append([entry["path"], actual])
    actual_root = digest(alpha1.frozen.canonical_json(pairs))
    require(actual_root == manifest["heldout_v1_protocol_sha256"] == EXPECTED_PROTOCOL_ROOT,
            "heldout-v1 protocol root mismatch")
    require(sha(TARGETS) == EXPECTED_TARGETS_SHA, "frozen scientific targets changed")
    return {
        "heldout_v1_protocol_sha256": actual_root,
        "target_artifact_path": str(TARGETS.relative_to(ROOT)),
        "target_artifact_sha256": sha(TARGETS),
        "target_count": len(read_jsonl(TARGETS)),
    }


def verify_upstreams():
    p0 = verify_frozen_manifest(
        alpha1_1.RUN, root_field="v23_alpha1_1_biological_unit_refinement_sha256")
    p1 = verify_frozen_manifest(
        alpha2_1.RUN, root_field="v23_alpha2_1_functional_relation_refinement_sha256")
    p2 = verify_frozen_manifest(
        alpha3.RUN, root_field="v23_alpha3_endpoint_semantics_shadow_sha256")
    require(p0["aggregate_sha256"] == EXPECTED_P0_ROOT, "P0 root mismatch")
    require(p1["aggregate_sha256"] == EXPECTED_P1_ROOT, "P1 root mismatch")
    require(p2["aggregate_sha256"] == EXPECTED_P2_ROOT, "P2 root mismatch")
    p2_decisions = sha(alpha3.RUN / "v23_alpha3_endpoint_shadow_decisions.jsonl")
    require(p2_decisions == EXPECTED_P2_DECISIONS, "P2 decision root mismatch")
    return {
        "p0": {"root": p0["aggregate_sha256"],
               "production_files": verify_declared_production_files(alpha1_1.RUN)},
        "p1": {"root": p1["aggregate_sha256"],
               "production_files": verify_declared_production_files(alpha2_1.RUN)},
        "p2": {"root": p2["aggregate_sha256"],
               "decision_sha256": p2_decisions,
               "production_files": verify_declared_production_files(alpha3.RUN)},
        "candidate_universe": verify_retrieval_sources(),
        "case_freeze": verify_case_freeze(),
    }


def protected_state():
    upstreams = verify_upstreams()
    paths = [
        RETRIEVAL / "manifest.json", METADATA, GATES, FULLTEXT_SELECTION, CASE_EXECUTION,
        CASE_FREEZE / "freeze_manifest.json", TARGETS,
        alpha1_1.RUN / "implementation_manifest.json",
        alpha2_1.RUN / "implementation_manifest.json",
        alpha3.RUN / "implementation_manifest.json",
        alpha3.RUN / "v23_alpha3_endpoint_shadow_decisions.jsonl",
    ]
    for block in (upstreams["p0"], upstreams["p1"], upstreams["p2"]):
        paths.extend(ROOT / row["path"] for row in block["production_files"])
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(paths))}


def original_disposition(gate):
    return "ABSTAIN" if gate.get("state") is None else gate["state"]


def candidate_sources():
    metadata = read_jsonl(METADATA)
    gates = read_jsonl(GATES)
    targets = read_jsonl(TARGETS)
    require(len(metadata) == len(gates) == 1072, "candidate source count mismatch")
    for index, (meta, gate) in enumerate(zip(metadata, gates), 1):
        require((meta["case_id"], meta["canonical_publication_id"], meta["pmid"], meta["metadata_depth"])
                == (gate["case_id"], gate["canonical_publication_id"], gate["pmid"], gate["metadata_depth"]),
                f"metadata/gate identity-order mismatch at {index}")
        require(meta["query_provenance"] == gate["query_provenance"],
                f"query provenance mismatch at {index}")
    target_map = {row["case_id"]: row for row in targets}
    require(set(target_map) == set(CASES) and len(targets) == 8, "target case identity mismatch")
    return metadata, gates, target_map


def identity_manifest(metadata, gates, upstreams):
    identities = []
    for index, (meta, gate) in enumerate(zip(metadata, gates), 1):
        identities.append({
            "candidate_order": index,
            "case_publication_identity": meta["case_publication_identity"],
            "case_id": meta["case_id"],
            "canonical_publication_id": meta["canonical_publication_id"],
            "pmid": meta["pmid"],
            "metadata_depth": meta["metadata_depth"],
            "original_v22_disposition": original_disposition(gate),
            "query_provenance_sha256": digest(alpha1.frozen.canonical_json(meta["query_provenance"])),
        })
    ids = [row["case_publication_identity"] for row in identities]
    require(len(ids) == len(set(ids)) == 1072, "candidate identity uniqueness mismatch")
    return tagged_structural({
        "artifact_schema_version": "CandidateUniverseIdentityManifestV1",
        "metadata_candidate_count": 1072,
        "unique_candidate_identity_count": 1072,
        "canonical_order_rule": "physical order of frozen metadata_inventory.jsonl",
        "ordered_identity_sha256": digest(alpha1.frozen.canonical_json(identities)),
        "source_roots": upstreams["candidate_universe"],
        "identities": identities,
    })


def build_p2_status():
    return tagged_structural({
        "module": "EndpointSemanticsV1",
        "tuning_status_on_heldout_v1": "CLOSED",
        "alpha3_1_performed": False,
        "endpoint_mismatch_total": 9,
        "detectability_counts": {
            "DETECTABLE_PREACQUISITION": 0,
            "PARTIALLY_DETECTABLE_PREACQUISITION": 3,
            "NOT_SAFELY_DETECTABLE_PREACQUISITION": 6,
        },
        "direct_endpoint_incompatible": 0,
        "endpoint_mismatch_classified_incompatible": 0,
        "alpha4_role": "diagnostic_and_annotation_supporting",
        "partial_nonblocking": True,
        "unresolved_nonblocking": True,
        "positive_incompatibility_state": "INCOMPATIBLE",
        "exact_or_authorized_equivalent_required_for_acquisition": False,
        "reason_no_alpha3_1": "Frozen heldout-v1 development showed no safely detectable endpoint mismatches; further tuning is prohibited.",
    })


def build_phase1(upstreams):
    metadata, gates, targets = candidate_sources()
    composite_policy = load_json(COMPOSITE_POLICY)
    tier_b_policy = load_json(TIER_B_POLICY)
    require(composite_policy["shadow_only"] and tier_b_policy["shadow_only"],
            "alpha4 policies must remain shadow-only")

    base_unit_registry = load_json(alpha1.REGISTRY_PATH)
    unit_overlay = load_json(alpha1_1.REGISTRY_OVERLAY_PATH)
    base_unit_policy = load_json(alpha1.POLICY_PATH)
    unit_policy = load_json(alpha1_1.POLICY_OVERLAY_PATH)
    unit_registry = BiologicalUnitRegistryV1_1(base_unit_registry, unit_overlay)
    base_relation_policy = load_json(alpha2_1.BASE_POLICY_PATH)
    relation_policy = load_json(alpha2_1.POLICY_PATH)
    endpoint_registry = load_json(alpha3.REGISTRY_PATH)
    endpoint_policy = load_json(alpha3.POLICY_PATH)

    profiles = []
    for order, (meta, gate) in enumerate(zip(metadata, gates), 1):
        candidate_id = meta["case_publication_identity"]
        target = targets[meta["case_id"]]
        publication_metadata = {
            key: meta.get(key) for key in
            ("pmid", "pmcid", "doi", "journal", "publication_date", "publication_type",
             "canonical_publication_id")
        }
        module_input = {
            "packet_or_candidate_id": candidate_id,
            "ScientificPropositionTargetV1": target,
            "title": meta["title"],
            "abstract": meta["abstract"],
            "publication_metadata": publication_metadata,
        }
        unit = decide_biological_unit_compatibility_v1_1(
            unit_registry, base_unit_policy, unit_policy, target["context_qualifiers"],
            title=meta["title"], abstract=meta["abstract"],
            publication_metadata=publication_metadata,
        )
        relation = decide_functional_relation_evidence_v1_1(
            candidate_id, target, title=meta["title"], abstract=meta["abstract"],
            publication_metadata=publication_metadata,
            base_policy=base_relation_policy, policy=relation_policy,
        )
        endpoint = decide_endpoint_semantics_v1(
            candidate_id, target, title=meta["title"], abstract=meta["abstract"],
            publication_metadata=publication_metadata,
            registry=endpoint_registry, policy=endpoint_policy,
        )
        profile = decide_composite_preacquisition_profile_v1(
            candidate_id, meta["case_id"], original_disposition(gate),
            biological_unit_state=unit.overall_state,
            biological_unit_reason_codes=unit.reason_codes,
            functional_relation_state=relation.evidence_state,
            functional_relation_reason_codes=relation.reason_codes,
            endpoint_state=endpoint.overall_state,
            endpoint_reason_codes=endpoint.reason_codes,
            policy=composite_policy, tier_b_policy=tier_b_policy,
        )
        profiles.append({
            "artifact_schema_version": "CompositePreAcquisitionProfileV1",
            "search_plan_version": SEARCH_PLAN_VERSION,
            "composite_preacquisition_profile_version": PROFILE_VERSION,
            "development_status": STRUCTURAL_STATUS,
            "candidate_order": order,
            "source_identity": {
                "case_publication_identity": candidate_id,
                "canonical_publication_id": meta["canonical_publication_id"],
                "pmid": meta["pmid"],
                "pmcid": meta.get("pmcid"),
                "metadata_depth": meta["metadata_depth"],
            },
            "query_provenance": meta["query_provenance"],
            "query_provenance_sha256": digest(alpha1.frozen.canonical_json(meta["query_provenance"])),
            "module_input_sha256": digest(alpha1.frozen.canonical_json(module_input)),
            **asdict(profile),
            "raw_module_decisions": {
                "p0_biological_unit": asdict(unit),
                "p1_functional_relation": asdict(relation),
                "p2_endpoint_semantics": asdict(endpoint),
            },
        })

    ids = [row["packet_or_candidate_id"] for row in profiles]
    require(len(profiles) == len(set(ids)) == 1072, "alpha4 profile identity mismatch")
    counts = Counter(row["original_v22_disposition"] for row in profiles)
    require(dict(counts) == EXPECTED_COUNTS, f"v2.2 disposition counts changed: {counts}")
    eligible = [row for row in profiles if row["alpha4_original_eligible"]]
    require(len(eligible) == 914, "alpha4 original eligible count mismatch")
    require(all(row["evidence_class"] in EVIDENCE_CLASSES and row["tier_b_subtier"] in B_SUBTIERS
                for row in eligible), "class/subtier coverage failure")
    require(all(not any(row["fulltext_eligibility_by_policy"].values())
                for row in profiles if not row["alpha4_original_eligible"]),
            "reject/abstain resurrection detected")
    body = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in profiles)
    profile_sha = digest(body)
    identity = identity_manifest(metadata, gates, upstreams)
    validation = tagged_structural({
        "status": "PASS",
        "metadata_candidate_count": 1072,
        "unique_candidate_identity_count": 1072,
        "original_v22_disposition_counts": dict(counts),
        "alpha4_original_eligible_universe_count": len(eligible),
        "original_rejects_resurrected": 0,
        "original_abstains_resurrected": 0,
        "metadata_gate_identity_order_match": True,
        "query_provenance_unchanged": True,
        "candidate_membership_unchanged": True,
        "candidate_order_unchanged": True,
        "all_original_tier_a_b_exactly_one_evidence_class": True,
        "all_original_tier_a_b_exactly_one_subtier": True,
        "module_decision_input_fields": [
            "ScientificPropositionTargetV1", "title", "abstract", "publication_metadata"
        ],
        "original_v22_tier_passed_to_p0_p1_p2": False,
        "acquisition_outcomes_loaded": False,
        "fulltext_loaded": False,
        "pass_a_loaded": False,
        "pass_b_loaded": False,
        "relevance_labels_loaded": False,
        "contaminant_labels_loaded": False,
        "evaluator_rationale_loaded": False,
        "heldout_failure_families_loaded": False,
        "numeric_scientific_score_created": False,
        "candidate_composite_profiles_sha256": profile_sha,
        "shadow_only": True,
        **ZERO_CALLS,
    })
    outputs = {
        "p2_endpoint_semantics_final_development_status.json": json_bytes(build_p2_status()),
        "composite_policy_snapshot.json": json_bytes(composite_policy),
        "tier_b_policy_snapshot.json": json_bytes(tier_b_policy),
        "candidate_universe_identity_manifest.json": json_bytes(identity),
        "candidate_universe_validation.json": json_bytes(validation),
        "v23_alpha4_candidate_composite_profiles.jsonl": body,
        "v23_alpha4_candidate_composite_profiles_sha256": (profile_sha + "\n").encode(),
    }
    return outputs, profiles, profile_sha


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in PHASE1_FILES:
        path = RUN / name
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == outputs[name],
                    f"existing alpha4 phase1 differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == outputs[name],
                f"alpha4 phase1 write verification failed: {name}")


def load_frozen_phase1():
    body = (RUN / "v23_alpha4_candidate_composite_profiles.jsonl").read_bytes()
    actual = digest(body)
    declared = (RUN / "v23_alpha4_candidate_composite_profiles_sha256").read_text().strip()
    require(actual == declared, "frozen alpha4 profile hash mismatch")
    profiles = [json.loads(line) for line in body.splitlines() if line]
    require(len(profiles) == len({row["packet_or_candidate_id"] for row in profiles}) == 1072,
            "frozen alpha4 profile identity mismatch")
    return profiles, actual


def count_by(values, keys):
    counts = Counter(values)
    return {key: counts[key] for key in keys}


def structural_analysis(profiles):
    cases = {}
    for case in CASES:
        rows = [row for row in profiles if row["case_id"] == case]
        eligible = [row for row in rows if row["alpha4_original_eligible"]]
        cases[case] = {
            "candidate_count": len(rows),
            "original_v22_disposition_counts": count_by(
                (row["original_v22_disposition"] for row in rows), EXPECTED_COUNTS),
            "evidence_class_counts_among_original_tier_a_b": count_by(
                (row["evidence_class"] for row in eligible), EVIDENCE_CLASSES),
            "tier_b_subtier_counts_among_original_tier_a_b": count_by(
                (row["tier_b_subtier"] for row in eligible), B_SUBTIERS),
        }
    eligible = [row for row in profiles if row["alpha4_original_eligible"]]
    return tagged_structural({
        "analysis_name": "candidate_universe_structural_analysis",
        "not_a_performance_metric": True,
        "candidate_count": len(profiles),
        "original_v22_disposition_counts": count_by(
            (row["original_v22_disposition"] for row in profiles), EXPECTED_COUNTS),
        "alpha4_original_eligible_universe_count": len(eligible),
        "evidence_class_counts_among_original_tier_a_b": count_by(
            (row["evidence_class"] for row in eligible), EVIDENCE_CLASSES),
        "tier_b_subtier_counts_among_original_tier_a_b": count_by(
            (row["tier_b_subtier"] for row in eligible), B_SUBTIERS),
        "cases": cases,
    })


def supply_analysis(profiles):
    definition = {
        "basis": "fixed historical fulltext acquisition budget of 10 candidates per case",
        "NO_TIER_A_SUPPLY": "0 original Tier-A candidates remain Tier-A eligible",
        "LOW_TIER_A_SUPPLY": "1 through 9 original Tier-A candidates remain Tier-A eligible",
        "ADEQUATE_TIER_A_SUPPLY": "at least 10 original Tier-A candidates remain Tier-A eligible",
        "label_dependent": False,
    }
    cases = []
    for case in CASES:
        rows = [row for row in profiles if row["case_id"] == case and row["alpha4_original_eligible"]]
        original_a = [row for row in rows if row["original_v22_disposition"] == "TIER_A"]
        remaining = sum(row["tier_a_eligible_shadow"] for row in original_a)
        status = ("NO_TIER_A_SUPPLY" if remaining == 0 else
                  "LOW_TIER_A_SUPPLY" if remaining < 10 else "ADEQUATE_TIER_A_SUPPLY")
        routed = [row for row in rows if not row["tier_a_eligible_shadow"]]
        cases.append({
            "case_id": case,
            "original_tier_a_count": len(original_a),
            "remaining_tier_a_eligible_count": remaining,
            "all_original_tier_a_b_subtier_supply": count_by(
                (row["tier_b_subtier"] for row in rows), B_SUBTIERS),
            "post_tier_a_constraint_routing_supply": count_by(
                (row["tier_b_subtier"] for row in routed), B_SUBTIERS),
            "tier_a_supply_status": status,
        })
    return tagged_structural({
        "analysis_name": "per_case_candidate_supply_analysis",
        "adequacy_definition": definition,
        "case_specific_repairs_performed": False,
        "cases": cases,
    })


def policy_structural(profiles, policy_name, tier_b_policy):
    rows = [row for row in profiles if row["alpha4_original_eligible"]]
    original_a = [row for row in rows if row["original_v22_disposition"] == "TIER_A"]
    common = {
        "analysis_name": policy_name.lower() + "_shadow_analysis",
        "policy_name": policy_name,
        "shadow_only": True,
        "production_selected": False,
        "production_activation": False,
        "alpha4_original_eligible_universe_count": len(rows),
        "original_tier_a_count": len(original_a),
        "original_tier_a_remaining_eligible": sum(row["tier_a_eligible_shadow"] for row in original_a),
        "original_tier_a_blocked": sum(not row["tier_a_eligible_shadow"] for row in original_a),
        "retrospective_affected_definition": tier_b_policy["retrospective_affected_definitions"][policy_name],
    }
    if policy_name == "POLICY_A_MINIMAL":
        common.update({
            "retainable_candidate_count": len(rows),
            "hard_rejected_candidate_count": 0,
            "historical_order_changed": False,
        })
    elif policy_name == "POLICY_B_CONSERVATIVE_PRIORITY":
        order = tier_b_policy["policies"][policy_name]["fulltext_priority_order"]
        common.update({
            "retainable_candidate_count": len(rows),
            "hard_rejected_candidate_count": 0,
            "priority_order": order,
            "priority_class_counts": count_by(
                (row["fulltext_priority_class_by_policy"][policy_name] for row in rows), order),
        })
    else:
        common.update({
            "fulltext_eligible_count": sum(
                row["fulltext_eligibility_by_policy"][policy_name] for row in rows),
            "metadata_only_diagnostic_count": sum(
                not row["fulltext_eligibility_by_policy"][policy_name] for row in rows),
            "fulltext_eligible_subtiers": tier_b_policy["policies"][policy_name]["fulltext_eligible_subtiers"],
            "metadata_only_subtiers": tier_b_policy["policies"][policy_name]["metadata_only_subtiers"],
            "automatic_production_selection": False,
        })
    return tagged_structural(common)


def replacement_boundary(profiles):
    inventory = read_jsonl(FULLTEXT_SELECTION)
    selected = [row for row in inventory if row["selected"]]
    unselected = [row for row in inventory if not row["selected"]]
    require(len(inventory) == 914 and len(selected) == 70, "historical acquisition inventory mismatch")
    unknown_oa = [row for row in unselected if row.get("pmcid_available") and row.get("oa_available") is None]
    case_rows = []
    for case in CASES:
        selected_count = sum(row["case_id"] == case for row in selected)
        case_rows.append({
            "case_id": case,
            "historical_budget": 10,
            "selected_known_old_acquired": selected_count,
            "selected_previously_unacquired": None,
            "filled_historical_budget_positions": selected_count,
            "open_historical_budget_positions": 10 - selected_count,
            "replacement_candidate_disposition": "UNKNOWN_NOT_SIMULATED",
        })
    return tagged_structural({
        "analysis_name": "replacement_simulation_boundary",
        "replacement_selection_status": "REPLACEMENT_SELECTION_NOT_EVALUABLE_FROM_FROZEN_METADATA",
        "reason": "Frozen inventory leaves legal OA availability null for PMCID-bearing unacquired candidates; exact same-budget replacement selection cannot be established.",
        "historical_selected_known_old_acquired": len(selected),
        "unselected_candidates_with_pmcid_and_unknown_oa_availability": len(unknown_oa),
        "new_relevance_labels_assigned": 0,
        "replacement_relevance_inferred": False,
        "title_or_abstract_relevance_adjudication_performed": False,
        "new_fulltext_acquired": 0,
        "policies_simulated": [],
        "cases": case_rows,
    })


def join_acquired70(profiles):
    profile_map = {(row["case_id"], row["source_identity"]["pmid"]): row for row in profiles}
    selected = [row for row in read_jsonl(FULLTEXT_SELECTION) if row["selected"]]
    labels = read_jsonl(LABELS)
    label_map = {(row["case_id"], str(row["pmid"])): row for row in labels}
    selected_keys = {(row["case_id"], str(row["pmid"])) for row in selected}
    require(len(selected_keys) == len(selected) == 70, "selected acquisition identity mismatch")
    require(selected_keys == set(label_map), "acquired70 label join identity mismatch")
    joined = []
    for selection in selected:
        key = (selection["case_id"], str(selection["pmid"]))
        require(key in profile_map, f"acquired candidate missing frozen profile: {key}")
        profile = profile_map[key]
        label = label_map[key]
        require(profile["original_v22_disposition"] == label["tier"] == selection["tier_state"],
                f"historical Tier mismatch for {key}")
        joined.append({
            "packet_id": label["packet_id"],
            "packet_or_candidate_id": profile["packet_or_candidate_id"],
            "case_id": profile["case_id"],
            "pmid": profile["source_identity"]["pmid"],
            "historical_selection_index_within_case": selection["selection_index_within_case"],
            "original_v22_disposition": profile["original_v22_disposition"],
            "biological_unit_state": profile["biological_unit_state"],
            "functional_relation_state": profile["functional_relation_state"],
            "endpoint_state": profile["endpoint_state"],
            "evidence_class": profile["evidence_class"],
            "tier_b_subtier": profile["tier_b_subtier"],
            "tier_a_eligible_shadow": profile["tier_a_eligible_shadow"],
            "fulltext_eligibility_by_policy": profile["fulltext_eligibility_by_policy"],
            "fulltext_priority_class_by_policy": profile["fulltext_priority_class_by_policy"],
            "relevance_state": label["relevance_state"],
            "contaminant_class": label["contaminant_class"],
        })
    require(len(joined) == 70, "acquired70 joined count mismatch")
    return joined


def is_affected(row, policy_name):
    tier_a_loss = (row["original_v22_disposition"] == "TIER_A"
                   and not row["tier_a_eligible_shadow"])
    if policy_name == "POLICY_A_MINIMAL":
        return tier_a_loss
    if policy_name == "POLICY_B_CONSERVATIVE_PRIORITY":
        priority = row["fulltext_priority_class_by_policy"][policy_name]
        return tier_a_loss or priority in {
            "B2_MULTI_UNRESOLVED", "B3_RELATION_WEAK", "INCOMPATIBLE_DIAGNOSTIC"
        }
    if policy_name == "POLICY_C_STRICT_FULLTEXT_ELIGIBILITY":
        return tier_a_loss or not row["fulltext_eligibility_by_policy"][policy_name]
    raise ValueError(policy_name)


def effect_counts(rows, policy_name):
    affected = [row for row in rows if is_affected(row, policy_name)]
    return {
        "population_count": len(rows),
        "affected_count": len(affected),
        "affected_packet_ids": [row["packet_id"] for row in affected],
    }


def acquired_safety(joined, tier_b_policy):
    direct = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    tier_a_direct = [row for row in direct if row["original_v22_disposition"] == "TIER_A"]
    tier_a_nondirect = [row for row in joined if row["original_v22_disposition"] == "TIER_A"
                        and row["relevance_state"] != "DIRECTLY_RELEVANT"]
    tier_b_direct = [row for row in direct if row["original_v22_disposition"] == "TIER_B"]
    require((len(direct), len(tier_a_direct), len(tier_a_nondirect), len(tier_b_direct))
            == (32, 24, 11, 8), "frozen retrospective population count mismatch")
    policies = {}
    for name in tier_b_policy["policies"]:
        policies[name] = {
            "affected_definition": tier_b_policy["retrospective_affected_definitions"][name],
            "direct": effect_counts(direct, name),
            "tier_a_direct": effect_counts(tier_a_direct, name),
            "tier_a_nondirect": effect_counts(tier_a_nondirect, name),
        }
    return tagged_retrospective({
        "analysis_name": "acquired70_retrospective_safety_analysis",
        "acquired_paper_count": len(joined),
        "evidence_class_counts": count_by((row["evidence_class"] for row in joined), EVIDENCE_CLASSES),
        "tier_b_subtier_counts": count_by((row["tier_b_subtier"] for row in joined), B_SUBTIERS),
        "tier_a_eligible_shadow_count": sum(row["tier_a_eligible_shadow"] for row in joined),
        "direct_papers_total": len(direct),
        "tier_a_direct_total": len(tier_a_direct),
        "tier_a_direct_losing_tier_a_eligibility": sum(
            not row["tier_a_eligible_shadow"] for row in tier_a_direct),
        "tier_a_nondirect_total": len(tier_a_nondirect),
        "tier_a_nondirect_losing_tier_a_eligibility": sum(
            not row["tier_a_eligible_shadow"] for row in tier_a_nondirect),
        "tier_b_direct_total": len(tier_b_direct),
        "tier_b_direct_subtier_distribution": count_by(
            (row["tier_b_subtier"] for row in tier_b_direct), B_SUBTIERS),
        "policy_effects": policies,
        "replacement_quality_interpreted": False,
        "survivor_only_direct_relevance_recomputed": False,
        "performance_improvement_claimed": False,
    })


def cross_module_overlap(profiles):
    rows = [row for row in profiles if row["alpha4_original_eligible"]]
    flags = {
        "p0_incompatible": lambda row: row["biological_unit_state"] == "INCOMPATIBLE",
        "p1_relation_weak": lambda row: bool(row["relation_weak_flags"]),
        "p2_incompatible": lambda row: row["endpoint_state"] == "INCOMPATIBLE",
        "p0_unresolved": lambda row: row["biological_unit_state"] == "UNRESOLVED",
        "p1_unresolved": lambda row: row["functional_relation_state"] == "UNRESOLVED",
        "p2_partial_or_unresolved": lambda row: row["endpoint_state"] in {"PARTIAL", "UNRESOLVED"},
    }
    counts = {name: sum(predicate(row) for row in rows) for name, predicate in flags.items()}
    blocker_sets = {
        name: {row["packet_or_candidate_id"] for row in rows if flags[name](row)}
        for name in ("p0_incompatible", "p1_relation_weak", "p2_incompatible")
    }
    intersections = []
    names = tuple(blocker_sets)
    for mask in range(1, 1 << len(names)):
        selected = [names[i] for i in range(len(names)) if mask & (1 << i)]
        shared = set.intersection(*(blocker_sets[name] for name in selected))
        intersections.append({"signals": selected, "intersection_count": len(shared)})
    blocker_multiplicity = Counter(sum(predicate(row) for predicate in (
        flags["p0_incompatible"], flags["p1_relation_weak"], flags["p2_incompatible"])) for row in rows)
    return tagged_structural({
        "analysis_name": "cross_module_overlap_analysis",
        "population": "original frozen Tier A plus Tier B",
        "population_count": len(rows),
        "raw_signal_counts": counts,
        "explicit_blocker_intersections": intersections,
        "explicit_blocker_multiplicity_counts": {
            str(number): blocker_multiplicity[number] for number in range(4)
        },
        "composite_disposition_double_counts_candidates": False,
        "learned_precedence_created": False,
        "numeric_score_created": False,
    })


def heldout_specific_rule_audit(profiles):
    forbidden = {row["case_id"] for row in profiles}
    forbidden |= {row["packet_or_candidate_id"] for row in profiles}
    forbidden |= {row["source_identity"]["pmid"] for row in profiles}
    forbidden |= {row["source_identity"]["canonical_publication_id"] for row in profiles}
    metadata = read_jsonl(METADATA)
    forbidden |= {row["first_query_family_id"] for row in metadata}
    forbidden |= {row["first_query_variant_id"] for row in metadata}
    titles = {row["title"] for row in metadata if row["title"]}
    branch = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id)\b")
    findings = []
    for path in PRODUCTION_FILES:
        text = path.read_text()
        tokens = sorted(token for token in forbidden if token and token in text)
        found_titles = sorted(title for title in titles if title in text)
        branches = [line.strip() for line in text.splitlines() if branch.search(line)]
        if tokens or found_titles or branches:
            findings.append({"path": str(path.relative_to(ROOT)), "forbidden_tokens": tokens,
                             "forbidden_titles": found_titles, "identity_specific_branches": branches})
    return tagged_structural({
        "analysis_name": "heldout_specific_rule_audit",
        "production_files_scanned": [str(path.relative_to(ROOT)) for path in PRODUCTION_FILES],
        "production_case_specific_rules": len(findings),
        "findings": findings,
        "development_analysis_fixtures_may_contain_ids": True,
    })


def build_phase2(profiles, profile_sha):
    tier_b_policy = load_json(TIER_B_POLICY)
    structural = structural_analysis(profiles)
    supply = supply_analysis(profiles)
    policy_a = policy_structural(profiles, "POLICY_A_MINIMAL", tier_b_policy)
    policy_b = policy_structural(profiles, "POLICY_B_CONSERVATIVE_PRIORITY", tier_b_policy)
    policy_c = policy_structural(profiles, "POLICY_C_STRICT_FULLTEXT_ELIGIBILITY", tier_b_policy)
    replacement = replacement_boundary(profiles)
    joined = join_acquired70(profiles)
    acquired_profiles = tagged_retrospective({
        "artifact_schema_version": "Acquired70CompositeProfilesV1",
        "candidate_profiles_frozen_sha256": profile_sha,
        "record_count": len(joined),
        "records": joined,
    })
    safety = acquired_safety(joined, tier_b_policy)
    cross = cross_module_overlap(profiles)
    rules = heldout_specific_rule_audit(profiles)
    require(rules["production_case_specific_rules"] == 0,
            "held-out-specific alpha4 production rule detected")
    outputs = {
        "candidate_universe_structural_analysis.json": json_bytes(structural),
        "per_case_candidate_supply_analysis.json": json_bytes(supply),
        "policy_a_shadow_analysis.json": json_bytes(policy_a),
        "policy_b_shadow_analysis.json": json_bytes(policy_b),
        "policy_c_shadow_analysis.json": json_bytes(policy_c),
        "replacement_simulation_boundary.json": json_bytes(replacement),
        "acquired70_composite_profiles.json": json_bytes(acquired_profiles),
        "acquired70_retrospective_safety_analysis.json": json_bytes(safety),
        "cross_module_overlap_analysis.json": json_bytes(cross),
        "heldout_specific_rule_audit.json": json_bytes(rules),
    }
    summary_values = {
        "structural": structural,
        "supply": supply,
        "policy_a": policy_a,
        "policy_b": policy_b,
        "policy_c": policy_c,
        "replacement": replacement,
        "safety": safety,
        "cross": cross,
        "rules": rules,
    }
    return outputs, summary_values


def build_final(phase1, phase2, values, profile_sha, upstreams, before, after):
    require(before == after, "protected upstream state changed during alpha4")
    safety = values["safety"]
    policy_effects = safety["policy_effects"]
    outputs = {**phase1, **phase2}
    outputs["scientific_state_safety_audit.json"] = json_bytes({
        "development_status": STRUCTURAL_STATUS,
        "status": "PASS",
        **ZERO_CALLS,
        "production_rejection_enabled": False,
        "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "v22_search_plan_modified": False,
        "alpha1_1_modified": False,
        "alpha2_1_modified": False,
        "alpha3_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_state_before": before,
        "protected_state_after": after,
    })
    outputs["validation.json"] = json_bytes(tagged_structural({
        "status": "PASS",
        "required_output_file_count": 21,
        "candidate_profile_count": 1072,
        "unique_candidate_identity_count": 1072,
        "alpha4_original_eligible_universe_count": 914,
        "phase1_frozen_before_retrospective_join": True,
        "phase1_forbidden_sources_loaded": False,
        "candidate_universe_generation_replay_byte_identical": True,
        "complete_analysis_replay_byte_identical": True,
        "raw_p0_p1_p2_decisions_preserved": True,
        "exact_one_class_assignment": True,
        "exact_one_subtier_or_preserved_disposition_assignment": True,
        "p2_partial_and_unresolved_nonblocking": True,
        "original_rejects_and_abstains_not_resurrected": True,
        "replacement_relevance_inferred": False,
        "performance_improvement_claimed": False,
        "policy_selected_for_production": None,
        "production_case_specific_rules": 0,
        "heldout_v2_required": True,
        "shadow_only": True,
    }))
    components = [{"path": name, "sha256": digest(outputs[name])}
                  for name in sorted(outputs)
                  if name not in {"implementation_manifest.json", "summary.json"}]
    aggregate = digest(alpha1.frozen.canonical_json(
        [[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = json_bytes({
        "development_status": STRUCTURAL_STATUS,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "composite_preacquisition_profile_version": PROFILE_VERSION,
        "tier_b_policy_version": "v1",
        "shadow_only": True,
        "upstream_verification": upstreams,
        "production_files": [
            {"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in PRODUCTION_FILES
        ],
        "candidate_profiles_sha256": profile_sha,
        "phase1_frozen_before_retrospective_join": True,
        "phase1_forbidden_sources_loaded": False,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required artifacts except implementation_manifest.json and summary.json.",
        "v23_alpha4_composite_tierb_shadow_sha256": aggregate,
    })
    structural = values["structural"]
    outputs["summary.json"] = json_bytes(tagged_retrospective({
        "status": "completed",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "shadow_only": True,
        "metadata_candidate_count": 1072,
        "original_v22_disposition_counts": structural["original_v22_disposition_counts"],
        "alpha4_original_eligible_universe_count": 914,
        "evidence_class_counts": structural["evidence_class_counts_among_original_tier_a_b"],
        "tier_b_subtier_counts": structural["tier_b_subtier_counts_among_original_tier_a_b"],
        "per_case_supply": values["supply"]["cases"],
        "replacement_selection_status": values["replacement"]["replacement_selection_status"],
        "direct_papers_total": 32,
        "tier_a_direct_total": 24,
        "tier_a_nondirect_total": 11,
        "policy_effects": policy_effects,
        "production_case_specific_rules": 0,
        "production_policy_selected": None,
        "production_rejection_enabled": False,
        "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "v22_search_plan_modified": False,
        "alpha1_1_modified": False,
        "alpha2_1_modified": False,
        "alpha3_modified": False,
        "candidate_universe_generation_replay_byte_identical": True,
        "complete_analysis_replay_byte_identical": True,
        "v23_alpha4_candidate_composite_profiles_sha256": profile_sha,
        "v23_alpha4_composite_tierb_shadow_sha256": aggregate,
        "output_file_count": 21,
        "scientific_boundary": "P0, P1, and P2 are closed on seen heldout-v1 development evidence; alpha4 is shadow only and heldout-v2 is required.",
        "performance_improvement_claimed": False,
        **ZERO_CALLS,
        "historical_assets_modified": False,
    }))
    require(set(outputs) == REQUIRED and len(outputs) == 21,
            f"alpha4 final output membership mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs


def write_complete(outputs):
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                    f"existing alpha4 output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                f"alpha4 output write verification failed: {name}")
    require({path.name for path in RUN.iterdir()} == REQUIRED,
            "alpha4 run contains unexpected files")


def generate_and_freeze():
    upstreams = verify_upstreams()
    before = protected_state()
    phase1_a, profiles_a, sha_a = build_phase1(upstreams)
    phase1_b, profiles_b, sha_b = build_phase1(upstreams)
    require(phase1_a == phase1_b and profiles_a == profiles_b and sha_a == sha_b,
            "alpha4 candidate-universe generation replay mismatch")
    freeze_phase1(phase1_a)
    frozen_profiles, frozen_sha = load_frozen_phase1()
    normalized = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in frozen_profiles)
    require(normalized == phase1_a["v23_alpha4_candidate_composite_profiles.jsonl"]
            and frozen_sha == sha_a, "frozen alpha4 profiles differ from Phase 1")
    phase2_a, values_a = build_phase2(frozen_profiles, frozen_sha)
    phase2_b, values_b = build_phase2(frozen_profiles, frozen_sha)
    require(phase2_a == phase2_b and values_a == values_b,
            "alpha4 complete analysis replay mismatch")
    after = protected_state()
    final_a = build_final(phase1_a, phase2_a, values_a, frozen_sha, upstreams, before, after)
    final_b = build_final(phase1_b, phase2_b, values_b, frozen_sha, upstreams, before, after)
    require(final_a == final_b, "alpha4 final artifact replay mismatch")
    write_complete(final_a)
    require(before == protected_state(), "protected state changed during alpha4 write")
    return final_a


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("candidate_universe_generation_replay_byte_identical=true")
    print("complete_analysis_replay_byte_identical=true")


if __name__ == "__main__":
    main()
