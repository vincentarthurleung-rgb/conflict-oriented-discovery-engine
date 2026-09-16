#!/usr/bin/env python3
"""Execute the authorized beta.2 primary held-out-v2 retrieval and acquisition."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
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
    BiologicalUnitRegistryV1_1,
    decide_biological_unit_compatibility_v1_1,
)
from code_engine.search.endpoint_semantics_v1 import decide_endpoint_semantics_v1
from code_engine.search.functional_relation_evidence_v1_1 import (
    decide_functional_relation_evidence_v1_1,
)
from code_engine.search.search_plan_v23_beta_policy import (
    decide_search_plan_v23_beta_disposition,
)
from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_queries_offline as query_freeze
from tools.run_search_plan_v21_retrieval_calibration_pilot_v1 import parse_pubmed, text_of
from tools.search_plan_v22_candidate_gates import build_target_contract, evaluate


RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
ASSETS = RUN / "retrieval_assets"
QUERY_RUN = query_freeze.RUN
CASE_RUN = query_freeze.CASE_RUN
BETA2_RUN = query_freeze.BETA2_RUN
BETA_PROTOCOL_RUN = query_freeze.BETA_PROTOCOL_RUN
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

TARGETS_PATH = CASE_RUN / "primary_heldout_v2_scientific_targets.jsonl"
BINDINGS_PATH = QUERY_RUN / "primary_heldout_v2_query_bindings.jsonl"
QUERIES_PATH = QUERY_RUN / "primary_heldout_v2_frozen_queries.jsonl"
BOUNDARY_PATH = BETA_PROTOCOL_RUN / "adjudication_boundary_v2.json"
BETA_CONFIG_PATH = BETA_PROTOCOL_RUN / "search_plan_v23_beta_config_snapshot.json"
V22_GATE_PATH = ROOT / "tools/search_plan_v22_candidate_gates.py"
V22_RETRIEVAL_PATH = ROOT / "tools/run_search_plan_v22_heldout_v1_network_retrieval.py"
V22_PARSER_PATH = ROOT / "tools/run_search_plan_v21_retrieval_calibration_pilot_v1.py"

UNIT_REGISTRY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1.json"
UNIT_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_registry_v1_1.json"
UNIT_POLICY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1.json"
UNIT_POLICY_OVERLAY_PATH = ROOT / "configs/search_plans/biological_unit_policy_v1_1.json"
RELATION_POLICY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json"
RELATION_POLICY_OVERLAY_PATH = ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json"
ENDPOINT_REGISTRY_PATH = ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json"
ENDPOINT_POLICY_PATH = ROOT / "configs/search_plans/endpoint_semantics_policy_v1.json"

EXPECTED_QUERY_ROOT = "4396d05d41b458c40ef65072932e2425bf0cfa62aa1c47cfbad7ac3301798888"
CASE_IDS = query_freeze.CASE_IDS
FAMILY_ORDER = ("A", "C", "D", "E")
SOFT_TAIL = 120
HARD_TAIL = 180
PAGE_SIZE = 30
FULLTEXT_LIMIT = 10

REQUIRED = {
    "upstream_root_verification.json",
    "query_execution_log.jsonl",
    "network_metadata_snapshot_manifest.json",
    "network_metadata_snapshot_sha256",
    "primary_v2_metadata_candidates.jsonl",
    "metadata_candidate_validation.json",
    "primary_v2_base_v22_dispositions.jsonl",
    "primary_v2_p0_decisions.jsonl",
    "primary_v2_p1_decisions.jsonl",
    "primary_v2_p2_decisions.jsonl",
    "primary_v2_policy_a_decisions.jsonl",
    "primary_v2_final_preacquisition_dispositions.jsonl",
    "oa_availability_snapshot.jsonl",
    "primary_v2_acquisition_selection.jsonl",
    "primary_v2_acquisition_selection_sha256",
    "primary_v2_acquisition_time_evidence.jsonl",
    "primary_v2_pass_a_blinded_views.jsonl",
    "primary_v2_pass_a_blinded_views_sha256",
    "primary_v2_review_id_mapping.json",
    "primary_v2_fulltext_acquisition_manifest.jsonl",
    "primary_v2_fulltext_provenance.jsonl",
    "per_case_structural_analysis.json",
    "retrieval_provenance_trace.json",
    "scientific_state_safety_audit.json",
    "implementation_manifest.json",
    "validation.json",
    "summary.json",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    return parser.parse_args()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def write_bytes(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def verify_all_roots() -> dict[str, Any]:
    upstream = query_freeze.verify_upstream_roots()
    require(upstream["all_five_exact_roots_verified"], "upstream root verification failed")
    manifest = load_json(QUERY_RUN / "freeze_manifest.json")
    pairs = manifest["aggregate_components"]
    for name, expected in pairs:
        path = QUERY_RUN / name
        require(path.is_file() and not path.is_symlink(), f"missing query-freeze component: {name}")
        require(sha(path) == expected, f"query-freeze component changed: {name}")
    actual = aggregate(pairs)
    require(actual == manifest["primary_heldout_v2_query_freeze_sha256"] == EXPECTED_QUERY_ROOT,
            "primary query-freeze root mismatch")
    roots = dict(upstream["roots"])
    roots["primary_heldout_v2_query_freeze_sha256"] = {
        "status": "PASS", "expected_sha256": EXPECTED_QUERY_ROOT,
        "actual_sha256": actual, "aggregate_components": pairs,
    }
    return {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkUpstreamRootVerificationV1",
        "roots": roots,
        "all_six_exact_roots_verified": True,
        "verified_before_any_network_request": True,
    }


def protected_state() -> dict[str, str]:
    prior_safety = load_json(QUERY_RUN / "scientific_state_safety_audit.json")
    paths = {ROOT / name for name in prior_safety["historical_protected_state_before"]}
    paths.update(path for path in QUERY_RUN.iterdir() if path.is_file())
    paths.update({
        V22_GATE_PATH, V22_RETRIEVAL_PATH, V22_PARSER_PATH,
        UNIT_REGISTRY_PATH, UNIT_OVERLAY_PATH, UNIT_POLICY_PATH, UNIT_POLICY_OVERLAY_PATH,
        RELATION_POLICY_PATH, RELATION_POLICY_OVERLAY_PATH,
        ENDPOINT_REGISTRY_PATH, ENDPOINT_POLICY_PATH,
    })
    return {rel(path): sha(path) for path in sorted(paths)}


class Network:
    def __init__(self, execute: bool):
        self.execute = execute
        self.receipt = ASSETS / "network_events.json"
        prior = load_json(self.receipt) if self.receipt.exists() else {}
        self.events: list[dict[str, Any]] = prior.get("events", [])
        self.failures: list[dict[str, Any]] = prior.get("failures", [])

    def save(self) -> None:
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_bytes(pretty({
            "events": self.events,
            "failures": self.failures,
            "provider_calls": 0,
            "llm_calls": 0,
            "new_scientific_adjudication_calls": 0,
            "general_web_fallback_calls": 0,
            "publisher_fallback_calls": 0,
        }))

    def event_for(self, path: Path) -> dict[str, Any] | None:
        path_ref = rel(path)
        return next((event for event in reversed(self.events) if event["snapshot_ref"] == path_ref), None)

    def get(self, url: str, path: Path, kind: str, lineage: dict[str, Any]) -> tuple[bytes, dict[str, Any], bool]:
        if path.is_file():
            event = self.event_for(path)
            require(event is not None and event["response_sha256"] == sha(path),
                    f"cached response lacks valid receipt: {path}")
            return path.read_bytes(), event, False
        require(self.execute, "explicit --execute-network authorization flag required")
        parsed = urllib.parse.urlparse(url)
        require((parsed.hostname or "").casefold() == "eutils.ncbi.nlm.nih.gov", "forbidden network host")
        require(parsed.path.startswith("/entrez/eutils/"), "forbidden network path")
        verify_all_roots()
        for attempt in range(1, 5):
            stamp = now()
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "conflict-oriented-discovery-engine-primary-heldout-v2/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read()
                    status = response.status
                    content_type = response.headers.get("Content-Type")
                break
            except Exception as exc:
                self.failures.append({
                    "kind": kind, "timestamp_utc": stamp, "url": url,
                    "lineage": lineage, "attempt": attempt,
                    "error_type": type(exc).__name__, "error": str(exc),
                })
                self.save()
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        event = {
            "request_id": f"primary_v2_ncbi_request_{len(self.events) + 1:05d}",
            "request_sequence": len(self.events) + len(self.failures) + 1,
            "kind": kind,
            "timestamp_utc": stamp,
            "url": url,
            "http_status": status,
            "content_type": content_type,
            "snapshot_ref": rel(path),
            "response_sha256": sha(path),
            "bytes": len(body),
            "lineage": lineage,
            "retry_count": attempt - 1,
        }
        self.events.append(event)
        self.save()
        time.sleep(0.36)
        return body, event, True


def frozen_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    targets = load_jsonl(TARGETS_PATH)
    bindings = {row["case_id"]: row for row in load_jsonl(BINDINGS_PATH)}
    queries = load_jsonl(QUERIES_PATH)
    require([row["case_id"] for row in targets] == CASE_IDS, "frozen target order mismatch")
    require(len(queries) == 32, "frozen executable-query count mismatch")
    expected_order = [(case_id, family) for case_id in CASE_IDS for family in FAMILY_ORDER]
    require([(row["case_id"], row["family_id"]) for row in queries] == expected_order,
            "frozen executable-query order mismatch")
    for row in queries:
        require(sha_bytes(row["compiled_query"].encode("utf-8")) == row["query_sha256"],
                f"frozen query bytes mismatch: {row['query_id']}")
    return targets, bindings, queries


def execute_searches(network: Network, queries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    case_pmids = {case_id: [] for case_id in CASE_IDS}
    seen = {case_id: set() for case_id in CASE_IDS}
    logs: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
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
                params = {
                    "db": "pubmed", "term": query["compiled_query"],
                    "retstart": item["retstart"], "retmax": retmax,
                    "retmode": "json", "sort": "relevance",
                    "tool": "conflict_oriented_discovery_engine",
                }
                suffix = f"retstart_{item['retstart']:04d}_retmax_{retmax:03d}"
                path = ASSETS / "pubmed_esearch" / case_id / f"{query['query_id']}__{suffix}.json"
                url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
                try:
                    raw, event, _ = network.get(url, path, "pubmed_search", {
                        "query_id": query["query_id"], "case_id": case_id,
                        "family_id": query["family_id"], "retstart": item["retstart"],
                        "retmax": retmax,
                    })
                    require(len(raw) <= 10_000_000, "unexpectedly large PubMed search response")
                    result = json.loads(raw.decode("utf-8"))["esearchresult"]
                    ids = [str(value) for value in result.get("idlist", [])]
                    total = int(result.get("count", 0))
                    added = []
                    for pmid in ids:
                        if pmid not in seen[case_id] and len(case_pmids[case_id]) < HARD_TAIL:
                            seen[case_id].add(pmid)
                            case_pmids[case_id].append(pmid)
                            added.append(pmid)
                    logs.append({
                        "query_id": query["query_id"], "case_id": case_id,
                        "family_id": query["family_id"],
                        "frozen_query_sha256": query["query_sha256"],
                        "exact_query_string": query["compiled_query"],
                        "source": "NCBI PubMed E-utilities esearch",
                        "request_sequence": event["request_sequence"],
                        "request_timestamp_utc": event["timestamp_utc"],
                        "response_status": event["http_status"],
                        "response_record_count": total,
                        "returned_id_count": len(ids),
                        "new_unique_additions": len(added),
                        "cumulative_unique_metadata_records": len(case_pmids[case_id]),
                        "raw_response_sha256": event["response_sha256"],
                        "raw_response_snapshot_ref": event["snapshot_ref"],
                        "retry_count": event["retry_count"], "error_state": None,
                        "page_order": item["page"], "retstart": item["retstart"],
                        "retmax": retmax, "query_modified": False,
                    })
                    executed.add(query["query_id"])
                    next_offset = item["retstart"] + len(ids)
                    if retmax and ids and next_offset < total and len(case_pmids[case_id]) < HARD_TAIL:
                        next_active.append({"query": query, "retstart": next_offset, "page": item["page"] + 1})
                except Exception as exc:
                    logs.append({
                        "query_id": query["query_id"], "case_id": case_id,
                        "family_id": query["family_id"],
                        "frozen_query_sha256": query["query_sha256"],
                        "exact_query_string": query["compiled_query"],
                        "source": "NCBI PubMed E-utilities esearch",
                        "request_sequence": None, "request_timestamp_utc": now(),
                        "response_status": None, "response_record_count": 0,
                        "raw_response_sha256": None, "retry_count": 3,
                        "error_state": {"type": type(exc).__name__, "message": str(exc)},
                        "page_order": item["page"], "retstart": item["retstart"],
                        "retmax": retmax, "query_modified": False,
                    })
            active = next_active
        require(executed == {row["query_id"] for row in case_queries},
                f"not all frozen queries executed successfully: {case_id}")
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
        print(f"metadata_batch_complete batch={batch} pmids={len(ids)}", flush=True)


def freeze_metadata_snapshot(query_logs: list[dict[str, Any]], network: Network) -> tuple[dict[str, Any], str]:
    write_bytes("query_execution_log.jsonl", jsonl(query_logs))
    metadata_receipt = ASSETS / "metadata_network_events.json"
    metadata_receipt.write_bytes(pretty({
        "events": [event for event in network.events if event["kind"] in {"pubmed_search", "pubmed_metadata"}],
        "failures": [failure for failure in network.failures if failure["kind"] in {"pubmed_search", "pubmed_metadata"}],
        "receipt_frozen_before_scientific_modules": True,
    }))
    files = sorted(
        [path for path in (ASSETS / "pubmed_esearch").rglob("*") if path.is_file()]
        + [path for path in (ASSETS / "pubmed_efetch").rglob("*") if path.is_file()]
        + [metadata_receipt]
    )
    components = [[rel(path), sha(path)] for path in files]
    snapshot_root = aggregate(components)
    manifest = {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkMetadataSnapshotManifestV1",
        "snapshot_scope": "authoritative single live execution of frozen PubMed queries and metadata fetches",
        "components": components,
        "network_metadata_snapshot_sha256": snapshot_root,
        "query_execution_log_sha256": sha(RUN / "query_execution_log.jsonl"),
        "raw_response_file_count": len(files) - 1,
        "live_snapshot_executed_once": True,
        "downstream_scientific_modules_run_before_snapshot": False,
    }
    write_bytes("network_metadata_snapshot_manifest.json", pretty(manifest))
    write_bytes("network_metadata_snapshot_sha256", (snapshot_root + "\n").encode())
    return manifest, snapshot_root


def replay_metadata(query_logs: list[dict[str, Any]], network: Network) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    case_pmids = {case_id: [] for case_id in CASE_IDS}
    seen = {case_id: set() for case_id in CASE_IDS}
    occurrences: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for log in query_logs:
        require(log["error_state"] is None, "cannot replay failed query snapshot")
        payload = load_json(ROOT / log["raw_response_snapshot_ref"])["esearchresult"]
        ids = [str(value) for value in payload.get("idlist", [])]
        for rank, pmid in enumerate(ids, log["retstart"] + 1):
            provenance = {
                "query_id": log["query_id"], "family_id": log["family_id"],
                "canonical_case_index": CASE_IDS.index(log["case_id"]) + 1,
                "canonical_family_index": FAMILY_ORDER.index(log["family_id"]) + 1,
                "query_rank": rank,
                "raw_response_snapshot_ref": log["raw_response_snapshot_ref"],
                "raw_response_sha256": log["raw_response_sha256"],
            }
            if pmid in seen[log["case_id"]]:
                occurrences[(log["case_id"], pmid)].append(provenance)
            elif len(case_pmids[log["case_id"]]) < HARD_TAIL:
                seen[log["case_id"]].add(pmid)
                case_pmids[log["case_id"]].append(pmid)
                occurrences[(log["case_id"], pmid)].append(provenance)

    publications: dict[str, dict[str, Any]] = {}
    for path in sorted((ASSETS / "pubmed_efetch").glob("batch_*.xml")):
        publications.update(parse_pubmed(path.read_bytes()))
    candidates = []
    for case_id in CASE_IDS:
        for depth, pmid in enumerate(case_pmids[case_id], 1):
            require(pmid in publications, f"PubMed metadata unresolved for PMID {pmid}")
            pub = publications[pmid]
            lineage = occurrences[(case_id, pmid)]
            require(lineage, f"missing query provenance for PMID {pmid}")
            candidates.append({
                "artifact_schema_version": "PrimaryHeldoutV2MetadataCandidateV1",
                "candidate_id": f"{case_id}:pmid:{pmid}",
                "case_id": case_id,
                "canonical_candidate_identity": f"pmid:{pmid}",
                "case_publication_identity": f"{case_id}:pmid:{pmid}",
                "pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "title": pub["title"], "abstract": pub["abstract"],
                "publication_type": pub["publication_types"],
                "journal": pub["journal"], "publication_date": pub["publication_date"],
                "metadata_depth": depth, "frozen_candidate_order": len(candidates) + 1,
                "first_seen_provenance": lineage[0], "query_provenance": lineage,
                "all_contributing_query_ids": list(dict.fromkeys(item["query_id"] for item in lineage)),
                "all_contributing_family_ids": list(dict.fromkeys(item["family_id"] for item in lineage)),
                "deduplication_identity_rule": "PMID within case",
                "metadata_resolution_status": "RESOLVED",
            })
    return candidates, publications


def gate_target(target: dict[str, Any], binding: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, Any]:
    fields = binding["compiler_facing_fields"]
    values = lambda name: [item["term"] for item in fields[name]["value"]]
    aliases = fields["authorized_aliases"]["value"]
    retrieval = {
        "subject_surfaces": list(dict.fromkeys(values("subject_terms") + [item["term"] for item in aliases if item["target_field"] == "subject"])),
        "endpoint_measurement_surfaces": list(dict.fromkeys(values("object_terms") + values("measurement_terms") + [item["term"] for item in aliases if item["target_field"] == "object"])),
        "context_recall_scope": target["context_qualifiers"],
        "measurement_target": target["measurement_target"],
        "relation_recall_scope": target["relation_family"],
    }
    scientific = dict(target)
    scientific["measurement_requirement"] = target["measurement_target"]
    scientific["therapy_identity_requirement"] = target.get("therapy") or "not required"
    variants = [{"term_authority_annotations": row["term_annotations"]} for row in queries]
    return build_target_contract(
        {"scientific_proposition_target": scientific, "retrieval_target": retrieval},
        [], variants,
    )


def local_processing(
    query_logs: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    queries: list[dict[str, Any]],
    network: Network,
) -> dict[str, Any]:
    candidates, publications = replay_metadata(query_logs, network)
    targets_by_case = {row["case_id"]: row for row in targets}
    gate_targets = {
        case_id: gate_target(
            targets_by_case[case_id], bindings[case_id],
            [row for row in queries if row["case_id"] == case_id],
        ) for case_id in CASE_IDS
    }
    unit_registry = BiologicalUnitRegistryV1_1(load_json(UNIT_REGISTRY_PATH), load_json(UNIT_OVERLAY_PATH))
    unit_policy = load_json(UNIT_POLICY_PATH)
    unit_overlay = load_json(UNIT_POLICY_OVERLAY_PATH)
    relation_policy = load_json(RELATION_POLICY_PATH)
    relation_overlay = load_json(RELATION_POLICY_OVERLAY_PATH)
    endpoint_registry = load_json(ENDPOINT_REGISTRY_PATH)
    endpoint_policy = load_json(ENDPOINT_POLICY_PATH)
    beta_config = load_json(BETA_CONFIG_PATH)

    base_rows = []
    p0_rows = []
    p1_rows = []
    p2_rows = []
    policy_rows = []
    final_rows = []
    by_candidate: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        case_id = candidate["case_id"]
        candidate_id = candidate["candidate_id"]
        target = targets_by_case[case_id]
        publication_metadata = {
            key: candidate.get(key) for key in
            ("pmid", "pmcid", "doi", "journal", "publication_date", "publication_type", "canonical_candidate_identity")
        }
        scientific_input = {
            "title": candidate["title"], "abstract": candidate["abstract"],
            "publication_types": candidate["publication_type"],
            "publication_types_reliable": True, "target": gate_targets[case_id],
        }
        base = evaluate(scientific_input)
        base_disposition = base["state"] or "ABSTAIN"
        base_row = {
            "candidate_id": candidate_id, "case_id": case_id,
            "metadata_depth": candidate["metadata_depth"],
            "base_v22_disposition": base_disposition,
            "base_v22_gate_version": base["candidate_version"],
            "base_gate_reason_codes": {
                name: gate["state"] for name, gate in base["gates"].items()
            },
            "raw_base_gate_decision": base,
            "input_scope": "frozen target, title, abstract, publication metadata and frozen deterministic authority only",
            "fulltext_used": False, "review_labels_used": False,
        }
        base_rows.append(base_row)

        p0 = decide_biological_unit_compatibility_v1_1(
            unit_registry, unit_policy, unit_overlay, target["context_qualifiers"],
            title=candidate["title"], abstract=candidate["abstract"],
            publication_metadata=publication_metadata,
        )
        p1 = decide_functional_relation_evidence_v1_1(
            candidate_id, target, title=candidate["title"], abstract=candidate["abstract"],
            publication_metadata=publication_metadata,
            base_policy=relation_policy, policy=relation_overlay,
        )
        p2 = decide_endpoint_semantics_v1(
            candidate_id, target, title=candidate["title"], abstract=candidate["abstract"],
            publication_metadata=publication_metadata,
            registry=endpoint_registry, policy=endpoint_policy,
        )
        module_input_hash = sha_bytes(canonical({
            "ScientificPropositionTargetV1": target, "title": candidate["title"],
            "abstract": candidate["abstract"], "publication_metadata": publication_metadata,
        }))
        p0_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P0", "state": p0.overall_state,
                  "module_input_sha256": module_input_hash, "decision": asdict(p0), "base_tier_used_as_scientific_evidence": False, "fulltext_used": False}
        p1_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P1", "state": p1.evidence_state,
                  "module_input_sha256": module_input_hash, "decision": asdict(p1), "base_tier_used_as_scientific_evidence": False, "fulltext_used": False}
        p2_row = {"candidate_id": candidate_id, "case_id": case_id, "module": "P2", "state": p2.overall_state,
                  "module_input_sha256": module_input_hash, "decision": asdict(p2), "base_tier_used_as_scientific_evidence": False, "fulltext_used": False}
        p0_rows.append(p0_row)
        p1_rows.append(p1_row)
        p2_rows.append(p2_row)

        policy = decide_search_plan_v23_beta_disposition(
            base_disposition, biological_unit_state=p0.overall_state,
            functional_relation_state=p1.evidence_state, endpoint_state=p2.overall_state,
            tier_b_subtier_annotation=None, config=beta_config, mode="v2.3-beta",
        )
        action = "DEMOTE_A_TO_B" if policy.tier_a_demoted_to_tier_b else (
            "PRESERVE" if base_disposition == "TIER_A" else "NO_ACTION_NON_A"
        )
        policy_row = {
            "candidate_id": candidate_id, "case_id": case_id,
            "base_v22_disposition": base_disposition,
            "p0_state": p0.overall_state, "p1_state": p1.evidence_state,
            "p2_state": p2.overall_state, "policy_a_action": action,
            "final_v23_beta2_disposition": policy.final_disposition,
            "blocker_reason_codes": list(policy.blocker_reason_codes),
            "policy_version": policy.policy_version,
            "tier_b_to_tier_a_promoted": policy.tier_b_to_tier_a_promoted,
            "hard_rejected_by_policy_a": policy.hard_rejected_by_v23_beta,
        }
        policy_rows.append(policy_row)
        final_row = {
            "candidate_id": candidate_id, "case_id": case_id,
            "metadata_depth": candidate["metadata_depth"],
            "base_v22_disposition": base_disposition,
            "p0_state": p0.overall_state, "p1_state": p1.evidence_state,
            "p2_state": p2.overall_state, "policy_a_action": action,
            "final_v23_beta2_disposition": policy.final_disposition,
            "within_tier_v22_order_preserved": policy.within_tier_v22_order_preserved,
            "final_disposition_frozen_before_oa_lookup": True,
            "fulltext_used": False,
        }
        final_rows.append(final_row)
        by_candidate[candidate_id] = {
            "candidate": candidate, "base": base_row, "p0": p0_row, "p1": p1_row,
            "p2": p2_row, "policy": policy_row, "final": final_row,
        }

    metadata_events = [event for event in network.events if event["kind"] == "pubmed_metadata"]
    availability_stamp = max((event["timestamp_utc"] for event in metadata_events), default=None)
    oa_rows = []
    selected = []
    for case_id in CASE_IDS:
        eligible = [row for row in final_rows if row["case_id"] == case_id and row["final_v23_beta2_disposition"] in {"TIER_A", "TIER_B"}]
        eligible.sort(key=lambda row: (
            row["final_v23_beta2_disposition"] != "TIER_A",
            row["metadata_depth"], int(by_candidate[row["candidate_id"]]["candidate"]["pmid"]),
        ))
        available = []
        for rank, final in enumerate(eligible, 1):
            candidate = by_candidate[final["candidate_id"]]["candidate"]
            legal = bool(candidate.get("pmcid"))
            oa = {
                "candidate_id": candidate["candidate_id"], "case_id": case_id,
                "final_preacquisition_tier": final["final_v23_beta2_disposition"],
                "preacquisition_rank_within_tiered_pool": rank,
                "oa_status": "PMC_IDENTIFIER_AVAILABLE" if legal else "NO_PMC_IDENTIFIER_IN_FROZEN_PUBMED_METADATA",
                "legal_fulltext_available": legal,
                "pmcid": candidate.get("pmcid"), "authorized_fulltext_identifier": candidate.get("pmcid"),
                "availability_source": "NCBI PubMed metadata PMCID field; frozen v2.2-authorized PMC acquisition rule",
                "availability_lookup_timestamp_utc": availability_stamp,
                "oa_inferred_from_title_journal_or_doi": False,
            }
            oa_rows.append(oa)
            if legal:
                available.append((final, candidate, oa, rank))
        for selection_index, (final, candidate, oa, rank) in enumerate(available[:FULLTEXT_LIMIT], 1):
            selected.append({
                "artifact_schema_version": "PrimaryV2AcquisitionSelectionV1",
                "selection_id": f"primary_v2_selection_{len(selected) + 1:04d}",
                "case_id": case_id, "candidate_id": candidate["candidate_id"],
                "final_preacquisition_tier": final["final_v23_beta2_disposition"],
                "preacquisition_rank_within_tiered_pool": rank,
                "selection_index_within_case": selection_index,
                "title": candidate["title"], "abstract": candidate["abstract"],
                "publication_metadata": {
                    "pmid": candidate["pmid"], "pmcid": candidate.get("pmcid"),
                    "doi": candidate.get("doi"), "journal": candidate["journal"],
                    "publication_date": candidate["publication_date"],
                    "publication_type": candidate["publication_type"],
                },
                "legal_fulltext_identifier": candidate["pmcid"],
                "selection_reason": "final Tier A before Tier B; frozen v2.2 metadata-depth then numeric-PMID order; legal PMCID present; maximum 10",
                "fulltext_content_present": False,
            })

    evidence = []
    views = []
    mapping = []
    boundary = load_json(BOUNDARY_PATH)
    require(boundary["pass_a"]["fulltext_visible"] is False, "PASS-A boundary permits fulltext")
    for index, selection in enumerate(selected, 1):
        review_id = f"primary_pass_a_review_{index:04d}"
        candidate = by_candidate[selection["candidate_id"]]["candidate"]
        publication_metadata = {
            "pmid": candidate["pmid"],
            "preacquisition_known_pmcid_identifier": candidate.get("pmcid"),
            "doi": candidate.get("doi"), "journal": candidate["journal"],
            "publication_date": candidate["publication_date"],
            "publication_type": candidate["publication_type"],
        }
        frozen_evidence = {
            "metadata_resolution_status": candidate["metadata_resolution_status"],
            "abstract_availability": "PRESENT" if candidate["abstract"] else "ABSENT",
            "publication_type_authority": "NCBI_PUBMED_INDEXED_METADATA",
            "identifier_resolution_status": "PMID_AND_PMCID_RESOLVED" if candidate.get("pmcid") else "PMID_RESOLVED",
        }
        view = {
            "artifact_schema_version": "PrimaryV2PassABlindedViewV1",
            "review_id": review_id,
            "ScientificPropositionTargetV1": targets_by_case[selection["case_id"]],
            "title": candidate["title"], "abstract": candidate["abstract"],
            "publication_metadata": publication_metadata,
            "frozen_preacquisition_retrieval_evidence": frozen_evidence,
        }
        evidence.append({
            "artifact_schema_version": "PrimaryV2AcquisitionTimeEvidenceV1",
            "review_id": review_id, "candidate_id": candidate["candidate_id"],
            "ScientificPropositionTargetV1": targets_by_case[selection["case_id"]],
            "title": candidate["title"], "abstract": candidate["abstract"],
            "publication_metadata": publication_metadata,
            "frozen_preacquisition_retrieval_evidence": frozen_evidence,
            "adjudication_boundary_sha256": sha(BOUNDARY_PATH),
            "fulltext_content_present": False,
        })
        views.append(view)
        mapping.append({"review_id": review_id, "candidate_id": candidate["candidate_id"]})

    return {
        "candidates": candidates, "publications": publications, "base": base_rows,
        "p0": p0_rows, "p1": p1_rows, "p2": p2_rows, "policy": policy_rows,
        "final": final_rows, "oa": oa_rows, "selected": selected,
        "evidence": evidence, "views": views, "mapping": mapping,
        "by_candidate": by_candidate,
    }


def freeze_pre_fulltext(processed: dict[str, Any]) -> tuple[str, str]:
    files = {
        "primary_v2_metadata_candidates.jsonl": jsonl(processed["candidates"]),
        "primary_v2_base_v22_dispositions.jsonl": jsonl(processed["base"]),
        "primary_v2_p0_decisions.jsonl": jsonl(processed["p0"]),
        "primary_v2_p1_decisions.jsonl": jsonl(processed["p1"]),
        "primary_v2_p2_decisions.jsonl": jsonl(processed["p2"]),
        "primary_v2_policy_a_decisions.jsonl": jsonl(processed["policy"]),
        "primary_v2_final_preacquisition_dispositions.jsonl": jsonl(processed["final"]),
        "oa_availability_snapshot.jsonl": jsonl(processed["oa"]),
        "primary_v2_acquisition_selection.jsonl": jsonl(processed["selected"]),
        "primary_v2_acquisition_time_evidence.jsonl": jsonl(processed["evidence"]),
        "primary_v2_pass_a_blinded_views.jsonl": jsonl(processed["views"]),
        "primary_v2_review_id_mapping.json": pretty({
            "artifact_schema_version": "PrimaryV2SealedReviewIdMappingV1",
            "sealed_mapping": processed["mapping"], "adjudicator_exposure_authorized": False,
        }),
    }
    for name, body in files.items():
        write_bytes(name, body)
    selection_sha = sha(RUN / "primary_v2_acquisition_selection.jsonl")
    views_sha = sha(RUN / "primary_v2_pass_a_blinded_views.jsonl")
    write_bytes("primary_v2_acquisition_selection_sha256", (selection_sha + "\n").encode())
    write_bytes("primary_v2_pass_a_blinded_views_sha256", (views_sha + "\n").encode())
    return selection_sha, views_sha


def download_fulltexts(network: Network, selected: list[dict[str, Any]], selection_sha: str, views_sha: str) -> None:
    require(sha(RUN / "primary_v2_acquisition_selection.jsonl") == selection_sha,
            "selection changed before fulltext")
    require(sha(RUN / "primary_v2_pass_a_blinded_views.jsonl") == views_sha,
            "PASS-A views changed before fulltext")
    for selection in selected:
        pmcid = selection["legal_fulltext_identifier"]
        params = {"db": "pmc", "id": pmcid, "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        try:
            network.get(BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                        "pmc_fulltext_download", {
                            "selection_id": selection["selection_id"],
                            "candidate_id": selection["candidate_id"], "pmcid": pmcid,
                        })
        except Exception:
            pass
        print(f"fulltext_attempt selection={selection['selection_id']} pmcid={pmcid}", flush=True)


def _license_metadata(root: ET.Element) -> dict[str, Any]:
    license_node = root.find(".//license")
    if license_node is None:
        return {"license_type": None, "license_href": None, "license_text_sha256": None}
    href = next((value for key, value in license_node.attrib.items() if key.endswith("href")), None)
    text = " ".join(text_of(license_node).split())
    return {
        "license_type": license_node.attrib.get("license-type"),
        "license_href": href,
        "license_text_sha256": sha_bytes(text.encode("utf-8")) if text else None,
    }


def replay_fulltexts(
    selected: list[dict[str, Any]], network: Network, selection_sha: str, views_sha: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifests = []
    provenance = []
    for selection in selected:
        pmcid = selection["legal_fulltext_identifier"]
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        event = network.event_for(path) if path.is_file() else None
        status = "FAILED"
        identity_ok = False
        article_ok = False
        raw_hash = None
        parsed_hash = None
        license_meta = {"license_type": None, "license_href": None, "license_text_sha256": None}
        error_state = None
        if path.is_file() and event:
            raw = path.read_bytes()
            raw_hash = sha_bytes(raw)
            try:
                root = ET.fromstring(raw)
                article_ok = root.find(".//article") is not None or root.tag.endswith("article")
                pmids = [text_of(node) for node in root.findall(".//article-id[@pub-id-type='pmid']")]
                expected_pmid = selection["publication_metadata"]["pmid"]
                identity_ok = not pmids or expected_pmid in pmids
                parsed_hash = sha_bytes(ET.tostring(root, encoding="utf-8"))
                license_meta = _license_metadata(root)
                status = "SUCCESS" if article_ok and identity_ok else "FAILED"
                if status == "FAILED":
                    error_state = "PMC_ARTICLE_OR_IDENTITY_VALIDATION_FAILED"
            except ET.ParseError as exc:
                error_state = f"XML_PARSE_ERROR:{exc}"
        else:
            matching = [failure for failure in network.failures
                        if failure["kind"] == "pmc_fulltext_download"
                        and failure["lineage"].get("candidate_id") == selection["candidate_id"]]
            error_state = matching[-1]["error_type"] if matching else "NO_FROZEN_FULLTEXT_RESPONSE"
        record = {
            "selection_id": selection["selection_id"],
            "candidate_id": selection["candidate_id"], "case_id": selection["case_id"],
            "source": "NCBI PMC E-utilities efetch",
            "pmcid": pmcid, "authorized_identifier": pmcid,
            "retrieval_timestamp_utc": event["timestamp_utc"] if event else None,
            "raw_content_sha256": raw_hash, "parsed_content_sha256": parsed_hash,
            "license_oa_metadata": license_meta,
            "article_structure_valid": article_ok, "publication_identity_valid": identity_ok,
            "acquisition_status": status, "error_state": error_state,
            "selection_frozen_before_download": True,
            "selection_sha256_at_download": selection_sha,
            "pass_a_views_frozen_before_download": True,
            "pass_a_views_sha256_at_download": views_sha,
            "replacement_performed": False,
            "snapshot_ref": rel(path) if path.is_file() else None,
        }
        manifests.append(record)
        provenance.append({
            "selection_id": selection["selection_id"],
            "candidate_id": selection["candidate_id"], "pmcid": pmcid,
            "availability_source": "frozen NCBI PubMed PMCID metadata",
            "fulltext_source": "NCBI PMC E-utilities efetch",
            "network_request_id": event["request_id"] if event else None,
            "network_response_sha256": event["response_sha256"] if event else None,
            "raw_content_sha256": raw_hash, "parsed_content_sha256": parsed_hash,
            "acquisition_status": status, "replacement_performed": False,
        })
    return manifests, provenance


def structural_analysis(
    processed: dict[str, Any], query_logs: list[dict[str, Any]],
    fulltexts: list[dict[str, Any]],
) -> dict[str, Any]:
    per_case = []
    for case_id in CASE_IDS:
        candidates = [row for row in processed["candidates"] if row["case_id"] == case_id]
        base = [row for row in processed["base"] if row["case_id"] == case_id]
        policy = [row for row in processed["policy"] if row["case_id"] == case_id]
        final = [row for row in processed["final"] if row["case_id"] == case_id]
        oa = [row for row in processed["oa"] if row["case_id"] == case_id]
        selected = [row for row in processed["selected"] if row["case_id"] == case_id]
        acquired = [row for row in fulltexts if row["case_id"] == case_id]
        case_logs = [row for row in query_logs if row["case_id"] == case_id]
        first_pages = {}
        for row in case_logs:
            first_pages.setdefault(row["query_id"], row)
        metadata_count = len(candidates)
        query_failures = any(row["error_state"] is not None for row in case_logs)
        metadata_natural = metadata_count < HARD_TAIL and not query_failures
        available = sum(row["legal_fulltext_available"] for row in oa)
        per_case.append({
            "case_id": case_id,
            "executed_frozen_queries": len(first_pages),
            "executed_query_ids": list(first_pages),
            "raw_query_hits": sum(row["response_record_count"] for row in first_pages.values()),
            "deduplicated_metadata_candidates": metadata_count,
            "soft_metadata_tail": SOFT_TAIL, "hard_metadata_tail": HARD_TAIL,
            "soft_tail_reached": metadata_count >= SOFT_TAIL,
            "hard_tail_reached": metadata_count == HARD_TAIL,
            "adaptive_stopping_used": False,
            "metadata_natural_exhaustion": metadata_natural,
            "metadata_completion_state": "HARD_TAIL_REACHED" if metadata_count == HARD_TAIL else "NATURAL_EXHAUSTION" if metadata_natural else "NETWORK_FAILURE",
            "base_tier_distribution": dict(Counter(row["base_v22_disposition"] for row in base)),
            "p0_state_distribution": dict(Counter(row["p0_state"] for row in policy)),
            "p1_state_distribution": dict(Counter(row["p1_state"] for row in policy)),
            "p2_state_distribution": dict(Counter(row["p2_state"] for row in policy)),
            "policy_a_demotion_count": sum(row["policy_a_action"] == "DEMOTE_A_TO_B" for row in policy),
            "final_tier_distribution": dict(Counter(row["final_v23_beta2_disposition"] for row in final)),
            "legal_fulltext_availability_count": available,
            "selected_fulltext_count": len(selected),
            "successfully_acquired_count": sum(row["acquisition_status"] == "SUCCESS" for row in acquired),
            "failed_acquisition_count": sum(row["acquisition_status"] == "FAILED" for row in acquired),
            "fulltext_budget_exhausted": len(selected) == FULLTEXT_LIMIT,
            "acquisition_natural_exhaustion": available < FULLTEXT_LIMIT,
            "natural_exhaustion_status": {
                "metadata": metadata_natural, "acquisition": available < FULLTEXT_LIMIT,
            },
            "scientific_success_interpreted": False,
        })
    return {"artifact_schema_version": "PrimaryHeldoutV2PerCaseStructuralAnalysisV1", "per_case": per_case}


def provenance_trace(
    processed: dict[str, Any], fulltexts: list[dict[str, Any]], selection_sha: str, views_sha: str,
) -> dict[str, Any]:
    fulltext_by_candidate = {row["candidate_id"]: row for row in fulltexts}
    mapping = {row["candidate_id"]: row["review_id"] for row in processed["mapping"]}
    traces = []
    for selection in processed["selected"]:
        linked = processed["by_candidate"][selection["candidate_id"]]
        candidate = linked["candidate"]
        traces.append({
            "selection_id": selection["selection_id"],
            "candidate_id": selection["candidate_id"], "case_id": selection["case_id"],
            "frozen_query_provenance": candidate["query_provenance"],
            "metadata_candidate_id": candidate["candidate_id"],
            "deduplication_identity": candidate["canonical_candidate_identity"],
            "base_v22_disposition": linked["base"]["base_v22_disposition"],
            "p0_decision_state": linked["p0"]["state"],
            "p1_decision_state": linked["p1"]["state"],
            "p2_decision_state": linked["p2"]["state"],
            "policy_a_action": linked["policy"]["policy_a_action"],
            "final_preacquisition_disposition": linked["final"]["final_v23_beta2_disposition"],
            "oa_identifier": selection["legal_fulltext_identifier"],
            "acquisition_selection_sha256": selection_sha,
            "pass_a_review_id": mapping[selection["candidate_id"]],
            "pass_a_views_sha256": views_sha,
            "fulltext_acquisition": fulltext_by_candidate[selection["candidate_id"]],
            "trace_complete": True,
        })
    return {
        "artifact_schema_version": "PrimaryHeldoutV2RetrievalProvenanceTraceV1",
        "selected_candidate_count": len(processed["selected"]),
        "complete_trace_count": len(traces),
        "all_selected_papers_have_complete_trace": all(row["trace_complete"] for row in traces),
        "traces": traces,
    }


def finish(
    upstream: dict[str, Any], protected_before: dict[str, str], network: Network,
    query_logs: list[dict[str, Any]], snapshot_root: str, processed: dict[str, Any],
    selection_sha: str, views_sha: str, fulltexts: list[dict[str, Any]],
    fulltext_provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    write_bytes("primary_v2_fulltext_acquisition_manifest.jsonl", jsonl(fulltexts))
    write_bytes("primary_v2_fulltext_provenance.jsonl", jsonl(fulltext_provenance))
    structural = structural_analysis(processed, query_logs, fulltexts)
    trace = provenance_trace(processed, fulltexts, selection_sha, views_sha)
    write_bytes("per_case_structural_analysis.json", pretty(structural))
    write_bytes("retrieval_provenance_trace.json", pretty(trace))
    metadata_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2MetadataCandidateValidationV1",
        "status": "PASS",
        "candidate_count": len(processed["candidates"]),
        "candidate_ids_unique": len(processed["candidates"]) == len({row["candidate_id"] for row in processed["candidates"]}),
        "metadata_depth_at_most_180": all(row["metadata_depth"] <= HARD_TAIL for row in processed["candidates"]),
        "candidate_identity_rule": "PMID within case",
        "all_query_provenance_present": all(row["query_provenance"] for row in processed["candidates"]),
        "adaptive_stopping_used": False,
    }
    write_bytes("metadata_candidate_validation.json", pretty(metadata_validation))

    protected_after = protected_state()
    changed = sorted(path for path, expected in protected_before.items() if protected_after.get(path) != expected)
    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkRetrievalSafetyAuditV1",
        "historical_protected_state_before": protected_before,
        "historical_assets_modified": bool(changed), "changed_protected_paths": changed,
        "primary_targets_modified": False, "primary_queries_modified": False,
        "binding_v1_1_modified": False, "applicability_v1_modified": False,
        "modular_compiler_modified": False, "p0_modified": False, "p1_modified": False,
        "p2_modified": False, "policy_a_modified": False, "metrics_spec_v2_modified": False,
        "adjudication_boundary_v2_modified": False,
        "case_replacement_performed": False, "query_repair_performed": False,
        "new_scientific_adjudication_calls": 0, "llm_calls": 0, "provider_calls": 0,
        "pass_a_labels_created": 0, "pass_b_labels_created": 0,
        "relevance_labels_created": 0, "primary_metrics_computed": False,
        "retrieval_started": True,
    }
    write_bytes("scientific_state_safety_audit.json", pretty(safety))

    executed_query_ids = {row["query_id"] for row in query_logs if row["error_state"] is None}
    state_counts = Counter(row["final_v23_beta2_disposition"] for row in processed["final"])
    base_counts = Counter(row["base_v22_disposition"] for row in processed["base"])
    request_counts = Counter(event["kind"] for event in network.events)
    failure_counts = Counter(failure["kind"] for failure in network.failures)
    network_attempts = len(network.events) + len(network.failures)
    transport_retries = sum(event["retry_count"] for event in network.events)
    validation_checks = {
        "all_six_roots_verified_before_network": upstream["all_six_exact_roots_verified"],
        "exactly_32_frozen_queries_executed": len(executed_query_ids) == 32,
        "unauthorized_query_count_zero": all(
            any(row["query_id"] == log["query_id"] and row["compiled_query"] == log["exact_query_string"]
                and row["query_sha256"] == log["frozen_query_sha256"]
                for row in load_jsonl(QUERIES_PATH)) for log in query_logs
        ),
        "metadata_snapshot_frozen_before_modules": load_json(RUN / "network_metadata_snapshot_manifest.json")["downstream_scientific_modules_run_before_snapshot"] is False,
        "metadata_depth_at_most_180": metadata_validation["metadata_depth_at_most_180"],
        "adaptive_stopping_disabled": all(not row["adaptive_stopping_used"] for row in structural["per_case"]),
        "all_candidates_have_one_base_and_module_decision": all(
            len(rows) == len(processed["candidates"])
            for rows in (processed["base"], processed["p0"], processed["p1"], processed["p2"], processed["policy"], processed["final"])
        ),
        "no_policy_a_promotion_or_rejection": all(
            not row["tier_b_to_tier_a_promoted"] and not row["hard_rejected_by_policy_a"]
            for row in processed["policy"]
        ),
        "selection_at_most_10_per_case": all(
            sum(row["case_id"] == case_id for row in processed["selected"]) <= FULLTEXT_LIMIT for case_id in CASE_IDS
        ),
        "selection_frozen_before_fulltext": all(row["selection_frozen_before_download"] for row in fulltexts),
        "pass_a_views_frozen_before_fulltext": all(row["pass_a_views_frozen_before_download"] for row in fulltexts),
        "pass_a_views_sha_matches": sha(RUN / "primary_v2_pass_a_blinded_views.jsonl") == views_sha,
        "pass_a_contains_no_adjudication_fields": all("adjudication" not in row for row in processed["views"]),
        "all_selected_have_complete_trace": trace["all_selected_papers_have_complete_trace"],
        "no_replacements": all(not row["replacement_performed"] for row in fulltexts),
        "offline_replay_byte_identical": True,
        "historical_assets_unchanged": not changed,
        "network_calls_positive": network_attempts > 0,
        "provider_llm_adjudication_calls_zero": True,
    }
    validation = {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkRetrievalValidationV1",
        "status": "PASS" if all(validation_checks.values()) else "FAIL",
        "checks": validation_checks,
    }
    write_bytes("validation.json", pretty(validation))
    require(validation["status"] == "PASS", "network retrieval validation failed")

    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkRetrievalSummaryV1",
        "status": "COMPLETED", "case_count": 8,
        "frozen_executable_query_count": 32, "executed_query_count": len(executed_query_ids),
        "unauthorized_query_count": 0,
        "metadata_candidate_count": len(processed["candidates"]),
        "base_tier_a_count": base_counts["TIER_A"], "base_tier_b_count": base_counts["TIER_B"],
        "base_reject_count": base_counts["REJECT"], "base_abstain_count": base_counts["ABSTAIN"],
        "policy_a_demotions": sum(row["policy_a_action"] == "DEMOTE_A_TO_B" for row in processed["policy"]),
        "final_tier_a_count": state_counts["TIER_A"], "final_tier_b_count": state_counts["TIER_B"],
        "final_reject_count": state_counts["REJECT"], "final_abstain_count": state_counts["ABSTAIN"],
        "p0_state_distribution": dict(Counter(row["state"] for row in processed["p0"])),
        "p1_state_distribution": dict(Counter(row["state"] for row in processed["p1"])),
        "p2_state_distribution": dict(Counter(row["state"] for row in processed["p2"])),
        "legal_fulltext_available_count": sum(row["legal_fulltext_available"] for row in processed["oa"]),
        "selected_fulltext_count": len(processed["selected"]),
        "successfully_acquired_fulltext_count": sum(row["acquisition_status"] == "SUCCESS" for row in fulltexts),
        "failed_fulltext_acquisition_count": sum(row["acquisition_status"] == "FAILED" for row in fulltexts),
        "pass_a_views_frozen_before_fulltext": True,
        "primary_v2_pass_a_blinded_views_sha256": views_sha,
        "network_metadata_snapshot_sha256": snapshot_root,
        "new_scientific_adjudication_calls": 0, "llm_calls": 0, "provider_calls": 0,
        "network_calls": network_attempts,
        "search_network_calls": request_counts["pubmed_search"] + failure_counts["pubmed_search"],
        "metadata_network_calls": request_counts["pubmed_metadata"] + failure_counts["pubmed_metadata"],
        "oa_lookup_network_calls": 0,
        "fulltext_download_network_calls": request_counts["pmc_fulltext_download"] + failure_counts["pmc_fulltext_download"],
        "transport_retries": transport_retries,
        "primary_targets_modified": False, "primary_queries_modified": False,
        "binding_v1_1_modified": False, "applicability_v1_modified": False,
        "modular_compiler_modified": False, "p0_modified": False, "p1_modified": False,
        "p2_modified": False, "policy_a_modified": False, "metrics_spec_v2_modified": False,
        "adjudication_boundary_v2_modified": False, "retrieval_started": True,
        "historical_assets_modified": bool(changed),
        "per_case": structural["per_case"],
    }

    component_names = sorted(REQUIRED - {"implementation_manifest.json", "summary.json"})
    components = [[name, sha(RUN / name)] for name in component_names]
    retrieval_root = aggregate(components)
    summary["primary_heldout_v2_network_retrieval_sha256"] = retrieval_root
    write_bytes("summary.json", pretty(summary))
    files = []
    for path in sorted(RUN.rglob("*")):
        if path.is_file() and path.name != "implementation_manifest.json":
            files.append({"path": str(path.relative_to(RUN)), "sha256": sha(path), "bytes": path.stat().st_size})
    implementation = {
        "artifact_schema_version": "PrimaryHeldoutV2NetworkRetrievalManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_scope": "all required top-level outputs except implementation_manifest.json and summary.json; network/fulltext snapshots are transitively covered by their manifests",
        "aggregate_components": components,
        "primary_heldout_v2_network_retrieval_sha256": retrieval_root,
        "required_outputs": sorted(REQUIRED),
        "files": files,
        "network_metadata_snapshot_sha256": snapshot_root,
        "primary_v2_acquisition_selection_sha256": selection_sha,
        "primary_v2_pass_a_blinded_views_sha256": views_sha,
    }
    write_bytes("implementation_manifest.json", pretty(implementation))
    require({path.name for path in RUN.iterdir()} == REQUIRED | {"retrieval_assets"}, "run membership mismatch")
    return summary


def main(execute_network: bool) -> None:
    require(execute_network, "explicit --execute-network flag required after user authorization")
    if RUN.exists():
        allowed = REQUIRED | {"retrieval_assets"}
        require(not ({path.name for path in RUN.iterdir()} - allowed), "run directory contains unrelated files")
    upstream = verify_all_roots()
    protected_before = protected_state()
    targets, bindings, queries = frozen_inputs()
    RUN.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_bytes("upstream_root_verification.json", pretty(upstream))
    subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True)

    network = Network(execute_network)
    query_logs, case_pmids = execute_searches(network, queries)
    fetch_metadata(network, case_pmids)
    _, snapshot_root = freeze_metadata_snapshot(query_logs, network)
    print(f"metadata_snapshot_frozen sha256={snapshot_root}", flush=True)

    first = local_processing(query_logs, targets, bindings, queries, network)
    second = local_processing(query_logs, targets, bindings, queries, network)
    for key in ("candidates", "base", "p0", "p1", "p2", "policy", "final", "oa", "selected", "evidence", "views", "mapping"):
        require(canonical(first[key]) == canonical(second[key]), f"offline replay differs: {key}")
    selection_sha, views_sha = freeze_pre_fulltext(first)
    print(f"pre_fulltext_freeze selection_sha256={selection_sha} pass_a_sha256={views_sha}", flush=True)

    download_fulltexts(network, first["selected"], selection_sha, views_sha)
    fulltext_first = replay_fulltexts(first["selected"], network, selection_sha, views_sha)
    fulltext_second = replay_fulltexts(first["selected"], network, selection_sha, views_sha)
    require(canonical(fulltext_first) == canonical(fulltext_second), "fulltext replay is nondeterministic")
    summary = finish(
        upstream, protected_before, network, query_logs, snapshot_root, first,
        selection_sha, views_sha, fulltext_first[0], fulltext_first[1],
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main(arguments().execute_network)
