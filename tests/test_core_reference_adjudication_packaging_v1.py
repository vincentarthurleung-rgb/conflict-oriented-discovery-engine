from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260816_core_reference_adjudication_packaging_v1_offline"
PACK = RUN / "reference_adjudication_pack_v1"
BLIND = PACK / "blind_reference_pack"
ADMIN = PACK / "admin_system_metadata_pack"
TRIAGE = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def blind_tasks():
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((BLIND / "tasks").glob("*/task.json"))]


def admin_tasks():
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ADMIN / "tasks").glob("*/task.json"))]


def module():
    path = ROOT / "scripts/run_core_reference_adjudication_packaging_v1.py"
    spec = importlib.util.spec_from_file_location("core_reference_packaging", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def test_real_inventory_is_scanned_not_hardcoded():
    inventory = json.loads((PACK / "manifests/core_reference_task_inventory.json").read_text())
    comparator = jsonl(TRIAGE / "comparator_annotation_targets.jsonl")
    factor = jsonl(TRIAGE / "factor_measurement_annotation_targets.jsonl")
    assert inventory["task_count"] == len(comparator) + len(factor) == len(blind_tasks())
    assert inventory["task_type_counts"] == {"comparator": len(comparator), "factor_application": len(factor)}
    assert inventory["task_count_hardcoded"] is False


def test_blind_pack_has_no_role_assignment_or_arm_metadata():
    text = "\n".join(path.read_text(encoding="utf-8") for path in BLIND.rglob("*") if path.is_file())
    for forbidden in ('"role": "control"', '"role": "comparator"', '"role": "baseline"',
                      "control_arm_raw", "comparison_arm_raw", "experimental_design_raw"):
        assert forbidden not in text


def test_blind_tasks_have_no_system_or_previous_answer_fields():
    forbidden = module().BLIND_FORBIDDEN_KEYS | module().TASK_ANSWER_KEYS
    for task in blind_tasks():
        assert not ({key for _, key in module().walk_keys(task)} & forbidden)


def test_comparator_question_selects_only_reference_arm():
    tasks = [task for task in blind_tasks() if task["task_type"] == "comparator"]
    assert tasks
    assert all("reference arm against which" in task["question"] for task in tasks)
    assert all("Do not select the experimental arm" in task["question"] for task in tasks)


def test_both_task_types_allow_candidate_set_incomplete():
    by_type = {task["task_type"]: task["allowed_statuses"] for task in blind_tasks()}
    assert "candidate_set_incomplete" in by_type["comparator"]
    assert "candidate_set_incomplete" in by_type["factor_application"]


def test_admin_pack_preserves_historical_roles_and_is_separate():
    tasks = admin_tasks()
    assert all(task["historical_roles"] for task in tasks)
    assert any(row.get("role") for task in tasks for row in task["historical_roles"])
    assert not (BLIND / "admin_system_metadata_pack").exists()
    assert not (ADMIN / "blind_reference_pack").exists()


def test_blind_and_admin_identity_sets_match_exactly():
    blind = {(x["task_id"], x["observation_identity"]) for x in blind_tasks()}
    admin = {(x["task_id"], x["observation_identity"]) for x in admin_tasks()}
    assert blind == admin


def test_factor_measurement_result_and_observation_ids_are_real():
    factors = {x["factor_id"] for x in jsonl(CORE / "experimental_factor_records.jsonl")}
    measurements = {x["measurement_id"] for x in jsonl(CORE / "measurement_records.jsonl")}
    results = {x["observed_result_id"] for x in jsonl(CORE / "observed_result_records.jsonl")}
    observations = {x["source_observation_identity"] for x in jsonl(CORE / "structured_experimental_observation_revisions.jsonl")}
    for task in blind_tasks():
        assert {x["factor_id"] for x in task["factor_candidates"]} <= factors
        assert task["measurement"]["measurement_id"] in measurements
        assert task["observed_result"]["observed_result_id"] in results
        assert task["observation_identity"] in observations


def test_evidence_refs_resolve_to_catalog():
    for task in blind_tasks():
        catalog = {x["ref"] for x in task["evidence_catalog"]}
        refs = {ref for row in task["factor_candidates"] for ref in row["evidence_anchor_ids"]}
        refs.update(task["measurement"]["evidence_anchor_ids"])
        refs.update(task["observed_result"]["evidence_anchor_ids"])
        assert refs <= catalog


def test_candidate_order_is_preserved_from_current_targets():
    targets = jsonl(TRIAGE / "comparator_annotation_targets.jsonl") + jsonl(TRIAGE / "factor_measurement_annotation_targets.jsonl")
    task_module = module()
    pilot = jsonl(task_module.PILOT_IDS)
    pilot_ids = {(x["observation_identity"], x["task_type"]): x["task_id"] for x in pilot if x["task_type"] in task_module.ALLOWED}
    expected = {task_module.stable_task_id(target, pilot_ids): target["factor_candidate_ids"] for target in targets}
    assert all([x["factor_id"] for x in task["factor_candidates"]] == expected[task["task_id"]] for task in blind_tasks())


def test_json_and_markdown_share_canonical_payload():
    task_module = module()
    for task in blind_tasks():
        assert task["identity_match"] is True
        assert task["identity_sha256"] == task_module.payload_hash(task) == task["recomputed_sha256"]
        packet = BLIND / "tasks" / task["task_id"] / "source_packet.md"
        assert packet.read_text(encoding="utf-8") == task_module.render_markdown(task)


def test_missing_source_sections_are_explicit():
    for task in blind_tasks():
        for value in task["source_material"].values():
            if isinstance(value, list):
                assert value
                assert all(entry["text"] for entry in value)
            else:
                assert value
    assert any(entry["text"] == "not_available" for task in blind_tasks()
               for value in task["source_material"].values() if isinstance(value, list) for entry in value)


def test_source_refs_point_to_existing_local_files():
    for task in blind_tasks():
        for ref in task["source_material_refs"]:
            assert (ROOT / ref.split("#", 1)[0]).is_file()


def test_response_schema_supports_invalid_tasks_and_upstream_errors():
    schema = json.loads((PACK / "schemas/reference_adjudication_response_v1.schema.json").read_text())
    validity = schema["properties"]["task_validity"]["enum"]
    errors = schema["properties"]["upstream_error_type"]["enum"]
    assert {"candidate_set_incomplete", "candidate_set_wrong", "source_packet_inadequate",
            "observation_structure_wrong", "task_semantics_wrong"} <= set(validity)
    assert {"reference_arm_missing", "candidate_generation_error", "source_packet_scope_error"} <= set(errors)
    assert schema["title"] == "source_grounded_reference_adjudication_v1"


def test_blind_package_has_only_two_files_per_task_and_no_html_or_response_template():
    for directory in (BLIND / "tasks").iterdir():
        assert {x.name for x in directory.iterdir()} == {"task.json", "source_packet.md"}


def test_validation_reports_all_pass():
    expected = ["blindness_validation.json", "reference_integrity_validation.json",
                "source_ref_validation.json", "canonical_payload_validation.json",
                "historical_asset_protection_validation.json"]
    for name in expected:
        report = json.loads((PACK / "validation" / name).read_text())
        assert report.get("status", report.get("blind_pack_status")) == "passed"


def test_candidate_completeness_is_intentionally_not_checked_or_repaired():
    report = json.loads((PACK / "validation/reference_integrity_validation.json").read_text())
    manifest = json.loads((PACK / "manifests/blind_pack_manifest.json").read_text())
    assert report["candidate_completeness_checked"] is False
    assert report["candidate_completeness_deferred_to"] == "source_grounded_reference_adjudication_v1"
    assert manifest["candidate_set_auto_corrected"] is False


def test_historical_assets_unchanged_and_external_calls_zero():
    report = json.loads((PACK / "validation/historical_asset_protection_validation.json").read_text())
    assert report["protected_hashes_before"] == report["protected_hashes_after"]
    assert report["historical_assets_modified"] is False
    assert report["preexisting_tracked_diff_preserved"] is True
    assert all(report[key] == 0 for key in ("provider_calls", "api_calls", "network_calls", "downloads", "human_annotation"))
    assert report["gold_created"] is False


def test_builder_has_no_network_or_provider_client_imports_and_does_not_read_response_dirs():
    text = (ROOT / "scripts/run_core_reference_adjudication_packaging_v1.py").read_text()
    assert all(token not in text for token in ("import requests", "import urllib", "import httpx", "import socket"))
    assert "annotator_A/responses" not in text and "annotator_B/responses" not in text


def test_zip_files_are_valid_separate_and_checksums_match():
    blind_zip = RUN / "core_reference_blind_pack_v1.zip"
    admin_zip = RUN / "core_reference_admin_metadata_pack_v1.zip"
    with zipfile.ZipFile(blind_zip) as archive:
        names = archive.namelist()
        assert names and all(name.startswith("blind_reference_pack/") for name in names)
        assert not any("admin_system_metadata" in name for name in names)
    with zipfile.ZipFile(admin_zip) as archive:
        names = archive.namelist()
        assert names and all(name.startswith("admin_system_metadata_pack/") for name in names)
        assert not any("blind_reference_pack" in name for name in names)
    checksums = (PACK / "checksums.sha256").read_text().splitlines()
    listed = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in checksums}
    for path in (blind_zip, admin_zip):
        assert listed[path.relative_to(RUN).as_posix()] == hashlib.sha256(path.read_bytes()).hexdigest()

