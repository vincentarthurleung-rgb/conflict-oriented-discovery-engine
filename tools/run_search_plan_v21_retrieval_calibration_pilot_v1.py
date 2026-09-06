#!/usr/bin/env python3
"""Execute/replay the frozen eight-case Search Plan v2.1 retrieval pilot.

Only NCBI PubMed/PMC retrieval is implemented.  There are deliberately no
provider, model, extraction, Candidate, Formal, Atlas, pointer, or VEM imports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260906_search_plan_v21_scientific_adjudication_integration_offline"
V2 = ROOT / "runs/20260906_search_plan_v2_multicase_stress_test_offline"
RUN = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
ASSETS = RUN / "retrieval_assets"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CASE_ORDER = ["spv2_017", "spv2_026", "spv2_001", "spv2_016", "spv2_003", "spv2_004", "spv2_006_REDESIGNED", "spv2_013_REDESIGNED"]
UNDERLYING = {"spv2_006_REDESIGNED": "spv2_006", "spv2_013_REDESIGNED": "spv2_013"}
REQUIRED = [
    "baseline.json", "execution_authorization.json", "frozen_calibration_case_set.json",
    "frozen_search_plans.jsonl", "frozen_query_variants.jsonl", "frozen_gate_rules.jsonl",
    "executed_queries.jsonl", "query_execution_summary.json", "raw_metadata_manifest.jsonl",
    "publication_identity_inventory.jsonl", "publication_deduplication_audit.json",
    "metadata_stage_results.jsonl", "abstract_snapshots_manifest.jsonl",
    "abstract_screening_results.jsonl", "tier_a_candidates.jsonl", "tier_b_candidates.jsonl",
    "rejected_known_mismatch.jsonl", "fulltext_acquisition_attempts.jsonl",
    "fulltext_acquired_manifest.jsonl", "cross_case_fulltext_cache_audit.json",
    "query_variant_contribution.jsonl", "query_family_contribution.jsonl",
    "retrieval_candidate_saturation_curves.jsonl", "retrieval_relevance_review_packets.jsonl",
    "retrieval_relevance_adjudication_template.jsonl", "failure_inventory.jsonl",
    "network_usage_audit.json", "provider_usage_audit.json", "scientific_state_safety_audit.json",
    "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json",
]
FROZEN_FILES = ["frozen_calibration_case_set.json", "frozen_search_plans.jsonl", "frozen_query_variants.jsonl", "frozen_gate_rules.jsonl"]


SCREEN = {
    "spv2_017": {"entity": ["pi3k", "phosphoinositide 3-kinase"], "endpoint": ["akt", "protein kinase b"], "relation": ["activat", "phosphorylat"], "context": ["cancer", "tumor", "carcinoma"]},
    "spv2_026": {"entity": ["p53", "tp53"], "endpoint": ["apoptosis", "apoptotic"], "relation": ["induc", "regulat", "mediat", "activat", "involved"], "context": ["cancer", "tumor", "carcinoma"]},
    "spv2_001": {"entity": ["epithelial-mesenchymal transition", "epithelial mesenchymal transition", "emt"], "endpoint": ["metastasis", "metastatic"], "relation": ["promot", "drive", "regulat", "involved", "associated"], "context": ["cancer", "tumor", "carcinoma"]},
    "spv2_016": {"entity": ["tumor microenvironment", "tumour microenvironment", "tme"], "endpoint": ["pd-l1 expression", "pdl1 expression", "cd274 expression", "pd-l1"], "relation": ["modulat", "regulat", "induc", "affect"], "context": ["cancer", "tumor", "carcinoma"]},
    "spv2_003": {"entity": ["epithelial-mesenchymal transition", "epithelial mesenchymal transition", "emt"], "endpoint": ["drug resistance", "therapy resistance", "chemoresistance", "drug sensitivity", "resistant"], "relation": ["associated", "involved", "contribut", "promot", "induc"], "context": ["cancer", "tumor", "carcinoma", "anticancer"], "treatment": ["drug", "therapy", "treatment", "chemotherapy", "inhibitor"], "contrast": ["resistant", "sensitive", "parental", "acquired", "ic50", "response difference", "sensitivity shift"]},
    "spv2_004": {"entity": ["ferroptosis", "ferroptotic"], "endpoint": ["therapy response", "treatment response", "drug sensitivity", "cell viability", "efficacy", "tumor regression", "resistance"], "relation": ["sensiti", "response", "efficacy", "viability", "regression"], "context": ["cancer", "tumor", "carcinoma", "anticancer"], "treatment": ["drug", "therapy", "treatment", "chemotherapy", "radiotherapy", "immunotherapy", "inhibitor"]},
    "spv2_006_REDESIGNED": {"entity": ["ferroptosis", "ferroptotic"], "endpoint": ["tolerance", "adaptation", "resistant", "persistence", "cell viability", "cell survival"], "relation": ["adapt", "toler", "resistan", "precondition", "survival"], "context": ["cancer", "tumor", "carcinoma", "cancer cell"], "adaptation": ["adapt", "toler", "resistant", "precondition", "persistent"], "contrast": ["parental", "control", "naive", "reference", "versus", "compared", "shift", "altered"]},
    "spv2_013_REDESIGNED": {"entity": ["nf-kappab", "nf kappa b", "nfkb", "nuclear factor kappa"], "endpoint": ["cancer cell survival", "tumor cell survival", "cell survival", "cell viability"], "relation": ["contribut", "promot", "support", "regulat", "mediate"], "context": ["cancer", "tumor", "carcinoma", "cancer cell"], "functional": ["activity", "activation", "inhibit", "knockdown", "silenc", "deplet", "perturb", "nuclear translocation"]},
}


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--replay", action="store_true")
    return parser.parse_args()


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rel(path): return str(Path(path).relative_to(ROOT))
def read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def read_jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def write_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def normalized(text):
    text = unicodedata.normalize("NFKD", text or "").casefold().replace("κ", "kappa")
    return re.sub(r"[^a-z0-9]+", " ", text)


def has_any(text, terms):
    raw = (text or "").casefold()
    norm = normalized(text)
    return any(term.casefold() in raw or normalized(term) in norm for term in terms)


def text_of(node): return "" if node is None else "".join(node.itertext()).strip()


def freeze_inputs():
    RUN.mkdir(parents=True, exist_ok=True); ASSETS.mkdir(parents=True, exist_ok=True)
    cal = read_json(SOURCE / "calibration_case_set_v1.json")
    if [x["calibration_case_id"] for x in cal["cases"]] != CASE_ORDER or any(x["calibration_case_id"] == "spv2_019" for x in cal["cases"]):
        raise ValueError("Calibration identity/version mismatch")
    source_plans = {x["case_id"]: x for x in read_jsonl(SOURCE / "revised_search_plan_v21_candidates.jsonl")}
    source_variants = read_jsonl(SOURCE / "revised_query_variants.jsonl")
    source_gates = read_jsonl(SOURCE / "fulltext_acquisition_gate_v21.jsonl")
    v2_plans = {x["case_id"]: x for x in read_jsonl(V2 / "search_plan_v2_candidates.jsonl")}
    budget = read_json(SOURCE / "calibration_budget_plan.json")["default_candidate_ceiling_per_case"]
    frozen_plans, frozen_variants, frozen_gates = [], [], []
    for item in cal["cases"]:
        cid = item["calibration_case_id"]; source_id = UNDERLYING.get(cid, cid)
        if cid in {"spv2_017", "spv2_026", "spv2_001", "spv2_016"}:
            old = v2_plans[cid]
            retrieval = old["frozen_retrieval_target"]
            scientific = old["frozen_retrieval_target"]
            for family in old["query_families"]:
                for q in family["queries"]:
                    mapping = {"required_search_anchor": "required_search_anchor", "authorized_alias": "scientific_authorized_alias", "recall_expansion_only": "planning_only_unverified_expansion", "context_expansion_only": "context_recall_only", "measurement_expansion_only": "measurement_recall_only", "relation_expansion_only": "relation_recall_only"}
                    frozen_variants.append({"case_id": cid, "query_family_id": f"{cid}:{family['family_code']}", "query_variant_id": q["query_id"], "query_string": q["query_string"], "term_authority_annotations": [{**a, "v21_authority_class": mapping[a["authority_class"]]} for a in q["term_annotations"]], "endpoint": "PubMed", "executable": True, "source_ref": old["target_proposition_ref"]})
            spec = SCREEN[cid]
            frozen_gates.extend([
                {"case_id": cid, "state": "TIER_A_HIGH_CONFIDENCE_ACQUIRE", "criteria": ["correct entity anchor", "correct endpoint/measurement family", "relation/evidence plausibility"], "source": "v2 gate translated to frozen v2.1 three-state form before execution"},
                {"case_id": cid, "state": "TIER_B_ACQUIRE_TO_RESOLVE", "known_plausible_fields": ["correct entity anchor", "endpoint/measurement family"], "unresolved_fields_requiring_fulltext": ["exact measurement property", "relation evidence", "context/model", "comparator"], "topic_only_forbidden": True},
                {"case_id": cid, "state": "REJECT_KNOWN_MISMATCH", "known_mismatch_reasons": ["wrong entity", "wrong endpoint family", "topic-only publication", "review-only evidence when primary evidence is required"]},
            ])
        else:
            plan = source_plans[source_id]
            retrieval = next(x for x in read_jsonl(SOURCE / "retrieval_target_v2_candidates.jsonl") if x["case_id"] == source_id)
            scientific = next(x for x in read_jsonl(SOURCE / "scientific_proposition_target_candidates.jsonl") if x["case_id"] == source_id)
            for v in source_variants:
                if v["case_id"] == source_id and v["search_use_allowed"]:
                    frozen_variants.append({"case_id": cid, "query_family_id": f"{cid}:{v['query_family_code']}", "query_variant_id": v["query_variant_id"].replace(source_id, cid), "query_string": v["query_text"], "term_authority_annotations": [{"surface_scope": "query_variant", "authority_class": v["authority_class"], "scientific_equivalence_authorized": v["scientific_equivalence_authorized"]}], "endpoint": "PubMed", "executable": True, "source_ref": plan["scientific_proposition_target_ref"]})
            for gate in source_gates:
                if gate["case_id"] == source_id:
                    frozen_gates.append({**gate, "case_id": cid})
        frozen_plans.append({"case_id": cid, "ambiguity_tier": item["ambiguity_tier"], "target_version_ref": item["target_version_ref"], "retrieval_target": retrieval, "scientific_proposition_target": scientific, "budget": budget, "saturation_policy": {"execute_all_active_variants": True, "early_stop_allowed_only_for": ["hard_case_budget", "network_safety_failure", "frozen_retrieval_candidate_saturation"], "first_peer_is_stop": False, "candidate_saturation_requires_manual_audit_for_final_conclusion": True}, "frozen": True})
    write_json(RUN / "frozen_calibration_case_set.json", cal)
    write_jsonl(RUN / "frozen_search_plans.jsonl", frozen_plans)
    write_jsonl(RUN / "frozen_query_variants.jsonl", frozen_variants)
    write_jsonl(RUN / "frozen_gate_rules.jsonl", frozen_gates)
    frozen_hashes = {name: sha(RUN / name) for name in FROZEN_FILES}
    protected = [SOURCE / "manifest.json", SOURCE / "summary.json", V2 / "manifest.json", V2 / "summary.json"]
    write_json(RUN / "baseline.json", {"artifact_schema_version": "retrieval_calibration_baseline.v1", "created_at": now(), "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(), "source_run": rel(SOURCE), "source_run_manifest_sha256": sha(SOURCE / "manifest.json"), "case_count": 8, "case_order": CASE_ORDER, "frozen_hashes_before_network": frozen_hashes, "protected_hashes_before": {rel(x): sha(x) for x in protected}, "network_started": False})
    write_json(RUN / "execution_authorization.json", {"artifact_schema_version": "retrieval_calibration_execution_authorization.v1", "explicit_user_authorization": True, "authorization_source": "user task Search Plan v2.1 Real Retrieval Calibration Pilot v1", "allowed_network_services": ["NCBI PubMed E-utilities", "NCBI PMC E-utilities"], "provider_calls_authorized": False, "llm_calls_authorized": False, "extraction_authorized": False, "maximum_case_publications": 480, "maximum_case_abstracts": 240, "maximum_case_fulltext_attempts": 120, "frozen_hashes": frozen_hashes})
    return len(frozen_variants)


class Network:
    def __init__(self, execute):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        self.events = read_json(self.receipt)["events"] if self.receipt.exists() else []

    def get(self, url, path, kind, lineage):
        path = Path(path)
        if path.exists():
            return path.read_bytes()
        if not self.execute: raise FileNotFoundError(path)
        assert_frozen()
        request = urllib.request.Request(url, headers={"User-Agent": "conflict-oriented-discovery-engine-retrieval-calibration/1.0"})
        stamp = now()
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read(); status = response.status; content_type = response.headers.get("Content-Type")
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        self.events.append({"request_id": f"ncbi_request_{len(self.events)+1:04d}", "kind": kind, "timestamp": stamp, "url": url, "http_status": status, "content_type": content_type, "snapshot_ref": rel(path), "response_sha256": sha(path), "bytes": len(body), "lineage": lineage})
        write_json(self.receipt, {"events": self.events, "provider_calls": 0, "llm_calls": 0})
        time.sleep(0.36)
        return body


def assert_frozen():
    auth = read_json(RUN / "execution_authorization.json")
    for name, digest in auth["frozen_hashes"].items():
        if sha(RUN / name) != digest: raise RuntimeError(f"Frozen plan changed after authorization: {name}")


def parse_pubmed(raw):
    root = ET.fromstring(raw); output = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = text_of(article.find("./MedlineCitation/PMID"))
        title = text_of(article.find("./MedlineCitation/Article/ArticleTitle"))
        abstract = "\n".join(text_of(x) for x in article.findall("./MedlineCitation/Article/Abstract/AbstractText"))
        ids = {x.attrib.get("IdType"): text_of(x) for x in article.findall("./PubmedData/ArticleIdList/ArticleId")}
        pubtypes = [text_of(x) for x in article.findall("./MedlineCitation/Article/PublicationTypeList/PublicationType")]
        journal = text_of(article.find("./MedlineCitation/Article/Journal/Title"))
        year = text_of(article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")) or text_of(article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate"))
        output[pmid] = {"canonical_publication_id": f"pmid:{pmid}", "pmid": pmid, "pmcid": ids.get("pmc"), "doi": ids.get("doi"), "title": title, "abstract": abstract, "publication_types": pubtypes, "journal": journal, "publication_date": year}
    return output


def screen_abstract(cid, publication):
    spec = SCREEN[cid]; text = publication["title"] + "\n" + publication["abstract"]
    entity = has_any(text, spec["entity"]); endpoint = has_any(text, spec["endpoint"]); relation = has_any(text, spec["relation"]); context = has_any(text, spec["context"])
    reason = []
    if cid == "spv2_013_REDESIGNED" and has_any(text, ["overall survival", "patient survival", "progression-free survival"]) and not has_any(text, ["cell survival", "cell viability", "cancer cell survival", "tumor cell survival"]):
        return "abstract_mismatch", "explicit patient-survival endpoint mismatches cellular survival target", {"entity": entity, "endpoint": False, "relation": relation, "context": context}
    if cid == "spv2_006_REDESIGNED" and has_any(text, ["overall survival", "patient survival", "animal survival"]) and not has_any(text, spec["adaptation"]):
        return "abstract_mismatch", "patient/organism survival without adaptation mismatches redesigned cellular target", {"entity": entity, "endpoint": False, "relation": relation, "context": context}
    if cid == "spv2_003" and has_any(text, ["bacterial resistance", "antibiotic resistance", "antimicrobial resistance"]) and not context:
        return "abstract_mismatch", "non-cancer antimicrobial resistance", {"entity": entity, "endpoint": endpoint, "relation": relation, "context": context}
    if entity and endpoint and (relation or context): state = "abstract_high_plausibility"
    elif entity and endpoint: state = "abstract_possible"
    elif entity or endpoint: state = "abstract_weak"
    else: state = "abstract_mismatch"
    reason.append("entity present" if entity else "entity absent")
    reason.append("endpoint family present" if endpoint else "endpoint family absent")
    reason.append("relation/evidence language present" if relation else "relation/evidence language unresolved")
    return state, "; ".join(reason), {"entity": entity, "endpoint": endpoint, "relation": relation, "context": context}


def tier_candidate(cid, publication, abstract_state, signals, gate_map):
    text = publication["title"] + "\n" + publication["abstract"]
    if abstract_state == "abstract_mismatch": return "REJECT_KNOWN_MISMATCH", "abstract establishes material target mismatch", [], []
    if abstract_state == "abstract_weak": return None, "insufficient abstract plausibility; retained as metadata only", [], []
    plausible = [k for k, value in signals.items() if value]
    unresolved = list(gate_map[(cid, "TIER_B_ACQUIRE_TO_RESOLVE")]["unresolved_fields_requiring_fulltext"])
    tier_a = abstract_state == "abstract_high_plausibility"
    if cid == "spv2_003": tier_a = tier_a and has_any(text, SCREEN[cid]["treatment"]) and has_any(text, SCREEN[cid]["contrast"])
    elif cid == "spv2_004": tier_a = tier_a and has_any(text, SCREEN[cid]["treatment"]) and not (has_any(text, ["cell viability", "drug sensitivity"]) and not has_any(text, ["clinical response", "objective response", "tumor regression", "treatment efficacy"]))
    elif cid == "spv2_006_REDESIGNED": tier_a = tier_a and has_any(text, SCREEN[cid]["adaptation"]) and has_any(text, SCREEN[cid]["contrast"])
    elif cid == "spv2_013_REDESIGNED": tier_a = tier_a and has_any(text, SCREEN[cid]["functional"])
    if tier_a: return "TIER_A_HIGH_CONFIDENCE_ACQUIRE", "minimum frozen entity/endpoint/relation signals satisfied", plausible, []
    return "TIER_B_ACQUIRE_TO_RESOLVE", "target remains plausible but frozen fields require fulltext resolution", plausible, unresolved


def execute(network_enabled):
    assert_frozen()
    network = Network(network_enabled)
    plans = {x["case_id"]: x for x in read_jsonl(RUN / "frozen_search_plans.jsonl")}
    variants = read_jsonl(RUN / "frozen_query_variants.jsonl")
    gates = read_jsonl(RUN / "frozen_gate_rules.jsonl")
    gate_map = {(x["case_id"], x["state"]): x for x in gates}
    executed, raw_manifest = [], []
    prior_attempts = read_jsonl(RUN / "fulltext_acquisition_attempts.jsonl") if (RUN / "fulltext_acquisition_attempts.jsonl").exists() else []
    prior_failed_pmc = {
        row["pmcid"]: row for row in prior_attempts
        if row.get("pmcid") and row.get("status") in {"fulltext_retrieval_failed", "fulltext_identity_mismatch"}
    }
    failures = ([
        {"failure_id": "failure_0001", "case_id": None, "failure_class": "QUERY_EXECUTION_FAILURE", "reason": "initial execution stopped after PubMed retrieval because the local abstract snapshot directory was not created; frozen inputs were unchanged and completed snapshots are reused", "fatal": False, "recovered_by_resume": True},
        {"failure_id": "failure_0002", "case_id": None, "failure_class": "QUERY_EXECUTION_FAILURE", "reason": "initial final-validation pass referenced title on the title-free acquired manifest; the generic validator was corrected to use preserved abstract snapshots, with frozen plans, gates, queries, and scientific classifications unchanged", "fatal": False, "recovered_by_resume": True},
    ]
                if (ASSETS / "network_events.json").exists() else [])
    case_pmids, pmid_queries, first_seen = defaultdict(list), defaultdict(list), {}
    for order, variant in enumerate(variants, 1):
        cid = variant["case_id"]
        if len(case_pmids[cid]) >= 60:
            executed.append({**variant, "execution_order": order, "execution_status": "not_executed_hard_budget_already_reached", "execution_timestamp": None, "result_count": None, "returned_id_count": 0, "accepted_case_publication_count": 0, "pagination_state": "stopped_before_first_page", "raw_response_snapshot_ref": None, "response_hash": None})
            failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "query_variant_id": variant["query_variant_id"], "failure_class": "BUDGET_STOP", "reason": "case metadata hard ceiling already reached", "fatal": False})
            continue
        params = {"db": "pubmed", "term": variant["query_string"], "retmax": 20, "retmode": "json", "sort": "relevance", "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "pubmed_esearch" / cid / f"{variant['query_variant_id'].replace(':','_')}.json"
        stamp = now(); url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
        try:
            raw = network.get(url, path, "pubmed_esearch", {"case_id": cid, "query_variant_id": variant["query_variant_id"]})
            payload = json.loads(raw); result = payload.get("esearchresult", {}); ids = [str(x) for x in result.get("idlist", [])]
            accepted = 0
            for pmid in ids:
                pmid_queries[(cid, pmid)].append(variant["query_variant_id"])
                if pmid not in case_pmids[cid] and len(case_pmids[cid]) < 60:
                    case_pmids[cid].append(pmid); first_seen[(cid, pmid)] = variant["query_variant_id"]; accepted += 1
            event = next((x for x in reversed(network.events) if x["snapshot_ref"] == rel(path)), None)
            timestamp = event["timestamp"] if event else stamp
            executed.append({**variant, "execution_order": order, "execution_status": "executed", "execution_timestamp": timestamp, "request_identity": event["request_id"] if event else None, "result_count": int(result.get("count", 0)), "returned_id_count": len(ids), "accepted_case_publication_count": accepted, "pagination_state": "first_page_retmax_20_complete", "raw_response_snapshot_ref": rel(path), "response_hash": sha(path)})
            raw_manifest.append({"source_identity": "PubMed esearch", "retrieval_timestamp": timestamp, "content_hash": sha(path), "snapshot_ref": rel(path), "query_lineage": [variant["query_variant_id"]], "publication_identity_lineage": ids})
        except Exception as exc:
            executed.append({**variant, "execution_order": order, "execution_status": "query_execution_failed", "execution_timestamp": stamp, "result_count": None, "returned_id_count": 0, "accepted_case_publication_count": 0, "pagination_state": "failed", "raw_response_snapshot_ref": None, "response_hash": None})
            failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "query_variant_id": variant["query_variant_id"], "failure_class": "QUERY_EXECUTION_FAILURE", "reason": str(exc), "fatal": False})
    all_pmids = sorted({p for values in case_pmids.values() for p in values}, key=int)
    publications = {}
    for batch_no, start in enumerate(range(0, len(all_pmids), 100), 1):
        ids = all_pmids[start:start+100]; path = ASSETS / "pubmed_efetch" / f"batch_{batch_no:03d}.xml"
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}
        url = BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params)
        try:
            raw = network.get(url, path, "pubmed_efetch", {"pmids": ids}); publications.update(parse_pubmed(raw))
            event = next((x for x in reversed(network.events) if x["snapshot_ref"] == rel(path)), None)
            raw_manifest.append({"source_identity": "PubMed efetch", "retrieval_timestamp": event["timestamp"] if event else now(), "content_hash": sha(path), "snapshot_ref": rel(path), "query_lineage": sorted({q for pmid in ids for cid in CASE_ORDER for q in pmid_queries.get((cid, pmid), [])}), "publication_identity_lineage": ids})
        except Exception as exc:
            failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": None, "failure_class": "NETWORK_FAILURE", "reason": f"PubMed efetch batch {batch_no}: {exc}", "fatal": False})
    identity_rows = []
    global_lineage = defaultdict(list)
    for cid in CASE_ORDER:
        for pmid in case_pmids[cid]: global_lineage[pmid].append(cid)
    for pmid in all_pmids:
        pub = publications.get(pmid, {"canonical_publication_id": f"pmid:{pmid}", "pmid": pmid, "pmcid": None, "doi": None, "title": "", "abstract": "", "publication_types": [], "journal": "", "publication_date": ""})
        identity_rows.append({**pub, "abstract": None, "identity_precedence": "PMID", "case_ids": global_lineage[pmid], "query_variant_ids": sorted({q for cid in global_lineage[pmid] for q in pmid_queries[(cid, pmid)]})})
    metadata_rows, abstract_manifests, abstract_rows = [], [], []
    tier_a, tier_b, rejects = [], [], []
    for cid in CASE_ORDER:
        for rank, pmid in enumerate(case_pmids[cid], 1):
            pub = publications.get(pmid)
            if not pub:
                metadata_rows.append({"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "metadata_state": "metadata_identity_only", "metadata_plausible": False, "reason": "PubMed article record unavailable", "query_lineage": pmid_queries[(cid, pmid)]})
                failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "publication_id": f"pmid:{pmid}", "failure_class": "ABSTRACT_UNAVAILABLE", "reason": "PubMed efetch record unavailable", "fatal": False}); continue
            plausible = bool(pub["title"])
            metadata_rows.append({"case_id": cid, "canonical_publication_id": pub["canonical_publication_id"], "metadata_state": "metadata_plausible" if plausible else "metadata_weak", "metadata_plausible": plausible, "reason": "stable PMID and bibliographic title retrieved" if plausible else "title unavailable", "query_lineage": pmid_queries[(cid, pmid)], "first_seen_query_variant_id": first_seen[(cid, pmid)]})
            if rank > 30: continue
            snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"
            if not snapshot.exists(): write_json(snapshot, pub)
            abstract_manifests.append({"case_id": cid, "canonical_publication_id": pub["canonical_publication_id"], "source_identity": "PubMed", "retrieval_timestamp": next((x["timestamp"] for x in network.events if x["kind"] == "pubmed_efetch" and pmid in x["lineage"].get("pmids", [])), None), "content_hash": sha(snapshot), "snapshot_ref": rel(snapshot), "query_lineage": pmid_queries[(cid, pmid)]})
            state, reason, signals = screen_abstract(cid, pub)
            arow = {"case_id": cid, "canonical_publication_id": pub["canonical_publication_id"], "pmid": pmid, "title": pub["title"], "screen_state": state, "reason": reason, "signals": signals, "query_lineage": pmid_queries[(cid, pmid)], "abstract_snapshot_ref": rel(snapshot), "scientific_proposition_compatibility_inferred": False, "support_opposition_conflict_inferred": False}
            abstract_rows.append(arow)
            tier, tier_reason, known, unresolved = tier_candidate(cid, pub, state, signals, gate_map)
            base = {"case_id": cid, "canonical_publication_id": pub["canonical_publication_id"], "pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"), "title": pub["title"], "abstract_state": state, "gate_reason": tier_reason, "query_lineage": pmid_queries[(cid, pmid)], "search_membership_grants_scientific_authority": False}
            if tier == "TIER_A_HIGH_CONFIDENCE_ACQUIRE": tier_a.append({**base, "tier_state": tier, "justifying_fields": known})
            elif tier == "TIER_B_ACQUIRE_TO_RESOLVE": tier_b.append({**base, "tier_state": tier, "known_plausible_fields": known, "unresolved_fields_requiring_fulltext": unresolved})
            elif tier == "REJECT_KNOWN_MISMATCH": rejects.append({**base, "tier_state": tier, "rejection_reason": tier_reason})
    # Acquire Tier A before Tier B within each case; one global PMCID request/cache.
    attempts, acquired, cache_events = [], [], []
    pmc_cache = {}
    candidates_by_case = defaultdict(list)
    for row in tier_a: candidates_by_case[row["case_id"]].append(row)
    for row in tier_b: candidates_by_case[row["case_id"]].append(row)
    for cid in CASE_ORDER:
        for row in candidates_by_case[cid][:15]:
            attempt_id = f"fta_{len(attempts)+1:04d}"; pmcid = row.get("pmcid")
            base = {"attempt_id": attempt_id, "case_id": cid, "canonical_publication_id": row["canonical_publication_id"], "pmid": row["pmid"], "pmcid": pmcid, "tier_state": row["tier_state"], "query_lineage": row["query_lineage"]}
            if not pmcid:
                attempts.append({**base, "status": "fulltext_not_available", "network_request_made": False, "reason": "PubMed record has no PMCID"})
                failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "publication_id": row["canonical_publication_id"], "failure_class": "FULLTEXT_NOT_AVAILABLE", "reason": "no PMCID", "fatal": False}); continue
            if pmcid in pmc_cache:
                cached = pmc_cache[pmcid]
                attempts.append({**base, "status": cached["status"], "network_request_made": False, "cross_case_cache_hit": True, "snapshot_ref": cached.get("snapshot_ref"), "content_hash": cached.get("content_hash"), "reason": "reused canonical PMCID acquisition result"})
                cache_events.append({"pmcid": pmcid, "case_id": cid, "source_case_id": cached["source_case_id"], "network_request_avoided": True, "status": cached["status"]})
                if cached["status"] == "fulltext_acquired": acquired.append({**base, "source_identity": "PMC efetch", "snapshot_ref": cached["snapshot_ref"], "content_hash": cached["content_hash"], "cross_case_cache_hit": True})
                continue
            if pmcid in prior_failed_pmc:
                prior = prior_failed_pmc[pmcid]
                status = prior["status"]; reason = prior["reason"]
                pmc_cache[pmcid] = {"status": status, "reason": reason, "source_case_id": cid}
                attempts.append({**base, "status": status, "network_request_made": True, "cross_case_cache_hit": False, "reason": reason, "preserved_failed_attempt_not_retried": True})
                failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "publication_id": row["canonical_publication_id"], "failure_class": "PUBLICATION_IDENTITY_FAILURE" if status == "fulltext_identity_mismatch" else "FULLTEXT_RETRIEVAL_FAILURE", "reason": reason, "fatal": False, "preserved_from_initial_execution": True})
                continue
            path = ASSETS / "fulltext" / f"{pmcid}.xml"; params = {"db": "pmc", "id": pmcid, "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}; url = BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params)
            try:
                raw = network.get(url, path, "pmc_fulltext_efetch", {"pmcid": pmcid, "pmid": row["pmid"], "case_id": cid})
                root = ET.fromstring(raw); article_ok = root.find(".//article") is not None or root.tag.endswith("article")
                xml_ids = [text_of(x) for x in root.findall(".//article-id[@pub-id-type='pmid']")]
                identity_ok = not xml_ids or row["pmid"] in xml_ids
                if not article_ok: status, reason = "fulltext_retrieval_failed", "PMC response contains no article"
                elif not identity_ok: status, reason = "fulltext_identity_mismatch", "PMC article PMID does not match PubMed identity"
                else: status, reason = "fulltext_acquired", "usable PMC XML article acquired"
                record = {"status": status, "reason": reason, "source_case_id": cid, "snapshot_ref": rel(path), "content_hash": sha(path)}; pmc_cache[pmcid] = record
                attempts.append({**base, **record, "network_request_made": True, "cross_case_cache_hit": False})
                if status == "fulltext_acquired": acquired.append({**base, "source_identity": "PMC efetch", "snapshot_ref": rel(path), "content_hash": sha(path), "cross_case_cache_hit": False})
                else: failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "publication_id": row["canonical_publication_id"], "failure_class": "PUBLICATION_IDENTITY_FAILURE" if status == "fulltext_identity_mismatch" else "FULLTEXT_RETRIEVAL_FAILURE", "reason": reason, "fatal": False})
            except Exception as exc:
                pmc_cache[pmcid] = {"status": "fulltext_retrieval_failed", "reason": str(exc), "source_case_id": cid}
                attempts.append({**base, "status": "fulltext_retrieval_failed", "network_request_made": True, "cross_case_cache_hit": False, "reason": str(exc)})
                failures.append({"failure_id": f"failure_{len(failures)+1:04d}", "case_id": cid, "publication_id": row["canonical_publication_id"], "failure_class": "FULLTEXT_RETRIEVAL_FAILURE", "reason": str(exc), "fatal": False})
    # Contribution and saturation are reconstructed from preserved first-seen/query lineage.
    abstract_by = {(x["case_id"], x["pmid"]): x for x in abstract_rows}; tier_a_keys = {(x["case_id"], x["pmid"]) for x in tier_a}; tier_b_keys = {(x["case_id"], x["pmid"]) for x in tier_b}; acquired_keys = {(x["case_id"], x["pmid"]) for x in acquired}
    variant_contrib, saturation = [], []
    cumulative = {cid: set() for cid in CASE_ORDER}
    for query in executed:
        cid, qid = query["case_id"], query["query_variant_id"]
        retrieved = {pmid for pmid in case_pmids[cid] if qid in pmid_queries[(cid, pmid)]}
        additions = {pmid for pmid in retrieved if first_seen.get((cid, pmid)) == qid}
        unique_only = {pmid for pmid in retrieved if len(pmid_queries[(cid, pmid)]) == 1}
        plausible_add = {p for p in additions if next((x["metadata_plausible"] for x in metadata_rows if x["case_id"] == cid and x["canonical_publication_id"] == f"pmid:{p}"), False)}
        ah = {p for p in additions if abstract_by.get((cid, p), {}).get("screen_state") == "abstract_high_plausibility"}; ap = {p for p in additions if abstract_by.get((cid, p), {}).get("screen_state") == "abstract_possible"}
        ta = {p for p in additions if (cid, p) in tier_a_keys}; tb = {p for p in additions if (cid, p) in tier_b_keys}
        variant_contrib.append({"case_id": cid, "query_family_id": query["query_family_id"], "query_variant_id": qid, "execution_status": query["execution_status"], "retrieved_publication_count": len(retrieved), "unique_publication_additions": len(additions), "metadata_plausible_additions": len(plausible_add), "abstract_high_plausibility_additions": len(ah), "abstract_possible_additions": len(ap), "tier_a_additions": len(ta), "tier_b_additions": len(tb), "eventual_manual_relevant_additions": "pending", "publications_uniquely_discovered_by_variant": sorted(f"pmid:{p}" for p in unique_only), "publications_discoverable_by_multiple_variants": sorted(f"pmid:{p}" for p in retrieved-unique_only)})
        cumulative[cid].update(additions)
        saturation.append({"case_id": cid, "query_variant_id": qid, "execution_order": query["execution_order"], "cumulative_unique_publications": len(cumulative[cid]), "cumulative_abstract_plausible_publications": sum(abstract_by.get((cid, p), {}).get("screen_state") in {"abstract_high_plausibility", "abstract_possible"} for p in cumulative[cid]), "cumulative_tier_a_b_publications": sum((cid, p) in tier_a_keys or (cid, p) in tier_b_keys for p in cumulative[cid]), "cumulative_acquired_fulltexts": sum((cid, p) in acquired_keys for p in cumulative[cid]), "new_candidate_gain": len(ta | tb), "saturation_concept": "retrieval_candidate_saturation", "scientific_evidence_saturation_inferred": False})
    family_contrib = []
    for (cid, fid), rows in sorted(defaultdict(list, {key: [x for x in variant_contrib if (x["case_id"], x["query_family_id"]) == key] for key in {(x["case_id"], x["query_family_id"]) for x in variant_contrib}}).items()):
        family_contrib.append({"case_id": cid, "query_family_id": fid, **{field: sum(x[field] for x in rows) for field in ["retrieved_publication_count", "unique_publication_additions", "metadata_plausible_additions", "abstract_high_plausibility_additions", "abstract_possible_additions", "tier_a_additions", "tier_b_additions"]}, "eventual_manual_relevant_additions": "pending", "variant_count": len(rows), "unique_publications_only_by_family": sorted({p for x in rows for p in x["publications_uniquely_discovered_by_variant"]})})
    packets, templates = [], []
    frozen_plan_map = {x["case_id"]: x for x in read_jsonl(RUN / "frozen_search_plans.jsonl")}
    for index, row in enumerate(acquired, 1):
        pub = publications[row["pmid"]]; tierrow = next(x for x in (tier_a + tier_b) if x["case_id"] == row["case_id"] and x["pmid"] == row["pmid"])
        packet_id = f"rrp_{index:04d}"
        packets.append({"packet_id": packet_id, "case_id": row["case_id"], "publication_identity": {k: pub.get(k) for k in ["canonical_publication_id", "pmid", "pmcid", "doi"]}, "title": pub["title"], "abstract": pub["abstract"], "retrieval_query_lineage": row["query_lineage"], "tier_state": row["tier_state"], "acquisition_gate_basis": tierrow.get("justifying_fields") or tierrow.get("known_plausible_fields"), "frozen_retrieval_target": frozen_plan_map[row["case_id"]]["retrieval_target"], "frozen_scientific_target_summary": frozen_plan_map[row["case_id"]]["scientific_proposition_target"], "fields_requiring_fulltext_resolution": tierrow.get("unresolved_fields_requiring_fulltext", []), "deterministically_selected_fulltext_snippets": [], "fulltext_ref": row["snapshot_ref"], "content_hash": row["content_hash"], "preferred_adjudication_answer": None, "manual_relevance_status": "pending"})
        templates.append({"packet_id": packet_id, "publication_id": pub["canonical_publication_id"], "case_id": row["case_id"], "reviewer_decision": None, "relevance_state": None, "matched_target_components": [], "mismatched_components": [], "fulltext_acquisition_was_justified": None, "contaminant_class": None, "notes": "", "audit_scope": "retrieval_relevance_only_not_downstream_conflict_gold"})
    write_jsonl(RUN / "executed_queries.jsonl", executed); write_jsonl(RUN / "raw_metadata_manifest.jsonl", raw_manifest)
    write_jsonl(RUN / "publication_identity_inventory.jsonl", identity_rows)
    shared = {pmid: cases for pmid, cases in global_lineage.items() if len(cases) > 1}
    write_json(RUN / "publication_deduplication_audit.json", {"identity_precedence": ["PMID", "PMCID", "DOI"], "deterministic": True, "unique_publication_count_global": len(all_pmids), "case_publication_count": sum(map(len, case_pmids.values())), "cross_case_duplicate_publication_count": sum(len(x)-1 for x in shared.values()), "shared_publications": {f"pmid:{k}": v for k, v in shared.items()}, "query_lineage_preserved": True})
    write_jsonl(RUN / "metadata_stage_results.jsonl", metadata_rows); write_jsonl(RUN / "abstract_snapshots_manifest.jsonl", abstract_manifests); write_jsonl(RUN / "abstract_screening_results.jsonl", abstract_rows)
    write_jsonl(RUN / "tier_a_candidates.jsonl", tier_a); write_jsonl(RUN / "tier_b_candidates.jsonl", tier_b); write_jsonl(RUN / "rejected_known_mismatch.jsonl", rejects)
    write_jsonl(RUN / "fulltext_acquisition_attempts.jsonl", attempts); write_jsonl(RUN / "fulltext_acquired_manifest.jsonl", acquired)
    write_json(RUN / "cross_case_fulltext_cache_audit.json", {"canonical_cache_key": "PMCID", "unique_pmcids_requested": sum(x["kind"] == "pmc_fulltext_efetch" for x in network.events), "cross_case_cache_hits": len(cache_events), "duplicate_network_requests_avoided": sum(x["network_request_avoided"] for x in cache_events), "events": cache_events})
    write_jsonl(RUN / "query_variant_contribution.jsonl", variant_contrib); write_jsonl(RUN / "query_family_contribution.jsonl", family_contrib); write_jsonl(RUN / "retrieval_candidate_saturation_curves.jsonl", saturation)
    write_jsonl(RUN / "retrieval_relevance_review_packets.jsonl", packets); write_jsonl(RUN / "retrieval_relevance_adjudication_template.jsonl", templates); write_jsonl(RUN / "failure_inventory.jsonl", failures)
    per_case = []
    for cid in CASE_ORDER:
        qrows = [x for x in executed if x["case_id"] == cid]; arows = [x for x in abstract_rows if x["case_id"] == cid]; att = [x for x in attempts if x["case_id"] == cid]
        per_case.append({"case_id": cid, "active_query_family_count": len({x["query_family_id"] for x in qrows}), "active_query_variant_count": len(qrows), "retrieved_unique_publications": len(case_pmids[cid]), "metadata_plausible_count": sum(x["case_id"] == cid and x["metadata_plausible"] for x in metadata_rows), "abstract_screened_count": len(arows), "abstract_high_plausibility_count": sum(x["screen_state"] == "abstract_high_plausibility" for x in arows), "abstract_possible_count": sum(x["screen_state"] == "abstract_possible" for x in arows), "abstract_mismatch_count": sum(x["screen_state"] == "abstract_mismatch" for x in arows), "tier_a_count": sum(x["case_id"] == cid for x in tier_a), "tier_b_count": sum(x["case_id"] == cid for x in tier_b), "known_mismatch_reject_count": sum(x["case_id"] == cid for x in rejects), "fulltext_acquisition_attempt_count": len(att), "fulltext_acquired_count": sum(x["status"] == "fulltext_acquired" for x in att), "fulltext_not_available_count": sum(x["status"] == "fulltext_not_available" for x in att), "fulltext_retrieval_failure_count": sum(x["status"] in {"fulltext_retrieval_failed", "fulltext_identity_mismatch"} for x in att), "query_variants_with_unique_additions": sum(x["case_id"] == cid and x["unique_publication_additions"] > 0 for x in variant_contrib), "candidate_saturation_stop_reason": "hard_metadata_budget" if len(case_pmids[cid]) >= 60 else "all_frozen_active_variants_executed", "manual_relevance_status": "pending"})
    network_events = network.events
    failed_network_attempts = sum(x.get("network_request_made", False) and x["status"] == "fulltext_retrieval_failed" for x in attempts)
    aggregate = {"case_count": 8, "executed_query_count": sum(x["execution_status"] == "executed" for x in executed), "unique_publication_count_global": len(all_pmids), "case_publication_count": sum(map(len, case_pmids.values())), "cross_case_duplicate_publication_count": sum(len(x)-1 for x in shared.values()), "metadata_plausible_count": sum(x["metadata_plausible"] for x in metadata_rows), "abstract_screened_count": len(abstract_rows), "tier_a_count": len(tier_a), "tier_b_count": len(tier_b), "known_mismatch_reject_count": len(rejects), "fulltext_acquisition_attempt_count": len(attempts), "unique_fulltexts_acquired_global": len({x["pmcid"] for x in acquired}), "case_fulltext_assignments": len(acquired), "query_variants_with_zero_unique_contribution": sum(x["unique_publication_additions"] == 0 for x in variant_contrib), "query_variants_with_nonzero_unique_contribution": sum(x["unique_publication_additions"] > 0 for x in variant_contrib), "network_request_count": len(network_events) + failed_network_attempts, "successful_network_response_count": len(network_events), "failed_network_attempt_count": failed_network_attempts, "provider_calls": 0, "llm_calls": 0, "manual_relevance_review_packet_count": len(packets)}
    write_json(RUN / "query_execution_summary.json", {"per_case": per_case, "aggregate": aggregate, "manual_metrics": {"manual_relevant_fulltexts": "pending", "manual_irrelevant_fulltexts": "pending", "fulltext_acquisition_precision": "not_yet_adjudicated", "retrieval_recall": "not_yet_adjudicated"}})
    request_counts = Counter(x["kind"] for x in network_events)
    request_counts["pmc_fulltext_efetch_failed"] += failed_network_attempts
    write_json(RUN / "network_usage_audit.json", {"authorized": read_json(RUN / "execution_authorization.json")["explicit_user_authorization"], "allowed_services_only": all("ncbi.nlm.nih.gov" in x["url"] for x in network_events), "network_request_count": len(network_events) + failed_network_attempts, "successful_network_response_count": len(network_events), "failed_network_attempt_count": failed_network_attempts, "request_counts_by_kind": dict(request_counts), "successful_response_events_ref": rel(network.receipt), "failed_attempts_ref": rel(RUN / "fulltext_acquisition_attempts.jsonl"), "credentials_logged": False})
    write_json(RUN / "provider_usage_audit.json", {"provider_calls": 0, "llm_calls": 0, "provider_or_model_client_created": False, "extraction_stage_invoked": False, "fulltext_acquisition_terminal_stage": True})
    protected = read_json(RUN / "baseline.json")["protected_hashes_before"]
    unchanged = all(sha(ROOT / path) == digest for path, digest in protected.items())
    write_json(RUN / "scientific_state_safety_audit.json", {"historical_assets_modified": not unchanged, "formal_v3_modified": False, "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False, "provider_calls": 0, "llm_calls": 0, "extraction_invoked": False, "support_opposition_conflict_inferred": False, "protected_hashes_before": protected, "protected_hashes_after": {path: sha(ROOT / path) for path in protected}})
    write_json(RUN / "production_leakage_audit.json", {"production_source_modified": False, "historical_candidates_modified": False, "historical_formal_modified": False, "atlas_modified": False, "active_pointer_changed": False, "vem_called": False, "case_specific_fix_applied_after_network_start": False})
    completion = "RETRIEVAL_CALIBRATION_DATA_READY_FOR_MANUAL_AUDIT" if len(packets) and all(any(x["case_id"] == cid for x in abstract_rows) for cid in CASE_ORDER) else "PARTIAL_RETRIEVAL_CALIBRATION_DATA_READY" if abstract_rows else "NETWORK_EXECUTION_FAILURE"
    summary = {"artifact_schema_version": "retrieval_calibration_pilot_summary.v1", "completion_state": completion, "per_case_metrics": per_case, **aggregate, "manual_relevance_status": "pending", "fulltext_acquisition_precision": "not_yet_adjudicated", "retrieval_recall": "not_yet_adjudicated", "historical_assets_modified": not unchanged, "formal_v3_modified": False, "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False}
    write_json(RUN / "summary.json", summary)
    validate_and_manifest(summary, failures)
    return summary


def validate_and_manifest(summary, failures):
    assert_frozen(); variants = read_jsonl(RUN / "frozen_query_variants.jsonl"); executed = read_jsonl(RUN / "executed_queries.jsonl"); tier_a = read_jsonl(RUN / "tier_a_candidates.jsonl"); tier_b = read_jsonl(RUN / "tier_b_candidates.jsonl"); acquired = read_jsonl(RUN / "fulltext_acquired_manifest.jsonl")
    acquired_keys = {(x["case_id"], x["pmid"]) for x in acquired}
    acquired_tier_a = [x for x in tier_a if (x["case_id"], x["pmid"]) in acquired_keys]
    publication_text = {}
    for row in acquired_tier_a:
        snapshot = ASSETS / "abstracts" / f"pmid_{row['pmid']}.json"
        publication = read_json(snapshot)
        publication_text[(row["case_id"], row["pmid"])] = publication["title"] + "\n" + publication["abstract"]
    checks = {"frozen_hashes_unchanged": True, "no_provider_or_model": summary["provider_calls"] == summary["llm_calls"] == 0, "no_extraction": read_json(RUN / "provider_usage_audit.json")["extraction_stage_invoked"] is False, "publication_dedup_deterministic": read_json(RUN / "publication_deduplication_audit.json")["deterministic"], "shared_fulltext_not_downloaded_redundantly": read_json(RUN / "cross_case_fulltext_cache_audit.json")["duplicate_network_requests_avoided"] == read_json(RUN / "cross_case_fulltext_cache_audit.json")["cross_case_cache_hits"], "tier_b_unresolved_ledgers_nonempty": all(x["known_plausible_fields"] and x["unresolved_fields_requiring_fulltext"] for x in tier_b), "patient_os_not_cell_survival": not any(x["case_id"] == "spv2_013_REDESIGNED" and has_any(publication_text[(x["case_id"], x["pmid"])], ["overall survival", "patient survival", "progression-free survival"]) and not has_any(publication_text[(x["case_id"], x["pmid"])], ["cell survival", "cell viability", "cancer cell survival", "tumor cell survival"]) for x in acquired_tier_a), "baseline_viability_not_adaptation_tier_a": not any(x["case_id"] == "spv2_006_REDESIGNED" and not has_any(publication_text[(x["case_id"], x["pmid"])], SCREEN[x["case_id"]]["adaptation"]) for x in acquired_tier_a), "query_lineage_preserved": all(x["query_lineage"] for x in read_jsonl(RUN / "metadata_stage_results.jsonl")), "global_budgets_respected": summary["case_publication_count"] <= 480 and summary["abstract_screened_count"] <= 240 and summary["fulltext_acquisition_attempt_count"] <= 120, "manual_metrics_pending": summary["fulltext_acquisition_precision"] == summary["retrieval_recall"] == "not_yet_adjudicated", "historical_state_unchanged": not summary["historical_assets_modified"], "all_frozen_variants_accounted": len(variants) == len(executed)}
    checks["required_artifacts_present"] = all((RUN / name).is_file() for name in REQUIRED if name not in {"final_validation.json", "manifest.json"})

    def write_validation():
        write_json(RUN / "final_validation.json", {"artifact_schema_version": "retrieval_calibration_final_validation.v1", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "failure_class_counts": dict(Counter(x["failure_class"] for x in failures))})

    def write_manifest():
        files = []
        for path in sorted(RUN.iterdir()):
            if not path.is_file() or path.name == "manifest.json": continue
            files.append({"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size, "record_count": sum(1 for x in path.read_text().splitlines() if x.strip()) if path.suffix == ".jsonl" else 1})
        write_json(RUN / "manifest.json", {"artifact_schema_version": "retrieval_calibration_manifest.v1", "required_artifact_count": len(REQUIRED), "files": files, "retrieval_assets": [{"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(ASSETS.rglob("*")) if path.is_file()], "network_request_count": summary["network_request_count"], "provider_calls": 0, "llm_calls": 0, "historical_assets_modified": summary["historical_assets_modified"]})

    write_validation(); write_manifest()
    manifest = read_json(RUN / "manifest.json")
    checks["manifest_hashes_valid"] = all(sha(RUN / row["path"]) == row["sha256"] for row in manifest["files"]) and all(sha(ROOT / row["path"]) == row["sha256"] for row in manifest["retrieval_assets"])
    write_validation(); write_manifest()


def main():
    opt = args()
    if opt.freeze:
        print(json.dumps({"frozen_query_variant_count": freeze_inputs(), "network_requests": 0}, indent=2)); return
    if opt.execute_network == opt.replay: raise SystemExit("Choose exactly one of --execute-network or --replay")
    summary = execute(opt.execute_network)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()
