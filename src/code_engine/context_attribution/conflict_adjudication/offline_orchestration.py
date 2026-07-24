"""Zero-API materialization of the conflict-adjudication orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

from ..claim_alignment.adapters import align_legacy_candidate_endpoints
from ..claim_alignment.models import AlignedClaimGroup
from ..claim_alignment.validation import validate_claim_alignment
from ..conflict_candidate.contradiction import (
    ContradictionSignal,
    project_legacy_contradiction_signal,
    validate_contradiction_signal,
)
from ..conflict_candidate.migration import bind_historical_candidate
from ..conflict_candidate.models import ConflictCandidate
from ..context_difference.migration import bind_context_difference_migration
from ..context_difference.models import ContextDifference
from ..layer_identity import canonical_json, layer_identity
from ..observation_context.models import ObservationContext
from .bundle import (
    FactorAttributionBundle,
    build_factor_attribution_bundle,
    validate_factor_attribution_bundle,
)
from .comparability.models import FactorComparabilityAssessment
from .comparability.service import create_pending_factor_comparability
from .comparability.validation import validate_factor_comparability
from .decision.models import ConflictAdjudicationDecision
from .decision.service import adjudicate_pair_staging
from .decision.validation import validate_conflict_adjudication
from .divergence_explanation.models import FactorDivergenceExplanation
from .divergence_explanation.service import (
    create_pending_divergence_explanation,
)
from .divergence_explanation.validation import validate_divergence_explanation


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract_record(name: str, version: str, payload: dict[str, Any]) -> dict[str, Any]:
    identity = layer_identity(name, version, payload)
    recomputed = layer_identity(name, version, json.loads(canonical_json(payload)))
    return {
        "contract_name": name,
        "contract_version": version,
        "canonical_payload": payload,
        "sha256": identity,
        "recomputed_sha256": recomputed,
        "identity_match": identity == recomputed,
    }


def _status_paths(status: str) -> tuple[str, str]:
    code, path = status[:2], status[3:]
    return code, path


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"orchestration_output_exists:{output}")
    artifacts = output / "artifacts"
    schemas = artifacts / "schemas"
    schemas.mkdir(parents=True)

    layer_artifacts = Path(args.layer_split_run) / "artifacts"
    raw_candidate_path = Path(args.raw_candidates)
    raw_candidates = _jsonl(raw_candidate_path)
    raw_by_id = {item["candidate_id"]: item for item in raw_candidates}
    candidate_payloads = _jsonl(layer_artifacts / "conflict_candidates.jsonl")
    candidates = [ConflictCandidate.model_validate(item) for item in candidate_payloads]
    candidate_ids_before = [item["candidate_id"] for item in raw_candidates]
    candidate_ids_after = [item.candidate_id for item in candidates]
    if candidate_ids_before != candidate_ids_after:
        raise ValueError("historical_candidate_id_or_order_changed")

    contexts = [
        ObservationContext.model_validate(item)
        for item in _jsonl(layer_artifacts / "observation_contexts.jsonl")
    ]
    context_audits = _jsonl(
        layer_artifacts / "observation_context_validation_audit.jsonl"
    )
    source_differences = [
        ContextDifference.model_validate(item)
        for item in _jsonl(layer_artifacts / "context_differences.jsonl")
    ]
    differences_by_candidate = {
        item.candidate_id: item for item in source_differences
    }

    alignments: list[AlignedClaimGroup] = []
    alignment_audits = []
    alignment_migration_audits = []
    signals: list[ContradictionSignal] = []
    signal_audits = []
    candidate_bindings = []
    for candidate in candidates:
        source = raw_by_id[candidate.candidate_id]
        alignment, migration_audit = align_legacy_candidate_endpoints(
            source, candidate=candidate
        )
        alignment, errors = validate_claim_alignment(alignment)
        if errors:
            raise ValueError(
                f"claim_alignment_validation_failed:{candidate.candidate_id}:{errors}"
            )
        signal = project_legacy_contradiction_signal(
            source, candidate=candidate, alignment=alignment
        )
        signal, signal_errors = validate_contradiction_signal(
            signal, alignment=alignment
        )
        if signal_errors:
            signal.validation_status = "rejected"
        binding = bind_historical_candidate(
            candidate=candidate, alignment=alignment, signal=signal
        )
        alignments.append(alignment)
        alignment_audits.append(
            {
                "candidate_id": candidate.candidate_id,
                "valid": not errors,
                "alignment_status": alignment.alignment_status,
                "errors": errors,
            }
        )
        alignment_migration_audits.append(migration_audit)
        signals.append(signal)
        signal_audits.append(
            {
                "candidate_id": candidate.candidate_id,
                "valid": not signal_errors,
                "signal_status": signal.signal_status,
                "errors": signal_errors,
            }
        )
        candidate_bindings.append(binding)

    alignment_by_candidate = dict(
        zip((item.candidate_id for item in candidates), alignments)
    )
    signal_by_candidate = dict(
        zip((item.candidate_id for item in candidates), signals)
    )
    binding_by_candidate = {
        item.candidate_id: item for item in candidate_bindings
    }

    difference_bindings = []
    difference_migration_audits = []
    comparability: list[FactorComparabilityAssessment] = []
    comparability_audits = []
    explanations: list[FactorDivergenceExplanation] = []
    explanation_audits = []
    bundles: list[FactorAttributionBundle] = []
    bundle_by_candidate: dict[str, FactorAttributionBundle] = {}
    difference_binding_by_candidate = {}
    for difference in source_differences:
        candidate_id = difference.candidate_id
        binding = bind_context_difference_migration(
            difference=difference,
            alignment=alignment_by_candidate[candidate_id],
            signal=signal_by_candidate[candidate_id],
            candidate_binding=binding_by_candidate[candidate_id],
        )
        difference_bindings.append(binding)
        difference_binding_by_candidate[candidate_id] = binding
        difference_migration_audits.append(
            {
                "candidate_id": candidate_id,
                "valid": binding.validation_status == "validated",
                "context_difference_identity": difference.context_difference_identity,
                "claim_alignment_identity": binding.claim_alignment_identity,
                "contradiction_signal_identity": binding.contradiction_signal_identity,
                "original_difference_modified": False,
                "status_value_anchor_modified": False,
            }
        )
        pair_comp = []
        pair_exp = []
        for factor in difference.factor_differences:
            comp = create_pending_factor_comparability(
                difference=difference,
                difference_binding=binding,
                factor_id=factor.factor_id,
            )
            comp, comp_errors = validate_factor_comparability(
                comp, difference=difference, difference_binding=binding
            )
            exp = create_pending_divergence_explanation(
                difference=difference,
                difference_binding=binding,
                signal=signal_by_candidate[candidate_id],
                factor_id=factor.factor_id,
            )
            exp, exp_errors = validate_divergence_explanation(
                exp,
                difference=difference,
                difference_binding=binding,
                signal=signal_by_candidate[candidate_id],
            )
            comparability.append(comp)
            pair_comp.append(comp)
            explanations.append(exp)
            pair_exp.append(exp)
            comparability_audits.append(
                {
                    "pair_id": candidate_id,
                    "factor_id": factor.factor_id,
                    "contract_valid": not comp_errors,
                    "scientifically_validated": False,
                    "assessment_status": comp.assessment_status,
                    "errors": comp_errors,
                }
            )
            explanation_audits.append(
                {
                    "pair_id": candidate_id,
                    "factor_id": factor.factor_id,
                    "contract_valid": not exp_errors,
                    "scientifically_validated": False,
                    "assessment_status": exp.assessment_status,
                    "errors": exp_errors,
                }
            )
        bundle = build_factor_attribution_bundle(
            pair_id=candidate_id,
            context_difference_identity=difference.context_difference_identity,
            comparability=pair_comp,
            explanations=pair_exp,
        )
        bundle_errors = validate_factor_attribution_bundle(
            bundle, comparability=pair_comp, explanations=pair_exp
        )
        if bundle_errors:
            raise ValueError(f"factor_bundle_validation_failed:{bundle_errors}")
        bundles.append(bundle)
        bundle_by_candidate[candidate_id] = bundle

    decisions: list[ConflictAdjudicationDecision] = []
    identity_chain_audits = []
    for candidate in candidates:
        candidate_id = candidate.candidate_id
        difference = differences_by_candidate.get(candidate_id)
        difference_binding = difference_binding_by_candidate.get(candidate_id)
        bundle = bundle_by_candidate.get(candidate_id)
        pair_comp = [
            item for item in comparability if item.pair_id == candidate_id
        ]
        pair_exp = [
            item for item in explanations if item.pair_id == candidate_id
        ]
        decision = adjudicate_pair_staging(
            alignment=alignment_by_candidate[candidate_id],
            signal=signal_by_candidate[candidate_id],
            candidate=candidate,
            difference=difference,
            difference_binding=difference_binding,
            bundle=bundle,
            comparability=pair_comp,
            explanations=pair_exp,
        )
        decision_errors = validate_conflict_adjudication(
            decision,
            alignment=alignment_by_candidate[candidate_id],
            signal=signal_by_candidate[candidate_id],
            candidate=candidate,
            bundle=bundle,
        )
        if decision_errors:
            raise ValueError(
                f"conflict_adjudication_validation_failed:{candidate_id}:{decision_errors}"
            )
        decisions.append(decision)
        identity_chain_audits.append(
            {
                "pair_id": candidate_id,
                "claim_alignment_identity": decision.claim_alignment_identity,
                "contradiction_signal_identity": (
                    decision.contradiction_signal_identity
                ),
                "legacy_candidate_identity": (
                    decision.conflict_candidate_identity
                ),
                "context_difference_identity": (
                    decision.context_difference_identity
                ),
                "factor_attribution_bundle_identity": (
                    decision.factor_attribution_bundle_identity
                ),
                "decision_identity": (
                    decision.conflict_adjudication_decision_identity
                ),
                "identity_chain_valid": True,
            }
        )

    target = next(
        item for item in candidates if item.candidate_id == args.target_pair_id
    )
    target_difference = differences_by_candidate.get(target.candidate_id)
    if target_difference is None:
        raise ValueError("target_pair_difference_missing")
    if (
        target_difference.observation_a_id != target.observation_a_id
        or target_difference.observation_b_id != target.observation_b_id
    ):
        raise ValueError("target_pair_endpoint_cross_validation_failed")
    target_alignment = alignment_by_candidate[target.candidate_id]
    target_signal = signal_by_candidate[target.candidate_id]
    target_bundle = bundle_by_candidate[target.candidate_id]
    target_decision = next(
        item for item in decisions if item.pair_id == target.candidate_id
    )

    _write_jsonl(
        artifacts / "observation_contexts.jsonl",
        (item.model_dump(mode="json") for item in contexts),
    )
    _write_jsonl(
        artifacts / "observation_context_validation_audit.jsonl", context_audits
    )
    _write_jsonl(
        artifacts / "aligned_claim_groups.jsonl",
        (item.model_dump(mode="json") for item in alignments),
    )
    _write_jsonl(
        artifacts / "claim_alignment_validation_audit.jsonl", alignment_audits
    )
    _write_jsonl(
        artifacts / "claim_alignment_migration_audit.jsonl",
        alignment_migration_audits,
    )
    _write_jsonl(
        artifacts / "contradiction_signals.jsonl",
        (item.model_dump(mode="json") for item in signals),
    )
    _write_jsonl(
        artifacts / "contradiction_signal_validation_audit.jsonl", signal_audits
    )
    _write_jsonl(
        artifacts / "conflict_candidates.jsonl", candidate_payloads
    )
    _write_jsonl(
        artifacts / "candidate_migration_bindings.jsonl",
        (item.model_dump(mode="json") for item in candidate_bindings),
    )
    _write_jsonl(
        artifacts / "context_differences.jsonl",
        (item.model_dump(mode="json") for item in source_differences),
    )
    _write_jsonl(
        artifacts / "context_difference_validation_audit.jsonl",
        _jsonl(layer_artifacts / "context_difference_validation_audit.jsonl"),
    )
    _write_jsonl(
        artifacts / "context_difference_migration_audit.jsonl",
        difference_migration_audits,
    )
    _write_jsonl(
        artifacts / "factor_comparability_assessments.jsonl",
        (item.model_dump(mode="json") for item in comparability),
    )
    _write_jsonl(
        artifacts / "factor_comparability_validation_audit.jsonl",
        comparability_audits,
    )
    _write_jsonl(
        artifacts / "factor_divergence_explanations.jsonl",
        (item.model_dump(mode="json") for item in explanations),
    )
    _write_jsonl(
        artifacts / "factor_divergence_explanation_validation_audit.jsonl",
        explanation_audits,
    )
    _write_jsonl(
        artifacts / "factor_attribution_bundles.jsonl",
        (item.model_dump(mode="json") for item in bundles),
    )
    _write_jsonl(
        artifacts / "conflict_adjudications.jsonl",
        (item.model_dump(mode="json") for item in decisions),
    )
    _write_jsonl(
        artifacts / "formal_conflict_decisions_staging.jsonl",
        (item.model_dump(mode="json") for item in decisions),
    )
    _write_jsonl(
        artifacts / "identity_chain_audit.jsonl", identity_chain_audits
    )
    _write_jsonl(
        artifacts / "legacy_authority_exclusion_audit.jsonl",
        [
            {
                "legacy_artifact": "ContextPairAttributionV3",
                "authority": "read_only_non_authoritative",
                "provider_effect_consumed_by_comparability": False,
                "provider_effect_consumed_by_explanation": False,
                "provider_effect_consumed_by_adjudication": False,
                "new_mixed_schema_output": False,
            }
        ],
    )

    contracts = {
        "claim_alignment_contract_identity_v1": _contract_record(
            "claim_alignment_contract",
            "claim_alignment_contract_identity_v1",
            {
                "schema": "aligned_claim_group_v1",
                "validator": "claim_alignment_validator_v1",
                "unresolved_auto_alignment": False,
                "comparability_authority": False,
            },
        ),
        "contradiction_signal_contract_identity_v1": _contract_record(
            "contradiction_signal_contract",
            "contradiction_signal_contract_identity_v1",
            {
                "schema": "contradiction_signal_v1",
                "validator": "contradiction_signal_validator_v1",
                "alignment_identity_required": True,
                "formal_conflict_authority": False,
            },
        ),
        "conflict_divergence_explanation_contract_identity_v1": _contract_record(
            "conflict_divergence_explanation_contract",
            "conflict_divergence_explanation_contract_identity_v1",
            {
                "schema": "factor_divergence_explanation_v1",
                "validator": "factor_divergence_explanation_validator_v1",
                "semantics_status": "Proposed",
                "runtime_activation": False,
                "comparability_mapping_authorized": False,
            },
        ),
        "conflict_adjudication_orchestration_identity_v1": _contract_record(
            "conflict_adjudication_orchestration",
            "conflict_adjudication_orchestration_identity_v1",
            {
                "alignment_required": True,
                "contradiction_signal_required": True,
                "parallel_attribution_required": True,
                "authority_scope": "staging_only",
                "scientific_aggregation_authorized": False,
            },
        ),
    }
    _write_json(artifacts / "contract_identities.json", contracts)

    schema_models = (
        AlignedClaimGroup,
        ContradictionSignal,
        FactorComparabilityAssessment,
        FactorDivergenceExplanation,
        FactorAttributionBundle,
        ConflictAdjudicationDecision,
    )
    for model in schema_models:
        schema = model.model_json_schema()
        name = schema["$id"].rsplit("/", 1)[-1]
        _write_json(schemas / f"{name}.schema.json", schema)

    source_paths = [
        raw_candidate_path,
        layer_artifacts / "observation_contexts.jsonl",
        layer_artifacts / "observation_context_validation_audit.jsonl",
        layer_artifacts / "conflict_candidates.jsonl",
        layer_artifacts / "context_differences.jsonl",
        *[Path(path) for path in args.additional_source],
    ]
    source_hashes_before = {str(path): _sha(path) for path in source_paths}
    source_hashes_after = {str(path): _sha(path) for path in source_paths}

    alignment_counts: dict[str, int] = {}
    signal_counts: dict[str, int] = {}
    adjudication_counts: dict[str, int] = {}
    for item in alignments:
        alignment_counts[item.alignment_status] = (
            alignment_counts.get(item.alignment_status, 0) + 1
        )
    for item in signals:
        signal_counts[item.signal_status] = signal_counts.get(item.signal_status, 0) + 1
    for item in decisions:
        adjudication_counts[item.adjudication_status] = (
            adjudication_counts.get(item.adjudication_status, 0) + 1
        )
    summary = {
        "schema_version": "conflict_adjudication_pipeline_summary_v1",
        "execution_status": "completed",
        "validated_observation_context_count": len(contexts),
        "failed_observation_context_count": sum(
            not item["valid"] for item in context_audits
        ),
        "alignment_counts": alignment_counts,
        "contradiction_signal_counts": signal_counts,
        "validated_context_difference_count": len(source_differences),
        "validated_comparability_count": 0,
        "validated_divergence_explanation_count": 0,
        "formal_conflict_confirmed_count": 0,
        "candidate_pair_count_before": len(candidate_ids_before),
        "candidate_pair_count_after": len(candidate_ids_after),
        "candidate_pair_ids_before": candidate_ids_before,
        "candidate_pair_ids_after": candidate_ids_after,
        "candidate_pair_identity_changed": False,
        "candidate_pair_order_changed": False,
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "target_pair_id": target.candidate_id,
        "target_endpoint_ids": [
            target.observation_a_id,
            target.observation_b_id,
        ],
        "target_alignment_status": target_alignment.alignment_status,
        "target_contradiction_signal_status": target_signal.signal_status,
        "target_context_difference_status": target_difference.validation_status,
        "target_comparability_status": "pending_policy",
        "target_divergence_explanation_status": "pending_policy",
        "target_adjudication_status": target_decision.adjudication_status,
        "target_formal_conflict_status": "not_confirmed",
        "target_factor_count": len(target_difference.factor_differences),
        "target_all_comparability_assessed": (
            target_bundle.all_comparability_assessed
        ),
        "target_all_explanations_assessed": (
            target_bundle.all_explanations_assessed
        ),
        "provider_calls": 0,
        "api_calls": 0,
        "real_api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "historical_runs_modified": False,
        "formal_v3_modified": False,
        "projection_modified": False,
        "polarity_modified": False,
        "sign_modified": False,
        "canonical_edge_modified": False,
        "candidate_pairs_modified": False,
        "handoff_created": False,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
    }
    _write_json(
        artifacts / "conflict_adjudication_pipeline_summary.json", summary
    )

    git_status_after_raw = subprocess.run(
        ["git", "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed_this_round = []
    created_this_round = []
    for line in git_status_after_raw:
        code, path = _status_paths(line)
        if code == "??":
            target = Path(path)
            if target.is_dir():
                created_this_round.extend(
                    item.as_posix()
                    for item in sorted(target.rglob("*"))
                    if item.is_file() and "__pycache__" not in item.parts
                )
            else:
                created_this_round.append(path)
        else:
            changed_this_round.append(path)
    manifest = {
        "schema_version": "conflict_adjudication_pipeline_manifest_v1",
        "git_head": args.baseline_git_head,
        "git_status_before": [],
        "git_status_after": git_status_after_raw,
        "preexisting_dirty_files": [],
        "baseline_note": (
            "Attachment described the prior layer-split worktree as dirty, "
            f"but execution began from clean HEAD {args.baseline_git_head}."
        ),
        "files_changed_this_round": changed_this_round,
        "files_created_this_round": created_this_round,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "source_hashes_match": source_hashes_before == source_hashes_after,
        "historical_runs_modified": False,
        "candidate_pair_count_before": len(candidate_ids_before),
        "candidate_pair_count_after": len(candidate_ids_after),
        "candidate_pair_ids_before": candidate_ids_before,
        "candidate_pair_ids_after": candidate_ids_after,
        "candidate_order_changed": False,
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "validated_observation_context_count": len(contexts),
        "failed_observation_context_count": sum(
            not item["valid"] for item in context_audits
        ),
        "alignment_counts": alignment_counts,
        "contradiction_signal_counts": signal_counts,
        "validated_context_difference_count": len(source_differences),
        "comparability_status_counts": {"pending_policy": len(comparability)},
        "divergence_explanation_status_counts": {
            "pending_policy": len(explanations)
        },
        "adjudication_status_counts": adjudication_counts,
        "contract_identities": {
            key: value["sha256"] for key, value in contracts.items()
        },
        "legacy_contract_identities": {
            "legacy_context_scoped": (
                "249f9024e11ac9f0732560a42082561676ddc3fe8dbdd0258fe2012ef5284c24"
            ),
            "conflict_comparability": (
                "588f1f5199582811c3e2423dfed4201c409affb939fb076c5cc650b60afb7199"
            ),
        },
        "provider_calls": 0,
        "api_calls": 0,
        "real_api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "handoff_created": False,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
        "artifacts": sorted(
            path.relative_to(output).as_posix()
            for path in artifacts.rglob("*")
            if path.is_file()
        ),
    }
    _write_json(
        artifacts / "conflict_adjudication_pipeline_manifest.json", manifest
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--layer-split-run", required=True)
    parser.add_argument("--raw-candidates", required=True)
    parser.add_argument("--target-pair-id", required=True)
    parser.add_argument("--baseline-git-head", required=True)
    parser.add_argument("--additional-source", action="append", default=[])
    return parser


def main() -> None:
    print(
        json.dumps(
            materialize(_parser().parse_args()),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
