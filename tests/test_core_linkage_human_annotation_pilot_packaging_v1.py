from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/20260726_core_linkage_human_annotation_pilot_packaging_v1_offline/annotation_pilot_v1"


def load_module():
    path = ROOT / "scripts/validate_core_linkage_annotation_package_v1.py"
    spec = importlib.util.spec_from_file_location("pilot_validator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_builder():
    path = ROOT / "scripts/run_core_linkage_human_annotation_pilot_packaging_v1.py"
    spec = importlib.util.spec_from_file_location("pilot_builder", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_complete_package_validation():
    load_module().validate_package(BASE)


def test_response_semantics_and_round_trip():
    mod = load_module()
    task = json.loads(next((BASE / "annotator_A/tasks").glob("*/task.json")).read_text(encoding="utf-8"))
    factor_id = task["factor_candidates"][0]["factor_id"]
    evidence_ref = task["evidence_catalog"][0]["ref"]
    response = {
        "annotator_id": "test", "task_id": task["task_id"], "task_type": task["task_type"],
        "selected_factor_ids": [factor_id], "selected_label": None, "evidence_refs": [evidence_ref],
        "evidence_quote": "test quote", "confidence": 2, "source_sufficiency": "sufficient",
        "abstention_reason": None, "annotator_notes": None, "submitted_at": None,
    }
    mod.validate_response(response, task)
    row = mod.json_to_csv(response, list(response))
    assert mod.csv_to_json(row, False) == response


def test_invalid_ids_abstention_and_evidence_are_rejected():
    mod = load_module()
    task = json.loads(next((BASE / "annotator_A/tasks").glob("*/task.json")).read_text(encoding="utf-8"))
    base = {
        "annotator_id": "test", "task_id": task["task_id"], "task_type": task["task_type"],
        "selected_factor_ids": ["experimental_factor_record_v1:" + "0" * 64], "selected_label": None,
        "evidence_refs": [], "evidence_quote": None, "confidence": 1, "source_sufficiency": "sufficient",
        "abstention_reason": None, "annotator_notes": None, "submitted_at": None,
    }
    try:
        mod.validate_response(base, task)
        assert False, "invalid factor ID should fail"
    except AssertionError:
        pass
    base["selected_factor_ids"] = []
    base["selected_label"] = "source_insufficient"
    base["source_sufficiency"] = "uncertain"
    try:
        mod.validate_response(base, task)
        assert False, "source_insufficient must map to insufficient"
    except AssertionError:
        pass


def test_csv_templates_are_bom_and_unanswered():
    for path in [
        BASE / "annotator_A/responses/core_responses_A.csv",
        BASE / "annotator_B/responses/core_responses_B.csv",
        BASE / "method_pilot/responses/method_responses_template.csv",
    ]:
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert all(not row.get("selected_label") for row in rows)
        assert all(not row.get("evidence_quote") for row in rows)


def test_payload_identity_stable_and_selection_input_order_independent():
    builder = load_builder()
    tasks = [json.loads(x) for x in (BASE / "manifests/canonical_core_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    for task in tasks:
        claimed = task["canonical_payload_identity"]
        payload = dict(task)
        del payload["canonical_payload_identity"]
        assert claimed == builder.identity("core_annotation_task_payload_v1", payload)
    bundles = builder.read_jsonl(builder.manifest_artifact_by_schema(builder.SOURCE_RUN, "core_annotation_observation_bundle_v1"))
    selection = builder.read_json(builder.manifest_artifact_by_schema(builder.TRIAGE_RUN, "experimental_annotation_pilot_selection_v1"))
    forward, _ = builder.select_core_bundles(bundles, selection)
    reverse, _ = builder.select_core_bundles(list(reversed(bundles)), selection)
    assert [x["identity"] for x in forward] == [x["identity"] for x in reverse]
