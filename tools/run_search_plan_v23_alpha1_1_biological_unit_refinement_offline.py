#!/usr/bin/env python3
"""Run V1_1 pre-acquisition shadow replay and outcome-informed comparison offline."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess

from code_engine.search.biological_unit_compatibility_v1_1 import (
    BiologicalUnitRegistryV1_1,
    decide_biological_unit_compatibility_v1_1,
)

if __package__:
    from . import audit_search_plan_v23_alpha1_1_biological_unit_refinement_offline as audit
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
else:
    import audit_search_plan_v23_alpha1_1_biological_unit_refinement_offline as audit
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1


ROOT = alpha1.ROOT
RUN = audit.RUN
STATUS = audit.STATUS
REGISTRY_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1_1.json"
POLICY_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1_1.json"
IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/biological_unit_compatibility_v1_1.py"
PRODUCTION_FILES = [IMPLEMENTATION_PATH, REGISTRY_OVERLAY_PATH, POLICY_OVERLAY_PATH]
V1_PROTECTED = {
    ROOT / "src/code_engine/search/biological_unit_compatibility_v1.py": "c47aac1ed2b3c4068ebe4b1fdaa8dbaf7d4884cfd615a7a2c0c294be45c6bdf0",
    alpha1.REGISTRY_PATH: "ec3cf188855230f5d6b8e2449d1fea383f4384122f655542bb0774fa1a282cfd",
    alpha1.POLICY_PATH: "2a2d4a8ac281114a1ca7cfa1c3c9553bbad75b3ecd1cc01d936845b0a74a0d21",
}
PHASE1_FILES = {
    "biological_unit_registry_v1_1_snapshot.json",
    "biological_unit_policy_v1_1_snapshot.json",
    "v23_alpha1_1_shadow_decisions.jsonl",
    "v23_alpha1_1_shadow_decisions_sha256",
}
REQUIRED = audit.AUDIT_FILES | PHASE1_FILES | {
    "alpha1_vs_alpha1_1_comparison.json",
    "counterfactual_policy_comparison.json",
    "heldout_specific_rule_audit.json",
    "implementation_manifest.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}
STATES = alpha1.COMPATIBILITY_STATES
ZERO_CALLS = alpha1.ZERO_CALLS


def tagged(payload):
    return {"development_status": STATUS, **payload}


def load_json(path):
    return json.loads(Path(path).read_bytes())


def verify_v1_immutability():
    for path, expected in V1_PROTECTED.items():
        alpha1.frozen.require(alpha1.frozen.sha256(path) == expected, f"immutable alpha1 source changed: {path}")
    return {str(path.relative_to(ROOT)): expected for path, expected in V1_PROTECTED.items()}


def alpha1_run_hashes():
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path)
            for path in sorted(alpha1.RUN.iterdir()) if path.is_file()}


def protected_hashes():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / name for name in tracked if name}
    for base in [alpha1.frozen.PROTOCOL, alpha1.frozen.REVIEW, alpha1.frozen.BLINDED,
                 alpha1.frozen.PASS_A, alpha1.frozen.PASS_B, alpha1.frozen.PRIMARY,
                 alpha1.frozen.RUN, alpha1.frozen.WORKSPACE, alpha1.ERROR_RUN, alpha1.RUN]:
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths.update(V1_PROTECTED)
    paths = {path for path in paths if not path.is_relative_to(RUN)}
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path) for path in sorted(paths)}


def build_phase1():
    base_registry = load_json(alpha1.REGISTRY_PATH)
    registry_overlay = load_json(REGISTRY_OVERLAY_PATH)
    base_policy = load_json(alpha1.POLICY_PATH)
    policy_overlay = load_json(POLICY_OVERLAY_PATH)
    alpha1.frozen.require(policy_overlay["enabled"] and policy_overlay["shadow_only"], "V1_1 must be shadow-only")
    alpha1.frozen.require(alpha1.frozen.sha256(alpha1.REGISTRY_PATH) == registry_overlay["base_registry_sha256"],
                          "V1_1 base registry mismatch")
    alpha1.frozen.require(alpha1.frozen.sha256(alpha1.POLICY_PATH) == policy_overlay["base_policy_sha256"],
                          "V1_1 base policy mismatch")
    registry = BiologicalUnitRegistryV1_1(base_registry, registry_overlay)
    inputs = alpha1.parse_preacquisition_batches()
    decisions = []
    for item in inputs:
        decision = decide_biological_unit_compatibility_v1_1(
            registry, base_policy, policy_overlay,
            item["scientific_target"]["context_qualifiers"],
            title=item["title"], abstract=item["abstract"],
            publication_metadata=item["publication_metadata"],
        )
        decisions.append({
            "artifact_schema_version": "BiologicalUnitCompatibilityDecisionV1_1",
            "search_plan_version": "v2.3-alpha1.1",
            "development_status": STATUS,
            "phase": "preacquisition_only_outcome_informed_development_shadow_replay",
            "packet_id": item["packet_id"],
            "preacquisition_input_sha256": alpha1.frozen.digest(alpha1.frozen.canonical_json(item)),
            "decision": asdict(decision),
            "shadow_only": True,
            "tier_change": False,
            "acquisition_change": False,
            "sample_change": False,
        })
    alpha1.frozen.require(len(decisions) == len({row["packet_id"] for row in decisions}) == 70,
                          "V1_1 shadow identity mismatch")
    body = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in decisions)
    digest = alpha1.frozen.digest(body)
    outputs = {
        "biological_unit_registry_v1_1_snapshot.json": alpha1._json(registry_overlay),
        "biological_unit_policy_v1_1_snapshot.json": alpha1._json(policy_overlay),
        "v23_alpha1_1_shadow_decisions.jsonl": body,
        "v23_alpha1_1_shadow_decisions_sha256": (digest + "\n").encode(),
    }
    return outputs, decisions, digest


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in PHASE1_FILES:
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == outputs[name],
                                  f"existing V1_1 phase1 differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        alpha1.frozen.require(alpha1.frozen.sha256(path) == alpha1.frozen.digest(outputs[name]),
                              f"V1_1 phase1 write verification failed: {name}")


def load_frozen_phase1():
    body = (RUN / "v23_alpha1_1_shadow_decisions.jsonl").read_bytes()
    digest = alpha1.frozen.digest(body)
    declared = (RUN / "v23_alpha1_1_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(digest == declared, "V1_1 frozen decision hash mismatch")
    records = [json.loads(line) for line in body.splitlines() if line]
    alpha1.frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                          "V1_1 frozen packet identity mismatch")
    return records, digest


def distribution(rows, decision_key="v1_1_decision"):
    counter = Counter(row[decision_key]["overall_state"] for row in rows)
    return {state: counter[state] for state in STATES}


def join_after_freeze(v1_1_records):
    alpha1_records, _ = alpha1.load_frozen_shadow_decisions()
    alpha1_by_id = {row["packet_id"]: row for row in alpha1_records}
    labels = alpha1.frozen.read_jsonl(alpha1.ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")
    labels_by_id = {row["packet_id"]: row for row in labels}
    ids = [row["packet_id"] for row in v1_1_records]
    alpha1.frozen.require(set(ids) == set(alpha1_by_id) == set(labels_by_id) and len(ids) == 70,
                          "comparison identity mismatch")
    return [{
        "packet_id": packet_id,
        "case_id": labels_by_id[packet_id]["case_id"],
        "tier": labels_by_id[packet_id]["tier"],
        "relevance_state": labels_by_id[packet_id]["relevance_state"],
        "contaminant_class": labels_by_id[packet_id]["contaminant_class"],
        "development_failure_families": labels_by_id[packet_id]["development_failure_families"],
        "alpha1_decision": alpha1_by_id[packet_id]["decision"],
        "v1_1_decision": next(row["decision"] for row in v1_1_records if row["packet_id"] == packet_id),
    } for packet_id in ids]


def group_comparison(rows, selection):
    return {
        "selection": selection,
        "N": len(rows),
        "alpha1_state_distribution": distribution(rows, "alpha1_decision"),
        "alpha1_1_state_distribution": distribution(rows),
    }


def build_comparison(joined):
    wrong = [row for row in joined if row["contaminant_class"] == "wrong_biological_unit"]
    direct = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    tier_a_direct = [row for row in direct if row["tier"] == "TIER_A"]
    tier_b_direct = [row for row in direct if row["tier"] == "TIER_B"]
    changed = [row for row in joined if row["alpha1_decision"]["overall_state"]
               != row["v1_1_decision"]["overall_state"]]
    return tagged({
        "analysis_name": "alpha1_vs_alpha1_1_comparison",
        "replay_interpretation": "outcome_informed_seen_development_comparison_not_validation",
        "all_70": group_comparison(joined, "all development packets"),
        "wrong_biological_unit_21": group_comparison(wrong, "frozen contaminant_class == wrong_biological_unit"),
        "directly_relevant_32": group_comparison(direct, "frozen relevance_state == DIRECTLY_RELEVANT"),
        "tier_a_direct": group_comparison(tier_a_direct, "Tier A and DIRECTLY_RELEVANT"),
        "tier_b_direct": group_comparison(tier_b_direct, "Tier B and DIRECTLY_RELEVANT"),
        "alpha1_direct_incompatible": sum(row["alpha1_decision"]["overall_state"] == "INCOMPATIBLE" for row in direct),
        "alpha1_1_direct_incompatible": sum(row["v1_1_decision"]["overall_state"] == "INCOMPATIBLE" for row in direct),
        "alpha1_wrong_unit_incompatible": sum(row["alpha1_decision"]["overall_state"] == "INCOMPATIBLE" for row in wrong),
        "alpha1_1_wrong_unit_incompatible": sum(row["v1_1_decision"]["overall_state"] == "INCOMPATIBLE" for row in wrong),
        "changed_packets": [{
            "packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
            "relevance_state": row["relevance_state"], "contaminant_class": row["contaminant_class"],
            "alpha1_state": row["alpha1_decision"]["overall_state"],
            "alpha1_1_state": row["v1_1_decision"]["overall_state"],
            "alpha1_1_applicable": row["v1_1_decision"]["applicability"]["applicable"],
        } for row in changed],
        "success_threshold_defined": False,
    })


def action_summary(rows, selected):
    direct = [row for row in selected if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    wrong = [row for row in selected if row["contaminant_class"] == "wrong_biological_unit"]
    return {
        "affected": len(selected),
        "affected_packet_ids": [row["packet_id"] for row in selected],
        "direct_papers_affected": len(direct),
        "wrong_unit_papers_affected": len(wrong),
        "by_tier": {tier: len([row for row in selected if row["tier"] == tier]) for tier in alpha1.frozen.TIERS},
        "per_case": {case: len([row for row in selected if row["case_id"] == case]) for case in alpha1.frozen.CASES},
        "population": len(rows),
    }


def build_counterfactual(joined):
    incompatible = [row for row in joined if row["v1_1_decision"]["overall_state"] == "INCOMPATIBLE"]
    tier_a_incompatible = [row for row in incompatible if row["tier"] == "TIER_A"]
    return tagged({
        "analysis_name": "counterfactual_policy_comparison",
        "candidate_a": {
            "action": "INCOMPATIBLE -> hard reject",
            "retained_papers": len(joined) - len(incompatible),
            "rejected_papers": len(incompatible),
            "rejection_effects": action_summary(joined, incompatible),
        },
        "candidate_b": {
            "action": "INCOMPATIBLE -> Tier A blocker/demote; no hard reject",
            "retained_papers": len(joined),
            "rejected_papers": 0,
            "demoted_papers": len(tier_a_incompatible),
            "demotion_effects": action_summary(joined, tier_a_incompatible),
        },
        "candidate_c": {
            "action": "retain and mark INCOMPATIBLE for later acquisition policy",
            "retained_papers": len(joined),
            "rejected_papers": 0,
            "marked_papers": len(incompatible),
            "marking_effects": action_summary(joined, incompatible),
        },
        "selected_for_production": None,
        "production_activation": False,
        "success_threshold_defined": False,
    })


def heldout_specific_rule_audit(joined):
    queries = alpha1.frozen.read_jsonl(alpha1.frozen.PROTOCOL / "heldout_frozen_queries.jsonl")
    primary = alpha1.frozen.read_jsonl(alpha1.frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
    forbidden = {row["case_id"] for row in joined} | {row["packet_id"] for row in joined}
    forbidden |= {row["query_family_id"] for row in queries} | {row["query_variant_id"] for row in queries}
    forbidden |= {str(row["source_identity"].get("pmid") or "") for row in primary}
    titles = {row["source_identity"]["title"] for row in primary}
    forbidden.discard("")
    findings = []
    branch = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id|title)\b")
    for path in PRODUCTION_FILES:
        text = path.read_text()
        tokens = sorted(token for token in forbidden if token in text)
        exact_titles = sorted(title for title in titles if title and title in text)
        branches = [line.strip() for line in text.splitlines() if branch.search(line)]
        if tokens or exact_titles or branches:
            findings.append({"path": str(path.relative_to(ROOT)), "forbidden_tokens": tokens,
                             "forbidden_titles": exact_titles, "identity_specific_branches": branches})
    return tagged({
        "analysis_name": "heldout_specific_rule_audit",
        "production_files_scanned": [str(path.relative_to(ROOT)) for path in PRODUCTION_FILES],
        "findings": findings,
        "production_case_specific_rules": len(findings),
        "development_tools_and_audit_fixtures_excluded": True,
    })


def build_phase2(frozen_v1_1, shadow_digest):
    joined = join_after_freeze(frozen_v1_1)
    comparison = build_comparison(joined)
    counterfactual = build_counterfactual(joined)
    rule_audit = heldout_specific_rule_audit(joined)
    alpha1.frozen.require(rule_audit["production_case_specific_rules"] == 0,
                          "held-out-specific V1_1 production rule detected")
    outputs = {
        "alpha1_vs_alpha1_1_comparison.json": alpha1._json(comparison),
        "counterfactual_policy_comparison.json": alpha1._json(counterfactual),
        "heldout_specific_rule_audit.json": alpha1._json(rule_audit),
        "implementation_manifest.json": alpha1._json(tagged({
            "search_plan_version": "v2.3-alpha1.1",
            "implementation": "BiologicalUnitCompatibilityV1_1",
            "integration_point": "code_engine.search.biological_unit_compatibility_v1_1.decide_biological_unit_compatibility_v1_1",
            "schemas": ["BiologicalUnitCompatibilityApplicabilityV1", "BiologicalUnitCompatibilityDecisionV1_1"],
            "production_files": [{"path": str(path.relative_to(ROOT)), "sha256": alpha1.frozen.sha256(path)}
                                 for path in PRODUCTION_FILES],
            "base_v1_sources_immutable": verify_v1_immutability(),
            "registry_relations_added_or_changed": [],
            "phase1_decisions_frozen_sha256": shadow_digest,
            "phase1_forbidden_sources_loaded": False,
            "outcome_informed_design": True,
            "production_rejection_enabled": False,
        })),
    }
    summary = {
        "status": "completed",
        "shadow_packet_count": 70,
        "shadow_unique_packet_ids": 70,
        "production_case_specific_rules": 0,
        "production_rejection_enabled": False,
        "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "alpha1_direct_incompatible": comparison["alpha1_direct_incompatible"],
        "alpha1_1_direct_incompatible": comparison["alpha1_1_direct_incompatible"],
        "alpha1_wrong_unit_incompatible": comparison["alpha1_wrong_unit_incompatible"],
        "alpha1_1_wrong_unit_incompatible": comparison["alpha1_1_wrong_unit_incompatible"],
        "v23_alpha1_1_shadow_decisions_sha256": shadow_digest,
        "v22_search_plan_modified": False,
        "alpha1_frozen_outputs_modified": False,
        **ZERO_CALLS,
    }
    return outputs, summary


def build_final(phase1, phase2, summary, before, after, alpha1_before, alpha1_after, audit_outputs):
    alpha1.frozen.require(before == after, "protected historical state changed")
    alpha1.frozen.require(alpha1_before == alpha1_after, "alpha1 frozen output changed")
    outputs = {**audit_outputs, **phase1, **phase2}
    outputs["scientific_state_safety_audit.json"] = alpha1._json(tagged({
        **ZERO_CALLS,
        "v22_search_plan_modified": False,
        "alpha1_frozen_outputs_modified": False,
        "production_rejection_enabled": False,
        "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "git_mutation_invoked": False,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "alpha1_run_hashes_before": alpha1_before,
        "alpha1_run_hashes_after": alpha1_after,
    }))
    outputs["validation.json"] = alpha1._json(tagged({
        "status": "PASS",
        "audit_frozen_before_v1_1_production_change": True,
        "audit_incompatible_packet_count": 11,
        "audit_unresolved_wrong_unit_packet_count": 12,
        "shadow_packet_count": 70,
        "shadow_unique_packet_ids": 70,
        "phase1_preacquisition_only": True,
        "phase1_labels_or_fulltext_loaded": False,
        "phase1_frozen_before_label_join": True,
        "v1_1_shadow_replay_byte_identical": True,
        "complete_output_replay_byte_identical": True,
        "all_results_seen_development_only": True,
        "success_threshold_defined": False,
        "production_case_specific_rules": 0,
        "production_rejection_enabled": False,
        "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "no_further_unit_tuning_on_seen_corpus": True,
        "new_heldout_v2_required": True,
    }))
    components = [{"path": name, "sha256": alpha1.frozen.digest(outputs[name])}
                  for name in sorted(outputs) if name != "implementation_manifest.json"]
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json([[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = alpha1._json({
        **json.loads(outputs["implementation_manifest.json"]),
        "upstream_alpha1_biological_unit_shadow_sha256": audit.ALPHA1_ROOT,
        "upstream_alpha1_shadow_decisions_sha256": audit.ALPHA1_SHADOW,
        "v23_alpha1_1_biological_unit_refinement_sha256": root,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required files except implementation_manifest.json and summary.json.",
    })
    outputs["summary.json"] = alpha1._json(tagged({
        **summary,
        "v23_alpha1_1_biological_unit_refinement_sha256": root,
        "output_file_count": len(REQUIRED),
        "overfitting_boundary": "No further biological-unit tuning on held-out-v1 after alpha1.1; use new held-out-v2.",
    }))
    alpha1.frozen.require(set(outputs) == REQUIRED, "V1_1 final output membership mismatch")
    return outputs


def write_complete(outputs):
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing V1_1 output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(alpha1.frozen.sha256(path) == alpha1.frozen.digest(body),
                              f"V1_1 output write verification failed: {name}")
    alpha1.frozen.require({path.name for path in RUN.iterdir()} == REQUIRED,
                          "V1_1 output run has unexpected files")


def generate_and_freeze():
    audit.verify_alpha1()
    verify_v1_immutability()
    audit_outputs = audit.build_audit_outputs()
    for name, body in audit_outputs.items():
        alpha1.frozen.require((RUN / name).read_bytes() == body, f"pre-code audit changed: {name}")
    before = protected_hashes()
    alpha1_before = alpha1_run_hashes()
    phase1_a, decisions_a, digest_a = build_phase1()
    phase1_b, decisions_b, digest_b = build_phase1()
    alpha1.frozen.require(phase1_a == phase1_b and decisions_a == decisions_b and digest_a == digest_b,
                          "V1_1 phase1 replay mismatch")
    freeze_phase1(phase1_a)
    frozen_records, frozen_digest = load_frozen_phase1()
    normalized = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in frozen_records)
    alpha1.frozen.require(normalized == phase1_a["v23_alpha1_1_shadow_decisions.jsonl"]
                          and frozen_digest == digest_a, "frozen V1_1 decisions differ")
    phase2_a, summary_a = build_phase2(frozen_records, frozen_digest)
    phase2_b, summary_b = build_phase2(frozen_records, frozen_digest)
    alpha1.frozen.require(phase2_a == phase2_b and summary_a == summary_b,
                          "V1_1 phase2 replay mismatch")
    after = protected_hashes()
    alpha1_after = alpha1_run_hashes()
    final_a = build_final(phase1_a, phase2_a, summary_a, before, after,
                          alpha1_before, alpha1_after, audit_outputs)
    final_b = build_final(phase1_b, phase2_b, summary_b, before, after,
                          alpha1_before, alpha1_after, audit_outputs)
    alpha1.frozen.require(final_a == final_b, "V1_1 complete output replay mismatch")
    write_complete(final_a)
    audit.verify_alpha1()
    alpha1.frozen.require(before == protected_hashes(), "protected state changed during V1_1 write")
    alpha1.frozen.require(alpha1_before == alpha1_run_hashes(), "alpha1 output changed during V1_1 write")
    return final_a


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("v1_1_shadow_replay_byte_identical=true")
    print("complete_output_replay_byte_identical=true")


if __name__ == "__main__":
    main()
