"""Authoritatively re-resolve full-text candidate PMCIDs from PMID keys."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from code_engine.fulltext.candidate_bridge import SOURCE_FILES, normalize_pmcid
from code_engine.fulltext.pmc_id_resolver import resolve_authoritative_pmcid_for_pmid


def _artifacts(path: Path) -> Path:
    return path / "artifacts" if (path / "artifacts").is_dir() else path


def _rows(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _historical_pmcid(row: dict) -> str | None:
    return normalize_pmcid(row.get("original_pmcid") or row.get("pmcid"))


def _collect(inputs: dict[str, list[dict]]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for source_file, rows in inputs.items():
        for index, row in enumerate(rows):
            pmid = str(row.get("pmid") or "").strip()
            key = f"pmid:{pmid}" if pmid else f"row:{source_file}:{index}"
            item = grouped.setdefault(key, {"pmid": pmid, "titles": [], "dois": [], "historical_pmcids": set(), "source_files": []})
            for field, target in (("title", "titles"), ("doi", "dois")):
                value = row.get(field)
                if value and value not in item[target]:
                    item[target].append(value)
            historical = _historical_pmcid(row)
            if historical:
                item["historical_pmcids"].add(historical)
            for value in row.get("historical_pmcids") or []:
                normalized = normalize_pmcid(value)
                if normalized:
                    item["historical_pmcids"].add(normalized)
            if source_file not in item["source_files"]:
                item["source_files"].append(source_file)
    return grouped


def _candidate_status(resolution: dict) -> str:
    canonical = resolution.get("canonical_pmcid_status")
    if canonical == "verified":
        return "verified"
    if canonical == "no_pmc_mapping":
        return "no_pmc_mapping"
    if resolution.get("forward_resolution_status") == "network_unavailable" or resolution.get("reverse_verification_status") == "network_unavailable":
        return "network_unavailable"
    return "rejected"


def _repair_row(row: dict, aggregate: dict, resolution: dict) -> dict:
    status = _candidate_status(resolution)
    verified = resolution.get("resolved_pmcid") if status == "verified" else None
    original = _historical_pmcid(row)
    return {
        **row,
        "original_pmcid": original,
        "historical_pmcids": sorted(aggregate["historical_pmcids"]),
        "verified_pmcid": verified,
        "pmcid": verified,
        "pmcid_verification_status": status,
        "pmcid_resolution_source": resolution.get("resolution_source"),
        "pmcid_observed_pmid": resolution.get("reverse_observed_pmid"),
    }


def repair_fulltext_candidate_pmcids(
    *, source_run: str | Path, output_run: str | Path | None = None,
    output_root: str | Path | None = None, output_suffix: str | None = None,
    network: bool = False, overwrite: bool = False, refresh_cache: bool = False,
    verify_reverse: bool = True,
    authoritative_resolver: Callable = resolve_authoritative_pmcid_for_pmid,
) -> dict:
    source = Path(source_run).resolve(); source_artifacts = _artifacts(source)
    if not source_artifacts.is_dir():
        raise FileNotFoundError(f"source run not found: {source_run}")
    case_id = source.name
    target = Path(output_run) if output_run else Path(output_root or "runs") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_suffix or case_id + '_pmcid_repair'}"
    target = target.resolve()
    if target in {source, source_artifacts}:
        raise ValueError("repair output must differ from source; raw source artifacts are never modified")
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"output run exists: {target}")
        shutil.rmtree(target)
    target_artifacts = target / "artifacts"; target_artifacts.mkdir(parents=True)
    cache = target_artifacts / "cache/pmc_idconv"

    inputs: dict[str, list[dict]] = {}
    for name in SOURCE_FILES:
        if (source_artifacts / name).is_file():
            inputs[name] = _rows(source_artifacts / name)
    plan_path = source_artifacts / "fulltext_escalation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else None
    if isinstance(plan, dict) and isinstance(plan.get("selected"), list):
        inputs[plan_path.name] = plan["selected"]
    if not inputs:
        raise FileNotFoundError("no full-text candidate files found")

    grouped = _collect(inputs); resolutions: dict[str, dict] = {}; audit: list[dict] = []
    for key, aggregate in grouped.items():
        pmid = aggregate["pmid"]
        if pmid:
            resolution = authoritative_resolver(pmid, network_enabled=network, cache_dir=cache,
                verify_reverse=verify_reverse, refresh_cache=refresh_cache)
        else:
            resolution = {"pmid": "", "resolved_pmcid": None, "forward_resolution_status": "error",
                "reverse_observed_pmid": None, "reverse_verification_status": "missing",
                "canonical_pmcid_status": "rejected", "resolution_source": None, "cache_hit": False,
                "reason": "candidate has no PMID; title-only resolution is forbidden"}
        resolutions[key] = resolution
        historical = sorted(aggregate["historical_pmcids"]); resolved = resolution.get("resolved_pmcid")
        canonical = resolution.get("canonical_pmcid_status")
        action = "replaced_historical" if canonical == "verified" and historical and resolved not in historical else "kept_verified" if canonical == "verified" else "kept_missing" if canonical == "no_pmc_mapping" else "blocked"
        audit.append({
            "case_id": case_id, "pmid": pmid or None,
            "title": aggregate["titles"][0] if aggregate["titles"] else None,
            "doi": aggregate["dois"][0] if aggregate["dois"] else None,
            "historical_pmcids": historical, "authoritative_resolved_pmcid": resolved,
            "forward_resolution_status": resolution.get("forward_resolution_status"),
            "reverse_observed_pmid": resolution.get("reverse_observed_pmid"),
            "reverse_verification_status": resolution.get("reverse_verification_status"),
            "canonical_pmcid_status": canonical, "resolution_source": resolution.get("resolution_source"),
            "cache_hit": bool(resolution.get("cache_hit")), "source_files": aggregate["source_files"],
            "action_taken": action, "reason": resolution.get("reason"),
        })

    for name, rows in inputs.items():
        repaired = []
        for index, row in enumerate(rows):
            pmid = str(row.get("pmid") or "").strip(); key = f"pmid:{pmid}" if pmid else f"row:{name}:{index}"
            repaired.append(_repair_row(row, grouped[key], resolutions[key]))
        if name == "fulltext_escalation_plan.json":
            plan["selected"] = repaired
            (target_artifacts / name).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            _write_jsonl(target_artifacts / name, repaired)
            _write_jsonl(target_artifacts / name.replace(".jsonl", ".verified.jsonl"), repaired)
    _write_jsonl(target_artifacts / "pmcid_enrichment_audit.jsonl", audit)

    historical_present = sum(bool(x["historical_pmcids"]) for x in audit)
    summary = {
        "schema_version": "pmcid_authoritative_reresolution_v2", "source_run": str(source), "output_run": str(target),
        "network_enabled": network, "verify_reverse": verify_reverse, "refresh_cache": refresh_cache,
        "candidate_count": len(audit), "historical_pmcid_present_count": historical_present,
        "historical_pmcid_conflict_count": sum(len(x["historical_pmcids"]) > 1 for x in audit),
        "authoritative_lookup_attempt_count": sum(bool(x["pmid"]) for x in audit),
        "authoritative_mapping_found_count": sum(x["forward_resolution_status"] == "resolved" for x in audit),
        "canonical_verified_pmcid_count": sum(x["canonical_pmcid_status"] == "verified" for x in audit),
        "no_pmc_mapping_count": sum(x["canonical_pmcid_status"] == "no_pmc_mapping" for x in audit),
        "network_unavailable_count": sum(x["forward_resolution_status"] == "network_unavailable" or x["reverse_verification_status"] == "network_unavailable" for x in audit),
        "canonical_rejected_count": sum(x["canonical_pmcid_status"] == "rejected" for x in audit),
        "historical_value_replaced_count": sum(x["action_taken"] == "replaced_historical" for x in audit),
        "repaired_files": list(inputs), "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (target / "pmcid_repair_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target_artifacts / "pmcid_repair_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authoritatively re-resolve candidate PMCIDs from PMID keys.")
    parser.add_argument("--source-run", required=True, type=Path)
    output = parser.add_mutually_exclusive_group(); output.add_argument("--output-run", type=Path); output.add_argument("--output-root", type=Path)
    parser.add_argument("--output-suffix"); parser.add_argument("--network", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--verify-reverse", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = repair_fulltext_candidate_pmcids(source_run=args.source_run, output_run=args.output_run,
        output_root=args.output_root, output_suffix=args.output_suffix, network=args.network, overwrite=args.overwrite,
        refresh_cache=args.refresh_cache, verify_reverse=args.verify_reverse)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
