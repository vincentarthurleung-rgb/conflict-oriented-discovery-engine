#!/usr/bin/env python3
"""Freeze the outcome-informed alpha1 audit before any V1_1 production change."""

from collections import Counter
import json
from pathlib import Path
import re

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260914_search_plan_v23_alpha1_1_biological_unit_refinement_offline"
STATUS = "seen_heldout_v1_outcome_informed_development_only"
ALPHA1_ROOT = "4529ed881b501509e574564f98eb4bedc9de95303fdb41387020b1fd6a3c9120"
ALPHA1_SHADOW = "dbaee296b84e9355b05e5caa0b0384a2d42f9922b124bc33ccbacee3ed458a60"
AUDIT_FILES = {
    "alpha1_incompatible_decision_audit.json",
    "alpha1_incompatible_decision_audit.md",
    "alpha1_unresolved_wrong_unit_audit.json",
    "alpha1_unresolved_wrong_unit_audit.md",
    "context_dimension_audit.json",
    "alpha1_refinement_decision.json",
}
DIMENSIONS = (
    "BIOLOGICAL_UNIT", "ANATOMICAL_REGION", "DISEASE_CONTEXT", "GENOTYPE_CONTEXT",
    "TREATMENT_CONTEXT", "OTHER_CONTEXT", "UNRESOLVED_CONTEXT_DIMENSION",
)


def tagged(payload):
    return {"development_status": STATUS, **payload}


def verify_alpha1():
    alpha1.verify_all_roots()
    manifest = alpha1._load(alpha1.RUN / "implementation_manifest.json")
    pairs = []
    for component in manifest["aggregate_components"]:
        actual = alpha1.frozen.sha256(alpha1.RUN / component["path"])
        alpha1.frozen.require(actual == component["sha256"], f"alpha1 component mismatch: {component['path']}")
        pairs.append([component["path"], actual])
    actual_root = alpha1.frozen.digest(alpha1.frozen.canonical_json(pairs))
    shadow_body = (alpha1.RUN / "v23_alpha1_shadow_decisions.jsonl").read_bytes()
    actual_shadow = alpha1.frozen.digest(shadow_body)
    declared_shadow = (alpha1.RUN / "v23_alpha1_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(actual_root == manifest["v23_alpha1_biological_unit_shadow_sha256"] == ALPHA1_ROOT,
                          "alpha1 root mismatch")
    alpha1.frozen.require(actual_shadow == declared_shadow == ALPHA1_SHADOW, "alpha1 shadow mismatch")
    return {"alpha1_root": actual_root, "alpha1_shadow_decisions_sha256": actual_shadow}


def load_development_rows():
    inputs = {row["packet_id"]: row for row in alpha1.parse_preacquisition_batches()}
    shadow, _ = alpha1.load_frozen_shadow_decisions()
    joined = alpha1.join_development_labels(shadow)
    alpha1.frozen.require(set(inputs) == {row["packet_id"] for row in joined}, "audit input identity mismatch")
    return inputs, joined


def context_dimensions(decision, qualifiers):
    dimensions = []
    unit_types = {item["unit_type"] for item in decision["target_units"]}
    if unit_types & {"cell_type", "cell_line", "tissue", "organ"}:
        dimensions.append("BIOLOGICAL_UNIT")
    if decision["target_anatomical_regions"]:
        dimensions.append("ANATOMICAL_REGION")
    if "mixed" in unit_types:
        dimensions.append("DISEASE_CONTEXT")
    if any(re.search(r"\b(?:mutant|mutation|genotype|t790m|egfr[- ]mutant)\b", qualifier.casefold())
           for qualifier in qualifiers):
        dimensions.append("GENOTYPE_CONTEXT")
    if not dimensions:
        dimensions.append("UNRESOLVED_CONTEXT_DIMENSION")
    return [dimension for dimension in DIMENSIONS if dimension in dimensions]


def alpha1_interpretation(decision, qualifiers):
    return {
        "target_context_dimensions": context_dimensions(decision, qualifiers),
        "target_units_alpha1": decision["target_units"],
        "target_anatomical_regions_alpha1": decision["target_anatomical_regions"],
        "alpha1_treated_non_unit_dimension_as_unit": any(
            item["unit_type"] in {"mixed", "unknown"} for item in decision["target_units"]
        ),
    }


def registry_and_policy_trace(decision):
    relation_reasons = {"AUTHORIZED_SUBTYPE", "AUTHORIZED_MODEL_OF"}
    return {
        "registry_relations_used": {
            "surface_resolutions": [
                {key: item[key] for key in ("canonical_id", "matched_surface", "match_type", "evidence_role", "field")}
                for item in decision["matched_surfaces"]
            ],
            "authorized_relation_reason_codes": [code for code in decision["reason_codes"] if code in relation_reasons],
            "target_region_constraints": [item["canonical_id"] for item in decision["target_anatomical_regions"]],
        },
        "policy_rules_used": {
            "allow_exact": True,
            "allow_alias": True,
            "allow_descendant": True,
            "allow_model_of": True,
            "allow_broader_container": False,
            "require_anatomical_region_match_when_specified": True,
            "experimental_units_only_for_positive_cell_decision": True,
            "conservative_multiple_unit_aggregation": True,
        },
    }


def incompatible_classification(row):
    if row["relevance_state"] == "DIRECTLY_RELEVANT":
        return "DIRECT_PAPER_FALSE_INCOMPATIBILITY"
    if row["contaminant_class"] == "wrong_biological_unit":
        return "TRUE_UNIT_INCOMPATIBILITY_CAPTURE"
    if "BIOLOGICAL_UNIT_MISMATCH" not in row["development_failure_families"]:
        return "NONDIRECT_BUT_NOT_UNIT_FAILURE"
    return "AMBIGUOUS_DEVELOPMENT_DIAGNOSIS"


def build_incompatible_audit(inputs, joined):
    selected = [row for row in joined if row["decision"]["overall_state"] == "INCOMPATIBLE"]
    alpha1.frozen.require(len(selected) == 11, "alpha1 incompatible count mismatch")
    records = []
    for row in selected:
        source, decision = inputs[row["packet_id"]], row["decision"]
        qualifiers = source["scientific_target"]["context_qualifiers"]
        records.append({
            "packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
            "target_context_qualifiers": qualifiers,
            "target_biological_unit_interpretation": alpha1_interpretation(decision, qualifiers),
            "preacquisition_observed_unit_surfaces": decision["matched_surfaces"],
            "resolved_observed_units": decision["observed_units"],
            "cell_identity_state": decision["cell_identity_state"],
            "anatomical_region_state": decision["anatomical_region_state"],
            "overall_state": decision["overall_state"], "reason_codes": decision["reason_codes"],
            **registry_and_policy_trace(decision),
            "frozen_retrospective": {
                "relevance_state": row["relevance_state"], "contaminant_class": row["contaminant_class"],
                "development_failure_families": row["development_failure_families"],
            },
            "retrospective_incompatibility_classification": incompatible_classification(row),
        })
    counts = Counter(row["retrospective_incompatibility_classification"] for row in records)
    direct = next(row for row in records if row["packet_id"] == "heldout_rrpv1_0043")
    return tagged({
        "audit_name": "alpha1_incompatible_decision_audit", "alpha1_decisions_modified": False,
        "packet_count": 11, "classification_counts": dict(sorted(counts.items())), "records": records,
        "direct_false_incompatibility_deep_audit": {
            "packet_id": direct["packet_id"],
            "source_fields": {
                "target_context_qualifiers": direct["target_context_qualifiers"],
                "observed_surface_field": "abstract",
                "observed_surface": "cancer cell",
                "observed_canonical_id": "BU:CELL:CANCER_GENERIC",
                "alpha1_target_canonical_id": "BU:MODEL:EGFR_MUTANT_NSCLC",
            },
            "alpha1_states": {key: direct[key] for key in
                              ("cell_identity_state", "anatomical_region_state", "overall_state")},
            "alpha1_reason_codes": direct["reason_codes"],
            "mechanism_families": [
                "target_qualifier_incorrectly_interpreted_as_biological_unit",
                "disease_context_conflated_with_cell_identity",
                "genotype_context_conflated_with_biological_unit",
            ],
            "root_cause": "Alpha1 registered a disease-plus-genotype model context as unit_type=mixed, then compared it as a required biological unit against the resolved experimental generic cancer-cell surface.",
            "cause_scope": "generic_context_dimension_and_applicability_failure",
            "packet_specific_repair_justified": False,
            "generic_applicability_fix_justified": True,
        },
    })


def unresolved_reason(row, source):
    decision = row["decision"]
    experimental = [item for item in decision["matched_surfaces"]
                    if item["evidence_role"] == "experimental_biological_unit"]
    experimental_units = {item["canonical_id"] for item in experimental
                          if not item["canonical_id"].startswith("BU:REGION:")}
    observed_types = {item["unit_type"] for item in decision["observed_units"]}
    dimensions = context_dimensions(decision, source["scientific_target"]["context_qualifiers"])
    if "DISEASE_CONTEXT" in dimensions and "BIOLOGICAL_UNIT" not in dimensions:
        return "CONTEXT_DIMENSION_AMBIGUITY", "OUTSIDE_MODULE_AUTHORITY"
    if row["packet_id"] == "heldout_rrpv1_0058":
        return "REGISTRY_COVERAGE_GAP", "FIXABLE_DETERMINISTIC_COVERAGE_BUT_NOT_IMPLEMENTED"
    if "MULTIPLE_CONFLICTING_UNITS" in decision["reason_codes"] or (
            len(experimental_units) > 1 and "DISTINCT_CELL_TYPE" in decision["reason_codes"]):
        return "MULTIPLE_CONFLICTING_UNITS", "GENUINELY_UNAVAILABLE_PREACQUISITION"
    if "BROADER_CONTAINER_ONLY" in decision["reason_codes"] or (
            observed_types & {"tissue", "organ"} and not experimental_units):
        return "BROADER_CONTAINER_ONLY", "GENUINELY_UNAVAILABLE_PREACQUISITION"
    if decision["observed_units"] and not experimental_units:
        return "EXPERIMENT_ROLE_AMBIGUITY", "FIXABLE_DETERMINISTIC_ROLE_CANDIDATE_NOT_IMPLEMENTED"
    if not decision["observed_units"]:
        return "MISSING_PREACQUISITION_UNIT_EVIDENCE", "GENUINELY_UNAVAILABLE_PREACQUISITION"
    return "UNIT_SURFACE_PRESENT_BUT_UNRESOLVED", "GENUINELY_UNAVAILABLE_PREACQUISITION"


def build_unresolved_audit(inputs, joined):
    selected = [row for row in joined if row["contaminant_class"] == "wrong_biological_unit"
                and row["decision"]["overall_state"] == "UNRESOLVED"]
    alpha1.frozen.require(len(selected) == 12, "alpha1 unresolved wrong-unit count mismatch")
    records = []
    for row in selected:
        source, decision = inputs[row["packet_id"]], row["decision"]
        reason, limitation = unresolved_reason(row, source)
        records.append({
            "packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
            "target_context_qualifiers": source["scientific_target"]["context_qualifiers"],
            "alpha1_states": {key: decision[key] for key in
                              ("cell_identity_state", "anatomical_region_state", "overall_state")},
            "alpha1_reason_codes": decision["reason_codes"],
            "observed_surfaces": decision["matched_surfaces"],
            "unresolved_reason_class": reason, "limitation_class": limitation,
            "force_to_incompatible": False,
            "frozen_retrospective": {
                "relevance_state": row["relevance_state"], "contaminant_class": row["contaminant_class"],
                "development_failure_families": row["development_failure_families"],
            },
        })
    reason_counts = Counter(row["unresolved_reason_class"] for row in records)
    limitation_counts = Counter(row["limitation_class"] for row in records)
    return tagged({
        "audit_name": "alpha1_unresolved_wrong_unit_audit", "packet_count": 12,
        "reason_distribution": dict(sorted(reason_counts.items())),
        "limitation_distribution": dict(sorted(limitation_counts.items())),
        "genuinely_unavailable_preacquisition_packet_ids": [
            row["packet_id"] for row in records
            if row["limitation_class"] == "GENUINELY_UNAVAILABLE_PREACQUISITION"
        ],
        "records": records, "no_forced_incompatible_decisions": True,
    })


def build_context_audit(inputs, joined):
    by_qualifier = {}
    lookup = {row["packet_id"]: row for row in joined}
    for source in inputs.values():
        qualifier = " | ".join(source["scientific_target"]["context_qualifiers"])
        if qualifier not in by_qualifier:
            decision = lookup[source["packet_id"]]["decision"]
            dimensions = context_dimensions(decision, source["scientific_target"]["context_qualifiers"])
            by_qualifier[qualifier] = {
                "target_context_qualifiers": source["scientific_target"]["context_qualifiers"],
                "dimensions": dimensions,
                "unit_constraints_present": "BIOLOGICAL_UNIT" in dimensions,
                "region_constraints_present": "ANATOMICAL_REGION" in dimensions,
                "non_unit_context_qualifiers": source["scientific_target"]["context_qualifiers"]
                if any(item in dimensions for item in ("DISEASE_CONTEXT", "GENOTYPE_CONTEXT", "TREATMENT_CONTEXT", "OTHER_CONTEXT")) else [],
                "packet_count": 0,
            }
        by_qualifier[qualifier]["packet_count"] += 1
    dimension_counts = Counter(dimension for row in by_qualifier.values()
                               for dimension in row["dimensions"] for _ in range(row["packet_count"]))
    return tagged({
        "audit_name": "context_dimension_audit", "dimension_vocabulary": list(DIMENSIONS),
        "records": list(by_qualifier.values()), "packet_dimension_counts": {
            dimension: dimension_counts[dimension] for dimension in DIMENSIONS
        },
        "finding": "Alpha1 did not cleanly separate unit identity from disease/genotype context because unit_type=mixed entries participated in cell-identity incompatibility.",
        "biological_unit_authority_limited_to": ["BIOLOGICAL_UNIT", "ANATOMICAL_REGION"],
        "v1_1_applicability_layer_required": True,
    })


def build_refinement_decision(incompatible, unresolved):
    return tagged({
        "decision_name": "alpha1_refinement_decision",
        "outcome_informed_development": True,
        "changes": [
            {
                "change_id": "V1_1_CONTEXT_DIMENSION_APPLICABILITY",
                "generic_failure_mechanism": "Disease/genotype context registered as unit_type=mixed was compared as biological-unit identity.",
                "affected_development_packets": ["heldout_rrpv1_0041", "heldout_rrpv1_0043", "heldout_rrpv1_0049"],
                "scientific_scope": "Target-side context-dimension classification and biological-unit applicability only.",
                "risk": "Over-conservative non-applicability can leave disease-unit mismatches to a separate disease-context module.",
                "implemented": True,
                "reason": "One generic mechanism caused both the direct false incompatibility and a non-unit failure; the module lacks authority over disease/genotype compatibility.",
            },
            {
                "change_id": "V1_1_POSITIVE_INCOMPATIBILITY_PRECONDITIONS",
                "generic_failure_mechanism": "Alpha1 had no explicit applicability prerequisite in its INCOMPATIBLE path.",
                "affected_development_packets": [row["packet_id"] for row in incompatible["records"]],
                "scientific_scope": "Generic fail-closed prerequisites for applicable, resolved target and experimental observed unit.",
                "risk": "More decisions remain UNRESOLVED.",
                "implemented": True,
                "reason": "Makes existing intended conservative semantics explicit without adding label-dependent runtime rules.",
            },
            {
                "change_id": "DEFER_EXPERIMENT_ROLE_EXPANSION",
                "generic_failure_mechanism": "Some wrong-unit surfaces occur only in titles or sentences alpha1 marks mentioned_unit.",
                "affected_development_packets": [row["packet_id"] for row in unresolved["records"]
                                                 if row["unresolved_reason_class"] == "EXPERIMENT_ROLE_AMBIGUITY"],
                "scientific_scope": "Evidence-role classification.",
                "risk": "Treating every title/context mention as experimental could create new false incompatibilities.",
                "implemented": False,
                "reason": "The seen corpus does not justify a safe generic expansion of experimental-role authority.",
            },
            {
                "change_id": "DEFER_SINGLE_PACKET_REGISTRY_EXPANSION",
                "generic_failure_mechanism": "One audit packet contains a biological-unit surface absent from alpha1 registry coverage.",
                "affected_development_packets": [row["packet_id"] for row in unresolved["records"]
                                                 if row["unresolved_reason_class"] == "REGISTRY_COVERAGE_GAP"],
                "scientific_scope": "Registry coverage.",
                "risk": "A relation or alias added from one seen packet could be packet-driven overfitting.",
                "implemented": False,
                "reason": "No independent curated source was available offline; retain the known limitation.",
            },
            {
                "change_id": "DEFER_CONSERVATIVE_AGGREGATION_CHANGE",
                "generic_failure_mechanism": "Multiple units or broader containers can downgrade positive mismatch evidence to UNRESOLVED.",
                "affected_development_packets": [row["packet_id"] for row in unresolved["records"]
                                                 if row["unresolved_reason_class"] in {"MULTIPLE_CONFLICTING_UNITS", "BROADER_CONTAINER_ONLY"}],
                "scientific_scope": "Multiple-unit and container aggregation.",
                "risk": "Choosing a target-adverse unit without experiment linkage would violate conservative aggregation.",
                "implemented": False,
                "reason": "Pre-acquisition evidence does not reliably assign every detected unit to the relevant experiment.",
            },
        ],
        "registry_relations_added_or_changed": [],
        "alpha1_mutation_permitted": False,
        "further_biological_unit_tuning_on_heldout_v1_permitted_after_v1_1": False,
    })


def markdown_incompatible(audit):
    lines = [
        "# Alpha1 incompatible decision audit", "", f"development_status = {STATUS}", "",
        "This is outcome-informed development evidence. Alpha1 decisions are unchanged.", "",
        "| packet_id | case | tier | retrospective classification | alpha1 reason codes |", "|---|---|---|---|---|",
    ]
    for row in audit["records"]:
        lines.append(f"| {row['packet_id']} | {row['case_id']} | {row['tier']} | {row['retrospective_incompatibility_classification']} | {', '.join(row['reason_codes'])} |")
    deep = audit["direct_false_incompatibility_deep_audit"]
    lines.extend(["", "## Direct false incompatibility", "", f"`{deep['packet_id']}`: {deep['root_cause']}", "",
                  "The cause is generic; a packet-specific repair is not justified. A target context-dimension/applicability layer is justified.", ""])
    return "\n".join(lines).encode()


def markdown_unresolved(audit):
    lines = [
        "# Alpha1 unresolved wrong-unit audit", "", f"development_status = {STATUS}", "",
        "No audited packet is forced to INCOMPATIBLE.", "", "| packet_id | reason class | limitation class |", "|---|---|---|",
    ]
    for row in audit["records"]:
        lines.append(f"| {row['packet_id']} | {row['unresolved_reason_class']} | {row['limitation_class']} |")
    lines.extend(["", "Genuinely unavailable before acquisition: " +
                  ", ".join(f"`{packet}`" for packet in audit["genuinely_unavailable_preacquisition_packet_ids"]), ""])
    return "\n".join(lines).encode()


def build_audit_outputs():
    verify_alpha1()
    inputs, joined = load_development_rows()
    incompatible = build_incompatible_audit(inputs, joined)
    unresolved = build_unresolved_audit(inputs, joined)
    outputs = {
        "alpha1_incompatible_decision_audit.json": alpha1._json(incompatible),
        "alpha1_incompatible_decision_audit.md": markdown_incompatible(incompatible),
        "alpha1_unresolved_wrong_unit_audit.json": alpha1._json(unresolved),
        "alpha1_unresolved_wrong_unit_audit.md": markdown_unresolved(unresolved),
        "context_dimension_audit.json": alpha1._json(build_context_audit(inputs, joined)),
        "alpha1_refinement_decision.json": alpha1._json(build_refinement_decision(incompatible, unresolved)),
    }
    alpha1.frozen.require(set(outputs) == AUDIT_FILES, "audit output membership mismatch")
    return outputs


def freeze_audits(outputs):
    RUN.mkdir(exist_ok=True)
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing audit differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(alpha1.frozen.sha256(path) == alpha1.frozen.digest(body),
                              f"audit write verification failed: {name}")


def main():
    outputs = build_audit_outputs()
    freeze_audits(outputs)
    print(json.dumps({"status": "audit_frozen_before_v1_1_production_change", "files": sorted(outputs)}, indent=2))


if __name__ == "__main__":
    main()
