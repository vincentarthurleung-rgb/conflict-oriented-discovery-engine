#!/usr/bin/env python3
"""Freeze the eight user-supplied held-out-v2 scientific targets offline."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.search.historical_manifest_verifier import verify_frozen_manifest

if __package__:
    from . import freeze_search_plan_v23_beta_protocol_offline as beta
else:
    import freeze_search_plan_v23_beta_protocol_offline as beta


ROOT = beta.ROOT
RUN = ROOT / "runs/20260915_search_plan_v23_beta_heldout_v2_case_freeze_offline"
PROTOCOL_RUN = beta.RUN
V1_TARGETS = beta.alpha4.TARGETS
EXPECTED_PROTOCOL_ROOT = "2bf89cca40c892307968cd279052ec1945d3c59940a785111b2e0de13eebf766"
ZERO_CALLS = {"network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0}
REQUIRED = {
    "heldout_v2_cases.json",
    "heldout_v2_scientific_targets.jsonl",
    "heldout_v2_case_selection_rationale.json",
    "heldout_v2_case_selection_rationale.md",
    "heldout_v1_nonoverlap_audit.json",
    "protocol_root_verification.json",
    "scientific_state_safety_audit.json",
    "freeze_manifest.json",
    "validation.json",
    "summary.json",
}


def require(condition, message):
    beta.require(condition, message)


def pretty(value):
    return beta.pretty(value)


def sha(path: Path):
    return beta.sha(path)


def digest(body: bytes):
    return beta.digest(body)


def canonical_json(value):
    return beta.alpha1.frozen.canonical_json(value)


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def norm(value):
    return normalize_lexical_surface(str(value or "")).normalized_surface


def tagged(payload):
    return {"freeze_status": "structured_prospective_case_selection_pre_retrieval", **payload}


def target(
    case_id, proposition, subject, canonical_subject, relation_family,
    canonical_relation_family, measurement_target, measurement_property_endpoint,
    context_qualifiers, context_dimensions, required_evidence_mode,
    acceptable_endpoint_evidence, insufficient_evidence, scientific_boundaries,
    *, therapy=None, subject_intervention=None,
):
    return {
        "acceptable_endpoint_evidence": acceptable_endpoint_evidence,
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "canonical_relation_family": canonical_relation_family,
        "canonical_subject": canonical_subject,
        "case_id": case_id,
        "context_qualifier_dimensions": context_dimensions,
        "context_qualifiers": context_qualifiers,
        "frozen": True,
        "insufficient_evidence": insufficient_evidence,
        "measurement_property_endpoint": measurement_property_endpoint,
        "measurement_target": measurement_target,
        "object": measurement_target,
        "primary_evidence_required": True,
        "primary_proposition_meaning": proposition,
        "relation_family": relation_family,
        "required_evidence_mode": required_evidence_mode,
        "retrieval_membership_grants_compatibility": False,
        "scientific_boundaries": scientific_boundaries,
        "scientific_proposition_target_id": f"{case_id}:scientific_proposition:v1",
        "subject": subject,
        "subject_intervention": subject_intervention,
        "therapy": therapy,
    }


def build_targets():
    return [
        target(
            "heldout_v2_001",
            "Insulin increases AKT phosphorylation in adipocytes.",
            "insulin", "insulin", "increases", "increases",
            "AKT", "phosphorylation / activation-state phosphorylation",
            ["adipocyte / adipocyte-compatible model", "insulin stimulation"],
            {"biological_unit": ["adipocyte / adipocyte-compatible model"],
             "treatment": ["insulin stimulation"]},
            "current-study perturbational evidence in which insulin exposure is linked to increased AKT phosphorylation",
            ["phospho-AKT", "AKT phosphorylation",
             "explicitly resolved activated phosphorylated AKT readout"],
            ["total AKT abundance", "glucose uptake without AKT phosphorylation",
             "insulin receptor phosphorylation without AKT endpoint", "insulin/AKT pathway discussion",
             "co-expression or association", "generic metabolic response"],
            ["Adipocytes and explicitly authorized adipocyte models may qualify.",
             "Other cell types must not automatically qualify."],
        ),
        target(
            "heldout_v2_002",
            "TNF-α increases ICAM1 expression in vascular endothelial cells.",
            "TNF-α / TNF", "TNF-α", "increases", "increases",
            "ICAM1", "expression / abundance",
            ["vascular endothelial cell", "TNF-α stimulation"],
            {"biological_unit": ["vascular endothelial cell"],
             "treatment": ["TNF-α stimulation"]},
            "current-study TNF-α perturbation linked to increased ICAM1 expression or abundance",
            ["ICAM1 mRNA when target policy explicitly permits expression-level endpoint evidence",
             "ICAM1 protein abundance", "cell-surface ICAM1 explicitly measured as expression"],
            ["VCAM1 only", "selectins only", "generic endothelial activation",
             "NF-κB activation without ICAM1 endpoint",
             "inflammatory association without TNF perturbation"],
            ["Non-endothelial cells are not compatible merely because ICAM1 is measured."],
        ),
        target(
            "heldout_v2_003",
            "Leptin increases STAT3 phosphorylation in hypothalamic neurons.",
            "leptin", "leptin", "increases", "increases",
            "STAT3", "phosphorylation",
            ["neuron", "hypothalamus / explicitly resolved hypothalamic neuronal population",
             "leptin stimulation"],
            {"biological_unit": ["neuron"],
             "anatomical_region": ["hypothalamus / explicitly resolved hypothalamic neuronal population"],
             "treatment": ["leptin stimulation"]},
            "current-study leptin perturbation linked to increased STAT3 phosphorylation in the required neuronal and anatomical-region context",
            ["STAT3 phosphorylation", "phospho-STAT3 in explicitly resolved hypothalamic neurons"],
            ["total STAT3", "leptin receptor abundance", "STAT3 phosphorylation in peripheral tissue",
             "hypothalamic tissue signal without neuronal resolution",
             "neuronal STAT3 in a non-hypothalamic region", "correlation between leptin and STAT3"],
            ["Anatomical location and neuronal identity are separate required dimensions."],
        ),
        target(
            "heldout_v2_004",
            "VEGF-A increases permeability of vascular endothelial barriers.",
            "VEGF-A / VEGF where identity resolves to VEGF-A under existing authority",
            "VEGF-A", "increases", "increases",
            "endothelial barrier permeability", "functional permeability / barrier leak",
            ["vascular endothelial cell / endothelial monolayer / explicitly compatible vascular endothelial model"],
            {"biological_unit": [
                "vascular endothelial cell / endothelial monolayer / explicitly compatible vascular endothelial model"
            ]},
            "current-study VEGF-A perturbation with a functional endothelial permeability or barrier readout",
            ["endothelial permeability", "transendothelial flux", "barrier leakage",
             "electrical barrier loss explicitly measuring endothelial permeability or barrier function"],
            ["VEGFR phosphorylation", "junction-protein expression without functional barrier measurement",
             "endothelial migration", "angiogenesis", "proliferation",
             "vascular permeability discussed only as background"],
            ["Junction localization is not functional permeability unless frozen endpoint authority explicitly permits it."],
        ),
        target(
            "heldout_v2_005",
            "TREM2 signaling increases amyloid-β phagocytosis by microglia.",
            "TREM2", "TREM2", "increases / promotes", "promotes",
            "amyloid-β phagocytosis", "cellular uptake / phagocytic clearance of amyloid-β",
            ["microglia"], {"biological_unit": ["microglia"]},
            "functional current-study evidence linking TREM2 perturbation or signaling to amyloid-β uptake, engulfment, phagocytosis, or directly compatible phagocytic clearance",
            ["TREM2 activation or gain with increased amyloid-β phagocytosis",
             "TREM2 loss or blockade with reduced amyloid-β phagocytosis",
             "target-specific rescue or necessity evidence"],
            ["TREM2 expression in disease-associated microglia", "microglial activation markers",
             "general phagocytosis without amyloid-β endpoint", "amyloid plaque association",
             "migration or chemotaxis", "inflammatory cytokine production",
             "macrophage evidence without microglial compatibility"],
            ["Generic phagocytosis is not amyloid-β phagocytosis."],
        ),
        target(
            "heldout_v2_006",
            "PINK1 loss decreases mitophagy in dopaminergic neurons.",
            "PINK1", "PINK1", "decreases when lost / is required for", "loss_decreases",
            "mitophagy", "selective mitochondrial autophagic clearance",
            ["dopaminergic neuron"], {"biological_unit": ["dopaminergic neuron"]},
            "current-study PINK1 loss, inhibition, or deficiency linked to reduced mitophagic clearance in dopaminergic neurons or explicitly authorized dopaminergic neuronal models",
            ["direct compatible mitophagy assay under PINK1 loss, inhibition, or deficiency"],
            ["mitochondrial membrane potential", "mitochondrial morphology", "general autophagy",
             "Parkin abundance or localization alone", "neuronal survival alone", "oxidative stress",
             "non-dopaminergic cell lines without authorized model compatibility",
             "PINK1 association with Parkinson disease without functional mitophagy evidence"],
            ["General autophagy is not mitophagy.",
             "Canonical proposition orientation is PINK1 loss to decreased mitophagy."],
            subject_intervention="loss / inhibition / deficiency",
        ),
        target(
            "heldout_v2_007",
            "YAP1 activation contributes to vemurafenib resistance in BRAF-mutant melanoma.",
            "YAP1 / YAP", "YAP1", "contributes_to resistance", "contributes_to",
            "vemurafenib treatment response", "resistance / reduced sensitivity",
            ["melanoma", "BRAF-mutant / BRAF V600-class context", "vemurafenib treatment"],
            {"disease_context": ["melanoma"],
             "genotype_context": ["BRAF-mutant / BRAF V600-class context"],
             "therapy": ["vemurafenib"]},
            "current-study functional evidence linking YAP1 activity to vemurafenib response",
            ["YAP1 activation increasing vemurafenib resistance",
             "YAP1 inhibition or knockdown restoring vemurafenib sensitivity",
             "target-specific necessity or rescue evidence"],
            ["YAP1 expression correlated with resistance", "generic MAPK inhibitor resistance",
             "resistance to a different therapy", "BRAF-mutant melanoma without YAP1 functional evidence",
             "generic melanoma growth", "viability effects without vemurafenib response context"],
            ["Other RAF or MEK inhibitors cannot substitute for vemurafenib unless existing therapy identity authority explicitly permits equivalence."],
            therapy="vemurafenib", subject_intervention="activation / inhibition-or-knockdown counterevidence",
        ),
        target(
            "heldout_v2_008",
            "ATR inhibition increases cisplatin sensitivity in ovarian cancer cells.",
            "ATR", "ATR", "inhibition increases sensitivity / sensitizes", "inhibition_increases_sensitivity",
            "cisplatin treatment response", "increased sensitivity / decreased resistance",
            ["ovarian cancer", "ovarian-cancer cell / explicitly compatible ovarian-cancer model",
             "cisplatin treatment"],
            {"disease_context": ["ovarian cancer"],
             "biological_unit": ["ovarian-cancer cell / explicitly compatible ovarian-cancer model"],
             "therapy": ["cisplatin"]},
            "current-study ATR inhibition or depletion linked to increased cisplatin sensitivity",
            ["ATR inhibitor plus cisplatin producing target-specific sensitization",
             "ATR knockdown or depletion increasing cisplatin response",
             "loss-of-function evidence compatible with increased cisplatin sensitivity"],
            ["ATR inhibitor monotherapy cytotoxicity", "cisplatin cytotoxicity without ATR perturbation",
             "generic DNA damage", "sensitivity to another platinum or drug without authorized therapy equivalence",
             "ovarian cancer association with ATR expression",
             "combination effect without evidence that ATR is the relevant target"],
            ["Generic viability reduction is not automatically cisplatin sensitization."],
            therapy="cisplatin", subject_intervention="inhibition / depletion / loss-of-function",
        ),
    ]


CASE_META = [
    ("heldout_v2_001", 1, "LOW", "non_oncology"),
    ("heldout_v2_002", 2, "LOW", "non_oncology"),
    ("heldout_v2_003", 3, "MEDIUM", "non_oncology"),
    ("heldout_v2_004", 4, "MEDIUM", "non_oncology"),
    ("heldout_v2_005", 5, "HIGH", "non_oncology"),
    ("heldout_v2_006", 6, "HIGH", "non_oncology"),
    ("heldout_v2_007", 7, "HIGH", "oncology"),
    ("heldout_v2_008", 8, "HIGH", "oncology"),
]


def build_cases(targets):
    by_id = {row["case_id"]: row for row in targets}
    cases = []
    for case_id, order, ambiguity, domain in CASE_META:
        item = by_id[case_id]
        cases.append({
            "artifact_schema_version": "HeldoutV2CaseV1",
            "case_id": case_id,
            "case_order": order,
            "ambiguity": ambiguity,
            "domain": domain,
            "oncology": domain == "oncology",
            "scientific_proposition": item["primary_proposition_meaning"],
            "scientific_proposition_target_id": item["scientific_proposition_target_id"],
            "case_selection_method": "structured_prospective_case_selection",
            "case_state": "FROZEN_PRE_QUERY_COMPILATION",
            "replacement_allowed_after_retrieval_begins": False,
        })
    return tagged({
        "artifact_schema_version": "HeldoutV2CaseSetV1",
        "search_plan_version": "v2.3-beta",
        "case_count": len(cases),
        "cases": cases,
    })


def build_rationale(cases):
    rationales = {
        "LOW": "Single clear perturbation, a well-defined molecular endpoint, and a relatively simple biological-unit constraint.",
        "MEDIUM": "An additional anatomical-region or functional-readout constraint creates scientific compatibility ambiguity without therapy-response complexity.",
        "HIGH": "The proposition combines one or more precise biological-unit, specialized functional-endpoint, inverse-perturbation, disease/genotype, therapy-identity, treatment-response, or target-specific contribution requirements.",
    }
    case_specific = {
        "heldout_v2_001": "Single insulin perturbation, molecular phosphorylation endpoint, and one adipocyte-unit constraint.",
        "heldout_v2_002": "Single TNF-α perturbation, explicit ICAM1 abundance endpoint, and one endothelial-cell constraint.",
        "heldout_v2_003": "Requires both neuronal identity and hypothalamic-region resolution in addition to the phosphorylation endpoint.",
        "heldout_v2_004": "Requires a functional endothelial barrier-permeability readout rather than related junction, migration, angiogenesis, or signaling observations.",
        "heldout_v2_005": "Combines a microglial-unit constraint, amyloid-β-specific phagocytosis, and compatible gain/loss or rescue reasoning.",
        "heldout_v2_006": "Combines dopaminergic-neuron specificity, selective mitophagy, and inverse PINK1-loss reasoning.",
        "heldout_v2_007": "Combines YAP1 functional contribution, BRAF-mutant melanoma context, exact vemurafenib identity, and resistance semantics.",
        "heldout_v2_008": "Combines ATR target-specific inhibition, ovarian-cancer model identity, exact cisplatin identity, and sensitization semantics.",
    }
    per_case = []
    for case in cases["cases"]:
        per_case.append({
            "case_id": case["case_id"],
            "ambiguity": case["ambiguity"],
            "rationale": case_specific[case["case_id"]],
            "frozen_before_retrieval": True,
            "modifiable_after_retrieval": False,
        })
    return tagged({
        "artifact_schema_version": "HeldoutV2CaseSelectionRationaleV1",
        "selection_method": "structured_prospective_case_selection",
        "random_sampling_claimed": False,
        "stratum_rationales": rationales,
        "per_case_rationales": per_case,
        "selection_independence": {
            "retrieval_yield_used": False,
            "pubmed_hit_counts_used": False,
            "candidate_relevance_used": False,
            "oa_availability_used": False,
            "prior_pass_a_or_b_outcomes_for_these_cases_used": False,
            "v23_beta_performance_used": False,
            "knowledge_of_favorable_p0_p1_p2_classification_used": False,
            "selection_basis": "frozen structural strata and scientifically heterogeneous proposition types",
        },
    })


def rationale_markdown(rationale, cases):
    per_case = {row["case_id"]: row["rationale"] for row in rationale["per_case_rationales"]}
    lines = [
        "# Held-out-v2 case-selection rationale", "",
        "Selection method: **structured prospective case selection**. Random sampling is not claimed.", "",
        "All rationales are frozen before query compilation, retrieval, candidate inspection, yield inspection, or OA inspection.", "",
        "## Strata", "",
    ]
    for stratum in ("LOW", "MEDIUM", "HIGH"):
        lines.extend([f"### {stratum}", "", rationale["stratum_rationales"][stratum], ""])
        for case in cases["cases"]:
            if case["ambiguity"] == stratum:
                lines.append(
                    f"- `{case['case_id']}` — {case['scientific_proposition']} "
                    f"Rationale: {per_case[case['case_id']]}"
                )
        lines.append("")
    lines.extend([
        "## Selection independence", "",
        "No retrieval yield, PubMed hit count, candidate relevance, OA availability, case-specific PASS A/B outcome, v2.3-beta performance result, or expected favorable module classification was used.", "",
        "Cases were selected to satisfy the frozen 2/2/4 ambiguity strata, 2/6 oncology composition, and scientific heterogeneity requirements.", "",
    ])
    return "\n".join(lines).encode()


ENDPOINT_FAMILY_MARKERS = {
    "phosphorylation": ("phosphorylation", "phospho"),
    "expression_or_abundance": ("expression", "abundance"),
    "functional_uptake_or_clearance": ("uptake", "phagocyt", "clearance"),
    "treatment_response": ("resistance", "sensitivity", "treatment response", "drug response"),
}


def marker_families(target_row):
    value = norm(target_row["measurement_property_endpoint"] + " " + target_row["measurement_target"])
    return {family for family, markers in ENDPOINT_FAMILY_MARKERS.items()
            if any(norm(marker) in value for marker in markers)}


def context_types_v1(target_row):
    types = {"biological_unit"} if target_row.get("context_qualifiers") else set()
    text = norm(" ".join(target_row.get("context_qualifiers", [])))
    if any(marker in text for marker in ("cancer", "leukemia", "melanoma")):
        types.add("disease_context")
    if "mutant" in text:
        types.add("genotype_context")
    if any(marker in text for marker in ("hippocamp", "hypothalam")):
        types.add("anatomical_region")
    if target_row.get("therapy"):
        types.add("therapy")
    return types


def context_types_v2(target_row):
    return set(target_row["context_qualifier_dimensions"])


def exact_triple(target_row, *, v2):
    subject = target_row["canonical_subject"] if v2 else target_row["subject"]
    relation = target_row["canonical_relation_family"] if v2 else target_row["relation_family"]
    endpoint = f"{target_row['measurement_target']}|{target_row['measurement_property_endpoint']}"
    return norm(subject), norm(relation), norm(endpoint)


def build_nonoverlap(targets):
    previous = read_jsonl(V1_TARGETS)
    v1_propositions = {norm(row["primary_proposition_meaning"]): row["case_id"] for row in previous}
    v1_triples = {exact_triple(row, v2=False): row["case_id"] for row in previous}
    proposition_overlaps = []
    triple_overlaps = []
    for row in targets:
        proposition_key = norm(row["primary_proposition_meaning"])
        triple_key = exact_triple(row, v2=True)
        if proposition_key in v1_propositions:
            proposition_overlaps.append({"heldout_v2_case_id": row["case_id"],
                                         "heldout_v1_case_id": v1_propositions[proposition_key]})
        if triple_key in v1_triples:
            triple_overlaps.append({"heldout_v2_case_id": row["case_id"],
                                    "heldout_v1_case_id": v1_triples[triple_key]})

    shared_subjects = sorted(set(norm(row["canonical_subject"]) for row in targets)
                             & set(norm(row["subject"]) for row in previous))
    shared_relations = sorted(set(norm(row["canonical_relation_family"]) for row in targets)
                              & set(norm(row["relation_family"]) for row in previous))
    v1_endpoint = set().union(*(marker_families(row) for row in previous))
    v2_endpoint = set().union(*(marker_families(row) for row in targets))
    v1_context = set().union(*(context_types_v1(row) for row in previous))
    v2_context = set().union(*(context_types_v2(row) for row in targets))
    require(not proposition_overlaps and not triple_overlaps, "heldout-v1 exact overlap detected")
    return tagged({
        "artifact_schema_version": "HeldoutV1NonOverlapAuditV1",
        "comparison_source": str(V1_TARGETS.relative_to(ROOT)),
        "comparison_source_sha256": sha(V1_TARGETS),
        "heldout_v1_target_count": len(previous),
        "heldout_v2_target_count": len(targets),
        "normalization": "existing deterministic lexical normalization; exact tuple equality after normalization",
        "exact_proposition_overlap": len(proposition_overlaps),
        "exact_proposition_overlap_records": proposition_overlaps,
        "exact_subject_relation_endpoint_triple_overlap": len(triple_overlaps),
        "exact_subject_relation_endpoint_triple_overlap_records": triple_overlaps,
        "descriptive_component_overlap_only": {
            "shared_exact_subject_values": shared_subjects,
            "shared_exact_relation_family_values": shared_relations,
            "shared_endpoint_marker_families": sorted(v1_endpoint & v2_endpoint),
            "shared_context_types": sorted(v1_context & v2_context),
            "invalidates_case_selection": False,
        },
        "shared_components_do_not_imply_exact_proposition_overlap": True,
    })


def verify_protocol_root():
    result = verify_frozen_manifest(
        PROTOCOL_RUN, manifest_name="version_manifest.json",
        root_field="search_plan_v23_beta_protocol_sha256",
    )
    require(result["aggregate_sha256"] == EXPECTED_PROTOCOL_ROOT,
            "v2.3-beta protocol root mismatch")
    manifest = json.loads((PROTOCOL_RUN / "version_manifest.json").read_bytes())
    require(manifest["search_plan_v23_beta_protocol_sha256"] == EXPECTED_PROTOCOL_ROOT,
            "declared v2.3-beta protocol root mismatch")
    for row in manifest["production_candidate_files"]:
        require(sha(ROOT / row["path"]) == row["sha256"],
                f"v2.3-beta production candidate changed: {row['path']}")
    beta.verify_upstreams()
    return tagged({
        "artifact_schema_version": "V23BetaProtocolRootVerificationV1",
        "status": "PASS",
        "expected_search_plan_v23_beta_protocol_sha256": EXPECTED_PROTOCOL_ROOT,
        "actual_search_plan_v23_beta_protocol_sha256": result["aggregate_sha256"],
        "match": True,
        "protected_component_count": result["protected_file_count"],
        "protocol_manifest_path": str((PROTOCOL_RUN / "version_manifest.json").relative_to(ROOT)),
    })


def protected_state():
    paths = [path for path in PROTOCOL_RUN.iterdir() if path.is_file()]
    paths.extend(path for path in beta.alpha4.RUN.iterdir() if path.is_file())
    paths.extend([
        beta.CONFIG, beta.IMPLEMENTATION, beta.V22_QUERY_COMPILER,
        beta.alpha1_1.IMPLEMENTATION_PATH, beta.alpha1_1.REGISTRY_OVERLAY_PATH,
        beta.alpha1_1.POLICY_OVERLAY_PATH, beta.alpha2_1.IMPLEMENTATION_PATH,
        beta.alpha2_1.POLICY_PATH, beta.alpha3.IMPLEMENTATION_PATH,
        beta.alpha3.REGISTRY_PATH, beta.alpha3.POLICY_PATH, V1_TARGETS,
    ])
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(paths))}


def validate_targets(targets, cases):
    required = {
        "subject", "relation_family", "measurement_target",
        "measurement_property_endpoint", "required_evidence_mode",
        "context_qualifiers", "context_qualifier_dimensions",
    }
    require(len(targets) == len({row["case_id"] for row in targets}) == 8,
            "heldout-v2 target identity mismatch")
    require(all(required <= set(row) and all(row[field] for field in required)
                for row in targets), "heldout-v2 target completeness failure")
    required_dimensions = {
        "heldout_v2_001": {"biological_unit", "treatment"},
        "heldout_v2_002": {"biological_unit", "treatment"},
        "heldout_v2_003": {"biological_unit", "anatomical_region", "treatment"},
        "heldout_v2_004": {"biological_unit"},
        "heldout_v2_005": {"biological_unit"},
        "heldout_v2_006": {"biological_unit"},
        "heldout_v2_007": {"disease_context", "genotype_context", "therapy"},
        "heldout_v2_008": {"disease_context", "biological_unit", "therapy"},
    }
    for row in targets:
        require(set(row["context_qualifier_dimensions"]) == required_dimensions[row["case_id"]],
                f"required context dimensions missing: {row['case_id']}")
    ambiguity = Counter(row["ambiguity"] for row in cases["cases"])
    domain = Counter(row["domain"] for row in cases["cases"])
    require(ambiguity == {"LOW": 2, "MEDIUM": 2, "HIGH": 4}, "ambiguity strata mismatch")
    require(domain == {"oncology": 2, "non_oncology": 6}, "domain strata mismatch")
    return ambiguity, domain


def build_core(before, after):
    require(before == after, "protected state changed before case-freeze build")
    targets = build_targets()
    cases = build_cases(targets)
    ambiguity, domain = validate_targets(targets, cases)
    rationale = build_rationale(cases)
    nonoverlap = build_nonoverlap(targets)
    protocol = verify_protocol_root()
    target_body = b"".join(canonical_json(row) + b"\n" for row in targets)
    safety = tagged({
        "artifact_schema_version": "HeldoutV2CaseFreezeScientificStateSafetyAuditV1",
        "status": "PASS",
        **ZERO_CALLS,
        "pubmed_searches": 0,
        "pmc_searches": 0,
        "crossref_searches": 0,
        "google_scholar_searches": 0,
        "general_web_searches": 0,
        "candidate_titles_inspected": 0,
        "oa_availability_inspected": False,
        "yield_estimated": False,
        "queries_compiled": False,
        "retrieval_started": False,
        "candidate_inspection_performed": False,
        "search_plan_v23_beta_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "adjudication_boundary_v2_modified": False,
        "query_compiler_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_state_before": before,
        "protected_state_after": after,
    })
    validation = tagged({
        "artifact_schema_version": "HeldoutV2CaseFreezeValidationV1",
        "status": "PASS",
        "case_count": len(targets),
        "low_count": ambiguity["LOW"],
        "medium_count": ambiguity["MEDIUM"],
        "high_count": ambiguity["HIGH"],
        "oncology_count": domain["oncology"],
        "non_oncology_count": domain["non_oncology"],
        "exact_proposition_overlap": nonoverlap["exact_proposition_overlap"],
        "exact_subject_relation_endpoint_triple_overlap": nonoverlap[
            "exact_subject_relation_endpoint_triple_overlap"
        ],
        "case_replacements": 0,
        "queries_compiled": False,
        "retrieval_started": False,
        "candidate_inspection_performed": False,
        "all_targets_have_required_core_fields": True,
        "all_targets_have_explicit_evidence_mode_requirement": True,
        "all_scientifically_required_context_qualifiers_present": True,
        "structured_prospective_case_selection": True,
        "random_sampling_claimed": False,
        "freeze_generation_replay_byte_identical": True,
    })
    outputs = {
        "heldout_v2_cases.json": pretty(cases),
        "heldout_v2_scientific_targets.jsonl": target_body,
        "heldout_v2_case_selection_rationale.json": pretty(rationale),
        "heldout_v2_case_selection_rationale.md": rationale_markdown(rationale, cases),
        "heldout_v1_nonoverlap_audit.json": pretty(nonoverlap),
        "protocol_root_verification.json": pretty(protocol),
        "scientific_state_safety_audit.json": pretty(safety),
        "validation.json": pretty(validation),
    }
    return outputs, targets, cases, validation


def build_complete(before, after):
    outputs, targets, cases, validation = build_core(before, after)
    components = [{"path": name, "sha256": digest(outputs[name])} for name in sorted(outputs)]
    aggregate = digest(canonical_json([[row["path"], row["sha256"]] for row in components]))
    manifest = tagged({
        "artifact_schema_version": "HeldoutV2CaseFreezeManifestV1",
        "search_plan_version": "v2.3-beta",
        "upstream_search_plan_v23_beta_protocol_sha256": EXPECTED_PROTOCOL_ROOT,
        "heldout_v2_case_freeze_sha256": aggregate,
        "component_count": len(components),
        "components": components,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "All required outputs except freeze_manifest.json and summary.json.",
        "required_outputs": sorted(REQUIRED),
    })
    summary = tagged({
        "status": "completed",
        "case_count": validation["case_count"],
        "low_count": validation["low_count"],
        "medium_count": validation["medium_count"],
        "high_count": validation["high_count"],
        "oncology_count": validation["oncology_count"],
        "non_oncology_count": validation["non_oncology_count"],
        "exact_proposition_overlap": 0,
        "exact_subject_relation_endpoint_triple_overlap": 0,
        "case_replacements": 0,
        "queries_compiled": False,
        "retrieval_started": False,
        "candidate_inspection_performed": False,
        "search_plan_v23_beta_modified": False,
        "p0_modified": False,
        "p1_modified": False,
        "p2_modified": False,
        "policy_a_modified": False,
        "metrics_spec_v2_modified": False,
        "adjudication_boundary_v2_modified": False,
        "query_compiler_modified": False,
        "heldout_v2_case_freeze_sha256": aggregate,
        "freeze_generation_replay_byte_identical": True,
        **ZERO_CALLS,
        "historical_assets_modified": False,
    })
    outputs["freeze_manifest.json"] = pretty(manifest)
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED and len(outputs) == 10,
            f"case-freeze output membership mismatch: {sorted(set(outputs) ^ REQUIRED)}")
    return outputs, aggregate, targets, cases


def write_outputs(outputs):
    RUN.mkdir(exist_ok=True)
    for name, body in outputs.items():
        path = RUN / name
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                    f"existing case-freeze artifact differs; no overwrite: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == body,
                f"case-freeze write verification failed: {name}")
    require({path.name for path in RUN.iterdir()} == REQUIRED,
            "case-freeze run contains unexpected files")


def freeze():
    verify_protocol_root()
    before = protected_state()
    after_inputs = protected_state()
    outputs_a, root_a, targets_a, cases_a = build_complete(before, after_inputs)
    outputs_b, root_b, targets_b, cases_b = build_complete(before, after_inputs)
    require(outputs_a == outputs_b and root_a == root_b
            and targets_a == targets_b and cases_a == cases_b,
            "case-freeze generation replay is not byte-identical")
    write_outputs(outputs_a)
    require(before == protected_state(), "historical state changed during case freeze")
    return outputs_a


def main():
    outputs = freeze()
    print(outputs["summary.json"].decode())
    print("freeze_generation_replay_byte_identical=true")


if __name__ == "__main__":
    main()
