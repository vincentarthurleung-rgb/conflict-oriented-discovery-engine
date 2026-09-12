#!/usr/bin/env python3
"""Create a minimal physical-copy workspace for fresh PASS B evaluators."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "pass_b_primary_evaluator_workspace"
AUDIT_RUN = ROOT / "runs/20260912_search_plan_v22_heldout_v1_pass_b_primary_evaluator_workspace_audit_offline"
AUDIT_PATH = AUDIT_RUN / "workspace_exposure_audit.json"
PROTOCOL_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
CORPUS_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline"
BLINDED_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_blinded_adjudication_views_offline"
PASS_A_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_pass_a_acquisition_adjudication_freeze_offline"
RUBRIC = Path("/home/vincent/.codex/attachments/5e47ea3f-a0a0-4bbe-aa09-6774e40ff675/pasted-text.txt")

HASHES = {
    "heldout_v1_protocol_sha256": "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127",
    "heldout_v1_review_corpus_sha256": "f2cfe4f1657667a66b18d3123e82d76cc4bf1af9da2863ac6b10f9efc3d092fb",
    "heldout_v1_blinded_adjudication_views_sha256": "2940e058b63df5dc02fb6ed07d970f651a74f9a000c9b6784affe3e6fac1dc0e",
    "heldout_v1_pass_a_acquisition_adjudications_sha256": "333fc6f20bab33b21387f2453905c2c9c11d92797177688a9e75cc2bab2e52df",
}
WORKSPACE_PURPOSE = "primary_blinded_pass_b_relevance_adjudication"
REVIEWER_TYPE = "model_retrieval_adjudicator"
BATCH_NAMES = [f"heldout_relevance_blind_batch_{index:02d}.md" for index in range(1, 6)]
CONTENT_NAMES = ["pass_b_evaluator_instruction.md", *BATCH_NAMES]
WORKSPACE_NAMES = {*CONTENT_NAMES, "evaluator_workspace_manifest.json"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def pretty(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_aggregate_root(base: Path, field: str, expected: str) -> dict:
    manifest = read_json(base / "freeze_manifest.json")
    components = []
    for row in manifest["components"]:
        actual = sha(base / row["path"])
        require(actual == row["sha256"], f"Frozen component hash mismatch: {base / row['path']}")
        components.append((row["path"], actual))
    actual = digest(canonical(components))
    require(actual == manifest[field] == expected, f"Frozen root mismatch: {field}")
    return {"field": field, "expected": expected, "actual": actual, "match": True}


def verify_pass_a_root() -> dict:
    manifest = read_json(PASS_A_RUN / "freeze_manifest.json")
    actual = sha(PASS_A_RUN / manifest["corpus"])
    expected = HASHES["heldout_v1_pass_a_acquisition_adjudications_sha256"]
    require(actual == manifest["heldout_v1_pass_a_acquisition_adjudications_sha256"] == expected,
            "Frozen PASS A root mismatch")
    return {"field": "heldout_v1_pass_a_acquisition_adjudications_sha256",
            "expected": expected, "actual": actual, "match": True}


def protected_state() -> dict[str, str]:
    paths = [path for base in (PROTOCOL_RUN, CORPUS_RUN, BLINDED_RUN, PASS_A_RUN)
             for path in sorted(base.rglob("*")) if path.is_file()]
    paths.append(RUBRIC)
    return {str(path): sha(path) for path in paths}


def packet_sections(markdown: str) -> list[tuple[str, str]]:
    parts = re.split(r"^### Packet (\S+)\n", markdown, flags=re.MULTILINE)
    return list(zip(parts[1::2], parts[2::2]))


def validate_batch_content(name: str, data: bytes) -> dict:
    text = data.decode("utf-8")
    sections = packet_sections(text)
    require(len(sections) == 14, f"{name} does not contain exactly 14 packets")
    prefilled_relevance = 0
    for packet_id, body in sections:
        require("\nADJUDICATION\n" in body, f"Missing adjudication form: {packet_id}")
        form = body.rsplit("\nADJUDICATION\n", 1)[1]
        for line in form.strip().splitlines():
            require(re.fullmatch(r"[a-z_]+:", line) is not None,
                    f"Prefilled or malformed PASS B adjudication field: {packet_id}")
            if line.startswith("relevance_state:") and line != "relevance_state:":
                prefilled_relevance += 1
    structural_forbidden = {
        "tier": bool(re.search(r"^Tier:", text, flags=re.MULTILINE)),
        "gate": "pre_acquisition_gate_states" in text or bool(re.search(r"^Why acquired:", text, flags=re.MULTILINE)),
        "metadata_depth": bool(re.search(r"^Metadata depth:", text, flags=re.MULTILINE)),
        "acquisition_label": bool(re.search(r"^acquisition_decision:\s*\S", text, flags=re.MULTILINE)),
        "unblinded_packet": "frozen_neutral_review_packets.jsonl" in text,
        "retrieval_performance": bool(re.search(r"^(Tier A candidate total|Tier B candidate total|metadata total):",
                                                  text, flags=re.MULTILINE | re.IGNORECASE)),
        "markdown_hidden_artifact_link": bool(re.search(r"\]\((?:/|\.\.?/|runs/)[^)]+\)", text)),
    }
    require(not any(structural_forbidden.values()), f"Forbidden exposure in {name}: {structural_forbidden}")
    return {
        "path": name,
        "packet_ids": [packet_id for packet_id, _ in sections],
        "packet_count": len(sections),
        "prefilled_relevance_labels": prefilled_relevance,
        "structural_forbidden_exposure": structural_forbidden,
    }


def build_manifest(content: dict[str, bytes], packet_ids: list[str]) -> tuple[bytes, str]:
    rows = [{"path": name, "sha256": digest(content[name]), "sha256_scope": "exact_file_bytes"}
            for name in CONTENT_NAMES]
    self_row = {
        "path": "evaluator_workspace_manifest.json",
        "sha256": None,
        "sha256_scope": "canonical manifest payload with this sha256 value set to null",
    }
    manifest = {
        "workspace_purpose": WORKSPACE_PURPOSE,
        "reviewer_type": REVIEWER_TYPE,
        "upstream_frozen_hashes": HASHES,
        "packet_count": len(packet_ids),
        "unique_packet_count": len(set(packet_ids)),
        "batch_count": 5,
        "batch_size": 14,
        "files": [*rows, self_row],
        "physical_copies_only": True,
        "symlinks_present": False,
        "source_blind_batches_byte_identical": True,
        "evaluator_facing_repository_links_added": False,
        "manifest_self_hash_convention": (
            "A file cannot contain its own exact byte hash without self-reference. "
            "The manifest entry binds its canonical payload with that entry null; "
            "the external workspace_exposure_audit.json records the final manifest file hash."
        ),
    }
    self_hash = digest(canonical(manifest))
    manifest["files"][-1]["sha256"] = self_hash
    return pretty(manifest), self_hash


def generate() -> tuple[dict[str, bytes], bytes]:
    roots = [
        verify_aggregate_root(PROTOCOL_RUN, "heldout_v1_protocol_sha256",
                              HASHES["heldout_v1_protocol_sha256"]),
        verify_aggregate_root(CORPUS_RUN, "heldout_v1_review_corpus_sha256",
                              HASHES["heldout_v1_review_corpus_sha256"]),
        verify_aggregate_root(BLINDED_RUN, "heldout_v1_blinded_adjudication_views_sha256",
                              HASHES["heldout_v1_blinded_adjudication_views_sha256"]),
        verify_pass_a_root(),
    ]
    before = protected_state()
    content = {"pass_b_evaluator_instruction.md": RUBRIC.read_bytes()}
    source_hashes = {}
    batch_audits = []
    packet_ids = []
    for name in BATCH_NAMES:
        source = BLINDED_RUN / name
        data = source.read_bytes()
        content[name] = data
        source_hashes[name] = sha(source)
        audit = validate_batch_content(name, data)
        batch_audits.append(audit)
        packet_ids.extend(audit["packet_ids"])
    require(len(packet_ids) == len(set(packet_ids)) == 70, "PASS B packet membership is not 70 unique IDs")
    manifest_bytes, manifest_payload_hash = build_manifest(content, packet_ids)
    content["evaluator_workspace_manifest.json"] = manifest_bytes
    after = protected_state()
    require(before == after, "Frozen or rubric source changed during workspace construction")

    actual_hashes = {name: digest(data) for name, data in content.items()}
    filename_exposure = {
        "unblinded_review_batches": any(re.fullmatch(r"heldout_review_batch_.*\.md", name) for name in content),
        "pass_a_material": any("acquisition_blind_batch" in name or "pass_a" in name.lower() for name in content),
        "gate_material": any("gate" in name.lower() for name in content),
        "metadata_depth_material": any("metadata" in name.lower() and "depth" in name.lower() for name in content),
        "metrics_material": any("metric" in name.lower() or "performance" in name.lower() for name in content),
        "unblinded_packet_files": any("neutral_review_packets" in name for name in content),
    }
    require(not any(filename_exposure.values()), f"Forbidden workspace filename: {filename_exposure}")
    audit = {
        "status": "PASS",
        "workspace_path": str(WORKSPACE),
        "workspace_contains_only_required_files": set(content) == WORKSPACE_NAMES,
        "workspace_file_count": len(content),
        "workspace_files": [{"path": name, "sha256": actual_hashes[name]}
                            for name in sorted(content)],
        "manifest_canonical_self_payload_sha256": manifest_payload_hash,
        "manifest_actual_file_sha256": actual_hashes["evaluator_workspace_manifest.json"],
        "root_verification": roots,
        "packet_count": len(packet_ids),
        "unique_packet_count": len(set(packet_ids)),
        "batch_count": 5,
        "batch_size": 14,
        "batch_audits": batch_audits,
        "source_batch_sha256": source_hashes,
        "workspace_batch_sha256": {name: actual_hashes[name] for name in BATCH_NAMES},
        "source_blind_batches_byte_identical": all(source_hashes[name] == actual_hashes[name]
                                                    for name in BATCH_NAMES),
        "instruction_byte_identical_to_frozen_pass_b_rubric": (
            actual_hashes["pass_b_evaluator_instruction.md"] == sha(RUBRIC)
        ),
        "symlinks_present": False,
        "unblinded_review_batches_present": False,
        "pass_a_material_present": False,
        "tier_material_present": False,
        "gate_material_present": False,
        "metadata_depth_material_present": False,
        "retrieval_performance_summaries_present": False,
        "calibration_performance_present": False,
        "metrics_present": False,
        "unblinded_packet_files_present": False,
        "prefilled_relevance_labels": sum(row["prefilled_relevance_labels"] for row in batch_audits),
        "prefilled_acquisition_labels": 0,
        "exposure_scan_scope": (
            "Evaluator batch filenames, structural field labels, adjudication forms, and links. "
            "Rubric prohibition text and ordinary source-paper wording are not treated as exposed artifacts."
        ),
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "adjudication_calls": 0,
        "metrics_calculated": False,
        "frozen_artifacts_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
    }
    require(audit["workspace_contains_only_required_files"], "Workspace content policy failed")
    require(audit["source_blind_batches_byte_identical"], "Batch byte identity failed")
    require(audit["prefilled_relevance_labels"] == audit["prefilled_acquisition_labels"] == 0,
            "A packet contains a prefilled label")
    return content, pretty(audit)


def main() -> None:
    content, audit_bytes = generate()
    if WORKSPACE.exists():
        require(WORKSPACE.is_dir() and not WORKSPACE.is_symlink(), "Workspace is not a physical directory")
        require({path.name for path in WORKSPACE.iterdir()} == set(content),
                "Existing workspace has unexpected files; refusing to modify it")
        require(all(not path.is_symlink() for path in WORKSPACE.iterdir()), "Workspace contains a symlink")
        require(all((WORKSPACE / name).read_bytes() == data for name, data in content.items()),
                "Existing workspace differs; refusing to overwrite")
    else:
        WORKSPACE.mkdir()
        for name, data in content.items():
            with (WORKSPACE / name).open("xb") as handle:
                handle.write(data)
    if AUDIT_PATH.exists():
        require(AUDIT_PATH.read_bytes() == audit_bytes, "Existing exposure audit differs; refusing to overwrite")
    else:
        AUDIT_RUN.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("xb") as handle:
            handle.write(audit_bytes)
    print(audit_bytes.decode("utf-8"))


if __name__ == "__main__":
    main()
