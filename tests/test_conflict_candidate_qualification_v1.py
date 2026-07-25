from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.code_engine.context_attribution.conflict_candidate.qualification.models import (
    ConflictCandidateQualificationV1,
    QualifiedCandidateAuthoritySidecarV1,
)
from src.code_engine.context_attribution.conflict_candidate.qualification.service import (
    build_authority_sidecar,
    build_scientific_pair,
    qualify_candidate,
)
from src.code_engine.context_attribution.context_difference.qualification_gate import (
    require_qualified_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
OLD = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts"
V2 = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"


def _json(name):
    return json.loads((RUN / name).read_text())


def _jsonl_at(base, name):
    return [json.loads(x) for x in (base / name).read_text().splitlines() if x]


def _jsonl(name):
    return _jsonl_at(RUN, name)


def _inputs(index=9):
    c = _jsonl_at(OLD, "conflict_candidates.jsonl")[index]
    a = _jsonl_at(V2, "claim_alignment_records_v2.jsonl")[index]
    s = _jsonl_at(V2, "contradiction_signals_v2.jsonl")[index]
    pair = build_scientific_pair(
        claim_a=c["claim_a_identity"], claim_b=c["claim_b_identity"],
        core_a=a["proposition_core_identity_a"], core_b=a["proposition_core_identity_b"],
        signal_type=s["signal_type"], contract_identity="pair-contract",
    )
    return c, a, s, pair


def _qualify(c, a, s, pair):
    return qualify_candidate(
        candidate=c, alignment=a, signal=s, pair=pair,
        contract_identity="qualification-contract",
        generation_policy_identity="generation-policy",
    )


def test_aligned_valid_signal_qualifies_without_l4_science():
    q = _qualify(*_inputs())
    assert q.qualification_status == "qualified" and q.qualified_for_l4
    assert not ({"comparability", "divergence_explanation", "formal_conflict"} & q.model_dump().keys())


@pytest.mark.parametrize("status", ["partially_aligned", "unaligned", "insufficient_information"])
def test_non_aligned_is_blocked_alignment(status):
    c, a, s, pair = _inputs()
    q = _qualify(c, {**a, "alignment_status": status}, s, pair)
    assert q.qualification_status == "blocked_alignment" and not q.qualified_for_l4


@pytest.mark.parametrize("field,value", [
    ("signal_structure_valid", False), ("signal_status", "rejected"),
    ("signal_provenance_complete", False), ("signal_schema_valid", False),
    ("signal_validator_valid", False),
])
def test_aligned_unusable_signal_is_blocked(field, value):
    c, a, s, pair = _inputs()
    q = _qualify(c, a, {**s, field: value}, pair)
    assert q.qualification_status == "blocked_signal" and not q.qualified_for_l4


def test_lineage_mismatch_is_rejected():
    c, a, s, pair = _inputs()
    q = _qualify(c, {**a, "observation_a_id": "different"}, s, pair)
    assert q.qualification_status == "rejected"
    assert "lineage_endpoint_mismatch" in q.qualification_error_codes


def test_qualification_schema_forbids_l4_extra():
    payload = _jsonl("conflict_candidate_qualifications.jsonl")[0]
    payload["comparability"] = "forbidden"
    with pytest.raises(ValidationError):
        ConflictCandidateQualificationV1.model_validate(payload)


def test_pair_identity_excludes_path_and_l4_but_preserves_order():
    c, a, s, pair = _inputs()
    same = build_scientific_pair(
        claim_a=c["claim_a_identity"], claim_b=c["claim_b_identity"],
        core_a=a["proposition_core_identity_a"], core_b=a["proposition_core_identity_b"],
        signal_type=s["signal_type"], contract_identity="pair-contract",
    )
    reverse = build_scientific_pair(
        claim_a=c["claim_b_identity"], claim_b=c["claim_a_identity"],
        core_a=a["proposition_core_identity_b"], core_b=a["proposition_core_identity_a"],
        signal_type=s["signal_type"], contract_identity="pair-contract",
    )
    assert pair.scientific_candidate_pair_identity == same.scientific_candidate_pair_identity
    assert pair.scientific_candidate_pair_identity != reverse.scientific_candidate_pair_identity
    assert "path" not in pair.model_dump() and "comparability" not in pair.model_dump()


def test_authority_sidecar_scope_and_preservation():
    for value in _jsonl("conflict_candidate_qualifications.jsonl"):
        q = ConflictCandidateQualificationV1.model_validate(value)
        sidecar = build_authority_sidecar(q)
        assert sidecar.authority_scope == ("future_standard" if q.qualified_for_l4 else "legacy_only")
        assert sidecar.source_pair_set_unchanged and sidecar.legacy_identity_preserved
        assert sidecar == build_authority_sidecar(q)


def test_authority_sidecar_rejects_false_preservation():
    payload = _jsonl("qualified_candidate_authority_sidecars.jsonl")[0]
    payload["legacy_identity_preserved"] = False
    with pytest.raises(ValidationError):
        QualifiedCandidateAuthoritySidecarV1.model_validate(payload)


def test_future_context_difference_requires_qualified_candidate():
    qualified = ConflictCandidateQualificationV1.model_validate(
        _jsonl("conflict_candidate_qualifications.jsonl")[-1]
    )
    blocked = ConflictCandidateQualificationV1.model_validate(
        _jsonl("conflict_candidate_qualifications.jsonl")[0]
    )
    require_qualified_candidate(qualified)
    with pytest.raises(PermissionError):
        require_qualified_candidate(blocked)


def test_signal_authority_is_separated_and_metrics_replace_old():
    rows, metrics = _jsonl("signal_authority_separation_audit.jsonl"), _json("signal_authority_metrics.json")
    assert len(rows) == 11 and all(x["signal_structure_valid"] for x in rows)
    assert all(not x["legacy_candidate_downgraded_signal_validity"] for x in rows)
    assert sum(x["alignment_eligible"] for x in rows) == 2
    assert sum(x["qualification_input_eligible"] for x in rows) == 2
    assert metrics["formal_signal_eligible_count"] == 0 and metrics["deprecated_ambiguous_metric"]
    assert metrics["qualified_candidate_signal_count"] == 2


def test_counts_candidate_safety_and_pair_bijection():
    summary, manifest = _json("candidate_qualification_summary.json"), _json("candidate_qualification_manifest.json")
    assert summary["qualified_candidate_count"] == 2
    assert summary["blocked_alignment_candidate_count"] == 9
    assert summary["blocked_signal_candidate_count"] == 0
    assert manifest["legacy_candidate_count_before"] == manifest["legacy_candidate_count_after"] == 11
    assert manifest["legacy_candidate_ids_before"] == manifest["legacy_candidate_ids_after"]
    assert manifest["legacy_candidate_identities_before"] == manifest["legacy_candidate_identities_after"]
    assert not manifest["candidate_order_changed"] and not manifest["scientific_pair_set_changed"]
    chains = _jsonl("l3_authority_identity_chain_audit.jsonl")
    assert len(chains) == len({x["scientific_candidate_pair_identity"] for x in chains}) == 11


def test_aligned_pair_audit_is_exact_and_real():
    rows = _jsonl("aligned_pair_candidate_qualification_audit.jsonl")
    assert [x["candidate_id"] for x in rows] == [
        "weak-3ca38dc452f5816bcb50", "weak-256ac5981f2df16f7f33",
    ]
    assert all(x["signal_status"] == "validated" and x["signal_structure_valid"] for x in rows)
    assert all(x["qualification_status"] == "qualified" for x in rows)
    assert [x["context_readiness_b"] for x in rows] == ["validated", "unavailable"]


def test_ebd5_remains_blocked_without_signal_downgrade():
    q, s, d = (_json("ebd5_candidate_qualification_audit.json"),
               _json("ebd5_signal_authority_audit.json"),
               _json("ebd5_downstream_status_audit.json"))
    assert q["endpoints"] == [
        "ftl1v3_71023211dcfb3d430a918e17", "ftl1v3_8a6dafe08d3c36201f191e09",
    ]
    assert q["qualification_status"] == "blocked_alignment" and not q["qualified_for_l4"]
    assert s["signal_structure_valid"] and not s["signal_validity_downgraded"]
    assert d["difference_artifact_status"] == "validated" and not d["l4_authority_eligible"]
    assert d["comparability_status"] == d["explanation_status"] == "pending_policy"
    assert d["adjudication_status"] == "blocked_alignment_unvalidated"
    assert d["formal_conflict_status"] == "not_confirmed"


def test_historical_difference_validity_is_not_new_authority():
    rows = _jsonl("context_difference_candidate_qualification_bindings.jsonl")
    assert len(rows) == 1 and rows[0]["artifact_valid"]
    assert not rows[0]["authoritative_for_new_l4"] and rows[0]["legacy_diagnostic_only"]


def test_contract_identities_recompute():
    contracts = _json("contract_identities.json")
    assert len(contracts) == 5
    assert all(x["identity_match"] and x["identity_sha256"] == x["recomputed_sha256"] for x in contracts.values())


def test_dependency_boundaries():
    contradiction = ast.parse((ROOT / "src/code_engine/context_attribution/conflict_candidate/contradiction_v2.py").read_text())
    imports = [ast.unparse(x) for x in ast.walk(contradiction) if isinstance(x, (ast.Import, ast.ImportFrom))]
    assert all("qualification" not in x for x in imports)
    forbidden = ("context_difference", "comparability", "divergence_explanation", "conflict_judgment")
    for path in (ROOT / "src/code_engine/context_attribution/conflict_candidate/qualification").glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = [ast.unparse(x) for x in ast.walk(tree) if isinstance(x, (ast.Import, ast.ImportFrom))]
        assert all(not any(word in item for word in forbidden) for item in imports)


def test_no_external_effects_or_historical_mutation():
    manifest = _json("candidate_qualification_manifest.json")
    for key in ("provider_calls", "api_calls", "network_calls", "downloads"):
        assert manifest[key] == 0
    for key in ("credential_values_read", "provider_client_created", "historical_runs_modified",
                "handoff_created", "atlas_activated", "active_pointer_changed", "variational_em_called"):
        assert manifest[key] is False
    assert manifest["source_hashes_before"] == manifest["source_hashes_after"]


@pytest.mark.parametrize("name", [
    "conflict_candidate_qualifications.jsonl", "conflict_candidate_qualification_validation_audit.jsonl",
    "scientific_candidate_pair_identities.jsonl", "qualified_candidate_authority_sidecars.jsonl",
    "signal_authority_separation_audit.jsonl", "signal_authority_metrics.json",
    "aligned_pair_candidate_qualification_audit.jsonl", "aligned_pair_candidate_qualification_audit.csv",
    "legacy_candidate_qualification_audit.jsonl", "candidate_lineage_audit.jsonl",
    "context_difference_candidate_qualification_bindings.jsonl", "downstream_candidate_authority_gate_audit.jsonl",
    "ebd5_candidate_qualification_audit.json", "ebd5_signal_authority_audit.json",
    "ebd5_downstream_status_audit.json", "l3_authority_identity_chain_audit.jsonl",
    "candidate_qualification_summary.json", "candidate_qualification_manifest.json",
])
def test_required_artifact_exists(name):
    assert (RUN / name).is_file()
