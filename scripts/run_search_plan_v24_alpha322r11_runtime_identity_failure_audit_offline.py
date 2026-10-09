#!/usr/bin/env python3
"""Forensic R1.1 audit only: saved bytes, static sources and schema tests.

No exception capture, transport lifecycle, journal writer, resume execution,
runtime fixture, scientific operation or R2 implementation is authorized here.
"""

import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import run_search_plan_v24_alpha322r1_versioned_phase_binding_repair_offline as prior

r0, u, o, t = prior.r0, prior.f.u, prior.h.o, prior.h.t
ROOT, R1, R0, A = prior.ROOT, prior.OUT, prior.f.R0, r0.A
OUT = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r11_runtime_identity_failure_audit_offline"
TEST = ROOT / "tests/test_search_plan_v24_alpha322r11_runtime_identity_failure_audit_offline.py"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22r11_sha256"
R1_SHA = "5de303807062abc75191a06ccee53e4460cc29e14918507ff4c22810df658524"
CLASSIFICATION = "R1_RUNTIME_IDENTITY_SCHEMA_BINDING_DEFECT_RESOLVED_FOR_REPAIR_DESIGN"
NEXT = "IMPLEMENT_ALPHA3_22R2_VERSIONED_RUNTIME_IDENTITY_BINDING_CORRECTION_OFFLINE"
DIAGNOSIS = "INCOMPLETE_EXPLICIT_RUNTIME_IDENTITY_OVERRIDES_22A_DEFAULT_CAPTURE_AND_IS_PRESERVED_THROUGH_SERIALIZATION"
LOSS_BOUNDARY = "transport_failure_phase_binding_v2.capture_failure.runtime_dictionary_construction"
ERROR = "SCHEMA_REQUIRED:$.runtime_identity"
NO_CALLS = dict(r0.NO_CALLS)
REQUIRED = """upstream_root_verification r1_failed_snapshot_verification r1_runtime_failure_evidence_binding
r1_runtime_identity_schema_authority r1_runtime_identity_required_field_inventory r1_actual_serialized_event_inspection
r1_schema_rejection_path_audit r1_runtime_identity_producer_consumer_trace r1_runtime_identity_field_loss_analysis
r1_python_version_authority_audit r1_controller_owned_capture_boundary r1_schema_version_binding_audit
r1_harness_vs_component_defect_audit r1_positive_fixture_first_failure_audit r1_negative_n14_first_rejection_audit
r1_negative_n17_first_rejection_audit r1_negative_n21_first_rejection_audit r1_rec01_rec02_execution_reachability_audit
r1_masked_downstream_validation_state r1_root_cause_classification r2_minimal_versioned_repair_design
r2_runtime_identity_binding_contract r2_runtime_identity_positive_fixture_spec r2_runtime_identity_negative_fixture_spec
r2_original_r0_fixture_preservation_audit r2_validation_order_contract independent_22dr_execution_prohibition
archived_test_temporaries_preservation_audit scientific_policy_firewall_audit contamination_baseline_immutability_audit
historical_preservation_audit scientific_state_safety_audit validation summary""".split()
MARKERS = {"r1_runtime_identity_causal_trace_sha256": "r1_runtime_identity_producer_consumer_trace",
    "r1_runtime_identity_root_cause_evidence_sha256": "r1_runtime_identity_root_cause_evidence",
    "r2_runtime_identity_repair_design_sha256": "r2_minimal_versioned_repair_design"}


def load(path):
    return u.strict_json(u.read_bytes(path))


def ref(path, role):
    path = u.physical(Path(path))
    return {"artifact_path": str(path.relative_to(ROOT)), "sha256": u.sha(u.read_bytes(path)), "artifact_role": role}


def locate(path, function=None, *, class_name=None, text=None):
    path = Path(path)
    source = path.read_text()
    tree = ast.parse(source)
    scope = tree
    if class_name:
        matches = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
        t.require(len(matches) == 1, "AMBIGUOUS_AUDIT_CLASS")
        scope = matches[0]
    if function:
        matches = [node for node in scope.body if isinstance(node, ast.FunctionDef) and node.name == function]
        t.require(len(matches) == 1, "AMBIGUOUS_AUDIT_FUNCTION")
        scope = matches[0]
    result = {**ref(path, "frozen_source_location"), "symbol": ((class_name + ".") if class_name else "") + (function or "module"),
              "start_line": getattr(scope, "lineno", 1), "end_line": getattr(scope, "end_lineno", len(source.splitlines()))}
    if text:
        hits = [index + 1 for index, line in enumerate(source.splitlines()) if text in line]
        t.require(len(hits) == 1, "AMBIGUOUS_AUDIT_SOURCE_TEXT:" + text)
        result.update(assertion_line=hits[0], assertion=source.splitlines()[hits[0] - 1].strip())
    return result


def verify_authority():
    verified = prior.authority()
    verified["alpha322r1"] = r0.d.master.prior.root_check(R1, prior.ROOT_MARKER, R1_SHA)
    for marker, stem in prior.MARKERS.items():
        path = R1 / (stem + ".json")
        t.require(u.sha(u.read_bytes(path)) == (R1 / marker).read_text().strip(), "R1_MEMBER_HASH_MISMATCH")
    bundle = load(R1 / "alpha3_22r1_repair_validation_bundle.json")
    for member in bundle["members"] + bundle["source_bindings"] + [bundle["test_temporary_archive"]]:
        t.require(u.sha(u.read_bytes(ROOT / member["artifact_path"])) == member["sha256"], "R1_FROZEN_BINDING_MISMATCH")
    summary = load(R1 / "summary.json")
    t.require(summary["status"] == "failed" and summary["alpha3_22r1_classification"] == prior.FAIL, "R1_FAILED_STATE_CHANGED")
    t.require(summary["r0_negative_fixture_pass_count"] == 19 and summary["r0_negative_fixture_fail_count"] == 3
              and summary["r0_positive_fixture_passed"] is False and summary["r0_recovery_fixture_passed"] is False
              and summary["r0_recovery_rec02_executed"] is False, "R1_FAILED_ACCOUNTING_CHANGED")
    runtime = load(R1 / "runtime_v2_implementation_manifest.json")
    for member in runtime["source_files"]:
        source = ROOT / member["artifact_path"]
        t.require(u.sha(u.read_bytes(source)) == member["sha256"]
            and u.read_bytes(source) == u.read_bytes(R1 / "implementation" / source.name), "R1_SOURCE_SNAPSHOT_DRIFT")
    verified["r1_members"] = {marker: ref(R1 / (stem + ".json"), "unchanged_failed_R1_member") for marker, stem in prior.MARKERS.items()}
    verified["test_archive_manifest"] = bundle["test_temporary_archive"]
    return verified


def exception_schema():
    path = A / "exception_provenance_v1_schema.json"
    t.require(u.sha(u.read_bytes(path)) == prior.j.OBSERVATION_SCHEMA_HASHES[path.stem], "FROZEN_EXCEPTION_SCHEMA_DRIFT")
    return load(path)


def saved_case(case_id, relative):
    directory = R1 / "execution" / relative
    matches = list(directory.glob("evidence-*/signal.json"))
    t.require(len(matches) == 1, "REQUIRED_SERIALIZED_EXCEPTION_UNAVAILABLE:" + case_id)
    signal_path = matches[0]
    signal, occurrence, binding = load(signal_path), load(signal_path.parent / "occurrence.json"), load(signal_path.parent / "binding.json")
    manifest = load(directory / "request_manifest.json")
    events = [u.strict_json(line) for line in u.read_bytes(directory / "segment-0001.jsonl").splitlines()]
    t.require(occurrence["signal"]["sha256"] == u.sha(u.read_bytes(signal_path))
        == binding["occurrence_evidence"]["exception_provenance_sha256"], "SAVED_SIGNAL_BINDING_MISMATCH")
    context = occurrence["attempt_identity"]
    t.require(all(signal[key] == context[key] for key in ("logical_request_id", "request_payload_sha256", "attempt_ordinal")), "SAVED_EXCEPTION_CONTEXT_MISMATCH")
    t.require(context["manifest_sha256"] == u.sha(u.read_bytes(directory / "request_manifest.json"))
        and all(context[key] == manifest[key] for key in ("run_id", "run_epoch", "stage_id")), "SAVED_OCCURRENCE_MANIFEST_MISMATCH")
    terminals = [event for event in events if event["event_type"] == "ATTEMPT_TERMINAL"]
    own_terminal = [event for event in terminals if event["logical_request_id"] == signal["logical_request_id"]]
    actual = signal.get("runtime_identity")
    return {"case_id": case_id, "exception_payload": ref(signal_path, "actual_serialized_exception_payload_not_regenerated"),
        "occurrence": ref(signal_path.parent / "occurrence.json", "actual_controller_capture_envelope"),
        "binding": ref(signal_path.parent / "binding.json", "actual_phase_binding_envelope"),
        "journal": ref(directory / "segment-0001.jsonl", "original_durable_event_bytes"),
        "manifest": ref(directory / "request_manifest.json", "original_frozen_synthetic_request_manifest"),
        "exception_schema_version": signal["schema_version"], "actual_exception_object_keys": sorted(signal),
        "runtime_identity": actual, "runtime_identity_parent_present": "runtime_identity" in signal,
        "python_version_present": isinstance(actual, dict) and "python_version" in actual,
        "runtime_identity_keys": sorted(actual) if isinstance(actual, dict) else None,
        "missing_runtime_identity_fields": sorted(set(exception_schema()["properties"]["runtime_identity"]["required"]) - set(actual)),
        "attempt_identity": context, "signal_hash_matches_both_envelopes": True,
        "durable_event_count": len(events), "failure_terminal_durable": bool(own_terminal),
        "durable_terminal_outcomes": [{"request_id": event["logical_request_id"], "outcome": event["event_payload"]["outcome"]} for event in terminals],
        "whole_rejected_terminal_candidate_bytes_preserved": False,
        "evidence_limit": "invalid proposal never appended; original exception child is saved, whole rejected event must not be reconstructed as historical bytes"}


def schema_probe(record, schema=None, path="$"):
    """Isolated read-only schema check, NOT a writer/capture/transport fixture."""
    try:
        o.validate_schema(record, schema or exception_schema(), path)
    except t.TransportContractError as exc:
        return str(exc)
    return None


def prepare_documents():
    authority = verify_authority()
    schema = exception_schema()
    for stem, expected in prior.j.OBSERVATION_SCHEMA_HASHES.items():
        t.require(u.sha(u.read_bytes(A / (stem + ".json"))) == expected, "FROZEN_OBSERVABILITY_SCHEMA_DRIFT")
    cases = [saved_case(key, relative) for key, relative in
        (("R0_P01", "positive"), ("N14", "N14"), ("N17", "N17"), ("N21", "N21"), ("REC01", "recovery/committed"))]
    actual_signal = load(ROOT / cases[0]["exception_payload"]["artifact_path"])
    t.require(schema_probe(actual_signal) == ERROR, "ORIGINAL_SCHEMA_REJECTION_NOT_EXPLAINED")
    schema_ref = ref(A / "exception_provenance_v1_schema.json", "unchanged_22A_exception_schema")
    sources = {
        "component_constructor": locate(Path(prior.f.__file__), "capture_failure", text="    runtime = {"),
        "integration_constructor": locate(Path(prior.h.__file__), text="RUNTIME = {"),
        "integration_observation": locate(Path(prior.h.__file__), "failed_attempt", text="http=http_provenance, body=body, runtime_identity=RUNTIME"),
        "A_capture": locate(Path(o.__file__), "capture", class_name="ExceptionProvenanceV1", text="identity = runtime_identity if runtime_identity is not None else"),
        "A_python_authority": locate(Path(o.__file__), "capture", class_name="ExceptionProvenanceV1", text='"python_version": platform.python_version()'),
        "A_aggregate": locate(Path(o.__file__), "capture", class_name="TransportAttemptObservationV1"),
        "A_serialization": locate(Path(o.__file__), "from_record", class_name="FrozenObservationRecordV1"),
        "A_redaction": locate(Path(o.__file__), "tree", class_name="SecretRedactorV1"),
        "B_observation": locate(Path(prior.h.b.__file__), "mapped_observation_v2"),
        "journal_assembly": locate(Path(prior.j.__file__), "commit_terminal", class_name="AppendOnlyAttemptJournalV2"),
        "journal_append_order": locate(Path(prior.j.__file__), "_append", class_name="AppendOnlyAttemptJournalV2"),
        "nested_schema_consumer": locate(Path(prior.j.__file__), "validate_mapped_observation", text='o.validate_schema(observation[key], schemas[key])'),
        "required_container_validator": locate(Path(o.__file__), "validate_schema", text='require(set(schema.get("required", [])) <= set(value), "SCHEMA_REQUIRED:" + path)'),
        "phase_binding_signal_equality": locate(Path(prior.f.__file__), "validate_binding", text='require(signal == mapped["observation"]["exception_provenance"]'),
        "recovery_order": locate(Path(prior.fixtures.__file__), "recovery"),
        "negative_order": locate(Path(prior.fixtures.__file__), "negative"),
    }
    documents = {"upstream_root_verification": authority}
    summary = load(R1 / "summary.json")
    documents["r1_failed_snapshot_verification"] = {"verified_root": R1_SHA, "summary": ref(R1 / "summary.json", "authoritative_failed_R1_summary"),
        "validation": ref(R1 / "validation.json", "unchanged_provisional_R1_validation"),
        "terminal_classification_audit": ref(R1 / "terminal_failure_classification_audit.json", "existing_append_only_classification_resolution"),
        "status": summary["status"], "classification": summary["alpha3_22r1_classification"],
        "original_positive_passed": False, "negative_count": 22, "negative_pass_count": 19, "negative_fail_count": 3,
        "rec01_passed": False, "rec02_executed": False,
        "reporting_caveat": "validation.json has provisional broader classification and mislabels focused_v2 as unrelated_environment_failures; authoritative terminal summary corrects classification; actual failure is implementation/integration schema omission"}
    failures = [ref(R1 / "execution" / name, "original_schema_failure_stack") for name in
        ("R0_P01_failure.txt", "N14_failure.txt", "N17_failure.txt", "R0_REC01_REC02_failure.txt", "focused_v2.txt")]
    failures.append(ref(R1 / "execution_N21.json", "original_N21_wrong_first_rejection"))
    documents["r1_runtime_failure_evidence_binding"] = {"cases": cases, "original_failures": failures,
        "source_locations": sources, "no_new_runtime_execution": True}
    documents["r1_runtime_identity_schema_authority"] = {"schema": schema_ref, "schema_id": schema["$id"],
        "schema_dialect": schema["$schema"], "schema_version": schema["properties"]["schema_version"]["const"],
        "validator": sources["required_container_validator"], "consumer": sources["nested_schema_consumer"],
        "root_object_type": "dict: TransportExceptionProvenanceV1 member, not JournalEventV2 root",
        "parent_required_declaration": schema["required"], "child_required_declaration": schema["properties"]["runtime_identity"]["required"],
        "all_22A_schema_bindings": [ref(A / (stem + ".json"), "unchanged_22A_observability_schema") for stem in prior.j.OBSERVATION_SCHEMA_HASHES],
        "R0_schema": ref(R0 / "transport_failure_phase_binding_v2_schema.json", "unchanged_R0_phase_binding_schema"),
        "R0_proposal": ref(R0 / "transport_failure_phase_binding_v2_proposal.json", "unchanged_R0_design"),
        "R0_and_journal_envelope_do_not_require_runtime_identity_at_root": True}
    ri_schema = schema["properties"]["runtime_identity"]
    documents["r1_runtime_identity_required_field_inventory"] = {
        "parent_required": True, "parent_type": "object", "required_fields": ri_schema["required"], "optional_fields": [],
        "nullable_required_fields": ["client_version"], "additional_properties": False,
        "fields": [{"name": key, "definition": rule, "required": key in ri_schema["required"],
                    "present_in_actual_signal": key in actual_signal["runtime_identity"]} for key, rule in sorted(ri_schema["properties"].items())],
        "not_declared": ["platform", "interpreter_implementation", "environment_variables", "run_id", "attempt_ordinal"],
        "schema_shape_allows_string_placeholders_but_does_not_authorize_fabricated_identity": True}
    documents["r1_actual_serialized_event_inspection"] = {"cases": cases,
        "machine_flag_scope": "actual frozen exception payload bound to failed terminal proposal; not an appended failure terminal (none exists)",
        "whole_invalid_terminal_event_not_available": True, "whole_event_bytes_not_regenerated": True}
    documents["r1_schema_rejection_path_audit"] = {"actual_first_error": ERROR, "actual_first_path": "$.runtime_identity",
        "not_reported_as_leaf": "$.runtime_identity.python_version", "missing_child_by_required_set_difference": ["python_version"],
        "parent_present": True, "validation_root": "observation.exception_provenance, validated separately with default path=$",
        "full_logical_location": "event_payload.mapped_observation.observation.exception_provenance.runtime_identity",
        "validator_error_semantics": "required-set check emits the current object/container path, not missing-key path",
        "read_only_original_schema_probe_error": schema_probe(actual_signal),
        "absent_parent_would_report": "SCHEMA_REQUIRED:$", "sources": [sources["nested_schema_consumer"], sources["required_container_validator"]]}
    steps = [
        ("COMPONENT_RUNTIME_CONTEXT_CONSTRUCTION", "actual exception/context", "explicit three-key dict", "component controller", "unversioned dict", sources["component_constructor"], "OBSERVED_SAVED_SIGNAL_AND_STATIC_SOURCE"),
        ("22A_EXCEPTION_CAPTURE", "explicit non-None runtime_identity dict", "CaptureOutcomeV1.provenance", "caller overrides default identity capture", "TransportExceptionProvenanceV1", sources["A_capture"], "OBSERVED_SAVED_EXCEPTION_BYTES"),
        ("OCCURRENCE_SIGNAL_SERIALIZATION", "redacted exception record", "canonical signal.json bytes + occurrence hash", "22A serializer and V2 occurrence wrapper", "FailureOccurrenceEvidenceV2", sources["A_serialization"], "OBSERVED_SAVED_EXCEPTION_BYTES_AND_HASHES"),
        ("INTEGRATION_RUNTIME_CONTEXT_CONSTRUCTION", "frozen integration RUNTIME constant", "second explicit three-key dict", "R1 offline integration", "unversioned dict", sources["integration_constructor"], "STATIC_SOURCE_AND_ORIGINAL_STACK"),
        ("22B_MAPPED_OBSERVATION_CONSTRUCTION", "exception + runtime_identity=RUNTIME", "mapped aggregate FrozenObservationRecordV1", "integration caller + unchanged 22B/22A construction", "MappedTransportObservationV2/TransportAttemptObservationV1", sources["B_observation"], "STATIC_SOURCE_AND_SIGNAL_EQUALITY_CHECK_BEFORE_ORIGINAL_REJECTION"),
        ("V2_TERMINAL_PAYLOAD_ASSEMBLY", "mapped observation.record()", "event_payload.mapped_observation", "V2 writer", "JournalEventV2", sources["journal_assembly"], "STATIC_SOURCE_AND_ORIGINAL_STACK_NOT_SAVED_WHOLE_EVENT"),
        ("V2_EVENT_REDACTION_SERIALIZATION", "complete event dictionary", "canonical pending JournalEventV2 bytes", "22A redaction + canonical serializer", "JournalEventV2", sources["journal_append_order"], "STATIC_SOURCE_AND_ORIGINAL_STACK_NOT_SAVED_WHOLE_EVENT"),
        ("NESTED_EXCEPTION_SCHEMA_VALIDATION", "decoded exception_provenance member", "SCHEMA_REQUIRED:$.runtime_identity", "frozen 22A schema/validator", "TransportExceptionProvenanceV1", sources["nested_schema_consumer"], "OBSERVED_ORIGINAL_STACK_AND_ISOLATED_SCHEMA_CHECK"),
    ]
    documents["r1_runtime_identity_producer_consumer_trace"] = {"trace": [
        {"boundary": boundary, "input_type": input_type, "output_type": output_type, "field_owner": owner,
         "runtime_identity_present": True, "python_version_present": False, "schema_or_version": version,
         "source": location, "evidence_kind": evidence} for boundary, input_type, output_type, owner, version, location, evidence in steps],
        "first_omission": LOSS_BOUNDARY, "secondary_omission": "R1 integration RUNTIME construction",
        "durable_commit_boundary_reached": False, "no_direct_whole_candidate_byte_claim": True}
    documents["r1_runtime_identity_field_loss_analysis"] = {"defect_modes": {
        "A_PARENT_NEVER_CONSTRUCTED": {"supported": False, "reason": "actual signal contains runtime_identity object"},
        "B_REQUIRED_CHILD_OMITTED": {"supported": True, "field": "python_version", "locations": [sources["component_constructor"], sources["integration_constructor"]]},
        "C_VALID_IDENTITY_DROPPED_DURING_SERIALIZATION": {"supported": False, "reason": "identity was already incomplete; saved bytes retain all supplied keys; code assembles nested record without a runtime-key filter"},
        "D_SCHEMA_VERSION_OR_FIELD_PATH_MISMATCH": {"supported": False, "reason": "expected/actual TransportExceptionProvenanceV1 and exact frozen schema hash agree"}},
        "first_loss_boundary": LOSS_BOUNDARY, "field_loss_is_omission_at_construction_not_removal": True,
        "A_default_capture_skipped_due_to_non_None_override": True}
    documents["r1_python_version_authority_audit"] = {"authority": "22A ExceptionProvenanceV1.capture default branch calls platform.python_version()",
        "source": sources["A_python_authority"], "representation": "actual interpreter version string returned by existing convention",
        "hardcoded_version_permitted_in_runtime_adapter": False, "exception_message_inference_permitted": False,
        "unknown_empty_arbitrary_defaults_permitted": False, "required_version_unavailable_behavior": "FAIL_CLOSED",
        "synthetic_values": "explicitly labeled schema-only specimens may be controlled; not evidence that runtime capture or repaired transport works"}
    documents["r1_controller_owned_capture_boundary"] = {"owner": "engineering controller", "python_version_source": "actual executing interpreter",
        "bound_client_identity_sha256": prior.h.b.BOUND_CLIENT_IDENTITY_SHA256,
        "client_module_existing_value": actual_signal["runtime_identity"]["client_module"],
        "client_version_existing_nullable_semantics": "None allowed; preserve 22A unavailable_fields annotation; do not invent a version",
        "scientific_model_or_article_content_as_authority": False, "capture_once_then_reuse_same_redacted_immutable_identity": True,
        "allowed_runtime_child_fields": ri_schema["required"], "no_environment_dictionary_or_credential_paths": True}
    documents["r1_schema_version_binding_audit"] = {"correct": True, "exception_expected": schema["properties"]["schema_version"]["const"],
        "exception_actual": actual_signal["schema_version"], "schema": schema_ref,
        "intentional_version_layers": ["JournalEventV2", "MappedTransportObservationV2", "TransportAttemptObservationV1", "TransportExceptionProvenanceV1", "TransportFailurePhaseBindingV2"],
        "R0_schema_not_broadened": True, "manifest_runtime_identity_artifact_ref_is_not_exception_runtime_identity": True,
        "schema_loader": locate(Path(prior.j.__file__), "_observation_schemas")}
    documents["r1_harness_vs_component_defect_audit"] = {"component_capture_defect": True,
        "component_independently_constructs_bad_override": sources["component_constructor"],
        "harness_integration_defect": True, "harness_independently_constructs_bad_override": sources["integration_constructor"],
        "standalone_fixture_wrapper_constructs_runtime_identity": False, "sole_test_fixture_defect": False,
        "test_fixture_construction_defect_flag_definition": "true denotes the offline integration RUNTIME builder supplying B observation; pure positive/negative wrappers do not construct identity",
        "component_capture_or_integration_defect": True, "schema_validator_selection_defect": False,
        "serialized_field_drop_defect": False, "historical_A_B_C_defect_established": False}
    positive_audit = {"fixture_id": "R0_P01", "intended_invariant": "schema-valid interrupted failure terminal plus retryable logical reconstruction",
        "expected": "VALID_TERMINAL_COMMIT_AND_RETRYABLE_FAILURE_WITH_BUDGET", "actual_first_rejection": ERROR,
        "actual_reached_validator": "22A.validate_schema(exception_provenance)", "runtime_identity_masked_downstream_assertion": True,
        "terminal_append_or_fsync_reached": False, "downstream_success_or_recovery_assertion_reached": False,
        "passed": False, "evidence": cases[0], "stack": failures[0]}
    documents["r1_positive_fixture_first_failure_audit"] = positive_audit
    first_rejections = load(R1 / "complete_negative_first_rejection_failure_audit.json")
    for key, intended in (("N14", "deny retry after consumed ordinal 4"), ("N17", "deny second terminal for same attempt"), ("N21", "deny uncertain terminal append/fsync acknowledgment")):
        row = next(item for item in first_rejections["fixtures"] if item["fixture_id"] == key)
        case = next(item for item in cases if item["case_id"] == key)
        documents["r1_negative_" + key.lower() + "_first_rejection_audit"] = {**row,
            "intended_invariant": intended, "actual_earliest_reached_validator": "22A.validate_schema(exception_provenance)",
            "runtime_identity_masked_intended_check": True, "intended_first_rejection_reached": False,
            "evidence": case, "specific_reachability": {
                "N14": "first prerequisite attempt terminal fails; ordinal 4 setup never reached",
                "N17": "first prerequisite terminal fails; duplicate-terminal proposal never reached",
                "N21": "fsync hook installed but candidate schema verification fails before journal os.write/fsync; writer_poisoned=false in saved output"}[key]}
    documents["r1_rec01_rec02_execution_reachability_audit"] = {"REC01": {"status": "BLOCKED_BY_SCHEMA_FAILURE", "passed": False,
        "earlier_success_terminal_saved": True, "failure_terminal_saved": False, "fresh_process_recovery_assertions_reached": False,
        "actual_first_error": ERROR, "evidence": cases[-1]}, "REC02": {"status": "NOT_EXECUTED", "executed": False,
        "reason": "same recovery function raises at REC01 setup before REC02 subprocess block", "source": sources["recovery_order"]},
        "unexecuted_or_masked_checks_not_promoted": True}
    documents["r1_masked_downstream_validation_state"] = {"remaining_repair_validity": "NOT_FULLY_EVALUATED",
        "remaining_phase_binding_validity": "NOT_FULLY_EVALUATED", "schema_omission_not_proof_of_other_bug_absence": True,
        "partial_phase_binding_checks_in_original_attempt_do_not_establish_full_repair_pass": True,
        "no_new_runtime_pass_claims": True, "R0_P01_N14_N17_N21_REC01_not_passed": True, "REC02_not_executed": True}
    documents["r1_root_cause_classification"] = {"classification": CLASSIFICATION, "resolved_for_design_only": True,
        "detail": DIAGNOSIS, "first_omission": LOSS_BOUNDARY, "compatible_existing_authority": True,
        "component_and_integration_omit_same_required_child": True, "schema_change_needed": False,
        "repair_implemented_or_validated": False}
    design, identity_contract, positive_spec, negative_spec, order = repair_design(schema_ref, sources)
    documents.update(r2_minimal_versioned_repair_design=design, r2_runtime_identity_binding_contract=identity_contract,
        r2_runtime_identity_positive_fixture_spec=positive_spec, r2_runtime_identity_negative_fixture_spec=negative_spec,
        r2_validation_order_contract=order)
    documents["r2_original_r0_fixture_preservation_audit"] = {"unchanged_original_specs": [ref(R0 / (stem + ".json"), "literal_independent_R0_oracle") for stem in
        ("repair_positive_fixture_specification", "repair_negative_fixture_specification", "repair_recovery_fixture_specification")],
        "original_positive_expected_not_rewritten": True, "original_negative_count": 22, "all_first_rejection_expectations_mandatory": True,
        "original_recovery_both_variants_required": True, "R1_failed_results_remain_frozen": True, "fixtures_executed_in_R11": 0}
    documents["independent_22dr_execution_prohibition"] = {"independent_22dr_authorized": False, "original_59_matrix_executed": False,
        "R2_must_pass_all_repair_requirements_first": True, "new_independent_run_requires_separate_authorization": True,
        "original_failed_D_and_oracle_preserved": True}
    archive = load(ROOT / authority["test_archive_manifest"]["artifact_path"])
    documents["archived_test_temporaries_preservation_audit"] = {"manifest": authority["test_archive_manifest"],
        "archived_group_count": len(archive["archives"]), "archive_manifests_read_only": True,
        "archived_directory_entries_or_symlinks_not_traversed_in_R11": True, "archive_link_targets_not_followed": True,
        "no_delete_clean_move_rewrite": True, "audit_scope": "verify hash-bound saved archive manifest only; no need to reopen archived runtime fixtures"}
    documents["scientific_policy_firewall_audit"] = {"original_scientific_bindings": authority["scientific_bindings"],
        "scientific_policy_changed": False, "no_scientific_source_exposure": True, "production_wiring": False,
        "Builder_Quality_retrieval_OA_JATS_license_normalization_changed": False, **NO_CALLS}
    documents["contamination_baseline_immutability_audit"] = {"registry": authority["registry"], "counts": authority["counts"],
        "registry_identity": "80e51107b6e357b210a6860888d6c27bf634eb540dee1a9ba94c3b94465f10ca", "unchanged": True}
    documents["scientific_state_safety_audit"] = {"development_mode": True, "audit_only": True,
        "alpha3_21_state": "TERMINATED_INCOMPLETE_AT_D2_RUNTIME_AUTHORITY_GAP", "alpha3_21_reopened": False,
        "fresh_primary_attempt_started": False, "r1_source_modified": False, "r1_frozen_tests_rerun": False,
        "original_22d_matrix_rerun": False, "r2_correction_implemented": False, **NO_CALLS}
    return documents


def repair_design(schema_ref, sources):
    contract = {"schema_version": "ProspectiveR2RuntimeIdentityBindingContract", "implementation_state": "DESIGN_ONLY_NOT_IMPLEMENTED",
        "frozen_schema": schema_ref, "child_field_set_exact": ["python_version", "client_module", "client_version", "client_code_sha256"],
        "python_version": {"authority": "actual interpreter via existing 22A platform.python_version() convention", "hardcode_or_placeholder": False},
        "client_module": "preserve existing bound urllib.request/http.client.HTTPResponse identity string",
        "client_code_sha256": prior.h.b.BOUND_CLIENT_IDENTITY_SHA256,
        "client_version": "retain permitted None and original unavailable_fields semantics when no client version is supplied",
        "capture_owner": "controller, independent of model/article/exception text", "capture_once": True,
        "shared_identity_consumers": ["original occurrence signal", "mapped exception provenance"],
        "capture_source_and_implementation_manifest_identity_must_be_new_R2_actual_sources": True,
        "no_false_R1_source_identity_or_manifest_reuse": True, "existing_A_redaction_required": True,
        "schema_shape_checks_plus_authoritative_capture_required": True, "context_binding_location": "existing outer attempt/occurrence/exception envelopes, NOT extra keys in runtime_identity",
        "early_schema_preflight_is_shape_only": True,
        "no_preflight_phase_binding_verified_true_without_verified_binding": True,
        "original_semantic_phase_validation_order_preserved": True,
        "python_version_unavailable": "FAIL_CLOSED_BEFORE_TERMINAL_PERSISTENCE", "empty_or_unknown_defaults": False,
        "new_scientific_fields_or_rules": False}
    design = {"schema_version": "R2MinimalVersionedRuntimeIdentityRepairDesign", "implementation_state": "DESIGN_ONLY_NOT_IMPLEMENTED",
        "functional_delta": "construct complete controller-owned identity once using existing runtime convention and reuse same immutable redacted identity for both exception captures",
        "correct_both_omission_sites": [sources["component_constructor"], sources["integration_constructor"]],
        "cannot_fix_harness_alone": "component builds its own incomplete non-None override independently",
        "cannot_fix_component_alone": "integration rebuilds incomplete identity; original signal equality binding must still hold",
        "prospective_surfaces": ["separate R2 runtime-identity capture adapter", "separate versioned phase-binding capture/integration adapter"],
        "narrow_dependency_fork_if_required": {
            "evidence": "R1 phase module binds capture_source_sha256 to its own file and implementation_identity to fixed R1 manifest; journal/resume/barrier statically import R1 modules",
            "required_versioned_isolation": "new R2 source bundle/manifest and explicit typed dependency wiring; preserve all R1 source bytes and schema versions",
            "permitted_mechanical_changes": "only prospective implementation identity, phase-capture dependency and matching typed reader/barrier dependency if unavoidable",
            "no_broad_journal_rewrite": True, "no_algorithm_storage_retry_barrier_change": True,
            "no_monkeypatch_of_frozen_globals_or_forged_R1_capture_hash": True},
        "new_run_directory_and_source_snapshot_required": True, "production_wiring_authorized": False,
        "immutable_authorities": ["R0 concrete phase-binding schema", "all 22A observability schemas", "22B mapping/retry delegation", "22C V1 journal", "R1 implementation/failed snapshot"],
        "validation_contract": "all original R0 fixtures plus new identity specs; first-rejection checks and fresh-process recoveries remain mandatory",
        "identity_schema_admission_not_sufficient_to_claim_whole_repair": True, "next_stage": NEXT}
    positive = {"fixture_id": "R2_RI_P01", "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED",
        "independent_expected_source": "unchanged R0 literal oracle plus existing 22A field contract; not SUT outputs",
        "input": "fresh offline synthetic same-attempt R0_P01 signal/context; complete actual controller identity; preserve occurrence/mapping BODY_READING and persistence RAW_RESPONSE_FROZEN",
        "python_version_expectation": "equals actual execution interpreter platform.python_version(); nonempty authoritative capture; never a hardcoded or placeholder runtime value",
        "identity_fields": contract["child_field_set_exact"], "same_captured_identity_used_for_occurrence_and_mapped_provenance": True,
        "required_checks": ["existing exception schema admission", "complete V2 observation/event schema", "same request/attempt binding", "actual lifecycle prefix", "raw path/hash/count quarantine", "unchanged semantic retry decision", "durable terminal fsync", "fresh-process V2 recovery"],
        "expected": {"schema_admission": True, "failure_terminal_commit": True, "logical_state": "RETRYABLE_FAILURE_WITH_BUDGET",
                     "attempts_consumed": 1, "remaining_attempts": 3, "next_ordinal": 2, "backoff_seconds": 2,
                     "partial_authoritative": False, "partial_parser_eligible": False},
        "failure_of_any_other_invariant_still_fails_closed": True}
    negative_rows = [
        ("RI01", "runtime_identity parent absent from exception record", "EXCEPTION_SCHEMA_ADMISSION", "SCHEMA_REQUIRED:$"),
        ("RI02", "runtime_identity present, python_version absent", "EXCEPTION_SCHEMA_ADMISSION", ERROR),
        ("RI03", "python_version has unsupported integer type, other fields valid", "EXCEPTION_SCHEMA_ADMISSION", "SCHEMA_TYPE:$.runtime_identity.python_version"),
        ("RI04", "wrong exception schema_version, otherwise schema-valid baseline", "EXCEPTION_SCHEMA_ADMISSION", "SCHEMA_CONST:$.schema_version"),
        ("RI05", "valid parent lost from exception member during event assembly/serialization", "POST_SERIALIZATION_EXCEPTION_SCHEMA_ADMISSION_BEFORE_APPEND", "SCHEMA_REQUIRED:$"),
        ("RI06", "valid exception identity envelope has different ordinal/request context, runtime child unchanged", "MAPPED_OBSERVATION_NESTED_CONTEXT_ADMISSION_BEFORE_FULL_TERMINAL", "NESTED_PROVENANCE_CONTEXT"),
    ]
    negatives = {"fixture_count": 6, "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED", "all_expected_fail_closed": True,
        "all_other_invariants_valid_to_isolate_first_rejection": True,
        "required_path_is_current_container_not_missing_key": True, "existing_runtime_child_does_not_bind_run_id_or_attempt": True,
        "fixtures": [{"fixture_id": key, "independent_perturbation": perturbation, "admission_stage": stage,
            "expected_first_rejection": error, "expected": {"durable_terminal_commit": False, "retry_dispatches": 0, "parser_invocations": 0},
            "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED"} for key, perturbation, stage, error in negative_rows],
        "RI06_full_terminal_order_note": "isolated existing nested-context admission stage, not bypass of phase binding; complete terminal run may reject earlier under unchanged R0 signal/context rules, which must be independently tested with original R0 oracles",
        "identity_fixture_specs_are_not_R11_runtime_execution": True}
    order = {"schema_version": "ProspectiveR2ValidationOrderContract", "execution_status": "NOT_EXECUTED",
        "stages": ["independent runtime-identity capture + new identity fixtures", "complete V2 observation/event schema", "R0 positive terminal commit",
                   "all 22 original negative first-rejection expectations", "committed-failure fresh-process recovery", "abandoned-attempt fresh-process recovery",
                   "durability/hash-chain/single-writer/terminal-uniqueness regressions", "legacy A/B/C behavior"],
        "early_failure_behavior": "preserve failure and stop according to separately frozen R2 execution protocol; no outcome-informed repair or oracle relaxation",
        "R2_execution_requires_separate_user_authorization": True, "independent_22DR_is_not_part_of_R2_or_R11": True}
    return design, contract, positive, negatives, order


def freeze_audit():
    documents = prepare_documents()
    before = documents["upstream_root_verification"]
    t.require(not OUT.exists(), "R11_OUTPUT_MUST_BE_NEW")
    store = t.RawArtifactStoreV1(OUT)
    def emit(stem, record):
        return store.freeze_bytes(stem + ".json", u.canonical(record))
    for stem, document in documents.items():
        emit(stem, document)
    store.freeze_bytes("audit_source.py", u.read_bytes(Path(__file__)))
    store.freeze_bytes("audit_tests.py", u.read_bytes(TEST))
    emit("audit_source_manifest", {"sources": [ref(Path(__file__), "new_forensic_audit_only_source"), ref(TEST, "focused_audit_schema_tests_only")],
                                   "R1_source_modification": False})
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error", str(TEST.relative_to(ROOT)), "--junitxml=" + str(OUT / "audit_tests.xml")]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    store.freeze_bytes("audit_tests.txt", (process.stdout + process.stderr).encode())
    print(process.stdout + process.stderr, flush=True)
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if (OUT / "audit_tests.xml").is_file():
        for suite in ET.parse(OUT / "audit_tests.xml").getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    comp = subprocess.run([sys.executable, "-m", "compileall", "-q", str(Path(__file__)), str(TEST)], cwd=ROOT, capture_output=True, text=True)
    checks = []
    for args in (["git", "diff", "--check"], ["git", "diff", "--no-index", "--check", "/dev/null", str(Path(__file__))],
                 ["git", "diff", "--no-index", "--check", "/dev/null", str(TEST)]):
        check = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        checks.append({"command": args, "exit_code": check.returncode, "diagnostics": check.stdout + check.stderr,
                       "passed": check.returncode in ({0} if len(args) == 3 else {0, 1}) and not check.stdout and not check.stderr})
    after = verify_authority()
    unchanged = u.canonical(before) == u.canonical(after)
    passed = process.returncode == 0 and counts["tests"] > 0 and not counts["failures"] and not counts["errors"] \
        and comp.returncode == 0 and all(check["passed"] for check in checks) and unchanged
    emit("historical_preservation_audit", {"frozen_roots_and_source_bindings_unchanged": unchanged,
        "before": ref(OUT / "upstream_root_verification.json", "verified_before_audit"), "after": after,
        "R1_runtime_source_bytes_unchanged": True, "archived_temporaries_not_traversed_or_mutated": True,
        "historical_assets_modified": not unchanged})
    emit("validation", {"passed": passed, "audit_schema_tests_only": True, "command": command, "exit_code": process.returncode,
        **counts, "test_output": ref(OUT / "audit_tests.txt", "actual_focused_schema_audit_test_log"),
        "compileall": {"exit_code": comp.returncode, "stdout": comp.stdout, "stderr": comp.stderr}, "whitespace_checks": checks,
        "R1_runtime_fixtures_executed": 0, "original_59_matrix_executed": False, "new_runtime_pass_claims": False,
        "isolated_schema_tests_do_not_validate_actual_runtime_capture": True,
        "all_repository_tests_executed": False, "historical_preservation_verified": unchanged, **NO_CALLS})
    emit("r1_runtime_identity_root_cause_evidence", {"classification": CLASSIFICATION, "detail": DIAGNOSIS,
        "audit_members": [ref(OUT / (stem + ".json"), "forensic_evidence_or_design") for stem in sorted(documents)],
        "source_manifest": ref(OUT / "audit_source_manifest.json", "source_binding"),
        "validation": ref(OUT / "validation.json", "audit_only_validation"),
        "historical_preservation": ref(OUT / "historical_preservation_audit.json", "post_audit_immutability_proof"),
        "runtime_repair_not_implemented_or_rerun": True})
    hashes = {}
    for marker, stem in MARKERS.items():
        hashes[marker] = u.sha(u.read_bytes(OUT / (stem + ".json")))
        store.freeze_bytes(marker, (hashes[marker] + "\n").encode())
    summary = {"status": "completed" if passed else "failed", "alpha3_22r11_classification": CLASSIFICATION,
        "original_r1_status_preserved": "failed", "actual_first_schema_rejection_path": "$.runtime_identity",
        "runtime_identity_parent_required": True, "python_version_required": True,
        "runtime_identity_parent_present_in_actual_event": True, "python_version_present_in_actual_event": False,
        "runtime_identity_first_loss_boundary": LOSS_BOUNDARY, "runtime_identity_source_authority_resolved": True,
        "schema_version_binding_correct": True, "serialization_drops_runtime_identity": False,
        "test_fixture_construction_defect": True, "component_capture_or_integration_defect": True,
        "r1_root_cause_resolved": True, "r1_root_cause_detail": DIAGNOSIS,
        "r0_positive_fixture_originally_passed": False, "r0_negative_fixture_count": 22,
        "r0_negative_fixture_original_pass_count": 19, "r0_negative_fixture_original_fail_count": 3,
        "n14_expected_first_rejection_reached": False, "n17_expected_first_rejection_reached": False,
        "n21_expected_first_rejection_reached": False, "rec01_passed": False, "rec02_executed": False,
        "remaining_phase_binding_validity": "NOT_FULLY_EVALUATED", "r2_versioned_repair_design_frozen": passed,
        "r1_source_modified": False, "r1_frozen_tests_rerun": False, "original_22d_matrix_rerun": False,
        "retry_policy_changed": False, "exception_mapping_table_changed": False, "scientific_policy_changed": False,
        "alpha3_21_reopened": False, "fresh_primary_attempt_started": False, "next_stage_recommendation": NEXT,
        "historical_assets_modified": not unchanged, "audit_test_counts": counts,
        "r2_correction_implemented": False, **before["counts"], **NO_CALLS, **hashes}
    emit("summary", summary)
    t.require(all((OUT / (stem + ".json")).is_file() for stem in REQUIRED), "REQUIRED_R11_ARTIFACT_MISSING")
    t.require(u.canonical(verify_authority()) == u.canonical(before), "FROZEN_AUTHORITY_DRIFT_BEFORE_SEAL")
    root = r0.d.master.root_hash(OUT, ROOT_MARKER)
    store.freeze_bytes(ROOT_MARKER, (root + "\n").encode())
    u.sync_directory(OUT)
    t.require(r0.d.master.root_hash(OUT, ROOT_MARKER) == root, "R11_ROOT_POST_FREEZE_MISMATCH")
    return {**summary, ROOT_MARKER: root, "workspace": str(OUT), "required_json_count": len(REQUIRED)}


if __name__ == "__main__":
    with r0.d.master.prior.offline_guard():
        print(json.dumps(freeze_audit(), ensure_ascii=False, sort_keys=True))
