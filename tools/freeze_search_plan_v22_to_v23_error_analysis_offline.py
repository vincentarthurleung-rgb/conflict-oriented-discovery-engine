#!/usr/bin/env python3
"""Freeze retrospective development analyses; never execute a search-plan gate."""

from collections import Counter
import csv
import io
import json
from pathlib import Path
import subprocess

if __package__:
    from . import calculate_search_plan_v22_heldout_v1_primary_metrics_offline as frozen
else:
    import calculate_search_plan_v22_heldout_v1_primary_metrics_offline as frozen


ROOT = frozen.ROOT
RUN = ROOT / "runs/20260912_search_plan_v22_to_v23_error_analysis_freeze_offline"
STATUS = "post_unblinding_retrospective_development_analysis"
METRICS_HASH = "76580be82dfa6a13f620514596caacb2ba13bf7a087f47dc62f76a5329f9adf1"
HASHES = {**frozen.EXPECTED_ROOTS, "heldout_v1_primary_metrics_sha256": METRICS_HASH}
FAMILIES = [
    "BIOLOGICAL_UNIT_MISMATCH", "FUNCTIONAL_RELATION_UNRESOLVED",
    "ENDPOINT_MISMATCH", "ENTITY_OR_INTERVENTION_MISMATCH", "THERAPY_MISMATCH",
    "PROPOSITION_DIRECTION_OR_ROLE_MISMATCH", "INSUFFICIENT_SPECIFICITY",
    "OTHER_FROZEN_RELEVANCE_FAILURE",
]
RULES = [
    {"id": "bio_contaminant", "family": FAMILIES[0], "field": "contaminant_class",
     "op": "equals", "values": ["wrong_biological_unit"]},
    {"id": "bio_component", "family": FAMILIES[0], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["biological_unit", "biological unit", "cell_type"]},
    {"id": "functional_contaminant", "family": FAMILIES[1], "field": "contaminant_class",
     "op": "equals", "values": ["wrong_evidence_mode", "association_vs_functional_relation"]},
    {"id": "functional_state", "family": FAMILIES[1], "field": "relevance_state",
     "op": "equals", "values": ["WRONG_EVIDENCE_MODE"]},
    {"id": "functional_component", "family": FAMILIES[1], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["relation_family", "evidence_mode"]},
    {"id": "functional_unresolved", "family": FAMILIES[1], "field": "remaining_unresolved_fields",
     "op": "substring_casefold", "values": ["functional", "causal", "relation", "perturbation", "response contrast"]},
    {"id": "endpoint_contaminant", "family": FAMILIES[2], "field": "contaminant_class",
     "op": "equals", "values": ["wrong_endpoint"]},
    {"id": "endpoint_state", "family": FAMILIES[2], "field": "relevance_state",
     "op": "equals", "values": ["WRONG_ENDPOINT"]},
    {"id": "endpoint_component", "family": FAMILIES[2], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["measurement_target", "measurement_property_endpoint", "endpoint"]},
    {"id": "endpoint_unresolved", "family": FAMILIES[2], "field": "remaining_unresolved_fields",
     "op": "substring_casefold", "values": ["measurement_target", "measurement_property_endpoint", "measurement endpoint", "secretion condition"]},
    {"id": "entity_contaminant", "family": FAMILIES[3], "field": "contaminant_class",
     "op": "equals", "values": ["wrong_entity"]},
    {"id": "entity_component", "family": FAMILIES[3], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["subject", "intervention", "entity", "subject_identity", "intervention_identity"]},
    {"id": "entity_state", "family": FAMILIES[3], "field": "relevance_state",
     "op": "equals", "values": ["WRONG_ENTITY"], "unless_contaminant": "wrong_biological_unit"},
    {"id": "therapy_state", "family": FAMILIES[4], "field": "relevance_state",
     "op": "equals", "values": ["WRONG_THERAPY"]},
    {"id": "therapy_component", "family": FAMILIES[4], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["therapy", "therapy_identity", "treatment_identity"]},
    {"id": "direction_or_role", "family": FAMILIES[5], "field": "mismatched_target_components",
     "op": "contains_exact", "values": ["subject role", "subject_role", "object_role", "direction", "relation_direction"]},
    {"id": "specificity_state", "family": FAMILIES[6], "field": "relevance_state",
     "op": "equals", "values": ["PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED", "INSUFFICIENT_SOURCE_EVIDENCE", "TOPIC_ONLY"]},
    {"id": "specificity_unresolved", "family": FAMILIES[6], "field": "remaining_unresolved_fields",
     "op": "nonempty", "values": []},
]
FUNCTIONAL_PATTERNS = {
    "A_co_change_or_correlation": ["concurrently", "coordinated", "correlation", "increase both", "exercise-associated", "accompaniment"],
    "B_upstream_downstream_pathway_association": ["upstream", "downstream", "secondarily"],
    "C_multiple_targets_unresolved_contribution": ["multikinase", "multi-target", "separated from concurrent"],
    "D_background_without_current_study_support": ["only as background", "background statements", "background proposition"],
}
ENDPOINT_PATTERNS = {
    "abundance_vs_activation_phosphorylation": [["abundance", "phosphorylation"], ["abundance", "activation"]],
    "transcription_vs_secretion": [["transcription", "secretion"]],
    "precursor_vs_mature_extracellular_product": [["precursor", "mature"], ["pro-il", "mature"]],
    "morphology_vs_density_number": [["morphology", "density"], ["morphology", "number"]],
    "localization_translocation_vs_functional_uptake": [["translocation", "uptake"], ["localization", "uptake"]],
    "generic_insulin_secretion_vs_gsis": [["insulin secretion", "glucose-stimulated secretion condition"]],
}
REQUIRED = {
    "heldout_v1_v23_development_error_matrix.jsonl", "heldout_v1_v23_development_error_matrix.csv",
    "development_failure_mapping.json", "biological_unit_error_analysis.json", "biological_unit_error_analysis.md",
    "functional_relation_error_analysis.json", "functional_relation_error_analysis.md",
    "endpoint_error_analysis.json", "endpoint_error_analysis.md", "tier_error_analysis.json", "tier_error_analysis.md",
    "per_case_v23_development_profiles.json", "per_case_v23_development_profiles.md",
    "v23_search_plan_design_requirements.json", "v23_search_plan_design_requirements.md",
    "v23_metrics_protocol_requirements.json", "v23_metrics_protocol_requirements.md",
    "v22_heldout_v1_final_status.md", "root_hash_verification.json", "scientific_state_safety_audit.json",
    "manifest.json", "validation.json", "summary.json",
}


def tagged(value):
    return {"analysis_status": STATUS, **value}


def verify_roots():
    roots = frozen.verify_all_roots()
    manifest = frozen.read_json(frozen.RUN / "manifest.json")
    pairs = []
    for item in manifest["metric_result_components"]:
        actual = frozen.sha256(frozen.RUN / item["path"])
        frozen.require(actual == item["sha256"], f"metrics component mismatch: {item['path']}")
        pairs.append([item["path"], actual])
    actual = frozen.digest(frozen.canonical_json(pairs))
    frozen.require(actual == manifest["heldout_v1_primary_metrics_sha256"] == METRICS_HASH,
                   "primary metrics root mismatch; no analysis permitted")
    frozen.require(all(manifest[name] == value for name, value in HASHES.items()), "metrics upstream roots mismatch")
    roots["heldout_v1_primary_metrics_sha256"] = {"actual": actual, "expected": METRICS_HASH, "match": True}
    return roots


def protected_hashes():
    # Include every tracked file (production code, existing tests, dirty files), plus
    # ignored frozen held-out roots. Byte reads only; no regeneration or git writes.
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / name for name in tracked if name}
    for base in [frozen.PROTOCOL, frozen.REVIEW, frozen.BLINDED, frozen.PASS_A,
                 frozen.PASS_B, frozen.PRIMARY, frozen.WORKSPACE, frozen.RUN]:
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths = {path for path in paths if not path.is_relative_to(RUN)}
    return {str(path.relative_to(ROOT)): frozen.sha256(path) if path.is_file() else None
            for path in sorted(paths)}


def failure_families(adjudication):
    """Only these four frozen PASS B fields influence retrospective families."""
    allowed = {name: adjudication[name] for name in ["contaminant_class", "relevance_state",
               "mismatched_target_components", "remaining_unresolved_fields"]}
    if allowed["relevance_state"] == "DIRECTLY_RELEVANT":
        return [], []
    trace = []
    for rule in RULES:
        if "unless_contaminant" in rule and rule["unless_contaminant"] == allowed["contaminant_class"]:
            continue
        value = allowed[rule["field"]]
        values = value if isinstance(value, list) else [value]
        if rule["op"] in ("equals", "contains_exact"):
            matches = [item for item in values if item in rule["values"]]
        elif rule["op"] == "substring_casefold":
            matches = [item for item in values if any(term.casefold() in item.casefold() for term in rule["values"])]
        else:
            matches = values if value else []
        if matches:
            trace.append({"rule_id": rule["id"], "family": rule["family"],
                          "source_field": rule["field"], "frozen_values": matches})
    families = [family for family in FAMILIES if any(hit["family"] == family for hit in trace)]
    if not families:
        families = [FAMILIES[-1]]
        trace = [{"rule_id": "non_direct_fallback", "family": FAMILIES[-1],
                  "source_field": "relevance_state", "frozen_values": [allowed["relevance_state"]]}]
    return families, trace


def make_matrix(records):
    rows = []
    for source in records:
        a, b, identity = source["pass_a"], source["pass_b"], source["source_identity"]
        families, trace = failure_families(b)
        rows.append(tagged({
            **{key: source[key] for key in ["packet_id", "case_id", "ambiguity", "tier"]},
            **{key: identity[key] for key in ["pmid", "pmcid", "doi", "title"]},
            "source_identity": identity,
            "acquisition_decision": a["acquisition_decision"], "acquisition_confidence": a["confidence"],
            "acquisition_rationale": a["rationale"], "acquisition_reviewer_type": a["reviewer_type"],
            **{key: b[key] for key in ["relevance_state", "matched_target_components", "mismatched_target_components",
                "fulltext_resolved_fields", "remaining_unresolved_fields", "contaminant_class"]},
            "relevance_confidence": b["confidence"], "relevance_rationale": b["rationale"],
            "relevance_reviewer_type": b["reviewer_type"],
            **{key: source[key] for key in ["frozen_gate_states", "frozen_acquisition_metadata",
                "scientific_target", "retrieval_target", "canonical_packet_sha256"]},
            "development_failure_families": families, "development_failure_mapping_trace": trace,
        }))
    return rows


def to_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: frozen.canonical_json(value).decode() for key, value in row.items()})
    return stream.getvalue().encode()


def from_csv(data):
    return [{key: json.loads(value) for key, value in row.items()}
            for row in csv.DictReader(io.StringIO(data.decode(), newline=""))]


def counts(rows, field, categories):
    result = Counter(row[field] for row in rows)
    return {value: result[value] for value in categories}


def selection_summary(rows):
    return {"packet_count": len(rows), "packet_ids": [row["packet_id"] for row in rows],
            "by_case": counts(rows, "case_id", frozen.CASES),
            "by_tier": counts(rows, "tier", frozen.TIERS),
            "by_ambiguity": counts(rows, "ambiguity", frozen.AMBIGUITIES),
            "relevance_states": counts(rows, "relevance_state", frozen.RELEVANCE_STATES)}


def family_composition(rows):
    return {family: selection_summary([row for row in rows if family in row["development_failure_families"]])
            for family in FAMILIES}


def contamination_counts(rows):
    result = Counter(row["contaminant_class"] or "no_contaminant" for row in rows)
    return {key: result[key] for key in frozen.CONTAMINANT_CLASSES}


def evidence(row):
    return {"packet_id": row["packet_id"], "case_id": row["case_id"], "tier": row["tier"],
            "scientific_target": row["scientific_target"],
            "relevance_state": row["relevance_state"], "contaminant_class": row["contaminant_class"],
            "mismatched_target_components": row["mismatched_target_components"],
            "remaining_unresolved_fields": row["remaining_unresolved_fields"],
            "frozen_relevance_rationale": row["relevance_rationale"],
            "source": "heldout_v1_primary_results.jsonl#packet_id=" + row["packet_id"]}


def biological_analysis(rows):
    affected = [row for row in rows if row["contaminant_class"] == "wrong_biological_unit"]
    frozen.require(len(affected) == 21, "frozen biological-unit count mismatch")
    supply = {}
    for case in frozen.CASES:
        case_rows = [row for row in rows if row["case_id"] == case]
        unit_rows = [row for row in affected if row["case_id"] == case]
        supply[case] = {"acquired_tier_counts": counts(case_rows, "tier", frozen.TIERS),
                        "wrong_biological_unit_count": len(unit_rows),
                        "target_context_qualifiers": case_rows[0]["scientific_target"]["context_qualifiers"],
                        "affected_packet_ids": [row["packet_id"] for row in unit_rows]}
    absent = [case for case in frozen.CASES if supply[case]["acquired_tier_counts"]["TIER_A"] == 0]
    return tagged({
        "selection": "contaminant_class == wrong_biological_unit (exact frozen class)",
        "summary": selection_summary(affected), "per_case_target_context": supply,
        "cases_without_acquired_tier_a": absent,
        "biological_unit_errors_in_cases_without_acquired_tier_a": selection_summary(
            [row for row in affected if row["case_id"] in absent]),
        "tier_pattern": "Tier B" if sum(row["tier"] == "TIER_B" for row in affected) > len(affected) / 2 else "no Tier B majority",
        "supply_limit": "These are acquired/adjudicated Tier counts only. Zero acquired Tier A does not establish zero eligible or retrieved Tier A candidates.",
        "context_boundary": "Organ/location mention does not establish required biological-unit identity. A liver-associated cell does not automatically imply hepatocyte. Frozen qualifiers are copied in full; no equivalence is added.",
        "records": [evidence(row) for row in affected],
    })


def functional_analysis(rows):
    selected = [row for row in rows if FAMILIES[1] in row["development_failure_families"]]
    patterns = {}
    covered = set()
    for name, terms in FUNCTIONAL_PATTERNS.items():
        hits = []
        for row in selected:
            fields = [row["relevance_rationale"], *row["remaining_unresolved_fields"]]
            match = [{"frozen_text": value, "literal_matches": [term for term in terms if term in value.casefold()]}
                     for value in fields if any(term in value.casefold() for term in terms)]
            if match:
                covered.add(row["packet_id"])
                hits.append({"packet_id": row["packet_id"], "matches": match})
        hit_ids = {hit["packet_id"] for hit in hits}
        patterns[name] = {"literal_markers_casefold": terms, "summary": selection_summary(
            [row for row in selected if row["packet_id"] in hit_ids]), "evidence": hits}
    return tagged({
        "selection": FAMILIES[1], "summary": selection_summary(selected), "patterns": patterns,
        "pattern_status": "Non-exclusive literal annotations of frozen evaluator wording; not a new evidence hierarchy or exhaustive scientific classification.",
        "unresolved_pattern_detail": selection_summary([row for row in selected if row["packet_id"] not in covered]),
        "records": [evidence(row) for row in selected],
    })


def endpoint_analysis(rows):
    selected = [row for row in rows if FAMILIES[2] in row["development_failure_families"]]
    patterns = {}
    for name, alternatives in ENDPOINT_PATTERNS.items():
        hits = [row for row in selected if any(all(term in row["relevance_rationale"].casefold()
                for term in conjunction) for conjunction in alternatives)]
        patterns[name] = {"all_literal_terms_in_any_group": alternatives,
                          "status": "EXPLICIT_FROZEN_WORDING_FOUND" if hits else "NOT_EXPLICITLY_ESTABLISHED_IN_SELECTED_FROZEN_ADJUDICATIONS",
                          "summary": selection_summary(hits), "records": [evidence(row) for row in hits]}
    targets = {case: next(row["scientific_target"] for row in rows if row["case_id"] == case)
               for case in frozen.CASES}
    return tagged({"selection": FAMILIES[2], "summary": selection_summary(selected),
                   "semantic_distinctions": patterns,
                   "frozen_target_boundaries_by_case": targets,
                   "limitation": "Target boundaries are preserved context, not evidence that each boundary caused an observed error. Literal nonmatches remain unspecified. No endpoint inference from paper text or target words alone.",
                   "records": [evidence(row) for row in selected]})


def tier_analysis(rows, primary_tiers):
    tiers = {}
    for tier in frozen.TIERS:
        selected = [row for row in rows if row["tier"] == tier]
        families = family_composition(selected)
        maximum = max(families[family]["packet_count"] for family in FAMILIES[:6])
        tiers[tier] = {"summary": selection_summary(selected),
                       "frozen_primary_metrics": primary_tiers[tier],
                       "non_direct_count": sum(row["relevance_state"] != "DIRECTLY_RELEVANT" for row in selected),
                       "leading_mechanistic_families": [family for family in FAMILIES[:6]
                           if families[family]["packet_count"] == maximum and maximum > 0],
                       "failure_families": families,
                       "contaminant_counts": contamination_counts(selected)}
    composition = {case: counts([row for row in rows if row["case_id"] == case], "tier", frozen.TIERS)
                   for case in frozen.CASES}
    return tagged({"tiers": tiers, "case_composition": composition,
                   "zero_acquired_tier_a_cases": [case for case in frozen.CASES if composition[case]["TIER_A"] == 0],
                   "one_acquired_tier_a_cases": [case for case in frozen.CASES if composition[case]["TIER_A"] == 1],
                   "tier_b_non_direct": selection_summary([row for row in rows if row["tier"] == "TIER_B" and row["relevance_state"] != "DIRECTLY_RELEVANT"]),
                   "failure_family_comparison": {family: {tier: tiers[tier]["failure_families"][family]["packet_count"]
                       for tier in frozen.TIERS} for family in FAMILIES},
                   "observed_contrast": {
                       tier: {"non_direct_count": tiers[tier]["non_direct_count"],
                              "leading_mechanistic_families": tiers[tier]["leading_mechanistic_families"]}
                       for tier in frozen.TIERS},
                   "interpretation": "Acquired case composition and overlapping failure families describe this seen sample; they do not establish a causal effect of Tier rules. Mechanistic leaders are largest raw counts among the first six families, retaining ties. No Tier B utility measure is defined. Zero/one counts describe acquired supply, not retrieval exhaustiveness."})


def case_profiles(rows):
    profiles = []
    issue_names = {FAMILIES[0]: "biological unit", FAMILIES[1]: "relation evidence",
                   FAMILIES[2]: "endpoint semantics", FAMILIES[3]: "intervention/entity identity"}
    for case in frozen.CASES:
        selected = [row for row in rows if row["case_id"] == case]
        composition = family_composition(selected)
        mechanism_counts = {family: composition[family]["packet_count"] for family in FAMILIES[:6]}
        maximum = max(mechanism_counts.values())
        leaders = [family for family, count in mechanism_counts.items() if count == maximum and count > 0]
        issue = issue_names.get(leaders[0], "mixed / insufficient evidence") if len(leaders) == 1 else "mixed / insufficient evidence"
        profiles.append(tagged({"case_id": case, "N": len(selected), "ambiguity": selected[0]["ambiguity"],
            "tier_counts": counts(selected, "tier", frozen.TIERS),
            "direct_count": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in selected),
            "relevance_distribution": counts(selected, "relevance_state", frozen.RELEVANCE_STATES),
            "contaminant_distribution": contamination_counts(selected),
            "development_failure_families": composition, "dominant_observed_failure_mechanisms": leaders,
            "primary_development_issue": issue,
            "tier_b_tail_context": selection_summary([row for row in selected if row["tier"] == "TIER_B" and row["relevance_state"] != "DIRECTLY_RELEVANT"]),
            "dominance_rule": "Largest packet count among the first six mechanistic families; preserve ties, exclude generic specificity/fallback categories. This is retrospective prioritization, not a heuristic threshold.",
            "frozen_evidence": [evidence(row) for row in selected if row["relevance_state"] != "DIRECTLY_RELEVANT"]}))
    return tagged({"profiles": profiles, "no_case_specific_gate_proposed": True,
                   "attribution_limit": "Mechanistic issue labels summarize frozen adjudication fields, not causal responsibility of retrieval. Tier B tail acquisition is reported separately as a co-occurring acquisition context."})


def design_requirements(rows):
    candidates = [
        ("V23-P0-BIOLOGICAL-UNIT", "P0", "BIOLOGICAL UNIT COMPATIBILITY", FAMILIES[0],
         "Represent required biological-unit identity independently of organ/location mentions; document any future compatibility authority.",
         ["EXACT", "COMPATIBLE_PARENT_CHILD", "UNRESOLVED", "INCOMPATIBLE"],
         "Overly broad parent-child compatibility could re-admit wrong cell types; overly narrow compatibility could reject legitimate models.",
         "Incomplete metadata and omitted model descriptions could remove relevant papers before fulltext resolves the unit."),
        ("V23-P1-FUNCTIONAL-RELATION", "P1", "FUNCTIONAL RELATION EVIDENCE LEVEL", FAMILIES[1],
         "Require a design that distinguishes target-directed contribution from co-change, upstream/downstream association, background mention, and unresolved multiple-target contribution.",
         ["DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN", "ASSOCIATION", "TOPIC_ONLY"],
         "Lexical perturbation cues cannot establish causal contribution, and multi-step evidence can be ambiguous.",
         "Demanding a fully explicit perturbation in abstracts could discard relevant mechanistic chains resolved only in fulltext."),
        ("V23-P2-ENDPOINT", "P2", "ENDPOINT SEMANTICS", FAMILIES[2],
         "Separate endpoint meaning from lexical entity overlap, preserving process, state, compartment and experimental condition where the target requires them.",
         ["measurement_entity", "measurement_property", "measurement_process", "measurement_state", "measurement_compartment"],
         "An over-detailed schema can create unsupported equivalence or false mismatch without evidence authority.",
         "Source-equivalent assays or underspecified metadata could be rejected despite genuine endpoint compatibility."),
        ("V23-P3-TIER-B", "P3", "TIER B ACQUISITION POLICY", None,
         "Design an auditable policy for unresolved component load and incompatible fallback candidates, especially when no Tier A papers were acquired. Preserve the opportunity to resolve missing metadata through fulltext.",
         ["B1 = one unresolved proposition component", "B2 = multiple unresolved components", "B3 = topic-relevant fallback"],
         "Post-adjudication failures cannot be treated as prospectively available selection signals; acquired samples do not establish retrieval supply.",
         "Eight frozen Tier B papers were directly relevant; indiscriminate restriction would lose demonstrated useful acquisitions."),
    ]
    requirements = []
    for identifier, priority, name, family, rationale, concepts, risk, recall in candidates:
        affected = [row for row in rows if family in row["development_failure_families"]] if family else [
            row for row in rows if row["tier"] == "TIER_B" and row["relevance_state"] != "DIRECTLY_RELEVANT"]
        summary = selection_summary(affected)
        requirements.append(tagged({
            "requirement_id": identifier, "priority": priority, "name": name,
            "support_status": "SUPPORTED_AS_DEVELOPMENT_DIRECTION", "candidate_taxonomy_validated": False,
            "observed_failure_evidence": {"selection": family or "frozen Tier B and non-DIRECTLY_RELEVANT",
                "packet_ids": summary["packet_ids"], "retrospective_counts": summary},
            "affected_cases": [case for case in frozen.CASES if summary["by_case"][case]],
            "affected_packet_count": len(affected), "affected_tier_distribution": summary["by_tier"],
            "scientific_rationale": rationale, "expected_risk": risk, "risk_to_recall": recall,
            "potential_future_concepts_only": concepts, "implementation_not_started": True,
        }))
    return tagged({"requirements": requirements, "priorities_are_user_requested_development_priorities": True,
                   "validation_required": "Develop on seen held-out-v1; evaluate final v2.3 on newly frozen unseen held-out-v2."})


def protocol_requirements(definition_audit, heuristics):
    topics = {
        "direct_relevance_numerator": "Freeze exact relevance-state membership and treatment of unresolved adjudications.",
        "direct_relevance_denominator": "Freeze inclusion, acquisition/adjudication scope, missing records, zero denominators and deduplication unit.",
        "acquisition_justification_mapping": "Freeze explicit acquisition_decision enum membership; do not infer JUSTIFIED-only or borderline inclusion.",
        "acquisition_acceptability_mapping": "Freeze explicit acceptable decision enum set independently of justification.",
        "tier_a_metrics": "Freeze Tier membership source, every numerator and denominator, and aggregation scope.",
        "tier_b_metrics": "Freeze Tier B direct relevance and any additional permitted metrics separately.",
        "tier_b_utility_proxy_if_retained": "Freeze proxy inputs, mapping, numerator, denominator and interpretation before retrieval, or omit it.",
        "contaminant_rates": "Freeze exact label field, class mapping, empty values, overlapping categories, combined review-only mapping and denominators.",
        "qualitative_heuristics": "Operationalize systematic, dominates and most cases with explicit algorithms and thresholds, or leave them non-evaluable.",
        "ambiguity_stratum_failure": "Freeze stratum assignment and catastrophic-failure definition, small-N handling and decision rule.",
        "thresholds": "Freeze operator, value, precision/comparison convention and handling of undefined metrics.",
    }
    return tagged({"proposed_future_file": "metrics_spec_v2.json", "freeze_before_retrieval_required": True,
                   "implementation_not_started": True,
                   "requirements": [{"requirement_id": "METRICS-V2-" + name.upper(), "topic": name,
                                     "requirement": text} for name, text in topics.items()],
                   "source_definition_gaps": [item for item in definition_audit["entries"] if not item["operationally_complete"]],
                   "frozen_v1_heuristic_statuses_preserved": heuristics,
                   "acceptance_requirement": "Machine-validate all definitions and freeze fixtures with expected numerator/denominator behavior before new retrieval. Under-specified retained names must fail closed.",
                   "retroactive_application_to_v1_primary_results_allowed": False,
                   "new_primary_statistics_or_thresholds_defined_here": False})


def md(title, lines):
    return ("# " + title + "\n\nanalysis_status = " + STATUS +
            "\n\nHeld-out v1 is seen evaluation evidence for v2.3. Development-only; no new primary result.\n\n" +
            "\n".join(lines) + "\n").encode()


def summary_lines(value):
    return [f"Affected packets: {value['packet_count']}", "",
            "| Dimension | Counts |", "|---|---|",
            *[f"| {key} | " + "; ".join(f"{name}: {number}" for name, number in value[key].items()) + " |"
              for key in ["by_case", "by_tier", "by_ambiguity", "relevance_states"]], ""]


def record_lines(records):
    return [f"- {row['packet_id']} ({row['case_id']}, {row['tier']}): {row['frozen_relevance_rationale']}"
            for row in records]


def build_analysis(records, metrics):
    frozen.validate_records(records)
    rows = make_matrix(records)
    ids = [row["packet_id"] for row in rows]
    frozen.require(ids == [row["packet_id"] for row in records] and len(set(ids)) == 70,
                   "matrix packet identity/order failed")
    csv_data = to_csv(rows)
    frozen.require(from_csv(csv_data) == rows, "CSV/JSONL record equivalence failed")
    mapping = tagged({"allowed_families": FAMILIES, "rules": RULES,
        "input_fields_allowlist": ["contaminant_class", "relevance_state", "mismatched_target_components", "remaining_unresolved_fields"],
        "semantics": "Evaluate rules in listed order; OR matching rules, deduplicate families in allowed-family order. Families overlap. Non-direct includes unresolved/plausible papers; it does not assert proven incompatibility for all families.",
        "directly_relevant_policy": "Zero families; do not contradict frozen direct relevance.",
        "fallback": "Non-direct with no matching rule gets OTHER_FROZEN_RELEVANCE_FAILURE.",
        "biological_unit_policy": "Generic context_qualifiers mismatch is not by itself mapped to biological-unit identity mismatch. Unresolved unit identity alone remains INSUFFICIENT_SPECIFICITY.",
        "entity_policy": "WRONG_ENTITY plus wrong_biological_unit is not by itself a subject/intervention failure; explicit subject/entity mismatch can independently trigger that family.",
        "direction_policy": "relation_family mismatch alone does not imply reversed direction or changed role. Require explicit component names.",
        "rationale_influences_failure_families": False,
        "supplemental_wording_annotations": {"functional_patterns": FUNCTIONAL_PATTERNS,
            "endpoint_patterns": ENDPOINT_PATTERNS,
            "policy": "Casefolded literal wording only, over frozen rationale/unresolved text; not adjudication. Non-exhaustive, overlapping and never fed back into failure families."},
        "csv_encoding": "UTF-8; LF; fixed column order; every CSV cell contains a JSON value. Decode each cell with json.loads for exact typed row equivalence.",
        "family_counts": family_composition(rows)})
    bio = biological_analysis(rows)
    functional = functional_analysis(rows)
    endpoint = endpoint_analysis(rows)
    tiers = tier_analysis(rows, metrics["tier_metrics.json"])
    profiles = case_profiles(rows)
    requirements = design_requirements(rows)
    protocol = protocol_requirements(metrics["metric_definition_audit.json"], metrics["engineering_heuristics.json"])
    outputs = {"heldout_v1_v23_development_error_matrix.jsonl": b"".join(frozen.canonical_json(row) + b"\n" for row in rows),
               "heldout_v1_v23_development_error_matrix.csv": csv_data}
    for filename, content in [
        ("development_failure_mapping.json", mapping), ("biological_unit_error_analysis.json", bio),
        ("functional_relation_error_analysis.json", functional), ("endpoint_error_analysis.json", endpoint),
        ("tier_error_analysis.json", tiers), ("per_case_v23_development_profiles.json", profiles),
        ("v23_search_plan_design_requirements.json", requirements), ("v23_metrics_protocol_requirements.json", protocol)]:
        outputs[filename] = frozen.pretty_json(content)
    outputs["biological_unit_error_analysis.md"] = md("Biological-unit error analysis",
        summary_lines(bio["summary"]) + [bio["context_boundary"], "", bio["supply_limit"], "",
        "Cases with no acquired Tier A: " + ", ".join(bio["cases_without_acquired_tier_a"]),
        "Biological-unit errors in those cases: " + str(bio["biological_unit_errors_in_cases_without_acquired_tier_a"]["packet_count"]),
        "", "Required frozen context qualifiers by case:", ""] + [
            f"- {case}: {json.dumps(value['target_context_qualifiers'], ensure_ascii=False)}; biological-unit failures={value['wrong_biological_unit_count']}"
            for case, value in bio["per_case_target_context"].items()] + ["", "Frozen adjudications:", ""] + record_lines(bio["records"]))
    functional_lines = summary_lines(functional["summary"]) + [functional["pattern_status"], ""]
    for pattern, value in functional["patterns"].items():
        functional_lines.extend([f"### {pattern}", ""] + summary_lines(value["summary"]))
    functional_lines += ["Unspecified detailed pattern: " + str(functional["unresolved_pattern_detail"]["packet_count"]),
                         "", "Frozen adjudications:", ""] + record_lines(functional["records"])
    outputs["functional_relation_error_analysis.md"] = md("Functional-relation error analysis", functional_lines)
    endpoint_lines = summary_lines(endpoint["summary"]) + [endpoint["limitation"], ""]
    for pattern, value in endpoint["semantic_distinctions"].items():
        endpoint_lines.append(f"- {pattern}: {value['status']}; explicit wording records={value['summary']['packet_count']}")
    endpoint_lines += ["", "Frozen endpoint boundaries (not observed failure counts):", ""] + [
        f"- {case}: {json.dumps(target['scientific_boundaries'], ensure_ascii=False)}"
        for case, target in endpoint["frozen_target_boundaries_by_case"].items()]
    endpoint_lines += ["", "Frozen adjudications:", ""] + record_lines(endpoint["records"])
    outputs["endpoint_error_analysis.md"] = md("Endpoint error analysis", endpoint_lines)
    outputs["tier_error_analysis.md"] = md("Tier error analysis", [tiers["interpretation"], "",
        "| Family (overlapping) | Tier A | Tier B |", "|---|---:|---:|"] + [
        f"| {family} | {value['TIER_A']} | {value['TIER_B']} |" for family, value in tiers["failure_family_comparison"].items()] +
        ["", "| Case | Acquired Tier A | Acquired Tier B |", "|---|---:|---:|"] + [
        f"| {case} | {value['TIER_A']} | {value['TIER_B']} |" for case, value in tiers["case_composition"].items()] +
        ["", *[f"{tier}: {value['non_direct_count']} non-direct packets; leading mechanistic families: {', '.join(value['leading_mechanistic_families'])}."
                for tier, value in tiers["observed_contrast"].items()],
         "", "Zero acquired Tier A: " + ", ".join(tiers["zero_acquired_tier_a_cases"]),
         "One acquired Tier A: " + ", ".join(tiers["one_acquired_tier_a_cases"]),
         "Frozen primary frequencies: Tier A 24/35 (68.571429%); Tier B 8/35 (22.857143%)."])
    profile_lines = []
    for profile in profiles["profiles"]:
        profile_lines += [f"## {profile['case_id']}", "",
            f"N={profile['N']}; directly relevant={profile['direct_count']}; Tier counts={profile['tier_counts']}.",
            f"Dominant observed mechanisms: {profile['dominant_observed_failure_mechanisms']}; development issue: {profile['primary_development_issue']}.",
            "", "Frozen relevance counts: " + json.dumps(profile["relevance_distribution"], sort_keys=True),
            "", "Frozen contaminant counts: " + json.dumps(profile["contaminant_distribution"], sort_keys=True),
            "", "Overlapping families: " + json.dumps({family: value["packet_count"] for family, value in profile["development_failure_families"].items()}),
            "", "Tier B non-direct packets: " + str(profile["tier_b_tail_context"]["packet_count"]), ""]
    outputs["per_case_v23_development_profiles.md"] = md("Per-case development profiles", profile_lines)
    requirement_lines = []
    for item in requirements["requirements"]:
        requirement_lines += [f"## {item['requirement_id']} — {item['name']}", "",
            f"Affected packets={item['affected_packet_count']}; cases={', '.join(item['affected_cases'])}; tiers={item['affected_tier_distribution']}.",
            "", item["scientific_rationale"], "", "Candidate concepts only: " + "; ".join(item["potential_future_concepts_only"]),
            "", "Expected risk: " + item["expected_risk"], "", "Recall risk: " + item["risk_to_recall"],
            "", "implementation_not_started = true", "candidate_taxonomy_validated = false", ""]
    outputs["v23_search_plan_design_requirements.md"] = md("v2.3 design requirements", requirement_lines)
    outputs["v23_metrics_protocol_requirements.md"] = md("v2.3 metrics protocol requirements", [
        "Require metrics_spec_v2.json to be machine-validated and frozen BEFORE retrieval.", "",
        *[f"- {item['topic']}: {item['requirement']}" for item in protocol["requirements"]], "",
        protocol["acceptance_requirement"], "", "No future definitions are applied retroactively to held-out v1 primary metrics.",
        "All six previously NOT_EVALUABLE_FROM_FROZEN_DEFINITION heuristics retain their status."])
    outputs["v22_heldout_v1_final_status.md"] = md("v2.2 held-out-v1 final scientific status", [
        "1. v2.2 is frozen.", "2. Held-out v1 is now seen evaluation evidence.",
        "3. Frozen primary direct relevance among adjudicated acquired papers: overall 32/70 = 45.714286%; Tier A 24/35 = 68.571429%; Tier B 8/35 = 22.857143%.",
        "4. The largest nonempty frozen secondary contaminant class is wrong_biological_unit: 21/70.",
        "5. No retroactive v2.2 tuning is permitted.", "6. Future modifications belong to v2.3; implementation has not started.",
        "7. Held-out v1 may support v2.3 development, retrospective replay, ablation, regression and failure-case testing; it is ineligible for v2.3 unseen primary validation.",
        "8. A new unseen held-out-v2 set is required for final v2.3 evaluation.", "",
        "Previously NOT_EVALUABLE heuristics remain NOT_EVALUABLE_FROM_FROZEN_DEFINITION.",
        "Reviewer type: model_retrieval_adjudicator. These data do not establish Human Gold or v2.3 generalization."])
    return outputs, rows


def validate_outputs(outputs, rows, records):
    reconstructed = []
    for row in rows:
        reconstructed.append({
            "artifact_schema_version": "HeldoutV1PrimaryResultV1",
            **{key: row[key] for key in ["packet_id", "case_id", "ambiguity", "tier", "frozen_gate_states",
                "frozen_acquisition_metadata", "scientific_target", "retrieval_target", "source_identity", "canonical_packet_sha256"]},
            "pass_a": {"acquisition_decision": row["acquisition_decision"], "confidence": row["acquisition_confidence"],
                       "rationale": row["acquisition_rationale"], "reviewer_type": row["acquisition_reviewer_type"]},
            "pass_b": {**{key: row[key] for key in ["relevance_state", "matched_target_components", "mismatched_target_components",
                         "fulltext_resolved_fields", "remaining_unresolved_fields", "contaminant_class"]},
                       "confidence": row["relevance_confidence"], "rationale": row["relevance_rationale"],
                       "reviewer_type": row["relevance_reviewer_type"]},
        })
    frozen.require(reconstructed == records, "matrix changed frozen primary fields")
    frozen.require(from_csv(outputs["heldout_v1_v23_development_error_matrix.csv"]) == rows,
                   "CSV records differ from JSONL")
    for name, data in outputs.items():
        if name.endswith(".json"):
            frozen.require(json.loads(data)["analysis_status"] == STATUS, f"missing analysis status: {name}")
        elif name.endswith(".md"):
            frozen.require(("analysis_status = " + STATUS).encode() in data, f"missing analysis status: {name}")
    frozen.require(all(row["analysis_status"] == STATUS for row in rows), "matrix missing analysis status")
    return {"input_packet_count": len(records), "error_matrix_record_count": len(rows),
            "unique_packet_ids": len({row["packet_id"] for row in rows}),
            "missing_packets": 0, "extra_packets": 0, "duplicate_packets": 0,
            "canonical_order_preserved": True, "frozen_primary_fields_preserved_exactly": True,
            "csv_jsonl_typed_records_identical": True, "all_analyses_marked_post_unblinding": True}


def generate():
    roots_before = verify_roots()
    before = protected_hashes()
    records = frozen.read_jsonl(frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
    metrics = {name: frozen.read_json(frozen.RUN / name) for name in [
        "tier_metrics.json", "metric_definition_audit.json", "engineering_heuristics.json"]}
    outputs, rows = build_analysis(records, metrics)
    roots_after = verify_roots()
    after = protected_hashes()
    frozen.require(before == after and roots_before == roots_after, "historical scientific assets changed")
    flags = {"source_adjudications_modified": False, "v22_search_plan_modified": False,
             "v23_production_behavior_added": False, "heldout_v1_marked_seen_for_v23": True,
             "new_primary_metrics_added": False, "retroactive_heuristics_assigned": False,
             "historical_assets_modified": False}
    outputs["root_hash_verification.json"] = frozen.pretty_json(tagged({
        **HASHES, "status": "PASS", "roots_before": roots_before, "roots_after": roots_after,
        "all_seven_frozen_roots_verified": True, "all_seven_frozen_roots_unchanged": True}))
    outputs["scientific_state_safety_audit.json"] = frozen.pretty_json(tagged({
        **flags, **frozen.ZERO_CALLS, **frozen.ZERO_MODIFICATIONS, "git_mutation_invoked": False,
        "protected_hashes_before": before, "protected_hashes_after": after,
        "protected_scope": "Every git-tracked file plus every file in the seven frozen source runs and evaluator workspace; no paper content is parsed.",
        "allowed_writes": [str(RUN.relative_to(ROOT))]}))
    validation = validate_outputs(outputs, rows, records)
    outputs["validation.json"] = frozen.pretty_json(tagged({"status": "PASS", **validation, **flags,
        "root_verification_precedes_analysis": True, "failure_mapping_fields_allowlisted": True,
        "canonical_primary_fields_reconstructed_exactly": True}))
    components = [{"path": name, "sha256": frozen.digest(outputs[name])} for name in sorted(outputs)]
    analysis_hash = frozen.digest(frozen.canonical_json([[item["path"], item["sha256"]] for item in components]))
    outputs["manifest.json"] = frozen.pretty_json(tagged({
        **HASHES, "v22_to_v23_error_analysis_sha256": analysis_hash, "components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs; UTF-8, sorted keys, compact separators)",
        "hash_scope": "Every run artifact except manifest.json and summary.json (nonrecursive hash carriers)",
        "implementation_not_started": True, "heldout_v1_seen_for_v23": True}))
    outputs["summary.json"] = frozen.pretty_json(tagged({
        "status": "completed", **validation, **flags, **frozen.ZERO_CALLS, **HASHES,
        "v22_to_v23_error_analysis_sha256": analysis_hash,
        "failure_family_counts": {family: value["packet_count"] for family, value in family_composition(rows).items()},
        "output_file_count": len(REQUIRED)}))
    frozen.require(set(outputs) == REQUIRED, "unexpected output membership")
    validate_outputs(outputs, rows, records)
    return outputs


def write_or_verify(outputs, destination):
    if destination.exists():
        frozen.require(destination.is_dir() and not destination.is_symlink(), "invalid output directory")
        frozen.require({path.name for path in destination.iterdir()} == set(outputs), "output membership differs; no overwrite")
        frozen.require(all(not (destination / name).is_symlink() and (destination / name).read_bytes() == data
                           for name, data in outputs.items()), "existing output differs; no overwrite")
    else:
        destination.mkdir()
        for name, data in outputs.items():
            with (destination / name).open("xb") as handle:
                handle.write(data)
    frozen.require(all(frozen.sha256(destination / name) == frozen.digest(data)
                       for name, data in outputs.items()), "post-write SHA-256 verification failed")


def main():
    before = protected_hashes()
    first, second = generate(), generate()
    frozen.require(first == second, "deterministic replay failed")
    write_or_verify(first, RUN)
    verify_roots()
    frozen.require(before == protected_hashes(), "protected state changed during write")
    print(first["summary.json"].decode())
    print("deterministic_replay_byte_identical=true")


if __name__ == "__main__":
    main()
