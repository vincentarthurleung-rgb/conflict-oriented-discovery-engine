#!/usr/bin/env python3
"""Run outcome-blind biological-unit shadow decisions, then retrospective evaluation."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess

from code_engine.search.biological_unit_compatibility_v1 import (
    COMPATIBILITY_STATES,
    BiologicalUnitRegistryV1,
    decide_biological_unit_compatibility,
)

if __package__:
    from . import calculate_search_plan_v22_heldout_v1_primary_metrics_offline as frozen
else:
    import calculate_search_plan_v22_heldout_v1_primary_metrics_offline as frozen


ROOT = frozen.ROOT
ERROR_RUN = ROOT / "runs/20260912_search_plan_v22_to_v23_error_analysis_freeze_offline"
RUN = ROOT / "runs/20260912_search_plan_v23_alpha1_biological_unit_shadow_offline"
REGISTRY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1.json"
POLICY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1.json"
IMPLEMENTATION_PATH = ROOT / "src/code_engine/search/biological_unit_compatibility_v1.py"
ERROR_ANALYSIS_HASH = "8e18a61200f22108f4f24b66ee72d6e2ecd11a32220eb0142d4a48552f4eaa9b"
DEVELOPMENT_STATUS = "seen_heldout_v1_retrospective_development_only"
PHASE1_STATUS = "outcome_blind_preacquisition_shadow_inference"
SHADOW_FILES = {
    "biological_unit_registry_snapshot.json",
    "biological_unit_policy_snapshot.json",
    "v23_alpha1_shadow_decisions.jsonl",
    "v23_alpha1_shadow_decisions_sha256",
    "shadow_decision_validation.json",
}
REQUIRED = SHADOW_FILES | {
    "biological_unit_failure_capture.json",
    "direct_paper_safety_analysis.json",
    "tier_a_safety_analysis.json",
    "tier_b_shadow_analysis.json",
    "per_case_shadow_analysis.json",
    "error_overlap_analysis.json",
    "incompatible_reject_counterfactual.json",
    "heldout_specific_rule_audit.json",
    "implementation_manifest.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}
PRODUCTION_FILES = [IMPLEMENTATION_PATH, REGISTRY_PATH, POLICY_PATH]
FORBIDDEN_PHASE1_KEYS = {
    "pass_a", "pass_b", "acquisition_decision", "relevance_state", "contaminant_class",
    "relevance_rationale", "fulltext_ref", "fulltext_sha256", "deterministic_fulltext_excerpts",
    "tier", "final_metrics", "development_failure_families",
}
ALLOWED_PHASE1_INPUT_KEYS = {
    "packet_id", "scientific_target", "title", "abstract", "publication_metadata", "source_refs",
}
ZERO_CALLS = {
    "network_calls": 0,
    "provider_calls": 0,
    "llm_calls": 0,
    "downloads": 0,
    "new_scientific_adjudication_calls": 0,
}


def _tag(value):
    return {"development_status": DEVELOPMENT_STATUS, **value}


def _load(path):
    return json.loads(Path(path).read_bytes())


def _json(value):
    return frozen.pretty_json(value)


def verify_error_analysis_root():
    manifest = _load(ERROR_RUN / "manifest.json")
    pairs = []
    for component in manifest["components"]:
        actual = frozen.sha256(ERROR_RUN / component["path"])
        frozen.require(actual == component["sha256"], f"error-analysis component mismatch: {component['path']}")
        pairs.append([component["path"], actual])
    actual = frozen.digest(frozen.canonical_json(pairs))
    frozen.require(
        actual == manifest["v22_to_v23_error_analysis_sha256"] == ERROR_ANALYSIS_HASH,
        "v2.2-to-v2.3 error-analysis root mismatch",
    )
    frozen.require(
        all(manifest[name] == value for name, value in {
            **frozen.EXPECTED_ROOTS,
            "heldout_v1_primary_metrics_sha256": "76580be82dfa6a13f620514596caacb2ba13bf7a087f47dc62f76a5329f9adf1",
        }.items()),
        "error-analysis upstream roots mismatch",
    )
    return {"actual": actual, "expected": ERROR_ANALYSIS_HASH, "match": True}


def verify_all_roots():
    roots = frozen.verify_all_roots()
    metrics = _load(frozen.RUN / "manifest.json")
    pairs = []
    for component in metrics["metric_result_components"]:
        actual = frozen.sha256(frozen.RUN / component["path"])
        frozen.require(actual == component["sha256"], f"primary-metrics component mismatch: {component['path']}")
        pairs.append([component["path"], actual])
    metrics_hash = frozen.digest(frozen.canonical_json(pairs))
    frozen.require(
        metrics_hash == metrics["heldout_v1_primary_metrics_sha256"]
        == "76580be82dfa6a13f620514596caacb2ba13bf7a087f47dc62f76a5329f9adf1",
        "primary-metrics root mismatch",
    )
    roots["heldout_v1_primary_metrics_sha256"] = {
        "actual": metrics_hash, "expected": metrics_hash, "match": True,
    }
    roots["v22_to_v23_error_analysis_sha256"] = verify_error_analysis_root()
    return roots


def protected_hashes():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / name for name in tracked if name}
    for base in [frozen.PROTOCOL, frozen.REVIEW, frozen.BLINDED, frozen.PASS_A, frozen.PASS_B,
                 frozen.PRIMARY, frozen.RUN, frozen.WORKSPACE, ERROR_RUN]:
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths = {path for path in paths if not path.is_relative_to(RUN)}
    return {str(path.relative_to(ROOT)): frozen.sha256(path) if path.is_file() else None
            for path in sorted(paths)}


def _extract_json(block, heading):
    match = re.search(r"^" + re.escape(heading) + r":\n```json\n(.*?)\n```$", block, re.M | re.S)
    frozen.require(match is not None, f"missing {heading}")
    return json.loads(match.group(1))


def parse_preacquisition_batches():
    """Parse only PASS A blinded views, which contain no fulltext or outcome labels."""
    records = []
    for batch in range(1, 6):
        path = frozen.BLINDED / f"heldout_acquisition_blind_batch_{batch:02d}.md"
        text = path.read_text()
        frozen.require("Fulltext excerpts:" not in text and "relevance_state:" not in text,
                       "forbidden evidence found in PASS A source")
        parts = re.split(r"^### Packet (\S+)\n", text, flags=re.M)
        frozen.require(len(parts) == 29, "PASS A batch packet count mismatch")
        for packet_id, block in zip(parts[1::2], parts[2::2]):
            target = _extract_json(block, "ScientificPropositionTargetV1")
            publication = _extract_json(block, "Publication")
            abstract = re.search(r"^Abstract:\n(.*?)\n\nADJUDICATION\n", block, re.M | re.S)
            frozen.require(abstract is not None, f"missing abstract: {packet_id}")
            publication_metadata = {key: value for key, value in publication.items() if key != "title"}
            row = {
                "packet_id": packet_id,
                "scientific_target": target,
                "title": publication["title"],
                "abstract": abstract.group(1),
                "publication_metadata": publication_metadata,
                "source_refs": [str(path.relative_to(ROOT)), "ScientificPropositionTargetV1", "Publication", "Abstract"],
            }
            frozen.require(set(row) == ALLOWED_PHASE1_INPUT_KEYS, "phase-1 input allowlist changed")
            frozen.require(not (set(row) & FORBIDDEN_PHASE1_KEYS), "forbidden phase-1 input key")
            records.append(row)
    frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                   "phase-1 packet identity mismatch")
    return records


def build_phase1_inputs_hash(records):
    return frozen.digest(b"".join(frozen.canonical_json(row) + b"\n" for row in records))


def build_phase1():
    registry_payload = _load(REGISTRY_PATH)
    policy = _load(POLICY_PATH)
    frozen.require(policy["enabled"] is True and policy["shadow_only"] is True, "alpha1 must remain shadow-only")
    registry = BiologicalUnitRegistryV1(registry_payload)
    inputs = parse_preacquisition_batches()
    decisions = []
    for item in inputs:
        decision = decide_biological_unit_compatibility(
            registry,
            policy,
            item["scientific_target"]["context_qualifiers"],
            title=item["title"],
            abstract=item["abstract"],
            publication_metadata=item["publication_metadata"],
        )
        decisions.append({
            "artifact_schema_version": "BiologicalUnitCompatibilityDecisionV1",
            "search_plan_version": "v2.3-alpha1",
            "development_status": DEVELOPMENT_STATUS,
            "phase": PHASE1_STATUS,
            "packet_id": item["packet_id"],
            "preacquisition_input_sha256": frozen.digest(frozen.canonical_json(item)),
            "decision": asdict(decision),
            "shadow_only": True,
            "tier_change": False,
            "acquisition_change": False,
            "sample_change": False,
        })
    body = b"".join(frozen.canonical_json(row) + b"\n" for row in decisions)
    shadow_hash = frozen.digest(body)
    counts = Counter(row["decision"]["overall_state"] for row in decisions)
    outputs = {
        "biological_unit_registry_snapshot.json": _json(registry_payload),
        "biological_unit_policy_snapshot.json": _json(policy),
        "v23_alpha1_shadow_decisions.jsonl": body,
        "v23_alpha1_shadow_decisions_sha256": (shadow_hash + "\n").encode(),
        "shadow_decision_validation.json": _json({
            "development_status": DEVELOPMENT_STATUS,
            "phase": PHASE1_STATUS,
            "status": "PASS",
            "shadow_packet_count": 70,
            "shadow_unique_packet_ids": 70,
            "canonical_packet_order": [row["packet_id"] for row in decisions],
            "preacquisition_input_corpus_sha256": build_phase1_inputs_hash(inputs),
            "shadow_decisions_sha256": shadow_hash,
            "compatibility_state_counts": {state: counts[state] for state in COMPATIBILITY_STATES},
            "input_fields_allowlist": sorted(ALLOWED_PHASE1_INPUT_KEYS),
            "source_files": [str((frozen.BLINDED / f"heldout_acquisition_blind_batch_{batch:02d}.md").relative_to(ROOT)) for batch in range(1, 6)],
            "pass_a_decisions_loaded": False,
            "pass_b_loaded": False,
            "contaminants_loaded": False,
            "final_relevance_labels_loaded": False,
            "fulltext_loaded": False,
            "fulltext_derived_fields_loaded": False,
            "primary_metrics_loaded": False,
            "tier_loaded": False,
            "decision_function_interface": ["target_context_qualifiers", "title", "abstract", "publication_metadata"],
            "shadow_only": True,
            "tier_changes": 0,
            "acquisition_changes": 0,
            "sample_changes": 0,
            **ZERO_CALLS,
        }),
    }
    return outputs, decisions


def freeze_phase1(outputs):
    RUN.mkdir(exist_ok=True)
    for name in SHADOW_FILES:
        path = RUN / name
        if path.exists():
            frozen.require(not path.is_symlink() and path.read_bytes() == outputs[name],
                           f"existing phase-1 artifact differs: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(outputs[name])
        frozen.require(frozen.sha256(path) == frozen.digest(outputs[name]), f"phase-1 write verification failed: {name}")


def load_frozen_shadow_decisions():
    declared = (RUN / "v23_alpha1_shadow_decisions_sha256").read_text().strip()
    body = (RUN / "v23_alpha1_shadow_decisions.jsonl").read_bytes()
    frozen.require(frozen.digest(body) == declared, "frozen shadow hash mismatch")
    records = [json.loads(line) for line in body.splitlines() if line.strip()]
    frozen.require(len(records) == len({row["packet_id"] for row in records}) == 70,
                   "frozen shadow identity mismatch")
    frozen.require(all(row["phase"] == PHASE1_STATUS and row["decision"]["preacquisition_only"]
                       for row in records), "invalid frozen phase-1 records")
    return records, declared


def state_distribution(rows):
    counter = Counter(row["decision"]["overall_state"] for row in rows)
    return {state: counter[state] for state in COMPATIBILITY_STATES}


def _identity(row):
    return {key: row[key] for key in ["packet_id", "case_id", "tier", "relevance_state", "contaminant_class"]}


def join_development_labels(shadow):
    """Phase 2 only: load frozen post-unblinding development matrix after Phase 1."""
    labels = frozen.read_jsonl(ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")
    lookup = {row["packet_id"]: row for row in labels}
    frozen.require(len(labels) == len(lookup) == 70, "development label identity mismatch")
    joined = []
    for item in shadow:
        label = lookup[item["packet_id"]]
        joined.append({
            "packet_id": item["packet_id"],
            "decision": item["decision"],
            "case_id": label["case_id"],
            "ambiguity": label["ambiguity"],
            "tier": label["tier"],
            "relevance_state": label["relevance_state"],
            "contaminant_class": label["contaminant_class"],
            "development_failure_families": label["development_failure_families"],
        })
    frozen.require(len(joined) == 70 and not (set(lookup) - {row["packet_id"] for row in joined}),
                   "shadow-to-label join mismatch")
    return joined


def _subset_artifact(name, selection, rows):
    return _tag({
        "analysis_name": name,
        "selection": selection,
        "N": len(rows),
        "compatibility_state_counts": state_distribution(rows),
        "packet_ids_by_state": {state: [row["packet_id"] for row in rows if row["decision"]["overall_state"] == state]
                                for state in COMPATIBILITY_STATES},
    })


def build_failure_capture(joined):
    rows = [row for row in joined if row["contaminant_class"] == "wrong_biological_unit"]
    frozen.require(len(rows) == 21, "frozen wrong-biological-unit count mismatch")
    return _subset_artifact(
        "biological_unit_failure_capture",
        "frozen contaminant_class == wrong_biological_unit",
        rows,
    )


def build_direct_safety(joined):
    rows = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    frozen.require(len(rows) == 32, "frozen direct-paper count mismatch")
    artifact = _subset_artifact("direct_paper_safety_analysis", "frozen relevance_state == DIRECTLY_RELEVANT", rows)
    artifact["incompatible_direct_papers"] = [_identity(row) for row in rows if row["decision"]["overall_state"] == "INCOMPATIBLE"]
    artifact["no_policy_repair_performed"] = True
    return artifact


def build_tier_a_safety(joined):
    rows = [row for row in joined if row["tier"] == "TIER_A"]
    critical = [row for row in rows if row["relevance_state"] == "DIRECTLY_RELEVANT"
                and row["decision"]["overall_state"] == "INCOMPATIBLE"]
    artifact = _subset_artifact("tier_a_safety_analysis", "frozen tier == TIER_A", rows)
    artifact["direct_tier_a_incompatible_count"] = len(critical)
    artifact["direct_tier_a_incompatible_packets"] = [_identity(row) for row in critical]
    return artifact


def build_tier_b(joined):
    rows = [row for row in joined if row["tier"] == "TIER_B"]
    direct = [row for row in rows if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    wrong_unit = [row for row in rows if row["contaminant_class"] == "wrong_biological_unit"]
    return _tag({
        "analysis_name": "tier_b_shadow_analysis",
        "tier_b": _subset_artifact("tier_b_all", "frozen tier == TIER_B", rows),
        "tier_b_direct_papers": _subset_artifact("tier_b_direct", "Tier B and DIRECTLY_RELEVANT", direct),
        "tier_b_wrong_biological_unit": _subset_artifact(
            "tier_b_wrong_biological_unit", "Tier B and wrong_biological_unit", wrong_unit
        ),
        "new_primary_metric_created": False,
    })


def build_per_case(joined):
    return _tag({
        "analysis_name": "per_case_shadow_analysis",
        "cases": {
            case: _subset_artifact("case_shadow", f"frozen case_id == {case}",
                                   [row for row in joined if row["case_id"] == case])
            for case in frozen.CASES
        },
    })


def build_overlap(joined):
    families = ["BIOLOGICAL_UNIT_MISMATCH", "FUNCTIONAL_RELATION_UNRESOLVED", "ENDPOINT_MISMATCH"]
    return _tag({
        "analysis_name": "error_overlap_analysis",
        "cross_gate_precedence_implemented": False,
        "families_overlap_allowed": True,
        "overlap": {
            family: _subset_artifact(
                family,
                f"frozen development_failure_families contains {family}",
                [row for row in joined if family in row["development_failure_families"]],
            )
            for family in families
        },
    })


def _retain_reject(rows):
    retained = [row for row in rows if row["decision"]["overall_state"] != "INCOMPATIBLE"]
    rejected = [row for row in rows if row["decision"]["overall_state"] == "INCOMPATIBLE"]
    return {
        "total": len(rows),
        "retained": len(retained),
        "rejected": len(rejected),
        "retained_packet_ids": [row["packet_id"] for row in retained],
        "rejected_packet_ids": [row["packet_id"] for row in rejected],
    }


def build_counterfactual(joined):
    direct = [row for row in joined if row["relevance_state"] == "DIRECTLY_RELEVANT"]
    wrong_unit = [row for row in joined if row["contaminant_class"] == "wrong_biological_unit"]
    return _tag({
        "analysis_name": "incompatible_reject_counterfactual",
        "policy_candidate": {"EXACT": "retain", "AUTHORIZED_COMPATIBLE": "retain",
                             "UNRESOLVED": "retain", "INCOMPATIBLE": "reject"},
        "all_papers": _retain_reject(joined),
        "direct_papers": _retain_reject(direct),
        "wrong_biological_unit": _retain_reject(wrong_unit),
        "by_tier": {tier: _retain_reject([row for row in joined if row["tier"] == tier]) for tier in frozen.TIERS},
        "by_case": {case: _retain_reject([row for row in joined if row["case_id"] == case]) for case in frozen.CASES},
        "production_activation": False,
        "threshold_defined": False,
        "tradeoff_only": True,
    })


def heldout_specific_rule_audit(joined):
    query_rows = frozen.read_jsonl(frozen.PROTOCOL / "heldout_frozen_queries.jsonl")
    forbidden = {row["case_id"] for row in joined} | {row["packet_id"] for row in joined}
    forbidden |= {row["query_family_id"] for row in query_rows} | {row["query_variant_id"] for row in query_rows}
    primary = frozen.read_jsonl(frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
    forbidden |= {str(row["source_identity"].get("pmid") or "") for row in primary}
    forbidden.discard("")
    findings = []
    branch_pattern = re.compile(r"\b(?:if|elif)\s+.*\b(?:case_id|packet_id|pmid|query_family_id|query_variant_id)\b")
    for path in PRODUCTION_FILES:
        text = path.read_text()
        tokens = sorted(token for token in forbidden if token in text)
        branches = [line.strip() for line in text.splitlines() if branch_pattern.search(line)]
        if tokens or branches:
            findings.append({"path": str(path.relative_to(ROOT)), "forbidden_tokens": tokens,
                             "identity_specific_branch_lines": branches})
    return _tag({
        "analysis_name": "heldout_specific_rule_audit",
        "production_files_scanned": [str(path.relative_to(ROOT)) for path in PRODUCTION_FILES],
        "forbidden_case_id_count": 8,
        "forbidden_packet_id_count": 70,
        "forbidden_pmid_count": len({row["source_identity"].get("pmid") for row in primary if row["source_identity"].get("pmid")}),
        "forbidden_query_identity_count": len({row["query_family_id"] for row in query_rows}
                                               | {row["query_variant_id"] for row in query_rows}),
        "findings": findings,
        "production_case_specific_rules": len(findings),
        "tests_and_retrospective_fixtures_excluded_from_production_scan": True,
    })


def build_phase2(shadow, shadow_hash):
    joined = join_development_labels(shadow)
    outputs = {
        "biological_unit_failure_capture.json": _json(build_failure_capture(joined)),
        "direct_paper_safety_analysis.json": _json(build_direct_safety(joined)),
        "tier_a_safety_analysis.json": _json(build_tier_a_safety(joined)),
        "tier_b_shadow_analysis.json": _json(build_tier_b(joined)),
        "per_case_shadow_analysis.json": _json(build_per_case(joined)),
        "error_overlap_analysis.json": _json(build_overlap(joined)),
        "incompatible_reject_counterfactual.json": _json(build_counterfactual(joined)),
        "heldout_specific_rule_audit.json": _json(heldout_specific_rule_audit(joined)),
    }
    direct = json.loads(outputs["direct_paper_safety_analysis.json"])
    capture = json.loads(outputs["biological_unit_failure_capture.json"])
    audit = json.loads(outputs["heldout_specific_rule_audit.json"])
    frozen.require(audit["production_case_specific_rules"] == 0, "held-out-specific production rule detected")
    outputs["implementation_manifest.json"] = _json(_tag({
        "search_plan_version": "v2.3-alpha1",
        "biological_unit_compatibility_version": "BiologicalUnitCompatibilityV1",
        "registry_version": _load(REGISTRY_PATH)["registry_version"],
        "policy_version": _load(POLICY_PATH)["policy_version"],
        "implementation_files": [{"path": str(path.relative_to(ROOT)), "sha256": frozen.sha256(path)}
                                 for path in PRODUCTION_FILES],
        "integration_point": "code_engine.search.biological_unit_compatibility_v1.decide_biological_unit_compatibility",
        "schemas": ["BiologicalUnitRefV1", "BiologicalUnitTargetV1", "ObservedUnitV1",
                    "BiologicalUnitCompatibilityDecisionV1"],
        "exact_four_states": list(COMPATIBILITY_STATES),
        "shadow_only": True,
        "enabled": True,
        "cross_gate_precedence_implemented": False,
        "v22_production_integration_changed": False,
        "phase1_source": "five frozen heldout_acquisition_blind_batch Markdown files",
        "phase1_forbidden_sources_loaded": False,
        "phase2_started_after_shadow_hash_verified": shadow_hash,
    }))
    summary = {
        "shadow_packet_count": 70,
        "shadow_unique_packet_ids": 70,
        "shadow_only": True,
        "tier_changes": 0,
        "acquisition_changes": 0,
        "sample_changes": 0,
        "production_case_specific_rules": 0,
        "direct_papers_total": direct["N"],
        "direct_papers_classified_incompatible": direct["compatibility_state_counts"]["INCOMPATIBLE"],
        "wrong_biological_unit_total": capture["N"],
        "wrong_biological_unit_classified_incompatible": capture["compatibility_state_counts"]["INCOMPATIBLE"],
        "v23_alpha1_shadow_decisions_sha256": shadow_hash,
        "v22_search_plan_modified": False,
        **ZERO_CALLS,
        "historical_assets_modified": False,
    }
    return outputs, summary


def build_final_outputs(phase1, phase2, summary, roots, before, after):
    frozen.require(before == after, "protected historical state changed")
    outputs = {**phase1, **phase2}
    safety = _tag({
        **ZERO_CALLS,
        "tier_changes": 0,
        "acquisition_changes": 0,
        "sample_changes": 0,
        "v22_search_plan_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "protected_scope": "Every tracked file plus all eight frozen upstream run trees and evaluator workspace; current output run excluded.",
    })
    outputs["scientific_state_safety_audit.json"] = _json(safety)
    validations = {
        "status": "PASS",
        "input_packet_count": 70,
        "shadow_packet_count": 70,
        "shadow_unique_packet_ids": 70,
        "phase1_frozen_before_phase2": True,
        "phase1_outcome_blind": True,
        "pass_b_or_fulltext_used_in_phase1": False,
        "exact_four_compatibility_states": True,
        "shadow_only": True,
        "tier_changes": 0,
        "acquisition_changes": 0,
        "sample_changes": 0,
        "production_case_specific_rules": 0,
        "all_retrospective_results_marked_development_only": True,
        "heldout_v1_seen_for_v23": True,
        "new_success_threshold_added": False,
        "cross_gate_precedence_implemented": False,
        "v22_search_plan_modified": False,
        "historical_assets_modified": False,
    }
    outputs["validation.json"] = _json(_tag(validations))
    components = [{"path": name, "sha256": frozen.digest(outputs[name])}
                  for name in sorted(outputs) if name != "implementation_manifest.json"]
    aggregate = frozen.digest(frozen.canonical_json([[row["path"], row["sha256"]] for row in components]))
    outputs["implementation_manifest.json"] = _json({
        **json.loads(outputs["implementation_manifest.json"]),
        "upstream_roots": roots,
        "v23_alpha1_biological_unit_shadow_sha256": aggregate,
        "aggregate_components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required artifacts except implementation_manifest.json and summary.json, which carry the aggregate hash.",
    })
    # Manifest changed after the nonrecursive component hash; it is intentionally excluded.
    outputs["summary.json"] = _json(_tag({
        "status": "completed",
        **summary,
        "v23_alpha1_biological_unit_shadow_sha256": aggregate,
        "output_file_count": len(REQUIRED),
    }))
    frozen.require(set(outputs) == REQUIRED, "output membership mismatch")
    return outputs


def write_complete(outputs):
    frozen.require(RUN.is_dir() and not RUN.is_symlink(), "invalid output run")
    for name, data in outputs.items():
        path = RUN / name
        if path.exists():
            frozen.require(not path.is_symlink() and path.read_bytes() == data,
                           f"existing output differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(data)
        frozen.require(frozen.sha256(path) == frozen.digest(data), f"write verification failed: {name}")
    frozen.require({path.name for path in RUN.iterdir()} == REQUIRED, "output run has unexpected files")


def generate_and_freeze():
    roots = verify_all_roots()
    before = protected_hashes()
    phase1_a, decisions_a = build_phase1()
    phase1_b, decisions_b = build_phase1()
    frozen.require(phase1_a == phase1_b and decisions_a == decisions_b,
                   "phase-1 deterministic replay mismatch")
    freeze_phase1(phase1_a)
    shadow, shadow_hash = load_frozen_shadow_decisions()
    reserialized_shadow = b"".join(frozen.canonical_json(row) + b"\n" for row in shadow)
    frozen.require(reserialized_shadow == phase1_a["v23_alpha1_shadow_decisions.jsonl"],
                   "frozen shadow differs from outcome-blind generation")
    phase2_a, summary_a = build_phase2(shadow, shadow_hash)
    phase2_b, summary_b = build_phase2(shadow, shadow_hash)
    frozen.require(phase2_a == phase2_b and summary_a == summary_b,
                   "complete development-analysis replay mismatch")
    after = protected_hashes()
    outputs = build_final_outputs(phase1_a, phase2_a, summary_a, roots, before, after)
    replayed_outputs = build_final_outputs(phase1_b, phase2_b, summary_b, roots, before, after)
    frozen.require(outputs == replayed_outputs, "complete output replay mismatch")
    write_complete(outputs)
    verify_all_roots()
    frozen.require(before == protected_hashes(), "protected state changed during output write")
    return outputs


def main():
    outputs = generate_and_freeze()
    print(outputs["summary.json"].decode())
    print("phase1_shadow_replay_byte_identical=true")
    print("complete_development_analysis_replay_byte_identical=true")


if __name__ == "__main__":
    main()
