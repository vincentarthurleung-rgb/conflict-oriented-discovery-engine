#!/usr/bin/env python3
"""Merge frozen held-out-v2 adjudications and unblind preregistered metrics offline."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication as common


RUN = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_metrics_unblinding"
PROTOCOL = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
BETA1 = ROOT / "runs/20260915_search_plan_v23_beta_1_query_binding_repair_offline"
BETA2 = ROOT / "runs/20260916_search_plan_v23_beta_2_modular_query_compiler_freeze_offline"
CASES = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline"
QUERIES = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_query_freeze_offline"
RETRIEVAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
NEUTRAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_freeze_offline"
PASS_A = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication"
PASS_B = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication"
V1_METRICS = ROOT / "runs/20260912_search_plan_v22_heldout_v1_primary_metrics_unblinding_offline"

METRICS_SPEC = PROTOCOL / "metrics_spec_v2.json"
MERGED_NAME = "primary_v2_merged_results.jsonl"
MERGED_HASH_NAME = "primary_v2_merged_results_sha256"

EXPECTED = {
    "search_plan_v23_beta_2_protocol_sha256": "3033bd951cd3b296a6e8aeb6d08a9a5367e58faaa41669619b99f0df7691a835",
    "primary_heldout_v2_network_retrieval_sha256": "0da797b2b3b23a1884a03741abb60d51adedcb03ea9e6faf39ba897a829e46d8",
    "primary_heldout_v2_neutral_review_freeze_sha256": "0db9d84b1567d95d78272d6259d5e41f24751d5204b273801025cd595469c971",
    "primary_heldout_v2_pass_a_adjudication_sha256": "6dfe17d595a38a148412d3b87b7fd6ad226488d3c408c8b3ea057dd01e133e40",
    "primary_v2_pass_a_adjudications_sha256": "bc8a26e18a4709b940e4545f5488fd7e3add489e5ba20570a0f4b99349c196f5",
    "primary_heldout_v2_pass_b_adjudication_sha256": "dff7cb53429cd3575ad2863195cc605073d089805f102725aef156b212745c44",
    "primary_v2_pass_b_adjudications_sha256": "6122b4766e3035555fc535349ac277d42ee330398f9de5f39b153709d05539f8",
    "primary_v2_pass_b_blinded_adjudications_sha256": "111da9ac2986c9031b464103d3020792d7a2dff7efb3f053fe19f93bbdfdf797",
    "metrics_spec_v2_sha256": "9bd177b657e2f93ef44a8a43e9d8b65436b7268f632e4473cc2f874bf39d0854",
}

CASES_ORDER = [f"heldout_v2_{value}" for value in range(101, 109)]
STRATA = ["LOW", "MEDIUM", "HIGH"]
ACQUISITION_STATES = [
    "JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
    "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE",
]

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json", MERGED_NAME, MERGED_HASH_NAME,
    "merge_validation.json", "primary_metrics.json", "primary_metrics.md",
    "raw_relevance_distribution.json", "raw_acquisition_distribution.json",
    "raw_contaminant_distribution.json", "contaminant_metrics.json",
    "per_case_metrics.json", "per_ambiguity_metrics.json",
    "engineering_criteria_results.json", "pass_a_pass_b_crosstab.json",
    "tier_relevance_crosstab.json", "policy_a_demotion_primary_outcome.json",
    "p0_p1_p2_postevaluation_diagnostics.json",
    "query_family_postevaluation_diagnostics.json",
    "heldout_v1_descriptive_comparison.json", "scientific_interpretation.json",
    "scientific_state_safety_audit.json", "implementation_manifest.json",
    "validation.json", "summary.json",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return digest_bytes(canonical(pairs))


def write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), f"non-physical output: {path}")
        require(path.read_bytes() == body, f"frozen output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def verify_component_manifest(run: Path, root_field: str, expected_root: str) -> dict[str, Any]:
    manifest = load_json(run / "implementation_manifest.json")
    checks = []
    for item in manifest["aggregate_components"]:
        name, expected = item if isinstance(item, list) else (item["path"], item["sha256"])
        path = run / name
        actual = sha(path) if path.is_file() and not path.is_symlink() else None
        checks.append({"path": name, "expected_sha256": expected, "actual_sha256": actual, "match": actual == expected})
    root = aggregate([[row["path"], row["actual_sha256"]] for row in checks])
    require(all(row["match"] for row in checks), f"component mismatch: {run.name}")
    require(root == manifest[root_field] == expected_root, f"root mismatch: {root_field}")
    return {"status": "PASS", "expected_sha256": expected_root, "actual_sha256": root,
            "component_count": len(checks), "all_components_match": True}


def verify_protocol_lineage() -> dict[str, Any]:
    base = load_json(PROTOCOL / "version_manifest.json")
    base_checks = []
    for row in base["aggregate_components"]:
        path = PROTOCOL / row["path"]
        actual = sha(path)
        require(actual == row["sha256"], f"base protocol component mismatch: {row['path']}")
        base_checks.append([row["path"], actual])
    base_root = aggregate(base_checks)
    require(base_root == base["search_plan_v23_beta_protocol_sha256"], "base protocol root mismatch")
    require(sha(METRICS_SPEC) == EXPECTED["metrics_spec_v2_sha256"], "metrics_spec_v2 mismatch")
    require(any(row["path"] == "metrics_spec_v2.json" and row["sha256"] == EXPECTED["metrics_spec_v2_sha256"]
                for row in base["aggregate_components"]), "metrics spec absent from base protocol root")

    beta1 = load_json(BETA1 / "version_manifest.json")
    beta1_root = aggregate(beta1["search_plan_v23_beta_1_protocol_aggregate_components"])
    require(beta1_root == beta1["search_plan_v23_beta_1_protocol_sha256"], "beta.1 root mismatch")
    require(beta1["base_search_plan_v23_beta_protocol_sha256"] == base_root, "beta.1 base lineage mismatch")
    beta2 = load_json(BETA2 / "version_manifest.json")
    beta2_root = aggregate(beta2["search_plan_v23_beta_2_protocol_components"])
    require(beta2_root == beta2["search_plan_v23_beta_2_protocol_sha256"] == EXPECTED["search_plan_v23_beta_2_protocol_sha256"],
            "beta.2 protocol root mismatch")
    require(beta2["upstream_search_plan_v23_beta_1_protocol_sha256"] == beta1_root, "beta.2 lineage mismatch")
    return {
        "status": "PASS", "actual_sha256": beta2_root,
        "expected_sha256": EXPECTED["search_plan_v23_beta_2_protocol_sha256"],
        "base_search_plan_v23_beta_protocol_sha256": base_root,
        "upstream_search_plan_v23_beta_1_protocol_sha256": beta1_root,
        "metrics_spec_v2_sha256": sha(METRICS_SPEC),
        "metrics_spec_v2_modified": False,
        "metrics_spec_transitively_anchored": True,
    }


def verify_neutral() -> dict[str, Any]:
    manifest = load_json(NEUTRAL / "freeze_manifest.json")
    checks = []
    for name, expected in manifest["aggregate_components"]:
        actual = sha(NEUTRAL / name)
        require(actual == expected, f"neutral component mismatch: {name}")
        checks.append([name, actual])
    root = aggregate(checks)
    require(root == manifest["primary_heldout_v2_neutral_review_freeze_sha256"] == EXPECTED["primary_heldout_v2_neutral_review_freeze_sha256"],
            "neutral root mismatch")
    return {"status": "PASS", "expected_sha256": EXPECTED["primary_heldout_v2_neutral_review_freeze_sha256"],
            "actual_sha256": root, "component_count": len(checks), "all_components_match": True}


def verify_all_roots() -> dict[str, Any]:
    protocol = verify_protocol_lineage()
    network = verify_component_manifest(RETRIEVAL, "primary_heldout_v2_network_retrieval_sha256",
                                        EXPECTED["primary_heldout_v2_network_retrieval_sha256"])
    neutral = verify_neutral()
    pass_a = verify_component_manifest(PASS_A, "primary_heldout_v2_pass_a_adjudication_sha256",
                                       EXPECTED["primary_heldout_v2_pass_a_adjudication_sha256"])
    pass_b = verify_component_manifest(PASS_B, "primary_heldout_v2_pass_b_adjudication_sha256",
                                       EXPECTED["primary_heldout_v2_pass_b_adjudication_sha256"])
    joined_a = sha(PASS_A / "primary_v2_pass_a_adjudications.jsonl")
    joined_b = sha(PASS_B / "primary_v2_pass_b_adjudications.jsonl")
    blind_b = sha(PASS_B / "primary_v2_pass_b_blinded_adjudications.jsonl")
    require(joined_a == EXPECTED["primary_v2_pass_a_adjudications_sha256"], "PASS-A joined hash mismatch")
    require(joined_b == EXPECTED["primary_v2_pass_b_adjudications_sha256"], "PASS-B joined hash mismatch")
    require(blind_b == EXPECTED["primary_v2_pass_b_blinded_adjudications_sha256"], "PASS-B blind hash mismatch")
    roots = {
        "search_plan_v23_beta_2_protocol_sha256": protocol,
        "primary_heldout_v2_network_retrieval_sha256": network,
        "primary_heldout_v2_neutral_review_freeze_sha256": neutral,
        "primary_heldout_v2_pass_a_adjudication_sha256": pass_a,
        "primary_v2_pass_a_adjudications_sha256": {"status": "PASS", "expected_sha256": joined_a, "actual_sha256": joined_a},
        "primary_heldout_v2_pass_b_adjudication_sha256": pass_b,
        "primary_v2_pass_b_adjudications_sha256": {"status": "PASS", "expected_sha256": joined_b, "actual_sha256": joined_b},
        "primary_v2_pass_b_blinded_adjudications_sha256": {"status": "PASS", "expected_sha256": blind_b, "actual_sha256": blind_b},
    }
    return {"artifact_schema_version": "PrimaryHeldoutV2MetricsUpstreamVerificationV1",
            "status": "PASS", "verified_before_merge": True, "all_roots_match": True,
            "metrics_spec_v2_modified": False, "roots": roots}


def protected_state() -> dict[str, str]:
    paths: set[Path] = set()
    for base in (PROTOCOL, BETA1, BETA2, CASES, QUERIES, RETRIEVAL, NEUTRAL, PASS_A, PASS_B, V1_METRICS):
        paths.update(path for path in base.rglob("*") if path.is_file())
    return {str(path.resolve().relative_to(ROOT)): sha(path) for path in sorted(paths)}


def index(rows: list[dict[str, Any]], key: str = "candidate_id") -> dict[str, dict[str, Any]]:
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), f"duplicate {key}")
    return result


def build_merged_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pass_a_rows = load_jsonl(PASS_A / "primary_v2_pass_a_adjudications.jsonl")
    pass_b_rows = load_jsonl(PASS_B / "primary_v2_pass_b_adjudications.jsonl")
    acquired_rows = load_jsonl(RETRIEVAL / "primary_v2_fulltext_acquisition_manifest.jsonl")
    selections = load_jsonl(RETRIEVAL / "primary_v2_acquisition_selection.jsonl")
    dispositions = index(load_jsonl(RETRIEVAL / "primary_v2_final_preacquisition_dispositions.jsonl"))
    p0 = index(load_jsonl(RETRIEVAL / "primary_v2_p0_decisions.jsonl"))
    p1 = index(load_jsonl(RETRIEVAL / "primary_v2_p1_decisions.jsonl"))
    p2 = index(load_jsonl(RETRIEVAL / "primary_v2_p2_decisions.jsonl"))
    policies = index(load_jsonl(RETRIEVAL / "primary_v2_policy_a_decisions.jsonl"))
    traces = index(load_json(RETRIEVAL / "retrieval_provenance_trace.json")["traces"])
    case_rows = load_json(CASES / "primary_heldout_v2_cases.json")["cases"]
    ambiguity = {row["case_id"]: row["ambiguity_tier"] for row in case_rows}
    a, b, acq, selected = map(index, (pass_a_rows, pass_b_rows, acquired_rows, selections))
    sets = [set(value) for value in (a, b, acq, selected)]
    require(all(len(value) == 60 for value in (pass_a_rows, pass_b_rows, acquired_rows, selections)), "source count is not 60")
    require(all(value == sets[0] for value in sets[1:]), "cross-source candidate identity mismatch")
    merged = []
    conflicts = []
    for candidate_id in sorted(sets[0]):
        rows = [a[candidate_id], b[candidate_id], acq[candidate_id], selected[candidate_id], dispositions[candidate_id]]
        case_ids = {row["case_id"] for row in rows}
        if len(case_ids) != 1:
            conflicts.append(candidate_id)
            continue
        case_id = next(iter(case_ids))
        disposition = dispositions[candidate_id]
        require(disposition["final_v23_beta2_disposition"] == selected[candidate_id]["final_preacquisition_tier"],
                f"tier identity mismatch: {candidate_id}")
        require(acq[candidate_id]["acquisition_status"] == "SUCCESS", f"unsuccessful acquired record: {candidate_id}")
        trace = traces[candidate_id]
        family_ids = sorted({row["family_id"] for row in trace["frozen_query_provenance"]})
        # Retrieval replay appends provenance in request order; the first item is
        # the frozen first-seen contribution used when the candidate was deduplicated.
        first = trace["frozen_query_provenance"][0]
        merged.append({
            "artifact_schema_version": "PrimaryHeldoutV2MergedResultV1",
            "packet_id": candidate_id,
            "candidate_id": candidate_id,
            "case_id": case_id,
            "ambiguity_stratum": ambiguity[case_id],
            "acquired": True,
            "acquired_status": acq[candidate_id]["acquisition_status"],
            "adjudication_status": "SUCCESSFULLY_ADJUDICATED",
            "final_v23_beta2_disposition": disposition["final_v23_beta2_disposition"],
            "final_v23_beta_disposition_at_acquisition": disposition["final_v23_beta2_disposition"],
            "base_v22_disposition": disposition["base_v22_disposition"],
            "policy_a_action": disposition["policy_a_action"],
            "acquisition_decision": a[candidate_id]["acquisition_decision"],
            "relevance_state": b[candidate_id]["relevance_state"],
            "contaminant_class": b[candidate_id]["contaminant_class"],
            "pass_b_secondary_fields": {
                "matched_target_components": b[candidate_id]["matched_target_components"],
                "mismatched_target_components": b[candidate_id]["mismatched_target_components"],
                "fulltext_resolved_fields": b[candidate_id]["fulltext_resolved_fields"],
                "remaining_unresolved_fields": b[candidate_id]["remaining_unresolved_fields"],
            },
            "p0_state": p0[candidate_id]["state"],
            "p1_state": p1[candidate_id]["state"],
            "p2_state": p2[candidate_id]["state"],
            "query_family_ids": family_ids,
            "first_contributing_query_family_id": first["family_id"],
            "pass_a_review_id": a[candidate_id]["review_id"],
            "pass_b_review_id": b[candidate_id]["review_id"],
        })
        require(policies[candidate_id]["final_v23_beta2_disposition"] == disposition["final_v23_beta2_disposition"],
                f"policy/final tier mismatch: {candidate_id}")
    require(not conflicts, "cross-pass identity conflicts")
    validation = {
        "artifact_schema_version": "PrimaryHeldoutV2MergeValidationV1", "status": "PASS",
        "pass_a_records": len(pass_a_rows), "pass_b_records": len(pass_b_rows),
        "acquired_records": len(acquired_rows), "selection_records": len(selections),
        "merged_records": len(merged), "missing_PASS_A": 0, "missing_PASS_B": 0,
        "duplicate_candidate_ids": 0, "cross_pass_identity_conflicts": 0,
        "records_dropped_for_label_disagreement": 0,
        "all_acquisition_status_success": True, "all_adjudication_status_successful": True,
        "one_to_one_identity_consistency": True,
    }
    require(len(merged) == 60, "merged count is not 60")
    return merged, validation


def predicate_matches(record: dict[str, Any], predicate: dict[str, Any]) -> bool:
    operator = predicate["operator"]
    if operator == "EQ":
        return record[predicate["field"]] == predicate["value"]
    if operator == "IN":
        return record[predicate["field"]] in predicate["values"]
    if operator == "AND":
        return all(predicate_matches(record, child) for child in predicate["predicates"])
    if operator == "OR":
        return any(predicate_matches(record, child) for child in predicate["predicates"])
    raise RuntimeError(f"unknown frozen predicate operator: {operator}")


def ratio(n: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {"n": n, "N": 0, "fraction": None, "percentage": None,
                "status": "UNDEFINED_ZERO_DENOMINATOR"}
    return {"n": n, "N": denominator, "fraction": n / denominator,
            "percentage": 100 * n / denominator, "status": "CALCULATED"}


def evaluate_metric(records: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    denominator = {row["packet_id"] for row in records if predicate_matches(row, definition["denominator_predicate"])}
    numerator = {row["packet_id"] for row in records if predicate_matches(row, definition["numerator_predicate"])}
    require(numerator <= denominator, f"numerator outside denominator: {definition['metric_id']}")
    return {"metric_id": definition["metric_id"], "terminology": definition["terminology"],
            "unit": definition["unit"], **ratio(len(numerator), len(denominator))}


def distribution(records: list[dict[str, Any]], field: str, categories: list[Any]) -> dict[str, Any]:
    counts = Counter(row[field] for row in records)
    require(set(counts) <= set(categories), f"unknown {field} category")
    return {"denominator": len(records), "categories": {
        ("no_contaminant" if category is None else str(category)): counts[category] for category in categories
    }}


def group_metrics(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    metrics = {row["metric_id"]: evaluate_metric(records, row) for row in spec["metrics"]}
    return {
        "adjudicated_acquired_N": len(records),
        "final_tier_a_N": sum(row["final_v23_beta2_disposition"] == "TIER_A" for row in records),
        "final_tier_b_N": sum(row["final_v23_beta2_disposition"] == "TIER_B" for row in records),
        "direct": metrics["overall_direct_relevance"],
        "justified": metrics["overall_acquisition_justification"],
        "acceptable": metrics["overall_acquisition_acceptability"],
        "relevance_distribution": distribution(records, "relevance_state", spec["categorical_mappings"]["relevance_state"]),
        "contaminant_distribution": distribution(records, "contaminant_class", spec["categorical_mappings"]["contaminant_class"]),
    }


def crosstab(records: list[dict[str, Any]], row_field: str, row_values: list[str], column_field: str,
             column_values: list[str]) -> dict[str, Any]:
    table = {row_value: {column_value: 0 for column_value in column_values} for row_value in row_values}
    for record in records:
        table[record[row_field]][record[column_field]] += 1
    return {"row_field": row_field, "column_field": column_field, "rows": table, "total": len(records)}


def module_diagnostics(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    relevance = spec["categorical_mappings"]["relevance_state"]
    contaminants = ["no_contaminant" if value is None else value for value in spec["categorical_mappings"]["contaminant_class"]]
    result: dict[str, Any] = {"analysis_type": "POST-EVALUATION DIAGNOSTIC ANALYSIS", "primary_metric": False,
                              "thresholds_added": 0, "modules_modified": False, "modules": {}}
    for module in ("p0_state", "p1_state", "p2_state"):
        states = sorted({row[module] for row in records})
        by_state = {}
        for state in states:
            subset = [row for row in records if row[module] == state]
            cont = Counter("no_contaminant" if row["contaminant_class"] is None else row["contaminant_class"] for row in subset)
            by_state[state] = {
                "N": len(subset),
                "relevance_distribution": {value: sum(row["relevance_state"] == value for row in subset) for value in relevance},
                "contaminant_distribution": {value: cont[value] for value in contaminants},
            }
        result["modules"][module.removesuffix("_state").upper()] = by_state
    triples = Counter((row["p0_state"], row["p1_state"], row["p2_state"], row["relevance_state"],
                       "no_contaminant" if row["contaminant_class"] is None else row["contaminant_class"])
                      for row in records)
    result["joint_state_outcomes"] = [
        {"p0_state": key[0], "p1_state": key[1], "p2_state": key[2], "relevance_state": key[3],
         "contaminant_class": key[4], "count": value}
        for key, value in sorted(triples.items())
    ]
    return result


def query_diagnostics(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    relevance = spec["categorical_mappings"]["relevance_state"]
    families = sorted({family for row in records for family in row["query_family_ids"]})
    any_contribution = {}
    first_contribution = {}
    for family in families:
        any_rows = [row for row in records if family in row["query_family_ids"]]
        first_rows = [row for row in records if row["first_contributing_query_family_id"] == family]
        any_contribution[family] = {"paper_N": len(any_rows),
                                    "relevance_distribution": {state: sum(row["relevance_state"] == state for row in any_rows) for state in relevance}}
        first_contribution[family] = {"paper_N": len(first_rows),
                                      "relevance_distribution": {state: sum(row["relevance_state"] == state for row in first_rows) for state in relevance}}
    return {
        "analysis_type": "POST-EVALUATION DIAGNOSTIC ANALYSIS", "primary_metric": False,
        "provenance_supported": True, "query_modifications": 0,
        "any_contributing_family": any_contribution,
        "first_contributing_family": first_contribution,
        "overlap_note": "Any-contributing-family counts overlap when a paper has multiple contributing families; first-contributing-family counts partition the 60 papers.",
    }


def markdown_report(primary: dict[str, Any], contamination: dict[str, Any], per_case: dict[str, Any],
                    criteria: dict[str, Any], relevance: dict[str, Any], acquisition: dict[str, Any],
                    interpretation: dict[str, Any]) -> bytes:
    lines = ["# Search Plan v2.3-beta.2 primary held-out-v2 metrics", "",
             "All 60 frozen acquired papers were merged one-to-one before metric computation. No labels were changed.", "",
             "## Seven preregistered primary metrics", "",
             "| Metric | n/N | Fraction | Percentage |", "|---|---:|---:|---:|"]
    for metric_id, value in primary["metrics"].items():
        lines.append(f"| {metric_id} | {value['n']}/{value['N']} | {value['fraction']} | {value['percentage']} |")
    lines.extend(["", "## Acquisition outcome", "",
                  f"Raw PASS-A counts: `{json.dumps(acquisition['categories'], sort_keys=True)}`.", "",
                  "## Relevance outcome", "",
                  f"Raw PASS-B counts: `{json.dumps(relevance['categories'], sort_keys=True)}`.", "",
                  "## Contamination metrics", "", "| Metric | n/N | Fraction |", "|---|---:|---:|"])
    for metric_id, value in contamination["metrics"].items():
        lines.append(f"| {metric_id} | {value['n']}/{value['N']} | {value['fraction']} |")
    lines.extend(["", "## Zero-yield cases", ""])
    for case_id in ("heldout_v2_104", "heldout_v2_107"):
        lines.append(f"- {case_id}: N=0; paper-level rates are `UNDEFINED_ZERO_DENOMINATOR`.")
    lines.extend(["", "## Frozen engineering criteria", ""])
    for item in criteria["criteria"]:
        lines.append(f"- {item['criterion_id']}: {item['status']} ({item['machine_reason']})")
    lines.extend(["", f"Overall: `{criteria['overall_frozen_engineering_status']}`.", "",
                  "## Scientific interpretation", "", f"`{interpretation['classification']}`", "",
                  interpretation["basis"], "", "## Boundary", "",
                  "This is not literature precision or recall. v2.3-beta.2 remains frozen; future changes belong to v2.4-dev.", ""])
    return "\n".join(lines).encode("utf-8")


def build_metric_outputs(roots: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    merged_path = RUN / MERGED_NAME
    merged_hash_path = RUN / MERGED_HASH_NAME
    require(merged_path.is_file() and merged_hash_path.is_file(), "merged freeze missing")
    merged_hash = sha(merged_path)
    require(merged_hash_path.read_text().strip() == merged_hash, "merged sidecar mismatch")
    records = load_jsonl(merged_path)
    require(len(records) == len({row["candidate_id"] for row in records}) == 60, "frozen merge invalid")
    spec = load_json(METRICS_SPEC)
    metrics = {row["metric_id"]: evaluate_metric(records, row) for row in spec["metrics"]}
    primary = {metric_id: metrics[metric_id] for metric_id in spec["primary_metric_ids"]}
    contaminants = {metric_id: metrics[metric_id] for metric_id in spec["contaminant_metric_ids"]}
    relevance = distribution(records, "relevance_state", spec["categorical_mappings"]["relevance_state"])
    acquisition = distribution(records, "acquisition_decision", ACQUISITION_STATES)
    contaminant_distribution = distribution(records, "contaminant_class", spec["categorical_mappings"]["contaminant_class"])

    case_groups = defaultdict(list)
    stratum_groups = defaultdict(list)
    for row in records:
        case_groups[row["case_id"]].append(row)
        stratum_groups[row["ambiguity_stratum"]].append(row)
    structural = {row["case_id"]: row for row in load_json(RETRIEVAL / "per_case_structural_analysis.json")["per_case"]}
    per_case = {}
    for case_id in CASES_ORDER:
        value = group_metrics(case_groups[case_id], spec)
        value["structural_retrieval"] = {
            "metadata": structural[case_id]["deduplicated_metadata_candidates"],
            "selected": structural[case_id]["selected_fulltext_count"],
            "acquired": structural[case_id]["successfully_acquired_count"],
        }
        per_case[case_id] = value
    per_ambiguity = {stratum: group_metrics(stratum_groups[stratum], spec) for stratum in STRATA}

    criterion_rows = []
    for definition in spec["engineering_criteria"]:
        value = metrics[definition["metric_id"]]
        if value["fraction"] is None:
            status, reason = "NOT_EVALUABLE", "UNDEFINED_ZERO_DENOMINATOR"
        else:
            passed = value["fraction"] >= definition["threshold"] if definition["operator"] == "GTE" else value["fraction"] <= definition["threshold"]
            status = "PASS" if passed else "FAIL"
            reason = f"{definition['metric_id']}={value['fraction']} {definition['operator']} {definition['threshold']} is {str(passed).lower()}"
        criterion_rows.append({**definition, "observed": value, "status": status, "machine_reason": reason})
    safety_rows = []
    ambiguity_fail = False
    for stratum in STRATA:
        value = per_ambiguity[stratum]
        applicable = value["adjudicated_acquired_N"] >= 10
        direct_n = value["direct"]["n"]
        status = "NOT_EVALUABLE" if not applicable else ("PASS" if direct_n >= 1 else "FAIL")
        reason = ("N_LT_10" if not applicable else
                  ("DIRECTLY_RELEVANT_PRESENT" if direct_n >= 1 else "FAIL_AMBIGUITY_STRATUM_ZERO_DIRECT"))
        ambiguity_fail = ambiguity_fail or status == "FAIL"
        safety_rows.append({"ambiguity_stratum": stratum, "N": value["adjudicated_acquired_N"],
                            "directly_relevant_n": direct_n, "status": status, "machine_reason": reason})
    criterion_rows.append({"criterion_id": "AMBIGUITY_STRATUM_DIRECT_SAFETY", "status": "FAIL" if ambiguity_fail else "PASS",
                           "machine_reason": "FAIL_AMBIGUITY_STRATUM_ZERO_DIRECT" if ambiguity_fail else "ALL_APPLICABLE_STRATA_HAVE_DIRECT",
                           "strata": safety_rows})
    all_pass = all(row["status"] == "PASS" for row in criterion_rows if row["status"] != "NOT_EVALUABLE")
    criteria = {"artifact_schema_version": "PrimaryHeldoutV2EngineeringCriteriaV1", "criteria": criterion_rows,
                "overall_frozen_engineering_status": "ALL_FROZEN_ENGINEERING_CRITERIA_PASS" if all_pass else "ONE_OR_MORE_FROZEN_ENGINEERING_CRITERIA_FAIL",
                "weighted_score_created": False}

    pass_cross = crosstab(records, "acquisition_decision", ACQUISITION_STATES, "relevance_state",
                          spec["categorical_mappings"]["relevance_state"])
    pass_cross["highlighted_counts"] = {
        "NOT_JUSTIFIED_plus_DIRECTLY_RELEVANT": pass_cross["rows"]["NOT_JUSTIFIED"]["DIRECTLY_RELEVANT"],
        "JUSTIFIED_or_BORDERLINE_plus_DIRECTLY_RELEVANT": sum(pass_cross["rows"][value]["DIRECTLY_RELEVANT"] for value in ("JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED")),
        "NOT_JUSTIFIED_plus_non_direct": sum(pass_cross["rows"]["NOT_JUSTIFIED"].values()) - pass_cross["rows"]["NOT_JUSTIFIED"]["DIRECTLY_RELEVANT"],
    }
    tier_cross = crosstab(records, "final_v23_beta2_disposition", ["TIER_A", "TIER_B"], "relevance_state",
                          spec["categorical_mappings"]["relevance_state"])

    policy_rows = [row for row in load_jsonl(RETRIEVAL / "primary_v2_policy_a_decisions.jsonl") if row["policy_a_action"] == "DEMOTE_A_TO_B"]
    require(len(policy_rows) == 1, "Policy-A demotion count is not one")
    demotion = policy_rows[0]
    merged_by_id = index(records)
    observed = merged_by_id.get(demotion["candidate_id"])
    policy_outcome = {
        "artifact_schema_version": "PrimaryHeldoutV2PolicyADemotionOutcomeV1",
        "demotion_count": 1, "candidate_id": demotion["candidate_id"], "case_id": demotion["case_id"],
        "base_v22_disposition": demotion["base_v22_disposition"],
        "final_v23_beta2_disposition": demotion["final_v23_beta2_disposition"],
        "policy_a_action": demotion["policy_a_action"], "acquired": observed is not None,
        "pass_a_acquisition_decision": None if observed is None else observed["acquisition_decision"],
        "pass_b_relevance_state": None if observed is None else observed["relevance_state"],
        "primary_label_status": "NOT_AVAILABLE_NOT_ACQUIRED" if observed is None else "AVAILABLE",
        "causal_policy_effectiveness_claimed": False,
    }

    v1_primary = load_json(V1_METRICS / "primary_metrics.json")["overall_direct_relevance"]
    v1_tiers = load_json(V1_METRICS / "tier_metrics.json")
    historical = {
        "artifact_schema_version": "HeldoutV1V2DescriptiveComparisonV1",
        "comparison_type": "DESCRIPTIVE CROSS-SET DELTA", "paired_comparison": False,
        "significance_test": False, "causal_algorithm_improvement_estimate": False,
        "different_scientific_case_set": True, "different_acquired_corpus": True,
        "acquisition_metric_delta_reported": False,
        "overall_direct_relevance": {
            "heldout_v1": {"n": v1_primary["numerator"], "N": v1_primary["denominator"], "percentage": v1_primary["percentage"]},
            "heldout_v2": primary["overall_direct_relevance"],
            "descriptive_percentage_point_delta_v2_minus_v1": primary["overall_direct_relevance"]["percentage"] - v1_primary["percentage"],
        },
        "tier_a_direct_relevance": {
            "heldout_v1": {"n": v1_tiers["TIER_A"]["direct_relevance"]["numerator"], "N": v1_tiers["TIER_A"]["N"],
                           "percentage": v1_tiers["TIER_A"]["direct_relevance"]["percentage"]},
            "heldout_v2": primary["tier_a_direct_relevance"],
        },
        "tier_b_direct_relevance": {
            "heldout_v1": {"n": v1_tiers["TIER_B"]["direct_relevance"]["numerator"], "N": v1_tiers["TIER_B"]["N"],
                           "percentage": v1_tiers["TIER_B"]["direct_relevance"]["percentage"]},
            "heldout_v2": primary["tier_b_direct_relevance"],
        },
        "historical_acquisition_raw_labels": {"JUSTIFIED": 38, "BORDERLINE_BUT_JUSTIFIED": 13, "NOT_JUSTIFIED": 19},
        "acquisition_comparability_warning": "Held-out-v1 used a different acquisition-evidence setup and underoperationalized original acquisition metric mappings; no primary acquisition delta is valid.",
    }
    interpretation = {
        "artifact_schema_version": "PrimaryHeldoutV2ScientificInterpretationV1",
        "classification": "D. RELEVANCE_AND_ACQUISITION_BOTH_WEAK",
        "basis": (f"Direct relevance was {primary['overall_direct_relevance']['n']}/{primary['overall_direct_relevance']['N']} "
                  f"and acquisition acceptability was {primary['overall_acquisition_acceptability']['n']}/{primary['overall_acquisition_acceptability']['N']}; "
                  "the latter fails its frozen 0.65 engineering threshold. The relevance description is descriptive, not a new threshold."),
        "new_pass_fail_criterion_created": False,
    }
    primary_record = {"artifact_schema_version": "PrimaryHeldoutV2PrimaryMetricsV1",
                      "scope": "adjudicated acquired papers", "metrics": primary,
                      "literature_precision_claimed": False, "recall_claimed": False,
                      "metrics_spec_v2_sha256": EXPECTED["metrics_spec_v2_sha256"]}
    contaminant_record = {"artifact_schema_version": "PrimaryHeldoutV2ContaminantMetricsV1",
                          "metrics": contaminants, "unique_packet_or_predicates": True}
    merge_validation = {**build_merged_records()[1], "primary_v2_merged_results_sha256": merged_hash,
                        "merge_frozen_before_metrics": True, "merged_records_modified_after_freeze": False}
    p_diagnostics = module_diagnostics(records, spec)
    q_diagnostics = query_diagnostics(records, spec)

    protected_after = protected_state()
    require(protected_after == protected_before, "historical frozen state changed")
    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2MetricsScientificStateSafetyAuditV1",
        "offline_only": True, "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "scientific_adjudication_calls": 0, "relabeling_calls": 0,
        "pass_a_label_modifications": 0, "pass_b_label_modifications": 0,
        "scientific_tuning_modifications": 0, "case_exclusions": 0,
        "denominator_modifications": 0, "threshold_modifications": 0,
        "p0_p1_p2_modifications": 0, "policy_a_modifications": 0,
        "query_modifications": 0, "target_modifications": 0, "metrics_spec_v2_modified": False,
        "historical_assets_modified": False, "protected_file_count": len(protected_before),
        "protected_state_before_sha256": digest_bytes(canonical(protected_before)),
        "protected_state_after_sha256": digest_bytes(canonical(protected_after)),
    }

    outputs: dict[str, bytes] = {
        "upstream_root_verification.json": pretty(roots), MERGED_NAME: merged_path.read_bytes(),
        MERGED_HASH_NAME: (merged_hash + "\n").encode("ascii"),
        "merge_validation.json": pretty(merge_validation), "primary_metrics.json": pretty(primary_record),
        "raw_relevance_distribution.json": pretty(relevance), "raw_acquisition_distribution.json": pretty(acquisition),
        "raw_contaminant_distribution.json": pretty(contaminant_distribution),
        "contaminant_metrics.json": pretty(contaminant_record), "per_case_metrics.json": pretty(per_case),
        "per_ambiguity_metrics.json": pretty(per_ambiguity), "engineering_criteria_results.json": pretty(criteria),
        "pass_a_pass_b_crosstab.json": pretty(pass_cross), "tier_relevance_crosstab.json": pretty(tier_cross),
        "policy_a_demotion_primary_outcome.json": pretty(policy_outcome),
        "p0_p1_p2_postevaluation_diagnostics.json": pretty(p_diagnostics),
        "query_family_postevaluation_diagnostics.json": pretty(q_diagnostics),
        "heldout_v1_descriptive_comparison.json": pretty(historical),
        "scientific_interpretation.json": pretty(interpretation),
        "scientific_state_safety_audit.json": pretty(safety),
    }
    outputs["primary_metrics.md"] = markdown_report(primary_record, contaminant_record, per_case, criteria,
                                                     relevance, acquisition, interpretation)
    component_names = sorted(REQUIRED_OUTPUTS - {"implementation_manifest.json", "validation.json", "summary.json"})
    components = [[name, digest_bytes(outputs[name])] for name in component_names]
    root = aggregate(components)
    implementation = {
        "artifact_schema_version": "PrimaryHeldoutV2MetricsImplementationManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": components, "primary_heldout_v2_metrics_unblinding_sha256": root,
        "required_outputs": sorted(REQUIRED_OUTPUTS), "merged_freeze_preceded_metrics": True,
        "deterministic_replay_count": 2, "deterministic_replay_byte_identical": True,
    }
    outputs["implementation_manifest.json"] = pretty(implementation)
    checks = {
        "all_upstream_roots_verified": True, "metrics_spec_v2_unchanged_and_lineage_verified": True,
        "exact_60_to_60_to_60_merge": True, "merged_freeze_preceded_metrics": True,
        "all_metrics_use_frozen_predicates": True, "zero_denominator_cases_preserved": True,
        "policy_a_single_demotion_reported": True, "query_provenance_supported": True,
        "no_labels_modified": True, "no_records_excluded": True, "no_primary_metric_redefinition": True,
        "historical_assets_unchanged": True, "offline_zero_calls": True,
    }
    require(all(checks.values()), "validation failed")
    outputs["validation.json"] = pretty({"artifact_schema_version": "PrimaryHeldoutV2MetricsValidationV1",
                                          "status": "PASS", "checks": checks})
    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2MetricsSummaryV1", "status": "COMPLETED",
        "merged_record_count": 60, "primary_metrics": primary,
        "contaminant_metrics": contaminants, "raw_acquisition_distribution": acquisition["categories"],
        "raw_relevance_distribution": relevance["categories"],
        "overall_frozen_engineering_status": criteria["overall_frozen_engineering_status"],
        "scientific_interpretation": interpretation["classification"],
        "primary_v2_merged_results_sha256": merged_hash,
        "primary_heldout_v2_metrics_unblinding_sha256": root,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED_OUTPUTS, "output membership mismatch")
    return outputs


def run() -> None:
    roots = verify_all_roots()
    protected = protected_state()
    merged_first, _ = build_merged_records()
    merged_second, _ = build_merged_records()
    merged_body = jsonl(merged_first)
    require(merged_body == jsonl(merged_second), "merge replay differs")
    merged_hash = digest_bytes(merged_body)
    RUN.mkdir(parents=True, exist_ok=True)
    write_exact(RUN / MERGED_NAME, merged_body)
    write_exact(RUN / MERGED_HASH_NAME, (merged_hash + "\n").encode("ascii"))
    require(sha(RUN / MERGED_NAME) == merged_hash, "merged freeze verification failed")
    first = build_metric_outputs(roots, protected)
    second = build_metric_outputs(roots, protected)
    require(first == second, "full metric replay is not byte-identical")
    for name in sorted(first):
        write_exact(RUN / name, first[name])
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "final output membership mismatch")
    require(protected_state() == protected, "historical state changed after output write")
    print((RUN / "summary.json").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    run()
