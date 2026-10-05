#!/usr/bin/env python3
"""Execute only frozen alpha3.21A PubMed ESearch pages, fail closed."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as validity


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
A = RUNS / "20261005_search_plan_v24_primary_alpha3_21a_fresh_source_acquisition_preregistration_offline"
MASTER = RUNS / "20261005_search_plan_v24_primary_alpha3_21_fresh_primary_master_preregistration_offline"
OUT = RUNS / "20261005_search_plan_v24_primary_alpha3_21a1_fresh_source_acquisition_execution"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21a1_sha256"
A_ROOT = "16d26159bef61fe84577a4f8f053f8cb13962974ddaa44fdee5ae7ac6fe58146"
MASTER_ROOT = "47c0ba15f6acb4e1e581d148edbfa0674a7dc1e82261764876cef20f4184d935"
QUERY_SHA = "9f699f4702ba6b98b91dbbd6af443638309dd8de615ffcdb43bf6bebd8a95eb5"
POTENTIAL_SHA = "f148cd5a1d2e8cef67dbaa0da1327f53e3eded1a03c48ca46867048c7a2ce50b"
FIRST_SHA = "74b03a7b6647b330d2f6050f114852de0594ebff3d1f96d2f306ba3f5b1c79f8"
SEEN_SHA = "2c1a5b6cb46d4dace84f77068bc2ba3805760594927e1f5b7e8e11af2e08dab3"
ES = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NEXT_OK = "PREREGISTER_ALPHA3_21B_OFFLINE_DEDUP_SEEN_EXCLUSION_AND_STRATIFIED_SAMPLING"
NEXT_FAIL = "AUDIT_ALPHA3_21A1_ACQUISITION_FAILURE_OFFLINE"
NEXT_DRIFT = "AUDIT_ALPHA3_21A1_PUBMED_RESULT_SET_DRIFT_OFFLINE"
CLASS_OK = "FRESH_PRIMARY_SOURCE_ACQUISITION_COMPLETE_AND_FROZEN"
CLASS_FAIL = "FRESH_PRIMARY_SOURCE_ACQUISITION_INCOMPLETE_TECHNICAL_FAILURE"
CLASS_DRIFT = "FRESH_PRIMARY_SOURCE_ACQUISITION_BLOCKED_BY_RESULT_SET_COUNT_DRIFT"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), digest(path)]
                          for path in files]))


def ref(path: Path, role: str) -> dict:
    return {"artifact_role": role, "artifact_path": str(path.relative_to(ROOT)),
            "sha256": digest(path), "immutable_frozen": True}


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def append_row(name: str, value: dict) -> None:
    with (OUT / name).open("ab") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA321A1_OUTPUT_ALREADY_EXISTS_NO_RERUN")
    for directory, marker_name, expected in (
        (A, "search_plan_v24_primary_alpha3_21a_prereg_sha256", A_ROOT),
        (MASTER, "search_plan_v24_primary_alpha3_21_master_prereg_sha256",
         MASTER_ROOT),
    ):
        require((directory / marker_name).read_text().strip() == expected
                and root_hash(directory, marker_name) == expected,
                "UPSTREAM_ROOT_MISMATCH:" + marker_name)
    for stem, expected in (
        ("alpha3_21_source_query_set", QUERY_SHA),
        ("alpha3_21_potential_page_request_manifest", POTENTIAL_SHA),
        ("alpha3_21_first_page_request_manifest", FIRST_SHA),
    ):
        require(digest(A / (stem + ".jsonl")) == expected
                and (A / (stem + "_sha256")).read_text().strip() == expected,
                "FROZEN_MANIFEST_HASH_MISMATCH:" + stem)
    require(digest(MASTER / "alpha3_21_seen_contamination_registry.json") ==
            SEEN_SHA and (MASTER /
            "alpha3_21_seen_contamination_registry_sha256").read_text().strip()
            == SEEN_SHA, "HISTORICAL_REGISTRY_HASH_MISMATCH")
    required_contracts = (
        "alpha3_21_esearch_response_validity_binding.json",
        "alpha3_21_technical_retry_policy.json",
        "alpha3_21_result_set_count_consistency_contract.json",
        "alpha3_21_raw_response_preservation_contract.json",
        "alpha3_21_acquisition_terminal_state_contract.json",
        "alpha3_21_page_expansion_contract.json",
        "alpha3_21_acquisition_completeness_contract.json",
        "alpha3_21_no_self_contamination_contract.json",
    )
    contracts = {name: obj(A / name) for name in required_contracts}
    retry = contracts["alpha3_21_technical_retry_policy.json"]
    count_policy = contracts["alpha3_21_result_set_count_consistency_contract.json"]
    expansion = contracts["alpha3_21_page_expansion_contract.json"]
    raw_policy = contracts["alpha3_21_raw_response_preservation_contract.json"]
    terminal = contracts["alpha3_21_acquisition_terminal_state_contract.json"]
    esearch = contracts["alpha3_21_esearch_response_validity_binding.json"]
    require(retry["max_attempts_per_logical_page"] == 4
            and retry["timeout_seconds"] == 60
            and retry["backoff_seconds"] == [2, 4, 8]
            and retry["retryable_http_status"] ==
                sorted(validity.RETRYABLE_HTTP_STATUS)
            and count_policy["subsequent_executed_page_count_must_equal_initial"]
                is True
            and count_policy["idlist_cardinality_must_match_retstart_retmax_count"]
                is True
            and expansion["execute_if"] ==
                "retstart < min(frozen_initial_result_count, 200)"
            and expansion["freeze_remaining_manifest_before_any_retstart_gt_zero"]
                is True
            and raw_policy["preserve_before_postprocessing"] is True
            and "RESULT_SET_COUNT_DRIFT" in terminal["terminal_states"]
            and esearch["http_200_backend_error_is_valid_page"] is False
            and esearch["implementation"]["sha256"] == digest(
                ROOT / esearch["implementation"]["artifact_path"]),
            "FROZEN_RUNTIME_POLICY_MISMATCH")
    potential = rows(A / "alpha3_21_potential_page_request_manifest.jsonl")
    first = rows(A / "alpha3_21_first_page_request_manifest.jsonl")
    queries = rows(A / "alpha3_21_source_query_set.jsonl")
    require(len(potential) == 24 and len(first) == len(queries) == 6
            and len({p["logical_request_id"] for p in potential}) == 24
            and first == [p for p in potential if p["retstart"] == 0]
            and [p["stratum_id"] for p in first] ==
                [q["stratum_id"] for q in queries],
            "FROZEN_24_AND_6_REQUEST_SET_MISMATCH")
    for page in potential:
        payload = page["request_payload"]
        require(page["endpoint"] == ES
                and payload["db"] == "pubmed"
                and payload["retmode"] == "json"
                and payload["sort"] == "relevance"
                and payload["retmax"] == 50
                and payload["retstart"] == page["retstart"]
                and page["retstart"] in (0, 50, 100, 150)
                and sha(canonical(payload)) == page["request_payload_sha256"]
                and sha(payload["term"].encode("utf-8")) ==
                    page["query_sha256"],
                "FROZEN_PAGE_PAYLOAD_MISMATCH")
    return {"potential": potential, "first": first, "queries": queries,
            "retry": retry, "contracts": contracts}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")


class PageFailure(RuntimeError):
    def __init__(self, page: dict, terminal_state: str, reason: str):
        super().__init__(reason)
        self.page = page
        self.terminal_state = terminal_state
        self.reason = reason


class Transport:
    def __init__(self, retry: dict, opener=None, sleep=time.sleep,
                 monotonic=time.monotonic):
        self.retry = retry
        self.opener = opener or urllib.request.build_opener(NoRedirect)
        self.sleep = sleep
        self.monotonic = monotonic
        self.last_started = None
        self.transport_attempts = 0
        self.technical_retries = 0
        self.invalid_responses = 0
        self.valid_responses = 0

    def request_page(self, page: dict, phase: str) -> dict:
        require(page["endpoint"] == ES, "NON_PUBMED_ESEARCH_ENDPOINT_FORBIDDEN")
        payload = page["request_payload"]
        require(sha(canonical(payload)) == page["request_payload_sha256"],
                "REQUEST_PAYLOAD_CHANGED_BEFORE_NETWORK")
        params = {key: str(payload[key]) for key in
                  ("db", "retmode", "sort", "retmax", "retstart", "term")}
        url = ES + "?" + urllib.parse.urlencode(params)
        require(urllib.parse.urlsplit(url).hostname == "eutils.ncbi.nlm.nih.gov",
                "NCBI_HOST_SCOPE_VIOLATION")
        for attempt in range(1, self.retry["max_attempts_per_logical_page"] + 1):
            if self.last_started is not None:
                delay = max(0.0, 0.38 - (self.monotonic() - self.last_started))
                if delay:
                    self.sleep(delay)
            self.last_started = self.monotonic()
            self.transport_attempts += 1
            require(self.transport_attempts <= 96,
                    "TRANSPORT_ATTEMPT_CEILING_VIOLATION")
            timestamp = utc_now()
            status, raw, error, headers = None, b"", None, {}
            request = urllib.request.Request(url, headers={
                "User-Agent": "conflict-oriented-discovery-engine-alpha321a1/1.0"})
            try:
                with self.opener.open(request, timeout=60) as response:
                    status = response.status
                    headers = {"content_type": response.headers.get("Content-Type")}
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                headers = {"content_type": exc.headers.get("Content-Type")
                           if exc.headers else None}
                raw = exc.read()
                error = type(exc).__name__
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
            raw_name = ("raw_pubmed_esearch_responses/" +
                        page["logical_request_id"] +
                        f"_attempt{attempt}.bin")
            raw_path = OUT / raw_name
            with raw_path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            raw_sha = sha(raw)
            verdict = validity.validate_response(status, raw,
                page["retstart"], page["retmax"])
            cardinality_ok = (verdict["valid_page"] and len(verdict["idlist"]) ==
                min(page["retmax"], max(0, verdict["count"] - page["retstart"])))
            if verdict["valid_page"] and not cardinality_ok:
                decision = "FAIL_CLOSED_IDLIST_CARDINALITY_MISMATCH"
            elif verdict["valid_page"]:
                decision = "ACCEPT_VALID_PAGE"
            elif error == "RuntimeError:NCBI_REDIRECT_FORBIDDEN":
                decision = "FAIL_CLOSED_NETWORK_SCOPE_VIOLATION"
            elif (verdict["technical_retryable"]
                  and verdict["state"] in validity.TECHNICAL_RETRYABLE_STATES
                  and attempt < self.retry["max_attempts_per_logical_page"]):
                decision = "RETRY_FROZEN_TECHNICAL_POLICY"
            else:
                decision = "FAIL_CLOSED_RESPONSE_OR_TRANSPORT"
            record = {"phase": phase, "logical_request_id":
                page["logical_request_id"], "stratum_id": page["stratum_id"],
                "retstart": page["retstart"], "attempt": attempt,
                "request_payload_sha256": page["request_payload_sha256"],
                "method": "GET", "endpoint": ES, "parameters": params,
                "url": url, "timestamp_utc": timestamp,
                "completed_timestamp_utc": utc_now(),
                "http_status": status, "http_metadata": headers,
                "transport_error": error, "raw_path": raw_name,
                "raw_sha256": raw_sha, "raw_bytes": len(raw),
                "validity": verdict, "idlist_cardinality_valid": cardinality_ok,
                "decision": decision}
            raw_manifest = {"phase": phase,
                "logical_request_id": page["logical_request_id"],
                "stratum_id": page["stratum_id"],
                "retstart": page["retstart"], "attempt": attempt,
                "raw_path": raw_name, "raw_sha256": raw_sha,
                "raw_bytes": len(raw), "http_status": status,
                "timestamp_utc": timestamp,
                "validator_state": verdict["state"]}
            prefix = "first_page" if phase == "FIRST_PAGE" else "remaining_page"
            append_row(prefix + "_request_attempt_log.jsonl", record)
            append_row("all_pubmed_request_attempt_log.jsonl", record)
            append_row(prefix + "_raw_response_manifest.jsonl", raw_manifest)
            append_row("all_pubmed_raw_response_manifest.jsonl", raw_manifest)
            if decision == "ACCEPT_VALID_PAGE":
                self.valid_responses += 1
                return {"page": page, "count": verdict["count"],
                        "idlist": verdict["idlist"],
                        "raw_sha256": raw_sha,
                        "raw_path": raw_name,
                        "attempt": attempt,
                        "validator_state": verdict["state"],
                        "timestamp_utc": timestamp}
            self.invalid_responses += 1
            if decision == "RETRY_FROZEN_TECHNICAL_POLICY":
                self.technical_retries += 1
                self.sleep(self.retry["backoff_seconds"][attempt - 1])
                continue
            terminal = ("RESPONSE_VALIDITY_FAILURE" if
                (status == 200 or decision == "FAIL_CLOSED_IDLIST_CARDINALITY_MISMATCH")
                else "TERMINAL_TECHNICAL_FAILURE")
            raise PageFailure(page, terminal, verdict["state"] + ":" + decision)
        raise RuntimeError("UNREACHABLE_RETRY_LOOP")


def initialize(state: dict) -> None:
    OUT.mkdir()
    (OUT / "raw_pubmed_esearch_responses").mkdir()
    for name in ("first_page_request_attempt_log.jsonl",
                 "first_page_raw_response_manifest.jsonl",
                 "remaining_page_request_attempt_log.jsonl",
                 "remaining_page_raw_response_manifest.jsonl",
                 "all_pubmed_request_attempt_log.jsonl",
                 "all_pubmed_raw_response_manifest.jsonl"):
        (OUT / name).open("xb").close()
    put("alpha3_21a_root_verification.json", {"verified": True,
        "root_sha256": A_ROOT})
    put("alpha3_21_master_root_verification.json", {"verified": True,
        "root_sha256": MASTER_ROOT})
    for output, source, expected in (
        ("source_query_set_preexecution_verification.json",
         A / "alpha3_21_source_query_set.jsonl", QUERY_SHA),
        ("potential_page_manifest_preexecution_verification.json",
         A / "alpha3_21_potential_page_request_manifest.jsonl", POTENTIAL_SHA),
        ("first_page_manifest_preexecution_verification.json",
         A / "alpha3_21_first_page_request_manifest.jsonl", FIRST_SHA),
    ):
        put(output, {"source": ref(source, output.removesuffix(".json")),
                     "expected_sha256": expected,
                     "byte_hash_verified_before_network": True})
    put("esearch_validity_contract_binding.json", {
        "frozen_contract": ref(A /
            "alpha3_21_esearch_response_validity_binding.json",
            "frozen_esearch_validity_binding"),
        "validator_implementation": ref(Path(__file__).resolve().parent /
            "search_plan_v24_alpha319a1_esearch_response_validity_v2_1.py",
            "frozen_esearch_validator_implementation")})
    put("technical_retry_policy_binding.json", {
        "frozen_policy": ref(A / "alpha3_21_technical_retry_policy.json",
                             "frozen_technical_retry_policy"),
        "maximum_attempts_per_logical_page": 4,
        "timeout_seconds": 60, "backoff_seconds": [2, 4, 8]})
    put("acquisition_pre_network_integrity_barrier.json", {
        "alpha3_21a_root_verified": True,
        "alpha3_21_master_root_verified": True,
        "query_set_verified": True,
        "potential_manifest_verified": True,
        "first_page_manifest_verified": True,
        "esearch_validity_verified": True,
        "technical_retry_verified": True,
        "result_set_count_consistency_verified": True,
        "raw_response_preservation_verified": True,
        "terminal_state_contract_verified": True,
        "six_first_pages_only_initial_execution": True,
        "preexisting_seen_registry_sha256": SEEN_SHA})


def run_with_transport(state: dict, transport: Transport) -> dict:
    initialize(state)
    started = utc_now()
    first_success: list[dict] = []
    remaining_success: list[dict] = []
    occurrences: list[dict] = []
    initial_counts: dict[str, int] = {}
    per_page: dict[str, dict] = {row["logical_request_id"]: {
        "logical_request_id": row["logical_request_id"],
        "stratum_id": row["stratum_id"], "retstart": row["retstart"],
        "terminal_state": "NOT_YET_EXECUTED", "failure_reason": None}
        for row in state["potential"]}
    failure: PageFailure | None = None
    drift: dict | None = None
    exposed: dict[str, dict] = {}
    executed_logical: set[str] = set()

    def accept(result: dict, *, trusted_for_normal_corpus: bool) -> None:
        page = result["page"]
        for rank, pmid in enumerate(result["idlist"], 1):
            occurrence = {"raw_acquisition_ordinal": len(occurrences) + 1,
                "pmid": pmid, "stratum_id": page["stratum_id"],
                "logical_page_id": page["logical_request_id"],
                "retstart": page["retstart"],
                "within_page_position": rank,
                "raw_response_sha256": result["raw_sha256"],
                "validator_state": result["validator_state"],
                "trusted_for_normal_acquisition_corpus": trusted_for_normal_corpus}
            occurrences.append(occurrence)
            exposed.setdefault(pmid, {
                "pmid": pmid,
                "first_exposure_logical_page_id": page["logical_request_id"],
                "first_exposure_stratum_id": page["stratum_id"],
                "first_exposure_timestamp_utc": result["timestamp_utc"],
                "future_attempt_seen": True,
                "current_alpha3_21_historical_exclusion": False})

    for page in state["first"]:
        executed_logical.add(page["logical_request_id"])
        try:
            result = transport.request_page(page, "FIRST_PAGE")
        except PageFailure as exc:
            failure = exc
            per_page[page["logical_request_id"]].update({
                "terminal_state": exc.terminal_state,
                "failure_reason": exc.reason})
            break
        initial_counts[page["stratum_id"]] = result["count"]
        first_success.append(result)
        accept(result, trusted_for_normal_corpus=True)
        per_page[page["logical_request_id"]]["terminal_state"] = "VALID_SUCCESS"
        print(json.dumps({"phase": "first_page", "stratum": page["stratum_id"],
                          "count": result["count"], "ids": len(result["idlist"]),
                          "first_page_valid": len(first_success)},
                         sort_keys=True), flush=True)
    put("first_page_count_snapshot.json", {
        "counts_by_stratum": initial_counts,
        "six_valid_first_pages": len(first_success) == 6,
        "count_authority": "valid frozen retstart=0 page only",
        "phase1_terminal_failure": None if failure is None else failure.reason})
    expansion: list[dict] = []
    if failure is None and len(first_success) == 6:
        for page in state["potential"]:
            if page["retstart"] == 0:
                continue
            count = initial_counts[page["stratum_id"]]
            required = page["retstart"] < min(count, 200)
            expansion.append({"logical_request_id": page["logical_request_id"],
                "stratum_id": page["stratum_id"],
                "retstart": page["retstart"],
                "initial_result_count": count,
                "execution_state": "REQUIRED" if required else
                    "NOT_REQUIRED_BY_COUNT"})
            if not required:
                per_page[page["logical_request_id"]]["terminal_state"] = \
                    "NOT_REQUIRED_BY_COUNT"
        require(len(expansion) == 18, "PAGE_EXPANSION_NOT_18")
        expansion_sha = put("alpha3_21a1_remaining_page_execution_manifest.json", {
            "status": "FROZEN_BEFORE_ANY_PHASE2_REQUEST",
            "first_page_count_snapshot_sha256": digest(OUT /
                "first_page_count_snapshot.json"),
            "page_entries": expansion,
            "required_count": sum(row["execution_state"] == "REQUIRED"
                                  for row in expansion),
            "not_required_count": sum(row["execution_state"] ==
                                      "NOT_REQUIRED_BY_COUNT" for row in expansion)})
        marker("alpha3_21a1_remaining_page_execution_manifest_sha256",
               expansion_sha)
        by_id = {row["logical_request_id"]: row for row in state["potential"]}
        for planned in expansion:
            if planned["execution_state"] != "REQUIRED":
                continue
            page = by_id[planned["logical_request_id"]]
            executed_logical.add(page["logical_request_id"])
            try:
                result = transport.request_page(page, "REMAINING_PAGE")
            except PageFailure as exc:
                failure = exc
                per_page[page["logical_request_id"]].update({
                    "terminal_state": exc.terminal_state,
                    "failure_reason": exc.reason})
                break
            expected_count = initial_counts[page["stratum_id"]]
            if result["count"] != expected_count:
                drift = {"logical_request_id": page["logical_request_id"],
                    "stratum_id": page["stratum_id"],
                    "retstart": page["retstart"],
                    "first_page_count": expected_count,
                    "subsequent_page_count": result["count"]}
                accept(result, trusted_for_normal_corpus=False)
                per_page[page["logical_request_id"]]["terminal_state"] = \
                    "RESULT_SET_COUNT_DRIFT"
                break
            remaining_success.append(result)
            accept(result, trusted_for_normal_corpus=True)
            per_page[page["logical_request_id"]]["terminal_state"] = "VALID_SUCCESS"
            print(json.dumps({"phase": "remaining_page",
                              "stratum": page["stratum_id"],
                              "retstart": page["retstart"],
                              "ids": len(result["idlist"]),
                              "remaining_page_valid": len(remaining_success)},
                             sort_keys=True), flush=True)
    else:
        expansion_sha = put("alpha3_21a1_remaining_page_execution_manifest.json", {
            "status": "NOT_DERIVED_PHASE1_TERMINAL_FAILURE",
            "page_entries": [{"logical_request_id": page["logical_request_id"],
                "stratum_id": page["stratum_id"], "retstart": page["retstart"],
                "execution_state": "NOT_DERIVED_PHASE1_TERMINAL_FAILURE"}
                for page in state["potential"] if page["retstart"] > 0],
            "required_count": 0, "not_required_count": 0})
        marker("alpha3_21a1_remaining_page_execution_manifest_sha256",
               expansion_sha)

    if failure is not None or drift is not None:
        for page_state in per_page.values():
            if page_state["terminal_state"] == "NOT_YET_EXECUTED":
                page_state["terminal_state"] = "NOT_EXECUTED_AFTER_STAGE_STOP"
    completed = (failure is None and drift is None
                 and len(first_success) == 6
                 and all(per_page[row["logical_request_id"]]["terminal_state"] ==
                         "VALID_SUCCESS" for row in expansion
                         if row["execution_state"] == "REQUIRED"))
    if drift is not None:
        classification, next_stage = CLASS_DRIFT, NEXT_DRIFT
    elif not completed:
        classification, next_stage = CLASS_FAIL, NEXT_FAIL
    else:
        classification, next_stage = CLASS_OK, NEXT_OK

    put_rows("per_page_terminal_states.jsonl", [
        per_page[row["logical_request_id"]] for row in state["potential"]])
    put("result_set_count_consistency_audit.json", {
        "initial_counts_by_stratum": initial_counts,
        "all_executed_additional_pages_match_first_page_count": drift is None,
        "count_drift_count": int(drift is not None),
        "count_drift": drift,
        "result_set_count_consistency_rule_frozen": True})
    put_rows("raw_pmid_occurrence_manifest.jsonl", occurrences)
    exposure_rows = sorted(exposed.values(), key=lambda row: int(row["pmid"]))
    exposure_sha = put("alpha3_21_current_attempt_source_exposure_registry.json", {
        "schema_version": "Alpha3_21CurrentAttemptSourceExposureRegistry",
        "use": "future_attempt_contamination_history_only",
        "not_current_alpha3_21_preexisting_exclusion": True,
        "exposed_unique_pmids": exposure_rows,
        "unique_pmid_count": len(exposure_rows),
        "acquisition_complete": completed})
    marker("alpha3_21_current_attempt_source_exposure_registry_sha256",
           exposure_sha)
    put("raw_pmid_provenance_audit.json", {
        "raw_pmid_occurrence_count": len(occurrences),
        "unique_exposed_pmid_count": len(exposure_rows),
        "within_page_deduplication_performed": False,
        "within_stratum_deduplication_performed": False,
        "cross_stratum_deduplication_performed": False,
        "untrusted_invalid_response_ids_imported": False,
        "count_drift_page_ids_exposed_for_future_only": drift is not None})
    if completed:
        corpus_sha = put_rows("alpha3_21a1_raw_acquisition_corpus.jsonl",
                              occurrences)
        marker("alpha3_21a1_raw_acquisition_corpus_sha256", corpus_sha)
    else:
        corpus_sha = None
        put_rows("alpha3_21a1_partial_raw_acquisition_corpus.jsonl", [
            {**row, "corpus_state":
             "INCOMPLETE_PRIMARY_ACQUISITION_NOT_ELIGIBLE_FOR_21B"}
            for row in occurrences])
    require(digest(MASTER / "alpha3_21_seen_contamination_registry.json") ==
            SEEN_SHA, "HISTORICAL_SEEN_REGISTRY_CHANGED_AFTER_NETWORK")
    put("preexisting_seen_registry_postexecution_verification.json", {
        "registry_sha256": SEEN_SHA,
        "historical_seen_pmid_count": 2545,
        "unchanged": True})
    put("current_attempt_no_self_contamination_audit.json", {
        "current_attempt_exposure_registry": ref(OUT /
            "alpha3_21_current_attempt_source_exposure_registry.json",
            "current_attempt_future_contamination_history"),
        "preexisting_registry_sha256": SEEN_SHA,
        "preexisting_registry_modified": False,
        "current_attempt_exposure_does_not_self_exclude": True,
        "historical_exclusion_performed_in_alpha3_21a1": False})
    finished = utc_now()
    all_attempts = rows(OUT / "all_pubmed_request_attempt_log.jsonl")
    all_raw = rows(OUT / "all_pubmed_raw_response_manifest.jsonl")
    require(len(all_attempts) == len(all_raw) == transport.transport_attempts
            and len(executed_logical) <= 24
            and transport.transport_attempts <= 96,
            "NETWORK_ACCOUNTING_OR_BUDGET_VIOLATION")
    put("acquisition_execution_timestamps.json", {
        "stage_start_utc": started,
        "stage_finish_utc": finished,
        "attempt_timestamps_utc": [row["timestamp_utc"] for row in all_attempts]})
    put("acquisition_snapshot_interpretation.json", {
        "observed_pubmed_index_interval_utc": [started, finished],
        "corpus_interpretation":
            "live PubMed index state observed during the frozen acquisition run",
        "all_matching_2026_publications_claim": False,
        "later_index_refresh_allowed": False})
    require(digest(A / "alpha3_21_source_query_set.jsonl") == QUERY_SHA
            and digest(A / "alpha3_21_potential_page_request_manifest.jsonl") ==
                POTENTIAL_SHA
            and digest(A / "alpha3_21_first_page_request_manifest.jsonl") ==
                FIRST_SHA,
            "FROZEN_QUERY_OR_MANIFEST_CHANGED_AFTER_NETWORK")
    put("query_manifest_postexecution_verification.json", {
        "source_query_set_sha256": QUERY_SHA,
        "potential_page_manifest_sha256": POTENTIAL_SHA,
        "first_page_manifest_sha256": FIRST_SHA,
        "all_unchanged": True})
    per_stratum = []
    for query in state["queries"]:
        sid = query["stratum_id"]
        per_stratum.append({"stratum_id": sid,
            "initial_result_count": initial_counts.get(sid),
            "executed_logical_pages": sum(row["stratum_id"] == sid and
                row["logical_request_id"] in executed_logical
                for row in state["potential"]),
            "valid_success_pages": sum(row["stratum_id"] == sid and
                per_page[row["logical_request_id"]]["terminal_state"] ==
                    "VALID_SUCCESS" for row in state["potential"]),
            "raw_pmid_occurrences": sum(row["stratum_id"] == sid
                                        for row in occurrences)})
    put("acquisition_completeness_audit.json", {
        "normal_complete": completed,
        "six_valid_first_pages": len(first_success) == 6,
        "remaining_manifest_frozen_before_phase2": True,
        "required_remaining_pages_all_valid": completed,
        "not_required_pages_unexecuted": all(
            per_page[row["logical_request_id"]]["terminal_state"] ==
                "NOT_REQUIRED_BY_COUNT" for row in expansion
                if row["execution_state"] == "NOT_REQUIRED_BY_COUNT"),
        "count_drift_count": int(drift is not None),
        "failure": None if failure is None else {"terminal_state":
            failure.terminal_state, "reason": failure.reason,
            "logical_request_id": failure.page["logical_request_id"]},
        "ordinary_alpha3_21b_handoff_allowed": completed})
    accounting = {"logical_page_requests_executed": len(executed_logical),
        "transport_attempts": transport.transport_attempts,
        "technical_retries": transport.technical_retries,
        "valid_page_responses": transport.valid_responses,
        "invalid_page_responses": transport.invalid_responses,
        "raw_pmid_occurrence_count": len(occurrences),
        "unique_exposed_pmid_count": len(exposure_rows),
        "per_stratum": per_stratum,
        "pubmed_logical_page_requests": len(executed_logical),
        "pubmed_transport_attempts": transport.transport_attempts,
        "pubmed_calls_convention": "transport attempts",
        "pmc_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "builder_calls": 0, "quality_calls": 0}
    put("acquisition_execution_accounting.json", accounting)
    put("fresh_primary_policy_nonadaptation_audit.json", {
        "query_modifications": 0, "date_modifications": 0,
        "new_page_coordinates": 0, "sort_modifications": 0,
        "strata_modifications": 0, "builder_v4_modifications": 0,
        "quality_modifications": 0, "metadata_calls": 0,
        "sampling_performed": False})
    put("builder_v4_nonuse_audit.json", {"builder_calls": 0,
        "builder_execution_started": False})
    put("quality_nonuse_audit.json", {"quality_calls": 0,
        "quality_execution_started": False})
    require(root_hash(A, "search_plan_v24_primary_alpha3_21a_prereg_sha256") ==
            A_ROOT and root_hash(MASTER,
            "search_plan_v24_primary_alpha3_21_master_prereg_sha256") ==
            MASTER_ROOT,
            "HISTORICAL_ROOT_CHANGED_DURING_EXECUTION")
    put("historical_preservation_audit.json", {
        "alpha3_21a_root_unchanged": True,
        "alpha3_21_master_root_unchanged": True,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "deduplication_performed": False,
        "preexisting_seen_exclusion_performed": False,
        "sampling_performed": False,
        "pubmed_metadata_calls": 0, "pmc_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "provider_calls": 0, "llm_calls": 0,
        "fresh_builder_execution_started": False,
        "fresh_quality_execution_started": False,
        "fresh_retrieval_evaluation_started": False})
    put("protocol_compliance_audit.json", {
        "network_scope_pubmed_esearch_only": all(
            row["endpoint"] == ES for row in all_attempts),
        "all_logical_requests_from_frozen_manifest":
            executed_logical <= {row["logical_request_id"]
                                 for row in state["potential"]},
        "first_page_phase_before_remaining_phase": all(
            row["phase"] == "FIRST_PAGE" for row in all_attempts[:sum(
                row["phase"] == "FIRST_PAGE" for row in all_attempts)]),
        "no_network_before_integrity_barrier": True,
        "maximum_transport_attempts_respected": transport.transport_attempts <= 96,
        "no_scientific_query_adaptation": True})
    validation = {"status": "completed" if completed else "failed",
        "alpha3_21a1_classification": classification,
        "alpha3_21a_root_verified": True,
        "alpha3_21_master_root_verified": True,
        "first_page_logical_requests_planned": 6,
        "first_page_logical_requests_executed": sum(
            row["retstart"] == 0 and
            row["logical_request_id"] in executed_logical
            for row in state["first"]),
        "first_page_valid_success_count": len(first_success),
        "remaining_page_required_count": sum(row["execution_state"] ==
            "REQUIRED" for row in expansion),
        "remaining_page_not_required_count": sum(row["execution_state"] ==
            "NOT_REQUIRED_BY_COUNT" for row in expansion),
        "remaining_page_executed_count": sum(row["retstart"] > 0 and
            row["logical_request_id"] in executed_logical
            for row in state["potential"]),
        "total_logical_page_requests_executed": len(executed_logical),
        "total_transport_attempts": transport.transport_attempts,
        "technical_retry_count": transport.technical_retries,
        "valid_page_response_count": transport.valid_responses,
        "invalid_page_response_count": transport.invalid_responses,
        "result_set_count_drift_count": int(drift is not None),
        "raw_pmid_occurrence_count": len(occurrences),
        "unique_exposed_pmid_count": len(exposure_rows),
        "current_attempt_exposure_registry_created": True,
        "alpha3_21_current_attempt_source_exposure_registry_sha256": exposure_sha,
        "historical_seen_registry_unchanged": True,
        "historical_seen_pmid_count": 2545,
        "current_attempt_exposure_does_not_self_exclude": True,
        "deduplication_performed": False,
        "preexisting_seen_exclusion_performed": False,
        "sampling_performed": False,
        "alpha3_21a1_raw_acquisition_corpus_sha256": corpus_sha,
        "pubmed_logical_page_requests": len(executed_logical),
        "pubmed_transport_attempts": transport.transport_attempts,
        "pmc_calls": 0, "builder_calls": 0,
        "quality_calls": 0, "llm_calls": 0, "provider_calls": 0,
        "fresh_builder_execution_started": False,
        "fresh_quality_execution_started": False,
        "fresh_retrieval_evaluation_started": False,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": validation["status"],
        "classification": classification,
        "first_page_valid_success_count": len(first_success),
        "remaining_page_required_count": validation["remaining_page_required_count"],
        "remaining_page_executed_count":
            validation["remaining_page_executed_count"],
        "raw_pmid_occurrence_count": len(occurrences),
        "unique_exposed_pmid_count": len(exposure_rows),
        "next_stage_recommendation": next_stage})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, ROOT_MARKER: root}


def run() -> dict:
    state = preflight()
    transport = Transport(state["retry"])
    return run_with_transport(state, transport)


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
