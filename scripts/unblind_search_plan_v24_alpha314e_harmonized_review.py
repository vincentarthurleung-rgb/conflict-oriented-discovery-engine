#!/usr/bin/env python3
"""After verified blinded freeze only: identity join and preregistered metrics."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED_313 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
FAILED_314B = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
ORIGINAL = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_metrics_unblinding"
CASE_FILE = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline/primary_heldout_v2_cases.json"
RUN = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def write(path: Path, value: Any) -> None:
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def write_lines(path: Path, values: list[Any]) -> None:
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(b"".join(canonical(item) + b"\n" for item in values))


def metric_predicate(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    op = rule["operator"]
    if op == "AND":
        return all(metric_predicate(row, part) for part in rule["predicates"])
    if op == "OR":
        return any(metric_predicate(row, part) for part in rule["predicates"])
    if op == "EQ":
        return row[rule["field"]] == rule["value"]
    if op == "IN":
        return row[rule["field"]] in rule["values"]
    raise RuntimeError(f"unknown frozen metric predicate {op}")


def metric(rows: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    denominator = {row["packet_id"] for row in rows if metric_predicate(row, spec["denominator_predicate"])}
    numerator = {row["packet_id"] for row in rows if metric_predicate(row, spec["numerator_predicate"])}
    require(numerator <= denominator, f"metric numerator not subset: {spec['metric_id']}")
    n, count = len(numerator), len(denominator)
    return {"n": n, "N": count, "fraction": n / count if count else None,
            "percentage": 100 * n / count if count else None,
            "status": "CALCULATED" if count else "UNDEFINED_ZERO_DENOMINATOR"}


def group_metrics(rows: list[dict[str, Any]], specs: list[dict[str, Any]]) -> dict[str, Any]:
    tiers = Counter(row["final_v23_beta_disposition_at_acquisition"] for row in rows)
    return {"reviewed_units": len(rows), "tier_a_N": tiers["TIER_A"], "tier_b_N": tiers["TIER_B"],
            "metrics": {spec["metric_id"]: metric(rows, spec) for spec in specs},
            "pass_a_acquisition_decision_distribution": dict(sorted(Counter(row["acquisition_decision"] for row in rows).items())),
            "pass_b_relevance_state_distribution": dict(sorted(Counter(row["relevance_state"] for row in rows).items())),
            "contaminant_class_distribution": dict(sorted(Counter("null" if row["contaminant_class"] is None else row["contaminant_class"] for row in rows).items()))}


def main() -> None:
    manifest_path = RUN / "harmonized_deepseek_blinded_adjudication_corpus_manifest.json"
    root_path = RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256"
    require(manifest_path.exists() and root_path.exists(), "complete blinded freeze required before arm access")
    frozen = load(manifest_path)
    pairs = frozen["aggregate_components"]
    require(all(sha(RUN / name) == checksum for name, checksum in pairs), "blinded component drift")
    blinded_root = digest(pairs)
    require(blinded_root == frozen["harmonized_deepseek_blinded_adjudication_corpus_sha256"] == root_path.read_text().strip(), "blinded root drift")
    require(frozen["valid_batch_identities"] == 16 and frozen["valid_review_units_per_pass"] == 71 and frozen["cumulative_inference_events"] == 17, "blinded accounting incomplete")
    require(not (RUN / "unblinding_barrier_audit.json").exists(), "unblinding already begun")
    require(not (RUN / "harmonized_arm_results.jsonl").exists(), "identity join already exists")
    # This durable barrier is created before the first hidden-map read.
    write(RUN / "unblinding_barrier_audit.json", {"blinded_adjudication_freeze_verified": True,
                                                "blinded_adjudication_corpus_sha256": blinded_root,
                                                "all_component_hashes_verified_before_map_open": True,
                                                "arm_map_accessed_before_blinded_freeze": False,
                                                "metrics_computed_before_blinded_freeze": False,
                                                "identity_join_permitted_after_barrier": True})
    hidden_path = SOURCE / "neutral_review_hidden_arm_map.jsonl"
    corpus_manifest = load(SOURCE / "harmonized_neutral_review_corpus_manifest.json")
    hidden_hash = next(checksum for name, checksum in corpus_manifest["aggregate_components"] if name == hidden_path.name)
    require(sha(hidden_path) == hidden_hash, "hidden arm map hash drift")
    hidden = lines(hidden_path)
    blind = lines(RUN / "complete_blinded_review_unit_results.jsonl")
    by_id = {row["review_unit_id"]: row for row in blind}
    require(len(hidden) == len(blind) == len(by_id) == 71 and {row["review_unit_id"] for row in hidden} == set(by_id), "hidden identity mapping mismatch")
    case_tiers = {row["case_id"]: row["ambiguity_tier"] for row in load(CASE_FILE)["cases"]}
    plan = load(SOURCE / "neutral_review_metrics_plan.json")
    specs = plan["original_metrics_spec_unmodified"]["metrics"]
    require(len(specs) == 10, "frozen metrics spec count drift")
    by_arm: dict[str, list[dict[str, Any]]] = {item["arm"]: [] for item in plan["arms"]}
    joined = []
    missing_excerpt = Counter()
    for edge in hidden:
        identifier, arm, case = edge["review_unit_id"], edge["arm_membership"], edge["case_id"]
        a, b = by_id[identifier]["pass_a"], by_id[identifier]["pass_b"]
        require(a["review_unit_id"] == b["review_unit_id"] == identifier, "blind cross-pass ID mismatch")
        row = {"packet_id": identifier, "case_id": case, "ambiguity_stratum": case_tiers[case],
               "acquired": True, "adjudication_status": "SUCCESSFULLY_ADJUDICATED",
               "final_v23_beta_disposition_at_acquisition": edge["frozen_preacquisition_tier"],
               "acquisition_decision": a["acquisition_decision"],
               "relevance_state": b["relevance_state"],
               "contaminant_class": b["contaminant_class"]}
        by_arm[arm].append(row)
        joined.append({"arm_membership": arm, **row})
        missing_excerpt[arm] += edge["fulltext_excerpt_count"] == 0
    require({arm: len(rows) for arm, rows in by_arm.items()} == {"ARM_HISTORICAL_V23": 60, "ARM_LEXICAL_V2": 11}, "arm denominator mismatch")
    require(missing_excerpt == {"ARM_HISTORICAL_V23": 12, "ARM_LEXICAL_V2": 8}, "frozen evidence availability mismatch")
    write_lines(RUN / "harmonized_arm_results.jsonl", joined)
    arm_metrics = {}
    for arm_plan in plan["arms"]:
        arm, rows = arm_plan["arm"], by_arm[arm_plan["arm"]]
        require(len(rows) == arm_plan["review_denominator"], "arm plan denominator drift")
        per_case = {}
        for case_id, expected_count in arm_plan["per_case_review_unit_counts"].items():
            subset = [row for row in rows if row["case_id"] == case_id]
            require(len(subset) == expected_count, f"case coverage drift: {arm}/{case_id}")
            per_case[case_id] = {"status": "REVIEWED" if subset else "NO_REVIEW_UNITS_FROM_RETRIEVAL", **group_metrics(subset, specs)}
        per_ambiguity = {stratum: group_metrics([row for row in rows if row["ambiguity_stratum"] == stratum], specs)
                         for stratum in ("LOW", "MEDIUM", "HIGH")}
        macro = {}
        for spec in specs:
            metric_id = spec["metric_id"]
            defined = [item["metrics"][metric_id]["fraction"] for item in per_case.values()
                       if item["metrics"][metric_id]["fraction"] is not None]
            macro[metric_id] = {"mean_defined_case_fraction": sum(defined) / len(defined) if defined else None,
                                "defined_case_count": len(defined), "undefined_case_count": len(per_case) - len(defined)}
        arm_metrics[arm] = {"micro": group_metrics(rows, specs), "per_case": per_case,
                            "per_ambiguity_stratum": per_ambiguity, "macro_by_case": macro,
                            "retrieval_missing_case_count": arm_plan["missing_case_count"],
                            "units_without_fulltext_excerpt": missing_excerpt[arm],
                            "scope": "seen-development retrospective descriptive"}
    write(RUN / "harmonized_v23_metrics.json", {"namespace": "HARMONIZED_DEEPSEEK_V23_REVIEW", **arm_metrics["ARM_HISTORICAL_V23"]})
    write(RUN / "harmonized_lexical_v2_metrics.json", {"namespace": "HARMONIZED_DEEPSEEK_LEXICAL_V2_REVIEW", **arm_metrics["ARM_LEXICAL_V2"]})
    original_primary = load(ORIGINAL / "primary_metrics.json")
    original_contaminants = load(ORIGINAL / "contaminant_metrics.json")
    require(load(ORIGINAL / "validation.json")["status"] == "PASS", "original historical metrics invalid")
    require(original_primary["metrics_spec_v2_sha256"] == plan["historical_metrics_spec_sha256"], "original metric spec drift")
    original_all = {**original_primary["metrics"], **original_contaminants["metrics"]}
    require(set(original_all) == {spec["metric_id"] for spec in specs}, "original metric ID mismatch")
    comparisons = []
    for spec in specs:
        metric_id = spec["metric_id"]
        original_value = original_all[metric_id]
        harmonized_value = arm_metrics["ARM_HISTORICAL_V23"]["micro"]["metrics"][metric_id]
        comparisons.append({"metric_id": metric_id, "original_n": original_value["n"], "original_N": original_value["N"], "original_fraction": original_value["fraction"],
                            "harmonized_n": harmonized_value["n"], "harmonized_N": harmonized_value["N"], "harmonized_fraction": harmonized_value["fraction"],
                            "descriptive_fraction_difference_harmonized_minus_original": harmonized_value["fraction"] - original_value["fraction"] if harmonized_value["fraction"] is not None and original_value["fraction"] is not None else None})
    write(RUN / "original_v23_vs_harmonized_v23_comparison.json", {"left_namespace": "ORIGINAL_V23_REVIEW", "right_namespace": "HARMONIZED_DEEPSEEK_V23_REVIEW", "scope": "descriptive provider/protocol comparison, not correction of original historical labels", "original_primary_metrics_sha256": sha(ORIGINAL / "primary_metrics.json"), "original_contaminant_metrics_sha256": sha(ORIGINAL / "contaminant_metrics.json"), "metrics": comparisons})
    arm_differences = []
    for spec in specs:
        metric_id = spec["metric_id"]
        left = arm_metrics["ARM_HISTORICAL_V23"]["micro"]["metrics"][metric_id]
        right = arm_metrics["ARM_LEXICAL_V2"]["micro"]["metrics"][metric_id]
        arm_differences.append({"metric_id": metric_id, "historical_arm": left, "lexical_v2_arm": right,
                                "descriptive_fraction_difference_lexical_minus_historical": right["fraction"] - left["fraction"] if right["fraction"] is not None and left["fraction"] is not None else None})
    write(RUN / "harmonized_v23_vs_lexical_v2_comparison.json", {"left_namespace": "HARMONIZED_DEEPSEEK_V23_REVIEW", "right_namespace": "HARMONIZED_DEEPSEEK_LEXICAL_V2_REVIEW", "scope": "seen-development descriptive only; different retrieval coverage and no precision or recall claim", "historical_arm_denominator": 60, "lexical_v2_arm_denominator": 11, "metrics": arm_differences})
    write(RUN / "evidence_availability_limitation_audit.json", {"historical_v23_units_without_fulltext_excerpt": 12, "historical_v23_review_denominator": 60, "lexical_v2_units_without_fulltext_excerpt": 8, "lexical_v2_review_denominator": 11, "missing_evidence_imputed": False, "interpretation_limitation_prominent": True})
    write(RUN / "case_coverage_summary.json", {arm: {case: group["reviewed_units"] for case, group in value["per_case"].items()} for arm, value in arm_metrics.items()})
    write(RUN / "no_review_units_case_summary.json", {arm: [case for case, group in value["per_case"].items() if group["status"] == "NO_REVIEW_UNITS_FROM_RETRIEVAL"] for arm, value in arm_metrics.items()})
    write(RUN / "historical_original_review_preservation_audit.json", {"original_v23_primary_metrics_sha256": sha(ORIGINAL / "primary_metrics.json"), "original_v23_contaminant_metrics_sha256": sha(ORIGINAL / "contaminant_metrics.json"), "original_historical_labels_overwritten": False, "original_historical_metrics_overwritten": False})
    write(RUN / "search_state_immutability_audit.json", {"query_modifications": 0, "lexical_changes": 0, "retrieval_calls": 0, "known_pmid_checks": 0, "search_tuning": False})
    write(RUN / "scientific_state_safety_audit.json", {"historical_assets_modified": False, "old_invalid_batch3_response_modified": False, "scientific_output_edits": 0, "human_gold_labels_created": 0, "arm_map_accessed_before_blinded_freeze": False, "metrics_computed_before_blinded_freeze": False, "openai_calls": 0, "new_deepseek_calls": 6, "retrieval_calls": 0})
    write(RUN / "validation.json", {"status": "PASS", "blinded_adjudication_freeze_complete": True, "arm_map_accessed_before_blinded_freeze": False, "valid_final_batch_adjudications": 16, "cumulative_provider_inference_events": 17, "invalid_superseded_inference_events": 1, "reinferred_batch_identities": 1, "new_deepseek_calls": 6, "pass_a_units": 71, "pass_b_units": 71, "historical_arm_denominator": 60, "lexical_v2_arm_denominator": 11})
    direct_historical = arm_metrics["ARM_HISTORICAL_V23"]["micro"]["metrics"]["overall_direct_relevance"]
    direct_lexical = arm_metrics["ARM_LEXICAL_V2"]["micro"]["metrics"]["overall_direct_relevance"]
    write(RUN / "summary.json", {"status": "completed", "planned_batch_identities": 16, "valid_final_batch_adjudications": 16, "cumulative_provider_inference_events": 17, "historical_inference_events": 11, "new_deepseek_calls": 6, "invalid_superseded_inference_events": 1, "reinferred_batch_identities": 1, "historical_v23_direct_n": direct_historical["n"], "historical_v23_direct_N": direct_historical["N"], "historical_v23_direct_rate": direct_historical["fraction"], "lexical_v2_direct_n": direct_lexical["n"], "lexical_v2_direct_N": direct_lexical["N"], "lexical_v2_direct_rate": direct_lexical["fraction"], "blinded_adjudication_corpus_sha256": blinded_root, "next_stage_recommendation": "INTERPRET_HARMONIZED_RETRIEVAL_RESULTS", "development_only": True, "historical_assets_modified": False})
    result_names = ["harmonized_deepseek_blinded_adjudication_corpus_manifest.json", "harmonized_deepseek_blinded_adjudication_corpus_sha256", "unblinding_barrier_audit.json", "harmonized_arm_results.jsonl", "harmonized_v23_metrics.json", "harmonized_lexical_v2_metrics.json", "original_v23_vs_harmonized_v23_comparison.json", "harmonized_v23_vs_lexical_v2_comparison.json", "evidence_availability_limitation_audit.json", "case_coverage_summary.json", "no_review_units_case_summary.json", "historical_original_review_preservation_audit.json", "search_state_immutability_audit.json", "scientific_state_safety_audit.json", "validation.json", "summary.json"]
    result_pairs = [[name, sha(RUN / name)] for name in sorted(result_names)]
    results_root = digest(result_pairs)
    write(RUN / "harmonized_deepseek_review_results_manifest.json", {"aggregate_components": result_pairs, "harmonized_deepseek_review_results_sha256": results_root, "blinded_freeze_preceded_unblinding": True, "preregistered_metrics_only": True})
    (RUN / "harmonized_deepseek_review_results_sha256").write_text(results_root + "\n", encoding="utf-8")
    all_paths = [path for path in sorted(RUN.rglob("*")) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14e_sha256"]
    run_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in all_paths]
    run_root = digest(run_pairs)
    (RUN / "search_plan_v24_dev_alpha3_14e_sha256").write_text(run_root + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "blinded_root": blinded_root, "results_root": results_root, "run_root": run_root, "direct_historical": direct_historical, "direct_lexical": direct_lexical}, sort_keys=True))


if __name__ == "__main__":
    main()
