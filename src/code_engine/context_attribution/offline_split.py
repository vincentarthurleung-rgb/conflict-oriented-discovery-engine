"""Zero-provider architecture-split materializer.

This module only reads explicitly supplied local artifacts.  It imports no
Provider client, does not inspect environment variables, and has no network or
download capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .conflict_candidate.adapters import adapt_legacy_weak_candidate
from .conflict_candidate.models import ConflictCandidate
from .conflict_candidate.validation import validate_conflict_candidate
from .conflict_comparability.service import create_pending_comparability
from .conflict_comparability.validation import validate_conflict_comparability
from .conflict_judgment.gate import stage_formal_conflict_decision
from .context_difference.adapters import adapt_legacy_pair_to_context_difference
from .context_difference.models import ContextDifference
from .context_difference.validation import validate_context_difference
from .layer_identity import layer_identity
from .observation_context.adapters import adapt_legacy_context_extraction
from .observation_context.models import ObservationContext
from .observation_context.validation import validate_observation_context

OLD_CONTRACT_IDENTITY = (
    "249f9024e11ac9f0732560a42082561676ddc3fe8dbdd0258fe2012ef5284c24"
)


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _claim_metadata(
    raw_candidate: dict[str, Any], candidate: ConflictCandidate, observation_id: str
) -> dict[str, str]:
    if observation_id == candidate.observation_a_id:
        preview = (raw_candidate.get("supporting_observations_preview") or [{}])[0]
        identity = candidate.claim_a_identity
    else:
        preview = (
            raw_candidate.get("opposing_observations_preview") or [{}]
        )[0]
        identity = candidate.claim_b_identity
    return {
        "normalized_claim_identity": identity,
        "canonical_subject": str(preview.get("subject_raw") or "unavailable"),
        "canonical_relation": str(preview.get("relation_raw") or "unavailable"),
        "canonical_object": str(preview.get("object_raw") or "unavailable"),
        "normalized_polarity": str(preview.get("direction") or "unavailable"),
    }


def _find_parsed_pair(
    provider_calls: list[dict[str, Any]], pair_id: str
) -> tuple[dict[str, Any], str]:
    for record in provider_calls:
        if record.get("call_type") == "comparison" and record.get("record_id") == pair_id:
            payload = record.get("parsed_payload")
            if not isinstance(payload, dict):
                raise ValueError("legacy_pair_parsed_payload_missing")
            prompt_identity = layer_identity(
                "legacy_context_pair_prompt",
                "legacy_context_pair_prompt_identity_v1",
                {
                    "provider_execution_identity_sha256": record.get(
                        "provider_execution_identity_sha256"
                    ),
                    "request_identity": record.get("request_identity"),
                    "comparison_schema_version": payload.get("schema_version"),
                },
            )
            return payload, prompt_identity
    raise ValueError(f"legacy_pair_not_found:{pair_id}")


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"offline_split_output_exists:{output}")
    artifacts = output / "artifacts"
    schemas = artifacts / "schemas"
    schemas.mkdir(parents=True)

    candidate_path = Path(args.candidates)
    observation_path = Path(args.observations)
    validation_audit_path = Path(args.observation_validation_audit)
    provider_calls_path = Path(args.legacy_provider_calls)
    registry_path = Path(args.registry)
    composition_path = Path(args.composition)
    raw_candidates = _jsonl(candidate_path)
    legacy_observations = _jsonl(observation_path)
    legacy_validation_audit = _jsonl(validation_audit_path)
    provider_calls = _jsonl(provider_calls_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    context_statuses = {
        record["record_id"]: "validated" if record.get("valid") else "failed"
        for record in legacy_validation_audit
        if record.get("record_type") == "extraction"
    }
    candidates: list[ConflictCandidate] = []
    raw_by_id: dict[str, dict[str, Any]] = {}
    claim_by_observation: dict[str, dict[str, str]] = {}
    candidate_audits: list[dict[str, Any]] = []
    for raw in raw_candidates:
        candidate = adapt_legacy_weak_candidate(
            raw, context_statuses=context_statuses
        )
        candidate, errors = validate_conflict_candidate(candidate)
        if errors:
            raise ValueError(f"candidate_projection_failed:{candidate.candidate_id}:{errors}")
        candidates.append(candidate)
        raw_by_id[candidate.candidate_id] = raw
        claim_by_observation.setdefault(
            candidate.observation_a_id,
            _claim_metadata(raw, candidate, candidate.observation_a_id),
        )
        claim_by_observation.setdefault(
            candidate.observation_b_id,
            _claim_metadata(raw, candidate, candidate.observation_b_id),
        )
        candidate_audits.append(
            {
                "candidate_id": candidate.candidate_id,
                "valid": True,
                "context_readiness": candidate.context_readiness,
                "legacy_candidate_identity_preserved": True,
            }
        )

    registry_identity = layer_identity(
        "factor_registry",
        "factor_registry_identity_v1",
        {
            "registry_version": registry["registry_version"],
            "content_sha256": _sha256(registry_path),
        },
    )
    composition_identity = layer_identity(
        "composition_policy",
        "composition_policy_identity_v1",
        {"content_sha256": _sha256(composition_path)},
    )
    contexts: list[ObservationContext] = []
    observation_audits: list[dict[str, Any]] = []
    adapter_audits: list[dict[str, Any]] = []
    for source in legacy_observations:
        observation_id = source["observation_id"]
        claim = claim_by_observation.get(observation_id)
        if not claim:
            observation_audits.append(
                {
                    "observation_id": observation_id,
                    "valid": False,
                    "errors": ["normalized_claim_identity_unavailable"],
                }
            )
            continue
        anchors = sorted(
            {
                anchor
                for factor in source.get("context_factors") or []
                for anchor in factor.get("evidence_anchor_ids") or []
            }
        )
        spans = [
            factor.get("explicit_span")
            for factor in source.get("context_factors") or []
            if factor.get("explicit_span")
        ]
        context, adapter_audit = adapt_legacy_context_extraction(
            source,
            claim=claim,
            evidence_chain_identity=layer_identity(
                "evidence_chain",
                "legacy_evidence_chain_identity_adapter_v1",
                {"observation_id": observation_id, "anchor_ids": anchors},
            ),
            token_catalog_identity=layer_identity(
                "token_catalog",
                "legacy_token_catalog_identity_adapter_v1",
                {"observation_id": observation_id, "explicit_spans": spans},
            ),
            anchor_set_identity=layer_identity(
                "anchor_set",
                "legacy_anchor_set_identity_adapter_v1",
                {"observation_id": observation_id, "anchor_ids": anchors},
            ),
            registry_identity=registry_identity,
            composition_identity=composition_identity,
        )
        context, errors = validate_observation_context(context)
        if errors:
            raise ValueError(f"observation_context_projection_failed:{observation_id}:{errors}")
        contexts.append(context)
        observation_audits.append(
            {"observation_id": observation_id, "valid": True, "errors": []}
        )
        adapter_audits.append(adapter_audit)

    for source_audit in legacy_validation_audit:
        if (
            source_audit.get("record_type") == "extraction"
            and not source_audit.get("valid")
        ):
            observation_audits.append(
                {
                    "observation_id": source_audit["record_id"],
                    "valid": False,
                    "errors": list(source_audit.get("errors") or []),
                    "failure_class": "observation_context_policy_coverage_failure",
                    "source_validation_reused_as_failure_only": True,
                }
            )

    contexts_by_id = {item.observation_id: item for item in contexts}
    candidate = next(
        item for item in candidates if item.candidate_id == args.target_pair_id
    )
    context_a = contexts_by_id[candidate.observation_a_id]
    context_b = contexts_by_id[candidate.observation_b_id]
    legacy_pair, legacy_prompt_identity = _find_parsed_pair(
        provider_calls, args.target_pair_id
    )
    difference, difference_adapter_audit = (
        adapt_legacy_pair_to_context_difference(
            legacy_pair,
            candidate=candidate,
            context_a=context_a,
            context_b=context_b,
            factor_registry_identity=registry_identity,
            legacy_prompt_identity=legacy_prompt_identity,
        )
    )
    known_factor_ids = {
        factor_id
        for profile in registry["profiles"].values()
        for factor_id in profile["factors"]
    }
    difference, difference_errors = validate_context_difference(
        difference,
        candidate=candidate,
        context_a=context_a,
        context_b=context_b,
        known_factor_ids=known_factor_ids,
    )
    difference_valid = not difference_errors
    if not difference_valid:
        difference.validation_status = "rejected"

    differences = [difference] if difference_valid else []
    comparabilities = []
    comparability_audits = []
    if difference_valid:
        comparability = create_pending_comparability(
            candidate=candidate, difference=difference
        )
        comparability, comparability_errors = validate_conflict_comparability(
            comparability, candidate=candidate, difference=difference
        )
        comparabilities.append(comparability)
        comparability_audits.append(
            {
                "candidate_id": candidate.candidate_id,
                "contract_valid": not comparability_errors,
                "scientifically_validated": False,
                "assessment_status": comparability.assessment_status,
                "errors": comparability_errors,
            }
        )
    else:
        comparability = None

    decisions = []
    for item in candidates:
        if item.candidate_id == candidate.candidate_id:
            decisions.append(
                stage_formal_conflict_decision(
                    candidate=item,
                    difference=difference if difference_valid else None,
                    comparability=comparability,
                )
            )
        else:
            decisions.append(
                stage_formal_conflict_decision(
                    candidate=item, difference=None, comparability=None
                )
            )

    _write_jsonl(
        artifacts / "observation_contexts.jsonl",
        (item.model_dump(mode="json") for item in contexts),
    )
    _write_jsonl(
        artifacts / "observation_context_validation_audit.jsonl",
        observation_audits,
    )
    _write_json(
        artifacts / "observation_context_cache.json",
        {
            item.observation_id: {
                "observation_context_identity": item.observation_context_identity,
                "validation_status": item.validation_status,
            }
            for item in contexts
        },
    )
    _write_jsonl(
        artifacts / "observation_context_adapter_audit.jsonl", adapter_audits
    )
    _write_jsonl(
        artifacts / "conflict_candidates.jsonl",
        (item.model_dump(mode="json") for item in candidates),
    )
    _write_jsonl(
        artifacts / "conflict_candidate_validation_audit.jsonl", candidate_audits
    )
    _write_jsonl(
        artifacts / "context_differences.jsonl",
        (item.model_dump(mode="json") for item in differences),
    )
    _write_jsonl(
        artifacts / "context_difference_validation_audit.jsonl",
        [
            {
                "candidate_id": candidate.candidate_id,
                "valid": difference_valid,
                "errors": difference_errors,
            }
        ],
    )
    _write_jsonl(
        artifacts / "context_difference_adapter_audit.jsonl",
        [difference_adapter_audit],
    )
    _write_jsonl(
        artifacts / "conflict_comparability_assessments.jsonl",
        (item.model_dump(mode="json") for item in comparabilities),
    )
    _write_jsonl(
        artifacts / "conflict_comparability_validation_audit.jsonl",
        comparability_audits,
    )
    _write_jsonl(
        artifacts / "formal_conflict_decisions_staging.jsonl",
        (item.model_dump(mode="json") for item in decisions),
    )

    schema_models = (
        ObservationContext,
        ConflictCandidate,
        ContextDifference,
        type(comparability) if comparability is not None else None,
        type(decisions[0]),
    )
    for model in schema_models:
        if model is not None:
            schema = model.model_json_schema()
            name = schema["$id"].rsplit("/", 1)[-1]
            _write_json(schemas / f"{name}.schema.json", schema)

    contract_payload = {
        "contract_version": "conflict_comparability_effect_semantic_contract_v1",
        "scope": "conflict_comparability",
        "authority": "proposed_non_runtime",
        "model_b_status": "Proposed",
        "runtime_activation": False,
    }
    new_contract_identity = layer_identity(
        "conflict_comparability_effect_semantic_contract",
        "conflict_comparability_effect_semantic_contract_identity_v1",
        contract_payload,
    )
    migration = {
        "legacy_context_scoped_contract_identity": OLD_CONTRACT_IDENTITY,
        "conflict_comparability_effect_semantic_contract_identity_v1": (
            new_contract_identity
        ),
        "scope_migration": "context_attribution_to_conflict_comparability",
        "semantic_content_changed": True,
        "runtime_activation": False,
        "historical_identity_preserved": True,
    }
    _write_json(artifacts / "effect_contract_scope_migration.json", migration)

    source_hashes = {
        str(path): _sha256(path)
        for path in (
            candidate_path,
            observation_path,
            validation_audit_path,
            provider_calls_path,
            registry_path,
            composition_path,
        )
    }
    summary = {
        "schema_version": "context_pipeline_layer_summary_v1",
        "execution_status": "completed",
        "validated_observation_context_count": len(contexts),
        "failed_observation_context_count": sum(
            not item["valid"] for item in observation_audits
        ),
        "validated_context_difference_count": len(differences),
        "validated_conflict_comparability_count": sum(
            item.assessment_status == "validated"
            and item.validation_status == "validated"
            for item in comparabilities
        ),
        "formal_conflict_confirmed_count": sum(
            item.formal_conflict_confirmed for item in decisions
        ),
        "target_pair_id": candidate.candidate_id,
        "target_difference_status": (
            "validated" if difference_valid else "rejected"
        ),
        "target_comparability_status": (
            comparability.assessment_status if comparability else "not_assessed"
        ),
        "target_formal_judgment_status": next(
            item.decision_status
            for item in decisions
            if item.candidate_id == candidate.candidate_id
        ),
        "candidate_pair_count_before": len(raw_candidates),
        "candidate_pair_count_after": len(candidates),
        "candidate_pair_ids_before": [
            item["candidate_id"] for item in raw_candidates
        ],
        "candidate_pair_ids_after": [item.candidate_id for item in candidates],
        "candidate_pair_identity_changed": False,
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
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
        "historical_runs_modified": False,
        "formal_v3_modified": False,
        "projection_modified": False,
        "polarity_modified": False,
        "sign_modified": False,
        "canonical_edge_modified": False,
        "candidate_pairs_modified": False,
        "composition_rules_added": 0,
    }
    _write_json(artifacts / "context_pipeline_layer_summary.json", summary)
    manifest = {
        "schema_version": "context_pipeline_layer_manifest_v1",
        "run_scope": "offline_architecture_split_staging",
        "source_hashes": source_hashes,
        "source_hashes_verified_after_materialization": all(
            _sha256(Path(path)) == digest for path, digest in source_hashes.items()
        ),
        "layers": {
            "L2.5": "observation_context_v1",
            "L3": "conflict_candidate_v1",
            "L4a": "context_difference_v1",
            "L4b": "conflict_comparability_assessment_v1",
            "L4c": "formal_conflict_decision_v1_staging_only",
        },
        "new_contract_identity": new_contract_identity,
        "legacy_contract_identity": OLD_CONTRACT_IDENTITY,
        "runtime_activation": False,
        "production_handoff_allowed": False,
        "artifacts": sorted(
            path.relative_to(output).as_posix()
            for path in artifacts.rglob("*")
            if path.is_file()
        ),
    }
    _write_json(artifacts / "context_pipeline_layer_manifest.json", manifest)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--observation-validation-audit", required=True)
    parser.add_argument("--legacy-provider-calls", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--composition", required=True)
    parser.add_argument("--target-pair-id", required=True)
    return parser


def main() -> None:
    summary = materialize(_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
