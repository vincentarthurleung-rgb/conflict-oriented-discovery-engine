#!/usr/bin/env python3
"""Calculate frozen held-out v1 metrics without changing scientific state."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
REVIEW = ROOT / "runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline"
BLINDED = ROOT / "runs/20260910_search_plan_v22_heldout_v1_blinded_adjudication_views_offline"
PASS_A = ROOT / "runs/20260910_search_plan_v22_heldout_v1_pass_a_acquisition_adjudication_freeze_offline"
PASS_B = ROOT / "runs/20260912_search_plan_v22_heldout_v1_pass_b_relevance_adjudication_freeze_offline"
PRIMARY = ROOT / "runs/20260912_search_plan_v22_heldout_v1_primary_results_freeze_offline"
WORKSPACE = ROOT / "pass_b_primary_evaluator_workspace"
RUN = ROOT / "runs/20260912_search_plan_v22_heldout_v1_primary_metrics_unblinding_offline"

EXPECTED_ROOTS = {
    "heldout_v1_protocol_sha256": "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127",
    "heldout_v1_review_corpus_sha256": "f2cfe4f1657667a66b18d3123e82d76cc4bf1af9da2863ac6b10f9efc3d092fb",
    "heldout_v1_blinded_adjudication_views_sha256": "2940e058b63df5dc02fb6ed07d970f651a74f9a000c9b6784affe3e6fac1dc0e",
    "heldout_v1_pass_a_acquisition_adjudications_sha256": "333fc6f20bab33b21387f2453905c2c9c11d92797177688a9e75cc2bab2e52df",
    "heldout_v1_pass_b_relevance_adjudications_sha256": "b3d4a5a93572666fa8a0986e4fddad13641969f9b874eac08a48c435f48ee465",
    "heldout_v1_primary_results_sha256": "13e760d4e154f2755cc786490016a92921fc80a4b570356609548cf5a2757119",
}

RELEVANCE_STATES = [
    "DIRECTLY_RELEVANT",
    "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
    "RELATED_BUT_WRONG_PROPOSITION",
    "WRONG_ENDPOINT",
    "WRONG_ENTITY",
    "WRONG_EVIDENCE_MODE",
    "WRONG_THERAPY",
    "TOPIC_ONLY",
    "INSUFFICIENT_SOURCE_EVIDENCE",
]
ACQUISITION_DECISIONS = [
    "JUSTIFIED",
    "BORDERLINE_BUT_JUSTIFIED",
    "NOT_JUSTIFIED",
    "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE",
]
CONTAMINANT_CLASSES = [
    "wrong_evidence_mode",
    "association_vs_functional_relation",
    "wrong_biological_unit",
    "wrong_endpoint",
    "wrong_entity",
    "baseline_viability_vs_adaptation",
    "no_contaminant",
]
CASES = [f"heldout_v1_{index:03d}" for index in range(1, 9)]
AMBIGUITIES = ["LOW", "MEDIUM", "HIGH"]
TIERS = ["TIER_A", "TIER_B"]

REQUIRED_OUTPUTS = {
    "primary_metrics.json",
    "primary_metrics.md",
    "relevance_distribution.json",
    "acquisition_distribution.json",
    "contaminant_distribution.json",
    "per_case_metrics.json",
    "per_ambiguity_metrics.json",
    "tier_metrics.json",
    "engineering_heuristics.json",
    "metric_definition_audit.json",
    "root_hash_verification.json",
    "scientific_state_safety_audit.json",
    "manifest.json",
    "validation.json",
    "summary.json",
}
METRIC_RESULT_COMPONENTS = [
    "primary_metrics.json",
    "primary_metrics.md",
    "relevance_distribution.json",
    "acquisition_distribution.json",
    "contaminant_distribution.json",
    "per_case_metrics.json",
    "per_ambiguity_metrics.json",
    "tier_metrics.json",
    "engineering_heuristics.json",
    "metric_definition_audit.json",
]
ZERO_CALLS = {
    "network_calls": 0,
    "provider_calls": 0,
    "llm_calls": 0,
    "downloads": 0,
    "scientific_extraction_calls": 0,
    "new_adjudication_calls": 0,
}
ZERO_MODIFICATIONS = {
    "case_modifications": 0,
    "target_modifications": 0,
    "query_modifications": 0,
    "gate_modifications": 0,
    "budget_modifications": 0,
    "sample_modifications": 0,
    "batch_assignment_modifications": 0,
    "pass_a_label_modifications": 0,
    "pass_b_label_modifications": 0,
    "primary_result_modifications": 0,
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical_json(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def pretty_json(value):
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha256(path):
    return digest(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_bytes().splitlines()
        if line.strip()
    ]


def verify_aggregate_root(base, field):
    manifest = read_json(base / "freeze_manifest.json")
    components = []
    for component in manifest["components"]:
        actual = sha256(base / component["path"])
        require(actual == component["sha256"], f"component mismatch: {component['path']}")
        components.append((component["path"], actual))
    actual = digest(canonical_json(components))
    expected = EXPECTED_ROOTS[field]
    require(actual == manifest[field] == expected, f"root mismatch: {field}")
    return {"actual": actual, "expected": expected, "match": True}


def verify_corpus_root(base, field):
    manifest = read_json(base / "freeze_manifest.json")
    corpus = base / manifest["corpus"]
    actual = sha256(corpus)
    expected = EXPECTED_ROOTS[field]
    require(actual == manifest[field] == expected, f"root mismatch: {field}")
    return {
        "actual": actual,
        "expected": expected,
        "match": True,
        "corpus_ref": str(corpus.relative_to(ROOT)),
    }


def verify_all_roots():
    roots = {
        "heldout_v1_protocol_sha256": verify_aggregate_root(
            PROTOCOL, "heldout_v1_protocol_sha256"
        ),
        "heldout_v1_review_corpus_sha256": verify_aggregate_root(
            REVIEW, "heldout_v1_review_corpus_sha256"
        ),
        "heldout_v1_blinded_adjudication_views_sha256": verify_aggregate_root(
            BLINDED, "heldout_v1_blinded_adjudication_views_sha256"
        ),
        "heldout_v1_pass_a_acquisition_adjudications_sha256": verify_corpus_root(
            PASS_A, "heldout_v1_pass_a_acquisition_adjudications_sha256"
        ),
        "heldout_v1_pass_b_relevance_adjudications_sha256": verify_corpus_root(
            PASS_B, "heldout_v1_pass_b_relevance_adjudications_sha256"
        ),
        "heldout_v1_primary_results_sha256": verify_corpus_root(
            PRIMARY, "heldout_v1_primary_results_sha256"
        ),
    }
    return roots


def protected_hashes():
    bases = [PROTOCOL, REVIEW, BLINDED, PASS_A, PASS_B, PRIMARY, WORKSPACE]
    paths = [
        path
        for base in bases
        for path in sorted(base.rglob("*"))
        if path.is_file()
    ]
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths}


def ratio(numerator, denominator):
    require(denominator > 0, "zero denominator for numeric result")
    return {
        "status": "CALCULATED",
        "numerator": numerator,
        "denominator": denominator,
        "proportion": round(numerator / denominator, 8),
        "percentage": round(100 * numerator / denominator, 6),
    }


def not_evaluable(reason):
    return {
        "status": "NOT_EVALUABLE_FROM_FROZEN_DEFINITION",
        "numerator": None,
        "denominator": None,
        "proportion": None,
        "percentage": None,
        "reason": reason,
    }


def distribution(counter, categories, denominator):
    return {
        "denominator": denominator,
        "categories": {
            category: {
                "count": counter.get(category, 0),
                "percentage": round(100 * counter.get(category, 0) / denominator, 6),
            }
            for category in categories
        },
    }


def contaminant_value(record):
    value = record["pass_b"]["contaminant_class"]
    return "no_contaminant" if value in (None, "") else value


def validate_records(records):
    require(len(records) == 70, "primary record count is not 70")
    packet_ids = [record["packet_id"] for record in records]
    require(len(set(packet_ids)) == 70, "primary packet IDs are not unique")
    require(set(record["case_id"] for record in records) == set(CASES), "case set mismatch")
    require(set(record["ambiguity"] for record in records) == set(AMBIGUITIES), "ambiguity set mismatch")
    require(set(record["tier"] for record in records) <= set(TIERS), "unknown tier")
    require(
        set(record["pass_b"]["relevance_state"] for record in records)
        <= set(RELEVANCE_STATES),
        "unknown relevance state",
    )
    require(
        set(record["pass_a"]["acquisition_decision"] for record in records)
        <= set(ACQUISITION_DECISIONS),
        "unknown acquisition decision",
    )
    require(
        set(contaminant_value(record) for record in records)
        <= set(CONTAMINANT_CLASSES),
        "unknown contaminant class",
    )
    case_ambiguities = {
        case: {record["ambiguity"] for record in records if record["case_id"] == case}
        for case in CASES
    }
    require(all(len(values) == 1 for values in case_ambiguities.values()), "case ambiguity changed")
    ambiguity_case_counts = Counter(next(iter(values)) for values in case_ambiguities.values())
    require(ambiguity_case_counts == Counter({"LOW": 2, "MEDIUM": 2, "HIGH": 4}), "ambiguity assignment mismatch")
    return {
        "record_count": 70,
        "unique_packet_ids": 70,
        "case_count": 8,
        "ambiguity_case_counts": {key: ambiguity_case_counts[key] for key in AMBIGUITIES},
    }


def raw_group_metrics(records):
    total = len(records)
    relevance = Counter(record["pass_b"]["relevance_state"] for record in records)
    acquisition = Counter(record["pass_a"]["acquisition_decision"] for record in records)
    contaminants = Counter(contaminant_value(record) for record in records)
    tiers = Counter(record["tier"] for record in records)
    return {
        "N": total,
        "direct_relevance": ratio(relevance["DIRECTLY_RELEVANT"], total),
        "acquisition_justified_label_frequency": ratio(acquisition["JUSTIFIED"], total),
        "acquisition_acceptable": not_evaluable(
            "Frozen pre-results artifacts do not define which acquisition decisions map to acceptable."
        ),
        "tier_counts": {tier: tiers[tier] for tier in TIERS},
        "relevance_distribution": distribution(relevance, RELEVANCE_STATES, total),
        "contaminant_distribution": distribution(contaminants, CONTAMINANT_CLASSES, total),
    }


def metric_definition_audit():
    metric_source = (
        "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/"
        "heldout_evaluation_metrics_preregistration.json"
    )
    heuristic_source = (
        "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline/"
        "heldout_evaluation_heuristics_preregistration.json"
    )
    direct_denominator = "all adjudicated acquired papers in the applicable frozen scope"

    def entry(name, source, numerator, denominator, threshold, complete, missing=None):
        return {
            "metric_name": name,
            "definition_source": source,
            "definition_frozen_before_unblinding": True,
            "numerator_definition": numerator,
            "denominator_definition": denominator,
            "threshold_if_any": threshold,
            "operationally_complete": complete,
            "posthoc_choice_required": not complete,
            "missing_frozen_operationalization": missing,
            "result_status": "CALCULATED" if complete else "NOT_EVALUABLE_FROM_FROZEN_DEFINITION",
        }

    entries = [
        entry(
            "overall_direct_relevance_rate",
            metric_source,
            "relevance_state == DIRECTLY_RELEVANT",
            direct_denominator,
            None,
            True,
        ),
        entry(
            "overall_acquisition_justification_rate",
            metric_source,
            None,
            None,
            None,
            False,
            "The frozen artifact names the metric but does not freeze a decision-to-numerator mapping or denominator.",
        ),
        entry(
            "overall_acquisition_acceptability_rate",
            metric_source,
            None,
            None,
            None,
            False,
            "The frozen artifact does not define which acquisition decisions are acceptable or its denominator.",
        ),
        entry(
            "tier_a_direct_relevance_rate",
            metric_source,
            "relevance_state == DIRECTLY_RELEVANT within frozen TIER_A",
            "all adjudicated acquired frozen TIER_A papers",
            None,
            True,
        ),
        entry(
            "tier_a_acquisition_acceptability_rate",
            metric_source,
            None,
            None,
            None,
            False,
            "The frozen artifact does not define the acquisition-acceptability mapping.",
        ),
        entry(
            "tier_b_direct_relevance_rate",
            metric_source,
            "relevance_state == DIRECTLY_RELEVANT within frozen TIER_B",
            "all adjudicated acquired frozen TIER_B papers",
            None,
            True,
        ),
        entry(
            "tier_b_utility_proxy",
            metric_source,
            None,
            None,
            None,
            False,
            "The frozen artifact names a utility proxy but supplies no proxy mapping or denominator.",
        ),
        entry(
            "contaminant_distribution",
            metric_source,
            "count for each frozen contaminant_class, with empty mapped to no_contaminant",
            "all adjudicated acquired papers in the reported frozen group",
            None,
            True,
        ),
        entry(
            "wrong_evidence_mode_contamination",
            metric_source,
            None,
            None,
            None,
            False,
            "A standalone numerator/denominator is not frozen; the raw class count remains reported in the contaminant distribution.",
        ),
        entry(
            "association_vs_functional_relation_contamination",
            metric_source,
            None,
            None,
            None,
            False,
            "A standalone numerator/denominator is not frozen; the raw class count remains reported in the contaminant distribution.",
        ),
        entry(
            "wrong_biological_unit_contamination",
            metric_source,
            None,
            None,
            None,
            False,
            "A standalone numerator/denominator is not frozen; the raw class count remains reported in the contaminant distribution.",
        ),
        entry(
            "per_case_results",
            metric_source,
            "raw frozen label counts and direct-relevance counts by frozen case_id",
            "all adjudicated acquired papers in each frozen case_id",
            None,
            True,
        ),
        entry(
            "per_ambiguity_results",
            metric_source,
            "raw frozen label counts and direct-relevance counts by frozen ambiguity",
            "all adjudicated acquired papers in each frozen ambiguity",
            None,
            True,
        ),
        entry(
            "tier_a_acquisition_acceptability_heuristic",
            heuristic_source,
            None,
            None,
            {"operator": ">=", "value": 0.8},
            False,
            "Threshold is frozen, but the acquisition-acceptability mapping is not.",
        ),
        entry(
            "overall_acquisition_acceptability_heuristic",
            heuristic_source,
            None,
            None,
            {"operator": ">=", "value": 0.65},
            False,
            "Threshold is frozen, but the acquisition-acceptability mapping is not.",
        ),
        entry(
            "review_only_or_wrong_evidence_mode_contamination_heuristic",
            heuristic_source,
            None,
            None,
            {"operator": "<=", "value": 0.15},
            False,
            "The frozen artifact supplies neither a review-only mapping nor a denominator.",
        ),
        entry(
            "tier_b_utility_proxy_heuristic",
            heuristic_source,
            None,
            None,
            {"operator": ">=", "value": 0.3},
            False,
            "The frozen artifact supplies no Tier B utility-proxy mapping or denominator.",
        ),
        entry(
            "no_systematic_contaminant_dominating_most_cases",
            heuristic_source,
            None,
            None,
            None,
            False,
            "The frozen artifact does not define systematic, dominates, or most cases operationally.",
        ),
        entry(
            "no_catastrophic_failure_across_ambiguity_stratum",
            heuristic_source,
            None,
            None,
            None,
            False,
            "The frozen artifact does not define catastrophic failure or its stratum decision rule.",
        ),
    ]
    return {
        "status": "PASS",
        "audit_rule": "No numeric primary result is calculated when a post-hoc choice would be required.",
        "entries": entries,
        "posthoc_primary_metric_definitions_added": 0,
        "all_numeric_primary_results_have_posthoc_choice_required_false": all(
            not item["posthoc_choice_required"]
            for item in entries
            if item["result_status"] == "CALCULATED"
        ),
    }


def heuristic_results():
    specifications = [
        (
            "tier_a_acquisition_acceptability",
            {"operator": ">=", "value": 0.8},
            "Frozen acquisition-acceptability mapping is absent.",
        ),
        (
            "overall_acquisition_acceptability",
            {"operator": ">=", "value": 0.65},
            "Frozen acquisition-acceptability mapping is absent.",
        ),
        (
            "review_only_or_wrong_evidence_mode_contamination",
            {"operator": "<=", "value": 0.15},
            "Frozen review-only mapping and denominator are absent.",
        ),
        (
            "tier_b_utility_proxy",
            {"operator": ">=", "value": 0.3},
            "Frozen utility-proxy mapping and denominator are absent.",
        ),
        (
            "no_systematic_contaminant_dominating_most_cases",
            None,
            "Frozen meanings of systematic, dominates, and most cases are absent.",
        ),
        (
            "no_catastrophic_failure_across_ambiguity_stratum",
            None,
            "Frozen catastrophic-failure and ambiguity-stratum decision rules are absent.",
        ),
    ]
    return {
        "classification": "engineering_calibration_heuristics_not_scientific_thresholds",
        "heuristics": [
            {
                "heuristic_name": name,
                "observed_numerator": None,
                "observed_denominator": None,
                "observed_value": None,
                "threshold": threshold,
                "status": "NOT_EVALUABLE_FROM_FROZEN_DEFINITION",
                "reason": reason,
            }
            for name, threshold, reason in specifications
        ],
        "posthoc_rule_created": False,
    }


def markdown_report(primary, tiers, relevance, acquisition, contaminants, cases, ambiguities, heuristics):
    def metric_line(label, result):
        if result["status"] != "CALCULATED":
            return f"- {label}: {result['status']}"
        return f"- {label}: {result['numerator']}/{result['denominator']} ({result['percentage']:.6f}%)"

    lines = [
        "# Search Plan v2.2 Held-out Validation v1: Primary Metrics",
        "",
        "This report describes the frozen held-out acquired-paper sample. It does not estimate literature-wide precision or recall.",
        "",
        "## Overall primary metrics",
        "",
        metric_line("Direct relevance among adjudicated acquired papers", primary["overall_direct_relevance"]),
        metric_line("Overall acquisition justification", primary["overall_acquisition_justification"]),
        metric_line("Overall acquisition acceptability", primary["overall_acquisition_acceptability"]),
        "",
        "## Tier metrics",
        "",
    ]
    for tier in TIERS:
        lines.extend(
            [
                f"### {tier}",
                "",
                f"- N: {tiers[tier]['N']}",
                metric_line("Direct relevance", tiers[tier]["direct_relevance"]),
            ]
        )
        if tier == "TIER_A":
            lines.append(
                metric_line(
                    "Acquisition acceptability", tiers[tier]["acquisition_acceptable"]
                )
            )
        else:
            lines.append(metric_line("Utility proxy", tiers[tier]["utility_proxy"]))
        lines.append("")
    lines.extend(["## Relevance distribution", ""])
    for name in RELEVANCE_STATES:
        value = relevance["categories"][name]
        lines.append(f"- {name}: {value['count']}/{relevance['denominator']} ({value['percentage']:.6f}%)")
    lines.extend(["", "## Acquisition distribution", ""])
    for name in ACQUISITION_DECISIONS:
        value = acquisition["categories"][name]
        lines.append(f"- {name}: {value['count']}/{acquisition['denominator']} ({value['percentage']:.6f}%)")
    lines.extend(["", "## Contaminant distribution", ""])
    for name in CONTAMINANT_CLASSES:
        value = contaminants["categories"][name]
        lines.append(f"- {name}: {value['count']}/{contaminants['denominator']} ({value['percentage']:.6f}%)")
    lines.extend(["", "## Per-case results", ""])
    for case in CASES:
        value = cases[case]
        lines.append(f"- {case}: N={value['N']}; direct={value['direct_relevance']['numerator']}/{value['N']}; JUSTIFIED={value['acquisition_justified_label_frequency']['numerator']}/{value['N']}; acceptable={value['acquisition_acceptable']['status']}")
    lines.extend(["", "## Per-ambiguity results", ""])
    for ambiguity in AMBIGUITIES:
        value = ambiguities[ambiguity]
        lines.append(f"- {ambiguity}: N={value['N']}; direct={value['direct_relevance']['numerator']}/{value['N']}; JUSTIFIED={value['acquisition_justified_label_frequency']['numerator']}/{value['N']}; acceptable={value['acquisition_acceptable']['status']}")
    lines.extend(["", "## Engineering heuristics", ""])
    for item in heuristics["heuristics"]:
        lines.append(f"- {item['heuristic_name']}: {item['status']}")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Results apply only to the frozen held-out acquired-paper sample and the model_retrieval_adjudicator labels. No Human Gold, literature recall, or literature-wide precision claim is made.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def generate():
    roots = verify_all_roots()
    before = protected_hashes()

    metric_registration = read_json(PROTOCOL / "heldout_evaluation_metrics_preregistration.json")
    heuristic_registration = read_json(PROTOCOL / "heldout_evaluation_heuristics_preregistration.json")
    require(metric_registration["frozen_before_retrieval"] is True, "metrics were not preregistered")
    require(heuristic_registration["frozen_before_retrieval"] is True, "heuristics were not preregistered")

    records = read_jsonl(PRIMARY / "heldout_v1_primary_results.jsonl")
    structure = validate_records(records)
    total = len(records)
    relevance_counts = Counter(record["pass_b"]["relevance_state"] for record in records)
    acquisition_counts = Counter(record["pass_a"]["acquisition_decision"] for record in records)
    contaminant_counts = Counter(contaminant_value(record) for record in records)

    relevance = distribution(relevance_counts, RELEVANCE_STATES, total)
    acquisition = distribution(acquisition_counts, ACQUISITION_DECISIONS, total)
    contaminants = distribution(contaminant_counts, CONTAMINANT_CLASSES, total)

    primary_metrics = {
        "scope": "held-out acquired-paper sample",
        "adjudicator": "model_retrieval_adjudicator",
        "overall_direct_relevance": ratio(relevance_counts["DIRECTLY_RELEVANT"], total),
        "overall_acquisition_justification": not_evaluable(
            "The frozen pre-results metric registration does not define its numerator mapping or denominator."
        ),
        "overall_acquisition_acceptability": not_evaluable(
            "The frozen pre-results metric registration does not define the acceptable-decision mapping or denominator."
        ),
        "literature_wide_precision_claimed": False,
        "literature_recall_claimed": False,
        "human_gold_claimed": False,
    }

    tier_metrics = {}
    for tier in TIERS:
        subset = [record for record in records if record["tier"] == tier]
        direct = sum(record["pass_b"]["relevance_state"] == "DIRECTLY_RELEVANT" for record in subset)
        tier_metrics[tier] = {
            "N": len(subset),
            "direct_relevance": ratio(direct, len(subset)),
        }
    tier_metrics["TIER_A"]["acquisition_acceptable"] = not_evaluable(
        "The frozen pre-results artifacts do not define the acceptable-decision mapping."
    )
    tier_metrics["TIER_B"]["utility_proxy"] = not_evaluable(
        "The frozen pre-results artifacts do not define the Tier B utility-proxy mapping or denominator."
    )

    grouped_cases = defaultdict(list)
    grouped_ambiguities = defaultdict(list)
    for record in records:
        grouped_cases[record["case_id"]].append(record)
        grouped_ambiguities[record["ambiguity"]].append(record)
    per_case = {case: raw_group_metrics(grouped_cases[case]) for case in CASES}
    per_ambiguity = {
        ambiguity: {
            **raw_group_metrics(grouped_ambiguities[ambiguity]),
            "case_count": structure["ambiguity_case_counts"][ambiguity],
        }
        for ambiguity in AMBIGUITIES
    }
    heuristics = heuristic_results()
    definition_audit = metric_definition_audit()

    outputs = {
        "primary_metrics.json": pretty_json(primary_metrics),
        "relevance_distribution.json": pretty_json(relevance),
        "acquisition_distribution.json": pretty_json(acquisition),
        "contaminant_distribution.json": pretty_json(contaminants),
        "per_case_metrics.json": pretty_json(per_case),
        "per_ambiguity_metrics.json": pretty_json(per_ambiguity),
        "tier_metrics.json": pretty_json(tier_metrics),
        "engineering_heuristics.json": pretty_json(heuristics),
        "metric_definition_audit.json": pretty_json(definition_audit),
    }
    outputs["primary_metrics.md"] = markdown_report(
        primary_metrics,
        tier_metrics,
        relevance,
        acquisition,
        contaminants,
        per_case,
        per_ambiguity,
        heuristics,
    )

    metric_components = [
        {"path": name, "sha256": digest(outputs[name])}
        for name in METRIC_RESULT_COMPONENTS
    ]
    metrics_hash = digest(
        canonical_json([(item["path"], item["sha256"]) for item in metric_components])
    )

    outputs["root_hash_verification.json"] = pretty_json(
        {
            "status": "PASS",
            "all_six_frozen_roots_verified": True,
            "roots": roots,
            **EXPECTED_ROOTS,
        }
    )
    after = protected_hashes()
    require(before == after, "protected frozen state changed")
    safety = {
        **ZERO_CALLS,
        **ZERO_MODIFICATIONS,
        "offline_only": True,
        "all_six_frozen_roots_unchanged": True,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
    }
    outputs["scientific_state_safety_audit.json"] = pretty_json(safety)
    manifest = {
        **EXPECTED_ROOTS,
        "heldout_v1_primary_metrics_sha256": metrics_hash,
        "hash_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "metric_result_components": metric_components,
        "metric_result_component_count": len(metric_components),
        "primary_metrics_calculated": True,
        "scientific_state_read_only": True,
    }
    outputs["manifest.json"] = pretty_json(manifest)
    checks = {
        "all_six_frozen_roots_verified": True,
        "primary_record_count_70": structure["record_count"] == 70,
        "primary_unique_packet_ids_70": structure["unique_packet_ids"] == 70,
        "all_frozen_categories_accounted_for": (
            sum(value["count"] for value in relevance["categories"].values()) == total
            and sum(value["count"] for value in acquisition["categories"].values()) == total
            and sum(value["count"] for value in contaminants["categories"].values()) == total
        ),
        "ambiguity_case_assignment_preserved": structure["ambiguity_case_counts"]
        == {"LOW": 2, "MEDIUM": 2, "HIGH": 4},
        "all_numeric_primary_definitions_operationally_complete": definition_audit[
            "all_numeric_primary_results_have_posthoc_choice_required_false"
        ],
        "posthoc_primary_metric_definitions_added_zero": definition_audit[
            "posthoc_primary_metric_definitions_added"
        ]
        == 0,
        "under_specified_heuristics_not_evaluated": all(
            item["status"] == "NOT_EVALUABLE_FROM_FROZEN_DEFINITION"
            for item in heuristics["heuristics"]
        ),
        "metric_component_hash_valid": metrics_hash
        == digest(canonical_json([(item["path"], item["sha256"]) for item in metric_components])),
        "scientific_state_unchanged": before == after,
        "offline_counters_zero": all(value == 0 for value in ZERO_CALLS.values()),
    }
    require(all(checks.values()), "metrics validation failed")
    outputs["validation.json"] = pretty_json({"status": "PASS", "checks": checks})
    outputs["summary.json"] = pretty_json(
        {
            "status": "completed",
            **EXPECTED_ROOTS,
            "heldout_v1_primary_metrics_sha256": metrics_hash,
            **structure,
            **ZERO_CALLS,
            **ZERO_MODIFICATIONS,
            "primary_metrics_calculated": True,
            "posthoc_primary_metric_definitions_added": 0,
            "historical_assets_modified": False,
            "deterministic_metric_result_component_count": len(metric_components),
        }
    )
    require(set(outputs) == REQUIRED_OUTPUTS, "required output membership mismatch")
    return outputs


def main():
    outputs = generate()
    if RUN.exists():
        require(RUN.is_dir() and not RUN.is_symlink(), "existing output path is invalid")
        require({path.name for path in RUN.iterdir()} == set(outputs), "existing output membership differs")
        require(
            all((RUN / name).read_bytes() == data for name, data in outputs.items()),
            "existing output differs; refusing overwrite",
        )
    else:
        RUN.mkdir()
        for name, data in outputs.items():
            with (RUN / name).open("xb") as handle:
                handle.write(data)
    print(outputs["summary.json"].decode("utf-8"))


if __name__ == "__main__":
    main()
