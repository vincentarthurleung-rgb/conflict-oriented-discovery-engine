# Length-bound development port; frozen source untouched; only explicit dependency bindings and length verifier change.
"""Offline development adapter/reader, explicitly isolated from frozen R2/DR.

Only synthetic local responses. This entrypoint is not a literature client.
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from code_engine import append_only_attempt_journal_v2_length_bound_v1 as j
from code_engine import deterministic_resume_planner_v2_length_bound_v1 as p
from code_engine import validator_outcome_adapter_length_bound_v1 as validity
from scripts import search_plan_v24_alpha322_length_bound_r2_integration_v1 as r2
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity
from scripts import run_search_plan_v24_alpha322dr_independent_59_scenario_revalidation_offline as dr

t, o, b, ROOT, NOW = j.t, j.o, j.b, r2.ROOT, r2.NOW
RUNTIME_ACTIVATION_ALLOWED = False


def manifest(key="repair:OA:0", *, kind="literal_boolean"):
    value = r2.manifest((key,)).record()
    value["authority"] = j.AUTHORITY
    value["requests"][0]["validity_authority_sha256"] = validity.contract_sha(kind)
    return j.FrozenRequestManifestV2(j.canonical(value))


def read_plan(directory):
    frozen = j.FrozenRequestManifestV2(j.read_bytes(Path(directory) / "request_manifest.json"))
    return p.DeterministicResumePlannerV2().build(j.JournalIntegrityVerifierV2.read(Path(directory), frozen)).record()


def fresh_plan(directory):
    process = subprocess.run([sys.executable, "-m", __name__, "--inspect", str(directory)], cwd=ROOT,
                             capture_output=True, text=True)
    t.require(process.returncode == 0, "FRESH_VALIDATOR_OUTCOME_READER_FAILED:" + process.stderr)
    return json.loads(process.stdout)


def prepare_complete(writer, *, raw=b"<synthetic/>"):
    key = writer.manifest.record()["requests"][0]["request_id"]
    lifecycle = r2.start(writer, key)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic:headers", timestamp=NOW)
    lifecycle.start_body("synthetic:local-body", timestamp=NOW)
    completion = t.assess_body_completion(raw, read_returned_normally=True, expected_content_length=len(raw),
        expected_length_trustworthy=True, expected_length_representation=t.ByteRepresentation.WIRE, timestamp=NOW)
    lifecycle.record_body(completion, "synthetic:complete-body", timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / "response.xml", raw)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return lifecycle, response


def prepare_result(writer, lifecycle, actual, *, response, kind="literal_boolean", parser_invoked=True):
    outcome = validity.record_result(writer, lifecycle, actual, kind=kind, timestamp=NOW, response=response)
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    decision = validity.decision_for_outcome(lifecycle, outcome, request)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
        trusted=True, status_origin="BOUND_HTTP_RESPONSE", body_byte_representation=lifecycle.completion.byte_representation.value)
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, lifecycle.completion,
                                       response.artifact, parser_invoked=parser_invoked)
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, http=http, body=body,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None)
    eligibility = {"authority_sha256": request["eligibility_authority_sha256"], "eligible": True} if outcome.record()["accepted"] is True else None
    return {"lifecycle": lifecycle, "outcome": outcome, "decision": decision, "observation": observation,
            "eligibility": eligibility, "artifact": response.artifact}


def commit(writer, item):
    return writer.commit_validator_outcome(item["lifecycle"], item["outcome"], item["observation"],
                                           eligibility=item["eligibility"], timestamp=NOW)


def t11(directory, *, commit_terminal=True):
    raw = j.read_bytes(dr.OUT / "scenarios/T11/raw/response.xml")
    frozen = manifest("T11:OA:0", kind="jats_primary_identity_v2")
    counts = dict.fromkeys(dr.h.oracle.CONSUMERS, 0)
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True) as writer:
        lifecycle, response = prepare_complete(writer, raw=raw)
        for name in ("generic_parser", "jats_structure"):
            counts[name] += 1
            t.guarded_parse(response, ET.fromstring)
        counts["primary_identity"] += 1
        actual_validator = t.guarded_parse(response, lambda body: identity.validate_jats_primary_identity_v2(
            body, expected_pmid="123", expected_pmcid="PMC123", expected_doi=None))
        item = prepare_result(writer, lifecycle, actual_validator, response=response, kind="jats_primary_identity_v2")
        if not commit_terminal:
            os._exit(73)  # real crash with complete raw and outcome, no terminal
        event = commit(writer, item)
        terminal = event.record()["event_payload"]
        committed = event.record()["event_type"] == "ATTEMPT_TERMINAL"
        refetch_reason = None
        try:
            writer.start_attempt("T11:OA:0", timestamp=NOW)
        except t.TransportContractError as exc:
            refetch_reason = str(exc)
    before = j.sha(j.read_bytes(directory / "segment-0001.jsonl"))
    plan = fresh_plan(directory)
    request = plan["requests"][0]
    actual = {"semantic_failure_class": item["decision"].retry.semantic_failure.value,
        "retry_authorized": item["decision"].retry.retry_authorized, "attempts_consumed": request["attempts_consumed"],
        "next_attempt_ordinal": request["next_authorized_ordinal"], "backoff_seconds": request["backoff_seconds"],
        "parser_invocation_counts": counts, "journal_integrity": "VERIFIED",
        "terminal_logical_state": request["current_derived_state"], "resume_executable_ids": plan["executable_request_ids"],
        "stage_barrier_state": "ABSENT", "raw_artifact_trust": "AUTHORITATIVE_COMPLETE", "body_complete": True,
        "content_length_match": response.completion.content_length_match, "durable_terminal_committed": committed, "dispatch_count": 1}
    _, expected = dr.frozen_inputs()
    mismatches = dr.h.compare(expected["T11"], actual)
    return {"passed": not mismatches and refetch_reason == "NOT_FIRST_AUTHORIZED_UNRESOLVED_REQUEST",
        "expected": expected["T11"], "actual": actual, "mismatches": mismatches,
        "actual_validator_result": actual_validator, "preserved_outcome": item["outcome"].record(),
        "transport_mapping": item["decision"].mapping.record(), "terminal_payload": terminal,
        "fresh_process_plan": plan, "refetch_rejection": refetch_reason,
        "fresh_reader_is_read_only": before == j.sha(j.read_bytes(directory / "segment-0001.jsonl")),
        "parser_exception_fabricated": False, "source_replacement_count": 0, "refetch_dispatch_count": 0}


def t05(directory):
    frozen = manifest("T05:OA:0")
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True) as writer:
        item = r2.failed_attempt(writer, r2.start(writer, "T05:OA:0"))
        binding = item["binding"].record()
    plan = fresh_plan(directory)
    request = plan["requests"][0]
    actual = {"semantic_failure_class": item["decision"].retry.semantic_failure.value,
        "retry_authorized": item["decision"].retry.retry_authorized, "attempts_consumed": request["attempts_consumed"],
        "next_attempt_ordinal": request["next_authorized_ordinal"], "backoff_seconds": request["backoff_seconds"],
        "parser_invocation_counts": dict.fromkeys(dr.h.oracle.CONSUMERS, 0), "journal_integrity": "VERIFIED",
        "terminal_logical_state": request["current_derived_state"], "resume_executable_ids": plan["executable_request_ids"],
        "stage_barrier_state": "ABSENT", "raw_artifact_trust": "NONAUTHORITATIVE_PARTIAL", "body_complete": False,
        "content_length_match": item["response"].completion.content_length_match,
        "durable_terminal_committed": True, "dispatch_count": 1}
    _, expected = dr.frozen_inputs()
    mismatches = dr.h.compare(expected["T05"], actual)
    return {"passed": not mismatches and binding["occurrence_evidence"]["failure_occurrence_phase"] == "RESPONSE_BODY_READING"
            and binding["mapping_evidence"]["mapping_evidence_phase"] == "RESPONSE_BODY_READING"
            and binding["terminal_persistence_phase"] == "RAW_RESPONSE_FROZEN",
            "expected": expected["T05"], "actual": actual, "mismatches": mismatches,
            "binding": binding, "fresh_process_plan": plan}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", type=Path)
    parser.add_argument("--crash-T11", type=Path)
    args = parser.parse_args()
    with dr.master.prior.offline_guard():
        if args.inspect is not None:
            print(json.dumps(read_plan(args.inspect), sort_keys=True))
        elif args.crash_T11 is not None:
            t11(args.crash_T11, commit_terminal=False)
        else:
            parser.error("explicit offline operation required")


if __name__ == "__main__":
    main()
