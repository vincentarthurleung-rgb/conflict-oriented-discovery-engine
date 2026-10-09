#!/usr/bin/env python3
"""Read frozen T05, freeze a versioned repair DESIGN, then stop.

No transport, fault injection, repair implementation, journal append, scientific
parsing or production wiring. Existing verification helpers are read-only.
Proposed fixtures/validators are descriptions, never executed runtime code.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from scripts import run_search_plan_v24_alpha322d_independent_fault_injection_offline as d
from scripts import search_plan_v24_alpha322r0_repair_fixture_specifications as fixtures


ROOT, MASTER, C, A, B = d.ROOT, d.master.OUT, d.upstream.OUT, d.upstream.prior.prior.OUT, d.upstream.prior.OUT
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22r0_cross_component_phase_binding_repair_design_offline"
UNSEALED_FAILURE = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22r0_cross_component_phase_binding_repair_design_offline_unsealed_freeze_failure_01"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22r0_sha256"
CLASSIFICATION = "VERSIONED_CROSS_COMPONENT_PHASE_BINDING_REPAIR_DESIGN_FROZEN"
CAUSE = "JOURNAL_FAILURE_PHASE_AND_PERSISTENCE_PHASE_CONFLATION"
NEXT = "IMPLEMENT_ALPHA3_22R1_VERSIONED_PHASE_BINDING_REPAIR_OFFLINE"
TEST = ROOT / "tests/test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"
D_SHA = "e265bb83e8b169fa18b1adb2e0b9ca39e1c0d85908916fb8f365028371bdbadc"
EVIDENCE_SHA = "78a9d078ad8baaeb2ceec06e5d0ef7f794465d7645b6b825885f872e77f7392a"
BUNDLE_SHA = "4fe51b934742f4e352e5e78cc99521de3599eb5cde061db7f398ba79833c7a80"
ORACLE_SHA = "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
SCENARIOS_SHA = "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
REQUIRED = tuple("""alpha3_22_master_root_verification alpha3_22a_root_verification alpha3_22b_root_verification
alpha3_22c_root_verification alpha3_22d_failed_root_verification alpha3_21_closure_verification alpha3_22r0_scope_boundary
t05_frozen_failure_evidence_binding t05_causal_execution_trace t05_expected_actual_first_divergence
t05_mapping_phase_provenance_audit t05_lifecycle_transition_audit t05_partial_raw_freeze_audit
t05_journal_mapping_phase_binding_audit t05_resume_reconstruction_audit cross_component_contract_authority_matrix
failure_occurrence_mapping_persistence_phase_analysis cross_component_root_cause_classification versioned_repair_design_decision
transport_failure_phase_binding_v2_proposal transport_failure_phase_binding_v2_schema transport_failure_phase_binding_v2_invariants
journal_terminal_event_v2_proposal journal_phase_transition_validation_proposal same_attempt_evidence_binding_contract
partial_quarantine_preservation_contract retry_authority_nonchange_audit minimal_implementation_change_surface
historical_component_immutability_plan repair_positive_fixture_specification repair_negative_fixture_specification
repair_recovery_fixture_specification independent_expected_outcome_preservation_audit future_r1_implementation_plan
future_independent_59_scenario_revalidation_plan alpha3_21_noncontinuation_audit scientific_policy_firewall_audit
contamination_baseline_immutability_audit historical_preservation_audit scientific_state_safety_audit validation summary""".split())
MARKERS = {"t05_causal_execution_trace_sha256": "t05_causal_execution_trace",
           "cross_component_root_cause_evidence_sha256": "cross_component_root_cause_evidence",
           "transport_failure_phase_binding_v2_proposal_sha256": "transport_failure_phase_binding_v2_proposal",
           "alpha3_22r0_repair_design_bundle_sha256": "alpha3_22r0_repair_design_bundle"}
NO_CALLS = {key: 0 for key in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
NO_CHANGE = {key: False for key in ("retry_policy_changed", "exception_mapping_table_changed",
    "historical_22a_implementation_modified", "historical_22b_implementation_modified", "historical_22c_implementation_modified",
    "historical_22d_artifacts_modified", "repair_implementation_started", "independent_fault_matrix_rerun_started",
    "alpha3_21_reopened", "fresh_primary_attempt_started", "builder_v4_changed", "quality_v2_changed",
    "search_plan_scientific_architecture_changed", "historical_assets_modified", "production_runtime_v2_wiring_enabled",
    "runtime_network_execution_started", "process_resume_executed_against_live_sources")}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def obj(path):
    return json.loads(Path(path).read_bytes())


def verify_design_references(value):
    """Distinguish literal JSON Schema definitions from actual file references.

    Historical checked_tree remains unchanged. The sole declarative schema has
    dictionary-valued artifact_path/sha256 *definitions*, not a physical ref.
    Its JSON bytes are still bound by the design bundle/root like every file.
    """
    if type(value) is dict and "$schema" in value:
        require(value.get("$id") == "urn:alpha322r0:TransportFailurePhaseBindingV2", "UNEXPECTED_DECLARATIVE_SCHEMA")
        require(value["$schema"] == "https://json-schema.org/draft/2020-12/schema", "SCHEMA_DIALECT_DRIFT")
        def strict_schema(node):
            if type(node) is dict:
                if node.get("type") == "object":
                    require(node.get("additionalProperties") is False
                            and set(node.get("required", [])) == set(node.get("properties", {})), "SCHEMA_OBJECT_CONTRACT_DRIFT")
                for child in node.values():
                    strict_schema(child)
            elif type(node) is list:
                for child in node:
                    strict_schema(child)
        strict_schema(value)
        return
    d.master.d2.d1.d.checked_tree(value)


def ref(path, role="read_only_frozen_authority"):
    return d.master.ref(Path(path), role)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def location(path, symbol, text=None):
    """Hash/line/source binding, not executing the referenced function."""
    path = Path(path)
    source = path.read_text()
    nodes = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == symbol]
    require(len(nodes) == 1, "AMBIGUOUS_SOURCE_SYMBOL:" + symbol)
    node = nodes[0]
    result = {**ref(path), "symbol": symbol, "start_line": node.lineno, "end_line": node.end_lineno}
    if text:
        hits = [index + 1 for index, line in enumerate(source.splitlines()) if text in line]
        require(len(hits) == 1, "AMBIGUOUS_SOURCE_ASSERTION:" + text)
        result.update(assertion_line=hits[0], assertion=source.splitlines()[hits[0] - 1].strip())
    return result


def verify_authority():
    with d.master.prior.offline_guard():
        authority = d.verify_authority()
        authority["alpha322d"] = d.master.prior.root_check(d.OUT, d.ROOT_MARKER, D_SHA)
        for marker, stem, expected in ((d.EVIDENCE_MARKER, "alpha3_22d_fault_execution_evidence", EVIDENCE_SHA),
            (d.BUNDLE_MARKER, "alpha3_22d_validation_bundle", BUNDLE_SHA),
            (d.SCENARIO_MARKER, "frozen_fault_scenario_manifest", SCENARIOS_SHA)):
            path = d.OUT / (stem + ".json")
            require(digest(path) == expected == (d.OUT / marker).read_text().strip(), "22D_MEMBER_BINDING_FAILURE")
            d.master.d2.d1.d.checked_tree(obj(path))
        oracle_path = d.OUT / "independent_expected_outcomes.jsonl"
        require(digest(oracle_path) == ORACLE_SHA == (d.OUT / d.ORACLE_MARKER).read_text().strip(), "ORACLE_INTEGRITY_FAILURE")
        # Frozen source bindings are checked without calling any fault harness.
        d.master.d2.d1.d.checked_tree(obj(d.OUT / "runtime_component_integrity_audit.json"))
        d.master.d2.d1.d.checked_tree(obj(d.OUT / "frozen_fault_scenario_manifest.json"))
        summary = obj(d.OUT / "summary.json")
        require(summary["status"] == "failed" and summary["alpha3_22d_classification"] == d.FAIL_CLASS, "22D_HISTORICAL_STATUS_CHANGED")
        require([summary[k] for k in ("fault_scenario_frozen_count", "fault_scenario_executed_count", "fault_scenario_pass_count",
                "fault_scenario_fail_count", "fault_scenario_not_executed_count")] == [59, 5, 4, 1, 54], "22D_ACCOUNTING_CHANGED")
        authority["22d_evidence"] = ref(d.OUT / "alpha3_22d_fault_execution_evidence.json")
        authority["22d_bundle"] = ref(d.OUT / "alpha3_22d_validation_bundle.json")
        return authority


def audit_t05():
    """Verify existing bytes/records only. No signal is reinjected or appended."""
    path = d.OUT / "scenario_T05.json"
    actual = obj(path)
    # scenario_T05 is transitively sealed by the verified D root and bundle.
    observation = obj(ROOT / actual["observation"]["artifact_path"])
    records = [json.loads(line) for line in (ROOT / actual["journal"]["artifact_path"]).read_bytes().splitlines()]
    manifest_path = d.OUT / "independent_execution/T05/request_manifest.json"
    manifest = d.j.FrozenRequestManifestV1(manifest_path.read_bytes())
    request = manifest.record()["requests"][0]
    expected_rows = [json.loads(line) for line in (d.OUT / "independent_expected_outcomes.jsonl").read_bytes().splitlines()]
    frozen_expected = next(row for row in expected_rows if row["scenario_id"] == "T05")
    require(len(expected_rows) == 59 and actual["comparison"]["expected"] == frozen_expected["expected"], "T05_EXPECTED_BINDING_FAILURE")
    d.master.d2.d1.d.checked_tree(actual)
    events = tuple(d.j.JournalEventV1(canonical(record)) for record in records)
    verified = d.j.JournalIntegrityVerifierV1.verify_events(events, manifest, manifest_path.parent)
    # Read-only revalidation of a saved plan, not fresh recovery or fault execution.
    require(d.p.DeterministicResumePlannerV1().build(verified).record() == actual["fresh_process_resume_plan"], "SAVED_RESUME_BINDING_FAILURE")
    context = {"logical_request_id": "T05:OA:0", "request_payload_sha256": request["request_payload_sha256"],
               "attempt_ordinal": 1, "runtime_contract_sha256": d.t.MASTER_ROOT_SHA256}
    require(context["request_payload_sha256"] == "d5436af0fb5500bd29cda69008818f94bd172d59ee71364a96511f9d3ae7a3e6", "T05_REQUEST_CHANGED")
    require(all(observation["observation"][key] == value for key, value in context.items()), "T05_IDENTITY_MISMATCH")
    mapping = observation["mapping"]
    require(mapping == actual["persisted_mapping_and_retry"][0]["mapping"] == actual["checkpoints"][1]["mapping"], "MAPPING_SNAPSHOT_DRIFT")
    require(mapping["phase"] == "RESPONSE_BODY_READING" and mapping["mapping_rule_id"] == "reset_body_read"
            and mapping["matched_exception_class"] == "builtins.ConnectionResetError"
            and mapping["semantic_failure_class"] == "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "UNRESOLVED_T05_MAPPING_AUTHORITY")
    table = obj(B / "transport_exception_mapping_v2_table.json")
    rule = next(row for row in table["rules"] if row["rule_id"] == mapping["mapping_rule_id"])
    require(rule["allowed_lifecycle_phases"] == ["RESPONSE_BODY_READING"] and digest(B / "transport_exception_mapping_v2_table.json") == mapping["mapping_table_sha256"], "MAPPING_RULE_BINDING_FAILURE")
    lifecycle = observation["observation"]["lifecycle_events"]
    require(lifecycle == [record["event_payload"]["lifecycle_event"] for record in records[1:]], "T05_TRACE_MISMATCH")
    require([edge["state"] for edge in lifecycle] == ["REQUEST_ATTEMPT_STARTED", "RESPONSE_HEADERS_RECEIVED",
            "RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN"], "T05_TRANSITION_MISMATCH")
    for edge in lifecycle:
        require((d.t.LifecycleState(edge["previous_state"]), d.t.LifecycleState(edge["state"])) in d.t.ALLOWED_TRANSITIONS
                and all(edge[key] == value for key, value in context.items()), "FROZEN_TRACE_INVALID")
    require(observation["observation"]["lifecycle_state"] == "RAW_RESPONSE_FROZEN", "PERSISTENCE_PHASE_UNRESOLVED")
    body = observation["observation"]["body_read_provenance"]
    raw = Path(actual["raw_artifact"]["artifact_path"]).read_bytes()
    require(raw == b"" and len(raw) == actual["raw_artifact"]["byte_count"] == body["bytes_read"] == 0, "T05_RAW_CHANGED")
    require(hashlib.sha256(raw).hexdigest() == body["partial_body_sha256"] == actual["raw_artifact"]["sha256"], "T05_PARTIAL_HASH_MISMATCH")
    require(body["completion_state"] == "BODY_INTERRUPTED" and body["read_returned_normally"] is False
            and body["parser_invoked"] is False and body["complete_body_sha256"] is None, "T05_QUARANTINE_CHANGED")
    retry = actual["persisted_mapping_and_retry"][0]["retry"]
    require(retry["retry_authorized"] is True and retry["attempt_ordinal"] == 1 and retry["next_attempt_ordinal"] == 2
            and retry["backoff_selected_seconds"] == 2 and request["replay_safe"] is True, "T05_RETRY_CHANGED")
    require(actual["durable_terminal_error"]["message"] == "MAPPING_PHASE_BINDING"
            and not any(record["event_type"] == "ATTEMPT_TERMINAL" for record in records), "T05_TERMINAL_CHANGED")
    require([row["field"] for row in actual["comparison"]["mismatches"]] == ["durable_terminal_committed", "terminal_logical_state"], "T05_DIVERGENCE_CHANGED")
    require(actual["actual"]["terminal_logical_state"] == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"
            and frozen_expected["expected"]["terminal_logical_state"] == "RETRYABLE_FAILURE_WITH_BUDGET", "T05_EXPECTED_ACTUAL_CHANGED")
    return {"actual": actual, "observation": observation, "journal": records, "manifest": manifest.record(),
            "manifest_reference": ref(manifest_path), "context": context, "rule": rule,
            "expected": frozen_expected, "oracle_scenario_ids": [row["scenario_id"] for row in expected_rows]}


def proposal_schema():
    """Declarative schema only: semantic validation belongs to future R1."""
    hash_field = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    string = {"type": "string", "minLength": 1}
    phase = {"enum": list(d.master.STATES)}
    def record(properties):
        return {"type": "object", "additionalProperties": False, "properties": properties, "required": list(properties)}
    artifact = record({"artifact_path": string, "sha256": hash_field, "byte_count": {"type": "integer", "minimum": 0}})
    event_ref = record({"journal_sequence_number": {"type": "integer", "minimum": 1}, "journal_entry_hash": hash_field})
    identity = record({**{key: string for key in ("run_id", "run_epoch", "stage_id", "logical_request_id")},
        "request_payload_sha256": hash_field, "attempt_ordinal": {"type": "integer", "minimum": 1, "maximum": 4},
        "manifest_sha256": hash_field, "attempt_start_entry_hash": hash_field})
    properties = {
        "schema_version": {"const": "TransportFailurePhaseBindingV2"},
        "binding_scope": {"const": "CONCRETE_EXCEPTION_OCCURRENCE"},
        "attempt_identity": identity,
        "authority": record({key: hash_field for key in ("master_sha256", "alpha322a_sha256", "alpha322b_sha256",
            "historical_alpha322c_sha256", "mapping_table_sha256", "semantic_retry_contract_sha256",
            "retry_orchestration_contract_sha256", "phase_binding_design_sha256", "runtime_v2_implementation_manifest_sha256")}),
        "failure_event_id": hash_field,
        "occurrence_evidence": record({"artifact": artifact, "capture_schema_version": {"const": "FailureOccurrenceEvidenceV2"},
            "failure_occurrence_phase": phase, "phase_anchor": event_ref, "exception_provenance_sha256": hash_field,
            "bound_client_identity_sha256": hash_field, "mapping_input_facts_sha256": hash_field,
            "mapped_decision_snapshot_sha256": hash_field}),
        "mapping_evidence": record({"artifact": artifact, "mapping_evidence_phase": phase,
            "mapping_rule_id": {"type": ["string", "null"]}, "mapping_table_sha256": hash_field,
            "semantic_failure_class": {"enum": list(d.master.TAXONOMY)}}),
        "lifecycle_trace": record({"artifact": artifact, "lifecycle_trace_id": hash_field,
            "occurrence_anchor": event_ref, "persistence_anchor": event_ref,
            "ordered_progress_event_refs": {"type": "array", "minItems": 1, "items": event_ref}}),
        "terminal_persistence_phase": phase,
        "raw_artifact": {"anyOf": [artifact, {"type": "null"}]},
        "raw_admission": record({"raw_artifact_frozen": {"type": "boolean"}, "body_complete": {"type": "boolean"},
            "authoritative": {"type": "boolean"}, "parser_eligible": {"type": "boolean"},
            "completion_provenance_sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"}}),
        "retry_decision_binding": record({"classified_retry_decision_artifact": artifact,
            "retry_decision_sha256": hash_field, "semantic_retry_contract_sha256": hash_field}),
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:alpha322r0:TransportFailurePhaseBindingV2",
            **record(properties), "$comment": "PROPOSAL ONLY. R0 does not implement semantic binding validation. No remote schema resolution."}


def build_documents(authority, frozen):
    """Authored evidence analysis and prospective contracts, not a repair SUT."""
    actual, mapped, journal = frozen["actual"], frozen["observation"], frozen["journal"]
    observation, mapping = mapped["observation"], mapped["mapping"]
    jpath = ROOT / "src/code_engine/append_only_attempt_journal_v1.py"
    tpath = ROOT / "src/code_engine/transport_lifecycle_v2.py"
    bpath = ROOT / "src/code_engine/transport_exception_mapping_v2.py"
    opath = ROOT / "src/code_engine/transport_observability_v1.py"
    ppath = ROOT / "src/code_engine/deterministic_resume_planner_v1.py"
    hpath = Path(d.__file__)
    master_lifecycle = obj(MASTER / "transport_lifecycle_contract_v2_draft.json")
    c_transition = obj(C / "journal_event_transition_contract.json")
    require(c_transition["lifecycle_owner"] == "alpha3.22A.ALLOWED_TRANSITIONS", "C_AUTHORITY_CONFLICT_STOP_BEFORE_DESIGN")
    require(any(edge["from"] == "RESPONSE_BODY_INTERRUPTED" and edge["to"] == "RAW_RESPONSE_FROZEN"
                for edge in master_lifecycle["transitions"]), "MASTER_AUTHORITY_CONFLICT_STOP_BEFORE_DESIGN")
    equality = location(jpath, "validate_mapped_observation", 'require(mapping["phase"] == observation["lifecycle_state"]')
    sources = {"22A": ref(tpath), "22A_observability": ref(opath), "22B": ref(bpath),
               "22C": ref(jpath), "22C_resume": ref(ppath), "22D_harness": ref(hpath)}
    docs = {
        "alpha3_22_master_root_verification": authority["master"],
        "alpha3_22a_root_verification": authority["alpha322a"],
        "alpha3_22b_root_verification": authority["alpha322b"],
        "alpha3_22c_root_verification": authority["alpha322c"],
        "alpha3_22d_failed_root_verification": {**authority["alpha322d"], "evidence": authority["22d_evidence"],
            "validation_bundle": authority["22d_bundle"], "historical_classification": d.FAIL_CLASS},
        "alpha3_21_closure_verification": authority["closure"],
        "alpha3_22r0_scope_boundary": {"stage_identity": "POST_ALPHA3_22D_VERSIONED_RUNTIME_REPAIR_DESIGN",
            "development_only": True, "offline_only": True, "repair_design_only": True,
            "allowed": ["read frozen records/code/contracts", "hash verification", "audit and descriptive proposals",
                        "static offline contract tests", "compileall", "git diff --check"],
            "forbidden": ["repair implementation", "22D reinjection/rerun", "network including localhost", "models",
                "scientific parsing", "live-source resume", "production wiring", "historical edits", "alpha3.21 continuation"],
            **NO_CALLS, **NO_CHANGE},
    }
    docs["t05_frozen_failure_evidence_binding"] = {
        "all_bindings_verified": True, "failed_22d_root": D_SHA, "evidence_sha256": EVIDENCE_SHA, "bundle_sha256": BUNDLE_SHA,
        "scenario": ref(d.OUT / "scenario_T05.json"), "failure_evidence": ref(d.OUT / "scenario_failure_evidence.json"),
        "oracle": ref(d.OUT / "independent_expected_outcomes.jsonl"), "oracle_sha256": ORACLE_SHA,
        "scenario_manifest": ref(d.OUT / "frozen_fault_scenario_manifest.json"),
        "observation": actual["observation"], "journal": actual["journal"],
        "manifest": frozen["manifest_reference"], "raw": actual["raw_artifact"], "source_bindings": sources,
        "original_22d_status": "failed", "frozen": 59, "executed": 5, "passed": 4, "failed": 1, "not_executed": 54,
    }
    trace_steps = [
        ("durable start acknowledged; dispatch logged once", "REQUEST_ATTEMPT_STARTED", [1, 2]),
        ("trusted HTTP 200 headers; body read starts", "RESPONSE_BODY_READING", [3, 4]),
        ("exact ConnectionResetError from bound HTTPResponse.read; mapped at occurrence", "RESPONSE_BODY_READING", []),
        ("22A retry decision permits next ordinal; no next START or dispatch", "RESPONSE_BODY_READING", []),
        ("empty observed byte artifact physically written/fsynced by RawArtifactStoreV1; not yet lifecycle-promoted", "RESPONSE_BODY_READING", []),
        ("22A record_body records interruption; progress acknowledged", "RESPONSE_BODY_INTERRUPTED", [5]),
        ("22A freeze_response rechecks bytes/hash; records partial RAW_RESPONSE_FROZEN", "RAW_RESPONSE_FROZEN", [6]),
        ("22B wrapper serializes immutable earlier mapping plus current 22A observation", "RAW_RESPONSE_FROZEN", []),
        ("22C terminal candidate rejected during verify_events, before append/fsync", "RAW_RESPONSE_FROZEN", []),
        ("frozen fresh-process read sees no trusted terminal; legitimate abandoned reconstruction", "RAW_RESPONSE_FROZEN", []),
    ]
    docs["t05_causal_execution_trace"] = {
        "schema_version": "FrozenT05CausalExecutionTraceR0", "evidence_binding": docs["t05_frozen_failure_evidence_binding"],
        "run_identity": {key: frozen["manifest"][key] for key in ("run_id", "run_epoch", "stage_id")},
        "attempt_context": frozen["context"], "request_replay_safe": True,
        "signal": {"qualified_class": "builtins.ConnectionResetError", "occurrence_phase": "RESPONSE_BODY_READING",
            "evidence": observation["exception_provenance"],
            "source": location(hpath, "actual_bound_failure"),
            "phase_resolution": "frozen concrete_fault_classified checkpoint + ordered journal BODY_READING anchor + bound call-site/traceback"},
        "mapping": mapping, "retry_decision": actual["persisted_mapping_and_retry"][0]["retry"],
        "steps": [{"causal_order": index, "action": action, "lifecycle_phase": phase,
                   "durable_journal_sequence_numbers": sequences}
                  for index, (action, phase, sequences) in enumerate(trace_steps, 1)],
        "lifecycle_events": observation["lifecycle_events"], "journal_events": journal,
        "terminal_commit_input": {"lifecycle_state": observation["lifecycle_state"], "classified_decision": actual["persisted_mapping_and_retry"][0],
            "mapped_observation": mapped, "raw_artifact": actual["raw_artifact"], "validation": None, "eligibility": None,
            "context_source": frozen["manifest_reference"], "call_site": location(hpath, "transport_scenario", "writer.commit_terminal(lifecycle, decision, observation, artifact=artifact, validation=validation, eligibility=eligibility, timestamp=NOW)")},
        "journal_error": actual["durable_terminal_error"], "fresh_process_resume_plan": actual["fresh_process_resume_plan"],
        "independent_expected": frozen["expected"],
        "timestamps_prove_order": False, "causal_order_from": "source order + immutable checkpoints + journal sequence/hash chain",
        "occurrence_has_separate_durable_event_in_original_22D": False,
        "no_new_occurrence_identity_retrofitted_to_22D": True,
    }
    docs["t05_expected_actual_first_divergence"] = {
        "first_observable_divergence": "durable_terminal_commit pre-append candidate validation",
        "original_defective_assumption": equality, "mismatches": actual["comparison"]["mismatches"],
        "prior_compatible_steps": ["correct phase-aware mapping", "correct 22A retry", "allowed A lifecycle",
            "non-authoritative empty partial artifact preserved", "unchanged mapping phase serialized", "current lifecycle phase serialized"],
        "incorrect_state_production": False, "incorrect_event_serialization": False,
        "incorrect_journal_validation": True, "incorrect_integration_call_sequence": False,
        "harness_contract_misuse_proven": False, "normative_frozen_authority_conflict_proven": False,
        "raw_staging_order": "Physical byte staging precedes record_body; A lifecycle freeze/admission follows recorded interruption. No frozen contract forbids non-authoritative staging.",
        "downstream_consequence_not_primary_cause": "saved fresh-process recovery classifies a missing terminal as abandoned under correct restart rule",
        "preappend_rejection_not_storage_io_failure": True,
    }
    docs["t05_mapping_phase_provenance_audit"] = {
        "mapping_input_phase": mapping["phase"], "mapping_output_phase": mapping["phase"], "mapping_rule": frozen["rule"],
        "checkpoint_mapping_equals_saved_mapping": True, "mapping_evidence_not_overwritten": True,
        "concrete_exception_occurrence_resolved": True,
        "facts_source": location(bpath, "TransportMappingFactsV2"), "result_source": location(bpath, "TransportMappingResultV2"),
        "classification_source": location(bpath, "classify"), "wrapper_source": location(bpath, "mapped_observation_v2"),
        "context_at_occurrence": location(hpath, "mapping_facts"), "binding_limitations": {
            "exception_provenance_client_code_sha256": observation["exception_provenance"]["runtime_identity"]["client_code_sha256"],
            "separate_occurrence_phase_field": "not present in original exception provenance",
            "resolution_authority": "verified B client/table bindings + frozen D call-site/checkpoint/traceback; not exception message",
            "future_V2_requires_explicit_controller_occurrence_capture": True},
    }
    docs["t05_lifecycle_transition_audit"] = {
        "all_five_transitions_verified": True, "events": observation["lifecycle_events"],
        "journal_progress_matches_observation": True, "lifecycle_owner": ref(tpath),
        "fault_to_persistence_suffix": ["RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN"],
        "logical_retry_state_is_lifecycle_enum_member": False, "retry_state_not_added_to_lifecycle": True,
        "master_contract": ref(MASTER / "transport_lifecycle_contract_v2_draft.json"),
    }
    docs["t05_partial_raw_freeze_audit"] = {
        "raw": actual["raw_artifact"], "body_provenance": observation["body_read_provenance"],
        "byte_count": 0, "why_empty": "reset has no recoverable .partial; do not invent transferred bytes",
        "raw_artifact_frozen": True, "body_complete": False, "authoritative": False, "parser_eligible": False,
        "complete_hash": None, "raw_hash_verified": True, "all_six_consumer_invocation_counts": actual["actual"]["parser_invocation_counts"],
        "RAW_RESPONSE_FROZEN_implies_BODY_COMPLETE": False,
        "frozen_response_semantics": location(tpath, "FrozenTransportResponseV2"), "freeze_response": location(tpath, "freeze_response"),
    }
    docs["t05_journal_mapping_phase_binding_audit"] = {
        "defective_check": equality, "comparison_values": {"mapping.phase": "RESPONSE_BODY_READING", "observation.lifecycle_state": "RAW_RESPONSE_FROZEN"},
        "mapping_phase_meaning": "immutable facts.phase used to select concrete B rule", "observation_phase_meaning": "current A phase when aggregate captured",
        "terminal_input_is_same_request_and_attempt": True, "durable_start_and_progress_count": 6,
        "terminal_count": 0, "candidate_prevalidation_rejected_before_storage_append": True,
        "call_chain": ["AppendOnlyAttemptJournalV1.commit_terminal", "_append", "JournalIntegrityVerifierV1.verify_events", "_reduce", "_verify_terminal", "validate_mapped_observation"],
        "other_required_validations_to_preserve": ["schema/exact fields", "all context identities", "table/rule/hash",
            "trace equals journal progress", "current phase equals last progress", "raw path/hash/count", "single terminal", "22A retry equality"],
    }
    docs["t05_resume_reconstruction_audit"] = {
        "saved_fresh_process_plan": actual["fresh_process_resume_plan"], "read_only_saved_plan_revalidated": True,
        "new_fresh_process_recovery_fixture_executed": False, "no_historical_journal_appended": True,
        "reconstruction_matches_existing_contract": True,
        "actual": "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", "independent_expected": "RETRYABLE_FAILURE_WITH_BUDGET",
        "not_a_resume_policy_defect": True, "cause": "failure terminal never reached durable commit",
        "in_memory_retry_evidence_not_terminal_authority": True, "source": location(ppath, "build"),
    }
    authority_rows = [
        ("master lifecycle/quarantine", ref(MASTER / "transport_lifecycle_contract_v2_draft.json"), "interrupted -> raw-frozen; partial -> validation forbidden; terminal separate", True),
        ("22A lifecycle", location(tpath, "record_body"), "interruption records BODY_INTERRUPTED at BODY_READING", True),
        ("22A raw freeze", location(tpath, "freeze_response"), "observed raw hash/count reverified; frozen != complete", True),
        ("22A observation", location(opath, "TransportAttemptObservationV1"), "lifecycle_state is CURRENT phase at capture", True),
        ("22B mapping", location(bpath, "classify"), "result.phase is supplied mapping facts phase; reset only BODY_READING", True),
        ("22B wrapper", location(bpath, "mapped_observation_v2"), "preserve old immutable mapping; capture current A aggregate", True),
        ("22C normative event contract", ref(C / "journal_event_transition_contract.json"), "A owns lifecycle; same ordinal; unique terminal", True),
        ("22C normative observations", ref(C / "journal_observability_schema_binding.json"), "A schema semantics unchanged; C owns durability wrapper", True),
        ("22C terminal technical branch", location(jpath, "_verify_terminal"), "partial raw allowed for technical failures; no scientific validation", True),
        ("22C implementation equality", equality, "mapping phase MUST equal observation current phase; rejects legitimate A/B trace", False),
        ("22C master restart", ref(C / "abandoned_attempt_resolution_contract.json"), "no committed terminal => abandoned, consumed ordinal preserved", True),
        ("22D integration", location(hpath, "transport_scenario"), "classify original exception at fault, preserve raw, commit afterward", True),
    ]
    docs["cross_component_contract_authority_matrix"] = {
        "rows": [{"authority": name, "source_binding": binding, "semantics": semantics, "T05_compatible": ok}
                 for name, binding, semantics, ok in authority_rows],
        "compatibility_scope": "prospective V2 correction preserves normative master/A/B/C semantics, NOT byte-compatible replacement of existing V1 behavior",
        "existing_V1_accepts_proposed_record": False, "in_place_V1_contract_amendment_allowed": False,
        "frozen_semantic_contracts_compatible": True, "historical_implementation_equality_is_defective": True,
        "why_not_authority_conflict": "C event contract explicitly delegates lifecycle to A and binds unchanged A observation semantics. No normative contract redefines B result.phase as persistence phase. The extra equality occurs in V1 validation code.",
        "raw_commit_order_scope": "C complete raw/validation ordering describes valid-response path; its frozen technical branch and own partial fixture explicitly allow quarantined partial failures. Do not infer a global complete-only requirement.",
        "raw_order_evidence": [ref(C / "raw_response_commit_order_contract.json"), location(jpath, "_verify_terminal"), location(Path(d.upstream.__file__), "terminal")],
        "conflict_branch": "If future evidence establishes an incompatible normative requirement, STOP; do not choose a rule by T05 outcome.",
    }
    docs["failure_occurrence_mapping_persistence_phase_analysis"] = {
        "failure_occurrence_phase": {"value": "RESPONSE_BODY_READING", "original_field": "scenario_T05.checkpoints[concrete_fault_classified].phase",
            "corroboration": "journal sequence 4 + frozen actual_bound_failure/transport_scenario order + actual exception traceback",
            "absent_field": "22A ExceptionProvenanceV1 has no separate failure-occurrence phase", "new_authority_not_retrofitted": True},
        "mapping_evidence_phase": {"value": "RESPONSE_BODY_READING", "original_fields": ["TransportMappingFactsV2.phase", "TransportMappingResultV2.phase", "MappedTransportObservationV2.mapping.phase"]},
        "persistence_phase": {"value": "RAW_RESPONSE_FROZEN", "original_fields": ["TransportLifecycleV2.state", "TransportAttemptObservationV1.lifecycle_state", "journal progress last state"]},
        "alias_policy": "BODY_READING is shorthand only; stored enum is RESPONSE_BODY_READING. Mapping/current-state fields retain frozen semantics. New wrapper aliases are checked projections, never independently controlled authority.",
        "proposed_relationship": "concrete mapping evidence phase == controller-captured exception occurrence phase; persistence is exact verified trace endpoint, not necessarily equal",
        "relationship_compatible_with_semantic_authorities": True, "timestamp_only_proof_allowed": False,
    }
    docs["cross_component_root_cause_classification"] = {
        "primary_cause": CAUSE, "uniquely_resolved": True, "causal_boundary": equality,
        "explanation": "C compares immutable original mapping facts.phase with current aggregate lifecycle_state after A legitimately freezes quarantined raw.",
        "secondary_contributors": [
            {"cause": "C partial fixture maps structured_body_completion after freeze, not a real concrete body exception before freeze",
             "evidence": location(Path(d.upstream.__file__), "terminal"), "not_primary_cause": True},
            {"cause": "original observation lacks explicit controller-owned failure event identity/anchor; future binding must add it without rewriting history",
             "evidence": ref(A / "exception_provenance_v1_schema.json"), "not_primary_cause": True}],
        "alternatives_rejected": {"INTEGRATION_EVENT_PHASE_BINDING_DEFECT": "upstream data retain both correct distinct phases; bad equality is at C validator",
            "FAULT_HARNESS_CONTRACT_MISUSE": "exact signal/phase, permitted transitions, same typed commit inputs; no frozen API says remap reset after freeze",
            "FROZEN_CROSS_COMPONENT_AUTHORITY_CONFLICT": "normative C lifecycle owner and unchanged schema binding align with A/B; source equality is an implementation defect",
            "ROOT_CAUSE_NOT_UNIQUELY_RESOLVED": "verified call-site, inputs, assertion and first divergence identify one primary cause"},
        "other_unexecuted_scenarios": "No claim about T06 onward or other suspected defects; all 54 remain unexecuted.",
    }
    docs["versioned_repair_design_decision"] = {"classification": CLASSIFICATION, "primary_cause": CAUSE,
        "design_supported": True, "cross_component_contract_compatible": True, "implementation_allowed_in_R0": False,
        "chosen_scope": "new controller-owned phase binding + versioned journal writer/verifier + explicit V2 resume reader",
        "not_a_harness_only_repair": True, "not_a_retry_policy_change": True,
        "rejected_shortcuts": ["delete phase validation", "overwrite mapping.phase with persistence", "remap concrete exception after freeze",
            "mark failed commit success", "infer committed failure from memory", "relabel old D", "change T05 oracle", "monkeypatch old V1"],
        "next_stage_recommendation": NEXT, "authorization_required_for_R1": True}
    return docs, sources


def design_documents(docs, sources):
    """Freeze normative future validation steps; none is implemented here."""
    docs["transport_failure_phase_binding_v2_schema"] = proposal_schema()
    docs["transport_failure_phase_binding_v2_proposal"] = {
        "schema_version": "TransportFailurePhaseBindingV2ProposalR0", "implementation_state": "NOT_IMPLEMENTED",
        "runtime_activation_allowed": False, "scope": "new synthetic development runs only, never alpha3.21 or historical D",
        "binding_record_schema": "transport_failure_phase_binding_v2_schema.json",
        "existing_data_preserved": ["22B TransportMappingResultV2 exact frozen record", "22A observation/schema/events",
            "22A classified semantic retry result", "request manifest identity and authority"],
        "new_fields_rationale": "Original A provenance lacks a controller-owned occurrence-phase anchor and failure-event identity. Add only a new wrapper, not historical A/B fields.",
        "checked_projection_fields": {"mapping_evidence.mapping_evidence_phase": "exact copy of frozen mapping.phase",
            "terminal_persistence_phase": "exact copy of observation.lifecycle_state and last persisted lifecycle event.state",
            "occurrence_evidence.failure_occurrence_phase": "new immutable capture of actual controller state in exception handler BEFORE subsequent lifecycle advancement"},
        "failure_event_identity": "SHA256(canonical occurrence artifact bytes), excluding no fields; occurrence artifact contains no self-referential ID",
        "occurrence_artifact_contract": {
            "schema_version": "FailureOccurrenceEvidenceV2",
            "required": ["full same-attempt identity", "current durable lifecycle anchor sequence/hash", "actual current phase",
                "frozen bound client identity", "redacted exact exception provenance artifact/hash",
                "22B input facts snapshot/artifact/hash", "22B mapping + 22A decision artifact/hash"],
            "capture_owner": "new isolated controller adapter in actual except handler; actual exception object passed unchanged to frozen 22B",
            "capture_sequence": ["ensure durable start/current lifecycle progress", "capture actual phase/identity/exception",
                "call unchanged 22B classification -> sole 22A decision", "freeze facts/exception/mapped-decision artifacts",
                "freeze occurrence envelope bytes before further A lifecycle transitions"],
            "no_exception_name_or_timestamp_only_authority": True,
            "hashes_do_not_prove_external_truth": "Trusted provenance requires the bound controller capture path and source bindings, not merely rehashed enum strings.",
        },
        "lifecycle_trace_identity": "SHA256(canonical trace artifact: full attempt identity + ordered complete same-attempt progress references/edges); no self hash field",
        "partial_artifact_identity": "physical raw path + bytes SHA256 + byte count; zero-length interrupted artifact remains partial",
        "retry_binding": "exact ClassifiedRetryDecisionV2 snapshot from frozen B->A call; verify using ONLY A semantic_retry_decision",
        "no_new_retry_function": True,
        "non_exception_paths": {
            "success": "no failure-occurrence binding; keep exact existing validated complete-response semantics in new event envelope",
            "structured_body_completion": "separate explicit structured-evidence route with its existing B adapter phase predicate; DO NOT falsely equate later adapter observation with an earlier exception occurrence",
            "structured_HTTP_or_backend": "keep existing versioned B rule/source/phase predicates unchanged; bind original decision evidence and explicit permitted trace",
            "unmapped_concrete_exception": "explicit rule_id=null and UNKNOWN decision denied by A; preserve evidence and durable nonretryable terminal, never upgrade to concrete-rule authority",
            "version_branch_selection": "frozen prospective manifest defines route; never result-driven remapping or generic phase-relaxation"},
        "migration": "V2 journals/events and verified types only in new output directories; V1 readers remain strict/unmodified; no cross-format append or historical conversion",
        "current_V1_runtime_incompatibility_is_explicit": True,
        "design_compatible_with_frozen_normative_semantics": True,
        "source_bindings": sources,
    }
    invariants = [
        ("I01", "All nested records share exact run_id/run_epoch/stage_id/logical_request_id/request_payload_sha256/attempt_ordinal/manifest and durable start identity"),
        ("I02", "Concrete exception mapping.phase equals captured actual occurrence phase; schema aliases equal original fields"),
        ("I03", "Frozen B table/version/rule/client identity and exact class/wrapper/structured requirements are verified; UNKNOWN with null rule cannot become retryable"),
        ("I04", "Occurrence event ID and mapping input/output artifacts remain byte/hash-identical after original capture; no remapping after lifecycle advances"),
        ("I05", "Occurrence anchor is existing durable same-attempt progress at actual captured phase; full trace equals journal progress from durable start through persistence anchor"),
        ("I06", "Ordered refs and journal sequence/hash chain are contiguous; each edge uses unchanged A ALLOWED_TRANSITIONS with unchanged semantic guards, not graph reachability alone"),
        ("I07", "Persistence phase equals terminal observation phase and last durable progress phase; it NEED NOT equal occurrence phase"),
        ("I08", "Body interruption suffix contains BODY_READING -> BODY_INTERRUPTED -> RAW_FROZEN, with interrupted completion and raw hash/count binding; cannot pass through BODY_COMPLETE/response validation"),
        ("I09", "Physical raw bytes/path/hash/count and partial-vs-complete provenance agree; interrupted/unknown partial never authoritative/parser-eligible"),
        ("I10", "Saved retry result exactly matches sole frozen A semantic_retry_decision for saved B semantics, replay authority and durable ordinal/budget; verification never grants additional authority"),
        ("I11", "Retry does not consume next ordinal; only new durable start does; maximum4 timeout60 backoff2/4/8 unchanged"),
        ("I12", "Raw and referenced evidence are durable BEFORE unique terminal append; verified pending event before fsync; uncertain append poisons writer, never marks success"),
        ("I13", "Recovery accepts only verified committed terminal; missing terminal remains abandoned under unchanged master restart, never inferred from sidecar or memory"),
        ("I14", "No mixing historical V1 and new V2 events, manifests or verified types; no monkeypatch or projection that changes frozen mapping.phase"),
        ("I15", "Timestamps supplement provenance only; presence of valid enum strings/hashes is not sufficient validation"),
    ]
    docs["transport_failure_phase_binding_v2_invariants"] = {"invariants": [{"id": key, "requirement": value} for key, value in invariants],
        "concrete_occurrence_mapping_equality_required": True, "persistence_occurrence_equality_required": False,
        "missing_evidence_policy": "FAIL_CLOSED", "semantic_validation_implemented": False}
    docs["journal_terminal_event_v2_proposal"] = {
        "schema_version": "JournalTerminalEventV2ProposalR0", "implementation_state": "NOT_IMPLEMENTED",
        "version_selection": "Explicit new JournalEventV2/VerifiedJournalV2 bound by new runtime implementation manifest; no historical V1 reinterpretation",
        "event_kinds": "preserve C ATTEMPT_STARTED/LIFECYCLE_PROGRESS/ATTEMPT_TERMINAL/ABANDONED/stage-reference kinds",
        "identity_envelope": "all existing C run/epoch/stage/manifest/request/ordinal/sequence/segment/previous-entry/hash bindings retained plus prospective implementation binding",
        "terminal_payload": {"existing_fields": ["outcome", "mapped_observation", "retry_decision", "raw_artifact", "validation", "eligibility"],
            "additional_field": "failure_phase_binding; non-null for concrete transport failure, route-specific structured binding otherwise, null on valid success",
            "mapping_and_observation": "exact frozen A/B record schemas, embedded without modifying field meanings"},
        "failure_append_order": ["durable start before dispatch", "durable occurrence evidence captured at fault",
            "22A interruption/progress", "raw quarantine and file/directory fsync", "22A raw-freeze progress",
            "evidence/trace artifacts hash+fsync", "full pending-event semantic preverification", "terminal append+fsync", "acknowledgment"],
        "logical_outcome": "unchanged existing C projection of verified A retry decision; RETRYABLE_FAILURE_WITH_BUDGET is not an A lifecycle state",
        "unique_terminal_required": True, "skip_terminal_commit_allowed": False,
        "fresh_process_reader_must_validate_V2": True,
    }
    docs["journal_phase_transition_validation_proposal"] = {
        "implementation_state": "NOT_IMPLEMENTED", "ordered_validation_steps": [
            "Verify exact event/envelope schemas, canonical bytes, authority/version bindings, monotonic sequence/hash chain and unique started attempt",
            "Read frozen physical occurrence/input/decision/exception/trace artifacts; verify path/hash/count and bound controller derivation",
            "Compare full attempt identity across event, manifest, occurrence, mapping facts/provenance and lifecycle references",
            "Compare immutable occurrence phase to original mapping evidence phase; reject missing/different/edited evidence",
            "Verify original B mapping rule/table/client and concrete class/wrapper/structured phase predicates from captured facts, without remapping at persistence phase",
            "Verify occurrence anchor exists in same-attempt durable progress; ordered full trace bytes match actual journal events/hash-linked refs",
            "Validate every exact A edge AND guard evidence; no arbitrary past phase or graph-only/timestamp-only shortcut",
            "Verify persistence anchor is last progress and observation lifecycle_state; for interrupted trace enforce no complete/validation promotion",
            "Verify raw/body provenance integrity/quarantine and six blocked consumer admissions",
            "Verify saved A retry snapshot using the unchanged A function and replay/ordinal/budget authority; reject contradictory positive retries",
            "Check unique terminal, raw/evidence durable before terminal; only fsynced validated append counts as committed"],
        "old_invalid_equality_replaced_by": "immutable occurrence==mapping + exact same-attempt controller trace ending at persistence, with all original orthogonal identity/rule/raw/retry checks",
        "acceptance_from_enum_strings_only": False, "validation_catch_and_success": False,
    }
    docs["same_attempt_evidence_binding_contract"] = {
        "identity_fields": ["run_id", "run_epoch", "stage_id", "logical_request_id", "request_payload_sha256", "attempt_ordinal"],
        "additional_bindings": ["manifest_sha256", "attempt_start_entry_hash", "journal_segment_id", "sequence_number", "runtime authority hashes"],
        "original_A_context": "logical_request_id/request_payload_sha256/attempt_ordinal/runtime_contract_sha256; run/stage belong to C envelope",
        "new_wrapper_owns_missing_run_stage_context": True, "cross_request_or_attempt_evidence_allowed": False,
        "request_hash_alias": "journal.frozen_request_hash must equal A request_payload_sha256 and immutable manifest request hash",
    }
    docs["partial_quarantine_preservation_contract"] = {
        "master_authority": ref(MASTER / "partial_response_quarantine_contract.json"),
        "raw_freeze_not_completion": True, "partial_response_authoritative": False, "partial_response_parser_allowed": False,
        "blocked_consumers": ["XML/JSON parser", "JATS structure/identity", "license", "BODY normalization", "scientific extraction"],
        "raw_artifact_frozen_and_complete_are_separate": True, "zero_length_partial_preserved": True,
        "partial_complete_hash_forbidden": True, "unknown_completion_quarantined": True,
        "partial_identifier_authority": "UNTRUSTED_PARTIAL_TRANSPORT_OBSERVATIONS",
        "later_success_overwrites_partial": False,
    }
    docs["retry_authority_nonchange_audit"] = {
        "retry_policy_changed": False, "exception_mapping_table_changed": False, "second_retry_function_proposed": False,
        "semantic_retry_owner": "22A.semantic_retry_decision", "orchestration": "unchanged 22B classify -> 22A decision",
        "matrix_authority": ref(MASTER / "transport_retryability_matrix.json"),
        "A_contract": ref(A / "semantic_retry_decision_contract.json"), "B_contract": ref(B / "retry_orchestration_v2_contract.json"),
        "B_table": ref(B / "transport_exception_mapping_v2_table.json"),
        "maximum_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "replay_safe_and_remaining_budget_required": True, "UNKNOWN_completed_failure_retry_allowed": False,
        "verification_not_new_authorization": "V2 journal compares original saved decision with unchanged A pure function, just as C does; does not re-infer or upgrade classifications.",
    }
    surfaces = [
        {"proposed_module_path": "src/code_engine/transport_failure_phase_binding_v2.py",
         "responsibility": "new immutable controller occurrence envelope/capture and phase-binding validation; no transport or retry policy",
         "existing_references": ["22B TransportMappingFactsV2/ResultV2/classify_transport_failure_and_decide_retry_v2/mapped_observation_v2", "22A events/context/body/raw/provenance"],
         "existing_modules_changed": False},
        {"proposed_module_path": "src/code_engine/append_only_attempt_journal_v2.py",
         "responsibility": "explicit versioned event/verified types, writer and terminal verifier; port C storage/identity/order semantics without widening other checks",
         "existing_references": ["append_only_attempt_journal_v1.validate_mapped_observation", "_verify_terminal", "_reduce",
                                 "JournalIntegrityVerifierV1.verify_events", "AppendOnlyAttemptJournalV1.commit_terminal/_append"],
         "why_not_adapter_only": "V1 _append and fresh-process verifier both enforce faulty equality; adapter cannot correct it without changing mapping meaning or bypassing validation",
         "existing_modules_changed": False},
        {"proposed_module_path": "src/code_engine/deterministic_resume_planner_v2.py",
         "responsibility": "explicit V2 verified-journal reader/reducer binding only; keep frozen logical-state/retry/skip/order/abandoned algorithm",
         "existing_references": ["deterministic_resume_planner_v1.DeterministicResumePlannerV1.build", "LogicalRequestExecutionStateV1", "abandoned_recovery"],
         "why_required": "V1 build requires exact VerifiedJournalV1 then reverifies through V1; cannot read V2 by duck typing",
         "existing_modules_changed": False},
        {"proposed_module_path": "scripts/search_plan_v24_alpha322r1_versioned_phase_binding_integration.py",
         "responsibility": "isolated offline new controller integration capture -> unchanged A/B -> new V2 commit; no production client imports/wiring",
         "existing_references": ["22D transport_scenario begin/classify/observation/commit sequence as read-only reference"],
         "existing_modules_changed": False},
    ]
    docs["minimal_implementation_change_surface"] = {
        "smallest_safe_change_is_not_removing_one_assertion": True, "new_versioned_surfaces": surfaces,
        "historical_A_B_C_D_edits_required": False, "A_B_retry_or_mapping_changes_required": False,
        "stage_barrier_contract_change_required": False,
        "stage_barrier_integration_note": "V2 journal must retain exact V1 snapshot bytes/derivation/parent/order semantics; any type-bound adapter is explicitly versioned and regression tested, never edited in place.",
        "new_module_paths_are_proposals_not_created_runtime_files": True,
    }
    docs["historical_component_immutability_plan"] = {
        "source_bindings": sources, "upstream_roots": {key: docs[key] for key in (
            "alpha3_22_master_root_verification", "alpha3_22a_root_verification", "alpha3_22b_root_verification",
            "alpha3_22c_root_verification", "alpha3_22d_failed_root_verification", "alpha3_21_closure_verification")},
        "no_overwrite_no_migration_no_monkeypatch": True, "new_runs_new_roots_required": True,
        "old_V1_behavior_reproducible": True, "original_22D_remains_failed": True,
        "verify_all_bound_sources_and_roots_before_and_after": True,
    }
    docs["repair_positive_fixture_specification"] = fixtures.positive()
    docs["repair_negative_fixture_specification"] = {"expected_source": "independent R0 requirements, not runtime validator answers",
        "required_N01_N14_present": True, "fixture_count": 22, "fixtures": fixtures.negatives(),
        "all_expected_fail_closed": True, "fixture_executions_in_R0": 0,
        "reason_codes_are_prospective_not_existing_runtime_enums": True}
    docs["repair_recovery_fixture_specification"] = fixtures.recovery()
    docs["independent_expected_outcome_preservation_audit"] = {
        "original_scenario_count": 59, "all_59_original_outcomes_preserved": True,
        "scenario_manifest_sha256": SCENARIOS_SHA, "original_oracle_sha256": ORACLE_SHA,
        "T05_expected_terminal": "RETRYABLE_FAILURE_WITH_BUDGET", "original_oracle_edited": False,
        "fixture_source": ref(Path(fixtures.__file__), "new_independent_descriptive_fixture_source_no_SUT_imports"),
        "SUT_calls_in_fixture_source": 0, "R0_fixture_runtime_executions": 0,
        "new_fixtures_do_not_replace_original_cases": True,
    }
    docs["future_r1_implementation_plan"] = {
        "authorization_required": True, "not_started": True, "recommended_stage": NEXT,
        "steps": ["reverify all frozen roots and R0 root", "freeze explicit V2 implementation interfaces/version binding before execution",
            "implement only new proposed surfaces under offline guards; preserve historical files", "keep exact A/B delegation and all C orthogonal invariants",
            "static schema + independent R0 positive/negative/recovery fixture tests", "regression-test old A/B/C unchanged",
            "freeze separate R1 implementation root; do not claim full fault-matrix PASS"],
        "stop_on_new_normative_conflict": True, "result_driven_policy_repair_allowed": False,
        "production_wiring_or_live_alpha321_continuation_allowed": False,
    }
    docs["future_independent_59_scenario_revalidation_plan"] = {
        "new_run_and_new_root_required": True, "requires_separate_authorization": True, "R0_rerun_started": False,
        "original_manifest": ref(d.OUT / "frozen_fault_scenario_manifest.json"),
        "original_oracle": ref(d.OUT / "independent_expected_outcomes.jsonl"),
        "required_original_scenario_count": 59, "scenario_ids": obj(d.OUT / "frozen_fault_scenario_manifest.json")["order"],
        "preserve_original_conditions_order_faults_expectations": True,
        "only_implementation_binding_changes": "new separately preregistered V2 system-under-test adapter; never regenerate or tune original expectations",
        "also_required": ["all 22 repair-negative fixtures", "R0 positive + nonempty-partial supplement", "both fresh-process recovery variants",
            "original mutation-sensitivity requirements", "all A/B/C focused regression tests", "original end-to-end/barrier/activation/quarantine tests"],
        "PASS_requires": "all required scenarios actually executed and passed; partial/early-stop run must fail gate; T05 alone never suffices",
        "new_critical_failure_policy": "preserve evidence and stop under new prospective stop policy; not-executed cases remain not executed",
        "old_D_directory_appends_allowed": False,
    }


def safety_documents(docs, authority):
    docs["alpha3_21_noncontinuation_audit"] = {
        "closure": authority["closure"], "classification": "TERMINATED_INCOMPLETE_AT_D2_RUNTIME_AUTHORITY_GAP",
        "alpha3_21_reopened": False, "PMID_42731998_retried": False, "remaining_37_JATS_requests_executed": False,
        "original_IncompleteRead_reclassified": False, "final_construction_source_count_derived": False,
        "alpha321_remains_SEEN_and_closed": True,
    }
    docs["scientific_policy_firewall_audit"] = {
        "unchanged_scientific_bindings": authority["scientific_bindings"],
        "legacy_sources": authority["legacy"], "scientific_policy_changed": False,
        "protected": ["Builder V4", "Quality V2", "scientific search architecture/queries", "OA eligibility",
                      "JATS identity validity", "license", "BODY normalization", "contamination rules"],
        **NO_CHANGE, **NO_CALLS,
    }
    docs["contamination_baseline_immutability_audit"] = {
        "registry": authority["registry"], "counts": authority["counts"], "registry_changed": False,
        "new_scientific_assets_acquired": 0,
    }
    docs["historical_preservation_audit"] = {
        "before_roots_and_code_verified": True, "after_roots_and_code_must_verify_before_freeze": True,
        "upstream": authority, "historical_assets_modified": False,
        "original_D_status": "failed", "D_frozen_scenarios": 59, "D_executed_scenarios": 5,
        "D_passed_scenarios": 4, "D_failed_scenarios": 1, "D_not_executed_scenarios": 54,
    }
    docs["scientific_state_safety_audit"] = {
        "development_only": True, "audit_read_only_on_all_historical_assets": True,
        "new_assets": "R0 design/audit files and new descriptive fixture source only",
        "scientific_selection_or_content_interpretation": False, "repair_code_created": False,
        "original_59_scenarios_executed_in_R0": 0, "proposed_repair_fixtures_executed_in_R0": 0,
        "existing_frozen_journal_saved_plan_read_only_validation": True,
        **NO_CALLS, **NO_CHANGE,
    }


def summary_record():
    return {"status": "completed", "search_plan_v24_dev_alpha3_22r0_status": "completed",
        "alpha3_22r0_classification": CLASSIFICATION,
        **{key: True for key in ("alpha3_22_master_root_verified", "alpha3_22a_root_verified", "alpha3_22b_root_verified",
            "alpha3_22c_root_verified", "alpha3_22d_failed_root_verified", "alpha3_21_closure_root_verified",
            "t05_root_cause_resolved", "failure_occurrence_phase_resolved", "mapping_evidence_phase_resolved",
            "persistence_phase_resolved", "cross_component_contract_compatible", "phase_binding_v2_design_frozen",
            "mapping_phase_required_to_match_failure_occurrence_phase", "persistence_phase_requires_valid_lifecycle_trace",
            "same_request_and_attempt_binding_required")},
        "original_22d_status_preserved": "failed", "original_22d_frozen_scenario_count": 59,
        "original_22d_executed_scenario_count": 5, "original_22d_passed_scenario_count": 4,
        "original_22d_failed_scenario_count": 1, "original_22d_not_executed_scenario_count": 54,
        "t05_root_cause_classification": CAUSE, "persistence_phase_required_to_equal_failure_phase": False,
        "partial_response_authoritative": False, "partial_response_parser_allowed": False,
        "repair_negative_fixture_specification_count": 22, "repair_fixture_execution_count": 0,
        "design_complete_not_runtime_gate_passed": True, "next_stage_recommendation": NEXT,
        **NO_CHANGE, **NO_CALLS}


def prepare_documents():
    """R0 read-only audit; no directory creation or implementation calls."""
    with d.master.prior.offline_guard():
        authority = verify_authority()
        frozen = audit_t05()
        docs, sources = build_documents(authority, frozen)
        design_documents(docs, sources)
        safety_documents(docs, authority)
        # Independent fixture source is descriptive, without any imports.
        tree = ast.parse(Path(fixtures.__file__).read_text())
        require(not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)), "REPAIR_FIXTURES_NOT_INDEPENDENT")
        require(set(REQUIRED) - set(docs) == {"validation", "summary"}, "MISSING_R0_DESIGN_ARTIFACTS")
        # Complete this check BEFORE any design output directory is created.
        for document in docs.values():
            verify_design_references(document)
        return authority, docs


def freeze_design(verification_path):
    require(not OUT.exists(), "R0_EXISTS_NO_OVERWRITE_OR_RERUN")
    verification = obj(verification_path)
    require(verification["scope"] == "R0 static audit/contract tests only; no original fault matrix or new repair fixture execution", "INVALID_TEST_SCOPE")
    require(verification["checks"] and all(check["exit_code"] == 0 for check in verification["checks"]), "OFFLINE_VERIFICATION_FAILED")
    with d.master.prior.offline_guard():
        authority, docs = prepare_documents()
        before = canonical(authority)
        docs["validation"] = {
            "status": "completed", "repair_design_checks_passed": True,
            "runtime_repair_implemented_or_validated": False,
            "checks": ["all upstream roots and recursively bound source SHA256", "T05 frozen oracle/mapping/journal/raw/resume exact match",
                "first divergence located", "unique primary cause", "normative semantic compatibility with explicit V1 runtime incompatibility",
                "versioned minimum surface and no retry drift", "independent descriptive fixtures and original oracle preservation"],
            "offline_verification": verification, "runtime_fixture_execution_count": 0,
            "fault_matrix_execution_count": 0, "R0_authority_unchanged_before_output": True,
        }
        require(UNSEALED_FAILURE.is_dir() and not (UNSEALED_FAILURE / ROOT_MARKER).exists(), "UNSEALED_FAILURE_PRESERVATION_MISSING")
        docs["r0_unsealed_freeze_failure_preservation_audit"] = {
            "attempt_identity": "R0 design packaging attempt 01; not 22D or runtime repair execution",
            "status": "UNSEALED_FREEZE_FAILED_SCHEMA_REFERENCE_CHECKER_TYPE_ERROR",
            "valid_frozen_R0_root_created": False, "upstream_binding_mismatch": False,
            "error": "TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'",
            "failure_file": "transport_failure_phase_binding_v2_schema.json",
            "reason": "Historical checked_tree misreads dictionary-valued artifact_path/sha256 schema property definitions as a file ref.",
            "preservation": "All 48 unsealed output files moved without rewriting; two physical byte-identical audit-script/test snapshots added before source correction.",
            "archive_members": [ref(path, "preserved_unsealed_failed_design_freeze_not_authority") for path in sorted(UNSEALED_FAILURE.rglob("*")) if path.is_file()],
            "historical_A_B_C_D_code_changed": False, "R0_audit_only_correction": "explicit strict declarative-schema check, unchanged historical reference checker for all actual refs; preflight moved before output creation",
            "scientific_or_transport_runtime_change": False, "original_22D_rerun": False,
            "old_unsealed_summary_not_a_valid_completed_stage": True,
        }
        require(canonical(verify_authority()) == before, "HISTORICAL_DRIFT_STOP_BEFORE_FREEZE")
        store = d.t.RawArtifactStoreV1(OUT)
        def emit(stem, record):
            path = OUT / (stem + ".json")
            store.freeze_bytes(path.name, canonical(record))
            return ref(path, "new_frozen_R0_design_or_audit")
        for stem, record in docs.items():
            emit(stem, record)
        evidence_stems = ("t05_frozen_failure_evidence_binding", "t05_causal_execution_trace", "t05_expected_actual_first_divergence",
            "t05_mapping_phase_provenance_audit", "t05_lifecycle_transition_audit", "t05_partial_raw_freeze_audit",
            "t05_journal_mapping_phase_binding_audit", "t05_resume_reconstruction_audit", "cross_component_contract_authority_matrix",
            "failure_occurrence_mapping_persistence_phase_analysis", "cross_component_root_cause_classification")
        emit("cross_component_root_cause_evidence", {"primary_cause": CAUSE, "uniquely_resolved": True,
            "members": [ref(OUT / (stem + ".json")) for stem in evidence_stems]})
        # No hash cycles: bundle excludes summary/root/itself and binds sources/tests.
        bundle = {"schema_version": "Alpha322R0RepairDesignBundleV1", "classification": CLASSIFICATION,
            "implementation_state": "NOT_IMPLEMENTED", "members": [ref(path) for path in sorted(OUT.glob("*.json"))],
            "R0_source_bindings": [ref(path, "R0_audit_or_fixture_or_test_source") for path in (Path(__file__), Path(fixtures.__file__), TEST)],
            "upstream_verification": authority, "offline_verification": verification,
            "runtime_fixture_execution_count": 0, **NO_CALLS, **NO_CHANGE}
        emit("alpha3_22r0_repair_design_bundle", bundle)
        hashes = {}
        for marker, stem in MARKERS.items():
            hashes[marker] = digest(OUT / (stem + ".json"))
            store.freeze_bytes(marker, (hashes[marker] + "\n").encode())
        summary = {**summary_record(), **hashes}
        emit("summary", summary)
        require(all((OUT / (stem + ".json")).is_file() for stem in REQUIRED), "R0_REQUIRED_ARTIFACT_MISSING")
        require(canonical(verify_authority()) == before, "HISTORICAL_DRIFT_DURING_FREEZE")
        for path in OUT.glob("*.json"):
            verify_design_references(obj(path))
        root = d.master.root_hash(OUT, ROOT_MARKER)
        store.freeze_bytes(ROOT_MARKER, (root + "\n").encode())
        d.j.sync_directory(OUT)
        require(d.master.root_hash(OUT, ROOT_MARKER) == root, "POST_FREEZE_ROOT_MISMATCH")
        return {**summary, ROOT_MARKER: root, "workspace": str(OUT), "json_file_count": len(list(OUT.glob("*.json")))}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(freeze_design(args.verification), ensure_ascii=False, sort_keys=True))
