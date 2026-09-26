#!/usr/bin/env python3
"""Unblind and compute frozen alpha3.13 metrics only after both passes are sealed."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
CASES = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline/primary_heldout_v2_cases.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: bool, reason: str) -> None:
    if not value:
        raise RuntimeError(reason)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_once(path: Path, value: Any) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()


def predicate(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    operator = rule["operator"]
    if operator == "AND":
        return all(predicate(row, part) for part in rule["predicates"])
    if operator == "OR":
        return any(predicate(row, part) for part in rule["predicates"])
    if operator == "EQ":
        return row[rule["field"]] == rule["value"]
    if operator == "IN":
        return row[rule["field"]] in rule["values"]
    raise RuntimeError(f"unrecognized frozen predicate: {operator}")


def metric(rows: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    denominator_ids = {row["packet_id"] for row in rows if predicate(row, spec["denominator_predicate"])}
    numerator_ids = {row["packet_id"] for row in rows if predicate(row, spec["numerator_predicate"])}
    require(numerator_ids <= denominator_ids, f"numerator not subset of denominator: {spec['metric_id']}")
    n, count = len(numerator_ids), len(denominator_ids)
    return {"n": n, "N": count, "fraction": n / count if count else None,
            "percentage": 100 * n / count if count else None,
            "status": "DEFINED" if count else "UNDEFINED_ZERO_DENOMINATOR"}


def summary(rows: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    values = {spec["metric_id"]: metric(rows, spec) for spec in metrics}
    relevant = Counter(row["relevance_state"] for row in rows)
    contaminants = Counter("null" if row["contaminant_class"] is None else row["contaminant_class"] for row in rows)
    tiers = Counter(row["final_v23_beta_disposition_at_acquisition"] for row in rows)
    return {"acquired_N": len(rows), "final_tier_a_N": tiers["TIER_A"], "final_tier_b_N": tiers["TIER_B"],
            "metrics": values, "full_relevance_state_distribution": dict(sorted(relevant.items())),
            "full_contaminant_distribution": dict(sorted(contaminants.items()))}


def main() -> None:
    # No hidden-map read, identity join, or metric computation occurs above this gate.
    freeze_path = RUN / "blinded_adjudication_freeze_manifest.json"
    require(freeze_path.exists(), "both PASS A and PASS B must be frozen before unblinding")
    freeze = load(freeze_path)
    require(freeze["pass_a_records"] == freeze["pass_b_records"] == 71 and freeze["provider_calls"] == 16, "incomplete blinded freeze")
    require(all(sha(RUN / name) == checksum for name, checksum in freeze["aggregate_components"]), "blinded output drift")
    root = hashlib.sha256(canonical(freeze["aggregate_components"])).hexdigest()
    require(root == freeze["blinded_adjudication_sha256"] == (RUN / "blinded_adjudication_sha256").read_text().strip(), "blinded freeze root mismatch")
    require(not (RUN / "metrics.json").exists(), "metrics already computed; no overwrite")
    # Only now is the hidden arm map opened.
    corpus = load(SOURCE / "harmonized_neutral_review_corpus_manifest.json")
    hidden_hash = next(checksum for name, checksum in corpus["aggregate_components"] if name == "neutral_review_hidden_arm_map.jsonl")
    require(sha(SOURCE / "neutral_review_hidden_arm_map.jsonl") == hidden_hash, "hidden mapping drift")
    hidden = lines(SOURCE / "neutral_review_hidden_arm_map.jsonl")
    a_rows = lines(RUN / "blinded_pass_a_adjudications.jsonl")
    b_rows = lines(RUN / "blinded_pass_b_adjudications.jsonl")
    a = {row["review_unit_id"]: row for row in a_rows}
    b = {row["review_unit_id"]: row for row in b_rows}
    require(len(hidden) == len(a) == len(b) == 71 and set(a) == set(b) == {row["review_unit_id"] for row in hidden}, "unblinded identity cardinality mismatch")
    plan = load(SOURCE / "neutral_review_metrics_plan.json")
    specs = plan["original_metrics_spec_unmodified"]["metrics"]
    cases = {row["case_id"]: row["ambiguity_tier"] for row in load(CASES)["cases"]}
    by_arm: dict[str, list[dict[str, Any]]] = {item["arm"]: [] for item in plan["arms"]}
    joined = []
    for edge in hidden:
        identifier = edge["review_unit_id"]
        case = edge["case_id"]
        row = {"packet_id": identifier, "case_id": case, "ambiguity_stratum": cases[case],
               "acquired": True, "adjudication_status": "SUCCESSFULLY_ADJUDICATED",
               "final_v23_beta_disposition_at_acquisition": edge["frozen_preacquisition_tier"],
               "acquisition_decision": a[identifier]["acquisition_decision"],
               "relevance_state": b[identifier]["relevance_state"],
               "contaminant_class": b[identifier]["contaminant_class"]}
        by_arm[edge["arm_membership"]].append(row)
        joined.append({"arm_membership": edge["arm_membership"], **row})
    results = {}
    for arm_plan in plan["arms"]:
        arm = arm_plan["arm"]
        rows = by_arm[arm]
        require(len(rows) == arm_plan["review_denominator"], f"arm count mismatch: {arm}")
        per_case = {}
        for case_id, expected_count in arm_plan["per_case_review_unit_counts"].items():
            subset = [row for row in rows if row["case_id"] == case_id]
            require(len(subset) == expected_count, f"per-case count mismatch: {arm}/{case_id}")
            per_case[case_id] = {"status": "REVIEWED" if subset else "NO_REVIEW_UNITS_FROM_RETRIEVAL", **summary(subset, specs)}
        per_ambiguity = {level: summary([row for row in rows if row["ambiguity_stratum"] == level], specs) for level in ("LOW", "MEDIUM", "HIGH")}
        macros = {}
        for spec in specs:
            metric_id = spec["metric_id"]
            defined = [item["metrics"][metric_id]["fraction"] for item in per_case.values() if item["metrics"][metric_id]["fraction"] is not None]
            macros[metric_id] = {"mean_defined_case_fraction": sum(defined) / len(defined) if defined else None,
                                 "defined_case_count": len(defined), "missing_case_count": len(per_case) - len(defined)}
        results[arm] = {"micro": summary(rows, specs), "per_case": per_case, "per_ambiguity_stratum": per_ambiguity,
                        "macro_by_case": macros, "retrieval_missing_case_count": arm_plan["missing_case_count"]}
    write_once(RUN / "unblinded_join.json", {"blinded_adjudication_sha256": root, "source_hidden_arm_map_sha256": hidden_hash, "rows": joined})
    write_once(RUN / "metrics.json", {"artifact_schema_version": "HarmonizedNeutralReviewAlpha313MetricsV1",
                                   "blinded_adjudication_sha256": root,
                                   "metrics_spec_sha256": plan["historical_metrics_spec_sha256"],
                                   "interpretation": "development retrospective descriptive comparison, not prospective held-out validation or correction of historical OpenAI labels",
                                   "arms": results})
    pairs = [[name, sha(RUN / name)] for name in ("blinded_adjudication_freeze_manifest.json", "unblinded_join.json", "metrics.json")]
    write_once(RUN / "final_manifest.json", {"aggregate_components": pairs,
                                             "aggregate_sha256": hashlib.sha256(canonical(pairs)).hexdigest(),
                                             "status": "completed", "deepseek_calls": 16,
                                             "openai_calls": 0, "retrieval_calls": 0,
                                             "historical_artifacts_modified": False})
    print(json.dumps({"status": "completed", "blinded_adjudication_sha256": root,
                      "final_manifest_sha256": sha(RUN / "final_manifest.json"),
                      "arm_denominators": {name: len(rows) for name, rows in by_arm.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
