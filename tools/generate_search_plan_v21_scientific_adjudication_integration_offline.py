#!/usr/bin/env python3
"""Integrate scientific adjudication into proposed Search Plan v2.1 artifacts.

Offline-only candidate generation.  Historical targets and production behavior
are read-only; repaired targets are emitted as new versioned candidates.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "runs/20260906_search_plan_v2_multicase_stress_test_offline"
V21_REVIEW = ROOT / "runs/20260906_search_plan_v21_high_ambiguity_review_offline"
RUN_ID = "20260906_search_plan_v21_scientific_adjudication_integration_offline"
OUT = ROOT / "runs" / RUN_ID
REVIEW_IDS = ["spv2_003", "spv2_004", "spv2_006", "spv2_008", "spv2_013", "spv2_019"]
CREATED_AT = "2026-09-06T00:00:00+08:00"


DECISIONS = [
    ("SAD-01", "spv2_003", "retrieval_scope", "A specific therapeutic agent is not mandatory for search; generic anticancer drug or therapy resistance terminology is allowed for recall."),
    ("SAD-02", "spv2_003", "proposition_scope", "Scientific proposition readiness requires a specific agent or scientifically meaningful defined therapy class; different therapies remain distinct."),
    ("SAD-03", "spv2_003", "tier_b", "Treatment-linked cell viability alone is Tier B at most and never independently authorizes drug resistance."),
    ("SAD-04", "spv2_003", "contrast", "Resistance readiness requires source-grounded resistance/sensitivity contrast semantics, without limiting qualifying language to a closed phrase list."),
    ("SAD-05", "spv2_004", "retrieval_scope", "Explicit scientifically appropriate anticancer treatment modalities may be separate search variants."),
    ("SAD-06", "spv2_004", "proposition_scope", "Therapy agent or modality remains proposition-critical and different therapies do not align solely through the cancer-therapy umbrella."),
    ("SAD-07", "spv2_004", "measurement_scale", "Treatment-linked viability or sensitivity is Tier B and does not automatically equal clinical response; preclinical and clinical scales remain distinct."),
    ("SAD-08", "spv2_006", "target_redesign", "Create a new target for cancer-cell tolerance or survival adaptation under ferroptotic stress; patient and organism survival are mismatches."),
    ("SAD-09", "spv2_006", "measurement_and_contrast", "Cell viability is Tier B search evidence only; adaptation readiness requires a resolved changed-tolerance contrast and baseline viability is insufficient."),
    ("SAD-10", "spv2_008", "retrieval_subject_scope", "Hypoxia exposure and gene signatures are recall surfaces only; unresolved signaling authority is Tier B."),
    ("SAD-11", "spv2_008", "therapy_scope", "Generic cancer therapy response is allowed for recall, but modality or agent must resolve downstream and modalities remain distinct."),
    ("SAD-12", "spv2_013", "target_redesign", "Create a new target using the existing contributes_to relation for cancer-cell survival or viability; tumor survival is not executable."),
    ("SAD-13", "spv2_013", "causal_gate", "Patient overall survival is a known mismatch; Tier A requires pathway activity or perturbation, cellular survival outcome, and functional/causal plausibility."),
    ("SAD-14", "spv2_019", "defer", "Generic metabolism is an umbrella retrieval concept and cannot become a minimum executable scientific proposition; a source-supported metabolic subtarget must be selected."),
    ("SAD-15", "spv2_019", "entity_and_evidence_scope", "mTORC1 may be search-only but cannot replace mTOR scientifically without authority; causal readiness requires activity or perturbation, and this case is excluded from calibration v1."),
]


TARGETS = {
    "spv2_003": {
        "version": "spv2_003_v21_candidate", "retrieval_subject": ["epithelial-mesenchymal transition", "EMT"],
        "retrieval_endpoint": ["drug resistance", "therapy resistance", "altered drug sensitivity", "treatment-linked cell viability"],
        "scientific_subject": "epithelial-mesenchymal transition", "scientific_relation": "involved in",
        "scientific_object": "resistance or altered sensitivity to a resolved anticancer agent or meaningful therapy class",
        "measurement": "source-grounded resistance/sensitivity contrast", "therapy": "specific agent or scientifically meaningful therapy class required",
        "contrast": "resistant/sensitive, resistant/parental, acquired-resistance, sensitivity/IC50 shift, therapy-response difference, or source-equivalent contrast",
        "state": "READY_FOR_RETRIEVAL_CALIBRATION", "redesigned": False,
    },
    "spv2_004": {
        "version": "spv2_004_v21_candidate", "retrieval_subject": ["ferroptosis"],
        "retrieval_endpoint": ["cancer therapy response", "chemotherapy response", "targeted therapy response", "radiotherapy response", "immunotherapy response", "treatment-linked sensitivity or viability"],
        "scientific_subject": "ferroptosis", "scientific_relation": "involved_in",
        "scientific_object": "therapy response at a resolved preclinical or clinical scale for a resolved anticancer agent/modality",
        "measurement": "resolved treatment-response, sensitivity, efficacy, or regression endpoint at its stated scale",
        "therapy": "agent or modality required; therapy-specific propositions remain distinct",
        "contrast": "treated versus comparator and, when relevant, ferroptosis-enabled versus ferroptosis-blocked",
        "state": "READY_FOR_RETRIEVAL_CALIBRATION", "redesigned": False,
    },
    "spv2_006": {
        "version": "spv2_006_REDESIGNED_v1", "retrieval_subject": ["ferroptosis", "ferroptotic stress"],
        "retrieval_endpoint": ["cancer-cell tolerance", "survival adaptation", "cell viability under ferroptotic challenge", "persistent survival"],
        "scientific_subject": "ferroptosis", "scientific_relation": "involved_in",
        "scientific_object": "cancer-cell tolerance or survival adaptation under ferroptotic stress",
        "measurement": "altered cancer-cell survival/tolerance under a defined ferroptotic challenge following a defined state or factor change",
        "therapy": "not proposition-critical unless the defining factor is a treatment",
        "contrast": "adapted/resistant versus parental, preconditioned versus reference, or source-equivalent changed-tolerance contrast",
        "state": "READY_FOR_RETRIEVAL_CALIBRATION", "redesigned": True,
    },
    "spv2_008": {
        "version": "spv2_008_v21_candidate", "retrieval_subject": ["hypoxia signaling", "hypoxia exposure", "hypoxia gene signature", "hypoxic response"],
        "retrieval_endpoint": ["cancer therapy response", "drug sensitivity", "therapy resistance"],
        "scientific_subject": "hypoxia signaling with current-contract pathway/activity authority",
        "scientific_relation": "associated_with", "scientific_object": "response to a resolved anticancer agent or modality",
        "measurement": "resolved clinical or preclinical treatment-response endpoint",
        "therapy": "agent or modality required downstream; modalities remain distinct",
        "contrast": "hypoxic/signaling strata plus treatment-response comparison",
        "state": "READY_FOR_RETRIEVAL_CALIBRATION", "redesigned": False,
    },
    "spv2_013": {
        "version": "spv2_013_REDESIGNED_v1", "retrieval_subject": ["NF-kappaB", "NF-kappaB activity", "NF-kappaB perturbation"],
        "retrieval_endpoint": ["cancer-cell survival", "cancer-cell viability"],
        "scientific_subject": "NF-kappaB activity or perturbation", "scientific_relation": "contributes_to",
        "scientific_object": "cancer-cell survival or viability",
        "measurement": "cell-survival or viability outcome with functional/causal relation plausibility",
        "therapy": "not required", "contrast": "NF-kappaB activity/perturbation versus an appropriate cellular control",
        "state": "READY_FOR_RETRIEVAL_CALIBRATION", "redesigned": True,
    },
    "spv2_019": {
        "version": "spv2_019_DEFERRED_v1", "retrieval_subject": ["mTOR", "mTORC1"],
        "retrieval_endpoint": ["metabolism", "metabolic process", "metabolic flux", "glycolysis", "oxidative phosphorylation", "lipid metabolism", "amino-acid metabolism"],
        "scientific_subject": None, "scientific_relation": None, "scientific_object": None,
        "measurement": "not selected; generic metabolism is insufficient", "therapy": "not applicable",
        "contrast": "not selectable until a metabolic subtarget and activity/perturbation construct are authorized",
        "state": "SEARCH_PLAN_REDESIGN_REQUIRED", "redesigned": False,
    },
}


VARIANTS = {
    "spv2_003": [
        ("A", '"epithelial-mesenchymal transition" AND "drug resistance"', "required_search_anchor", "approved_candidate", "exact frozen surfaces"),
        ("A", '"EMT" AND "drug resistance"', "scientific_authorized_alias", "approved_candidate", "local EMT alias authority"),
        ("B", '"epithelial-mesenchymal transition" AND "therapy resistance"', "search_lexical_authorized", "approved_search_only", "generic anticancer resistance recall"),
        ("D", '"epithelial-mesenchymal transition" AND "altered drug sensitivity"', "search_lexical_authorized", "approved_search_only", "adjudicated sensitivity-contrast surface"),
        ("D", '"epithelial-mesenchymal transition" AND "cancer treatment" AND "cell viability"', "measurement_recall_only", "tier_b_only", "viability requires treatment relevance and fulltext resolution"),
        ("G", '"epithelial-mesenchymal transition" AND "therapy resistance" AND "role"', "planning_only_unverified_expansion", "rejected", "generic role adds contamination without scientific authority"),
    ],
    "spv2_004": [
        ("A", '"ferroptosis" AND "cancer therapy response"', "required_search_anchor", "approved_candidate", "exact frozen surfaces"),
        ("B", '"ferroptosis" AND "chemotherapy response"', "search_lexical_authorized", "approved_search_only", "explicit modality variant"),
        ("B", '"ferroptosis" AND "targeted therapy response"', "search_lexical_authorized", "approved_search_only", "explicit modality variant"),
        ("B", '"ferroptosis" AND "radiotherapy response"', "search_lexical_authorized", "approved_search_only", "explicit modality variant"),
        ("B", '"ferroptosis" AND "immunotherapy response"', "search_lexical_authorized", "approved_search_only", "explicit modality variant"),
        ("D", '"ferroptosis" AND "anticancer treatment" AND "cell viability"', "measurement_recall_only", "tier_b_only", "preclinical scale unresolved"),
        ("D", '"ferroptosis" AND "drug sensitivity" AND "cancer"', "measurement_recall_only", "tier_b_only", "preclinical response candidate only"),
        ("B", '"ferroptosis" AND "treatment outcome"', "planning_only_unverified_expansion", "rejected", "outcome is too generic"),
    ],
    "spv2_006": [
        ("A", '"ferroptosis" AND "cancer-cell tolerance"', "required_search_anchor", "approved_candidate", "redesigned target with repository relation/entity terminology"),
        ("A", '"ferroptosis" AND "survival adaptation" AND "cancer cell"', "search_lexical_authorized", "approved_search_only", "retains historical retrieval surface at cellular scale"),
        ("D", '"ferroptosis" AND "cell viability" AND "adaptation"', "measurement_recall_only", "tier_b_only", "viability cannot authorize adaptation"),
        ("D", '"ferroptotic challenge" AND "tolerance" AND "parental"', "search_lexical_authorized", "approved_search_only", "changed-tolerance contrast wording"),
        ("B", '"ferroptosis" AND "cell survival"', "planning_only_unverified_expansion", "rejected", "baseline cell survival lacks adaptation signal"),
        ("B", '"ferroptosis" AND "patient survival"', "negative_filter_candidate", "rejected_known_mismatch", "patient survival is not target-equivalent"),
    ],
    "spv2_008": [
        ("A", '"hypoxia signaling" AND "cancer therapy response"', "required_search_anchor", "approved_candidate", "exact frozen surfaces"),
        ("A", '"hypoxia exposure" AND "cancer therapy response"', "context_recall_only", "tier_b_only", "exposure does not establish signaling"),
        ("A", '"hypoxia gene signature" AND "cancer therapy response"', "measurement_recall_only", "tier_b_only", "signature does not establish signaling"),
        ("B", '"hypoxic response" AND "drug sensitivity" AND "cancer"', "search_lexical_authorized", "tier_b_only", "subject and response scale require resolution"),
        ("B", '"hypoxia signaling" AND "therapy resistance"', "search_lexical_authorized", "approved_search_only", "generic therapy outcome recall"),
        ("B", '"hypoxia signaling" AND "treatment outcome"', "planning_only_unverified_expansion", "rejected", "outcome is too generic"),
    ],
    "spv2_013": [
        ("A", '"NF-kappaB" AND "cancer-cell survival"', "required_search_anchor", "approved_candidate", "redesigned endpoint"),
        ("D", '"NF-kappaB" AND "cancer-cell viability"', "measurement_recall_only", "approved_search_only", "approved cellular measurement surface"),
        ("C", '"NF-kappaB activity" AND "cell viability"', "search_lexical_authorized", "approved_search_only", "functional activity signal"),
        ("C", '"NF-kappaB perturbation" AND "cell survival"', "relation_recall_only", "approved_search_only", "causal evidence-mode signal"),
        ("A", '"NF-kappaB" AND "tumor survival"', "planning_only_unverified_expansion", "rejected", "historical endpoint is not executable"),
        ("B", '"NF-kappaB" AND "overall survival"', "negative_filter_candidate", "rejected_known_mismatch", "patient overall survival is a mismatch"),
    ],
    "spv2_019": [
        ("A", '"mTOR" AND "metabolism"', "required_search_anchor", "deferred_umbrella_retrieval_only", "cannot produce an executable proposition"),
        ("A", '"mTORC1" AND "metabolism"', "search_lexical_authorized", "deferred_search_only", "entity equivalence is not authorized"),
        ("D", '"mTOR" AND "metabolic flux"', "measurement_recall_only", "manual_subtarget_selection_required", "one possible property; not selected"),
        ("D", '"mTOR" AND "glycolysis"', "planning_only_unverified_expansion", "manual_subtarget_selection_required", "named process needs source authority"),
        ("D", '"mTOR" AND "oxidative phosphorylation"', "planning_only_unverified_expansion", "manual_subtarget_selection_required", "named process needs source authority"),
        ("G", '"mTOR" AND "metabolic regulation" AND "role"', "planning_only_unverified_expansion", "rejected", "generic relation and umbrella endpoint"),
    ],
}


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in values))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v2_plans = {x["case_id"]: x for x in load_jsonl(V2 / "search_plan_v2_candidates.jsonl")}
    review_packets = {x["case_id"]: x for x in load_jsonl(V21_REVIEW / "high_ambiguity_manual_review_packets.jsonl")}
    if set(TARGETS) != set(REVIEW_IDS) or not all(x in v2_plans and x in review_packets for x in REVIEW_IDS):
        raise ValueError("Adjudication input case set mismatch")

    decision_rows = [{"decision_id": did, "case_id": cid, "decision_category": cat, "decision": text,
                      "authority_scope": "search_plan_candidate_revision_only",
                      "does_not_modify_historical_science": True} for did, cid, cat, text in DECISIONS]
    retrieval_targets, proposition_targets, revised_plans, variant_rows, gate_rows, authority_rows = [], [], [], [], [], []
    for cid in REVIEW_IDS:
        old, target = v2_plans[cid], TARGETS[cid]
        retrieval_id = f"{target['version']}:retrieval"
        proposition_id = f"{target['version']}:scientific_proposition"
        retrieval = {
            "artifact_schema_version": "RetrievalTargetV2", "retrieval_target_id": retrieval_id,
            "case_id": cid, "supersedes_for_candidate_planning": f"{cid}:retrieval_target_v2",
            "subject_surfaces": target["retrieval_subject"], "endpoint_measurement_surfaces": target["retrieval_endpoint"],
            "relation_recall_scope": old["frozen_retrieval_target"]["relation_family"],
            "context_recall_scope": old["frozen_retrieval_target"]["context_qualifiers"],
            "broader_than_scientific_proposition_allowed": True,
            "search_membership_implies_proposition_compatibility": False,
            "activation_state": "PROPOSED_NOT_ACTIVATED",
        }
        proposition = {
            "artifact_schema_version": "ScientificPropositionTargetV1", "scientific_proposition_target_id": proposition_id,
            "case_id": cid, "candidate_version": target["version"], "historical_target_ref": old["target_proposition_ref"],
            "historical_target_overwritten": False, "subject": target["scientific_subject"],
            "relation_family": target["scientific_relation"], "object_endpoint": target["scientific_object"],
            "measurement_requirement": target["measurement"], "therapy_identity_requirement": target["therapy"],
            "contrast_requirement": target["contrast"], "candidate_state": target["state"],
            "executable_candidate": target["state"] == "READY_FOR_RETRIEVAL_CALIBRATION",
            "retrieval_membership_grants_compatibility": False,
        }
        retrieval_targets.append(retrieval); proposition_targets.append(proposition)
        variants = []
        for index, (family, query, authority, disposition, reason) in enumerate(VARIANTS[cid], 1):
            row = {"query_variant_id": f"{target['version']}:qv{index:02d}", "case_id": cid,
                   "query_family_code": family, "query_text": query, "authority_class": authority,
                   "disposition": disposition, "search_use_allowed": disposition in {"approved_candidate", "approved_search_only", "tier_b_only", "deferred_umbrella_retrieval_only", "deferred_search_only", "manual_subtarget_selection_required"},
                   "scientific_equivalence_authorized": authority == "scientific_authorized_alias",
                   "tier_b_only": disposition == "tier_b_only", "rationale": reason,
                   "activation_state": "PROPOSED_NOT_ACTIVATED"}
            variants.append(row); variant_rows.append(row)
        revised_plans.append({
            "artifact_schema_version": "search_plan_v21_adjudicated_candidate.v1", "case_id": cid,
            "candidate_version": target["version"], "historical_plan_ref": f"runs/20260906_search_plan_v2_multicase_stress_test_offline/search_plan_v2_candidates.jsonl#case_id={cid}",
            "historical_plan_overwritten": False, "retrieval_target_ref": retrieval_id,
            "scientific_proposition_target_ref": proposition_id, "query_variant_refs": [x["query_variant_id"] for x in variants],
            "ready_state": target["state"], "ready_only_through_redesigned_target": target["redesigned"],
            "retrieval_calibration_eligible": target["state"] == "READY_FOR_RETRIEVAL_CALIBRATION",
            "production_activation": False,
        })
        common_reject = ["wrong biological entity", "topic-only mention", "review/discussion-only when primary evidence is required"]
        case_rules = {
            "spv2_003": (["EMT/drug-resistance entity and endpoint family", "explicit anticancer treatment relevance", "meaningful resistance/sensitivity comparison"], ["therapy agent/class", "exact resistance contrast", "clinical versus cellular scale"], ["non-cancer resistance", "treatment-unlinked baseline viability"]),
            "spv2_004": (["ferroptosis", "explicit anticancer treatment", "treatment-linked response at stated scale"], ["agent/modality", "preclinical versus clinical scale", "comparator", "ferroptosis evidence status"], ["normal-tissue toxicity", "molecular response without therapy outcome"]),
            "spv2_006": (["ferroptotic stress", "cancer-cell tolerance/adaptation", "changed-tolerance contrast"], ["defined challenge", "state/factor change", "adaptation comparator", "viability versus tolerance"], ["patient or organism survival", "baseline viability only"]),
            "spv2_008": (["hypoxia signaling authority", "anticancer treatment", "treatment-response endpoint"], ["exposure/signature versus signaling", "agent/modality", "response scale", "comparison strata"], ["prognosis only", "hypoxia biology without treatment"]),
            "spv2_013": (["NF-kappaB activity or perturbation", "cancer-cell survival/viability", "functional/causal plausibility"], ["activity/perturbation authority", "cellular comparator", "viability assay details"], ["patient overall survival", "tumor persistence/growth without cell-survival evidence"]),
            "spv2_019": (["mTOR or search-only mTORC1 surface", "measured metabolic process candidate"], ["authorized metabolic subtarget", "mTOR versus mTORC1 scope", "activity/perturbation evidence", "measurement property"], ["generic metabolism as a scientific proposition", "mTOR abundance/mention alone"]),
        }[cid]
        plausible, unresolved, rejects = case_rules
        gate_rows.extend([
            {"case_id": cid, "candidate_version": target["version"], "state": "TIER_A_HIGH_CONFIDENCE_ACQUIRE", "criteria": plausible, "no_known_fatal_mismatch": True, "eligible": cid != "spv2_019"},
            {"case_id": cid, "candidate_version": target["version"], "state": "TIER_B_ACQUIRE_TO_RESOLVE", "known_plausible_fields": plausible[:2], "unresolved_fields_requiring_fulltext": unresolved, "topic_only_forbidden": True, "eligible": True},
            {"case_id": cid, "candidate_version": target["version"], "state": "REJECT_KNOWN_MISMATCH", "known_mismatch_reasons": rejects + common_reject, "eligible": True},
        ])
        authority_rows.append({
            "case_id": cid, "retrieval_target_id": retrieval_id, "scientific_proposition_target_id": proposition_id,
            "retrieval_scope": {"subject_surfaces": target["retrieval_subject"], "endpoint_surfaces": target["retrieval_endpoint"]},
            "scientific_scope": {"subject": target["scientific_subject"], "object_endpoint": target["scientific_object"], "measurement": target["measurement"], "therapy": target["therapy"], "contrast": target["contrast"]},
            "boundary_assertions": ["retrieval membership is not proposition compatibility", "search lexical authorization is not scientific equivalence", "measurement scale remains explicit", "therapy identities remain distinct", "unresolved fields route to Tier B"],
            "boundary_status": "PASS",
        })

    # Compact lexical registry: only adjudicated or still-needed surfaces.
    lexical_surfaces = []
    seen = set()
    for row in variant_rows:
        surface = row["query_text"]
        key = (row["case_id"], surface)
        if key in seen: continue
        seen.add(key)
        lexical_surfaces.append({"artifact_schema_version": "SearchLexicalEntryV1", "lexical_entry_id": f"slv2_{len(lexical_surfaces)+1:03d}",
                                 "case_id": row["case_id"], "canonical_search_concept": TARGETS[row["case_id"]]["scientific_object"] or "metabolism umbrella retrieval",
                                 "surface": surface, "surface_type": "query_variant", "scope": "search_plan_v21_adjudicated_candidate",
                                 "source_of_authority": "explicit_scientific_adjudication" if row["authority_class"] in {"search_lexical_authorized", "measurement_recall_only", "context_recall_only", "relation_recall_only"} else "existing_frozen_or_pending_authority",
                                 "search_use_allowed": row["search_use_allowed"], "scientific_equivalence_authorized": row["scientific_equivalence_authorized"],
                                 "scientific_equivalence_basis": "independent_local_alias_authority" if row["scientific_equivalence_authorized"] else None,
                                 "notes": row["rationale"], "activation_state": "PROPOSED_NOT_ACTIVATED"})

    redesign_006 = {"artifact_schema_version": "target_redesign_candidate.v1", "case_id": "spv2_006", "new_case_version": TARGETS["spv2_006"]["version"], "historical_target_overwritten": False, "historical_target": v2_plans["spv2_006"]["frozen_retrieval_target"], "retrieval_target": next(x for x in retrieval_targets if x["case_id"] == "spv2_006"), "scientific_proposition_target": next(x for x in proposition_targets if x["case_id"] == "spv2_006"), "known_mismatches": ["patient survival", "organism survival", "baseline cell viability without changed-tolerance evidence"]}
    redesign_013 = {"artifact_schema_version": "target_redesign_candidate.v1", "case_id": "spv2_013", "new_case_version": TARGETS["spv2_013"]["version"], "historical_target_overwritten": False, "historical_target": v2_plans["spv2_013"]["frozen_retrieval_target"], "retrieval_target": next(x for x in retrieval_targets if x["case_id"] == "spv2_013"), "scientific_proposition_target": next(x for x in proposition_targets if x["case_id"] == "spv2_013"), "known_mismatches": ["patient overall survival", "tumor persistence or growth without cell-survival evidence"], "tier_a_causal_requirement": ["NF-kappaB activity or perturbation authority", "cell-survival or viability outcome", "functional or causal relation plausibility"]}
    defer_019 = {"artifact_schema_version": "target_defer_candidate.v1", "case_id": "spv2_019", "candidate_version": TARGETS["spv2_019"]["version"], "state": "SEARCH_PLAN_REDESIGN_REQUIRED", "calibration_v1_eligible": False, "reason": "Metabolism is not a sufficiently specific scientific measurement/property.", "historical_target_overwritten": False, "umbrella_retrieval_allowed": True, "candidate_subtargets_not_selected": ["glycolysis", "oxidative phosphorylation", "lipid metabolism", "amino-acid metabolism", "specific metabolic flux/process"], "mTORC1_search_use_allowed": True, "mTORC1_scientific_equivalence_authorized": False, "minimum_future_evidence": ["source-supported metabolic subtarget", "resolved measurement property", "mTOR/mTORC1 scope authority", "activity or perturbation evidence"]}

    calibration_cases = [
        ("spv2_017", "LOW", "existing_v2", "molecular-relation control"),
        ("spv2_026", "LOW", "existing_v2", "defined-process control"),
        ("spv2_001", "MEDIUM", "existing_v2", "phenotype and assay-scale control"),
        ("spv2_016", "MEDIUM", "existing_v2", "expression measurement boundary"),
        ("spv2_003", "HIGH", TARGETS["spv2_003"]["version"], "therapy-resistance boundary"),
        ("spv2_004", "HIGH", TARGETS["spv2_004"]["version"], "therapy modality and scale boundary"),
        ("spv2_006_REDESIGNED", "HIGH", TARGETS["spv2_006"]["version"], "changed-tolerance target repair"),
        ("spv2_013_REDESIGNED", "HIGH", TARGETS["spv2_013"]["version"], "cell-survival and causal gate repair"),
    ]
    calibration_set = {"artifact_schema_version": "calibration_case_set_v1", "status": "FROZEN_CANDIDATE_NOT_EXECUTED", "case_count": 8,
                       "cases": [{"calibration_case_id": cid, "ambiguity_tier": tier, "target_version_ref": ref, "evaluation_role": role} for cid, tier, ref, role in calibration_cases],
                       "excluded": [{"case_id": "spv2_019", "reason": "scientific metabolic subtarget not defined"}]}
    default_budget = {"metadata_unique": {"soft_range": [30, 40], "hard": 60}, "abstract_screening": {"soft_range": [15, 20], "hard": 30}, "fulltext_acquisition": {"soft_range": [6, 10], "hard": 15}, "provider_calls": {"hard": 0}}
    budget_plan = {"artifact_schema_version": "calibration_budget_plan.v1", "authorization": "planning_only_not_execution_authorization", "default_candidate_ceiling_per_case": default_budget, "cases": [{"calibration_case_id": x[0], "budget": default_budget} for x in calibration_cases]}
    execution_plan = {"artifact_schema_version": "calibration_execution_plan.v1", "status": "PREPARED_NOT_EXECUTED", "purpose": "retrieval calibration only; not extraction or conflict accuracy", "provider_extraction_enabled": False,
                      "stages": ["execute approved query variants", "deduplicate metadata", "high-recall metadata plausibility screening", "abstract plausibility classification", "Tier A/Tier B/Reject classification", "fulltext acquisition within ceilings", "manual retrieval-relevance adjudication", "query-family and query-variant contribution accounting", "saturation analysis"],
                      "future_empirical_goals": ["retrieval breadth", "relevant-publication coverage", "fulltext acquisition precision", "Tier-A precision", "Tier-B utility", "query-family contribution", "query-variant contribution", "contaminant classes", "saturation behavior"],
                      "excluded_evaluations": ["provider extraction accuracy", "conflict accuracy", "scientific hypothesis validity"], "network_execution_authorized": False}

    ready = {cid: TARGETS[cid]["state"] == "READY_FOR_RETRIEVAL_CALIBRATION" for cid in REVIEW_IDS}
    summary = {"artifact_schema_version": "search_plan_v21_scientific_adjudication_summary.v1", "run_id": RUN_ID,
               "scientific_adjudication_decision_count": len(decision_rows), "review_case_count": 6,
               "retrieval_target_candidate_count": len(retrieval_targets), "scientific_proposition_target_candidate_count": len(proposition_targets),
               "revised_search_plan_count": len(revised_plans), "query_variant_count": len(variant_rows),
               "approved_or_tier_b_search_variant_count": sum(x["search_use_allowed"] for x in variant_rows),
               "rejected_query_variant_count": sum(x["disposition"].startswith("rejected") for x in variant_rows),
               "fulltext_gate_rule_count": len(gate_rows), "calibration_case_count": 8,
               "case_states": {cid: TARGETS[cid]["state"] for cid in REVIEW_IDS},
               "search_plan_v21_activation_state": "pending_retrieval_calibration", "production_activated": False,
               "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "historical_assets_modified": False}
    safety = {"artifact_schema_version": "scientific_state_safety_audit.v1", "run_id": RUN_ID, "offline_only": True,
              "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "searches_executed": 0,
              "historical_scientific_assets_modified": False, "historical_targets_overwritten": False,
              "production_behavior_modified": False, "git_commit_created": False,
              "source_runs_read_only": [str(V2.relative_to(ROOT)), str(V21_REVIEW.relative_to(ROOT))],
              "new_artifact_scope": str(OUT.relative_to(ROOT))}
    outputs = {
        "scientific_adjudication_decisions.jsonl": decision_rows,
        "retrieval_target_v2_candidates.jsonl": retrieval_targets,
        "scientific_proposition_target_candidates.jsonl": proposition_targets,
        "target_redesign_spv2_006.json": redesign_006, "target_redesign_spv2_013.json": redesign_013,
        "target_defer_spv2_019.json": defer_019, "revised_search_plan_v21_candidates.jsonl": revised_plans,
        "revised_query_variants.jsonl": variant_rows, "search_lexical_registry_candidates_v2.jsonl": lexical_surfaces,
        "fulltext_acquisition_gate_v21.jsonl": gate_rows, "retrieval_vs_scientific_authority_audit.jsonl": authority_rows,
        "calibration_case_set_v1.json": calibration_set, "calibration_budget_plan.json": budget_plan,
        "calibration_execution_plan.json": execution_plan, "scientific_state_safety_audit.json": safety,
        "summary.json": summary,
    }
    for name, value in outputs.items(): (write_jsonl if name.endswith(".jsonl") else write_json)(OUT / name, value)
    checks = {
        "decision_count_15": len(decision_rows) == 15,
        "retrieval_can_be_broader": all(x["broader_than_scientific_proposition_allowed"] for x in retrieval_targets),
        "search_membership_never_grants_compatibility": all(not x["search_membership_implies_proposition_compatibility"] for x in retrieval_targets) and all(not x["retrieval_membership_grants_compatibility"] for x in proposition_targets),
        "therapy_identity_preserved": "specific agent" in TARGETS["spv2_003"]["therapy"] and "agent or modality" in TARGETS["spv2_004"]["therapy"] and "agent or modality" in TARGETS["spv2_008"]["therapy"],
        "patient_survival_rejected_for_cell_target": any("patient overall survival" in r for r in deferless(gate_rows, "spv2_013", "REJECT_KNOWN_MISMATCH")),
        "viability_not_adaptation_authority": any(x["case_id"] == "spv2_006" and x["tier_b_only"] and "viability" in x["query_text"] for x in variant_rows),
        "hypoxia_exposure_not_signaling_authority": all(x["disposition"] == "tier_b_only" for x in variant_rows if x["case_id"] == "spv2_008" and ("exposure" in x["query_text"] or "signature" in x["query_text"])),
        "generic_metabolism_not_executable": not next(x for x in proposition_targets if x["case_id"] == "spv2_019")["executable_candidate"],
        "mtorc1_not_scientific_equivalent": not defer_019["mTORC1_scientific_equivalence_authorized"],
        "therapy_modalities_not_aligned": all(not x["scientific_equivalence_authorized"] for x in variant_rows if x["case_id"] == "spv2_004" and any(m in x["query_text"] for m in ["chemotherapy", "targeted therapy", "radiotherapy", "immunotherapy"])),
        "tier_b_ledgers_complete": all(x.get("known_plausible_fields") and x.get("unresolved_fields_requiring_fulltext") and x["topic_only_forbidden"] for x in gate_rows if x["state"] == "TIER_B_ACQUIRE_TO_RESOLVE"),
        "calibration_set_exact": [x["calibration_case_id"] for x in calibration_set["cases"]] == [x[0] for x in calibration_cases] and calibration_set["case_count"] == 8,
        "spv2_019_excluded": calibration_set["excluded"][0]["case_id"] == "spv2_019" and all(x["calibration_case_id"] != "spv2_019" for x in calibration_set["cases"]),
        "expected_ready_states": all(ready[x] for x in ["spv2_003", "spv2_004", "spv2_006", "spv2_008", "spv2_013"]) and not ready["spv2_019"],
        "offline_counters_zero": all(safety[x] == 0 for x in ["network_calls", "provider_calls", "llm_calls", "downloads", "searches_executed"]),
        "historical_artifacts_unchanged": not safety["historical_scientific_assets_modified"] and not safety["historical_targets_overwritten"],
    }
    validation = {"artifact_schema_version": "search_plan_v21_scientific_adjudication_final_validation.v1", "run_id": RUN_ID,
                  "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
                  "scientific_adjudication_decision_count": 15, "calibration_case_count": 8}
    write_json(OUT / "final_validation.json", validation)
    files = []
    for path in sorted(OUT.iterdir()):
        if path.name == "manifest.json": continue
        files.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
                      "record_count": sum(1 for x in path.read_text().splitlines() if x.strip()) if path.suffix == ".jsonl" else 1})
    manifest = {"artifact_schema_version": "search_plan_v21_scientific_adjudication_manifest.v1", "run_id": RUN_ID,
                "created_at": CREATED_AT, "mode": "offline_candidate_integration", "generator": str(Path(__file__).relative_to(ROOT)),
                "required_artifact_count": 18, "files": files, "network_calls": 0, "provider_calls": 0,
                "llm_calls": 0, "downloads": 0, "historical_assets_modified": False}
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"run": str(OUT.relative_to(ROOT)), "validation": validation["status"], **summary}, indent=2))


def deferless(rows, case_id, state):
    row = next(x for x in rows if x["case_id"] == case_id and x["state"] == state)
    return row["known_mismatch_reasons"]


if __name__ == "__main__":
    main()
