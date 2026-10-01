#!/usr/bin/env python3
"""Execute frozen alpha3.19C PubMed-only metadata and pre-OA eligibility."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as frozen_rules
from scripts import run_search_plan_v24_alpha319b_dedup_seen_sampling_offline as b
from scripts import search_plan_v24_alpha318a3_correction_reference as correction
from scripts import search_plan_v24_alpha318a1_source_contracts as source_policy


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19c_pubmed_metadata_eligibility"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19c_sha256"
B_SHA = "7b409cd2bf35b01f7d511717cafa7f030ca0a0b351ec41a6a7e75cd31f5aa1f8"
PREREG_SHA = "d65e7b2ed58e855201e12fc31cf100f14d9e37bc91a0dafeb21183418f7cd132"
MANIFEST_SHA = "103199b656d10fbd850d3e0ebbdf3329685ec8438f4c5df0752afc1748733899"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFERRED_UPDATEOF = "DEFERRED_TO_STRUCTURE_STAGE"


def require(ok: bool, code: str):
    if not ok:
        raise RuntimeError(code)


def load(path: Path):
    return json.loads(path.read_bytes())


def rows(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def write_json(name: str, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, values):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        for value in values:
            handle.write(master.canonical(value) + b"\n")


def append_jsonl(name: str, value):
    with (OUT / name).open("ab") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_bytes(name: str, value: bytes):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def root_hash():
    paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "OUTPUT_SYMLINK_FORBIDDEN")
    return master.sha(master.canonical([[str(path.relative_to(OUT)), master.digest(path)]
                                      for path in paths]))


def children(node: ET.Element, tag: str):
    return [child for child in node if source_policy.local(child.tag) == tag]


def node_text(node: ET.Element):
    return source_policy.node_text(node)


def parse_metadata(raw: bytes, expected_pmid: str):
    """Bind current citation by direct paths; never traverse ReferenceList IDs."""
    root = ET.fromstring(raw)
    articles = ([root] if source_policy.local(root.tag) == "PubmedArticle" else
                children(root, "PubmedArticle"))
    if len(articles) != 1:
        raise ValueError("PUBMED_ARTICLE_COUNT_NOT_ONE")
    article = articles[0]
    citations = children(article, "MedlineCitation")
    if len(citations) != 1:
        raise ValueError("MEDLINE_CITATION_COUNT_NOT_ONE")
    citation = citations[0]
    pmids = [node_text(node) for node in children(citation, "PMID")]
    if pmids != [expected_pmid]:
        raise ValueError("PRIMARY_CITATION_PMID_MISSING_OR_MISMATCH")
    article_nodes = children(citation, "Article")
    if len(article_nodes) != 1:
        raise ValueError("CITATION_ARTICLE_COUNT_NOT_ONE")
    pubmed_data = children(article, "PubmedData")
    if len(pubmed_data) > 1:
        raise ValueError("PUBMEDDATA_DUPLICATE")
    id_lists = children(pubmed_data[0], "ArticleIdList") if pubmed_data else []
    if len(id_lists) > 1:
        raise ValueError("DIRECT_ARTICLE_ID_LIST_DUPLICATE")
    direct_ids = ([{"id_type": node.get("IdType", ""), "value": node_text(node)}
                   for node in children(id_lists[0], "ArticleId")] if id_lists else [])
    direct_pubmed = sorted({row["value"] for row in direct_ids if row["id_type"] == "pubmed"})
    if direct_pubmed and direct_pubmed != [expected_pmid]:
        raise ValueError("DIRECT_PUBMED_ID_MISMATCH")
    pmcids = sorted({row["value"] for row in direct_ids if row["id_type"] == "pmc"})
    dois = sorted({row["value"] for row in direct_ids if row["id_type"] == "doi"})
    pmcid = pmcids[0] if len(pmcids) == 1 and re.fullmatch(r"PMC[1-9][0-9]*", pmcids[0]) else None
    doi = dois[0] if len(dois) == 1 else None
    year, date_raw_state = frozen_rules.frozen_date_year(raw, expected_pmid)
    date_state = {"ELIGIBLE": "CLEAR", "INELIGIBLE": "INELIGIBLE",
                  "UNRESOLVED": "UNRESOLVED"}[date_raw_state]
    type_lists = children(article_nodes[0], "PublicationTypeList")
    types = [node_text(entry) for group in type_lists
             for entry in children(group, "PublicationType")]
    refs = []
    for group in children(citation, "CommentsCorrectionsList"):
        for entry in children(group, "CommentsCorrections"):
            linked_pmids = children(entry, "PMID")
            sources = children(entry, "RefSource")
            refs.append({"ref_type": entry.get("RefType", ""),
                         "linked_pmid": node_text(linked_pmids[0]) if linked_pmids else None,
                         "ref_source": node_text(sources[0]) if sources else None})
    unresolved = []
    if pmcid is None:
        unresolved.append("PMCID_MISSING_OR_AMBIGUOUS")
    if len(dois) > 1:
        unresolved.append("DOI_AMBIGUOUS")
    return {"pmid": expected_pmid, "pmcid": pmcid, "doi": doi,
            "publication_year": year, "date_state": date_state,
            "publication_types": types, "correction_relationships": refs,
            "direct_primary_article_ids": direct_ids,
            "direct_pubmed_ids": direct_pubmed,
            "metadata_state": "RESOLVED" if not unresolved else "UNRESOLVED",
            "metadata_unresolved_reasons": unresolved,
            "reference_article_ids_scanned": False}


def preflight():
    require(not OUT.exists(), "ALPHA319C_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(b.root_hash() == B_SHA and (b.OUT / b.ROOT_MARKER).read_text().strip() == B_SHA,
            "ALPHA319B_ROOT_MISMATCH")
    sample_path = b.OUT / "sampled_source_manifest.jsonl"
    sample = rows(sample_path)
    sample_audit = load(b.OUT / "sampling_execution_audit.json")
    require(len(sample) == len({row["pmid"] for row in sample}) == 72 and
            sample_audit["sampled_source_manifest_sha256"] == master.digest(sample_path) and
            all(isinstance(row["pmid"], str) and re.fullmatch(r"[1-9][0-9]*", row["pmid"])
                and row["seen_source_match"] is False for row in sample),
            "FROZEN_SAMPLE_IDENTITY_MISMATCH")
    require(prereg.frozen_root(prereg.OUT, "search_plan_v24_dev_alpha3_19a_prereg_sha256") == PREREG_SHA and
            master.digest(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json") == MANIFEST_SHA,
            "FROZEN_PREREG_OR_MANIFEST_MISMATCH")
    manifest = load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")
    for field in ("sampled_metadata_execution", "primary_citation_execution", "date_rule",
                  "publication_type_rule", "correction_rule", "historical_contamination_gate",
                  "metadata_barrier", "pre_oa_manifest"):
        prereg.check_ref(manifest[field])
    metadata = load(ROOT / manifest["sampled_metadata_execution"]["path"])
    identity = load(ROOT / manifest["primary_citation_execution"]["path"])
    correction_rule = load(ROOT / manifest["correction_rule"]["path"])
    pre_oa_rule = load(ROOT / manifest["pre_oa_manifest"]["path"])
    transport = load(ROOT / metadata["transport_policy"]["path"])
    for binding in (metadata["metadata_policy"], metadata["transport_policy"],
                    identity["contract"], identity["article_id_scope"],
                    correction_rule["contract"], correction_rule["pipeline"]):
        prereg.check_ref(binding)
    require(metadata["route"] == {"db": "pubmed", "endpoint": EFETCH,
                                  "id": "frozen sampled canonical PMID", "method": "GET",
                                  "retmode": "xml"} and
            identity["canonical_path"] == "PubmedArticle/MedlineCitation/PMID" and
            identity["matching_records_required"] == 1 and
            identity["ReferenceList_identity_contribution"] is False and
            correction_rule["rules_changed"] is False and
            pre_oa_rule["conditional_UpdateOf_final_source_admission"] is False and
            pre_oa_rule["clear_or_conditional_UpdateOf_only"] is True and
            transport["maximum_attempts_per_request"] == 4 and
            transport["timeout_seconds"] == 60 and
            transport["backoff_seconds"] == [2, 4, 8] and
            manifest["technical_retry_failure"]["terminal_metadata_or_jats_source"] ==
                "RECORD_EXCLUDE_NO_REPLACEMENT" and
            manifest["sampling_seed"]["sha256"] ==
                master.digest(master.OUT / "alpha3_19_sampling_seed_contract.json"),
            "FROZEN_METADATA_POLICY_MISMATCH")
    accepted = load(master.A1 / "publication_type_acceptance_set.json")
    excluded = load(master.A1 / "publication_type_exclusion_set.json")
    require(master.digest(master.A1 / "publication_type_acceptance_set.json") ==
            load(ROOT / manifest["publication_type_rule"]["path"])["accepted_vocabulary"]["sha256"] and
            master.digest(master.A1 / "publication_type_exclusion_set.json") ==
            load(ROOT / manifest["publication_type_rule"]["path"])["excluded_vocabulary"]["sha256"],
            "PUBLICATION_TYPE_VOCABULARY_MISMATCH")
    return sample, transport, accepted, excluded


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")


class PubMedTransport:
    def __init__(self, policy):
        self.policy = policy
        self.opener = urllib.request.build_opener(NoRedirect)
        self.last_started = 0.0
        self.calls = 0
        self.attempts = []

    def fetch(self, ordinal: int, pmid: str):
        params = {"db": "pubmed", "retmode": "xml", "id": pmid}
        require(EFETCH == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                "NETWORK_SCOPE_VIOLATION")
        url = EFETCH + "?" + urllib.parse.urlencode(params)
        history = []
        for number in range(1, self.policy["maximum_attempts_per_request"] + 1):
            delay = max(0.0, 0.38 - (time.monotonic() - self.last_started))
            if delay:
                time.sleep(delay)
            self.last_started = time.monotonic()
            self.calls += 1
            status = None
            raw = b""
            error = None
            started = datetime.now(timezone.utc).isoformat()
            request = urllib.request.Request(url, headers={
                "User-Agent": "conflict-oriented-discovery-engine-alpha319c/1.0"})
            try:
                with self.opener.open(request, timeout=self.policy["timeout_seconds"]) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                error = type(exc).__name__
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
            raw_path = f"sampled_metadata_raw_responses/{ordinal:03d}_{pmid}_attempt{number}.bin"
            write_bytes(raw_path, raw)
            record = {"sample_ordinal": ordinal, "pmid": pmid, "attempt": number,
                      "method": "GET", "endpoint": EFETCH, "parameters": params,
                      "url": url, "timestamp_utc": started, "http_status": status,
                      "transport_error": error, "raw_path": raw_path,
                      "raw_sha256": master.sha(raw), "raw_bytes": len(raw)}
            self.attempts.append(record)
            history.append(record)
            with (OUT / "sampled_metadata_request_attempts.jsonl").open("ab") as handle:
                handle.write(master.canonical(record) + b"\n")
            if status == 200 and error is None:
                return raw, history
            retryable = status is None or status in self.policy["http_status_retryable"]
            if not retryable or number == self.policy["maximum_attempts_per_request"]:
                break
            time.sleep(self.policy["backoff_seconds"][number - 1])
        return None, history


def run(sample, transport, accepted, excluded):
    requests = [{"sample_ordinal": i, "pmid": row["pmid"], "endpoint": EFETCH,
                 "parameters": {"db": "pubmed", "retmode": "xml", "id": row["pmid"]}}
                for i, row in enumerate(sample, 1)]
    write_jsonl("sampled_metadata_request_manifest.jsonl", requests)
    metadata_records = []
    integrity_rows = []
    pre_oa = []
    for request in requests:
        ordinal, pmid = request["sample_ordinal"], request["pmid"]
        raw, attempts = transport.fetch(ordinal, pmid)
        parsed = None
        error = None
        if raw is None:
            error = "TERMINAL_METADATA_TRANSPORT_FAILURE"
        else:
            try:
                parsed = parse_metadata(raw, pmid)
            except (ValueError, ET.ParseError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
        if parsed is None:
            date_state = "UNRESOLVED"
            type_result = {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "METADATA_UNAVAILABLE"}
            correction_result = {"schema_version": correction.SCHEMA_VERSION,
                "state": "CORRECTION_REFERENCE_UNRESOLVED",
                "unresolved_reasons": ["METADATA_UNAVAILABLE"], "ineligible_reasons": []}
            metadata_state = "SOURCE_FAILED_CLOSED"
            deferred = False
        else:
            date_state = parsed["date_state"]
            type_result = frozen_rules.publication_type_state(
                parsed["publication_types"], accepted, excluded)
            correction_result = correction.classify(
                parsed["publication_types"], parsed["correction_relationships"])
            metadata_state = parsed["metadata_state"]
            deferred = (correction_result["state"] == "CORRECTION_REFERENCE_UNRESOLVED" and
                        correction_result["unresolved_reasons"] ==
                        ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"])
        type_state = {"PRELIMINARY_TYPE_ACCEPTED": "CLEAR",
                      "SOURCE_TYPE_INELIGIBLE": "INELIGIBLE",
                      "SOURCE_TYPE_UNRESOLVED": "UNRESOLVED"}[type_result["state"]]
        correction_state = correction_result["state"].removeprefix("CORRECTION_REFERENCE_")
        admissible = (parsed is not None and metadata_state == "RESOLVED" and
                      date_state == "CLEAR" and type_state == "CLEAR" and
                      (correction_state == "CLEAR" or deferred))
        eligibility = ("PRE_OA_CONDITIONAL_UPDATEOF" if admissible and deferred else
                       "PRE_OA_CLEAR" if admissible else "BLOCKED")
        record = {"sample_ordinal": ordinal, "pmid": pmid,
                  "metadata_state": metadata_state, "metadata_error": error,
                  "raw_xml_sha256": master.sha(raw) if raw is not None else None,
                  "raw_xml_path": attempts[-1]["raw_path"] if raw is not None else None,
                  "request_attempts": attempts,
                  "pmcid": parsed["pmcid"] if parsed else None,
                  "doi": parsed["doi"] if parsed else None,
                  "publication_year": parsed["publication_year"] if parsed else None,
                  "date_state": date_state,
                  "publication_types": parsed["publication_types"] if parsed else [],
                  "publication_type_state": type_state,
                  "publication_type_reason": type_result["reason"],
                  "correction_relationships": parsed["correction_relationships"] if parsed else [],
                  "correction_reference_state": correction_state,
                  "correction_ineligible_reasons": correction_result["ineligible_reasons"],
                  "correction_unresolved_reasons": correction_result["unresolved_reasons"],
                  "updateof_deferred_state": DEFERRED_UPDATEOF if deferred else None,
                  "metadata_eligibility_state": eligibility,
                  "identity_unresolved_reasons": parsed["metadata_unresolved_reasons"] if parsed else [],
                  "direct_primary_article_ids": parsed["direct_primary_article_ids"] if parsed else [],
                  "reference_article_ids_scanned": False}
        metadata_records.append(record)
        append_jsonl("sampled_metadata_records_v3.jsonl", record)
        integrity = {"sample_ordinal": ordinal, "pmid": pmid,
                               "date_state": date_state, "publication_type_state": type_state,
                               "correction_reference_state": correction_state,
                               "updateof_deferred": deferred, "metadata_eligibility_state": eligibility}
        integrity_rows.append(integrity)
        append_jsonl("publication_integrity_results_v3.jsonl", integrity)
        if admissible:
            pre_oa.append({"sample_ordinal": ordinal, "pmid": pmid,
                           "pmcid": parsed["pmcid"], "doi": parsed["doi"],
                           "raw_metadata_sha256": master.sha(raw),
                           "correction_reference_preliminary_state": correction_result["state"],
                           "updateof_deferred_to_structure_stage": deferred})
        if ordinal % 12 == 0:
            print(json.dumps({"stage": "pubmed_metadata", "completed": ordinal,
                              "total": len(requests)}, sort_keys=True), flush=True)
    write_jsonl("post_metadata_pre_oa_source_manifest_v3.jsonl", pre_oa)
    return metadata_records, integrity_rows, pre_oa


def finalize(status, sample, records, integrity, pre_oa, transport, failure=None):
    parsed = sum(row["metadata_state"] in {"RESOLVED", "UNRESOLVED"} for row in records)
    fetched = sum(row["raw_xml_sha256"] is not None for row in records)
    deferred_count = sum(row["updateof_deferred_state"] is not None for row in records)
    failed_sources = [row["pmid"] for row in records if row["metadata_state"] == "SOURCE_FAILED_CLOSED"]
    write_json("primary_identity_audit.json", {
        "sampled_count": len(sample), "records_processed": len(records),
        "primary_citation_direct_path_only": True, "reference_article_ids_scanned": False,
        "direct_pubmeddata_article_id_list_only": True,
        "parsed_identity_count": parsed, "source_failed_identity_or_transport_pmids": failed_sources})
    write_json("publication_integrity_audit.json", {
        "date_clear_count": sum(row["date_state"] == "CLEAR" for row in integrity),
        "publication_type_clear_count": sum(row["publication_type_state"] == "CLEAR" for row in integrity),
        "terminal_state_count": len(integrity),
        "publication_type_source": "PubMed PublicationTypeList only",
        "publication_date_cohort": ["2024-01-01", "2025-12-31"]})
    write_json("correction_reference_audit.json", {
        "correction_clear_count": sum(row["correction_reference_state"] == "CLEAR" for row in integrity),
        "correction_ineligible_count": sum(row["correction_reference_state"] == "INELIGIBLE" for row in integrity),
        "correction_unresolved_count": sum(row["correction_reference_state"] == "UNRESOLVED" for row in integrity),
        "updateof_deferred_count": deferred_count,
        "updateof_conditional_pre_oa_count": sum(row["updateof_deferred_to_structure_stage"] for row in pre_oa),
        "precedence": ["INELIGIBLE", "UNRESOLVED", "CLEAR"],
        "final_updateof_source_admission_decided": False})
    write_json("validation.json", {
        "status": status, "alpha3_19b_root_verified": True,
        "sample_count_unchanged": len(sample) == 72,
        "all_sampled_sources_have_terminal_metadata_states": len(records) == len(sample),
        "all_raw_attempts_frozen": len(transport.attempts) == transport.calls and all(
            master.digest(OUT / row["raw_path"]) == row["raw_sha256"]
            for row in transport.attempts),
        "network_scope_pubmed_efetch_only": all(row["endpoint"] == EFETCH and
            row["parameters"]["db"] == "pubmed" for row in transport.attempts),
        "pmc_requests": 0, "oa_verification_executed": False,
        "source_queries_changed": False, "sampling_seed_changed": False,
        "sample_changed": False, "scientific_policy_changed": False,
        "model_calls": 0, "source_replacement_count": 0,
        "failure": failure})
    write_json("summary.json", {
        "status": status, "source_root_sha256": B_SHA,
        "sampled_count": len(sample), "metadata_fetch_success_count": fetched,
        "metadata_success_count": parsed, "metadata_source_failure_count": len(failed_sources),
        "date_clear_count": sum(row["date_state"] == "CLEAR" for row in integrity),
        "publication_type_clear_count": sum(row["publication_type_state"] == "CLEAR" for row in integrity),
        "correction_clear_count": sum(row["correction_reference_state"] == "CLEAR" for row in integrity),
        "updateof_deferred_count": deferred_count,
        "pre_oa_source_count": len(pre_oa),
        "ncbi_pubmed_efetch_attempts": transport.calls, "pmc_requests": 0,
        "network_calls_non_ncbi": 0, "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "source_replacement_count": 0,
        "scientific_policy_changed": False,
        "next_stage": "AUTHORIZE_ALPHA3_19D_OA_JATS_EXECUTION" if status == "completed"
                      else "AUDIT_ALPHA3_19C_RUNTIME_FAILURE_OFFLINE",
        "failure": failure})
    (OUT / ROOT_MARKER).write_text(root_hash() + "\n")
    print(json.dumps({"status": status, "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
                      "sampled_count": len(sample), "metadata_success_count": parsed,
                      "pre_oa_source_count": len(pre_oa), "ncbi_attempts": transport.calls,
                      "failure": failure}, sort_keys=True), flush=True)


def main():
    sample, policy, accepted, excluded = preflight()
    OUT.mkdir()
    write_json("pre_network_integrity_verification.json", {
        "alpha3_19b_root_sha256": B_SHA, "sampled_source_manifest_sha256":
            master.digest(b.OUT / "sampled_source_manifest.jsonl"),
        "sampled_count": len(sample), "frozen_prereg_sha256": PREREG_SHA,
        "frozen_manifest_sha256": MANIFEST_SHA,
        "updateof_deferred_contract_preserved": True,
        "per_source_metadata_failure_isolated": True})
    transport = PubMedTransport(policy)
    try:
        records, integrity, pre_oa = run(sample, transport, accepted, excluded)
    except Exception as exc:
        records = rows(OUT / "sampled_metadata_records_v3.jsonl") if (
            OUT / "sampled_metadata_records_v3.jsonl").exists() else []
        integrity = rows(OUT / "publication_integrity_results_v3.jsonl") if (
            OUT / "publication_integrity_results_v3.jsonl").exists() else []
        finalize("failed_closed", sample, records, integrity, [], transport,
                 type(exc).__name__ + ":" + str(exc))
        return
    finalize("completed", sample, records, integrity, pre_oa, transport)


if __name__ == "__main__":
    main()
