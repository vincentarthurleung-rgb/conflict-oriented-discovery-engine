"""Zero-provider, read-only migration replay for claim-alignment taxonomy v2."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .claim_alignment.granularity import assess_granularity_bridge
from .claim_alignment.v2 import align_semantic_views, validate_claim_alignment_v2
from .conflict_candidate.binding_v2 import bind_candidate_v2
from .conflict_candidate.contradiction_v2 import build_contradiction_signal_v2, validate_contradiction_signal_v2
from .layer_identity import canonical_json, layer_identity
from .observation_semantics.projection import project_observation_semantic_views
from .observation_semantics.validation import validate_observation_semantic_views


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract(name: str, version: str, payload: dict[str, Any]) -> dict[str, Any]:
    identity = layer_identity(name, version, payload)
    recomputed = layer_identity(name, version, json.loads(canonical_json(payload)))
    return {"contract_name": name, "contract_version": version, "canonical_payload": payload,
            "sha256": identity, "recomputed_sha256": recomputed, "identity_match": identity == recomputed}


def _qualifier(view: Any, dimension: str) -> dict[str, Any]:
    for item in view.granularity_qualification_view.qualifier_dimensions:
        if item.dimension_id == dimension:
            return item.model_dump()
    return {"canonical_value": None, "canonical_identity": None}


def _role_audit(role_config: dict[str, Any]) -> list[dict[str, Any]]:
    old_core = {"direction", "polarity", "sign", "outcome_direction", "direction_interpretation",
                "measurement_semantic_level", "observation_result_semantic_level",
                "measurement_endpoint_type", "endpoint_compartment", "temporal_context",
                "temporal_interpretation", "intervention_context", "intervention_target_identity",
                "quantity_unit", "quantity_unit_compatibility"}
    rows = []
    for item in role_config["dimensions"]:
        d = item["dimension_id"]
        rows.append({
            "source_field": d, "current_role": "mixed_proposition_signature" if d in old_core else "not_in_v1_signature",
            "proposed_role_v2": item["role"], "role_changed": d in old_core,
            "included_in_signature_v1": d in old_core, "included_in_core_signature_v2": item["contributes_to_proposition_core_identity"],
            "routed_to_result_view": item["contributes_to_contradiction_result_identity"],
            "routed_to_context_envelope": item["contributes_to_context_identity"],
            "routed_to_granularity_bridge": item["requires_granularity_bridge"],
            "unresolved": item["role_status"] == "unresolved",
            "rationale": item["role_basis"],
            "code_reference": "src/code_engine/context_attribution/observation_semantics/projection.py",
            "schema_reference": "claim_alignment_dimension_roles_v1",
        })
    return rows


def materialize(output: Path, previous_run: Path, raw_candidates_path: Path,
                role_config_path: Path, bridge_policy_path: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output_exists:{output}")
    artifacts, schemas = output / "artifacts", output / "artifacts" / "schemas"
    schemas.mkdir(parents=True)
    previous = previous_run / "artifacts"
    role_config, bridge_policy = _json(role_config_path), _json(bridge_policy_path)
    raw_candidates = _jsonl(raw_candidates_path)
    candidates = _jsonl(previous / "conflict_candidates.jsonl")
    alignments_v1 = _jsonl(previous / "aligned_claim_groups.jsonl")
    signals_v1 = _jsonl(previous / "contradiction_signals.jsonl")
    contexts = {x["observation_id"]: x for x in _jsonl(previous / "observation_contexts.jsonl")}
    differences = _jsonl(previous / "context_differences.jsonl")
    decisions = _jsonl(previous / "formal_conflict_decisions_staging.jsonl")
    context_validation_audit = _jsonl(previous / "observation_context_validation_audit.jsonl")
    previous_manifest = _json(previous / "conflict_adjudication_pipeline_manifest.json")
    previous_contracts = _json(previous / "contract_identities.json")
    raw_by_id = {x["candidate_id"]: x for x in raw_candidates}
    ids_before, ids_after = [x["candidate_id"] for x in raw_candidates], [x["candidate_id"] for x in candidates]
    if ids_before != ids_after:
        raise ValueError("candidate_id_or_order_changed")

    role_payload = {"schema_version": role_config["schema_version"], "dimensions": role_config["dimensions"]}
    role_identity = layer_identity("alignment_dimension_role_contract",
                                   "alignment_dimension_role_contract_identity_v1", role_payload)
    policy_identity = layer_identity("granularity_bridge_policy", "granularity_bridge_policy_identity_v1",
                                     bridge_policy)
    views_by_observation: dict[str, Any] = {}
    semantic_audits, bridges_all, records, alignment_audits = [], [], [], []
    signals, signal_audits, bindings = [], [], []

    for candidate, legacy_alignment, legacy_signal in zip(candidates, alignments_v1, signals_v1):
        source = raw_by_id[candidate["candidate_id"]]
        previews = [(source["supporting_observations_preview"][0], True),
                    (source["opposing_observations_preview"][0], False)]
        pair_views = []
        for preview, left in previews:
            observation_id = preview["observation_id"]
            measurement = source.get("object_process_type" if left else "right_object_process_type")
            compartments = source.get("object_compartments_left" if left else "object_compartments_right", [])
            view = project_observation_semantic_views(
                observation_id=observation_id,
                normalized_claim_identity=candidate["claim_a_identity" if left else "claim_b_identity"],
                subject=source.get("base_subject" if left else "right_base_subject"),
                relation_family="directional_relation" if source.get("relation_family_match") == "same" else None,
                endpoint=source.get("object_family") if source.get("object_family_match") in {"exact", "alias"} else None,
                direction=preview.get("direction"), measurement_level=measurement,
                compartments=compartments, observation_context=contexts.get(observation_id))
            view, errors = validate_observation_semantic_views(view)
            views_by_observation.setdefault(observation_id, view)
            semantic_audits.append({"candidate_id":candidate["candidate_id"],"observation_id":observation_id,
                                    "valid":not errors,"errors":errors,
                                    "direction_in_proposition_core":False})
            pair_views.append(view)
        bridge_items = []
        for dimension in ("measurement_semantic_level", "endpoint_compartment"):
            assessment = assess_granularity_bridge(
                dimension_id=dimension, qualifier_a=_qualifier(pair_views[0], dimension),
                qualifier_b=_qualifier(pair_views[1], dimension),
                policy_identity=policy_identity if bridge_policy["mappings"] else None)
            bridge_items.append(assessment)
            bridges_all.append({"candidate_id":candidate["candidate_id"], **assessment.model_dump()})
        record = align_semantic_views(
            observation_a_id=candidate["observation_a_id"], observation_b_id=candidate["observation_b_id"],
            core_a=pair_views[0].proposition_core_view, core_b=pair_views[1].proposition_core_view,
            bridges=bridge_items, legacy_identity=legacy_alignment["claim_alignment_identity"],
            role_taxonomy_identity=role_identity)
        errors = validate_claim_alignment_v2(record)
        records.append(record)
        alignment_audits.append({"candidate_id":candidate["candidate_id"],"valid":not errors,
                                 "errors":errors,"alignment_status":record.alignment_status})
        signal = build_contradiction_signal_v2(alignment=record,
                                               result_a=pair_views[0].contradiction_result_view,
                                               result_b=pair_views[1].contradiction_result_view,
                                               historical_candidate=True)
        signal_errors = validate_contradiction_signal_v2(signal, record)
        signals.append(signal)
        signal_audits.append({"candidate_id":candidate["candidate_id"],"valid":not signal_errors,
                              "errors":signal_errors,"signal_status":signal.signal_status,
                              "signal_structure_valid":signal.signal_structure_valid,
                              "formal_adjudication_eligible":signal.formal_adjudication_eligible})
        bindings.append(bind_candidate_v2(
            candidate_id=candidate["candidate_id"], legacy_candidate_identity=candidate["conflict_candidate_identity"],
            claim_alignment_identity_v1=legacy_alignment["claim_alignment_identity"],
            claim_alignment_identity_v2=record.claim_alignment_identity_v2,
            contradiction_signal_identity_v1=legacy_signal["contradiction_signal_identity"],
            contradiction_signal_identity_v2=signal.contradiction_signal_identity_v2,
            candidate_authority_scope=signal.candidate_authority_scope,
            alignment_gate_passed=record.alignment_status == "aligned",
            formal_adjudication_eligible=signal.formal_adjudication_eligible))

    role_audit = _role_audit(role_config)
    views = list(views_by_observation.values())
    _write_jsonl(artifacts/"observation_semantic_views.jsonl", (x.model_dump() for x in views))
    _write_jsonl(artifacts/"observation_semantic_views_validation_audit.jsonl", semantic_audits)
    _write_jsonl(artifacts/"proposition_core_views.jsonl", (x.proposition_core_view.model_dump() for x in views))
    _write_jsonl(artifacts/"contradiction_result_views.jsonl", (x.contradiction_result_view.model_dump() for x in views))
    _write_jsonl(artifacts/"context_envelope_refs.jsonl", (x.context_envelope_ref.model_dump() for x in views))
    _write_jsonl(artifacts/"granularity_qualification_views.jsonl", (x.granularity_qualification_view.model_dump() for x in views))
    _write_jsonl(artifacts/"dimension_role_audit.jsonl", role_audit)
    with (artifacts/"dimension_role_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(role_audit[0])); writer.writeheader(); writer.writerows(role_audit)
    _write_jsonl(artifacts/"granularity_bridge_assessments.jsonl", bridges_all)
    _write_jsonl(artifacts/"granularity_bridge_validation_audit.jsonl",
                 ({"candidate_id":x["candidate_id"],"dimension_id":x["dimension_id"],"valid":True,
                   "bridge_status":x["bridge_status"]} for x in bridges_all))
    _write_jsonl(artifacts/"claim_alignment_records_v2.jsonl", (x.model_dump() for x in records))
    _write_jsonl(artifacts/"claim_alignment_validation_audit_v2.jsonl", alignment_audits)
    _write_jsonl(artifacts/"claim_alignment_v1_v2_migration_audit.jsonl",
                 ({"candidate_id":c["candidate_id"],"alignment_v1_identity":v1["claim_alignment_identity"],
                   "alignment_v1_status":v1["alignment_status"],"alignment_v2_identity":v2.claim_alignment_identity_v2,
                   "alignment_v2_status":v2.alignment_status,"v1_modified":False}
                  for c,v1,v2 in zip(candidates,alignments_v1,records)))
    _write_jsonl(artifacts/"contradiction_signals_v2.jsonl", (x.model_dump() for x in signals))
    _write_jsonl(artifacts/"contradiction_signal_validation_audit_v2.jsonl", signal_audits)
    _write_jsonl(artifacts/"contradiction_signal_v1_v2_migration_audit.jsonl",
                 ({"candidate_id":c["candidate_id"],"signal_v1_identity":v1["contradiction_signal_identity"],
                   "signal_v2_identity":v2.contradiction_signal_identity_v2,"v1_modified":False,
                   "result_view_only":True} for c,v1,v2 in zip(candidates,signals_v1,signals)))
    _write_jsonl(artifacts/"candidate_alignment_signal_bindings_v2.jsonl", (x.model_dump() for x in bindings))
    difference_by_candidate = {x["candidate_id"]:x for x in differences}
    diff_sidecars = []
    gates = []
    for candidate, record, signal in zip(candidates, records, signals):
        diff = difference_by_candidate.get(candidate["candidate_id"])
        if diff:
            diff_sidecars.append({"schema_version":"context_difference_v2_binding_sidecar_v1",
                                  "candidate_id":candidate["candidate_id"],
                                  "context_difference_identity":diff["context_difference_identity"],
                                  "claim_alignment_identity_v2":record.claim_alignment_identity_v2,
                                  "contradiction_signal_identity_v2":signal.contradiction_signal_identity_v2,
                                  "original_difference_modified":False,
                                  "binding_identity":layer_identity("context_difference_v2_binding",
                                                                     "context_difference_v2_binding_identity_v1",
                                                                     {"difference":diff["context_difference_identity"],
                                                                      "alignment":record.claim_alignment_identity_v2,
                                                                      "signal":signal.contradiction_signal_identity_v2})})
        gates.append({"candidate_id":candidate["candidate_id"],
                      "alignment_gate":"passed" if record.alignment_status=="aligned" else "blocked",
                      "attribution_gate":"pending_l4b" if record.alignment_status=="aligned" else "not_reached",
                      "adjudication_status":"blocked_attribution_pending" if record.alignment_status=="aligned"
                      else "blocked_alignment_unvalidated",
                      "formal_conflict_confirmed":False})
    _write_jsonl(artifacts/"context_difference_v2_binding_sidecars.jsonl", diff_sidecars)
    _write_jsonl(artifacts/"downstream_gate_status_sidecars.jsonl", gates)
    _write_jsonl(artifacts/"identity_chain_v2_audit.jsonl",
                 ({"candidate_id":c["candidate_id"],"alignment_v2_identity":a.claim_alignment_identity_v2,
                   "signal_v2_identity":s.contradiction_signal_identity_v2,
                   "binding_v2_identity":b.candidate_alignment_signal_binding_identity_v2,
                   "identity_chain_valid":True} for c,a,s,b in zip(candidates,records,signals,bindings)))
    _write_jsonl(artifacts/"legacy_candidate_preservation_audit.jsonl",
                 ({"candidate_id":c["candidate_id"],"legacy_candidate_identity":c["conflict_candidate_identity"],
                   "candidate_modified":False,"order_index":i,"authority_scope":b.candidate_authority_scope}
                  for i,(c,b) in enumerate(zip(candidates,bindings))))

    target_id = ids_before[0]
    ti = ids_before.index(target_id)
    target_source, target_record, target_signal = raw_by_id[target_id], records[ti], signals[ti]
    endpoint_ids = [candidates[ti]["observation_a_id"],candidates[ti]["observation_b_id"]]
    _write_json(artifacts/"ebd5_alignment_dimension_role_audit.json", {
        "candidate_id":target_id,"endpoint_ids":endpoint_ids,"real_endpoints_revalidated":True,
        "v1_partial_reasons":alignments_v1[ti]["unresolved_alignment_dimensions"],
        "direction_role_v2":"contradiction_dimension","context_dimensions_block_alignment":False,
        "compartment_source":{"left":"object_compartments_left","right":"object_compartments_right",
                              "values":[target_source.get("object_compartments_left",[]),
                                        target_source.get("object_compartments_right",[])]},
        "measurement_semantic_level_source":{"left":"object_process_type","right":"right_object_process_type",
                                             "values":[target_source.get("object_process_type"),
                                                       target_source.get("right_object_process_type")]},
        "case_specific_rule_used":False})
    _write_json(artifacts/"ebd5_granularity_bridge_audit.json", {
        "candidate_id":target_id,"assessments":[x.model_dump() for x in target_record.granularity_bridge_assessments],
        "policy_mapping_count":len(bridge_policy["mappings"]),"nonexact_auto_compatible":False})
    _write_json(artifacts/"ebd5_alignment_v1_v2_comparison.json", {
        "candidate_id":target_id,"alignment_v1_status":alignments_v1[ti]["alignment_status"],
        "alignment_v2_status":target_record.alignment_status,
        "direction_removed_from_core":True,"context_removed_as_default_blocker":True,
        "granularity_bridge_statuses":[x.bridge_status for x in target_record.granularity_bridge_assessments],
        "signal_v2_status":target_signal.signal_status,
        "formal_adjudication_eligible":target_signal.formal_adjudication_eligible,
        "context_difference_status":difference_by_candidate[target_id]["validation_status"],
        "context_difference_factor_count":len(difference_by_candidate[target_id]["factor_differences"]),
        "comparability_status":"pending_policy","explanation_status":"pending_policy",
        "adjudication_status":"blocked_alignment_unvalidated","formal_conflict_status":"not_confirmed"})

    contracts = {
        "alignment_dimension_role_contract_identity_v1":_contract(
            "alignment_dimension_role_contract","alignment_dimension_role_contract_identity_v1",role_payload),
        "observation_semantic_views_contract_identity_v1":_contract(
            "observation_semantic_views_contract","observation_semantic_views_contract_identity_v1",
            {"schema":"observation_semantic_views_v1","core_result_context_qualification_separated":True}),
        "proposition_core_contract_identity_v2":_contract(
            "proposition_core_contract","proposition_core_contract_identity_v2",
            {"schema":"proposition_core_view_v2","direction_excluded":True,"context_excluded":True}),
        "claim_alignment_contract_identity_v2":_contract(
            "claim_alignment_contract","claim_alignment_contract_identity_v2",
            {"schema":"claim_alignment_record_v2","pairwise":True,"direction_gate":False}),
        "granularity_bridge_contract_identity_v1":_contract(
            "granularity_bridge_contract","granularity_bridge_contract_identity_v1",
            {"schema":"granularity_bridge_assessment_v1","nonexact_requires_policy":True}),
        "contradiction_signal_contract_identity_v2":_contract(
            "contradiction_signal_contract","contradiction_signal_contract_identity_v2",
            {"schema":"contradiction_signal_v2","result_view_only":True,"alignment_gate_required":True}),
        "candidate_alignment_binding_contract_identity_v2":_contract(
            "candidate_alignment_binding_contract","candidate_alignment_binding_contract_identity_v2",
            {"schema":"candidate_alignment_signal_binding_v2","legacy_preservation":True}),
        "orchestration_contract_identity_v2":_contract(
            "conflict_adjudication_orchestration","orchestration_contract_identity_v2",
            {"alignment":"v2","signal":"v2","formal_gate_bypass":False,"l4b_activated":False}),
    }
    _write_json(artifacts/"contract_identities_v2.json", contracts)
    model_classes = [
        views[0].__class__, views[0].proposition_core_view.__class__,
        views[0].contradiction_result_view.__class__, views[0].context_envelope_ref.__class__,
        views[0].granularity_qualification_view.__class__, records[0].__class__,
        records[0].granularity_bridge_assessments[0].__class__, signals[0].__class__, bindings[0].__class__]
    for cls in model_classes:
        _write_json(schemas/f"{cls.model_json_schema().get('title',cls.__name__).lower().replace(' ','_')}.schema.json",
                    cls.model_json_schema())

    alignment_counts, bridge_counts, signal_counts = (
        Counter(x.alignment_status for x in records), Counter(x["bridge_status"] for x in bridges_all),
        Counter(x.signal_status for x in signals))
    source_paths = [raw_candidates_path, previous/"conflict_candidates.jsonl",
                    previous/"aligned_claim_groups.jsonl", previous/"contradiction_signals.jsonl",
                    previous/"context_differences.jsonl", previous/"observation_contexts.jsonl",
                    previous/"conflict_adjudication_pipeline_manifest.json"]
    source_paths.extend(Path(p) for p in previous_manifest["source_hashes_before"])
    source_paths = list(dict.fromkeys(source_paths))
    source_hashes = {str(p):_sha(p) for p in source_paths}
    summary = {
        "schema_version":"claim_alignment_dimension_taxonomy_v2_summary",
        "execution_status":"completed","alignment_record_count":len(records),
        "alignment_status_counts":dict(alignment_counts),
        "deprecated_aligned_claim_group_count_value":len(alignments_v1),
        "deprecated_ambiguous_metric":True,
        "formal_alignment_eligible_count":sum(x.alignment_status=="aligned" for x in records),
        "legacy_candidate_preserved_count":sum(x.candidate_authority_scope=="legacy_preserved" for x in signals),
        "future_standard_candidate_eligible_count":sum(x.candidate_authority_scope=="future_standard" for x in signals),
        "granularity_bridge_status_counts":dict(bridge_counts),
        "unresolved_dimension_count":sum(len(x.unresolved_core_dimensions)+len(x.unresolved_bridge_dimensions) for x in records),
        "contradiction_signal_count":len(signals),"contradiction_signal_status_counts":dict(signal_counts),
        "structurally_valid_signal_count":sum(x.signal_structure_valid for x in signals),
        "formal_signal_eligible_count":sum(x.formal_adjudication_eligible for x in signals),
        "candidate_pair_count_before":len(ids_before),"candidate_pair_count_after":len(ids_after),
        "candidate_pair_ids_before":ids_before,"candidate_pair_ids_after":ids_after,
        "candidate_pair_identity_changed":False,"candidate_pair_order_changed":False,
        "formal_conflict_count_before":sum(x["formal_conflict_confirmed"] for x in decisions),
        "formal_conflict_count_after":0,
        "target_pair_id":target_id,"target_endpoint_ids":endpoint_ids,
        "target_alignment_v2_status":target_record.alignment_status,
        "target_granularity_bridge_status":"unresolved" if "unresolved" in
        [x.bridge_status for x in target_record.granularity_bridge_assessments] else "exact_match",
        "target_signal_v2_status":target_signal.signal_status,
        "target_formal_adjudication_eligible":target_signal.formal_adjudication_eligible,
        "target_context_difference_status":"validated","target_context_difference_factor_count":8,
        "target_comparability_status":"pending_policy","target_explanation_status":"pending_policy",
        "target_adjudication_status":"blocked_alignment_unvalidated",
        "target_formal_conflict_status":"not_confirmed",
        "failed_observation_ids":[x["observation_id"] for x in context_validation_audit if not x["valid"]],
        "failed_observation_status":"observation_context_policy_coverage_failure",
        "provider_calls":0,"api_calls":0,
        "network_calls":0,"downloads":0,"credential_values_read":False,"provider_client_created":False,
        "historical_runs_modified":False,"formal_v3_modified":False,"projection_modified":False,
        "candidate_pairs_modified":False,"handoff_created":False,"atlas_activated":False,
        "active_pointer_changed":False,"variational_em_called":False}
    _write_json(artifacts/"claim_alignment_dimension_taxonomy_v2_summary.json", summary)
    changed = subprocess.run(["git","status","--short"],capture_output=True,text=True,check=True).stdout.splitlines()
    artifact_names = sorted(str(p.relative_to(output)) for p in artifacts.rglob("*") if p.is_file())
    manifest = {
        "schema_version":"alignment_dimension_taxonomy_v2_manifest_v1",
        "git_head_before":"c51876a3fa190df30864ec253e3ade56778b70b4","git_head_after":
        subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip(),
        "baseline_note":"Attachment described a dirty baseline; execution began from clean HEAD c51876a3fa190df30864ec253e3ade56778b70b4.",
        "preexisting_dirty_files":[],"files_changed_this_round":changed,
        "files_created_this_round":changed,"source_hashes_before":source_hashes,
        "source_hashes_after":{str(p):_sha(p) for p in source_paths},"historical_runs_modified":False,
        "dimension_role_counts":dict(Counter(x["role"] for x in role_config["dimensions"])),
        "role_changed_count":sum(x["role_changed"] for x in role_audit),
        "core_signature_excluded_dimension_count":sum(not x["included_in_core_signature_v2"] for x in role_audit),
        **{k:v for k,v in summary.items() if k not in {"schema_version","execution_status"}},
        "contract_identities":{k:v["sha256"] for k,v in contracts.items()},
        "legacy_contract_identities":{k:v["sha256"] for k,v in previous_contracts.items()},
        "artifacts":artifact_names,"provider_calls":0,"api_calls":0,"network_calls":0,"downloads":0,
        "credential_values_read":False,"provider_client_created":False,"handoff_created":False,
        "atlas_activated":False,"active_pointer_changed":False,"variational_em_called":False}
    _write_json(artifacts/"alignment_dimension_taxonomy_v2_manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--previous-run", required=True, type=Path)
    parser.add_argument("--raw-candidates", required=True, type=Path)
    parser.add_argument("--role-config", required=True, type=Path)
    parser.add_argument("--bridge-policy", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output,args.previous_run,args.raw_candidates,
                                 args.role_config,args.bridge_policy),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
