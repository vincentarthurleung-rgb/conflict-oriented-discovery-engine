"""Read-only audit of current System A handoffs for the Atlas v2 contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.integration.atlas_handoff import build_handoff_manifest, sha256_file


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())


def audit(*, runs_root: Path, projection_root: Path) -> dict:
    registry = _json(projection_root / "current_projection.json")
    projection = _json(projection_root / registry["projection_relative_path"] / "projection_manifest.json")
    rows = []
    for source in projection.get("source_manifests", []):
        run = runs_root / source["source_run_id"]
        handoff = build_handoff_manifest(run, runs_root=runs_root)
        capability = handoff["capabilities"]
        lineage = handoff.get("lineage") or {}
        l1 = runs_root / str(lineage.get("fulltext_l1_run") or "")
        chunks = l1 / "artifacts/l35_fulltext_discovery_selected_chunks.jsonl"
        rows.append({
            "case_id": handoff["case_id"],
            "source_run_id": handoff["source_run_id"],
            "handoff_schema_version": _json(run / "artifacts/atlas_handoff_manifest.json").get("schema_version"),
            "fulltext_claims": capability["fulltext_l1"]["record_count"],
            "reasoning_records": capability["reasoning_trace"]["record_count"],
            "reasoning_steps": sum(len(row.get("reasoning_steps") or []) for row in _rows(run, handoff, "fulltext_reasoning_traces")),
            "usable_reasoning": capability["reasoning_trace"]["usable_record_count"],
            "reasoning_coverage": capability["reasoning_trace"]["coverage"],
            "context_records": capability["context_consolidation"]["record_count"],
            "nonempty_context": capability["context_consolidation"]["nonempty_record_count"],
            "context_coverage": capability["context_consolidation"]["coverage"],
            "context_slot_coverage": capability["context_consolidation"]["slot_coverage"],
            "domain_status": handoff["domain_classification"]["status"],
            "primary_domain_id": handoff["domain_classification"].get("primary_domain_id"),
            "source_units": _jsonl_count(chunks),
            "source_units_artifact_sha256": sha256_file(chunks) if chunks.is_file() else None,
            "artifact_schema_versions": {name: spec.get("schema_version") for name, spec in handoff["artifacts"].items() if spec.get("schema_version")},
            "artifact_hashes": {name: spec["sha256"] for name, spec in handoff["artifacts"].items()},
            "projection": "current",
        })
    return {"schema_version": "system_a_v2_readonly_audit_v1", "current_projection_id": registry.get("projection_id"), "cases": rows}


def _rows(run: Path, handoff: dict, logical_name: str) -> list[dict]:
    spec = handoff.get("artifacts", {}).get(logical_name)
    if not spec:
        return []
    path = run / spec["relative_path"]
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--projection-root", type=Path, default=Path("system_b_outputs/system_a_sync"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = audit(runs_root=args.runs_root, projection_root=args.projection_root)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
