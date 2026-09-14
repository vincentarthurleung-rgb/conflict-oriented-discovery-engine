#!/usr/bin/env python3
"""Freeze alpha2 relation decisions before retrospective development analysis."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess

from code_engine.search.functional_relation_evidence_v1 import (
    EVIDENCE_STATES,
    decide_functional_relation_evidence_v1,
)

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as alpha1_1


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260914_search_plan_v23_alpha2_functional_relation_shadow_offline"
POLICY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json"
IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/functional_relation_evidence_v1.py"
PRODUCTION_FILES = [IMPLEMENTATION_PATH, POLICY_PATH]
DEVELOPMENT_STATUS = "seen_heldout_v1_retrospective_development_only"
PHASE1_STATUS = "outcome_blind_preacquisition_relation_shadow_inference"
ALPHA1_1_ROOT = "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c"
ALPHA1_1_SHADOW = "165a5a1656e37eb74eab21296f7b63a8a990fe1f6bbcb2e2cc7994221943d049"
ALPHA1_1_PROTECTED = {
    ROOT / "src/code_engine/search/biological_unit_compatibility_v1_1.py": "0627ac601156864ac7363b7c46bcfe4cfc1f4d174bb1374cc7e53871f8c3b80d",
    ROOT / "configs/search_plans/biological_unit_registry_v1_1.json": "5fd815b26f14f2a1d9a086d1221fb6772eaea0292fa5a160ba84d22b4dd791be",
    ROOT / "configs/search_plans/biological_unit_policy_v1_1.json": "f0d28b6e41d2e265438722d5d834b1bfaddf38563a5a55b571cfdbfe2cef6f9a",
}
BLOCKER_STATES = ("ASSOCIATION_ONLY", "BACKGROUND_ONLY", "MULTI_TARGET_AMBIGUOUS")
PHASE1_FILES = {
    "functional_relation_policy_snapshot.json",
    "v23_alpha2_relation_shadow_decisions.jsonl",
    "v23_alpha2_relation_shadow_decisions_sha256",
    "shadow_decision_validation.json",
}
REQUIRED = PHASE1_FILES | {
    "functional_relation_failure_capture.json", "direct_paper_safety_analysis.json",
    "tier_a_direct_safety_analysis.json", "tier_a_nondirect_analysis.json",
    "tier_b_relation_analysis.json", "per_case_relation_analysis.json",
    "error_overlap_analysis.json", "counterfactual_policy_comparison.json",
    "heldout_specific_rule_audit.json", "implementation_manifest.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
}
ZERO_CALLS = alpha1.ZERO_CALLS


def tagged(payload):
    return {"development_status": DEVELOPMENT_STATUS, **payload}


def load_json(path):
    return json.loads(Path(path).read_bytes())


def verify_alpha1_1_root():
    manifest = load_json(alpha1_1.RUN / "implementation_manifest.json")
    pairs = []
    for component in manifest["aggregate_components"]:
        actual = alpha1.frozen.sha256(alpha1_1.RUN / component["path"])
        alpha1.frozen.require(actual == component["sha256"],
                              f"alpha1.1 component mismatch: {component['path']}")
        pairs.append([component["path"], actual])
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json(pairs))
    shadow_body = (alpha1_1.RUN / "v23_alpha1_1_shadow_decisions.jsonl").read_bytes()
    shadow_hash = alpha1.frozen.digest(shadow_body)
    declared = (alpha1_1.RUN / "v23_alpha1_1_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(root == manifest["v23_alpha1_1_biological_unit_refinement_sha256"]
                          == ALPHA1_1_ROOT, "alpha1.1 root mismatch")
    alpha1.frozen.require(shadow_hash == declared == ALPHA1_1_SHADOW, "alpha1.1 shadow mismatch")
    for path, expected in ALPHA1_1_PROTECTED.items():
        alpha1.frozen.require(alpha1.frozen.sha256(path) == expected,
                              f"alpha1.1 production source changed: {path}")
    return {"root": root, "shadow_decisions_sha256": shadow_hash,
            "production_sources": {str(path.relative_to(ROOT)): expected
                                   for path, expected in ALPHA1_1_PROTECTED.items()}}


def alpha1_1_hashes():
    paths = {path for path in alpha1_1.RUN.rglob("*") if path.is_file()} | set(ALPHA1_1_PROTECTED)
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path) for path in sorted(paths)}


def protected_hashes():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / name for name in tracked if name}
    for base in [alpha1.frozen.PROTOCOL, alpha1.frozen.REVIEW, alpha1.frozen.BLINDED,
                 alpha1.frozen.PASS_A, alpha1.frozen.PASS_B, alpha1.frozen.PRIMARY,
                 alpha1.frozen.RUN, alpha1.frozen.WORKSPACE, alpha1.ERROR_RUN,
                 alpha1.RUN, alpha1_1.RUN]:
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths.update(ALPHA1_1_PROTECTED)
    paths = {path for path in paths if not path.is_relative_to(RUN)}
    return {str(path.relative_to(ROOT)): alpha1.frozen.sha256(path) for path in sorted(paths)}


def build_phase1():
    policy = load_json(POLICY_PATH)
    alpha1.frozen.require(policy["enabled"] is True and policy["shadow_only"] is True,
                          "alpha2 must remain shadow-only")
    inputs = alpha1.parse_preacquisition_batches()
    decisions = []
    for item in inputs:
        decision = decide_functional_relation_evidence_v1(
            item["packet_id"], item["scientific_target"], title=item["title"],
            abstract=item["abstract"], publication_metadata=item["publication_metadata"], policy=policy,
        )
        decisions.append({
            "artifact_schema_version": "FunctionalRelationEvidenceDecisionV1",
            "search_plan_version": "v2.3-alpha2",
            "development_status": DEVELOPMENT_STATUS,
            "phase": PHASE1_STATUS,
            "packet_id": item["packet_id"],
            "preacquisition_input_sha256": alpha1.frozen.digest(alpha1.frozen.canonical_json(item)),
            "decision": asdict(decision),
            "shadow_only": True,
            "tier_change": False, "acquisition_change": False,
            "sample_change": False, "reject_change": False,
        })
    alpha1.frozen.require(len(decisions) == len({row["packet_id"] for row in decisions}) == 70,
                          "alpha2 phase1 packet mismatch")
    body = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in decisions)
    digest = alpha1.frozen.digest(body)
    counts = Counter(row["decision"]["evidence_state"] for row in decisions)
    validation = {
        "development_status": DEVELOPMENT_STATUS,
        "phase": PHASE1_STATUS,
        "status": "PASS",
        "shadow_packet_count": 70,
        "shadow_unique_packet_ids": 70,
        "relation_shadow_decisions_sha256": digest,
        "evidence_state_counts": {state: counts[state] for state in EVIDENCE_STATES},
        "source_files": [str((alpha1.frozen.BLINDED / f"heldout_acquisition_blind_batch_{batch:02d}.md").relative_to(ROOT))
                         for batch in range(1, 6)],
        "decision_input_fields": ["ScientificPropositionTargetV1", "title", "abstract", "publication_metadata"],
        "pass_a_labels_loaded": False, "pass_b_loaded": False,
        "relevance_state_loaded": False, "contaminant_class_loaded": False,
        "evaluator_rationale_loaded": False, "fulltext_loaded": False,
        "fulltext_derived_fields_loaded": False, "primary_metrics_loaded": False,
        "development_failure_families_loaded": False, "tier_loaded": False,
        "shadow_only": True, "tier_changes": 0, "acquisition_changes": 0,
        "sample_changes": 0, "reject_changes": 0, **ZERO_CALLS,
    }
    outputs = {
        "functional_relation_policy_snapshot.json": alpha1._json(policy),
        "v23_alpha2_relation_shadow_decisions.jsonl": body,
        "v23_alpha2_relation_shadow_decisions_sha256": (digest + "\n").encode(),
        "shadow_decision_validation.json": alpha1._json(validation),
    }
    return outputs, decisions, digest


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in PHASE1_FILES:
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == outputs[name],
                                  f"existing alpha2 phase1 differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        alpha1.frozen.require(alpha1.frozen.sha256(path) == alpha1.frozen.digest(outputs[name]),
                              f"alpha2 phase1 write verification failed: {name}")


def load_frozen_phase1():
    body = (RUN / "v23_alpha2_relation_shadow_decisions.jsonl").read_bytes()
    digest = alpha1.frozen.digest(body)
    declared = (RUN / "v23_alpha2_relation_shadow_decisions_sha256").read_text().strip()
    alpha1.frozen.require(digest == declared, "alpha2 frozen shadow hash mismatch")
    records = [json.loads(line) for line in body.splitlines() if line]
    alpha1.frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                          "alpha2 frozen shadow identity mismatch")
    return records, digest


def join_development_labels(shadow):
    labels = alpha1.frozen.read_jsonl(alpha1.ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")
    label_by_id = {row["packet_id"]: row for row in labels}
    units = alpha1.frozen.read_jsonl(alpha1_1.RUN / "v23_alpha1_1_shadow_decisions.jsonl")
    unit_by_id = {row["packet_id"]: row for row in units}
    ids = [row["packet_id"] for row in shadow]
    alpha1.frozen.require(set(ids) == set(label_by_id) == set(unit_by_id) and len(ids) == 70,
                          "alpha2 phase2 join identity mismatch")
    return [{
        "packet_id": row["packet_id"],
        "relation_decision": row["decision"],
        "biological_unit_compatibility_state": unit_by_id[row["packet_id"]]["decision"]["overall_state"],
        "case_id": label_by_id[row["packet_id"]]["case_id"],
        "tier": label_by_id[row["packet_id"]]["tier"],
        "relevance_state": label_by_id[row["packet_id"]]["relevance_state"],
        "contaminant_class": label_by_id[row["packet_id"]]["contaminant_class"],
        "development_failure_families": label_by_id[row["packet_id"]]["development_failure_families"],
    } for row in shadow]


def state_distribution(rows):
    counter = Counter(row["relation_decision"]["evidence_state"] for row in rows)
    return {state: counter[state] for state in EVIDENCE_STATES}


def identity(row):
    return {key: row[key] for key in ("packet_id", "case_id", "tier", "relevance_state", "contaminant_class")}


def subset(name, selection, rows):
    return tagged({
        "analysis_name": name, "selection": selection, "N": len(rows),
        "evidence_state_counts": state_distribution(rows),
        "packet_ids_by_state": {
            state: [row["packet_id"] for row in rows if row["relation_decision"]["evidence_state"] == state]
            for state in EVIDENCE_STATES
        },
    })


def blocker_records(rows):
    return [
        {**identity(row), "evidence_state": row["relation_decision"]["evidence_state"],
         "reason_codes": row["relation_decision"]["reason_codes"]}
        for row in rows if row["relation_decision"]["evidence_state"] in BLOCKER_STATES
    ]


def build_failure_capture(joined):
    rows = [row for row in joined if "FUNCTIONAL_RELATION_UNRESOLVED" in row["development_failure_families"]]
    alpha1.frozen.require(len(rows) == 24, "functional-relation family count mismatch")
    return subset("functional_relation_failure_capture",
                  "frozen development_failure_families contains FUNCTIONAL_RELATION_UNRESOLVED", rows)


def build_direct_safety(joined):
    rows = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 32, "direct-paper count mismatch")
    result = subset("direct_paper_safety_analysis", "frozen relevance_state == DIRECTLY_RELEVANT", rows)
    result["potential_false_blockers"] = blocker_records(rows)
    result["unresolved_direct_papers"] = [identity(row) for row in rows
                                          if row["relation_decision"]["evidence_state"] == "UNRESOLVED"]
    result["unresolved_is_not_automatically_an_error"] = True
    return result


def build_tier_a_direct(joined):
    rows = [row for row in joined if row["tier"] == "TIER_A"
            and row["relevance_state"] == "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 24, "Tier A direct count mismatch")
    result = subset("tier_a_direct_safety_analysis", "Tier A and DIRECTLY_RELEVANT", rows)
    result["potential_false_blockers"] = blocker_records(rows)
    return result


def build_tier_a_nondirect(joined):
    rows = [row for row in joined if row["tier"] == "TIER_A"
            and row["relevance_state"] != "DIRECTLY_RELEVANT"]
    alpha1.frozen.require(len(rows) == 11, "Tier A non-direct count mismatch")
    return subset("tier_a_nondirect_analysis", "Tier A and not DIRECTLY_RELEVANT", rows)


def build_tier_b(joined):
    rows = [row for row in joined if row["tier"] == "TIER_B"]
    direct = [row for row in rows if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    return tagged({
        "analysis_name": "tier_b_relation_analysis",
        "tier_b_all": subset("tier_b_all", "Tier B", rows),
        "tier_b_direct": subset("tier_b_direct", "Tier B and DIRECTLY_RELEVANT", direct),
        "tier_b_direct_potential_false_blockers": blocker_records(direct),
    })


def build_per_case(joined):
    return tagged({
        "analysis_name": "per_case_relation_analysis",
        "cases": {case: subset("per_case", f"case_id == {case}",
                               [row for row in joined if row["case_id"] == case])
                  for case in alpha1.frozen.CASES},
    })


def cross_counts(rows):
    counts = Counter((row["biological_unit_compatibility_state"],
                      row["relation_decision"]["evidence_state"]) for row in rows)
    unit_states = ("EXACT", "AUTHORIZED_COMPATIBLE", "UNRESOLVED", "INCOMPATIBLE")
    return {unit: {state: counts[(unit, state)] for state in EVIDENCE_STATES} for unit in unit_states}


def build_overlap(joined):
    families = ("BIOLOGICAL_UNIT_MISMATCH", "ENDPOINT_MISMATCH", "FUNCTIONAL_RELATION_UNRESOLVED")
    family_rows = {family: [row for row in joined if family in row["development_failure_families"]]
                   for family in families}
    return tagged({
        "analysis_name": "error_overlap_analysis",
        "cross_gate_precedence_implemented": False,
        "all_packets_relation_by_biological_unit_state": cross_counts(joined),
        "families": {family: {
            "N": len(rows), "relation_evidence_state_counts": state_distribution(rows),
            "relation_by_biological_unit_state": cross_counts(rows),
        } for family, rows in family_rows.items()},
        "biological_unit_incompatible_plus_relation_association_only": [
            identity(row) for row in joined
            if row["biological_unit_compatibility_state"] == "INCOMPATIBLE"
            and row["relation_decision"]["evidence_state"] == "ASSOCIATION_ONLY"
        ],
    })


def effect(rows, affected):
    affected_ids = {row["packet_id"] for row in affected}
    return {
        "papers_affected": len(affected),
        "affected_packet_ids": [row["packet_id"] for row in affected],
        "direct_papers_affected": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in affected),
        "tier_a_direct_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] == "DIRECTLY_RELEVANT"
                                      for row in affected),
        "tier_a_nondirect_affected": sum(row["tier"] == "TIER_A" and row["relevance_state"] != "DIRECTLY_RELEVANT"
                                         for row in affected),
        "tier_b_affected": sum(row["tier"] == "TIER_B" for row in affected),
        "per_case_effects": {case: sum(row["case_id"] == case for row in affected)
                             for case in alpha1.frozen.CASES},
        "unaffected_papers": len(rows) - len(affected_ids),
    }


def build_counterfactual(joined):
    weak = [row for row in joined if row["relation_decision"]["evidence_state"] in BLOCKER_STATES]
    tier_a_weak = [row for row in weak if row["tier"] == "TIER_A"]
    background = [row for row in joined if row["relation_decision"]["evidence_state"] == "BACKGROUND_ONLY"]
    return tagged({
        "analysis_name": "counterfactual_policy_comparison",
        "candidate_a": {
            "policy": "weak states block Tier A; UNRESOLVED does not block",
            "retained_papers": len(joined), "hard_rejected_papers": 0,
            "tier_a_blocked_or_demoted": len(tier_a_weak), "effects": effect(joined, tier_a_weak),
        },
        "candidate_b": {
            "policy": "weak states marked relation-weak and retained",
            "retained_papers": len(joined), "hard_rejected_papers": 0,
            "marked_papers": len(weak), "effects": effect(joined, weak),
        },
        "candidate_c": {
            "policy": "BACKGROUND_ONLY hard reject; all others retained",
            "retained_papers": len(joined) - len(background), "hard_rejected_papers": len(background),
            "effects": effect(joined, background),
        },
        "selected_for_production": None,
        "production_activation": False,
        "threshold_optimization_performed": False,
    })


def heldout_specific_rule_audit(joined):
    queries = alpha1.frozen.read_jsonl(alpha1.frozen.PROTOCOL / "heldout_frozen_queries.jsonl")
    primary = alpha1.frozen.read_jsonl(alpha1.frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
    targets = [item["scientific_target"] for item in alpha1.parse_preacquisition_batches()]
    forbidden = {row["case_id"] for row in joined} | {row["packet_id"] for row in joined}
    forbidden |= {row["query_family_id"] for row in queries} | {row["query_variant_id"] for row in queries}
    forbidden |= {str(row["source_identity"].get("pmid") or "") for row in primary}
    titles = {row["source_identity"]["title"] for row in primary}
    case_entities = {str(target.get(key) or "") for target in targets for key in ("subject", "object")}
    forbidden.discard("")
    findings = []
    # Exact frozen titles are scanned separately.  Do not treat a structural
    # branch on the input field name (for example field == "title") as a
    # case-specific title rule.
    branch = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id)\b")
    for path in PRODUCTION_FILES:
        text = path.read_text()
        tokens = sorted(token for token in forbidden if token in text)
        exact_titles = sorted(title for title in titles if title and title in text)
        entity_names = sorted(name for name in case_entities if name and len(name) >= 4 and name in text)
        branches = [line.strip() for line in text.splitlines() if branch.search(line)]
        if tokens or exact_titles or entity_names or branches:
            findings.append({"path": str(path.relative_to(ROOT)), "forbidden_tokens": tokens,
                             "forbidden_titles": exact_titles, "case_entity_names": entity_names,
                             "identity_specific_branches": branches})
    return tagged({
        "analysis_name": "heldout_specific_rule_audit",
        "production_files_scanned": [str(path.relative_to(ROOT)) for path in PRODUCTION_FILES],
        "findings": findings, "production_case_specific_rules": len(findings),
        "tests_and_retrospective_tools_excluded": True,
    })


def build_phase2(shadow, shadow_hash):
    joined = join_development_labels(shadow)
    outputs = {
        "functional_relation_failure_capture.json": alpha1._json(build_failure_capture(joined)),
        "direct_paper_safety_analysis.json": alpha1._json(build_direct_safety(joined)),
        "tier_a_direct_safety_analysis.json": alpha1._json(build_tier_a_direct(joined)),
        "tier_a_nondirect_analysis.json": alpha1._json(build_tier_a_nondirect(joined)),
        "tier_b_relation_analysis.json": alpha1._json(build_tier_b(joined)),
        "per_case_relation_analysis.json": alpha1._json(build_per_case(joined)),
        "error_overlap_analysis.json": alpha1._json(build_overlap(joined)),
        "counterfactual_policy_comparison.json": alpha1._json(build_counterfactual(joined)),
        "heldout_specific_rule_audit.json": alpha1._json(heldout_specific_rule_audit(joined)),
    }
    direct = json.loads(outputs["direct_paper_safety_analysis.json"])
    tier_a_direct = json.loads(outputs["tier_a_direct_safety_analysis.json"])
    rule_audit = json.loads(outputs["heldout_specific_rule_audit.json"])
    alpha1.frozen.require(rule_audit["production_case_specific_rules"] == 0,
                          "held-out-specific alpha2 rule detected")
    outputs["implementation_manifest.json"] = alpha1._json(tagged({
        "search_plan_version": "v2.3-alpha2",
        "functional_relation_evidence_version": "FunctionalRelationEvidenceV1",
        "integration_point": "code_engine.search.functional_relation_evidence_v1.decide_functional_relation_evidence_v1",
        "schemas": ["FunctionalRelationApplicabilityV1", "FunctionalRelationEvidenceDecisionV1"],
        "production_files": [{"path": str(path.relative_to(ROOT)), "sha256": alpha1.frozen.sha256(path)}
                             for path in PRODUCTION_FILES],
        "shadow_only": True, "cross_module_precedence_implemented": False,
        "alpha1_1_modified": False, "v22_modified": False,
        "phase1_forbidden_sources_loaded": False,
        "phase1_decisions_frozen_sha256": shadow_hash,
    }))
    summary = {
        "status": "completed", "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "shadow_only": True, "tier_changes": 0, "acquisition_changes": 0,
        "sample_changes": 0, "reject_changes": 0,
        "production_case_specific_rules": 0,
        "direct_papers_total": direct["N"],
        "direct_papers_relation_blocker_state": len(direct["potential_false_blockers"]),
        "tier_a_direct_total": tier_a_direct["N"],
        "tier_a_direct_relation_blocker_state": len(tier_a_direct["potential_false_blockers"]),
        "functional_relation_unresolved_total": 24,
        "v23_alpha2_relation_shadow_decisions_sha256": shadow_hash,
        "v22_search_plan_modified": False, "alpha1_1_modified": False,
        **ZERO_CALLS, "historical_assets_modified": False,
    }
    return outputs, summary


def build_final(phase1, phase2, summary, before, after, alpha1_1_before, alpha1_1_after, roots):
    alpha1.frozen.require(before == after, "protected historical state changed")
    alpha1.frozen.require(alpha1_1_before == alpha1_1_after, "alpha1.1 changed")
    outputs = {**phase1, **phase2}
    outputs["scientific_state_safety_audit.json"] = alpha1._json(tagged({
        **ZERO_CALLS, "tier_changes": 0, "acquisition_changes": 0,
        "sample_changes": 0, "reject_changes": 0,
        "v22_search_plan_modified": False, "alpha1_1_modified": False,
        "historical_assets_modified": False, "git_mutation_invoked": False,
        "protected_hashes_before": before, "protected_hashes_after": after,
        "alpha1_1_hashes_before": alpha1_1_before, "alpha1_1_hashes_after": alpha1_1_after,
    }))
    outputs["validation.json"] = alpha1._json(tagged({
        "status": "PASS", "shadow_packet_count": 70, "shadow_unique_packet_ids": 70,
        "phase1_outcome_blind_execution": True, "phase1_preacquisition_only": True,
        "phase1_forbidden_sources_loaded": False, "phase1_frozen_before_phase2": True,
        "phase1_replay_byte_identical": True, "complete_output_replay_byte_identical": True,
        "exact_six_evidence_states": True, "unresolved_is_not_blocked": True,
        "threshold_or_weight_optimization_performed": False,
        "cross_module_precedence_implemented": False,
        "production_case_specific_rules": 0, "shadow_only": True,
        "v22_search_plan_modified": False, "alpha1_1_modified": False,
        "heldout_v1_seen_development_data": True, "heldout_v2_required": True,
    }))
    components = [{"path": name, "sha256": alpha1.frozen.digest(outputs[name])}
                  for name in sorted(outputs) if name != "implementation_manifest.json"]
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json([[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = alpha1._json({
        **json.loads(outputs["implementation_manifest.json"]),
        "upstream_roots": roots,
        "v23_alpha2_functional_relation_shadow_sha256": root,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required artifacts except implementation_manifest.json and summary.json.",
    })
    outputs["summary.json"] = alpha1._json(tagged({
        **summary, "v23_alpha2_functional_relation_shadow_sha256": root,
        "output_file_count": len(REQUIRED),
        "stop_condition": "Diagnostic alpha2 frozen; no immediate repair. Audit generic causes before any single alpha2.1 cycle.",
    }))
    alpha1.frozen.require(set(outputs) == REQUIRED, "alpha2 final output membership mismatch")
    return outputs


def write_complete(outputs):
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing alpha2 output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(alpha1.frozen.sha256(path) == alpha1.frozen.digest(body),
                              f"alpha2 output write verification failed: {name}")
    alpha1.frozen.require({path.name for path in RUN.iterdir()} == REQUIRED,
                          "alpha2 output run has unexpected files")


def generate_and_freeze():
    roots = {"v22_and_error_analysis": alpha1.verify_all_roots(),
             "v23_alpha1_1": verify_alpha1_1_root()}
    before = protected_hashes()
    alpha1_1_before = alpha1_1_hashes()
    phase1_a, decisions_a, digest_a = build_phase1()
    phase1_b, decisions_b, digest_b = build_phase1()
    alpha1.frozen.require(phase1_a == phase1_b and decisions_a == decisions_b and digest_a == digest_b,
                          "alpha2 phase1 replay mismatch")
    freeze_phase1(phase1_a)
    frozen_shadow, frozen_digest = load_frozen_phase1()
    normalized = b"".join(alpha1.frozen.canonical_json(row) + b"\n" for row in frozen_shadow)
    alpha1.frozen.require(normalized == phase1_a["v23_alpha2_relation_shadow_decisions.jsonl"]
                          and frozen_digest == digest_a, "alpha2 frozen shadow differs")
    phase2_a, summary_a = build_phase2(frozen_shadow, frozen_digest)
    phase2_b, summary_b = build_phase2(frozen_shadow, frozen_digest)
    alpha1.frozen.require(phase2_a == phase2_b and summary_a == summary_b,
                          "alpha2 analysis replay mismatch")
    after = protected_hashes()
    alpha1_1_after = alpha1_1_hashes()
    final_a = build_final(phase1_a, phase2_a, summary_a, before, after,
                          alpha1_1_before, alpha1_1_after, roots)
    final_b = build_final(phase1_b, phase2_b, summary_b, before, after,
                          alpha1_1_before, alpha1_1_after, roots)
    alpha1.frozen.require(final_a == final_b, "alpha2 complete output replay mismatch")
    write_complete(final_a)
    verify_alpha1_1_root()
    alpha1.frozen.require(before == protected_hashes(), "protected state changed during alpha2 write")
    alpha1.frozen.require(alpha1_1_before == alpha1_1_hashes(), "alpha1.1 changed during alpha2 write")
    return final_a


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("phase1_relation_shadow_replay_byte_identical=true")
    print("complete_analysis_replay_byte_identical=true")


if __name__ == "__main__":
    main()
