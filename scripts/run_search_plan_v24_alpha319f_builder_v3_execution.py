#!/usr/bin/env python3
"""Execute exactly the frozen alpha3.19 Builder V3 requests, then offline postchecks."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from scripts import run_search_plan_v24_alpha318b_builder as historical_runner
from scripts import run_search_plan_v24_alpha319e_builder_request_freeze_offline as e
from scripts import run_search_plan_v24_alpha319e1_source_token_authority_audit_offline as e1
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks
from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality


ROOT = e.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19f_builder_v3_execution"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19f_sha256"
E1_SHA = "3a13c2d644f6b7ad48d36cb0f4663783d1780dd00341d9b4679262c0335da035"
E_SHA = e1.E_SHA
REQUEST_SHA = e1.REQUEST_SHA
DOC_SHA = e1.DOC_SHA
ANCHOR_SHA = e1.ANCHOR_SHA
PROVIDER = "DeepSeek"
MODEL = "deepseek-flash"
URL = historical_runner.URL
POSTCHECK_DIR = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline"
CONTRACTS = {
    "builder_transport_retry_contract.json": "6a6033d52530d8dc4c28a7b9cb6c58d8b748eebee817605325e24774d77b32e4",
    "builder_terminal_state_contract.json": "514d53075fe5f5b196c5d916614bd53411b0184adcbda3cae64904f53dbd5348",
    "builder_candidate_identity_contract.json": "d5f1409295fd03b4c1a6622d5f0ce93168582ca6c111c0109f7ee2b4eab7f157",
    "builder_exact_dedup_contract.json": "07edcc089c370faeb4ff653490776cc1e6d8e7afbdbbfbb20c1f16d4540f67db",
    "builder_grounding_precheck_contract.json": "8a46df3d3f42107bd1637dc9e7bcafed0ca763ae46bb745f25c848117a5062fe",
    "builder_leakage_execution_contract.json": "d1e8b692978526bdc2c4a3eb69600534566334426c3ec8c9b50e7803bbd1e12e",
    "quality_source_grouping_contract.json": "049660a71e7f7e85b66b99d0e4d953f3d2a1905dc29cc3ec8d1c8ae39a9c2f76",
}


def require(ok: bool, reason: str):
    if not ok:
        raise RuntimeError(reason)


def put(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def obj(name: str, value):
    put(OUT / name, e.master.canonical(value) + b"\n")


def lines(name: str, values):
    put(OUT / name, b"".join(e.master.canonical(value) + b"\n" for value in values))


def ref(path: Path):
    return {"path": str(path.relative_to(ROOT)), "sha256": e.master.digest(path)}


def root_hash():
    paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != ROOT_MARKER)
    require(not any(path.is_symlink() for path in OUT.rglob("*")), "OUTPUT_SYMLINK_FORBIDDEN")
    return e.master.sha(e.master.canonical([[str(path.relative_to(OUT)), e.master.digest(path)]
                                            for path in paths]))


def preflight():
    require(not OUT.exists(), "ALPHA319F_OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    require(e1.root_hash() == E1_SHA and
            (e1.OUT / e1.ROOT_MARKER).read_text().strip() == E1_SHA and
            e.root_hash() == E_SHA and (e.OUT / e.ROOT_MARKER).read_text().strip() == E_SHA,
            "E_OR_E1_ROOT_MISMATCH")
    require(e.prereg.frozen_root(POSTCHECK_DIR,
                "search_plan_v24_dev_alpha3_18b_prereg_sha256") ==
            historical_runner.PREREG_SHA and
            (POSTCHECK_DIR / "search_plan_v24_dev_alpha3_18b_prereg_sha256").read_text().strip() ==
            historical_runner.PREREG_SHA,
            "FROZEN_POSTCHECK_PREREG_ROOT_MISMATCH")
    for filename, expected in (
        ("alpha3_19_builder_v3_request_manifest.jsonl", REQUEST_SHA),
        ("construction_document_manifest.jsonl", DOC_SHA),
        ("body_anchor_manifest.jsonl", ANCHOR_SHA)):
        marker = filename.removesuffix(".jsonl") + "_sha256"
        require(e.master.digest(e.OUT / filename) == expected and
                (e.OUT / marker).read_text().strip() == expected,
                "FROZEN_MANIFEST_MISMATCH:" + filename)
    require(e.master.digest(e.V3_DIR / "builder_grounding_contract_v3.json") ==
            e.V3_CONTRACT_SHA and
            e.master.digest(e.V3_DIR / "builder_output_schema_v3.json") ==
            e.V3_SCHEMA_SHA and
            e.master.digest(e.ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py") ==
            e.IMPLEMENTATION_SHA and
            e.master.digest(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py") ==
            "cc6623dc75b07dd54d7f4fec2ca71bc1b66ae9ab8741865d8f4b917a7e8fa383" and
            e.master.digest(ROOT / "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py") ==
            "388942dd216a92a54f5dcb6019eca28e690044584c66261d0d096cfd1fa703b2" and
            e.master.digest(ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py") ==
            "48808884c1a6a603908abaa962ab1ef15c4f11257b02a4fa3f93c63077052ce8",
            "FROZEN_V3_SCHEMA_OR_POSTCHECK_IMPLEMENTATION_MISMATCH")
    contracts = {}
    for filename, expected in CONTRACTS.items():
        path = POSTCHECK_DIR / filename
        require(path.is_file() and (not expected or e.master.digest(path) == expected),
                "FROZEN_POSTCHECK_CONTRACT_MISMATCH:" + filename)
        contracts[filename] = e.load(path)
    require(contracts["builder_transport_retry_contract.json"]["automatic_retry"] is False and
            contracts["builder_transport_retry_contract.json"]["known_no_inference_transport_retry_enabled"] is False and
            contracts["builder_terminal_state_contract.json"]["schema_invalid_does_not_stop_later_sources"] is True and
            contracts["builder_leakage_execution_contract.json"]["shared_consecutive_tokens_failure_threshold"] == 8 and
            contracts["builder_leakage_execution_contract.json"]["qualifying_token_jaccard_failure_threshold"] == 0.8 and
            contracts["quality_source_grouping_contract.json"]["cross_source_mixing"] is False,
            "FROZEN_RETRY_OR_POSTCHECK_POLICY_MISMATCH")
    binding = e.load(e.OUT / "builder_provider_binding_alpha3_19.json")
    authority = e.load(e1.OUT / "validation.json")
    requests = e.rows(e.OUT / "alpha3_19_builder_v3_request_manifest.jsonl")
    docs = {row["source_token"]: row for row in e.rows(e.OUT / "construction_document_manifest.jsonl")}
    anchors = e.rows(e.OUT / "body_anchor_manifest.jsonl")
    source_rows = {row["opaque_source_token"]: row for row in
                   e.rows(e.d1.OUT / "final_construction_source_manifest.jsonl")}
    terminal = e.rows(e.OUT / "source_preparation_terminal_states.jsonl")
    schema = e.load(e.V3_DIR / "builder_output_schema_v3.json")["schema"]
    require(binding["provider"] == PROVIDER and binding["model"] == MODEL and
            binding["thinking"] == {"type": "enabled"} and
            binding["reasoning_effort"] == "high" and
            binding["response_format"] == {"type": "json_object"} and
            authority["status"] == "completed" and
            authority["existing_builder_request_manifest_execution_eligible"] is True and
            authority["identifiable_source_information_leak_count"] == 0 and
            len(requests) == len(docs) == 14 and len(anchors) == 545 and
            len(source_rows) == len(terminal) == 15 and
            [row["source_token"] for row in requests] ==
                [row["source_token"] for row in terminal if row["state"] == "BUILDER_REQUEST_READY"] and
            schema["properties"]["candidates"]["items"]["properties"][
                "construction_evidence_span"]["properties"]["source_field"]["enum"] == ["body"] and
            schema["properties"]["candidates"]["minItems"] == 0 and
            schema["properties"]["candidates"]["maxItems"] == 3,
            "FROZEN_REQUEST_AUTHORITY_OR_CARDINALITY_MISMATCH")
    anchor_by_token = {}
    for row in anchors:
        anchor_by_token.setdefault(row["source_token"], []).append(row)
    for ordinal, row in enumerate(requests, 1):
        token = row["source_token"]
        document = docs[token]
        require(row["ordinal"] == ordinal and row["provider"] == PROVIDER and
                row["model"] == MODEL and row["request"]["model"] == MODEL and
                row["request"]["thinking"] == {"type": "enabled"} and
                row["request"]["reasoning_effort"] == "high" and
                row["request"]["response_format"] == {"type": "json_object"} and
                row["request_sha256"] == e.master.sha(e.master.canonical(row["request"])) and
                row["document_sha256"] == document["document_sha256"] ==
                    e.master.digest(e.OUT / document["document_path"]) and
                row["body_anchor_set_sha256"] ==
                    e.master.sha(e.master.canonical(anchor_by_token[token])) and
                row["builder_grounding_contract_version"] == "BuilderGroundingContractV3" and
                row["builder_output_schema_version"] == "PropositionBuilderOutputV3" and
                token in source_rows and
                row["request"]["messages"][1]["content"].startswith("Source token: " + token + "\n"),
                "FROZEN_REQUEST_DOCUMENT_ANCHOR_OR_ORDER_MISMATCH:" + str(ordinal))
    return {"requests": requests, "docs": docs, "sources": source_rows,
            "schema": schema, "contracts": contracts, "binding": binding}


def freeze_preflight(state):
    OUT.mkdir()
    obj("alpha3_19e1_root_verification.json", {"root_sha256": E1_SHA,
        "verified": e1.root_hash() == E1_SHA})
    obj("alpha3_19e_root_verification.json", {"root_sha256": E_SHA,
        "verified": e.root_hash() == E_SHA,
        "construction_document_manifest_sha256": DOC_SHA,
        "body_anchor_manifest_sha256": ANCHOR_SHA})
    obj("builder_request_manifest_verification.json", {"manifest": ref(e.OUT /
        "alpha3_19_builder_v3_request_manifest.jsonl"), "verified": True,
        "request_count": 14, "request_regeneration_used": False})
    obj("builder_execution_preflight.json", {"status": "PASS",
        "planned_builder_sources": 14, "planned_builder_requests": 14,
        "builder_grounding_contract": ref(e.V3_DIR / "builder_grounding_contract_v3.json"),
        "builder_output_schema": ref(e.V3_DIR / "builder_output_schema_v3.json"),
        "postcheck_contracts": [ref(POSTCHECK_DIR / name) for name in CONTRACTS],
        "all_upstream_hashes_verified_before_provider_access": True,
        "provider_binding_verified_before_access": True})
    obj("builder_execution_order.json", {"ordering": "frozen manifest ordinal",
        "calls": [{"ordinal": row["ordinal"], "source_token": row["source_token"],
                    "request_sha256": row["request_sha256"]} for row in state["requests"]]})
    obj("builder_provider_binding_verification.json", {"binding": ref(e.OUT /
        "builder_provider_binding_alpha3_19.json"), "provider": PROVIDER,
        "model": MODEL, "thinking": "enabled", "reasoning_effort": "high",
        "api_surface": "Chat Completions", "response_format": "json_object",
        "temperature": "omitted", "top_p": "omitted", "stream": "omitted as frozen request",
        "fresh_independent_context_per_source": True,
        "automatic_retry": False, "fallback": False})
    obj("source_token_authority_binding.json", {"e1_root_sha256": E1_SHA,
        "classification": "LATER_INSTRUCTION_INTRODUCED_PROSPECTIVE_POLICY_DRIFT",
        "token_role": "OPAQUE_NONSEMANTIC_RESPONSE_BINDING_HANDLE",
        "identifiable_source_information_leak_count": 0,
        "literal_private_token_visibility_count": 14})


def error_code(response: httpx.Response) -> str:
    if response.status_code in (400, 404):
        try:
            error = response.json().get("error", {})
            message = (str(error.get("message", "")) + " " +
                       str(error.get("code", "")) + " " + str(error.get("type", ""))).lower()
        except (ValueError, AttributeError):
            message = ""
        if "model" in message and any(word in message for word in
                ("not found", "does not exist", "invalid", "unsupported", "unknown", "unavailable")):
            return "BUILDER_PROVIDER_BINDING_FAILURE"
    return "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS"


def freeze_failure(code: str, ordinal: int | None, detail: str, attempts: int,
                   scientific_events: int):
    if not OUT.is_dir():
        return
    obj("runtime_failure.json", {"failure_code": code, "request_ordinal": ordinal,
        "detail": detail, "requests_attempted": attempts,
        "scientific_inference_events_confirmed": scientific_events,
        "later_sources_not_executed": True, "scientific_retry": False,
        "next_stage_recommendation": "AUDIT_ALPHA3_19F_RUNTIME_FAILURE_OFFLINE"})
    obj("scientific_state_safety_audit.json", {"provider": PROVIDER, "model": MODEL,
        "deepseek_calls": attempts, "confirmed_builder_scientific_inference_events": scientific_events,
        "quality_calls": 0, "openai_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0, "scientific_builder_retry_used": False,
        "historical_assets_modified": False})
    obj("validation.json", {"status": "failed", "failure_code": code,
        "alpha3_19e1_root_verified": e1.root_hash() == E1_SHA,
        "builder_request_manifest_verified": e.master.digest(e.OUT /
            "alpha3_19_builder_v3_request_manifest.jsonl") == REQUEST_SHA,
        "planned_builder_sources": 14, "planned_builder_requests": 14,
        "builder_requests_attempted": attempts,
        "builder_scientific_inference_events_confirmed": scientific_events,
        "actual_future_quality_scientific_call_count": None,
        "next_stage_recommendation": "AUDIT_ALPHA3_19F_RUNTIME_FAILURE_OFFLINE"})
    obj("summary.json", {"status": "failed", "failure_code": code,
        "request_ordinal": ordinal, "requests_attempted": attempts,
        "scientific_inference_events_confirmed": scientific_events,
        "quality_input_manifest_created": False,
        "next_stage_recommendation": "AUDIT_ALPHA3_19F_RUNTIME_FAILURE_OFFLINE"})
    put(OUT / ROOT_MARKER, (root_hash() + "\n").encode())


def execute_provider(state, secret):
    raw_rows, transport_rows, terminal_rows, validation_rows, binding_rows, candidate_rows = (
        [], [], [], [], [], [])
    attempts = scientific_events = 0
    for row in state["requests"]:
        ordinal, token = row["ordinal"], row["source_token"]
        request = row["request"]
        require(e.master.sha(e.master.canonical(request)) == row["request_sha256"],
                "FROZEN_REQUEST_HASH_CHANGED_BEFORE_NETWORK")
        obj(f"attempts/{ordinal:02d}.json", {"ordinal": ordinal, "source_token": token,
            "request_sha256": row["request_sha256"], "provider": PROVIDER,
            "model": MODEL, "attempt_number": 1,
            "committed_before_network": True, "started_unix_time": time.time()})
        attempts += 1
        print(f"ALPHA319F_BUILDER_STARTED {ordinal}/14", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={"Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"}, content=e.master.canonical(request))
        except Exception as exc:
            obj(f"inference_status_events/{ordinal:02d}.json", {"ordinal": ordinal,
                "source_token": token, "scientific_inference_status": "UNKNOWN_AMBIGUOUS",
                "reason": "transport exception"})
            freeze_failure("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal,
                           type(exc).__name__ + ":" + str(exc), attempts, scientific_events)
            return False
        raw_path = OUT / "raw_provider_responses" / f"{ordinal:02d}.bin"
        put(raw_path, response.content)
        transport = {"ordinal": ordinal, "source_token": token,
            "request_sha256": row["request_sha256"], "provider": PROVIDER,
            "model": MODEL, "attempt_number": 1,
            "http_status": response.status_code, "raw_response_sha256": e.master.sha(response.content),
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "elapsed_seconds": response.elapsed.total_seconds(), "technical_retries": 0}
        obj(f"transport_events/{ordinal:02d}.json", transport)
        transport_rows.append(transport)
        if response.status_code != 200:
            code = error_code(response)
            obj(f"inference_status_events/{ordinal:02d}.json", {"ordinal": ordinal,
                "source_token": token,
                "scientific_inference_status": "KNOWN_NO_INFERENCE" if code ==
                    "BUILDER_PROVIDER_BINDING_FAILURE" else "UNKNOWN_AMBIGUOUS",
                "reason": code})
            freeze_failure(code, ordinal, "HTTP_" + str(response.status_code),
                           attempts, scientific_events)
            return False
        try:
            envelope = response.json()
            choices = envelope["choices"]
            require(isinstance(choices, list) and len(choices) == 1,
                    "PROVIDER_CHOICES_INVALID")
            content = choices[0]["message"]["content"]
            finish = choices[0]["finish_reason"]
            require(isinstance(content, str) and isinstance(finish, str),
                    "PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
            obj(f"inference_status_events/{ordinal:02d}.json", {"ordinal": ordinal,
                "source_token": token, "scientific_inference_status": "UNKNOWN_AMBIGUOUS",
                "reason": "provider envelope invalid"})
            freeze_failure("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal,
                           type(exc).__name__ + ":" + str(exc), attempts, scientific_events)
            return False
        scientific_events += 1
        obj(f"inference_status_events/{ordinal:02d}.json", {"ordinal": ordinal,
            "source_token": token, "scientific_inference_status": "COMPLETED",
            "response_sha256": e.master.sha(response.content)})
        raw = {"ordinal": ordinal, "source_token": token,
            "request_sha256": row["request_sha256"], "provider": PROVIDER,
            "model": MODEL, "transport": transport,
            "model_content_raw": content, "finish_reason": finish,
            "provider_response_id": envelope.get("id"), "usage": envelope.get("usage"),
            "scientific_inference_confirmed": True}
        obj(f"raw_events/{ordinal:02d}.json", raw)
        raw_rows.append(raw)
        try:
            if finish != "stop":
                raise ValueError("BUILDER_V3_RESPONSE_INCOMPLETE_FINISH:" + finish)
            parsed = checks.validate_builder_response(content.encode(), token, state["schema"])
        except ValueError as exc:
            try:
                token_echo = json.loads(content).get("source_record_token")
                exact_echo = token_echo == token
            except (ValueError, AttributeError):
                exact_echo = None
            validation = {"ordinal": ordinal, "source_token": token,
                "status": "BUILDER_V3_RESPONSE_INVALID", "reason": str(exc)}
            terminal = {"ordinal": ordinal, "source_token": token,
                "terminal_state": "BUILDER_V3_RESPONSE_INVALID"}
            binding = {"ordinal": ordinal, "source_token": token,
                "exact_token_echo_valid": exact_echo,
                "binding_state": "INVALID_SCHEMA_OR_TOKEN"}
        else:
            validation = {"ordinal": ordinal, "source_token": token,
                "status": "V3_SCHEMA_VALID", "candidate_count": len(parsed["candidates"])}
            terminal = {"ordinal": ordinal, "source_token": token,
                "terminal_state": "BUILDER_VALID_NONZERO" if parsed["candidates"] else
                                  "BUILDER_VALID_ZERO"}
            binding = {"ordinal": ordinal, "source_token": token,
                "exact_token_echo_valid": True, "binding_state": "EXACT_MATCH"}
            candidate_rows.extend({"ordinal": ordinal, "source_token": token,
                "raw_array_position": position, "candidate": candidate,
                "state": "RAW_BUILDER_V3_CANDIDATE"}
                for position, candidate in enumerate(parsed["candidates"]))
        validation_rows.append(validation)
        terminal_rows.append(terminal)
        binding_rows.append(binding)
        obj(f"source_events/{ordinal:02d}.json", {"raw": raw, "validation": validation,
            "terminal": terminal, "token_binding": binding})
        print(f"ALPHA319F_BUILDER_FROZEN {ordinal}/14 {terminal['terminal_state']}", flush=True)
    lines("builder_raw_provider_responses.jsonl", raw_rows)
    lines("builder_transport_provenance.jsonl", transport_rows)
    lines("builder_source_terminal_states.jsonl", terminal_rows)
    lines("builder_response_schema_validation.jsonl", validation_rows)
    lines("builder_source_token_binding_audit.jsonl", binding_rows)
    lines("raw_builder_candidate_manifest.jsonl", candidate_rows)
    obj("all_builder_outputs_freeze_barrier.json", {"all_14_terminal_states_frozen": True,
        "raw_responses_frozen_before_postchecks": True,
        "schema_validation_frozen_before_postchecks": True,
        "raw_candidate_arrays_frozen_before_postchecks": True,
        "request_count": 14, "raw_candidate_count": len(candidate_rows),
        "raw_manifest_sha256": e.master.digest(OUT / "builder_raw_provider_responses.jsonl"),
        "terminal_manifest_sha256": e.master.digest(OUT / "builder_source_terminal_states.jsonl")})
    return {"raw": raw_rows, "transport": transport_rows,
            "terminal": terminal_rows, "validation": validation_rows,
            "binding": binding_rows, "candidates": candidate_rows,
            "scientific_events": scientific_events, "attempts": attempts}


def postcheck(state, execution):
    candidates_by_token = {}
    for record in execution["candidates"]:
        candidates_by_token.setdefault(record["source_token"], []).append(record["candidate"])
    identity_rows, grounding_rows, leakage_rows, progression_rows, survivors, groups = (
        [], [], [], [], [], [])
    duplicate_by_source = []
    for request in state["requests"]:
        token, ordinal = request["source_token"], request["ordinal"]
        raw_candidates = candidates_by_token.get(token, [])
        if not raw_candidates:
            continue
        document_row = state["docs"][token]
        doc_path = e.OUT / document_row["document_path"]
        require(e.master.digest(doc_path) == document_row["document_sha256"],
                "FROZEN_CONSTRUCTION_DOCUMENT_CHANGED")
        document = json.loads(doc_path.read_bytes())
        source = state["sources"][token]
        jats_path = e.d.OUT / source["normalized_jats_path"]
        require(e.master.digest(jats_path) == source["normalized_jats_sha256"],
                "FROZEN_CANONICAL_JATS_CHANGED")
        private = checks.private_identity_from_jats(jats_path.read_bytes(),
            source["pmid"], source["pmcid"], source.get("doi"))
        parsed = {"source_record_token": token, "candidates": raw_candidates}
        checked = checks.precheck_candidates(parsed, document, private["title_1"])
        duplicate_by_source.append({"source_ordinal": ordinal, "source_token": token,
            "raw_candidate_count": len(raw_candidates),
            "exact_duplicates_removed": checked["exact_duplicate_candidates_removed"]})
        for record in checked["candidate_records_private"]:
            core = {"source_ordinal": ordinal, "source_token": token, **record}
            identity_rows.append(core)
            grounding_rows.append({"source_ordinal": ordinal, "source_token": token,
                "candidate_id": record["candidate_id"],
                "state": record["grounding_reference_state"],
                "reason": record.get("grounding_reason"),
                "private_anchor_id": record.get("private_anchor_id")})
            leakage_rows.append({"source_ordinal": ordinal, "source_token": token,
                "candidate_id": record["candidate_id"],
                "state": record["leakage_gate_state"]})
            progression_rows.append({"source_ordinal": ordinal, "source_token": token,
                "candidate_id": record["candidate_id"],
                "BUILDER_SCHEMA_STATE": "V3_SCHEMA_VALID",
                "CANDIDATE_ID_STATE": record["deterministic_id_state"],
                "EXACT_DUPLICATE_STATE": record["exact_dedup_state"],
                "BODY_GROUNDING_STATE": record["grounding_reference_state"],
                "LEXICAL_LEAKAGE_STATE": record["leakage_gate_state"]})
        group_survivors = checked["survivors_private"]
        for item in group_survivors:
            survivors.append({"source_ordinal": ordinal, "source_token": token,
                "candidate_id": item["candidate_id"],
                "candidate_payload_sha256": item["candidate_payload_sha256"],
                "candidate": item["candidate"],
                "state": "QUALITY_ADJUDICATION_INPUT_CANDIDATE"})
        if group_survivors:
            groups.append({"source_ordinal": ordinal, "source_token": token,
                "source_group_id": quality.source_group_id(token),
                "candidate_count": len(group_survivors),
                "candidate_ids": [item["candidate_id"] for item in group_survivors]})
    raw_count = len(execution["candidates"])
    duplicate_count = sum(row["exact_duplicates_removed"] for row in duplicate_by_source)
    grounded = [row for row in grounding_rows if row["state"] == "GROUNDING_REFERENCE_VALID"]
    grounding_failed = len(grounding_rows) - len(grounded)
    leakage_evaluated = [row for row in leakage_rows if row["state"] in
                         ("LEXICAL_LEAKAGE_FAILED", "LEXICAL_LEAKAGE_PASSED")]
    leakage_failed = sum(row["state"] == "LEXICAL_LEAKAGE_FAILED" for row in leakage_evaluated)
    require(raw_count - duplicate_count == len(identity_rows) == len(grounding_rows) ==
            len(leakage_rows) == len(progression_rows) and
            len(leakage_evaluated) == len(grounded) and
            len(groups) <= 14 and len(survivors) <= len(leakage_evaluated),
            "POSTCHECK_ACCOUNTING_INVARIANT_FAILED")
    lines("candidate_identity_manifest.jsonl", identity_rows)
    obj("exact_within_source_duplicate_audit.json", {"raw_candidate_count": raw_count,
        "unique_after_exact_dedup": len(identity_rows),
        "exact_duplicates_removed": duplicate_count,
        "per_source": duplicate_by_source, "semantic_deduplication_used": False})
    lines("body_grounding_audit.jsonl", grounding_rows)
    obj("body_grounding_summary.json", {"evaluated": len(grounding_rows),
        "body_grounding_pass_count": len(grounded),
        "body_grounding_failure_count": grounding_failed,
        "body_only_grounding_enforced": True,
        "abstract_reference_repaired": False})
    lines("lexical_leakage_audit.jsonl", leakage_rows)
    obj("lexical_leakage_summary.json", {"lexical_leakage_denominator": len(leakage_evaluated),
        "lexical_leakage_failure_count": leakage_failed,
        "shared_consecutive_tokens_threshold": 8,
        "qualifying_token_jaccard_threshold": 0.8,
        "leakage_not_run_after_grounding_failure": True})
    lines("candidate_state_progression.jsonl", progression_rows)
    lines("quality_input_candidate_manifest.jsonl", survivors)
    lines("quality_source_group_manifest.jsonl", groups)
    obj("future_quality_call_budget.json", {"quality_input_candidate_count": len(survivors),
        "quality_source_group_count": len(groups),
        "actual_future_quality_scientific_call_count": len(groups),
        "maximum_future_quality_calls": 14,
        "formula": "one future Quality inference per nonempty original source group",
        "quality_requests_constructed": 0, "quality_calls": 0,
        "future_quality_calls_authorized_by_this_stage": False})
    return {"raw_count": raw_count, "duplicates": duplicate_count,
            "grounding_pass": len(grounded), "grounding_fail": grounding_failed,
            "leakage_denominator": len(leakage_evaluated), "leakage_fail": leakage_failed,
            "quality_candidates": len(survivors), "quality_groups": len(groups)}


def finalize(state, execution, post):
    states = [row["terminal_state"] for row in execution["terminal"]]
    zero, nonzero, invalid = (states.count("BUILDER_VALID_ZERO"),
                             states.count("BUILDER_VALID_NONZERO"),
                             states.count("BUILDER_V3_RESPONSE_INVALID"))
    require(zero + nonzero + invalid == 14 and execution["scientific_events"] == 14,
            "BUILDER_TERMINAL_ACCOUNTING_INVALID")
    next_stage = ("PREREGISTER_ALPHA3_19G_QUALITY_REQUEST_FREEZE"
                  if post["quality_groups"] else "INTERPRET_ZERO_QUALITY_INPUT_AFTER_ALPHA3_19F")
    obj("alpha3_18_contamination_nonuse_audit.json", {
        "historical_builder_candidates_used": 0, "historical_quality_results_used": 0,
        "alpha3_18_scientific_output_read_for_alpha3_19_decisions": False,
        "frozen_generic_contracts_reused": True})
    obj("search_plan_firewall_audit.json", {"search_plan_queries_accessed": False,
        "retrieval_outcomes_accessed": False, "development_labels_accessed": False,
        "known_paper_id_checks": False})
    obj("deepseek_flash_execution_audit.json", {"provider": PROVIDER, "model": MODEL,
        "requests_attempted": 14, "fallback_to_deepseek_v4_pro": False,
        "independent_context_per_source": True,
        "other_provider_calls": 0})
    obj("builder_execution_accounting.json", {"planned_builder_sources": 14,
        "planned_builder_requests": 14, "builder_requests_attempted": 14,
        "builder_scientific_inference_events": 14,
        "builder_transport_retries": 0, "builder_valid_zero": zero,
        "builder_valid_nonzero": nonzero, "builder_response_invalid": invalid,
        "builder_raw_candidate_count": post["raw_count"]})
    obj("historical_inference_accounting.json", {
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "alpha3_19_builder_scientific_inference_events": 14,
        "historical_events_erased_or_relabelled": False})
    obj("protocol_compliance_audit.json", {"alpha3_19e1_root_verified": True,
        "alpha3_19e_root_verified": True, "builder_request_manifest_verified": True,
        "planned_builder_sources": 14, "planned_builder_requests": 14,
        "provider": PROVIDER, "model": MODEL,
        "deepseek_v4_pro_fallback_used": False,
        "opaque_source_token_authority_bound": True,
        "identifiable_source_information_leak_count": 0,
        "builder_request_regeneration_used": False,
        "source_topup_used": False, "scientific_builder_retry_used": False,
        "body_only_grounding_enforced": True,
        "frozen_leakage_rules_used": True,
        "quality_requests_constructed": False,
        "quality_calls": 0, "ncbi_calls": 0, "openai_calls": 0,
        "non_deepseek_network_calls": 0})
    obj("scientific_state_safety_audit.json", {"provider": PROVIDER, "model": MODEL,
        "deepseek_calls": 14, "builder_scientific_inference_events": 14,
        "quality_calls": 0, "openai_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0, "source_topup_used": False,
        "historical_assets_modified": False})
    obj("historical_preservation_audit.json", {"alpha3_19e1_root_unchanged":
        e1.root_hash() == E1_SHA, "alpha3_19e_root_unchanged": e.root_hash() == E_SHA,
        "request_manifest_unchanged": e.master.digest(e.OUT /
            "alpha3_19_builder_v3_request_manifest.jsonl") == REQUEST_SHA,
        "construction_document_manifest_unchanged": e.master.digest(e.OUT /
            "construction_document_manifest.jsonl") == DOC_SHA,
        "body_anchor_manifest_unchanged": e.master.digest(e.OUT /
            "body_anchor_manifest.jsonl") == ANCHOR_SHA,
        "historical_assets_modified": False})
    validation = {"status": "completed", "alpha3_19e1_root_verified": True,
        "alpha3_19e_root_verified": True, "builder_request_manifest_verified": True,
        "planned_builder_sources": 14, "planned_builder_requests": 14,
        "builder_requests_attempted": 14, "builder_scientific_inference_events": 14,
        "builder_transport_retries": 0, "builder_valid_zero": zero,
        "builder_valid_nonzero": nonzero, "builder_response_invalid": invalid,
        "builder_raw_candidate_count": post["raw_count"],
        "source_token_binding_failures": sum(row["exact_token_echo_valid"] is False
            for row in execution["binding"]),
        "identifiable_source_information_leak_count": 0,
        "exact_duplicates_removed": post["duplicates"],
        "body_grounding_pass_count": post["grounding_pass"],
        "body_grounding_failure_count": post["grounding_fail"],
        "lexical_leakage_denominator": post["leakage_denominator"],
        "lexical_leakage_failure_count": post["leakage_fail"],
        "quality_input_candidate_count": post["quality_candidates"],
        "quality_source_group_count": post["quality_groups"],
        "actual_future_quality_scientific_call_count": post["quality_groups"],
        "provider": PROVIDER, "model": MODEL,
        "deepseek_v4_pro_fallback_used": False,
        "source_topup_used": False, "scientific_builder_retry_used": False,
        "alpha3_19_builder_scientific_inference_events": 14,
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "deepseek_calls": 14, "quality_calls": 0, "openai_calls": 0,
        "ncbi_calls": 0, "non_deepseek_network_calls": 0,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False}
    obj("validation.json", validation)
    obj("summary.json", {"status": "completed",
        "builder_source_states": {"valid_zero": zero, "valid_nonzero": nonzero,
                                  "invalid": invalid},
        "raw_candidate_count": post["raw_count"],
        "quality_input_candidate_count": post["quality_candidates"],
        "quality_source_group_count": post["quality_groups"],
        "actual_future_quality_scientific_call_count": post["quality_groups"],
        "quality_requests_constructed": False, "quality_calls": 0,
        "next_stage_recommendation": next_stage})
    require(e1.root_hash() == E1_SHA and e.root_hash() == E_SHA,
            "UPSTREAM_ROOT_CHANGED_AFTER_EXECUTION")
    put(OUT / ROOT_MARKER, (root_hash() + "\n").encode())
    print(json.dumps({"status": "completed", "root_sha256":
          (OUT / ROOT_MARKER).read_text().strip(),
          "builder_scientific_inference_events": 14,
          "raw_candidates": post["raw_count"],
          "quality_input_candidates": post["quality_candidates"],
          "future_quality_calls": post["quality_groups"]}, sort_keys=True), flush=True)


def main():
    state = preflight()
    secret = historical_runner.key()
    freeze_preflight(state)
    execution = execute_provider(state, secret)
    if execution is False:
        return
    try:
        post = postcheck(state, execution)
        finalize(state, execution, post)
    except Exception as exc:
        if not (OUT / ROOT_MARKER).exists():
            freeze_failure("POST_BUILDER_DETERMINISTIC_PROCESSING_FAILURE", None,
                           type(exc).__name__ + ":" + str(exc), 14, 14)
        raise


if __name__ == "__main__":
    main()
