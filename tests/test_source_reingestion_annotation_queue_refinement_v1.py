from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from code_engine.extraction_assets.experimental_core.refinement_v1 import (
    bundle_annotation_targets,
    inspect_local_xml,
    rebuild_envelope_v2,
    run_bounded_iterations,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260726_hif1a_source_reingestion_annotation_queue_refinement_v1_offline"
ART = RUN / "artifacts"
V3 = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline/artifacts"


def rows(name: str) -> list[dict]:
    return [json.loads(x) for x in (ART / name).read_text().splitlines() if x.strip()]


def value(name: str) -> dict:
    return json.loads((ART / name).read_text())


def validate_strict_schema(schema: dict, instance) -> None:
    expected = schema.get("type")
    if isinstance(expected, list):
        if instance is None:
            return
        non_null = [x for x in expected if x != "null"]
        if len(non_null) == 1:
            validate_strict_schema({**schema, "type": non_null[0]}, instance)
        return
    elif expected == "object":
        assert isinstance(instance, dict)
        assert set(schema["required"]) <= set(instance)
        assert schema["additionalProperties"] is False
        assert set(instance) <= set(schema["properties"])
        for key, child in schema["properties"].items():
            validate_strict_schema(child, instance[key])
        return
    elif expected == "array":
        assert isinstance(instance, list)
        for item in instance:
            validate_strict_schema(schema["items"], item)
        return
    elif expected == "string":
        assert isinstance(instance, str)
    elif expected == "boolean":
        assert isinstance(instance, bool)
    elif expected == "integer":
        assert isinstance(instance, int) and not isinstance(instance, bool)
    elif expected == "number":
        assert isinstance(instance, (int, float)) and not isinstance(instance, bool)


def test_offline_run_and_required_artifacts_exist():
    required = {
        "autonomous_iteration_ledger.jsonl", "autonomous_issue_inventory.jsonl",
        "local_source_asset_recoveries.jsonl", "source_asset_revisions_v2.jsonl",
        "source_resolution_envelopes_v2.jsonl", "core_source_gap_target_retriage.jsonl",
        "external_source_retrieval_candidates.jsonl",
        "core_annotation_observation_bundles.jsonl",
        "annotation_pending_readiness_reconciliation.json",
        "structured_core_source_gap_reconciliation.json",
        "measurement_method_enrichment_pool.jsonl",
        "measurement_method_enrichment_pilot.json",
        "machine_reuse_readiness_v4_candidates.jsonl",
        "experimental_core_remediation_requirements_v4.jsonl",
        "statistical_invariant_audit.json",
        "source_reingestion_annotation_queue_manifest.json",
    }
    assert required <= {p.name for p in ART.iterdir()}


def test_iteration_zero_is_scan_only_and_loop_is_bounded():
    ledger = rows("autonomous_iteration_ledger.jsonl")
    assert ledger[0]["iteration_id"] == 0
    assert ledger[0]["files_changed"] == []
    assert len(ledger) <= 6


def test_bounded_loop_stops_after_two_stagnant_rounds():
    records = [{
        "iteration_id": i, "files_changed": [], "metrics_before": {"x": 1},
        "metrics_after": {"x": 1}, "scientific_ambiguity_repaired": False,
    } for i in range(4)]
    assert len(run_bounded_iterations(records)) == 2


def test_bounded_loop_rejects_scientific_repair():
    with pytest.raises(ValueError, match="scientific ambiguity"):
        run_bounded_iterations([{
            "iteration_id": 0, "files_changed": [], "metrics_before": {},
            "metrics_after": {}, "scientific_ambiguity_repaired": True,
        }])


def test_bounded_loop_rejects_iteration_zero_mutation():
    with pytest.raises(ValueError, match="scan-only"):
        run_bounded_iterations([{
            "iteration_id": 0, "files_changed": ["x"], "metrics_before": {},
            "metrics_after": {}, "scientific_ambiguity_repaired": False,
        }])


def test_bioc_methods_results_and_figure_captions_are_indexed(tmp_path):
    xml = tmp_path / "article.xml"
    xml.write_text(
        "<collection><document>"
        "<passage><infon key='section_type'>METHODS</infon><infon key='type'>paragraph</infon>"
        "<text>Assay method.</text></passage>"
        "<passage><infon key='section_type'>RESULTS</infon><infon key='type'>paragraph</infon>"
        "<text>Result sentence.</text></passage>"
        "<passage><infon key='section_type'>FIG</infon><infon key='type'>fig_caption</infon>"
        "<text>Figure caption.</text></passage></document></collection>"
    )
    indexed = inspect_local_xml(xml, relative_to=tmp_path)
    assert indexed["methods"] and indexed["results"] and indexed["figures"]


def test_jats_methods_and_table_captions_are_indexed(tmp_path):
    xml = tmp_path / "article.xml"
    xml.write_text(
        "<article><body><sec><title>Methods</title><p>Assay.</p></sec>"
        "<sec><title>Results</title><p>Result.</p></sec>"
        "<table-wrap><caption>Table caption.</caption></table-wrap></body></article>"
    )
    indexed = inspect_local_xml(xml, relative_to=tmp_path)
    assert indexed["methods"] and indexed["results"] and indexed["tables"]


def test_all_twelve_source_blocks_are_classified_from_local_xml():
    recoveries = rows("local_source_asset_recoveries.jsonl")
    assert len(recoveries) == 12
    assert all(x["xml_availability"] for x in recoveries)
    assert all(x["recovery_status"] == "locally_recovered" for x in recoveries)


def test_recovery_never_authorizes_external_execution():
    assert all(
        not x["execution_authorized"] and not x["network_authorized"]
        for x in rows("local_source_asset_recoveries.jsonl")
    )


def test_source_revision_is_immutable_and_separates_authorities():
    revisions = rows("source_asset_revisions_v2.jsonl")
    assert len(revisions) == 12
    assert all(x["immutable"] for x in revisions)
    assert all(x["source_authority"] == "authoritative_current_fulltext" for x in revisions)
    assert all(x["historical_provider_input_authority"] != "authoritative" for x in revisions)


def test_source_revision_identity_is_stable():
    revisions = rows("source_asset_revisions_v2.jsonl")
    assert len({x["identity"] for x in revisions}) == len(revisions)
    assert all(x["identity"] == x["source_asset_revision_id"] for x in revisions)


def test_envelope_v2_count_and_component_scopes():
    envelopes = rows("source_resolution_envelopes_v2.jsonl")
    assert len(envelopes) == 361
    assert all(set(x["component_specific_scope"]) == {
        "comparator", "factor_application", "measurement_method"
    } for x in envelopes)


def test_envelope_v2_retains_methods_and_caption_refs():
    recovered = [x for x in rows("source_resolution_envelopes_v2.jsonl") if x["local_recovery_applied"]]
    assert recovered
    assert all(x["methods_text_refs"] for x in recovered)
    assert all(x["figure_caption_refs"] or x["table_caption_refs"] for x in recovered)


def test_envelope_v1_is_not_modified():
    manifest = value("source_reingestion_annotation_queue_manifest.json")
    assert manifest["historical_assets_unchanged"]
    assert manifest["protected_hashes_before"] == manifest["protected_hashes_after"]


def test_only_the_prior_fifty_core_source_gap_targets_are_retriaged():
    retriage = rows("core_source_gap_target_retriage.jsonl")
    assert len(retriage) == 50
    assert len({x["target_identity"] for x in retriage}) == 50


def test_source_expansion_does_not_auto_resolve_scientific_linkage():
    retriage = rows("core_source_gap_target_retriage.jsonl")
    assert {x["status_after"] for x in retriage} == {"unresolved"}
    assert not any(x["authority_changed"] for x in retriage)
    assert not any(x["annotation_target_required"] for x in retriage)


def test_external_absence_only_creates_non_authorized_candidates():
    candidates = rows("external_source_retrieval_candidates.jsonl")
    assert all(not x["execution_authorized"] and not x["network_authorized"] for x in candidates)


def test_annotation_targets_are_bundled_by_exact_observation():
    bundles = rows("core_annotation_observation_bundles.jsonl")
    assert len(bundles) == len({x["observation_identity"] for x in bundles})
    assert sum(x["target_count"] for x in bundles) == 39


def test_bundle_does_not_copy_primary_source_text_or_create_authority():
    forbidden = {"primary_text", "scientific_conclusion", "conflict", "comparability", "explanation"}
    for bundle in rows("core_annotation_observation_bundles.jsonl"):
        assert not forbidden.intersection(bundle)
        assert not bundle["scientific_authority"]
        assert bundle["abstain_allowed"]


def test_bundle_reports_actual_39_target_39_observation_membership():
    summary = value("core_annotation_bundle_summary.json")
    assert summary["core_annotation_target_count"] == 39
    assert summary["unique_core_annotation_observation_count"] == 39
    assert summary["multi_task_observation_count"] == 0


def test_37_38_39_denominators_are_reconciled_per_id():
    reconciliation = value("annotation_pending_readiness_reconciliation.json")
    assert {k: len(v) for k, v in reconciliation["sets"].items()} == {
        "core_remediation_v3": 37, "core_bundle_v1": 39, "readiness_v3": 38,
    }
    assert reconciliation["difference_reason_per_id"]


def test_50_7_59_source_gap_denominators_are_reconciled_per_id():
    reconciliation = value("structured_core_source_gap_reconciliation.json")
    sets = reconciliation["sets"]
    assert len(sets["source_reingestion_v3"]) == 50
    assert len(sets["source_not_reported_v3"]) == 7
    assert len(sets["readiness_source_gap_v3"]) == 59
    assert set(sets["source_reingestion_v3"]).isdisjoint(sets["source_not_reported_v3"])


def test_method_pool_is_outside_core_queue_and_conserved():
    pool = rows("measurement_method_enrichment_pool.jsonl")
    pilot = value("measurement_method_enrichment_pilot.json")
    backlog = rows("measurement_method_optional_backlog.jsonl")
    assert len(pool) == 240
    assert all(not x["core_queue"] for x in pool)
    assert 9 <= pilot["selected_count"] <= 18
    assert pilot["selected_count"] + len(backlog) == 240


def test_unavailable_method_pilot_coverage_is_explicit_not_invented():
    pilot = value("measurement_method_enrichment_pilot.json")
    assert set(pilot["unavailable_coverage_dimensions"]) == {
        name for name, covered in pilot["coverage_status"].items() if not covered
    }
    if pilot["unavailable_coverage_dimensions"]:
        assert pilot["unavailable_coverage_reason"]


def test_readiness_v4_uniquely_classifies_all_observations():
    records = rows("machine_reuse_readiness_v4_candidates.jsonl")
    assert len(records) == 418
    assert len({x["observation_identity"] for x in records}) == 418
    assert all(x["candidate_only"] and not x["active_v3_replaced"] for x in records)


def test_method_enrichment_does_not_become_core_pending():
    records = rows("machine_reuse_readiness_v4_candidates.jsonl")
    assert all(not x["method_enrichment_core_blocking"] for x in records)


@pytest.mark.parametrize(
    "field, expected",
    [
        ("provider_required_count", 0), ("provider_candidate_count", 0),
        ("provider_calls", 0), ("api_calls", 0), ("network_calls", 0),
        ("downloads", 0), ("credential_values_read", False),
        ("provider_client_created", False), ("human_annotations_executed", 0),
        ("human_gold_created", False), ("historical_runs_modified", False),
        ("candidate_pairs_modified", False), ("formal_conflict_count_before", 0),
        ("formal_conflict_count_after", 0),
    ],
)
def test_safety_zeroes(field, expected):
    assert value("source_reingestion_annotation_queue_safety_audit.json")[field] == expected


def test_remediation_v4_never_authorizes_provider_network_human_or_gold():
    for record in rows("experimental_core_remediation_requirements_v4.jsonl"):
        assert not record["provider_required"]
        assert not record["provider_candidate"]
        assert not record["execution_authorized"]
        assert not record["network_authorized"]
        assert not record["human_annotation_executed"]
        assert not record["human_gold"]


def test_statistical_invariants_all_pass():
    audit = value("statistical_invariant_audit.json")
    assert audit["all_passed"]
    assert all(v for k, v in audit.items() if k != "all_passed")


def test_schema_snapshots_are_strict_and_self_valid():
    for path in (RUN / "schemas").glob("*.schema.json"):
        schema = json.loads(path.read_text())
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["type"] == "object"
        assert set(schema["required"]) == set(schema["properties"])
        assert schema["additionalProperties"] is False


def test_artifacts_validate_against_representative_schemas():
    pairs = [
        ("local_source_asset_recovery_v1.schema.json", "local_source_asset_recoveries.jsonl"),
        ("source_resolution_asset_revision_v2.schema.json", "source_asset_revisions_v2.jsonl"),
        ("source_grounded_experimental_resolution_envelope_v2.schema.json",
         "source_resolution_envelopes_v2.jsonl"),
        ("core_annotation_observation_bundle_v1.schema.json",
         "core_annotation_observation_bundles.jsonl"),
        ("measurement_method_enrichment_pool_v1.schema.json",
         "measurement_method_enrichment_pool.jsonl"),
        ("experimental_observation_machine_reuse_readiness_v4_candidate.schema.json",
         "machine_reuse_readiness_v4_candidates.jsonl"),
        ("experimental_core_remediation_requirement_v4.schema.json",
         "experimental_core_remediation_requirements_v4.jsonl"),
    ]
    for schema_name, artifact_name in pairs:
        schema = json.loads((RUN / "schemas" / schema_name).read_text())
        for record in rows(artifact_name):
            validate_strict_schema(schema, record)


def test_contract_identity_snapshots_recompute():
    for path in (RUN / "contract_identities").glob("*.json"):
        record = json.loads(path.read_text())
        digest = hashlib.sha256(json.dumps(
            record["canonical_payload"], sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        assert record["identity_match"]
        assert record["identity_sha256"] == digest == record["recomputed_sha256"]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("weak_3ca_source_reingestion_audit.json", ("context_entry_status", "ready")),
        ("weak_256_source_reingestion_audit.json",
         ("context_entry_status", "blocked_context_b_unavailable")),
        ("ebd5_source_reingestion_audit.json",
         ("candidate_qualification_status", "blocked_alignment")),
        ("context_17b_source_reingestion_audit.json",
         ("status", "fail_closed_policy_coverage_failure")),
        ("context_41f_source_reingestion_audit.json",
         ("status", "fail_closed_policy_coverage_failure")),
    ],
)
def test_existing_scientific_state_is_preserved(name, expected):
    audit = value(name)
    assert audit[expected[0]] == expected[1]
    assert audit["historical_state_unchanged"]


def test_docs_and_adr_exist_and_adr_is_accepted():
    paths = [
        ROOT / "docs/architecture/source_reingestion_and_core_annotation_queue_refinement_v1.md",
        ROOT / "docs/contracts/local_source_asset_recovery_v1.md",
        ROOT / "docs/contracts/source_grounded_resolution_envelope_v2.md",
        ROOT / "docs/contracts/core_annotation_observation_bundle_v1.md",
        ROOT / "docs/contracts/measurement_method_enrichment_pool_v1.md",
        ROOT / "docs/contracts/experimental_observation_machine_reuse_readiness_v4_candidate.md",
        ROOT / "docs/contracts/bounded_autonomous_repair_loop_v1.md",
        ROOT / "docs/adr/ADR-bounded-autonomous-repair-with-scientific-fail-closed-boundary-v1.md",
    ]
    assert all(path.is_file() for path in paths)
    assert "Status: Accepted" in paths[-1].read_text()
