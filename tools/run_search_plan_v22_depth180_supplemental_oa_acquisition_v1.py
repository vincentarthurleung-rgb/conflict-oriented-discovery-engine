#!/usr/bin/env python3
"""Acquire exactly the seven preselected supplemental PMC fulltexts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline"
PLAN = SOURCE / "supplemental_151_180_selection_plan.jsonl"
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_oa_acquisition_v1"
ASSETS = RUN / "retrieval_assets"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EXPECTED_PLAN_SHA256 = "7ae45177a102c370501608c871a82b231b727ed1e6ea9187b14936d3b692acc4"
EXPECTED_IDS = [
    ("spv2_017", "32133736", "PMC7132338"),
    ("spv2_017", "32863234", "PMC7472926"),
    ("spv2_017", "25071204", "PMC4156761"),
    ("spv2_016", "41579327", "PMC12913879"),
    ("spv2_016", "42160305", "PMC13189296"),
    ("spv2_003", "38531859", "PMC10965960"),
    ("spv2_003", "40569965", "PMC12200854"),
]
REQUIRED = ["baseline.json", "acquisition_attempts.jsonl", "fulltext_manifest.jsonl",
            "network_usage_audit.json", "provider_usage_audit.json", "scientific_state_safety_audit.json",
            "validation.json", "summary.json", "manifest.json"]


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def objsha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
def rel(path): return str(Path(path).resolve().relative_to(ROOT))


def protected_hashes():
    paths = [PLAN, SOURCE / "supplemental_151_180_candidate_inventory.jsonl",
             SOURCE / "supplemental_151_180_balance_summary.json", SOURCE / "manifest.json",
             ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180/tail_metadata_121_180.jsonl",
             ROOT / "tools/search_plan_v22_candidate_gates.py"]
    return {rel(p): sha(p) for p in paths}


class Network:
    def __init__(self, execute):
        self.execute = execute; self.receipt = ASSETS / "network_events.json"
        prior = readj(self.receipt) if self.receipt.exists() else {}
        self.events, self.failures = prior.get("events", []), prior.get("failures", [])

    def get(self, url, path, lineage):
        path = Path(path)
        if path.exists(): return path.read_bytes(), False
        if not self.execute: raise FileNotFoundError(path)
        stamp = now(); request = urllib.request.Request(url, headers={"User-Agent": "conflict-oriented-discovery-engine-supplemental-oa/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body, status, content_type = response.read(), response.status, response.headers.get("Content-Type")
        except Exception as exc:
            self.failures.append({"timestamp": stamp, "kind": "pmc_fulltext_efetch_preselected_supplement",
                                  "url": url, "lineage": lineage, "error_type": type(exc).__name__, "error": str(exc)})
            self.save(); raise
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        self.events.append({"request_id": f"supplemental_pmc_request_{len(self.events)+1:04d}",
            "timestamp": stamp, "kind": "pmc_fulltext_efetch_preselected_supplement", "url": url,
            "http_status": status, "content_type": content_type, "snapshot_ref": rel(path),
            "response_sha256": sha(path), "bytes": len(body), "lineage": lineage})
        self.save(); time.sleep(.36); return body, True

    def save(self):
        writej(self.receipt, {"events": self.events, "failures": self.failures,
                              "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0})


def execute(network_enabled):
    if RUN.exists() and any(p.name not in REQUIRED and p.name != "retrieval_assets" for p in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True); ASSETS.mkdir(parents=True, exist_ok=True)
    protected_before = protected_hashes(); plan_hash = sha(PLAN); plan = readl(PLAN)
    identities = [(x["case_id"], x["pmid"], x["preserved_pmcid"]) for x in plan]
    if plan_hash != EXPECTED_PLAN_SHA256 or identities != EXPECTED_IDS or len(plan) != 7:
        raise RuntimeError("Frozen seven-paper selection plan identity/hash mismatch")
    if any(not x["preserved_pmcid_available"] or x["label_fields_used"] for x in plan):
        raise RuntimeError("Selection plan is not the authorized preserved-PMCID label-blind plan")
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    writej(RUN / "baseline.json", {"source_selection_plan_ref": rel(PLAN), "source_selection_plan_sha256": plan_hash,
        "explicit_network_authorization": True,
        "authorization_scope": "exact seven preselected preserved PMCIDs; NCBI PMC efetch only",
        "authorized_selection_count": 7, "authorized_identities": [list(x) for x in identities],
        "pubmed_search_authorized": False, "metadata_extension_authorized": False,
        "replacement_discovery_authorized": False, "provider_authorized": False,
        "llm_authorized": False, "extraction_authorized": False,
        "protected_hashes_before": protected_before, "git_head_at_execution": git_head})

    network = Network(network_enabled); attempts, acquired = [], []
    for row in plan:
        pmcid, pmid = row["preserved_pmcid"], row["pmid"]
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        params = {"db": "pmc", "id": pmcid, "retmode": "xml", "tool": "conflict_oriented_discovery_engine"}
        base = {"attempt_id": f"supplemental_oa_{row['planned_selection_order']:04d}",
            "planned_selection_order": row["planned_selection_order"], "case_id": row["case_id"],
            "publication_id": row["publication_id"], "pmid": pmid, "pmcid": pmcid,
            "metadata_depth": row["metadata_depth"], "tier_state": row["tier_state"],
            "source_selection_plan_ref": rel(PLAN), "source_selection_plan_sha256": plan_hash,
            "replacement_used": False, "pubmed_search_performed": False, "metadata_depth_extended": False}
        try:
            raw, request_made = network.get(BASE + "?" + urllib.parse.urlencode(params), path,
                                            {"planned_selection_order": row["planned_selection_order"],
                                             "case_id": row["case_id"], "pmid": pmid, "pmcid": pmcid})
            root = ET.fromstring(raw); article_ok = root.find(".//article") is not None or root.tag.endswith("article")
            xml_pmids = ["".join(x.itertext()).strip() for x in root.findall(".//article-id[@pub-id-type='pmid']")]
            identity_ok = not xml_pmids or pmid in xml_pmids
            status = "fulltext_acquired" if article_ok and identity_ok else ("fulltext_identity_mismatch" if article_ok else "fulltext_retrieval_failed")
            result = {**base, "status": status, "network_request_made": request_made,
                "pmc_article_present": article_ok, "pmid_identity_valid": identity_ok, "xml_pmids": xml_pmids,
                "snapshot_ref": rel(path), "content_hash": sha(path), "bytes": path.stat().st_size,
                "source_identity": "NCBI PMC efetch", "scientific_extraction_performed": False}
            attempts.append(result)
            if status == "fulltext_acquired": acquired.append(result)
        except Exception as exc:
            attempts.append({**base, "status": "fulltext_retrieval_failed", "network_request_made": network_enabled,
                             "error_type": type(exc).__name__, "error": str(exc), "scientific_extraction_performed": False})
    writel(RUN / "acquisition_attempts.jsonl", attempts); writel(RUN / "fulltext_manifest.jsonl", acquired)

    request_counts = Counter(x["kind"] for x in network.events)
    writej(RUN / "network_usage_audit.json", {"authorized": True, "authorization_scope_respected": True,
        "network_request_count": len(network.events)+len(network.failures), "successful_network_response_count": len(network.events),
        "failed_network_attempt_count": len(network.failures), "request_counts_by_kind": dict(request_counts),
        "allowed_service_only": all("eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi" in x["url"] for x in network.events),
        "requested_pmcids": [x["lineage"]["pmcid"] for x in network.events],
        "authorized_pmcids": [x[2] for x in EXPECTED_IDS], "pubmed_search_calls": 0,
        "metadata_calls": 0, "replacement_discovery_calls": 0, "event_receipt_ref": rel(network.receipt),
        "credentials_logged": False})
    writej(RUN / "provider_usage_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "experimental_extraction_calls": 0, "provider_or_model_client_created": False,
        "fulltext_scientific_content_extracted": False})
    protected_after = protected_hashes()
    changed = sorted(k for k in set(protected_before)|set(protected_after) if protected_before.get(k) != protected_after.get(k))
    safety = {"historical_assets_modified": bool(changed), "changed_protected_paths": changed,
        "source_selection_plan_unchanged": sha(PLAN) == plan_hash, "exact_selection_preserved": identities == EXPECTED_IDS,
        "new_pubmed_search_performed": False, "metadata_depth_extended": False,
        "replacement_papers_discovered_or_used": False, "selection_changed": False,
        "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0,
        "search_plan_modified": False, "gate_modified": False, "git_mutation_invoked": False}
    writej(RUN / "scientific_state_safety_audit.json", safety)
    summary = {"status": "completed" if len(acquired) == 7 and not network.failures else "partial",
        "authorized_selection_count": 7, "acquisition_attempt_count": len(attempts),
        "fulltext_acquired_count": len(acquired), "retrieval_failure_count": sum(x["status"] != "fulltext_acquired" for x in attempts),
        "per_case": [{"case_id": cid, "selected_count": sum(x["case_id"] == cid for x in plan),
                      "acquired_count": sum(x["case_id"] == cid for x in acquired)} for cid in ["spv2_017", "spv2_016", "spv2_003"]],
        "network_request_count": len(network.events)+len(network.failures), "pubmed_search_calls": 0,
        "metadata_calls": 0, "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0,
        "selection_changed": False, "replacement_count": 0, "historical_assets_modified": bool(changed),
        "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)
    checks = {"exact_seven_plan_hash": plan_hash == EXPECTED_PLAN_SHA256, "exact_seven_identity_order": identities == EXPECTED_IDS,
        "attempted_exactly_once": len(attempts) == len({x["pmcid"] for x in attempts}) == 7,
        "all_fulltexts_acquired": len(acquired) == 7, "all_pmc_articles_valid": all(x["pmc_article_present"] for x in acquired),
        "all_pmid_identities_valid": all(x["pmid_identity_valid"] for x in acquired),
        "only_authorized_pmcids_requested": set(x["lineage"]["pmcid"] for x in network.events) <= set(x[2] for x in EXPECTED_IDS),
        "no_pubmed_search_or_metadata_calls": summary["pubmed_search_calls"] == summary["metadata_calls"] == 0,
        "no_replacement_or_selection_change": not summary["selection_changed"] and summary["replacement_count"] == 0,
        "provider_llm_extraction_zero": summary["provider_calls"] == summary["llm_calls"] == summary["extraction_calls"] == 0,
        "source_plan_and_historical_assets_unchanged": not changed and sha(PLAN) == plan_hash,
        "required_payloads_present": all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json", "manifest.json"})}
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    assets = [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(ASSETS.rglob("*")) if p.is_file()]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files, "retrieval_assets": assets,
        "source_selection_plan_sha256": plan_hash, "network_request_count": len(network.events)+len(network.failures),
        "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0})
    checks["manifest_hashes_valid"] = all(sha(RUN/x["path"]) == x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN/x).is_file() for x in REQUIRED)
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files, "retrieval_assets": assets,
        "source_selection_plan_sha256": plan_hash, "network_request_count": len(network.events)+len(network.failures),
        "provider_calls": 0, "llm_calls": 0, "extraction_calls": 0})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()): raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--execute-network", action="store_true"); parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.execute_network == args.replay: raise SystemExit("Choose exactly one mode")
    execute(args.execute_network)


if __name__ == "__main__": main()
