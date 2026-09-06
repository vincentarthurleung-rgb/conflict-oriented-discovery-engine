#!/usr/bin/env python3
"""Generate the proposed Search Plan v2.1 high-ambiguity review packet.

The script consumes only the prior offline planning run and repository-local
artifacts.  It performs no retrieval, network, provider, or model operations.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "runs/20260906_search_plan_v2_multicase_stress_test_offline"
RUN_ID = "20260906_search_plan_v21_high_ambiguity_review_offline"
OUT = ROOT / "runs" / RUN_ID
CASE_IDS = ["spv2_003", "spv2_004", "spv2_006", "spv2_008", "spv2_013", "spv2_019"]
CREATED_AT = "2026-09-06T00:00:00+08:00"


REVIEW = {
    "spv2_003": {
        "ambiguity": "Drug resistance leaves therapeutic identity, intrinsic/acquired status, evidence scale, and resistance readout unfixed.",
        "retrieval_granularity": "EMT plus drug/therapy resistance-family wording; named agents may be separate optional variants only after authority is supplied.",
        "scientific_granularity": "A resistance observation must identify the drug or therapy, resistant-versus-sensitive or exposure comparator, and a resistance-relevant outcome.",
        "false_positive": ["antimicrobial resistance", "stress resistance without cancer treatment", "EMT marker studies with no treatment phenotype", "discussion-only EMT/resistance co-mention"],
        "false_negative": ["authorized EMT abbreviation absent from this plan", "papers framed as loss of sensitivity rather than resistance", "agent-specific resistance papers omitting generic drug-resistance wording"],
        "unresolved": ["therapy identity", "intrinsic versus acquired resistance", "cellular versus clinical evidence level", "minimum resistance comparator"],
        "revisions": ["add an EMT-authorized alias variant", "separate resistance wording from sensitivity wording", "route agent-specific variants to manual authority", "replace generic role query with explicit relation variants"],
        "questions": [
            "Must a qualifying proposition name a specific therapeutic agent, or is an identified therapy class sufficient?",
            "Is loss of cell viability under treatment an acceptable resistance-family signal for Tier B when a resistant-versus-sensitive comparator is absent?",
        ],
        "therapy": {"applies": True, "identity_status": "unresolved_and_proposition_critical", "class_sufficient_for_retrieval": True, "generic_therapy_use": "recall_only_with_resistance_anchor", "too_noisy_when": "therapy appears without resistance/sensitivity evidence"},
        "comparator": {"likely_contrasts": ["resistant versus sensitive", "treated resistant model versus treated control"], "search_required": False, "tier_a_required": True, "tier_b_uncertainty_allowed": "resistance phenotype is plausible but exact comparator is absent"},
        "tier_a": "EMT or scientifically authorized alias AND cancer drug-resistance/sensitivity evidence AND an explicit treatment-linked comparative phenotype, with no wrong-entity or non-cancer-resistance mismatch.",
        "tier_b": "EMT and a cancer treatment resistance family are plausible, but fulltext must resolve therapy identity, resistance comparator, intrinsic/acquired status, or phenotype scale.",
        "reject": ["non-cancer antimicrobial resistance", "stress resistance without therapy", "EMT-only study lacking treatment phenotype", "review/discussion-only co-mention when primary evidence is required"],
        "outcome": "SCIENTIFIC_REVIEW_REQUIRED",
    },
    "spv2_004": {
        "ambiguity": "Cancer therapy response can mean clinical response, tumor regression, cell sensitivity/viability, molecular response, or general efficacy; the therapy is unspecified.",
        "retrieval_granularity": "Ferroptosis plus cancer therapy/response, sensitivity, or efficacy wording; therapy modalities remain separate variants.",
        "scientific_granularity": "The evidence must identify a therapy, response level, response endpoint, and comparison; ferroptosis markers alone are insufficient.",
        "false_positive": ["ferroptosis induction without treatment-response evidence", "normal-tissue treatment toxicity", "molecular pathway response only", "review-only therapeutic discussion"],
        "false_negative": ["agent-specific sensitivity studies omitting 'therapy response'", "tumor-regression wording", "British tumour spelling", "response described as efficacy or sensitization"],
        "unresolved": ["therapy identity or modality", "clinical versus preclinical response", "response endpoint family", "ferroptosis evidence requirement"],
        "revisions": ["split response, sensitivity, efficacy, and regression variants", "do not merge chemotherapy, radiotherapy, targeted therapy, or immunotherapy", "remove generic treatment-outcome variant", "require treatment-linked endpoint evidence at acquisition"],
        "questions": [
            "Which therapy modalities are within proposition scope: any cancer therapy, or only a specified modality/class?",
            "Does a treatment-linked viability or sensitivity assay qualify as the intended response family, or only as Tier B evidence?",
        ],
        "therapy": {"applies": True, "identity_status": "unresolved_and_proposition_critical", "class_sufficient_for_retrieval": True, "generic_therapy_use": "recall_only", "too_noisy_when": "no treatment-linked outcome is visible"},
        "comparator": {"likely_contrasts": ["treated versus untreated", "ferroptosis-enabled versus ferroptosis-blocked under treatment"], "search_required": False, "tier_a_required": True, "tier_b_uncertainty_allowed": "therapy and response family are plausible but comparator or modality is absent"},
        "tier_a": "Ferroptosis evidence AND a cancer treatment anchor AND a treatment-linked response/sensitivity/efficacy endpoint, with a plausible mechanistic relation and no fatal scale mismatch.",
        "tier_b": "Ferroptosis and treatment-linked outcome evidence are plausible, but fulltext must resolve therapy modality, endpoint scale, comparator, or whether ferroptosis is measured rather than merely discussed.",
        "reject": ["toxicity outside cancer", "molecular response without treatment efficacy phenotype", "ferroptosis-only mechanistic study", "review-only evidence when primary evidence is required"],
        "outcome": "SCIENTIFIC_REVIEW_REQUIRED",
    },
    "spv2_006": {
        "ambiguity": "Survival adaptation does not specify patient, animal, tumor, cell, viability, persistence, or stress-adaptation level.",
        "retrieval_granularity": "Ferroptosis plus survival-adaptation wording; cell survival/viability remains a review-gated variant, not an endpoint equivalence.",
        "scientific_granularity": "The survival unit, adaptive exposure or state, measurement, and comparator must be fixed before proposition compatibility can be evaluated.",
        "false_positive": ["patient overall-survival studies", "animal survival in organ injury", "baseline cell viability without adaptation", "ferroptosis cytotoxicity without survival adaptation"],
        "false_negative": ["adaptive tolerance or persistence wording", "viability assays used as an adaptation readout", "stress-conditioned survival studies", "papers omitting the phrase survival adaptation"],
        "unresolved": ["survival unit", "meaning of adaptation", "required stress/exposure", "acceptable viability endpoint", "comparison state"],
        "revisions": ["do not default-map survival to cell survival", "create separately reviewable viability, persistence, and adaptation variants", "remove generic role variant", "require a visible adaptation signal before acquisition"],
        "questions": [
            "Is the frozen target intended to concern cancer-cell survival adaptation rather than patient or organism survival?",
            "What minimum adaptive contrast is required: prior stress/exposure, resistant state, or survival under ferroptotic challenge?",
            "May cell viability be used as a Tier B retrieval surface without authorizing viability as the scientific endpoint?",
        ],
        "therapy": {"applies": False, "identity_status": "not_in_frozen_target", "class_sufficient_for_retrieval": False, "generic_therapy_use": "not_recommended", "too_noisy_when": "always unless a future adjudication adds therapy context"},
        "comparator": {"likely_contrasts": ["adapted versus non-adapted", "challenged versus control"], "search_required": False, "tier_a_required": True, "tier_b_uncertainty_allowed": "adaptation is explicit but the exact control or survival assay is absent"},
        "tier_a": "Ferroptosis AND an explicit cellular/tumor survival-adaptation or persistence phenotype AND an adaptation/challenge comparison, excluding patient/animal survival senses.",
        "tier_b": "Ferroptosis and an adaptive cellular survival phenotype are plausible, but fulltext must resolve survival unit, adaptation exposure, viability/persistence measurement, or comparator.",
        "reject": ["patient prognostic survival", "animal survival outside tumor biology", "baseline viability only", "cell death study with no adaptive survival construct"],
        "outcome": "SEARCH_PLAN_REDESIGN_REQUIRED",
    },
    "spv2_008": {
        "ambiguity": "Hypoxia signaling may mean oxygen exposure, HIF pathway activity, or a hypoxia signature; therapy response may be clinical, tumor-level, cellular, or molecular.",
        "retrieval_granularity": "Hypoxia-signaling or hypoxic-response language plus treatment-linked response-family wording; modalities remain separate.",
        "scientific_granularity": "The hypoxia construct, treatment, response scale, endpoint, and association contrast must be recoverable downstream.",
        "false_positive": ["prognostic hypoxia signature without treatment analysis", "hypoxia treatment studies outside cancer", "molecular response to hypoxia without therapy outcome", "generic hypoxia review"],
        "false_negative": ["hypoxic-response wording", "HIF-pathway proxy terminology", "agent-specific sensitivity/resistance wording", "therapy modality terms replacing generic therapy"],
        "unresolved": ["hypoxia exposure versus signaling", "therapy identity", "response endpoint and scale", "association contrast"],
        "revisions": ["separate hypoxia exposure from signaling variants", "separate sensitivity/resistance from generic response", "remove treatment-outcome variant", "retain association language only as relation recall"],
        "questions": [
            "Can hypoxia exposure or a hypoxia gene signature satisfy retrieval plausibility when pathway signaling is not directly measured?",
            "Is generic cancer therapy response sufficient for the proposition, or must a therapy modality or agent be fixed?",
        ],
        "therapy": {"applies": True, "identity_status": "unresolved_and_proposition_critical", "class_sufficient_for_retrieval": True, "generic_therapy_use": "recall_only_with_response_endpoint", "too_noisy_when": "only prognosis or hypoxia biology is visible"},
        "comparator": {"likely_contrasts": ["hypoxic versus normoxic", "high versus low hypoxia signaling", "treated outcome strata"], "search_required": False, "tier_a_required": False, "tier_b_uncertainty_allowed": "association and treatment outcome are plausible but the hypoxia or outcome contrast is absent"},
        "tier_a": "Hypoxia-signaling evidence AND cancer treatment-response endpoint evidence AND an explicit association or comparative link, without prognosis-only or molecular-response mismatch.",
        "tier_b": "Hypoxia signaling/exposure and treatment outcome are both plausible, but fulltext must resolve signaling proxy, therapy identity, response scale, or comparison strata.",
        "reject": ["prognosis-only outcome", "hypoxia biology without treatment", "molecular hypoxia response mistaken for treatment response", "wrong disease context when cancer is critical"],
        "outcome": "SCIENTIFIC_REVIEW_REQUIRED",
    },
    "spv2_013": {
        "ambiguity": "Tumor survival could mean tumor-cell viability, tumor persistence, animal tumor maintenance, or patient survival; contributes_to is causal rather than mere association.",
        "retrieval_granularity": "NF-kappaB plus tumor/cancer-cell survival, viability, or persistence variants, each retaining its own scale label.",
        "scientific_granularity": "The survival unit, causal evidence mode, NF-kappaB activity measure, and perturbation/comparison must be fixed.",
        "false_positive": ["overall-survival prognostic associations", "immune-cell survival", "NF-kappaB expression without activity or perturbation", "cancer survival statistics"],
        "false_negative": ["cell viability or persistence wording", "NF-kappaB activity/nuclear-localization wording", "inhibition or knockdown evidence", "hyphenation/character variation"],
        "unresolved": ["survival unit", "viability versus persistence endpoint", "minimum causal evidence", "acceptable NF-kappaB activity proxy"],
        "revisions": ["remove slash-combined survival wording", "split viability and persistence variants", "do not use promotes as causal equivalence without review", "reject patient-survival sense at abstract stage when explicit"],
        "questions": [
            "Does tumor survival mean survival/viability of tumor cells, persistence of a tumor, or another unit?",
            "Must Tier A include NF-kappaB perturbation/activity evidence to support contributes_to, or is a strong temporal association sufficient?",
            "Should explicit patient overall survival be a known mismatch even when NF-kappaB is prognostic?",
        ],
        "therapy": {"applies": False, "identity_status": "not_in_frozen_target", "class_sufficient_for_retrieval": False, "generic_therapy_use": "not_recommended", "too_noisy_when": "therapy does not establish tumor survival"},
        "comparator": {"likely_contrasts": ["NF-kappaB perturbed versus control", "high versus low pathway activity"], "search_required": False, "tier_a_required": True, "tier_b_uncertainty_allowed": "cell/tumor survival and NF-kappaB activity are plausible but perturbation or comparator is unclear"},
        "tier_a": "NF-kappaB evidence AND an explicit tumor-cell/tumor survival phenotype AND causal/perturbational plausibility, excluding patient-survival and immune-cell-survival senses.",
        "tier_b": "NF-kappaB and the correct cellular/tumor survival family are plausible, but fulltext must resolve survival unit, activity proxy, causal evidence, or comparator.",
        "reject": ["patient overall/progression-free survival", "non-tumor immune-cell survival", "generic cancer-survival statistics", "NF-kappaB mention without survival phenotype"],
        "outcome": "SEARCH_PLAN_REDESIGN_REQUIRED",
    },
    "spv2_019": {
        "ambiguity": "Metabolism can denote global phenotype, a named pathway, flux, metabolite abundance, substrate use, glycolysis, oxidative phosphorylation, or systemic metabolism.",
        "retrieval_granularity": "mTOR plus broad metabolic wording, followed by separately labeled pathway, flux, and metabolite variants; cancer context remains complementary.",
        "scientific_granularity": "A named metabolic process or measurable property, the mTOR activity/perturbation construct, evidence mode, and comparator must be fixed.",
        "false_positive": ["systemic metabolic disease", "mTOR mention with no metabolic observation", "metabolite abundance without mTOR relation", "review-only pathway discussion"],
        "false_negative": ["specific pathway terms omitting metabolism", "metabolic flux or substrate-use wording", "mTORC1 rather than mTOR surface", "oxidative phosphorylation abbreviations"],
        "unresolved": ["metabolic process", "measurement property", "mTOR versus mTORC1 scope", "activity versus abundance", "required perturbation/comparator"],
        "revisions": ["split global, pathway, flux, and metabolite variants", "do not default-authorize glycolysis or oxidative phosphorylation", "remove generic role query", "require a metabolic observation before acquisition"],
        "questions": [
            "Which metabolic process or property is proposition-critical: global metabolism, flux, glycolysis, oxidative phosphorylation, or another named pathway?",
            "Is mTORC1 a scientifically authorized entity scope for this target, or only a search-lexical candidate?",
            "Must the evidence measure mTOR activity/perturbation, rather than mTOR abundance or mention?",
        ],
        "therapy": {"applies": False, "identity_status": "not_in_frozen_target", "class_sufficient_for_retrieval": False, "generic_therapy_use": "not_recommended", "too_noisy_when": "always for the current proposition"},
        "comparator": {"likely_contrasts": ["mTOR perturbed versus control", "high versus low mTOR activity"], "search_required": False, "tier_a_required": False, "tier_b_uncertainty_allowed": "a metabolic measurement and mTOR relation are plausible but property or contrast is unclear"},
        "tier_a": "mTOR evidence AND an explicit metabolic process/property measurement AND plausible mechanistic involvement, excluding systemic-only or discussion-only metabolism.",
        "tier_b": "mTOR and a measured metabolic phenotype are plausible, but fulltext must resolve pathway/property, flux versus abundance, mTOR activity/complex, or comparator.",
        "reject": ["systemic metabolism without target context", "mTOR-only signaling paper", "metabolism mentioned only in discussion", "metabolite study without an mTOR relation"],
        "outcome": "SEARCH_PLAN_REDESIGN_REQUIRED",
    },
}


TRIAGE = {
    "spv2_003": {"therapy resistance": "A", "drug sensitivity": "B", "role": "C"},
    "spv2_004": {"therapy response": "A", "treatment outcome": "C", "modulates": "B"},
    "spv2_006": {"adaptive survival": "B", "cell survival": "B", "role": "C"},
    "spv2_008": {"therapy response": "A", "treatment outcome": "C", "association": "A"},
    "spv2_013": {"cell survival": "B", "promotes": "B", "survival of tumor cells/tumor": "D"},
    "spv2_019": {"metabolic": "A", "metabolic regulation": "B", "role": "C"},
}
TRIAGE_LABELS = {"A": "safe_search_lexical_candidate", "B": "useful_but_requires_manual_authorization",
                 "C": "too_ambiguous_for_default_use", "D": "scientifically_incorrect_or_misleading"}


ADDITIONS = {
    ("spv2_003", "A"): [("\"EMT\" AND \"drug resistance\"", "EMT", "scientific_authorized_alias", "Captures the locally authorized abbreviation.", "May retrieve developmental EMT; resistance and cancer screening remain required.")],
    ("spv2_003", "D"): [("\"epithelial-mesenchymal transition\" AND \"loss of sensitivity\"", "loss of sensitivity", "measurement_recall_only", "Captures inverse sensitivity framing.", "Can retrieve sensitivity changes that are not resistance.")],
    ("spv2_004", "B"): [("\"ferroptosis\" AND \"treatment efficacy\"", "treatment efficacy", "planning_only_unverified_expansion", "Adds efficacy wording for review.", "Efficacy may not be a response endpoint or may concern toxicity.")],
    ("spv2_004", "D"): [("\"ferroptosis\" AND \"drug sensitivity\" AND \"cancer\"", "drug sensitivity", "measurement_recall_only", "Captures preclinical sensitivity framing.", "May overrepresent viability assays.")],
    ("spv2_006", "B"): [("\"ferroptosis\" AND \"cell viability\" AND \"adaptation\"", "cell viability", "planning_only_unverified_expansion", "Tests a possible cellular readout while retaining adaptation.", "Viability may be baseline or cytotoxicity rather than adaptation.")],
    ("spv2_006", "D"): [("\"ferroptosis\" AND \"persistent cells\"", "persistent cells", "planning_only_unverified_expansion", "Adds persistence wording for adjudication.", "Persistence may not represent survival adaptation.")],
    ("spv2_008", "A"): [("\"hypoxic response\" AND \"cancer therapy response\"", "hypoxic response", "planning_only_unverified_expansion", "Captures alternate hypoxia wording.", "Hypoxic response may not establish hypoxia signaling.")],
    ("spv2_008", "D"): [("\"hypoxia signaling\" AND \"drug sensitivity\"", "drug sensitivity", "measurement_recall_only", "Captures sensitivity-scale studies.", "May omit clinical response and therapy identity.")],
    ("spv2_013", "B"): [("\"NF-kappaB\" AND \"cancer cell viability\"", "cancer cell viability", "planning_only_unverified_expansion", "Tests the likely cellular survival sense.", "Viability does not necessarily establish causal survival contribution.")],
    ("spv2_013", "D"): [("\"NF-kappaB\" AND \"tumor persistence\"", "tumor persistence", "planning_only_unverified_expansion", "Separates persistence from viability.", "Persistence may refer to residual disease or organism-level tumor burden.")],
    ("spv2_019", "B"): [("\"mTOR\" AND \"metabolic flux\"", "metabolic flux", "measurement_recall_only", "Adds an explicit measurement-property surface.", "Flux is one metabolic property and cannot define the proposition.")],
    ("spv2_019", "D"): [("\"mTOR\" AND \"metabolite abundance\"", "metabolite abundance", "measurement_recall_only", "Separates abundance measurements from flux.", "May retrieve metabolomics with no mechanistic mTOR relation.")],
}


RELATION_REPLACEMENTS = {
    "spv2_003": "\"epithelial-mesenchymal transition\" AND \"drug resistance\" AND \"associated with\"",
    "spv2_004": "\"ferroptosis\" AND \"cancer therapy response\" AND \"involved in\"",
    "spv2_006": "\"ferroptosis\" AND \"survival adaptation\" AND \"involved in\"",
    "spv2_008": "\"hypoxia signaling\" AND \"cancer therapy response\" AND \"associated with\"",
    "spv2_013": "\"NF-kappaB\" AND \"tumor survival\" AND \"contributes to\"",
    "spv2_019": "\"mTOR\" AND \"metabolism\" AND \"involved in\"",
}


LEXICAL = [
    ("therapy_response", "therapy response", "endpoint_wording", "six-case v2 term audit", True, False, "Search-only response-family surface; therapy and endpoint identity remain unresolved."),
    ("drug_resistance", "therapy resistance", "endpoint_wording", "spv2_003 triage A", True, False, "May broaden drug to therapy; never establishes a specific agent or resistance definition."),
    ("survival", "cell survival", "endpoint_wording", "spv2_006/spv2_013 triage B", False, False, "Manual authorization required because the frozen survival unit is unresolved."),
    ("viability", "cell viability", "measurement_wording", "recurring v2 measurement concept", False, False, "Candidate only; viability is not automatically survival or adaptation."),
    ("association", "association", "relation_wording", "spv2_008 triage A", True, False, "Permitted for search recall, not relation equivalence."),
    ("metabolism", "metabolic", "lexical_morphology", "spv2_019 triage A", True, False, "Morphological search variant; no pathway/property equivalence."),
    ("activity", "activity", "measurement_property", "wider v2 recurring term audit", True, False, "Requires entity-specific downstream interpretation."),
    ("activation", "activation", "relation_or_measurement", "wider v2 recurring term audit", True, False, "Could mean phosphorylation, activity, expression, or causal activation."),
    ("expression", "expression", "measurement_property", "wider v2 recurring term audit", True, False, "Does not distinguish RNA, protein, abundance, or cell compartment."),
    ("prognosis", "prognosis", "endpoint_context", "wider v2 contaminant audit", True, False, "Useful to detect prognostic literature; never authorizes a survival endpoint."),
    ("response", "response", "endpoint_wording", "wider v2 recurring term audit", True, False, "Must be disambiguated as clinical, cellular, molecular, or treatment efficacy."),
    ("mammalian_target_of_rapamycin", "MTOR", "entity_surface", "local pilot fixture only", False, False, "Fixture evidence is insufficient for production scientific alias authority."),
]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))


def mapped_authority(annotation, case_id):
    old = annotation["authority_class"]
    if old == "required_search_anchor": return "required_search_anchor"
    if old == "authorized_alias": return "scientific_authorized_alias"
    term = annotation["term"]
    if annotation.get("planning_only_unverified_expansion"):
        return "search_lexical_authorized" if TRIAGE[case_id].get(term) == "A" else "planning_only_unverified_expansion"
    return {"context_expansion_only": "context_recall_only", "measurement_expansion_only": "measurement_recall_only",
            "relation_expansion_only": "relation_recall_only", "recall_expansion_only": "planning_only_unverified_expansion"}.get(old, "planning_only_unverified_expansion")


def variant_review(plans):
    rows = []
    for plan in plans:
        cid = plan["case_id"]
        for family in plan["query_families"]:
            code = family["family_code"]
            existing = []
            for query in family["queries"]:
                existing.append({"query_text": query["query_string"], "authority_classifications": [mapped_authority(x, cid) for x in query["term_annotations"]], "disposition": "remove" if code == "G" else ("replace" if code == "C" else "retain")})
            proposed = []
            if code == "C":
                proposed.append({"query_text": RELATION_REPLACEMENTS[cid], "added_lexical_surface": RELATION_REPLACEMENTS[cid].split(" AND ")[-1].strip('"'), "authority_class": "relation_recall_only", "expected_recall_benefit": "Uses natural-language relation morphology instead of underscore serialization.", "expected_contamination_risk": "Relation phrase may be used non-causally.", "activation_state": "proposed_not_activated"})
            for text, surface, authority, benefit, risk in ADDITIONS.get((cid, code), []):
                proposed.append({"query_text": text, "added_lexical_surface": surface, "authority_class": authority, "expected_recall_benefit": benefit, "expected_contamination_risk": risk, "activation_state": "proposed_not_activated"})
            if code == "G": action = "remove"
            elif code == "C" or proposed: action = "split_into_variants"
            elif code == "B" and any(TRIAGE[cid].get(x["term"]) in {"B", "C", "D"} for q in family["queries"] for x in q["term_annotations"]): action = "manual_authorization_required"
            else: action = "retain_as_is"
            rows.append({"case_id": cid, "query_family_id": family["query_family_id"], "family_code": code,
                         "architecture": family["architecture"], "recommended_action": action,
                         "existing_variants": existing, "proposed_new_or_replacement_variants": proposed,
                         "variant_authority_invariant": "Search authorization never establishes scientific equivalence."})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_plans = load_jsonl(SOURCE_RUN / "search_plan_v2_candidates.jsonl")
    all_terms = load_jsonl(SOURCE_RUN / "term_authority_audit.jsonl")
    by_id = {x["case_id"]: x for x in all_plans}
    plans = [by_id[x] for x in CASE_IDS]
    if len(plans) != 6 or set(REVIEW) != set(CASE_IDS): raise ValueError("Frozen six-case set mismatch")
    terms_by_case = {cid: [x for x in all_terms if x["case_id"] == cid] for cid in CASE_IDS}

    inventory, packets, measurement_rows, therapy_rows, comparator_rows = [], [], [], [], []
    recall_rows, precision_rows, tier_rows, questions, outcomes = [], [], [], [], []
    triage_rows = []
    for plan in plans:
        cid, review = plan["case_id"], REVIEW[plan["case_id"]]
        unique_terms = {(x["term"], x["authority_class"], x.get("planning_only_unverified_expansion", False)) for x in terms_by_case[cid]}
        required = sorted({t for t, cls, _ in unique_terms if cls == "required_search_anchor"})
        aliases = sorted({t for t, cls, _ in unique_terms if cls == "authorized_alias"})
        unverified = sorted({t for t, _, flag in unique_terms if flag})
        inventory.append({"case_id": cid, "source_plan_ref": f"runs/20260906_search_plan_v2_multicase_stress_test_offline/search_plan_v2_candidates.jsonl#case_id={cid}", "target_proposition_ref": plan["target_proposition_ref"], "target_summary": plan["target_summary"], "frozen_target_proposition": plan["frozen_retrieval_target"], "selection_reason": "one_of_six_frozen_high_priority_ambiguity_cases", "source_plan_sha256": hashlib.sha256((SOURCE_RUN / "search_plan_v2_candidates.jsonl").read_bytes()).hexdigest()})
        negative_filters = [
            {"term": review["false_positive"][0], "classification": "not_recommended", "activated": False, "rationale": "A contaminant class is not necessarily a lexically safe NOT filter."},
            {"term": "review", "classification": "unsafe_negative_filter", "activated": False, "rationale": "The word can occur in valid primary-publication metadata or titles; filter publication type downstream."},
        ]
        packets.append({
            "artifact_schema_version": "high_ambiguity_manual_review_packet.v1", "case_id": cid,
            "frozen_target_proposition": plan["frozen_retrieval_target"],
            "proposition_critical_fields": ["subject_entity", "relation_family", "object_target", "measurement_target", "measurement_property_endpoint", "evidence_causal_mode", "intervention_proposition", "contrast_role", "context_qualifiers"],
            "existing_query_families": [{"query_family_id": f["query_family_id"], "family_code": f["family_code"], "architecture": f["architecture"]} for f in plan["query_families"]],
            "existing_query_variants": [{"query_family_id": f["query_family_id"], "query_id": q["query_id"], "query_text": q["query_string"]} for f in plan["query_families"] for q in f["queries"]],
            "required_search_anchors": required, "authorized_aliases": aliases,
            "planning_only_expansions": unverified, "dangerous_ambiguities": [review["ambiguity"], *plan["dangerous_ambiguities"]],
            "likely_false_positive_publication_classes": review["false_positive"],
            "likely_false_negative_publication_classes": review["false_negative"],
            "current_abstract_gate": plan["abstract_gate"], "current_fulltext_gate": plan["fulltext_acquisition_gate"],
            "scientific_decisions_still_unresolved": review["unresolved"],
            "recommended_deterministic_revisions": review["revisions"],
            "questions_requiring_human_scientific_adjudication": review["questions"],
            "negative_filter_candidates": negative_filters, "review_outcome": review["outcome"],
        })
        measurement_rows.append({"case_id": cid, "measurement_target": plan["frozen_retrieval_target"]["measurement_target"], "measurement_property": plan["frozen_retrieval_target"]["measurement_property_endpoint"], "endpoint_family": plan["frozen_retrieval_target"]["object_target"], "assay_measurement_granularity": "unresolved", "retrieval_granularity": review["retrieval_granularity"], "scientific_proposition_granularity": review["scientific_granularity"], "broader_retrieval_terminology_acceptable": True, "broader_terms_authorize_equivalence": False})
        therapy_rows.append({"case_id": cid, **review["therapy"], "modality_merging_prohibited": True, "activation_state": "review_only"})
        comparator_rows.append({"case_id": cid, **review["comparator"], "comparator_resolution_required_at_metadata_search": False})
        recall_rows.append({"case_id": cid, "risks": [{"rank": "high" if i == 0 else "medium", "mechanism": x} for i, x in enumerate(review["false_negative"])], "controls": review["revisions"]})
        precision_rows.append({"case_id": cid, "risks": [{"rank": "high" if i < 2 else "medium", "mechanism": x} for i, x in enumerate(review["false_positive"])], "topic_similarity_is_insufficient": True})
        tier_rows.extend([
            {"case_id": cid, "state": "TIER_A_HIGH_CONFIDENCE_ACQUIRE", "deterministic_rule": review["tier_a"], "minimum_signal_groups": ["correct entity", "relevant endpoint/measurement family", "plausible relation/evidence mode"], "no_known_fatal_mismatch": True},
            {"case_id": cid, "state": "TIER_B_ACQUIRE_TO_RESOLVE", "deterministic_rule": review["tier_b"], "already_plausible": ["correct entity", "target endpoint/measurement family", "scientific relation"], "fulltext_must_resolve": review["unresolved"], "vague_topic_similarity_allowed": False},
            {"case_id": cid, "state": "REJECT_KNOWN_MISMATCH", "deterministic_rule": "Reject when available evidence establishes any listed material mismatch.", "known_mismatch_reasons": review["reject"]},
        ])
        for number, q in enumerate(review["questions"], 1):
            questions.append({"question_id": f"{cid}_q{number}", "case_id": cid, "question": q, "decision_scope": review["unresolved"], "answer_status": "unresolved_requires_human_scientific_adjudication", "bounded": True})
        outcomes.append({"case_id": cid, "outcome": review["outcome"], "rationale": review["ambiguity"], "automatic_pass_prohibited": True, "next_step": "human scientific decision" if review["outcome"] == "SCIENTIFIC_REVIEW_REQUIRED" else "redesign frozen measurement/endpoint scope"})
        for term in unverified:
            letter = TRIAGE[cid][term]
            triage_rows.append({"case_id": cid, "term": term, "triage_class": letter, "triage_label": TRIAGE_LABELS[letter], "search_use_allowed_candidate": letter == "A", "scientific_equivalence_authorized": False, "manual_authorization_required": letter == "B", "default_query_use_allowed": letter == "A", "rationale": {"A": "Useful target-linked search surface when screened with the required anchor; scientific normalization remains separate.", "B": "Potentially useful but changes endpoint, relation, or scale and needs a bounded scientific decision.", "C": "Generic wording has excessive topic-only contamination risk.", "D": "The combined surface collapses unresolved scientific units and should not be used."}[letter]})

    family_review = variant_review(plans)
    before_count = sum(len(x["existing_variants"]) for x in family_review)
    after_count = sum(sum(v["disposition"] == "retain" for v in x["existing_variants"]) + len(x["proposed_new_or_replacement_variants"]) for x in family_review)
    lexical_rows = [{"artifact_schema_version": "SearchLexicalEntryV1", "lexical_entry_id": f"sle_{i:03d}", "canonical_search_concept": c, "surface": s, "surface_type": st, "scope": "search_plan_v21_candidate_only", "source_of_authority": src, "search_use_allowed": use, "scientific_equivalence_authorized": eq, "notes": note, "activation_state": "PROPOSED_NOT_ACTIVATED"} for i, (c, s, st, src, use, eq, note) in enumerate(LEXICAL, 1)]
    recurring = [
        {"concept": "survival", "needs": ["search lexical variants", "endpoint-level disambiguation", "measurement-level disambiguation"]},
        {"concept": "response", "needs": ["search lexical variants", "endpoint-level disambiguation", "therapy disambiguation"]},
        {"concept": "resistance", "needs": ["search lexical variants", "endpoint-level disambiguation", "therapy disambiguation", "evidence-mode disambiguation"]},
        {"concept": "expression", "needs": ["measurement-level disambiguation"]},
        {"concept": "activity/activation", "needs": ["measurement-level disambiguation", "evidence-mode disambiguation"]},
        {"concept": "metabolism", "needs": ["search lexical variants", "endpoint-level disambiguation", "measurement-level disambiguation"]},
        {"concept": "therapy", "needs": ["therapy disambiguation", "endpoint-level disambiguation"]},
        {"concept": "prognosis", "needs": ["endpoint-level disambiguation", "evidence-mode disambiguation"]},
        {"concept": "viability", "needs": ["measurement-level disambiguation", "endpoint-level disambiguation"]},
    ]
    candidate_rules = {
        "artifact_schema_version": "search_plan_v21_candidate_rules.v1", "status": "PROPOSED",
        "activation_state": "NOT_ACTIVATED", "calibration_state": "PENDING_RETRIEVAL_CALIBRATION",
        "rules": [
            {"rule_id": "SP21-R01", "category": "query_family_variant_separation", "rule": "A QueryFamily expresses a retrieval purpose; QueryVariants express justified lexical realizations within it. Variant count may be zero or greater and must not be mechanically multiplied."},
            {"rule_id": "SP21-R02", "category": "lexical_authority_boundary", "rule": "search_use_allowed does not imply scientific_equivalence_authorized; every surface records both values independently."},
            {"rule_id": "SP21-R03", "category": "expansion_authority", "rule": "A search expansion cannot mutate frozen entity, relation, endpoint, measurement, therapy, comparator, or context authority."},
            {"rule_id": "SP21-R04", "category": "fulltext_acquisition_tiering", "rule": "Every candidate receives exactly one of Tier A acquire, Tier B acquire-to-resolve, or Reject known mismatch; Tier B names both plausible components and fields requiring fulltext."},
            {"rule_id": "SP21-R05", "category": "endpoint_ambiguity", "rule": "Generic response, survival, resistance, and metabolism surfaces retain explicit endpoint and scale ambiguity until downstream adjudication."},
            {"rule_id": "SP21-R06", "category": "measurement_granularity", "rule": "Retrieval granularity may be broader than scientific proposition granularity, and the two values must be stored separately."},
            {"rule_id": "SP21-R07", "category": "therapy_identity", "rule": "Therapy modality/class/agent variants remain distinct unless frozen authority permits merging; generic therapy wording is recall-only."},
            {"rule_id": "SP21-R08", "category": "comparator_uncertainty", "rule": "Comparator absence need not block metadata retrieval, but acquisition requires either sufficient comparative plausibility or a named Tier B comparator-resolution reason."},
            {"rule_id": "SP21-R09", "category": "negative_filters", "rule": "Negative-filter candidates are never activated automatically and must be classified safe, unsafe, or not recommended."},
        ],
        "recurring_lexical_concept_requirements": recurring,
        "case_specific_production_rules": False,
    }
    calibration = {
        "artifact_schema_version": "future_retrieval_calibration_case_selection.v1", "execution_status": "not_executed",
        "selection_purpose": "Evaluate search and acquisition-gate behavior, not conflict likelihood.",
        "cases": [
            {"case_id": "spv2_017", "ambiguity_level": "low", "target": "PI3K activates AKT", "coverage_role": "molecular-relation control"},
            {"case_id": "spv2_026", "ambiguity_level": "low", "target": "p53 signaling involved in apoptosis", "coverage_role": "defined-process control"},
            {"case_id": "spv2_001", "ambiguity_level": "medium", "target": "EMT involved in metastasis", "coverage_role": "phenotype wording and assay-scale control"},
            {"case_id": "spv2_016", "ambiguity_level": "medium", "target": "tumor microenvironment modulates PD-L1 expression", "coverage_role": "expression/measurement disambiguation"},
            {"case_id": "spv2_003", "ambiguity_level": "high", "target": "EMT involved in drug resistance", "coverage_role": "therapy-resistance identity boundary"},
            {"case_id": "spv2_006", "ambiguity_level": "high", "target": "ferroptosis involved in survival adaptation", "coverage_role": "survival-unit boundary"},
            {"case_id": "spv2_013", "ambiguity_level": "high", "target": "NF-kappaB contributes to tumor survival", "coverage_role": "causal mode and survival scale"},
            {"case_id": "spv2_019", "ambiguity_level": "high", "target": "mTOR involved in metabolism", "coverage_role": "measurement-property breadth"},
        ],
    }
    metric_names = ["retrieved_unique_publications", "metadata_plausible", "abstract_high_plausibility", "abstract_possible", "tier_a_acquisition_candidates", "tier_b_acquisition_candidates", "fulltexts_acquired", "manual_relevant_fulltexts", "manual_irrelevant_fulltexts", "query_family_unique_relevant_contribution", "query_variant_unique_relevant_contribution", "known_mismatch_rejection_count", "fulltext_required_to_resolve_count", "retrieval_saturation_curve"]
    metrics_contract = {"artifact_schema_version": "future_retrieval_metrics_contract.v1", "execution_status": "not_executed", "metrics": [{"name": n, "value": None, "population_status": "future_calibration_only"} for n in metric_names], "empirical_precision_recall_claims": False}
    relevance_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "RetrievalRelevanceAdjudicationV1", "title": "RetrievalRelevanceAdjudicationV1", "type": "object", "additionalProperties": False,
        "required": ["publication_id", "case_id", "reviewer_decision", "relevance_state", "matched_target_components", "mismatched_components", "fulltext_acquisition_was_justified", "contaminant_class", "notes"],
        "properties": {"publication_id": {"type": "string", "minLength": 1}, "case_id": {"type": "string", "minLength": 1}, "reviewer_decision": {"type": "string", "enum": ["relevant", "irrelevant", "uncertain"]}, "relevance_state": {"type": "string", "enum": ["directly_relevant", "plausibly_relevant_fulltext_required", "related_but_wrong_proposition", "wrong_endpoint", "wrong_entity", "wrong_evidence_mode", "wrong_therapy", "topic_only", "insufficient_metadata"]}, "matched_target_components": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}, "mismatched_components": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}, "fulltext_acquisition_was_justified": {"type": ["boolean", "null"]}, "contaminant_class": {"type": ["string", "null"]}, "notes": {"type": "string"}, "audit_scope": {"const": "retrieval_relevance_only_not_downstream_conflict_gold"}},
    }
    triage_counts = Counter(x["triage_class"] for x in triage_rows)
    outcome_counts = Counter(x["outcome"] for x in outcomes)
    aggregate = {
        "review_case_count": 6, "query_family_count": len(family_review), "query_variant_count_before": before_count,
        "query_variant_count_proposed_after": after_count, "planning_only_expansions_reviewed": len(triage_rows),
        "safe_search_lexical_candidates": triage_counts["A"], "manual_authorization_expansions": triage_counts["B"],
        "too_ambiguous_expansions": triage_counts["C"], "incorrect_expansions": triage_counts["D"],
        "tier_a_rule_count": sum(x["state"] == "TIER_A_HIGH_CONFIDENCE_ACQUIRE" for x in tier_rows),
        "tier_b_rule_count": sum(x["state"] == "TIER_B_ACQUIRE_TO_RESOLVE" for x in tier_rows),
        "reject_rule_count": sum(x["state"] == "REJECT_KNOWN_MISMATCH" for x in tier_rows),
        "bounded_scientific_review_question_count": len(questions),
        "cases_ready_for_retrieval_calibration": outcome_counts["READY_FOR_RETRIEVAL_CALIBRATION"],
        "cases_ready_after_minor_authorization": outcome_counts["READY_AFTER_MINOR_LEXICAL_AUTHORIZATION"],
        "cases_scientific_review_required": outcome_counts["SCIENTIFIC_REVIEW_REQUIRED"],
        "cases_search_plan_redesign_required": outcome_counts["SEARCH_PLAN_REDESIGN_REQUIRED"],
        "search_lexical_registry_candidate_count": len(lexical_rows), "future_calibration_case_count": len(calibration["cases"]),
    }
    safety = {"artifact_schema_version": "scientific_state_safety_audit.v1", "run_id": RUN_ID, "offline_only": True,
              "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "searches_executed": 0,
              "historical_scientific_assets_modified": False, "production_behavior_modified": False,
              "candidate_activation_state": "PROPOSED_NOT_ACTIVATED_PENDING_RETRIEVAL_CALIBRATION", "git_commit_created": False,
              "source_run_read_only": str(SOURCE_RUN.relative_to(ROOT)), "new_artifact_scope": str(OUT.relative_to(ROOT))}
    summary = {"artifact_schema_version": "search_plan_v21_review_summary.v1", "run_id": RUN_ID,
               "activation_state": "proposed_not_activated", **aggregate, "network_calls": 0, "provider_calls": 0,
               "llm_calls": 0, "downloads": 0, "historical_assets_modified": False, "empirical_precision_recall_claims": False}
    outputs = {
        "review_case_inventory.jsonl": inventory, "high_ambiguity_manual_review_packets.jsonl": packets,
        "query_family_variant_review.jsonl": family_review, "unverified_expansion_triage.jsonl": triage_rows,
        "measurement_granularity_review.jsonl": measurement_rows, "therapy_identity_review.jsonl": therapy_rows,
        "comparator_contrast_review.jsonl": comparator_rows, "recall_risk_audit.jsonl": recall_rows,
        "precision_risk_audit.jsonl": precision_rows, "fulltext_acquisition_tier_rules.jsonl": tier_rows,
        "search_lexical_registry_candidates.jsonl": lexical_rows, "search_plan_v21_candidate_rules.json": candidate_rules,
        "bounded_scientific_review_questions.jsonl": questions, "per_case_review_outcomes.jsonl": outcomes,
        "future_retrieval_calibration_case_selection.json": calibration, "future_retrieval_metrics_contract.json": metrics_contract,
        "retrieval_relevance_adjudication_v1.schema.json": relevance_schema,
        "scientific_state_safety_audit.json": safety, "summary.json": summary,
    }
    for name, value in outputs.items(): (write_jsonl if name.endswith(".jsonl") else write_json)(OUT / name, value)
    checks = {
        "exact_frozen_case_set": {x["case_id"] for x in inventory} == set(CASE_IDS),
        "query_family_variant_separate": all("existing_variants" in x and "query_family_id" in x for x in family_review),
        "lexical_authority_independent": all(not x["scientific_equivalence_authorized"] for x in lexical_rows),
        "three_acquisition_states_per_case": all({x["state"] for x in tier_rows if x["case_id"] == cid} == {"TIER_A_HIGH_CONFIDENCE_ACQUIRE", "TIER_B_ACQUIRE_TO_RESOLVE", "REJECT_KNOWN_MISMATCH"} for cid in CASE_IDS),
        "tier_b_resolution_explicit": all(x.get("fulltext_must_resolve") for x in tier_rows if x["state"] == "TIER_B_ACQUIRE_TO_RESOLVE"),
        "expansions_do_not_modify_authority": all(not x["scientific_equivalence_authorized"] for x in triage_rows),
        "generic_response_not_equivalent": "response" in {x["canonical_search_concept"] for x in lexical_rows} and all(not x["scientific_equivalence_authorized"] for x in lexical_rows if x["canonical_search_concept"] == "response"),
        "generic_survival_not_equivalent": all(not x["scientific_equivalence_authorized"] for x in lexical_rows if x["canonical_search_concept"] == "survival"),
        "generic_resistance_not_equivalent": all(not x["scientific_equivalence_authorized"] for x in lexical_rows if x["canonical_search_concept"] == "drug_resistance"),
        "measurement_scale_visible": all(x["retrieval_granularity"] != x["scientific_proposition_granularity"] for x in measurement_rows),
        "therapy_identity_visible": all("identity_status" in x for x in therapy_rows),
        "no_case_specific_production_rules": not candidate_rules["case_specific_production_rules"] and all(not any(term in x["rule"] for term in ["TRIB3", "EMT", "ferroptosis", "hypoxia", "NF-kappaB", "mTOR"]) for x in candidate_rules["rules"]),
        "offline_counters_zero": all(safety[k] == 0 for k in ["network_calls", "provider_calls", "llm_calls", "downloads", "searches_executed"]),
        "historical_state_unchanged": not safety["historical_scientific_assets_modified"],
        "not_activated": candidate_rules["status"] == "PROPOSED" and candidate_rules["activation_state"] == "NOT_ACTIVATED",
        "aggregate_counts_consistent": len(triage_rows) == sum(triage_counts.values()) and len(outcomes) == sum(outcome_counts.values()),
    }
    validation = {"artifact_schema_version": "search_plan_v21_final_validation.v1", "run_id": RUN_ID,
                  "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "aggregate_metrics": aggregate}
    write_json(OUT / "final_validation.json", validation)
    files = []
    for path in sorted(OUT.iterdir()):
        if path.name == "manifest.json": continue
        files.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
                      "record_count": sum(1 for x in path.read_text().splitlines() if x.strip()) if path.suffix == ".jsonl" else 1})
    manifest = {"artifact_schema_version": "search_plan_v21_run_manifest.v1", "run_id": RUN_ID,
                "created_at": CREATED_AT, "mode": "offline_candidate_review_only", "generator": str(Path(__file__).relative_to(ROOT)),
                "required_artifact_count": 21, "files": files, "network_calls": 0, "provider_calls": 0,
                "llm_calls": 0, "downloads": 0, "historical_assets_modified": False}
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"run": str(OUT.relative_to(ROOT)), "validation": validation["status"], **aggregate}, indent=2))


if __name__ == "__main__":
    main()
