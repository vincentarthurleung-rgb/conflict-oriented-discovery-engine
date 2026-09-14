#!/usr/bin/env python3
"""Freeze EndpointSemanticsV1 shadow decisions before retrospective analysis."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re

from code_engine.search.endpoint_semantics_v1 import ENDPOINT_STATES, decide_endpoint_semantics_v1
from code_engine.search.historical_manifest_verifier import verify_frozen_manifest

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    from . import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
    import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as alpha2_1


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260915_search_plan_v23_alpha3_endpoint_semantics_shadow_offline"
REGISTRY_PATH = ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json"
POLICY_PATH = ROOT / "configs/search_plans/endpoint_semantics_policy_v1.json"
IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/endpoint_semantics_v1.py"
PRODUCTION_FILES = [IMPLEMENTATION_PATH, REGISTRY_PATH, POLICY_PATH]
STATUS = "seen_heldout_v1_retrospective_development_only"
ERROR_ROOT = "8e18a61200f22108f4f24b66ee72d6e2ecd11a32220eb0142d4a48552f4eaa9b"
ALPHA1_1_ROOT = "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c"
ALPHA2_1_ROOT = "fc5b98266996235995595ad6c097dc433ef0345d6023cda4e5deaa55a32e12b3"
ALPHA2_1_SHADOW = "50865556b923567a1e03f270659d263690d444e4934fd51a6183332ae41cf4e3"
ALPHA2_1_PROTECTED = {
    ROOT / "src/code_engine/search/functional_relation_evidence_v1_1.py": "7dfae2624218e98b16c8605d412b6dbb39ec4afb2b84076d7310fc99eff2cadd",
    ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json": "eac34b30fdf25490153dcfcc539e80244c851e79c4d7a7203bc78b44c509eda2",
}
RELATION_BLOCKERS = {"ASSOCIATION_ONLY", "BACKGROUND_ONLY", "MULTI_TARGET_AMBIGUOUS"}
ZERO_CALLS = alpha1.ZERO_CALLS
PHASE1_FILES = {
    "endpoint_semantics_registry_snapshot.json", "endpoint_semantics_policy_snapshot.json",
    "v23_alpha3_endpoint_shadow_decisions.jsonl", "v23_alpha3_endpoint_shadow_decisions_sha256",
    "shadow_decision_validation.json",
}
REQUIRED = PHASE1_FILES | {
    "endpoint_mismatch_capture.json", "endpoint_mismatch_audit.json", "endpoint_mismatch_audit.md",
    "direct_paper_safety_analysis.json", "tier_a_direct_safety_analysis.json",
    "tier_a_nondirect_endpoint_analysis.json", "tier_b_endpoint_analysis.json",
    "per_case_endpoint_analysis.json", "cross_module_shadow_analysis.json",
    "counterfactual_policy_comparison.json", "heldout_specific_rule_audit.json",
    "implementation_manifest.json", "scientific_state_safety_audit.json", "validation.json", "summary.json",
}


def load_json(path):
    return json.loads(Path(path).read_bytes())


def tagged(payload):
    return {"development_status": STATUS, **payload}


def tree_hashes(base):
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path)
            for path in sorted(base.rglob("*")) if path.is_file()}


def verify_upstreams():
    roots = alpha1.verify_all_roots()
    alpha1.frozen.require(roots["v22_to_v23_error_analysis_sha256"]["actual"] == ERROR_ROOT,
                          "error-analysis root mismatch")
    alpha1_1_result = verify_frozen_manifest(
        alpha1_1.RUN, root_field="v23_alpha1_1_biological_unit_refinement_sha256")
    alpha2_1_result = verify_frozen_manifest(
        alpha2_1.RUN, root_field="v23_alpha2_1_functional_relation_refinement_sha256")
    shadow = alpha1.frozen.sha256(alpha2_1.RUN / "v23_alpha2_1_relation_shadow_decisions.jsonl")
    alpha1.frozen.require(alpha1_1_result["aggregate_sha256"] == ALPHA1_1_ROOT,
                          "alpha1.1 root mismatch")
    alpha1.frozen.require(alpha2_1_result["aggregate_sha256"] == ALPHA2_1_ROOT,
                          "alpha2.1 root mismatch")
    alpha1.frozen.require(shadow == ALPHA2_1_SHADOW, "alpha2.1 shadow mismatch")
    for path, expected in ALPHA2_1_PROTECTED.items():
        alpha1.frozen.require(alpha1.frozen.sha256(path) == expected,
                              f"FunctionalRelationEvidenceV1_1 changed: {path}")
    return {
        "v22_to_v23_error_analysis_sha256": ERROR_ROOT,
        "v23_alpha1_1_biological_unit_refinement_sha256": alpha1_1_result["aggregate_sha256"],
        "v23_alpha2_1_functional_relation_refinement_sha256": alpha2_1_result["aggregate_sha256"],
        "v23_alpha2_1_relation_shadow_decisions_sha256": shadow,
    }


def protected_state():
    verify_upstreams()
    return {
        "v22_error_analysis": tree_hashes(alpha1.ERROR_RUN),
        "alpha1_1": tree_hashes(alpha1_1.RUN),
        "alpha2_1": tree_hashes(alpha2_1.RUN),
        "alpha2_1_production": {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path)
                                for path in ALPHA2_1_PROTECTED},
    }


def build_phase1():
    registry = load_json(REGISTRY_PATH)
    policy = load_json(POLICY_PATH)
    alpha1.frozen.require(policy["enabled"] is True and policy["shadow_only"] is True,
                          "EndpointSemanticsV1 must remain shadow-only")
    inputs = alpha1.parse_preacquisition_batches()
    decisions = []
    for item in inputs:
        decision = decide_endpoint_semantics_v1(
            item["packet_id"], item["scientific_target"], title=item["title"],
            abstract=item["abstract"], publication_metadata=item["publication_metadata"],
            registry=registry, policy=policy,
        )
        decisions.append({
            "artifact_schema_version": "EndpointSemanticDecisionV1",
            "search_plan_version": "v2.3-alpha3",
            "endpoint_semantics_version": "v1",
            "phase": "preacquisition_only_endpoint_semantics_shadow_inference",
            "packet_id": item["packet_id"],
            "preacquisition_input_sha256": alpha1.frozen.digest(alpha1.frozen.canonical_json(item)),
            "decision": asdict(decision), "shadow_only": True,
            "tier_change": False, "acquisition_change": False,
            "sample_change": False, "reject_change": False,
        })
    alpha1.frozen.require(len(decisions) == len({row["packet_id"] for row in decisions}) == 70,
                          "alpha3 phase1 identity mismatch")
    body = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in decisions)
    digest = alpha1.frozen.digest(body)
    counts = Counter(row["decision"]["overall_state"] for row in decisions)
    validation = {
        "phase": "preacquisition_only_endpoint_semantics_shadow_inference", "status": "PASS",
        "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "endpoint_shadow_decisions_sha256": digest,
        "endpoint_state_counts": {state: counts[state] for state in ENDPOINT_STATES},
        "decision_input_fields": ["ScientificPropositionTargetV1", "title", "abstract", "publication_metadata"],
        "pass_a_labels_loaded": False, "pass_b_loaded": False, "relevance_state_loaded": False,
        "contaminant_class_loaded": False, "evaluator_rationale_loaded": False,
        "fulltext_loaded": False, "development_failure_families_loaded": False,
        "heldout_metrics_loaded": False, "tier_loaded": False, "shadow_only": True,
        "tier_changes": 0, "acquisition_changes": 0, "sample_changes": 0, "reject_changes": 0,
        **ZERO_CALLS,
    }
    return {
        "endpoint_semantics_registry_snapshot.json": alpha1._json(registry),
        "endpoint_semantics_policy_snapshot.json": alpha1._json(policy),
        "v23_alpha3_endpoint_shadow_decisions.jsonl": body,
        "v23_alpha3_endpoint_shadow_decisions_sha256": (digest + "\n").encode(),
        "shadow_decision_validation.json": alpha1._json(validation),
    }, decisions, digest


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in PHASE1_FILES:
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == outputs[name],
                                  f"existing alpha3 phase1 differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        alpha1.frozen.require(path.is_file() and not path.is_symlink() and path.read_bytes() == outputs[name],
                              f"alpha3 phase1 write verification failed: {name}")


def load_frozen_phase1():
    body = (RUN / "v23_alpha3_endpoint_shadow_decisions.jsonl").read_bytes()
    digest = alpha1.frozen.digest(body)
    declared = (RUN / "v23_alpha3_endpoint_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(digest == declared, "alpha3 frozen decision hash mismatch")
    records = [json.loads(line) for line in body.splitlines() if line]
    alpha1.frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                          "alpha3 frozen decision identity mismatch")
    return records, digest


def join_after_freeze(shadow):
    labels = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha1.ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")}
    units = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha1_1.RUN / "v23_alpha1_1_shadow_decisions.jsonl")}
    relations = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(
        alpha2_1.RUN / "v23_alpha2_1_relation_shadow_decisions.jsonl")}
    ids = {row["packet_id"] for row in shadow}
    alpha1.frozen.require(ids == set(labels) == set(units) == set(relations) and len(ids) == 70,
                          "alpha3 retrospective join identity mismatch")
    return [{
        "packet_id": row["packet_id"], "endpoint_decision": row["decision"],
        "biological_unit_state": units[row["packet_id"]]["decision"]["overall_state"],
        "functional_relation_state": relations[row["packet_id"]]["decision"]["evidence_state"],
        "case_id": labels[row["packet_id"]]["case_id"], "tier": labels[row["packet_id"]]["tier"],
        "relevance_state": labels[row["packet_id"]]["relevance_state"],
        "contaminant_class": labels[row["packet_id"]]["contaminant_class"],
        "development_failure_families": labels[row["packet_id"]]["development_failure_families"],
    } for row in shadow]


def state_distribution(rows):
    counts = Counter(row["endpoint_decision"]["overall_state"] for row in rows)
    return {state: counts[state] for state in ENDPOINT_STATES}


def subset(name, selection, rows):
    return tagged({
        "analysis_name": name, "selection": selection, "N": len(rows),
        "endpoint_state_counts": state_distribution(rows),
        "packet_ids_by_state": {state: [row["packet_id"] for row in rows
                                         if row["endpoint_decision"]["overall_state"] == state]
                                for state in ENDPOINT_STATES},
    })


def build_endpoint_mismatch(joined):
    rows = [row for row in joined if "ENDPOINT_MISMATCH" in row["development_failure_families"]]
    alpha1.frozen.require(len(rows) == 9, "frozen endpoint-mismatch count changed")
    capture = subset("endpoint_mismatch_capture", "frozen ENDPOINT_MISMATCH development family", rows)
    records = []
    for row in rows:
        decision = row["endpoint_decision"]
        states = {
            "measurement_entity": decision["entity_state"],
            "measurement_property": decision["property_state"],
            "measurement_process": decision["process_state"],
            "measurement_state": decision["molecular_state_state"],
            "measurement_compartment": decision["compartment_state"],
            "measurement_condition": decision["condition_state"],
            "response_context": decision["response_context_state"],
        }
        incompatible = [name for name, state in states.items() if state == "INCOMPATIBLE"]
        unresolved = [name for name, state in states.items() if state == "UNRESOLVED"]
        if decision["overall_state"] == "INCOMPATIBLE":
            detectability, visible = "DETECTABLE_PREACQUISITION", True
        elif decision["overall_state"] == "PARTIAL":
            detectability, visible = "PARTIALLY_DETECTABLE_PREACQUISITION", True
        else:
            detectability, visible = "NOT_SAFELY_DETECTABLE_PREACQUISITION", False
        records.append({
            "packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
            "target_endpoint_dimensions": decision["target_endpoint_spec"],
            "observed_endpoint_dimensions": decision["observed_endpoint_candidates"],
            "dimension_states": states, "incompatible_dimensions": incompatible,
            "unresolved_dimensions": unresolved, "alpha3_overall_state": decision["overall_state"],
            "reason_codes": decision["reason_codes"],
            "mismatch_visible_from_preacquisition_evidence": visible,
            "retrospective_detectability": detectability,
        })
    detectability_counts = Counter(row["retrospective_detectability"] for row in records)
    audit = tagged({
        "analysis_name": "endpoint_mismatch_audit", "packet_count": 9,
        "endpoint_state_counts": state_distribution(rows),
        "detectability_counts": dict(sorted(detectability_counts.items())),
        "rules_modified_after_audit": False, "records": records,
    })
    lines = ["# Endpoint mismatch audit", "", f"development_status: `{STATUS}`", "", "packet_count: 9", ""]
    for record in records:
        lines.extend([
            f"## {record['packet_id']}", "",
            f"- case/tier: `{record['case_id']}` / `{record['tier']}`",
            f"- alpha3 state: `{record['alpha3_overall_state']}`",
            f"- detectability: `{record['retrospective_detectability']}`",
            f"- incompatible dimensions: `{', '.join(record['incompatible_dimensions']) or 'none'}`",
            f"- unresolved dimensions: `{', '.join(record['unresolved_dimensions']) or 'none'}`", "",
        ])
    return capture, audit, ("\n".join(lines) + "\n").encode()


def build_direct_safety(joined):
    rows = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 32, "direct-paper count mismatch")
    result = subset("direct_paper_safety_analysis", "DIRECTLY_RELEVANT", rows)
    result["potential_false_blockers"] = [
        {"packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
         "reason_codes": row["endpoint_decision"]["reason_codes"]}
        for row in rows if row["endpoint_decision"]["overall_state"] == "INCOMPATIBLE"
    ]
    result["partial_and_unresolved_are_not_blockers"] = True
    return result


def build_tier_a_direct(joined):
    rows = [row for row in joined if row["tier"] == "TIER_A"
            and row["relevance_state"] == "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 24, "Tier A direct count mismatch")
    result = subset("tier_a_direct_safety_analysis", "Tier A and DIRECTLY_RELEVANT", rows)
    result["tier_a_direct_incompatible"] = [row["packet_id"] for row in rows
                                             if row["endpoint_decision"]["overall_state"] == "INCOMPATIBLE"]
    return result


def build_tier_a_nondirect(joined):
    rows = [row for row in joined if row["tier"] == "TIER_A"
            and row["relevance_state"] != "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 11, "Tier A non-direct count mismatch")
    return subset("tier_a_nondirect_endpoint_analysis", "Tier A and non-direct", rows)


def build_tier_b(joined):
    rows = [row for row in joined if row["tier"] == "TIER_B"]
    direct = [row for row in rows if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(direct) == 8, "Tier B direct count mismatch")
    return tagged({
        "analysis_name": "tier_b_endpoint_analysis",
        "tier_b_all": subset("tier_b_all", "Tier B", rows),
        "tier_b_direct": subset("tier_b_direct", "Tier B and direct", direct),
    })


def build_per_case(joined):
    return tagged({
        "analysis_name": "per_case_endpoint_analysis",
        "cases": {case: subset("per_case", f"case_id == {case}",
                               [row for row in joined if row["case_id"] == case])
                  for case in alpha1.frozen.CASES},
    })


def build_cross_module(joined):
    endpoint_incompatible = [row for row in joined if row["endpoint_decision"]["overall_state"] == "INCOMPATIBLE"]
    endpoint_uncertain = [row for row in joined if row["endpoint_decision"]["overall_state"] in {"PARTIAL", "UNRESOLVED"}]
    relation_weak = lambda row: row["functional_relation_state"] in RELATION_BLOCKERS
    groups = {
        "endpoint_incompatible_plus_biological_unit_incompatible": [row for row in endpoint_incompatible if row["biological_unit_state"] == "INCOMPATIBLE"],
        "endpoint_incompatible_plus_relation_blocker": [row for row in endpoint_incompatible if relation_weak(row)],
        "endpoint_partial_or_unresolved_plus_relation_blocker": [row for row in endpoint_uncertain if relation_weak(row)],
    }
    cube = Counter((row["endpoint_decision"]["overall_state"], row["biological_unit_state"],
                    row["functional_relation_state"]) for row in joined)
    return tagged({
        "analysis_name": "cross_module_shadow_analysis", "precedence_implemented": False,
        "composite_score_created": False, "final_tier_rule_created": False,
        "groups": {name: {"count": len(rows), "packet_ids": [row["packet_id"] for row in rows]}
                   for name, rows in groups.items()},
        "endpoint_biological_unit_relation_cube": [
            {"endpoint_state": key[0], "biological_unit_state": key[1],
             "functional_relation_state": key[2], "count": count}
            for key, count in sorted(cube.items())
        ],
    })


def effect(population, affected):
    return {
        "total_affected": len(affected), "affected_packet_ids": [row["packet_id"] for row in affected],
        "direct_affected": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in affected),
        "tier_a_direct_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] == "DIRECTLY_RELEVANT" for row in affected),
        "tier_a_non_direct_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] != "DIRECTLY_RELEVANT" for row in affected),
        "tier_b_affected": sum(row["tier"] == "TIER_B" for row in affected),
        "endpoint_mismatch_affected": sum("ENDPOINT_MISMATCH" in row["development_failure_families"] for row in affected),
        "per_case_effects": {case: sum(row["case_id"] == case for row in affected)
                             for case in alpha1.frozen.CASES},
        "unaffected": len(population) - len(affected),
    }


def build_counterfactual(joined):
    incompatible = [row for row in joined if row["endpoint_decision"]["overall_state"] == "INCOMPATIBLE"]
    tier_a = [row for row in incompatible if row["tier"] == "TIER_A"]
    return tagged({
        "analysis_name": "counterfactual_policy_comparison",
        "candidate_a": {"policy": "INCOMPATIBLE blocks Tier A eligibility", "effects": effect(joined, tier_a)},
        "candidate_b": {"policy": "INCOMPATIBLE marks endpoint-weak and retains", "effects": effect(joined, incompatible)},
        "candidate_c": {"policy": "INCOMPATIBLE hard rejects", "effects": effect(joined, incompatible)},
        "selected_for_production": None, "production_activation": False,
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
    branch = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id)\b")
    findings = []
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
        "findings": findings, "production_case_specific_rules": len(findings),
        "development_analysis_files_excluded": True,
    })


def build_phase2(shadow, shadow_digest):
    joined = join_after_freeze(shadow)
    capture, mismatch_audit, mismatch_md = build_endpoint_mismatch(joined)
    direct = build_direct_safety(joined)
    tier_a_direct = build_tier_a_direct(joined)
    tier_a_nondirect = build_tier_a_nondirect(joined)
    tier_b = build_tier_b(joined)
    per_case = build_per_case(joined)
    cross = build_cross_module(joined)
    counterfactual = build_counterfactual(joined)
    rules = heldout_specific_rule_audit(joined)
    alpha1.frozen.require(rules["production_case_specific_rules"] == 0,
                          "held-out-specific EndpointSemanticsV1 production rule detected")
    outputs = {
        "endpoint_mismatch_capture.json": alpha1._json(capture),
        "endpoint_mismatch_audit.json": alpha1._json(mismatch_audit),
        "endpoint_mismatch_audit.md": mismatch_md,
        "direct_paper_safety_analysis.json": alpha1._json(direct),
        "tier_a_direct_safety_analysis.json": alpha1._json(tier_a_direct),
        "tier_a_nondirect_endpoint_analysis.json": alpha1._json(tier_a_nondirect),
        "tier_b_endpoint_analysis.json": alpha1._json(tier_b),
        "per_case_endpoint_analysis.json": alpha1._json(per_case),
        "cross_module_shadow_analysis.json": alpha1._json(cross),
        "counterfactual_policy_comparison.json": alpha1._json(counterfactual),
        "heldout_specific_rule_audit.json": alpha1._json(rules),
        "implementation_manifest.json": alpha1._json(tagged({
            "search_plan_version": "v2.3-alpha3", "endpoint_semantics_version": "v1",
            "schema": ["EndpointSemanticRefV1", "EndpointTargetSpecV1", "EndpointSemanticDecisionV1"],
            "integration_point": "code_engine.search.endpoint_semantics_v1.decide_endpoint_semantics_v1",
            "production_files": [{"path": str(path.relative_to(ROOT)), "sha256": alpha1.frozen.sha256(path)}
                                 for path in PRODUCTION_FILES],
            "phase1_decisions_frozen_sha256": shadow_digest,
            "phase1_forbidden_sources_loaded": False, "shadow_only": True,
            "production_rejection_enabled": False,
        })),
    }
    summary = {
        "status": "completed", "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "shadow_only": True, "tier_changes": 0, "acquisition_changes": 0,
        "sample_changes": 0, "reject_changes": 0, "production_case_specific_rules": 0,
        "direct_papers_total": 32, "direct_papers_endpoint_incompatible": len(direct["potential_false_blockers"]),
        "tier_a_direct_total": 24,
        "tier_a_direct_endpoint_incompatible": len(tier_a_direct["tier_a_direct_incompatible"]),
        "endpoint_mismatch_total": 9,
        "endpoint_mismatch_classified_incompatible": capture["endpoint_state_counts"]["INCOMPATIBLE"],
        "v23_alpha3_endpoint_shadow_decisions_sha256": shadow_digest,
        "production_rejection_enabled": False, "production_tier_behavior_changed": False,
        "production_acquisition_behavior_changed": False,
        "v22_search_plan_modified": False, "alpha1_1_modified": False, "alpha2_1_modified": False,
        "historical_assets_modified": False, **ZERO_CALLS,
    }
    return outputs, summary


def build_final(phase1, phase2, summary, before, after):
    alpha1.frozen.require(before == after, "protected upstream state changed")
    outputs = {**phase1, **phase2}
    outputs["scientific_state_safety_audit.json"] = alpha1._json(tagged({
        **ZERO_CALLS, "tier_changes": 0, "acquisition_changes": 0, "sample_changes": 0,
        "reject_changes": 0, "production_rejection_enabled": False,
        "production_tier_behavior_changed": False, "production_acquisition_behavior_changed": False,
        "v22_search_plan_modified": False, "alpha1_1_modified": False, "alpha2_1_modified": False,
        "historical_assets_modified": False, "git_mutation_invoked": False,
        "protected_state_before": before, "protected_state_after": after,
    }))
    outputs["validation.json"] = alpha1._json(tagged({
        "status": "PASS", "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "phase1_preacquisition_only": True, "phase1_forbidden_sources_loaded": False,
        "phase1_frozen_before_retrospective_join": True, "phase1_replay_byte_identical": True,
        "complete_analysis_replay_byte_identical": True, "exact_five_endpoint_states": True,
        "partial_and_unresolved_are_nonblocking": True, "endpoint_blocker_state": "INCOMPATIBLE",
        "production_case_specific_rules": 0, "shadow_only": True,
        "p0_closed_on_heldout_v1": True, "p1_closed_on_heldout_v1": True,
        "p2_diagnostic_only": True, "heldout_v2_required": True,
        "rules_modified_after_endpoint_mismatch_audit": False,
    }))
    components = [{"path": name, "sha256": alpha1.frozen.digest(outputs[name])}
                  for name in sorted(outputs) if name != "implementation_manifest.json"]
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json(
        [[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = alpha1._json({
        **json.loads(outputs["implementation_manifest.json"]), "upstream_roots": verify_upstreams(),
        "v23_alpha3_endpoint_semantics_shadow_sha256": root,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required artifacts except implementation_manifest.json and summary.json.",
    })
    outputs["summary.json"] = alpha1._json(tagged({
        **summary, "v23_alpha3_endpoint_semantics_shadow_sha256": root,
        "output_file_count": len(REQUIRED),
        "scientific_boundary": "P0 and P1 closed on held-out-v1; P2 is diagnostic only and requires held-out-v2 validation.",
    }))
    alpha1.frozen.require(set(outputs) == REQUIRED and len(outputs) == 20,
                          "alpha3 final output membership mismatch")
    return outputs


def write_complete(outputs):
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing alpha3 output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                              f"alpha3 output write verification failed: {name}")
    alpha1.frozen.require({path.name for path in RUN.iterdir()} == REQUIRED,
                          "alpha3 output run has unexpected files")


def generate_and_freeze():
    before = protected_state()
    phase1_a, decisions_a, digest_a = build_phase1()
    phase1_b, decisions_b, digest_b = build_phase1()
    alpha1.frozen.require(phase1_a == phase1_b and decisions_a == decisions_b and digest_a == digest_b,
                          "alpha3 phase1 replay mismatch")
    freeze_phase1(phase1_a)
    frozen, frozen_digest = load_frozen_phase1()
    normalized = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in frozen)
    alpha1.frozen.require(normalized == phase1_a["v23_alpha3_endpoint_shadow_decisions.jsonl"]
                          and frozen_digest == digest_a, "alpha3 frozen decisions differ")
    phase2_a, summary_a = build_phase2(frozen, frozen_digest)
    phase2_b, summary_b = build_phase2(frozen, frozen_digest)
    alpha1.frozen.require(phase2_a == phase2_b and summary_a == summary_b,
                          "alpha3 complete analysis replay mismatch")
    after = protected_state()
    final_a = build_final(phase1_a, phase2_a, summary_a, before, after)
    final_b = build_final(phase1_b, phase2_b, summary_b, before, after)
    alpha1.frozen.require(final_a == final_b, "alpha3 final artifact replay mismatch")
    write_complete(final_a)
    alpha1.frozen.require(before == protected_state(), "protected state changed during alpha3 write")
    return final_a


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("phase1_endpoint_shadow_replay_byte_identical=true")
    print("complete_analysis_replay_byte_identical=true")


if __name__ == "__main__":
    main()
