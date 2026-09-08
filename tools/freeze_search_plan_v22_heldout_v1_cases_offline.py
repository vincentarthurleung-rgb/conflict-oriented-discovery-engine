#!/usr/bin/env python3
"""Pre-register eight unseen held-out cases and frozen queries without retrieval."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from generate_search_plan_v2_multicase_stress_test_offline import make_queries
except ModuleNotFoundError:
    from tools.generate_search_plan_v2_multicase_stress_test_offline import make_queries


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
BUDGET_SOURCE = ROOT / "runs/20260909_search_plan_v22_depth180_supplemental_relevance_adjudication_v1_offline/heldout_retrieval_budget_protocol_v1.json"
COMPILER = ROOT / "tools/generate_search_plan_v2_multicase_stress_test_offline.py"
GATE = ROOT / "tools/search_plan_v22_candidate_gates.py"
CALIBRATION_IDS = ["spv2_017", "spv2_026", "spv2_001", "spv2_016", "spv2_003", "spv2_004",
                   "spv2_006_REDESIGNED", "spv2_013_REDESIGNED"]
HISTORICAL_EXCLUSIONS = ["TRIB3-survival", "HIF1A", "CSN8-SOX2"]
REQUIRED = ["heldout_case_registry.jsonl", "heldout_scientific_targets.jsonl", "heldout_retrieval_targets.jsonl",
            "heldout_search_lexical_entries.jsonl", "heldout_query_families.jsonl", "heldout_query_variants.jsonl",
            "heldout_frozen_queries.jsonl", "unseen_proposition_audit.jsonl", "calibration_collision_audit.json",
            "heldout_budget_binding.json", "heldout_fulltext_acquisition_protocol.json",
            "heldout_evaluation_metrics_preregistration.json", "heldout_evaluation_heuristics_preregistration.json",
            "domain_ambiguity_balance.json", "freeze_manifest.json", "scientific_state_safety_audit.json",
            "production_leakage_audit.json", "validation.json", "manifest.json", "summary.json"]


CASES = [
 {"case_id":"heldout_v1_001","ambiguity":"LOW","domain":"inflammation / liver biology","oncology":False,
  "subject":"IL-6","relation":"activates","object":"STAT3","measurement":"STAT3","endpoint":"phosphorylation / activation",
  "context":["hepatocytes or hepatic cells"],"therapy":None,"meaning":"IL-6 exposure activates STAT3 signaling in hepatocyte/hepatic-cell models.",
  "acceptable":["phospho-STAT3 increase","STAT3 phosphorylation","experimentally supported STAT3 activation","nuclear/activity evidence explicitly used as STAT3 activation"],
  "boundary":["generic IL-6/STAT3 co-expression is not activation"],
  "surfaces":{"subject":["IL-6","interleukin-6"],"object":["STAT3","p-STAT3","phospho-STAT3"]},
  "broader":"STAT3 activation","measure_term":"phospho-STAT3","relation_terms":["activation","activates"]},
 {"case_id":"heldout_v1_002","ambiguity":"LOW","domain":"innate immunity","oncology":False,
  "subject":"NLRP3 activation","relation":"increases","object":"IL-1β secretion","measurement":"mature IL-1β","endpoint":"secretion / extracellular release",
  "context":["macrophages"],"therapy":None,"meaning":"Activation of the NLRP3 inflammasome increases mature IL-1β secretion from macrophages.",
  "acceptable":["mature extracellular IL-1β secretion","mature IL-1β release"],
  "boundary":["pro-IL-1β transcription/expression alone does not satisfy the endpoint"],
  "surfaces":{"subject":["NLRP3","NLRP3 inflammasome"],"object":["IL-1β","IL-1beta","interleukin-1 beta"]},
  "broader":"IL-1beta secretion","measure_term":"mature IL-1β","relation_terms":["increases","increase"]},
 {"case_id":"heldout_v1_003","ambiguity":"MEDIUM","domain":"fibrosis","oncology":False,
  "subject":"TGF-β signaling","relation":"increases","object":"collagen I expression","measurement":"COL1A1 / collagen I","endpoint":"gene or protein abundance",
  "context":["fibroblasts"],"therapy":None,"meaning":"TGF-β signaling increases COL1A1 / type-I collagen expression in fibroblast models.",
  "acceptable":["fibroblast COL1A1 abundance","fibroblast type-I collagen abundance"],
  "boundary":["fibrotic tissue association without a fibroblast-level regulatory relation is insufficient"],
  "surfaces":{"subject":["TGF-β","TGF-beta","transforming growth factor beta"],"object":["COL1A1","collagen I","type I collagen"]},
  "broader":"type I collagen","measure_term":"COL1A1","relation_terms":["increases","increase"]},
 {"case_id":"heldout_v1_004","ambiguity":"MEDIUM","domain":"metabolic / endocrine biology","oncology":False,
  "subject":"GLP-1 receptor activation","relation":"increases","object":"glucose-stimulated insulin secretion","measurement":"insulin secretion","endpoint":"GSIS / glucose-stimulated secretion",
  "context":["pancreatic beta cells"],"therapy":None,"meaning":"GLP-1 receptor activation increases glucose-stimulated insulin secretion in pancreatic beta cells.",
  "acceptable":["GSIS","glucose-stimulated insulin secretion"],
  "boundary":["generic insulin abundance or basal insulin expression is not equivalent to GSIS"],
  "surfaces":{"subject":["GLP-1 receptor","GLP1R","GLP-1R"],"object":["glucose-stimulated insulin secretion","GSIS","insulin secretion"]},
  "broader":"insulin secretion","measure_term":"GSIS","relation_terms":["increases","increase"]},
 {"case_id":"heldout_v1_005","ambiguity":"HIGH","domain":"oncology / targeted therapy","oncology":True,
  "subject":"AXL activation","relation":"contributes_to","object":"osimertinib resistance","measurement":"osimertinib treatment response","endpoint":"resistant/sensitive treatment-response contrast",
  "context":["EGFR-mutant non-small-cell lung cancer"],"therapy":"osimertinib","meaning":"AXL activation contributes to osimertinib resistance in EGFR-mutant non-small-cell lung cancer.",
  "acceptable":["resolved osimertinib identity","resistant/sensitive or equivalent response contrast","AXL activity/expression perturbation functionally relevant to resistance"],
  "boundary":["generic AXL expression in lung cancer without treatment response is insufficient"],
  "surfaces":{"subject":["AXL","AXL activation"],"object":["osimertinib","AZD9291"],"context":["EGFR-mutant NSCLC","EGFR mutant lung cancer"]},
  "broader":"treatment resistance","measure_term":"osimertinib resistance","relation_terms":["contributes to","association"]},
 {"case_id":"heldout_v1_006","ambiguity":"HIGH","domain":"hematologic oncology / combination therapy","oncology":True,
  "subject":"BRD4 inhibition","relation":"increases_sensitivity_to","object":"venetoclax","measurement":"venetoclax sensitivity","endpoint":"drug-response / viability / apoptosis contrast",
  "context":["acute myeloid leukemia"],"therapy":"venetoclax","meaning":"BRD4 inhibition increases sensitivity to venetoclax in acute myeloid leukemia.",
  "acceptable":["altered venetoclax sensitivity","viability/apoptosis response to venetoclax","combination-response evidence","source-equivalent drug-response contrast"],
  "boundary":["BRD4 effects on AML growth without venetoclax response are insufficient","BET inhibitor is search-use only unless intervention authority is resolved"],
  "surfaces":{"subject":["BRD4","BRD4 inhibition","BET inhibition"],"object":["venetoclax","ABT-199"],"context":["acute myeloid leukemia","AML"]},
  "broader":"venetoclax response","measure_term":"venetoclax sensitivity","relation_terms":["sensitivity","response"]},
 {"case_id":"heldout_v1_007","ambiguity":"HIGH","domain":"neuroscience","oncology":False,
  "subject":"BDNF","relation":"increases","object":"dendritic spine density","measurement":"dendritic spines","endpoint":"spine density / spine number",
  "context":["hippocampal neurons"],"therapy":None,"meaning":"BDNF increases dendritic spine density in hippocampal neurons.",
  "acceptable":["dendritic spine density","dendritic spine number"],
  "boundary":["neurite length, neuronal survival, synapse-marker abundance or generic plasticity are not automatically equivalent","TrkB/NTRK2 does not replace BDNF as subject"],
  "surfaces":{"subject":["BDNF","brain-derived neurotrophic factor"],"object":["dendritic spine","spine density","spine number"],"context":["hippocampal neuron","hippocampus"]},
  "broader":"spine number","measure_term":"dendritic spine","relation_terms":["increases","increase"]},
 {"case_id":"heldout_v1_008","ambiguity":"HIGH","domain":"metabolic / skeletal muscle biology","oncology":False,
  "subject":"AMPK activation","relation":"increases","object":"glucose uptake","measurement":"glucose uptake","endpoint":"cellular glucose uptake",
  "context":["skeletal muscle cells / myotubes"],"therapy":None,"meaning":"AMPK activation increases glucose uptake in skeletal muscle cells or myotubes.",
  "acceptable":["cellular glucose uptake","2-deoxyglucose uptake","2-DG uptake"],
  "boundary":["GLUT4 abundance/translocation alone does not automatically satisfy glucose uptake"],
  "surfaces":{"subject":["AMPK","AMP-activated protein kinase","AMPK activation"],"object":["glucose uptake","2-deoxyglucose uptake","2-DG uptake"],"context":["skeletal muscle","myotube","myocyte"]},
  "broader":"cellular glucose uptake","measure_term":"2-deoxyglucose uptake","relation_terms":["increases","increase"]},
]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def objsha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value): Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows): Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
def rel(path): return str(Path(path).resolve().relative_to(ROOT))
def norm(value): return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def signature(target):
    return {"subject": norm(target["subject"]), "relation_family": norm(target["relation_family"]),
            "object": norm(target["object"]), "measurement_target": norm(target["measurement_target"]),
            "measurement_property_endpoint": norm(target["measurement_property_endpoint"]),
            "context_qualifiers": sorted(norm(x) for x in target["context_qualifiers"]),
            "therapy": norm(target.get("therapy") or "")}


def historical_source_paths():
    paths = set()
    roots = [ROOT/"configs", ROOT/"case_bundles", ROOT/"archived_experiments", ROOT/"tests/fixtures"]
    names = re.compile(r"(semantic_intake|search_plan\.frozen|case.*manifest|scientific.*target|target.*inventory)")
    for base in roots:
        if not base.exists(): continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".json", ".jsonl"} and names.search(path.name): paths.add(path)
    for pattern in ["runs/*/manifest.json", "runs/*/frozen_search_plans.jsonl", "runs/*/*target*.json*",
                    "runs/*/*search_plan*.json*",
                    "runs/*/artifacts/case_bundle_manifest.json", "runs/*/artifacts/full_line_case_manifest.json",
                    "runs/*/triple_run_manifest.json"]:
        paths.update(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(path for path in paths if RUN not in path.resolve().parents)


def walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value: yield from walk_dicts(child)


def load_values(path):
    try:
        if path.suffix == ".jsonl": return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
        return [readj(path)]
    except (json.JSONDecodeError, UnicodeDecodeError): return []


def candidate_signature(obj):
    if not isinstance(obj, dict): return None
    subject = obj.get("subject") or obj.get("subject_entity")
    relation = obj.get("relation_family") or obj.get("relation")
    object_ = obj.get("object") or obj.get("object_target") or obj.get("object_endpoint")
    measurement = obj.get("measurement_target") or obj.get("measurement_requirement")
    endpoint = obj.get("measurement_property_endpoint") or obj.get("measurement_requirement")
    contexts = obj.get("context_qualifiers") or obj.get("context_recall_scope") or obj.get("context")
    if not (subject and relation and object_ and measurement and endpoint and contexts): return None
    if isinstance(contexts, str): contexts = [contexts]
    return {"subject":norm(subject), "relation_family":norm(relation), "object":norm(object_),
            "measurement_target":norm(measurement), "measurement_property_endpoint":norm(endpoint),
            "context_qualifiers":sorted(norm(x) for x in contexts), "therapy":norm(obj.get("therapy") or obj.get("therapy_identity_requirement") or "")}


def protected_hashes(source_paths):
    paths = source_paths + [BUDGET_SOURCE, COMPILER, GATE]
    return {rel(path): sha(path) for path in paths}


def main():
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()): raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    source_paths = historical_source_paths(); protected_before = protected_hashes(source_paths)
    budget_source = readj(BUDGET_SOURCE)
    if (budget_source["metadata_soft_checkpoint"], budget_source["metadata_hard_safety_ceiling"], budget_source["adaptive_early_stop_state"]) != (120,180,"deferred"):
        raise RuntimeError("Frozen held-out budget source mismatch")

    registry, scientific_targets, retrieval_targets, lexical = [], [], [], []
    for order, case in enumerate(CASES, 1):
        cid = case["case_id"]
        registry.append({"case_order": order, "case_id": cid, "ambiguity_tier": case["ambiguity"],
            "domain": case["domain"], "oncology_case": case["oncology"], "case_state": "FROZEN_PRE_RETRIEVAL",
            "case_selection_authority": "user-specified exact held-out v1 proposition", "replacement_allowed": False})
        scientific_targets.append({"artifact_schema_version":"ScientificPropositionTargetV1",
            "scientific_proposition_target_id":f"{cid}:scientific_proposition:v1", "case_id":cid,
            "subject":case["subject"], "relation_family":case["relation"], "object":case["object"],
            "measurement_target":case["measurement"], "measurement_property_endpoint":case["endpoint"],
            "context_qualifiers":case["context"], "therapy":case["therapy"],
            "primary_proposition_meaning":case["meaning"], "acceptable_endpoint_evidence":case["acceptable"],
            "scientific_boundaries":case["boundary"], "primary_evidence_required":True,
            "retrieval_membership_grants_compatibility":False, "frozen":True})
        retrieval_targets.append({"artifact_schema_version":"RetrievalTargetV2",
            "retrieval_target_id":f"{cid}:retrieval:v2", "case_id":cid,
            "subject_surfaces":case["surfaces"]["subject"], "endpoint_measurement_surfaces":case["surfaces"]["object"],
            "context_recall_scope":case["surfaces"].get("context",case["context"]),
            "relation_recall_scope":case["relation_terms"], "therapy_search_surface":case["therapy"],
            "broader_than_scientific_proposition_allowed":True,
            "search_membership_implies_proposition_compatibility":False,
            "scientific_equivalence_authority":"separate ScientificPropositionTargetV1 and existing entity authority only",
            "frozen":True})
        for category, terms in case["surfaces"].items():
            for lexical_order, term in enumerate(terms, 1):
                lexical.append({"case_id":cid, "category":category, "surface":term, "surface_order":lexical_order,
                    "search_use_allowed":True, "scientific_equivalence_authorized":False,
                    "search_membership_grants_proposition_compatibility":False,
                    "authority":"user-supplied held-out pre-registration search-only surface", "frozen":True})
    writel(RUN/"heldout_case_registry.jsonl",registry); writel(RUN/"heldout_scientific_targets.jsonl",scientific_targets)
    writel(RUN/"heldout_retrieval_targets.jsonl",retrieval_targets); writel(RUN/"heldout_search_lexical_entries.jsonl",lexical)

    historical = []
    for path in source_paths:
        for root_value in load_values(path):
            for obj in walk_dicts(root_value):
                sig = candidate_signature(obj)
                if sig:
                    historical.append({"path":rel(path), "signature":sig,
                        "case_id":obj.get("case_id") or obj.get("candidate_case_id") or obj.get("source_case_id")})
    audits = []
    for case, target in zip(CASES, scientific_targets):
        sig = signature(target)
        exact_records = [record for record in historical if record["signature"] == sig]
        exact = sorted({record["path"] for record in exact_records})
        calibration_refs = sorted({record["path"] for record in exact_records
            if record["case_id"] in CALIBRATION_IDS or "calibration" in record["path"].casefold()})
        retrieval_calibration_refs = sorted({record["path"] for record in exact_records
            if "retrieval" in record["path"].casefold() or "calibration" in record["path"].casefold()})
        adjudication_refs = sorted({record["path"] for record in exact_records
            if "adjudication" in record["path"].casefold()})
        searchable = " ".join([case["subject"],case["object"],case["measurement"],*case["context"]]).casefold()
        entity_overlap = []
        for path in source_paths:
            text = path.read_text(encoding="utf-8",errors="ignore").casefold()
            if norm(case["subject"]).split()[0] in norm(text) and norm(case["object"]).split()[0] in norm(text): entity_overlap.append(rel(path))
        audits.append({"case_id":case["case_id"], "proposition_signature":sig,
            "proposition_signature_sha256":objsha(sig), "exact_proposition_signature_previously_used":bool(exact),
            "exact_collision_refs":exact, "calibration_case_collision":bool(calibration_refs),
            "calibration_collision_refs":calibration_refs,
            "prior_retrieval_calibration_collision":bool(retrieval_calibration_refs),
            "prior_retrieval_calibration_collision_refs":retrieval_calibration_refs,
            "prior_adjudication_collision":bool(adjudication_refs),
            "prior_adjudication_collision_refs":adjudication_refs,
            "entity_or_topic_overlap_ref_count":len(entity_overlap), "entity_or_topic_overlap_is_not_case_collision":True,
            "audit_source_count":len(source_paths), "audit_method":"structural normalized subject/relation/object/measurement/endpoint/context/therapy signature",
            "offline_repository_inspection_only":True})
    writel(RUN/"unseen_proposition_audit.jsonl",audits)
    collision_count = sum(x["exact_proposition_signature_previously_used"] for x in audits)
    calibration_overlap = sum(x["calibration_case_collision"] for x in audits)
    collision_summary = {"heldout_case_count":8, "audit_source_count":len(source_paths),
        "audit_source_inventory":[{"path":rel(p),"sha256":sha(p)} for p in source_paths],
        "calibration_case_ids":CALIBRATION_IDS, "historical_exclusions":HISTORICAL_EXCLUSIONS,
        "deferred_case_ids":["spv2_019"], "calibration_case_overlap":calibration_overlap,
        "exact_prior_proposition_collision":collision_count,
        "prior_retrieval_calibration_collision":sum(x["prior_retrieval_calibration_collision"] for x in audits),
        "prior_adjudication_collision":sum(x["prior_adjudication_collision"] for x in audits),
        "entity_occurrence_not_treated_as_collision":True, "status":"PASS" if not collision_count and not calibration_overlap else "COLLISION_STOP"}
    writej(RUN/"calibration_collision_audit.json",collision_summary)
    if collision_count or calibration_overlap: raise RuntimeError("Exact proposition or calibration case collision; held-out freeze stopped")

    families, variants, frozen_queries = [], [], []
    for case_order, (case, target) in enumerate(zip(CASES, scientific_targets), 1):
        cid = case["case_id"]
        compiler_target = {"subject":case["subject"],"object":case["object"],"relation_family":case["relation"]}
        aliases = {}
        subject_aliases = [x for x in case["surfaces"]["subject"] if norm(x) != norm(case["subject"])]
        object_aliases = [x for x in case["surfaces"]["object"] if norm(x) != norm(case["object"])]
        if subject_aliases: aliases[case["subject"]] = subject_aliases
        if object_aliases: aliases[case["object"]] = object_aliases
        compiler_spec = {"broader":case["broader"], "measurement_terms":[case["measure_term"]],
            "measurement_property_endpoint":case["endpoint"], "relation_terms":case["relation_terms"],
            "context_qualifiers":case["context"], "aliases":aliases, "unverified":[]}
        compiled = make_queries(cid, compiler_target, compiler_spec, f"user_protocol#case_id={cid}")
        for family_order, family in enumerate(compiled, 1):
            families.append({"case_id":cid,"case_order":case_order,"family_order":family_order,
                "query_family":family["query_family_id"],"query_family_id":family["query_family_id"],"family_code":family["family_code"],
                "architecture":family["architecture"],"scientific_justification":family["scientific_justification"],
                "compiler_source_ref":rel(COMPILER),"compiler_source_sha256":sha(COMPILER),"frozen":True})
            for variant_order, query in enumerate(family["queries"], 1):
                qid = query["query_id"]
                authority = [{**ann,
                    "compiler_authorizes_proposition_identity":ann["authorizes_proposition_identity"],
                    "authorizes_proposition_identity":False,"search_use_allowed":True,
                    "search_membership_grants_proposition_compatibility":False,
                    "scientific_equivalence_authorized":False,
                    "compiler_authority_annotation_preserved":ann} for ann in query["term_annotations"]]
                query_order = len(frozen_queries) + 1
                row = {"case_id":cid,"case_order":case_order,"query_family":family["query_family_id"],
                    "query_family_id":family["query_family_id"],"family_order":family_order,
                    "query_variant":qid,"query_variant_id":qid,"variant_order":variant_order,
                    "query_order":query_order,"query_text":query["query_string"],"sort":"relevance","endpoint":"PubMed",
                    "lexical_provenance":authority,"direction_steering_terms_added":False,
                    "execution_status":"frozen_not_executed","frozen":True}
                variants.append(row)
                frozen_queries.append({"query_order":query_order,"global_query_order":query_order,"case_id":cid,
                    "case_order":case_order,"query_family":family["query_family_id"],
                    "query_family_id":family["query_family_id"],"family_order":family_order,
                    "query_variant":qid,"query_variant_id":qid,"variant_order":variant_order,"query_text":query["query_string"],
                    "sort":"relevance","metadata_soft_checkpoint":120,"metadata_hard_safety_ceiling":180,
                    "network_execution_authorized":False,"frozen":True})
    writel(RUN/"heldout_query_families.jsonl",families); writel(RUN/"heldout_query_variants.jsonl",variants)
    writel(RUN/"heldout_frozen_queries.jsonl",frozen_queries)

    binding = {"protocol_ref":rel(BUDGET_SOURCE),"protocol_sha256":sha(BUDGET_SOURCE),
        "metadata_soft_checkpoint":120,"metadata_hard_safety_ceiling":180,"adaptive_early_stop_state":"deferred",
        "same_maximum_for_all_ambiguity_levels":True,"per_case_budget_override":False,
        "retrieval_beyond_180_allowed":False,"natural_query_exhaustion_before_180":"record_as_natural_exhaustion",
        "heldout_validation_started":False,"budget_frozen":True,
        "hard_ceiling_is_scientific_saturation_claim":False}
    writej(RUN/"heldout_budget_binding.json",binding)
    acquisition = {"max_fulltext_selection_per_case":10,"eligibility":["frozen Tier A or Tier B","legal OA"],
        "selection_order":"frozen deterministic Tier A before Tier B, then metadata depth and stable publication identity",
        "reviewer_label_influence_allowed":False,"replacement_based_on_expected_relevance_allowed":False,
        "pmcid_absence_is_irrelevance":False,"provider_allowed":False,"frozen_before_retrieval":True}
    writej(RUN/"heldout_fulltext_acquisition_protocol.json",acquisition)
    metrics = {"frozen_before_retrieval":True,"metrics":[
        {"metric":"overall_direct_relevance_rate","scope":"adjudicated acquired papers"},
        {"metric":"overall_acquisition_justification_rate"},{"metric":"overall_acquisition_acceptability_rate"},
        {"metric":"tier_a_direct_relevance_rate"},{"metric":"tier_a_acquisition_acceptability_rate"},
        {"metric":"tier_b_direct_relevance_utility_proxy"},{"metric":"contaminant_distribution"},
        {"metric":"wrong_evidence_mode_contamination"},{"metric":"association_vs_functional_relation_contamination"},
        {"metric":"wrong_biological_unit_contamination"},{"metric":"per_case_results"},{"metric":"per_ambiguity_results"}],
        "true_literature_precision_or_recall_claimed":False}
    writej(RUN/"heldout_evaluation_metrics_preregistration.json",metrics)
    heuristics = {"frozen_before_retrieval":True,"classification":"engineering_calibration_heuristics_not_scientific_thresholds",
        "tier_a_acquisition_acceptability_target":{"operator":">=","value":0.80},
        "overall_acquisition_acceptability_target":{"operator":">=","value":0.65},
        "review_only_or_wrong_evidence_mode_contamination_target":{"operator":"<=","value":0.15},
        "tier_b_utility_proxy_target":{"operator":">=","value":0.30},
        "qualitative_requirements":["no single systematic contaminant dominates most held-out cases",
            "no case-specific catastrophic failure across an entire ambiguity stratum",
            "no post-hoc case-specific gate repair before primary held-out results are reported"],
        "failure_policy":"report unmet heuristic; do not repair before primary held-out analysis is frozen"}
    writej(RUN/"heldout_evaluation_heuristics_preregistration.json",heuristics)
    ambiguity = Counter(x["ambiguity_tier"] for x in registry)
    balance = {"heldout_case_count":8,"ambiguity_counts":dict(ambiguity),"domain_count":8,
        "domains":[x["domain"] for x in registry],"oncology_case_count":sum(x["oncology_case"] for x in registry),
        "non_oncology_case_count":sum(not x["oncology_case"] for x in registry),
        "distribution_intent":"cross-domain generalization robustness","alter_after_retrieval_allowed":False}
    writej(RUN/"domain_ambiguity_balance.json",balance)

    frozen_names = ["heldout_case_registry.jsonl","heldout_scientific_targets.jsonl","heldout_retrieval_targets.jsonl",
        "heldout_search_lexical_entries.jsonl","heldout_query_families.jsonl","heldout_query_variants.jsonl",
        "heldout_frozen_queries.jsonl","heldout_budget_binding.json","heldout_evaluation_metrics_preregistration.json",
        "heldout_evaluation_heuristics_preregistration.json"]
    components = [{"path":name,"sha256":sha(RUN/name)} for name in frozen_names]
    protocol_hash = objsha([(x["path"],x["sha256"]) for x in components])
    writej(RUN/"freeze_manifest.json",{"components":components,"component_count":len(components),
        "aggregate_algorithm":"sha256(canonical JSON ordered [path, sha256] pairs)",
        "heldout_v1_protocol_sha256":protocol_hash,"queries_frozen":True,"targets_frozen":True,
        "metrics_frozen":True,"evaluation_heuristics_frozen":True,
        "later_retrieval_must_verify_protocol_hash":True})

    protected_after = protected_hashes(source_paths); changed = sorted(k for k in set(protected_before)|set(protected_after) if protected_before.get(k)!=protected_after.get(k))
    safety = {"network_calls":0,"provider_calls":0,"llm_calls":0,"downloads":0,"extraction_calls":0,
        "retrieval_performed":False,"relevance_labels_created_or_predicted":False,"future_performance_inspected":False,
        "historical_assets_modified":bool(changed),"changed_historical_paths":changed,"frozen_gate_modified":False,
        "frozen_budget_modified":False,"git_mutation_invoked":False}
    writej(RUN/"scientific_state_safety_audit.json",safety)
    production = {"search_plan_v22_activation_state":"candidate_frozen_not_activated","heldout_validation_started":False,
        "network_execution_authorized":False,"calibration_tuning_reopened":False,
        "heldout_labels_observed":False,"production_behavior_modified":False,"status":"NO_PRODUCTION_LEAKAGE"}
    writej(RUN/"production_leakage_audit.json",production)
    checks = {"heldout_case_count_8":len(registry)==8,"low_count_2":ambiguity["LOW"]==2,
        "medium_count_2":ambiguity["MEDIUM"]==2,"high_count_4":ambiguity["HIGH"]==4,
        "oncology_case_count_2":balance["oncology_case_count"]==2,"non_oncology_case_count_6":balance["non_oncology_case_count"]==6,
        "calibration_case_overlap_zero":calibration_overlap==0,"exact_prior_proposition_collision_zero":collision_count==0,
        "prior_retrieval_calibration_collision_zero":all(not x["prior_retrieval_calibration_collision"] for x in audits),
        "prior_adjudication_collision_zero":all(not x["prior_adjudication_collision"] for x in audits),
        "budget_120_180_deferred":binding["metadata_soft_checkpoint"]==120 and binding["metadata_hard_safety_ceiling"]==180 and binding["adaptive_early_stop_state"]=="deferred",
        "max_fulltext_selection_10":acquisition["max_fulltext_selection_per_case"]==10,
        "query_family_count_48":len(families)==48,"query_variant_count_48":len(variants)==48,"query_count_48":len(frozen_queries)==48,
        "six_query_families_per_case":all(sum(x["case_id"]==case["case_id"] for x in families)==6 for case in CASES),
        "queries_frozen":all(x["frozen"] for x in frozen_queries),"targets_frozen":all(x["frozen"] for x in scientific_targets+retrieval_targets),
        "metrics_frozen":metrics["frozen_before_retrieval"],"evaluation_heuristics_frozen":heuristics["frozen_before_retrieval"],
        "scientific_retrieval_separation":all(not x["search_membership_implies_proposition_compatibility"] for x in retrieval_targets),
        "lexical_search_only_authority":all(x["search_use_allowed"] and not x["scientific_equivalence_authorized"] for x in lexical),
        "query_compiler_reused":all(x["compiler_source_sha256"]==sha(COMPILER) for x in families),
        "no_outcome_steering_terms_added":all(not x["direction_steering_terms_added"] for x in variants) and all(
            forbidden not in x["query_text"].casefold() for x in variants
            for forbidden in ("contradiction", "conflict", "opposite", "unexpected", "resistance reversal")),
        "protocol_hash_valid":protocol_hash==objsha([(x["path"],sha(RUN/x["path"])) for x in components]),
        "heldout_validation_not_started":not production["heldout_validation_started"],
        "offline_all_calls_zero":safety["network_calls"]==safety["provider_calls"]==safety["llm_calls"]==safety["downloads"]==safety["extraction_calls"]==0,
        "historical_assets_unchanged":not safety["historical_assets_modified"],
        "required_payloads_present":all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json","manifest.json","summary.json"})}
    writej(RUN/"validation.json",{"status":"PASS" if all(checks.values()) else "FAIL","checks":checks})
    summary = {"status":"completed" if all(checks.values()) else "failed","heldout_case_count":8,
        "low_count":ambiguity["LOW"],"medium_count":ambiguity["MEDIUM"],"high_count":ambiguity["HIGH"],
        "oncology_case_count":balance["oncology_case_count"],"non_oncology_case_count":balance["non_oncology_case_count"],
        "calibration_case_overlap":calibration_overlap,"exact_prior_proposition_collision":collision_count,
        "query_family_count":len(families),"query_variant_count":len(variants),"query_count":len(frozen_queries),
        "queries_frozen":True,"targets_frozen":True,"metadata_soft_checkpoint":120,"metadata_hard_safety_ceiling":180,
        "max_fulltext_selection_per_case":10,"adaptive_early_stop_state":"deferred","metrics_frozen":True,
        "evaluation_heuristics_frozen":True,"heldout_v1_protocol_sha256":protocol_hash,
        "heldout_validation_started":False,"network_calls":0,"provider_calls":0,"llm_calls":0,"downloads":0,"extraction_calls":0,
        "historical_assets_modified":bool(changed),"git_head":subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        "git_mutation_invoked":False}
    writej(RUN/"summary.json",summary)
    files=[{"path":p.name,"sha256":sha(p),"bytes":p.stat().st_size,"record_count":len(readl(p)) if p.suffix==".jsonl" else 1}
           for p in sorted(RUN.iterdir()) if p.is_file() and p.name!="manifest.json"]
    writej(RUN/"manifest.json",{"required_artifact_count":len(REQUIRED),"files":files,
        "heldout_v1_protocol_sha256":protocol_hash,"network_calls":0,"provider_calls":0,"llm_calls":0,"downloads":0,"extraction_calls":0})
    checks["manifest_hashes_valid"]=all(sha(RUN/x["path"])==x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"]=all((RUN/x).is_file() for x in REQUIRED)
    writej(RUN/"validation.json",{"status":"PASS" if all(checks.values()) else "FAIL","checks":checks})
    files=[{"path":p.name,"sha256":sha(p),"bytes":p.stat().st_size,"record_count":len(readl(p)) if p.suffix==".jsonl" else 1}
           for p in sorted(RUN.iterdir()) if p.is_file() and p.name!="manifest.json"]
    writej(RUN/"manifest.json",{"required_artifact_count":len(REQUIRED),"files":files,
        "heldout_v1_protocol_sha256":protocol_hash,"network_calls":0,"provider_calls":0,"llm_calls":0,"downloads":0,"extraction_calls":0})
    print(json.dumps(summary,indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__=="__main__": main()
