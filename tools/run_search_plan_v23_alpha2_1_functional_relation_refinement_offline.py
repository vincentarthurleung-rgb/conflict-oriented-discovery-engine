#!/usr/bin/env python3
"""Freeze alpha2.1 relation decisions, then run retrospective comparisons."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re

from code_engine.search.functional_relation_evidence_v1 import EVIDENCE_STATES
from code_engine.search.functional_relation_evidence_v1_1 import decide_functional_relation_evidence_v1_1
from code_engine.search.historical_manifest_verifier import verify_frozen_manifest

if __package__:
    from . import audit_search_plan_v23_alpha2_1_functional_relation_refinement_offline as audit
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    from . import run_search_plan_v23_alpha2_functional_relation_shadow_offline as alpha2
else:
    import audit_search_plan_v23_alpha2_1_functional_relation_refinement_offline as audit
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    import run_search_plan_v23_alpha2_functional_relation_shadow_offline as alpha2


ROOT = alpha1.ROOT
RUN = audit.RUN
STATUS = audit.STATUS
POLICY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json"
BASE_POLICY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json"
IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/functional_relation_evidence_v1_1.py"
BASE_IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/functional_relation_evidence_v1.py"
PRODUCTION_FILES = [IMPLEMENTATION_PATH, POLICY_PATH]
V1_PROTECTED = {
    BASE_IMPLEMENTATION_PATH: "9f962503566acdbd8d37587d73eef99a6211bf74f339116e1adefba335678e5f",
    BASE_POLICY_PATH: "70462b30f3620c3cc2f43b87bb98f0579aec70f525cf563c539ee9b892642c8d",
}
BLOCKER_STATES = ("ASSOCIATION_ONLY", "BACKGROUND_ONLY", "MULTI_TARGET_AMBIGUOUS")
PHASE1_FILES = {
    "functional_relation_policy_v1_1_snapshot.json",
    "v23_alpha2_1_relation_shadow_decisions.jsonl",
    "v23_alpha2_1_relation_shadow_decisions_sha256",
}
REQUIRED = audit.AUDIT_FILES | PHASE1_FILES | {
    "alpha2_vs_alpha2_1_comparison.json", "cross_module_shadow_analysis.json",
    "counterfactual_policy_comparison.json", "historical_manifest_regression_fix_audit.json",
    "heldout_specific_rule_audit.json", "implementation_manifest.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
}
ZERO_CALLS = alpha1.ZERO_CALLS


def load_json(path):
    return json.loads(Path(path).read_bytes())


def tagged(payload):
    return {"development_status": STATUS, **payload}


def verify_v1_immutability():
    result = {}
    for path, expected in V1_PROTECTED.items():
        actual = alpha1.frozen.sha256(path)
        alpha1.frozen.require(actual == expected, f"FunctionalRelationEvidenceV1 changed: {path}")
        result[str(path.relative_to(ROOT))] = actual
    return result


def tree_hashes(base):
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path)
            for path in sorted(base.rglob("*")) if path.is_file()}


def protected_state():
    audit.verify_upstreams()
    alpha1.verify_all_roots()
    verify_v1_immutability()
    return {
        "alpha1_1": tree_hashes(alpha1_1.RUN),
        "alpha2": tree_hashes(alpha2.RUN),
        "functional_relation_v1": verify_v1_immutability(),
    }


def build_phase1():
    base_policy = load_json(BASE_POLICY_PATH)
    policy = load_json(POLICY_PATH)
    alpha1.frozen.require(policy["enabled"] is True and policy["shadow_only"] is True,
                          "alpha2.1 must remain shadow-only")
    alpha1.frozen.require(policy["base_policy_sha256"] == V1_PROTECTED[BASE_POLICY_PATH],
                          "alpha2.1 base policy mismatch")
    decisions = []
    for item in alpha1.parse_preacquisition_batches():
        decision = decide_functional_relation_evidence_v1_1(
            item["packet_id"], item["scientific_target"], title=item["title"],
            abstract=item["abstract"], publication_metadata=item["publication_metadata"],
            base_policy=base_policy, policy=policy,
        )
        decisions.append({
            "artifact_schema_version": "FunctionalRelationEvidenceDecisionV1_1",
            "search_plan_version": "v2.3-alpha2.1",
            "development_status": STATUS,
            "phase": "preacquisition_only_outcome_informed_development_shadow_replay",
            "packet_id": item["packet_id"],
            "preacquisition_input_sha256": alpha1.frozen.digest(alpha1.frozen.canonical_json(item)),
            "decision": asdict(decision),
            "shadow_only": True, "tier_change": False, "acquisition_change": False,
            "sample_change": False, "reject_change": False,
        })
    alpha1.frozen.require(len(decisions) == len({row["packet_id"] for row in decisions}) == 70,
                          "alpha2.1 phase1 packet mismatch")
    body = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in decisions)
    digest = alpha1.frozen.digest(body)
    outputs = {
        "functional_relation_policy_v1_1_snapshot.json": alpha1._json(policy),
        "v23_alpha2_1_relation_shadow_decisions.jsonl": body,
        "v23_alpha2_1_relation_shadow_decisions_sha256": (digest + "\n").encode(),
    }
    return outputs, decisions, digest


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in PHASE1_FILES:
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == outputs[name],
                                  f"existing alpha2.1 phase1 differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        alpha1.frozen.require(path.is_file() and not path.is_symlink()
                              and path.read_bytes() == outputs[name],
                              f"alpha2.1 phase1 write verification failed: {name}")


def load_frozen_phase1():
    body = (RUN / "v23_alpha2_1_relation_shadow_decisions.jsonl").read_bytes()
    digest = alpha1.frozen.digest(body)
    declared = (RUN / "v23_alpha2_1_relation_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(digest == declared, "alpha2.1 frozen shadow hash mismatch")
    records = [json.loads(line) for line in body.splitlines() if line]
    alpha1.frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                          "alpha2.1 frozen shadow identity mismatch")
    return records, digest


def join_after_freeze(shadow):
    labels = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha1.ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")}
    prior = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha2.RUN / "v23_alpha2_relation_shadow_decisions.jsonl")}
    units = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha1_1.RUN / "v23_alpha1_1_shadow_decisions.jsonl")}
    ids = {row["packet_id"] for row in shadow}
    alpha1.frozen.require(ids == set(labels) == set(prior) == set(units) and len(ids) == 70,
                          "alpha2.1 retrospective join identity mismatch")
    return [{
        "packet_id": row["packet_id"], "alpha2_1_decision": row["decision"],
        "alpha2_decision": prior[row["packet_id"]]["decision"],
        "biological_unit_state": units[row["packet_id"]]["decision"]["overall_state"],
        "case_id": labels[row["packet_id"]]["case_id"], "tier": labels[row["packet_id"]]["tier"],
        "relevance_state": labels[row["packet_id"]]["relevance_state"],
        "contaminant_class": labels[row["packet_id"]]["contaminant_class"],
        "development_failure_families": labels[row["packet_id"]]["development_failure_families"],
    } for row in shadow]


def distribution(rows, decision_key):
    counts = Counter(row[decision_key]["evidence_state"] for row in rows)
    return {state: counts[state] for state in EVIDENCE_STATES}


def comparison_subset(name, selection, rows):
    transitions = Counter((row["alpha2_decision"]["evidence_state"],
                           row["alpha2_1_decision"]["evidence_state"]) for row in rows)
    return {
        "name": name, "selection": selection, "N": len(rows),
        "alpha2_state_counts": distribution(rows, "alpha2_decision"),
        "alpha2_1_state_counts": distribution(rows, "alpha2_1_decision"),
        "transitions": [{"alpha2": left, "alpha2_1": right, "count": count}
                        for (left, right), count in sorted(transitions.items())],
    }


def relation_blockers(rows, decision_key="alpha2_1_decision"):
    return [row for row in rows if row[decision_key]["evidence_state"] in BLOCKER_STATES]


def build_comparison(joined):
    direct = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    tier_a_direct = [row for row in direct if row["tier"] == "TIER_A"]
    tier_a_nondirect = [row for row in joined if row["tier"] == "TIER_A"
                        and row["relevance_state"] != "DIRECTLY_RELEVANT"]
    tier_b_direct = [row for row in direct if row["tier"] == "TIER_B"]
    unresolved_family = [row for row in joined
                         if "FUNCTIONAL_RELATION_UNRESOLVED" in row["development_failure_families"]]
    alpha1.frozen.require([len(joined), len(direct), len(tier_a_direct), len(tier_a_nondirect),
                           len(tier_b_direct), len(unresolved_family)] == [70, 32, 24, 11, 8, 24],
                          "alpha2.1 comparison population mismatch")
    return tagged({
        "analysis_name": "alpha2_vs_alpha2_1_comparison",
        "blocker_definition": list(BLOCKER_STATES), "unresolved_is_nonblocking": True,
        "subsets": {
            "all_70": comparison_subset("all_70", "all packets", joined),
            "direct_32": comparison_subset("direct_32", "DIRECTLY_RELEVANT", direct),
            "tier_a_direct_24": comparison_subset("tier_a_direct_24", "TIER_A and direct", tier_a_direct),
            "tier_a_nondirect_11": comparison_subset("tier_a_nondirect_11", "TIER_A and non-direct", tier_a_nondirect),
            "tier_b_direct_8": comparison_subset("tier_b_direct_8", "TIER_B and direct", tier_b_direct),
            "functional_relation_unresolved_24": comparison_subset(
                "functional_relation_unresolved_24", "frozen FUNCTIONAL_RELATION_UNRESOLVED family", unresolved_family),
        },
        "alpha2_direct_blocker_state": len(relation_blockers(direct, "alpha2_decision")),
        "alpha2_1_direct_blocker_state": len(relation_blockers(direct)),
        "alpha2_tier_a_direct_blocker_state": len(relation_blockers(tier_a_direct, "alpha2_decision")),
        "alpha2_1_tier_a_direct_blocker_state": len(relation_blockers(tier_a_direct)),
        "success_threshold_defined": False,
    })


def effect(population, affected):
    return {
        "total_affected": len(affected),
        "affected_packet_ids": [row["packet_id"] for row in affected],
        "direct_affected": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in affected),
        "tier_a_direct_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] == "DIRECTLY_RELEVANT" for row in affected),
        "tier_a_non_direct_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] != "DIRECTLY_RELEVANT" for row in affected),
        "tier_b_affected": sum(row["tier"] == "TIER_B" for row in affected),
        "per_case_effects": {case: sum(row["case_id"] == case for row in affected)
                             for case in alpha1.frozen.CASES},
        "unaffected": len(population) - len(affected),
    }


def build_counterfactual(joined):
    weak = relation_blockers(joined)
    tier_a_weak = [row for row in weak if row["tier"] == "TIER_A"]
    background = [row for row in joined if row["alpha2_1_decision"]["evidence_state"] == "BACKGROUND_ONLY"]
    return tagged({
        "analysis_name": "counterfactual_policy_comparison",
        "candidate_a": {"policy": "block blocker states from Tier A", "effects": effect(joined, tier_a_weak)},
        "candidate_b": {"policy": "mark blocker states relation-weak but retain", "effects": effect(joined, weak)},
        "candidate_c": {"policy": "BACKGROUND_ONLY hard reject only", "effects": effect(joined, background)},
        "selected_for_production": None, "production_activation": False,
        "success_threshold_defined": False,
    })


def build_cross_module(joined):
    blocker_rows = relation_blockers(joined)
    compatible_states = {"EXACT", "AUTHORIZED_COMPATIBLE"}
    groups = {
        "biological_unit_incompatible_plus_relation_blocker": [row for row in blocker_rows if row["biological_unit_state"] == "INCOMPATIBLE"],
        "biological_unit_unresolved_plus_relation_blocker": [row for row in blocker_rows if row["biological_unit_state"] == "UNRESOLVED"],
        "biological_unit_compatible_plus_relation_blocker": [row for row in blocker_rows if row["biological_unit_state"] in compatible_states],
    }
    return tagged({
        "analysis_name": "cross_module_shadow_analysis", "cross_module_precedence_created": False,
        "composite_score_created": False,
        "groups": {name: {"count": len(rows), "packet_ids": [row["packet_id"] for row in rows],
                          "relation_state_counts": distribution(rows, "alpha2_1_decision")}
                   for name, rows in groups.items()},
    })


def heldout_specific_rule_audit(joined):
    queries = alpha1.frozen.read_jsonl(alpha1.frozen.PROTOCOL / "heldout_frozen_queries.jsonl")
    primary = alpha1.frozen.read_jsonl(alpha1.frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
    inputs = alpha1.parse_preacquisition_batches()
    forbidden = {row["case_id"] for row in joined} | {row["packet_id"] for row in joined}
    forbidden |= {row["query_family_id"] for row in queries} | {row["query_variant_id"] for row in queries}
    forbidden |= {str(row["source_identity"].get("pmid") or "") for row in primary}
    titles = {row["source_identity"]["title"] for row in primary}
    entities = {str(item["scientific_target"].get(key) or "") for item in inputs for key in ("subject", "object")}
    forbidden.discard("")
    branch = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id)\b")
    findings = []
    for path in PRODUCTION_FILES:
        text = path.read_text()
        tokens = sorted(token for token in forbidden if token in text)
        found_titles = sorted(title for title in titles if title and title in text)
        names = sorted(name for name in entities if len(name) >= 4 and name in text)
        branches = [line.strip() for line in text.splitlines() if branch.search(line)]
        if tokens or found_titles or names or branches:
            findings.append({"path": str(path.relative_to(ROOT)), "forbidden_tokens": tokens,
                             "forbidden_titles": found_titles, "case_entity_names": names,
                             "identity_specific_branches": branches})
    return tagged({
        "analysis_name": "heldout_specific_rule_audit",
        "production_files_scanned": [str(path.relative_to(ROOT)) for path in PRODUCTION_FILES],
        "findings": findings, "production_case_specific_rules": len(findings),
        "development_audit_fixtures_excluded": True,
    })


def historical_manifest_audit():
    manifest_path = alpha1_1.RUN / "implementation_manifest.json"
    before = alpha1.frozen.sha256(manifest_path)
    result = verify_frozen_manifest(
        alpha1_1.RUN, root_field="v23_alpha1_1_biological_unit_refinement_sha256")
    after = alpha1.frozen.sha256(manifest_path)
    alpha1.frozen.require(before == after and result["aggregate_sha256"] == audit.ALPHA1_1_ROOT,
                          "historical alpha1.1 verification failed")
    return tagged({
        "analysis_name": "historical_manifest_regression_fix_audit", "status": "PASS",
        "historical_manifest_sha256_before": before, "historical_manifest_sha256_after": after,
        "historical_manifest_modified": False, "historical_aggregate_hashes_unchanged": True,
        "verified_aggregate_sha256": result["aggregate_sha256"],
        "protected_file_count": result["protected_file_count"],
        "membership_source": result["membership_source"],
        "current_repository_membership_enumerated": False,
        "generic_regression_tests": [
            "later new tracked file does not invalidate historical freeze",
            "historical protected file modification fails", "historical protected file deletion fails",
            "historical protected file replacement fails", "original historical aggregate hashes still verify",
        ],
    })


def build_phase2(frozen_shadow, shadow_digest):
    joined = join_after_freeze(frozen_shadow)
    comparison = build_comparison(joined)
    counterfactual = build_counterfactual(joined)
    cross_module = build_cross_module(joined)
    rules = heldout_specific_rule_audit(joined)
    historical = historical_manifest_audit()
    alpha1.frozen.require(rules["production_case_specific_rules"] == 0,
                          "held-out-specific alpha2.1 production rule detected")
    outputs = {
        "alpha2_vs_alpha2_1_comparison.json": alpha1._json(comparison),
        "cross_module_shadow_analysis.json": alpha1._json(cross_module),
        "counterfactual_policy_comparison.json": alpha1._json(counterfactual),
        "historical_manifest_regression_fix_audit.json": alpha1._json(historical),
        "heldout_specific_rule_audit.json": alpha1._json(rules),
        "implementation_manifest.json": alpha1._json(tagged({
            "search_plan_version": "v2.3-alpha2.1",
            "functional_relation_evidence_version": "FunctionalRelationEvidenceV1_1",
            "integration_point": "code_engine.search.functional_relation_evidence_v1_1.decide_functional_relation_evidence_v1_1",
            "production_files": [{"path": str(path.relative_to(ROOT)), "sha256": alpha1.frozen.sha256(path)}
                                 for path in PRODUCTION_FILES],
            "base_v1_sources_immutable": verify_v1_immutability(),
            "phase1_decisions_frozen_sha256": shadow_digest,
            "phase1_forbidden_sources_loaded": False, "outcome_informed_design": True,
            "shadow_only": True, "production_rejection_enabled": False,
        })),
    }
    summary = {
        "status": "completed", "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "production_case_specific_rules": 0, "production_rejection_enabled": False,
        "production_tier_behavior_changed": False, "production_acquisition_behavior_changed": False,
        "alpha2_direct_blocker_state": comparison["alpha2_direct_blocker_state"],
        "alpha2_1_direct_blocker_state": comparison["alpha2_1_direct_blocker_state"],
        "alpha2_tier_a_direct_blocker_state": comparison["alpha2_tier_a_direct_blocker_state"],
        "alpha2_1_tier_a_direct_blocker_state": comparison["alpha2_1_tier_a_direct_blocker_state"],
        "v23_alpha2_1_relation_shadow_decisions_sha256": shadow_digest,
        "historical_alpha1_1_manifest_modified": False, "historical_alpha1_1_hashes_unchanged": True,
        "v22_search_plan_modified": False, "alpha1_1_modified": False,
        "alpha2_frozen_outputs_modified": False, **ZERO_CALLS,
    }
    return outputs, summary


def build_final(phase1, phase2, summary, before, after, audit_outputs):
    alpha1.frozen.require(before == after, "protected upstream state changed")
    outputs = {**audit_outputs, **phase1, **phase2}
    outputs["scientific_state_safety_audit.json"] = alpha1._json(tagged({
        **ZERO_CALLS, "production_rejection_enabled": False,
        "production_tier_behavior_changed": False, "production_acquisition_behavior_changed": False,
        "v22_search_plan_modified": False, "alpha1_1_modified": False,
        "alpha2_frozen_outputs_modified": False, "historical_manifests_modified": False,
        "git_mutation_invoked": False, "protected_state_before": before, "protected_state_after": after,
    }))
    outputs["validation.json"] = alpha1._json(tagged({
        "status": "PASS", "audit_frozen_before_v1_1_production_files": True,
        "direct_blocker_audit_count": 14, "direct_unresolved_audit_count": 15,
        "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "phase1_preacquisition_only": True, "phase1_forbidden_sources_loaded": False,
        "phase1_frozen_before_retrospective_join": True,
        "v1_1_replay_byte_identical": True, "complete_output_replay_byte_identical": True,
        "exact_six_evidence_states": True, "unresolved_is_nonblocking": True,
        "production_case_specific_rules": 0, "shadow_only": True,
        "relation_tuning_closed_on_heldout_v1": True, "heldout_v2_required": True,
        "success_threshold_defined": False, "cross_module_precedence_created": False,
    }))
    components = [{"path": name, "sha256": alpha1.frozen.digest(outputs[name])}
                  for name in sorted(outputs) if name != "implementation_manifest.json"]
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json(
        [[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = alpha1._json({
        **json.loads(outputs["implementation_manifest.json"]),
        "upstream_roots": audit.verify_upstreams(),
        "v23_alpha2_1_functional_relation_refinement_sha256": root,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required artifacts except implementation_manifest.json and summary.json.",
    })
    outputs["summary.json"] = alpha1._json(tagged({
        **summary, "v23_alpha2_1_functional_relation_refinement_sha256": root,
        "output_file_count": len(REQUIRED),
        "overfitting_boundary": "Functional Relation Evidence tuning is closed on held-out-v1; validate on held-out-v2.",
    }))
    alpha1.frozen.require(set(outputs) == REQUIRED and len(outputs) == 19,
                          "alpha2.1 final output membership mismatch")
    return outputs


def write_complete(outputs):
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing alpha2.1 output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                              f"alpha2.1 output write verification failed: {name}")
    alpha1.frozen.require({path.name for path in RUN.iterdir()} == REQUIRED,
                          "alpha2.1 output run has unexpected files")


def generate_and_freeze():
    audit_outputs = audit.build_outputs()
    for name, body in audit_outputs.items():
        alpha1.frozen.require((RUN / name).read_bytes() == body, f"frozen audit changed: {name}")
    before = protected_state()
    phase1_a, decisions_a, digest_a = build_phase1()
    phase1_b, decisions_b, digest_b = build_phase1()
    alpha1.frozen.require(phase1_a == phase1_b and decisions_a == decisions_b and digest_a == digest_b,
                          "alpha2.1 phase1 replay mismatch")
    freeze_phase1(phase1_a)
    frozen_shadow, frozen_digest = load_frozen_phase1()
    normalized = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in frozen_shadow)
    alpha1.frozen.require(normalized == phase1_a["v23_alpha2_1_relation_shadow_decisions.jsonl"]
                          and frozen_digest == digest_a, "alpha2.1 frozen decision mismatch")
    phase2_a, summary_a = build_phase2(frozen_shadow, frozen_digest)
    phase2_b, summary_b = build_phase2(frozen_shadow, frozen_digest)
    alpha1.frozen.require(phase2_a == phase2_b and summary_a == summary_b,
                          "alpha2.1 retrospective analysis replay mismatch")
    after = protected_state()
    final_a = build_final(phase1_a, phase2_a, summary_a, before, after, audit_outputs)
    final_b = build_final(phase1_b, phase2_b, summary_b, before, after, audit_outputs)
    alpha1.frozen.require(final_a == final_b, "alpha2.1 complete output replay mismatch")
    write_complete(final_a)
    alpha1.frozen.require(before == protected_state(), "protected state changed during alpha2.1 write")
    return final_a


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("v1_1_shadow_replay_byte_identical=true")
    print("complete_output_replay_byte_identical=true")


if __name__ == "__main__":
    main()
