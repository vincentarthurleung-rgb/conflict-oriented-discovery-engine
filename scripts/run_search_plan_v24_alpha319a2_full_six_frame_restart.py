#!/usr/bin/env python3
"""Run the authorized alpha3.19A2 PubMed frame-only technical restart."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha319a1_audit_backend_failure_offline as audit
from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as validity


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19a2_full_six_frame_ncbi_restart"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19a2_sha256"
A1_SHA = "05d155650b10556ac173978f69d5f607ab18872676db8e2d9e0d7e1ee340d1a7"
A2_MANIFEST_SHA = "67e4222f03021f43f84cf944878851b9989751421fff38e114070d7caca8b40a"
QUERY_SHA = "45536e1b734d1eeb54e0d111d6878c1b6dee58d1a762ad934d66b7d40089885e"
VALIDATOR_SHA = "4a77d09cc623b7d3739fe1efdebead512556e123c733353d069a22e87743efb4"
NEXT_PASS = "PREREGISTER_ALPHA3_19B_METADATA_AND_ELIGIBILITY_HANDOFF"
NEXT_FAIL = "AUDIT_ALPHA3_19A2_RUNTIME_FAILURE_OFFLINE"


class FrameFailure(RuntimeError):
    def __init__(self, failure_class: str, frame_index: int, retstart: int,
                 attempts: list[dict]):
        super().__init__(f"{failure_class}:frame={frame_index}:retstart={retstart}")
        self.failure_class = failure_class
        self.frame_index = frame_index
        self.retstart = retstart
        self.attempts = attempts


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def write_json(name: str, value: Any):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, values: list[dict]):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(b"".join(master.canonical(value) + b"\n" for value in values))


def write_bytes(name: str, raw: bytes):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def marker(name: str, value: str):
    write_bytes(name, (value + "\n").encode())


def root_hash():
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "SYMLINK_IN_RUN")
    return master.sha(master.canonical([[str(path.relative_to(OUT)), master.digest(path)]
                                      for path in files]))


def preflight():
    require(not OUT.exists(), "A2_RUN_ALREADY_EXISTS_NO_RERUN")
    require(audit.root_hash() == A1_SHA and
            (audit.OUT / audit.ROOT_MARKER).read_text().strip() == A1_SHA and
            audit.failed.root_hash() == audit.FAILED_SHA,
            "HISTORICAL_OR_AUDIT_ROOT_MISMATCH")
    manifest_path = audit.OUT / "alpha3_19a2_source_acquisition_execution_manifest.json"
    validator_path = audit.OUT / "pubmed_esearch_response_validity_v2_1.json"
    query_path = prereg.OUT / "alpha3_19_source_query_set.jsonl"
    require(master.digest(manifest_path) == A2_MANIFEST_SHA and
            (audit.OUT / "alpha3_19a2_source_acquisition_execution_manifest_sha256").read_text().strip() ==
            A2_MANIFEST_SHA and
            master.digest(validator_path) == VALIDATOR_SHA and
            (audit.OUT / "pubmed_esearch_response_validity_v2_1_sha256").read_text().strip() ==
            VALIDATOR_SHA and
            master.digest(query_path) == QUERY_SHA and
            (prereg.OUT / "alpha3_19_source_query_set_sha256").read_text().strip() == QUERY_SHA,
            "A2_FROZEN_BINDING_MISMATCH")
    manifest = audit.load(manifest_path)
    queries = master.rows(query_path)
    retry = audit.load(audit.OUT / "alpha3_19a2_retry_policy.json")
    master_seed = audit.load(master.OUT / "alpha3_19_sampling_seed_contract.json")
    require(len(queries) == manifest["query_count"] == 6 and
            manifest["query_hashes"] == [q["query_sha256"] for q in queries] and
            manifest["restart_mode"] == "FULL_SIX_FRAME_FROM_FRAME_1_RETSTART_0" and
            manifest["source_run_disposition"] == "FAILED_19A_PROVENANCE_ONLY_NO_DIRECT_IMPORT" and
            manifest["response_aware_retry_adapter_required"] and
            manifest["material_runtime_policy_unresolved_count"] == 0 and
            manifest["esearch_validator"]["sha256"] == VALIDATOR_SHA and
            manifest["esearch_retry_policy"]["sha256"] == master.digest(audit.OUT / "alpha3_19a2_retry_policy.json") and
            retry["attempts_max_per_logical_page"] == 4 and
            retry["timeout_seconds"] == 60 and retry["backoff_seconds"] == [2, 4, 8] and
            not retry["technical_budget_increased"] and
            manifest["sampling_seed"]["sha256"] ==
                master.digest(master.OUT / "alpha3_19_sampling_seed_contract.json") and
            master_seed["seed"] == master.sha(master_seed["seed_input"].encode()),
            "A2_POLICY_OR_SEED_DRIFT")
    old = audit.load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")
    scientific_keys = audit.load(audit.OUT / "scientific_configuration_nonadaptation_audit.json")[
        "scientific_manifest_keys_preserved"]
    require(all(manifest[key] == old[key] for key in scientific_keys),
            "A2_SCIENTIFIC_CONFIGURATION_DRIFT")
    require(manifest["network_scope"]["allowed_host"] == "eutils.ncbi.nlm.nih.gov" and
            manifest["network_scope"]["allowed_endpoints"] == [prereg.ES, prereg.EF] and
            all(q["endpoint"] == prereg.ES and q["db"] == "pubmed" and
                q["sort"] == "relevance" and q["page_size"] == 50 and
                q["retstart_sequence"] == [0, 50, 100, 150] and
                master.sha(q["query_utf8"].encode()) == q["query_sha256"] and
                q["query_utf8"].count('"pubmed pmc"[sb]') == 1
                for q in queries),
            "A2_NETWORK_OR_QUERY_DRIFT")
    def verify_refs(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                prereg.check_ref(value)
            for child in value.values():
                verify_refs(child)
        elif isinstance(value, list):
            for child in value:
                verify_refs(child)
    verify_refs(manifest)
    return {"manifest": manifest, "queries": queries, "retry": retry,
            "seed_sha256": master_seed["seed"]}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")


def retry_decision(verdict: dict, attempt: int, retry: dict) -> str:
    if verdict["valid_page"]:
        return "ACCEPT_PAGE"
    state = verdict["state"]
    if state not in validity.TECHNICAL_RETRYABLE_STATES or not verdict["technical_retryable"]:
        return "FAIL_CLOSED_NO_RETRY"
    if attempt >= retry["attempts_max_per_logical_page"]:
        return "FAIL_CLOSED_RETRY_EXHAUSTED"
    return "RETRY_WITHIN_FOUR_ATTEMPTS"


class ResponseAwareTransport:
    def __init__(self, retry: dict):
        self.retry = retry
        self.opener = urllib.request.build_opener(NoRedirect)
        self.last_started = 0.0
        self.calls = 0
        self.log: list[dict] = []

    def fetch_page(self, ordinal: int, query: dict, offset: int):
        endpoint = prereg.ES
        require(endpoint == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                "NETWORK_SCOPE_VIOLATION")
        parameters = {"db": "pubmed", "retmode": "json", "sort": "relevance",
                      "retmax": "50", "retstart": str(offset), "term": query["query_utf8"]}
        url = endpoint + "?" + urllib.parse.urlencode(parameters)
        attempts = []
        request_key = f"{query['ordinal']:02d}_{offset:03d}"
        for attempt in range(1, self.retry["attempts_max_per_logical_page"] + 1):
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
                "User-Agent": "conflict-oriented-discovery-engine-alpha319a2/1.0"})
            try:
                with self.opener.open(request, timeout=self.retry["timeout_seconds"]) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                error = type(exc).__name__
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
            except RuntimeError as exc:
                error = type(exc).__name__ + ":" + str(exc)
            raw_path = f"source_query_raw_responses/{request_key}_attempt{attempt}.bin"
            write_bytes(raw_path, raw)
            verdict = validity.validate_response(status, raw, offset, 50)
            decision = retry_decision(verdict, attempt, self.retry)
            if error == "RuntimeError:NCBI_REDIRECT_FORBIDDEN":
                decision = "FAIL_CLOSED_NETWORK_SCOPE_VIOLATION"
            record = {"request_ordinal": ordinal, "request_key": request_key,
                "frame_index": query["ordinal"], "stratum_id": query["stratum_id"],
                "retstart": offset, "attempt": attempt, "method": "GET",
                "endpoint": endpoint, "parameters": parameters, "url": url,
                "timestamp_utc": started, "http_status": status, "transport_error": error,
                "raw_path": raw_path, "raw_sha256": master.sha(raw),
                "raw_bytes": len(raw), "validity": verdict, "decision": decision}
            attempts.append(record)
            self.log.append(record)
            with (OUT / "ncbi_transport_attempts.jsonl").open("ab") as handle:
                handle.write(master.canonical(record) + b"\n")
            if decision == "ACCEPT_PAGE":
                return raw, verdict, attempts
            if decision.startswith("FAIL_CLOSED"):
                raise FrameFailure(verdict["state"] + ":" + decision,
                                   query["ordinal"], offset, attempts)
            time.sleep(self.retry["backoff_seconds"][attempt - 1])
        raise FrameFailure("UNREACHABLE_RETRY_LOOP_STATE", query["ordinal"], offset, attempts)


def run_frames(state: dict, transport: ResponseAwareTransport, counts: dict):
    queries = state["queries"]
    planned = [{"request_ordinal": i, "frame_index": query["ordinal"],
        "stratum_id": query["stratum_id"], "query_utf8": query["query_utf8"],
        "query_sha256": query["query_sha256"], "retstart": offset,
        "endpoint": prereg.ES, "parameters": {"db": "pubmed", "retmode": "json",
        "sort": "relevance", "retmax": "50", "retstart": str(offset),
        "term": query["query_utf8"]}}
        for i, (query, offset) in enumerate(((q, offset) for q in queries
            for offset in (0, 50, 100, 150)), 1)]
    write_jsonl("source_query_request_manifest.jsonl", planned)
    ordinal_by_page = {(x["frame_index"], x["retstart"]): x["request_ordinal"] for x in planned}
    page_results = []
    try:
        for query in queries:
            raw_order = []
            pages = []
            for offset in (0, 50, 100, 150):
                ordinal = ordinal_by_page[(query["ordinal"], offset)]
                try:
                    raw, verdict, attempts = transport.fetch_page(ordinal, query, offset)
                except FrameFailure as exc:
                    page_results.append({"request_ordinal": ordinal,
                        "frame_index": query["ordinal"], "stratum_id": query["stratum_id"],
                        "retstart": offset, "query_sha256": query["query_sha256"],
                        "terminal_state": "FAILED_CLOSED", "failure_class": exc.failure_class,
                        "attempts": exc.attempts})
                    raise
                page_results.append({"request_ordinal": ordinal,
                    "frame_index": query["ordinal"], "stratum_id": query["stratum_id"],
                    "retstart": offset, "query_sha256": query["query_sha256"],
                    "raw_response_sha256": master.sha(raw),
                    "validator_state": verdict["state"],
                    "querytranslation": verdict["querytranslation"],
                    "count": verdict["count"], "idlist": verdict["idlist"],
                    "attempts": attempts})
                ids = verdict["idlist"]
                count = verdict["count"]
                require(ids is not None and count is not None, "VALID_PAGE_MISSING_DATA")
                raw_order.extend(ids)
                pages.append({"retstart": offset, "count": count, "pmids": ids,
                              "raw_response_sha256": master.sha(raw),
                              "validator_state": verdict["state"],
                              "querytranslation": verdict["querytranslation"],
                              "attempt_count": len(attempts)})
                if len(ids) < 50 or offset + len(ids) >= count:
                    break
            write_json(f"six_source_frame_manifests/{query['ordinal']:02d}_{query['stratum_id']}.json", {
                "frame_index": query["ordinal"], "stratum_id": query["stratum_id"],
                "query_sha256": query["query_sha256"], "raw_pmid_order": raw_order,
                "raw_record_count": len(raw_order), "page_records": pages,
                "terminal_state": "COMPLETE_VALID_FRAME",
                "within_frame_deduplication_performed": False})
            counts["source_frames_completed"] += 1
            counts["raw_source_records"] += len(raw_order)
            print(json.dumps({"stage": "source_frame", "completed": counts["source_frames_completed"],
                "stratum": query["stratum_id"], "raw_records": len(raw_order)}, sort_keys=True), flush=True)
    finally:
        write_jsonl("source_query_execution_results.jsonl", page_results)
    frame_files = sorted((OUT / "six_source_frame_manifests").glob("*.json"))
    require(len(frame_files) == 6, "SIX_FRAME_COMPLETION_BARRIER_FAILED")
    marker("six_source_frames_sha256", master.sha(master.canonical(
        [[p.name, master.digest(p)] for p in frame_files])))
    counts["six_source_frames_frozen"] = True


def finalize(status: str, failure: FrameFailure | None, counts: dict,
             transport: ResponseAwareTransport):
    endpoints = {x["endpoint"] for x in transport.log}
    ncbi_only = endpoints <= {prereg.ES} and all(
        urllib.parse.urlsplit(x).hostname == "eutils.ncbi.nlm.nih.gov" for x in endpoints)
    failure_record = None if failure is None else {"failure_class": failure.failure_class,
        "failed_frame_index": failure.frame_index, "failed_retstart": failure.retstart,
        "attempts": failure.attempts}
    write_json("frame_completion_state.json", {"source_frames_completed": counts["source_frames_completed"],
        "required_frames": 6, "six_source_frames_frozen": counts["six_source_frames_frozen"],
        "failure": failure_record,
        "deduplication_or_sampling_started": False})
    write_json("network_scope_audit.json", {"allowed_endpoint": prereg.ES,
        "observed_endpoints": sorted(endpoints), "ncbi_only": ncbi_only,
        "ncbi_attempts": transport.calls, "non_ncbi_calls": 0,
        "pmc_or_efetch_requests": 0})
    write_json("protocol_compliance_audit.json", {"audit_root_verified": True,
        "a2_manifest_verified": True, "source_query_set_verified": True,
        "v2_1_validator_bound": True, "response_aware_retry_used": True,
        "queries_changed": False, "sampling_seed_changed": False,
        "historical_frames_reused": False, "historical_pages_imported": False,
        "frame1_retstart0_first": bool(transport.log and
            transport.log[0]["frame_index"] == 1 and transport.log[0]["retstart"] == 0),
        "old_new_page_union": False,
        "metadata_oa_jats_dedup_sampling_executed": False,
        "network_scope_ncbi_only": ncbi_only})
    write_json("scientific_state_safety_audit.json", {
        "deduplication_executed": False, "sampling_executed": False,
        "historical_contamination_gate_executed": False,
        "metadata_extraction_executed": False, "publication_type_filtering_executed": False,
        "correction_or_retraction_evaluation_executed": False,
        "pmc_oa_or_jats_executed": False, "license_or_builder_or_quality_executed": False,
        "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "non_ncbi_network_calls": 0, "historical_assets_modified": False})
    summary = {"status": status, "execution_identity":
        "PROSPECTIVE_TECHNICAL_ACQUISITION_RESTART_AFTER_PRE_SAMPLING_NCBI_FAILURE",
        "source_frames_completed": counts["source_frames_completed"],
        "source_frames_required": 6,
        "six_source_frames_frozen": counts["six_source_frames_frozen"],
        "raw_source_records": counts["raw_source_records"],
        "failed_frame_index": failure.frame_index if failure else None,
        "failed_retstart": failure.retstart if failure else None,
        "failure_class": failure.failure_class if failure else None,
        "failure_attempt_count": len(failure.attempts) if failure else 0,
        "ncbi_attempts": transport.calls,
        "network_scope_ncbi_only": ncbi_only,
        "source_query_set_sha256": QUERY_SHA,
        "sampling_seed_sha256": master.digest(master.OUT / "alpha3_19_sampling_seed_contract.json"),
        "sampling_seed_changed": False,
        "historical_frames_reused": False,
        "deduplication_executed": False, "sampling_executed": False,
        "metadata_oa_jats_executed": False,
        "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "non_ncbi_network_calls": 0,
        "next_stage_recommendation": NEXT_PASS if status == "completed" else NEXT_FAIL,
        "historical_assets_modified": False}
    write_json("alpha3_19a2_source_acquisition_execution_summary.json", summary)
    write_json("validation.json", {"status": status,
        "six_frame_barrier_crossed": counts["six_source_frames_frozen"],
        "all_raw_attempts_frozen": len(transport.log) == transport.calls and all(
            master.digest(OUT / x["raw_path"]) == x["raw_sha256"] for x in transport.log),
        "source_query_changes": 0, "historical_page_reuse": False,
        "network_scope_ncbi_only": ncbi_only,
        "downstream_actions_executed": False,
        "failure": failure_record})
    marker(ROOT_MARKER, root_hash())
    print(json.dumps({"status": status, "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
        "source_frames_completed": counts["source_frames_completed"],
        "raw_source_records": counts["raw_source_records"],
        "ncbi_attempts": transport.calls, "failure": failure_record}, sort_keys=True), flush=True)


def main():
    state = preflight()  # no filesystem execution run or network request before this gate
    OUT.mkdir()
    write_json("pre_network_integrity_verification.json", {
        "historical_failed_19a_root_sha256": audit.FAILED_SHA,
        "alpha3_19a1_audit_root_sha256": A1_SHA,
        "alpha3_19a2_execution_manifest_sha256": A2_MANIFEST_SHA,
        "query_set_sha256": QUERY_SHA, "validator_contract_sha256": VALIDATOR_SHA,
        "retry_policy_sha256": master.digest(audit.OUT / "alpha3_19a2_retry_policy.json"),
        "sampling_seed_sha256": master.digest(master.OUT / "alpha3_19_sampling_seed_contract.json"),
        "all_manifest_references_verified_before_network": True,
        "failed_frame_artifacts_not_imported": True})
    transport = ResponseAwareTransport(state["retry"])
    counts = {"source_frames_completed": 0, "raw_source_records": 0,
              "six_source_frames_frozen": False}
    try:
        run_frames(state, transport, counts)
    except FrameFailure as exc:
        finalize("failed_closed", exc, counts, transport)
        return
    except Exception as exc:
        last = transport.log[-1] if transport.log else None
        failure = FrameFailure(
            "UNCLASSIFIED_RUNTIME_FAILURE:" + type(exc).__name__ + ":" + str(exc),
            last["frame_index"] if last else 0,
            last["retstart"] if last else 0,
            [last] if last else [],
        )
        finalize("failed_closed", failure, counts, transport)
        return
    finalize("completed", None, counts, transport)


if __name__ == "__main__":
    main()
