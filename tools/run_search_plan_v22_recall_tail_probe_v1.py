#!/usr/bin/env python3
"""Continue three frozen PubMed searches from depth 60 to at most 120.

Only NCBI PubMed/PMC E-utilities are used.  The frozen v2.1 abstract screen
and frozen v2.2 candidate gate are imported without modification.  No provider,
LLM, extraction, Formal, Atlas, or production code is invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, screen_abstract, text_of
    from search_plan_v22_candidate_gates import build_target_contract, evaluate
except ModuleNotFoundError:  # Support package-style imports in focused tests.
    from tools.run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, screen_abstract, text_of
    from tools.search_plan_v22_candidate_gates import build_target_contract, evaluate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
V22 = ROOT / "runs/20260907_search_plan_v22_failure_decomposition_counterfactual_replay_offline"
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"
ASSETS = RUN / "retrieval_assets"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CASES = ["spv2_017", "spv2_016", "spv2_003"]
OVERLAYS = [ROOT / f"runs/20260907_retrieval_relevance_adjudication_batch_{i:02d}_v1_offline" for i in range(1, 6)]
REQUIRED = [
    "baseline.json", "probe_case_inventory.json", "original_retrieval_state.jsonl",
    "continued_query_executions.jsonl", "tail_metadata_inventory.jsonl",
    "tail_abstract_screening.jsonl", "tail_v22_gate_outputs.jsonl",
    "tail_fulltext_acquisition_attempts.jsonl", "tail_fulltext_manifest.jsonl",
    "tail_review_packets.jsonl", "depth_bin_metrics.jsonl", "query_tail_contribution.jsonl",
    "tail_saturation_audit.jsonl", "budget_recommendation.json", "network_usage_audit.json",
    "provider_usage_audit.json", "scientific_state_safety_audit.json", "final_validation.json",
    "manifest.json", "summary.json",
]
PROTECTED_SCOPES = [
    "src", "configs", "runs", "runs_archive", "data", "system_b_inputs", "system_b_outputs",
    "system_b_replays", "case_bundles", "case_bundles_preserved", "preserved_case_bundles",
    "reference_inputs", "search_plan_reviews", "scripts", "alembic", "docker", "batch_runs",
    "archived_experiments", "tools",
]


def now(): return datetime.now(timezone.utc).isoformat()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    # ASCII escaping keeps U+2028/U+2029 embedded in PubMed text from becoming
    # physical JSONL line separators for common splitlines()-based readers.
    path.write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()
def rel(path): return str(Path(path).resolve().relative_to(ROOT))
def objhash(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def protected_hashes():
    result = {}
    for scope in PROTECTED_SCOPES:
        for path in sorted((ROOT / scope).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.is_relative_to(RUN): continue
            result[rel(path)] = sha(path)
    for path in sorted(ROOT.iterdir()):
        if path.is_file(): result[rel(path)] = sha(path)
    return result


class Network:
    def __init__(self, execute):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        receipt = readj(self.receipt) if self.receipt.exists() else {}
        self.events = receipt.get("events", [])
        self.failures = receipt.get("failures", [])

    def get(self, url, path, kind, lineage):
        path = Path(path)
        if path.exists(): return path.read_bytes()
        if not self.execute: raise FileNotFoundError(path)
        request = urllib.request.Request(url, headers={"User-Agent": "conflict-oriented-discovery-engine-tail-probe/1.0"})
        stamp = now()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read(); status = response.status; content_type = response.headers.get("Content-Type")
        except Exception as exc:
            self.failures.append({"kind": kind, "timestamp": stamp, "url": url, "lineage": lineage,
                                  "error_type": type(exc).__name__, "error": str(exc)})
            self._save(); raise
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        self.events.append({"request_id": f"tail_ncbi_request_{len(self.events)+1:04d}", "kind": kind,
                            "timestamp": stamp, "url": url, "http_status": status,
                            "content_type": content_type, "snapshot_ref": rel(path),
                            "response_sha256": sha(path), "bytes": len(body), "lineage": lineage})
        self._save(); time.sleep(0.36)
        return body

    def _save(self):
        writej(self.receipt, {"events": self.events, "failures": self.failures,
                              "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0})


def target_contract(case_id, plans, gates, variants):
    target = build_target_contract(plans[case_id], [x for x in gates if x["case_id"] == case_id],
                                   [x for x in variants if x["case_id"] == case_id])
    target["primary_evidence_required"] = True
    target["primary_requirement_authority"] = {
        "policy": "Search Plan v2.2 calibration target primary-evidence requirement frozen before this probe",
        "source_ref": rel(V22 / "search_plan_v22_candidate_contract.json"),
        "source_sha256": sha(V22 / "search_plan_v22_candidate_contract.json"),
        "gate_engine_sha256": sha(ROOT / "tools/search_plan_v22_candidate_gates.py"),
    }
    return target


def source_state():
    files = [SOURCE / "manifest.json", SOURCE / "frozen_search_plans.jsonl",
             SOURCE / "frozen_query_variants.jsonl", SOURCE / "frozen_gate_rules.jsonl",
             SOURCE / "executed_queries.jsonl", SOURCE / "metadata_stage_results.jsonl",
             V22 / "manifest.json", V22 / "search_plan_v22_candidate_contract.json",
             ROOT / "tools/search_plan_v22_candidate_gates.py"]
    return {rel(path): sha(path) for path in files}


def blank_adjudication(packet_id, case_id, publication_id):
    return {"packet_id": packet_id, "case_id": case_id, "publication_id": publication_id,
            "relevance_state": None, "acquisition_decision": None, "matched_target_components": [],
            "mismatched_target_components": [], "fulltext_resolved_fields": [],
            "remaining_unresolved_fields": [], "contaminant_class": None,
            "reviewer_rationale": None, "confidence": None, "reviewer_type": None,
            "reviewer_id_or_label": None, "timestamp": None}


def v22_decision(case_id, publication, targets):
    scientific = {"title": publication.get("title", ""), "abstract": publication.get("abstract", ""),
                  "publication_types": publication.get("publication_types", []), "target": targets[case_id]}
    decision = evaluate(scientific)
    return scientific, decision


def tail_state(depth, bin1, bin2, network_ok):
    """Prespecified diagnostic rule; candidate yield, never literature recall."""
    if not network_ok or depth < 120: return "TAIL_EVIDENCE_INSUFFICIENT"
    total = bin1 + bin2
    if total <= 1: return "TAIL_YIELD_MINIMAL"
    if bin2 >= max(2, bin1 / 2): return "TAIL_YIELD_ACTIVE"
    return "TAIL_YIELD_DECLINING"


def execute(network_enabled):
    if RUN.exists() and any(p.name not in REQUIRED and p.name != "retrieval_assets" for p in RUN.iterdir()):
        raise RuntimeError("Probe run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True); ASSETS.mkdir(parents=True, exist_ok=True)
    protected_before = protected_hashes()
    sources_before = source_state()
    plans = {x["case_id"]: x for x in readl(SOURCE / "frozen_search_plans.jsonl")}
    variants = [x for x in readl(SOURCE / "frozen_query_variants.jsonl") if x["case_id"] in CASES]
    gates = readl(SOURCE / "frozen_gate_rules.jsonl")
    old_exec = {x["query_variant_id"]: x for x in readl(SOURCE / "executed_queries.jsonl") if x["case_id"] in CASES}
    old_metadata = [x for x in readl(SOURCE / "metadata_stage_results.jsonl") if x["case_id"] in CASES]
    old_screens = [x for x in readl(SOURCE / "abstract_screening_results.jsonl") if x["case_id"] in CASES]
    old_identity = {x["pmid"]: x for x in readl(SOURCE / "publication_identity_inventory.jsonl")}
    targets = {case_id: target_contract(case_id, plans, gates, variants) for case_id in CASES}
    gate_hash = sha(ROOT / "tools/search_plan_v22_candidate_gates.py")
    baseline = {"artifact_schema_version": "search_plan_v22_recall_tail_probe_baseline.v1",
                "source_calibration_run": rel(SOURCE), "source_v22_candidate_run": rel(V22),
                "explicit_network_authorization": True,
                "authorization_source": "user message: Network/PubMed/NCBI allowed; OA fulltext allowed <=10/case; metadata <=120/case",
                "allowed_services": ["NCBI PubMed E-utilities", "NCBI PMC E-utilities"],
                "metadata_hard_ceiling_per_case": 120, "additional_abstract_ceiling_per_case": 60,
                "fulltext_selection_ceiling_per_case": 10, "provider_authorized": False,
                "llm_authorized": False, "experimental_extraction_authorized": False,
                "continuation_consistency_limit": "The preserved run has no PubMed WebEnv/cursor. Frozen query text, sort, order, and next retstart are preserved, but the live PubMed relevance index may have shifted since the original first pages.",
                "frozen_source_hashes": sources_before, "protected_tree_digest_before": objhash(protected_before),
                "protected_file_count": len(protected_before),
                "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                           capture_output=True, check=True).stdout.strip()}
    writej(RUN / "baseline.json", baseline)
    network = Network(network_enabled)

    original_by_case = defaultdict(list)
    for row in old_metadata: original_by_case[row["case_id"]].append(row["canonical_publication_id"].split(":", 1)[1])
    if any(len(original_by_case[c]) != 60 for c in CASES): raise RuntimeError("Probe cases do not all have frozen depth 60")
    original_state = []
    eligible = defaultdict(list)
    for variant in variants:
        prior = old_exec[variant["query_variant_id"]]
        reason = None; initial_offset = None
        if prior["execution_status"] == "not_executed_hard_budget_already_reached":
            reason, initial_offset = "budget_stopped_before_first_page", 0
        elif prior["execution_status"] == "executed" and prior.get("result_count", 0) > prior.get("returned_id_count", 0):
            reason, initial_offset = "first_page_not_fully_consumed", prior["returned_id_count"]
        if reason:
            eligible[variant["case_id"]].append({**variant, "continuation_reason": reason,
                                                 "initial_retstart": initial_offset,
                                                 "original_result_count": prior.get("result_count")})
    for cid in CASES:
        original_state.append({"case_id": cid, "original_metadata_depth": len(original_by_case[cid]),
                               "original_abstract_screened_count": sum(x["case_id"] == cid for x in old_screens),
                               "original_query_state_ref": rel(SOURCE / "executed_queries.jsonl"),
                               "original_metadata_state_ref": rel(SOURCE / "metadata_stage_results.jsonl"),
                               "eligible_continuation_variant_ids": [x["query_variant_id"] for x in eligible[cid]],
                               "query_order_preserved": True, "original_records_retrieved_again": False})
    writej(RUN / "probe_case_inventory.json", {"case_count": 3, "case_ids": CASES,
                                               "selection_authority": "user-specified exact probe cases",
                                               "frozen_gate_sha256": gate_hash})
    writel(RUN / "original_retrieval_state.jsonl", original_state)

    case_ordered = {cid: list(original_by_case[cid]) for cid in CASES}
    query_hits = defaultdict(list); first_tail_query = {}; query_runs = []
    for cid in CASES:
        seen = set(case_ordered[cid]); page_round = 0; active = list(eligible[cid])
        while len(case_ordered[cid]) < 120 and active:
            next_active = []
            for item in active:
                if len(case_ordered[cid]) >= 120: break
                offset = item["initial_retstart"] + page_round * 20
                if item.get("original_result_count") is not None and offset >= item["original_result_count"]: continue
                params = {"db": "pubmed", "term": item["query_string"], "retstart": offset,
                          "retmax": 20, "retmode": "json", "sort": "relevance",
                          "tool": "conflict_oriented_discovery_engine"}
                url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
                safe_name = item["query_variant_id"].replace(":", "_")
                path = ASSETS / "pubmed_esearch" / cid / f"{safe_name}__retstart_{offset:04d}.json"
                stamp = now()
                try:
                    raw = network.get(url, path, "pubmed_esearch_continuation",
                                      {"case_id": cid, "query_variant_id": item["query_variant_id"], "retstart": offset})
                    event = next((x for x in network.events if x["snapshot_ref"] == rel(path)), None)
                    stamp = event["timestamp"] if event else stamp
                    result = json.loads(raw).get("esearchresult", {}); ids = [str(x) for x in result.get("idlist", [])]
                    added = []
                    for pmid in ids:
                        if pmid not in query_hits[(cid, item["query_variant_id"])]:
                            query_hits[(cid, item["query_variant_id"])].append(pmid)
                        if pmid not in seen and len(case_ordered[cid]) < 120:
                            seen.add(pmid); case_ordered[cid].append(pmid); added.append(pmid)
                            first_tail_query[(cid, pmid)] = item["query_variant_id"]
                    query_runs.append({"case_id": cid, "query_family_id": item["query_family_id"],
                                       "query_variant_id": item["query_variant_id"], "query_string": item["query_string"],
                                       "continuation_reason": item["continuation_reason"], "retstart": offset,
                                       "retmax": 20, "execution_timestamp": stamp, "execution_status": "executed",
                                       "result_count_at_continuation": int(result.get("count", 0)),
                                       "returned_id_count": len(ids), "new_unique_additions": len(added),
                                       "new_unique_publication_ids": [f"pmid:{x}" for x in added],
                                       "raw_response_snapshot_ref": rel(path), "response_sha256": sha(path),
                                       "original_records_retrieved_again": False})
                    if ids and offset + len(ids) < int(result.get("count", 0)): next_active.append(item)
                except Exception as exc:
                    query_runs.append({"case_id": cid, "query_family_id": item["query_family_id"],
                                       "query_variant_id": item["query_variant_id"], "query_string": item["query_string"],
                                       "continuation_reason": item["continuation_reason"], "retstart": offset,
                                       "retmax": 20, "execution_timestamp": stamp, "execution_status": "failed",
                                       "error_type": type(exc).__name__, "error": str(exc), "new_unique_additions": 0})
            active = next_active; page_round += 1
    writel(RUN / "continued_query_executions.jsonl", query_runs)

    tail_pmids_by_case = {cid: case_ordered[cid][60:] for cid in CASES}
    all_tail_pmids = sorted({p for values in tail_pmids_by_case.values() for p in values}, key=int)
    publications = {}
    for batch, start in enumerate(range(0, len(all_tail_pmids), 100), 1):
        ids = all_tail_pmids[start:start + 100]
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        url = BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params)
        path = ASSETS / "pubmed_efetch" / f"tail_batch_{batch:03d}.xml"
        try: publications.update(parse_pubmed(network.get(url, path, "pubmed_efetch_tail", {"pmids": ids})))
        except Exception: pass

    # Recover all observed query lineage from continuation pages, without new calls.
    lineage = defaultdict(list)
    for cid in CASES:
        for item in eligible[cid]:
            qid = item["query_variant_id"]
            for pmid in query_hits[(cid, qid)]:
                if pmid in tail_pmids_by_case[cid] and qid not in lineage[(cid, pmid)]: lineage[(cid, pmid)].append(qid)
    tail_metadata = []; tail_screens = []; gate_outputs = []; gate_by_key = {}
    for cid in CASES:
        for depth, pmid in enumerate(case_ordered[cid][60:], 61):
            pub = publications.get(pmid, {"canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                                         "pmcid": None, "doi": None, "title": "", "abstract": "",
                                         "publication_types": [], "journal": "", "publication_date": ""})
            qids = lineage[(cid, pmid)] or [first_tail_query[(cid, pmid)]]
            metadata_state = "metadata_plausible" if pub["title"] else "metadata_identity_only"
            tail_metadata.append({"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                                  "metadata_depth": depth, "depth_bin": "61-90" if depth <= 90 else "91-120",
                                  "metadata_state": metadata_state, "title": pub["title"], "journal": pub["journal"],
                                  "publication_date": pub["publication_date"], "publication_types": pub["publication_types"],
                                  "pmcid": pub.get("pmcid"), "doi": pub.get("doi"), "query_lineage": qids,
                                  "first_discovery_query": first_tail_query[(cid, pmid)],
                                  "source_ref": next((x["snapshot_ref"] for x in network.events
                                                      if x["kind"] == "pubmed_efetch_tail" and pmid in x["lineage"]["pmids"]), None)})
            snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"
            writej(snapshot, pub)
            screen_state, reason, signals = screen_abstract(cid, pub)
            tail_screens.append({"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                                 "metadata_depth": depth, "depth_bin": "61-90" if depth <= 90 else "91-120",
                                 "screen_state": screen_state, "reason": reason, "signals": signals,
                                 "query_lineage": qids, "abstract_snapshot_ref": rel(snapshot),
                                 "abstract_snapshot_sha256": sha(snapshot), "frozen_v21_screen_logic": True,
                                 "manual_relevance_state": "pending", "scientific_proposition_compatibility_inferred": False})
            scientific, decision = v22_decision(cid, pub, targets)
            output = {"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                      "metadata_depth": depth, "depth_bin": "61-90" if depth <= 90 else "91-120",
                      "query_lineage": qids, "pre_acquisition_input_sha256": objhash(scientific),
                      "pre_acquisition_evidence_refs": {"abstract": {"path": rel(snapshot), "sha256": sha(snapshot)},
                                                        "publication_metadata": {"path": rel(snapshot), "sha256": sha(snapshot)},
                                                        "frozen_target": {"path": rel(SOURCE / "frozen_search_plans.jsonl"),
                                                                          "sha256": sha(SOURCE / "frozen_search_plans.jsonl"),
                                                                          "selector": f"case_id={cid}"}},
                      **decision}
            gate_outputs.append(output); gate_by_key[(cid, pmid)] = output
    writel(RUN / "tail_metadata_inventory.jsonl", tail_metadata)
    writel(RUN / "tail_abstract_screening.jsonl", tail_screens)
    writel(RUN / "tail_v22_gate_outputs.jsonl", gate_outputs)

    # Existing fulltexts are reused by PMCID.  No text is parsed or extracted.
    old_acquired = readl(SOURCE / "fulltext_acquired_manifest.jsonl")
    fulltext_cache = {x["pmcid"]: {"snapshot_ref": x["snapshot_ref"], "content_hash": x["content_hash"],
                                            "source_case_id": x["case_id"], "source": "preserved_v21_cache"}
                      for x in old_acquired if x.get("pmcid")}
    attempts = []; acquired = []
    for cid in CASES:
        candidates = [x for x in gate_outputs if x["case_id"] == cid and x["state"] in {"TIER_A", "TIER_B"}]
        candidates.sort(key=lambda x: (x["state"] != "TIER_A", x["metadata_depth"]))
        for selected_index, output in enumerate(candidates[:10], 1):
            pmid = output["pmid"]; pub = publications[pmid]; pmcid = pub.get("pmcid")
            base = {"attempt_id": f"tail_fta_{len(attempts)+1:04d}", "case_id": cid,
                    "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid, "pmcid": pmcid,
                    "metadata_depth": output["metadata_depth"], "tier_state": output["state"],
                    "query_lineage": output["query_lineage"], "selection_index_within_case": selected_index,
                    "fulltext_selection_ceiling": 10}
            if not pmcid:
                attempts.append({**base, "status": "fulltext_not_available", "network_request_made": False,
                                 "reason": "PubMed metadata contains no PMCID"}); continue
            if pmcid in fulltext_cache:
                cached = fulltext_cache[pmcid]
                row = {**base, "status": "fulltext_acquired", "network_request_made": False,
                       "cross_probe_cache_hit": True, "reason": "reused canonical PMCID fulltext without network",
                       "snapshot_ref": cached["snapshot_ref"], "content_hash": cached["content_hash"],
                       "source_identity": "PMC efetch", "cache_source": cached["source"]}
                attempts.append(row); acquired.append(row); continue
            path = ASSETS / "fulltext" / f"{pmcid}.xml"
            params = {"db": "pmc", "id": pmcid, "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}
            url = BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params)
            try:
                raw = network.get(url, path, "pmc_fulltext_efetch_tail", {"case_id": cid, "pmid": pmid, "pmcid": pmcid})
                root = ET.fromstring(raw); article_ok = root.find(".//article") is not None or root.tag.endswith("article")
                xml_ids = [text_of(x) for x in root.findall(".//article-id[@pub-id-type='pmid']")]
                identity_ok = not xml_ids or pmid in xml_ids
                if not article_ok: status, reason = "fulltext_retrieval_failed", "PMC response contains no article"
                elif not identity_ok: status, reason = "fulltext_identity_mismatch", "PMC article PMID does not match PubMed identity"
                else: status, reason = "fulltext_acquired", "usable PMC XML article acquired"
                row = {**base, "status": status, "network_request_made": True, "cross_probe_cache_hit": False,
                       "reason": reason, "snapshot_ref": rel(path), "content_hash": sha(path), "source_identity": "PMC efetch"}
                attempts.append(row)
                fulltext_cache[pmcid] = {"snapshot_ref": rel(path), "content_hash": sha(path),
                                        "source_case_id": cid, "source": "current_probe"}
                if status == "fulltext_acquired": acquired.append(row)
            except Exception as exc:
                attempts.append({**base, "status": "fulltext_retrieval_failed", "network_request_made": True,
                                 "reason": str(exc), "error_type": type(exc).__name__})
    writel(RUN / "tail_fulltext_acquisition_attempts.jsonl", attempts)
    writel(RUN / "tail_fulltext_manifest.jsonl", acquired)

    packets = []
    for index, row in enumerate(acquired, 1):
        cid, pmid = row["case_id"], row["pmid"]; pub = publications[pmid]; output = gate_by_key[(cid, pmid)]
        packet_id = f"rrtailv1_{index:04d}"; snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"
        packets.append({"packet_id": packet_id, "review_unit_id": packet_id, "case_id": cid,
                        "ambiguity_tier": plans[cid]["ambiguity_tier"],
                        "retrieval_target": plans[cid]["retrieval_target"],
                        "scientific_proposition_target": plans[cid]["scientific_proposition_target"],
                        "publication_identity": {"pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                                                 "title": pub["title"], "year": pub.get("publication_date"),
                                                 "publication_types": pub.get("publication_types", [])},
                        "retrieval_provenance": {"query_variants": row["query_lineage"],
                                                 "first_discovery_query": first_tail_query[(cid, pmid)],
                                                 "metadata_depth": row["metadata_depth"]},
                        "pre_acquisition_evidence": {"title": pub["title"], "abstract": pub["abstract"],
                                                     "abstract_snapshot_ref": rel(snapshot),
                                                     "abstract_snapshot_sha256": sha(snapshot),
                                                     "tier_state": output["state"], "gate_reasons": output["gates"],
                                                     "known_plausible_fields": output["known_plausible_fields"],
                                                     "unresolved_fields_requiring_fulltext": output["unresolved_fields_requiring_fulltext"],
                                                     "why_fulltext_can_resolve": output["why_fulltext_can_resolve"]},
                        "fulltext_evidence_packet": {"source_ref": row["snapshot_ref"],
                                                     "fulltext_sha256": row["content_hash"], "excerpts": [],
                                                     "experimental_extraction_performed": False},
                        "adjudication": blank_adjudication(packet_id, cid, f"pmid:{pmid}"),
                        "automatic_relevance_prediction": None, "manual_relevance_status": "pending"})
    writel(RUN / "tail_review_packets.jsonl", packets)

    # First two bins are reused only where actually observed; 31-60 remains explicitly unobserved.
    old_screen_by = {(x["case_id"], x["pmid"]): x for x in old_screens}
    old_acquired_keys = {(x["case_id"], x["pmid"]) for x in old_acquired}
    prior_gate_inputs = readl(V22 / "counterfactual_gate_inputs.jsonl")
    prior_labels = {x["packet_id"]: x for base in OVERLAYS for x in readl(base / "adjudications.jsonl")}
    old_direct_by_depth = {(x["case_id"], x["metadata_first_seen_depth"]):
                           prior_labels[x["packet_id"]]["relevance_state"] == "DIRECTLY_RELEVANT"
                           for x in prior_gate_inputs if x["case_id"] in CASES}
    depth_metrics = []
    for cid in CASES:
        for low, high in [(1, 30), (31, 60), (61, 90), (91, 120)]:
            if high <= 60:
                pmids = original_by_case[cid][low-1:high]
                screened = [old_screen_by[(cid, p)] for p in pmids if (cid, p) in old_screen_by]
                gate_rows = []
                for p in pmids:
                    if (cid, p) not in old_screen_by: continue
                    snap = ROOT / old_screen_by[(cid, p)]["abstract_snapshot_ref"]
                    pub = readj(snap); _, decision = v22_decision(cid, pub, targets)
                    gate_rows.append(decision)
                complete = len(screened) == len(pmids)
                evidence = "REUSED_FROZEN_V21_ABSTRACTS" if complete else "UNOBSERVED_AT_ORIGINAL_ABSTRACT_CEILING"
            else:
                pmids = tail_pmids_by_case[cid][low-61:high-60]
                screened = [x for x in tail_screens if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
                gate_rows = [x for x in gate_outputs if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
                complete = len(screened) == len(pmids) == high-low+1
                evidence = "CURRENT_AUTHORIZED_TAIL_PROBE" if complete else "PARTIAL_CURRENT_TAIL_PROBE"
            if high <= 60:
                acquired_ids = {p for position, p in enumerate(original_by_case[cid], 1)
                                if low <= position <= high and (cid, p) in old_acquired_keys}
                manual_direct = sum(old_direct_by_depth.get((cid, position), False)
                                    for position in range(low, high + 1))
            else:
                acquired_ids = {x["pmid"] for x in acquired if x["case_id"] == cid and low <= x["metadata_depth"] <= high}
                manual_direct = "pending" if acquired_ids else 0
            depth_metrics.append({"case_id": cid, "depth_bin": f"{low}-{high}", "unique_metadata_publications": len(pmids),
                                  "abstract_evidence_state": evidence, "abstract_screening_complete_for_bin": complete,
                                  "abstract_plausible_publications": sum(x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screened) if complete else None,
                                  "v22_tier_a": sum(x["state"] == "TIER_A" for x in gate_rows) if complete else None,
                                  "v22_tier_b": sum(x["state"] == "TIER_B" for x in gate_rows) if complete else None,
                                  "known_mismatch_rejects": sum(x["state"] == "REJECT" for x in gate_rows) if complete else None,
                                  "not_admitted_insufficient_plausibility": sum(x["state"] is None for x in gate_rows) if complete else None,
                                  "fulltexts_acquired": len(acquired_ids), "manual_directly_relevant_count": manual_direct,
                                  "literature_recall_or_saturation_inferred": False})
    writel(RUN / "depth_bin_metrics.jsonl", depth_metrics)

    contribution = []
    gate_candidates = {(x["case_id"], x["pmid"]) for x in gate_outputs if x["state"] in {"TIER_A", "TIER_B"}}
    for variant in variants:
        cid, qid = variant["case_id"], variant["query_variant_id"]
        discovered = [p for p in tail_pmids_by_case[cid] if first_tail_query.get((cid, p)) == qid]
        linked = [p for p in tail_pmids_by_case[cid] if qid in lineage[(cid, p)]]
        runs = [x for x in query_runs if x["case_id"] == cid and x["query_variant_id"] == qid]
        contribution.append({"case_id": cid, "query_family_id": variant["query_family_id"], "query_variant_id": qid,
                             "continuation_eligible": bool([x for x in eligible[cid] if x["query_variant_id"] == qid]),
                             "continuation_execution_count": len(runs), "continuation_status": "executed" if runs else "not_needed_or_hard_ceiling_reached",
                             "new_unique_publications": len(discovered), "new_unique_publication_ids": [f"pmid:{p}" for p in discovered],
                             "linked_new_tail_publications": len(linked),
                             "new_v22_acquisition_candidates": sum((cid, p) in gate_candidates for p in discovered),
                             "zero_addition_variant": bool(runs) and not discovered,
                             "query_text_or_order_modified": False, "manual_relevance_count": "pending"})
    writel(RUN / "query_tail_contribution.jsonl", contribution)

    saturation = []; recommendations = {}
    for cid in CASES:
        row1 = next(x for x in depth_metrics if x["case_id"] == cid and x["depth_bin"] == "61-90")
        row2 = next(x for x in depth_metrics if x["case_id"] == cid and x["depth_bin"] == "91-120")
        b1 = (row1["v22_tier_a"] or 0) + (row1["v22_tier_b"] or 0)
        b2 = (row2["v22_tier_a"] or 0) + (row2["v22_tier_b"] or 0)
        failed = any(x["case_id"] == cid and x["execution_status"] == "failed" for x in query_runs)
        state = tail_state(len(case_ordered[cid]), b1, b2, not failed)
        recommendation = {"TAIL_YIELD_ACTIVE": 120, "TAIL_YIELD_DECLINING": 100,
                          "TAIL_YIELD_MINIMAL": 60, "TAIL_EVIDENCE_INSUFFICIENT": 120}[state]
        recommendations[cid] = recommendation
        saturation.append({"case_id": cid, "original_metadata_depth": 60, "new_metadata_depth": len(case_ordered[cid]),
                           "candidate_count_61_90": b1, "candidate_count_91_120": b2,
                           "tail_yield_state": state, "recommended_future_metadata_ceiling": recommendation,
                           "rule": "MINIMAL <=1 total; ACTIVE later bin >=max(2, half earlier); otherwise DECLINING; incomplete/failed is INSUFFICIENT",
                           "retrieval_candidate_saturation_only": True, "scientific_recall_saturation_inferred": False,
                           "manual_direct_relevance_pending": True})
    writel(RUN / "tail_saturation_audit.jsonl", saturation)
    policy = (next(iter(set(recommendations.values()))) if len(set(recommendations.values())) == 1
              else "ADAPTIVE_SATURATION_BEFORE_HARD_CEILING")
    writej(RUN / "budget_recommendation.json", {"candidate_future_budget_policy": policy,
                                                 "per_case_recommendations": recommendations,
                                                 "calibration_only": True, "activated": False,
                                                 "scientific_recall_completeness_claimed": False})

    request_counts = Counter(x["kind"] for x in network.events)
    writej(RUN / "network_usage_audit.json", {"authorized": True, "authorization_scope_respected": True,
                                              "allowed_services_only": all("ncbi.nlm.nih.gov" in x["url"] for x in network.events),
                                              "network_request_count": len(network.events) + len(network.failures),
                                              "successful_network_response_count": len(network.events),
                                              "failed_network_attempt_count": len(network.failures),
                                              "request_counts_by_kind": dict(request_counts),
                                              "event_receipt_ref": rel(network.receipt), "credentials_logged": False,
                                              "original_depth_1_60_retrieval_repeated": False})
    writej(RUN / "provider_usage_audit.json", {"provider_calls": 0, "llm_calls": 0,
                                               "provider_or_model_client_created": False,
                                               "experimental_extraction_invoked": False,
                                               "fulltext_text_parsed_for_science": False})
    protected_after = protected_hashes(); sources_after = source_state()
    changed = sorted(p for p in set(protected_before) | set(protected_after) if protected_before.get(p) != protected_after.get(p))
    safety = {"historical_assets_modified": bool(changed), "changed_protected_paths": changed,
              "protected_file_count": len(protected_before), "protected_tree_digest_before": objhash(protected_before),
              "protected_tree_digest_after": objhash(protected_after), "frozen_source_hashes_before": sources_before,
              "frozen_source_hashes_after": sources_after, "frozen_sources_unchanged": sources_before == sources_after,
              "search_plan_tuning_performed": False, "case_specific_fix_performed": False,
              "production_behavior_modified": False, "formal_v3_modified": False, "atlas_activated": False,
              "active_pointer_changed": False, "provider_calls": 0, "llm_calls": 0,
              "experimental_extraction_invoked": False, "git_commit_created": False}
    writej(RUN / "scientific_state_safety_audit.json", safety)

    per_case = []
    for cid in CASES:
        outputs = [x for x in gate_outputs if x["case_id"] == cid]
        screens = [x for x in tail_screens if x["case_id"] == cid]
        sat = next(x for x in saturation if x["case_id"] == cid)
        per_case.append({"case_id": cid, "original_metadata_depth": 60, "new_metadata_depth": len(case_ordered[cid]),
                         "metadata_61_90_count": sum(x["depth_bin"] == "61-90" for x in outputs),
                         "metadata_91_120_count": sum(x["depth_bin"] == "91-120" for x in outputs),
                         "abstract_plausible_61_90": sum(x["depth_bin"] == "61-90" and x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screens),
                         "abstract_plausible_91_120": sum(x["depth_bin"] == "91-120" and x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screens),
                         "v22_tier_a_tail_count": sum(x["state"] == "TIER_A" for x in outputs),
                         "v22_tier_b_tail_count": sum(x["state"] == "TIER_B" for x in outputs),
                         "v22_reject_tail_count": sum(x["state"] == "REJECT" for x in outputs),
                         "v22_not_admitted_insufficient_plausibility_count": sum(x["state"] is None for x in outputs),
                         "fulltext_tail_acquired_count": sum(x["case_id"] == cid for x in acquired),
                         "tail_yield_state": sat["tail_yield_state"],
                         "recommended_future_metadata_ceiling": sat["recommended_future_metadata_ceiling"]})
    continued_variants = {(x["case_id"], x["query_variant_id"]) for x in query_runs if x["execution_status"] == "executed"}
    eligible_variants = {(c, x["query_variant_id"]) for c in CASES for x in eligible[c]}
    summary = {"status": "completed" if not network.failures and all(len(case_ordered[c]) == 120 for c in CASES) else "partial",
               "probe_case_count": 3, "new_unique_publication_count": len(all_tail_pmids),
               "new_case_publication_count": sum(len(x) for x in tail_pmids_by_case.values()),
               "new_abstract_plausible_count": sum(x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in tail_screens),
               "new_tier_a_count": sum(x["state"] == "TIER_A" for x in gate_outputs),
               "new_tier_b_count": sum(x["state"] == "TIER_B" for x in gate_outputs),
               "new_known_mismatch_reject_count": sum(x["state"] == "REJECT" for x in gate_outputs),
               "new_not_admitted_insufficient_plausibility_count": sum(x["state"] is None for x in gate_outputs),
               "new_fulltext_count": len(acquired), "new_network_fulltext_download_count": sum(x.get("network_request_made") for x in acquired),
               "continued_query_variant_count": len(continued_variants),
               "zero_addition_continued_variant_count": sum(x["zero_addition_variant"] for x in contribution),
               "eligible_variants_not_continued_due_hard_ceiling_count": len(eligible_variants - continued_variants),
               "per_case": per_case, "candidate_future_budget_policy": policy,
               "manual_relevance_status": "pending", "heldout_v22_validation": False,
               "budget_calibration_only": True, "provider_calls": 0, "llm_calls": 0,
               "experimental_extraction_calls": 0, "historical_assets_modified": bool(changed)}
    writej(RUN / "summary.json", summary)

    checks = {"exact_probe_cases": {x["case_id"] for x in per_case} == set(CASES),
              "metadata_ceiling_respected": all(len(case_ordered[c]) <= 120 for c in CASES),
              "abstract_ceiling_respected": all(sum(x["case_id"] == c for x in tail_screens) <= 60 for c in CASES),
              "fulltext_ceiling_respected": all(sum(x["case_id"] == c for x in attempts) <= 10 for c in CASES),
              "provider_llm_extraction_zero": summary["provider_calls"] == summary["llm_calls"] == summary["experimental_extraction_calls"] == 0,
              "frozen_gate_unchanged": gate_hash == sha(ROOT / "tools/search_plan_v22_candidate_gates.py"),
              "frozen_sources_unchanged": sources_before == sources_after,
              "historical_state_unchanged": not changed,
              "query_text_unchanged": all(x["query_string"] == old_exec[x["query_variant_id"]]["query_string"] for x in query_runs),
              "only_eligible_variants_continued": all(any(e["query_variant_id"] == x["query_variant_id"] for e in eligible[x["case_id"]]) for x in query_runs),
              "original_retrieval_not_repeated": all(x.get("retstart", 0) >= (20 if old_exec[x["query_variant_id"]]["execution_status"] == "executed" else 0) for x in query_runs),
              "tail_depth_exact_and_unique": all([x["metadata_depth"] for x in tail_metadata if x["case_id"] == c] == list(range(61, len(case_ordered[c])+1)) and len(set(case_ordered[c])) == len(case_ordered[c]) for c in CASES),
              "gate_evidence_preacquisition_only": all(x["proposition_compatibility_inferred"] is False for x in gate_outputs),
              "rejects_have_positive_gate": all(x["reject_gate_names"] for x in gate_outputs if x["state"] == "REJECT"),
              "tier_b_ledgers_complete": all(x["known_plausible_fields"] and x["unresolved_fields_requiring_fulltext"] and x["why_fulltext_can_resolve"] for x in gate_outputs if x["state"] == "TIER_B"),
              "review_packets_neutral": all(x["automatic_relevance_prediction"] is None and x["adjudication"]["relevance_state"] is None for x in packets),
              "manual_relevance_pending": summary["manual_relevance_status"] == "pending",
              "not_heldout_validation": summary["heldout_v22_validation"] is False,
              "required_payload_artifacts_present": all((RUN / x).is_file() for x in REQUIRED if x not in {"final_validation.json", "manifest.json"})}
    writej(RUN / "final_validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": sum(bool(x) for x in p.read_text(encoding="utf-8").splitlines()) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    assets = [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size}
              for p in sorted(ASSETS.rglob("*")) if p.is_file()]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
                                   "retrieval_assets": assets, "network_request_count": len(network.events)+len(network.failures),
                                   "provider_calls": 0, "llm_calls": 0, "historical_assets_modified": bool(changed)})
    manifest = readj(RUN / "manifest.json")
    checks["manifest_hashes_valid"] = (all(sha(RUN / x["path"]) == x["sha256"] for x in manifest["files"])
                                        and all(sha(ROOT / x["path"]) == x["sha256"] for x in manifest["retrieval_assets"]))
    checks["required_artifacts_present"] = all((RUN / x).is_file() for x in REQUIRED)
    writej(RUN / "final_validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    # Refresh final-validation hash after the final checks.
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": sum(bool(x) for x in p.read_text(encoding="utf-8").splitlines()) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
                                   "retrieval_assets": assets, "network_request_count": len(network.events)+len(network.failures),
                                   "provider_calls": 0, "llm_calls": 0, "historical_assets_modified": bool(changed)})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()): raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.execute_network == args.replay: raise SystemExit("Choose exactly one of --execute-network or --replay")
    execute(args.execute_network)


if __name__ == "__main__": main()
