#!/usr/bin/env python3
"""Frozen alpha3.19D: PMC OA/JATS acquisition and mechanical eligibility only."""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha318a4_esearch_response_validity as esearch_v2
from scripts import search_plan_v24_alpha318a6_license_extraction as license_v2
from scripts import search_plan_v24_alpha318a1_source_contracts as source_policy
from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as frozen_rules
from scripts import run_search_plan_v24_alpha319c_pubmed_metadata_eligibility as c


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19d_sha256"
C_SHA = "922cc952e03bca7e8605971b9dcb6f4acfe3cfbe02e308ca26c9ab37c3a86689"
MANIFEST_SHA = "103199b656d10fbd850d3e0ebbdf3329685ec8438f4c5df0752afc1748733899"
ES = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EF = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


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


def preflight():
    require(not OUT.exists(), "ALPHA319D_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    require(c.root_hash() == C_SHA and (c.OUT / c.ROOT_MARKER).read_text().strip() == C_SHA,
            "ALPHA319C_ROOT_MISMATCH")
    summary = load(c.OUT / "summary.json")
    validation = load(c.OUT / "validation.json")
    pre_oa_path = c.OUT / "post_metadata_pre_oa_source_manifest_v3.jsonl"
    pre_oa = rows(pre_oa_path)
    metadata = rows(c.OUT / "sampled_metadata_records_v3.jsonl")
    by_pmid = {row["pmid"]: row for row in metadata}
    require(summary["status"] == validation["status"] == "completed" and
            summary["sampled_count"] == 72 and summary["pre_oa_source_count"] == 42 and
            len(pre_oa) == len({row["pmid"] for row in pre_oa}) == 42 and
            len(metadata) == len(by_pmid) == 72 and
            sum(row["updateof_deferred_to_structure_stage"] for row in pre_oa) == 2 and
            validation["sample_changed"] is False and
            validation["scientific_policy_changed"] is False,
            "ALPHA319C_HANDOFF_STATE_MISMATCH")
    for row in pre_oa:
        pmid = row["pmid"]
        source = by_pmid[pmid]
        require(re.fullmatch(r"[1-9][0-9]*", pmid) and
                re.fullmatch(r"PMC[1-9][0-9]*", row["pmcid"]) and
                row["pmcid"] == source["pmcid"] and
                row["raw_metadata_sha256"] == source["raw_xml_sha256"] ==
                    master.digest(c.OUT / source["raw_xml_path"]) and
                source["metadata_eligibility_state"] in
                    {"PRE_OA_CLEAR", "PRE_OA_CONDITIONAL_UPDATEOF"} and
                row["updateof_deferred_to_structure_stage"] ==
                    (source["metadata_eligibility_state"] == "PRE_OA_CONDITIONAL_UPDATEOF") and
                source["date_state"] == source["publication_type_state"] == "CLEAR" and
                source["correction_reference_state"] in {"CLEAR", "UNRESOLVED"},
                "ALPHA319C_SOURCE_IDENTITY_OR_GATE_MISMATCH")
    manifest_path = prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json"
    require(master.digest(manifest_path) == MANIFEST_SHA, "FROZEN_MANIFEST_MISMATCH")
    manifest = load(manifest_path)
    for field in ("oa_subset_route", "jats_route", "jats_handoff", "license_extraction",
                  "source_type_v1"):
        if field in manifest:
            prereg.check_ref(manifest[field])
    for field in ("oa_subset_route", "jats_route", "jats_handoff"):
        prereg.check_ref(manifest[field])
    oa = load(ROOT / manifest["oa_subset_route"]["path"])
    jats = load(ROOT / manifest["jats_route"]["path"])
    handoff = load(ROOT / manifest["jats_handoff"]["path"])
    for binding in (oa["source_contract"], jats["acquisition_policy"],
                    jats["failure_policy"], handoff["handoff_contracts"]["future_license_extraction"],
                    handoff["handoff_contracts"]["future_source_type"]):
        prereg.check_ref(binding)
    license_contract = load(ROOT / handoff["handoff_contracts"]["future_license_extraction"]["path"])
    source_type_contract = load(ROOT / handoff["handoff_contracts"]["future_source_type"]["path"])
    jats_failure = load(ROOT / jats["failure_policy"]["path"])
    construction_oa_contract_path = ROOT / (
        "runs/20261001_search_plan_v24_dev_alpha3_18a6_license_extraction_v2_offline_replay/"
        "construction_oa_eligibility_v2.json")
    require(oa["endpoint"] == ES and oa["db"] == "pmc" and oa["PMCID_alone_sufficient"] is False and
            oa["retmax"] == 1 and oa["retmode"] == "json" and
            jats["route"]["endpoint"] == EF and jats["route"]["db"] == "pmc" and
            jats["route"]["retmode"] == "xml" and
            jats["technical_max_attempts"] == 4 and jats["timeout_seconds"] == 60 and
            jats["backoff_seconds"] == [2, 4, 8] and
            jats["terminal_failure"] == "RECORD_NO_REPLACEMENT" and
            jats_failure["attempts_max"] == 4 and
            jats_failure["timeout_seconds"] == 60 and
            jats_failure["backoff_seconds"] == [2, 4, 8] and
            jats_failure["retryable_status"] == [408, 429, 500, 502, 503, 504] and
            license_contract["schema_version"] == "ConstructionLicenseExtractionV2" and
            source_type_contract["schema_version"] == "SourceTypeMechanicalEligibilityV1" and
            handoff["construction_document_generated"] is False and
            master.digest(construction_oa_contract_path) ==
                "81003710ce39ca351c1f9cf3dba23ceb18849b94828e46776b17f10e8d530d17" and
            master.digest(ROOT / license_contract["parser"]["path"]) ==
                license_contract["parser"]["sha256"] and
            master.digest(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py") ==
                "88c4370ebe45c157f9501ea1c7e6350f0348d67a15463254be68d8c315546c5e",
            "FROZEN_OA_JATS_LICENSE_SOURCE_TYPE_POLICY_MISMATCH")
    return pre_oa, by_pmid, oa, jats, handoff


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")


class PMCTransport:
    def __init__(self, attempts_max=4, timeout=60, backoff=(2, 4, 8)):
        self.opener = urllib.request.build_opener(NoRedirect)
        self.attempts_max = attempts_max
        self.timeout = timeout
        self.backoff = backoff
        self.last_started = 0.0
        self.attempts = []
        self.calls = 0

    def fetch(self, stage: str, ordinal: int, pmid: str, endpoint: str,
              parameters: dict[str, str], raw_dir: str):
        require(endpoint in {ES, EF} and parameters["db"] == "pmc" and
                urllib.parse.urlsplit(endpoint).hostname == "eutils.ncbi.nlm.nih.gov",
                "NETWORK_SCOPE_VIOLATION")
        url = endpoint + "?" + urllib.parse.urlencode(parameters)
        history = []
        for number in range(1, self.attempts_max + 1):
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
                "User-Agent": "conflict-oriented-discovery-engine-alpha319d/1.0"})
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                error = type(exc).__name__
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
            raw_path = f"{raw_dir}/{ordinal:03d}_{pmid}_attempt{number}.bin"
            write_bytes(raw_path, raw)
            entry = {"stage": stage, "ordinal": ordinal, "pmid": pmid, "attempt": number,
                     "method": "GET", "endpoint": endpoint, "parameters": parameters,
                     "url": url, "timestamp_utc": started, "http_status": status,
                     "transport_error": error, "raw_path": raw_path,
                     "raw_sha256": master.sha(raw), "raw_bytes": len(raw)}
            self.attempts.append(entry)
            history.append(entry)
            append_jsonl("pmc_request_attempts.jsonl", entry)
            if status == 200 and error is None:
                return raw, history
            retryable = status is None or status in {408, 429, 500, 502, 503, 504}
            if not retryable or number == self.attempts_max:
                break
            time.sleep(self.backoff[number - 1])
        return None, history


def oa_subset_state(raw: bytes | None, attempts: list[dict], pmcid: str):
    verdict = esearch_v2.validate_response(
        attempts[-1]["http_status"] if raw is not None else None, raw or b"", 0, 1)
    if verdict["state"] not in esearch_v2.VALID_STATES:
        return "OA_SUBSET_UNRESOLVED", verdict
    count, ids = verdict["count"], verdict["idlist"]
    if count == 0 and ids == []:
        return "OA_SUBSET_INELIGIBLE", verdict
    if ids == [pmcid[3:]]:
        return "OA_SUBSET_ELIGIBLE", verdict
    return "OA_SUBSET_UNRESOLVED", verdict


def run(pre_oa, metadata_by_pmid, transport):
    oa_requests = [{"ordinal": i, "pmid": row["pmid"], "pmcid": row["pmcid"],
                    "endpoint": ES, "parameters": {"db": "pmc", "retmode": "json",
                        "retmax": "1", "term": source_policy.oa_subset_esearch_term(row["pmcid"])}}
                   for i, row in enumerate(pre_oa, 1)]
    write_jsonl("pmc_oa_subset_request_manifest.jsonl", oa_requests)
    oa_rows = []
    for request in oa_requests:
        raw, attempts = transport.fetch("PMC_OA_SUBSET", request["ordinal"], request["pmid"],
                                        ES, request["parameters"], "pmc_oa_subset_raw_responses")
        state, verdict = oa_subset_state(raw, attempts, request["pmcid"])
        entry = {"ordinal": request["ordinal"], "pmid": request["pmid"],
                 "pmcid": request["pmcid"], "state": state,
                 "validity": verdict, "raw_response_sha256": master.sha(raw) if raw is not None else None,
                 "request_attempts": attempts}
        oa_rows.append(entry)
        append_jsonl("pmc_oa_subset_results.jsonl", entry)
    require(len(oa_rows) == len(pre_oa) == 42, "OA_TERMINAL_STATES_INCOMPLETE")
    write_json("pmc_oa_completion_barrier.json", {"all_42_terminal_states_frozen": True,
        "oa_subset_eligible_count": sum(x["state"] == "OA_SUBSET_ELIGIBLE" for x in oa_rows),
        "oa_subset_results_sha256": master.digest(OUT / "pmc_oa_subset_results.jsonl"),
        "pmcid_alone_treated_as_oa_proof": False})
    print(json.dumps({"stage": "pmc_oa_subset", "completed": 42,
                      "eligible": sum(x["state"] == "OA_SUBSET_ELIGIBLE" for x in oa_rows)},
                     sort_keys=True), flush=True)

    eligible = [row for row, result in zip(pre_oa, oa_rows)
                if result["state"] == "OA_SUBSET_ELIGIBLE"]
    jats_requests = [{"ordinal": i, "pmid": row["pmid"], "pmcid": row["pmcid"],
                     "endpoint": EF, "parameters": {"db": "pmc", "retmode": "xml",
                          "id": row["pmcid"][3:]}}
                    for i, row in enumerate(eligible, 1)]
    write_jsonl("pmc_jats_request_manifest.jsonl", jats_requests)
    jats_by_pmid = {}
    for request in jats_requests:
        pmid, pmcid = request["pmid"], request["pmcid"]
        raw, attempts = transport.fetch("PMC_JATS", request["ordinal"], pmid, EF,
                                        request["parameters"], "pmc_jats_raw_responses")
        canonical = None
        error = None
        if raw is None:
            error = "TERMINAL_JATS_TRANSPORT_FAILURE"
        else:
            try:
                canonical = frozen_rules.canonical_jats(raw, pmcid)
            except (ET.ParseError, ValueError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
        canonical_path = None
        token = None
        if canonical is not None:
            canonical_path = f"pmc_jats_normalized/{request['ordinal']:03d}_{pmid}.xml"
            write_bytes(canonical_path, canonical)
            token = "src_" + secrets.token_hex(32)
        entry = {"ordinal": request["ordinal"], "pmid": pmid, "pmcid": pmcid,
                 "terminal_state": "JATS_CANONICALIZED" if canonical is not None else "JATS_FAILED_NO_REPLACEMENT",
                 "error": error, "raw_jats_path": attempts[-1]["raw_path"] if raw is not None else None,
                 "raw_jats_sha256": master.sha(raw) if raw is not None else None,
                 "normalized_jats_path": canonical_path,
                 "normalized_jats_sha256": master.sha(canonical) if canonical is not None else None,
                 "opaque_source_token": token, "request_attempts": attempts}
        jats_by_pmid[pmid] = entry
        append_jsonl("pmc_jats_terminal_states.jsonl", entry)
    require(len(jats_by_pmid) == len(jats_requests), "JATS_TERMINAL_STATES_INCOMPLETE")
    write_json("pmc_jats_completion_barrier.json", {
        "all_oa_eligible_sources_have_jats_terminal_states": True,
        "jats_requested_count": len(jats_requests),
        "jats_canonicalized_count": sum(x["terminal_state"] == "JATS_CANONICALIZED"
                                       for x in jats_by_pmid.values()),
        "jats_terminal_states_sha256": master.digest(OUT / "pmc_jats_terminal_states.jsonl")
            if jats_by_pmid else None,
        "replacement_sources_requested": 0})
    print(json.dumps({"stage": "pmc_jats", "requested": len(jats_requests),
                      "canonicalized": sum(x["terminal_state"] == "JATS_CANONICALIZED"
                                           for x in jats_by_pmid.values())}, sort_keys=True), flush=True)

    states = []
    handoff = []
    by_oa = {row["pmid"]: row for row in oa_rows}
    for source in pre_oa:
        pmid = source["pmid"]
        metadata = metadata_by_pmid[pmid]
        oa = by_oa[pmid]
        jats = jats_by_pmid.get(pmid)
        license_result = None
        source_type_result = None
        canonical = None
        if jats is not None and jats["terminal_state"] == "JATS_CANONICALIZED":
            canonical = (OUT / jats["normalized_jats_path"]).read_bytes()
            license_result = license_v2.extract_license_v2(canonical)
            source_type_result = source_policy.source_type_state(metadata["publication_types"], canonical)
        subset_result = (True if oa["state"] == "OA_SUBSET_ELIGIBLE" else
                         False if oa["state"] == "OA_SUBSET_INELIGIBLE" else None)
        construction_oa_result = license_v2.construction_oa_v2(source["pmcid"],
                                                               subset_result, canonical)
        license_state = license_result["state"] if license_result else "NOT_EVALUATED_NO_JATS"
        type_state = source_type_result["state"] if source_type_result else "NOT_EVALUATED_NO_JATS"
        if license_result is not None:
            require(construction_oa_result["state"] == "CONSTRUCTION_OA_" + license_state,
                    "CONSTRUCTION_OA_LICENSE_STATE_CONFLICT")
        if oa["state"] != "OA_SUBSET_ELIGIBLE":
            construction_state = "BLOCKED_OA_SUBSET"
        elif jats is None or jats["terminal_state"] != "JATS_CANONICALIZED":
            construction_state = "BLOCKED_JATS"
        elif license_state != "ELIGIBLE":
            construction_state = "BLOCKED_LICENSE"
        elif type_state != "SOURCE_TYPE_ELIGIBLE":
            construction_state = "BLOCKED_SOURCE_TYPE"
        elif source["updateof_deferred_to_structure_stage"]:
            construction_state = "CONDITIONAL_UPDATEOF_PENDING_FROZEN_FINALIZATION"
        else:
            construction_state = "CONSTRUCTION_SOURCE_ELIGIBLE"
        entry = {"sample_ordinal": source["sample_ordinal"], "pmid": pmid,
                 "pmcid": source["pmcid"], "doi": source["doi"],
                 "pre_oa_state": "CONDITIONAL_UPDATEOF" if source["updateof_deferred_to_structure_stage"]
                     else "DIRECT_CLEAR",
                 "correction_reference_preliminary_state": source["correction_reference_preliminary_state"],
                 "updateof_deferred_unresolved": source["updateof_deferred_to_structure_stage"],
                 "oa_subset_state": oa["state"],
                 "jats_terminal_state": jats["terminal_state"] if jats else "NOT_REQUESTED_OA_NOT_ELIGIBLE",
                 "construction_oa_state": construction_oa_result["state"],
                 "construction_oa_result": construction_oa_result,
                 "license_state": license_state, "license_result": license_result,
                 "source_type_state": type_state, "source_type_result": source_type_result,
                 "construction_eligibility_state": construction_state,
                 "opaque_source_token": jats["opaque_source_token"] if jats else None,
                 "normalized_jats_path": jats["normalized_jats_path"] if jats else None,
                 "normalized_jats_sha256": jats["normalized_jats_sha256"] if jats else None}
        states.append(entry)
        append_jsonl("construction_eligibility_states.jsonl", entry)
        if construction_state in {"CONSTRUCTION_SOURCE_ELIGIBLE",
                                  "CONDITIONAL_UPDATEOF_PENDING_FROZEN_FINALIZATION"}:
            handoff.append({"sample_ordinal": source["sample_ordinal"], "pmid": pmid,
                "pmcid": source["pmcid"], "doi": source["doi"],
                "opaque_source_token": jats["opaque_source_token"],
                "pre_oa_state": entry["pre_oa_state"],
                "construction_eligibility_state": construction_state,
                "builder_ready": construction_state == "CONSTRUCTION_SOURCE_ELIGIBLE",
                "updateof_deferred_unresolved": source["updateof_deferred_to_structure_stage"],
                "oa_subset_state": oa["state"], "license_state": license_state,
                "source_type_state": type_state,
                "raw_metadata_sha256": source["raw_metadata_sha256"],
                "raw_jats_path": jats["raw_jats_path"],
                "raw_jats_sha256": jats["raw_jats_sha256"],
                "normalized_jats_path": jats["normalized_jats_path"],
                "normalized_jats_sha256": jats["normalized_jats_sha256"]})
    require(len(states) == len(pre_oa) == 42 and
            len({row["pmid"] for row in states}) == 42 and
            all(row["updateof_deferred_unresolved"] ==
                (row["pre_oa_state"] == "CONDITIONAL_UPDATEOF") for row in states),
            "CONSTRUCTION_ELIGIBILITY_STATE_INVARIANT_FAILED")
    write_jsonl("construction_source_handoff_manifest.jsonl", handoff)
    return oa_rows, jats_by_pmid, states, handoff


def finalize(status, pre_oa, transport, oa_rows, jats_by_pmid, states, handoff, failure=None):
    oa_counts = Counter(row["state"] for row in oa_rows)
    jats_counts = Counter(row["terminal_state"] for row in jats_by_pmid.values())
    construction_counts = Counter(row["construction_eligibility_state"] for row in states)
    write_json("validation.json", {"status": status, "alpha3_19c_root_verified": True,
        "pre_oa_source_count": len(pre_oa), "source_eligibility_terminal_count": len(states),
        "all_42_sources_preserved": len(states) == 42 and
            [x["pmid"] for x in states] == [x["pmid"] for x in pre_oa],
        "all_raw_attempts_frozen": len(transport.attempts) == transport.calls and all(
            master.digest(OUT / row["raw_path"]) == row["raw_sha256"] for row in transport.attempts),
        "network_scope_ncbi_pmc_only": all(row["endpoint"] in {ES, EF} and
            row["parameters"]["db"] == "pmc" for row in transport.attempts),
        "pubmed_metadata_rerun_count": 0, "replacement_source_count": 0,
        "updateof_deferred_states_preserved": sum(row["updateof_deferred_unresolved"] for row in states) == 2
            if len(states) == 42 else False,
        "construction_documents_generated": 0, "span_anchors_generated": 0,
        "builder_calls": 0, "quality_calls": 0, "model_calls": 0,
        "historical_assets_modified": False, "scientific_policy_changed": False,
        "failure": failure})
    write_json("summary.json", {"status": status, "input_alpha3_19c_sha256": C_SHA,
        "pre_oa_source_count": len(pre_oa), "pre_oa_direct_count":
            sum(not x["updateof_deferred_to_structure_stage"] for x in pre_oa),
        "pre_oa_updateof_deferred_count":
            sum(x["updateof_deferred_to_structure_stage"] for x in pre_oa),
        "oa_subset_counts": dict(oa_counts), "jats_terminal_counts": dict(jats_counts),
        "license_state_counts": dict(Counter(row["license_state"] for row in states)),
        "source_type_state_counts": dict(Counter(row["source_type_state"] for row in states)),
        "construction_eligibility_counts": dict(construction_counts),
        "construction_source_handoff_count": len(handoff),
        "builder_ready_count": sum(row["builder_ready"] for row in handoff),
        "conditional_updateof_handoff_count": sum(row["updateof_deferred_unresolved"] for row in handoff),
        "ncbi_pmc_request_attempts": transport.calls, "pubmed_metadata_reruns": 0,
        "replacement_sources": 0, "model_calls": 0,
        "construction_documents_generated": 0, "span_anchors_generated": 0,
        "next_stage": "ALPHA3_19E_BUILDER_PREPARATION_PREREGISTRATION" if status == "completed"
                      else "AUDIT_ALPHA3_19D_RUNTIME_FAILURE_OFFLINE",
        "failure": failure})
    (OUT / ROOT_MARKER).write_text(root_hash() + "\n")
    print(json.dumps({"status": status, "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
                      "oa_subset_counts": dict(oa_counts), "jats_terminal_counts": dict(jats_counts),
                      "construction_eligibility_counts": dict(construction_counts),
                      "ncbi_pmc_request_attempts": transport.calls, "failure": failure},
                     sort_keys=True), flush=True)


def main():
    pre_oa, metadata_by_pmid, oa, jats, handoff_contract = preflight()
    OUT.mkdir()
    write_json("pre_network_integrity_verification.json", {
        "alpha3_19c_root_sha256": C_SHA,
        "post_metadata_pre_oa_manifest_sha256": master.digest(
            c.OUT / "post_metadata_pre_oa_source_manifest_v3.jsonl"),
        "pre_oa_source_count": len(pre_oa),
        "oa_subset_contract_sha256": master.digest(ROOT /
            load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")["oa_subset_route"]["path"]),
        "jats_contract_sha256": master.digest(ROOT /
            load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")["jats_route"]["path"]),
        "corrected_license_v2_bound": True, "mechanical_source_type_v1_bound": True,
        "deferred_updateof_not_finalized": True,
        "pubmed_metadata_not_requested": True})
    transport = PMCTransport(jats["technical_max_attempts"], jats["timeout_seconds"],
                             tuple(jats["backoff_seconds"]))
    try:
        oa_rows, jats_by_pmid, states, handoff = run(pre_oa, metadata_by_pmid, transport)
    except Exception as exc:
        oa_rows = rows(OUT / "pmc_oa_subset_results.jsonl") if (
            OUT / "pmc_oa_subset_results.jsonl").exists() else []
        jats_rows = rows(OUT / "pmc_jats_terminal_states.jsonl") if (
            OUT / "pmc_jats_terminal_states.jsonl").exists() else []
        states = rows(OUT / "construction_eligibility_states.jsonl") if (
            OUT / "construction_eligibility_states.jsonl").exists() else []
        finalize("failed_closed", pre_oa, transport, oa_rows,
                 {row["pmid"]: row for row in jats_rows}, states, [],
                 type(exc).__name__ + ":" + str(exc))
        return
    finalize("completed", pre_oa, transport, oa_rows, jats_by_pmid, states, handoff)


if __name__ == "__main__":
    main()
