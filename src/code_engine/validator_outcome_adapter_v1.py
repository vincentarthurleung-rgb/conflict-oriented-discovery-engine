"""Unwired completed-response validator-result propagation; no B mapping edits.

Transport mapping remains the unchanged B record. Response validity is the
separate, literal boolean result already owned by A.record_validation. Both
channels and the unmodified actual validator output are durably bound.
"""

from dataclasses import dataclass
from pathlib import Path

from . import append_only_attempt_journal_v2_r2 as base
from . import transport_failure_phase_binding_v2_r2 as phase

t, o, b = base.t, base.o, base.b
ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ACTIVATION_ALLOWED = False


def source_identity():
    return base.sha(base.read_bytes(Path(__file__)))


def contract(kind):
    definitions = {
        "literal_boolean": ("src/code_engine/transport_lifecycle_v2.py", "TransportLifecycleV2.record_validation", None),
        "jats_primary_identity_v2": ("scripts/search_plan_v24_alpha321_jats_primary_identity_v2.py",
                                     "validate_jats_primary_identity_v2", "source_identity_allows_progression")}
    t.require(type(kind) is str and kind in definitions, "UNAUTHORIZED_VALIDATOR_CONTRACT")
    path, function, projection = definitions[kind]
    return {"schema_version": "FrozenBooleanValidatorReturnContractV1", "kind": kind,
            "validator_source": {"artifact_path": path, "sha256": base.sha(base.read_bytes(ROOT / path))},
            "validator_function": function, "projection_field": projection,
            "true_semantic": "NO_TECHNICAL_FAILURE", "false_semantic": "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE",
            "unauthorized_return": "FAIL_CLOSED", "truthiness_coercion": False}


def contract_sha(kind):
    return base.sha(base.canonical(contract(kind)))


def accepted_result(actual, kind):
    rule = contract(kind)
    if rule["projection_field"] is None:
        value = actual
    else:
        t.require(type(actual) is dict and actual.get("schema_version") == "JATSPrimarySourceIdentityContractV2"
                  and rule["projection_field"] in actual, "UNSUPPORTED_VALIDATOR_RESULT")
        value = actual[rule["projection_field"]]
    t.require(type(value) is bool, "UNSUPPORTED_VALIDATOR_RESULT")
    return value


@dataclass(frozen=True)
class FrozenValidatorOutcomeV1:
    serialized: bytes
    artifact: t.RawArtifactV1

    def record(self):
        t.require(self.artifact.verified_bytes() == self.serialized, "VALIDATOR_RESULT_HASH_MISMATCH")
        return base.strict_json(self.serialized)


def record_result(writer, lifecycle, actual, *, kind, timestamp, response=None):
    t.require(type(lifecycle) is t.TransportLifecycleV2 and lifecycle.state == t.LifecycleState.RAW_RESPONSE_FROZEN
              and lifecycle.completion is not None and lifecycle.completion.body_completion_state == t.BodyState.COMPLETE
              and type(response) is t.FrozenTransportResponseV2 and response.context == lifecycle.context
              and response.completion == lifecycle.completion and response.parser_eligible,
              "VALIDATION_REQUIRES_AUTHORITATIVE_COMPLETE_RESPONSE")
    accepted = accepted_result(actual, kind)
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    t.require(request["validity_authority_sha256"] == contract_sha(kind), "VALIDATOR_AUTHORITY")
    # Consume the actual A result; never discard it or classify False as an
    # exception. None/0/empty objects have already been rejected above.
    semantic = lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=timestamp)
    writer.record_lifecycle(lifecycle, timestamp=timestamp)
    prefix = [event.record() for event in writer.verified().events]
    identity = phase.attempt_identity(writer.manifest, lifecycle.context, prefix)
    value = {"schema_version": "CompletedResponseValidatorOutcomeV1", "attempt_identity": identity,
             "validator_contract": contract(kind), "actual_validator_result": actual, "accepted": accepted,
             "response_validity_semantic": semantic.value, "transport_body_state": "BODY_COMPLETE",
             "scientific_eligibility_established": False,
             "raw_artifact": dict(response.artifact.__dict__),
             "validation_anchor": phase.event_ref(prefix[-1]), "adapter_source_sha256": source_identity()}
    raw = base.canonical(value)
    artifact = base.atomic_freeze(writer.directory / ("validator-outcome-" + identity["attempt_start_entry_hash"] + ".json"), raw)
    return FrozenValidatorOutcomeV1(raw, artifact)


def decision_for_outcome(lifecycle, outcome, request):
    saved = outcome.record()
    t.require(lifecycle.response_valid is saved["accepted"], "VALIDATION_NOT_RECORDED_BY_ALPHA322A")
    facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=lifecycle.completion)
    mapping = b.TransportExceptionMappingV2().classify(None, facts)
    t.require(mapping.semantic_failure_class == t.SemanticFailure.NO_TECHNICAL_FAILURE, "VALIDATOR_RESULT_CANNOT_REPLACE_TRANSPORT_FAILURE")
    semantic = t.SemanticFailure(saved["response_validity_semantic"])
    retry = t.semantic_retry_decision(semantic, request_replay_safe=request["replay_safe"], attempt_ordinal=lifecycle.context.attempt_ordinal)
    # A owns final semantic retry. B still describes transport only, unchanged.
    return b.ClassifiedRetryDecisionV2(mapping, retry)


def verify_terminal(payload, context, request, progress, manifest_sha, manifest, prefix, directory):
    base.exact_keys(payload, ("outcome", "mapped_observation", "retry_decision", "raw_artifact", "validation",
                             "eligibility", "failure_phase_binding", "validator_outcome"), "TERMINAL_FIELDS")
    t.require(payload["failure_phase_binding"] is None, "VALIDATOR_RESULT_NOT_EXCEPTION_OCCURRENCE")
    mapped = payload["mapped_observation"]
    base.exact_keys(mapped, ("schema_version", "mapping", "observation"), "MAPPED_OBSERVATION_FIELDS")
    t.require(mapped["schema_version"] == "MappedTransportObservationV2", "MAPPED_OBSERVATION_VERSION")
    observation = mapped["observation"]
    schemas = base._observation_schemas()
    o.validate_schema(observation, schemas["observation"])
    for key in schemas:
        if key != "observation" and observation[key] is not None:
            o.validate_schema(observation[key], schemas[key])
            t.require(all(observation[key][name] == value for name, value in context.record().items()), "NESTED_PROVENANCE_CONTEXT")
    t.require(all(observation[name] == value for name, value in context.record().items()), "OBSERVATION_CONTEXT")
    t.require(observation["exception_provenance"] is None, "VALIDATOR_RESULT_NOT_EXCEPTION_OCCURRENCE")
    t.require(observation["lifecycle_events"] == progress, "JOURNAL_LIFECYCLE_PROVENANCE_MISMATCH")
    t.require(progress and observation["lifecycle_state"] == progress[-1]["state"] == "RESPONSE_VALIDATION_COMPLETE",
              "TRUSTED_VALIDATED_HTTP_REQUIRED")
    raw = base.verify_artifact(payload["raw_artifact"])
    body, http = observation["body_read_provenance"], observation["http_response_provenance"]
    t.require(body is not None and body["completion_state"] == "BODY_COMPLETE" and body["read_returned_normally"] is True
              and body["complete_body_sha256"] == base.sha(raw) and body["bytes_read"] == len(raw)
              and body["complete_body_artifact_path"] == payload["raw_artifact"]["artifact_path"]
              and body["partial_body_artifact_path"] is None and body["partial_body_sha256"] is None, "COMPLETE_RAW_REQUIRED")
    t.require(http is not None and http["HTTP_provenance_trusted"] is True and http["status"] == 200
              and http["status_origin"] == "BOUND_HTTP_RESPONSE", "TRUSTED_VALIDATED_HTTP_REQUIRED")
    t.require(body["semantic_failure_state"] is None
              and (body["expected_content_length_bytes"] is None or body["expected_content_length_bytes"] == len(raw))
              and not any(item.get("authoritative") is True and item.get("passed") is not True
                          for item in body["framing_integrity_checks"]), "CONTRADICTORY_COMPLETE_BODY_EVIDENCE")
    reference = payload["validator_outcome"]
    saved = phase.read_evidence(reference, directory, "VALIDATOR_RESULT_HASH_MISMATCH")
    base.exact_keys(saved, ("schema_version", "attempt_identity", "validator_contract", "actual_validator_result", "accepted",
                           "response_validity_semantic", "transport_body_state", "scientific_eligibility_established",
                           "raw_artifact", "validation_anchor", "adapter_source_sha256"), "VALIDATOR_RESULT_FIELDS")
    identity = phase.attempt_identity(manifest, context, prefix)
    phase.check_identity(saved["attempt_identity"], identity)
    t.require(Path(reference["artifact_path"]) == base.physical(directory) / ("validator-outcome-" + identity["attempt_start_entry_hash"] + ".json"),
              "UNBOUND_VALIDATOR_RESULT")
    t.require(saved["schema_version"] == "CompletedResponseValidatorOutcomeV1"
              and saved["adapter_source_sha256"] == source_identity(), "VALIDATOR_RESULT_AUTHORITY")
    kind = saved["validator_contract"]["kind"]
    t.require(saved["validator_contract"] == contract(kind)
              and contract_sha(kind) == request["validity_authority_sha256"], "VALIDATOR_AUTHORITY")
    accepted = accepted_result(saved["actual_validator_result"], kind)
    semantic = t.SemanticFailure.NO_TECHNICAL_FAILURE if accepted is True else t.SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE
    t.require(saved["accepted"] is accepted and saved["response_validity_semantic"] == semantic.value
              and saved["transport_body_state"] == "BODY_COMPLETE" and saved["scientific_eligibility_established"] is False,
              "VALIDATOR_OUTCOME_CONFLICT")
    current = phase.attempt_records(prefix, identity)[-1]
    t.require(saved["validation_anchor"] == phase.event_ref(current)
              and current["event_type"] == "LIFECYCLE_PROGRESS"
              and current["event_payload"]["lifecycle_event"]["state"] == "RESPONSE_VALIDATION_COMPLETE"
              and current["event_payload"]["lifecycle_event"]["evidence_reference"] == request["validity_authority_sha256"],
              "VALIDATOR_LIFECYCLE_BINDING")
    t.require(saved["raw_artifact"] == payload["raw_artifact"], "RAW_ARTIFACT_HASH_MISMATCH")
    # Reconstruct complete structured transport facts from preserved body
    # evidence, not from a fabricated exception or validator failure label.
    completion = t.assess_body_completion(raw, read_returned_normally=True, timestamp=body["body_read_ended_at"])
    facts = b.TransportMappingFactsV2(t.LifecycleState.RESPONSE_VALIDATION_COMPLETE, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=completion)
    t.require(mapped["mapping"] == b.TransportExceptionMappingV2().classify(None, facts).record(), "VALIDATOR_RESULT_CANNOT_REPLACE_TRANSPORT_FAILURE")
    expected_retry = phase.primitive(t.semantic_retry_decision(semantic,
        request_replay_safe=request["replay_safe"], attempt_ordinal=context.attempt_ordinal))
    t.require(base.canonical(payload["retry_decision"]) == base.canonical(expected_retry), "PERSISTED_RETRY_DECISION_INCONSISTENT")
    base.exact_keys(payload["validation"], ("authority_sha256", "accepted"), "VALIDATION_FIELDS")
    t.require(payload["validation"]["authority_sha256"] == request["validity_authority_sha256"]
              and payload["validation"]["accepted"] is accepted, "VALIDATOR_OUTCOME_CONFLICT")
    outcome = payload["outcome"]
    t.require(accepted is (outcome != "TERMINAL_RESPONSE_VALIDITY_FAILURE"), "VALIDATOR_OUTCOME_CONFLICT")
    if accepted is False:
        t.require(outcome == "TERMINAL_RESPONSE_VALIDITY_FAILURE" and payload["eligibility"] is None,
                  "VALIDITY_FAILURE_OUTCOME_CONFLICT")
    else:
        t.require(outcome in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"}, "VALIDATOR_OUTCOME_CONFLICT")
        base.exact_keys(payload["eligibility"], ("authority_sha256", "eligible"), "ELIGIBILITY_FIELDS")
        t.require(type(payload["eligibility"]["eligible"]) is bool
                  and payload["eligibility"]["authority_sha256"] == request["eligibility_authority_sha256"]
                  and payload["eligibility"]["eligible"] is (outcome == "VALID_SUCCESS"), "ELIGIBILITY_OUTCOME_CONFLICT")
    retry = t.semantic_retry_decision(semantic, request_replay_safe=request["replay_safe"], attempt_ordinal=context.attempt_ordinal)
    replay = {"manifest_sha256": manifest_sha, "request_id": request["request_id"]} if request["replay_safe"] else None
    provenance = o.RetryDecisionProvenanceV1.capture(context, o.SecretRedactorV1(), retry, replay_safety_authority=replay)
    t.require(observation["retry_decision_provenance"] == provenance.record(), "RETRY_PROVENANCE_INCONSISTENT")
    return observation
