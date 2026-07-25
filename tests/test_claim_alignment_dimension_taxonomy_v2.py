from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.code_engine.context_attribution.claim_alignment.granularity import assess_granularity_bridge
from src.code_engine.context_attribution.claim_alignment.v2 import align_semantic_views
from src.code_engine.context_attribution.conflict_candidate.contradiction_v2 import build_contradiction_signal_v2
from src.code_engine.context_attribution.observation_semantics.identities import proposition_core_identity
from src.code_engine.context_attribution.observation_semantics.models import PropositionCoreView
from src.code_engine.context_attribution.observation_semantics.projection import project_observation_semantic_views

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"


def _view(observation_id: str, direction: str, level: str | None = None,
          compartments: list[str] | None = None, subject: str = "s"):
    return project_observation_semantic_views(
        observation_id=observation_id, normalized_claim_identity=f"claim-{observation_id}",
        subject=subject, relation_family="directional_relation", endpoint="e",
        direction=direction, measurement_level=level, compartments=compartments or [],
        observation_context=None)


def _bridge(a, b, dimension="measurement_semantic_level"):
    qa = next(x for x in a.granularity_qualification_view.qualifier_dimensions if x.dimension_id == dimension)
    qb = next(x for x in b.granularity_qualification_view.qualifier_dimensions if x.dimension_id == dimension)
    return assess_granularity_bridge(dimension_id=dimension, qualifier_a=qa.model_dump(),
                                     qualifier_b=qb.model_dump())


def _alignment(a, b, bridges):
    return align_semantic_views(
        observation_a_id=a.observation_id, observation_b_id=b.observation_id,
        core_a=a.proposition_core_view, core_b=b.proposition_core_view, bridges=bridges,
        legacy_identity="legacy", role_taxonomy_identity="roles")


@pytest.mark.parametrize("field", ["direction","sign","polarity","dose","duration","species",
                                   "measurement_method","comparability","explanation","final","observation_id"])
def test_proposition_core_rejects_forbidden_fields(field):
    payload = _view("a","positive").proposition_core_view.model_dump()
    payload[field] = "forbidden"
    with pytest.raises(ValidationError):
        PropositionCoreView.model_validate(payload)


@pytest.mark.parametrize("field", ["direction","sign","polarity"])
def test_result_changes_do_not_change_core_identity(field):
    left, right = _view("a","positive"), _view("b","negative")
    assert left.proposition_core_view.proposition_core_identity != right.proposition_core_view.proposition_core_identity
    left_payload = left.proposition_core_view.model_dump()
    left_payload["normalization_identities"] = []
    right_payload = right.proposition_core_view.model_dump()
    right_payload["normalization_identities"] = []
    assert proposition_core_identity(left_payload) == proposition_core_identity(right_payload)


def test_context_change_does_not_change_core_identity():
    a = _view("a","positive")
    b = project_observation_semantic_views(
        observation_id="a", normalized_claim_identity="claim-a", subject="s",
        relation_family="directional_relation", endpoint="e", direction="positive",
        measurement_level=None, compartments=[], observation_context={"validation_status":"validated",
        "observation_context_identity":"ctx","facts":[]})
    assert a.proposition_core_view.proposition_core_identity == b.proposition_core_view.proposition_core_identity


@pytest.mark.parametrize("changed", ["subject","relation","endpoint"])
def test_core_semantic_change_changes_identity(changed):
    kwargs = dict(observation_id="a", normalized_claim_identity="claim-a", subject="s",
                  relation_family="r", endpoint="e", direction="positive",
                  measurement_level=None, compartments=[], observation_context=None)
    first = project_observation_semantic_views(**kwargs)
    kwargs[changed if changed != "relation" else "relation_family"] = "changed"
    second = project_observation_semantic_views(**kwargs)
    assert first.proposition_core_view.proposition_core_identity != second.proposition_core_view.proposition_core_identity


def test_exact_bridge_is_exact_match():
    a, b = _view("a","positive","protein"), _view("b","negative","protein")
    assert _bridge(a,b).bridge_status == "exact_match"


def test_nonexact_bridge_without_policy_is_unresolved():
    a, b = _view("a","positive","protein"), _view("b","negative","rna")
    bridge = _bridge(a,b)
    assert bridge.bridge_status == "unresolved"
    assert not bridge.deterministic_authority
    assert bridge.provenance["string_similarity_used"] is False


def test_both_missing_bridge_is_not_applicable():
    assert _bridge(_view("a","positive"),_view("b","negative")).bridge_status == "not_applicable"


def test_unresolved_bridge_yields_partial_alignment():
    a, b = _view("a","positive","protein"), _view("b","negative","rna")
    assert _alignment(a,b,[_bridge(a,b)]).alignment_status == "partially_aligned"


def test_core_mismatch_yields_unaligned():
    a, b = _view("a","positive",subject="x"), _view("b","negative",subject="y")
    assert _alignment(a,b,[_bridge(a,b)]).alignment_status == "unaligned"


def test_exact_core_and_bridge_yields_aligned():
    a, b = _view("a","positive","protein"), _view("b","negative","protein")
    assert _alignment(a,b,[_bridge(a,b)]).alignment_status == "aligned"


def test_direction_difference_does_not_block_alignment():
    a, b = _view("a","positive"), _view("b","negative")
    assert _alignment(a,b,[_bridge(a,b)]).alignment_status == "aligned"


def test_historical_signal_is_structural_but_not_formal():
    a, b = _view("a","positive"), _view("b","negative")
    alignment = _alignment(a,b,[_bridge(a,b)])
    signal = build_contradiction_signal_v2(
        alignment=alignment, result_a=a.contradiction_result_view,
        result_b=b.contradiction_result_view, historical_candidate=True)
    assert signal.signal_structure_valid
    assert signal.signal_status == "validated"
    assert signal.candidate_authority_scope == "legacy_preserved"
    assert not signal.formal_adjudication_eligible


def test_future_signal_requires_aligned():
    a, b = _view("a","positive","protein"), _view("b","negative","rna")
    signal = build_contradiction_signal_v2(
        alignment=_alignment(a,b,[_bridge(a,b)]), result_a=a.contradiction_result_view,
        result_b=b.contradiction_result_view, historical_candidate=False)
    assert signal.candidate_authority_scope == "diagnostic_only"
    assert not signal.formal_adjudication_eligible


@pytest.mark.parametrize("name", [
    "observation_semantic_views.jsonl","dimension_role_audit.jsonl","dimension_role_audit.csv",
    "proposition_core_views.jsonl","contradiction_result_views.jsonl","context_envelope_refs.jsonl",
    "granularity_qualification_views.jsonl","granularity_bridge_assessments.jsonl",
    "claim_alignment_records_v2.jsonl","contradiction_signals_v2.jsonl",
    "candidate_alignment_signal_bindings_v2.jsonl","context_difference_v2_binding_sidecars.jsonl",
    "downstream_gate_status_sidecars.jsonl","ebd5_alignment_dimension_role_audit.json",
    "ebd5_granularity_bridge_audit.json","ebd5_alignment_v1_v2_comparison.json",
    "identity_chain_v2_audit.jsonl","legacy_candidate_preservation_audit.jsonl",
    "claim_alignment_dimension_taxonomy_v2_summary.json","alignment_dimension_taxonomy_v2_manifest.json"])
def test_required_offline_artifact_exists(name):
    assert (RUN / name).is_file()


def test_candidate_ids_and_order_preserved():
    summary = json.loads((RUN/"claim_alignment_dimension_taxonomy_v2_summary.json").read_text())
    assert summary["candidate_pair_count_before"] == summary["candidate_pair_count_after"] == 11
    assert summary["candidate_pair_ids_before"] == summary["candidate_pair_ids_after"]
    assert not summary["candidate_pair_order_changed"]


def test_ebd5_remains_uncurated():
    audit = json.loads((RUN/"ebd5_alignment_v1_v2_comparison.json").read_text())
    assert audit["alignment_v2_status"] == "partially_aligned"
    assert audit["formal_adjudication_eligible"] is False
    assert audit["context_difference_factor_count"] == 8
    assert audit["comparability_status"] == audit["explanation_status"] == "pending_policy"
    assert audit["formal_conflict_status"] == "not_confirmed"


def test_contract_identities_recompute():
    contracts = json.loads((RUN/"contract_identities_v2.json").read_text())
    assert len(contracts) == 8
    assert all(x["identity_match"] and x["sha256"] == x["recomputed_sha256"] for x in contracts.values())


def test_no_external_activity_or_mutation():
    manifest = json.loads((RUN/"alignment_dimension_taxonomy_v2_manifest.json").read_text())
    for key in ("provider_calls","api_calls","network_calls","downloads"):
        assert manifest[key] == 0
    for key in ("credential_values_read","provider_client_created","historical_runs_modified",
                "candidate_pairs_modified","handoff_created","atlas_activated",
                "active_pointer_changed","variational_em_called"):
        assert manifest[key] is False
