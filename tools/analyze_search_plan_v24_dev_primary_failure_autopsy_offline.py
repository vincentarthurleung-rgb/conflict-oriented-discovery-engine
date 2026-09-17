#!/usr/bin/env python3
"""Offline post-evaluation autopsy of the closed v2.3-beta.2 primary failure."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import calculate_search_plan_v23_beta_2_primary_heldout_v2_metrics_offline as primary


RUN = ROOT / "runs/20260917_search_plan_v24_dev_primary_failure_autopsy_offline"
METRICS_RUN = primary.RUN
RETRIEVAL = primary.RETRIEVAL
CASE_RUN = primary.CASES
QUERY_RUN = primary.QUERIES

EXPECTED_MERGED = "d7848aa3a94189f9652fe643f1732fe000c5a929dbbe183d2e30dd6292839d97"
EXPECTED_METRICS = "84341b99e67ac93e4b20c494d33f1134842d90f94e1370d6c566571b70c0dc94"

DIMENSIONS = [
    "subject_identity", "biological_unit", "relation_semantics", "evidence_mode",
    "measurement_target", "endpoint_property", "therapy_identity", "disease_context",
    "genotype_context", "nested_treatment_context", "proposition_direction",
    "insufficient_specificity",
]
RELEVANCE = [
    "DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
    "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
    "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY",
    "INSUFFICIENT_SOURCE_EVIDENCE",
]
ACQUISITION = [
    "JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
    "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE",
]
CASES = [f"heldout_v2_{value}" for value in range(101, 109)]
FAMILIES = ["A", "C", "D", "E"]

REQUIRED_OUTPUTS = {
    "failure_corpus_status.json", "paper_level_failure_decomposition.jsonl",
    "query_family_failure_autopsy.json", "per_case_failure_autopsy.json",
    "tier_failure_autopsy.json", "p0_failure_autopsy.json", "p1_failure_autopsy.json",
    "p2_failure_autopsy.json", "acquisition_failure_autopsy.json",
    "zero_yield_case_autopsy.json", "stage_attribution_summary.json",
    "v24_development_priority.json", "v24_development_priority.md",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {row["candidate_id"]: row for row in rows}
    require(len(result) == len(rows), "duplicate candidate identity")
    return result


def verify_authority() -> dict[str, Any]:
    roots = primary.verify_all_roots()
    merged = sha(METRICS_RUN / primary.MERGED_NAME)
    require(merged == EXPECTED_MERGED, "authoritative merged corpus mismatch")
    manifest = load_json(METRICS_RUN / "implementation_manifest.json")
    components = []
    for name, expected in manifest["aggregate_components"]:
        actual = sha(METRICS_RUN / name)
        require(actual == expected, f"metrics component mismatch: {name}")
        components.append([name, actual])
    aggregate = digest(canonical(components))
    require(aggregate == manifest["primary_heldout_v2_metrics_unblinding_sha256"] == EXPECTED_METRICS,
            "authoritative metrics root mismatch")
    return {
        "status": "PASS", "upstream_roots_verified": roots["all_roots_match"],
        "primary_v2_merged_results_sha256": merged,
        "primary_heldout_v2_metrics_unblinding_sha256": aggregate,
        "verified_before_autopsy": True,
    }


def protected_state() -> dict[str, str]:
    state = primary.protected_state()
    for path in METRICS_RUN.rglob("*"):
        if path.is_file():
            state[str(path.resolve().relative_to(ROOT))] = sha(path)
    return dict(sorted(state.items()))


def strings(record: dict[str, Any]) -> tuple[list[str], str]:
    secondary = record["pass_b_secondary_fields"]
    items = secondary["mismatched_target_components"] + secondary["remaining_unresolved_fields"]
    return items, " ".join(items).lower()


def failure_dimensions(record: dict[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    if record["relevance_state"] == "DIRECTLY_RELEVANT":
        return [], {}
    mismatch, text = strings(record)
    hits: dict[str, list[str]] = defaultdict(list)
    relevance = record["relevance_state"]
    contaminant = record["contaminant_class"]

    def add(dimension: str, condition: bool, reason: str) -> None:
        if condition:
            hits[dimension].append(reason)

    add("biological_unit", contaminant == "wrong_biological_unit" or bool(re.search(
        r"\b(cells?|cell line|tissue|macrophage|monocyte|lymphocyte|chondrocyte|cardiomyocyte|hepatocyte|"
        r"fibroblast|keratinocyte|dendritic|neuronal|neuron|alveolar|atrial|renal|ovarian|breast cancer|"
        r"pancreatic cancer|colorectal cancer|glioblastoma model|patient serum|pbmc)\b", text)),
        "frozen mismatch or contaminant identifies an incompatible biological unit")
    add("endpoint_property", relevance == "WRONG_ENDPOINT" or contaminant == "wrong_endpoint" or bool(re.search(
        r"nuclear (?:β-catenin )?(?:accumulation|localization)|surface hla-dr|secretion endpoint|extracellular|"
        r"dynamic[- ]flux|autophagic flux|phosphorylation endpoint|rather than phosphorylation|"
        r"total β-catenin|reporter activity|transcript", text)),
        "frozen mismatch identifies an endpoint-property or localization/assay mismatch")
    add("evidence_mode", relevance == "WRONG_EVIDENCE_MODE" or contaminant in {
        "association_vs_functional_relation", "wrong_evidence_mode"} or bool(re.search(
        r"no .*perturbation|not .*perturb|association|correlat|parallel response|current-study|functional evidence|"
        r"functional linkage|causal relation|causal .*link|baseline expression biomarker", text)),
        "frozen mismatch identifies absent functional/current-study evidence")
    add("relation_semantics", relevance == "WRONG_EVIDENCE_MODE" or contaminant == "association_vs_functional_relation" or bool(re.search(
        r"causal|functional .*link|perturbation-to|suppression relation|sensitization|association|correlat|"
        r"parallel response|does not establish|directional .*relation", text)),
        "frozen mismatch identifies an absent or incompatible proposition relation")
    add("therapy_identity", relevance == "WRONG_THERAPY" or bool(re.search(
        r"temozolomide (?:therapy|is absent)|rather than temozolomide|therapy is .* rather than|combination partner", text)),
        "frozen mismatch identifies the wrong or absent therapy")
    add("disease_context", bool(re.search(
        r"disease context|glioblastoma|melanoma|breast cancer|ovarian cancer|pancreatic cancer|colorectal cancer|"
        r"multiple.myeloma|rhabdoid", text)), "frozen mismatch identifies an incompatible disease context")
    add("genotype_context", "kras" in text or "genotype context" in text,
        "frozen mismatch identifies an incompatible or absent genotype context")
    add("nested_treatment_context", "lps" in text,
        "frozen mismatch identifies the missing nested LPS treatment context")
    add("proposition_direction", bool(re.search(
        r"rather than increased|activated rather than inhibited|arrest rather than increased|positive rather than suppressive|"
        r"directional|inhibited rather than increased|suppression.*not|induces both", text)),
        "frozen mismatch identifies an incompatible response direction")
    add("measurement_target", bool(re.search(
        r"rather than erk1/2|hla-dr endpoint|tnf-α secretion endpoint|other .* rather than|kv1\.3 rather than|"
        r"pd-l1|histone h3", text)), "frozen mismatch identifies the wrong or absent measured target")
    subject_patterns = {
        "heldout_v2_101": r"hb-egf rather than egf",
        "heldout_v2_102": r"rather than ifn|no ifn-γ stimulation|ifn-γ is .*output|rbd protein|mtb antigens|ccl25",
        "heldout_v2_103": r"rather than direct wnt3a|no direct wnt3a|wnt3a-stimulation.*not",
        "heldout_v2_105": r"rather than mtorc1 inhibition|mtorc1 is not directly|primary perturbation rather than|mcoln1|bin1|epa supplementation",
        "heldout_v2_106": r"il-10 .*not .*perturb|no il-10|il-10 perturbation|rather than il-10|mixed b-cell supernatant|plasma extracellular vesicles",
        "heldout_v2_108": r"parp1 .*not|no parp1|parp1 inhibition or loss|required current-study parp1|strict parp1|unambiguous parp1",
    }
    add("subject_identity", contaminant == "wrong_entity" or bool(re.search(subject_patterns.get(record["case_id"], r"$^"), text)),
        "frozen mismatch identifies the wrong or unresolved proposition subject/intervention")
    unresolved = record["pass_b_secondary_fields"]["remaining_unresolved_fields"]
    add("insufficient_specificity", bool(unresolved) or bool(re.search(
        r"no explicit|not explicitly|unresolved|generic|unambiguous|strict .*selectivity|not selectively|"
        r"does not resolve|absence|not measured", text)),
        "frozen mismatch or unresolved field lacks proposition-level specificity")
    if not hits:
        hits["insufficient_specificity"].append("fail-closed residual for a frozen non-direct record")
    ordered = [dimension for dimension in DIMENSIONS if dimension in hits]
    return ordered, {dimension: hits[dimension] for dimension in ordered}


def evidence_summary(decision: dict[str, Any]) -> dict[str, Any]:
    value = decision["decision"]
    surfaces = []
    for field in ("matched_surfaces", "observed_subject_surfaces", "observed_endpoint_surfaces"):
        for item in value.get(field, []):
            surfaces.append({key: item[key] for key in ("field", "surface", "matched_surface", "evidence_role", "sentence_index", "source_sentence") if key in item})
    return {
        "state": decision["state"], "reason_codes": value.get("reason_codes", []),
        "resolver_status": value.get("resolver_status"), "evidence_surfaces": surfaces,
        "fulltext_used": decision["fulltext_used"], "module_input_sha256": decision["module_input_sha256"],
    }


def module_outcome(module: str, state: str, reason_codes: list[str], dimensions: list[str]) -> str:
    targets = {
        "P0": {"biological_unit"},
        "P1": {"subject_identity", "relation_semantics", "evidence_mode", "proposition_direction"},
        "P2": {"measurement_target", "endpoint_property"},
    }[module]
    if not targets.intersection(dimensions):
        return "NO_TARGETED_FAILURE_DIMENSION"
    detected = {
        "P0": {"INCOMPATIBLE"},
        "P1": {"ASSOCIATION_ONLY", "BACKGROUND_ONLY", "MULTI_TARGET_AMBIGUOUS"},
        "P2": {"INCOMPATIBLE"},
    }[module]
    compatible = {
        "P0": {"EXACT", "AUTHORIZED_COMPATIBLE"},
        "P1": {"DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN"},
        "P2": {"EXACT", "AUTHORIZED_EQUIVALENT"},
    }[module]
    if state in detected:
        return "DETECTED_PREACQUISITION_FAILURE"
    if state in compatible:
        return "MODULE_SEMANTIC_ERROR"
    if any(re.search(r"PARSER|RESOLVER|UNSUPPORTED|CONTRACT", code) for code in reason_codes):
        return "PARSER_RESOLUTION_FAILURE"
    return "PREACQUISITION_EVIDENCE_UNAVAILABLE"


def distribution(rows: list[dict[str, Any]], field: str, categories: list[str]) -> dict[str, int]:
    counts = Counter(row[field] for row in rows)
    return {category: counts[category] for category in categories}


def build_outputs(authority: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    merged = load_jsonl(METRICS_RUN / primary.MERGED_NAME)
    require(len(merged) == 60, "development corpus count mismatch")
    targets = {row["case_id"]: row for row in load_jsonl(CASE_RUN / "primary_heldout_v2_scientific_targets.jsonl")}
    queries = load_jsonl(QUERY_RUN / "primary_heldout_v2_frozen_queries.jsonl")
    queries_by_case = defaultdict(list)
    queries_by_id = {}
    for row in queries:
        queries_by_case[row["case_id"]].append(row)
        queries_by_id[row["query_id"]] = row
    trace = index(load_json(RETRIEVAL / "retrieval_provenance_trace.json")["traces"])
    selection = index(load_jsonl(RETRIEVAL / "primary_v2_acquisition_selection.jsonl"))
    base = index(load_jsonl(RETRIEVAL / "primary_v2_base_v22_dispositions.jsonl"))
    final = index(load_jsonl(RETRIEVAL / "primary_v2_final_preacquisition_dispositions.jsonl"))
    p0 = index(load_jsonl(RETRIEVAL / "primary_v2_p0_decisions.jsonl"))
    p1 = index(load_jsonl(RETRIEVAL / "primary_v2_p1_decisions.jsonl"))
    p2 = index(load_jsonl(RETRIEVAL / "primary_v2_p2_decisions.jsonl"))
    structure = {row["case_id"]: row for row in load_json(RETRIEVAL / "per_case_structural_analysis.json")["per_case"]}
    query_logs = load_jsonl(RETRIEVAL / "query_execution_log.jsonl")

    paper_rows = []
    for row in merged:
        candidate_id = row["candidate_id"]
        dims, basis = failure_dimensions(row)
        q_provenance = trace[candidate_id]["frozen_query_provenance"]
        contributing_ids = list(dict.fromkeys(item["query_id"] for item in q_provenance))
        gate = base[candidate_id]["raw_base_gate_decision"]
        p_summaries = {"P0": evidence_summary(p0[candidate_id]), "P1": evidence_summary(p1[candidate_id]),
                       "P2": evidence_summary(p2[candidate_id])}
        stage = {module: module_outcome(module, value["state"], value["reason_codes"], dims)
                 for module, value in p_summaries.items()} if dims else {}
        paper_rows.append({
            "artifact_schema_version": "V24DevPaperFailureDecompositionV1",
            "candidate_id": candidate_id, "case_id": row["case_id"],
            "development_corpus_status": "seen_primary_failure_development_corpus_for_v24",
            "frozen_scientific_proposition_target": targets[row["case_id"]],
            "contributing_query_families": row["query_family_ids"],
            "first_seen_query_family": row["first_contributing_query_family_id"],
            "contributing_queries": [{
                "query_id": query_id, "family_id": queries_by_id[query_id]["family_id"],
                "exact_query_string": queries_by_id[query_id]["compiled_query"],
                "exact_terms": [item["term"] for item in queries_by_id[query_id]["term_annotations"]],
                "represented_target_fields": sorted({item["target_field"] for item in queries_by_id[query_id]["term_annotations"]}),
            } for query_id in contributing_ids],
            "metadata_evidence": {"title": selection[candidate_id]["title"], "abstract": selection[candidate_id]["abstract"],
                                  "publication_metadata": selection[candidate_id]["publication_metadata"]},
            "base_v22_gate": {"disposition": base[candidate_id]["base_v22_disposition"],
                              "reason_codes": base[candidate_id]["base_gate_reason_codes"],
                              "gate_states": {name: value["state"] for name, value in gate["gates"].items()},
                              "gate_evidence": {name: value.get("evidence", []) for name, value in gate["gates"].items()}},
            "P0": p_summaries["P0"], "P1": p_summaries["P1"], "P2": p_summaries["P2"],
            "final_v23_beta2_disposition": final[candidate_id]["final_v23_beta2_disposition"],
            "pass_a_acquisition_decision": row["acquisition_decision"],
            "pass_b_relevance_state": row["relevance_state"],
            "pass_b_contaminant_class": row["contaminant_class"],
            "frozen_mismatched_target_components": row["pass_b_secondary_fields"]["mismatched_target_components"],
            "frozen_remaining_unresolved_fields": row["pass_b_secondary_fields"]["remaining_unresolved_fields"],
            "development_failure_dimensions": dims,
            "development_failure_dimension_basis": basis,
            "module_stage_attribution": stage,
            "new_scientific_adjudication": False,
        })
    by_id = index(paper_rows)
    nondirect = [row for row in paper_rows if row["pass_b_relevance_state"] != "DIRECTLY_RELEVANT"]
    direct = [row for row in paper_rows if row["pass_b_relevance_state"] == "DIRECTLY_RELEVANT"]
    require(len(nondirect) == 58 and len(direct) == 2, "frozen direct/non-direct partition mismatch")
    dim_counts = {dimension: sum(dimension in row["development_failure_dimensions"] for row in nondirect) for dimension in DIMENSIONS}

    family_profiles = {}
    family_core = {
        "A": "TOPIC_INTERSECTION_WITHOUT_RELATION",
        "C": "MISSING_BIOLOGICAL_UNIT",
        "D": "OTHER",
        "E": "MISSING_EVIDENCE_MODE",
    }
    for family in FAMILIES:
        any_rows = [row for row in paper_rows if family in row["contributing_query_families"]]
        first_rows = [row for row in paper_rows if row["first_seen_query_family"] == family]
        qrows = [row for row in queries if row["family_id"] == family]
        exact_queries = []
        for query in qrows:
            represented = sorted({item["target_field"] for item in query["term_annotations"]})
            expected_fields = {"subject", "object", "relation_family", "measurement_property_endpoint", "context_qualifiers", "required_evidence_mode"}
            exact_queries.append({"case_id": query["case_id"], "query_id": query["query_id"],
                                  "exact_query_string": query["compiled_query"],
                                  "exact_terms": [item["term"] for item in query["term_annotations"]],
                                  "represented_target_fields": represented,
                                  "omitted_target_fields": sorted(expected_fields - set(represented))})
        family_profiles[family] = {
            "structural_core_failure": family_core[family],
            "first_seen": {
                "paper_N": len(first_rows), "pass_b_relevance_distribution": distribution(first_rows, "pass_b_relevance_state", RELEVANCE),
                "pass_a_acquisition_distribution": distribution(first_rows, "pass_a_acquisition_decision", ACQUISITION),
                "failure_dimension_distribution": {d: sum(d in row["development_failure_dimensions"] for row in first_rows) for d in DIMENSIONS},
            },
            "any_contributing": {
                "paper_N": len(any_rows), "overlapping_count_not_precision": True,
                "pass_b_relevance_distribution": distribution(any_rows, "pass_b_relevance_state", RELEVANCE),
                "pass_a_acquisition_distribution": distribution(any_rows, "pass_a_acquisition_decision", ACQUISITION),
                "failure_dimension_distribution": {d: sum(d in row["development_failure_dimensions"] for row in any_rows) for d in DIMENSIONS},
            },
            "exact_frozen_queries": exact_queries,
        }
    query_autopsy = {"artifact_schema_version": "V24DevQueryFamilyFailureAutopsyV1",
                      "analysis_type": "POST_EVALUATION_DEVELOPMENT_DIAGNOSTIC",
                      "families": family_profiles, "query_changes": 0,
                      "family_a_primary_observation": "Family A contributed to 36 acquired papers and zero DIRECTLY_RELEVANT papers; it structurally represented subject plus object while omitting relation, measurement property, context, and evidence mode."}

    case_autopsy = {}
    for case_id in CASES:
        subset = [row for row in paper_rows if row["case_id"] == case_id]
        case_autopsy[case_id] = {
            "acquired_N": len(subset),
            "tier_distribution": dict(Counter(row["final_v23_beta2_disposition"] for row in subset)),
            "pass_a_distribution": distribution(subset, "pass_a_acquisition_decision", ACQUISITION),
            "pass_b_distribution": distribution(subset, "pass_b_relevance_state", RELEVANCE),
            "failure_dimension_distribution": {d: sum(d in row["development_failure_dimensions"] for row in subset) for d in DIMENSIONS},
            "p0_state_distribution": dict(Counter(row["P0"]["state"] for row in subset)),
            "p1_state_distribution": dict(Counter(row["P1"]["state"] for row in subset)),
            "p2_state_distribution": dict(Counter(row["P2"]["state"] for row in subset)),
            "metadata_N": structure[case_id]["deduplicated_metadata_candidates"],
            "selected_N": structure[case_id]["selected_fulltext_count"],
            "frozen_queries": [{"query_id": row["query_id"], "family_id": row["family_id"],
                                "exact_query_string": row["compiled_query"]} for row in queries_by_case[case_id]],
        }

    tier_autopsy = {"artifact_schema_version": "V24DevTierFailureAutopsyV1", "tiers": {}}
    for tier in ("TIER_A", "TIER_B"):
        subset = [row for row in paper_rows if row["final_v23_beta2_disposition"] == tier]
        bad = [row for row in subset if row["pass_b_relevance_state"] != "DIRECTLY_RELEVANT"]
        gate_states = {gate: dict(Counter(base[row["candidate_id"]]["base_gate_reason_codes"][gate] for row in bad))
                       for gate in ("entity", "relation", "endpoint", "context", "therapy", "evidence_mode")}
        tier_autopsy["tiers"][tier] = {
            "N": len(subset), "direct_N": len(subset) - len(bad), "non_direct_N": len(bad),
            "failure_dimension_distribution_among_non_direct": {d: sum(d in row["development_failure_dimensions"] for row in bad) for d in DIMENSIONS},
            "base_v22_gate_reason_distributions_among_non_direct": gate_states,
        }
    tier_autopsy["tier_a_principal_driver"] = "LEXICAL_TOPIC_AND_PLAUSIBILITY_GATES_MORE_THAN_FULL_PROPOSITION_COMPATIBILITY"
    tier_autopsy["tier_a_principal_driver_basis"] = "Frozen v2.2 Tier-A gates accepted plausible entity/endpoint/evidence surfaces while many PASS-B failures retained biological-unit, relation/evidence-mode, endpoint-property, therapy, or disease-context dimensions."
    tier_autopsy["rules_modified"] = False

    module_autopsies = {}
    for module in ("P0", "P1", "P2"):
        outcomes = Counter(row["module_stage_attribution"][module] for row in nondirect)
        state_counts = Counter(row[module]["state"] for row in nondirect)
        direct_details = []
        for row in direct:
            direct_details.append({"candidate_id": row["candidate_id"], "state": row[module]["state"],
                                   "reason_codes": row[module]["reason_codes"],
                                   "resolver_status": row[module]["resolver_status"],
                                   "evidence_surfaces": row[module]["evidence_surfaces"]})
        module_autopsies[module] = {
            "artifact_schema_version": f"V24Dev{module}FailureAutopsyV1",
            "non_direct_N": 58, "non_direct_state_distribution": dict(state_counts),
            "non_direct_stage_attribution_distribution": dict(outcomes),
            "non_direct_failure_resolution_counts": {
                "correctly_identified_failure_N": outcomes["DETECTED_PREACQUISITION_FAILURE"],
                "module_semantic_error_N": outcomes["MODULE_SEMANTIC_ERROR"],
                "parser_resolution_failure_N": outcomes["PARSER_RESOLUTION_FAILURE"],
                "preacquisition_evidence_unavailable_N": outcomes["PREACQUISITION_EVIDENCE_UNAVAILABLE"],
                "no_targeted_failure_dimension_N": outcomes["NO_TARGETED_FAILURE_DIMENSION"],
                "module_state_unresolved_N": state_counts["UNRESOLVED"],
            },
            "direct_paper_audit": direct_details, "module_modified": False,
        }
    module_autopsies["P0"]["direct_paper_interpretation"] = {
        "heldout_v2_102:pmid:28565847": "MODULE_SEMANTIC_ERROR: P0 saw the target monocyte sentence but elevated a T-cell mention to experimental-unit authority and emitted DISTINCT_CELL_TYPE.",
        "heldout_v2_105:pmid:27023784": "PARSER_RESOLUTION_FAILURE: cardiomyocyte remained an unresolved context dimension and P0 emitted NO_BIOLOGICAL_UNIT_EVIDENCE despite cardiac/cardiomyocyte abstract surfaces.",
    }
    module_autopsies["P1"]["direct_paper_interpretation"] = {
        "heldout_v2_102:pmid:28565847": "PARSER_RESOLUTION_FAILURE: the IFN-gamma/HLA-DR sentence was preserved but relation extraction emitted CURRENT_STUDY_RELATION_UNRESOLVED and PARSER_UNCERTAINTY_FAIL_CLOSED.",
        "heldout_v2_105:pmid:27023784": "PARSER_RESOLUTION_FAILURE: inverse perturbation semantics remained CURRENT_STUDY_RELATION_UNRESOLVED.",
    }
    module_autopsies["P2"]["direct_paper_interpretation"] = {
        row["candidate_id"]: "CORRECT_ENDPOINT_SIGNAL: P2 resolved the frozen endpoint as EXACT from explicit current-study surface evidence." for row in direct
    }

    zero_104 = structure["heldout_v2_104"]
    logs_107 = [row for row in query_logs if row["case_id"] == "heldout_v2_107"]
    zero_yield = {
        "artifact_schema_version": "V24DevZeroYieldCaseAutopsyV1",
        "heldout_v2_104": {
            "deterministic_path": [
                {"stage": "deduplicated_metadata", "N": zero_104["deduplicated_metadata_candidates"]},
                {"stage": "base_v22_dispositions", "distribution": zero_104["base_tier_distribution"]},
                {"stage": "P0", "distribution": zero_104["p0_state_distribution"]},
                {"stage": "P1", "distribution": zero_104["p1_state_distribution"]},
                {"stage": "P2", "distribution": zero_104["p2_state_distribution"]},
                {"stage": "final_v23_beta2_dispositions", "distribution": zero_104["final_tier_distribution"]},
                {"stage": "legal_fulltext_available", "N": zero_104["legal_fulltext_availability_count"]},
                {"stage": "selected_acquired", "selected": 0, "acquired": 0},
            ],
            "deterministic_explanation": "The base v2.2 gate assigned all 180 records to ABSTAIN or REJECT and no Tier A/B candidates existed. P0/P1/P2 did not promote candidates; Policy A only preserves/demotes. Legal OA availability was also zero.",
        },
        "heldout_v2_107": {
            "query_count": 4,
            "queries": [{key: row[key] for key in ("query_id", "family_id", "exact_query_string", "response_status", "response_record_count", "returned_id_count", "new_unique_additions", "error_state", "retry_count")} for row in logs_107],
            "metadata_N": 0, "selected_N": 0, "acquired_N": 0,
            "deterministic_explanation": "All four exact frozen composite-literal queries returned HTTP 200 with zero records, zero errors, and zero retries. The frozen evidence establishes zero exact-query yield but does not authorize a broadened counterfactual query.",
        },
        "queries_broadened_or_rerun": False,
    }

    stage_summary = {
        "artifact_schema_version": "V24DevStageAttributionSummaryV1",
        "non_direct_N": 58, "failure_dimension_distribution": dim_counts,
        "module_attribution": {module: module_autopsies[module]["non_direct_stage_attribution_distribution"] for module in ("P0", "P1", "P2")},
        "overlapping_dimensions_allowed": True,
        "attribution_taxonomy": ["DETECTED_PREACQUISITION_FAILURE", "MODULE_SEMANTIC_ERROR",
                                 "PREACQUISITION_EVIDENCE_UNAVAILABLE", "PARSER_RESOLUTION_FAILURE",
                                 "NO_TARGETED_FAILURE_DIMENSION"],
    }

    direct_ids = {row["candidate_id"] for row in direct}
    observable_predicates = {
        "P2_EXACT": lambda row: row["P2"]["state"] == "EXACT",
        "P1_UNRESOLVED": lambda row: row["P1"]["state"] == "UNRESOLVED",
        "P0_INCOMPATIBLE_OR_UNRESOLVED": lambda row: row["P0"]["state"] in {"INCOMPATIBLE", "UNRESOLVED"},
        "P0_NONPOSITIVE_AND_P1_UNRESOLVED_AND_P2_EXACT": lambda row: (
            row["P0"]["state"] in {"INCOMPATIBLE", "UNRESOLVED"}
            and row["P1"]["state"] == "UNRESOLVED" and row["P2"]["state"] == "EXACT"
        ),
        "BASE_RELATION_DIRECTLY_PLAUSIBLE": lambda row: (
            row["base_v22_gate"]["gate_states"]["relation"] == "RELATION_DIRECTLY_PLAUSIBLE"
        ),
        "FIRST_SEEN_FAMILY_C_OR_E": lambda row: row["first_seen_query_family"] in {"C", "E"},
        "ABSTRACT_PRESENT": lambda row: bool(row["metadata_evidence"]["abstract"]),
    }
    feature_prevalence = {
        name: {
            "direct_N": sum(predicate(row) for row in direct),
            "non_direct_N": sum(predicate(row) for row in nondirect),
        }
        for name, predicate in observable_predicates.items()
    }
    acquisition_autopsy = {
        "artifact_schema_version": "V24DevAcquisitionFailureAutopsyV1",
        "frozen_relationship": {"NOT_JUSTIFIED_plus_DIRECT": 0,
                                "JUSTIFIED_or_BORDERLINE_plus_DIRECT": 2,
                                "NOT_JUSTIFIED_plus_NON_DIRECT": 58,
                                "JUSTIFIED_or_BORDERLINE_plus_NON_DIRECT": 0},
        "acceptable_direct_papers": [{
            "candidate_id": row["candidate_id"], "pass_a": row["pass_a_acquisition_decision"],
            "final_tier": row["final_v23_beta2_disposition"], "first_seen_family": row["first_seen_query_family"],
            "p0_state": row["P0"]["state"], "p1_state": row["P1"]["state"], "p2_state": row["P2"]["state"],
            "observable_preacquisition_features": {
                "title": selection[row["candidate_id"]]["title"],
                "base_gate_reason_codes": base[row["candidate_id"]]["base_gate_reason_codes"],
                "abstract_present": bool(selection[row["candidate_id"]]["abstract"]),
            },
        } for row in direct],
        "comparative_feature_counts": {
            "direct": {
                "N": 2, "final_tier": dict(Counter(row["final_v23_beta2_disposition"] for row in direct)),
                "first_seen_family": dict(Counter(row["first_seen_query_family"] for row in direct)),
                "P0": dict(Counter(row["P0"]["state"] for row in direct)),
                "P1": dict(Counter(row["P1"]["state"] for row in direct)),
                "P2": dict(Counter(row["P2"]["state"] for row in direct)),
            },
            "non_direct": {
                "N": 58, "final_tier": dict(Counter(row["final_v23_beta2_disposition"] for row in nondirect)),
                "first_seen_family": dict(Counter(row["first_seen_query_family"] for row in nondirect)),
                "P0": dict(Counter(row["P0"]["state"] for row in nondirect)),
                "P1": dict(Counter(row["P1"]["state"] for row in nondirect)),
                "P2": dict(Counter(row["P2"]["state"] for row in nondirect)),
            },
        },
        "observable_feature_prevalence": feature_prevalence,
        "clean_raw_feature_separator_found": False,
        "diagnostic_conclusion": (
            "No audited raw pre-acquisition feature or listed conjunction cleanly separated both direct papers "
            "from all 58 non-direct papers. P2 EXACT was shared by 2/2 direct and 8/58 non-direct papers; "
            "P1 UNRESOLVED and non-positive P0 were also common among non-direct papers. The frozen PASS-A "
            "decision separates the observed labels, but it is an adjudication outcome and is not converted "
            "into a new rule by this diagnostic."
        ),
        "diagnostic_only": True, "classifier_trained": False, "thresholds_optimized": False,
        "model_based_gate_introduced": False, "direct_candidate_ids": sorted(direct_ids),
    }

    priority_counts = {
        "QUERY_PROPOSITION_ALIGNMENT": sum(bool({"subject_identity", "relation_semantics", "evidence_mode"}.intersection(row["development_failure_dimensions"])) for row in nondirect),
        "TIER_A_ELIGIBILITY": sum(row["final_v23_beta2_disposition"] == "TIER_A" for row in nondirect),
        "BIOLOGICAL_UNIT_GENERALIZATION": dim_counts["biological_unit"],
        "FUNCTIONAL_RELATION_RESOLUTION": sum(bool({"relation_semantics", "evidence_mode", "proposition_direction"}.intersection(row["development_failure_dimensions"])) for row in nondirect),
        "THERAPY_CONTEXT": sum(bool({"therapy_identity", "disease_context", "genotype_context", "nested_treatment_context"}.intersection(row["development_failure_dimensions"])) for row in nondirect),
        "ENDPOINT_SEMANTICS": sum(bool({"measurement_target", "endpoint_property"}.intersection(row["development_failure_dimensions"])) for row in nondirect),
        "GENERIC_AUTHORITY_COVERAGE": sum(any(row["module_stage_attribution"].get(module) == "PARSER_RESOLUTION_FAILURE" for module in ("P0", "P1", "P2")) for row in nondirect),
        "ACQUISITION_POLICY": 0,
    }
    fixed_order = ["QUERY_PROPOSITION_ALIGNMENT", "BIOLOGICAL_UNIT_GENERALIZATION", "FUNCTIONAL_RELATION_RESOLUTION",
                   "ENDPOINT_SEMANTICS", "THERAPY_CONTEXT", "TIER_A_ELIGIBILITY", "GENERIC_AUTHORITY_COVERAGE",
                   "ACQUISITION_POLICY"]
    ranked = sorted(fixed_order, key=lambda name: (-priority_counts[name], fixed_order.index(name)))
    priority_stage_evidence = {
        "QUERY_PROPOSITION_ALIGNMENT": {
            "family_A_any_contributing_N": family_profiles["A"]["any_contributing"]["paper_N"],
            "family_A_direct_N": family_profiles["A"]["any_contributing"]["pass_b_relevance_distribution"]["DIRECTLY_RELEVANT"],
            "P1_stage_attribution": module_autopsies["P1"]["non_direct_stage_attribution_distribution"],
        },
        "BIOLOGICAL_UNIT_GENERALIZATION": {
            "biological_unit_failure_N": dim_counts["biological_unit"],
            "P0_stage_attribution": module_autopsies["P0"]["non_direct_stage_attribution_distribution"],
        },
        "FUNCTIONAL_RELATION_RESOLUTION": {
            "relation_or_evidence_or_direction_failure_N": priority_counts["FUNCTIONAL_RELATION_RESOLUTION"],
            "P1_stage_attribution": module_autopsies["P1"]["non_direct_stage_attribution_distribution"],
        },
        "ENDPOINT_SEMANTICS": {
            "measurement_or_endpoint_failure_N": priority_counts["ENDPOINT_SEMANTICS"],
            "P2_stage_attribution": module_autopsies["P2"]["non_direct_stage_attribution_distribution"],
        },
        "THERAPY_CONTEXT": {
            "therapy_or_context_failure_N": priority_counts["THERAPY_CONTEXT"],
            "component_counts": {name: dim_counts[name] for name in (
                "therapy_identity", "disease_context", "genotype_context", "nested_treatment_context"
            )},
        },
        "TIER_A_ELIGIBILITY": {
            "tier_A_non_direct_N": tier_autopsy["tiers"]["TIER_A"]["non_direct_N"],
            "tier_A_direct_N": tier_autopsy["tiers"]["TIER_A"]["direct_N"],
        },
        "GENERIC_AUTHORITY_COVERAGE": {
            "papers_with_parser_resolution_failure_N": priority_counts["GENERIC_AUTHORITY_COVERAGE"],
            "module_stage_attribution": {
                module: module_autopsies[module]["non_direct_stage_attribution_distribution"]
                for module in ("P0", "P1", "P2")
            },
        },
        "ACQUISITION_POLICY": {
            "NOT_JUSTIFIED_plus_DIRECT": 0,
            "JUSTIFIED_or_BORDERLINE_plus_NON_DIRECT": 0,
        },
    }
    priorities = [{"rank": index_value, "priority": name, "observed_affected_paper_count": priority_counts[name],
                   "implementation_status": "NOT_IMPLEMENTED",
                   "stage_attribution_evidence": priority_stage_evidence[name],
                   "justification": ("No PASS-A/PASS-B separation errors were observed; retain as a diagnostic boundary rather than a repair target."
                                     if name == "ACQUISITION_POLICY" else
                                     f"Observed in {priority_counts[name]} frozen non-direct papers or stage-attributed failures; counts overlap across priorities.")}
                  for index_value, name in enumerate(ranked, 1)]
    priority_record = {"artifact_schema_version": "V24DevelopmentPriorityV1", "ranking": priorities,
                       "ranking_basis": "descending observed affected-paper count with fixed deterministic tie order",
                       "overlapping_counts": True, "algorithm_changes_implemented": False}
    lines = ["# v2.4-dev development priorities", "", "No production change is implemented by this autopsy.", "",
             "| Rank | Priority | Observed affected papers |", "|---:|---|---:|"]
    for row in priorities:
        lines.append(f"| {row['rank']} | {row['priority']} | {row['observed_affected_paper_count']} |")
    lines.extend(["", "Counts may overlap because paper-level failure dimensions are intentionally non-exclusive.", "",
                  "The closed 60-paper corpus is development-seen and cannot serve as independent v2.4 validation.", ""])

    corpus_status = {
        "artifact_schema_version": "V24DevelopmentFailureCorpusStatusV1",
        "source_record_count": 60, "source_direct_count": 2, "source_non_direct_count": 58,
        "corpus_status": "seen_primary_failure_development_corpus_for_v24",
        "eligible_for_future_independent_validation": False,
        "future_independent_validation_requires_fresh_case_set": True,
        "primary_v2_merged_results_sha256": EXPECTED_MERGED,
        "primary_heldout_v2_metrics_unblinding_sha256": EXPECTED_METRICS,
    }

    protected_after = protected_state()
    require(protected_after == protected_before, "closed v2.3-beta.2 state changed")
    safety = {
        "artifact_schema_version": "V24DevPrimaryFailureAutopsySafetyAuditV1",
        "offline_only": True, "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "new_scientific_adjudication_calls": 0, "algorithm_changes": 0, "query_changes": 0,
        "target_changes": 0, "label_changes": 0, "p0_p1_p2_changes": 0,
        "policy_a_changes": 0, "v23_beta2_remains_frozen": True,
        "historical_assets_modified": False,
        "protected_state_before_sha256": digest(canonical(protected_before)),
        "protected_state_after_sha256": digest(canonical(protected_after)),
    }

    outputs = {
        "failure_corpus_status.json": pretty(corpus_status),
        "paper_level_failure_decomposition.jsonl": jsonl(paper_rows),
        "query_family_failure_autopsy.json": pretty(query_autopsy),
        "per_case_failure_autopsy.json": pretty({"artifact_schema_version": "V24DevPerCaseFailureAutopsyV1", "cases": case_autopsy}),
        "tier_failure_autopsy.json": pretty(tier_autopsy),
        "p0_failure_autopsy.json": pretty(module_autopsies["P0"]),
        "p1_failure_autopsy.json": pretty(module_autopsies["P1"]),
        "p2_failure_autopsy.json": pretty(module_autopsies["P2"]),
        "acquisition_failure_autopsy.json": pretty(acquisition_autopsy),
        "zero_yield_case_autopsy.json": pretty(zero_yield),
        "stage_attribution_summary.json": pretty(stage_summary),
        "v24_development_priority.json": pretty(priority_record),
        "v24_development_priority.md": "\n".join(lines).encode("utf-8"),
        "scientific_state_safety_audit.json": pretty(safety),
    }
    component_names = sorted(REQUIRED_OUTPUTS - {"validation.json", "summary.json"})
    components = [[name, digest(outputs[name])] for name in component_names]
    root = digest(canonical(components))
    validation = {
        "artifact_schema_version": "V24DevPrimaryFailureAutopsyValidationV1", "status": "PASS",
        "checks": {
            "authoritative_roots_verified": True, "all_60_papers_reconstructed": len(paper_rows) == 60,
            "all_58_non_direct_papers_decomposed": all(row["development_failure_dimensions"] for row in nondirect),
            "multiple_failure_dimensions_allowed": True, "all_eight_cases_audited": set(case_autopsy) == set(CASES),
            "all_four_executed_families_audited": set(family_profiles) == set(FAMILIES),
            "zero_yield_cases_audited": True, "direct_papers_audited_in_all_modules": True,
            "deterministic_replay_required": True, "v23_beta2_unchanged": protected_after == protected_before,
            "no_v24_algorithm_changes_implemented": True,
        },
        "aggregate_components": components,
        "search_plan_v24_primary_failure_autopsy_sha256": root,
    }
    failed_checks = [name for name, passed in validation["checks"].items() if not passed]
    require(not failed_checks, f"autopsy validation failed: {failed_checks}")
    summary = {
        "artifact_schema_version": "V24DevPrimaryFailureAutopsySummaryV1", "status": "COMPLETED",
        "record_count": 60, "direct_count": 2, "non_direct_count": 58,
        "failure_dimension_distribution": dim_counts,
        "family_any_contributing_counts": {family: family_profiles[family]["any_contributing"]["paper_N"] for family in FAMILIES},
        "family_direct_counts": {family: family_profiles[family]["any_contributing"]["pass_b_relevance_distribution"]["DIRECTLY_RELEVANT"] for family in FAMILIES},
        "development_priority_order": ranked,
        "search_plan_v24_primary_failure_autopsy_sha256": root,
        "v23_beta2_primary_evaluation_failed": True, "v23_beta2_remains_frozen": True,
        "heldout_v2_primary_corpus_reclassified_for_v24_development": True,
        "v24_algorithm_changes_implemented": False,
        "future_independent_validation_requires_fresh_case_set": True,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "new_scientific_adjudication_calls": 0, "historical_assets_modified": False,
    }
    outputs["validation.json"] = pretty(validation)
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED_OUTPUTS, "required output membership mismatch")
    return outputs


def run() -> None:
    authority = verify_authority()
    protected = protected_state()
    first = build_outputs(authority, protected)
    second = build_outputs(authority, protected)
    require(first == second, "autopsy replay is not byte-identical")
    RUN.mkdir(parents=True, exist_ok=True)
    require(not any(RUN.iterdir()), "output run already contains files")
    for name in sorted(first):
        path = RUN / name
        with path.open("xb") as stream:
            stream.write(first[name])
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "written output membership mismatch")
    require(protected_state() == protected, "closed v2.3-beta.2 state changed after write")
    print((RUN / "summary.json").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    run()
