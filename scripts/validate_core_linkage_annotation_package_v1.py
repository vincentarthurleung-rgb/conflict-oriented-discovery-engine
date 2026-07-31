#!/usr/bin/env python3
"""Self-contained package and response validator for annotation pilot v1."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


FORBIDDEN = {
    "candidate_answers", "candidate_answer_evidence", "candidate_score", "candidate_scores",
    "preferred_answer", "preferred_candidate", "readiness_diagnosis", "correct_answer",
    "human_answer", "gold_answer", "adjudication_result", "conflict", "comparability",
    "divergence_explanation", "formal_conflict", "hypothesis",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keys_recursive(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k).lower() for k in value} | set().union(*(keys_recursive(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(keys_recursive(v) for v in value), set())
    return set()


def assert_task(task: dict[str, Any], method: bool = False, repo_root: Path | None = None) -> None:
    required = {
        "task_id", "task_type", "observation_identity", "experiment_scope_identity",
        "source_envelope_v2_identity", "source_authority", "source_scope_completeness",
        "context", "evidence_catalog", "source_material", "allowed_labels",
        "abstain_allowed", "annotation_guideline_version", "canonical_payload_identity",
    }
    assert required <= task.keys()
    assert task["abstain_allowed"] is True
    assert not (keys_recursive(task) & FORBIDDEN)
    refs = {x["ref"] for x in task["evidence_catalog"]}
    assert refs and all(x.get("text") is not None for x in task["evidence_catalog"])
    for section in task["source_material"].values():
        if not isinstance(section, list):
            continue
        for item in section:
            ref = item.get("ref")
            if isinstance(ref, str) and ref.startswith("runs/"):
                root = repo_root or Path.cwd()
                assert (root / ref.split("#", 1)[0]).is_file(), f"dangling source ref: {ref}"
    if method:
        assert task["task_type"] == "measurement_method"
        assert task["endpoint_inference_prohibited"] is True
    else:
        assert task["task_type"] in {"comparator", "factor_application"}
        factors = task["factor_candidates"]
        ids = [x["factor_id"] for x in factors]
        assert ids and len(ids) == len(set(ids))
        assert all(re.fullmatch(r"experimental_factor_record_v1:[0-9a-f]{64}", x) for x in ids)
        assert set(task["measurement_identities"]) == {x["measurement_id"] for x in task["measurements"]}
        assert set(task["result_identities"]) == {x["observed_result_id"] for x in task["observed_results"]}


def csv_to_json(row: dict[str, str], method: bool) -> dict[str, Any]:
    list_fields = ["evidence_refs"] if method else ["selected_factor_ids", "evidence_refs"]
    nullable = ["specific_method_text", "selected_label", "evidence_quote", "confidence", "annotator_notes", "submitted_at"] if method else [
        "selected_label", "evidence_quote", "confidence", "abstention_reason", "annotator_notes", "submitted_at"
    ]
    out: dict[str, Any] = dict(row)
    for key in list_fields:
        out[key] = row[key].split("|") if row[key] else []
    for key in nullable:
        out[key] = row[key] if row[key] != "" else None
    if out.get("confidence") is not None:
        out["confidence"] = int(out["confidence"])
    return out


def json_to_csv(row: dict[str, Any], fields: list[str]) -> dict[str, str]:
    return {k: ("|".join(row[k]) if isinstance(row[k], list) else ("" if row.get(k) is None else str(row[k]))) for k in fields}


def validate_response(response: dict[str, Any], task: dict[str, Any]) -> None:
    evidence = {x["ref"] for x in task["evidence_catalog"]}
    assert set(response["evidence_refs"]) <= evidence, "Evidence ref does not exist in Source Packet"
    if task["task_type"] == "measurement_method":
        labels = {"method_not_reported", "source_insufficient", "cannot_determine"}
        assert response["method_granularity"] in {"specific_method", "assay_family", "semantic_level_only", "unresolved"}
        assert response["selected_label"] in labels | {None}
        assert not (response["specific_method_text"] and response["selected_label"])
        if response["selected_label"]:
            assert response["method_granularity"] == "unresolved"
        elif response["specific_method_text"]:
            assert response["evidence_refs"], "Reported method requires evidence"
        else:
            raise AssertionError("Method response requires text or an abstention label")
        return
    ids = {x["factor_id"] for x in task["factor_candidates"]}
    assert set(response["selected_factor_ids"]) <= ids
    assert not (response["selected_factor_ids"] and response["selected_label"])
    if response["selected_factor_ids"]:
        assert response["evidence_refs"], "Non-abstention answer requires evidence"
    if response["selected_label"]:
        assert response["abstention_reason"], "Abstention requires a reason"
    if response["selected_label"] == "source_insufficient":
        assert response["source_sufficiency"] == "insufficient"
    if response["selected_label"] == "no_comparator_reported":
        assert response["source_sufficiency"] != "insufficient"
    labels = ({"multiple_comparators", "no_comparator_reported", "source_insufficient", "cannot_determine"}
              if task["task_type"] == "comparator" else {"all_listed_factors", "none", "source_insufficient", "cannot_determine"})
    assert response["selected_label"] in labels | {None}


def validate_package(base: Path) -> None:
    repo_root = base.parents[2]
    core = jsonl(base / "manifests/canonical_core_tasks.jsonl")
    method = jsonl(base / "manifests/method_pilot_tasks.jsonl")
    assert len(core) == len({x["observation_identity"] for x in core}) == 8
    assert Counter(x["difficulty"] for x in core) == Counter({"easy": 4, "medium": 2, "hard": 2})
    assert Counter(x["task_type"] for x in core) == Counter({"comparator": 4, "factor_application": 4})
    assert len(method) == 10
    core_ids, method_ids = {x["task_id"] for x in core}, {x["task_id"] for x in method}
    assert not core_ids & method_ids
    for task in core: assert_task(task, repo_root=repo_root)
    for task in method: assert_task(task, True, repo_root=repo_root)
    task_sets = []
    for name in ["annotator_A", "annotator_B"]:
        manifest = load(base / name / "package_manifest.json")
        dirs = {x.parent.name for x in (base / name / "tasks").glob("*/task.json")}
        assert dirs == core_ids
        assert not (base / name / ("annotator_B" if name == "annotator_A" else "annotator_A")).exists()
        assert manifest["contains_other_annotator_material"] is False
        assert manifest["answers_prefilled"] is False
        expected_files_hash = hashlib.sha256(json.dumps([
            (str(path.relative_to(base / name)), sha(path))
            for path in sorted(x for x in (base / name).rglob("*") if x.is_file() and x.name != "package_manifest.json")
        ], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        assert manifest["package_files_sha256"] == expected_files_hash
        task_sets.append(dirs)
        for task_id in dirs:
            packaged = load(base / name / "tasks" / task_id / "task.json")
            canonical_task = next(x for x in core if x["task_id"] == task_id)
            assert packaged == canonical_task
            md = (base / name / "tasks" / task_id / "source_packet.md").read_text(encoding="utf-8")
            ht = (base / name / "tasks" / task_id / "source_packet.html").read_text(encoding="utf-8")
            assert packaged["canonical_payload_identity"] in ht
            assert packaged["task_id"] in md and packaged["task_id"] in ht
    assert task_sets[0] == task_sets[1]
    assert load(base / "annotator_A/package_manifest.json")["package_id"] != load(base / "annotator_B/package_manifest.json")["package_id"]
    for path in [base / "annotator_A/responses/core_responses_A.csv", base / "annotator_B/responses/core_responses_B.csv",
                 base / "method_pilot/responses/method_responses_template.csv", base / "manifests/canonical_core_tasks.csv"]:
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    for path, tasks, method_mode in [
        (base / "annotator_A/responses/core_responses_A.csv", core, False),
        (base / "annotator_B/responses/core_responses_B.csv", core, False),
        (base / "method_pilot/responses/method_responses_template.csv", method, True),
    ]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        by_id = {x["task_id"]: x for x in tasks}
        assert len(rows) == len(tasks)
        for row in rows:
            converted = csv_to_json(row, method_mode)
            assert json_to_csv(converted, list(row)) == row
            assert converted["task_id"] in by_id
    listed = {}
    for line in (base / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        checksum, rel = line.split("  ", 1); listed[rel] = checksum
    actual = {str(x.relative_to(base)): sha(x) for x in base.rglob("*") if x.is_file() and x.name != "checksums.sha256"}
    assert listed == actual
    text = "\n".join(str(x.relative_to(base)) for x in base.rglob("*"))
    assert not re.search(r"(?i)(credential|api[_-]?key|provider_payload|access[_-]?token|secret)", text)
    manifest = load(base / "package_manifest.json")
    assert manifest["historical_assets_modified"] is False
    assert manifest["historical_assets_hash_before"] == manifest["historical_assets_hash_after"]
    assert manifest["provider_calls"] == manifest["api_calls"] == manifest["network_calls"] == manifest["downloads"] == 0
    for schema_name in ["core_annotation_response_v1.schema.json", "method_annotation_response_v1.schema.json"]:
        schema = load(base / "schemas" / schema_name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        assert schema["type"] == "object" and schema["required"] and schema["properties"]
    print("package validation: passed")


def validate_csv(path: Path, base: Path) -> None:
    is_method = "method" in path.name
    tasks = jsonl(base / "manifests" / ("method_pilot_tasks.jsonl" if is_method else "canonical_core_tasks.jsonl"))
    by_id = {x["task_id"]: x for x in tasks}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            response = csv_to_json(raw, is_method)
            assert response["task_id"] in by_id
            validate_response(response, by_id[response["task_id"]])
    print("response validation: passed")


def main() -> None:
    here = Path(__file__).resolve()
    if here.parent.name == "validation":
        base = here.parent.parent
    else:
        base = Path("runs/20260726_core_linkage_human_annotation_pilot_packaging_v1_offline/annotation_pilot_v1").resolve()
    if len(sys.argv) > 1:
        validate_csv(Path(sys.argv[1]), base)
    else:
        validate_package(base)


if __name__ == "__main__":
    main()
