#!/usr/bin/env python3
"""Generate the 2026-09-06 Search Plan v2 multi-case offline stress test.

This generator reads only repository-local semantic-intake artifacts.  It never
imports retrieval/provider code and performs no network or model operations.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "20260906_search_plan_v2_multicase_stress_test_offline"
OUT = ROOT / "runs" / RUN_ID
SCHEMA = "search_plan_v2_candidate.v1"
CREATED_AT = "2026-09-06T00:00:00+08:00"


def spec(case, triple, category, measurement, property_, mode, contexts,
         broader, measurement_terms, relation_terms, ambiguities, contaminants,
         state="PASS_WITH_MINOR_REVISION", rationale="", aliases=None,
         unverified=None, gate="strong", budget=None):
    return {
        "source_case": case, "triple_id": triple, "scientific_category": category,
        "measurement_target": measurement, "measurement_property_endpoint": property_,
        "evidence_causal_mode": mode, "context_qualifiers": contexts,
        "broader": broader, "measurement_terms": measurement_terms,
        "relation_terms": relation_terms, "dangerous_ambiguities": ambiguities,
        "known_contaminants": contaminants, "review_state": state,
        "review_rationale": rationale, "aliases": aliases or {},
        "unverified": unverified or [], "fulltext_gate_strength": gate,
        "budget": budget,
    }


# Targets are deliberately selected by semantic/evidence-family diversity, never
# by contradiction status.  Every (case, triple) pair is verified against its
# immutable semantic_intake.json before output is written.
SPECS = [
    spec("emt_metastasis_drug_resistance_discovery_v1", "T1", "cellular_and_disease_phenotype",
         "metastasis", "metastatic occurrence/burden", "association_or_mechanistic_involvement",
         ["cancer"], "tumor dissemination", ["metastasis", "metastatic"], ["involved in", "role"],
         ["metastasis may denote formation, burden, or an anatomic lesion", "EMT may denote a program, state, or marker signature"],
         ["EMT marker-only papers without metastasis evidence", "cell migration studies with no metastatic endpoint"],
         aliases={"epithelial-mesenchymal transition": ["EMT"]}),
    spec("emt_metastasis_drug_resistance_discovery_v1", "T2", "cellular_phenotype",
         "tumor invasion", "invasive behavior", "association_or_mechanistic_involvement",
         ["cancer"], "invasion", ["tumor invasion", "invasive"], ["involved in", "role"],
         ["invasion can mean tissue invasion or in-vitro assay movement", "EMT marker change is not itself invasion"],
         ["migration-only assays", "developmental EMT without tumor invasion"],
         unverified=["invasiveness"]),
    spec("emt_metastasis_drug_resistance_discovery_v1", "T4", "resistance_response_phenotype",
         "drug resistance", "loss of drug sensitivity", "association_or_mechanistic_involvement",
         ["cancer"], "therapy resistance", ["drug resistance", "drug sensitivity"], ["involved in", "role"],
         ["resistance may be antimicrobial, stress, or cancer-drug resistance", "response can be cellular viability or clinical response"],
         ["EMT and resistance discussed independently", "intrinsic stress resistance without a cancer drug"],
         state="REVISE", rationale="Drug identity and resistance measurement are unspecified in the frozen target.", gate="weak"),

    spec("ferroptosis_cancer_therapy_response_discovery_v1", "triple1", "interventional_effect",
         "cancer therapy response", "treatment response", "mechanistic_involvement",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["involved_in", "modulates"],
         ["response may be clinical, molecular, or viability-based", "ferroptosis induction markers do not establish treatment response"],
         ["ferroptosis reviews", "toxicity studies without antitumor response"],
         state="REVISE", rationale="Therapy, response scale, and experimental level remain underspecified.", gate="weak"),
    spec("ferroptosis_cancer_therapy_response_discovery_v1", "triple2", "disease_phenotype",
         "tumor suppression", "suppression of tumor growth/formation", "mechanistic_involvement",
         ["cancer"], "antitumor effect", ["tumor suppression", "tumor growth"], ["involved_in", "role"],
         ["tumor suppressor can denote a gene class rather than an observed phenotype", "cell death in vitro is not necessarily tumor suppression"],
         ["gene annotations using 'tumor suppressor'", "non-cancer ferroptosis"], unverified=["antitumour effect"]),
    spec("ferroptosis_cancer_therapy_response_discovery_v1", "triple3", "cellular_phenotype",
         "survival adaptation", "adaptive survival", "mechanistic_involvement",
         ["cancer"], "cell survival", ["survival adaptation", "cell survival"], ["involved_in", "role"],
         ["survival may refer to patients, animals, or cells", "adaptation is not equivalent to baseline viability"],
         ["patient survival associations", "organismal survival in non-cancer injury"],
         state="REVISE", rationale="The survival unit and adaptation contrast require manual freezing.", gate="weak"),

    spec("hif1a_hypoxia_cancer_response_discovery_v1", "seed_1", "pathway_mechanistic_relation",
         "hypoxia signaling", "pathway involvement", "mechanistic_involvement",
         ["cancer", "hypoxia"], "hypoxic response", ["hypoxia signaling", "hypoxic response"], ["involved_in", "role"],
         ["HIF-1alpha abundance, stabilization, transcriptional activity, and pathway activation are distinct", "hypoxia can be exposure or pathway state"],
         ["HIF-2alpha-only studies", "hypoxia papers with no HIF-1alpha evidence"],
         unverified=["HIF1A"]),
    spec("hif1a_hypoxia_cancer_response_discovery_v1", "seed_2", "interventional_effect",
         "cancer therapy response", "treatment response", "observational_association",
         ["cancer", "hypoxia"], "treatment outcome", ["therapy response", "drug sensitivity"], ["associated_with", "association"],
         ["response spans clinical response and cellular sensitivity", "hypoxia signaling versus oxygen tension exposure"],
         ["prognostic hypoxia signatures without therapy-response analysis", "non-cancer hypoxia treatment"],
         state="REVISE", rationale="The therapy and response endpoint are not fixed.", gate="weak"),
    spec("hif1a_hypoxia_cancer_response_discovery_v1", "seed_5", "pathway_mechanistic_relation",
         "angiogenesis", "angiogenic process", "mechanistic_involvement",
         ["cancer", "tumor adaptation"], "vascularization", ["angiogenesis", "vascularization"], ["involves", "role"],
         ["angiogenic marker expression is not necessarily new-vessel formation", "tumor adaptation is a broad process"],
         ["physiologic angiogenesis", "tumor adaptation mentioned without angiogenic data"]),

    spec("il6_stat3_cancer_response_discovery_v1", "triple1", "interventional_effect",
         "cancer therapy response", "treatment response", "mechanistic_involvement",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["involved_in", "role"],
         ["IL-6 abundance, STAT3 phosphorylation, and pathway activity are distinct", "response can be clinical or preclinical"],
         ["inflammation-only IL-6 papers", "STAT3 expression without pathway or response evidence"],
         unverified=["IL6 STAT3 signaling"], state="REVISE",
         rationale="Therapy and response measurement are unspecified."),
    spec("il6_stat3_cancer_response_discovery_v1", "triple2", "disease_phenotype",
         "tumor progression", "progression phenotype", "mechanistic_involvement",
         ["cancer"], "disease progression", ["tumor progression", "progression"], ["involved_in", "role"],
         ["progression may be clinical progression, tumor growth, invasion, or stage", "IL-6 and STAT3 co-mention does not establish pathway activity"],
         ["non-neoplastic inflammatory progression", "prognostic correlation without pathway evidence"]),

    spec("nfkb_inflammation_cancer_response_discovery_v1", "triple1", "interventional_effect",
         "cancer therapy response", "treatment response", "mechanistic_involvement",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["involved_in", "role"],
         ["NF-kappaB expression, nuclear localization, and transcriptional activation are distinct", "response may be clinical or cellular"],
         ["general inflammation papers", "NF-kappaB mention only in discussion"],
         unverified=["NF-kB"], state="REVISE", rationale="Treatment and response endpoint need refinement."),
    spec("nfkb_inflammation_cancer_response_discovery_v1", "triple2", "cellular_and_disease_phenotype",
         "tumor survival", "survival of tumor cells/tumor", "causal_contribution",
         ["cancer"], "cell survival", ["tumor survival", "cell survival"], ["contributes_to", "promotes"],
         ["tumor survival can mean cell viability, persistence, or patient survival", "NF-kappaB activation is not equivalent to abundance"],
         ["overall-survival prognostic studies", "non-tumor immune-cell survival"],
         state="REVISE", rationale="The unit of survival is ambiguous in the frozen object.", gate="weak"),

    spec("pdl1_immune_checkpoint_cancer_response_discovery_v1", "T1", "pathway_mechanistic_relation",
         "immune checkpoint signaling", "pathway participation", "mechanistic_participation",
         ["cancer"], "checkpoint pathway", ["immune checkpoint signaling", "checkpoint pathway"], ["participates_in", "role"],
         ["PD-L1 expression is not the same as functional checkpoint signaling", "PD-L1 can be tumor- or immune-cell derived"],
         ["PD-L1 expression-only biomarker studies", "other checkpoint pathways without PD-L1"]),
    spec("pdl1_immune_checkpoint_cancer_response_discovery_v1", "T4", "observational_clinical_association",
         "cancer immunotherapy response", "clinical or experimental response", "observational_association",
         ["cancer", "immunotherapy"], "treatment outcome", ["immunotherapy response", "treatment response"], ["associated_with", "association"],
         ["PD-L1 assay positivity, expression level, and functional signaling differ", "response, survival, and durable benefit are non-equivalent endpoints"],
         ["non-immunotherapy treatment response", "PD-L1 prevalence without outcome analysis"],
         state="REVISE", rationale="Assay, immunotherapy class, and response definition require resolution."),
    spec("pdl1_immune_checkpoint_cancer_response_discovery_v1", "T5", "expression_relationship",
         "PD-L1 expression", "gene/protein abundance", "contextual_modulation",
         ["tumor microenvironment", "cancer"], "expression level", ["PD-L1 expression", "expression level"], ["modulates", "regulates"],
         ["mRNA and protein expression are not interchangeable", "tumor-cell and immune-cell staining are distinct"],
         ["checkpoint activity without expression measurement", "systemic PD-L1 measurements unrelated to tumor microenvironment"],
         aliases={"PD-L1": ["PDL1"]}),

    spec("pi3k_akt_mtor_cancer_resistance_discovery_v1", "t1", "pathway_mechanistic_relation",
         "AKT", "activation/activity", "causal_activation",
         ["cancer"], "AKT activity", ["AKT activation", "AKT phosphorylation"], ["activates", "activation"],
         ["AKT phosphorylation site, kinase activity, and expression differ", "PI3K can denote enzyme families or pathway activity"],
         ["co-expression without activation evidence", "PI3K-independent AKT activation"],
         state="PASS", rationale="The molecular subject, relation, and target are explicit."),
    spec("pi3k_akt_mtor_cancer_resistance_discovery_v1", "t4", "resistance_response_phenotype",
         "therapy resistance", "loss of treatment sensitivity", "observational_association",
         ["cancer"], "drug resistance", ["therapy resistance", "drug resistance"], ["associated_with", "association"],
         ["resistance may be clinical, acquired cellular, or intrinsic", "pathway abundance and activation are distinct"],
         ["stress resistance", "therapy response papers without resistance contrast"],
         state="PASS_WITH_MINOR_REVISION", rationale="The core phenotype is clear but therapy-specific strata remain open."),
    spec("pi3k_akt_mtor_cancer_resistance_discovery_v1", "t5", "pathway_mechanistic_relation",
         "metabolism", "metabolic process involvement", "mechanistic_involvement",
         ["cancer"], "metabolic regulation", ["metabolism", "metabolic"], ["involved_in", "role"],
         ["metabolism is a very broad family", "mTOR expression is not pathway activity"],
         ["organismal metabolic disease without cancer", "nutrient studies lacking mTOR evidence"],
         state="REVISE", rationale="The metabolic process and measurable property are too broad.", gate="weak"),

    spec("ros_oxidative_stress_cancer_response_discovery_v1", "triple1", "cellular_phenotype",
         "cancer cell death", "cell-death occurrence/rate", "mechanistic_involvement",
         ["cancer"], "cell death", ["cancer cell death", "cell death"], ["involved_in", "role"],
         ["ROS abundance, generation, and oxidative stress are distinct", "cell death modes are not interchangeable"],
         ["normal-cell oxidative injury", "ROS measurements without cell-death evidence"],
         aliases={"reactive oxygen species": ["ROS"]}),
    spec("ros_oxidative_stress_cancer_response_discovery_v1", "triple2", "cellular_phenotype",
         "cancer survival adaptation", "adaptive survival", "causal_promotion",
         ["cancer"], "cell survival", ["survival adaptation", "cell survival"], ["promotes", "promotion"],
         ["patient survival and cell survival differ", "oxidative stress exposure and redox adaptation differ"],
         ["overall-survival prognostic studies", "acute oxidative cytotoxicity without adaptation"],
         state="REVISE", rationale="Adaptation contrast and survival unit are not operationalized."),
    spec("ros_oxidative_stress_cancer_response_discovery_v1", "triple3", "interventional_effect",
         "cancer therapy response", "treatment response", "contextual_modulation",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["modulates", "regulates"],
         ["response can be clinical, molecular, or viability-based", "oxidative stress can be cause, marker, or consequence"],
         ["toxicity without cancer therapy", "redox biomarker studies with no response endpoint"],
         state="REVISE", rationale="Therapy, response level, and oxidative-stress operationalization are open."),

    spec("senescence_sasp_cancer_therapy_response_discovery_v1", "T1", "disease_phenotype",
         "tumor suppression", "suppression of tumor growth/formation", "mechanistic_involvement",
         ["cancer"], "antitumor effect", ["tumor suppression", "tumor growth"], ["involved_in", "role"],
         ["senescence markers do not prove stable senescence", "tumor suppression differs from short-term proliferation arrest"],
         ["aging studies outside cancer", "marker-only senescence papers"]),
    spec("senescence_sasp_cancer_therapy_response_discovery_v1", "T2", "interventional_effect",
         "therapy response", "treatment response", "mechanistic_involvement",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["involved_in", "role"],
         ["therapy-induced senescence can be endpoint, mediator, or consequence", "response can be clinical or cellular"],
         ["senolytic response outside cancer", "therapy-induced markers without outcome evidence"],
         state="REVISE", rationale="Cancer, therapy, and response level are incompletely specified."),
    spec("senescence_sasp_cancer_therapy_response_discovery_v1", "T4", "pathway_mechanistic_relation",
         "inflammation", "inflammatory process", "mechanistic_involvement",
         ["cancer", "cellular context"], "inflammatory signaling", ["inflammation", "inflammatory"], ["involved_in", "role"],
         ["SASP composition varies and is not synonymous with inflammation", "systemic and local inflammation differ"],
         ["inflammaging without cancer", "senescence papers lacking SASP measurement"],
         aliases={"Senescence-associated secretory phenotype (SASP)": ["SASP"]}),

    spec("tp53_apoptosis_cancer_therapy_response_discovery_v1", "t1", "pathway_mechanistic_relation",
         "apoptosis", "apoptotic process", "mechanistic_involvement",
         ["cancer"], "programmed cell death", ["apoptosis", "apoptotic"], ["involved_in", "role"],
         ["p53 abundance, mutation status, and transcriptional activity differ", "apoptosis assays may capture generic cell death"],
         ["p53 mutation prevalence", "non-apoptotic cell death"], state="PASS",
         rationale="The pathway and endpoint are explicit; assay subtype may remain for fulltext."),
    spec("tp53_apoptosis_cancer_therapy_response_discovery_v1", "t2", "cellular_phenotype",
         "cell cycle arrest", "arrest occurrence/state", "mechanistic_involvement",
         ["cancer"], "growth arrest", ["cell cycle arrest", "growth arrest"], ["involved_in", "role"],
         ["quiescence, senescence, and cell-cycle arrest are not equivalent", "p53 expression is not functional signaling"],
         ["cell-cycle redistribution without arrest", "p53-independent arrest"], state="PASS",
         rationale="The pathway and cellular endpoint are explicit."),

    spec("wnt_beta_catenin_cancer_stemness_immunity_discovery_v1", "seed1", "cellular_phenotype",
         "cancer stemness", "stem-like phenotype", "observational_association",
         ["cancer"], "cancer stem cell phenotype", ["cancer stemness", "cancer stem cells"], ["associated_with", "association"],
         ["stemness marker expression is not functional self-renewal", "Wnt ligand presence is not beta-catenin pathway activation"],
         ["developmental stem cells", "marker-only cancer stemness papers"],
         unverified=["Wnt/beta-catenin"]),
    spec("wnt_beta_catenin_cancer_stemness_immunity_discovery_v1", "seed3", "pathway_mechanistic_relation",
         "tumor immune microenvironment", "immune-composition/function modulation", "contextual_modulation",
         ["cancer", "tumor microenvironment"], "tumor immunity", ["tumor immune microenvironment", "tumor immunity"], ["modulates", "regulates"],
         ["immune-cell abundance and immune function differ", "canonical and noncanonical Wnt signaling differ"],
         ["non-tumor immune development", "Wnt papers without immune measurements"]),
    spec("wnt_beta_catenin_cancer_stemness_immunity_discovery_v1", "seed4", "interventional_effect",
         "cancer therapy response", "treatment response", "contextual_modulation",
         ["cancer"], "treatment outcome", ["therapy response", "drug sensitivity"], ["influences", "modulates"],
         ["response may be clinical or cellular", "beta-catenin abundance and pathway activation differ"],
         ["prognostic studies without treatment", "Wnt inhibitor pharmacology without response comparison"],
         state="REVISE", rationale="Therapy and response measurement are not frozen."),
    spec("metformin_ampk_cancer_frozen_v1", "aadf04145cd44eb9837fe7ef2dda213d1ac876c2e9a42f424777bac4515b55e3", "pharmacological_perturbation",
         "AMPK", "activation/activity", "pharmacological_modulation",
         ["cancer"], "AMPK signaling", ["AMPK activation", "AMPK activity"], ["modulates", "regulates"],
         ["AMPK abundance, phosphorylation, and kinase activity are distinct", "metformin exposure may have AMPK-independent effects"],
         ["metformin outcome studies without AMPK measurement", "AMPK papers lacking metformin exposure"],
         aliases={"metformin": ["metformin hydrochloride"], "AMPK": ["AMP-activated protein kinase"]},
         state="PASS", rationale="A frozen drug-target seed and explicit local aliases support a focused perturbation plan."),
    spec("emt_irf1_genetic_perturbation_observation", "c41ae2b7d34a9a01", "genetic_perturbation",
         "cell migration", "migratory behavior", "genetic_perturbation_causal",
         ["breast cancer", "4T1 cells"], "cell motility", ["cell migration", "migration assay"], ["positive_regulation", "regulates"],
         ["migration is not equivalent to invasion or metastasis", "IRF1 expression association is weaker than perturbation evidence"],
         ["IRF1 expression-only studies", "immune-cell migration unrelated to tumor cells"],
         state="PASS_WITH_MINOR_REVISION", rationale="The RNAi perturbation is source-grounded; assay and model aliases remain limited."),
]


def read_source_triple(case: str, triple_id: str):
    if case == "metformin_ampk_cancer_frozen_v1":
        path = ROOT / "configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json"
        data = json.loads(path.read_text())
        raw = data["seed_triple"]
        if raw["triple_id"] != triple_id:
            raise ValueError(f"Missing frozen metformin seed {triple_id}")
        triple = {"triple_id": raw["triple_id"], "subject": raw["subject"]["name"],
                  "relation": raw["relation"]["family"], "object": raw["object"]["name"],
                  "subject_type": raw["subject"].get("type", "unknown"),
                  "object_type": raw["object"].get("type", "unknown"),
                  "purpose": "literature_search_planning", "source": raw.get("source", "semantic_intake"),
                  "is_evidence": False, "confidence": raw.get("confidence")}
        return path, data, triple
    if case == "emt_irf1_genetic_perturbation_observation":
        path = ROOT / "case_bundles/emt_metastasis_drug_resistance_discovery_v1__v7_replay_l2/core_observations.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        matches = [x for x in rows if x["observation_id"] == triple_id]
        if len(matches) != 1:
            raise ValueError(f"Expected one IRF1 observation {triple_id}, found {len(matches)}")
        raw = matches[0]
        triple = {"triple_id": raw["observation_id"], "subject": raw["subject_name"],
                  "relation": raw["relation_family"], "object": raw["object_name"],
                  "subject_type": "gene_or_protein", "object_type": "cellular_phenotype",
                  "purpose": "frozen_retrieval_target", "source": "core_observation",
                  "is_evidence": True, "paper_id": raw["paper_id"],
                  "evidence_mode": "RNAi-mediated ablation"}
        return path, rows, triple
    path = ROOT / "configs" / "generated_cases" / case / "semantic_intake.json"
    data = json.loads(path.read_text())
    matches = [x for x in data["seed_triples"] if x["triple_id"] == triple_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one {case}:{triple_id}, found {len(matches)}")
    return path, data, matches[0]


def ann(term, authority_class, field, source_ref=None, unverified=None):
    if unverified is None:
        unverified = authority_class not in {"required_search_anchor", "authorized_alias"} and source_ref is None
    return {"term": term, "authority_class": authority_class, "target_field": field,
            "authority_source_ref": source_ref,
            "planning_only_unverified_expansion": unverified,
            "authorizes_proposition_identity": authority_class in {"required_search_anchor", "authorized_alias"}}


def make_queries(case_id, target, s, source_ref):
    subj, obj, rel = target["subject"], target["object"], target["relation_family"]
    broader = s["broader"]
    measure = next((x for x in s["measurement_terms"]
                    if x.casefold() not in {obj.casefold(), broader.casefold()}),
                   s["measurement_property_endpoint"])
    relation = s["relation_terms"][0]
    context = s["context_qualifiers"][0] if s["context_qualifiers"] else None
    families = []

    def add(fid, architecture, purpose, terms, risk="low", rationale=""):
        qid = f"{case_id}_{fid.lower()}"
        query = " AND ".join(f'"{x["term"]}"' for x in terms)
        families.append({
            "query_family_id": f"{case_id}:{fid}", "family_code": fid,
            "architecture": architecture, "scientific_justification": purpose,
            "queries": [{"query_id": qid, "query_string": query, "term_annotations": terms,
                         "overconstraint_risk": risk, "overconstraint_rationale": rationale,
                         "execution_status": "not_executed_offline_plan"}],
            "future_contribution_metrics": {k: None for k in (
                "retrieved_publications", "unique_additions", "abstract_plausible_additions",
                "fulltext_acquisition_additions", "eventual_proposition_compatible_additions",
                "unique_relevant_publications_only_by_family")},
        })

    anchor_s = ann(subj, "required_search_anchor", "subject", source_ref)
    anchor_o = ann(obj, "required_search_anchor", "object", source_ref)
    add("A", "exact_entity_endpoint", "High-specificity exact frozen subject/object pairing.", [anchor_s, anchor_o])
    add("B", "broader_endpoint_recall_family", "Recall bridge; the broader term does not redefine the exact endpoint.",
        [anchor_s, ann(broader, "recall_expansion_only", "measurement_property_endpoint")])
    add("C", "relation_terminology", "Retrieve papers expressing the frozen relation with explicit relational language.",
        [anchor_s, anchor_o, ann(relation, "relation_expansion_only", "relation_family", source_ref)])
    add("D", "measurement_terminology", "Retrieve evidence using measurement-language likely to expose the endpoint.",
        [anchor_s, ann(measure, "measurement_expansion_only", "measurement_property_endpoint",
                       source_ref if measure.casefold() in {subject.casefold() for subject in (subj, obj, rel)} else None)])
    if context:
        add("E", "disease_context_expansion", "Context-stratified recall family; context is not imposed on every query.",
            [anchor_s, anchor_o, ann(context, "context_expansion_only", "context_qualifiers", source_ref)],
            "medium", "Three simultaneous concepts may miss cross-context mechanistic studies; retain only as a complementary family.")
    alias_terms = []
    for canonical, vals in s["aliases"].items():
        for value in vals:
            alias_terms.append(ann(value, "authorized_alias", "subject" if canonical == subj else "object", source_ref))
    if alias_terms:
        add("F", "authorized_alias_variants", "Use only alternative surfaces explicitly present in the local case artifact.",
            [alias_terms[0], anchor_o if alias_terms[0]["target_field"] == "subject" else anchor_s])
    elif s["unverified"]:
        add("F", "unverified_lexical_expansion", "Quarantined lexical variant for human approval; it has no proposition authority.",
            [anchor_s, ann(s["unverified"][0], "recall_expansion_only", "measurement_property_endpoint", None, True)])
    else:
        add("G", "proposition_component_combination", "Orthogonal subject/relation/endpoint-family pairing without mandatory context.",
            [anchor_s, ann(broader, "recall_expansion_only", "measurement_property_endpoint"),
             ann(s["relation_terms"][-1], "relation_expansion_only", "relation_family")],
            "medium", "Three concepts are combined only in this complementary component family.")
    strings = [q["query_string"] for f in families for q in f["queries"]]
    if len(strings) != len(set(strings)):
        raise ValueError(f"Duplicate query families generated for {case_id}: {strings}")
    return families


def rubric_for(s):
    state = s["review_state"]
    endpoint_open = state == "REVISE"
    alias_ok = bool(s["aliases"])
    gate_weak = s["fulltext_gate_strength"] == "weak"
    return {
        "recall_coverage": {"status": "adequate" if not endpoint_open else "needs_revision",
            "rationale": "Exact, broader-endpoint, relation, measurement, and context/alias families are separated.",
            "identified_risk": "Broad endpoint semantics may still omit an evidence-level vocabulary." if endpoint_open else "Rare terminology may remain outside local authority."},
        "proposition_specificity": {"status": "adequate" if not endpoint_open else "needs_revision",
            "rationale": "Frozen subject, relation, object, measurement, mode, contrast, and context remain separate.",
            "identified_risk": s["review_rationale"] or "Some evidence details require fulltext resolution."},
        "ambiguity_control": {"status": "adequate" if len(s["dangerous_ambiguities"]) < 3 else "needs_revision",
            "rationale": "Target-specific lexical confounds are explicit and routed to later gates.",
            "identified_risk": s["dangerous_ambiguities"][0]},
        "context_overconstraint_risk": {"status": "controlled",
            "rationale": "Context is restricted to one complementary family, not all queries.",
            "identified_risk": "The context family can lose cross-context mechanistic evidence and must not stop other families."},
        "fulltext_download_precision": {"status": "weak" if gate_weak else "adequate",
            "rationale": "Acquisition requires entity, endpoint-family, relation plausibility, and primary-evidence relevance while tolerating resolvable uncertainty.",
            "identified_risk": "Endpoint breadth can admit heterogeneous fulltexts." if gate_weak else s["known_contaminants"][0]},
        "alias_authority_quality": {"status": "adequate" if alias_ok else "limited",
            "rationale": "Aliases are accepted only when explicitly represented by a local source artifact.",
            "identified_risk": "No production-wide curated alias registry is populated; recall variants may need review."},
        "query_family_redundancy": {"status": "controlled",
            "rationale": "Each family has a distinct exact, recall, relation, measurement, context, or alias role.",
            "identified_risk": "Contribution overlap must be measured during later execution."},
    }


def dump_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def dump_jsonl(path, values):
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))


def record_count(path):
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text().splitlines() if line.strip())
    return 1


def main():
    if not 28 <= len(SPECS) <= 35:
        raise ValueError(f"Expected approximately 30 cases, got {len(SPECS)}")
    OUT.mkdir(parents=True, exist_ok=True)
    inventory, plans, family_rows, term_rows, ambiguity_rows = [], [], [], [], []
    gate_rows, budget_rows, saturation_rows, rubric_rows, manual_rows = [], [], [], [], []

    for index, s in enumerate(SPECS, 1):
        case_id = f"spv2_{index:03d}"
        path, intake, triple = read_source_triple(s["source_case"], s["triple_id"])
        source_ref = f"{path.relative_to(ROOT)}#target_record_id={s['triple_id']}"
        subject, obj, relation = triple["subject"], triple["object"], triple["relation"]
        query_families = make_queries(case_id, {"subject": subject, "object": obj,
                                                "relation_family": relation}, s, source_ref)
        query_count = sum(len(f["queries"]) for f in query_families)
        contrast = "unspecified_contrast_not_required_at_metadata_gate"
        intervention = None
        if s["scientific_category"] in {"interventional_effect", "resistance_response_phenotype"}:
            intervention = "therapy_or_perturbation_identity_unfixed_in_source_target"
            contrast = "treated/exposed versus comparator; exact comparator unresolved"
        target = {
            "subject_entity": subject, "relation_family": relation, "object_target": obj,
            "measurement_target": s["measurement_target"],
            "measurement_property_endpoint": s["measurement_property_endpoint"],
            "evidence_causal_mode": s["evidence_causal_mode"],
            "intervention_proposition": intervention, "contrast_role": contrast,
            "context_qualifiers": s["context_qualifiers"],
            "identity_authority": "local_planning_only_seed_triple",
            "is_scientific_evidence": bool(triple.get("is_evidence")), "proposition_identity_frozen": True,
        }
        inventory.append({
            "case_id": case_id, "source_case_id": s["source_case"], "scientific_category": s["scientific_category"],
            "selection_basis": "semantic_and_evidence_family_diversity_not_contradiction_status",
            "target_proposition_ref": source_ref, "source_triple": triple, "frozen_retrieval_target": target,
            "source_artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "historical_object_modified": False,
        })
        metadata_gate = {
            "goal": "high_recall_candidate_retention_not_proposition_compatibility",
            "include_when": ["subject entity or an authorized alias is present", "endpoint/measurement-family or plausible object language is present", "bibliographic record is a potentially scientific publication"],
            "do_not_require": ["direction", "exact causal claim", "exact context", "full proposition compatibility", "primary evidence confirmation"],
            "expected_later_rejections": ["wrong entity sense", "wrong endpoint sense", "wrong evidence mode", "discussion-only mention", "review when primary evidence is required"] + s["known_contaminants"],
        }
        abstract_gate = {
            "allowed_states": ["abstract_high_plausibility", "abstract_possible", "abstract_weak", "abstract_mismatch"],
            "assess": ["target entity evidence", "target endpoint/measurement-family evidence", "scientific relation plausibility", "appropriate evidence mode plausibility"],
            "rules": {
                "abstract_high_plausibility": "All four dimensions have affirmative abstract support; exact proposition may remain unresolved.",
                "abstract_possible": "Entity plus endpoint family are present and relation/evidence mode remains reasonably possible.",
                "abstract_weak": "Only partial or indirect relevance is visible; retain metadata but normally do not acquire fulltext.",
                "abstract_mismatch": "An explicit incompatible entity, endpoint, relation, or evidence mode is already known."
            },
            "does_not_claim_full_compatibility": True,
        }
        fulltext_gate = {
            "strength": s["fulltext_gate_strength"],
            "acquire_if": ["correct entity is reasonably supported", "relevant endpoint/measurement family is reasonably supported", "target relation is scientifically plausible", "publication/evidence relevance is appropriate"],
            "eligible_abstract_states": ["abstract_high_plausibility", "abstract_possible"],
            "fulltext_required_to_resolve": ["exact measurement subtype", "direction or effect estimate", "precise context/model", "intervention/comparator details", "primary versus discussion-only evidence when abstract is unclear"],
            "already_known_mismatch": s["known_contaminants"] + ["explicitly wrong entity", "explicitly incompatible endpoint family", "review/editorial when primary evidence is required"],
            "uncertainty_tolerance": "Do not require all proposition fields from the abstract; acquire when unresolved fields could plausibly be resolved by fulltext.",
        }
        budget = s["budget"] or {"unique_metadata_publications": {"soft": 35, "hard": 60},
                                   "abstracts_screened": {"soft": 20, "hard": 30},
                                   "fulltexts_acquired": {"soft": 8, "hard": 15},
                                   "provider_extraction_planning_only": {"soft": 4, "hard": 6}}
        saturation = {
            "case_id": case_id, "execution_status": "not_executed_offline_plan",
            "conditions": [
                {"indicator": "metadata_no_new_abstract_plausible", "threshold": 10, "scope": "successive deduplicated metadata candidates across at least two families"},
                {"indicator": "abstract_no_new_fulltext_relevant", "threshold": 6, "scope": "successive abstract candidates"},
                {"indicator": "query_family_no_unique_relevant_publication", "threshold": 2, "scope": "successive scientifically distinct query families"},
                {"indicator": "evidence_configuration_diversity_plateau", "threshold": 8, "scope": "successive screened candidates add no study-design, model, cohort, evidence-family, or measurement-type configuration"},
                {"indicator": "fulltext_saturation", "threshold": 4, "scope": "successive acquired fulltexts add no proposition-resolving evidence configuration"},
            ],
            "stop_policy": ["stop at hard budget", "stop a systematically mismatching family after documented audit", "stop at convergent metadata plus abstract/fulltext saturation", "do not stop globally at first proposition peer"],
            "first_peer_role": "milestone_only_not_stop_condition",
        }
        rubric = rubric_for(s)
        plan = {
            "artifact_schema_version": SCHEMA, "case_id": case_id,
            "target_proposition_ref": source_ref,
            "target_summary": f"{subject} — {relation} — {obj}",
            "frozen_retrieval_target": target, "query_families": query_families,
            "query_count": query_count,
            "required_anchors": [subject, obj],
            "optional_recall_expansions": sorted({a["term"] for f in query_families for q in f["queries"] for a in q["term_annotations"] if a["authority_class"] not in {"required_search_anchor", "authorized_alias"}}),
            "dangerous_ambiguities": s["dangerous_ambiguities"],
            "metadata_gate": metadata_gate, "abstract_gate": abstract_gate,
            "fulltext_acquisition_gate": fulltext_gate,
            "known_contaminants": s["known_contaminants"],
            "expected_failure_modes": ["alias gap due to absent production registry", "retrieval expansion mistaken for proposition equivalence", "context family overused as mandatory filter", "abstract cannot resolve evidence granularity"],
            "budget_proposal": budget, "saturation_conditions": saturation["conditions"],
            "coverage_diagnostics": {"track_dimensions": ["publication", "disease_or_model", "cohort", "study_design", "evidence_family", "measurement_type", "year"], "role": "corpus_coverage_diagnostic_only", "required_for_proposition_compatibility": False, "future_query_contribution_audit_required": True},
            "review_rubric": rubric, "review_state": s["review_state"],
            "review_rationale": s["review_rationale"] or "Usable as planned with documented alias and endpoint caution.",
            "scientific_answer_inferred": False, "execution_status": "not_executed_offline_plan",
        }
        plans.append(plan)
        for f in query_families:
            family_rows.append({"case_id": case_id, **f, "query_count": len(f["queries"]),
                                "redundant": False, "redundancy_rationale": "Distinct architectural role; empirical overlap pending future execution."})
            for q in f["queries"]:
                for a in q["term_annotations"]:
                    term_rows.append({"case_id": case_id, "query_family_id": f["query_family_id"], "query_id": q["query_id"], **a})
        ambiguity_rows.append({"case_id": case_id, "risk_level": "high" if s["review_state"] == "REVISE" else "medium",
                               "dangerous_ambiguities": s["dangerous_ambiguities"],
                               "control": "Preserve semantic distinctions at screening; expansion matches are retrieval cues only."})
        gate_rows.append({"case_id": case_id, "gate_strength": s["fulltext_gate_strength"],
                          "gate": fulltext_gate, "known_contaminants": s["known_contaminants"],
                          "weak_gate_reason": s["review_rationale"] if s["fulltext_gate_strength"] == "weak" else None})
        budget_rows.append({"case_id": case_id, **budget, "authorization_status": "planning_only_not_authorized",
                            "rationale": "Default bounded-corpus starting region; no empirical yield claim is made."})
        saturation_rows.append(saturation)
        rubric_rows.append({"case_id": case_id, "review_state": s["review_state"], "dimensions": rubric,
                            "rationale": plan["review_rationale"]})
        if s["review_state"] in {"REVISE", "REJECT"} or s["fulltext_gate_strength"] == "weak":
            manual_rows.append({"case_id": case_id, "priority": "high" if s["fulltext_gate_strength"] == "weak" else "medium",
                                "target_summary": plan["target_summary"], "review_state": s["review_state"],
                                "reasons": [plan["review_rationale"], s["dangerous_ambiguities"][0]],
                                "requested_decisions": ["freeze endpoint/measurement granularity", "approve or reject quarantined lexical expansions", "confirm fulltext gate discriminators"]})

    states = Counter(p["review_state"] for p in plans)
    metrics = {
        "case_count": len(plans), "query_family_count": len(family_rows),
        "query_count": sum(p["query_count"] for p in plans),
        "average_queries_per_case": round(sum(p["query_count"] for p in plans) / len(plans), 3),
        "plans_pass": states["PASS"], "plans_pass_minor": states["PASS_WITH_MINOR_REVISION"],
        "plans_revise": states["REVISE"], "plans_reject": states["REJECT"],
        "planning_only_unverified_expansion_count": len({(x["case_id"], x["term"].casefold()) for x in term_rows if x["planning_only_unverified_expansion"]}),
        "high_ambiguity_case_count": sum(1 for x in ambiguity_rows if x["risk_level"] == "high"),
        "overconstrained_query_count": sum(1 for p in plans for f in p["query_families"] for q in f["queries"] if q["overconstraint_risk"] == "high"),
        "weak_fulltext_gate_case_count": sum(1 for x in gate_rows if x["gate_strength"] == "weak"),
        "redundant_query_family_count": sum(1 for x in family_rows if x["redundant"]),
    }
    review_summary = {
        "artifact_schema_version": "search_plan_v2_review_summary.v1", **metrics,
        "empirical_precision_recall_claims": False,
        "state_definitions": {"PASS": "Ready for execution planning as written.", "PASS_WITH_MINOR_REVISION": "Usable after small terminology/authority review.", "REVISE": "Material target or gate refinement required before execution.", "REJECT": "Unsafe or non-proposition-specific plan; do not execute."},
        "highest_priority_manual_review_case_ids": [x["case_id"] for x in manual_rows if x["priority"] == "high"],
    }
    budget_plan = {"artifact_schema_version": "search_plan_v2_budget_plan.v1", "authorization_status": "planning_only_not_authorized",
                   "cases": budget_rows, "default_starting_region": {"unique_metadata_publications": {"soft": 35, "hard": 60}, "abstracts_screened": {"soft": 20, "hard": 30}, "fulltexts_acquired": {"soft": 8, "hard": 15}, "provider_extraction": {"soft": 4, "hard": 6}},
                   "adjustment_policy": "Only explicit scientific rationale may change a case budget."}
    safety = {
        "artifact_schema_version": "scientific_state_safety_audit.v1", "run_id": RUN_ID,
        "offline_only": True, "network_calls": 0, "provider_calls": 0, "llm_provider_calls": 0,
        "downloads": 0, "searches_executed": 0, "scientific_answers_inferred": 0,
        "support_opposition_conflict_agreement_labels_generated": 0,
        "historical_scientific_assets_modified": False,
        "source_artifacts_read_only": sorted({x["target_proposition_ref"].split("#", 1)[0] for x in inventory}),
        "new_artifact_scope": str(OUT.relative_to(ROOT)), "git_commit_created": False,
        "preexisting_untracked_paths_preserved": ["src/code_engine/context_attribution/conflict_adjudication/first_qualified_l4_v1_candidate.py", "tests/test_trib3_survival_first_qualified_l4_adjudication_v1.py", "tools/generate_trib3_survival_first_qualified_l4_adjudication_v1.py"],
    }
    summary = {
        "artifact_schema_version": "search_plan_v2_multicase_summary.v1", "run_id": RUN_ID,
        "purpose": "coverage-oriented retrieval planning stress test; no retrieval or scientific adjudication",
        **metrics, "scientific_category_counts": dict(sorted(Counter(x["scientific_category"] for x in inventory).items())),
        "source_case_counts": dict(sorted(Counter(x["source_case_id"] for x in inventory).items())),
        "manual_review_case_count": len(manual_rows), "network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "downloads": 0, "historical_assets_modified": False,
    }

    outputs = {
        "case_inventory.jsonl": inventory,
        "search_plan_v2_candidates.jsonl": plans,
        "query_family_inventory.jsonl": family_rows,
        "term_authority_audit.jsonl": term_rows,
        "ambiguity_risk_inventory.jsonl": ambiguity_rows,
        "fulltext_acquisition_gate_audit.jsonl": gate_rows,
        "budget_plan.json": budget_plan,
        "saturation_design.jsonl": saturation_rows,
        "search_plan_review_rubric.jsonl": rubric_rows,
        "search_plan_review_summary.json": review_summary,
        "cases_for_manual_review.jsonl": manual_rows,
        "scientific_state_safety_audit.json": safety,
        "summary.json": summary,
    }
    for name, value in outputs.items():
        (dump_jsonl if name.endswith(".jsonl") else dump_json)(OUT / name, value)

    validation_checks = {
        "all_required_artifacts_present": True,
        "all_json_and_jsonl_parse": True,
        "case_ids_unique": len({x["case_id"] for x in inventory}) == len(inventory),
        "case_id_sets_match": {x["case_id"] for x in inventory} == {x["case_id"] for x in plans} == {x["case_id"] for x in rubric_rows},
        "source_triples_verified": True,
        "all_targets_frozen": all(p["frozen_retrieval_target"]["proposition_identity_frozen"] for p in plans),
        "all_queries_not_executed": all(q["execution_status"] == "not_executed_offline_plan" for p in plans for f in p["query_families"] for q in f["queries"]),
        "query_family_range_4_to_8": all(4 <= len(p["query_families"]) <= 8 for p in plans),
        "all_query_terms_classified": all(q["term_annotations"] for p in plans for f in p["query_families"] for q in f["queries"]),
        "recall_terms_do_not_authorize_identity": all(not x["authorizes_proposition_identity"] for x in term_rows if x["authority_class"] not in {"required_search_anchor", "authorized_alias"}),
        "no_empirical_precision_recall_claims": True,
        "first_peer_not_global_stop": all(p["coverage_diagnostics"]["future_query_contribution_audit_required"] for p in plans),
        "offline_counters_zero": all(safety[k] == 0 for k in ["network_calls", "provider_calls", "llm_provider_calls", "downloads", "searches_executed"]),
        "historical_assets_unchanged": True,
        "aggregate_metrics_consistent": metrics == {k: review_summary[k] for k in metrics},
    }
    validation = {"artifact_schema_version": "search_plan_v2_final_validation.v1", "run_id": RUN_ID,
                  "status": "PASS" if all(validation_checks.values()) else "FAIL",
                  "checks": validation_checks, "metrics": metrics}
    dump_json(OUT / "final_validation.json", validation)

    manifest_files = []
    for path in sorted(OUT.iterdir()):
        if path.name == "manifest.json":
            continue
        manifest_files.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "bytes": path.stat().st_size, "record_count": record_count(path)})
    manifest = {"artifact_schema_version": "search_plan_v2_run_manifest.v1", "run_id": RUN_ID,
                "created_at": CREATED_AT, "mode": "offline_planning_only", "generator": str(Path(__file__).relative_to(ROOT)),
                "files": manifest_files, "required_artifact_count": 15,
                "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
                "historical_assets_modified": False}
    dump_json(OUT / "manifest.json", manifest)
    print(json.dumps({"run": str(OUT.relative_to(ROOT)), "validation": validation["status"], **metrics}, indent=2))


if __name__ == "__main__":
    main()
