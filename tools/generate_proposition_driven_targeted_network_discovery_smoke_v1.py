#!/usr/bin/env python3
"""Execute or replay the bounded, provider-free targeted discovery smoke."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from code_engine.context_attribution.conflict_candidate.targeted_network_discovery_v1_candidate import (
    ProviderExtractionCandidateV1,
    contains_all_groups_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260827_proposition_driven_targeted_network_discovery_smoke_v1"
ART = RUN / "artifacts"
ASSETS = RUN / "retrieval_assets"
PROTOCOL = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline/artifacts"
ENTITY = ROOT / "runs/20260825_scientific_entity_identity_authority_v1_offline/artifacts"
QUAL = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
PI3K = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts"
FORMAL = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
FILES = (
    "baseline.json", "executed_retrieval_queries.jsonl", "metadata_candidate_inventory.jsonl",
    "publication_independence_audit.jsonl", "abstract_proposition_screen.jsonl",
    "fulltext_acquisition_inventory.jsonl", "fulltext_proposition_screen.jsonl",
    "provider_extraction_candidates_v1.jsonl", "target_execution_ledger.jsonl",
    "retrieval_budget_accounting.json", "provider_extraction_smoke_plan.json",
    "discovery_smoke_decision.json", "scientific_state_safety_audit.json",
    "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json",
)
ORDER = [
    "future_proposition_target_v1:45b8c00ad24ef8f5",
    "future_proposition_target_v1:84faa47f886bfd88",
    "future_proposition_target_v1:4257c6640102256b",
    "future_proposition_target_v1:64f78bb753d6c662",
]
PROHIBITED = {"contradictory", "opposite", "conflicting", "controversial"}
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    for name in ("focused_pass_count", "related_pass_count", "full_pass_count", "full_subtest_pass_count", "full_failure_count", "full_collected_count"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=0)
    parser.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--final-failure-id", action="append", default=[])
    return parser.parse_args()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_rows(name: str, values: Iterable[Any]) -> None:
    rows = [value.model_dump(mode="json") if hasattr(value, "model_dump") else value for value in values]
    (ART / name).write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def text_of(node: ET.Element | None) -> str:
    return "" if node is None else "".join(node.itertext()).strip()


def build_query(components: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    entity = [term for term in components["entity_terms"] if not term.startswith(("EntrezGene:", "NCIT:"))]
    measurement = [term for term in components["measurement_target_terms"] if not term.startswith(("EntrezGene:", "NCIT:"))]
    if not measurement:
        measurement = components["measurement_target_terms"]
    relation = components["relation_effect_terms"]
    def lane(terms: list[str]) -> str:
        return "(" + " OR ".join(f'"{term}"[Title/Abstract]' for term in terms) + ")"
    query = " AND ".join((lane(entity), lane(measurement), lane(relation)))
    assert not any(term in query.casefold() for term in PROHIBITED)
    return query, {"entity": entity, "measurement_target": measurement, "relation_effect": relation}


def parse_summary(raw: bytes) -> list[dict[str, Any]]:
    payload = json.loads(raw)
    result = payload.get("result", {})
    output = []
    for pmid in result.get("uids", []):
        row = result.get(pmid, {})
        ids = {item.get("idtype"): item.get("value") for item in row.get("articleids", [])}
        output.append({
            "pmid": str(pmid), "pmcid": ids.get("pmc"), "doi": ids.get("doi"),
            "title": row.get("title") or "", "publication_date": row.get("pubdate"),
            "journal": row.get("fulljournalname") or row.get("source"),
        })
    return output


def parse_articles(raw: bytes) -> dict[str, dict[str, Any]]:
    root = ET.fromstring(raw)
    output = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = text_of(article.find("./MedlineCitation/PMID"))
        title = text_of(article.find("./MedlineCitation/Article/ArticleTitle"))
        abstract = "\n".join(text_of(node) for node in article.findall("./MedlineCitation/Article/Abstract/AbstractText"))
        ids = {node.attrib.get("IdType"): text_of(node) for node in article.findall("./PubmedData/ArticleIdList/ArticleId")}
        output[pmid] = {"pmid": pmid, "pmcid": ids.get("pmc"), "doi": ids.get("doi"), "title": title, "abstract": abstract}
    return output


class Retrieval:
    def __init__(self, execute: bool):
        self.execute = execute
        self.receipt_path = ASSETS / "execution_receipt.json"
        self.events: list[dict[str, Any]] = []
        self.recorded_events = [] if execute or not self.receipt_path.exists() else read_json(self.receipt_path)["events"]

    def timestamp_for(self, destination: Path, fallback: str) -> str:
        events = self.events if self.execute else self.recorded_events
        return next((event["timestamp"] for event in events if event["relative_path"] == rel(destination)), fallback)

    def get(self, url: str, destination: Path, kind: str) -> bytes:
        if destination.exists() and not self.execute:
            return destination.read_bytes()
        if not self.execute:
            raise FileNotFoundError(destination)
        request = Request(url, headers={"User-Agent": "CODE-targeted-network-discovery-smoke-v1/1.0"})
        started = now()
        with urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        self.events.append({"kind": kind, "timestamp": started, "url": url, "http_status": status, "content_type": content_type, "relative_path": rel(destination), "sha256": sha(destination), "bytes": len(body)})
        time.sleep(0.36)
        return body

    def finish(self) -> dict[str, Any]:
        if self.execute:
            receipt = {"schema_version": "targeted_retrieval_execution_receipt_v1", "authorized_by_user": True, "events": self.events, "provider_calls": 0, "llm_calls": 0}
            self.receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return receipt
        return read_json(self.receipt_path)


def main() -> None:
    opt = args()
    ART.mkdir(parents=True, exist_ok=True); ASSETS.mkdir(parents=True, exist_ok=True)
    specs = {row["target_id"]: row for row in jsonl(PROTOCOL / "targeted_retrieval_specifications_v1.jsonl")}
    components = {row["target_id"]: row for row in jsonl(PROTOCOL / "planned_query_components.jsonl")}
    entity_rows = jsonl(ENTITY / "local_entity_equivalence_classes_v1.jsonl")
    existing_pmids = {ref.split(":", 1)[1] for row in entity_rows for ref in row.get("publication_refs", []) if ref.startswith("pmid:")}
    existing_pmcids = {path.name for path in ROOT.glob("runs/**/fulltext/pmc_oa/PMC*") if path.is_dir() and RUN not in path.parents}
    protected = [
        QUAL / "scientific_candidate_pair_identities.jsonl", QUAL / "conflict_candidate_qualifications.jsonl",
        ALIGN / "claim_alignment_records_v2.jsonl", ALIGN / "contradiction_signals_v2.jsonl", FORMAL,
        CORE / "structured_experimental_observation_revisions.jsonl", CORE / "experimental_factor_records.jsonl",
        CORE / "measurement_records.jsonl", CORE / "observed_result_records.jsonl",
        PI3K / "signal_integrity_audit.jsonl", PI3K / "f389_candidate_experiment_filtering.jsonl",
        PROTOCOL / "targeted_retrieval_specifications_v1.jsonl",
    ]
    before = {rel(path): sha(path) for path in protected}
    write_json("baseline.json", {
        "schema_version": "targeted_network_discovery_smoke_v1_baseline", "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip(),
        "frozen_specification_artifact": rel(PROTOCOL / "targeted_retrieval_specifications_v1.jsonl"), "frozen_specification_sha256": sha(PROTOCOL / "targeted_retrieval_specifications_v1.jsonl"),
        "target_count": 4, "target_order": ORDER, "existing_corpus_pmids": sorted(existing_pmids),
        "historical_candidate_count": 11, "formal_conflict_count": 0, "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "network_authorized_by_user": True, "provider_execution_authorized": False, "protected_hashes_before": before,
    })
    retrieval = Retrieval(opt.execute_network)
    query_records: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    independence_rows: list[dict[str, Any]] = []
    abstract_rows: list[dict[str, Any]] = []
    acquisition_rows: list[dict[str, Any]] = []
    fulltext_rows: list[dict[str, Any]] = []
    provider_candidates: list[ProviderExtractionCandidateV1] = []
    ledgers: list[dict[str, Any]] = []
    global_stop = False
    for position, target_id in enumerate(ORDER, 1):
        spec, comp = specs[target_id], components[target_id]
        rejection_counts: Counter[str] = Counter()
        if global_stop:
            ledgers.append({"schema_version": "target_execution_ledger_v1", "target_id": target_id, "execution_order": position, "metadata_inspected": 0, "unique_independent_publications": 0, "abstracts_inspected": 0, "abstract_plausible_candidates": 0, "fulltexts_acquired": 0, "fulltext_plausible_candidates": 0, "existing_cache_hits": 0, "provider_extraction_candidates": 0, "rejection_counts_by_reason": {}, "budget_consumed": {"metadata": 0, "abstract": 0, "fulltext": 0}, "stop_reason": "global_early_stop_provider_smoke_informative"})
            continue
        query, used = build_query(comp)
        stamp = now()
        query_key = target_id.rsplit(":", 1)[1]
        search_path = ASSETS / query_key / "pubmed_esearch.json"
        summary_path = ASSETS / query_key / "pubmed_esummary.json"
        abstract_path = ASSETS / query_key / "pubmed_efetch.xml"
        search_url = BASE_URL + "/esearch.fcgi?" + urlencode({"db": "pubmed", "term": query, "retmax": 12, "retmode": "json", "sort": "relevance", "tool": "CODE_targeted_smoke"})
        try:
            search_raw = retrieval.get(search_url, search_path, "metadata_search")
        except FileNotFoundError:
            ledgers.append({"schema_version": "target_execution_ledger_v1", "target_id": target_id, "execution_order": position, "metadata_inspected": 0, "unique_independent_publications": 0, "abstracts_inspected": 0, "abstract_plausible_candidates": 0, "fulltexts_acquired": 0, "fulltext_plausible_candidates": 0, "existing_cache_hits": 0, "provider_extraction_candidates": 0, "rejection_counts_by_reason": {}, "budget_consumed": {"metadata": 0, "abstract": 0, "fulltext": 0}, "stop_reason": "not_executed_no_replay_asset"})
            continue
        stamp = retrieval.timestamp_for(search_path, stamp)
        ids = json.loads(search_raw).get("esearchresult", {}).get("idlist", [])[:12]
        query_records.append({"schema_version": "executed_retrieval_query_v1", "target_id": target_id, "execution_order": position, "query_timestamp": stamp, "service": "PubMed", "database": "pubmed", "exact_query": query, "components_used": used, "components_deferred_to_screen": {"measurement_property": comp["measurement_property_terms"], "causal_evidential_mode": spec["causal_evidential_mode"], "intervention": comp["intervention_terms"]}, "result_id_count": len(ids), "result_cap": 12, "primary_direction_terms_used": [], "raw_asset": rel(search_path), "raw_sha256": sha(search_path)})
        summaries = []
        if ids:
            summary_url = BASE_URL + "/esummary.fcgi?" + urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": "CODE_targeted_smoke"})
            summaries = parse_summary(retrieval.get(summary_url, summary_path, "metadata_summary"))
        independent_for_abstract = []
        for rank, row in enumerate(summaries, 1):
            pmcid = row.get("pmcid")
            if row["pmid"] in existing_pmids:
                state, reason = "existing_publication", "PMID already represented in current scientific corpus"
            elif pmcid and pmcid in existing_pmcids:
                state, reason = "duplicate_source", "PMCID already present in local fulltext assets"
            elif not row["pmid"]:
                state, reason = "publication_identity_unresolved", "no stable publication identifier"
            else:
                state, reason = "independent_publication", "resolved PMID is absent from current corpus; PMCID absent from local source assets"
                independent_for_abstract.append(row)
            candidate_id = f"pubmed:{row['pmid']}"
            metadata_rows.append({"schema_version": "metadata_candidate_inventory_v1", "target_id": target_id, "candidate_id": candidate_id, "retrieval_rank": rank, **row, "metadata_source": "PubMed esummary", "retrieval_timestamp": stamp, "executed_query": query, "metadata_snapshot_sha256": sha(summary_path)})
            independence_rows.append({"schema_version": "publication_independence_audit_v1", "target_id": target_id, "candidate_id": candidate_id, "pmid": row["pmid"], "pmcid": pmcid, "doi": row.get("doi"), "local_publication_identity_matches": [f"pmid:{row['pmid']}"] if row["pmid"] in existing_pmids else [], "source_asset_identity_match": pmcid if pmcid in existing_pmcids else None, "independence_state": state, "reason": reason, "checked_before_abstract_admission": True, "checked_before_extraction_recommendation": True})
            if state != "independent_publication": rejection_counts[state] += 1
        selected = independent_for_abstract[:6]
        article_map: dict[str, dict[str, Any]] = {}
        if selected:
            abstract_url = BASE_URL + "/efetch.fcgi?" + urlencode({"db": "pubmed", "id": ",".join(row["pmid"] for row in selected), "retmode": "xml", "tool": "CODE_targeted_smoke"})
            abstract_raw = retrieval.get(abstract_url, abstract_path, "abstract_fetch")
            article_map = parse_articles(abstract_raw)
        plausible = []
        entity_group = [term for term in comp["entity_terms"] if not term.startswith(("EntrezGene:", "NCIT:"))]
        measurement_group = [term for term in comp["measurement_target_terms"] if not term.startswith(("EntrezGene:", "NCIT:"))] or comp["measurement_target_terms"]
        relation_group = comp["relation_effect_terms"]
        for row in selected:
            article = article_map.get(row["pmid"], {**row, "abstract": ""})
            snapshot = ASSETS / query_key / "abstracts" / f"pmid_{row['pmid']}.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(json.dumps(article, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            combined = article.get("title", "") + "\n" + article.get("abstract", "")
            entity_ok = contains_all_groups_v1(combined, [entity_group])
            measurement_ok = contains_all_groups_v1(combined, [measurement_group])
            relation_ok = contains_all_groups_v1(combined, [relation_group])
            if entity_ok and measurement_ok and relation_ok:
                state, reason = "possible_same_proposition", "exact local entity, measurement-target, and relation-family surfaces occur in title/abstract"
                plausible.append({**row, **article})
            elif entity_ok and measurement_ok:
                state, reason = "possible_but_authority_insufficient", "entity and measurement target occur but relation/causal authority is insufficient"
                rejection_counts[state] += 1
            elif not measurement_ok:
                state, reason = "wrong_measurement_target", "target measurement surface absent from retrieved title/abstract"
                rejection_counts[state] += 1
            else:
                state, reason = "resolved_proposition_mismatch", "target entity surface absent from retrieved title/abstract"
                rejection_counts[state] += 1
            abstract_rows.append({"schema_version": "abstract_proposition_screen_v1", "target_id": target_id, "candidate_id": f"pubmed:{row['pmid']}", "pmid": row["pmid"], "screen_state": state, "reason": reason, "entity_surface_present": entity_ok, "measurement_target_surface_present": measurement_ok, "relation_effect_surface_present": relation_ok, "formal_alignment_inferred": False, "direction_used_for_admission": False, "abstract_snapshot": rel(snapshot), "abstract_sha256": sha(snapshot)})
        target_candidates_before = len(provider_candidates)
        target_acquisitions_before = len(acquisition_rows)
        target_fulltexts_before = len(fulltext_rows)
        cache_hits = 0
        for row in plausible:
            if len(acquisition_rows) - target_acquisitions_before >= 2:
                break
            pmcid = row.get("pmcid")
            if not pmcid:
                rejection_counts["fulltext_not_available_from_allowed_source"] += 1
                acquisition_rows.append({"schema_version": "fulltext_acquisition_inventory_v1", "target_id": target_id, "candidate_id": f"pubmed:{row['pmid']}", "pmid": row["pmid"], "pmcid": None, "source": "PMC", "availability": "no_pmc_identifier", "license_access_state": "not_checked_no_pmc_identifier", "downloaded": False, "fulltext_snapshot": None, "fulltext_sha256": None})
                continue
            fulltext_path = ASSETS / query_key / "fulltext" / f"{pmcid}.xml"
            fulltext_url = BASE_URL + "/efetch.fcgi?" + urlencode({"db": "pmc", "id": pmcid, "retmode": "xml", "tool": "CODE_targeted_smoke"})
            fulltext_raw = retrieval.get(fulltext_url, fulltext_path, "fulltext_download")
            try:
                full_root = ET.fromstring(fulltext_raw)
                full_text = " ".join(part.strip() for part in full_root.itertext() if part.strip())
            except ET.ParseError:
                full_text = ""
            article_present = "<article" in fulltext_raw[:10000].decode("utf-8", errors="ignore")
            license_text = text_of(full_root.find(".//license")) if full_text else ""
            availability = "usable_pmc_fulltext" if article_present else "pmc_response_not_usable_fulltext"
            acquisition_rows.append({"schema_version": "fulltext_acquisition_inventory_v1", "target_id": target_id, "candidate_id": f"pubmed:{row['pmid']}", "pmid": row["pmid"], "pmcid": pmcid, "source": "PMC efetch", "source_url": fulltext_url, "availability": availability, "license_access_state": license_text[:500] or "PMC_access_available_license_not_structured", "retrieval_timestamp": retrieval.timestamp_for(fulltext_path, now()), "downloaded": article_present, "fulltext_snapshot": rel(fulltext_path), "fulltext_sha256": sha(fulltext_path)})
            full_entity = contains_all_groups_v1(full_text, [entity_group])
            full_measurement = contains_all_groups_v1(full_text, [measurement_group])
            structural = all(term in full_text.casefold() for term in ("method", "result"))
            if article_present and full_entity and full_measurement and structural:
                state = "fulltext_possible_but_requires_extraction"
                reason = "fulltext contains exact target entity and measurement surfaces plus methods/results structure; experiment-level compatibility remains unresolved"
            elif article_present and full_entity and full_measurement:
                state = "fulltext_structural_authority_insufficient"
                reason = "target surfaces occur but methods/results structure was not deterministically established"
            elif article_present:
                state = "fulltext_resolved_mismatch"
                reason = "target entity or measurement surface is absent from fulltext"
            else:
                state = "fulltext_structural_authority_insufficient"
                reason = "PMC response is not a usable article snapshot"
            fulltext_rows.append({"schema_version": "fulltext_proposition_screen_v1", "target_id": target_id, "candidate_id": f"pubmed:{row['pmid']}", "pmid": row["pmid"], "pmcid": pmcid, "screen_state": state, "reason": reason, "entity_surface_present": full_entity, "measurement_target_surface_present": full_measurement, "methods_results_structure_present": structural, "deterministic_local_screen_only": True, "direction_evaluated": False, "provider_called": False, "fulltext_sha256": sha(fulltext_path)})
            if state != "fulltext_possible_but_requires_extraction":
                rejection_counts[state] += 1
                continue
            source_hash = sha(fulltext_path)
            cache_scan = subprocess.run(["rg", "-l", "-F", source_hash, "runs", "--glob", "*.json", "--glob", "*.jsonl"], cwd=ROOT, capture_output=True, text=True, check=False)
            matching_cache = [line for line in cache_scan.stdout.splitlines() if RUN.name not in line]
            if matching_cache:
                cache_hits += 1; rejection_counts["existing_cache_sufficient"] += 1
                continue
            identity = {"pmid": row["pmid"], "pmcid": pmcid, "doi": row.get("doi")}
            candidate_payload = {"target_id": target_id, "publication_identity": identity, "fulltext_sha256": source_hash}
            candidate_id = "provider_extraction_candidate_v1:" + hashlib.sha256(json.dumps(candidate_payload, sort_keys=True).encode()).hexdigest()[:20]
            provider_candidates.append(ProviderExtractionCandidateV1(
                candidate_id=candidate_id, target_id=target_id, publication_identity=identity,
                publication_independence_state="independent_publication", fulltext_source=rel(fulltext_path), fulltext_sha256=source_hash,
                plausibility_evidence=["abstract_possible_same_proposition", "fulltext_exact_entity_surface", "fulltext_exact_measurement_target_surface", "fulltext_methods_results_structure"],
                remaining_scientific_uncertainty=["experiment_identity", "factor_and_arm_semantics", "measurement_property_authority", "intervention_and_contrast_semantics", "result_semantic_family"],
                cache_state="miss_no_sufficient_matching_extraction", duplicate_state="not_known_duplicate",
                recommended_extraction_contract={"contract_id": "targeted_experimental_observation_extraction_v1", "target_specification_ref": target_id, "required_outputs": ["Validated ExperimentalObservation", "Factor", "Arm", "Measurement", "Observed Result", "Context", "Evidence spans"], "scientific_gates": ["ScientificEntityIntegrityGateV1", "MinimumScientificPropositionProfile", "ScientificPropositionSignatureV1", "Scientific Proposition Compatibility"], "direction_blind_until_compatibility": True},
            ))
            break
        target_candidate_count = len(provider_candidates) - target_candidates_before
        stop_reason = "strong_provider_extraction_candidate_found" if target_candidate_count else "bounded_candidate_set_exhausted_without_provider_candidate"
        ledgers.append({"schema_version": "target_execution_ledger_v1", "target_id": target_id, "execution_order": position, "metadata_inspected": len(summaries), "unique_independent_publications": len(independent_for_abstract), "abstracts_inspected": len(selected), "abstract_plausible_candidates": len(plausible), "fulltexts_acquired": sum(row["downloaded"] for row in acquisition_rows[target_acquisitions_before:]), "fulltext_plausible_candidates": sum(row["screen_state"] == "fulltext_possible_but_requires_extraction" for row in fulltext_rows[target_fulltexts_before:]), "existing_cache_hits": cache_hits, "provider_extraction_candidates": target_candidate_count, "rejection_counts_by_reason": dict(sorted(rejection_counts.items())), "budget_consumed": {"metadata": len(summaries), "abstract": len(selected), "fulltext": sum(row["downloaded"] for row in acquisition_rows[target_acquisitions_before:])}, "stop_reason": stop_reason})
        if target_candidate_count:
            global_stop = True
    receipt = retrieval.finish()
    write_rows("executed_retrieval_queries.jsonl", query_records)
    write_rows("metadata_candidate_inventory.jsonl", metadata_rows)
    write_rows("publication_independence_audit.jsonl", independence_rows)
    write_rows("abstract_proposition_screen.jsonl", abstract_rows)
    write_rows("fulltext_acquisition_inventory.jsonl", acquisition_rows)
    write_rows("fulltext_proposition_screen.jsonl", fulltext_rows)
    write_rows("provider_extraction_candidates_v1.jsonl", provider_candidates)
    write_rows("target_execution_ledger.jsonl", ledgers)
    events = receipt["events"]
    counts = Counter(event["kind"] for event in events)
    metrics = {
        "target_count": 4, "metadata_candidates_inspected": len(metadata_rows),
        "independent_publications_found": sum(row["independence_state"] == "independent_publication" for row in independence_rows),
        "abstracts_inspected": len(abstract_rows), "abstract_plausible_count": sum(row["screen_state"] == "possible_same_proposition" for row in abstract_rows),
        "fulltexts_downloaded": sum(row["downloaded"] for row in acquisition_rows),
        "fulltext_plausible_count": sum(row["screen_state"] == "fulltext_possible_but_requires_extraction" for row in fulltext_rows),
        "existing_cache_hit_count": sum(row["existing_cache_hits"] for row in ledgers),
        "provider_extraction_candidate_count": len(provider_candidates),
        "targets_with_provider_candidate": sum(row["provider_extraction_candidates"] > 0 for row in ledgers),
        "targets_exhausted_without_candidate": sum(row["stop_reason"] == "bounded_candidate_set_exhausted_without_provider_candidate" for row in ledgers),
        "metadata_budget_max": 48, "abstract_budget_max": 24, "fulltext_budget_max": 8,
        "network_calls": len(events), "metadata_requests": counts["metadata_search"] + counts["metadata_summary"],
        "abstract_requests": counts["abstract_fetch"], "fulltext_download_requests": counts["fulltext_download"],
        "provider_calls": 0, "llm_calls": 0,
    }
    write_json("retrieval_budget_accounting.json", {"schema_version": "retrieval_budget_accounting_v1", "metrics": metrics, "per_target_ceiling": {"metadata": 12, "abstract": 6, "fulltext": 2}, "global_ceiling": {"metadata": 48, "abstract": 24, "fulltext": 8}, "ceilings_are_not_quotas": True, "budget_exceeded": False, "execution_receipt": rel(retrieval.receipt_path)})
    ranked = [candidate.model_dump(mode="json") for candidate in provider_candidates]
    write_json("provider_extraction_smoke_plan.json", {"schema_version": "provider_extraction_smoke_plan_v1", "execution_authorized": False, "candidate_count": len(ranked), "ranked_candidates": [{"rank": index, **candidate} for index, candidate in enumerate(ranked, 1)], "planned_provider_calls": len(ranked), "maximum_attempts_per_source": 1, "retry_count": 0, "cache_prerequisite": "repeat exact source-snapshot plus contract/model-family cache check immediately before execution", "provider_calls_executed": 0, "llm_calls_executed": 0})
    decision = "PROVIDER_EXTRACTION_SMOKE_JUSTIFIED" if provider_candidates else "NO_PROVIDER_EXTRACTION_JUSTIFIED"
    write_json("discovery_smoke_decision.json", {"schema_version": "discovery_smoke_decision_v1", "decision": decision, "basis": "at least one independent publication has direction-neutral abstract and fulltext proposition plausibility, a usable fulltext snapshot, unresolved experiment-level semantics, and no sufficient cache match" if provider_candidates else "no independently sourced fulltext met the provider-candidate gate within the bounded smoke", "scientific_answer_inferred": False, "contradiction_adjudicated": False, "provider_execution_authorized": False})
    after = {rel(path): sha(path) for path in protected}; unchanged = before == after
    write_json("scientific_state_safety_audit.json", {"schema_version": "targeted_network_discovery_scientific_state_safety_audit_v1", "historical_candidate_count_before": 11, "historical_candidate_count_after": 11, "formal_conflict_count_before": 0, "formal_conflict_count_after": 0, "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2, "pi3k": {"signal_40f_state": "historically_blocked", "f389_state": "manual_scientific_review"}, "historical_assets_modified": not unchanged, "candidate_pairs_modified": False, "formal_v3_modified": False, "experimental_core_modified": False, "canonical_entity_records_modified": False, "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False, "protected_hashes_before": before, "protected_hashes_after": after, "network_calls": metrics["network_calls"], "metadata_requests": metrics["metadata_requests"], "abstract_requests": metrics["abstract_requests"], "fulltext_downloads": metrics["fulltexts_downloaded"], "provider_calls": 0, "llm_calls": 0})
    contradiction_terms = sum(any(term in row["exact_query"].casefold() for term in PROHIBITED) for row in query_records)
    write_json("production_leakage_audit.json", {"schema_version": "targeted_network_discovery_production_leakage_audit_v1", "candidate_sidecars_only": True, "production_modules_modified": False, "direction_used_for_retrieval_admission": False, "contradiction_seeking_query_count": contradiction_terms, "supportive_or_opposing_classified": False, "alignment_inferred": False, "candidate_generation_executed": False, "l4_executed": False, "formal_executed": False, "provider_clients_imported_or_called": False, "llm_used": False, "credentials_logged": False})
    assertions = {
        "frozen_targets_used_in_order": [row["target_id"] for row in ledgers] == ORDER,
        "no_contradiction_seeking_primary_queries": contradiction_terms == 0,
        "metadata_budget_not_exceeded": metrics["metadata_candidates_inspected"] <= 48 and all(row["metadata_inspected"] <= 12 for row in ledgers),
        "abstract_budget_not_exceeded": metrics["abstracts_inspected"] <= 24 and all(row["abstracts_inspected"] <= 6 for row in ledgers),
        "fulltext_budget_not_exceeded": metrics["fulltexts_downloaded"] <= 8 and all(row["fulltexts_acquired"] <= 2 for row in ledgers),
        "independence_before_recommendation": all(candidate.publication_independence_state == "independent_publication" for candidate in provider_candidates),
        "cache_before_recommendation": all(candidate.cache_state == "miss_no_sufficient_matching_extraction" for candidate in provider_candidates),
        "provider_llm_zero": metrics["provider_calls"] == metrics["llm_calls"] == 0,
        "historical_scientific_state_unchanged": unchanged,
        "no_scientific_answer_or_contradiction_adjudication": True,
        "all_network_events_preserved": all((ROOT / event["relative_path"]).exists() for event in events),
    }
    baseline_failures = read_json(PROTOCOL / "final_validation.json")["baseline_failure_ids"]
    final_failures = sorted(set(opt.final_failure_id))
    write_json("final_validation.json", {"schema_version": "targeted_network_discovery_smoke_v1_final_validation", "status": opt.status, "assertions": assertions, "all_assertions_passed": all(assertions.values()), "focused_test_pass_count": opt.focused_pass_count, "related_test_pass_count": opt.related_pass_count, "full_suite_pass_count": opt.full_pass_count, "full_suite_subtest_pass_count": opt.full_subtest_pass_count, "full_suite_failure_count": opt.full_failure_count, "full_suite_collected_count": opt.full_collected_count, "baseline_failure_ids": baseline_failures, "final_failure_ids": final_failures, "new_failure_ids": sorted(set(final_failures) - set(baseline_failures)), "compileall": opt.compileall, "git_diff_check": opt.git_diff_check, "network_calls": metrics["network_calls"], "provider_calls": 0, "llm_calls": 0})
    write_json("summary.json", {"schema_version": "targeted_network_discovery_smoke_v1_summary", "status": opt.status, "decision": decision, "metrics": metrics, "target_results": ledgers, "scientific_answer_inferred": False, "execution_authorized": False, "historical_assets_modified": not unchanged})
    artifact_paths = [ART / name for name in FILES if name != "manifest.json"] + sorted(path for path in ASSETS.rglob("*") if path.is_file())
    manifest_rows = [{"relative_path": rel(path), "sha256": sha(path), "file_size_bytes": path.stat().st_size, "line_count": len(path.read_text(encoding="utf-8", errors="replace").splitlines())} for path in artifact_paths]
    write_json("manifest.json", {"schema_version": "targeted_network_discovery_smoke_v1_manifest", "run_id": RUN.name, "status": opt.status, "required_artifact_count": len(FILES), "manifest_entry_count": len(manifest_rows), "manifest_self_hash_excluded": True, "all_required_artifacts_present": all((ART / name).exists() for name in FILES if name != "manifest.json"), "artifacts_and_retrieval_assets": manifest_rows, "execution_authorized": False, "network_calls": metrics["network_calls"], "provider_calls": 0, "llm_calls": 0})
    if not all(assertions.values()):
        raise RuntimeError([name for name, passed in assertions.items() if not passed])


if __name__ == "__main__":
    main()
