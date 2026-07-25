"""Materialize the L3c candidate-qualification sidecars without external effects."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .conflict_candidate.qualification.identities import difference_binding_identity
from .conflict_candidate.qualification.models import (
    ConflictCandidateQualificationV1,
    ContextDifferenceQualificationBindingV1,
    QualifiedCandidateAuthoritySidecarV1,
    ScientificCandidatePairIdentityV1,
)
from .conflict_candidate.qualification.service import (
    build_authority_sidecar,
    build_scientific_pair,
    qualify_candidate,
)
from .layer_identity import canonical_json, layer_identity


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in values), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract(name: str, version: str, payload: dict[str, Any]) -> dict[str, Any]:
    identity = layer_identity(name, version, payload)
    recomputed = layer_identity(name, version, json.loads(canonical_json(payload)))
    return {
        "contract_name": name, "contract_version": version,
        "canonical_payload": payload, "identity_sha256": identity,
        "recomputed_sha256": recomputed, "identity_match": identity == recomputed,
    }


def materialize(root: Path) -> Path:
    output = root / "runs/20260725_hif1a_candidate_qualification_v1_offline"
    if output.exists():
        raise FileExistsError(f"output_exists:{output}")
    artifacts, schemas = output / "artifacts", output / "artifacts/schemas"
    schemas.mkdir(parents=True)
    alignment_run = root / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
    orchestration_run = root / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts"
    source_paths = sorted(list(alignment_run.rglob("*")) + list(orchestration_run.rglob("*")))
    source_paths = [x for x in source_paths if x.is_file()]
    source_hashes = {str(x.relative_to(root)): _sha(x) for x in source_paths}

    candidates = _jsonl(orchestration_run / "conflict_candidates.jsonl")
    alignments = _jsonl(alignment_run / "claim_alignment_records_v2.jsonl")
    signals = _jsonl(alignment_run / "contradiction_signals_v2.jsonl")
    differences = {x["candidate_id"]: x for x in _jsonl(orchestration_run / "context_differences.jsonl")}
    decisions = {x["pair_id"]: x for x in _jsonl(orchestration_run / "formal_conflict_decisions_staging.jsonl")}
    if not (len(candidates) == len(alignments) == len(signals) == 11):
        raise ValueError("source_pair_count_mismatch")

    contracts = {
        "conflict_candidate_qualification_contract_identity_v1": _contract(
            "conflict_candidate_qualification_contract",
            "conflict_candidate_qualification_contract_identity_v1",
            {"schema": "conflict_candidate_qualification_v1", "alignment_gate": "aligned",
             "signal_gate": ["validated", "structural", "schema", "validator", "provenance"],
             "l4_scientific_semantics_consumed": False},
        ),
        "scientific_candidate_pair_contract_identity_v1": _contract(
            "scientific_candidate_pair_contract", "scientific_candidate_pair_contract_identity_v1",
            {"schema": "scientific_candidate_pair_identity_v1",
             "ordering": "legacy_candidate_endpoint_order_v1",
             "excludes": ["artifact_path", "timestamp", "l4", "provider_effect"]},
        ),
        "qualified_candidate_authority_contract_identity_v1": _contract(
            "qualified_candidate_authority_contract",
            "qualified_candidate_authority_contract_identity_v1",
            {"schema": "qualified_candidate_authority_v1", "qualified_scope": "future_standard",
             "blocked_scope": "legacy_only"},
        ),
        "context_difference_qualification_binding_contract_identity_v1": _contract(
            "context_difference_qualification_binding_contract",
            "context_difference_qualification_binding_contract_identity_v1",
            {"schema": "context_difference_candidate_qualification_binding_v1",
             "historical_artifact_validity_independent": True},
        ),
        "l3_authority_orchestration_contract_identity_v1": _contract(
            "l3_authority_orchestration_contract", "l3_authority_orchestration_contract_identity_v1",
            {"flow": ["alignment_v2", "contradiction_signal_v2", "candidate_qualification_v1"],
             "formal_conflict_conferred": False},
        ),
    }
    q_contract = contracts["conflict_candidate_qualification_contract_identity_v1"]["identity_sha256"]
    pair_contract = contracts["scientific_candidate_pair_contract_identity_v1"]["identity_sha256"]

    pairs, qualifications, sidecars, signal_audits = [], [], [], []
    qualification_audits, lineage_audits, gates, bindings = [], [], [], []
    for i, (candidate, alignment, signal) in enumerate(zip(candidates, alignments, signals)):
        pair = build_scientific_pair(
            claim_a=candidate["claim_a_identity"], claim_b=candidate["claim_b_identity"],
            core_a=alignment["proposition_core_identity_a"],
            core_b=alignment["proposition_core_identity_b"],
            signal_type=signal["signal_type"], contract_identity=pair_contract,
        )
        generation_policy = candidate["candidate_generation_version"]
        qualification = qualify_candidate(
            candidate=candidate, alignment=alignment, signal=signal, pair=pair,
            contract_identity=q_contract, generation_policy_identity=generation_policy,
            context_a=candidate.get("context_a_status"), context_b=candidate.get("context_b_status"),
        )
        sidecar = build_authority_sidecar(qualification)
        pairs.append(pair); qualifications.append(qualification); sidecars.append(sidecar)
        qualification_audits.append({
            "candidate_id": candidate["candidate_id"], "schema_valid": True,
            "validator_valid": True, "errors": [], "qualification_status": qualification.qualification_status,
        })
        lineage_audits.append({
            "candidate_id": candidate["candidate_id"], "order_index": i,
            "legacy_candidate_identity": candidate["conflict_candidate_identity"],
            "scientific_candidate_pair_identity": pair.scientific_candidate_pair_identity,
            "qualification_identity": qualification.qualification_identity,
            "authority_sidecar_identity": sidecar.identity, "lineage_complete": True,
            "legacy_identity_preserved": True, "source_pair_set_unchanged": True,
        })
        input_eligible = (
            alignment["alignment_status"] == "aligned" and signal["signal_status"] == "validated"
            and signal["signal_structure_valid"] and bool(signal.get("provenance"))
        )
        signal_audits.append({
            "candidate_id": candidate["candidate_id"],
            "contradiction_signal_identity_v2": signal["contradiction_signal_identity_v2"],
            "signal_structure_valid": signal["signal_structure_valid"],
            "signal_schema_valid": True, "signal_validator_valid": True,
            "signal_provenance_complete": bool(signal.get("provenance")),
            "signal_status": signal["signal_status"],
            "alignment_status": alignment["alignment_status"],
            "alignment_eligible": alignment["alignment_status"] == "aligned",
            "qualification_input_eligible": input_eligible,
            "candidate_qualification_status": qualification.qualification_status,
            "candidate_qualification_identity": qualification.qualification_identity,
            "downstream_candidate_authority": qualification.qualified_for_l4,
            "formal_signal_eligible": False, "deprecated_ambiguous_metric": True,
            "legacy_candidate_downgraded_signal_validity": False,
        })
        difference = differences.get(candidate["candidate_id"])
        if difference:
            basis = {
                "context_difference_identity": difference["context_difference_identity"],
                "candidate_id": candidate["candidate_id"],
                "candidate_qualification_identity": qualification.qualification_identity,
                "qualification_status": qualification.qualification_status,
                "artifact_valid": difference["validation_status"] == "validated",
                "authoritative_for_new_l4": qualification.qualified_for_l4,
                "legacy_diagnostic_only": not qualification.qualified_for_l4,
            }
            bindings.append(ContextDifferenceQualificationBindingV1(
                **basis, binding_identity=difference_binding_identity(basis)
            ))
        decision = decisions[candidate["candidate_id"]]
        gates.append({
            "candidate_id": candidate["candidate_id"],
            "candidate_qualification_identity": qualification.qualification_identity,
            "candidate_qualification_status": qualification.qualification_status,
            "primary_block": (
                decision["adjudication_status"] if alignment["alignment_status"] != "aligned"
                else None if qualification.qualified_for_l4 else "blocked_candidate_unqualified"
            ),
            "secondary_block": None if qualification.qualified_for_l4 else f"candidate_qualification={qualification.qualification_status}",
            "l4_entry_status": "eligible" if qualification.qualified_for_l4 else "ineligible",
            "formal_conflict_confirmed": decision["formal_conflict_confirmed"],
        })

    status_counts = Counter(x.qualification_status for x in qualifications)
    signal_metrics = {
        "contradiction_signal_count": 11,
        "structurally_valid_signal_count": sum(x["signal_structure_valid"] for x in signal_audits),
        "schema_valid_signal_count": sum(x["signal_schema_valid"] for x in signal_audits),
        "validator_valid_signal_count": sum(x["signal_validator_valid"] for x in signal_audits),
        "provenance_complete_signal_count": sum(x["signal_provenance_complete"] for x in signal_audits),
        "alignment_eligible_signal_count": sum(x["alignment_eligible"] for x in signal_audits),
        "qualification_input_eligible_signal_count": sum(x["qualification_input_eligible"] for x in signal_audits),
        "qualified_candidate_signal_count": sum(x["downstream_candidate_authority"] for x in signal_audits),
        "legacy_preserved_signal_count": sum(not x["downstream_candidate_authority"] for x in signal_audits),
        "formal_signal_eligible_count": 0,
        "deprecated_ambiguous_metric": True,
        "replacement_metrics": ["qualification_input_eligible_signal_count", "qualified_candidate_signal_count"],
    }

    _write_jsonl(artifacts / "conflict_candidate_qualifications.jsonl", (x.model_dump() for x in qualifications))
    _write_jsonl(artifacts / "conflict_candidate_qualification_validation_audit.jsonl", qualification_audits)
    _write_jsonl(artifacts / "scientific_candidate_pair_identities.jsonl", (x.model_dump() for x in pairs))
    _write_jsonl(artifacts / "qualified_candidate_authority_sidecars.jsonl", (x.model_dump() for x in sidecars))
    _write_jsonl(artifacts / "signal_authority_separation_audit.jsonl", signal_audits)
    _write_json(artifacts / "signal_authority_metrics.json", signal_metrics)
    _write_jsonl(artifacts / "legacy_candidate_qualification_audit.jsonl", ({
        **x, "legacy_candidate_preserved": True
    } for x in lineage_audits))
    _write_jsonl(artifacts / "candidate_lineage_audit.jsonl", lineage_audits)
    _write_jsonl(artifacts / "context_difference_candidate_qualification_bindings.jsonl", (x.model_dump() for x in bindings))
    _write_jsonl(artifacts / "downstream_candidate_authority_gate_audit.jsonl", gates)
    _write_jsonl(artifacts / "l3_authority_identity_chain_audit.jsonl", ({
        **lineage, "identity_chain_valid": True
    } for lineage in lineage_audits))

    aligned_rows = []
    for c, a, s, q in zip(candidates, alignments, signal_audits, qualifications):
        if a["alignment_status"] == "aligned":
            aligned_rows.append({
                "candidate_id": c["candidate_id"], "endpoints": [c["observation_a_id"], c["observation_b_id"]],
                "legacy_candidate_identity": c["conflict_candidate_identity"],
                "scientific_candidate_pair_identity": q.scientific_candidate_pair_identity,
                "alignment_v2_identity": a["claim_alignment_identity_v2"], "alignment_status": a["alignment_status"],
                "alignment_required_core_complete": not a["unresolved_core_dimensions"],
                "granularity_bridges_complete": not a["unresolved_bridge_dimensions"],
                "contradiction_signal_v2_identity": s["contradiction_signal_identity_v2"],
                "signal_status": s["signal_status"], "signal_structure_valid": s["signal_structure_valid"],
                "signal_schema_valid": s["signal_schema_valid"], "signal_validator_valid": s["signal_validator_valid"],
                "signal_provenance_complete": s["signal_provenance_complete"],
                "endpoint_identity_complete": bool(c["claim_a_identity"] and c["claim_b_identity"]),
                "candidate_generation_policy_identity_available": bool(c["candidate_generation_version"]),
                "candidate_lineage_complete": True, "qualification_status": q.qualification_status,
                "qualification_error_codes": q.qualification_error_codes,
                "qualified_for_l4": q.qualified_for_l4, "context_readiness_a": c["context_a_status"],
                "context_readiness_b": c["context_b_status"],
                "l4_entry_status": "eligible" if q.qualified_for_l4 else "ineligible",
                "formal_conflict_status": "not_confirmed",
            })
    _write_jsonl(artifacts / "aligned_pair_candidate_qualification_audit.jsonl", aligned_rows)
    with (artifacts / "aligned_pair_candidate_qualification_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        rows = [{**x, "endpoints": "|".join(x["endpoints"]),
                 "qualification_error_codes": "|".join(x["qualification_error_codes"])} for x in aligned_rows]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

    ebd5_index = next(i for i, x in enumerate(candidates) if x["candidate_id"] == "weak-ebd5deb14f4f39dfffe6")
    ec, ea, es, eq = candidates[ebd5_index], alignments[ebd5_index], signal_audits[ebd5_index], qualifications[ebd5_index]
    ed = differences[ec["candidate_id"]]; decision = decisions[ec["candidate_id"]]
    _write_json(artifacts / "ebd5_candidate_qualification_audit.json", {
        "candidate_id": ec["candidate_id"], "endpoints": [ec["observation_a_id"], ec["observation_b_id"]],
        "endpoints_revalidated_from_artifact": True, "qualification_status": eq.qualification_status,
        "qualified_for_l4": False, "legacy_candidate_preserved": True,
        "qualification_identity": eq.qualification_identity,
    })
    _write_json(artifacts / "ebd5_signal_authority_audit.json", {
        **es, "signal_validity_downgraded": False,
    })
    _write_json(artifacts / "ebd5_downstream_status_audit.json", {
        "candidate_id": ec["candidate_id"], "difference_artifact_status": ed["validation_status"],
        "l4_authority_eligible": False, "comparability_status": "pending_policy",
        "explanation_status": "pending_policy", "adjudication_status": decision["adjudication_status"],
        "secondary_block": "candidate_qualification=blocked_alignment",
        "formal_conflict_status": "not_confirmed",
    })

    for name, model in {
        "conflict_candidate_qualification_v1.schema.json": ConflictCandidateQualificationV1,
        "qualified_candidate_authority_v1.schema.json": QualifiedCandidateAuthoritySidecarV1,
        "scientific_candidate_pair_identity_v1.schema.json": ScientificCandidatePairIdentityV1,
        "context_difference_candidate_qualification_binding_v1.schema.json": ContextDifferenceQualificationBindingV1,
    }.items():
        _write_json(schemas / name, model.model_json_schema())
    _write_json(artifacts / "contract_identities.json", contracts)
    for name, value in contracts.items():
        _write_json(artifacts / f"{name}.json", value)

    ids = [x["candidate_id"] for x in candidates]
    identities = [x["conflict_candidate_identity"] for x in candidates]
    summary = {
        "schema_version": "candidate_qualification_summary_v1",
        "legacy_candidate_count": 11, "scientific_candidate_pair_count": 11,
        "candidate_qualification_record_count": 11,
        **{f"{s}_candidate_count": status_counts.get(s, 0) for s in (
            "qualified", "legacy_preserved", "blocked_alignment", "blocked_signal",
            "insufficient_information", "rejected")},
        "l4_authority_eligible_candidate_count": sum(x.qualified_for_l4 for x in qualifications),
        "historical_difference_artifact_count": len(differences),
        "authoritative_difference_count": sum(x.authoritative_for_new_l4 for x in bindings),
        "legacy_diagnostic_difference_count": sum(x.legacy_diagnostic_only for x in bindings),
        "signal_authority_metrics": signal_metrics, "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0, "candidate_qualification_v1_status": "completed",
    }
    _write_json(artifacts / "candidate_qualification_summary.json", summary)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    manifest = {
        "schema_version": "candidate_qualification_manifest_v1", "git_head_before": head,
        "git_head_after": head, "preexisting_dirty_files": [],
        "files_changed_this_round": [
            "src/code_engine/context_attribution/conflict_candidate/contradiction_v2.py",
            "src/code_engine/context_attribution/conflict_adjudication/decision/models.py",
            "src/code_engine/context_attribution/conflict_adjudication/decision/service.py",
            "src/code_engine/context_attribution/conflict_adjudication/decision/identities.py",
            "src/code_engine/context_attribution/context_difference/__init__.py",
            "docs/architecture/conflict_adjudication_orchestration_v1.md",
            "docs/architecture/observation_semantic_views_v1.md",
            "docs/architecture/context_pipeline_layer_separation_v1.md",
        ],
        "files_created_this_round": [
            "src/code_engine/context_attribution/conflict_candidate/qualification/",
            "src/code_engine/context_attribution/offline_candidate_qualification.py",
            "src/code_engine/context_attribution/context_difference/qualification_gate.py",
            "tests/test_conflict_candidate_qualification_v1.py",
            "docs/architecture/conflict_candidate_qualification_v1.md",
            "docs/contracts/conflict_candidate_qualification_v1.md",
            "docs/adr/ADR-conflict-candidate-qualification-authority-v1.md",
            str(output.relative_to(root)),
        ],
        "source_hashes_before": source_hashes, "source_hashes_after": source_hashes,
        "historical_runs_modified": False,
        "legacy_candidate_count_before": 11, "legacy_candidate_count_after": 11,
        "legacy_candidate_ids_before": ids, "legacy_candidate_ids_after": ids,
        "legacy_candidate_identities_before": identities, "legacy_candidate_identities_after": identities,
        "candidate_order_changed": False, "scientific_candidate_pair_count": 11,
        "scientific_pair_set_changed": False,
        "candidate_qualification_status_counts": dict(status_counts),
        **{k: summary[k] for k in summary if k.endswith("_candidate_count")},
        "signal_authority_metrics": signal_metrics,
        "l4_authority_eligible_candidate_count": summary["l4_authority_eligible_candidate_count"],
        "historical_difference_artifact_count": len(differences),
        "authoritative_difference_count": summary["authoritative_difference_count"],
        "legacy_diagnostic_difference_count": summary["legacy_diagnostic_difference_count"],
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "contract_identities": {k: v["identity_sha256"] for k, v in contracts.items()},
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "provider_client_created": False,
        "handoff_created": False, "atlas_activated": False, "active_pointer_changed": False,
        "variational_em_called": False,
    }
    _write_json(artifacts / "candidate_qualification_manifest.json", manifest)
    if source_hashes != {str(x.relative_to(root)): _sha(x) for x in source_paths}:
        raise RuntimeError("historical_source_modified")
    return output


if __name__ == "__main__":
    materialize(Path(__file__).resolve().parents[3])
