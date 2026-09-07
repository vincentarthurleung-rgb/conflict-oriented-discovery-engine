#!/usr/bin/env python3
"""Continue the three frozen v2.2 calibration searches from depth 120 to 180."""
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
    from run_search_plan_v22_recall_tail_probe_v1 import blank_adjudication, target_contract, v22_decision
except ModuleNotFoundError:
    from tools.run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, screen_abstract, text_of
    from tools.run_search_plan_v22_recall_tail_probe_v1 import blank_adjudication, target_contract, v22_decision


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
V1 = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"
ADJ = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_adjudication_v1_offline"
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180"
ASSETS = RUN / "retrieval_assets"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CASES = ["spv2_017", "spv2_016", "spv2_003"]
REQUIRED = ["baseline.json", "probe_case_inventory.json", "continuation_state.jsonl",
            "continued_query_executions.jsonl", "tail_metadata_121_180.jsonl",
            "tail_abstract_screening_121_180.jsonl", "tail_v22_gate_outputs_121_180.jsonl",
            "tail_acquisition_candidate_inventory.jsonl", "tail_fulltext_acquisition_attempts.jsonl",
            "tail_fulltext_manifest.jsonl", "tail_review_packets.jsonl", "depth_bin_metrics.jsonl",
            "query_tail_contribution.jsonl", "tail_candidate_saturation_audit.jsonl",
            "previous_tail_adjudication_linkage.json", "budget_recommendation_pre_adjudication.json",
            "network_usage_audit.json", "provider_usage_audit.json", "scientific_state_safety_audit.json",
            "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json"]
PROTECTED_SCOPES = ["src", "configs", "scripts", "alembic", "docker", "tools"]


def now(): return datetime.now(timezone.utc).isoformat()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
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


def source_hashes():
    paths = [SOURCE / "frozen_search_plans.jsonl", SOURCE / "frozen_query_variants.jsonl",
             SOURCE / "frozen_gate_rules.jsonl", SOURCE / "executed_queries.jsonl",
             V1 / "continued_query_executions.jsonl", V1 / "tail_metadata_inventory.jsonl",
             V1 / "tail_v22_gate_outputs.jsonl", V1 / "manifest.json",
             ADJ / "adjudications.jsonl", ADJ / "tail_relevance_metrics.json",
             ROOT / "tools/search_plan_v22_candidate_gates.py"]
    return {rel(path): sha(path) for path in paths}


class Network:
    def __init__(self, execute):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        prior = readj(self.receipt) if self.receipt.exists() else {}
        self.events, self.failures = prior.get("events", []), prior.get("failures", [])

    def get(self, url, path, kind, lineage):
        path = Path(path)
        if path.exists(): return path.read_bytes()
        if not self.execute: raise FileNotFoundError(path)
        stamp = now()
        request = urllib.request.Request(url, headers={"User-Agent": "conflict-oriented-discovery-engine-tail-probe-v2/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body, status, content_type = response.read(), response.status, response.headers.get("Content-Type")
        except Exception as exc:
            self.failures.append({"kind": kind, "timestamp": stamp, "url": url, "lineage": lineage,
                                  "error_type": type(exc).__name__, "error": str(exc)})
            self.save(); raise
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        self.events.append({"request_id": f"tail_v2_ncbi_request_{len(self.events)+1:04d}", "kind": kind,
                            "timestamp": stamp, "url": url, "http_status": status,
                            "content_type": content_type, "snapshot_ref": rel(path),
                            "response_sha256": sha(path), "bytes": len(body), "lineage": lineage})
        self.save(); time.sleep(.36)
        return body

    def save(self):
        writej(self.receipt, {"events": self.events, "failures": self.failures,
                              "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0})


def candidate_state(depth, first, second, failed):
    if failed or depth < 180: return "TAIL_CANDIDATE_EVIDENCE_INSUFFICIENT"
    if first + second <= 1: return "TAIL_CANDIDATE_YIELD_MINIMAL"
    if second >= max(2, first / 2): return "TAIL_CANDIDATE_YIELD_ACTIVE"
    return "TAIL_CANDIDATE_YIELD_DECLINING"


def execute(network_enabled):
    if RUN.exists() and any(p.name not in REQUIRED and p.name != "retrieval_assets" for p in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True); ASSETS.mkdir(parents=True, exist_ok=True)
    protected_before, sources_before = protected_hashes(), source_hashes()
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    gate_hash = sha(ROOT / "tools/search_plan_v22_candidate_gates.py")
    writej(RUN / "baseline.json", {
        "artifact_schema_version": "search_plan_v22_recall_tail_probe_v2_depth180_baseline.v1",
        "source_tail_probe_v1": rel(V1), "source_tail_adjudication": rel(ADJ),
        "explicit_network_authorization": True,
        "authorization_source": "user explicitly authorized this one 120-to-180 budget-calibration probe",
        "allowed_services": ["NCBI PubMed E-utilities", "NCBI PMC E-utilities"],
        "metadata_start_depth": 120, "metadata_hard_ceiling_per_case": 180,
        "additional_abstract_ceiling_per_case": 60, "fulltext_selection_ceiling_per_case": 10,
        "provider_authorized": False, "llm_authorized": False, "extraction_authorized": False,
        "continuation_consistency_limit": "No PubMed WebEnv/cursor was preserved. Frozen query text, sort, order and next retstart are preserved, but the live PubMed relevance index may have shifted since prior pages.",
        "source_hashes": sources_before, "protected_tree_digest_before": objhash(protected_before),
        "protected_file_count": len(protected_before), "git_head_at_authorized_execution": git_head})

    plans = {x["case_id"]: x for x in readl(SOURCE / "frozen_search_plans.jsonl")}
    variants = [x for x in readl(SOURCE / "frozen_query_variants.jsonl") if x["case_id"] in CASES]
    original_exec = {x["query_variant_id"]: x for x in readl(SOURCE / "executed_queries.jsonl") if x["case_id"] in CASES}
    v1_exec = readl(V1 / "continued_query_executions.jsonl")
    original_meta = [x for x in readl(SOURCE / "metadata_stage_results.jsonl") if x["case_id"] in CASES]
    v1_meta = readl(V1 / "tail_metadata_inventory.jsonl")
    targets = {cid: target_contract(cid, plans, readl(SOURCE / "frozen_gate_rules.jsonl"), variants) for cid in CASES}

    prior_order = defaultdict(list)
    for row in original_meta:
        prior_order[row["case_id"]].append(row["canonical_publication_id"].split(":", 1)[1])
    for row in v1_meta: prior_order[row["case_id"]].append(row["pmid"])
    if any(len(prior_order[cid]) != 120 or len(set(prior_order[cid])) != 120 for cid in CASES):
        raise RuntimeError("Each preserved continuation case must have exactly 120 unique prior records")

    continuation = defaultdict(list); continuation_rows = []
    for variant in variants:
        cid, qid = variant["case_id"], variant["query_variant_id"]
        prior_runs = [x for x in v1_exec if x["case_id"] == cid and x["query_variant_id"] == qid and x["execution_status"] == "executed"]
        if prior_runs:
            last = max(prior_runs, key=lambda x: x["retstart"])
            next_offset = last["retstart"] + last["returned_id_count"]
            result_count = last["result_count_at_continuation"]
            reason = "partially_consumed_at_depth_120"
        else:
            first = original_exec[qid]
            if first["execution_status"] == "executed":
                next_offset, result_count, reason = first["returned_id_count"], first.get("result_count"), "not_reached_in_probe_v1_after_original_page"
            else:
                next_offset, result_count, reason = 0, first.get("result_count"), "frozen_variant_not_yet_reached"
        eligible = result_count is None or next_offset < result_count
        row = {"case_id": cid, "query_family_id": variant["query_family_id"], "query_variant_id": qid,
               "query_string": variant["query_string"], "sort": "relevance", "next_retstart": next_offset,
               "last_observed_result_count": result_count, "continuation_reason": reason,
               "eligible_at_depth_120": eligible, "frozen_query_order": variants.index(variant),
               "query_text_modified": False, "prior_pages_repeated": False}
        continuation_rows.append(row)
        if eligible: continuation[cid].append({**variant, "next_retstart": next_offset, "continuation_reason": reason})
    writel(RUN / "continuation_state.jsonl", continuation_rows)
    writej(RUN / "probe_case_inventory.json", {"case_count": 3, "case_ids": CASES,
           "selection_authority": "user-specified exact calibration cases", "metadata_start_depth": 120,
           "metadata_max_depth": 180, "frozen_gate_sha256": gate_hash})

    network = Network(network_enabled)
    ordered = {cid: list(prior_order[cid]) for cid in CASES}
    query_hits, first_query, query_runs = defaultdict(list), {}, []
    for cid in CASES:
        active, seen = [dict(x) for x in continuation[cid]], set(ordered[cid])
        while len(ordered[cid]) < 180 and active:
            next_active = []
            for item in active:
                if len(ordered[cid]) >= 180: break
                offset = item["next_retstart"]
                params = {"db": "pubmed", "term": item["query_string"], "retstart": offset,
                          "retmax": 20, "retmode": "json", "sort": "relevance",
                          "tool": "conflict_oriented_discovery_engine"}
                path = ASSETS / "pubmed_esearch" / cid / f"{item['query_variant_id'].replace(':', '_')}__retstart_{offset:04d}.json"
                stamp = now()
                try:
                    raw = network.get(BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params), path,
                                      "pubmed_esearch_continuation_121_180",
                                      {"case_id": cid, "query_variant_id": item["query_variant_id"], "retstart": offset})
                    event = next((x for x in network.events if x["snapshot_ref"] == rel(path)), None)
                    stamp = event["timestamp"] if event else stamp
                    result = json.loads(raw)["esearchresult"]; ids = [str(x) for x in result.get("idlist", [])]
                    added = []
                    for pmid in ids:
                        if pmid not in query_hits[(cid, item["query_variant_id"])]: query_hits[(cid, item["query_variant_id"])].append(pmid)
                        if pmid not in seen and len(ordered[cid]) < 180:
                            seen.add(pmid); ordered[cid].append(pmid); added.append(pmid); first_query[(cid, pmid)] = item["query_variant_id"]
                    query_runs.append({"case_id": cid, "query_family_id": item["query_family_id"],
                        "query_variant_id": item["query_variant_id"], "query_string": item["query_string"],
                        "continuation_reason": item["continuation_reason"], "retstart": offset, "retmax": 20,
                        "execution_timestamp": stamp, "execution_status": "executed",
                        "result_count_at_continuation": int(result.get("count", 0)), "returned_id_count": len(ids),
                        "new_unique_additions": len(added), "new_unique_publication_ids": [f"pmid:{x}" for x in added],
                        "raw_response_snapshot_ref": rel(path), "response_sha256": sha(path), "prior_pages_repeated": False})
                    if ids and offset + len(ids) < int(result.get("count", 0)):
                        item["next_retstart"] = offset + len(ids); next_active.append(item)
                except Exception as exc:
                    query_runs.append({"case_id": cid, "query_family_id": item["query_family_id"],
                        "query_variant_id": item["query_variant_id"], "query_string": item["query_string"],
                        "continuation_reason": item["continuation_reason"], "retstart": offset, "retmax": 20,
                        "execution_timestamp": stamp, "execution_status": "failed", "error_type": type(exc).__name__,
                        "error": str(exc), "new_unique_additions": 0, "prior_pages_repeated": False})
            active = next_active
    writel(RUN / "continued_query_executions.jsonl", query_runs)

    new_by_case = {cid: ordered[cid][120:] for cid in CASES}
    all_pmids = sorted({p for values in new_by_case.values() for p in values}, key=int)
    publications = {}
    for batch, start in enumerate(range(0, len(all_pmids), 100), 1):
        ids = all_pmids[start:start + 100]
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "pubmed_efetch" / f"tail_121_180_batch_{batch:03d}.xml"
        try: publications.update(parse_pubmed(network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                                                           "pubmed_efetch_tail_121_180", {"pmids": ids})))
        except Exception: pass

    lineage = defaultdict(list)
    for cid in CASES:
        for item in continuation[cid]:
            for pmid in query_hits[(cid, item["query_variant_id"])]:
                if pmid in new_by_case[cid]: lineage[(cid, pmid)].append(item["query_variant_id"])
    metadata, screens, gates, gate_by_key = [], [], [], {}
    for cid in CASES:
        for depth, pmid in enumerate(new_by_case[cid], 121):
            pub = publications.get(pmid, {"pmid": pmid, "pmcid": None, "doi": None, "title": "", "abstract": "",
                                          "publication_types": [], "journal": "", "publication_date": ""})
            qids = lineage[(cid, pmid)] or [first_query[(cid, pmid)]]
            depth_bin = "121-150" if depth <= 150 else "151-180"
            snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"; writej(snapshot, pub)
            source_ref = next((x["snapshot_ref"] for x in network.events
                               if x["kind"] == "pubmed_efetch_tail_121_180" and pmid in x["lineage"]["pmids"]), None)
            metadata.append({"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                "metadata_depth": depth, "depth_bin": depth_bin,
                "metadata_state": "metadata_plausible" if pub["title"] else "metadata_identity_only",
                "title": pub["title"], "journal": pub["journal"], "publication_date": pub["publication_date"],
                "publication_types": pub["publication_types"], "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "query_lineage": qids, "first_discovery_query": first_query[(cid, pmid)], "source_ref": source_ref})
            screen_state, reason, signals = screen_abstract(cid, pub)
            screens.append({"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                "metadata_depth": depth, "depth_bin": depth_bin, "screen_state": screen_state, "reason": reason,
                "signals": signals, "query_lineage": qids, "abstract_snapshot_ref": rel(snapshot),
                "abstract_snapshot_sha256": sha(snapshot), "frozen_v21_screen_logic": True,
                "manual_relevance_state": "pending", "scientific_proposition_compatibility_inferred": False})
            scientific, decision = v22_decision(cid, pub, targets)
            output = {"case_id": cid, "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                "metadata_depth": depth, "depth_bin": depth_bin, "query_lineage": qids,
                "pre_acquisition_input_sha256": objhash(scientific),
                "pre_acquisition_evidence_refs": {"abstract": {"path": rel(snapshot), "sha256": sha(snapshot)},
                    "publication_metadata": {"path": rel(snapshot), "sha256": sha(snapshot)},
                    "frozen_target": {"path": rel(SOURCE / "frozen_search_plans.jsonl"),
                                      "sha256": sha(SOURCE / "frozen_search_plans.jsonl"), "selector": f"case_id={cid}"}},
                **decision}
            gates.append(output); gate_by_key[(cid, pmid)] = output
    writel(RUN / "tail_metadata_121_180.jsonl", metadata)
    writel(RUN / "tail_abstract_screening_121_180.jsonl", screens)
    writel(RUN / "tail_v22_gate_outputs_121_180.jsonl", gates)

    prior_fulltexts = readl(SOURCE / "fulltext_acquired_manifest.jsonl") + readl(V1 / "tail_fulltext_manifest.jsonl")
    cache = {x["pmcid"]: x for x in prior_fulltexts if x.get("pmcid") and x.get("snapshot_ref")}
    candidates, attempts, acquired = [], [], []
    for cid in CASES:
        selected = sorted((x for x in gates if x["case_id"] == cid and x["state"] in {"TIER_A", "TIER_B"}),
                          key=lambda x: (x["state"] != "TIER_A", x["metadata_depth"]))[:10]
        selected_ids = {x["pmid"] for x in selected}
        index_by_id = {x["pmid"]: i for i, x in enumerate(selected, 1)}
        for output in [x for x in gates if x["case_id"] == cid and x["state"] in {"TIER_A", "TIER_B"}]:
            candidates.append({"case_id": cid, "pmid": output["pmid"], "canonical_publication_id": f"pmid:{output['pmid']}",
                "metadata_depth": output["metadata_depth"], "depth_bin": output["depth_bin"], "tier_state": output["state"],
                "query_lineage": output["query_lineage"], "selected_for_acquisition": output["pmid"] in selected_ids,
                "selection_index_within_case": index_by_id.get(output["pmid"]),
                "selection_policy": "Tier A before Tier B, then ascending metadata depth; maximum 10 per case",
                "predicted_relevance_used": False})
        for output in selected:
            pmid = output["pmid"]; pub = publications[pmid]; pmcid = pub.get("pmcid")
            base = {"attempt_id": f"tail_v2_fta_{len(attempts)+1:04d}", "case_id": cid,
                "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid, "pmcid": pmcid,
                "metadata_depth": output["metadata_depth"], "depth_bin": output["depth_bin"],
                "tier_state": output["state"], "query_lineage": output["query_lineage"],
                "selected_for_acquisition": True, "selection_index_within_case": index_by_id[pmid],
                "fulltext_selection_ceiling": 10}
            if not pmcid:
                attempts.append({**base, "status": "fulltext_not_available", "pmcid_available": False,
                                 "oa_acquisition_attempted": False, "network_request_made": False,
                                 "reason": "PubMed metadata contains no PMCID; no relevance inference made"}); continue
            if pmcid in cache:
                old = cache[pmcid]
                row = {**base, "status": "fulltext_acquired", "pmcid_available": True,
                    "oa_acquisition_attempted": False, "network_request_made": False, "cross_probe_cache_hit": True,
                    "reason": "reused preserved canonical PMCID fulltext without network",
                    "snapshot_ref": old["snapshot_ref"], "content_hash": old["content_hash"], "source_identity": "PMC efetch"}
                attempts.append(row); acquired.append(row); continue
            path = ASSETS / "fulltext" / f"{pmcid}.xml"
            params = {"db": "pmc", "id": pmcid, "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}
            try:
                raw = network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                                  "pmc_fulltext_efetch_tail_121_180", {"case_id": cid, "pmid": pmid, "pmcid": pmcid})
                root = ET.fromstring(raw); article_ok = root.find(".//article") is not None or root.tag.endswith("article")
                xml_ids = [text_of(x) for x in root.findall(".//article-id[@pub-id-type='pmid']")]
                identity_ok = not xml_ids or pmid in xml_ids
                status = "fulltext_acquired" if article_ok and identity_ok else ("fulltext_identity_mismatch" if article_ok else "fulltext_retrieval_failed")
                reason = "usable PMC XML article acquired" if status == "fulltext_acquired" else "PMC response failed article or identity validation"
                row = {**base, "status": status, "pmcid_available": True, "oa_acquisition_attempted": True,
                    "network_request_made": True, "cross_probe_cache_hit": False, "reason": reason,
                    "snapshot_ref": rel(path), "content_hash": sha(path), "source_identity": "PMC efetch"}
                attempts.append(row)
                if status == "fulltext_acquired": acquired.append(row); cache[pmcid] = row
            except Exception as exc:
                attempts.append({**base, "status": "fulltext_retrieval_failed", "pmcid_available": True,
                    "oa_acquisition_attempted": True, "network_request_made": True,
                    "reason": str(exc), "error_type": type(exc).__name__})
    writel(RUN / "tail_acquisition_candidate_inventory.jsonl", candidates)
    writel(RUN / "tail_fulltext_acquisition_attempts.jsonl", attempts)
    writel(RUN / "tail_fulltext_manifest.jsonl", acquired)

    packets = []
    for index, row in enumerate(acquired, 1):
        cid, pmid = row["case_id"], row["pmid"]; pub = publications[pmid]; output = gate_by_key[(cid, pmid)]
        packet_id = f"rrtailv2_{index:04d}"; snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"
        packets.append({"packet_id": packet_id, "review_unit_id": packet_id, "case_id": cid,
            "ambiguity_tier": plans[cid]["ambiguity_tier"], "retrieval_target": plans[cid]["retrieval_target"],
            "scientific_proposition_target": plans[cid]["scientific_proposition_target"],
            "publication_identity": {"pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "title": pub["title"], "year": pub.get("publication_date"), "publication_types": pub.get("publication_types", [])},
            "retrieval_provenance": {"query_variants": row["query_lineage"],
                "first_discovery_query": first_query[(cid, pmid)], "metadata_depth": row["metadata_depth"]},
            "pre_acquisition_evidence": {"title": pub["title"], "abstract": pub["abstract"],
                "abstract_snapshot_ref": rel(snapshot), "abstract_snapshot_sha256": sha(snapshot),
                "tier_state": output["state"], "gate_reasons": output["gates"],
                "known_plausible_fields": output["known_plausible_fields"],
                "unresolved_fields_requiring_fulltext": output["unresolved_fields_requiring_fulltext"],
                "why_fulltext_can_resolve": output["why_fulltext_can_resolve"]},
            "fulltext_evidence_packet": {"source_ref": row["snapshot_ref"], "fulltext_sha256": row["content_hash"],
                "excerpts": [], "experimental_extraction_performed": False},
            "adjudication": blank_adjudication(packet_id, cid, f"pmid:{pmid}"),
            "automatic_relevance_prediction": None, "manual_relevance_status": "pending"})
    writel(RUN / "tail_review_packets.jsonl", packets)

    previous_depth = readl(V1 / "depth_bin_metrics.jsonl")
    prior_adjudications = readl(ADJ / "adjudications.jsonl")
    prior_packets = {x["packet_id"]: x for x in readl(V1 / "tail_review_packets.jsonl")}
    prior_direct = defaultdict(int)
    for row in prior_adjudications:
        if row["relevance_state"] == "DIRECTLY_RELEVANT":
            p = prior_packets[row["packet_id"]]; depth = p["retrieval_provenance"]["metadata_depth"]
            prior_direct[(row["case_id"], "61-90" if depth <= 90 else "91-120")] += 1
    depth_metrics = []
    for row in previous_depth:
        copied = {**row, "source_probe_ref": rel(V1 / "depth_bin_metrics.jsonl"), "current_probe_new_observation": False}
        if row["depth_bin"] in {"61-90", "91-120"}:
            copied["manual_directly_relevant_count"] = prior_direct[(row["case_id"], row["depth_bin"])]
            copied["manual_relevance_scope"] = "previously acquired 15-paper tail sample only"
        depth_metrics.append(copied)
    for cid in CASES:
        for label, low, high in [("121-150", 121, 150), ("151-180", 151, 180)]:
            mrows = [x for x in metadata if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
            srows = [x for x in screens if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
            grows = [x for x in gates if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
            arows = [x for x in acquired if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
            selected = [x for x in attempts if x["case_id"] == cid and low <= x["metadata_depth"] <= high]
            complete = len(mrows) == high-low+1
            depth_metrics.append({"case_id": cid, "depth_bin": label, "unique_metadata_publications": len(mrows),
                "abstract_evidence_state": "CURRENT_AUTHORIZED_TAIL_PROBE" if complete else "PARTIAL_CURRENT_TAIL_PROBE",
                "abstract_screening_complete_for_bin": len(srows) == len(mrows),
                "abstract_plausible_publications": sum(x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in srows),
                "v22_tier_a": sum(x["state"] == "TIER_A" for x in grows),
                "v22_tier_b": sum(x["state"] == "TIER_B" for x in grows),
                "known_mismatch_rejects": sum(x["state"] == "REJECT" for x in grows),
                "not_admitted_insufficient_plausibility": sum(x["state"] is None for x in grows),
                "oa_acquisition_candidates": sum(x["state"] in {"TIER_A", "TIER_B"} for x in grows),
                "fulltexts_selected": len(selected), "fulltexts_acquired": len(arows),
                "manual_directly_relevant_count": "PENDING" if arows else 0,
                "current_probe_new_observation": True, "scientific_recall_or_saturation_inferred": False})
    writel(RUN / "depth_bin_metrics.jsonl", depth_metrics)

    contributions = []
    candidate_keys = {(x["case_id"], x["pmid"]) for x in gates if x["state"] in {"TIER_A", "TIER_B"}}
    for variant in variants:
        cid, qid = variant["case_id"], variant["query_variant_id"]
        discovered = [p for p in new_by_case[cid] if first_query.get((cid, p)) == qid]
        runs = [x for x in query_runs if x["case_id"] == cid and x["query_variant_id"] == qid]
        state = next(x for x in continuation_rows if x["case_id"] == cid and x["query_variant_id"] == qid)
        contributions.append({"case_id": cid, "query_family_id": variant["query_family_id"], "query_variant_id": qid,
            "continuation_reason": state["continuation_reason"], "continued": bool(runs),
            "previously_unreached_variant_executed": bool(runs) and "not_yet_reached" in state["continuation_reason"],
            "continuation_execution_count": len(runs), "new_unique_publications": len(discovered),
            "new_unique_publication_ids": [f"pmid:{p}" for p in discovered],
            "new_v22_acquisition_candidates": sum((cid, p) in candidate_keys for p in discovered),
            "zero_addition_variant": bool(runs) and not discovered, "query_text_or_order_modified": False,
            "manual_relevance_count": "PENDING"})
    writel(RUN / "query_tail_contribution.jsonl", contributions)

    saturation = []
    for cid in CASES:
        b1 = sum(x["case_id"] == cid and x["depth_bin"] == "121-150" and x["state"] in {"TIER_A", "TIER_B"} for x in gates)
        b2 = sum(x["case_id"] == cid and x["depth_bin"] == "151-180" and x["state"] in {"TIER_A", "TIER_B"} for x in gates)
        failed = any(x["case_id"] == cid and x["execution_status"] == "failed" for x in query_runs)
        state = candidate_state(len(ordered[cid]), b1, b2, failed)
        saturation.append({"case_id": cid, "metadata_start_depth": 120, "deepest_metadata_depth_reached": len(ordered[cid]),
            "candidate_count_121_150": b1, "candidate_count_151_180": b2, "tail_candidate_state": state,
            "rule": "MINIMAL <=1 total; ACTIVE later bin >=max(2, half earlier); otherwise DECLINING; incomplete/failed is INSUFFICIENT",
            "retrieval_candidate_yield_only": True, "scientific_relevance_saturation_inferred": False,
            "manual_direct_relevance": "PENDING"})
    writel(RUN / "tail_candidate_saturation_audit.jsonl", saturation)
    writej(RUN / "previous_tail_adjudication_linkage.json", {
        "source_ref": rel(ADJ / "adjudications.jsonl"), "source_sha256": sha(ADJ / "adjudications.jsonl"),
        "sample_size": 15, "directly_relevant_count": 10, "justified_count": 10,
        "deepest_adjudicated_direct_relevance_depth": 101,
        "used_as_retrieval_or_gate_input": False, "reporting_context_only": True})
    writej(RUN / "budget_recommendation_pre_adjudication.json", {
        "candidate_future_budget_policy": "TAIL_CALIBRATION_STILL_INSUFFICIENT",
        "allowed_policy_enum": ["120_HARD_CEILING_SUPPORTED", "150_HARD_CEILING_SUPPORTED", "180_HARD_CEILING_SUPPORTED",
            "ADAPTIVE_SATURATION_WITH_120_SOFT_TARGET", "ADAPTIVE_SATURATION_WITH_180_SAFETY_CEILING",
            "TAIL_CALIBRATION_STILL_INSUFFICIENT"],
        "reason": "New depth-121-to-180 fulltexts require manual adjudication before a budget decision.",
        "calibration_only": True, "activated": False, "scientific_recall_completeness_claimed": False})

    request_counts = Counter(x["kind"] for x in network.events)
    writej(RUN / "network_usage_audit.json", {"authorized": True, "authorization_scope_respected": True,
        "allowed_services_only": all("ncbi.nlm.nih.gov" in x["url"] for x in network.events),
        "network_request_count": len(network.events)+len(network.failures),
        "successful_network_response_count": len(network.events), "failed_network_attempt_count": len(network.failures),
        "request_counts_by_kind": dict(request_counts), "event_receipt_ref": rel(network.receipt),
        "credentials_logged": False, "prior_depth_1_120_pages_repeated": False})
    writej(RUN / "provider_usage_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "provider_or_model_client_created": False, "experimental_extraction_invoked": False,
        "fulltext_text_parsed_for_science": False})

    sources_after, protected_after = source_hashes(), protected_hashes()
    changed = sorted(p for p in set(protected_before)|set(protected_after) if protected_before.get(p) != protected_after.get(p))
    writej(RUN / "scientific_state_safety_audit.json", {"historical_assets_modified": bool(changed),
        "changed_protected_paths": changed, "frozen_sources_unchanged": sources_before == sources_after,
        "frozen_gate_sha256_before": gate_hash, "frozen_gate_sha256_after": sha(ROOT / "tools/search_plan_v22_candidate_gates.py"),
        "search_plan_tuning_performed": False, "gate_modification_performed": False,
        "case_specific_fix_performed": False, "production_behavior_modified": False,
        "heldout_validation_started": False, "provider_calls": 0, "llm_calls": 0,
        "extraction_calls": 0, "git_mutation_invoked": False})
    writej(RUN / "production_leakage_audit.json", {"v22_candidate_activated": False,
        "active_pointer_changed": False, "production_config_modified": False,
        "formal_v3_modified": False, "atlas_activated": False, "heldout_validation_started": False,
        "tail_adjudication_labels_used_in_gate_inputs": False, "status": "NO_PRODUCTION_LEAKAGE"})

    per_case = []
    for cid in CASES:
        sat = next(x for x in saturation if x["case_id"] == cid)
        def count(bin_name, predicate): return sum(x["case_id"] == cid and x["depth_bin"] == bin_name and predicate(x) for x in gates)
        def plausible(bin_name): return sum(x["case_id"] == cid and x["depth_bin"] == bin_name and x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screens)
        per_case.append({"case_id": cid,
            "metadata_121_150_count": count("121-150", lambda x: True), "metadata_151_180_count": count("151-180", lambda x: True),
            "abstract_plausible_121_150": plausible("121-150"), "abstract_plausible_151_180": plausible("151-180"),
            "tier_a_121_150": count("121-150", lambda x: x["state"] == "TIER_A"), "tier_a_151_180": count("151-180", lambda x: x["state"] == "TIER_A"),
            "tier_b_121_150": count("121-150", lambda x: x["state"] == "TIER_B"), "tier_b_151_180": count("151-180", lambda x: x["state"] == "TIER_B"),
            "reject_121_150": count("121-150", lambda x: x["state"] == "REJECT"), "reject_151_180": count("151-180", lambda x: x["state"] == "REJECT"),
            "not_admitted_121_150": count("121-150", lambda x: x["state"] is None), "not_admitted_151_180": count("151-180", lambda x: x["state"] is None),
            "new_fulltext_selected": sum(x["case_id"] == cid for x in attempts),
            "new_fulltext_acquired": sum(x["case_id"] == cid for x in acquired),
            "deepest_metadata_depth_reached": len(ordered[cid]), "tail_candidate_state": sat["tail_candidate_state"]})
    continued = {(x["case_id"], x["query_variant_id"]) for x in query_runs if x["execution_status"] == "executed"}
    summary = {"status": "completed" if not network.failures and all(len(ordered[c]) == 180 for c in CASES) else "partial",
        "probe_case_count": 3, "metadata_start_depth": 120, "metadata_max_depth": 180,
        "new_unique_publication_count": len(all_pmids), "new_case_publication_count": sum(map(len, new_by_case.values())),
        "new_abstract_plausible_count": sum(x["screen_state"] in {"abstract_high_plausibility", "abstract_possible"} for x in screens),
        "new_tier_a_count": sum(x["state"] == "TIER_A" for x in gates),
        "new_tier_b_count": sum(x["state"] == "TIER_B" for x in gates),
        "new_reject_count": sum(x["state"] == "REJECT" for x in gates),
        "new_not_admitted_insufficient_plausibility_count": sum(x["state"] is None for x in gates),
        "new_fulltext_selected_count": len(attempts), "new_fulltext_acquired_count": len(acquired),
        "pmcid_available_selected_count": sum(x.get("pmcid_available") for x in attempts),
        "no_pmcid_selected_count": sum(not x.get("pmcid_available") for x in attempts),
        "continued_query_variant_count": len(continued),
        "previously_unreached_variant_executed_count": sum(x["previously_unreached_variant_executed"] for x in contributions),
        "per_case": per_case, "previous_deepest_adjudicated_direct_relevance_depth": 101,
        "previous_tail_sample_direct_relevance": {"numerator": 10, "denominator": 15},
        "manual_relevance_status": "PENDING", "budget_activation_state": "not_activated",
        "budget_calibration_only": True, "v22_candidate_status": True, "heldout_v22_validation": False,
        "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0,
        "historical_assets_modified": bool(changed), "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)

    checks = {"exact_probe_cases": {x["case_id"] for x in per_case} == set(CASES),
        "metadata_depth_at_most_180": all(len(ordered[c]) <= 180 for c in CASES),
        "abstract_ceiling_at_most_60_new_per_case": all(sum(x["case_id"] == c for x in screens) <= 60 for c in CASES),
        "fulltext_selection_at_most_10_per_case": all(sum(x["case_id"] == c for x in attempts) <= 10 for c in CASES),
        "no_query_modification": all(x["query_string"] == next(v["query_string"] for v in variants if v["query_variant_id"] == x["query_variant_id"]) for x in query_runs),
        "no_gate_modification": gate_hash == sha(ROOT / "tools/search_plan_v22_candidate_gates.py"),
        "no_adjudication_labels_in_retrieval_or_gating": all(x["proposition_compatibility_inferred"] is False for x in gates),
        "provider_llm_extraction_zero": summary["provider_calls"] == summary["llm_calls"] == summary["extraction_calls"] == 0,
        "historical_scientific_state_unchanged": not changed and sources_before == sources_after,
        "production_not_activated": summary["budget_activation_state"] == "not_activated" and not summary["heldout_v22_validation"],
        "prior_120_records_not_overwritten": all(len(prior_order[c]) == 120 for c in CASES),
        "new_depth_sequence_exact_and_unique": all([x["metadata_depth"] for x in metadata if x["case_id"] == c] == list(range(121, len(ordered[c])+1)) and len(set(ordered[c])) == len(ordered[c]) for c in CASES),
        "review_packets_neutral": all(x["automatic_relevance_prediction"] is None and x["manual_relevance_status"] == "pending" and all(v is None or v == [] for v in x["adjudication"].values()) for x in packets),
        "packet_identity_depth_linkage_preserved": all(x["retrieval_provenance"]["metadata_depth"] == next(y["metadata_depth"] for y in metadata if y["case_id"] == x["case_id"] and y["pmid"] == x["publication_identity"]["pmid"]) for x in packets),
        "candidate_state_enum_valid": all(x["tail_candidate_state"] in {"TAIL_CANDIDATE_YIELD_ACTIVE", "TAIL_CANDIDATE_YIELD_DECLINING", "TAIL_CANDIDATE_YIELD_MINIMAL", "TAIL_CANDIDATE_EVIDENCE_INSUFFICIENT"} for x in saturation),
        "no_scientific_saturation_claim": all(not x["scientific_relevance_saturation_inferred"] for x in saturation),
        "required_payloads_present": all((RUN / x).is_file() for x in REQUIRED if x not in {"final_validation.json", "manifest.json"})}
    # Blank packet identity fields are intentionally populated, so test judgment fields explicitly.
    checks["review_packets_neutral"] = all(x["automatic_relevance_prediction"] is None and x["manual_relevance_status"] == "pending"
        and x["adjudication"]["relevance_state"] is None and x["adjudication"]["acquisition_decision"] is None
        and x["adjudication"]["confidence"] is None and not x["adjudication"]["matched_target_components"] for x in packets)
    writej(RUN / "final_validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    assets = [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(ASSETS.rglob("*")) if p.is_file()]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "retrieval_assets": assets, "network_request_count": len(network.events)+len(network.failures),
        "provider_calls": 0, "llm_calls": 0, "historical_assets_modified": bool(changed)})
    checks["manifest_hashes_valid"] = all(sha(RUN / x["path"]) == x["sha256"] for x in readj(RUN / "manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN / x).is_file() for x in REQUIRED)
    writej(RUN / "final_validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
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
    if args.execute_network == args.replay: raise SystemExit("Choose exactly one mode")
    execute(args.execute_network)


if __name__ == "__main__": main()
