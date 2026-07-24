from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.conflict_candidate.identities import (
    conflict_candidate_identity,
)
from code_engine.context_attribution.conflict_candidate.models import ConflictCandidate
from code_engine.context_attribution.conflict_comparability.identities import (
    conflict_comparability_identity,
)
from code_engine.context_attribution.conflict_comparability.models import (
    ConflictComparabilityAssessment,
)
from code_engine.context_attribution.conflict_comparability.validation import (
    validate_conflict_comparability,
)
from code_engine.context_attribution.conflict_judgment.gate import (
    stage_formal_conflict_decision,
)
from code_engine.context_attribution.context_difference.identities import (
    context_difference_identity,
)
from code_engine.context_attribution.context_difference.models import (
    ContextDifference,
    FactorDifference,
)
from code_engine.context_attribution.context_difference.validation import (
    validate_context_difference,
)
from code_engine.context_attribution.observation_context.identities import (
    observation_context_identity,
)
from code_engine.context_attribution.observation_context.models import (
    ObservationContext,
)

ROOT = Path(__file__).parents[1]
RUN = ROOT / "runs/20260725_hif1a_context_pipeline_layer_split_v1_offline/artifacts"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


@pytest.fixture
def ebd5():
    candidates = {
        item["candidate_id"]: ConflictCandidate.model_validate(item)
        for item in _jsonl(RUN / "conflict_candidates.jsonl")
    }
    difference = ContextDifference.model_validate(
        _jsonl(RUN / "context_differences.jsonl")[0]
    )
    contexts = {
        item["observation_id"]: ObservationContext.model_validate(item)
        for item in _jsonl(RUN / "observation_contexts.jsonl")
    }
    comparability = ConflictComparabilityAssessment.model_validate(
        _jsonl(RUN / "conflict_comparability_assessments.jsonl")[0]
    )
    candidate = candidates[difference.candidate_id]
    return (
        candidate,
        difference,
        contexts[candidate.observation_a_id],
        contexts[candidate.observation_b_id],
        comparability,
    )


@pytest.mark.parametrize(
    "forbidden",
    ["pair_id", "comparability_effect", "formal_conflict_eligible"],
)
def test_observation_context_rejects_pairwise_fields(ebd5, forbidden):
    payload = ebd5[2].model_dump()
    payload[forbidden] = "forbidden"
    with pytest.raises(ValidationError):
        ObservationContext.model_validate(payload)


def test_observation_context_has_no_comparability_dependency():
    package = ROOT / "src/code_engine/context_attribution/observation_context"
    imported = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported.extend(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, (ast.ImportFrom,))
        )
    assert not any("conflict_comparability" in module for module in imported)


@pytest.mark.parametrize(
    "forbidden,value",
    [
        ("comparability_effect", "none"),
        ("comparability_class", "comparable"),
        ("formal_conflict_eligible", True),
        ("confirmed_conflict", True),
    ],
)
def test_context_difference_rejects_decision_fields(ebd5, forbidden, value):
    payload = ebd5[1].model_dump()
    payload[forbidden] = value
    with pytest.raises(ValidationError):
        ContextDifference.model_validate(payload)


@pytest.mark.parametrize(
    "status,a,b,valid",
    [
        ("same", "x", "x", True),
        ("different", "x", "y", True),
        ("missing_a", None, "y", True),
        ("missing_b", "x", None, True),
        ("missing_both", None, None, True),
        ("same", None, None, False),
        ("different", "x", None, False),
        ("missing_a", "x", "y", False),
    ],
)
def test_context_difference_status_value_matrix(status, a, b, valid):
    payload = {
        "factor_id": "species",
        "status": status,
        "claim_a_value": a,
        "claim_b_value": b,
        "comparison_rationale": "fixture",
        "provenance": {},
    }
    if valid:
        FactorDifference.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            FactorDifference.model_validate(payload)


def test_context_difference_rejects_empty_string():
    with pytest.raises(ValidationError):
        FactorDifference.model_validate(
            {
                "factor_id": "species",
                "status": "same",
                "claim_a_value": "",
                "claim_b_value": "",
                "comparison_rationale": "fixture",
                "provenance": {},
            }
        )


def test_legacy_pair_projection_drops_effect_and_audits_it():
    difference = _jsonl(RUN / "context_differences.jsonl")[0]
    audit = _jsonl(RUN / "context_difference_adapter_audit.jsonl")[0]
    assert "comparability_effect" not in json.dumps(difference)
    legacy = audit["legacy_non_authoritative_comparability_fields"]
    assert all("comparability_effect" in item for item in legacy["factor_fields"])
    assert audit["status_or_value_modified"] is False
    assert audit["anchor_modified_or_created"] is False
    assert audit["new_comparability_created"] is False


def test_ebd5_real_fixture_independent_difference_validation(ebd5):
    candidate, difference, context_a, context_b, _ = ebd5
    known = {item.factor_id for item in difference.factor_differences}
    _, errors = validate_context_difference(
        difference,
        candidate=candidate,
        context_a=context_a,
        context_b=context_b,
        known_factor_ids=known,
    )
    assert errors == []
    assert difference.validation_status == "validated"


def test_difference_success_does_not_validate_comparability(ebd5):
    assert ebd5[1].validation_status == "validated"
    assert ebd5[4].assessment_status == "pending_policy"
    assert ebd5[4].validation_status == "unvalidated"


def test_comparability_requires_validated_difference_identity(ebd5):
    candidate, difference, _, _, comparability = ebd5
    payload = comparability.model_dump()
    payload["context_difference_identity"] = "drift"
    payload["conflict_comparability_identity"] = conflict_comparability_identity(
        payload
    )
    drifted = ConflictComparabilityAssessment.model_validate(payload)
    _, errors = validate_conflict_comparability(
        drifted, candidate=candidate, difference=difference
    )
    assert "comparability_upstream_identity_mismatch" in errors


@pytest.mark.parametrize("field", ["comparability_effect", "provider_effect"])
def test_raw_provider_effect_cannot_enter_comparability(ebd5, field):
    payload = ebd5[4].model_dump()
    payload[field] = "none"
    with pytest.raises(ValidationError):
        ConflictComparabilityAssessment.model_validate(payload)


def test_pending_comparability_is_fail_closed(ebd5):
    candidate, difference, _, _, comparability = ebd5
    decision = stage_formal_conflict_decision(
        candidate=candidate,
        difference=difference,
        comparability=comparability,
    )
    assert decision.decision_status == "blocked_comparability_pending"
    assert decision.formal_conflict_confirmed is False


def test_difference_unvalidated_blocks_formal_gate(ebd5):
    candidate, difference, _, _, comparability = ebd5
    bad = difference.model_copy(update={"validation_status": "rejected"})
    decision = stage_formal_conflict_decision(
        candidate=candidate, difference=bad, comparability=comparability
    )
    assert decision.decision_status == "blocked_difference_unvalidated"


def test_context_unavailable_does_not_delete_candidate():
    candidates = _jsonl(RUN / "conflict_candidates.jsonl")
    assert len(candidates) == 11
    assert any(item["context_readiness"] != "context_ready" for item in candidates)
    assert all(item["validation_status"] == "validated" for item in candidates)


def test_candidate_identity_does_not_bind_comparability(ebd5):
    candidate = ebd5[0].model_dump()
    identity = conflict_candidate_identity(candidate)
    candidate["provenance"]["legacy_comparability_fields_non_authoritative"] = {}
    assert conflict_candidate_identity(candidate) == identity
    assert "comparability" not in json.dumps(
        {
            key: candidate[key]
            for key in (
                "candidate_id",
                "canonical_edge_identity",
                "observation_a_id",
                "observation_b_id",
                "claim_a_identity",
                "claim_b_identity",
                "disagreement_signal",
                "candidate_reason",
                "candidate_generation_version",
            )
        }
    )


def test_candidate_count_and_ids_preserved():
    summary = _json(RUN / "context_pipeline_layer_summary.json")
    assert summary["candidate_pair_count_before"] == 11
    assert summary["candidate_pair_count_after"] == 11
    assert summary["candidate_pair_ids_before"] == summary["candidate_pair_ids_after"]
    assert summary["candidate_pair_identity_changed"] is False


def test_observation_context_identity_drift_blocks_difference(ebd5):
    candidate, difference, context_a, context_b, _ = ebd5
    payload = context_a.model_dump()
    payload["normalized_polarity"] = "drift"
    payload["observation_context_identity"] = observation_context_identity(payload)
    drifted = ObservationContext.model_validate(payload)
    _, errors = validate_context_difference(
        difference,
        candidate=candidate,
        context_a=drifted,
        context_b=context_b,
        known_factor_ids={item.factor_id for item in difference.factor_differences},
    )
    assert "context_difference_endpoint_identity_mismatch" in errors


def test_difference_identity_drift_blocks_comparability(ebd5):
    candidate, difference, _, _, comparability = ebd5
    payload = difference.model_dump()
    payload["prompt_identity"] = "drift"
    payload["context_difference_identity"] = context_difference_identity(payload)
    drifted = ContextDifference.model_validate(payload)
    _, errors = validate_conflict_comparability(
        comparability, candidate=candidate, difference=drifted
    )
    assert "comparability_upstream_identity_mismatch" in errors


def test_observation_context_adapter_did_not_fill_data():
    audits = _jsonl(RUN / "observation_context_adapter_audit.jsonl")
    assert len(audits) == 5
    assert all(item["source_payload_modified"] is False for item in audits)
    assert all(item["span_or_component_synthesized"] is False for item in audits)
    assert all(item["value_synthesized"] is False for item in audits)


def test_failed_observation_contexts_remain_fail_closed():
    audits = _jsonl(RUN / "observation_context_validation_audit.jsonl")
    failures = [item for item in audits if not item["valid"]]
    assert len(failures) == 2
    assert all(
        item["failure_class"] == "observation_context_policy_coverage_failure"
        for item in failures
    )
    assert all(
        any(error.startswith("rule_derivation_failed") for error in item["errors"])
        for item in failures
    )


def test_offline_boundary_and_no_activation():
    summary = _json(RUN / "context_pipeline_layer_summary.json")
    for key in (
        "provider_calls",
        "api_calls",
        "real_api_calls",
        "network_calls",
        "downloads",
    ):
        assert summary[key] == 0
    for key in (
        "credential_values_read",
        "provider_client_created",
        "historical_runs_modified",
        "formal_v3_modified",
        "projection_modified",
        "candidate_pairs_modified",
        "handoff_created",
        "atlas_activated",
        "active_pointer_changed",
        "variational_em_called",
    ):
        assert summary[key] is False


def test_historical_source_hashes_still_match():
    manifest = _json(RUN / "context_pipeline_layer_manifest.json")
    assert manifest["source_hashes_verified_after_materialization"] is True
    for raw_path, expected in manifest["source_hashes"].items():
        import hashlib

        assert hashlib.sha256((ROOT / raw_path).read_bytes()).hexdigest() == expected


def test_effect_contract_scope_migration():
    migration = _json(RUN / "effect_contract_scope_migration.json")
    assert migration["legacy_context_scoped_contract_identity"] == (
        "249f9024e11ac9f0732560a42082561676ddc3fe8dbdd0258fe2012ef5284c24"
    )
    assert migration["historical_identity_preserved"] is True
    assert migration["runtime_activation"] is False
    assert migration[
        "conflict_comparability_effect_semantic_contract_identity_v1"
    ] != migration["legacy_context_scoped_contract_identity"]


def test_docs_and_schema_scope():
    architecture_adr = (
        ROOT
        / "docs/adr/ADR-observation-context-conflict-comparability-separation-v1.md"
    ).read_text(encoding="utf-8")
    effect_adr = (
        ROOT / "docs/adr/ADR-conflict-comparability-effect-semantics-v1.md"
    ).read_text(encoding="utf-8")
    schema = _json(
        ROOT
        / "docs/contracts/conflict_comparability_effect_adjudication_v1.schema.json"
    )
    assert "Status: **Accepted**" in architecture_adr
    assert "Status: **Proposed**" in effect_adr
    assert schema["title"] == "Conflict Comparability Effect Adjudication v1"
    assert "conflict_comparability" in schema["$id"]


def test_layer_json_schemas_have_scoped_titles_and_ids():
    models = (
        ObservationContext,
        ConflictCandidate,
        ContextDifference,
        ConflictComparabilityAssessment,
    )
    for model in models:
        schema = model.model_json_schema()
        assert schema["$id"].startswith(
            "https://conflict-oriented-discovery-engine.local/schemas/"
        )
        assert "Context Pair Attribution" not in schema["title"]


def test_formal_staging_does_not_confirm_or_modify_production():
    decisions = _jsonl(RUN / "formal_conflict_decisions_staging.jsonl")
    assert len(decisions) == 11
    assert all(item["authority_scope"] == "staging_only" for item in decisions)
    assert not any(item["formal_conflict_confirmed"] for item in decisions)
    assert all(item["provenance"]["formal_v3_modified"] is False for item in decisions)


def test_new_pipeline_never_outputs_mixed_pair_schema():
    manifest = _json(RUN / "context_pipeline_layer_manifest.json")
    assert not any(
        "context_pair_attributions" in path for path in manifest["artifacts"]
    )
    all_new = "".join(
        path.read_text(encoding="utf-8")
        for path in RUN.glob("*.jsonl")
        if "adapter_audit" not in path.name
    )
    assert '"schema_version": "context_pair_attribution_' not in all_new


def test_legacy_cli_is_explicitly_deprecated():
    source = (
        ROOT / "src/code_engine/cli/context_attribution.py"
    ).read_text(encoding="utf-8")
    assert "DeprecationWarning" in source
    assert "offline_split" in source
