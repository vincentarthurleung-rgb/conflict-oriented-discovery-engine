#!/usr/bin/env python3
"""Execute the frozen alpha3.4 development retrospective retrieval.

The only network routes are frozen NCBI PubMed/PMC E-utilities routes.  This
tool performs no planner, provider, LLM, relevance-adjudication, or known-paper
recovery operation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.biological_unit_compatibility_v1_1 import (
    BiologicalUnitRegistryV1_1, decide_biological_unit_compatibility_v1_1,
)
from code_engine.search.endpoint_semantics_v1 import decide_endpoint_semantics_v1
from code_engine.search.functional_relation_evidence_v1_1 import decide_functional_relation_evidence_v1_1
from code_engine.search.search_plan_v23_beta_policy import decide_search_plan_v23_beta_disposition
from tools.run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, text_of
from tools.run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval import (
    gate_target, frozen_inputs as v23_frozen_inputs,
)
from tools.search_plan_v22_candidate_gates import evaluate

RUN = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval"
ASSETS = RUN / "retrieval_assets"
PREREG = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
EXECUTION_MANIFEST = PREREG / "development_retrospective_retrieval_execution_manifest.json"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

EXPECTED_PREREG = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
EXPECTED_EXECUTION = "559b09754580bb06f05c51cc58f513e5364d2a5e2d541a8a074351a8b09f9320"
EXPECTED_ALPHA33 = "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"
EXPECTED_QUERY_SET = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"
CASES = tuple(f"heldout_v2_{n}" for n in range(101, 109))
SOFT_TAIL, HARD_TAIL, PAGE_SIZE, FULLTEXT_LIMIT = 120, 180, 30, 10

UNIT_REGISTRY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1.json"
UNIT_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1_1.json"
UNIT_POLICY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1.json"
UNIT_POLICY_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1_1.json"
RELATION_POLICY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json"
RELATION_POLICY_OVERLAY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json"
ENDPOINT_REGISTRY_PATH = ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json"
ENDPOINT_POLICY_PATH = ROOT / "configs/search_plans/endpoint_semantics_policy_v1.json"
BETA_CONFIG_PATH = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline/search_plan_v23_beta_config_snapshot.json"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return value_sha(pairs)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def write(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and path.read_bytes() == body, f"refusing to change frozen output: {name}")
        return
    path.write_bytes(body)


def verify_aggregate(run: Path, validation_name: str, root_name: str, expected: str) -> dict[str, Any]:
    validation = load(run / validation_name)
    pairs = validation["aggregate_components"]
    for name, digest in pairs:
        require(sha(run / name) == digest, f"upstream component changed: {run.name}/{name}")
    actual = aggregate(pairs)
    recorded = (run / root_name).read_text().strip()
    require(actual == recorded == expected, f"upstream root mismatch: {run.name}")
    return {"path": rel(run), "expected": expected, "actual": actual, "verified": True}


def preflight() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    prereg = verify_aggregate(PREREG, "validation.json", "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_PREREG)
    alpha33 = verify_aggregate(ALPHA33, "validation.json", "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33)
    require(sha(EXECUTION_MANIFEST) == EXPECTED_EXECUTION, "execution manifest hash mismatch")
    manifest = load(EXECUTION_MANIFEST)
    require(manifest["compiled_query_set_sha256"] == EXPECTED_QUERY_SET, "query set hash mismatch")
    require(manifest["state"] == "FROZEN_AWAITING_SEPARATE_NETWORK_AUTHORIZATION", "manifest state mismatch")
    require(manifest["retrieval_executed"] is False, "preregistered manifest already marked executed")
    queries = manifest["exact_queries"]
    require(len(queries) == 29 and tuple(sorted({q["case_id"] for q in queries})) == CASES,
            "frozen query corpus mismatch")
    query_policy = load(PREREG / "query_execution_policy.json")
    tail = load(PREREG / "tail_policy.json")
    retry = load(PREREG / "retrieval_retry_policy.json")
    fulltext = load(PREREG / "fulltext_acquisition_policy.json")
    require(query_policy["page_size"] == PAGE_SIZE and query_policy["pubmed_sort"] == "relevance",
            "query transport policy mismatch")
    require((tail["soft_tail"], tail["hard_tail"], tail["adaptive_tail_enabled"]) ==
            (SOFT_TAIL, HARD_TAIL, False), "tail policy mismatch")
    require(retry["maximum_total_attempts"] == 4 and retry["timeout_seconds"] == 60,
            "retry policy mismatch")
    require(fulltext["maximum_fulltexts_per_case"] == FULLTEXT_LIMIT, "fulltext cap mismatch")

    old_targets, old_bindings, old_queries = v23_frozen_inputs()
    targets = {row["case_id"]: row for row in old_targets}
    require(tuple(sorted(targets)) == CASES, "target set mismatch")
    for case_id, expected in manifest["target_hashes"].items():
        require(value_sha(targets[case_id]) == expected, f"target hash mismatch: {case_id}")
    gate_queries = defaultdict(list)
    for query in old_queries:
        gate_queries[query["case_id"]].append(query)
    gates = {case_id: gate_target(targets[case_id], old_bindings[case_id], gate_queries[case_id])
             for case_id in CASES}
    verification = {
        "artifact_schema_version": "Alpha3_4ExecutionAuthorizationVerificationV1",
        "preregistration_root": prereg, "search_plan_root": alpha33,
        "execution_manifest_sha256": sha(EXECUTION_MANIFEST),
        "compiled_query_set_sha256": manifest["compiled_query_set_sha256"],
        "query_count": len(queries), "target_hashes_verified": True,
        "downstream_policy_hashes_verified": all(
            sha(PREREG / name) == digest for name, digest in manifest["downstream_policy_hashes"].items()),
        "network_authorization_required_for_execution": True,
    }
    require(verification["downstream_policy_hashes_verified"], "downstream policy hash mismatch")
    return verification, manifest, queries, old_targets, gates


class Network:
    def __init__(self, execute: bool):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        prior = load(self.receipt) if self.receipt.exists() else {}
        self.events = prior.get("events", [])
        self.failures = prior.get("failures", [])

    def save(self) -> None:
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_bytes(pretty({
            "events": self.events, "failures": self.failures,
            "provider_calls": 0, "llm_calls": 0, "planner_calls": 0,
            "general_web_fallback_calls": 0, "publisher_fallback_calls": 0,
            "known_pmid_checks": 0, "relevance_adjudication_calls": 0,
        }))

    def event_for(self, path: Path) -> dict[str, Any] | None:
        path_ref = rel(path)
        return next((event for event in reversed(self.events) if event["snapshot_ref"] == path_ref), None)

    def get(self, url: str, path: Path, kind: str, lineage: dict[str, Any]) -> tuple[bytes, dict[str, Any], bool]:
        if path.is_file():
            event = self.event_for(path)
            require(event is not None and event["response_sha256"] == sha(path),
                    f"cached response lacks matching receipt: {path}")
            return path.read_bytes(), event, False
        require(self.execute, "explicit --execute-network authorization flag required")
        parsed = urllib.parse.urlparse(url)
        require(parsed.hostname == "eutils.ncbi.nlm.nih.gov", "forbidden network host")
        require(parsed.path.startswith("/entrez/eutils/"), "forbidden network path")
        body = b""
        status = None
        content_type = None
        stamp = now()
        for attempt in range(1, 5):
            stamp = now()
            request = urllib.request.Request(
                url, headers={"User-Agent": "conflict-oriented-discovery-engine-v24-dev-retrospective/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read()
                    status = response.status
                    content_type = response.headers.get("Content-Type")
                break
            except Exception as exc:
                self.failures.append({"kind": kind, "timestamp_utc": stamp, "url": url,
                                      "lineage": lineage, "attempt": attempt,
                                      "error_type": type(exc).__name__, "error": str(exc)})
                self.save()
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        event = {
            "request_id": f"v24dev_ncbi_request_{len(self.events) + 1:05d}",
            "request_sequence": len(self.events) + len(self.failures) + 1,
            "kind": kind, "timestamp_utc": stamp, "url": url, "http_status": status,
            "content_type": content_type, "snapshot_ref": rel(path),
            "response_sha256": sha(path), "bytes": len(body), "lineage": lineage,
            "retry_count": attempt - 1,
        }
        self.events.append(event)
        self.save()
        time.sleep(0.36)
        return body, event, True


def execute_searches(network: Network, queries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    case_pmids = {case_id: [] for case_id in CASES}
    seen = {case_id: set() for case_id in CASES}
    logs = []
    for case_id in CASES:
        case_queries = [row for row in queries if row["case_id"] == case_id]
        active = [{"query": row, "retstart": 0, "page": 1} for row in case_queries]
        executed: set[str] = set()
        while active:
            next_active = []
            for item in active:
                query = item["query"]
                at_cap = len(case_pmids[case_id]) >= HARD_TAIL
                if at_cap and query["query_id"] in executed:
                    continue
                retmax = 0 if at_cap else PAGE_SIZE
                params = {"db": "pubmed", "term": query["exact_query_text"],
                          "retstart": item["retstart"], "retmax": retmax,
                          "retmode": "json", "sort": "relevance",
                          "tool": "conflict_oriented_discovery_engine"}
                suffix = f"retstart_{item['retstart']:04d}_retmax_{retmax:03d}"
                path = ASSETS / "pubmed_esearch" / case_id / f"{query['query_id'].replace(':', '_')}__{suffix}.json"
                url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
                try:
                    raw, event, _ = network.get(url, path, "pubmed_search", {
                        "case_id": case_id, "query_id": query["query_id"],
                        "query_sha256": query["query_sha256"], "intent_type": query["intent_type"],
                        "relation_core_ref": query["relation_core_ref"],
                        "retstart": item["retstart"], "retmax": retmax})
                    require(len(raw) <= 10_000_000, "unexpectedly large PubMed response")
                    result = json.loads(raw.decode())["esearchresult"]
                    ids = [str(value) for value in result.get("idlist", [])]
                    total = int(result.get("count", 0))
                    added = []
                    for pmid in ids:
                        if pmid not in seen[case_id] and len(case_pmids[case_id]) < HARD_TAIL:
                            seen[case_id].add(pmid)
                            case_pmids[case_id].append(pmid)
                            added.append(pmid)
                    logs.append({
                        "case_id": case_id, "query_id": query["query_id"],
                        "intent_type": query["intent_type"], "relation_core_ref": query["relation_core_ref"],
                        "frozen_query_sha256": query["query_sha256"],
                        "exact_query_text": query["exact_query_text"],
                        "execution_status": "SUCCESS", "raw_hit_count": total,
                        "returned_id_count": len(ids), "new_unique_additions": len(added),
                        "cumulative_unique_pmids": len(case_pmids[case_id]),
                        "request_id": event["request_id"], "request_sequence": event["request_sequence"],
                        "request_timestamp_utc": event["timestamp_utc"], "response_status": event["http_status"],
                        "raw_response_sha256": event["response_sha256"],
                        "raw_response_snapshot_ref": event["snapshot_ref"],
                        "retry_count": event["retry_count"], "page": item["page"],
                        "retstart": item["retstart"], "retmax": retmax,
                        "query_modified": False, "error_state": None})
                    executed.add(query["query_id"])
                    next_offset = item["retstart"] + len(ids)
                    if retmax and ids and next_offset < total and len(case_pmids[case_id]) < HARD_TAIL:
                        next_active.append({"query": query, "retstart": next_offset,
                                            "page": item["page"] + 1})
                except Exception as exc:
                    logs.append({"case_id": case_id, "query_id": query["query_id"],
                                 "intent_type": query["intent_type"],
                                 "frozen_query_sha256": query["query_sha256"],
                                 "exact_query_text": query["exact_query_text"],
                                 "execution_status": "TERMINAL_FAILURE", "raw_hit_count": None,
                                 "error_state": {"type": type(exc).__name__, "message": str(exc)},
                                 "page": item["page"], "retstart": item["retstart"], "retmax": retmax})
                    write("query_execution_log.jsonl", jsonl(logs))
                    raise RuntimeError(f"terminal PubMed search failure: {case_id}/{query['query_id']}") from exc
            active = next_active
        require(executed == {row["query_id"] for row in case_queries},
                f"not all frozen queries executed: {case_id}")
        print(f"search_complete case={case_id} unique_pmids={len(case_pmids[case_id])}", flush=True)
    return logs, case_pmids


def fetch_metadata(network: Network, case_pmids: dict[str, list[str]]) -> None:
    all_pmids = sorted({pmid for rows in case_pmids.values() for pmid in rows}, key=int)
    for batch, start in enumerate(range(0, len(all_pmids), 100), 1):
        ids = all_pmids[start:start + 100]
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "pubmed_efetch" / f"batch_{batch:03d}.xml"
        network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                    "pubmed_metadata", {"pmids": ids, "batch": batch})
        print(f"metadata_complete batch={batch} pmids={len(ids)}", flush=True)


def freeze_metadata_network(logs: list[dict[str, Any]], network: Network) -> str:
    write("query_execution_log.jsonl", jsonl(logs))
    metadata_events = [row for row in network.events if row["kind"] in {"pubmed_search", "pubmed_metadata"}]
    metadata_failures = [row for row in network.failures if row["kind"] in {"pubmed_search", "pubmed_metadata"}]
    receipt = ASSETS / "metadata_network_events.json"
    receipt.write_bytes(pretty({"events": metadata_events, "failures": metadata_failures,
                                "frozen_before_candidate_scoring": True}))
    files = sorted([p for p in (ASSETS / "pubmed_esearch").rglob("*") if p.is_file()] +
                   [p for p in (ASSETS / "pubmed_efetch").rglob("*") if p.is_file()] + [receipt])
    pairs = [[rel(path), sha(path)] for path in files]
    root = aggregate(pairs)
    write("network_metadata_snapshot_manifest.json", pretty({
        "artifact_schema_version": "V24DevelopmentNetworkMetadataSnapshotManifestV1",
        "components": pairs, "network_metadata_snapshot_sha256": root,
        "query_execution_log_sha256": sha(RUN / "query_execution_log.jsonl"),
        "snapshot_frozen_before_candidate_scoring": True,
    }))
    write("network_metadata_snapshot_sha256", (root + "\n").encode())
    return root


def replay_metadata(logs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    case_pmids = {case_id: [] for case_id in CASES}
    seen = {case_id: set() for case_id in CASES}
    occurrences: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for log in logs:
        require(log["execution_status"] == "SUCCESS", "cannot replay failed query")
        ids = [str(value) for value in load(ROOT / log["raw_response_snapshot_ref"])["esearchresult"].get("idlist", [])]
        for rank, pmid in enumerate(ids, log["retstart"] + 1):
            provenance = {"query_id": log["query_id"], "query_sha256": log["frozen_query_sha256"],
                          "intent_type": log["intent_type"], "relation_core_ref": log["relation_core_ref"],
                          "query_rank": rank, "page": log["page"], "retstart": log["retstart"],
                          "raw_response_sha256": log["raw_response_sha256"],
                          "raw_response_snapshot_ref": log["raw_response_snapshot_ref"]}
            if pmid in seen[log["case_id"]]:
                occurrences[(log["case_id"], pmid)].append(provenance)
            elif len(case_pmids[log["case_id"]]) < HARD_TAIL:
                seen[log["case_id"]].add(pmid)
                case_pmids[log["case_id"]].append(pmid)
                occurrences[(log["case_id"], pmid)].append(provenance)
    publications = {}
    for path in sorted((ASSETS / "pubmed_efetch").glob("batch_*.xml")):
        publications.update(parse_pubmed(path.read_bytes()))
    candidates = []
    for case_id in CASES:
        for depth, pmid in enumerate(case_pmids[case_id], 1):
            require(pmid in publications, f"metadata unresolved for PMID {pmid}")
            pub = publications[pmid]
            lineage = occurrences[(case_id, pmid)]
            candidates.append({
                "artifact_schema_version": "V24DevelopmentMetadataCandidateV1",
                "candidate_id": f"{case_id}:pmid:{pmid}", "case_id": case_id,
                "canonical_candidate_identity": f"pmid:{pmid}",
                "case_publication_identity": f"{case_id}:pmid:{pmid}",
                "pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "title": pub["title"], "abstract": pub["abstract"],
                "publication_type": pub["publication_types"], "journal": pub["journal"],
                "publication_date": pub["publication_date"], "metadata_depth": depth,
                "first_seen_provenance": lineage[0], "query_provenance": lineage,
                "all_contributing_query_ids": list(dict.fromkeys(row["query_id"] for row in lineage)),
                "all_contributing_intent_types": list(dict.fromkeys(row["intent_type"] for row in lineage)),
                "all_contributing_relation_core_refs": list(dict.fromkeys(row["relation_core_ref"] for row in lineage)),
                "deduplication_identity_rule": "PMID within case", "metadata_resolution_status": "RESOLVED"})
    return candidates, publications


def score_and_select(candidates: list[dict[str, Any]], targets: list[dict[str, Any]],
                     gates: dict[str, dict[str, Any]], network: Network) -> dict[str, Any]:
    targets_by_case = {row["case_id"]: row for row in targets}
    unit_registry = BiologicalUnitRegistryV1_1(load(UNIT_REGISTRY_PATH), load(UNIT_OVERLAY_PATH))
    unit_policy, unit_overlay = load(UNIT_POLICY_PATH), load(UNIT_POLICY_OVERLAY_PATH)
    relation_policy, relation_overlay = load(RELATION_POLICY_PATH), load(RELATION_POLICY_OVERLAY_PATH)
    endpoint_registry, endpoint_policy = load(ENDPOINT_REGISTRY_PATH), load(ENDPOINT_POLICY_PATH)
    beta_config = load(BETA_CONFIG_PATH)
    base_rows, p0_rows, p1_rows, p2_rows, policy_rows, final_rows = [], [], [], [], [], []
    by_candidate = {}
    for candidate in candidates:
        case_id, candidate_id = candidate["case_id"], candidate["candidate_id"]
        target = targets_by_case[case_id]
        publication_metadata = {key: candidate.get(key) for key in
                                ("pmid", "pmcid", "doi", "journal", "publication_date",
                                 "publication_type", "canonical_candidate_identity")}
        scientific_input = {"title": candidate["title"], "abstract": candidate["abstract"],
                            "publication_types": candidate["publication_type"],
                            "publication_types_reliable": True, "target": gates[case_id]}
        base = evaluate(scientific_input)
        base_disposition = base["state"] or "ABSTAIN"
        base_row = {"candidate_id": candidate_id, "case_id": case_id,
                    "metadata_depth": candidate["metadata_depth"],
                    "base_v22_disposition": base_disposition,
                    "base_v22_gate_version": base["candidate_version"],
                    "base_gate_reason_codes": {name: gate["state"] for name, gate in base["gates"].items()},
                    "fulltext_used": False, "review_labels_used": False}
        p0 = decide_biological_unit_compatibility_v1_1(
            unit_registry, unit_policy, unit_overlay, target["context_qualifiers"],
            title=candidate["title"], abstract=candidate["abstract"], publication_metadata=publication_metadata)
        p1 = decide_functional_relation_evidence_v1_1(
            candidate_id, target, title=candidate["title"], abstract=candidate["abstract"],
            publication_metadata=publication_metadata, base_policy=relation_policy, policy=relation_overlay)
        p2 = decide_endpoint_semantics_v1(
            candidate_id, target, title=candidate["title"], abstract=candidate["abstract"],
            publication_metadata=publication_metadata, registry=endpoint_registry, policy=endpoint_policy)
        module_hash = value_sha({"target": target, "title": candidate["title"],
                                 "abstract": candidate["abstract"], "metadata": publication_metadata})
        p0_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P0",
                  "state": p0.overall_state, "module_input_sha256": module_hash,
                  "decision": asdict(p0), "fulltext_used": False, "review_labels_used": False}
        p1_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P1",
                  "state": p1.evidence_state, "module_input_sha256": module_hash,
                  "decision": asdict(p1), "fulltext_used": False, "review_labels_used": False}
        p2_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P2",
                  "state": p2.overall_state, "module_input_sha256": module_hash,
                  "decision": asdict(p2), "fulltext_used": False, "review_labels_used": False}
        decision = decide_search_plan_v23_beta_disposition(
            base_disposition, biological_unit_state=p0.overall_state,
            functional_relation_state=p1.evidence_state, endpoint_state=p2.overall_state,
            tier_b_subtier_annotation=None, config=beta_config, mode="v2.3-beta")
        action = "DEMOTE_A_TO_B" if decision.tier_a_demoted_to_tier_b else (
            "PRESERVE" if base_disposition == "TIER_A" else "NO_ACTION_NON_A")
        policy_row = {"candidate_id": candidate_id, "case_id": case_id,
                      "base_v22_disposition": base_disposition, "p0_state": p0.overall_state,
                      "p1_state": p1.evidence_state, "p2_state": p2.overall_state,
                      "policy_a_action": action, "final_v23_beta2_disposition": decision.final_disposition,
                      "blocker_reason_codes": list(decision.blocker_reason_codes),
                      "policy_version": decision.policy_version,
                      "tier_b_to_tier_a_promoted": decision.tier_b_to_tier_a_promoted,
                      "hard_rejected_by_policy_a": decision.hard_rejected_by_v23_beta}
        final_row = {"candidate_id": candidate_id, "case_id": case_id,
                     "metadata_depth": candidate["metadata_depth"],
                     "base_v22_disposition": base_disposition, "p0_state": p0.overall_state,
                     "p1_state": p1.evidence_state, "p2_state": p2.overall_state,
                     "policy_a_action": action,
                     "final_v23_beta2_disposition": decision.final_disposition,
                     "within_tier_v22_order_preserved": decision.within_tier_v22_order_preserved,
                     "final_disposition_frozen_before_oa_lookup": True,
                     "fulltext_used": False, "review_labels_used": False}
        base_rows.append(base_row); p0_rows.append(p0_row); p1_rows.append(p1_row)
        p2_rows.append(p2_row); policy_rows.append(policy_row); final_rows.append(final_row)
        by_candidate[candidate_id] = {"candidate": candidate, "base": base_row, "p0": p0_row,
                                     "p1": p1_row, "p2": p2_row, "policy": policy_row,
                                     "final": final_row}
    metadata_events = [row for row in network.events if row["kind"] == "pubmed_metadata"]
    availability_stamp = max((row["timestamp_utc"] for row in metadata_events), default=None)
    oa_rows, selected = [], []
    for case_id in CASES:
        eligible = [row for row in final_rows if row["case_id"] == case_id and
                    row["final_v23_beta2_disposition"] in {"TIER_A", "TIER_B"}]
        eligible.sort(key=lambda row: (row["final_v23_beta2_disposition"] != "TIER_A",
                                      row["metadata_depth"],
                                      int(by_candidate[row["candidate_id"]]["candidate"]["pmid"])))
        available = []
        for rank, final in enumerate(eligible, 1):
            candidate = by_candidate[final["candidate_id"]]["candidate"]
            legal = bool(candidate.get("pmcid"))
            oa = {"candidate_id": candidate["candidate_id"], "case_id": case_id,
                  "final_preacquisition_tier": final["final_v23_beta2_disposition"],
                  "preacquisition_rank_within_tiered_pool": rank,
                  "oa_status": "PMC_IDENTIFIER_AVAILABLE" if legal else "NO_PMC_IDENTIFIER_IN_FROZEN_PUBMED_METADATA",
                  "legal_fulltext_available": legal, "pmcid": candidate.get("pmcid"),
                  "authorized_fulltext_identifier": candidate.get("pmcid"),
                  "availability_source": "frozen NCBI PubMed metadata PMCID field",
                  "availability_lookup_timestamp_utc": availability_stamp,
                  "oa_inferred_from_title_journal_or_doi": False}
            oa_rows.append(oa)
            if legal:
                available.append((final, candidate, rank))
        for index, (final, candidate, rank) in enumerate(available[:FULLTEXT_LIMIT], 1):
            selected.append({
                "artifact_schema_version": "V24DevelopmentAcquisitionSelectionV1",
                "selection_id": f"v24dev_selection_{len(selected) + 1:04d}",
                "case_id": case_id, "candidate_id": candidate["candidate_id"],
                "final_preacquisition_tier": final["final_v23_beta2_disposition"],
                "preacquisition_rank_within_tiered_pool": rank,
                "selection_index_within_case": index,
                "publication_metadata": {key: candidate.get(key) for key in
                                         ("pmid", "pmcid", "doi", "journal", "publication_date", "publication_type")},
                "legal_fulltext_identifier": candidate["pmcid"],
                "selection_reason": "final Tier A before Tier B; metadata depth then numeric PMID; PMCID present; maximum 10",
                "fulltext_content_present": False})
    return {"candidates": candidates, "base": base_rows, "p0": p0_rows, "p1": p1_rows,
            "p2": p2_rows, "policy": policy_rows, "final": final_rows, "oa": oa_rows,
            "selected": selected, "by_candidate": by_candidate}


def freeze_selection(processed: dict[str, Any], metadata_root: str) -> str:
    files = {
        "metadata_candidates.jsonl": jsonl(processed["candidates"]),
        "base_v22_dispositions.jsonl": jsonl(processed["base"]),
        "p0_decisions.jsonl": jsonl(processed["p0"]), "p1_decisions.jsonl": jsonl(processed["p1"]),
        "p2_decisions.jsonl": jsonl(processed["p2"]), "policy_a_decisions.jsonl": jsonl(processed["policy"]),
        "final_preacquisition_dispositions.jsonl": jsonl(processed["final"]),
        "oa_availability_snapshot.jsonl": jsonl(processed["oa"]),
        "ordered_fulltext_selection_manifest.jsonl": jsonl(processed["selected"]),
    }
    for name, body in files.items():
        write(name, body)
    selection_sha = sha(RUN / "ordered_fulltext_selection_manifest.jsonl")
    write("ordered_fulltext_selection_manifest_sha256", (selection_sha + "\n").encode())
    write("pre_fulltext_selection_freeze.json", pretty({
        "artifact_schema_version": "PreFulltextSelectionFreezeV1",
        "network_metadata_snapshot_sha256": metadata_root,
        "selection_manifest_sha256": selection_sha,
        "selection_count": len(processed["selected"]),
        "selection_frozen_before_any_fulltext_download": True,
        "fulltext_content_used_for_selection": False,
    }))
    return selection_sha


def download_and_replay_fulltexts(network: Network, selected: list[dict[str, Any]],
                                  selection_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(sha(RUN / "ordered_fulltext_selection_manifest.jsonl") == selection_sha,
            "selection changed before download")
    manifests, provenance = [], []
    for selection in selected:
        pmcid = selection["legal_fulltext_identifier"]
        params = {"db": "pmc", "id": pmcid, "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        try:
            network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                        "pmc_fulltext", {"selection_id": selection["selection_id"],
                                         "candidate_id": selection["candidate_id"], "pmcid": pmcid})
        except Exception:
            pass
        event = network.event_for(path) if path.is_file() else None
        status, error = "FAILED", None
        article_ok = identity_ok = False
        raw_hash = parsed_hash = None
        license_meta = {"license_type": None, "license_href": None, "license_text_sha256": None}
        if path.is_file() and event:
            raw = path.read_bytes(); raw_hash = hashlib.sha256(raw).hexdigest()
            try:
                root = ET.fromstring(raw)
                article_ok = root.find(".//article") is not None or root.tag.endswith("article")
                pmids = [text_of(node) for node in root.findall(".//article-id[@pub-id-type='pmid']")]
                expected_pmid = selection["publication_metadata"]["pmid"]
                identity_ok = not pmids or expected_pmid in pmids
                parsed_hash = hashlib.sha256(ET.tostring(root, encoding="utf-8")).hexdigest()
                license_node = root.find(".//license")
                if license_node is not None:
                    license_text = " ".join(text_of(license_node).split())
                    license_meta = {
                        "license_type": license_node.attrib.get("license-type"),
                        "license_href": next((v for k, v in license_node.attrib.items() if k.endswith("href")), None),
                        "license_text_sha256": hashlib.sha256(license_text.encode()).hexdigest() if license_text else None}
                status = "SUCCESS" if article_ok and identity_ok else "FAILED"
                if status == "FAILED": error = "PMC_ARTICLE_OR_IDENTITY_VALIDATION_FAILED"
            except ET.ParseError as exc:
                error = f"XML_PARSE_ERROR:{exc}"
        else:
            failures = [row for row in network.failures if row["kind"] == "pmc_fulltext" and
                        row["lineage"].get("candidate_id") == selection["candidate_id"]]
            error = failures[-1]["error_type"] if failures else "NO_FROZEN_FULLTEXT_RESPONSE"
        record = {
            "selection_id": selection["selection_id"], "candidate_id": selection["candidate_id"],
            "case_id": selection["case_id"], "source": "NCBI PMC E-utilities efetch",
            "pmcid": pmcid, "authorized_identifier": pmcid,
            "retrieval_timestamp_utc": event["timestamp_utc"] if event else None,
            "raw_content_sha256": raw_hash, "parsed_content_sha256": parsed_hash,
            "license_oa_metadata": license_meta, "article_structure_valid": article_ok,
            "publication_identity_valid": identity_ok, "acquisition_status": status,
            "error_state": error, "selection_frozen_before_download": True,
            "selection_sha256_at_download": selection_sha, "replacement_performed": False,
            "snapshot_ref": rel(path) if path.is_file() else None}
        manifests.append(record)
        provenance.append({"selection_id": selection["selection_id"],
                           "candidate_id": selection["candidate_id"], "pmcid": pmcid,
                           "availability_source": "frozen NCBI PubMed PMCID metadata",
                           "fulltext_source": "NCBI PMC E-utilities efetch",
                           "network_request_id": event["request_id"] if event else None,
                           "network_response_sha256": event["response_sha256"] if event else None,
                           "raw_content_sha256": raw_hash, "parsed_content_sha256": parsed_hash,
                           "acquisition_status": status, "replacement_performed": False})
        print(f"fulltext_complete selection={selection['selection_id']} status={status}", flush=True)
    return manifests, provenance


def finish(verification: dict[str, Any], manifest: dict[str, Any], queries: list[dict[str, Any]],
           targets: list[dict[str, Any]], logs: list[dict[str, Any]], metadata_root: str,
           processed: dict[str, Any], selection_sha: str, fulltexts: list[dict[str, Any]],
           fulltext_provenance: list[dict[str, Any]], network: Network) -> dict[str, Any]:
    write("fulltext_acquisition_manifest.jsonl", jsonl(fulltexts))
    write("fulltext_provenance.jsonl", jsonl(fulltext_provenance))
    target_by_case = {row["case_id"]: row for row in targets}
    traces = []
    fulltext_by_candidate = {row["candidate_id"]: row for row in fulltexts}
    for selection in processed["selected"]:
        linked = processed["by_candidate"][selection["candidate_id"]]
        case_id = selection["case_id"]
        traces.append({
            "selection_id": selection["selection_id"], "candidate_id": selection["candidate_id"],
            "case_id": case_id, "target_sha256": manifest["target_hashes"][case_id],
            "planner_v3_raw_output_hashes": manifest["raw_planner_output_hashes"][case_id],
            "validated_v3_plan_sha256": manifest["validated_plan_hashes"][case_id],
            "query_provenance": linked["candidate"]["query_provenance"],
            "metadata_candidate_identity": linked["candidate"]["canonical_candidate_identity"],
            "base_v22_disposition": linked["base"]["base_v22_disposition"],
            "p0_state": linked["p0"]["state"], "p1_state": linked["p1"]["state"],
            "p2_state": linked["p2"]["state"], "policy_a_action": linked["policy"]["policy_a_action"],
            "final_preacquisition_disposition": linked["final"]["final_v23_beta2_disposition"],
            "ordered_selection_manifest_sha256": selection_sha,
            "fulltext_acquisition": fulltext_by_candidate[selection["candidate_id"]],
            "trace_complete": True})
    write("retrieval_provenance_trace.jsonl", jsonl(traces))
    funnels = []
    for case_id in CASES:
        case_logs = [row for row in logs if row["case_id"] == case_id]
        first_pages = {row["query_id"]: row for row in case_logs if row["page"] == 1}
        candidates = [row for row in processed["candidates"] if row["case_id"] == case_id]
        final = [row for row in processed["final"] if row["case_id"] == case_id]
        oa = [row for row in processed["oa"] if row["case_id"] == case_id]
        selected = [row for row in processed["selected"] if row["case_id"] == case_id]
        acquired = [row for row in fulltexts if row["case_id"] == case_id]
        metadata_natural = len(candidates) < HARD_TAIL
        funnels.append({
            "case_id": case_id, "frozen_query_count": len([q for q in queries if q["case_id"] == case_id]),
            "executed_query_count": len(first_pages),
            "raw_query_hits": sum(row["raw_hit_count"] for row in first_pages.values()),
            "unique_pmid_count_before_tail": len(candidates), "metadata_candidate_count": len(candidates),
            "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
            "metadata_completion_state": "HARD_TAIL_REACHED" if len(candidates) == HARD_TAIL else "NATURAL_EXHAUSTION",
            "base_and_final_tier_distribution": dict(Counter(row["final_v23_beta2_disposition"] for row in final)),
            "oa_eligible_count": sum(row["legal_fulltext_available"] for row in oa),
            "selected_candidate_count": len(selected),
            "successfully_acquired_fulltext_count": sum(row["acquisition_status"] == "SUCCESS" for row in acquired),
            "failed_fulltext_acquisition_count": sum(row["acquisition_status"] == "FAILED" for row in acquired),
            "metadata_natural_exhaustion": metadata_natural,
            "acquisition_natural_exhaustion": sum(row["legal_fulltext_available"] for row in oa) < FULLTEXT_LIMIT,
            "replacement_count": 0, "scientific_relevance_adjudicated": False})
    write("per_case_retrieval_acquisition_funnel.json", pretty({
        "artifact_schema_version": "V24DevelopmentRetrievalAcquisitionFunnelV1", "cases": funnels}))

    request_counts = Counter(row["kind"] for row in network.events)
    failure_counts = Counter(row["kind"] for row in network.failures)
    safety = {"artifact_schema_version": "V24DevelopmentRetrievalSafetyAuditV1",
              "preregistration_root_verified": True, "query_set_changed": False,
              "query_repair_count": 0, "fallback_search_count": 0, "manual_paper_injection_count": 0,
              "known_pmid_recovery_checks": 0, "relevance_labels_created": 0,
              "pass_a_reviews": 0, "pass_b_reviews": 0, "planner_calls": 0,
              "provider_calls": 0, "llm_calls": 0, "general_web_calls": 0,
              "publisher_calls": 0, "replacement_count": 0,
              "historical_assets_modified": False}
    write("scientific_state_safety_audit.json", pretty(safety))
    summary = {
        "artifact_schema_version": "V24DevelopmentRetrospectiveRetrievalSummaryV1",
        "status": "COMPLETED", "case_count": 8, "frozen_query_count": 29,
        "executed_query_count": len({row["query_id"] for row in logs}),
        "query_set_changed": False, "metadata_candidate_count": len(processed["candidates"]),
        "final_tier_distribution": dict(Counter(row["final_v23_beta2_disposition"] for row in processed["final"])),
        "oa_eligible_count": sum(row["legal_fulltext_available"] for row in processed["oa"]),
        "selected_fulltext_count": len(processed["selected"]),
        "successfully_acquired_fulltext_count": sum(row["acquisition_status"] == "SUCCESS" for row in fulltexts),
        "failed_fulltext_acquisition_count": sum(row["acquisition_status"] == "FAILED" for row in fulltexts),
        "zero_hit_query_count": sum(row["page"] == 1 and row["raw_hit_count"] == 0 for row in logs),
        "zero_hit_case_count": sum(row["metadata_candidate_count"] == 0 for row in funnels),
        "zero_acquisition_case_count": sum(row["successfully_acquired_fulltext_count"] == 0 for row in funnels),
        "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL, "adaptive_tail_enabled": False,
        "max_fulltexts_per_case": FULLTEXT_LIMIT, "selection_manifest_sha256": selection_sha,
        "network_metadata_snapshot_sha256": metadata_root,
        "network_calls": len(network.events) + len(network.failures),
        "successful_network_responses": len(network.events), "failed_network_attempts": len(network.failures),
        "search_network_calls": request_counts["pubmed_search"] + failure_counts["pubmed_search"],
        "metadata_network_calls": request_counts["pubmed_metadata"] + failure_counts["pubmed_metadata"],
        "fulltext_network_calls": request_counts["pmc_fulltext"] + failure_counts["pmc_fulltext"],
        "transport_retries": sum(row["retry_count"] for row in network.events),
        "provider_calls": 0, "llm_calls": 0, "planner_calls": 0,
        "relevance_adjudication_calls": 0, "known_pmid_checks": 0,
        "corpus_frozen_before_relevance_adjudication": True,
        "next_stage": "FREEZE_NEUTRAL_REVIEW_CORPUS_BEFORE_ANY_ADJUDICATION",
        "per_case": funnels}
    write("authorization_verification.json", pretty(verification))
    write("summary.json", pretty(summary))

    required = {"authorization_verification.json", "query_execution_log.jsonl",
                "network_metadata_snapshot_manifest.json", "network_metadata_snapshot_sha256",
                "metadata_candidates.jsonl", "base_v22_dispositions.jsonl", "p0_decisions.jsonl",
                "p1_decisions.jsonl", "p2_decisions.jsonl", "policy_a_decisions.jsonl",
                "final_preacquisition_dispositions.jsonl", "oa_availability_snapshot.jsonl",
                "ordered_fulltext_selection_manifest.jsonl", "ordered_fulltext_selection_manifest_sha256",
                "pre_fulltext_selection_freeze.json", "fulltext_acquisition_manifest.jsonl",
                "fulltext_provenance.jsonl", "retrieval_provenance_trace.jsonl",
                "per_case_retrieval_acquisition_funnel.json", "scientific_state_safety_audit.json",
                "summary.json"}
    require({p.name for p in RUN.iterdir()} == required | {"retrieval_assets"}, "run membership mismatch")
    checks = {
        "preregistration_verified": verification["preregistration_root"]["verified"],
        "exactly_29_queries_executed": summary["executed_query_count"] == 29,
        "query_set_unchanged": not summary["query_set_changed"],
        "metadata_depth_at_most_180": all(row["metadata_depth"] <= HARD_TAIL for row in processed["candidates"]),
        "selection_at_most_10_per_case": all(sum(row["case_id"] == case for row in processed["selected"]) <= FULLTEXT_LIMIT for case in CASES),
        "selection_frozen_before_download": all(row["selection_frozen_before_download"] for row in fulltexts),
        "no_replacements": all(not row["replacement_performed"] for row in fulltexts),
        "complete_provenance": len(traces) == len(processed["selected"]) and all(row["trace_complete"] for row in traces),
        "no_relevance_adjudication": summary["relevance_adjudication_calls"] == 0,
        "no_provider_llm_planner_calls": not any(summary[key] for key in ("provider_calls", "llm_calls", "planner_calls")),
        "corpus_frozen_before_adjudication": summary["corpus_frozen_before_relevance_adjudication"],
    }
    require(all(checks.values()), "retrieval validation failed")
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir()) if path.is_file()]
    validation = {"artifact_schema_version": "V24DevelopmentRetrospectiveRetrievalValidationV1",
                  "status": "PASS", "checks": checks, "aggregate_components": pairs}
    write("validation.json", pretty(validation))
    root = aggregate(pairs)
    write("search_plan_v24_dev_alpha3_4_retrieval_sha256", (root + "\n").encode())
    summary["search_plan_v24_dev_alpha3_4_retrieval_sha256"] = root
    # Summary is already part of the immutable aggregate; keep the root in a sidecar only.
    return {**summary, "search_plan_v24_dev_alpha3_4_retrieval_sha256": root}


def main(execute_network: bool, preflight_only: bool) -> None:
    verification, manifest, queries, targets, gates = preflight()
    print(json.dumps({"preflight": verification, "status": "PASS"}, indent=2, sort_keys=True), flush=True)
    if preflight_only:
        return
    require(execute_network, "explicit --execute-network required")
    require(not RUN.exists(), f"refusing to overwrite existing run: {RUN}")
    RUN.mkdir(parents=False)
    ASSETS.mkdir()
    write("authorization_verification.json", pretty(verification))
    network = Network(True)
    logs, case_pmids = execute_searches(network, queries)
    fetch_metadata(network, case_pmids)
    metadata_root = freeze_metadata_network(logs, network)
    candidates, _ = replay_metadata(logs)
    processed = score_and_select(candidates, targets, gates, network)
    selection_sha = freeze_selection(processed, metadata_root)
    print(f"selection_frozen sha256={selection_sha} count={len(processed['selected'])}", flush=True)
    fulltexts, provenance = download_and_replay_fulltexts(network, processed["selected"], selection_sha)
    summary = finish(verification, manifest, queries, targets, logs, metadata_root,
                     processed, selection_sha, fulltexts, provenance, network)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    options = args()
    main(options.execute_network, options.preflight_only)
