from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.claim_alignment.identities import (
    claim_alignment_identity,
)
from code_engine.context_attribution.claim_alignment.models import AlignedClaimGroup
from code_engine.context_attribution.conflict_adjudication.bundle import (
    FactorAttributionBundle,
    build_factor_attribution_bundle,
    validate_factor_attribution_bundle,
)
from code_engine.context_attribution.conflict_adjudication.comparability.identities import (
    factor_comparability_identity,
)
from code_engine.context_attribution.conflict_adjudication.comparability.models import (
    FactorComparabilityAssessment,
)
from code_engine.context_attribution.conflict_adjudication.comparability.validation import (
    validate_factor_comparability,
)
from code_engine.context_attribution.conflict_adjudication.decision.service import (
    adjudicate_pair_staging,
)
from code_engine.context_attribution.conflict_adjudication.divergence_explanation.identities import (
    factor_divergence_explanation_identity,
)
from code_engine.context_attribution.conflict_adjudication.divergence_explanation.models import (
    FactorDivergenceExplanation,
)
from code_engine.context_attribution.conflict_adjudication.divergence_explanation.validation import (
    validate_divergence_explanation,
)
from code_engine.context_attribution.conflict_candidate.contradiction import (
    ContradictionSignal,
    contradiction_signal_identity,
    validate_contradiction_signal,
)
from code_engine.context_attribution.conflict_candidate.models import ConflictCandidate
from code_engine.context_attribution.context_difference.migration import (
    ContextDifferenceMigrationBinding,
)
from code_engine.context_attribution.context_difference.models import ContextDifference
from code_engine.context_attribution.layer_identity import layer_identity

ROOT = Path(__file__).parents[1]
RUN = (
    ROOT
    / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts"
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def chain():
    candidates = {
        item["candidate_id"]: ConflictCandidate.model_validate(item)
        for item in _jsonl(RUN / "conflict_candidates.jsonl")
    }
    alignments = {
        item["provenance"]["legacy_candidate_id"]: AlignedClaimGroup.model_validate(
            item
        )
        for item in _jsonl(RUN / "aligned_claim_groups.jsonl")
    }
    signals = {
        item["signal_provenance"]["candidate_id"]: ContradictionSignal.model_validate(
            item
        )
        for item in _jsonl(RUN / "contradiction_signals.jsonl")
    }
    difference = ContextDifference.model_validate(
        _jsonl(RUN / "context_differences.jsonl")[0]
    )
    binding = ContextDifferenceMigrationBinding.model_validate(
        {
            **_jsonl(RUN / "context_difference_migration_audit.jsonl")[0],
        }
    ) if False else None
    # The full binding is recoverable from the factor artifacts; load it by
    # recreating the schema payload from the generated chain audit fields.
    candidate_id = difference.candidate_id
    comp = [
        FactorComparabilityAssessment.model_validate(item)
        for item in _jsonl(RUN / "factor_comparability_assessments.jsonl")
        if item["pair_id"] == candidate_id
    ]
    exp = [
        FactorDivergenceExplanation.model_validate(item)
        for item in _jsonl(RUN / "factor_divergence_explanations.jsonl")
        if item["pair_id"] == candidate_id
    ]
    migration_audit = _jsonl(RUN / "context_difference_migration_audit.jsonl")[0]
    candidate_binding = next(
        item
        for item in _jsonl(RUN / "candidate_migration_bindings.jsonl")
        if item["candidate_id"] == candidate_id
    )
    binding_payload = {
        "schema_version": "context_difference_alignment_signal_binding_v1",
        "context_difference_identity": difference.context_difference_identity,
        "claim_alignment_identity": migration_audit["claim_alignment_identity"],
        "contradiction_signal_identity": migration_audit[
            "contradiction_signal_identity"
        ],
        "conflict_candidate_identity": difference.conflict_candidate_identity,
        "candidate_migration_binding_identity": candidate_binding[
            "migration_binding_identity"
        ],
        "observation_context_a_identity": difference.observation_context_a_identity,
        "observation_context_b_identity": difference.observation_context_b_identity,
        "migration_binding_identity": comp[0].context_difference_binding_identity,
        "validation_status": "validated",
        "provenance": {
            "original_context_difference_modified": False,
            "status_value_anchor_modified": False,
            "binding_is_sidecar": True,
        },
    }
    binding = ContextDifferenceMigrationBinding.model_validate(binding_payload)
    bundle = FactorAttributionBundle.model_validate(
        _jsonl(RUN / "factor_attribution_bundles.jsonl")[0]
    )
    return (
        candidates[candidate_id],
        alignments[candidate_id],
        signals[candidate_id],
        difference,
        binding,
        comp,
        exp,
        bundle,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("comparability_effect", "none"),
        ("comparability_class", "comparable"),
        ("formal_conflict_eligible", True),
        ("confirmed_conflict", True),
    ],
)
def test_alignment_rejects_downstream_fields(chain, field, value):
    payload = chain[1].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        AlignedClaimGroup.model_validate(payload)


def test_proposition_signature_is_source_and_observation_id_free(chain):
    signature = json.dumps(
        chain[1].canonical_proposition_signature.model_dump(), ensure_ascii=False
    )
    assert "ftl1v3_" not in signature
    assert "PMC" not in signature
    assert "33282728" not in signature
    assert "/home/" not in signature


def test_unresolved_critical_dimension_cannot_auto_align(chain):
    payload = chain[1].model_dump()
    payload["alignment_status"] = "aligned"
    payload["claim_alignment_identity"] = claim_alignment_identity(payload)
    with pytest.raises(ValidationError):
        AlignedClaimGroup.model_validate(payload)


def test_historical_candidate_preserved_without_authorizing_future_candidate():
    bindings = _jsonl(RUN / "candidate_migration_bindings.jsonl")
    assert len(bindings) == 11
    assert all(item["historical_candidate_preserved"] for item in bindings)
    assert not any(
        item["provenance"]["future_candidate_generation_authorized"]
        for item in bindings
    )


def test_context_failure_does_not_delete_historical_candidate():
    candidates = _jsonl(RUN / "conflict_candidates.jsonl")
    assert len(candidates) == 11
    assert any(item["context_readiness"] != "context_ready" for item in candidates)


def test_alignment_identity_does_not_bind_effect_contract(chain):
    payload = chain[1].model_dump()
    identity = claim_alignment_identity(payload)
    payload["provenance"]["unrelated_effect_contract"] = "changed"
    assert claim_alignment_identity(payload) == identity


def _imports(package: Path) -> list[str]:
    modules = []
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules.extend(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
    return modules


def test_alignment_does_not_import_l4():
    imports = _imports(ROOT / "src/code_engine/context_attribution/claim_alignment")
    assert not any(
        name
        for name in imports
        if "context_difference" in name or "conflict_adjudication" in name
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("comparability_effect", "none"),
        ("explanatory_effect", "potentially_explanatory"),
        ("formal_conflict_confirmed", True),
    ],
)
def test_signal_rejects_l4_and_formal_fields(chain, field, value):
    payload = chain[2].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        ContradictionSignal.model_validate(payload)


def test_signal_references_and_validates_alignment(chain):
    _, errors = validate_contradiction_signal(chain[2], alignment=chain[1])
    assert errors == []
    drift = chain[1].model_copy(
        update={"claim_alignment_identity": "alignment-drift"}
    )
    _, errors = validate_contradiction_signal(chain[2], alignment=drift)
    assert "contradiction_alignment_identity_mismatch" in errors


def test_signal_direction_sources_are_explicit(chain):
    assert chain[2].signal_type == "opposite_direction"
    assert {chain[2].claim_a_direction, chain[2].claim_b_direction} == {
        "positive",
        "negative",
    }
    assert chain[2].signal_status == "validated"


def test_signal_identity_excludes_context_effect(chain):
    payload = chain[2].model_dump()
    identity = contradiction_signal_identity(payload)
    payload["signal_provenance"]["context_effect"] = "none"
    assert contradiction_signal_identity(payload) == identity


def test_candidate_sidecar_binds_alignment_and_signal_without_id_change(chain):
    binding = next(
        item
        for item in _jsonl(RUN / "candidate_migration_bindings.jsonl")
        if item["candidate_id"] == chain[0].candidate_id
    )
    assert binding["legacy_candidate_identity"] == chain[0].conflict_candidate_identity
    assert binding["claim_alignment_identity"] == chain[1].claim_alignment_identity
    assert (
        binding["contradiction_signal_identity"]
        == chain[2].contradiction_signal_identity
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("comparability_effect", "none"),
        ("comparability_class", "comparable"),
        ("explanatory_effect", "potentially_explanatory"),
        ("formal_status", "confirmed"),
    ],
)
def test_difference_still_rejects_attribution_fields(chain, field, value):
    payload = chain[3].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        ContextDifference.model_validate(payload)


def test_difference_sidecar_binds_alignment_and_signal(chain):
    audit = _jsonl(RUN / "context_difference_migration_audit.jsonl")[0]
    assert audit["valid"] is True
    assert audit["claim_alignment_identity"] == chain[1].claim_alignment_identity
    assert audit["contradiction_signal_identity"] == (
        chain[2].contradiction_signal_identity
    )
    assert audit["original_difference_modified"] is False
    assert audit["status_value_anchor_modified"] is False


def test_real_difference_remains_valid_with_eight_unchanged_factors(chain):
    assert chain[3].validation_status == "validated"
    assert len(chain[3].factor_differences) == 8
    source = _jsonl(
        ROOT
        / "runs/20260725_hif1a_context_pipeline_layer_split_v1_offline/artifacts/context_differences.jsonl"
    )[0]
    assert chain[3].model_dump(mode="json") == source


def test_difference_valid_does_not_validate_attribution(chain):
    assert chain[3].validation_status == "validated"
    assert all(item.validation_status == "unvalidated" for item in chain[5])
    assert all(item.validation_status == "unvalidated" for item in chain[6])


@pytest.mark.parametrize(
    "field,value",
    [
        ("explanatory_effect", "not_explanatory"),
        ("divergence_explanation", "anything"),
    ],
)
def test_comparability_cannot_contain_explanation(chain, field, value):
    payload = chain[5][0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        FactorComparabilityAssessment.model_validate(payload)


def test_pending_comparability_keeps_effect_null(chain):
    for item in chain[5]:
        assert item.assessment_status == "pending_policy"
        assert item.effect_assessment_status is None
        assert item.comparability_severity is None
        assert item.provenance["missing_mapped_to_unknown"] is False
        assert item.provenance["severity_automatically_assigned"] is False
        assert item.provenance["model_b_activated"] is False


def test_comparability_requires_validated_difference(chain):
    bad = chain[3].model_copy(update={"validation_status": "rejected"})
    _, errors = validate_factor_comparability(
        chain[5][0], difference=bad, difference_binding=chain[4]
    )
    assert "factor_comparability_requires_validated_difference" in errors


def test_legacy_provider_effect_has_no_comparability_authority(chain):
    assert all(
        item.provenance["legacy_provider_effect_consumed"] is False
        for item in chain[5]
    )


@pytest.mark.parametrize(
    "status,effect,valid",
    [
        ("pending_policy", None, True),
        ("not_assessed", None, True),
        ("insufficient_information", None, True),
        ("pending_policy", "not_explanatory", False),
        ("insufficient_information", "potentially_explanatory", False),
    ],
)
def test_divergence_explanation_null_state_contract(chain, status, effect, valid):
    payload = chain[6][0].model_dump()
    payload["assessment_status"] = status
    payload["explanatory_effect"] = effect
    payload["factor_divergence_explanation_identity"] = (
        factor_divergence_explanation_identity(payload)
    )
    if valid:
        FactorDivergenceExplanation.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            FactorDivergenceExplanation.model_validate(payload)


def test_assessed_explanation_requires_authority(chain):
    payload = chain[6][0].model_dump()
    payload["assessment_status"] = "assessed"
    payload["explanatory_effect"] = "potentially_explanatory"
    payload["factor_divergence_explanation_identity"] = (
        factor_divergence_explanation_identity(payload)
    )
    with pytest.raises(ValidationError):
        FactorDivergenceExplanation.model_validate(payload)


def test_explanation_requires_difference_and_signal(chain):
    bad_difference = chain[3].model_copy(update={"validation_status": "rejected"})
    _, errors = validate_divergence_explanation(
        chain[6][0],
        difference=bad_difference,
        difference_binding=chain[4],
        signal=chain[2],
    )
    assert "explanation_requires_validated_difference" in errors
    bad_signal = chain[2].model_copy(update={"validation_status": "rejected"})
    _, errors = validate_divergence_explanation(
        chain[6][0],
        difference=chain[3],
        difference_binding=chain[4],
        signal=bad_signal,
    )
    assert "explanation_requires_validated_signal" in errors


def test_explanation_does_not_map_comparability_or_factor_names(chain):
    for item in chain[6]:
        assert item.explanatory_effect is None
        assert item.provenance["comparability_mapped_to_explanation"] is False
        assert item.provenance["factor_name_rule_used"] is False
        assert item.provenance["provider_raw_text_consumed"] is False


def test_factor_bundle_is_reference_only_and_pending(chain):
    bundle = chain[7]
    assert len(bundle.comparability_assessment_ids) == 8
    assert len(bundle.divergence_explanation_ids) == 8
    assert bundle.all_comparability_assessed is False
    assert bundle.all_explanations_assessed is False
    assert bundle.pending_factor_ids
    dumped = bundle.model_dump()
    assert "max_severity" not in dumped
    assert "aggregate_explanatory_score" not in dumped
    assert "automatic_pair_class" not in dumped


def test_bundle_identity_drift_is_rejected(chain):
    drifted = chain[5][0].model_copy(
        update={"factor_comparability_identity": "drift"}
    )
    errors = validate_factor_attribution_bundle(
        chain[7], comparability=[drifted, *chain[5][1:]], explanations=chain[6]
    )
    assert "comparability_bundle_identity_drift" in errors


def _validated_comp(item, severity="none"):
    payload = item.model_dump()
    payload.update(
        {
            "assessment_status": "validated",
            "effect_assessment_status": "assessed",
            "comparability_severity": severity,
            "comparability_policy_identity": "approved-policy",
            "validation_status": "validated",
        }
    )
    payload["provenance"]["authority_validated"] = True
    payload["factor_comparability_identity"] = factor_comparability_identity(payload)
    return FactorComparabilityAssessment.model_validate(payload)


def _assessed_exp(item, effect="not_explanatory"):
    payload = item.model_dump()
    payload.update(
        {
            "assessment_status": "assessed",
            "explanatory_effect": effect,
            "explanation_policy_identity": "approved-policy",
            "validation_status": "validated",
        }
    )
    payload["provenance"]["authority_validated"] = True
    payload["factor_divergence_explanation_identity"] = (
        factor_divergence_explanation_identity(payload)
    )
    return FactorDivergenceExplanation.model_validate(payload)


def _decision(chain, *, alignment=None, signal=None, candidate=None, difference=None,
              comp=None, exp=None):
    alignment = alignment or chain[1]
    signal = signal or chain[2]
    candidate = candidate or chain[0]
    difference = difference if difference is not None else chain[3]
    comp = comp if comp is not None else chain[5]
    exp = exp if exp is not None else chain[6]
    bundle = build_factor_attribution_bundle(
        pair_id=candidate.candidate_id,
        context_difference_identity=chain[3].context_difference_identity,
        comparability=comp,
        explanations=exp,
    )
    return adjudicate_pair_staging(
        alignment=alignment,
        signal=signal,
        candidate=candidate,
        difference=difference,
        difference_binding=chain[4],
        bundle=bundle,
        comparability=comp,
        explanations=exp,
    )


def test_ebd5_adjudication_fails_closed_on_partial_alignment(chain):
    decision = _decision(chain)
    assert chain[1].alignment_status == "partially_aligned"
    assert decision.adjudication_status == "blocked_alignment_unvalidated"
    assert decision.formal_conflict_confirmed is False


def test_unvalidated_signal_blocks_adjudication(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    signal = chain[2].model_copy(update={"validation_status": "rejected"})
    assert _decision(chain, alignment=aligned, signal=signal).adjudication_status == (
        "blocked_contradiction_unvalidated"
    )


def test_context_unavailable_blocks_adjudication(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    candidate = chain[0].model_copy(update={"context_readiness": "context_partial"})
    assert _decision(chain, alignment=aligned, candidate=candidate).adjudication_status == (
        "blocked_context_unavailable"
    )


def test_difference_unvalidated_blocks_adjudication(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    difference = chain[3].model_copy(update={"validation_status": "rejected"})
    assert _decision(chain, alignment=aligned, difference=difference).adjudication_status == (
        "blocked_difference_unvalidated"
    )


def test_either_attribution_branch_pending_blocks_adjudication(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    comp = [_validated_comp(item) for item in chain[5]]
    assert _decision(chain, alignment=aligned, comp=comp).adjudication_status == (
        "blocked_attribution_pending"
    )
    exp = [_assessed_exp(item) for item in chain[6]]
    assert _decision(chain, alignment=aligned, exp=exp).adjudication_status == (
        "blocked_attribution_pending"
    )


def test_non_comparable_and_sufficient_explanation_are_distinct(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    comp = [_validated_comp(item) for item in chain[5]]
    comp[0] = _validated_comp(chain[5][0], "blocking")
    exp = [_assessed_exp(item) for item in chain[6]]
    exp[0] = _assessed_exp(chain[6][0], "sufficiently_explanatory")
    assert _decision(
        chain, alignment=aligned, comp=comp, exp=exp
    ).adjudication_status == "non_comparable"
    comp[0] = _validated_comp(chain[5][0], "none")
    assert _decision(
        chain, alignment=aligned, comp=comp, exp=exp
    ).adjudication_status == "context_explained_divergence"


def test_comparable_and_contradiction_valid_do_not_confirm_conflict(chain):
    aligned = chain[1].model_copy(update={"alignment_status": "aligned"})
    comp = [_validated_comp(item, "none") for item in chain[5]]
    exp = [_assessed_exp(item, "not_explanatory") for item in chain[6]]
    decision = _decision(chain, alignment=aligned, comp=comp, exp=exp)
    assert chain[2].signal_status == "validated"
    assert decision.adjudication_status == "unresolved_disagreement"
    assert decision.formal_conflict_confirmed is False


def test_staging_run_never_confirms_formal_conflict():
    decisions = _jsonl(RUN / "conflict_adjudications.jsonl")
    assert len(decisions) == 11
    assert all(item["authority_scope"] == "staging_only" for item in decisions)
    assert not any(item["formal_conflict_confirmed"] for item in decisions)


@pytest.mark.parametrize(
    "package,forbidden",
    [
        ("observation_context", ("claim_alignment", "context_difference", "conflict_adjudication")),
        ("claim_alignment", ("context_difference", "conflict_adjudication")),
        ("conflict_candidate", ("context_difference", "conflict_adjudication")),
        ("context_difference", ("conflict_adjudication",)),
    ],
)
def test_dependency_boundaries(package, forbidden):
    imports = _imports(ROOT / f"src/code_engine/context_attribution/{package}")
    assert not any(any(name in module for name in forbidden) for module in imports)


def test_attribution_branches_do_not_import_decision():
    for package in ("comparability", "divergence_explanation"):
        imports = _imports(
            ROOT
            / f"src/code_engine/context_attribution/conflict_adjudication/{package}"
        )
        assert not any("decision" in module for module in imports)


def test_legacy_is_explicitly_non_authoritative():
    audit = _jsonl(RUN / "legacy_authority_exclusion_audit.jsonl")[0]
    assert audit["authority"] == "read_only_non_authoritative"
    assert audit["new_mixed_schema_output"] is False
    assert not any(
        audit[key]
        for key in (
            "provider_effect_consumed_by_comparability",
            "provider_effect_consumed_by_explanation",
            "provider_effect_consumed_by_adjudication",
        )
    )


def test_new_pipeline_outputs_no_context_pair_attribution():
    manifest = _json(RUN / "conflict_adjudication_pipeline_manifest.json")
    assert not any("context_pair_attribution" in path for path in manifest["artifacts"])


def test_17b_41f_remain_policy_coverage_failures():
    failures = [
        item
        for item in _jsonl(RUN / "observation_context_validation_audit.jsonl")
        if not item["valid"]
    ]
    assert len(failures) == 2
    assert all(
        item["failure_class"] == "observation_context_policy_coverage_failure"
        for item in failures
    )


def test_candidate_count_ids_order_and_formal_count_unchanged():
    summary = _json(RUN / "conflict_adjudication_pipeline_summary.json")
    assert summary["candidate_pair_count_before"] == 11
    assert summary["candidate_pair_count_after"] == 11
    assert summary["candidate_pair_ids_before"] == summary["candidate_pair_ids_after"]
    assert summary["candidate_pair_identity_changed"] is False
    assert summary["candidate_pair_order_changed"] is False
    assert summary["formal_conflict_count_before"] == 0
    assert summary["formal_conflict_count_after"] == 0


def test_safety_accounting_and_historical_hashes():
    summary = _json(RUN / "conflict_adjudication_pipeline_summary.json")
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
    manifest = _json(RUN / "conflict_adjudication_pipeline_manifest.json")
    assert manifest["source_hashes_before"] == manifest["source_hashes_after"]
    for path, expected in manifest["source_hashes_after"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected


def test_contract_identities_independently_recompute():
    contracts = _json(RUN / "contract_identities.json")
    assert len(contracts) == 4
    for record in contracts.values():
        actual = layer_identity(
            record["contract_name"],
            record["contract_version"],
            record["canonical_payload"],
        )
        assert actual == record["sha256"] == record["recomputed_sha256"]
        assert record["identity_match"] is True
        serialized = json.dumps(record["canonical_payload"])
        assert "ftl1v3_" not in serialized
        assert "weak-ebd5" not in serialized
        assert "/home/" not in serialized


def test_adr_statuses_are_scoped_correctly():
    orchestration = (
        ROOT / "docs/adr/ADR-conflict-adjudication-orchestration-v1.md"
    ).read_text(encoding="utf-8")
    divergence = (
        ROOT / "docs/adr/ADR-conflict-divergence-explanation-semantics-v1.md"
    ).read_text(encoding="utf-8")
    comparability = (
        ROOT / "docs/adr/ADR-conflict-comparability-effect-semantics-v1.md"
    ).read_text(encoding="utf-8")
    assert "Status: **Accepted**" in orchestration
    assert "Status: **Proposed**" in divergence
    assert "Status: **Proposed**" in comparability
