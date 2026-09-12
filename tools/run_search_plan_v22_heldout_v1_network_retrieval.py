#!/usr/bin/env python3
"""Execute the explicitly authorized frozen held-out v1 PubMed/PMC retrieval."""
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
    from run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, text_of
    from search_plan_v22_candidate_gates import build_target_contract, evaluate
except ModuleNotFoundError:
    from tools.run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, text_of
    from tools.search_plan_v22_candidate_gates import build_target_contract, evaluate


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
PREFLIGHT = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_preflight_offline"
RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
ASSETS = RUN / "retrieval_assets"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GATE = ROOT / "tools/search_plan_v22_candidate_gates.py"
EXPECTED_PROTOCOL_HASH = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
EXPECTED_GATE_HASH = "58d8afba78584e060c297005df76b0ce1533c56782c7a5d94ee3d26dea5bdc4f"
CASE_IDS = [f"heldout_v1_{index:03d}" for index in range(1, 9)]
REQUIRED = [
    "protocol_verification.json", "freeze_hash_verification.json",
    "heldout_case_execution_inventory.jsonl", "query_execution_log.jsonl",
    "metadata_inventory.jsonl", "abstract_screening.jsonl", "v22_gate_outputs.jsonl",
    "case_retrieval_metrics.jsonl", "ambiguity_retrieval_metrics.jsonl",
    "fulltext_selection_inventory.jsonl", "fulltext_acquisition_attempts.jsonl",
    "fulltext_manifest.jsonl", "neutral_review_packets.jsonl", "network_usage_audit.json",
    "provider_usage_audit.json", "protocol_leakage_audit.json",
    "scientific_state_safety_audit.json", "validation.json", "manifest.json", "summary.json",
]


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    return parser.parse_args()


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_sha(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows), encoding="utf-8")


def relative(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return str(path.relative_to(ROOT))


def verify_frozen():
    manifest = read_json(FREEZE / "freeze_manifest.json")
    components = []
    for item in manifest["components"]:
        path = FREEZE / item["path"]
        actual = sha(path) if path.is_file() else None
        components.append({"path": item["path"], "expected_sha256": item["sha256"],
                           "actual_sha256": actual, "match": actual == item["sha256"]})
    aggregate = object_sha([(item["path"], item["actual_sha256"]) for item in components])
    match = (all(item["match"] for item in components)
             and manifest["heldout_v1_protocol_sha256"] == EXPECTED_PROTOCOL_HASH
             and aggregate == EXPECTED_PROTOCOL_HASH)
    if not match:
        raise RuntimeError("Frozen held-out protocol hash mismatch")
    if sha(GATE) != EXPECTED_GATE_HASH:
        raise RuntimeError("Frozen v2.2 gate hash mismatch")
    return manifest, components, aggregate


def protected_hashes():
    paths = [path for path in sorted(FREEZE.iterdir()) if path.is_file()] + [GATE]
    return {relative(path): sha(path) for path in paths}


class Network:
    def __init__(self, execute):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        prior = read_json(self.receipt) if self.receipt.exists() else {}
        self.events = prior.get("events", [])
        self.failures = prior.get("failures", [])

    def save(self):
        write_json(self.receipt, {"events": self.events, "failures": self.failures,
                                  "provider_calls": 0, "llm_calls": 0,
                                  "general_web_fallback_calls": 0, "publisher_fallback_calls": 0,
                                  "scientific_extraction_calls": 0})

    def get(self, url, path, kind, lineage):
        path = Path(path)
        if path.is_file():
            return path.read_bytes()
        if not self.execute:
            raise RuntimeError("Network execution flag is required")
        parsed = urllib.parse.urlparse(url)
        normalized_host = (parsed.hostname or "").casefold()
        if normalized_host != "eutils.ncbi.nlm.nih.gov" or not parsed.path.startswith("/entrez/eutils/"):
            raise RuntimeError(f"Forbidden network destination: {normalized_host}")
        verify_frozen()
        for attempt in range(1, 5):
            stamp = None  # keep the retry loop free of mutable scientific state
            stamp = now()
            request = urllib.request.Request(
                url, headers={"User-Agent": "conflict-oriented-discovery-engine-heldout-v1/1.0"}
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read()
                    status = response.status
                    content_type = response.headers.get("Content-Type")
                break
            except Exception as exc:
                self.failures.append({"kind": kind, "timestamp": stamp, "url": url,
                                      "lineage": lineage, "attempt": attempt,
                                      "error_type": type(exc).__name__, "error": str(exc)})
                self.save()
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.events.append({"request_id": f"heldout_v1_ncbi_request_{len(self.events)+1:04d}",
                            "kind": kind, "timestamp": stamp, "url": url,
                            "http_status": status, "content_type": content_type,
                            "snapshot_ref": relative(path), "response_sha256": sha(path),
                            "bytes": len(body), "lineage": lineage})
        self.save()
        time.sleep(0.36)
        return body


def gate_target(scientific, retrieval, variants):
    adapted = dict(scientific)
    adapted["measurement_requirement"] = scientific["measurement_target"]
    adapted["therapy_identity_requirement"] = scientific.get("therapy") or "not required"
    plan = {"scientific_proposition_target": adapted, "retrieval_target": retrieval}
    compiler_variants = [{"term_authority_annotations": row["lexical_provenance"]} for row in variants]
    return build_target_contract(plan, [], compiler_variants)


def normalized(text):
    return " ".join("".join(char.casefold() if char.isalnum() else " " for char in (text or "")).split())


def deterministic_excerpts(xml_path, surfaces, limit=6):
    root = ET.parse(xml_path).getroot()
    candidates = []
    normalized_surfaces = [(surface, normalized(surface)) for surface in surfaces if normalized(surface)]
    for index, node in enumerate(root.findall(".//body//p"), 1):
        text = " ".join(text_of(node).split())
        if not text:
            continue
        norm = normalized(text)
        matched = [surface for surface, value in normalized_surfaces if value in norm]
        candidates.append({"paragraph_index": index, "text": text[:1600],
                           "matched_frozen_surfaces": matched})
    selected = [row for row in candidates if row["matched_frozen_surfaces"]][:limit]
    if not selected:
        selected = candidates[:min(3, limit)]
    return selected


def main(execute_network):
    if not execute_network:
        raise RuntimeError("Explicit --execute-network flag required after user authorization")
    if RUN.exists() and any(path.name not in REQUIRED and path.name != "retrieval_assets" for path in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    manifest, component_checks, protocol_hash = verify_frozen()
    preflight = read_json(PREFLIGHT / "summary.json")
    if not preflight["protocol_hash_match"] or preflight["network_calls"] != 0:
        raise RuntimeError("Offline preflight did not pass cleanly")
    RUN.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    protected_before = protected_hashes()
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()

    registry = read_jsonl(FREEZE / "heldout_case_registry.jsonl")
    scientific_rows = read_jsonl(FREEZE / "heldout_scientific_targets.jsonl")
    retrieval_rows = read_jsonl(FREEZE / "heldout_retrieval_targets.jsonl")
    variants = read_jsonl(FREEZE / "heldout_query_variants.jsonl")
    queries = read_jsonl(FREEZE / "heldout_frozen_queries.jsonl")
    budget = read_json(FREEZE / "heldout_budget_binding.json")
    acquisition = read_json(FREEZE / "heldout_fulltext_acquisition_protocol.json")
    case_map = {row["case_id"]: row for row in registry}
    scientific = {row["case_id"]: row for row in scientific_rows}
    retrieval = {row["case_id"]: row for row in retrieval_rows}
    targets = {case_id: gate_target(scientific[case_id], retrieval[case_id],
                                    [row for row in variants if row["case_id"] == case_id])
               for case_id in CASE_IDS}

    write_json(RUN / "protocol_verification.json", {
        "status": "PASS", "explicit_user_network_authorization": True,
        "authorization_scope": "eight frozen held-out v1 cases; exact 48 PubMed queries; at most 180 unique metadata records and 10 legal PMC fulltexts per case",
        "frozen_protocol_ref": relative(FREEZE), "expected_protocol_sha256": EXPECTED_PROTOCOL_HASH,
        "recomputed_protocol_sha256": protocol_hash, "protocol_hash_match": True,
        "heldout_case_count": len(registry), "frozen_query_count": len(queries),
        "metadata_soft_checkpoint": 120, "metadata_hard_safety_ceiling": 180,
        "adaptive_early_stop_state": "deferred", "max_fulltext_selection_per_case": 10,
        "allowed_network_services": ["NCBI PubMed E-utilities", "NCBI PMC E-utilities"],
        "provider_authorized": False, "llm_authorized": False,
        "general_web_fallback_authorized": False, "publisher_fallback_authorized": False,
        "scientific_extraction_authorized": False, "relevance_prediction_authorized": False,
        "git_head_at_execution": git_head,
    })
    write_json(RUN / "freeze_hash_verification.json", {
        "status": "PASS", "components": component_checks, "all_component_hashes_match": True,
        "manifest_protocol_sha256": manifest["heldout_v1_protocol_sha256"],
        "recomputed_protocol_sha256": protocol_hash, "protocol_hash_match": True,
        "gate_expected_sha256": EXPECTED_GATE_HASH, "gate_actual_sha256": sha(GATE),
        "gate_hash_match": sha(GATE) == EXPECTED_GATE_HASH,
    })

    network = Network(execute_network)
    case_pmids = {case_id: [] for case_id in CASE_IDS}
    seen = {case_id: set() for case_id in CASE_IDS}
    occurrences = defaultdict(list)
    query_logs = []
    query_failed = defaultdict(bool)
    for case_id in CASE_IDS:
        active = [{"query": row, "retstart": 0, "page": 1}
                  for row in queries if row["case_id"] == case_id]
        executed_query_ids = set()
        while active:
            next_active = []
            for item in active:
                query = item["query"]
                at_cap = len(case_pmids[case_id]) >= 180
                if at_cap and query["query_variant_id"] in executed_query_ids:
                    continue
                retmax = 0 if at_cap else 30
                params = {"db": "pubmed", "term": query["query_text"],
                          "retstart": item["retstart"], "retmax": retmax,
                          "retmode": "json", "sort": query["sort"],
                          "tool": "conflict_oriented_discovery_engine"}
                suffix = f"retstart_{item['retstart']:04d}_retmax_{retmax:03d}"
                path = ASSETS / "pubmed_esearch" / case_id / f"{query['query_variant_id']}__{suffix}.json"
                url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
                stamp = now()
                try:
                    raw = network.get(url, path, "pubmed_esearch_heldout_v1",
                                      {"case_id": case_id, "query_variant_id": query["query_variant_id"],
                                       "query_order": query["query_order"], "retstart": item["retstart"],
                                       "retmax": retmax})
                    if len(raw) > 10_000_000:
                        raise RuntimeError("Unexpectedly large PubMed esearch response")
                    payload = json.loads(raw.decode("utf-8"))["esearchresult"]
                    ids = [str(value) for value in payload.get("idlist", [])]
                    total = int(payload.get("count", 0))
                    added = []
                    for rank_offset, pmid in enumerate(ids, item["retstart"] + 1):
                        if pmid in seen[case_id]:
                            occurrences[(case_id, pmid)].append({
                                "query_family_id": query["query_family_id"],
                                "query_variant_id": query["query_variant_id"],
                                "query_order": query["query_order"], "query_rank": rank_offset})
                        elif len(case_pmids[case_id]) < 180:
                            seen[case_id].add(pmid)
                            case_pmids[case_id].append(pmid)
                            added.append(pmid)
                            occurrences[(case_id, pmid)].append({
                                "query_family_id": query["query_family_id"],
                                "query_variant_id": query["query_variant_id"],
                                "query_order": query["query_order"], "query_rank": rank_offset})
                    snapshot_ref = relative(path)
                    event = next((row for row in reversed(network.events)
                                  if row["snapshot_ref"] == snapshot_ref), None)
                    query_logs.append({"case_id": case_id, "query_family_id": query["query_family_id"],
                        "query_variant_id": query["query_variant_id"], "query_order": query["query_order"],
                        "query_text": query["query_text"], "sort": query["sort"],
                        "page_order": item["page"], "retstart": item["retstart"], "retmax": retmax,
                        "execution_status": "executed", "execution_timestamp": event["timestamp"] if event else stamp,
                        "request_id": event["request_id"] if event else None, "result_count": total,
                        "returned_id_count": len(ids), "new_unique_additions": len(added),
                        "cumulative_unique_metadata_records": len(case_pmids[case_id]),
                        "execution_mode": "count_only_after_hard_ceiling" if retmax == 0 else "metadata_retrieval",
                        "raw_response_snapshot_ref": snapshot_ref, "response_sha256": sha(path),
                        "query_modified": False})
                    executed_query_ids.add(query["query_variant_id"])
                    next_offset = item["retstart"] + len(ids)
                    if retmax and ids and next_offset < total and len(case_pmids[case_id]) < 180:
                        next_active.append({"query": query, "retstart": next_offset, "page": item["page"] + 1})
                except Exception as exc:
                    query_failed[case_id] = True
                    query_logs.append({"case_id": case_id, "query_family_id": query["query_family_id"],
                        "query_variant_id": query["query_variant_id"], "query_order": query["query_order"],
                        "query_text": query["query_text"], "sort": query["sort"],
                        "page_order": item["page"], "retstart": item["retstart"], "retmax": retmax,
                        "execution_status": "failed", "execution_timestamp": stamp,
                        "error_type": type(exc).__name__, "error": str(exc),
                        "new_unique_additions": 0, "query_modified": False})
            active = next_active
        if set(row["query_variant_id"] for row in queries if row["case_id"] == case_id) != executed_query_ids:
            query_failed[case_id] = True
    write_jsonl(RUN / "query_execution_log.jsonl", query_logs)

    all_pmids = sorted({pmid for rows in case_pmids.values() for pmid in rows}, key=int)
    publications = {}
    for batch, start in enumerate(range(0, len(all_pmids), 100), 1):
        ids = all_pmids[start:start + 100]
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "pubmed_efetch" / f"batch_{batch:03d}.xml"
        raw = network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                          "pubmed_efetch_heldout_v1", {"pmids": ids, "batch": batch})
        publications.update(parse_pubmed(raw))

    metadata_rows = []
    screen_rows = []
    gate_rows = []
    gate_by_key = {}
    for case_id in CASE_IDS:
        for depth, pmid in enumerate(case_pmids[case_id], 1):
            pub = publications.get(pmid, {"canonical_publication_id": f"pmid:{pmid}", "pmid": pmid,
                "pmcid": None, "doi": None, "title": "", "abstract": "", "publication_types": [],
                "journal": "", "publication_date": ""})
            snapshot = ASSETS / "abstracts" / f"pmid_{pmid}.json"
            write_json(snapshot, pub)
            lineage = occurrences[(case_id, pmid)]
            first = lineage[0]
            metadata_rows.append({"case_id": case_id, "case_publication_identity": f"{case_id}:pmid:{pmid}",
                "canonical_publication_id": f"pmid:{pmid}", "pmid": pmid, "pmcid": pub.get("pmcid"),
                "doi": pub.get("doi"), "title": pub["title"], "publication_type": pub["publication_types"],
                "journal": pub["journal"], "publication_date": pub["publication_date"],
                "abstract": pub["abstract"], "metadata_depth": depth,
                "first_query_family_id": first["query_family_id"],
                "first_query_variant_id": first["query_variant_id"],
                "first_query_rank": first["query_rank"], "query_provenance": lineage,
                "deduplication_identity": "PMID within case", "metadata_resolved": pmid in publications,
                "abstract_snapshot_ref": relative(snapshot), "abstract_snapshot_sha256": sha(snapshot)})
            scientific_input = {"title": pub["title"], "abstract": pub["abstract"],
                "publication_types": pub["publication_types"], "publication_types_reliable": True,
                "target": targets[case_id]}
            decision = evaluate(scientific_input)
            screen_state = ("ABSTRACT_PLAUSIBLE" if decision["state"] in {"TIER_A", "TIER_B"}
                            else "ABSTRACT_KNOWN_MISMATCH" if decision["state"] == "REJECT"
                            else "ABSTRACT_INSUFFICIENT_PLAUSIBILITY")
            screen_rows.append({"case_id": case_id, "pmid": pmid, "metadata_depth": depth,
                "screen_state": screen_state, "abstract_present": bool(pub["abstract"]),
                "candidate_tier_state": decision["state"], "query_provenance": lineage,
                "abstract_snapshot_ref": relative(snapshot), "abstract_snapshot_sha256": sha(snapshot),
                "scientific_proposition_compatibility_inferred": False,
                "relevance_prediction_performed": False})
            output = {"case_id": case_id, "pmid": pmid, "canonical_publication_id": f"pmid:{pmid}",
                "metadata_depth": depth, "query_provenance": lineage,
                "scientific_input_sha256": object_sha(scientific_input),
                "input_scope": "metadata, publication type, abstract, frozen targets and lexical authorities only",
                "fulltext_facts_used": False, "reviewer_labels_used": False,
                "previous_calibration_rationale_used": False, **decision}
            gate_rows.append(output)
            gate_by_key[(case_id, pmid)] = output
    write_jsonl(RUN / "metadata_inventory.jsonl", metadata_rows)
    write_jsonl(RUN / "abstract_screening.jsonl", screen_rows)
    write_jsonl(RUN / "v22_gate_outputs.jsonl", gate_rows)

    selection_rows = []
    selected = []
    for case_id in CASE_IDS:
        candidates = [row for row in gate_rows if row["case_id"] == case_id and row["state"] in {"TIER_A", "TIER_B"}]
        candidates.sort(key=lambda row: (row["state"] != "TIER_A", row["metadata_depth"], int(row["pmid"])))
        eligible = [row for row in candidates if publications[row["pmid"]].get("pmcid")]
        selected_keys = {(row["case_id"], row["pmid"]) for row in eligible[:10]}
        selection_index = {row["pmid"]: index for index, row in enumerate(eligible[:10], 1)}
        for candidate in candidates:
            pub = publications[candidate["pmid"]]
            is_selected = (case_id, candidate["pmid"]) in selected_keys
            row = {"case_id": case_id, "pmid": candidate["pmid"], "pmcid": pub.get("pmcid"),
                "metadata_depth": candidate["metadata_depth"], "tier_state": candidate["state"],
                "selected": is_selected, "selection_index_within_case": selection_index.get(candidate["pmid"]),
                "pmcid_available": bool(pub.get("pmcid")), "no_pmcid": not bool(pub.get("pmcid")),
                "oa_available": None, "acquisition_attempted": False, "acquired": False,
                "retrieval_failure": False,
                "selection_policy": "Tier A before Tier B, then metadata depth and numeric PMID; PMCID required; maximum 10 per case",
                "reviewer_label_influence": False, "relevance_prediction_used": False}
            selection_rows.append(row)
            if is_selected:
                selected.append(row)

    attempts = []
    acquired = []
    pmc_cache = {}
    for selection in sorted(selected, key=lambda row: (CASE_IDS.index(row["case_id"]), row["selection_index_within_case"])):
        case_id, pmid, pmcid = selection["case_id"], selection["pmid"], selection["pmcid"]
        base = {"attempt_id": f"heldout_v1_oa_{len(attempts)+1:04d}", "case_id": case_id,
                "pmid": pmid, "pmcid": pmcid, "metadata_depth": selection["metadata_depth"],
                "tier_state": selection["tier_state"], "selected": True,
                "selection_index_within_case": selection["selection_index_within_case"],
                "pmcid_available": True, "no_pmcid": False,
                "fulltext_selection_ceiling_per_case": 10}
        if pmcid in pmc_cache:
            cached = pmc_cache[pmcid]
            row = {**base, **cached, "network_request_made": False, "cross_case_cache_hit": True,
                   "reason": "reused current-run canonical PMCID acquisition result"}
            attempts.append(row)
            if row["status"] == "fulltext_acquired":
                acquired.append(row)
            continue
        params = {"db": "pmc", "id": pmcid, "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        try:
            raw = network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                              "pmc_fulltext_efetch_heldout_v1",
                              {"case_id": case_id, "pmid": pmid, "pmcid": pmcid})
            root = ET.fromstring(raw)
            article_ok = root.find(".//article") is not None or root.tag.endswith("article")
            xml_pmids = [text_of(node) for node in root.findall(".//article-id[@pub-id-type='pmid']")]
            identity_ok = not xml_pmids or pmid in xml_pmids
            status = ("fulltext_acquired" if article_ok and identity_ok else
                      "fulltext_identity_mismatch" if article_ok else "fulltext_retrieval_failed")
            reason = ("legal PMC XML article acquired and identity checked" if status == "fulltext_acquired"
                      else "PMC XML article or PMID identity validation failed")
            cached = {"status": status, "oa_available": status == "fulltext_acquired",
                      "acquisition_attempted": True, "acquired": status == "fulltext_acquired",
                      "retrieval_failure": status != "fulltext_acquired", "snapshot_ref": relative(path),
                      "content_hash": sha(path), "source_identity": "NCBI PMC efetch"}
            pmc_cache[pmcid] = cached
            row = {**base, **cached, "network_request_made": True, "cross_case_cache_hit": False,
                   "reason": reason}
            attempts.append(row)
            if status == "fulltext_acquired":
                acquired.append(row)
        except Exception as exc:
            cached = {"status": "fulltext_retrieval_failed", "oa_available": None,
                      "acquisition_attempted": True, "acquired": False, "retrieval_failure": True,
                      "source_identity": "NCBI PMC efetch"}
            pmc_cache[pmcid] = cached
            attempts.append({**base, **cached, "network_request_made": True,
                             "cross_case_cache_hit": False, "reason": str(exc),
                             "error_type": type(exc).__name__})
    attempt_by_key = {(row["case_id"], row["pmid"]): row for row in attempts}
    for row in selection_rows:
        attempt = attempt_by_key.get((row["case_id"], row["pmid"]))
        if attempt:
            row.update({key: attempt[key] for key in
                        ("oa_available", "acquisition_attempted", "acquired", "retrieval_failure")})
            row["acquisition_status"] = attempt["status"]
        elif row["no_pmcid"]:
            row["oa_available"] = False
            row["acquisition_status"] = "no_pmcid_not_selected"
        else:
            row["acquisition_status"] = "eligible_not_selected_ceiling"
    write_jsonl(RUN / "fulltext_selection_inventory.jsonl", selection_rows)
    write_jsonl(RUN / "fulltext_acquisition_attempts.jsonl", attempts)
    write_jsonl(RUN / "fulltext_manifest.jsonl", acquired)

    packets = []
    metadata_by_key = {(row["case_id"], row["pmid"]): row for row in metadata_rows}
    for index, row in enumerate(acquired, 1):
        case_id, pmid = row["case_id"], row["pmid"]
        pub = publications[pmid]
        gate = gate_by_key[(case_id, pmid)]
        meta = metadata_by_key[(case_id, pmid)]
        surfaces = targets[case_id]["subject_surfaces"] + targets[case_id]["endpoint_surfaces"]
        excerpts = deterministic_excerpts(ROOT / row["snapshot_ref"], surfaces)
        packet_id = f"heldout_rrpv1_{index:04d}"
        expected = list(gate["unresolved_fields_requiring_fulltext"])
        if not expected:
            expected = ["scientific proposition compatibility", "endpoint evidence and measurement",
                        "context and biological-unit fit"]
        packets.append({"artifact_schema_version": "RetrievalRelevanceReviewPacketV1-compatible",
            "packet_id": packet_id, "case_id": case_id, "ambiguity": case_map[case_id]["ambiguity_tier"],
            "metadata_depth": meta["metadata_depth"], "tier": gate["state"],
            "scientific_target": scientific[case_id], "retrieval_target": retrieval[case_id],
            "query_family_variant_provenance": meta["query_provenance"],
            "publication_identity": {"pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "title": pub["title"], "publication_types": pub["publication_types"],
                "publication_date": pub["publication_date"]},
            "pre_acquisition_gate_states": gate["gates"], "abstract": pub["abstract"],
            "fulltext_ref": row["snapshot_ref"], "fulltext_sha256": row["content_hash"],
            "deterministic_fulltext_excerpts": excerpts,
            "excerpt_selection_policy": "document-order PMC body paragraphs matching frozen subject or endpoint surfaces; structural fallback only; no scientific interpretation",
            "fields_expected_to_resolve": expected,
            "adjudication": {"relevance_state": None, "acquisition_decision": None,
                "matched_target_components": [], "mismatched_target_components": [],
                "contaminant_class": None, "reviewer_rationale": None, "confidence": None},
            "automatic_relevance_prediction": None, "acquisition_quality_prediction": None,
            "confidence_prediction": None, "manual_relevance_status": "pending",
            "scientific_extraction_performed": False})
    write_jsonl(RUN / "neutral_review_packets.jsonl", packets)

    case_metrics = []
    for case_id in CASE_IDS:
        case_gates = [row for row in gate_rows if row["case_id"] == case_id]
        case_selections = [row for row in selection_rows if row["case_id"] == case_id]
        case_attempts = [row for row in attempts if row["case_id"] == case_id]
        count = len(case_pmids[case_id])
        case_metrics.append({"case_id": case_id, "ambiguity": case_map[case_id]["ambiguity_tier"],
            "unique_metadata_records": count, "deepest_metadata_depth": count,
            "metadata_soft_checkpoint": 120, "metadata_hard_safety_ceiling": 180,
            "hard_ceiling_reached": count == 180,
            "natural_exhaustion": count < 180 and not query_failed[case_id],
            "completion_reason": "hard_metadata_ceiling" if count == 180 else
                                 "frozen_queries_naturally_exhausted" if not query_failed[case_id] else "network_failure",
            "adaptive_early_stop_used": False,
            "abstract_plausible_count": sum(row["state"] in {"TIER_A", "TIER_B"} for row in case_gates),
            "tier_a_count": sum(row["state"] == "TIER_A" for row in case_gates),
            "tier_b_count": sum(row["state"] == "TIER_B" for row in case_gates),
            "reject_count": sum(row["state"] == "REJECT" for row in case_gates),
            "insufficient_plausibility_count": sum(row["state"] is None for row in case_gates),
            "tier_a_b_with_no_pmcid_count": sum(row["no_pmcid"] for row in case_selections),
            "oa_selected_count": sum(row["selected"] for row in case_selections),
            "oa_acquisition_attempt_count": len(case_attempts),
            "oa_acquired_count": sum(row["acquired"] for row in case_attempts),
            "oa_retrieval_failure_count": sum(row["retrieval_failure"] for row in case_attempts),
            "neutral_review_packet_count": sum(row["case_id"] == case_id for row in packets),
            "relevance_metrics_calculated": False})
    write_jsonl(RUN / "case_retrieval_metrics.jsonl", case_metrics)
    ambiguity_metrics = []
    for ambiguity in ("LOW", "MEDIUM", "HIGH"):
        rows = [row for row in case_metrics if row["ambiguity"] == ambiguity]
        ambiguity_metrics.append({"ambiguity": ambiguity, "case_count": len(rows),
            **{field: sum(row[field] for row in rows) for field in
               ("unique_metadata_records", "abstract_plausible_count", "tier_a_count", "tier_b_count",
                "reject_count", "insufficient_plausibility_count", "oa_selected_count",
                "oa_acquired_count", "oa_retrieval_failure_count", "neutral_review_packet_count")},
            "relevance_metrics_calculated": False})
    write_jsonl(RUN / "ambiguity_retrieval_metrics.jsonl", ambiguity_metrics)
    write_jsonl(RUN / "heldout_case_execution_inventory.jsonl", [
        {**case_map[row["case_id"]], "execution_state": "RETRIEVAL_COMPLETE",
         "unique_metadata_records": row["unique_metadata_records"],
         "completion_reason": row["completion_reason"], "frozen_query_count": 6,
         "query_modifications": 0, "target_modifications": 0, "case_replacements": 0}
        for row in case_metrics
    ])

    request_counts = Counter(row["kind"] for row in network.events)
    write_json(RUN / "network_usage_audit.json", {
        "authorized": True, "authorization_scope_respected": True,
        "allowed_services_only": all(urllib.parse.urlparse(row["url"]).hostname == "eutils.ncbi.nlm.nih.gov"
                                     for row in network.events),
        "network_request_count": len(network.events) + len(network.failures),
        "successful_network_response_count": len(network.events),
        "failed_network_attempt_count": len(network.failures),
        "request_counts_by_kind": dict(request_counts), "event_receipt_ref": relative(network.receipt),
        "general_web_fallback_calls": 0, "publisher_fallback_calls": 0,
        "credentials_logged": False})
    write_json(RUN / "provider_usage_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "provider_or_model_client_created": False,
        "scientific_extraction_calls": 0, "relevance_prediction_calls": 0,
        "deterministic_excerpt_preparation_only": True})
    protected_after = protected_hashes()
    changed = sorted(path for path in protected_before if protected_before[path] != protected_after[path])
    write_json(RUN / "protocol_leakage_audit.json", {
        "query_modifications": 0, "target_modifications": 0, "gate_modifications": 0,
        "budget_modifications": 0, "case_replacements": 0, "adaptive_early_stopping_used": False,
        "metadata_depth_above_180": False, "post_hoc_rule_tuning": False,
        "previous_calibration_rationale_used": False, "heldout_relevance_conclusion_created": False,
        "preregistered_heuristic_pass_fail_calculated": False, "status": "NO_PROTOCOL_LEAKAGE"})
    write_json(RUN / "scientific_state_safety_audit.json", {
        "historical_assets_modified": bool(changed), "changed_protected_paths": changed,
        "frozen_protocol_sha256_before": EXPECTED_PROTOCOL_HASH,
        "frozen_protocol_sha256_after": verify_frozen()[2],
        "frozen_gate_sha256_before": EXPECTED_GATE_HASH, "frozen_gate_sha256_after": sha(GATE),
        "relevance_labels_created": False, "scientific_extraction_performed": False,
        "support_opposition_or_conflict_inferred": False, "production_behavior_modified": False,
        "git_mutation_invoked": False})

    executed_ids = {row["query_variant_id"] for row in query_logs if row["execution_status"] == "executed"}
    packet_blank = all(packet["adjudication"][field] is None
                       for packet in packets for field in
                       ("relevance_state", "acquisition_decision", "contaminant_class",
                        "reviewer_rationale", "confidence"))
    validation = {
        "protocol_hash_match": verify_frozen()[2] == EXPECTED_PROTOCOL_HASH,
        "heldout_case_count_8": len(case_metrics) == 8,
        "all_48_frozen_queries_executed": len(executed_ids) == 48,
        "query_modifications_zero": all(not row["query_modified"] for row in query_logs),
        "target_modifications_zero": True, "gate_modifications_zero": sha(GATE) == EXPECTED_GATE_HASH,
        "budget_modifications_zero": True, "case_replacements_zero": True,
        "metadata_depth_per_case_at_most_180": all(row["unique_metadata_records"] <= 180 for row in case_metrics),
        "all_cases_complete_by_ceiling_or_natural_exhaustion": all(
            row["completion_reason"] in {"hard_metadata_ceiling", "frozen_queries_naturally_exhausted"}
            for row in case_metrics),
        "no_adaptive_early_stop": all(not row["adaptive_early_stop_used"] for row in case_metrics),
        "fulltext_selected_per_case_at_most_10": all(row["oa_selected_count"] <= 10 for row in case_metrics),
        "selected_are_tier_a_or_b_with_pmcid": all(row["tier_state"] in {"TIER_A", "TIER_B"}
                                                    and row["pmcid_available"] for row in selected),
        "neutral_packets_only_for_acquired": len(packets) == len(acquired),
        "neutral_packet_adjudication_fields_blank": packet_blank,
        "no_relevance_predictions": all(packet["automatic_relevance_prediction"] is None for packet in packets),
        "provider_calls_zero": True, "llm_calls_zero": True,
        "general_web_fallback_zero": True, "publisher_fallback_zero": True,
        "scientific_extraction_calls_zero": True,
        "historical_assets_unchanged": not changed,
        "metadata_records_resolved": all(row["metadata_resolved"] for row in metadata_rows),
    }
    write_json(RUN / "validation.json", {"status": "PASS" if all(validation.values()) else "FAIL",
                                         "checks": validation})
    aggregate = {field: sum(row[field] for row in case_metrics) for field in
                 ("unique_metadata_records", "abstract_plausible_count", "tier_a_count", "tier_b_count",
                  "reject_count", "insufficient_plausibility_count", "oa_selected_count",
                  "oa_acquired_count", "oa_retrieval_failure_count", "neutral_review_packet_count")}
    summary = {"status": "completed" if all(validation.values()) else "failed",
        "heldout_v1_protocol_sha256": EXPECTED_PROTOCOL_HASH, "heldout_case_count": 8,
        "frozen_query_count": 48, **aggregate,
        "per_case": case_metrics, "relevance_metrics_calculated": False,
        "heldout_relevance_conclusion_created": False, "preregistered_heuristic_pass_fail_calculated": False,
        "neutral_review_batch_state": "GENERATED_PENDING_SEPARATE_FREEZE",
        "network_request_count": len(network.events) + len(network.failures),
        "network_calls": len(network.events) + len(network.failures),
        "provider_calls": 0, "llm_calls": 0, "general_web_fallback_calls": 0,
        "publisher_fallback_calls": 0, "extraction_calls": 0,
        "query_modifications": 0, "target_modifications": 0, "gate_modifications": 0,
        "budget_modifications": 0, "case_replacements": 0, "adaptive_early_stopping_used": False,
        "historical_assets_modified": bool(changed), "git_mutation_invoked": False}
    write_json(RUN / "summary.json", summary)
    files = []
    for path in sorted(RUN.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append({"path": str(path.relative_to(RUN)), "sha256": sha(path),
                          "bytes": path.stat().st_size,
                          "record_count": len(read_jsonl(path)) if path.suffix == ".jsonl" else 1})
    write_json(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED),
        "required_artifacts": REQUIRED, "files": files,
        "heldout_v1_protocol_sha256": EXPECTED_PROTOCOL_HASH,
        "network_request_count": summary["network_request_count"], "provider_calls": 0,
        "llm_calls": 0, "general_web_fallback_calls": 0, "publisher_fallback_calls": 0,
        "extraction_calls": 0, "historical_assets_modified": bool(changed)})
    print(json.dumps(summary, indent=2))
    if not all(validation.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main(arguments().execute_network)
